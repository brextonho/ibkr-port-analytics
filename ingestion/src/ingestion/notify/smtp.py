"""SMTP notifier (PRD §9). Body is the run summary, not \"done\"."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ingestion.config import SmtpSettings


class SMTPNotifier:
    def __init__(self, settings: SmtpSettings, to: str):
        self._settings = settings
        self._to = to

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._settings.username
        msg["To"] = self._to
        msg.set_content(body)
        with smtplib.SMTP(self._settings.host, self._settings.port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self._settings.username, self._settings.password)
            smtp.send_message(msg)
