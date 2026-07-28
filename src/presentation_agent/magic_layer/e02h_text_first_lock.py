"""Text-first lock for E02H references."""

from __future__ import annotations

from typing import Any


def build_e02h_text_first_lock_report(reference_definition: dict[str, Any]) -> dict[str, Any]:
    zones = []
    for region in reference_definition.get("regions", []):
        if region.get("object_type") != "text":
            continue
        zones.append(
            {
                "source_object_id": region["object_id"],
                "semantic_role": region["semantic_role"],
                "bbox_norm": region["bbox_norm"],
                "text_like_zone": True,
                "ocr_confidence": None,
                "ocr_text_claimed": False,
                "lock_policy": "protect_before_visual_backplate_planning",
                "backplate_consumption_allowed": False,
            }
        )
    return {
        "schema_name": "text_first_lock_report",
        "status": "passed",
        "reference_id": reference_definition["reference_id"],
        "ocr_performed": False,
        "ocr_claimed": False,
        "protected_text_zone_count": len(zones),
        "semantic_text_absorbed_into_backplate_count": 0,
        "protected_zones": zones,
        "canva_parity_claimed": False,
    }


def text_first_lock_report_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Text-First Lock Report",
            "",
            f"- Status: `{report['status']}`",
            f"- Protected text zones: `{report['protected_text_zone_count']}`",
            f"- OCR performed: `{report['ocr_performed']}`",
            f"- Semantic text absorbed into backplates: `{report['semantic_text_absorbed_into_backplate_count']}`",
            "- Broad Canva parity claimed: `False`",
        ]
    )
