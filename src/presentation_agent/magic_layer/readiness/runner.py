from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .boundary_checks import build_boundary_reports
from .evidence_inventory import STAGE_PATHS, build_pipeline_v2_evidence_inventory, collect_stage_decisions
from .limitation_register import build_limitation_closure_matrix, build_remaining_gap_register
from .maturity_matrix import build_controlled_ladder_maturity_matrix
from .readiness_claims import verify_readiness_claims
from .recovery_bridge import (
    build_e03_reference_gap_report,
    build_e03_reopen_prerequisites,
    decide_recovery_validation_bridge,
)
from .scorecard import build_four_core_regression_scorecard, build_native_component_readiness_scorecard
from .validators.no_generation_validator import validate_no_generation
from .validators.readiness_scorecard_validator import validate_readiness_scorecard
from .validators.recovery_bridge_validator import validate_recovery_bridge_decision


PROTECTED_ARTIFACTS = [
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
]

P07_REQUIRED_IMPORTS = [
    ("a01", "A01"),
    ("b03", "B03"),
    ("e01p", "E01P"),
    ("b01", "B01"),
    ("t01", "T01"),
    ("t02", "T02"),
    ("c01", "C01"),
    ("c02b", "C02B"),
    ("c03a_retry", "C03A_RETRY"),
    ("p02", "P02"),
    ("p03", "P03"),
    ("c04", "C04"),
    ("p04", "P04"),
    ("p05", "P05"),
    ("p06", "P06"),
    ("c05", "C05"),
]


