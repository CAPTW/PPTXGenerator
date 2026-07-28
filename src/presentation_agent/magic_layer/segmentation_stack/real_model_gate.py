"""E01X-R4 real model readiness gate."""

from __future__ import annotations

from typing import Any


def evaluate_r4_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    decision = "E01X_R4_READY_FOR_E01X_REENTRY"

    if not candidate.get("protected_artifacts_unchanged", True):
        decision = "E01X_R4_FAIL_PROTECTED_ARTIFACTS"
        reasons.append("protected_artifacts_changed")
    elif not candidate.get("reference_image_present", False):
        decision = "E01X_R4_BLOCKED_MODEL_PACK_NOT_CONFIGURED"
        reasons.append("reference_image_missing")
    elif candidate.get("fake_proposal_count", 0) > 0 or (
        candidate.get("total_real_proposal_count", 0) == 0 and candidate.get("total_heuristic_proposal_count", 0) > 0
    ):
        decision = "E01X_R4_BLOCKED_MODEL_PACK_NOT_CONFIGURED"
        reasons.append("fake_or_heuristic_only_proposals_rejected")
    elif candidate.get("adapter_runtime_failure_count", 0) > 0 and candidate.get("total_real_proposal_count", 0) == 0:
        decision = "E01X_R4_BLOCKED_ADAPTER_RUNTIME_FAILURE"
        reasons.append("configured_adapter_runtime_failure")
    elif candidate.get("real_text_adapter_count", 0) == 0 and candidate.get("real_non_text_adapter_count", 0) == 0:
        decision = "E01X_R4_BLOCKED_MODEL_PACK_NOT_CONFIGURED"
        reasons.append("no_real_adapters_available")
    elif candidate.get("real_text_adapter_count", 0) > 0 and candidate.get("real_non_text_adapter_count", 0) == 0:
        decision = "E01X_R4_PARTIAL_TEXT_ONLY_NEEDS_LAYOUT_OR_OBJECT_MODEL"
        reasons.append("missing_non_text_layout_object_layer_or_mask_model")
    elif candidate.get("real_text_adapter_count", 0) == 0 and candidate.get("real_non_text_adapter_count", 0) > 0:
        decision = "E01X_R4_PARTIAL_LAYOUT_ONLY_NEEDS_TEXT_FIRST_LOCK"
        reasons.append("missing_text_first_lock_model")
    elif not candidate.get("text_first_lock_available", False):
        decision = "E01X_R4_BLOCKED_TEXT_FIRST_LOCK_UNAVAILABLE"
        reasons.append("text_first_lock_unavailable")
    elif not candidate.get("non_text_proposal_available", False):
        decision = "E01X_R4_BLOCKED_NO_NON_TEXT_PROPOSAL_MODEL"
        reasons.append("non_text_proposal_model_unavailable")
    elif candidate.get("fusion_accepted_object_count", 0) <= 0:
        decision = "E01X_R4_PATCH_ADAPTER_IMPLEMENTATION"
        reasons.append("fusion_produced_no_accepted_objects")

    return {
        "schema_name": "e01x_r4_gate_report",
        "schema_version": "1.0",
        "decision": decision,
        "status": "ready" if decision == "E01X_R4_READY_FOR_E01X_REENTRY" else "blocked",
        "block_reasons": reasons,
        "e01x_may_be_rerun": decision == "E01X_R4_READY_FOR_E01X_REENTRY",
        "e01_may_start": False,
        "canva_parity_claimed": False,
        **{key: candidate.get(key) for key in sorted(candidate.keys())},
    }


def r4_gate_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E01X-R4 Gate Report",
        "",
        f"- Decision: `{report['decision']}`",
        f"- Status: `{report['status']}`",
        f"- E01X may be rerun: `{report['e01x_may_be_rerun']}`",
        f"- E01 may start: `{report['e01_may_start']}`",
        f"- Real text adapters: `{report.get('real_text_adapter_count', 0)}`",
        f"- Real non-text adapters: `{report.get('real_non_text_adapter_count', 0)}`",
        f"- Total real proposals: `{report.get('total_real_proposal_count', 0)}`",
        f"- Total heuristic proposals: `{report.get('total_heuristic_proposal_count', 0)}`",
        "",
        "## Block Reasons",
        "",
    ]
    lines.extend(f"- `{reason}`" for reason in report.get("block_reasons", []) or ["none"])
    lines.append("")
    lines.append("Canva parity claimed: `False`")
    return "\n".join(lines) + "\n"


