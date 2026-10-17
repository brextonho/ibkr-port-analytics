"""Notifier selection (PRD §9.1): adding a backend = add a class, change one YAML key."""
from __future__ import annotations

from ingestion.config import ConfigError, NotificationSettings
from ingestion.notify.base import Notifier
from ingestion.notify.null import NullNotifier
from ingestion.notify.smtp import SMTPNotifier


def build_notifier(settings: NotificationSettings) -> Notifier:
    if not settings.enabled or settings.backend == "none":
        return NullNotifier()
    if settings.backend == "smtp":
        return SMTPNotifier(settings.smtp, settings.to)
    raise ConfigError(f"unknown notification backend {settings.backend!r}")
