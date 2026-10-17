"""Settings: each field and its default is defined once, here.

config/config.yaml is optional and only overrides what you change; unknown
keys are an error, so a typo fails loudly instead of being ignored. Secrets
never live in YAML: the Flex token and query ID come from the environment,
which is loaded from .env.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError


class ConfigError(Exception):
    """Configuration is missing or malformed."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetrySettings(_Strict):
    attempts: int = 5
    backoff_seconds: float = 30.0  # doubles each retry


class FlexSettings(_Strict):
    query_id: str
    token: SecretStr  # prints as ********** in reprs, logs and errors


class Settings(_Strict):
    database: str = "portfolio.db"  # SQLite file path, or any SQLAlchemy URL
    base_currency: str = "SGD"
    benchmark: str = "VWRA.L"  # Yahoo Finance ticker, converted to base currency
    risk_free_rate: float = 0.0  # annual, for Sharpe / Sortino
    lookback_days: int = 14  # overlap re-fetched on every live pull
    retry: RetrySettings = RetrySettings()
    # from the environment, never from YAML
    account_id: str | None = None
    flex: FlexSettings | None = None

    @property
    def database_url(self) -> str:
        return self.database if "://" in self.database else f"sqlite:///{self.database}"


def load_settings(path: str | Path = "config/config.yaml", *, database: str | None = None) -> Settings:
    # .env in the working directory only (load_dotenv() alone searches upward
    # from this file); variables already in the environment win
    load_dotenv(Path.cwd() / ".env")
    p = Path(path)
    raw = (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: expected a mapping of settings")
    for secret in ("flex", "account_id"):
        if secret in raw:
            raise ConfigError(f"{p}: '{secret}' belongs in .env, not the config file")
    if database:
        raw["database"] = database
    token, query_id = os.environ.get("FLEX_TOKEN"), os.environ.get("FLEX_QUERY_ID")
    if token and query_id:
        raw["flex"] = {"token": token, "query_id": query_id}
    raw["account_id"] = os.environ.get("IBKR_ACCOUNT_ID") or None
    try:
        return Settings(**raw)
    except ValidationError as exc:
        raise ConfigError(f"{p}: {exc}") from exc
