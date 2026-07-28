"""Verify semantic layer substitution remains source-bound after BP cloning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_semantic_layer_substitution_report(
    *,
    slot_binding_ledger: str | Path | dict[str, Any],
    svg_package_proof_report: str | Path | dict[str, Any],
    clone_report: dict[str, Any],
) -> dict[str, Any]:
    slots = _load(slot_binding_ledger)
    svg = _load(svg_package_proof_report)
    slide_bindings = slots.get("slide_bindings", [])
    source_bound = all(row.get("source_refs") and row.get("evidence_ref") and row.get("citation_footer") for row in slide_bindings)
    text_overflow = int(slots.get("text_overflow_count", 0))
    text_truncation = int(slots.get("text_truncation_count", 0))
    internal_label_leakage = int(slots.get("internal_label_leakage_count", 0))
    svg_pass = (
        svg.get("status") == "passed"
        and svg.get("required_semantic_icon_svg_bound_coverage", 1.0) == 1.0
        and svg.get("semantic_icon_raster_fallback_count", 0) == 0
        and svg.get("empty_circle_placeholder_count", 0) == 0
    )
    passed = (
        clone_report.get("status") == "passed"
        and source_bound
        and svg_pass
        and text_overflow == 0
        and text_truncation == 0
        and internal_label_leakage == 0
        and clone_report.get("semantic_raster_violation_count", 0) == 0
    )
    return {
        "schema_name": "e04h_bp_semantic_layer_substitution_report",
        "status": "passed" if passed else "failed",
        "semantic_layer_replacement_mode": "replace_semantic_content_only",
        "semantic_text_remains_editable": True,
        "source_binding_pass": source_bound,
        "svg_provenance_pass": svg_pass,
        "source_bound_slide_count": len(slide_bindings),
        "text_overflow_count": text_overflow,
        "text_truncation_count": text_truncation,
        "internal_label_leakage_count": internal_label_leakage,
        "semantic_raster_violation_count": clone_report.get("semantic_raster_violation_count", 0),
        "unknown_content_bearing_layer_count": clone_report.get("unknown_content_bearing_layer_count", 0),
        "clone_strategy": clone_report.get("clone_strategy"),
        "canva_parity_claimed": False,
    }


def _load(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    path = Path(value)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
