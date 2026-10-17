from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from ingestion.transform import RAW_TABLE_ORDER, transform_all

INGESTED_AT = datetime(2026, 7, 17, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def rows(frames):
    return transform_all(frames, ingested_at=INGESTED_AT, base_currency="SGD")


def test_all_raw_tables_present(rows):
    assert set(rows) == set(RAW_TABLE_ORDER)


def test_nav_history_shape(rows):
    nav = sorted(rows["nav_history"], key=lambda r: r["report_date"])
    assert len(nav) == 2
    latest = nav[-1]
    assert latest["report_date"] == date(2026, 7, 15)
    assert latest["total"] == Decimal("96711.27489")
    assert latest["base_currency"] == "SGD"
    assert latest["ingested_at"] == INGESTED_AT


def test_positions_use_ib_base_value_and_string_enums(rows):
    positions = rows["positions"]
    assert len(positions) == 7
    imae = next(p for p in positions if p["conid"] == "79000336")
    # IB's own positionValueInBase, not a float round-trip
    assert imae["position_value_sgd"] == Decimal("6826.974")
    assert imae["quantity"] == Decimal("50")
    assert imae["side"] == "Long"
    assert imae["level_of_detail"] == "SUMMARY"
    assert isinstance(imae["side"], str)  # enum coerced to its .value


def test_securities_deduped_on_conid(rows):
    securities = rows["securities"]
    conids = [s["conid"] for s in securities]
    assert len(conids) == len(set(conids))
    aapl = next(s for s in securities if s["conid"] == "265598")
    assert aapl["asset_category"] == "STK"
    assert aapl["sub_category"] == "COMMON"
    assert aapl["issuer_country_code"] == "US"


def test_fx_rates_quoted_in_base(rows):
    fx = rows["fx_rates"]
    assert len(fx) == 6
    eur = next(r for r in fx if r["currency"] == "EUR")
    assert eur["rate_to_base"] == Decimal("1.4777")
    assert eur["rate_date"] == date(2026, 7, 15)


def test_change_in_nav_mapping(rows):
    row = rows["change_in_nav"][0]
    assert row["from_date"] == date(2026, 7, 15)
    assert row["twr_ib"] == Decimal("0.6235337558")
    assert row["forex_translation"] == Decimal("0.75024")


def test_empty_sections_transform_to_empty_row_lists(rows):
    assert rows["trades"] == []
    assert rows["cash_transactions"] == []


def test_underconfigured_cash_section_fails_with_the_fix(frames):
    # IB lets a section be enabled with its fields unticked; a real pull came
    # back with dateTime alone. Classifying flows from that is impossible, and
    # proceeding would book deposits as investment gains (§7.4).
    import pandas as pd
    import pytest

    from ingestion.transform.base import IncompleteSectionError
    from ingestion.transform.cash import transform_cash

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
        transform_cash(df, ingested_at=datetime(2026, 7, 17, tzinfo=timezone.utc))
    assert "Cash Transactions" in str(exc.value)
    assert "type" in str(exc.value)


def test_complete_cash_section_still_transforms(frames):
    from decimal import Decimal

    import pandas as pd

    from ingestion.transform.cash import transform_cash

    df = pd.DataFrame([{
        "transactionID": "t1",
        "type": "Deposits/Withdrawals",
        "amount": Decimal("1000"),
        "currency": "SGD",
        "fxRateToBase": Decimal("1"),
        "dateTime": "2025-09-15;20:20:00",
    }])
    out = transform_cash(df, ingested_at=datetime(2026, 7, 17, tzinfo=timezone.utc))
    assert out["is_external_flow"].tolist() == [True]
    assert out["amount_sgd"].tolist() == [Decimal("1000")]


def test_cash_conid_resolved_from_isin_when_absent():
    # Some Flex queries ship CashTransaction with isin but no conid; dividends
    # would then be unattributable without the SecuritiesInfo lookup.
    from decimal import Decimal

    import pandas as pd

    from ingestion.transform.cash import transform_cash

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
    out = transform_cash(
        df,
        ingested_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        securities=securities,
    )
    assert out["conid"].tolist()[0] == "208813720"
    assert pd.isna(out["conid"].tolist()[1])
