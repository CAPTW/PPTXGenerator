"""E03.3 readiness gate for E03.2.4A reviewed icon library v6."""

from __future__ import annotations

from typing import Any


def build_icon_retrieval_policy_v6() -> dict[str, Any]:
    return {
        "schema_name": "icon_retrieval_policy_v6",
        "status": "passed",
        "retrieval_order": [
            "curated_v6_exact_role_and_shape_match",
            "human_approved_library_match",
            "cleaned_glyph_crop_hash_match",
            "authored_svg_from_approved_crop",
            "non_quarantined_generated_observed_svg_with_quality_pass",
            "blocker",
        ],
        "forbidden": ["quarantined_svg", "contaminated_crop", "role_only_generic", "plus_placeholder", "raster_fallback"],
        "semantic_raster_fallback_allowed": False,
    }


def build_e03_3_readiness_report(
    *,
    annotation_mapping: dict[str, Any],
    review_resolution: dict[str, Any],
    role_resolution: dict[str, Any],
    authored_quality: dict[str, Any],
    curated_manifest: dict[str, Any],
    policy: dict[str, Any],
    protected_unchanged: bool,
    decision_namespace: str = "E03_2_4A",
) -> dict[str, Any]:
    unresolved_p0 = max(int(review_resolution.get("unresolved_p0_count", 0)), int(role_resolution.get("unresolved_p0_count", 0)))
    unresolved_p1 = max(int(review_resolution.get("unresolved_p1_count", 0)), int(role_resolution.get("unresolved_required_p1_count", 0)))
    semantic_raster = int(authored_quality.get("semantic_raster_icon_count", 0)) + int(curated_manifest.get("semantic_raster_icon_count", 0))
    concrete_annotations = int(annotation_mapping.get("concrete_annotation_count", 0))
    mapping_complete = bool(annotation_mapping.get("mapping_complete"))
    ready = (
        mapping_complete
        and concrete_annotations > 0
        and review_resolution.get("status") == "passed"
        and unresolved_p0 == 0
        and unresolved_p1 == 0
        and authored_quality.get("status") in {"passed", "not_run"}
        and curated_manifest.get("status") == "passed"
        and int(curated_manifest.get("quarantined_svg_reused_count", 0)) == 0
        and int(curated_manifest.get("generic_placeholder_count", 0)) == 0
        and policy.get("status") == "passed"
        and semantic_raster == 0
        and protected_unchanged
    )
    return {
        "schema_name": "e03_3_readiness_report",
        "status": "passed" if ready else "locked",
        "decision": f"{decision_namespace}_PASS_START_E03_3_BATCH_OBJECT_PLACEMENT_GENERALIZATION" if ready else _blocked_decision(decision_namespace, mapping_complete, concrete_annotations, unresolved_p0, unresolved_p1, authored_quality, curated_manifest, semantic_raster, protected_unchanged),
        "e03_3_unlocked": ready,
        "e04_unlocked": False,
        "e04_lock_status": "LOCKED_PENDING_E03_3_16_OF_16",
        "annotation_mapping_complete": mapping_complete,
        "concrete_annotation_count": concrete_annotations,
        "review_queue_fully_resolved": review_resolution.get("status") == "passed",
        "unresolved_p0_count": unresolved_p0,
        "unresolved_required_p1_count": unresolved_p1,
        "authored_svg_quality_passes": authored_quality.get("status") in {"passed", "not_run"},
        "curated_v6_exists": curated_manifest.get("status") == "passed",
        "retrieval_policy_v6_exists": policy.get("status") == "passed",
        "semantic_raster_icon_count": semantic_raster,
        "protected_artifacts_unchanged": protected_unchanged,
        "broad_canva_parity_claimed": False,
    }


def _blocked_decision(decision_namespace: str, mapping_complete: bool, concrete_annotations: int, unresolved_p0: int, unresolved_p1: int, quality: dict[str, Any], curated: dict[str, Any], semantic_raster: int, protected_unchanged: bool) -> str:
    if not protected_unchanged:
        return f"{decision_namespace}_FAIL_PROTECTED_ARTIFACTS"
    if semantic_raster:
        return f"{decision_namespace}_FAIL_SEMANTIC_RASTER_ICON_POLICY"
    if not mapping_complete or concrete_annotations == 0:
        return f"{decision_namespace}_PATCH_ANNOTATION_MAPPING_REQUIRED"
    if unresolved_p0:
        return f"{decision_namespace}_PATCH_P0_ROLE_RESOLUTION_REQUIRED"
    if unresolved_p1:
        return f"{decision_namespace}_PATCH_P0_ROLE_RESOLUTION_REQUIRED"
    if quality.get("status") == "failed":
        return f"{decision_namespace}_PATCH_MANUAL_SVG_AUTHORING_REQUIRED"
    if curated.get("status") != "passed":
        return f"{decision_namespace}_PATCH_CURATED_V6_REQUIRED"
    return f"{decision_namespace}_PATCH_CURATED_V6_REQUIRED"
