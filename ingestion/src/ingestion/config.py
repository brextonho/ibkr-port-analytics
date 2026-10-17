"""Typed settings loaded from YAML with ${VAR} environment interpolation (PRD §8).

Secrets never live in the file — the YAML references environment variables and
this loader resolves them. Sections whose secrets are absent can be tolerated
when the run doesn't need them (offline --xml ingestion needs no Flex token).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ENV_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

DEFAULT_RETRYABLE_CODES = (1001, 1004, 1005, 1006, 1007, 1008, 1009, 1018, 1019, 1021)
DEFAULT_FATAL_CODES = (1003, 1010, 1011, 1012, 1013, 1014, 1015, 1016, 1017, 1020)


class ConfigError(Exception):
    """Raised when configuration is missing or malformed."""


def _interpolate(value: Any) -> Any:
    """Recursively substitute ${VAR} with environment values; raise if unset."""
    if isinstance(value, str):

        def _replace(match: re.Match[str]) -> str:
            var = match.group(1)
            if var not in os.environ:
                raise ConfigError(
                    f"config references undefined environment variable {var!r}"
                )
            return os.environ[var]

        return _ENV_VAR.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


@dataclass(frozen=True)
class RetrySettings:
    attempts: int = 5
    backoff_seconds: float = 30.0
    fatal_codes: tuple[int, ...] = DEFAULT_FATAL_CODES


@dataclass(frozen=True)
class IngestionSettings:
    cron: str = "0 21 * * FRI"
    lookback_days: int = 14
    max_lookback_days: int = 365
    retry: RetrySettings = field(default_factory=RetrySettings)


@dataclass(frozen=True)
class FlexSettings:
    query_id: str
    token: str
    base_url: str = (
        "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
    )
    version: int = 3
    user_agent: str = "ibkr-portfolio/0.1"


@dataclass(frozen=True)
class BenchmarkSettings:
    ticker: str = "VWRA.L"
    source: str = "yfinance"
    convert_to_base: bool = True


@dataclass(frozen=True)
class PortfolioSettings:
    account_id: str | None = None
    base_currency: str = "SGD"
    benchmark: BenchmarkSettings = field(default_factory=BenchmarkSettings)


@dataclass(frozen=True)
class MetricsSettings:
    grain: str = "daily"
    flow_convention: str = "end_of_day"  # end_of_day | beginning_of_day (§7.3)
    annualization_factor: int = 252
    rolling_window_days: int = 63
    risk_free_rate: float = 0.0
    twr_validation_tolerance_bps: float = 5.0


@dataclass(frozen=True)
class SmtpSettings:
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""


@dataclass(frozen=True)
class NotificationSettings:
    enabled: bool = False
    backend: str = "none"  # smtp | slack | none
    on_success: bool = True
    on_failure: bool = True
    to: str = ""
    smtp: SmtpSettings = field(default_factory=SmtpSettings)


@dataclass(frozen=True)
class EnrichmentSettings:
    security_tags_file: str = "config/security_tags.yaml"
    position_notes_file: str = "config/position_notes.yaml"


@dataclass(frozen=True)
class Settings:
    ingestion: IngestionSettings
    flex: FlexSettings | None
    database_url: str
    portfolio: PortfolioSettings
    metrics: MetricsSettings
    notifications: NotificationSettings
    enrichment: EnrichmentSettings = field(default_factory=EnrichmentSettings)


def load_settings(
    path: str | Path,
    *,
    database_url: str | None = None,
    require_flex: bool = True,
) -> Settings:
    raw = yaml.safe_load(Path(path).read_text()) or {}

    ing_raw = _interpolate(raw.get("ingestion") or {})
    retry_raw = ing_raw.get("retry") or {}
    ingestion = IngestionSettings(
        cron=ing_raw.get("cron", IngestionSettings.cron),
        lookback_days=int(ing_raw.get("lookback_days", IngestionSettings.lookback_days)),
        max_lookback_days=int(
            ing_raw.get("max_lookback_days", IngestionSettings.max_lookback_days)
        ),
        retry=RetrySettings(
            attempts=int(retry_raw.get("attempts", RetrySettings.attempts)),
            backoff_seconds=float(
                retry_raw.get("backoff_seconds", RetrySettings.backoff_seconds)
            ),
            fatal_codes=tuple(retry_raw.get("fatal_codes", DEFAULT_FATAL_CODES)),
        ),
    )

    flex: FlexSettings | None = None
    flex_raw = raw.get("flex") or {}
    if flex_raw:
        try:
            f = _interpolate(flex_raw)
            flex = FlexSettings(
                query_id=str(f["query_id"]),
                token=str(f["token"]),
                base_url=f.get("base_url", FlexSettings.base_url),
                version=int(f.get("version", FlexSettings.version)),
                user_agent=f.get("user_agent", FlexSettings.user_agent),
            )
        except (ConfigError, KeyError):
            if require_flex:
                raise
            flex = None
    elif require_flex:
        raise ConfigError("config has no 'flex' section but a live fetch was requested")

    if database_url is None:
        db_raw = (raw.get("database") or {}).get("url")
        if db_raw is not None:
            database_url = str(_interpolate(db_raw))
    if not database_url:
        raise ConfigError("no database URL: set database.url in config or pass --db")

    pf_raw = raw.get("portfolio") or {}
    try:
        account_id = _interpolate(pf_raw.get("account_id"))
    except ConfigError:
        account_id = None  # only needed as a sanity check on live pulls
    bm_raw = pf_raw.get("benchmark") or {}
    portfolio = PortfolioSettings(
        account_id=account_id,
        base_currency=pf_raw.get("base_currency", PortfolioSettings.base_currency),
        benchmark=BenchmarkSettings(
            ticker=bm_raw.get("ticker", BenchmarkSettings.ticker),
            source=bm_raw.get("source", BenchmarkSettings.source),
            convert_to_base=bool(
                bm_raw.get("convert_to_base", BenchmarkSettings.convert_to_base)
            ),
        ),
    )

    m_raw = _interpolate(raw.get("metrics") or {})
    metrics = MetricsSettings(
        grain=m_raw.get("grain", MetricsSettings.grain),
        flow_convention=m_raw.get("flow_convention", MetricsSettings.flow_convention),
        annualization_factor=int(
            m_raw.get("annualization_factor", MetricsSettings.annualization_factor)
        ),
        rolling_window_days=int(
            m_raw.get("rolling_window_days", MetricsSettings.rolling_window_days)
        ),
        risk_free_rate=float(m_raw.get("risk_free_rate", MetricsSettings.risk_free_rate)),
        twr_validation_tolerance_bps=float(
            m_raw.get(
                "twr_validation_tolerance_bps",
                MetricsSettings.twr_validation_tolerance_bps,
            )
        ),
    )

    e_raw = _interpolate(raw.get("enrichment") or {})
    enrichment = EnrichmentSettings(
        security_tags_file=e_raw.get(
            "security_tags_file", EnrichmentSettings.security_tags_file
        ),
        position_notes_file=e_raw.get(
            "position_notes_file", EnrichmentSettings.position_notes_file
        ),
    )

    n_raw = raw.get("notifications") or {}
    enabled = bool(n_raw.get("enabled", False))
    backend = n_raw.get("backend", "none")
    try:
        n = _interpolate(n_raw)
    except ConfigError:
        if enabled and backend == "smtp":
            raise
        n = {"enabled": False, "backend": "none"}
    smtp_raw = n.get("smtp") or {}
    notifications = NotificationSettings(
        enabled=bool(n.get("enabled", False)),
        backend=n.get("backend", "none"),
        on_success=bool(n.get("on_success", True)),
        on_failure=bool(n.get("on_failure", True)),
        to=n.get("to", ""),
        smtp=SmtpSettings(
            host=smtp_raw.get("host", ""),
            port=int(smtp_raw.get("port", 587)),
            username=smtp_raw.get("username", ""),
            password=smtp_raw.get("password", ""),
        ),
    )

    return Settings(
        ingestion=ingestion,
        flex=flex,
        database_url=database_url,
        portfolio=portfolio,
        metrics=metrics,
        notifications=notifications,
        enrichment=enrichment,
    )