def evaluate_r5_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    decision = "E01X_R5_READY_FOR_E01X_REENTRY"
    if not candidate.get("protected_artifacts_unchanged", True):
        decision = "E01X_R5_FAIL_PROTECTED_ARTIFACTS"
        reasons.append("protected_artifacts_changed")
    elif not candidate.get("reference_image_present", False):
        decision = "E01X_R5_BLOCKED_CREATE_LOCAL_MODEL_PACK_MANIFEST"
        reasons.append("reference_image_missing")
    elif not candidate.get("manifest_present", False):
        decision = "E01X_R5_BLOCKED_CREATE_LOCAL_MODEL_PACK_MANIFEST"
        reasons.append("local_model_pack_manifest_missing")
    elif candidate.get("missing_model_path_count", 0) > 0:
        decision = "E01X_R5_BLOCKED_MODEL_PATHS_MISSING"
        reasons.append("model_paths_missing")
    elif candidate.get("total_real_proposal_count", 0) == 0 and candidate.get("total_heuristic_proposal_count", 0) > 0:
        decision = "E01X_R5_BLOCKED_CREATE_LOCAL_MODEL_PACK_MANIFEST"
        reasons.append("heuristic_only_proposals_rejected")
    elif candidate.get("adapter_runtime_failure_count", 0) > 0 and candidate.get("total_real_proposal_count", 0) == 0:
        decision = "E01X_R5_BLOCKED_ADAPTER_RUNTIME_FAILURE"
        reasons.append("adapter_runtime_failure")
    elif candidate.get("real_text_adapter_count", 0) == 0 and candidate.get("real_non_text_adapter_count", 0) == 0:
        decision = "E01X_R5_BLOCKED_CREATE_LOCAL_MODEL_PACK_MANIFEST"
        reasons.append("no_real_adapters_available")
    elif candidate.get("real_text_adapter_count", 0) > 0 and candidate.get("real_non_text_adapter_count", 0) == 0:
        decision = "E01X_R5_PARTIAL_TEXT_ONLY_NEEDS_NON_TEXT_MODEL"
        reasons.append("non_text_adapter_missing")
    elif candidate.get("real_text_adapter_count", 0) == 0 and candidate.get("real_non_text_adapter_count", 0) > 0:
        decision = "E01X_R5_PARTIAL_NON_TEXT_ONLY_NEEDS_TEXT_FIRST_LOCK"
        reasons.append("text_adapter_missing")
    elif candidate.get("fusion_accepted_object_count", 0) <= 0:
        decision = "E01X_R5_PATCH_GENERIC_ADAPTER_IMPLEMENTATION"
        reasons.append("fusion_no_accepted_objects")
    elif candidate.get("semantic_raster_violation_count", 0) > 0:
        decision = "E01X_R5_PATCH_GENERIC_ADAPTER_IMPLEMENTATION"
        reasons.append("semantic_raster_violation")
    elif candidate.get("unknown_content_bearing_layer_count", 0) > 0:
        decision = "E01X_R5_PATCH_GENERIC_ADAPTER_IMPLEMENTATION"
        reasons.append("unknown_content_bearing_layer")
    return {
        "schema_name": "e01x_r5_gate_report",
        "schema_version": "1.0",
        "decision": decision,
        "status": "ready" if decision == "E01X_R5_READY_FOR_E01X_REENTRY" else "blocked",
        "block_reasons": reasons,
        "e01x_may_be_rerun": decision == "E01X_R5_READY_FOR_E01X_REENTRY",
        "e01_may_start": False,
        "canva_parity_claimed": False,
        **{key: candidate.get(key) for key in sorted(candidate.keys())},
    }


def r5_gate_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E01X-R5 Gate Report",
        "",
        f"- Decision: `{report['decision']}`",
        f"- E01X may be rerun: `{report['e01x_may_be_rerun']}`",
        f"- E01 may start: `{report['e01_may_start']}`",
        f"- Real text adapters: `{report.get('real_text_adapter_count', 0)}`",
        f"- Real non-text adapters: `{report.get('real_non_text_adapter_count', 0)}`",
        f"- Real proposals: `{report.get('total_real_proposal_count', 0)}`",
        f"- Heuristic proposals: `{report.get('total_heuristic_proposal_count', 0)}`",
        "",
        "## Block Reasons",
        "",
    ]
    lines.extend(f"- `{reason}`" for reason in report.get("block_reasons", []) or ["none"])
    lines.append("")
    lines.append("Canva parity claimed: `False`")
    return "\n".join(lines) + "\n"
