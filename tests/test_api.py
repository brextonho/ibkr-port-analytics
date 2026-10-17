"""API integration tests: the app reads a database the real ingest seeded from
the demo year, and its answers are checked against the XML itself."""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from portfolio.api.app import create_app


@pytest.fixture(scope="module")
def seeded_db_url(tmp_path_factory, fixture_xml_path):
    from portfolio.config import Settings
    from portfolio.ingest import run

    url = f"sqlite:///{tmp_path_factory.mktemp('api') / 'portfolio.db'}"
    assert run(Settings(database=url), xml_paths=[fixture_xml_path], benchmark=False) == 0
    return url


@pytest.fixture(scope="module")
def client(seeded_db_url):
    return TestClient(create_app(seeded_db_url))


@pytest.fixture(scope="module")
def last_day(xml_rows):
    """The final statement's figures, straight from the XML."""
    cin = xml_rows("ChangeInNAV")[-1]
    base_cash = next(r for r in reversed(xml_rows("CashReportCurrency")) if r["currency"] == "BASE_SUMMARY")
    return {"nav": float(cin["endingValue"]), "cash": float(base_cash["endingCash"]), "date": cin["toDate"]}


def holdings(client):
    return [r for r in client.get("/api/positions").json() if r["asset_category"] != "CASH"]


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_performance_ties_to_ib(client, xml_rows, last_day):
    perf = client.get("/api/performance", params={"period": "all"}).json()
    assert (perf["start"], perf["end"], perf["days"]) == ("2025-10-01", "2026-09-30", 260)
    base, last = perf["series"][0], perf["series"][-1]
    assert base["cum_twr"] == 0.0 and base["drawdown"] == 0.0  # series start at the base point
    assert last["nav_sgd"] == pytest.approx(last_day["nav"])
    ib_twr = math.prod(1 + float(r["twr"]) / 100 for r in xml_rows("ChangeInNAV")) - 1
    assert last["cum_twr"] == pytest.approx(ib_twr)
    assert perf["portfolio"]["total_return"] == pytest.approx(ib_twr)
    assert 1 + last["cum_twr"] == pytest.approx((1 + last["cum_local"]) * (1 + last["cum_fx"]))
    assert perf["portfolio"]["annualized"] is not None and perf["portfolio"]["sharpe"] is not None
    assert perf["benchmark"] is None and perf["relative"] is None  # tests skip the Yahoo fetch


def test_periods_end_at_latest_data_date_not_today(client):
    month = client.get("/api/performance", params={"period": "1m"}).json()
    assert month["end"] == "2026-09-30" and month["start"] >= "2026-08-31"
    everything = client.get("/api/performance", params={"period": "all"}).json()
    assert client.get("/api/performance", params={"period": "5y"}).json()["days"] == everything["days"]


def test_invalid_period_is_422(client):
    assert client.get("/api/performance", params={"period": "2w"}).status_code == 422


def test_fx_by_currency_starts_at_zero(client):
    rows = client.get("/api/fx", params={"period": "all"}).json()
    assert {r["currency"] for r in rows} == {"USD", "EUR", "JPY"}
    assert all(r["cum_contribution"] == 0 for r in rows if r["report_date"] == "2025-10-01")


def test_holdings_join_securities_and_sort_by_value(client):
    rows = holdings(client)
    assert {r["symbol"] for r in rows} == {"CSPX", "VWRA", "IMAE", "ES3", "MSFT", "NVDA", "7203"}
    cspx = next(r for r in rows if r["symbol"] == "CSPX")
    assert (cspx["sub_category"], cspx["issuer_country_code"], cspx["sleeve"]) == ("ETF", "IE", None)
    values = [r["position_value_sgd"] for r in rows]
    assert values == sorted(values, reverse=True)


def test_avg_cost_local_is_the_average_purchase_price(client, xml_rows):
    buys = [r for r in xml_rows("Trade") if r["symbol"] == "CSPX"]
    qty = sum(float(r["quantity"]) for r in buys)
    expected = sum(float(r["quantity"]) * float(r["tradePrice"]) for r in buys) / qty
    cspx = next(r for r in holdings(client) if r["symbol"] == "CSPX")
    assert cspx["quantity"] == qty == 30
    assert cspx["avg_cost_local"] == pytest.approx(expected)
    assert cspx["unrealized_capital_gains_pnl"] + cspx["unrealized_fx_pnl"] == pytest.approx(cspx["unrealized_pnl"])


def test_holdings_and_cash_add_up_to_nav(client, last_day):
    rows = client.get("/api/positions").json()
    assert sum(r["position_value_sgd"] for r in rows) == pytest.approx(last_day["nav"])
    assert sum(r["percent_of_nav"] for r in rows) == pytest.approx(100)


def test_cash_rows_tie_to_ibs_base_total(client, last_day):
    cash = {r["currency"]: r for r in client.get("/api/positions").json() if r["asset_category"] == "CASH"}
    assert set(cash) == {"SGD", "USD", "JPY"}  # EUR is spent to zero, so it's left out
    assert sum(r["position_value_sgd"] for r in cash.values()) == pytest.approx(last_day["cash"])
    assert cash["SGD"]["position_value_sgd"] == pytest.approx(cash["SGD"]["quantity"])
    assert cash["USD"]["conid"] == "CASH.USD" and cash["USD"]["unrealized_pnl"] is None


def test_share_of_nav_is_value_over_nav_not_ibs_figure(client, last_day):
    # IB's percentOfNAV is share of invested value; ours divides by NAV
    cspx = next(r for r in holdings(client) if r["symbol"] == "CSPX")
    assert cspx["percent_of_nav"] == pytest.approx(cspx["position_value_sgd"] / last_day["nav"] * 100)


