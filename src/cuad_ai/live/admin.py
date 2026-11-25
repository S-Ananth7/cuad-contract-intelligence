"""Manage clients, who may sign in, API keys and retention.

    python -m cuad_ai live-admin [--hosted] <command>

--hosted uses HOSTED_DATABASE_URL from .env (your Neon database) instead of DATABASE_URL (local).
Commands: add-client, add-user, remove-user, key, list, audit, purge. Run with -h for each command's options.
"""
import argparse
import os

import psycopg
from dotenv import load_dotenv

from cuad_ai.live import store, tenants


def parser():
    p = argparse.ArgumentParser(prog="python -m cuad_ai live-admin", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hosted", action="store_true", help="use HOSTED_DATABASE_URL instead of DATABASE_URL")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("add-client", help="create a client, or replace its settings if it exists")
    c.add_argument("client", help="short id: lowercase letters, digits, - or _")
    c.add_argument("name", help="display name, for example \"Acme Corp\"")
    c.add_argument("--retention", type=int, default=30, help="delete uploads after this many days (default 30)")
    c.add_argument("--daily-cap", type=int, default=None, help="uploads per day (default: the LIVE_DAILY_CAP setting)")

    u = sub.add_parser("add-user", help="allow an email address to sign in for a client")
    u.add_argument("client")
    u.add_argument("email")

    r = sub.add_parser("remove-user", help="stop an email address from signing in")
    r.add_argument("email")

    k = sub.add_parser("key", help="make a new API key for a client (the old one stops working)")
    k.add_argument("client")

    sub.add_parser("list", help="every client with its people and settings")

    a = sub.add_parser("audit", help="who did what for a client, newest first")
    a.add_argument("client")
    a.add_argument("--limit", type=int, default=50)

    sub.add_parser("purge", help="delete uploads older than their client's retention")
    return p


def run(conn, argv, out=print):
    """Run one command against an open connection. Prints with `out`. Raises SystemExit with a clear message."""
    args = parser().parse_args(argv)
    try:
        if args.command == "add-client":
            tenants.create_tenant(conn, args.client, args.name, args.retention, args.daily_cap)
            cap = args.daily_cap if args.daily_cap is not None else "default"
            out(f"client '{args.client}' saved: retention {args.retention} days, daily cap {cap}")
        elif args.command == "add-user":
            tenants.add_user(conn, args.client, args.email)
            out(f"{tenants.clean_email(args.email)} may now sign in for '{args.client}'")
        elif args.command == "remove-user":
            gone = tenants.remove_user(conn, args.email)
            out("removed" if gone else "that email was not on the list")
        elif args.command == "key":
            key = tenants.new_api_key(conn, args.client)
            out(f"New API key for '{args.client}'. It is shown once and cannot be looked up later:")
            out(key)
        elif args.command == "list":
            clients = tenants.list_tenants(conn)
            for t in clients:
                cap = t["daily_cap"] if t["daily_cap"] is not None else "default"
                out(f"{t['id']}  ({t['name']})  retention {t['retention_days']} days, daily cap {cap}")
                for email in tenants.list_users(conn, t["id"]) or ["(no people yet)"]:
                    out(f"    {email}")
            if not clients:
                out("no clients yet: add one with add-client")
        elif args.command == "audit":
            rows = tenants.list_audit(conn, args.client, args.limit)
            for r in rows:
                out(f"{r['at']:%Y-%m-%d %H:%M}  {r['actor']}  {r['action']}  #{r['submission_id'] or '-'}  {r['detail']}")
            if not rows:
                out("no entries")
        elif args.command == "purge":
            out(f"deleted {tenants.purge_expired(conn)} expired upload(s)")
    except (ValueError, LookupError) as error:
        raise SystemExit(f"error: {error}") from None


def main(argv=None):
    import sys

    argv = sys.argv[1:] if argv is None else list(argv)
    hosted = "--hosted" in argv
    load_dotenv()
    name = "HOSTED_DATABASE_URL" if hosted else "DATABASE_URL"
    url = os.environ.get(name)
    if not url:
        raise SystemExit(f"{name} is not set. Put it in .env (see .env.example).")
    try:
        with psycopg.connect(url, connect_timeout=10) as conn:
            store.ensure_schema(conn)
            run(conn, argv)
    except psycopg.OperationalError:
        raise SystemExit(f"could not reach the database in {name}") from None


if __name__ == "__main__":
    main()
