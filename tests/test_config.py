from __future__ import annotations

import textwrap

import pytest

from ingestion.config import ConfigError, load_settings

MINIMAL = textwrap.dedent(
    """
    flex:
      query_id: ${FLEX_QUERY_ID}
      token: ${FLEX_TOKEN}
    database:
      url: sqlite:///test.db
    portfolio:
      base_currency: SGD
    """
)


def _write(tmp_path, content):
    path = tmp_path / "config.yaml"
    path.write_text(content)
    return path


def test_env_interpolation(tmp_path, monkeypatch):
    monkeypatch.setenv("FLEX_QUERY_ID", "12345")
    monkeypatch.setenv("FLEX_TOKEN", "secret")
    settings = load_settings(_write(tmp_path, MINIMAL))
    assert settings.flex is not None
    assert settings.flex.query_id == "12345"
    assert settings.flex.token == "secret"
    assert settings.database_url == "sqlite:///test.db"


def test_missing_env_var_raises_when_flex_required(tmp_path, monkeypatch):
    monkeypatch.delenv("FLEX_TOKEN", raising=False)
    monkeypatch.setenv("FLEX_QUERY_ID", "12345")
    with pytest.raises(ConfigError):
        load_settings(_write(tmp_path, MINIMAL))


def test_offline_mode_tolerates_missing_flex_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("FLEX_TOKEN", raising=False)
    monkeypatch.delenv("FLEX_QUERY_ID", raising=False)
    settings = load_settings(_write(tmp_path, MINIMAL), require_flex=False)
    assert settings.flex is None
    assert settings.portfolio.base_currency == "SGD"


def test_database_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("FLEX_QUERY_ID", "1")
    monkeypatch.setenv("FLEX_TOKEN", "t")
    settings = load_settings(_write(tmp_path, MINIMAL), database_url="sqlite://")
    assert settings.database_url == "sqlite://"


def test_no_database_anywhere_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_settings(_write(tmp_path, "portfolio:\n  base_currency: SGD\n"), require_flex=False)


def test_defaults_match_prd(tmp_path):
    settings = load_settings(
        _write(tmp_path, "database:\n  url: sqlite://\n"), require_flex=False
    )
    assert settings.ingestion.lookback_days == 14
    assert settings.ingestion.max_lookback_days == 365
    assert settings.ingestion.retry.attempts == 5
    assert settings.metrics.flow_convention == "end_of_day"
    assert settings.metrics.annualization_factor == 252
    assert settings.notifications.backend == "none"
