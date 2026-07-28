"""E01.1 visual defect register for the E01.2 patch."""

from __future__ import annotations

from typing import Any


DEFECT_CATEGORIES = [
    "TEXT_RUN_FORMATTING_LOSS",
    "TEXT_CONTRAST_FAILURE",
    "CHECKLIST_TITLE_COLLISION",
    "CHECKLIST_CARD_GEOMETRY_DRIFT",
    "CHECKLIST_BODY_OVERFLOW_OR_CLIP",
    "CHECKLIST_ICON_ROLE_MISMATCH",
    "BOTTOM_ACTION_ICON_ROLE_MISMATCH",
    "BOTTOM_ACTION_BAR_DENSITY_LOSS",
    "THUMBNAIL_CALLOUT_ALIGNMENT_DRIFT",
    "HERO_LAYER_SEGMENTATION_INSUFFICIENT",
    "TECHNICAL_OVERLAY_UNDER_RECONSTRUCTED",
    "SOURCE_FOOTER_TOO_WEAK_OR_TOO_SMALL",
    "REGION_SPECIFIC_RENDER_DIFF_HIGH",
]


def build_e01_1_visual_defect_register(e01_1_report: dict[str, Any], visual_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e01_1_visual_defect_register",
        "status": "patch_required",
        "source_decision": e01_1_report.get("decision"),
        "source_visual_similarity_proxy": visual_report.get("visual_similarity_proxy"),
        "defect_count": len(DEFECT_CATEGORIES),
        "defects": [
            {
                "defect_id": category.lower(),
                "category": category,
                "severity": "HIGH_PRODUCT_RISK" if category in {"REGION_SPECIFIC_RENDER_DIFF_HIGH", "HERO_LAYER_SEGMENTATION_INSUFFICIENT"} else "MEDIUM_PATCH",
                "evidence": "Visual review of E01.1 reference-vs-render contact sheets.",
                "target_patch": "E01.2 render fidelity and semantic polish",
            }
            for category in DEFECT_CATEGORIES
        ],
        "canva_parity_claimed": False,
    }

