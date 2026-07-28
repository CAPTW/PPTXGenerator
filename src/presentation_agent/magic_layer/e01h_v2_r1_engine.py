"""Engine-level policy and readiness helpers for E01H-V2-R1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_r1_policy_artifacts() -> dict[str, dict[str, Any]]:
    return {
        "segmented_backplate_policy_r1": {
            "schema_name": "segmented_backplate_policy_r1",
            "status": "active",
            "allowed": [
                "background substrate as native fill or nonsemantic texture",
                "bounded decorative texture",
                "hero/photo field that excludes semantic text",
                "chart/table/card depth shadow without duplicate chrome",
                "decorative ornament and technical overlay",
            ],
            "forbidden": [
                "full page raster",
                "blurred full reference image",
                "semantic-contaminated crop",
                "placeholder/debug boxes",
                "duplicate chrome",
                "raster containing text/table/chart/icon",
            ],
            "canva_parity_claimed": False,
        },
        "internal_label_removal_policy": {
            "schema_name": "internal_label_removal_policy",
            "status": "active",
            "visible_internal_labels_allowed": False,
            "labels_allowed_in_json_reports_only": True,
            "canva_parity_claimed": False,
        },
        "full_reference_backplate_ban_policy": {
            "schema_name": "full_reference_backplate_ban_policy",
            "status": "active",
            "full_reference_image_background_allowed": False,
            "large_blurred_page_backplate_allowed": False,
            "largest_picture_area_threshold": 0.50,
            "canva_parity_claimed": False,
        },
        "fixture_truth_scoring_only_policy": {
            "schema_name": "fixture_truth_scoring_only_policy",
            "status": "active",
            "source_layer_truth_allowed_for_compilation": False,
            "source_layer_truth_allowed_for_scoring": True,
            "production_inputs": ["reference.pdf object extraction", "PDF text spans", "PDF vector primitives", "PDF image objects", "rendered reference image analysis", "SVG resolver", "style analysis"],
            "canva_parity_claimed": False,
        },
        "semantic_reconstruction_depth_policy": {
            "schema_name": "semantic_reconstruction_depth_policy",
            "status": "active",
            "minimum_semantic_text_reconstruction_depth": 0.75,
            "minimum_semantic_object_reconstruction_depth": 0.70,
            "minimum_chart_table_truth_match": 0.70,
            "generic_overlay_boxes_count_as_reconstruction": False,
            "canva_parity_claimed": False,
        },
        "style_foreground_transfer_policy": {
            "schema_name": "style_foreground_transfer_policy",
            "status": "active",
            "foreground_components_must_inherit_style": True,
            "preserve_light_non_dark_styles": True,
            "forbid_dark_cyan_normalization": True,
            "canva_parity_claimed": False,
        },
        "actual_strategy_classification_policy": {
            "schema_name": "actual_strategy_classification_policy",
            "status": "active",
            "allowed_pass_strategies": ["hybrid_backplate_semantic_native", "native_shape_reconstruction_baseline"],
            "forbidden_pass_strategies": ["raster_page_baseline", "text_lift_overlay_baseline", "unknown_or_mixed"],
            "gate_on_observed_strategy": True,
            "canva_parity_claimed": False,
        },
    }


def build_r1_manifest(final: dict[str, Any], case_count: int, output_dir: str) -> dict[str, Any]:
    return {
        "schema_name": "e01h_v2_r1_manifest",
        "status": final.get("status"),
        "decision": final.get("decision"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_folder": output_dir,
        "case_count": case_count,
        "e02h_v2_unlocked": final.get("e02h_v2_unlocked", False),
        "e05_unlocked": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }


def build_r1_readiness(final: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    e02_unlocked = final.get("decision") == "E01H_V2_R1_PASS_READY_FOR_E02H_V2_GENERALIZATION"
    e02 = {
        "schema_name": "e02h_v2_readiness_after_e01h_v2_r1",
        "status": "ready" if e02_unlocked else "locked",
        "e02h_v2_unlocked": e02_unlocked,
        "reason": "E01H-V2-R1 passed all repaired validation gates." if e02_unlocked else "E01H-V2-R1 did not pass all repaired validation gates.",
        "e02h_v2_started": False,
        "e05_unlocked": False,
        "canva_parity_claimed": False,
    }
    e05 = {
        "schema_name": "e05_readiness_after_e01h_v2_r1",
        "status": "locked",
        "e05_unlocked": False,
        "reason": "E01H-V2-R1 may not unlock E05; E05 remains locked.",
        "e05_started": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }
    return e02, e05


def build_r1_final_decision(decision: str, reason: str) -> dict[str, Any]:
    return {
        "schema_name": "e01h_v2_r1_final_decision",
        "status": "passed" if decision == "E01H_V2_R1_PASS_READY_FOR_E02H_V2_GENERALIZATION" else "patch_required",
        "decision": decision,
        "reason": reason,
        "e02h_v2_unlocked": decision == "E01H_V2_R1_PASS_READY_FOR_E02H_V2_GENERALIZATION",
        "e02h_v2_started": False,
        "e05_unlocked": False,
        "e05_started": False,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }
