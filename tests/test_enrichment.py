"""Enrichment seeding (PRD §6.2): YAML → security_tags / position_notes."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from ingestion.analytics.exposures import position_exposures
from ingestion.config import EnrichmentSettings
from ingestion.enrichment import EnrichmentError, load_enrichment


def _settings(tmp_path, tags: str | None = None, notes: str | None = None):
    tags_file = tmp_path / "security_tags.yaml"
    notes_file = tmp_path / "position_notes.yaml"
    if tags is not None:
        tags_file.write_text(tags)
    if notes is not None:
        notes_file.write_text(notes)
    return EnrichmentSettings(
        security_tags_file=str(tags_file), position_notes_file=str(notes_file)
    )


def test_loads_rows_with_uniform_fields_and_timestamp(tmp_path):
    rows = load_enrichment(
        _settings(
            tmp_path,
            tags='"123":\n  theme: crypto\n',
            notes='"123":\n  thesis: "Because reasons."\n  target_price: 250\n',
        )
    )
    tag = rows["security_tags"][0]
    assert tag["conid"] == "123"
    assert tag["theme"] == "crypto"
    assert tag["sector"] is None  # absent fields become explicit NULLs
    assert tag["updated_at"] is not None
    note = rows["position_notes"][0]
    assert note["thesis"] == "Because reasons."
    assert note["target_price"] == 250


def test_missing_files_yield_empty_seeds(tmp_path):
    rows = load_enrichment(_settings(tmp_path))
    assert rows == {"security_tags": [], "position_notes": []}


def test_unknown_field_raises(tmp_path):
    with pytest.raises(EnrichmentError, match="unknown fields"):
        load_enrichment(_settings(tmp_path, tags='"123":\n  sektor: tech\n'))


def test_geography_override_reaches_exposures(raw_frames, tmp_path):
    tags = pd.DataFrame(
        [{"conid": "76023663", "sector": None, "geography": "GLOBAL", "theme": None}]
    )
    exp = position_exposures(
        raw_frames["positions"],
        raw_frames["securities"],
        raw_frames["nav_history"],
        dimension="geography",
        security_tags=tags,
    )
    day = exp[exp["snapshot_date"] == date(2026, 7, 15)]
    assert "GLOBAL" in set(day["bucket"])  # CSPX moved out of IE
