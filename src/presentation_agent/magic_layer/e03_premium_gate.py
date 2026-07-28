"""Premium visual quality gate for E03 template packs."""

from __future__ import annotations

from typing import Any


def evaluate_premium_template_pack_gate(
    *,
    structural_native_editability_pass: bool,
    semantic_raster_violations: int,
    unknown_content_bearing_layers: int,
    duplicate_bbox_collisions: int,
    visual_richness_report: dict[str, Any],
    identity_report: dict[str, Any],
    placeholder_report: dict[str, Any],
    regression_report: dict[str, Any],
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    failures: list[str] = []
    if not protected_artifacts_unchanged:
        failures.append("protected_artifacts_changed")
    if not structural_native_editability_pass:
        failures.append("structural_native_editability_not_passed")
    if semantic_raster_violations:
        failures.append("semantic_raster_violations_present")
    if unknown_content_bearing_layers:
        failures.append("unknown_content_bearing_layers_present")
    if duplicate_bbox_collisions:
        failures.append("duplicate_bbox_collisions_present")
    if visual_richness_report.get("status") != "passed":
        failures.extend(visual_richness_report.get("failures", ["visual_richness_failed"]))
    if identity_report.get("status") != "passed":
        failures.extend(identity_report.get("failures", ["archetype_identity_failed"]))
    if placeholder_report.get("status") == "failed":
        failures.extend(placeholder_report.get("failures", ["placeholder_overdominance_failed"]))
    if regression_report.get("status") != "passed":
        failures.extend(regression_report.get("failures", ["e01x_p_visual_regression_detected"]))

    visual_design_pass = not any(
        failure
        for failure in failures
        if failure
        not in {
            "protected_artifacts_changed",
            "structural_native_editability_not_passed",
            "semantic_raster_violations_present",
            "unknown_content_bearing_layers_present",
            "duplicate_bbox_collisions_present",
        }
    )
    decision = _decision(failures)
    return {
        "schema_name": "premium_template_pack_gate_report",
        "status": "passed" if not failures else "failed",
        "decision": decision,
        "structural_native_editability_pass": structural_native_editability_pass,
        "premium_visual_design_pass": visual_design_pass,
        "visual_design_pass": visual_design_pass,
        "archetype_identity_pass": identity_report.get("status") == "passed",
        "e01x_p_visual_regression_detected": regression_report.get("status") != "passed",
        "semantic_raster_violations": semantic_raster_violations,
        "unknown_content_bearing_layers": unknown_content_bearing_layers,
        "duplicate_bbox_collisions": duplicate_bbox_collisions,
        "e04_readiness": not failures,
        "failures": sorted(set(failures)),
        "canva_parity_claimed": False,
    }


def _decision(failures: list[str]) -> str:
    if not failures:
        return "E03_VQ_PASS_E04_UNLOCK_RESTORED"
    if "protected_artifacts_changed" in failures:
        return "E03_VQ_FAIL_PROTECTED_ARTIFACTS"
    if any("identity" in failure or failure.startswith(("cover_", "section_", "visual_", "standard_", "evidence_", "card_", "methodology_", "process_", "comparison_", "data_", "table_", "timeline_")) for failure in failures):
        if any("visual_richness" in failure or "placeholder" in failure for failure in failures):
            return "E03_VQ_PATCH_VISUAL_DESIGN_REQUIRED"
        return "E03_VQ_PATCH_ARCHETYPE_IDENTITY"
    if any("regression" in failure or "e01x" in failure for failure in failures):
        return "E03_VQ_PATCH_REFERENCE_FIDELITY"
    return "E03_VQ_PATCH_VISUAL_DESIGN_REQUIRED"
