"""One command for every pipeline stage: python -m cuad_ai <stage> [arguments]."""
import importlib
import sys

# stage name -> (module, one line of help). Modules load only when their stage runs, so --help is instant.
STAGES = {
    "extract": ("cuad_ai.pipeline.extraction", "ask the model about every clause (SET, K, LIMIT, OFFSET from the environment)"),
    "gate": ("cuad_ai.pipeline.gate", "<run folder>/report.json: how close each quote is to each clause's lawyer examples"),
    "route": ("cuad_ai.pipeline.route", "<run folder> [risk table]: split answers into accept and review"),
    "judge1": ("cuad_ai.pipeline.judge_quote", "<run folder>: judge 1 sees the quote and the clause question"),
    "judge2": ("cuad_ai.pipeline.judge_examples", "<run folder>: judge 2 also sees 3 lawyer examples"),
    "finalize": ("cuad_ai.pipeline.finalize", "<run folder>: accept, reject or queue every question and print the scores"),
    "freeze-risk": ("cuad_ai.pipeline.risk", "<validation run folders...>: write evals/risk_table.json"),
    "pipeline": ("cuad_ai.pipeline.run_all", "[run folder]: every stage in order (extracts first when no folder is given)"),
}


def usage():
    lines = ["usage: python -m cuad_ai <stage> [arguments]", "", "stages:"]
    lines += [f"  {name:<12}{text}" for name, (_, text) in STAGES.items()]
    return "\n".join(lines)


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if not args or args[0] in ("-h", "--help"):
        print(usage())
        return 0
    name, rest = args[0], args[1:]
    if name not in STAGES:
        raise SystemExit(f"unknown stage: {name}\n\n{usage()}")
    importlib.import_module(STAGES[name][0]).main(rest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
