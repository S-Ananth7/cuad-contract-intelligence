r"""Browse the full CUAD file from the terminal. No size limit. Nothing is uploaded.

  python scripts\browse_cuad.py                      list contract titles (first 40)
  python scripts\browse_cuad.py SONUS                find titles that contain SONUS
  python scripts\browse_cuad.py SONUS 1              open match number 1: all 41 clauses
  python scripts\browse_cuad.py SONUS 1 "Governing Law"   show that clause's full highlights
"""
import sys

from cuad_ai.loader import load_contracts


def main():
    args = sys.argv[1:]
    contracts = load_contracts()
    if not args:
        print(len(contracts), "contracts. First 40:")
        for number, c in enumerate(contracts[:40], start=1):
            print(f"{number:>3}  {c['title'][:95]}")
        return
    matches = [c for c in contracts if args[0].lower() in c["title"].lower()]
    if len(args) == 1:
        print(len(matches), "match(es):")
        for number, c in enumerate(matches[:40], start=1):
            print(f"{number:>3}  {c['title'][:95]}")
        return
    contract = matches[int(args[1]) - 1]
    para = contract["paragraphs"][0]
    if len(args) == 2:
        print("TITLE:", contract["title"])
        print("CONTRACT LENGTH:", len(para["context"]), "characters")
        print(f"{'CLAUSE':<36}{'PRESENT':<9}HIGHLIGHTS")
        for qa in para["qas"]:
            name = qa["id"].split("__")[-1]
            print(f"{name:<36}{'yes' if qa['answers'] else '-':<9}{len(qa['answers'])}")
        return
    clause = args[2]
    qa = next(q for q in para["qas"] if q["id"].endswith("__" + clause))
    print("CLAUSE:", clause, "| present:", bool(qa["answers"]))
    print("QUESTION:", qa["question"])
    for number, a in enumerate(qa["answers"], start=1):
        print(f"\nHIGHLIGHT {number} (starts at character {a['answer_start']}):")
        print(" ".join(a["text"].split()))


main()
