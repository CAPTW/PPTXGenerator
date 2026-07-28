"""Contract V2 gate for E04 source-bound deck."""

from __future__ import annotations

from typing import Any


FATAL_WARNING_CODES = [
    "FULL_SLIDE_RASTER",
    "BAKED_TEXT_RASTER",
    "SEMANTIC_ICON_RASTER",
    "SEMANTIC_CHART_RASTER",
    "SEMANTIC_TABLE_RASTER",
    "SOURCE_BINDING_MISSING",
    "CITATION_BINDING_MISSING",
    "SLOT_BINDING_MISSING",
    "TEXT_OVERFLOW",
    "UNKNOWN_WARNING_CODE",
    "UNRECORDED_FALLBACK",
    "UNALLOWLISTED_FALLBACK",
]


def build_e04_contract_v2_report(slot_ledger: dict[str, Any], source_ledger: dict[str, Any], citation_ledger: dict[str, Any], text_report: dict[str, Any], raster_report: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if slot_ledger.get("status") != "passed":
        failures.append("SLOT_BINDING_MISSING")
    if source_ledger.get("status") != "passed":
        failures.append("SOURCE_BINDING_MISSING")
    if citation_ledger.get("status") != "passed":
        failures.append("CITATION_BINDING_MISSING")
    if int(text_report.get("text_overflow_count", 0)) or int(text_report.get("text_clipping_count", 0)):
        failures.append("TEXT_OVERFLOW")
    if int(raster_report.get("semantic_raster_violation_count", 0)):
        failures.append("SEMANTIC_ICON_RASTER")
    return {
        "schema_name": "e04_contract_v2_report",
        "status": "passed" if not failures else "failed",
        "fatal_warning_codes": FATAL_WARNING_CODES,
        "failures": failures,
        "source_binding_required": True,
        "citation_binding_required": True,
        "selected_route": "source_bound_magic_layer_pack",
    }
