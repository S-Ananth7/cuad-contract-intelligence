"""The official test set stays locked unless the caller explicitly confirms."""
import pytest

from cuad_ai.pipeline import extraction as run_rag


@pytest.fixture
def main_without_data(monkeypatch):
    """main() reads the dataset first; a fresh clone has none, so stub that part out."""
    monkeypatch.setattr(run_rag, "load_contracts", lambda: [])
    monkeypatch.setattr(run_rag, "clause_questions", lambda contracts: {})
    monkeypatch.setattr(run_rag, "SET", "test")
    monkeypatch.delenv("CONFIRM_TEST", raising=False)


def test_test_set_refuses_to_run_without_confirmation(main_without_data):
    with pytest.raises(SystemExit, match="CONFIRM_TEST=yes"):
        run_rag.main()


@pytest.mark.parametrize("value", ["1", "true", "YES", ""])
def test_only_the_exact_word_yes_counts_as_confirmation(main_without_data, monkeypatch, value):
    monkeypatch.setenv("CONFIRM_TEST", value)
    with pytest.raises(SystemExit, match="CONFIRM_TEST=yes"):
        run_rag.main()
