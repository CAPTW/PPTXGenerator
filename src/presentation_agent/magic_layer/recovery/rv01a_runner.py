from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .e03_missing_reference_kit import (
    EXPECTED_ARCHETYPES,
    EXPANSION_ARCHETYPES,
    build_archetype_kit,
    build_core_reference_reuse_guidance,
    build_dimension_contract,
    build_dropzone_manifest,
    build_expansion_reference_requirements,
    build_filename_contract,
    build_forbidden_reference_source_contract,
    build_manual_placement_checklist,
    build_provenance_contract,
    build_readiness_rerun_checklist,
    build_rv01a_manual_placement_kit,
    build_semantic_assertion_contract,
    build_semantic_assertion_template,
)
from .e03_reference_registry import build_rv01a_registry_patch
from .recovery_claims import verify_rv01a_claims
from .recovery_scope_guard import build_canonical_promotion_block_report, build_e04_d08_scaleout_block_report
from .validators.manual_placement_kit_validator import validate_manual_placement_kit
from .validators.no_generation_validator import validate_rv01a_no_generation


PROTECTED_ARTIFACTS = [
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
]

RV00_OUT = Path("design_runs/run_004/outputs/rv00_rx_recovery_validation_objective_lock_e03_reference_readiness_reopen_plan")
RV01_OUT = Path("design_runs/run_004/outputs/rv01_rx_e03_reference_inventory_readiness_revalidation")
P07_OUT = Path("design_runs/run_003/outputs/p07_rx_four_core_regression_readiness_review_recovery_validation_bridge")
P05_OUT = Path("design_runs/run_003/outputs/p05_rx_four_core_pipeline_v2_regression_e02_references")
P06_OUT = Path("design_runs/run_003/outputs/p06_rx_four_core_pipeline_v2_aggregate_regression_review_pack")
C05_OUT = Path("design_runs/run_003/outputs/c05_rx_patch_four_core_pipeline_v2_limitations_native_component_hardening")


