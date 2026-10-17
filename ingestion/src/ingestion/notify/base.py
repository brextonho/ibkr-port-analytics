"""Notifier protocol (PRD §9): an observer, never a participant.

The send is always wrapped by the caller — a dead SMTP server must not mark
a successful ingestion as failed.
"""
from __future__ import annotations

from typing import Protocol


class Notifier(Protocol):
    def send(self, subject: str, body: str) -> None: ...
