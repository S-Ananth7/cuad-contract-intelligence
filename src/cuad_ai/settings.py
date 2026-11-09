"""Every setting in one place.

Two kinds:
  - Pipeline rules: measured on the validation contracts. Fixed constants, never read
    from the environment, so nobody can tune them by accident (least of all on the test set).
  - Run knobs and secrets: come from the environment (.env), read through the helpers below,
    which say which variable is wrong instead of failing with a bare KeyError.
"""
import os

# ---- pipeline rules ----
HEADER_CLAUSES = frozenset({"Document Name", "Parties", "Agreement Date", "Effective Date"})
HEADER_CHUNKS = 4  # these clauses are found in the first chunks of a contract
RRF_K = 60  # reciprocal rank fusion constant
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

RISK_LIMIT = 0.5  # clauses above this false-alarm rate always go to review
PRIOR_WEIGHT = 3  # how strongly a rare clause is pulled toward the overall rate
ALWAYS_ACCEPT = frozenset({"Document Name", "Agreement Date"})

N_EXAMPLES = 3  # lawyer examples shown to judge 2
EXAMPLE_CHARS = 400  # characters kept from each example


# ---- environment helpers ----
def require(name):
    """A setting the program cannot run without."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


def env_text(name, default):
    return os.environ.get(name) or default


def env_int(name, default):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a whole number, got {raw!r}") from None


def env_float(name, default):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a number, got {raw!r}") from None


def env_flag(name):
    """True when the variable is set to anything non-empty."""
    return bool(os.environ.get(name))


def database_url():
    return require("DATABASE_URL")