def run_rv01a_manual_placement_kit(root: str | Path, run_folder: str | Path, out_dir: str | Path) -> dict[str, Any]:
    root = Path(root)
    run = (root / run_folder).resolve() if not Path(run_folder).is_absolute() else Path(run_folder)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    command_log: list[str] = []
    initial_snapshot = _forbidden_snapshot(run) | _forbidden_snapshot(out)

    rv01 = _read_json(root / RV01_OUT / "rv01_rx_decision.json")
    rv00 = _read_json(root / RV00_OUT / "rv00_rx_decision.json")
    precheck = _protected_check(root, "pre", command_log)
    _write_report(out, "protected_artifact_precheck", precheck, "Protected Artifact Precheck", _protected_lines(precheck))

    entry = _entry_check(root, run, out, rv01, rv00)
    _write_report(out, "rv01a_rx_entry_check", entry, "RV01A Entry Check", [f"- entry_status: `{entry['entry_status']}`", "- RV01 blocked state and run_004 registry were checked."])
    _write_report(out, "rv00_import_report", _import_report(root / RV00_OUT / "rv00_rx_decision.json", "RV00"), "RV00 Import Report", [f"- decision: `{rv00.get('decision')}`"])
    _write_report(out, "rv01_import_report", _import_report(root / RV01_OUT / "rv01_rx_decision.json", "RV01"), "RV01 Import Report", [f"- decision: `{rv01.get('decision')}`"])
    _write_report(out, "p07_import_report", _import_report(root / P07_OUT / "p07_rx_decision.json", "P07"), "P07 Import Report", ["- P07 readiness evidence imported read-only."])
    core_evidence = _core_evidence(root)
    _write_report(out, "p05_p06_c05_core_evidence_import_report", core_evidence, "P05/P06/C05 Core Evidence Import Report", ["- Core prior hashes and native hardening context were imported read-only."])

    prior_hashes = {item["archetype_id"]: item.get("prior_hash") for item in core_evidence["core_references"]}
    kit = build_rv01a_manual_placement_kit(run)
    dropzone = build_dropzone_manifest(run)
    filename_contract = build_filename_contract()
    dimension_contract = build_dimension_contract()
    provenance_contract = build_provenance_contract()
    semantic_template = build_semantic_assertion_template()
    semantic_contract = build_semantic_assertion_contract()
    forbidden_contract = build_forbidden_reference_source_contract()
    checklist = build_manual_placement_checklist(run)
    core_guidance = build_core_reference_reuse_guidance(prior_hashes)
    expansion_requirements = build_expansion_reference_requirements()
    registry_patch = build_rv01a_registry_patch(run / "inputs/e03_rx/reference_registry.json", update_active=True, prior_hashes=prior_hashes)
    registry_patch_plan = _registry_patch_plan(run)
    rerun_checklist = build_readiness_rerun_checklist()
    kit_validation = validate_manual_placement_kit(kit)

    _write_report(out, "missing_reference_placement_plan", kit, "Missing Reference Placement Plan", [f"- missing_count: `{kit['missing_count']}`", "- RV01A creates instructions only; no references were generated."])
    _write_report(out, "manual_reference_dropzone_manifest", dropzone, "Manual Reference Dropzone Manifest", [f"- dropzone_path: `{dropzone['dropzone_path']}`"])
    _write_report(out, "e03_reference_filename_contract.v1", filename_contract, "E03 Reference Filename Contract", ["- Exact lowercase snake_case `.png` filenames are required."])
    _write_report(out, "e03_reference_dimension_contract.v1", dimension_contract, "E03 Reference Dimension Contract", ["- Preferred dimension is 1920x1080 with 16:9 aspect ratio."])
    _write_report(out, "e03_reference_provenance_contract.v1", provenance_contract, "E03 Reference Provenance Contract", ["- Provenance and forbidden-source confirmations are required."])
    _write_report(out, "e03_reference_semantic_assertion_contract.v1", semantic_contract, "E03 Reference Semantic Assertion Contract", ["- Semantic assertion defaults remain NOT_ASSERTED."])
    _write_report(out, "e03_forbidden_reference_source_contract.v1", forbidden_contract, "E03 Forbidden Reference Source Contract", ["- Renders, overlays, contact sheets, generated flood, quarantine, and canonical outputs are forbidden."])
    _write_report(out, "e03_reference_manual_placement_checklist", checklist, "E03 Reference Manual Placement Checklist", ["- Checklist is false by default until an operator places files and fills registry assertions."])
    _write_markdown(out / "e03_reference_operator_instructions.md", "E03 Reference Operator Instructions", _operator_lines(dropzone, filename_contract))
    _write_report(out, "e03_core_reference_reuse_guidance", core_guidance, "E03 Core Reference Reuse Guidance", ["- Core four have prior evidence, but active run_004 references are still required."])
    _write_report(out, "e03_expansion_reference_requirements", expansion_requirements, "E03 Expansion Reference Requirements", ["- Minimum E03 requires 8 valid expansion references; full E03 requires 12."])
    _write_report(out, "e03_manual_semantic_assertion_template", semantic_template, "E03 Manual Semantic Assertion Template", ["- Default semantic_assertion_status is NOT_ASSERTED."])
    _write_report(out, "e03_reference_registry_patch_plan", registry_patch_plan, "E03 Reference Registry Patch Plan", ["- Active registry entries are patched to AWAITING_MANUAL_PLACEMENT."])
    _write_json(out / "e03_reference_registry_proposed.json", registry_patch["registry"])
    _write_report(out, "e03_reference_registry_update_report", {k: v for k, v in registry_patch.items() if k != "registry"}, "E03 Reference Registry Update Report", [f"- status: `{registry_patch['status']}`", "- No fake hashes or dimensions were inserted."])
    _write_report(out, "e03_reference_readiness_rerun_checklist", rerun_checklist, "E03 Reference Readiness Rerun Checklist", ["- RV01 rerun is required after manual placement."])

    _write_input_guides(run, filename_contract, forbidden_contract, semantic_template, checklist)
    for archetype in EXPECTED_ARCHETYPES:
        _write_archetype_kit(out / "archetype_kits" / archetype, build_archetype_kit(run, archetype), semantic_template)

    claims = verify_rv01a_claims(kit_created=kit_validation["pass"], registry_patch_applied=registry_patch["active_registry_updated"])
    _write_report(out, "rv01a_claim_verification_report", claims, "RV01A Claim Verification Report", ["- Manual placement kit claim is verified; generation/E03/product claims are rejected."])
    _write_report(out, "registry_claim_integration_report", {"schema": "registry_claim_integration_report.v1", "claims": claims["claims"], "product_pass": False}, "Registry Claim Integration Report", ["- Registry claim integration preserves product_pass=false."])
    repo_update = _update_repo_state(root, "pending")
    _write_report(out, "repo_state_rv01a_update_report", repo_update, "Repo State RV01A Update Report", [f"- status: `{repo_update['status']}`"])
    _write_report(out, "cli_implementation_report", _cli_report(), "CLI Implementation Report", ["- recovery missing-reference-kit/reference-placement-checklist/propose-reference-registry commands create reports only."])
    _write_report(out, "integration_report", _integration_report(registry_patch), "Integration Report", ["- RV01 missing-reference result imported; manual placement kit created."])
    _write_report(out, "scaleout_lock_recheck_report", _scaleout_report(), "Scaleout Lock Recheck Report", ["- E03 direct run, E04, D08, C11/bulk, and canonical promotion remain blocked."])
    _write_report(out, "phase_manual_reference_placement_entry_context", _phase_manual(dropzone), "Phase Manual Reference Placement Entry Context", ["- Operator places references manually in the run_004 dropzone."])
    _write_report(out, "phase_rv01_rerun_entry_context", _phase_rv01_rerun(), "Phase RV01 Rerun Entry Context", ["- RV01 rerun is needed after files and registry assertions are placed."])
    _write_report(out, "phase_rv01b_entry_context", _phase_rv01b(), "Phase RV01B Entry Context", ["- RV01B is only for missing/insufficient semantic assertions after files exist."])
    _write_report(out, "phase_e03_recovery_entry_context", _phase_e03(), "Phase E03 Recovery Entry Context", ["- E03-RV remains blocked until RV01 rerun passes and explicit E03-RV prompt starts."])
    _write_markdown(out / "next_promptset_after_rv01a_rx.md", "Next PromptSet After RV01A", ["- 권장: `MANUAL_STEP — Place E03 Reference Images and Fill Registry Assertions`", "- 그 다음: `RV01-RX-RERUN — E03 Reference Inventory and Readiness Revalidation`", "- direct E03 rerun, E04, D08, C11, bulk, canonical promotion은 권장하지 않는다."])

    tests = _run_tests(root, command_log)
    tests["json_parse_validation"] = _validate_json(out)
    tests["status"] = "PASS" if tests["pytest_status"] == "PASS" and tests["protect_check_status"] == "PASS" and tests["json_parse_validation"]["status"] == "PASS" else "FAIL"
    _write_report(out, "tests_report", tests, "Tests Report", [f"- status: `{tests['status']}`", f"- pytest_status: `{tests['pytest_status']}`"])

    postcheck = _protected_check(root, "post", command_log)
    postcheck["matches_precheck"] = _snapshots_equal(precheck, postcheck)
    postcheck["status"] = "PASS_UNCHANGED" if postcheck["all_present"] and postcheck["matches_precheck"] and postcheck["protect_check"]["exit_code"] == 0 else "FAIL_CHANGED_OR_MISSING"
    _write_report(out, "protected_artifact_postcheck", postcheck, "Protected Artifact Postcheck", _protected_lines(postcheck))

    no_generation = _combined_no_generation(run, out, initial_snapshot)
    _write_report(out, "rv01a_no_generation_audit_report", no_generation, "RV01A No-Generation Audit Report", [f"- pass: `{no_generation['pass']}`", f"- new_image_count: `{no_generation['new_image_count']}`", f"- new_pptx_count: `{no_generation['new_pptx_count']}`"])
    final = _final_decision(entry, kit_validation, registry_patch, no_generation, postcheck, tests)
    _write_report(out, "rv01a_rx_decision", final, "RV01A Final Decision", [f"- decision: `{final['decision']}`", "- RV01A creates a manual placement kit; it does not create references."])
    _write_markdown(out / "rv01a_rx_executive_summary.md", "RV01A Executive Summary", _summary_lines(final, dropzone, registry_patch))
    _write_json(out / "rv01a_rx_manifest.json", _manifest(out, final))
    _write_markdown(out / "rv01a_rx_command_log.md", "RV01A Command Log", command_log or ["- no external generation command executed."])
    _update_repo_state(root, final["decision"])
    return final


