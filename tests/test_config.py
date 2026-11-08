from __future__ import annotations

from pathlib import Path

import pytest

from portfolio.config import ConfigError, load_settings


@pytest.fixture(autouse=True)
def no_env(monkeypatch, tmp_path):
    # isolate from the developer's real .env and environment
    monkeypatch.chdir(tmp_path)
    for var in ("FLEX_TOKEN", "FLEX_QUERY_ID", "IBKR_ACCOUNT_ID"):
        monkeypatch.setenv(var, "")  # records the original, so teardown restores it
        monkeypatch.delenv(var)


def _write(tmp_path, content: str):
    path = tmp_path / "config.yaml"
    path.write_text(content)
    return path


def test_missing_file_means_all_defaults(tmp_path):
    s = load_settings(tmp_path / "absent.yaml")
    assert s.database_url == "sqlite:///portfolio.db"
    assert s.benchmark == "VWRA.L"
    assert s.lookback_days == 14
    assert s.retry.attempts == 5
    assert s.flex is None


def test_file_overrides_only_what_it_sets(tmp_path):
    s = load_settings(_write(tmp_path, "benchmark: CSPX.L\nretry:\n  attempts: 2\n"))
    assert s.benchmark == "CSPX.L"
    assert s.retry.attempts == 2
    assert s.retry.backoff_seconds == 30.0


def test_unknown_key_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="benchmrk"):
        load_settings(_write(tmp_path, "benchmrk: CSPX.L\n"))


def test_secrets_in_the_file_are_refused(tmp_path):
    with pytest.raises(ConfigError, match=".env"):
        load_settings(_write(tmp_path, "flex:\n  token: abc\n"))


def test_flex_secrets_come_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FLEX_TOKEN", "secret")
    monkeypatch.setenv("FLEX_QUERY_ID", "12345")
    s = load_settings(tmp_path / "absent.yaml")
    assert s.flex is not None and s.flex.token.get_secret_value() == "secret" and s.flex.query_id == "12345"
    assert "secret" not in repr(s) and "secret" not in str(s)  # never printed by accident


def test_dotenv_file_is_loaded(tmp_path):
    (tmp_path / ".env").write_text("FLEX_TOKEN=fromfile\nFLEX_QUERY_ID=1\n")
    assert load_settings(tmp_path / "absent.yaml").flex.token.get_secret_value() == "fromfile"


def test_database_override_and_bare_paths(tmp_path):
    s = load_settings(_write(tmp_path, "database: mine.db\n"), database="other.db")
    assert s.database_url == "sqlite:///other.db"
    assert load_settings(tmp_path / "x.yaml", database="sqlite://").database_url == "sqlite://"


def test_example_config_is_valid():
    example = Path(__file__).resolve().parents[1] / "config" / "config.example.yaml"
    assert load_settings(example).database == "portfolio.db"
