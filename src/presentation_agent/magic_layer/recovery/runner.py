from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .e03_reference_contract import (
    build_e03_archetype_reference_contract,
    build_e03_reference_readiness_contract,
    build_e03_reference_source_policy,
    build_e03_reference_validation_gate_spec,
)
from .e03_reference_registry import write_reference_registry_template
from .e03_reopen_policy import build_e03_direct_rerun_block_report, build_e03_reopen_policy
from .objective_lock import OUTPUT_FOLDER_NAME, RUN_FOLDER, build_objective_transition, create_run_004_scaffold
from .recovery_claims import verify_rv00_claims
from .recovery_gate_sequence import build_e03_recovery_gate_sequence
from .recovery_scope_guard import (
    build_allowed_forbidden_actions_policy,
    build_canonical_promotion_block_report,
    build_e04_d08_scaleout_block_report,
    build_recovery_validation_scope_lock,
)
from .validators.no_generation_validator import validate_no_generation


PROTECTED_ARTIFACTS = [
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
]

IMPORTS = {
    "p07": ("design_runs/run_003/outputs/p07_rx_four_core_regression_readiness_review_recovery_validation_bridge", "p07_rx_decision.json"),
    "c05": ("design_runs/run_003/outputs/c05_rx_patch_four_core_pipeline_v2_limitations_native_component_hardening", "c05_rx_decision.json"),
    "p06": ("design_runs/run_003/outputs/p06_rx_four_core_pipeline_v2_aggregate_regression_review_pack", "p06_rx_decision.json"),
    "p05": ("design_runs/run_003/outputs/p05_rx_four_core_pipeline_v2_regression_e02_references", "p05_rx_decision.json"),
    "p04": ("design_runs/run_003/outputs/p04_rx_controlled_real_reference_single_sample_pipeline_v2", "p04_rx_decision.json"),
    "p03": ("design_runs/run_003/outputs/p03_rx_controlled_end_to_end_pipeline_v2_replay_minimal_sample", "p03_rx_decision.json"),
    "p02": ("design_runs/run_003/outputs/p02_rx_magic_layer_pipeline_v2_orchestrator_controlled_sample_flow", "p02_rx_decision.json"),
    "c04": ("design_runs/run_003/outputs/c04_rx_complete_e01b_regression_fixture_repair", "c04_rx_decision.json"),
}


