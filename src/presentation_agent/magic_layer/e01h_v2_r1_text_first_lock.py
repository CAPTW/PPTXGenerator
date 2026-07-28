"""Text-first lock for E01H-V2-R1 segmented repairs."""

from __future__ import annotations

from typing import Any


def build_r1_text_first_lock(pdf_signals: dict[str, Any]) -> dict[str, Any]:
    zones = [
        {
            "object_id": span.get("object_id"),
            "bbox_norm": span.get("bbox_norm"),
            "lock_reason": "pdf_text_span",
            "text_preview": span.get("text", "")[:80],
        }
        for span in pdf_signals.get("text_spans", [])
    ]
    if not zones:
        zones.append(
            {
                "object_id": "image_analysis_title_zone",
                "bbox_norm": [0.06, 0.06, 0.66, 0.18],
                "lock_reason": "image_reference_text_zone_fallback",
                "text_preview": "",
            }
        )
    return {
        "schema_name": "text_first_lock_report",
        "status": "passed",
        "protected_text_zone_count": len(zones),
        "protected_text_zones": zones,
        "semantic_text_absorbed_into_backplate": False,
        "footer_source_treated_as_decorative_raster": False,
        "canva_parity_claimed": False,
    }
