"""Build content contract schemas and gap reports."""

from __future__ import annotations

from typing import Any


def build_contract_content_schema_v1() -> dict[str, Any]:
    return {
        "schema_name": "contract_content_schema_v1",
        "required_fields": [
            "text_content_ref",
            "source_binding_id",
            "citation_binding_id",
            "slot_binding_id",
            "content_bearing",
            "visible_text",
        ],
        "source": "baseline candidate visible text and binding ledger inventory",
    }


def build_recompiled_content_gap_report(baseline_content: dict[str, Any], candidate_content: dict[str, Any]) -> dict[str, Any]:
    baseline_count = int(baseline_content.get("text_shape_count", 0))
    candidate_count = int(candidate_content.get("text_shape_count", 0))
    missing = max(0, baseline_count - candidate_count)
    return {
        "schema_name": "recompiled_content_gap_report",
        "status": "passed" if missing == 0 else "failed",
        "baseline_text_shape_count": baseline_count,
        "candidate_text_shape_count": candidate_count,
        "missing_text_count": missing,
        "missing_slide_title_count": 0 if missing == 0 else None,
    }
