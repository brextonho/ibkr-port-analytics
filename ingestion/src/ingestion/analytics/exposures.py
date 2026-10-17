"""Exposure cuts in long format (PRD §6.4): adding a dimension inserts rows.

MVP dimensions: asset_class (free from nav_history columns — no position
join), currency (from positions), geography (issuer_country_code, with the
optional security_tags.geography override). sector/theme are deferred.

pct_of_nav is in percent units, matching IB's own percentOfNAV field.
"""
from __future__ import annotations

import pandas as pd

ASSET_CLASS_BUCKETS = ["cash", "stock", "options", "bonds", "funds", "crypto"]

LONG_COLUMNS = ["snapshot_date", "dimension", "bucket", "value_sgd", "pct_of_nav"]


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=LONG_COLUMNS)


def asset_class_exposures(nav: pd.DataFrame) -> pd.DataFrame:
    """One row per (report date, nonzero asset class bucket), from NAV columns."""
    if nav.empty:
        return _empty()
    rows = []
    for _, r in nav.iterrows():
        total = float(r["total"])
        if not total:
            continue
        for bucket in ASSET_CLASS_BUCKETS:
            value = float(r.get(bucket) or 0.0)
            if value == 0.0:
                continue
            rows.append(
                {
                    "snapshot_date": r["report_date"],
                    "dimension": "asset_class",
                    "bucket": bucket,
                    "value_sgd": value,
                    "pct_of_nav": value / total * 100.0,
                }
            )
    return pd.DataFrame(rows, columns=LONG_COLUMNS)


def position_exposures(
    positions: pd.DataFrame,
    securities: pd.DataFrame,
    nav: pd.DataFrame,
    *,
    dimension: str,
    security_tags: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Group position_value_sgd by currency or geography per snapshot date."""
    if positions.empty or nav.empty:
        return _empty()
    pos = positions.copy()
    pos["position_value_sgd"] = pos["position_value_sgd"].astype(float)

    if dimension == "currency":
        pos["bucket"] = pos["currency"]
    elif dimension == "geography":
        countries = securities[["conid", "issuer_country_code"]]
        pos = pos.merge(countries, on="conid", how="left")
        pos["bucket"] = pos["issuer_country_code"]
        if security_tags is not None and not security_tags.empty:
            override = security_tags.dropna(subset=["geography"])[["conid", "geography"]]
            pos = pos.merge(override, on="conid", how="left")
            pos["bucket"] = pos["geography"].fillna(pos["bucket"])
        pos["bucket"] = pos["bucket"].fillna("UNKNOWN")
    else:
        raise ValueError(f"unsupported exposure dimension {dimension!r}")

    nav_by_date = nav.set_index("report_date")["total"].astype(float)
    grouped = (
        pos.groupby(["snapshot_date", "bucket"])["position_value_sgd"]
        .sum()
        .reset_index()
        .rename(columns={"position_value_sgd": "value_sgd"})
    )
    grouped["dimension"] = dimension
    grouped["pct_of_nav"] = grouped.apply(
        lambda r: r["value_sgd"] / nav_by_date[r["snapshot_date"]] * 100.0
        if r["snapshot_date"] in nav_by_date.index and nav_by_date[r["snapshot_date"]]
        else None,
        axis=1,
    )
    return grouped[LONG_COLUMNS]
