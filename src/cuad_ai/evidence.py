"""Put each answer's quotes next to the passages the lawyers marked, for the demo's evidence view."""
from __future__ import annotations

import gzip
import json


def lawyer_passages(cuad):
    """{(title, clause): [passage, ...]} from the CUAD file, duplicates removed, order kept."""
    out = {}
    for contract in cuad["data"]:
        for paragraph in contract["paragraphs"]:
            for qa in paragraph["qas"]:
                clause = qa["id"].rsplit("__", 1)[-1]
                seen = out.setdefault((contract["title"], clause), [])
                for answer in qa["answers"]:
                    if answer["text"] not in seen:
                        seen.append(answer["text"])
    return out


def build_evidence(decisions, report_rows, cuad):
    """{title: {clause: {"quotes": [...], "gold": [...]}}} for every answer worth comparing.

    An answer is left out only when nothing was found and the lawyers marked nothing either.
    """
    gold = lawyer_passages(cuad)
    quotes = {(r["title"], r["clause"]): r["quotes"] or [] for r in report_rows}
    evidence = {}
    for row in decisions:
        key = (row["title"], row["clause"])
        passages = gold.get(key, [])
        if row["decision"] == "not_found" and not passages:
            continue
        evidence.setdefault(row["title"], {})[row["clause"]] = {"quotes": quotes.get(key, []), "gold": passages}
    return evidence


def save_evidence(evidence, path):
    """Write compact gzip JSON. mtime=0 keeps the file identical when the content is identical."""
    data = json.dumps(evidence, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as out:
        out.write(data)
