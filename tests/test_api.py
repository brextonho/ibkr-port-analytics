"""API integration tests (PRD §10): the app reads a warehouse that the real
ingestion pipeline seeded from the fixture — the same contract as production.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture(scope="module")
def seeded_db_url(tmp_path_factory, fixture_xml_path):
    from ingestion.__main__ import main as ingest_main

    db_path = tmp_path_factory.mktemp("api") / "warehouse.db"
    url = f"sqlite:///{db_path}"
    rc = ingest_main(
        [
            "--config",
            "config/config.example.yaml",
            "--xml",
            str(fixture_xml_path),
            "--db",
            url,
            "--no-benchmark",
        ]
    )
    assert rc == 0
    return url


@pytest.fixture(scope="module")
def client(seeded_db_url):
    return TestClient(create_app(seeded_db_url))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_nav_series(client):
    points = client.get("/nav", params={"period": "all"}).json()
    assert len(points) == 2
    assert points[-1]["report_date"] == "2026-07-15"
    assert points[-1]["nav_sgd"] == pytest.approx(96711.27, abs=0.01)


def test_returns_series(client):
    points = client.get("/returns", params={"period": "all"}).json()
    assert points[0]["r_period"] is None
    assert points[-1]["r_period"] == pytest.approx(0.0062353, abs=1e-6)
    assert points[-1]["cum_twr"] == pytest.approx(0.0062353, abs=1e-6)


def test_metrics_latest(client):
    m = client.get("/metrics").json()
    assert m["report_date"] == "2026-07-15"
    assert m["twr_cum"] == pytest.approx(0.0062353, abs=1e-6)
    assert m["sharpe"] is None  # one observed return


def test_drawdown(client):
    points = client.get("/drawdown", params={"period": "all"}).json()
    assert len(points) == 2
    assert all(p["drawdown_current"] <= 0 for p in points)


def test_exposures_currency(client):
    slices = client.get("/exposures", params={"by": "currency"}).json()
    assert slices  # non-empty
    assert sum(s["pct_of_nav"] for s in slices) == pytest.approx(98.22, abs=0.1)
    assert slices == sorted(slices, key=lambda s: -s["value_sgd"])


def test_exposures_deferred_dimensions_return_empty_not_error(client):
    assert client.get("/exposures", params={"by": "sector"}).json() == []
    assert client.get("/exposures", params={"by": "theme"}).json() == []


def test_exposures_invalid_dimension_is_422(client):
    assert client.get("/exposures", params={"by": "astrology"}).status_code == 422


def test_fx_attribution_empty_for_single_day_fixture(client):
    assert client.get("/attribution/fx", params={"period": "all"}).json() == []


def test_positions_grid_joins_all_four_tables(client):
    rows = client.get("/positions").json()
    assert len(rows) == 7
    cspx = next(r for r in rows if r["symbol"] == "CSPX")
    assert cspx["sub_category"] == "ETF"
    assert cspx["issuer_country_code"] == "IE"
    assert cspx["thesis"] is None  # no notes yet
    # ordered by value desc
    values = [r["position_value_sgd"] for r in rows]
    assert values == sorted(values, reverse=True)


def test_put_position_notes_roundtrip(client):
    conid = "76023663"  # CSPX
    resp = client.put(
        f"/positions/{conid}/notes",
        json={"thesis": "Core beta holding.", "target_price": 200},
    )
    assert resp.status_code == 200
    assert resp.json()["thesis"] == "Core beta holding."
    assert resp.json()["updated_at"] is not None

    rows = client.get("/positions").json()
    cspx = next(r for r in rows if r["conid"] == conid)
    assert cspx["thesis"] == "Core beta holding."
    assert cspx["target_price"] == 200


def test_put_notes_unknown_conid_404(client):
    assert client.put("/positions/000/notes", json={"thesis": "x"}).status_code == 404


def test_trades_journal_and_stats_empty(client):
    assert client.get("/trades/journal").json() == []
    assert client.get("/trades/stats").json() is None


def test_put_grade_unknown_trade_404(client):
    resp = client.put("/trades/nope/grade", json={"process_grade": "A"})
    assert resp.status_code == 404


def test_ops_runs(client):
    runs = client.get("/ops/runs", params={"n": 5}).json()
    assert len(runs) >= 1
    latest = runs[0]
    assert latest["status"] == "success"
    assert latest["rows_upserted"]["positions"] == 7
    assert latest["watermark_after"] == "2026-07-15"


def test_pnl_daily_breakdown(client):
    points = client.get("/pnl", params={"period": "all"}).json()
    assert [p["report_date"] for p in points] == ["2026-07-15"]
    assert points[0]["change_in_unrealized"] == pytest.approx(598.540425, abs=1e-6)
    assert points[0]["cash_sgd"] == pytest.approx(1697.21064, abs=1e-6)
    assert points[0]["nav_sgd"] == pytest.approx(96711.27489, abs=1e-6)


def test_dividends_empty_without_cash_transactions(client):
    assert client.get("/dividends", params={"period": "all"}).json() == []


def test_positions_carry_cost_basis(client):
    rows = client.get("/positions").json()
    assert all("cost_basis_price" in r and "fx_rate_to_base" in r for r in rows)


def test_avg_cost_local_is_in_the_quote_currency(client):
    # IMAE: 50 sh, value 4620 EUR at 1.4777, price P&L 613.2455 SGD →
    # local cost 4620 − 613.2455/1.4777 = 4205.0 EUR → 84.10 per share
    rows = {r["conid"]: r for r in client.get("/positions").json()}
    imae = rows["79000336"]
    assert imae["avg_cost_local"] == pytest.approx(84.10, abs=0.01)
    assert imae["unrealized_fx_pnl"] == pytest.approx(63.916)


def test_periods_anchor_to_latest_data_date_not_today(client):
    # fixture data is from 2026-07; 1M must still include it whatever today is
    assert len(client.get("/nav", params={"period": "1m"}).json()) == 2
    assert len(client.get("/nav", params={"period": "5y"}).json()) == 2
