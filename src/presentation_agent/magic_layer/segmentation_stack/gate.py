"""Magic Layer+ segmentation stack gate for E01X."""

from __future__ import annotations

from typing import Any


def evaluate_segmentation_stack_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    block_reasons: list[str] = []
    decision = "E01X_PASS_READY_FOR_E01_CONVERSION"

    if not candidate.get("protected_artifacts_unchanged", True):
        decision = "E01X_FAIL_PROTECTED_ARTIFACTS"
        block_reasons.append("protected_canonical_artifacts_changed")
    elif not candidate.get("reference_image_present", False):
        decision = "E01X_BLOCKED_MISSING_REFERENCE_IMAGE"
        block_reasons.append("missing_reference_image")
    elif candidate.get("semantic_raster_violation_count", 0) > 0 or candidate.get("full_slide_raster_detected") or candidate.get("screenshot_slide_detected"):
        decision = "E01X_FAIL_SEMANTIC_RASTER_POLICY"
        if candidate.get("semantic_raster_violation_count", 0) > 0:
            block_reasons.append("semantic_raster_violation")
        if candidate.get("full_slide_raster_detected") or candidate.get("screenshot_slide_detected"):
            block_reasons.append("full_slide_raster_or_screenshot_candidate")
    elif candidate.get("unknown_content_bearing_layer_count", 0) > 0:
        decision = "E01X_FAIL_UNKNOWN_CONTENT_BEARING_LAYERS"
        block_reasons.append("unknown_content_bearing_layer")
    elif candidate.get("real_model_proposal_count", 0) <= 0:
        decision = "E01X_BLOCKED_NO_REAL_PROPOSAL_MODELS"
        block_reasons.append("no_real_proposal_models")
        if candidate.get("proposal_stack_heuristic_only"):
            block_reasons.append("heuristic_only_proposal_stack")
    elif candidate.get("text_bearing_reference") and candidate.get("text_first_lock_status") == "unavailable":
        decision = "E01X_BLOCKED_TEXT_FIRST_LOCK_UNAVAILABLE"
        block_reasons.append("text_first_lock_unavailable_for_text_bearing_reference")
    elif candidate.get("semantic_objects_without_native_target", 0) > 0:
        decision = "E01X_PATCH_NATIVE_RECONSTRUCTION_READINESS"
        block_reasons.append("semantic_objects_without_native_target")
    elif candidate.get("native_promotion_readiness_rate", 0) < 1.0:
        decision = "E01X_PATCH_NATIVE_RECONSTRUCTION_READINESS"
        block_reasons.append("native_promotion_readiness_incomplete")
    elif candidate.get("adapter_runtime_failures", 0) > 0:
        decision = "E01X_PATCH_ADAPTER_INTEGRATION"
        block_reasons.append("adapter_runtime_failures")

    status = "passed" if decision == "E01X_PASS_READY_FOR_E01_CONVERSION" else "blocked"
    return {
        "schema_name": "segmentation_stack_gate_report",
        "schema_version": "1.0",
        "status": status,
        "decision": decision,
        "block_reasons": block_reasons,
        "semantic_raster_violation_count": int(candidate.get("semantic_raster_violation_count", 0)),
        "unknown_content_bearing_layer_count": int(candidate.get("unknown_content_bearing_layer_count", 0)),
        "real_proposal_adapter_count": int(candidate.get("real_proposal_adapter_count", 0)),
        "real_model_proposal_count": int(candidate.get("real_model_proposal_count", 0)),
        "proposal_stack_heuristic_only": bool(candidate.get("proposal_stack_heuristic_only", False)),
        "text_first_lock_status": candidate.get("text_first_lock_status"),
        "native_promotion_readiness_rate": candidate.get("native_promotion_readiness_rate", 0),
        "e01_may_start": decision == "E01X_PASS_READY_FOR_E01_CONVERSION",
        "canva_parity_claimed": False,
    }


def gate_report_markdown(report: dict[str, Any]) -> str:
    reasons = report.get("block_reasons") or ["none"]
    return "\n".join(
        [
            "# E01X Segmentation Stack Gate Report",
            "",
            f"- Final decision: `{report['decision']}`",
            f"- Status: `{report['status']}`",
            f"- E01 may start: `{report['e01_may_start']}`",
            f"- Semantic raster violations: `{report['semantic_raster_violation_count']}`",
            f"- Unknown content-bearing layers: `{report['unknown_content_bearing_layer_count']}`",
            f"- Real proposal adapters: `{report['real_proposal_adapter_count']}`",
            f"- Real model proposals: `{report['real_model_proposal_count']}`",
            f"- Heuristic-only status: `{report['proposal_stack_heuristic_only']}`",
            f"- Text-first lock status: `{report['text_first_lock_status']}`",
            "",
            "## Block Reasons",
            "",
            *[f"- `{reason}`" for reason in reasons],
            "",
            "Canva parity claimed: `False`",
        ]
    ) + "\n"
