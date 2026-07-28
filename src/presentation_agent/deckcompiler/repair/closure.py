"""Fail-closed Phase 6 bounded-repair closure records.

The helpers in this module describe and bind a repair.  They never patch PPTX or
HTML outputs: the only permitted action is to rematerialize the declared
canonical upstream owner and then regenerate every invalidated derivative.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from ..identity import content_sha256, stable_id
from ..qa.contracts import TIMEZONE, now_iso
from .fixture import verify_bound_hash


SCHEMA_VERSION = "1.0.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

INVALIDATED_ARTIFACT_IDS = (
    "generated_runtime_source",
    "handoff_project",
    "project_crop_plan",
    "asset_manifest",
    "per_slide_crop_evidence",
    "reconstruction_manifest",
    "pptx",
    "html",
    "powerpoint_renders",
    "html_screenshots",
    "pptx_raster_evidence",
    "html_screenshot_evidence",
    "objective_evidence",
    "reconstruction_score",
    "official_final_gate_report",
    "external_qa_output",
    "external_reconciliation",
    "semantic_qa",
    "source_coverage_qa",
    "creative_qa",
    "editability_qa",
    "visual_qa",
    "raster_crop_qa",
    "parity_qa",
    "contact_sheet",
    "composite_report",
    "acceptance_report",
)


class RepairClosureError(RuntimeError):
    """A bounded-repair prerequisite or evidence binding failed."""


def _hash_record(payload: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(payload)
    result[field] = content_sha256(result)
    return result


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise RepairClosureError(f"INVALID_SHA256: {label}")
    return value


def _require_commit(value: str) -> str:
    if COMMIT_RE.fullmatch(value) is None:
        raise RepairClosureError("INVALID_SOURCE_COMMIT")
    return value


def _require_bound_record(payload: Mapping[str, Any], field: str, label: str) -> None:
    if not verify_bound_hash(dict(payload), field):
        raise RepairClosureError(f"INVALID_{label}_HASH")


def build_repair_plan(
    detection: Mapping[str, Any],
    application: Mapping[str, Any],
    fixture_spec: Mapping[str, Any],
    repair_contract: Mapping[str, Any],
    *,
    source_commit: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Bind a real controlled detection to its sole canonical repair owner."""

    detection = dict(detection)
    application = dict(application)
    fixture_spec = dict(fixture_spec)
    repair_contract = dict(repair_contract)
    checks = detection.get("checks")
    if (
        detection.get("schema_name") != "phase6_failure_detection_report"
        or detection.get("status") != "NEEDS_REPAIR"
        or not isinstance(checks, Mapping)
        or checks.get("expected_finding_detected") is not True
        or checks.get("repair_owner_proven") is not True
    ):
        raise RepairClosureError("CONTROLLED_DETECTION_REQUIRED")
    _require_bound_record(detection, "report_hash", "DETECTION_REPORT")
    _require_bound_record(fixture_spec, "fixture_hash", "FIXTURE")
    _require_bound_record(repair_contract, "contract_hash", "REPAIR_CONTRACT")

    finding = detection.get("detected_finding")
    if not isinstance(finding, Mapping) or not finding.get("finding_id") or not finding.get("detector"):
        raise RepairClosureError("CONTROLLED_DETECTION_REQUIRED")
    fixture_id = detection.get("fixture_id")
    owner = detection.get("canonical_repair_owner")
    target_field = detection.get("target_field")
    spec_owner = fixture_spec.get("canonical_repair_owner")
    if not isinstance(spec_owner, Mapping):
        raise RepairClosureError("CANONICAL_REPAIR_OWNER_MISMATCH")
    if any(item.get("fixture_id") != fixture_id for item in (application, fixture_spec, repair_contract)):
        raise RepairClosureError("FIXTURE_ID_MISMATCH")
    if (
        application.get("canonical_owner_path") != owner
        or spec_owner.get("path") != owner
        or repair_contract.get("owner_artifact") != owner
        or application.get("target_field") != target_field
        or fixture_spec.get("target_field") != target_field
        or repair_contract.get("owner_field") != target_field
    ):
        raise RepairClosureError("CANONICAL_REPAIR_OWNER_MISMATCH")
    baseline_sha256 = _require_sha256(application.get("before_sha256"), "baseline")
    faulty_sha256 = _require_sha256(application.get("after_sha256"), "faulty")
    if spec_owner.get("sha256") != baseline_sha256 or repair_contract.get("owner_sha256") != baseline_sha256:
        raise RepairClosureError("CANONICAL_REPAIR_OWNER_HASH_MISMATCH")
    if repair_contract.get("repair_action_type") != "rematerialize_canonical_owner":
        raise RepairClosureError("UNSUPPORTED_REPAIR_ACTION")
    if repair_contract.get("direct_final_pptx_patch") is not False or repair_contract.get("direct_final_html_patch") is not False:
        raise RepairClosureError("DIRECT_FINAL_OUTPUT_PATCH_REJECTED")
    maximum = repair_contract.get("maximum_outer_waves")
    if maximum != 3:
        raise RepairClosureError("INVALID_REPAIR_LIMIT")

    core = {
        "schema_name": "phase6_repair_plan",
        "schema_version": SCHEMA_VERSION,
        "plan_id": stable_id("repair_plan", fixture_id, detection["report_hash"], source_commit),
        "fixture_id": fixture_id,
        "source_commit": _require_commit(source_commit),
        "source_detection_report_hash": detection["report_hash"],
        "source_fault_application_hash": _require_sha256(application.get("application_hash"), "fault application"),
        "source_fixture_hash": fixture_spec["fixture_hash"],
        "source_repair_contract_hash": repair_contract["contract_hash"],
        "finding_ids": [str(finding["finding_id"])],
        "source_detector": str(finding["detector"]),
        "canonical_repair_owner": str(owner),
        "target_field": str(target_field),
        "repair_action": "rematerialize_canonical_owner",
        "baseline_sha256": baseline_sha256,
        "faulty_sha256": faulty_sha256,
        "expected_repaired_sha256": baseline_sha256,
        "invalidated_artifact_ids": list(INVALIDATED_ARTIFACT_IDS),
        "current_wave": 1,
        "maximum_outer_waves": maximum,
        "direct_final_pptx_patch": False,
        "direct_final_html_patch": False,
        "semantic_content_change": False,
        "evidence_binding_change": False,
        "visual_target_change": False,
        "created_at": created_at or now_iso(),
        "timezone": TIMEZONE,
    }
    return _hash_record(core, "plan_hash")


