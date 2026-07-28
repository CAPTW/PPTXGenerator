"""Observed icon inventory v2 for E01.5."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .observed_icon_detector import detect_observed_icon_candidates


def build_e01_4_reclassification_for_icon_pipeline(e01_4_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e01_4_reclassification_for_icon_pipeline",
        "e01_4_status": "PASS_AS_OBSERVED_ICON_TRACE_PROOF",
        "e01_4_not_sufficient_for_user_intended_icon_pipeline": True,
        "library_first_exact_match_status": "NOT_PROVEN",
        "generated_svg_persistence_status": "PARTIAL_OR_NOT_PROVEN",
        "pptx_actual_svg_insertion_status": "NOT_PROVEN_UNTIL_E01_5_AUDIT",
        "atomic_icon_grouping_status": "INSUFFICIENT",
        "duplicate_icon_overlap_status": "NEEDS_PATCH",
        "bottom_bar_label_safety_status": "NEEDS_PATCH",
        "checklist_icon_scale_alignment_status": "NEEDS_PATCH",
        "canva_parity_claimed": False,
        "e02_unlocked": False,
        "e01_4_decision": e01_4_report.get("decision"),
        "decision": "E01_4_RECLASSIFIED_PASS_TRACE_PROOF_REQUIRE_E01_5_LIBRARY_FIRST_ATOMIC_SVG",
    }


def build_observed_icon_inventory_v2(reference_image: Path, output_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    detection, crop_manifest = detect_observed_icon_candidates(reference_image, output_root)
    inventory = {
        "schema_name": "observed_icon_inventory_v2",
        "status": "passed" if crop_manifest["crop_count"] >= 16 else "failed",
        "expected_minimum_semantic_icon_regions": 16,
        "observed_semantic_icon_count": crop_manifest["crop_count"],
        "semantic_regions": [
            {
                "region_id": crop["crop_id"],
                "observed_crop_path": crop["crop_path"],
                "bbox_px": crop["bbox_px"],
                "bbox_norm": crop["bbox_norm"],
                "likely_role": crop["role_hint"],
                "source_region": crop["component"],
                "z_order": crop["z_order"],
                "container_shape": crop.get("container_bbox_px") is not None,
                "glyph_shape": True,
                "badge_or_accent_shape": crop["shape_kind"] == "chevron_next",
                "shadow_or_decorative_support": False,
            }
            for crop in crop_manifest["crops"]
        ],
        "technical_overlays_treated_as_semantic_icons": False,
        "canva_parity_claimed": False,
    }
    for crop in crop_manifest["crops"]:
        source = Path(crop["crop_path"])
        target = output_root / "icon_crops" / source.name
        if source.resolve() != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return inventory, crop_manifest, detection
