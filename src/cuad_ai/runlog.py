import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path("evals/runs")
RESULTS_PATH = Path("evals/results.md")
HEADER = (
    "| run id | n | recall | recall incl. errors | precision | invented | errors | avg s | commit | thinking |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
)


def new_run_id(label: str) -> str:
    """Unique id for one run: a timestamp plus a safe label. Never reused."""
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in label)
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + safe


def run_info(prompt_text: str="", uses_model: bool=True) -> dict:
    """The recipe for a run, so a number can be repeated and trusted later."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        commit = "unknown"
    return {
        "git_commit": commit,
        "thinking": os.environ.get("LLM_THINKING", "default") if uses_model else "n/a",
        "max_tokens": os.environ.get("LLM_MAX_TOKENS", "2000") if uses_model else "n/a",
        "prompt_hash": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:8] if prompt_text else None,
    }


def write_report(run_id, meta, summary, rows, runs_dir=RUNS_DIR) -> Path:
    """Write this run's report into its own folder. Calling it again for the same run updates that run only."""
    folder = Path(runs_dir) / run_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "report.json"
    path.write_text(json.dumps({"meta": meta, "summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    return path


def log_run(run_id, summary, info, path=RESULTS_PATH) -> None:
    """Append one line for a finished run. This line stays in Git."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    if not file.exists():
        file.write_text(HEADER, encoding="utf-8")
    cells = [
        run_id, summary["contracts"], summary["recall"], summary["recall_errors_as_misses"],
        summary["precision"], summary["invented_quotes"], summary["errors"], summary["avg_seconds"],
        info["git_commit"], info["thinking"],
    ]
    with file.open("a", encoding="utf-8") as handle:
        handle.write("| " + " | ".join(str(cell) for cell in cells) + " |\n")


def find_run(key: str, runs_dir=RUNS_DIR) -> Path:
    """The latest run whose id contains `key`."""
    folder = Path(runs_dir)
    matches = sorted(p for p in folder.iterdir() if p.is_dir() and key in p.name) if folder.exists() else []
    if not matches:
        raise FileNotFoundError(f"no run matches: {key}")
    return matches[-1]


def load_report(key: str, runs_dir=RUNS_DIR) -> dict:
    return json.loads((find_run(key, runs_dir) / "report.json").read_text(encoding="utf-8"))
