import shutil
from pathlib import Path

for path in sorted(Path("evals/reports").glob("*.json")):
    stamp = path.stem[-15:]
    folder = Path("evals/runs") / f"{stamp}_legacy_{path.stem[:-16]}"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(folder / "report.json"))
    print("moved:", path.name, "->", folder.name)
