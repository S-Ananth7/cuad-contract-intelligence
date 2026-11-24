"""Limits for the live review. Read when used, not when imported, so tests and deployments can change them."""
from cuad_ai.settings import env_int, env_text

SQL_PATH = "sql/live.sql"


def max_chars():
    return env_int("LIVE_MAX_CHARS", 400_000)  # the longest CUAD contract is about 300k


def daily_cap():
    return env_int("LIVE_DAILY_CAP", 20)  # uploads accepted per rolling 24 hours, all users together


def workers():
    return max(1, env_int("LIVE_WORKERS", 4))  # questions asked in parallel inside one upload


def token_cap():
    return env_int("LIVE_TOKEN_CAP", 400_000)  # a typical contract uses about 100k; this stops a runaway


def stale_minutes():
    return env_int("LIVE_STALE_MINUTES", 10)  # a running job with no heartbeat this long is put back in the queue


def access_key():
    """The key callers must send (header X-API-Key) to use the live endpoints. Unset means they are switched off:
    the live review spends model tokens, so it is never open by default."""
    return env_text("LIVE_API_KEY", "")


def enabled():
    return bool(access_key())
