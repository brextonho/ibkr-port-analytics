"""Exposure cuts (PRD §6.4) against the fixture, incl. the §12 weights check."""
from __future__ import annotations

from datetime import date

import pytest

from ingestion.analytics.exposures import asset_class_exposures, position_exposures

SNAPSHOT = date(2026, 7, 15)


def test_asset_class_comes_free_from_nav_columns(raw_frames):
    exp = asset_class_exposures(raw_frames["nav_history"])
    day = exp[exp["snapshot_date"] == SNAPSHOT]
    buckets = dict(zip(day["bucket"], day["value_sgd"]))
    assert buckets["stock"] == pytest.approx(94995.61305)
    assert buckets["cash"] == pytest.approx(1697.21064)
    assert "options" not in buckets  # zero buckets dropped
    # cash + stock ≈ the whole book (accruals are the remainder)
    assert day["pct_of_nav"].sum() == pytest.approx(99.99, abs=0.05)


def test_currency_exposures_sum_to_position_values(raw_frames):
    exp = position_exposures(
        raw_frames["positions"],
        raw_frames["securities"],
        raw_frames["nav_history"],
        dimension="currency",
    )
    total = float(raw_frames["positions"]["position_value_sgd"].astype(float).sum())
    assert exp["value_sgd"].sum() == pytest.approx(total)
    assert set(exp["dimension"]) == {"currency"}
    assert len(exp) < 7  # grouped, not per-position


def test_computed_weights_reconcile_with_ib_percent_of_nav(raw_frames):
    """§12: Σ computed pct_of_nav ≈ Σ IB's own percentOfNAV."""
    exp = position_exposures(
        raw_frames["positions"],
        raw_frames["securities"],
        raw_frames["nav_history"],
        dimension="currency",
    )
    ib_sum = float(raw_frames["positions"]["percent_of_nav"].astype(float).sum())
    assert exp["pct_of_nav"].sum() == pytest.approx(ib_sum, abs=0.5)


def test_geography_from_issuer_country(raw_frames):
    exp = position_exposures(
        raw_frames["positions"],
        raw_frames["securities"],
        raw_frames["nav_history"],
        dimension="geography",
    )
    assert {"US", "IE"} <= set(exp["bucket"])
    assert (exp["dimension"] == "geography").all()


def test_unknown_dimension_raises(raw_frames):
    with pytest.raises(ValueError):
        position_exposures(
            raw_frames["positions"],
            raw_frames["securities"],
            raw_frames["nav_history"],
            dimension="astrology",
        )
