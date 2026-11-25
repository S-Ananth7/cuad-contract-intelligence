import threading
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGE = str(Path(__file__).resolve().parents[1] / "deploy" / "live" / "streamlit_app.py")


def test_without_an_access_code_secret_the_page_stays_closed(monkeypatch):
    monkeypatch.delenv("LIVE_ACCESS_CODE", raising=False)
    page = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not page.exception
    assert "LIVE_ACCESS_CODE" in page.error[0].value
    assert not page.text_input  # nothing to type into: there is no way in


def test_a_wrong_code_is_refused_and_does_not_start_the_worker(monkeypatch):
    monkeypatch.setenv("LIVE_ACCESS_CODE", "right-code")
    page = AppTest.from_file(PAGE, default_timeout=30).run()
    page.text_input[0].set_value("wrong").run()
    assert not page.exception
    assert "not right" in page.error[0].value
    assert "granted" not in page.session_state
    assert "live-worker" not in [t.name for t in threading.enumerate()]
