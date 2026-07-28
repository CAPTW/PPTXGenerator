"""D06 Magic Layer batch reference conversion helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


PRODUCTION_REFERENCE_IDS = [
    "cover_hero",
    "standard_content",
    "data_dashboard",
    "table_heavy",
    "section_divider",
    "visual_toc",
    "evidence_overview",
    "card_grid",
    "methodology_framework",
    "process_flow",
    "comparison_matrix",
    "timeline_roadmap",
    "decision_record",
    "risk_register",
    "case_study",
    "closing_synthesis",
]

CANONICAL_PACK_PATHS = {
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def batch_conversion_policy_v1() -> dict[str, Any]:
    return {
        "schema_name": "batch_conversion_policy_v1",
        "template_reference_policy": "references_are_template_archetype_inputs_not_final_slide_content",
        "reference_text_policy": "slot_evidence_only_not_final_copy",
        "full_slide_raster_background_allowed": False,
        "screenshot_slide_allowed": False,
        "semantic_icon_chart_table_raster_final_use_allowed": False,
        "scoped_raster_allowed": "nonsemantic_photo_hero_or_decorative_visual_field_only",
        "unknown_content_bearing_layers_blocking": True,
        "ocr_text_final_copy_allowed": False,
        "text_ocr_risk_status": "bounded_when_slot_geometry_reliable",
        "mask_polygon_risk_status": "bounded_when_major_region_fidelity_preserved",
        "canva_benchmark_production_scope_allowed": False,
        "canva_parity_claimed": False,
    }


def build_batch_reference_inventory(reference_defs: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    missing_ids: list[str] = []
    unreadable_ids: list[str] = []
    aspect_failures: list[str] = []
    rendered_output_refs: list[str] = []
    canva_in_production: list[str] = []

    for ref in reference_defs:
        reference_id = str(ref["reference_id"])
        path = Path(ref["path"])
        if reference_id in seen:
            duplicate_ids.append(reference_id)
        seen.add(reference_id)
        if reference_id == "canva_benchmark" or "benchmarks/canva_magic_layer" in path.as_posix():
            canva_in_production.append(reference_id)
        if any(part in path.as_posix() for part in ["/outputs/", "\\outputs\\"]) and "/refs/" not in path.as_posix() and "\\refs\\" not in path.as_posix():
            rendered_output_refs.append(reference_id)
        if not path.exists():
            missing_ids.append(reference_id)
            entries.append({**ref, "status": "missing", "path": path.as_posix()})
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception as exc:  # noqa: BLE001 - inventory must record unreadable refs.
            unreadable_ids.append(reference_id)
            entries.append({**ref, "status": "unreadable", "path": path.as_posix(), "error": str(exc)})
            continue
        aspect_ratio = width / height if height else 0.0
        near_16_9 = 1.70 <= aspect_ratio <= 1.86
        if not near_16_9:
            aspect_failures.append(reference_id)
        entries.append(
            {
                **ref,
                "path": path.as_posix(),
                "status": "available" if near_16_9 else "aspect_ratio_warning",
                "width": width,
                "height": height,
                "aspect_ratio": round(aspect_ratio, 4),
                "near_16_9": near_16_9,
                "production_scope": True,
            }
        )

    required_missing = [item for item in PRODUCTION_REFERENCE_IDS if item not in seen]
    status = "passed"
    if missing_ids or unreadable_ids or aspect_failures or duplicate_ids or rendered_output_refs or canva_in_production or required_missing:
        status = "failed"
    return {
        "schema_name": "batch_reference_inventory",
        "status": status,
        "required_reference_count": len(PRODUCTION_REFERENCE_IDS),
        "production_reference_count": len(entries),
        "entries": entries,
        "missing_reference_ids": sorted(set(missing_ids + required_missing)),
        "unreadable_reference_ids": unreadable_ids,
        "aspect_ratio_failure_ids": aspect_failures,
        "duplicate_archetype_ids": duplicate_ids,
        "rendered_output_reference_ids": rendered_output_refs,
        "canva_benchmark_in_production_scope": bool(canva_in_production),
        "canva_boundary_only": True,
        "canva_parity_claimed": False,
    }


def validate_batch_reference_inventory(inventory: dict[str, Any]) -> list[str]:
    errors = []
    if inventory.get("canva_benchmark_in_production_scope"):
        errors.append("canva_benchmark_cannot_be_production_template_reference")
    for key in ["missing_reference_ids", "unreadable_reference_ids", "aspect_ratio_failure_ids", "duplicate_archetype_ids", "rendered_output_reference_ids"]:
        if inventory.get(key):
            errors.append(f"{key}:{','.join(inventory[key])}")
    if inventory.get("production_reference_count") != len(PRODUCTION_REFERENCE_IDS):
        errors.append("production_reference_count_must_be_16")
    return errors


def build_patch_queue_d06(reference_results: list[dict[str, Any]]) -> dict[str, Any]:
    patches: list[dict[str, Any]] = []
    for result in reference_results:
        archetype_id = result["archetype_id"]
        if not result.get("candidate_compiled") or not result.get("candidate_rendered"):
            patches.append(_patch(archetype_id, "render_failure", "Candidate did not compile/render.", "CRITICAL_BLOCKER", True, True))
        if result.get("visual_fidelity_status") != "passed":
            patches.append(_patch(archetype_id, "visual_fidelity", "Reference-vs-render fidelity did not meet D06 threshold.", "HIGH_PRODUCT_RISK", True, True))
        if result.get("semantic_editability_status") != "passed" or result.get("semantic_raster_count", 0):
            patches.append(_patch(archetype_id, "semantic_editability", "Semantic editability gate failed or raster semantic fallback appeared.", "CRITICAL_BLOCKER", True, True))
        if result.get("unknown_content_bearing_layer_count", 0):
            patches.append(_patch(archetype_id, "unknown_layer", "Content-bearing unknown layer remains unresolved.", "CRITICAL_BLOCKER", True, True))
        if result.get("text_ocr_risk_status") != "bounded":
            patches.append(_patch(archetype_id, "text_ocr_risk", "Text/OCR slot geometry risk is unbounded.", "HIGH_PRODUCT_RISK", True, True))
        if result.get("mask_polygon_risk_status") != "bounded":
            patches.append(_patch(archetype_id, "mask_polygon_risk", "Mask/polygon risk is unbounded.", "HIGH_PRODUCT_RISK", True, True))
    if not patches:
        patches.extend(
            [
                _patch("batch", "text_ocr_risk", "OCR remains unavailable; source-bound D07 must fill editable text from source, not OCR.", "MEDIUM_PATCH", False, False),
                _patch("batch", "mask_polygon_risk", "Masks remain mostly rectangular; D07 should avoid relying on exact polygon masks.", "MEDIUM_PATCH", False, False),
            ]
        )
    return {
        "schema_name": "patch_queue_d06",
        "patch_count": len(patches),
        "critical_blocker_count": sum(1 for item in patches if item["severity"] == "CRITICAL_BLOCKER"),
        "high_product_risk_count": sum(1 for item in patches if item["severity"] == "HIGH_PRODUCT_RISK"),
        "patches": patches,
    }


def build_d07_readiness(
    reference_results: list[dict[str, Any]],
    patch_queue: dict[str, Any],
    *,
    candidate_pack_exists: bool,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    processed = len(reference_results) == len(PRODUCTION_REFERENCE_IDS)
    compiled = all(item.get("candidate_compiled") for item in reference_results)
    rendered = all(item.get("candidate_rendered") for item in reference_results)
    no_background = all(item.get("no_full_slide_background") for item in reference_results)
    no_screenshot = all(item.get("no_screenshot_slide") for item in reference_results)
    semantic_ok = all(item.get("semantic_editability_status") == "passed" and item.get("semantic_raster_count", 0) == 0 for item in reference_results)
    unknown_ok = all(item.get("unknown_content_bearing_layer_count", 0) == 0 for item in reference_results)
    text_bounded = all(item.get("text_ocr_risk_status") == "bounded" for item in reference_results)
    mask_bounded = all(item.get("mask_polygon_risk_status") == "bounded" for item in reference_results)
    visual_ok = all(item.get("visual_fidelity_status") == "passed" for item in reference_results)
    no_high = patch_queue.get("critical_blocker_count", 0) == 0 and patch_queue.get("high_product_risk_count", 0) == 0
    accepted_without_pack = processed and compiled and rendered and visual_ok and semantic_ok
    unlocked = (
        processed
        and compiled
        and rendered
        and (candidate_pack_exists or accepted_without_pack)
        and no_background
        and no_screenshot
        and semantic_ok
        and unknown_ok
        and text_bounded
        and mask_bounded
        and visual_ok
        and no_high
        and protected_artifacts_unchanged
    )
    if not protected_artifacts_unchanged:
        decision = "D06_FAIL_PROTECTED_ARTIFACTS"
    elif not processed or not compiled or not rendered:
        decision = "D06_FAIL_REFERENCE_BATCH"
    elif not semantic_ok:
        decision = "D06_PATCH_SEMANTIC_EDITABILITY"
    elif not unknown_ok:
        decision = "D06_PATCH_UNKNOWN_LAYER_POLICY"
    elif not visual_ok:
        decision = "D06_PATCH_RENDER_FIDELITY"
    elif not text_bounded:
        decision = "D06_PATCH_TEXT_OCR_RISK"
    elif not mask_bounded:
        decision = "D06_PATCH_MASK_POLYGON_RISK"
    else:
        decision = "D06_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D07"
    return {
        "schema_name": "d07_readiness_report",
        "decision": decision,
        "d07_unlocked": unlocked and decision in {"D06_PASS_START_D07_SOURCE_BOUND_SMALL_DECK", "D06_PASS_WITH_LIMITED_TEXT_AND_MASK_RISK_START_D07"},
        "unlock_conditions": {
            "production_references_processed_16_of_16": processed,
            "isolated_candidates_compile_16_of_16": compiled,
            "isolated_candidates_render_16_of_16": rendered,
            "candidate_pack_exists_or_isolated_accepted": candidate_pack_exists or accepted_without_pack,
            "no_full_slide_reference_background": no_background,
            "no_screenshot_slide": no_screenshot,
            "semantic_components_editable_or_explicitly_rejected": semantic_ok,
            "no_semantic_raster_icon_chart_table": semantic_ok,
            "unknown_content_bearing_layers_zero": unknown_ok,
            "text_ocr_risk_bounded": text_bounded,
            "mask_polygon_risk_bounded": mask_bounded,
            "visual_fidelity_acceptable_all_production_references": visual_ok,
            "no_critical_blockers": patch_queue.get("critical_blocker_count", 0) == 0,
            "no_high_product_risks": patch_queue.get("high_product_risk_count", 0) == 0,
            "source_bound_deck_created": False,
            "bulk_deck_created": False,
            "c11_remains_frozen": True,
            "protected_artifacts_unchanged": protected_artifacts_unchanged,
        },
        "canva_parity_claimed": False,
    }


def validate_candidate_pack_path(path: Path) -> list[str]:
    normalized = path.as_posix().replace("\\", "/")
    if normalized in CANONICAL_PACK_PATHS or normalized.endswith("/outputs/golden_template_masters.pptx"):
        return ["candidate_pack_cannot_overwrite_canonical_golden_masters"]
    return []


def _patch(archetype_id: str, category: str, issue: str, severity: str, d06_1_required: bool, d07_locked: bool) -> dict[str, Any]:
    return {
        "archetype_id": archetype_id,
        "reference_id": archetype_id,
        "issue": issue,
        "evidence": category,
        "severity": severity,
        "category": category,
        "proposed_action": "Patch the D06 per-reference conversion and rerun D06.1." if d06_1_required else "Carry forward as bounded engine limitation.",
        "D06_1_required": d06_1_required,
        "D07_remains_locked": d07_locked,
    }
