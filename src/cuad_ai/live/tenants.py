"""Clients, who may sign in for them, API keys, retention and the audit trail.

A client (tenant) owns uploads. A person belongs to one client by email. Everything the page or the API shows is
scoped by the client id that comes from the sign-in or the API key, never from anything the person types.
"""
import hashlib
import re
import secrets

from cuad_ai.live import config

TENANT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
LEGACY = "legacy"


def clean_email(email):
    return (email or "").strip().lower()


def create_tenant(conn, tenant, name, retention_days=30, daily_cap=None):
    if not TENANT_ID.match(tenant or "") or tenant == LEGACY:
        raise ValueError("client id: 1-40 characters, lowercase letters, digits, - or _, and not 'legacy'")
    if retention_days < 1:
        raise ValueError("retention must be at least 1 day")
    conn.execute(
        "INSERT INTO live_tenants (id, name, retention_days, daily_cap) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, retention_days = EXCLUDED.retention_days, "
        "daily_cap = EXCLUDED.daily_cap", (tenant, name.strip() or tenant, retention_days, daily_cap))
    conn.commit()


def get_tenant(conn, tenant):
    row = conn.execute("SELECT id, name, retention_days, daily_cap FROM live_tenants WHERE id = %s",
                       (tenant,)).fetchone()
    return dict(zip(("id", "name", "retention_days", "daily_cap"), row)) if row else None


def list_tenants(conn):
    rows = conn.execute("SELECT id, name, retention_days, daily_cap FROM live_tenants ORDER BY id").fetchall()
    return [dict(zip(("id", "name", "retention_days", "daily_cap"), row)) for row in rows]


def add_user(conn, tenant, email):
    """Allow an email to sign in for this client. An email that belongs to another client is refused, not moved."""
    email = clean_email(email)
    if "@" not in email:
        raise ValueError("that does not look like an email address")
    if get_tenant(conn, tenant) is None:
        raise LookupError(f"no such client: {tenant}")
    row = conn.execute(
        "INSERT INTO live_users (email, tenant) VALUES (%s, %s) ON CONFLICT (email) DO NOTHING RETURNING email",
        (email, tenant)).fetchone()
    if row is None:
        owner = conn.execute("SELECT tenant FROM live_users WHERE email = %s", (email,)).fetchone()[0]
        if owner != tenant:
            raise ValueError("that email already belongs to another client; remove it there first")
    conn.commit()


def remove_user(conn, email):
    row = conn.execute("DELETE FROM live_users WHERE email = %s RETURNING email", (clean_email(email),)).fetchone()
    conn.commit()
    return row is not None


def list_users(conn, tenant):
    return [r[0] for r in conn.execute("SELECT email FROM live_users WHERE tenant = %s ORDER BY email",
                                       (tenant,)).fetchall()]


def tenant_for_email(conn, email):
    """The client this email may use, or None. This is the whole sign-in allow-list check."""
    row = conn.execute("SELECT tenant FROM live_users WHERE email = %s", (clean_email(email),)).fetchone()
    return row[0] if row else None


def _hash(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def new_api_key(conn, tenant):
    """Make (or replace) the client's API key. The key is returned once and only its hash is stored."""
    if get_tenant(conn, tenant) is None:
        raise LookupError(f"no such client: {tenant}")
    key = "lk_" + secrets.token_urlsafe(32)
    conn.execute("UPDATE live_tenants SET api_key_sha256 = %s WHERE id = %s", (_hash(key), tenant))
    conn.commit()
    return key


def tenant_for_key(conn, key):
    """The client an API key belongs to, or None. Looks up the hash, so the key itself is never stored."""
    if not key:
        return None
    row = conn.execute("SELECT id FROM live_tenants WHERE api_key_sha256 = %s", (_hash(key),)).fetchone()
    return row[0] if row else None


def audit(conn, tenant, actor, action, submission_id=None, detail=""):
    conn.execute("INSERT INTO live_audit (tenant, actor, action, submission_id, detail) VALUES (%s, %s, %s, %s, %s)",
                 (tenant, actor[:200], action, submission_id, detail[:300]))
    conn.commit()


def list_audit(conn, tenant, limit=100):
    rows = conn.execute("SELECT at, actor, action, submission_id, detail FROM live_audit "
                        "WHERE tenant = %s ORDER BY id DESC LIMIT %s", (tenant, limit)).fetchall()
    return [dict(zip(("at", "actor", "action", "submission_id", "detail"), row)) for row in rows]


def purge_expired(conn):
    """Delete uploads older than their client's retention. 'legacy' uploads use the default. Returns how many."""
    rows = conn.execute(
        "DELETE FROM live_submissions s WHERE s.created_at < now() - make_interval(days => COALESCE("
        "(SELECT t.retention_days FROM live_tenants t WHERE t.id = s.tenant), %s)) "
        "AND s.status <> 'running' RETURNING s.id, s.tenant, s.filename", (config.retention_days(),)).fetchall()
    for sid, tenant, filename in rows:
        conn.execute("INSERT INTO live_audit (tenant, actor, action, submission_id, detail) VALUES (%s, 'system', "
                     "'purged', %s, %s)", (tenant, sid, filename[:300]))
    conn.commit()
    return len(rows)