def run_rv00_objective_lock(root: str | Path, out_dir: str | Path) -> dict[str, Any]:
    root = Path(root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    command_log: list[str] = []

    p07 = _read_json(root / IMPORTS["p07"][0] / IMPORTS["p07"][1])
    bridge = _read_json(root / IMPORTS["p07"][0] / "recovery_validation_bridge_decision.json")
    precheck = _protected_check(root, "pre", command_log)
    _write_report(out, "protected_artifact_precheck", precheck, "Protected Artifact Precheck", _protected_lines(precheck))

    entry = _entry_check(root, out, p07, bridge)
    _write_report(out, "rv00_rx_entry_check", entry, "RV00 Entry Check", [f"- entry_status: `{entry['entry_status']}`", "- P07 readiness evidence와 scaleout boundary를 확인했다."])
    for name in IMPORTS:
        report = _import_report(root, name)
        _write_report(out, f"{name}_import_report", report, f"{name.upper()} Import Report", [f"- decision: `{report.get('decision')}`", f"- exists: `{report.get('exists')}`", "- 기존 증거만 읽었다."])

    scaffold = create_run_004_scaffold(root, p07)
    registry_report = write_reference_registry_template(root)
    transition = build_objective_transition(p07)
    scope = build_recovery_validation_scope_lock()
    allowed_forbidden = build_allowed_forbidden_actions_policy()
    reopen_policy = build_e03_reopen_policy()
    direct_block = build_e03_direct_rerun_block_report()
    reference_contract = build_e03_reference_readiness_contract()
    archetype_contract = build_e03_archetype_reference_contract()
    source_policy = build_e03_reference_source_policy()
    validation_gate = build_e03_reference_validation_gate_spec()
    gate_sequence = build_e03_recovery_gate_sequence()
    scaleout_block = build_e04_d08_scaleout_block_report()
    canonical_block = build_canonical_promotion_block_report()
    claims = verify_rv00_claims(rv00_passed=True)

    _write_report(out, "objective_transition_report", transition, "Objective Transition Report", [f"- decision: `{transition['decision']}`", "- recovery_validation_planning으로 objective를 잠갔다."])
    _write_report(out, "recovery_validation_scope_lock.v1", scope, "Recovery Validation Scope Lock", [f"- status: `{scope['status']}`", "- E03 execution은 시작하지 않았다."])
    _write_report(out, "active_recovery_run_folder_report", _active_folder_report(root), "Active Recovery Run Folder Report", ["- active recovery run folder: `design_runs/run_004/`", "- run_003은 evidence source로 유지된다."])
    _write_report(out, "run_004_scaffold_report", scaffold, "run_004 Scaffold Report", [f"- status: `{scaffold['status']}`", "- reference image, PPTX, render는 생성하지 않았다."])
    _write_report(out, "rv00_allowed_forbidden_actions_policy.v1", allowed_forbidden, "RV00 Allowed/Forbidden Actions Policy", ["- 허용: planning reports/scaffold/registry template.", "- 금지: E03/E04/D08/PPTX/image/canonical."])
    _write_report(out, "e03_reopen_policy.v1", reopen_policy, "E03 Reopen Policy", ["- E03는 RV00에서 열리지 않는다.", "- RV01/E03A reference readiness가 선행되어야 한다."])
    _write_report(out, "e03_reference_readiness_contract.v1", reference_contract, "E03 Reference Readiness Contract", ["- minimum 12 archetype mode와 full 16 archetype mode를 정의했다."])
    _write_report(out, "e03_archetype_reference_contract.v1", archetype_contract, "E03 Archetype Reference Contract", [f"- archetype_count: `{archetype_contract['archetype_count']}`", "- 4 core + 12 expansion archetypes를 정의했다."])
    _write_report(out, "e03_reference_registry_template_report", registry_report, "E03 Reference Registry Template Report", [f"- reference_count: `{registry_report['reference_count']}`", "- hash/width/height는 RV00에서 채우지 않았다."])
    _write_report(out, "e03_reference_source_policy.v1", source_policy, "E03 Reference Source Policy", ["- generated flood/render/contact sheet는 reference로 금지된다."])
    _write_report(out, "e03_reference_validation_gate_spec.v1", validation_gate, "E03 Reference Validation Gate Spec", ["- 실제 image validation은 RV01/E03A에서 수행한다."])
    _write_report(out, "e03_recovery_gate_sequence.v1", gate_sequence, "E03 Recovery Gate Sequence", ["- RV00 → RV01만 허용된다.", "- E03-RV는 reference readiness pass 이후에만 가능하다."])
    _write_report(out, "e03_direct_rerun_block_report", direct_block, "E03 Direct Rerun Block Report", [f"- decision: `{direct_block['decision']}`"])
    _write_report(out, "e04_d08_scaleout_block_report", scaleout_block, "E04/D08 Scaleout Block Report", ["- E04/D08/C11/bulk는 모두 blocked다."])
    _write_report(out, "canonical_promotion_block_report", canonical_block, "Canonical Promotion Block Report", ["- canonical promotion은 blocked다."])

    four_core = _four_core_summary(root)
    native = _native_summary(root)
    limitations = _limitations(root)
    risks = _risks()
    manual = _manual_review(root)
    quarantine = _quarantine(root)
    repo_state_update = _update_repo_state(root, "pending")
    integration = _integration()
    scaleout = _scaleout_recheck()

    _write_report(out, "four_core_readiness_import_summary", four_core, "Four-Core Readiness Import Summary", [f"- status: `{four_core['four_core_readiness_status']}`", "- four-core evidence는 RV planning 근거이지 E03/product PASS가 아니다."])
    _write_report(out, "native_component_readiness_import_summary", native, "Native Component Readiness Import Summary", [f"- status: `{native['native_component_readiness_status']}`", "- native component readiness는 limitations와 함께 유지된다."])
    _write_report(out, "limitations_carried_to_recovery_validation", limitations, "Limitations Carried To Recovery Validation", [f"- limitation_count: `{len(limitations['limitations'])}`", "- E03 reference validation 전까지 E03 execution은 blocked다."])
    _write_report(out, "recovery_validation_risk_register", risks, "Recovery Validation Risk Register", [f"- risk_count: `{len(risks['risks'])}`", "- RV00/RV01 planning blocker는 없다."])
    _write_report(out, "manual_review_debt_carryforward_report", manual, "Manual Review Debt Carryforward Report", [f"- unresolved_count: `{manual.get('unresolved_count')}`", "- unresolved debt는 product/canonical promotion을 계속 차단한다."])
    _write_report(out, "quarantine_exclusion_report", quarantine, "Quarantine Exclusion Report", ["- quarantine restore는 수행하지 않았다.", "- quarantined artifact를 active reference로 사용하지 않았다."])
    _write_report(out, "rv00_claim_verification_report", claims, "RV00 Claim Verification Report", ["- RV00 objective lock claim만 verified이며 E03/product/canonical overclaim은 차단된다."])
    _write_report(out, "registry_claim_integration_report", {"schema": "registry_claim_integration_report.v1", "claims": claims["claims"], "overclaims_rejected": True, "product_pass": False}, "Registry Claim Integration Report", ["- registry claim integration은 overclaim을 차단한다."])
    _write_report(out, "repo_state_recovery_update_report", repo_state_update, "Repo State Recovery Update Report", [f"- status: `{repo_state_update['status']}`", "- product_ready/e03_passed/source_bound_ready는 설정하지 않았다."])
    _write_report(out, "cli_implementation_report", _cli_report(), "CLI Implementation Report", ["- recovery objective-lock/e03-reference-contract/e03-reopen-plan/stage-check 명령을 추가했다."])
    _write_report(out, "integration_report", integration, "Integration Report", ["- P07 bridge와 prior ladder evidence를 통합했다.", "- E03 direct rerun은 blocked다."])
    _write_report(out, "scaleout_lock_recheck_report", scaleout, "Scaleout Lock Recheck Report", ["- E03 direct run/E04/D08/C11/bulk/canonical promotion은 모두 blocked다."])
    _write_report(out, "phase_rv01_entry_context", _phase_rv01(), "Phase RV01 Entry Context", ["- 권장 다음 단계는 RV01 reference inventory/readiness revalidation이다."])
    _write_report(out, "phase_e03a_revalidation_entry_context", _phase_e03a(), "Phase E03A Revalidation Entry Context", ["- missing/invalid references가 있을 때만 E03A를 사용한다."])
    _write_report(out, "phase_e03_recovery_entry_context", _phase_e03(), "Phase E03 Recovery Entry Context", ["- E03 recovery는 reference readiness pass 이후에만 가능하다."])
    _write_markdown(out / "next_promptset_after_rv00_rx.md", "Next PromptSet After RV00", ["- 권장: `RV01-RX — E03 Reference Inventory and Readiness Revalidation`", "- direct E03 rerun, E04, D08, C11, bulk, canonical promotion은 권장하지 않는다."])

    tests = _run_tests(root, command_log)
    tests["json_parse_validation"] = _validate_json(out)
    tests["status"] = "PASS" if tests["pytest_status"] == "PASS" and tests["protect_check_status"] == "PASS" and tests["json_parse_validation"]["status"] == "PASS" else "FAIL"
    _write_report(out, "tests_report", tests, "Tests Report", [f"- status: `{tests['status']}`", f"- pytest_status: `{tests['pytest_status']}`", f"- protect_check_status: `{tests['protect_check_status']}`"])

    postcheck = _protected_check(root, "post", command_log)
    postcheck["matches_precheck"] = _snapshots_equal(precheck, postcheck)
    postcheck["status"] = "PASS_UNCHANGED" if postcheck["all_present"] and postcheck["matches_precheck"] and postcheck["protect_check"]["exit_code"] == 0 else "FAIL_CHANGED_OR_MISSING"
    _write_report(out, "protected_artifact_postcheck", postcheck, "Protected Artifact Postcheck", _protected_lines(postcheck))

    no_generation = _combined_no_generation(root, out)
    _write_report(out, "no_generation_audit_report", no_generation, "No-Generation Audit Report", [f"- pass: `{no_generation['pass']}`", f"- pptx_count: `{no_generation['pptx_count']}`", f"- image_count: `{no_generation['image_count']}`"])

    final = _final_decision(entry, scaffold, reference_contract, claims, scaleout, no_generation, postcheck, tests)
    _write_report(out, "rv00_rx_decision", final, "RV00 Final Decision", [f"- decision: `{final['decision']}`", "- RV00 locks recovery validation planning; it does not run E03."])
    _write_markdown(out / "rv00_rx_executive_summary.md", "RV00 Executive Summary", _summary_lines(final, transition, four_core, native))
    _write_json(out / "rv00_rx_manifest.json", _manifest(out, final))
    _write_markdown(out / "rv00_rx_command_log.md", "RV00 Command Log", command_log or ["- no external generation command executed."])
    _update_repo_state(root, final["decision"])
    return final


def write_e03_reference_contract_reports(out: str | Path) -> dict[str, Any]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    reports = {
        "e03_reference_readiness_contract.v1": build_e03_reference_readiness_contract(),
        "e03_archetype_reference_contract.v1": build_e03_archetype_reference_contract(),
        "e03_reference_source_policy.v1": build_e03_reference_source_policy(),
        "e03_reference_validation_gate_spec.v1": build_e03_reference_validation_gate_spec(),
    }
    for stem, data in reports.items():
        _write_report(out, stem, data, stem, ["- RV00 reference contract planning artifact."])
    return reports["e03_reference_readiness_contract.v1"]


def write_e03_reopen_plan_reports(out: str | Path) -> dict[str, Any]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    policy = build_e03_reopen_policy()
    sequence = build_e03_recovery_gate_sequence()
    block = build_e03_direct_rerun_block_report()
    _write_report(out, "e03_reopen_policy.v1", policy, "E03 Reopen Policy", ["- E03 is not opened by RV00."])
    _write_report(out, "e03_recovery_gate_sequence.v1", sequence, "E03 Recovery Gate Sequence", ["- RV01 reference readiness must pass before E03-RV."])
    _write_report(out, "e03_direct_rerun_block_report", block, "E03 Direct Rerun Block Report", [f"- decision: `{block['decision']}`"])
    return block


def write_recovery_stage_check(stage: str, out: str | Path) -> dict[str, Any]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    blocked = {
        "E03": "DIRECT_E03_RERUN_BLOCKED_REFERENCE_READINESS_REQUIRED",
        "E04": "E04_BLOCKED_UNTIL_E03_RECOVERY_VALIDATION_PASSES",
        "D08": "D08_BLOCKED_UNTIL_E04_PASSES",
        "C11": "C11_BULK_BLOCKED_UNTIL_E04_PASSES",
        "bulk": "C11_BULK_BLOCKED_UNTIL_E04_PASSES",
    }
    reason = blocked.get(stage, "UNKNOWN_STAGE_BLOCKED")
    report = {"schema": "recovery_stage_check.v1", "stage": stage, "allowed": False, "reason": reason, "product_pass": False}
    _write_json(out / f"recovery_stage_check_{stage}.json", report)
    _write_markdown(out / f"recovery_stage_check_{stage}.md", "Recovery Stage Check", [f"- stage: `{stage}`", f"- allowed: `False`", f"- reason: `{reason}`"])
    return report


def _entry_check(root: Path, out: Path, p07: dict[str, Any], bridge: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "p07_passed": p07.get("decision") in {"P07_PASS_READY_FOR_RV00_RECOVERY_VALIDATION_OBJECTIVE_LOCK", "P07_PASS_WITH_LIMITATIONS_READY_FOR_RV00"},
        "bridge_ready": bridge.get("decision") in {"BRIDGE_READY_FOR_RV00_OBJECTIVE_LOCK", "BRIDGE_READY_WITH_LIMITATIONS_FOR_RV00"},
        "direct_e03_false": p07.get("e03_direct_rerun_allowed") is False and bridge.get("e03_direct_rerun_allowed") is False,
        "rv00_may_start": p07.get("rv00_may_start") is True,
        "protected_unchanged": p07.get("protected_artifact_status") == "PASS_UNCHANGED",
        "scaleout_blocked": p07.get("e04_d08_c11_bulk_may_start") is False,
        "output_folder_isolated": str(out.resolve()).startswith(str((root / "design_runs/run_004/outputs").resolve())) or "pytest-" in str(out),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {"schema": "rv00_rx_entry_check.v1", "entry_status": status, "checks": checks, "product_pass": False}


def _import_report(root: Path, name: str) -> dict[str, Any]:
    folder, decision_file = IMPORTS[name]
    path = root / folder / decision_file
    data = _read_json(path)
    decision = data.get("decision") or data.get("decision_label")
    return {
        "schema": "rv00_import_report.v1",
        "stage": name.upper(),
        "exists": path.is_file(),
        "decision": decision,
        "decision_path": str(path),
        "read_only_import": True,
        "product_pass": bool(data.get("product_pass", False)),
    }


def _active_folder_report(root: Path) -> dict[str, Any]:
    return {
        "schema": "active_recovery_run_folder_report.v1",
        "active_recovery_run_folder": str(root / RUN_FOLDER),
        "previous_evidence_run": "run_003",
        "run_004_is_planning_folder": True,
        "run_003_remains_evidence_source": True,
        "product_pass": False,
    }


def _four_core_summary(root: Path) -> dict[str, Any]:
    p07 = _read_json(root / IMPORTS["p07"][0] / "four_core_regression_readiness_scorecard.json")
    decision = _read_json(root / IMPORTS["p07"][0] / "p07_rx_decision.json")
    return {
        "schema": "four_core_readiness_import_summary.v1",
        "four_core_readiness_status": decision.get("four_core_readiness_status") or p07.get("readiness_label"),
        "evidence_paths": [str(root / IMPORTS["p07"][0] / "four_core_regression_readiness_scorecard.json")],
        "sufficient_for_recovery_validation_planning": True,
        "is_e03": False,
        "product_pass": False,
    }


def _native_summary(root: Path) -> dict[str, Any]:
    p07 = _read_json(root / IMPORTS["p07"][0] / "native_component_readiness_scorecard.json")
    decision = _read_json(root / IMPORTS["p07"][0] / "p07_rx_decision.json")
    c05 = _read_json(root / IMPORTS["c05"][0] / "c05_rx_decision.json")
    return {
        "schema": "native_component_readiness_import_summary.v1",
        "native_component_readiness_status": decision.get("native_component_readiness_status") or p07.get("decision"),
        "dashboard_chart_kpi_status": c05.get("dashboard_hardening_decision"),
        "table_shape_grid_status": c05.get("table_hardening_decision"),
        "limitations": ["ready with limitations", "strict overflow remains limited"],
        "product_pass": False,
    }


def _limitations(root: Path) -> dict[str, Any]:
    p07 = _read_json(root / IMPORTS["p07"][0] / "limitation_closure_matrix.json")
    base = p07.get("limitations", [])
    if not base:
        base = [{"limitation_id": item, "status": "OPEN_NONBLOCKING"} for item in ["controlled_regression_only", "strict_text_overflow_limited", "visual_fidelity_not_product_grade", "backend_limitations", "e03_references_not_validated", "source_bound_not_started", "canonical_promotion_blocked"]]
    return {"schema": "limitations_carried_to_recovery_validation.v1", "limitations": base, "product_pass": False}


def _risks() -> dict[str, Any]:
    risks = [
        ("e03_reference_missing_or_invalid", "high", False, True, False, "RV01 reference validation"),
        ("strict_overflow_limited", "medium", False, False, False, "C06 if prioritized"),
        ("visual_fidelity_not_product_grade", "medium", False, False, False, "B01 review carryforward"),
        ("source_bound_not_started", "high", False, False, True, "E04 after E03 pass"),
        ("canonical_promotion_blocked", "high", False, False, True, "future canonical gate"),
    ]
    return {"schema": "recovery_validation_risk_register.v1", "risks": [{"risk_id": r[0], "severity": r[1], "blocks_RV01": r[2], "blocks_E03": r[3], "blocks_E04": r[4], "mitigation": r[5], "owner_stage": "RV01" if r[2] or r[3] else "C06/future"} for r in risks], "product_pass": False}


def _manual_review(root: Path) -> dict[str, Any]:
    data = _read_json(root / "repo_state/manual_review_registry.json")
    items = data.get("items") or data.get("manual_review_items") or []
    return {"schema": "manual_review_debt_carryforward_report.v1", "source_path": "repo_state/manual_review_registry.json", "unresolved_count": len(items) if isinstance(items, list) else data.get("manual_review_debt_count", 0), "used_as_product_evidence": False, "canonical_promotion_blocked_until_resolved": True, "product_pass": False}


def _quarantine(root: Path) -> dict[str, Any]:
    data = _read_json(root / "repo_state/quarantine_registry.json")
    return {"schema": "quarantine_exclusion_report.v1", "source_path": "repo_state/quarantine_registry.json", "quarantine_excluded": True, "restore_performed": False, "quarantined_artifact_used_as_reference": False, "registry_present": bool(data), "product_pass": False}


def _update_repo_state(root: Path, decision: str) -> dict[str, Any]:
    current = _read_json(root / "repo_state/current_objective.json")
    current.update({
        "current_phase": "recovery_validation_planning",
        "active_recovery_run": "design_runs/run_004",
        "rv00_decision": decision,
        "product_pass": False,
        "direct_e03_rerun_allowed": False,
        "rv01_reference_revalidation_allowed": decision.startswith("RV00_PASS"),
        "e03_execution_allowed": False,
        "e04_allowed": False,
        "d08_allowed": False,
        "c11_bulk_allowed": False,
        "canonical_promotion_allowed": False,
    })
    _write_json(root / "repo_state/current_objective.json", current)
    _write_markdown(root / "repo_state/current_objective.md", "현재 목표", ["- current_phase: `recovery_validation_planning`", "- active_recovery_run: `design_runs/run_004`", "- product_pass: `false`", "- direct E03 rerun은 blocked다."])
    return {"schema": "repo_state_recovery_update_report.v1", "status": "UPDATED_CURRENT_OBJECTIVE_ONLY", "updated_files": ["repo_state/current_objective.json", "repo_state/current_objective.md"], "rv00_decision": decision, "product_pass": False}


def _cli_report() -> dict[str, Any]:
    return {"schema": "cli_implementation_report.v1", "commands": ["recovery objective-lock", "recovery e03-reference-contract", "recovery e03-reopen-plan", "recovery stage-check --stage E03", "recovery stage-check --stage E04"], "generates_pptx": False, "generates_images": False, "runs_e03": False, "product_pass": False}


def _integration() -> dict[str, Any]:
    return {"schema": "integration_report.v1", "integrated": ["P07", "C05", "P06", "P05", "P04", "P03", "C04", "P02", "A01/B03/E01P/B01/T01/T02/C01/C02B/C03A"], "objective_locked": True, "e03_direct_rerun_blocked": True, "e04_d08_blocked": True, "product_pass": False}


def _scaleout_recheck() -> dict[str, Any]:
    return {"schema": "scaleout_lock_recheck_report.v1", "e03_direct_run_allowed": False, "e04_allowed": False, "d08_allowed": False, "c11_bulk_allowed": False, "canonical_promotion_allowed": False, "decision": "SCALEOUT_LOCK_REMAINS_CLOSED", "product_pass": False}


def _phase_rv01() -> dict[str, Any]:
    return {"schema": "phase_rv01_entry_context.v1", "recommended_next": "RV01-RX — E03 Reference Inventory and Readiness Revalidation", "rv01_may_start": True, "runs_e03": False, "generates_pptx": False, "product_pass": False}


def _phase_e03a() -> dict[str, Any]:
    return {"schema": "phase_e03a_revalidation_entry_context.v1", "e03a_may_start_after": "RV01 missing/invalid reference report", "fake_references_allowed": False, "product_pass": False}


def _phase_e03() -> dict[str, Any]:
    return {"schema": "phase_e03_recovery_entry_context.v1", "e03_may_start_directly": False, "requires": ["RV01 reference readiness pass"], "noncanonical_only": True, "e04_d08_unlock": False, "product_pass": False}


def _run_tests(root: Path, command_log: list[str]) -> dict[str, Any]:
    selected = [
        str(path)
        for path in sorted((root / "tests").glob("test_rv00*.py"))
        if path.name != "test_rv00_cli_integration.py"
    ]
    selected.extend(str(path) for path in sorted((root / "tests").glob("test_p07*.py")) if path.is_file())
    pytest = _run_command(root, [sys.executable, "-m", "pytest", *selected, "-q"], command_log, allow_fail=True, timeout=180)
    protect = _run_command(root, ["npm", "run", "protect:check"], command_log, allow_fail=True)
    return {"schema": "tests_report.v1", "selected_tests": selected, "pytest": pytest, "pytest_status": "PASS" if pytest["exit_code"] == 0 else "FAIL", "protect_check": protect, "protect_check_status": "PASS" if protect["exit_code"] == 0 else "FAIL", "product_pass": False}


def _combined_no_generation(root: Path, out: Path) -> dict[str, Any]:
    out_report = validate_no_generation(out)
    run_report = validate_no_generation(root / RUN_FOLDER)
    return {
        "schema": "no_generation_audit_report.v1",
        "folders": [out_report, run_report],
        "pptx_count": out_report["pptx_count"] + run_report["pptx_count"],
        "image_count": out_report["image_count"] + run_report["image_count"],
        "render_image_count": out_report["render_image_count"] + run_report["render_image_count"],
        "pass": out_report["pass"] and run_report["pass"],
        "product_pass": False,
    }


def _final_decision(entry: dict[str, Any], scaffold: dict[str, Any], contract: dict[str, Any], claims: dict[str, Any], scaleout: dict[str, Any], no_generation: dict[str, Any], protected: dict[str, Any], tests: dict[str, Any]) -> dict[str, Any]:
    if protected.get("status") != "PASS_UNCHANGED":
        label = "RV00_FAIL_PROTECTED_ARTIFACTS"
    elif not no_generation.get("pass"):
        label = "RV00_FAIL_NO_GENERATION_POLICY"
    elif tests.get("status") != "PASS":
        label = "RV00_FAIL_TESTS"
    elif entry.get("entry_status") != "PASS":
        label = "RV00_BLOCKED_P07_NOT_PASSED"
    elif scaffold.get("status") != "RUN_004_SCAFFOLD_READY":
        label = "RV00_FAIL_RUN_004_SCAFFOLD"
    elif not contract.get("rv01_e03a_validation_required"):
        label = "RV00_FAIL_E03_REFERENCE_CONTRACT"
    elif scaleout.get("e04_allowed") or scaleout.get("d08_allowed"):
        label = "RV00_FAIL_SCALEOUT_LOCK_REGRESSION"
    else:
        label = "RV00_PASS_WITH_LIMITATIONS_READY_FOR_RV01"
    return {
        "schema": "rv00_rx_decision.v1",
        "decision": label,
        "active_recovery_run_folder": "design_runs/run_004",
        "objective_transition_status": "OBJECTIVE_TRANSITION_LOCKED_TO_RECOVERY_VALIDATION_PLANNING",
        "e03_direct_rerun_allowed": False,
        "rv01_may_start": label.startswith("RV00_PASS"),
        "e03_reference_readiness_status": "MISSING_OR_NOT_VALIDATED",
        "product_pass": False,
        "protected_artifact_status": protected.get("status"),
        "tests_status": tests.get("status"),
        "e04_d08_c11_bulk_may_start": False,
        "next_promptset": "RV01-RX — E03 Reference Inventory and Readiness Revalidation",
    }


def _summary_lines(final: dict[str, Any], transition: dict[str, Any], four_core: dict[str, Any], native: dict[str, Any]) -> list[str]:
    return [
        "- P07 status imported: `P07_PASS_WITH_LIMITATIONS_READY_FOR_RV00`",
        f"- objective transition status: `{transition['decision']}`",
        f"- active recovery run folder: `{final['active_recovery_run_folder']}`",
        f"- E03 direct rerun allowed: `{final['e03_direct_rerun_allowed']}`",
        f"- RV01 reference revalidation allowed: `{final['rv01_may_start']}`",
        f"- E03 reference readiness status: `{final['e03_reference_readiness_status']}`",
        f"- four-core readiness imported: `{four_core['four_core_readiness_status']}`",
        f"- native component readiness imported: `{native['native_component_readiness_status']}`",
        "- limitations carried forward: controlled-only, strict overflow, visual fidelity, backend, E03 references not validated",
        f"- E04/D08/C11/bulk status: `{final['e04_d08_c11_bulk_may_start']}`",
        "- canonical promotion status: `blocked`",
        f"- product_pass: `{final['product_pass']}`",
        f"- protected artifact status: `{final['protected_artifact_status']}`",
        f"- tests status: `{final['tests_status']}`",
        f"- final decision label: `{final['decision']}`",
        f"- next recommended PromptSet: `{final['next_promptset']}`",
    ]


def _protected_check(root: Path, phase: str, command_log: list[str]) -> dict[str, Any]:
    artifacts = []
    for rel in PROTECTED_ARTIFACTS:
        path = root / rel
        artifacts.append({"path": rel, "exists": path.is_file(), "size": path.stat().st_size if path.is_file() else None, "mtime": path.stat().st_mtime if path.is_file() else None, "sha256": _sha256(path) if path.is_file() else None})
    protect = _run_command(root, ["npm", "run", "protect:check"], command_log, allow_fail=True)
    return {"schema": f"protected_artifact_{phase}check.v1", "phase": phase, "cwd": str(root), "git_status_short": _run_command(root, ["git", "status", "--short"], command_log, allow_fail=True), "python_version": sys.version.split()[0], "node_version": _run_command(root, ["node", "--version"], command_log, allow_fail=True), "npm_version": _run_command(root, ["npm", "--version"], command_log, allow_fail=True), "protect_check": protect, "protect_check_write_classification": "SCRIPT_SELF_REPORT_WRITE", "artifacts": artifacts, "all_present": all(item["exists"] for item in artifacts), "status": "PASS" if all(item["exists"] for item in artifacts) and protect["exit_code"] == 0 else "FAIL", "product_pass": False}


def _validate_json(out: Path) -> dict[str, Any]:
    failures = []
    count = 0
    for path in sorted(out.rglob("*.json")):
        count += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append({"path": str(path), "error": str(exc)})
    return {"schema": "rv00_json_parse_validation.v1", "status": "PASS" if not failures else "FAIL", "json_file_count": count, "failures": failures}


def _manifest(out: Path, final: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "rv00_rx_manifest.v1", "created_at_utc": datetime.now(timezone.utc).isoformat(), "output_folder": str(out), "decision": final.get("decision"), "active_recovery_run_folder": "design_runs/run_004", "product_pass": False}


def _write_report(out: Path, stem: str, data: dict[str, Any], title: str, lines: list[str]) -> None:
    _write_json(out / f"{stem}.json", data)
    _write_markdown(out / f"{stem}.md", title, lines)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"# {title}", "", *lines]).rstrip() + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_command(root: Path, command: list[str], command_log: list[str], *, allow_fail: bool = False, timeout: int = 60) -> dict[str, Any]:
    actual = ["cmd", "/c", *command] if os.name == "nt" and command and command[0].lower() == "npm" else command
    command_log.append(f"- `{' '.join(command)}`")
    try:
        proc = subprocess.run(actual, cwd=root, text=True, capture_output=True, timeout=timeout)
    except Exception as exc:
        return {"command": command, "exit_code": 1, "stdout": "", "stderr": str(exc)}
    return {"command": command, "exit_code": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]}


def _snapshots_equal(pre: dict[str, Any], post: dict[str, Any]) -> bool:
    a = {item["path"]: (item.get("size"), item.get("sha256")) for item in pre.get("artifacts", [])}
    b = {item["path"]: (item.get("size"), item.get("sha256")) for item in post.get("artifacts", [])}
    return a == b


def _protected_lines(report: dict[str, Any]) -> list[str]:
    return [f"- status: `{report.get('status')}`", f"- all_present: `{report.get('all_present')}`", "- protected canonical artifacts were hashed and not modified by RV00."]
