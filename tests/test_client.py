"""Retry classification: 1019 retries, 1012 fails immediately."""
from __future__ import annotations

from datetime import date

import pytest
import requests

from portfolio.config import FlexSettings, RetrySettings
from portfolio.flex.client import (
    FlexFatalError,
    FlexRetryExhaustedError,
    fetch_statement,
)

FLEX = FlexSettings(query_id="123", token="tok")
WINDOW = dict(from_date=date(2026, 7, 3), to_date=date(2026, 7, 17))
RETRY = RetrySettings(attempts=3, backoff_seconds=1.0)

SEND_OK = b"""<FlexStatementResponse timestamp="x">
<Status>Success</Status><ReferenceCode>REF42</ReferenceCode>
<Url>https://flex.example/GetStatement</Url></FlexStatementResponse>"""

STATEMENT = b"""<FlexQueryResponse queryName="q" type="AF"><FlexStatements count="1">
</FlexStatements></FlexQueryResponse>"""


def _error(code: int) -> bytes:
    return (
        f'<FlexStatementResponse timestamp="x"><Status>Warn</Status>'
        f"<ErrorCode>{code}</ErrorCode><ErrorMessage>msg</ErrorMessage>"
        f"</FlexStatementResponse>"
    ).encode()


class FakeHttp:
    """Scripted responses keyed by endpoint, recording every call."""

    def __init__(self, send_responses: list[bytes], get_responses: list[bytes]):
        self.scripts = {"SendRequest": send_responses, "GetStatement": get_responses}
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url: str, params: dict, headers: dict) -> bytes:
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append((endpoint, params))
        assert headers.get("User-Agent")  # IB requires the header
        return self.scripts[endpoint].pop(0)


def test_happy_path_passes_explicit_window_and_reference_code():
    http = FakeHttp([SEND_OK], [STATEMENT])
    payload, retries = fetch_statement(
        FLEX, **WINDOW, retry=RETRY, http_get=http, sleep=lambda s: None
    )
    assert payload == STATEMENT
    assert retries == []
    send_params = http.calls[0][1]
    assert send_params["fd"] == "20260703" and send_params["td"] == "20260717"
    assert send_params["t"] == "tok"  # the real token string, not the masked SecretStr
    assert http.calls[1][1]["q"] == "REF42"


def test_retryable_code_backs_off_then_succeeds():
    http = FakeHttp([SEND_OK], [_error(1019), _error(1009), STATEMENT])
    sleeps: list[float] = []
    payload, retries = fetch_statement(
        FLEX, **WINDOW, retry=RETRY, http_get=http, sleep=sleeps.append
    )
    assert payload == STATEMENT
    assert [r["code"] for r in retries] == [1019, 1009]
    assert sleeps == [1.0, 2.0]  # exponential backoff


def test_fatal_code_fails_immediately_without_retry():
    http = FakeHttp([_error(1012)], [])
    with pytest.raises(FlexFatalError) as exc_info:
        fetch_statement(FLEX, **WINDOW, retry=RETRY, http_get=http, sleep=lambda s: None)
    assert exc_info.value.code == 1012
    assert len(http.calls) == 1  # exactly one attempt, no wasted rate budget


def test_retry_budget_exhausts():
    http = FakeHttp([SEND_OK], [_error(1019)] * 3)
    with pytest.raises(FlexRetryExhaustedError):
        fetch_statement(FLEX, **WINDOW, retry=RETRY, http_get=http, sleep=lambda s: None)


def _failing_get(exc):
    def get(*args, **kwargs):
        raise exc

    return get


@pytest.mark.parametrize(
    "make_error",
    [
        # a connection failure: requests names the full URL, token and all
        lambda: requests.ConnectionError(
            "HTTPSConnectionPool: Max retries exceeded with url: /SendRequest?t=tok-SECRET&q=123"
        ),
        # an HTTP error status: raise_for_status() also puts the URL in the message
        lambda: _http_error(500),
    ],
)
def test_http_failures_never_carry_the_token(monkeypatch, make_error):
    from portfolio.flex.client import FlexAPIError, _default_http_get

    monkeypatch.setattr(requests, "get", _failing_get(make_error()))
    with pytest.raises(FlexAPIError) as info:
        _default_http_get("https://flex.example/SendRequest", {"t": "tok-SECRET", "q": "123"}, {})
    assert "SECRET" not in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__  # not in tracebacks either
    assert "SendRequest" in str(info.value)


def _http_error(status: int) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    resp.reason = "Server Error"
    resp.url = "https://flex.example/SendRequest?t=tok-SECRET&q=123"
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        assert "tok-SECRET" in str(exc)  # what requests would have leaked
        return exc
    raise AssertionError("expected an HTTPError")
