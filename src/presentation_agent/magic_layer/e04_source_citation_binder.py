"""Source and citation binding ledgers for E04."""

from __future__ import annotations

from typing import Any


def build_e04_source_and_citation_ledgers(slot_ledger: dict[str, Any], source_inventory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    records = {row["citation_id"]: row for row in source_inventory.get("source_records", [])}
    source_rows = []
    citation_rows = []
    missing_source = []
    missing_citation = []
    for row in slot_ledger.get("rows", []):
        citation = records.get(row.get("citation_id"))
        source_bound = bool(row.get("source_id")) and citation is not None
        citation_bound = bool(row.get("citation_id")) and citation is not None
        source_row = {**row, "source_binding_status": "bound" if source_bound else "missing", "source_anchor": citation.get("anchor") if citation else None}
        citation_row = {**row, "citation_binding_status": "bound" if citation_bound else "missing", "citation_text": citation.get("citation_text") if citation else None}
        source_rows.append(source_row)
        citation_rows.append(citation_row)
        if not source_bound:
            missing_source.append(source_row)
        if not citation_bound:
            missing_citation.append(citation_row)
    source_ledger = {
        "schema_name": "e04_source_binding_ledger",
        "status": "passed" if not missing_source else "failed",
        "source_binding_count": len(source_rows) - len(missing_source),
        "missing_source_binding_count": len(missing_source),
        "missing_source_bindings": missing_source,
        "rows": source_rows,
    }
    citation_ledger = {
        "schema_name": "e04_citation_binding_ledger",
        "status": "passed" if not missing_citation else "failed",
        "citation_binding_count": len(citation_rows) - len(missing_citation),
        "missing_citation_binding_count": len(missing_citation),
        "missing_citation_bindings": missing_citation,
        "rows": citation_rows,
    }
    return source_ledger, citation_ledger
