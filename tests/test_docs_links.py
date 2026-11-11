"""Every relative link in the README and the documents must point at a file that exists."""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
LINK = re.compile(r"\]\(([^)\s]+)\)")


def markdown_files():
    return [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")), *sorted((ROOT / "notes").glob("*.md")),
            ROOT / "evals" / "final_test" / "README.md"]


def broken_links(path):
    broken = []
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not (path.parent / target.split("#")[0]).exists():
            broken.append(target)
    return broken


def test_no_relative_link_is_broken():
    problems = {str(p.relative_to(ROOT)): links for p in markdown_files() if (links := broken_links(p))}
    assert not problems, problems
