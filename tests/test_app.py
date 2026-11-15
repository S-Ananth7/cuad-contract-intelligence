from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def test_page_runs_and_shows_the_final_numbers():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert len(at.tabs) == 3
    shown = {m.label: m.value for m in at.metric}
    assert shown["Precision"] == "0.757"
    assert shown["Recall"] == "0.916"
