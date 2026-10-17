"""API integration tests: the app reads a database the real ingest seeded
from the fixture."""
from __future__ import annotations

from datetime import date, datetime

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


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_performance_series_and_stats(client):
    perf = client.get("/api/performance", params={"period": "all"}).json()
    assert (perf["start"], perf["end"], perf["days"]) == ("2026-07-14", "2026-07-15", 1)
    base, last = perf["series"]
    assert base["cum_twr"] == 0.0 and base["drawdown"] == 0.0  # series start at the base point
    assert last["nav_sgd"] == pytest.approx(96711.27, abs=0.01)
    assert last["cum_twr"] == pytest.approx(0.006235337558)
    assert last["cum_local"] == pytest.approx(last["cum_twr"])  # no FX history yet
    assert perf["portfolio"]["total_return"] == pytest.approx(0.006235337558)
    assert perf["portfolio"]["sharpe"] is None  # one return is not enough
    assert perf["benchmark"] is None and perf["relative"] is None


def test_periods_anchor_to_latest_data_date_not_today(client):
    # fixture data is from 2026-07; 1M must still include it whatever today is
    for period in ("1m", "5y"):
        assert len(client.get("/api/performance", params={"period": period}).json()["series"]) == 2


def test_invalid_period_is_422(client):
    assert client.get("/api/performance", params={"period": "2w"}).status_code == 422


def test_fx_empty_for_single_day_fixture(client):
    assert client.get("/api/fx", params={"period": "all"}).json() == []


def test_positions_join_securities_and_annotations(client):
    rows = client.get("/api/positions").json()
    assert len(rows) == 7
    cspx = next(r for r in rows if r["symbol"] == "CSPX")
    assert cspx["sub_category"] == "ETF"
    assert cspx["issuer_country_code"] == "IE"
    assert cspx["sleeve"] is None
    values = [r["position_value_sgd"] for r in rows]
    assert values == sorted(values, reverse=True)


def test_avg_cost_local_is_in_the_quote_currency(client):
    # IMAE: 50 sh, value 4620 EUR at 1.4777, price P&L 613.2455 SGD →
    # local cost 4620 − 613.2455/1.4777 = 4205.0 EUR → 84.10 per share
    imae = next(r for r in client.get("/api/positions").json() if r["conid"] == "79000336")
    assert imae["avg_cost_local"] == pytest.approx(84.10, abs=0.01)
    assert imae["unrealized_fx_pnl"] == pytest.approx(63.916)


def test_annotation_roundtrip_keeps_unsent_fields(client):
    conid = "76023663"  # CSPX
    first = client.put(f"/api/positions/{conid}", json={"sleeve": "Core", "thesis": "Beta."})
    assert first.status_code == 200 and first.json()["updated_at"] is not None
    client.put(f"/api/positions/{conid}", json={"theme": "US large cap"})
    cspx = next(r for r in client.get("/api/positions").json() if r["conid"] == conid)
    assert (cspx["sleeve"], cspx["thesis"], cspx["theme"]) == ("Core", "Beta.", "US large cap")


def test_annotation_unknown_conid_404(client):
    assert client.put("/api/positions/000", json={"sleeve": "Core"}).status_code == 404


def test_exposures_currency(client):
    slices = client.get("/api/exposures", params={"by": "currency"}).json()
    assert sum(s["pct_of_nav"] for s in slices) == pytest.approx(98.22, abs=0.1)
    assert slices == sorted(slices, key=lambda s: -s["value_sgd"])


def test_exposures_asset_class_sum_to_nav(client):
    slices = client.get("/api/exposures", params={"by": "asset_class"}).json()
    assert {s["bucket"] for s in slices} >= {"cash", "stock"}
    assert sum(s["pct_of_nav"] for s in slices) == pytest.approx(100, abs=0.5)  # minus accruals


def test_exposures_by_sleeve_put_unlabelled_in_unassigned(client):
    client.put("/api/positions/76023663", json={"sleeve": "Core"})
    slices = {s["bucket"]: s for s in client.get("/api/exposures", params={"by": "sleeve"}).json()}
    assert set(slices) == {"Core", "Unassigned"}


def test_exposures_invalid_dimension_is_422(client):
    assert client.get("/api/exposures", params={"by": "astrology"}).status_code == 422


def test_closed_trades_and_note_roundtrip(client, seeded_db_url):
    from sqlalchemy import create_engine, insert

    from portfolio.load.models import ClosedLot

    with create_engine(seeded_db_url).begin() as conn:
        conn.execute(
            insert(ClosedLot).values(
                trade_id="T1", open_transaction_id="O1", conid="76023663", quantity=2,
                cost=1000, fifo_pnl_realized=150, trade_date=date(2026, 7, 15),
                open_date_time=datetime(2026, 5, 16, 9, 30),
            )
        )
    assert client.put("/api/closed-trades/T1", json={"note": "Took profit."}).status_code == 200
    (trade,) = client.get("/api/closed-trades").json()
    assert trade["symbol"] == "CSPX"
    assert trade["days_held"] == 60
    assert trade["realized_pnl_sgd"] == pytest.approx(150)
    assert trade["return_pct"] == pytest.approx(15.0)
    assert trade["note"] == "Took profit."


def test_note_on_unknown_trade_404(client):
    assert client.put("/api/closed-trades/nope", json={"note": "x"}).status_code == 404


def test_ops_runs(client):
    latest = client.get("/api/ops/runs", params={"n": 5}).json()[0]
    assert latest["status"] == "success"
    assert latest["rows_upserted"]["positions"] == 7
    assert latest["watermark_after"] == "2026-07-15"


def test_pnl_daily_breakdown(client):
    points = client.get("/api/pnl", params={"period": "all"}).json()
    assert [p["report_date"] for p in points] == ["2026-07-15"]
    assert points[0]["change_in_unrealized"] == pytest.approx(598.540425, abs=1e-6)
    assert points[0]["cash_sgd"] == pytest.approx(1697.21064, abs=1e-6)
    assert points[0]["nav_sgd"] == pytest.approx(96711.27489, abs=1e-6)


def test_dividends_empty_without_cash_transactions(client):
    assert client.get("/api/dividends", params={"period": "all"}).json() == []


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