def build_invalidation_manifest(
    repair_plan: Mapping[str, Any],
    prior_hashes: Mapping[str, str],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Invalidate every prior derivative in a deterministic order."""

    plan = dict(repair_plan)
    _require_bound_record(plan, "plan_hash", "REPAIR_PLAN")
    expected = list(INVALIDATED_ARTIFACT_IDS)
    if plan.get("invalidated_artifact_ids") != expected or set(prior_hashes) != set(expected):
        raise RepairClosureError("INVALIDATION_SET_INCOMPLETE")
    rows = [
        {
            "artifact_id": artifact_id,
            "prior_sha256": _require_sha256(prior_hashes[artifact_id], artifact_id),
            "status": "INVALIDATED",
            "reason": "canonical_upstream_owner_rematerialized",
        }
        for artifact_id in expected
    ]
    core = {
        "schema_name": "phase6_invalidation_manifest",
        "schema_version": SCHEMA_VERSION,
        "manifest_id": stable_id("invalidation", plan["plan_hash"], rows),
        "repair_plan_hash": plan["plan_hash"],
        "invalidated_artifact_count": len(rows),
        "invalidated_artifacts": rows,
        "stale_artifact_policy": "reject_all_prior_downstream_evidence",
        "regeneration_required": True,
        "created_at": created_at or now_iso(),
        "timezone": TIMEZONE,
    }
    return _hash_record(core, "invalidation_hash")


def build_repair_history(
    repair_plan: Mapping[str, Any],
    invalidation_manifest: Mapping[str, Any],
    repaired: Mapping[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Close one bounded wave only after fresh, complete, finding-free evidence."""

    plan = dict(repair_plan)
    invalidation = dict(invalidation_manifest)
    repaired = dict(repaired)
    wave = plan.get("current_wave")
    allowed = plan.get("maximum_outer_waves")
    if not isinstance(wave, int) or not isinstance(allowed, int) or wave < 1 or wave > allowed:
        raise RepairClosureError("REPAIR_LIMIT")
    _require_bound_record(plan, "plan_hash", "REPAIR_PLAN")
    _require_bound_record(invalidation, "invalidation_hash", "INVALIDATION")
    if repaired.get("fault_state") != "repaired" or repaired.get("prior_runtime_reused") is not False:
        raise RepairClosureError("FRESH_REPAIRED_RUNTIME_REQUIRED")
    if repaired.get("upstream_sha256") != plan.get("expected_repaired_sha256"):
        raise RepairClosureError("REPAIRED_UPSTREAM_HASH_MISMATCH")
    if repaired.get("expected_finding_resolved") is not True:
        raise RepairClosureError("EXPECTED_FINDING_NOT_RESOLVED")
    if repaired.get("new_severe_finding_count") != 0:
        raise RepairClosureError("NEW_SEVERE_FINDING")
    expected = {
        "official_final_gate": "PASS",
        "render_count": 6,
        "html_screenshot_count": 6,
        "repaired_micro_canary_count": 2,
        "timeout_count": 0,
        "dimension_mismatch_count": 0,
        "missing_artifact_count": 0,
        "stale_artifact_count": 0,
        "hash_mismatch_count": 0,
        "external_reconciliation": "PASS",
        "composite_qa": "PASS",
        "raster_violation_count": 0,
    }
    if any(repaired.get(key) != value for key, value in expected.items()):
        raise RepairClosureError("REPAIRED_EVIDENCE_INCOMPLETE")
    for field in (
        "pptx_sha256", "html_sha256", "html_screenshot_capture_manifest_hash",
        "objective_evidence_hash", "evidence_capsule_manifest_hash",
        "external_reconciliation_report_hash", "composite_report_hash",
    ):
        _require_sha256(repaired.get(field), field)
    for field in ("pptx_render_sha256_by_slide", "html_screenshot_sha256_by_slide"):
        values = repaired.get(field)
        if not isinstance(values, Mapping) or len(values) != 6:
            raise RepairClosureError("REPAIRED_EVIDENCE_INCOMPLETE")
        for key, value in values.items():
            _require_sha256(value, f"{field}.{key}")

    wave_record = {
        "wave": wave,
        "repair_action": plan["repair_action"],
        "canonical_repair_owner": plan["canonical_repair_owner"],
        "before_faulty_sha256": plan["faulty_sha256"],
        "after_repaired_sha256": repaired["upstream_sha256"],
        "direct_output_patch": False,
        "prior_runtime_reused": False,
        "run_id": repaired.get("run_id"),
        "source_commit": repaired.get("source_commit"),
        "official_final_gate": repaired["official_final_gate"],
        "external_reconciliation": repaired["external_reconciliation"],
        "composite_qa": repaired["composite_qa"],
        "expected_finding_resolved": True,
        "new_severe_finding_count": 0,
        "evidence": repaired,
        "status": "CONVERGED",
    }
    core = {
        "schema_name": "phase6_repair_history",
        "schema_version": SCHEMA_VERSION,
        "history_id": stable_id("repair_history", plan["plan_hash"], invalidation["invalidation_hash"], wave_record),
        "repair_plan_hash": plan["plan_hash"],
        "invalidation_manifest_hash": invalidation["invalidation_hash"],
        "waves_used": wave,
        "waves_allowed": allowed,
        "waves": [wave_record],
        "status": "CONVERGED",
        "created_at": created_at or now_iso(),
        "timezone": TIMEZONE,
    }
    return _hash_record(core, "history_hash")


def build_before_after_manifest(
    repair_plan: Mapping[str, Any],
    baseline: Mapping[str, Any],
    faulty: Mapping[str, Any],
    repaired: Mapping[str, Any],
    *,
    semantic_content_unchanged: bool,
    evidence_bindings_unchanged: bool,
    visual_targets_unchanged: bool,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Bind baseline, controlled-fault, and regenerated states."""

    plan = dict(repair_plan)
    _require_bound_record(plan, "plan_hash", "REPAIR_PLAN")
    if not all((semantic_content_unchanged, evidence_bindings_unchanged, visual_targets_unchanged)):
        raise RepairClosureError("PROTECTED_AUTHORITY_CHANGED")
    states = {"baseline": dict(baseline), "faulty": dict(faulty), "repaired": dict(repaired)}
    if (
        states["baseline"].get("upstream_sha256") != plan.get("baseline_sha256")
        or states["faulty"].get("upstream_sha256") != plan.get("faulty_sha256")
        or states["repaired"].get("upstream_sha256") != plan.get("expected_repaired_sha256")
    ):
        raise RepairClosureError("BEFORE_AFTER_UPSTREAM_BINDING_MISMATCH")
    for state_name, state in states.items():
        for field in ("upstream_sha256", "pptx_sha256", "html_sha256"):
            _require_sha256(state.get(field), f"{state_name}.{field}")
    core = {
        "schema_name": "phase6_before_after_manifest",
        "schema_version": SCHEMA_VERSION,
        "manifest_id": stable_id("before_after", plan["plan_hash"], states),
        "repair_plan_hash": plan["plan_hash"],
        "states": states,
        "semantic_content_unchanged": True,
        "evidence_bindings_unchanged": True,
        "visual_targets_unchanged": True,
        "direct_final_output_patch": False,
        "created_at": created_at or now_iso(),
        "timezone": TIMEZONE,
    }
    return _hash_record(core, "manifest_hash")


_RELEASE_PREREQUISITES: dict[str, Any] = {
    "phase6a_baseline_composite": "PASS",
    "phase61a1_reconciliation": "PASS",
    "postcommit_baseline_reachability": "PASS",
    "html_screenshot_stabilization": "PASS",
    "controlled_fault_detection": "PASS",
    "canonical_repair_owner_valid": True,
    "invalidation_complete": True,
    "repair_waves_used": 1,
    "repair_waves_allowed": 3,
    "repaired_official_final_gate": "PASS",
    "repaired_render_count": 6,
    "repaired_screenshot_count": 6,
    "repaired_external_reconciliation": "PASS",
    "repaired_composite_qa": "PASS",
    "external_skill_unchanged": True,
    "phase4_unchanged": True,
    "phase5_unchanged": True,
    "removed_skill_absent": True,
    "protected_outputs_absent": True,
    "git_clean_at_evaluation": True,
}


def build_unified_release_gate(
    evidence: Mapping[str, Any], *, source_commit: str, created_at: str | None = None
) -> dict[str, Any]:
    """Return packaging eligibility while explicitly withholding release authority."""

    evidence = dict(evidence)
    missing = [key for key, value in _RELEASE_PREREQUISITES.items() if evidence.get(key) != value]
    if missing:
        raise RepairClosureError("BLOCKED_RELEASE_EVIDENCE_INCOMPLETE: " + ", ".join(missing))
    core = {
        "schema_name": "phase6_unified_release_gate_report",
        "schema_version": SCHEMA_VERSION,
        "report_id": stable_id("release_gate", source_commit, evidence),
        "source_commit": _require_commit(source_commit),
        "checks": {key: evidence[key] for key in _RELEASE_PREREQUISITES},
        "status": "ELIGIBLE_FOR_PACKAGING",
        "phase6_accepted": True,
        "final_release_eligible": False,
        "devpost_release_eligible": False,
        "phase7_required": True,
        "phase7_started": False,
        "active_output_set": "phase5_baseline",
        "created_at": created_at or now_iso(),
        "timezone": TIMEZONE,
    }
    return _hash_record(core, "report_hash")


def build_phase6_acceptance(
    unified_gate: Mapping[str, Any], *, created_at: str | None = None
) -> dict[str, Any]:
    """Create the non-release Phase 6 acceptance record."""

    gate = dict(unified_gate)
    _require_bound_record(gate, "report_hash", "UNIFIED_RELEASE_GATE")
    if gate.get("status") != "ELIGIBLE_FOR_PACKAGING" or gate.get("phase6_accepted") is not True:
        raise RepairClosureError("PHASE6_UNIFIED_GATE_NOT_ACCEPTED")
    core = {
        "schema_name": "phase6_acceptance",
        "schema_version": SCHEMA_VERSION,
        "acceptance_id": stable_id("phase6_acceptance", gate["report_hash"]),
        "unified_release_gate_report_hash": gate["report_hash"],
        "status": "ELIGIBLE_FOR_PACKAGING",
        "phase6_accepted": True,
        "final_release_eligible": False,
        "devpost_release_eligible": False,
        "phase7_required": True,
        "phase7_started": False,
        "active_output_set": "phase5_baseline",
        "created_at": created_at or now_iso(),
        "timezone": TIMEZONE,
    }
    return _hash_record(core, "acceptance_hash")


__all__ = [
    "INVALIDATED_ARTIFACT_IDS",
    "RepairClosureError",
    "build_before_after_manifest",
    "build_invalidation_manifest",
    "build_phase6_acceptance",
    "build_repair_history",
    "build_repair_plan",
    "build_unified_release_gate",
]
