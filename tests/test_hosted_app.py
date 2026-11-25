import threading
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGE = str(Path(__file__).resolve().parents[1] / "deploy" / "live" / "streamlit_app.py")


def no_worker():
    return "live-worker" not in [t.name for t in threading.enumerate()]


def test_without_sign_in_secrets_the_page_stays_closed():
    page = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not page.exception
    assert "not set up" in page.error[0].value
    assert not page.button and not page.text_input  # no way in
    assert "tenant" not in page.session_state and no_worker()


def test_with_sign_in_set_up_the_page_offers_the_providers_and_nothing_else():
    page = AppTest.from_file(PAGE, default_timeout=30)
    page.secrets["auth"] = {"redirect_uri": "http://localhost/oauth2callback", "cookie_secret": "x"}
    page.run()
    assert not page.exception
    assert [b.label for b in page.button] == ["Sign in with Google", "Sign in with Microsoft"]
    assert not page.text_input  # no code box to guess at
    assert "tenant" not in page.session_state and no_worker()
