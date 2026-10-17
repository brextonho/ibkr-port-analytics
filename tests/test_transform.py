from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from portfolio.transform import RAW_TABLE_ORDER, transform_all

INGESTED_AT = datetime(2026, 7, 17, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def rows(frames):
    return transform_all(frames, ingested_at=INGESTED_AT, base_currency="SGD")


def test_all_raw_tables_present(rows):
    assert set(rows) == set(RAW_TABLE_ORDER)


def test_nav_history_shape(rows, xml_rows):
    last = max(rows["nav_history"], key=lambda r: r["report_date"])
    assert last["report_date"] == date(2026, 9, 30)
    assert last["total"] == Decimal(xml_rows("EquitySummaryByReportDateInBase")[-1]["total"])
    assert last["base_currency"] == "SGD"
    assert last["ingested_at"] == INGESTED_AT


def test_positions_use_ib_base_value_and_string_enums(rows, xml_rows):
    src = xml_rows("OpenPosition")[-1]
    row = next(p for p in rows["positions"] if p["conid"] == src["conid"] and p["snapshot_date"].isoformat() == src["reportDate"])
    # IB's own positionValueInBase, not a float round-trip
    assert row["position_value_sgd"] == Decimal(src["positionValueInBase"])
    assert row["unrealized_capital_gains_pnl"] + row["unrealized_fx_pnl"] == pytest.approx(row["unrealized_pnl"], abs=1e-5)
    assert row["side"] == "Long" and isinstance(row["side"], str)  # enum coerced to its .value
    assert row["level_of_detail"] == "SUMMARY"


def test_securities_deduped_on_conid(rows):
    conids = [s["conid"] for s in rows["securities"]]
    assert len(conids) == len(set(conids)) == 7  # listed in all 260 statements, kept once
    msft = next(s for s in rows["securities"] if s["symbol"] == "MSFT")
    assert (msft["asset_category"], msft["sub_category"], msft["issuer_country_code"]) == ("STK", "COMMON", "US")


def test_fx_rates_quoted_in_base(rows, xml_rows):
    src = xml_rows("ConversionRate")[-1]
    row = next(r for r in rows["fx_rates"] if r["currency"] == src["fromCurrency"] and r["rate_date"].isoformat() == src["reportDate"])
    assert row["rate_to_base"] == Decimal(src["rate"])


def test_change_in_nav_mapping(rows, xml_rows):
    src, row = xml_rows("ChangeInNAV")[-1], rows["change_in_nav"][-1]
    assert row["from_date"] == row["to_date"] == date(2026, 9, 30)
    assert row["twr_ib"] == Decimal(src["twr"])
    assert row["forex_translation"] == Decimal(src["fxTranslation"])


def test_cash_transactions_get_conid_from_isin(rows):
    # the demo, like real pulls, has isin but no conid on dividend rows
    divs = [r for r in rows["cash_transactions"] if r["type"] == "Dividends"]
    assert divs and all(r["conid"] for r in divs)


def test_underconfigured_cash_section_fails_with_the_fix(frames):
    # IB lets a section be enabled with its fields unticked; a real pull came
    # back with dateTime alone. Without type and amount, dividends can't be
    # told apart from deposits.
    import pandas as pd
    import pytest

    from portfolio.transform import IncompleteSectionError, transform_table

    # ibflex fills every dataclass field, so unticked attributes arrive as
    # present-but-all-None columns, not absent ones.
    df = pd.DataFrame([{
        "dateTime": "2025-09-15;20:20:00",
        "type": None,
        "amount": None,
        "currency": None,
        "fxRateToBase": None,
        "transactionID": None,
    }])
    with pytest.raises(IncompleteSectionError) as exc:
        transform_table("cash_transactions", df)
    assert "Cash Transactions" in str(exc.value)
    assert "type" in str(exc.value)


def test_complete_cash_section_still_transforms(frames):
    from decimal import Decimal

    import pandas as pd

    from portfolio.transform import transform_table

    df = pd.DataFrame([{
        "transactionID": "t1",
        "type": "Deposits/Withdrawals",
        "amount": Decimal("1000"),
        "currency": "SGD",
        "fxRateToBase": Decimal("1"),
        "dateTime": "2025-09-15;20:20:00",
    }])
    out = transform_table("cash_transactions", df)
    assert out["amount_sgd"].tolist() == [Decimal("1000")]


def test_cash_conid_resolved_from_isin_when_absent():
    # Some Flex queries ship CashTransaction with isin but no conid; dividends
    # would then be unattributable without the SecuritiesInfo lookup.
    from decimal import Decimal

    import pandas as pd

    from portfolio.transform import transform_table

    df = pd.DataFrame([
        {
            "transactionID": "d1",
            "type": "Dividends",
            "amount": Decimal("1.26"),
            "currency": "USD",
            "fxRateToBase": Decimal("1.28"),
            "dateTime": "2025-06-16;20:20:00",
            "isin": "US02079K1079",
            "conid": None,
        },
        {
            "transactionID": "w1",
            "type": "Deposits/Withdrawals",
            "amount": Decimal("1000"),
            "currency": "SGD",
            "fxRateToBase": Decimal("1"),
            "dateTime": "2025-06-16;20:20:00",
            "isin": None,
            "conid": None,
        },
    ])
    securities = pd.DataFrame([{"conid": "208813720", "isin": "US02079K1079"}])
    out = transform_table("cash_transactions", df, securities=securities)
    assert out["conid"].tolist()[0] == "208813720"
    assert pd.isna(out["conid"].tolist()[1])
