"""Limits for the live review. Read when used, not when imported, so tests and deployments can change them."""
from cuad_ai.settings import env_int, env_text

SQL_PATH = "sql/live.sql"


def max_chars():
    return env_int("LIVE_MAX_CHARS", 400_000)  # the longest CUAD contract is about 300k


def max_file_mb():
    return env_int("LIVE_MAX_FILE_MB", 10)  # size of the uploaded file itself, before its text is read out


def max_pages():
    return env_int("LIVE_MAX_PAGES", 300)  # PDF pages


def daily_cap():
    return env_int("LIVE_DAILY_CAP", 20)  # uploads one client may make per rolling 24 hours (a client can override)


def global_cap():
    return env_int("LIVE_GLOBAL_DAILY_CAP", 100)  # uploads across all clients per 24 hours: protects the model bill


def retention_days():
    return env_int("LIVE_RETENTION_DAYS", 30)  # default for a client with no setting of its own


def workers():
    return max(1, env_int("LIVE_WORKERS", 4))  # questions asked in parallel inside one upload


def token_cap():
    return env_int("LIVE_TOKEN_CAP", 400_000)  # a typical contract uses about 100k; this stops a runaway


def stale_minutes():
    return env_int("LIVE_STALE_MINUTES", 10)  # a running job with no heartbeat this long is put back in the queue


def enabled():
    """Whether the HTTP endpoints exist. Off unless LIVE_API is set to 1/true/yes/on: the live review spends model
    tokens, so it is never open by default. Callers then need a client's API key (made with `cuad live-admin key`)."""
    return env_text("LIVE_API", "").strip().lower() in ("1", "true", "yes", "on")
