"""Reclassify E01.3 before observed icon parsing in E01.4."""

from __future__ import annotations

from typing import Any


def reclassify_e01_3(e01_3_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e01_3_reclassification_report",
        "semantic_role_resolution_status": "PASS" if int(e01_3_report.get("semantic_icon_role_count", 0)) > 0 else "INCONCLUSIVE",
        "semantic_raster_violation_status": "PASS" if int(e01_3_report.get("semantic_raster_violation_count", 1)) == 0 else "FAIL",
        "procedural_svg_policy_status": "PASS_FOR_ROLE_PROOF",
        "observed_icon_exact_parsing_status": "INSUFFICIENT",
        "exact_library_match_policy_status": "NOT_IMPLEMENTED_IN_E01_3",
        "vision_svg_trace_policy_status": "NOT_IMPLEMENTED_IN_E01_3",
        "generated_icon_library_persistence_status": "INSUFFICIENT",
        "e02_unlock_status": "REMAINS_LOCKED",
        "e01_4_unlock_status": True,
        "decision": "E01_3_RECLASSIFIED_AS_ROLE_SVG_PROOF_NOT_OBSERVED_ICON_PARSING",
        "canva_parity_claimed": False,
    }
