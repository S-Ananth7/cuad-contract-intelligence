import hashlib
import json
import os
from pathlib import Path

CACHE_DIR = Path("evals/cache")


def cache_key(prompt: str) -> str:
    """Same model, same settings, same prompt gives the same key."""
    settings = "|".join(
        [os.environ.get("LLM_MODEL", ""), os.environ.get("LLM_THINKING", ""), os.environ.get("LLM_MAX_TOKENS", "")]
    )
    return hashlib.sha256((settings + "\n" + prompt).encode("utf-8")).hexdigest()


def cached(call, cache_dir=CACHE_DIR, enabled=True):
    """Wrap a model call. A repeat reads the saved reply and costs nothing."""

    def wrapper(prompt):
        if not enabled:
            return call(prompt)
        path = Path(cache_dir) / (cache_key(prompt) + ".json")
        if path.exists():
            wrapper.hits += 1
            return json.loads(path.read_text(encoding="utf-8"))
        result = call(prompt)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
        return result

    wrapper.hits = 0
    return wrapper