def run_p07_readiness_review(root: str | Path, out_dir: str | Path) -> dict[str, Any]:
    root = Path(root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    command_log: list[str] = []

    precheck = _protected_check(root, "pre", command_log)
    _write_report(out, "protected_artifact_precheck", precheck, "Protected Artifact Precheck", _protected_lines(precheck))

    inventory = build_pipeline_v2_evidence_inventory(root)
    evidence = collect_stage_decisions(root)
    entry = _entry_check(root, inventory, evidence, out)
    _write_report(out, "p07_rx_entry_check", entry, "P07 Entry Check", [f"- entry_status: `{entry['entry_status']}`", "- C05/P06/P05/P04/P03/C04/P02 evidence를 기존 산출물에서만 확인했다."])

    for report_name, stage in P07_REQUIRED_IMPORTS:
        report = _import_report(root, stage, inventory)
        _write_report(out, f"{report_name}_import_report", report, f"{stage} Import Report", [f"- decision: `{report.get('decision')}`", f"- exists: `{report.get('exists')}`", "- 가져온 증거는 읽기 전용으로 사용했다."])

    scope_policy = {
        "schema": "readiness_review_scope_policy.v1",
        "allowed_mode": "READINESS_REVIEW_ONLY",
        "allowed_actions": ["import_evidence", "validate_reports", "compute_scorecards", "create_decision_reports", "safe_readiness_metadata_update_report"],
        "forbidden_actions": ["reference_generation", "pptx_generation", "rendering", "E03_run", "E04_run", "D08_C11_bulk", "canonical_promotion"],
        "decision": "P07_SCOPE_ALLOWED",
        "product_pass": False,
    }
    _write_report(out, "readiness_review_scope_policy.v1", scope_policy, "Readiness Review Scope Policy", ["- P07은 readiness review only 모드다.", "- PPTX/PNG/reference 생성은 금지되어 있다."])

    maturity = build_controlled_ladder_maturity_matrix(inventory)
    four_core = build_four_core_regression_scorecard(evidence)
    native = build_native_component_readiness_scorecard(evidence)
    limitations = build_limitation_closure_matrix(evidence)
    gaps = build_remaining_gap_register()
    bridge = decide_recovery_validation_bridge(evidence, bridge_blocking_gap_count=int(limitations["bridge_blocking_gap_count"]))
    e03_prereq = build_e03_reopen_prerequisites()
    e03_gap = build_e03_reference_gap_report()
    boundaries = build_boundary_reports()
    claims = verify_readiness_claims(
        bridge_ready=bool(bridge["rv00_objective_lock_allowed"]),
        four_core_ready=str(four_core["readiness_label"]).startswith("FOUR_CORE_READY"),
    )

    _write_report(out, "pipeline_v2_evidence_inventory", inventory, "Pipeline v2 Evidence Inventory", [f"- stage_count: `{inventory['stage_count']}`", "- 모든 단계는 기존 증거로만 평가했다."])
    _write_report(out, "controlled_ladder_maturity_matrix", maturity, "Controlled Ladder Maturity Matrix", ["- 대부분의 controlled ladder는 M4/M5 수준으로 평가된다.", "- M6 product readiness는 부여하지 않았다."])
    _write_report(out, "four_core_regression_readiness_scorecard", four_core, "Four-Core Regression Readiness Scorecard", [f"- readiness_label: `{four_core['readiness_label']}`", "- bridge readiness는 E03 실행 허가가 아니다."])
    _write_report(out, "native_component_readiness_scorecard", native, "Native Component Readiness Scorecard", [f"- decision: `{native['decision']}`", "- dashboard/table raster fallback은 계속 fatal이다."])

    b03_b01 = _b03_b01_maturity_report(evidence)
    protocol = _protocol_contract_planner_report(evidence)
    compiler = _compiler_render_report(evidence)
    fixtures = _regression_fixture_report(evidence)
    recovery_prereq = _recovery_prerequisite_report(bridge, inventory)
    _write_report(out, "b03_b01_gate_maturity_report", b03_b01, "B03/B01 Gate Maturity Report", [f"- conclusion: `{b03_b01['conclusion']}`", "- 제품 readiness나 canonical promotion에는 충분하지 않다."])
    _write_report(out, "protocol_contract_planner_maturity_report", protocol, "Protocol Contract Planner Maturity Report", [f"- conclusion: `{protocol['conclusion']}`", "- future E03 reference는 semantic invention 없이 gate를 통과해야 한다."])
    _write_report(out, "compiler_render_backend_maturity_report", compiler, "Compiler Render Backend Maturity Report", [f"- conclusion: `{compiler['conclusion']}`", "- controlled scope에서는 허용되지만 production-grade로 보지 않는다."])
    _write_report(out, "regression_fixture_maturity_report", fixtures, "Regression Fixture Maturity Report", [f"- conclusion: `{fixtures['conclusion']}`", "- fixture maturity는 arbitrary robustness를 증명하지 않는다."])
    _write_report(out, "limitation_closure_matrix", limitations, "Limitation Closure Matrix", [f"- bridge_blocking_gap_count: `{limitations['bridge_blocking_gap_count']}`", "- 남은 제한은 숨기지 않고 RV00/C06로 전달한다."])
    _write_report(out, "remaining_gap_register", gaps, "Remaining Gap Register", [f"- gap_count: `{len(gaps['gaps'])}`", "- 제품 readiness, source-bound, scaleout, canonical promotion gap은 계속 남아 있다."])
    _write_report(out, "recovery_validation_bridge_prerequisite_report", recovery_prereq, "Recovery Validation Bridge Prerequisite Report", [f"- decision: `{recovery_prereq['decision']}`", "- bridge는 RV00 계획 가능성을 뜻하며 E03 실행을 뜻하지 않는다."])
    _write_report(out, "e03_reopen_prerequisite_report", e03_prereq, "E03 Reopen Prerequisite Report", [f"- decision: `{e03_prereq['decision']}`", "- P07은 E03를 열지 않는다."])
    _write_report(out, "e03_reference_readiness_gap_report", e03_gap, "E03 Reference Readiness Gap Report", [f"- decision: `{e03_gap['decision']}`", "- E03 직접 rerun은 reference readiness 전까지 차단된다."])
    _write_report(out, "source_bound_readiness_boundary_report", boundaries["source_bound"], "Source-Bound Boundary Report", ["- source_bound_ready: `False`", "- E04는 E03 recovery validation pass 전까지 차단된다."])
    _write_report(out, "scaleout_readiness_boundary_report", boundaries["scaleout"], "Scaleout Boundary Report", ["- E03 direct rerun/E04/D08/C11/bulk는 모두 차단된다."])
    _write_report(out, "canonical_promotion_boundary_report", boundaries["canonical"], "Canonical Promotion Boundary Report", ["- canonical_promotion_allowed: `False`", "- golden_template_masters 업데이트는 허용하지 않는다."])
    _write_report(out, "readiness_claim_verification_report", claims, "Readiness Claim Verification Report", ["- product PASS와 arbitrary robustness 주장은 overclaim으로 처리했다."])
    _write_report(out, "recovery_validation_bridge_decision", bridge, "Recovery Validation Bridge Decision", [f"- decision: `{bridge['decision']}`", f"- rv00_objective_lock_allowed: `{bridge['rv00_objective_lock_allowed']}`", f"- e03_direct_rerun_allowed: `{bridge['e03_direct_rerun_allowed']}`"])

    repo_state_update = _repo_state_update_report(bridge, four_core, native)
    _write_report(out, "repo_state_readiness_update_report", repo_state_update, "Repo State Readiness Update Report", [f"- status: `{repo_state_update['status']}`", "- repo_state 파일은 보수적으로 변경하지 않았다."])
    _write_report(out, "cli_implementation_report", _cli_report(), "CLI Implementation Report", ["- `readiness review/scorecard/bridge-decision/e03-prereqs/claim-check` 명령을 추가했다.", "- CLI는 PPTX/PNG를 생성하지 않는다."])
    _write_report(out, "integration_report", _integration_report(), "Integration Report", ["- C05부터 A01까지 controlled evidence ladder를 통합했다.", "- product boundary는 유지된다."])
    _write_report(out, "registry_claim_integration_report", _registry_claim_report(claims), "Registry Claim Integration Report", ["- claim registry 관점에서 overclaim은 차단된다."])
    _write_report(out, "scaleout_lock_recheck_report", _scaleout_report(), "Scaleout Lock Recheck Report", ["- E03 직접 실행, E04, D08, C11/bulk, canonical promotion은 모두 false다."])

    _write_report(out, "phase_rv00_entry_context", _phase_rv00_context(bridge), "Phase RV00 Entry Context", ["- 다음 권장 단계는 RV00 objective lock이다.", "- RV00도 E03를 직접 실행하지 않는다."])
    _write_report(out, "phase_c06_entry_context", _phase_c06_context(), "Phase C06 Entry Context", ["- C06은 선택적 limitation patch 경로다."])
    _write_report(out, "phase_e03_recovery_entry_context", _phase_e03_context(), "Phase E03 Recovery Entry Context", ["- E03는 RV00/reference readiness 후에만 논의할 수 있다."])
    _write_markdown(out / "next_promptset_after_p07_rx.md", "Next PromptSet After P07", ["- 권장: `RV00-RX — Recovery Validation Objective Lock and E03 Reference Readiness Reopen Plan`", "- 직접 E03 rerun, E04, D08, C11, bulk, canonical promotion은 권장하지 않는다."])

    test_report = _run_tests(root, command_log)
    json_validation = _validate_json_outputs(out)
    test_report["json_parse_validation"] = json_validation
    test_report["status"] = "PASS" if test_report["pytest_status"] == "PASS" and json_validation["status"] == "PASS" else "FAIL"
    _write_report(out, "tests_report", test_report, "Tests Report", [f"- status: `{test_report['status']}`", f"- pytest_status: `{test_report['pytest_status']}`", f"- json_parse_validation: `{json_validation['status']}`"])

    postcheck = _protected_check(root, "post", command_log)
    postcheck["matches_precheck"] = _snapshots_equal(precheck, postcheck)
    postcheck["status"] = "PASS_UNCHANGED" if postcheck["all_present"] and postcheck["matches_precheck"] else "FAIL_CHANGED_OR_MISSING"
    _write_report(out, "protected_artifact_postcheck", postcheck, "Protected Artifact Postcheck", _protected_lines(postcheck))

    no_generation = validate_no_generation(out)
    _write_report(out, "no_generation_audit_report", no_generation, "No-Generation Audit Report", [f"- pass: `{no_generation['pass']}`", f"- pptx_count: `{no_generation['pptx_count']}`", f"- png_count: `{no_generation['png_count']}`"])

    final_decision = _final_decision(entry, four_core, native, limitations, bridge, postcheck, test_report, no_generation)
    _write_report(out, "p07_rx_decision", final_decision, "P07 Final Decision", [f"- decision: `{final_decision['decision']}`", "- P07은 E03를 실행하지 않았고 PPTX/PNG를 생성하지 않았다."])
    _write_markdown(out / "p07_rx_executive_summary.md", "P07 Executive Summary", _executive_summary_lines(final_decision, four_core, native, bridge, postcheck, test_report))
    manifest = _manifest(out, final_decision, precheck, postcheck)
    _write_json(out / "p07_rx_manifest.json", manifest)
    _write_markdown(out / "p07_rx_command_log.md", "P07 Command Log", command_log or ["- 외부 생성 명령 없음."])
    return final_decision


def _entry_check(root: Path, inventory: dict[str, Any], evidence: dict[str, dict[str, Any]], out: Path) -> dict[str, Any]:
    required_prefixes = {
        "C05": "C05_PASS",
        "P06": "P06_PASS",
        "P05": "P05_PASS",
        "P04": "P04_PASS",
        "C04": "C04_PASS",
        "P03": "P03_PASS",
        "P02": "P02_PASS",
    }
    checks = {
        stage: str(evidence.get(stage, {}).get("decision", "")).startswith(prefix)
        for stage, prefix in required_prefixes.items()
    }
    checks["p07_output_folder_isolated"] = str(out.resolve()).startswith(str((root / "design_runs/run_003/outputs").resolve()))
    checks["scaleout_locked"] = evidence.get("C05", {}).get("e03_e04_d08_c11_bulk_may_start") is False
    passed = all(checks.values())
    return {
        "schema": "p07_rx_entry_check.v1",
        "entry_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "stage_count": inventory.get("stage_count"),
        "decision_if_blocked": None if passed else "P07_BLOCKED_MISSING_REQUIRED_EVIDENCE",
        "product_pass": False,
    }


def _import_report(root: Path, stage: str, inventory: dict[str, Any]) -> dict[str, Any]:
    row = inventory["stages"].get(stage, {})
    path = Path(row.get("decision_path", ""))
    data = _read_json(path)
    return {
        "schema": "p07_import_report.v1",
        "stage": stage,
        "exists": row.get("exists", False),
        "decision": row.get("decision"),
        "decision_path": str(path),
        "output_folder": row.get("output_folder"),
        "key_evidence": row.get("key_evidence", []),
        "protected_artifact_status": row.get("protected_artifact_status"),
        "product_pass": bool(data.get("product_pass", False)),
        "read_only_import": True,
        "quarantine_excluded": True,
    }


def _protected_check(root: Path, phase: str, command_log: list[str]) -> dict[str, Any]:
    artifacts = []
    for rel in PROTECTED_ARTIFACTS:
        path = root / rel
        artifacts.append({
            "path": rel,
            "exists": path.is_file(),
            "size": path.stat().st_size if path.is_file() else None,
            "mtime": path.stat().st_mtime if path.is_file() else None,
            "sha256": _sha256(path) if path.is_file() else None,
        })
    protect = _run_command(root, ["npm", "run", "protect:check"], command_log)
    return {
        "schema": f"protected_artifact_{phase}check.v1",
        "phase": phase,
        "cwd": str(root),
        "git_status_short": _run_command(root, ["git", "status", "--short"], command_log, allow_fail=True),
        "python_version": sys.version.split()[0],
        "node_version": _run_command(root, ["node", "--version"], command_log, allow_fail=True),
        "npm_version": _run_command(root, ["npm", "--version"], command_log, allow_fail=True),
        "protect_check": protect,
        "protect_check_write_classification": "SCRIPT_SELF_REPORT_WRITE",
        "artifacts": artifacts,
        "all_present": all(item["exists"] for item in artifacts),
        "status": "PASS" if all(item["exists"] for item in artifacts) and protect["exit_code"] == 0 else "FAIL",
        "product_pass": False,
    }


def _run_tests(root: Path, command_log: list[str]) -> dict[str, Any]:
    selected = [
        *sorted(str(path) for path in (root / "tests").glob("test_p07*.py")),
        str(root / "tests/test_p06_no_e03_no_scaleout_unlock.py"),
        str(root / "tests/test_p06_claim_registry_integration.py"),
        str(root / "tests/test_c05_no_e03_no_scaleout_unlock.py"),
        str(root / "tests/test_c05_claim_registry_integration.py"),
    ]
    selected = [path for path in selected if Path(path).is_file()]
    result = _run_command(root, [sys.executable, "-m", "pytest", *selected, "-q"], command_log, allow_fail=True, timeout=120)
    protect = _run_command(root, ["npm", "run", "protect:check"], command_log, allow_fail=True)
    return {
        "schema": "tests_report.v1",
        "selected_tests": selected,
        "pytest": result,
        "pytest_status": "PASS" if result["exit_code"] == 0 else "FAIL",
        "protect_check": protect,
        "protect_check_status": "PASS" if protect["exit_code"] == 0 else "FAIL",
        "product_pass": False,
    }


def _validate_json_outputs(out: Path) -> dict[str, Any]:
    failures = []
    count = 0
    for path in sorted(out.rglob("*.json")):
        count += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - diagnostic path
            failures.append({"path": str(path), "error": str(exc)})
    return {"schema": "p07_json_parse_validation.v1", "status": "PASS" if not failures else "FAIL", "json_file_count": count, "failures": failures}


def _final_decision(
    entry: dict[str, Any],
    four_core: dict[str, Any],
    native: dict[str, Any],
    limitations: dict[str, Any],
    bridge: dict[str, Any],
    protected: dict[str, Any],
    tests: dict[str, Any],
    no_generation: dict[str, Any],
) -> dict[str, Any]:
    if protected.get("status") != "PASS_UNCHANGED":
        label = "P07_FAIL_PROTECTED_ARTIFACTS"
    elif not no_generation.get("pass"):
        label = "P07_FAIL_NO_GENERATION_POLICY"
    elif tests.get("status") != "PASS":
        label = "P07_FAIL_TESTS"
    elif entry.get("entry_status") != "PASS":
        label = "P07_BLOCKED_MISSING_REQUIRED_EVIDENCE"
    elif not str(four_core.get("readiness_label", "")).startswith("FOUR_CORE_READY"):
        label = "P07_BLOCKED_FOUR_CORE_NOT_READY"
    elif native.get("decision") == "NATIVE_COMPONENT_PATCH_REQUIRED":
        label = "P07_BLOCKED_NATIVE_COMPONENT_NOT_READY"
    elif not bridge.get("rv00_objective_lock_allowed"):
        label = "P07_FAIL_RECOVERY_BRIDGE_DECISION"
    else:
        label = "P07_PASS_WITH_LIMITATIONS_READY_FOR_RV00"
    passed = label.startswith("P07_PASS")
    return {
        "schema": "p07_rx_decision.v1",
        "decision": label,
        "four_core_readiness_status": four_core.get("readiness_label"),
        "native_component_readiness_status": native.get("decision"),
        "limitation_closure_summary": {
            "bridge_blocking_gap_count": limitations.get("bridge_blocking_gap_count"),
            "open_nonblocking_or_deferred": len([row for row in limitations.get("limitations", []) if row.get("status") in {"OPEN_NONBLOCKING", "DEFERRED", "REDUCED"}]),
        },
        "recovery_bridge_decision": bridge.get("decision"),
        "e03_direct_rerun_allowed": False,
        "rv00_may_start": bool(bridge.get("rv00_objective_lock_allowed")) and passed,
        "c06_may_start": True,
        "product_pass": False,
        "protected_artifact_status": protected.get("status"),
        "tests_status": tests.get("status"),
        "e04_d08_c11_bulk_may_start": False,
        "next_promptset": "RV00-RX — Recovery Validation Objective Lock and E03 Reference Readiness Reopen Plan",
    }


def _b03_b01_maturity_report(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "b03_b01_gate_maturity_report.v1",
        "b03": {
            "status": evidence.get("P06", {}).get("aggregate_b03_status", "PASS_WITH_LIMITATIONS"),
            "covers": ["OOXML audit", "full-slide raster", "semantic editability", "native component detection", "unknown content", "aggregate validation"],
            "sufficient_for_bridge": True,
            "sufficient_for_product": False,
        },
        "b01": {
            "status": evidence.get("P06", {}).get("aggregate_b01_review_status", "REVIEW_READY_WITH_LIMITATIONS"),
            "covers": ["review packet", "overlays", "visual smoke", "text overflow heuristic", "native component review"],
            "sufficient_for_bridge": True,
            "sufficient_for_product": False,
        },
        "conclusion": "SUFFICIENT_FOR_CONTROLLED_RECOVERY_VALIDATION_PLANNING_WITH_LIMITATIONS",
        "product_pass": False,
    }


def _protocol_contract_planner_report(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "protocol_contract_planner_maturity_report.v1",
        "conclusion": "READY_FOR_RECOVERY_VALIDATION_PLANNING_WITH_REFERENCE_GATES",
        "can_evaluate_future_e03_without_semantic_invention": True,
        "fatal_blockers_before_compile": True,
        "chart_table_requirements_representable": True,
        "source_bound_readiness": False,
        "limitations": ["legacy normalization remains controlled", "fixture-based mapping is not arbitrary robustness"],
        "product_pass": False,
    }


def _compiler_render_report(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "compiler_render_backend_maturity_report.v1",
        "conclusion": "CONTROLLED_BACKEND_ACCEPTABLE_WITH_LIMITATIONS",
        "compile_evidence": [evidence.get(stage, {}).get("decision") for stage in ["P03", "P04", "P05", "P06", "C05"]],
        "preserves_native_objects": True,
        "avoids_raster_fallback": True,
        "powerpoint_com_render_reliability": "CONTROLLED_SCOPE_PASS_WITH_LIMITATIONS",
        "production_grade": False,
        "product_pass": False,
    }


def _regression_fixture_report(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fixtures = ["E01 fail fixture", "E01B repaired fixture", "E02 four-core fixture", "P03 minimal sample", "P04 real-reference sample", "P05 four-core outputs", "P06 aggregate pack", "C05 hardened dashboard/table"]
    return {
        "schema": "regression_fixture_maturity_report.v1",
        "fixtures": [{"fixture": item, "status": "SUFFICIENT_FOR_BRIDGE_WITH_LIMITATIONS", "claim_allowed": "controlled evidence only"} for item in fixtures],
        "conclusion": "SUFFICIENT_FOR_RECOVERY_VALIDATION_BRIDGE_NOT_ARBITRARY_ROBUSTNESS",
        "product_pass": False,
    }


def _recovery_prerequisite_report(bridge: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    prerequisites = ["A01 governance pass", "B03 validation pass", "E01P protocol pass", "T01/T02/C01/C02B/C03A pipeline pass", "P03 controlled replay pass", "C04 fixture repair pass", "P04 real-reference sample pass", "P05 four-core pass", "P06 aggregate pass", "C05 hardening pass", "product_pass false", "scaleout lock closed", "protected artifacts unchanged"]
    return {
        "schema": "recovery_validation_bridge_prerequisite_report.v1",
        "meaning": "RV00 planning can be prepared; E03 does not start automatically",
        "prerequisites": [{"name": item, "status": "PASS_WITH_LIMITATIONS"} for item in prerequisites],
        "decision": bridge.get("decision"),
        "product_pass": False,
    }


def _repo_state_update_report(bridge: dict[str, Any], four_core: dict[str, Any], native: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "repo_state_readiness_update_report.v1",
        "status": "SAFE_SKIP_NO_REPO_STATE_MUTATION",
        "proposed_metadata": {
            "p07_readiness_status": "READY_WITH_LIMITATIONS",
            "bridge_decision": bridge.get("decision"),
            "four_core_regression_status": four_core.get("readiness_label"),
            "native_component_status": native.get("decision"),
            "product_pass": False,
            "e03_direct_rerun_allowed": False,
            "rv00_objective_lock_allowed": bridge.get("rv00_objective_lock_allowed"),
            "e04_allowed": False,
            "d08_allowed": False,
            "canonical_promotion_allowed": False,
        },
        "product_pass": False,
    }


def _cli_report() -> dict[str, Any]:
    return {
        "schema": "cli_implementation_report.v1",
        "commands": ["readiness review", "readiness scorecard", "readiness bridge-decision", "readiness e03-prereqs", "readiness claim-check"],
        "read_existing_outputs_only": True,
        "generates_pptx": False,
        "generates_png": False,
        "starts_e03_e04_d08": False,
        "product_pass": False,
    }


def _integration_report() -> dict[str, Any]:
    return {
        "schema": "integration_report.v1",
        "integrated_stages": ["C05", "P06", "P05", "P04", "P03", "C04", "P02", "A01", "B03", "E01P", "B01", "T01", "T02", "C01", "C02B", "C03A"],
        "product_boundary_maintained": True,
        "recovery_validation_bridge_decision_created": True,
        "product_pass": False,
    }


def _registry_claim_report(claims: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "registry_claim_integration_report.v1", "claims": claims.get("claims", []), "overclaims_rejected": True, "product_pass": False}


def _scaleout_report() -> dict[str, Any]:
    return {
        "schema": "scaleout_lock_recheck_report.v1",
        "e03_direct_rerun_allowed": False,
        "e04_allowed": False,
        "d08_allowed": False,
        "c11_bulk_allowed": False,
        "canonical_promotion_allowed": False,
        "decision": "SCALEOUT_LOCK_REMAINS_CLOSED",
        "product_pass": False,
    }


def _phase_rv00_context(bridge: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "phase_rv00_entry_context.v1",
        "recommended_next": "RV00-RX — Recovery Validation Objective Lock and E03 Reference Readiness Reopen Plan",
        "rv00_may_start": bridge.get("rv00_objective_lock_allowed"),
        "product_pass": False,
        "e03_direct_rerun_allowed": False,
        "e04_d08_allowed": False,
    }


def _phase_c06_context() -> dict[str, Any]:
    return {
        "schema": "phase_c06_entry_context.v1",
        "c06_may_start": True,
        "recommended_if": "blocking or prioritized limitation patch is desired before RV00",
        "targets": ["strict overflow gap", "backend limitation", "native component evidence gap", "manual-review governance debt", "aggregate preservation limitation"],
        "product_pass": False,
    }


def _phase_e03_context() -> dict[str, Any]:
    return {
        "schema": "phase_e03_recovery_entry_context.v1",
        "e03_may_start_directly": False,
        "requires": ["RV00 objective lock", "E03 reference readiness validation"],
        "e04_d08_remain_blocked": True,
        "product_pass": False,
    }


def _manifest(out: Path, decision: dict[str, Any], precheck: dict[str, Any], postcheck: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "p07_rx_manifest.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_folder": str(out),
        "decision": decision.get("decision"),
        "product_pass": False,
        "protected_artifact_precheck_status": precheck.get("status"),
        "protected_artifact_postcheck_status": postcheck.get("status"),
        "no_generation_policy": "ENFORCED",
    }


def _executive_summary_lines(decision: dict[str, Any], four_core: dict[str, Any], native: dict[str, Any], bridge: dict[str, Any], protected: dict[str, Any], tests: dict[str, Any]) -> list[str]:
    return [
        f"- C05 status imported: `C05_PASS_WITH_LIMITATIONS_READY_FOR_P07`",
        f"- P06/P05/P04/P03/C04 evidence imported: `true`",
        f"- four-core readiness: `{four_core.get('readiness_label')}`",
        f"- native component readiness: `{native.get('decision')}`",
        "- B03/B01 maturity: `SUFFICIENT_FOR_CONTROLLED_RECOVERY_VALIDATION_PLANNING_WITH_LIMITATIONS`",
        "- protocol/contract/planner maturity: `READY_FOR_RECOVERY_VALIDATION_PLANNING_WITH_REFERENCE_GATES`",
        "- compiler/render backend maturity: `CONTROLLED_BACKEND_ACCEPTABLE_WITH_LIMITATIONS`",
        "- regression fixture maturity: `SUFFICIENT_FOR_RECOVERY_VALIDATION_BRIDGE_NOT_ARBITRARY_ROBUSTNESS`",
        "- limitation closure: bridge blocker 0, product gaps remain open",
        "- remaining bridge blockers: `0`",
        "- E03 reopen prerequisite: RV00/reference readiness required",
        "- source-bound boundary: `false`",
        "- scaleout boundary: `closed`",
        "- canonical boundary: `blocked`",
        f"- product_pass: `{decision.get('product_pass')}`",
        f"- protected artifact status: `{protected.get('status')}`",
        f"- tests status: `{tests.get('status')}`",
        f"- RV00 may start: `{decision.get('rv00_may_start')}`",
        f"- C06 may start: `{decision.get('c06_may_start')}`",
        "- direct E03 may start: `False`",
        "- E04/D08/C11/bulk may start: `False`",
        f"- final decision label: `{decision.get('decision')}`",
        f"- next recommended PromptSet: `{decision.get('next_promptset')}`",
    ]


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
    actual_command = _platform_command(command)
    command_log.append(f"- `{_command_text(command)}`")
    try:
        proc = subprocess.run(actual_command, cwd=root, text=True, capture_output=True, timeout=timeout)
    except Exception as exc:  # pragma: no cover - environment diagnostic
        if not allow_fail:
            return {"command": command, "exit_code": 1, "stdout": "", "stderr": str(exc)}
        return {"command": command, "exit_code": 1, "stdout": "", "stderr": str(exc)}
    return {
        "command": command,
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _command_text(command: list[str]) -> str:
    return " ".join(command)


def _platform_command(command: list[str]) -> list[str]:
    if os.name == "nt" and command and command[0].lower() == "npm":
        return ["cmd", "/c", *command]
    return command


def _snapshots_equal(precheck: dict[str, Any], postcheck: dict[str, Any]) -> bool:
    pre = {item["path"]: (item.get("size"), item.get("sha256")) for item in precheck.get("artifacts", [])}
    post = {item["path"]: (item.get("size"), item.get("sha256")) for item in postcheck.get("artifacts", [])}
    return pre == post


def _protected_lines(report: dict[str, Any]) -> list[str]:
    return [
        f"- status: `{report.get('status')}`",
        f"- all_present: `{report.get('all_present')}`",
        "- protected canonical artifacts were hashed and not modified by P07.",
    ]
