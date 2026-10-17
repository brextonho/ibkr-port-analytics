"""No-op notifier for local runs and tests."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class NullNotifier:
    def send(self, subject: str, body: str) -> None:
        logger.info("notification suppressed (backend=none): %s", subject)
