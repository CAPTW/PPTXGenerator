"""Text-first protected-zone locking for E01H."""

from __future__ import annotations

from typing import Any


def build_text_first_lock_report(reference_analysis: dict[str, Any]) -> dict[str, Any]:
    protected = []
    for region in reference_analysis.get("semantic_text_regions", []):
        protected.append(
            {
                "zone_id": f"lock_{region['object_id']}",
                "source_object_id": region["object_id"],
                "semantic_role": region["semantic_role"],
                "bbox_norm": region["bbox_norm"],
                "bbox_px": region["bbox_px"],
                "text_value_source": "manual_visible_reference_transcription_or_semantic_slot_label",
                "ocr_confidence": None,
                "must_promote_to_ppt_text": True,
                "exclude_from_raster_backplate": True,
            }
        )
    return {
        "schema_name": "text_first_lock_report",
        "status": "passed" if protected else "failed",
        "ocr_performed": False,
        "ocr_reliable": False,
        "ocr_uncertainty_recorded": True,
        "text_like_protected_zone_count": len(protected),
        "raster_backplate_exclusion_count": len([zone for zone in protected if zone["exclude_from_raster_backplate"]]),
        "protected_zones": protected,
        "policy": "Text-like zones are locked before raster segmentation and must be reconstructed as editable PPT text.",
        "canva_parity_claimed": False,
    }


def text_first_lock_report_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Text-First Lock Report",
            "",
            f"- Status: `{report['status']}`",
            f"- OCR performed: `{report['ocr_performed']}`",
            f"- Protected text-like zones: `{report['text_like_protected_zone_count']}`",
            f"- Raster exclusion count: `{report['raster_backplate_exclusion_count']}`",
            "- Canva parity claimed: `False`",
        ]
    )