def test_annotation_roundtrip_keeps_unsent_fields(client):
    conid = "900101"  # CSPX
    first = client.put(f"/api/positions/{conid}", json={"sleeve": "Core", "thesis": "Beta."})
    assert first.status_code == 200 and first.json()["updated_at"] is not None
    client.put(f"/api/positions/{conid}", json={"theme": "US large cap"})
    cspx = next(r for r in holdings(client) if r["conid"] == conid)
    assert (cspx["sleeve"], cspx["thesis"], cspx["theme"]) == ("Core", "Beta.", "US large cap")
    client.put(f"/api/positions/{conid}", json={"sleeve": None, "thesis": None, "theme": None})


def test_cash_rows_take_a_sleeve(client):
    assert client.put("/api/positions/CASH.USD", json={"sleeve": "Cash"}).status_code == 200
    usd = next(r for r in client.get("/api/positions").json() if r["conid"] == "CASH.USD")
    assert usd["sleeve"] == "Cash"
    assert "Cash" in {s["bucket"] for s in client.get("/api/exposures", params={"by": "sleeve"}).json()}
    assert client.put("/api/positions/CASH.XYZ", json={"sleeve": "Cash"}).status_code == 404
    client.put("/api/positions/CASH.USD", json={"sleeve": None})


def test_annotation_unknown_conid_404(client):
    assert client.put("/api/positions/000", json={"sleeve": "Core"}).status_code == 404


def test_exposures_include_cash_and_sum_to_nav(client):
    for by in ("currency", "geography", "sleeve", "asset_class"):
        slices = client.get("/api/exposures", params={"by": by}).json()
        assert sum(s["pct_of_nav"] for s in slices) == pytest.approx(100), by
        assert slices == sorted(slices, key=lambda s: -s["value_sgd"]), by


def test_exposures_by_sleeve_put_unlabelled_in_unassigned(client):
    client.put("/api/positions/900101", json={"sleeve": "Core"})
    slices = {s["bucket"] for s in client.get("/api/exposures", params={"by": "sleeve"}).json()}
    assert slices == {"Core", "Unassigned"}
    client.put("/api/positions/900101", json={"sleeve": None})


def test_exposures_invalid_dimension_is_422(client):
    assert client.get("/api/exposures", params={"by": "astrology"}).status_code == 422


def test_closed_trades_tie_to_realized_pnl(client, xml_rows):
    trades = {t["symbol"]: t for t in client.get("/api/closed-trades").json()}
    assert set(trades) == {"NVDA", "MSFT"}
    realized = sum(float(r["realized"]) for r in xml_rows("ChangeInNAV"))
    assert sum(t["realized_pnl_sgd"] for t in trades.values()) == pytest.approx(realized)
    lots = [r for r in xml_rows("Lot") if r["symbol"] == "NVDA"]
    assert trades["NVDA"]["open_date"] == min(r["openDateTime"][:10] for r in lots)
    assert trades["NVDA"]["quantity"] == 40  # one sale across two purchases


def test_note_roundtrip_and_unknown_trade_404(client):
    trade_id = client.get("/api/closed-trades").json()[0]["trade_id"]
    assert client.put(f"/api/closed-trades/{trade_id}", json={"note": "Took profit."}).status_code == 200
    assert next(t for t in client.get("/api/closed-trades").json() if t["trade_id"] == trade_id)["note"] == "Took profit."
    assert client.put("/api/closed-trades/nope", json={"note": "x"}).status_code == 404


def test_ops_runs(client, xml_rows):
    latest = client.get("/api/ops/runs", params={"n": 5}).json()[0]
    assert latest["status"] == "success"
    assert latest["rows_upserted"]["positions"] == len(xml_rows("OpenPosition"))
    assert latest["watermark_after"] == "2026-09-30"


def test_pnl_daily_breakdown_ties_to_change_in_nav(client, xml_rows):
    points = client.get("/api/pnl", params={"period": "all"}).json()
    assert len(points) == 260
    expected = sum(float(r["dividends"]) for r in xml_rows("ChangeInNAV"))
    assert sum(p["dividends"] for p in points) == pytest.approx(expected)


def test_dividends_and_withholding(client, xml_rows):
    rows = client.get("/api/dividends", params={"period": "all"}).json()
    assert len(rows) == len(xml_rows("CashTransaction")) - 3  # less 2 deposits and 1 withdrawal
    assert all(r["symbol"] for r in rows)  # conid found from ISIN
    gross = sum(r["amount_sgd"] for r in rows if r["type"] == "Dividends")
    assert gross == pytest.approx(sum(float(r["dividends"]) for r in xml_rows("ChangeInNAV")))


def test_failed_run_is_recorded_and_watermark_holds(tmp_path, fixture_xml_path):
    from portfolio.config import Settings
    from portfolio.ingest import run

    url = f"sqlite:///{tmp_path / 'p.db'}"
    bad = tmp_path / "not_ready.xml"
    bad.write_text(
        fixture_xml_path.read_text().replace(
            "<FlexStatements", "<Message>Realized P/L is not ready.</Message><FlexStatements", 1
        )
    )
    assert run(Settings(database=url), xml_paths=[bad], benchmark=False) == 1
    (r,) = TestClient(create_app(url)).get("/api/ops/runs").json()
    assert r["status"] == "failed" and r["error_code"] == "StatementNotReadyError"
    assert r["watermark_after"] is None
    assert TestClient(create_app(url)).get("/api/positions").json() == []  # nothing written


def test_dashboard_page_is_rechecked_on_every_load(client):
    from portfolio.api.app import WEB_DIST

    if not WEB_DIST.is_dir():
        pytest.skip("dashboard not built")
    assert client.get("/").headers["cache-control"] == "no-cache"
    assert "cache-control" not in client.get("/api/health").headers
