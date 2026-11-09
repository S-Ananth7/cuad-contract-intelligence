import importlib

import pytest

from cuad_ai import settings


def test_require_names_the_missing_setting(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        settings.database_url()


def test_require_treats_an_empty_value_as_missing(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "")
    with pytest.raises(RuntimeError, match="LLM_MODEL is not set"):
        settings.require("LLM_MODEL")


def test_require_returns_the_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    assert settings.database_url() == "postgresql://x"


def test_env_int_uses_default_when_unset_or_empty(monkeypatch):
    monkeypatch.delenv("K", raising=False)
    assert settings.env_int("K", 5) == 5
    monkeypatch.setenv("K", "")
    assert settings.env_int("K", 5) == 5


def test_env_int_reads_a_number(monkeypatch):
    monkeypatch.setenv("K", "10")
    assert settings.env_int("K", 5) == 10


def test_env_int_names_the_bad_setting(monkeypatch):
    monkeypatch.setenv("K", "ten")
    with pytest.raises(RuntimeError, match="K must be a whole number, got 'ten'"):
        settings.env_int("K", 5)


def test_env_float_reads_and_rejects(monkeypatch):
    monkeypatch.setenv("PAUSE_SECONDS", "0.5")
    assert settings.env_float("PAUSE_SECONDS", 0.2) == 0.5
    monkeypatch.setenv("PAUSE_SECONDS", "slow")
    with pytest.raises(RuntimeError, match="PAUSE_SECONDS must be a number"):
        settings.env_float("PAUSE_SECONDS", 0.2)


def test_env_flag(monkeypatch):
    monkeypatch.delenv("NO_CACHE", raising=False)
    assert settings.env_flag("NO_CACHE") is False
    monkeypatch.setenv("NO_CACHE", "1")
    assert settings.env_flag("NO_CACHE") is True


def test_pipeline_rules_are_not_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("RISK_LIMIT", "0.99")
    importlib.reload(settings)
    assert settings.RISK_LIMIT == 0.5