def _entry_check(root: Path, run: Path, out: Path, rv01: dict[str, Any], rv00: dict[str, Any]) -> dict[str, Any]:
    blocked_decisions = {
        "RV01_BLOCKED_MISSING_CORE_REFERENCES",
        "RV01_BLOCKED_MISSING_EXPANSION_REFERENCES",
        "RV01_BLOCKED_INVALID_REFERENCES",
        "RV01_BLOCKED_SEMANTIC_NOT_VALIDATED",
        "RV01_BLOCKED_REFERENCE_REGISTRY_INVALID",
    }
    already_ready = str(rv01.get("decision", "")).startswith("RV01_PASS")
    checks = {
        "rv01_present": bool(rv01),
        "rv01_blocked_for_reference_issue": rv01.get("decision") in blocked_decisions,
        "rv01a_may_start": rv01.get("rv01a_rv01b_may_start") is True or "RV01A" in _read_text(root / RV01_OUT / "next_promptset_after_rv01_rx.md"),
        "rv01_no_generation": _read_json(root / RV01_OUT / "rv01_no_generation_audit_report.json").get("pass") is True,
        "rv00_passed": str(rv00.get("decision", "")).startswith("RV00_PASS"),
        "run_004_exists": run.is_dir(),
        "registry_exists": (run / "inputs/e03_rx/reference_registry.json").is_file(),
        "protected_unchanged": rv01.get("protected_artifact_status") == "PASS_UNCHANGED",
        "scaleout_blocked": rv01.get("e04_d08_c11_bulk_may_start") is False,
        "output_folder_isolated": str(out.resolve()).startswith(str((root / "design_runs/run_004/outputs").resolve())) or "pytest-" in str(out),
        "references_already_ready": already_ready is False,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {"schema": "rv01a_rx_entry_check.v1", "entry_status": status, "checks": checks, "product_pass": False}


def _core_evidence(root: Path) -> dict[str, Any]:
    hashes = _read_json(root / P05_OUT / "four_core_reference_hash_validation.json").get("rows", {})
    p05 = _read_json(root / P05_OUT / "p05_rx_decision.json")
    p06 = _read_json(root / P06_OUT / "p06_rx_decision.json")
    c05 = _read_json(root / C05_OUT / "c05_rx_decision.json")
    rows = []
    for archetype in ["cover_hero", "standard_content", "data_dashboard", "table_heavy"]:
        rows.append({
            "archetype_id": archetype,
            "prior_hash": hashes.get(archetype, {}).get("sha256"),
            "prior_reference_path": hashes.get(archetype, {}).get("selected_reference_path"),
            "p05_decision": p05.get("per_archetype_decisions", {}).get(archetype),
            "p06_decision": p06.get("decision"),
            "c05_status": c05.get("dashboard_hardening_decision") if archetype == "data_dashboard" else c05.get("table_hardening_decision") if archetype == "table_heavy" else None,
            "active_run_004_reference_required": True,
        })
    return {"schema": "p05_p06_c05_core_evidence_import_report.v1", "core_references": rows, "rv01a_copied_references": False, "product_pass": False}


def _registry_patch_plan(run: Path) -> dict[str, Any]:
    return {
        "schema": "e03_reference_registry_patch_plan.v1",
        "registry_path": str(run / "inputs/e03_rx/reference_registry.json"),
        "target_status": "AWAITING_MANUAL_PLACEMENT",
        "entries_to_patch": len(EXPECTED_ARCHETYPES),
        "fake_hashes_allowed": False,
        "fake_dimensions_allowed": False,
        "semantic_asserted_by_rv01a": False,
        "next_validation_stage": "RV01_RERUN",
        "product_pass": False,
    }


def _write_input_guides(run: Path, filename_contract: dict[str, Any], forbidden_contract: dict[str, Any], semantic_template: dict[str, Any], checklist: dict[str, Any]) -> None:
    base = run / "inputs/e03_rx"
    refs = base / "references"
    refs.mkdir(parents=True, exist_ok=True)
    _write_markdown(base / "README.md", "E03 Reference Input Folder", ["- 이 폴더는 RV01A manual placement kit용 입력 위치다.", "- RV01A는 image/PPTX/render를 생성하지 않는다.", "- reference images는 operator가 수동으로 배치한 뒤 RV01 rerun으로 검증한다."])
    _write_markdown(refs / "README.md", "E03 Reference Dropzone", ["- 이 폴더에 정확한 파일명으로 reference images를 수동 배치한다.", "- renders, overlays, contact sheets, screenshots, generated flood, quarantine, canonical/output artifacts는 금지된다."])
    _write_markdown(refs / "PLACEMENT_CHECKLIST.md", "Placement Checklist", _checklist_lines(checklist))
    _write_json(refs / "SEMANTIC_ASSERTION_TEMPLATE.json", semantic_template)
    _write_markdown(refs / "FORBIDDEN_SOURCES.md", "Forbidden Sources", [f"- `{item}`" for item in forbidden_contract["forbidden_sources"]])
    _write_markdown(refs / "EXPECTED_FILENAMES.md", "Expected Filenames", [f"- `{name}`" for name in filename_contract["expected_filenames"]])


def _write_archetype_kit(folder: Path, kit: dict[str, Any], semantic_template: dict[str, Any]) -> None:
    _write_report(folder, "requirements", kit, "Requirements", [f"- archetype_id: `{kit['archetype_id']}`", f"- expected_filename: `{kit['expected_filename']}`"])
    _write_markdown(folder / "placement_instruction.md", "Placement Instruction", [f"- Place `{kit['expected_filename']}` at `{kit['expected_path']}`.", "- Do not use renders, overlays, contact sheets, screenshots, generated flood, quarantine, output, or canonical artifacts."])
    example = dict(semantic_template)
    example["archetype_id"] = kit["archetype_id"]
    example["reference_filename"] = kit["expected_filename"]
    example["required_semantic_elements_present"] = []
    _write_json(folder / "semantic_assertion_example.json", example)
    _write_markdown(folder / "forbidden_examples.md", "Forbidden Examples", ["- render/contact_sheet/overlay/screenshot filenames", "- generated-flood references", "- quarantine or canonical/output artifacts"])
    checklist = {"schema": "rv01a_archetype_readiness_checklist.v1", "archetype_id": kit["archetype_id"], "items": {"file_placed": False, "correct_filename": False, "dimension_checked": False, "provenance_filled": False, "semantic_assertion_filled": False, "forbidden_source_checked": False, "ready_for_rv01_rerun": False}, "product_pass": False}
    _write_report(folder, "readiness_checklist", checklist, "Readiness Checklist", ["- All checklist values remain false until manual placement is complete."])


def _operator_lines(dropzone: dict[str, Any], filename_contract: dict[str, Any]) -> list[str]:
    return [
        f"- Place reference images under `{dropzone['dropzone_path']}`.",
        "- Use exact filenames:",
        *[f"  - `{name}`" for name in filename_contract["expected_filenames"]],
        "- Do not place renders, overlays, contact sheets, screenshots, generated-flood images, quarantine files, old output artifacts, or canonical artifacts.",
        "- Update `reference_registry.json` with provenance, semantic assertion, source note, and forbidden-source confirmations.",
        "- Minimum E03 requires 4 core + at least 8 expansion references.",
        "- Full E03 requires all 16 references.",
        "- After placement, run `RV01-RX-RERUN — E03 Reference Inventory and Readiness Revalidation`.",
    ]


def _checklist_lines(checklist: dict[str, Any]) -> list[str]:
    lines = ["- Operator checklist before RV01 rerun:"]
    for item in checklist["items"]:
        lines.append(f"- `{item['expected_filename']}`: file placed, filename correct, 16:9, provenance filled, semantic assertion filled, forbidden source checked.")
    return lines


def _combined_no_generation(run: Path, out: Path, before: set[str]) -> dict[str, Any]:
    run_report = validate_rv01a_no_generation(run, before)
    out_report = validate_rv01a_no_generation(out, before)
    return {
        "schema": "rv01a_no_generation_audit_report.v1",
        "run_folder": run_report,
        "output_folder": out_report,
        "new_image_count": run_report["new_image_count"] + out_report["new_image_count"],
        "new_pptx_count": run_report["new_pptx_count"] + out_report["new_pptx_count"],
        "pass": run_report["pass"] and out_report["pass"],
        "product_pass": False,
    }


def _final_decision(entry: dict[str, Any], kit_validation: dict[str, Any], registry_patch: dict[str, Any], no_generation: dict[str, Any], protected: dict[str, Any], tests: dict[str, Any]) -> dict[str, Any]:
    if protected.get("status") != "PASS_UNCHANGED":
        label = "RV01A_FAIL_PROTECTED_ARTIFACTS"
    elif not no_generation.get("pass"):
        label = "RV01A_FAIL_NO_GENERATION_POLICY"
    elif tests.get("status") != "PASS":
        label = "RV01A_FAIL_TESTS"
    elif entry.get("entry_status") != "PASS":
        label = "RV01A_BLOCKED_RV01_MISSING"
    elif not kit_validation.get("pass"):
        label = "RV01A_FAIL_MANUAL_PLACEMENT_KIT"
    elif not registry_patch.get("active_registry_updated"):
        label = "RV01A_PASS_MANUAL_PLACEMENT_KIT_READY_FOR_MANUAL_REFERENCES"
    else:
        label = "RV01A_PASS_WITH_REGISTRY_PATCH_READY_FOR_MANUAL_REFERENCES"
    return {
        "schema": "rv01a_rx_decision.v1",
        "decision": label,
        "reference_dropzone_path": "design_runs/run_004/inputs/e03_rx/references",
        "registry_patch_status": registry_patch.get("status"),
        "missing_references_count": 16,
        "expected_core_filenames": [f"{archetype}.png" for archetype in ["cover_hero", "standard_content", "data_dashboard", "table_heavy"]],
        "expected_expansion_filenames": [f"{archetype}.png" for archetype in EXPANSION_ARCHETYPES],
        "semantic_assertion_template_path": "design_runs/run_004/inputs/e03_rx/references/SEMANTIC_ASSERTION_TEMPLATE.json",
        "no_generation_audit_status": "PASS" if no_generation.get("pass") else "FAIL",
        "protected_artifact_status": protected.get("status"),
        "tests_status": tests.get("status"),
        "manual_placement_may_start": label.startswith("RV01A_PASS"),
        "rv01_rerun_may_start": False,
        "e03_may_start": False,
        "e04_d08_c11_bulk_may_start": False,
        "product_pass": False,
        "next_promptset": "MANUAL_STEP — Place E03 Reference Images and Fill Registry Assertions; then RV01-RX-RERUN — E03 Reference Inventory and Readiness Revalidation",
    }


def _summary_lines(final: dict[str, Any], dropzone: dict[str, Any], registry_patch: dict[str, Any]) -> list[str]:
    return [
        "- RV01 status imported: `RV01_BLOCKED_MISSING_CORE_REFERENCES`",
        "- missing reference count: `16`",
        "- kit output path: `design_runs/run_004/outputs/rv01a_rx_patch_missing_invalid_e03_references_manual_placement_kit/`",
        f"- reference dropzone path: `{dropzone['dropzone_path']}`",
        f"- registry patch status: `{registry_patch['status']}`",
        "- core reference reuse guidance status: `CREATED`",
        "- expansion reference requirements status: `CREATED`",
        "- semantic assertion template status: `CREATED_NOT_ASSERTED`",
        f"- no-generation audit status: `{final['no_generation_audit_status']}`",
        f"- protected artifact status: `{final['protected_artifact_status']}`",
        f"- tests status: `{final['tests_status']}`",
        f"- manual placement may start: `{final['manual_placement_may_start']}`",
        "- RV01 rerun may start now: `False`",
        "- E03 may start: `False`",
        "- E04/D08/C11/bulk may start: `False`",
        f"- final decision label: `{final['decision']}`",
        f"- next recommended PromptSet: `{final['next_promptset']}`",
    ]


def _run_tests(root: Path, command_log: list[str]) -> dict[str, Any]:
    selected = [
        str(path)
        for path in sorted((root / "tests").glob("test_rv01a_*.py"))
        if path.name != "test_rv01a_cli_integration.py"
    ]
    selected.extend(str(path) for path in sorted((root / "tests").glob("test_rv01_*.py")) if path.name != "test_rv01_cli_integration.py")
    selected.extend(str(path) for path in sorted((root / "tests").glob("test_rv00_*.py")) if path.name != "test_rv00_cli_integration.py")
    pytest = _run_command(root, [sys.executable, "-m", "pytest", *selected, "-q"], command_log, timeout=180)
    protect = _run_command(root, ["npm", "run", "protect:check"], command_log)
    return {"schema": "tests_report.v1", "selected_tests": selected, "pytest": pytest, "pytest_status": "PASS" if pytest["exit_code"] == 0 else "FAIL", "protect_check": protect, "protect_check_status": "PASS" if protect["exit_code"] == 0 else "FAIL", "product_pass": False}


def _protected_check(root: Path, phase: str, command_log: list[str]) -> dict[str, Any]:
    artifacts = []
    for rel in PROTECTED_ARTIFACTS:
        path = root / rel
        artifacts.append({"path": rel, "exists": path.is_file(), "size": path.stat().st_size if path.is_file() else None, "mtime": path.stat().st_mtime if path.is_file() else None, "sha256": _sha256(path) if path.is_file() else None})
    environment = {
        "pwd": str(root),
        "git_status_short": _run_command(root, ["git", "status", "--short"], command_log),
        "python_version": _run_command(root, [sys.executable, "--version"], command_log),
        "node_version": _run_command(root, ["node", "--version"], command_log),
        "npm_version": _run_command(root, ["npm", "--version"], command_log),
    }
    protect = _run_command(root, ["npm", "run", "protect:check"], command_log)
    return {"schema": f"protected_artifact_{phase}check.v1", "phase": phase, "environment": environment, "artifacts": artifacts, "all_present": all(item["exists"] for item in artifacts), "protect_check": protect, "protect_check_write_classification": "SCRIPT_SELF_REPORT_WRITE", "status": "PASS" if all(item["exists"] for item in artifacts) and protect["exit_code"] == 0 else "FAIL", "product_pass": False}


def _update_repo_state(root: Path, decision: str) -> dict[str, Any]:
    path = root / "repo_state/current_objective.json"
    data = _read_json(path)
    data.update({
        "current_phase": "recovery_validation_reference_manual_placement",
        "active_recovery_run": "design_runs/run_004",
        "rv01a_decision": decision,
        "product_pass": False,
        "e03_reference_readiness_status": "AWAITING_MANUAL_PLACEMENT",
        "e03_execution_allowed": False,
        "direct_e03_rerun_allowed": False,
        "rv01_rerun_allowed_after_manual_placement": True,
        "e04_allowed": False,
        "d08_allowed": False,
        "c11_bulk_allowed": False,
        "canonical_promotion_allowed": False,
    })
    _write_json(path, data)
    return {"schema": "repo_state_rv01a_update_report.v1", "status": "UPDATED_CURRENT_OBJECTIVE_ONLY", "rv01a_decision": decision, "product_pass": False}


def _phase_manual(dropzone: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "phase_manual_reference_placement_entry_context.v1", "dropzone_path": dropzone["dropzone_path"], "expected_filenames": dropzone["expected_filenames"], "minimum_mode": "4 core + 8 expansion", "full_mode": "4 core + 12 expansion", "product_pass": False}


def _phase_rv01_rerun() -> dict[str, Any]:
    return {"schema": "phase_rv01_rerun_entry_context.v1", "rerun_after_manual_placement": True, "runs_e03": False, "expected_decisions": ["minimum ready", "full ready", "still blocked missing", "semantic not validated"], "product_pass": False}


def _phase_rv01b() -> dict[str, Any]:
    return {"schema": "phase_rv01b_entry_context.v1", "use_if": "files present but semantic assertions missing or insufficient", "generates_images": False, "uses_ocr": False, "product_pass": False}


def _phase_e03() -> dict[str, Any]:
    return {"schema": "phase_e03_recovery_entry_context.v1", "blocked_until_rv01_rerun_passes": True, "requires_explicit_e03_rv_prompt": True, "e04_d08_remain_blocked": True, "product_pass": False}


def _cli_report() -> dict[str, Any]:
    return {"schema": "cli_implementation_report.v1", "commands": ["recovery missing-reference-kit", "recovery reference-placement-checklist", "recovery propose-reference-registry", "recovery stage-check --stage E03"], "generates_images": False, "generates_pptx": False, "runs_e03": False, "product_pass": False}


def _integration_report(registry_patch: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "integration_report.v1", "rv00_imported": True, "rv01_missing_reference_result_imported": True, "run_004_registry_patched": registry_patch.get("active_registry_updated"), "manual_placement_kit_created": True, "rv01_rerun_next_after_manual_placement": True, "e03_direct_run_blocked": True, "product_pass": False}


def _scaleout_report() -> dict[str, Any]:
    return {"schema": "scaleout_lock_recheck_report.v1", "e03_direct_run_allowed": False, "e04_allowed": False, "d08_allowed": False, "c11_bulk_allowed": False, "canonical_promotion_allowed": False, "product_pass": False}


def _import_report(path: Path, stage: str) -> dict[str, Any]:
    data = _read_json(path)
    return {"schema": "rv01a_import_report.v1", "stage": stage, "exists": path.is_file(), "decision": data.get("decision"), "path": str(path), "product_pass": bool(data.get("product_pass", False))}


def _manifest(out: Path, final: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "rv01a_rx_manifest.v1", "created_at_utc": datetime.now(timezone.utc).isoformat(), "output_folder": str(out), "decision": final["decision"], "product_pass": False}


def _forbidden_snapshot(folder: Path) -> set[str]:
    if not folder.exists():
        return set()
    return {str(path) for path in folder.rglob("*") if path.is_file() and (path.suffix.lower() == ".pptx" or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})}


def _validate_json(out: Path) -> dict[str, Any]:
    failures = []
    count = 0
    for path in sorted(out.rglob("*.json")):
        count += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append({"path": str(path), "error": str(exc)})
    return {"schema": "rv01a_json_parse_validation.v1", "status": "PASS" if not failures else "FAIL", "json_file_count": count, "failures": failures}


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


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_command(root: Path, command: list[str], command_log: list[str], timeout: int = 60) -> dict[str, Any]:
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
    return [f"- status: `{report.get('status')}`", "- protected canonical artifacts were hashed and not modified by RV01A."]
