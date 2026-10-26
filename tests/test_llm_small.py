from types import SimpleNamespace

import pytest

from cuad_ai.llm import call_model


class FakeError(Exception):

    def __init__(self, status_code):
        self.status_code = status_code


def fake_response(text="hi"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class FakeClient:

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def no_sleep(seconds):
    pass


def test_success_returns_text_and_tokens(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    result = call_model("prompt", client=FakeClient([fake_response("hi")]), sleep=no_sleep)
    assert (result["text"], result["tokens_in"], result["tokens_out"], result["attempts"]) == ("hi", 10, 5, 1)


def test_retries_busy_line_then_succeeds(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    client = FakeClient([FakeError(429), FakeError(503), fake_response()])
    result = call_model("prompt", client=client, sleep=no_sleep)
    assert result["attempts"] == 3 and client.calls == 3


def test_does_not_retry_bad_key(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    client = FakeClient([FakeError(401)])
    with pytest.raises(FakeError):
        call_model("prompt", client=client, sleep=no_sleep)
    assert client.calls == 1


def test_gives_up_after_four_attempts(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    client = FakeClient([FakeError(429)] * 4)
    with pytest.raises(FakeError):
        call_model("prompt", client=client, sleep=no_sleep)
    assert client.calls == 4
