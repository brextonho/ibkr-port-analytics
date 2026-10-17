"""Shared transform helpers: enum coercion, column remapping, row extraction.

Rules (PRD §5.5): Decimal stays Decimal (never round-trip money through
float), enums are stored as their .value string, every row gets ingested_at.
"""
from __future__ import annotations

import enum
from typing import Any, cast

import pandas as pd


def _coerce(v: Any) -> Any:
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (tuple, list, set, frozenset)):
        # ibflex parses code/notes attributes into tuples of Code enums
        if not v:
            return None
        return ";".join(str(x.value if isinstance(x, enum.Enum) else x) for x in v)
    return v


def coerce_enums(df: pd.DataFrame) -> pd.DataFrame:
    """Replace ibflex enums with .value strings and code tuples with ';' joins."""
    if df.empty:
        return df
    return df.map(_coerce)


def remap(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Select and rename source columns to schema columns.

    Source columns missing from the frame become all-None columns rather than
    KeyErrors — IB adds and drops attributes, and ibflex parses leniently, so
    the transform must too.
    """
    out = pd.DataFrame(index=df.index)
    for src, dst in mapping.items():
        out[dst] = df[src] if src in df.columns else None
    return out


class IncompleteSectionError(Exception):
    """A Flex section arrived without the fields the pipeline needs.

    Flex sections are configured field-by-field in Client Portal, so a
    section can be enabled while the columns that make it meaningful are
    left unticked. Guessing past that would silently corrupt the metrics
    downstream, so the run fails with the fix spelled out (PRD §4.2).
    """


def require_columns(
    df: pd.DataFrame, required: dict[str, str], *, section: str, where: str
) -> None:
    """Raise if a non-empty section lacks usable values for load-bearing fields.

    A column that is absent *or* entirely null counts as missing: ibflex
    parses into dataclasses carrying every field, so an unticked Flex
    attribute arrives as a present-but-all-None column rather than no column
    at all. `required` maps the Flex attribute name to what it feeds, so the
    error says why each one matters.
    """
    if df.empty:
        return
    missing = {
        src: why
        for src, why in required.items()
        if src not in df.columns or df[src].isna().all()
    }
    if not missing:
        return
    populated = sorted(c for c in df.columns if not df[c].isna().all())
    detail = "\n".join(f"  - {src}: {why}" for src, why in missing.items())
    raise IncompleteSectionError(
        f"the {section} section came back without these required fields:\n{detail}\n"
        f"Fix in IBKR Client Portal: {where}, tick those fields, save, then "
        f"rerun. The section is enabled but those columns are unticked — only "
        f"{populated} carried any value across {len(df)} rows."
    )


def frame_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame → list of dicts with NaN/NaT normalized to None for the DB."""
    if df.empty:
        return []
    clean = df.astype(object).where(pd.notna(df), None)
    return cast(list[dict[str, Any]], clean.to_dict(orient="records"))
