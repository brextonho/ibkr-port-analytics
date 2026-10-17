"""User-maintained enrichment: YAML files → security_tags / position_notes (§6.2).

The YAML files are the durable source of truth for the conids they mention:
each seeded row is written whole, so a field omitted from the YAML becomes
NULL on the next run. The API's PUT endpoints are the quick-edit path — use
one or the other per conid, not both.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ingestion.config import EnrichmentSettings

logger = logging.getLogger(__name__)

SECURITY_TAG_FIELDS = ("sector", "geography", "theme")
POSITION_NOTE_FIELDS = (
    "thesis",
    "catalyst_date",
    "target_price",
    "base_price",
    "bear_price",
    "sellable_date",
)


class EnrichmentError(Exception):
    """Malformed enrichment YAML. Fail loudly — silent partial seeds drift."""


def _load_file(path: str | Path, allowed: tuple[str, ...]) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text()) or {}
    if not isinstance(data, dict):
        raise EnrichmentError(f"{p}: expected a mapping of conid -> fields")
    rows: list[dict[str, Any]] = []
    for conid, fields in data.items():
        fields = fields or {}
        if not isinstance(fields, dict):
            raise EnrichmentError(f"{p}: conid {conid}: expected a field mapping")
        unknown = set(fields) - set(allowed)
        if unknown:
            raise EnrichmentError(
                f"{p}: conid {conid}: unknown fields {sorted(unknown)}; "
                f"allowed: {list(allowed)}"
            )
        # uniform rows: absent fields become NULL (the file is source of truth)
        row: dict[str, Any] = {"conid": str(conid)}
        row.update({f: fields.get(f) for f in allowed})
        rows.append(row)
    return rows


def load_enrichment(settings: EnrichmentSettings) -> dict[str, list[dict[str, Any]]]:
    """Rows for security_tags and position_notes, stamped with updated_at."""
    now = datetime.now(timezone.utc)
    tags = _load_file(settings.security_tags_file, SECURITY_TAG_FIELDS)
    notes = _load_file(settings.position_notes_file, POSITION_NOTE_FIELDS)
    for row in (*tags, *notes):
        row["updated_at"] = now
    return {"security_tags": tags, "position_notes": notes}
