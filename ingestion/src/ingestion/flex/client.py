"""Two-step Flex Web Service fetch with classified retry (PRD §3.3–3.4, §5.2).

SendRequest returns a reference code; GetStatement exchanges it for XML.
Error codes are classified — retryable ("not ready yet") codes back off
exponentially, fatal codes (expired token, invalid query) fail immediately
rather than wasting the 10-requests/minute budget.

The HTTP call and sleep are injectable so retry behaviour is unit-testable
offline.
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any, Callable

import requests

from ingestion.config import (
    DEFAULT_FATAL_CODES,
    DEFAULT_RETRYABLE_CODES,
    FlexSettings,
    RetrySettings,
)

logger = logging.getLogger(__name__)

HttpGet = Callable[[str, dict[str, Any], dict[str, str]], bytes]


class FlexAPIError(Exception):
    def __init__(self, code: int | None, message: str):
        super().__init__(f"Flex error {code}: {message}" if code else message)
        self.code = code
        self.message = message


class FlexRetryableError(FlexAPIError):
    """Statement not ready / server busy — try again shortly."""


class FlexFatalError(FlexAPIError):
    """Do not retry: fix the token/query/config and rerun."""


class FlexRetryExhaustedError(FlexAPIError):
    """Still not ready after all attempts."""


def _default_http_get(url: str, params: dict[str, Any], headers: dict[str, str]) -> bytes:
    resp = requests.get(url, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.content


def _classify(code: int, message: str, fatal_codes: tuple[int, ...]) -> FlexAPIError:
    if code in fatal_codes:
        return FlexFatalError(code, message)
    if code in DEFAULT_RETRYABLE_CODES:
        return FlexRetryableError(code, message)
    # Unknown codes are treated as fatal: retrying blind wastes the rate budget
    return FlexFatalError(code, f"unrecognised Flex error code: {message}")


def _raise_if_error_response(payload: bytes, fatal_codes: tuple[int, ...]) -> ET.Element | None:
    """Return the parsed root for FlexStatementResponse payloads, raising on errors.

    GetStatement success payloads are FlexQueryResponse XML (or arbitrarily
    large statements) — those return None untouched.
    """
    head = payload[:200].lstrip()
    if not head.startswith(b"<FlexStatementResponse"):
        return None
    root = ET.fromstring(payload)
    error_code = root.findtext("ErrorCode")
    if error_code:
        message = root.findtext("ErrorMessage") or "no message"
        raise _classify(int(error_code), message, fatal_codes)
    return root


def _with_retry(
    fn: Callable[[], Any],
    retry: RetrySettings,
    sleep: Callable[[float], None],
    retries_log: list[dict[str, int]],
) -> Any:
    last: FlexRetryableError | None = None
    for attempt in range(1, retry.attempts + 1):
        try:
            return fn()
        except FlexRetryableError as exc:
            last = exc
            retries_log.append({"code": exc.code or 0, "attempt": attempt})
            if attempt == retry.attempts:
                break
            delay = retry.backoff_seconds * 2 ** (attempt - 1)
            logger.info(
                "Flex code %s (attempt %d/%d), retrying in %.0fs",
                exc.code, attempt, retry.attempts, delay,
            )
            sleep(delay)
    raise FlexRetryExhaustedError(
        last.code if last else None,
        f"gave up after {retry.attempts} attempts: {last.message if last else 'unknown'}",
    )


def fetch_statement(
    flex: FlexSettings,
    *,
    from_date: date,
    to_date: date,
    retry: RetrySettings | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[bytes, list[dict[str, int]]]:
    """Fetch statement XML for an explicit fd/td window (never the saved period, §5.2).

    Returns (xml_bytes, retries_log) so the run log can record retried codes.
    """
    retry = retry or RetrySettings()
    http_get = http_get or _default_http_get
    headers = {"User-Agent": flex.user_agent}  # header must be present (§3.3)
    fatal_codes = tuple(retry.fatal_codes)
    retries_log: list[dict[str, int]] = []

    def send_request() -> str:
        payload = http_get(
            f"{flex.base_url}/SendRequest",
            {
                "t": flex.token,
                "q": flex.query_id,
                "v": flex.version,
                "fd": from_date.strftime("%Y%m%d"),
                "td": to_date.strftime("%Y%m%d"),
            },
            headers,
        )
        root = _raise_if_error_response(payload, fatal_codes)
        if root is None:
            raise FlexFatalError(None, "unexpected SendRequest payload")
        reference_code = root.findtext("ReferenceCode")
        if not reference_code:
            raise FlexFatalError(None, "SendRequest returned no ReferenceCode")
        return reference_code

    reference_code = _with_retry(send_request, retry, sleep, retries_log)

    def get_statement() -> bytes:
        payload = http_get(
            f"{flex.base_url}/GetStatement",
            {"t": flex.token, "q": reference_code, "v": flex.version},
            headers,
        )
        _raise_if_error_response(payload, fatal_codes)
        return payload

    statement = _with_retry(get_statement, retry, sleep, retries_log)
    return statement, retries_log
