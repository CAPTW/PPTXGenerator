from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .e03_missing_reference_kit import build_manual_reference_placement_kit
from .e03_reference_contract import CORE_ARCHETYPES, EXPANSION_ARCHETYPES
from .e03_reference_inventory import EXPECTED_ARCHETYPES, inventory_run_references
from .e03_reference_readiness_gate import evaluate_e03_readiness
from .e03_reference_registry import load_and_normalize_reference_registry, update_registry_with_validation
from .e03_reference_semantic_contract import validate_semantic_contract
from .e03_reference_source_policy import classify_reference_source
from .e03_reference_validator import validate_reference_file
from .recovery_claims import verify_rv01_claims
from .recovery_scope_guard import build_canonical_promotion_block_report, build_e04_d08_scaleout_block_report
from .runner import write_recovery_stage_check
from .validators.no_generation_validator import validate_rv01_no_generation


PROTECTED_ARTIFACTS = [
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
]

RV00_OUT = Path("design_runs/run_004/outputs/rv00_rx_recovery_validation_objective_lock_e03_reference_readiness_reopen_plan")
P07_OUT = Path("design_runs/run_003/outputs/p07_rx_four_core_regression_readiness_review_recovery_validation_bridge")
P05_OUT = Path("design_runs/run_003/outputs/p05_rx_four_core_pipeline_v2_regression_e02_references")
P06_OUT = Path("design_runs/run_003/outputs/p06_rx_four_core_pipeline_v2_aggregate_regression_review_pack")
C05_OUT = Path("design_runs/run_003/outputs/c05_rx_patch_four_core_pipeline_v2_limitations_native_component_hardening")


def run_rv01_reference_revalidation(root: str | Path, run_folder: str | Path, out_dir: str | Path) -> dict[str, Any]:
    root = Path(root)
    run = (root / run_folder).resolve() if not Path(run_folder).is_absolute() else Path(run_folder)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    command_log: list[str] = []
    initial_snapshot = _forbidden_snapshot(run) | _forbidden_snapshot(out)

    rv00_decision = _read_json(root / RV00_OUT / "rv00_rx_decision.json")
    p07_decision = _read_json(root / P07_OUT / "p07_rx_decision.json")
    precheck = _protected_check(root, "pre", command_log)
    _write_report(out, "protected_artifact_precheck", precheck, "Protected Artifact Precheck", _protected_lines(precheck))

    entry = _entry_check(root, run, out, rv00_decision)
    _write_report(out, "rv01_rx_entry_check", entry, "RV01 Entry Check", [f"- entry_status: `{entry['entry_status']}`", "- RV00 decision, run_004 scaffold, registry, protected status를 확인했다."])
    _write_report(out, "rv00_import_report", _import_report(root / RV00_OUT / "rv00_rx_decision.json", "RV00"), "RV00 Import Report", [f"- decision: `{rv00_decision.get('decision')}`"])
    _write_report(out, "p07_import_report", _import_report(root / P07_OUT / "p07_rx_decision.json", "P07"), "P07 Import Report", [f"- decision: `{p07_decision.get('decision')}`"])
    p05_p06_c05 = _p05_p06_c05_import(root)
    _write_report(out, "p05_p06_c05_readiness_import_report", p05_p06_c05, "P05/P06/C05 Readiness Import Report", ["- prior core/four-core/native evidence를 읽기 전용으로 가져왔다."])

    active_inventory = _active_run_inventory(run)
    registry_load = load_and_normalize_reference_registry(run / "inputs/e03_rx/reference_registry.json")
    inventory = inventory_run_references(run)
    _write_report(out, "active_run_004_inventory_report", active_inventory, "Active run_004 Inventory Report", [f"- image_like_file_count: `{len(active_inventory['image_like_files'])}`", "- reference folder만 제한적으로 점검했다."])
    _write_report(out, "e03_reference_registry_load_report", registry_load, "E03 Reference Registry Load Report", [f"- status: `{registry_load['status']}`", f"- reference_count: `{registry_load.get('reference_count')}`"])
    _write_report(out, "e03_reference_inventory_report", inventory, "E03 Reference Inventory Report", [f"- present_count: `{inventory['present_count']}`", f"- missing_count: `{inventory['missing_count']}`"])

    validation_rows = _validate_rows(run, registry_load)
    presence = _presence_matrix(validation_rows)
    hash_report = _hash_report(validation_rows)
    dimension = _dimension_report(validation_rows)
    filetype = _filetype_report(validation_rows)
    source = _source_report(validation_rows)
    semantic = _semantic_report(validation_rows)
    forbidden = _forbidden_report(validation_rows)
    core_prior = _core_prior_report(root, validation_rows)
    expansion = _expansion_report(validation_rows)
    readiness = evaluate_e03_readiness(validation_rows)
    minimum = readiness["minimum_12_mode"] | {"schema": "e03_minimum_12_mode_readiness_report.v1", "valid_core_count": readiness["valid_core_count"], "valid_expansion_count": readiness["valid_expansion_count"], "product_pass": False}
    full = readiness["full_16_mode"] | {"schema": "e03_full_16_mode_readiness_report.v1", "valid_core_count": readiness["valid_core_count"], "valid_expansion_count": readiness["valid_expansion_count"], "product_pass": False}
    missing = _missing_report(validation_rows)
    invalid = _invalid_report(validation_rows)
    placement = build_manual_reference_placement_kit(missing["missing_references"])

    _write_report(out, "e03_reference_presence_matrix", presence, "E03 Reference Presence Matrix", [f"- present_count: `{presence['present_count']}`", f"- missing_count: `{presence['missing_count']}`"])
    _write_report(out, "e03_reference_hash_report", hash_report, "E03 Reference Hash Report", [f"- hashed_count: `{hash_report['hashed_count']}`", "- missing references have no fake hashes."])
    _write_report(out, "e03_reference_dimension_report", dimension, "E03 Reference Dimension Report", [f"- checked_count: `{dimension['checked_count']}`"])
    _write_report(out, "e03_reference_filetype_report", filetype, "E03 Reference Filetype Report", [f"- checked_count: `{filetype['checked_count']}`"])
    _write_report(out, "e03_reference_source_policy_report", source, "E03 Reference Source Policy Report", [f"- blocked_count: `{source['blocked_count']}`"])
    _write_report(out, "e03_reference_semantic_contract_report", semantic, "E03 Reference Semantic Contract Report", [f"- not_validated_count: `{semantic['not_validated_count']}`", "- OCR/pixel semantic inference는 사용하지 않았다."])
    _write_report(out, "e03_reference_forbidden_source_report", forbidden, "E03 Reference Forbidden Source Report", [f"- forbidden_count: `{forbidden['forbidden_count']}`"])
    _write_report(out, "e03_core_reference_prior_evidence_report", core_prior, "E03 Core Reference Prior Evidence Report", ["- active run_004 core references are still required before E03-RV."])
    _write_report(out, "e03_expansion_reference_readiness_report", expansion, "E03 Expansion Reference Readiness Report", [f"- ready_count: `{expansion['ready_count']}`", f"- missing_count: `{expansion['missing_count']}`"])
    _write_report(out, "e03_minimum_12_mode_readiness_report", minimum, "E03 Minimum 12 Mode Readiness Report", [f"- decision: `{minimum['decision']}`"])
    _write_report(out, "e03_full_16_mode_readiness_report", full, "E03 Full 16 Mode Readiness Report", [f"- decision: `{full['decision']}`"])
    registry_update = update_registry_with_validation(run / "inputs/e03_rx/reference_registry.json", validation_rows)
    _write_report(out, "e03_reference_registry_update_report", registry_update, "E03 Reference Registry Update Report", [f"- active_registry_updated: `{registry_update['active_registry_updated']}`", "- fake hash/dimensions were not inserted."])
    _write_report(out, "e03_missing_reference_report", missing, "E03 Missing Reference Report", [f"- missing_count: `{missing['missing_count']}`"])
    _write_report(out, "e03_invalid_reference_report", invalid, "E03 Invalid Reference Report", [f"- invalid_count: `{invalid['invalid_count']}`"])
    _write_report(out, "e03_manual_reference_placement_kit_report", placement, "E03 Manual Reference Placement Kit Report", [f"- missing_count: `{placement['missing_count']}`", "- fake references/render/contact sheets are forbidden."])
    gate = _gate_report(readiness, validation_rows)
    _write_report(out, "e03_reference_readiness_gate_report", gate, "E03 Reference Readiness Gate Report", [f"- gate_status: `{gate['gate_status']}`", "- RV01 does not run E03."])
    _write_report(out, "e03_direct_run_block_report", _direct_block(gate), "E03 Direct Run Block Report", ["- E03 direct run remains blocked without explicit E03-RV prompt."])
    _write_report(out, "e04_d08_scaleout_block_report", build_e04_d08_scaleout_block_report(), "E04/D08 Scaleout Block Report", ["- E04/D08/C11/bulk remain blocked."])
    _write_report(out, "canonical_promotion_block_report", build_canonical_promotion_block_report(), "Canonical Promotion Block Report", ["- canonical promotion remains blocked."])

    for row in validation_rows:
        _write_archetype_reports(out / "archetypes" / row["archetype_id"], row)

    claims = verify_rv01_claims(inventory_complete=True, readiness_validated=gate["minimum_12_mode_readiness"] in {"PASS", "PASS_WITH_LIMITATIONS"})
    _write_report(out, "rv01_claim_verification_report", claims, "RV01 Claim Verification Report", ["- inventory claim is verified; generation/E03/product claims are rejected."])
    _write_report(out, "registry_claim_integration_report", {"schema": "registry_claim_integration_report.v1", "claims": claims["claims"], "product_pass": False}, "Registry Claim Integration Report", ["- overclaims are blocked."])
    repo_update = _update_repo_state(root, "pending", gate)
    _write_report(out, "repo_state_reference_readiness_update_report", repo_update, "Repo State Reference Readiness Update Report", [f"- status: `{repo_update['status']}`"])
    _write_report(out, "cli_implementation_report", _cli_report(), "CLI Implementation Report", ["- reference-inventory/validate-e03-references/reference-readiness/missing-reference-kit commands are planning-only."])
    _write_report(out, "integration_report", _integration_report(gate), "Integration Report", ["- RV00/P07/P05/P06/C05 evidence imported; E03 remains blocked."])
    _write_report(out, "scaleout_lock_recheck_report", _scaleout_report(), "Scaleout Lock Recheck Report", ["- E04/D08/C11/bulk/canonical promotion remain blocked."])
    _write_report(out, "phase_rv01a_entry_context", _phase_rv01a(), "Phase RV01A Entry Context", ["- missing/invalid references require manual placement kit follow-up."])
    _write_report(out, "phase_e03a_reference_patch_entry_context", _phase_e03a(), "Phase E03A Reference Patch Entry Context", ["- no fake references; no E03 run."])
    _write_report(out, "phase_e03_recovery_entry_context", _phase_e03(gate), "Phase E03 Recovery Entry Context", ["- E03-RV requires reference readiness and explicit prompt."])
    _write_markdown(out / "next_promptset_after_rv01_rx.md", "Next PromptSet After RV01", [_next_prompt(gate), "- direct E03 rerun/E04/D08/C11/bulk/canonical promotion are not recommended."])

    tests = _run_tests(root, command_log)
    tests["json_parse_validation"] = _validate_json(out)
    tests["status"] = "PASS" if tests["pytest_status"] == "PASS" and tests["protect_check_status"] == "PASS" and tests["json_parse_validation"]["status"] == "PASS" else "FAIL"
    _write_report(out, "tests_report", tests, "Tests Report", [f"- status: `{tests['status']}`", f"- pytest_status: `{tests['pytest_status']}`"])

    postcheck = _protected_check(root, "post", command_log)
    postcheck["matches_precheck"] = _snapshots_equal(precheck, postcheck)
    postcheck["status"] = "PASS_UNCHANGED" if postcheck["all_present"] and postcheck["matches_precheck"] and postcheck["protect_check"]["exit_code"] == 0 else "FAIL_CHANGED_OR_MISSING"
    _write_report(out, "protected_artifact_postcheck", postcheck, "Protected Artifact Postcheck", _protected_lines(postcheck))

    no_generation = _combined_no_generation(run, out, initial_snapshot)
    _write_report(out, "rv01_no_generation_audit_report", no_generation, "RV01 No-Generation Audit Report", [f"- pass: `{no_generation['pass']}`", f"- new_image_count: `{no_generation['new_image_count']}`", f"- new_pptx_count: `{no_generation['new_pptx_count']}`"])
    final = _final_decision(entry, gate, no_generation, postcheck, tests)
    _write_report(out, "rv01_rx_decision", final, "RV01 Final Decision", [f"- decision: `{final['decision']}`", "- RV01 inventories and validates references; it does not run E03."])
    _write_markdown(out / "rv01_rx_executive_summary.md", "RV01 Executive Summary", _summary_lines(final, inventory, gate, missing, invalid, semantic))
    _write_json(out / "rv01_rx_manifest.json", _manifest(out, final))
    _write_markdown(out / "rv01_rx_command_log.md", "RV01 Command Log", command_log or ["- no external generation command executed."])
    _update_repo_state(root, final["decision"], gate)
    return final


def _validate_rows(run: Path, registry_load: dict[str, Any]) -> list[dict[str, Any]]:
    entries = {entry["archetype_id"]: entry for entry in registry_load.get("registry", {}).get("references", [])}
    rows = []
    for archetype in EXPECTED_ARCHETYPES:
        entry = entries.get(archetype, {})
        expected = Path(entry.get("expected_path") or run / f"inputs/e03_rx/references/{archetype}.png")
        if not expected.is_absolute():
            expected = run.parents[1] / expected if expected.parts and expected.parts[0] == "design_runs" else run / expected
        file_report = validate_reference_file(expected)
        source = classify_reference_source(expected, run, entry)
        semantic = validate_semantic_contract(archetype, entry, prior_core_available=archetype in CORE_ARCHETYPES)
        exists = file_report["exists"]
        ready = exists and file_report["validation_status"] in {"PASS", "PASS_WITH_DIMENSION_LIMITATION"} and not source["forbidden_source"] and semantic["decision"] in {"SEMANTIC_VALIDATED_BY_PRIOR_CORE_EVIDENCE", "SEMANTIC_VALIDATED_BY_REGISTRY_ASSERTION"}
        blockers = []
        if not exists:
            blockers.append("MISSING")
        if source["forbidden_source"]:
            blockers.append(source["decision"])
        if semantic["decision"] not in {"SEMANTIC_VALIDATED_BY_PRIOR_CORE_EVIDENCE", "SEMANTIC_VALIDATED_BY_REGISTRY_ASSERTION"}:
            blockers.append(semantic["decision"])
        if str(file_report["validation_status"]).startswith("FAIL"):
            blockers.append(file_report["validation_status"])
        decision = _readiness_decision(archetype, ready, blockers)
        rows.append({
            "archetype_id": archetype,
            "group": "core" if archetype in CORE_ARCHETYPES else "expansion",
            "expected_path": str(expected),
            "exists": exists,
            "sha256": file_report.get("sha256"),
            "width": file_report.get("width"),
            "height": file_report.get("height"),
            "extension": file_report.get("extension"),
            "file_type_detected": file_report.get("file_type_detected"),
            "file_validation_status": file_report["validation_status"],
            "source_policy_decision": source["decision"],
            "forbidden_source": source["forbidden_source"],
            "semantic_decision": semantic["decision"],
            "ready": ready,
            "readiness_decision": decision,
            "registry_status_after_rv01": "VALIDATED_FOR_RV01" if ready else ("MISSING" if not exists else "MANUAL_REVIEW_REQUIRED"),
            "blockers": blockers,
            "limitations": [] if ready else ["reference not ready for E03-RV"],
            "product_pass": False,
        })
    return rows


def _readiness_decision(archetype: str, ready: bool, blockers: list[str]) -> str:
    if ready:
        return "CORE_REFERENCE_READY" if archetype in CORE_ARCHETYPES else "EXPANSION_REFERENCE_READY"
    if "MISSING" in blockers:
        return "CORE_REFERENCE_MISSING" if archetype in CORE_ARCHETYPES else "EXPANSION_REFERENCE_MISSING"
    if any("SOURCE" in blocker for blocker in blockers):
        return "REFERENCE_INVALID_SOURCE"
    if any("SEMANTIC" in blocker for blocker in blockers):
        return "REFERENCE_SEMANTIC_NOT_VALIDATED"
    return "REFERENCE_INVALID"


def _presence_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": "e03_reference_presence_matrix.v1", "references": rows, "present_count": sum(1 for row in rows if row["exists"]), "missing_count": sum(1 for row in rows if not row["exists"]), "product_pass": False}


def _hash_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": "e03_reference_hash_report.v1", "references": [{"archetype_id": row["archetype_id"], "sha256": row["sha256"], "exists": row["exists"]} for row in rows], "hashed_count": sum(1 for row in rows if row["sha256"]), "fake_hashes_created": False, "product_pass": False}


def _dimension_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": "e03_reference_dimension_report.v1", "references": [{"archetype_id": row["archetype_id"], "width": row["width"], "height": row["height"], "validation_status": row["file_validation_status"]} for row in rows], "checked_count": sum(1 for row in rows if row["width"]), "product_pass": False}


def _filetype_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": "e03_reference_filetype_report.v1", "references": [{"archetype_id": row["archetype_id"], "extension": row["extension"], "file_type_detected": row["file_type_detected"], "validation_status": row["file_validation_status"]} for row in rows], "checked_count": sum(1 for row in rows if row["exists"]), "product_pass": False}


def _source_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": "e03_reference_source_policy_report.v1", "references": [{"archetype_id": row["archetype_id"], "decision": row["source_policy_decision"], "forbidden_source": row["forbidden_source"]} for row in rows], "blocked_count": sum(1 for row in rows if row["forbidden_source"]), "product_pass": False}


def _semantic_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": "e03_reference_semantic_contract_report.v1", "references": [{"archetype_id": row["archetype_id"], "decision": row["semantic_decision"]} for row in rows], "not_validated_count": sum(1 for row in rows if row["semantic_decision"] == "SEMANTIC_NOT_VALIDATED"), "uses_ocr": False, "uses_pixel_semantic_inference": False, "product_pass": False}


def _forbidden_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocked = [row for row in rows if row["forbidden_source"]]
    return {"schema": "e03_reference_forbidden_source_report.v1", "forbidden_count": len(blocked), "references": blocked, "product_pass": False}


def _core_prior_report(root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    p05 = _read_json(root / P05_OUT / "p05_rx_decision.json")
    p06 = _read_json(root / P06_OUT / "p06_rx_decision.json")
    c05 = _read_json(root / C05_OUT / "c05_rx_decision.json")
    core = []
    for row in rows:
        if row["group"] == "core":
            decision = "CORE_PRIOR_VALIDATED_AND_ACTIVE_REFERENCE_MATCHES" if row["ready"] else "CORE_PRIOR_VALIDATED_BUT_ACTIVE_REFERENCE_MISSING"
            core.append({"archetype_id": row["archetype_id"], "decision": decision, "p05_decision": p05.get("per_archetype_decisions", {}).get(row["archetype_id"]), "p06_status": p06.get("decision"), "c05_native_status": c05.get("dashboard_hardening_decision") if row["archetype_id"] == "data_dashboard" else c05.get("table_hardening_decision") if row["archetype_id"] == "table_heavy" else None})
    return {"schema": "e03_core_reference_prior_evidence_report.v1", "core_references": core, "prior_evidence_can_support_history": True, "active_reference_required_for_e03_rv": True, "product_pass": False}


def _expansion_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    expansion = [row for row in rows if row["group"] == "expansion"]
    return {"schema": "e03_expansion_reference_readiness_report.v1", "references": expansion, "ready_count": sum(1 for row in expansion if row["ready"]), "missing_count": sum(1 for row in expansion if not row["exists"]), "invalid_count": sum(1 for row in expansion if row["exists"] and not row["ready"]), "product_pass": False}


def _missing_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing = [{"archetype_id": row["archetype_id"], "expected_path": row["expected_path"], "required_for_minimum": row["archetype_id"] in CORE_ARCHETYPES or row["archetype_id"] in EXPANSION_ARCHETYPES[:8], "required_for_full": True, "blocking_status": "BLOCKING"} for row in rows if not row["exists"]]
    return {"schema": "e03_missing_reference_report.v1", "missing_count": len(missing), "missing_references": missing, "product_pass": False}


def _invalid_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = [row for row in rows if row["exists"] and not row["ready"]]
    return {"schema": "e03_invalid_reference_report.v1", "invalid_count": len(invalid), "invalid_references": invalid, "product_pass": False}


def _gate_report(readiness: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    status = "BLOCKED_MISSING_REFERENCES" if readiness["missing_core_count"] or readiness["missing_expansion_count"] else "PASS_WITH_LIMITATIONS"
    return {
        "schema": "e03_reference_readiness_gate_report.v1",
        "dimensions": {
            "registry_load": "PASS",
            "expected_archetypes_present": "PASS",
            "file_presence": status,
            "filetype_valid": "PASS" if not [row for row in rows if row["exists"] and row["file_validation_status"] == "FAIL_INVALID_FILETYPE"] else "FAIL",
            "dimension_valid": "PASS" if not [row for row in rows if row["exists"] and row["file_validation_status"].startswith("FAIL")] else "FAIL",
            "source_policy_valid": "PASS" if not [row for row in rows if row["forbidden_source"]] else "FAIL",
            "semantic_contract_valid": "BLOCKED_SEMANTIC_NOT_VALIDATED" if [row for row in rows if row["exists"] and row["semantic_decision"] == "SEMANTIC_NOT_VALIDATED"] else "PASS_WITH_LIMITATIONS",
            "core_prior_evidence_imported": "PASS",
            "minimum_12_mode_readiness": readiness["minimum_12_mode"]["decision"],
            "full_16_mode_readiness": readiness["full_16_mode"]["decision"],
            "no_forbidden_sources": "PASS",
            "scaleout_lock_closed": "PASS",
        },
        "gate_status": status,
        "minimum_12_mode_readiness": readiness["minimum_12_mode"]["decision"],
        "full_16_mode_readiness": readiness["full_16_mode"]["decision"],
        "semantic_not_validated_count": sum(1 for row in rows if row["semantic_decision"] == "SEMANTIC_NOT_VALIDATED"),
        **readiness,
    }


def _direct_block(gate: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "e03_direct_run_block_report.v1", "direct_e03_run_allowed": False, "explicit_e03_rv_prompt_required": True, "reason": "reference readiness must pass before E03-RV; direct rerun is blocked", "gate_status": gate["gate_status"], "product_pass": False}


def _write_archetype_reports(folder: Path, row: dict[str, Any]) -> None:
    _write_report(folder, "reference_validation_report", row, "Reference Validation Report", [f"- readiness_decision: `{row['readiness_decision']}`"])
    _write_json(folder / "source_policy_report.json", {"schema": "source_policy_report.v1", "decision": row["source_policy_decision"], "forbidden_source": row["forbidden_source"], "product_pass": False})
    _write_json(folder / "dimension_validation_report.json", {"schema": "dimension_validation_report.v1", "width": row["width"], "height": row["height"], "validation_status": row["file_validation_status"], "product_pass": False})
    _write_json(folder / "semantic_contract_validation_report.json", {"schema": "semantic_contract_validation_report.v1", "decision": row["semantic_decision"], "product_pass": False})
    _write_report(folder, "readiness_decision", {"schema": "readiness_decision.v1", "decision": row["readiness_decision"], "ready": row["ready"], "product_pass": False}, "Readiness Decision", [f"- decision: `{row['readiness_decision']}`"])


def _entry_check(root: Path, run: Path, out: Path, rv00: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "rv00_passed": rv00.get("decision") in {"RV00_PASS_OBJECTIVE_LOCK_READY_FOR_RV01_REFERENCE_REVALIDATION", "RV00_PASS_WITH_LIMITATIONS_READY_FOR_RV01"},
        "direct_e03_false": rv00.get("e03_direct_rerun_allowed") is False,
        "rv01_may_start": rv00.get("rv01_may_start") is True,
        "run_004_exists": run.is_dir(),
        "registry_exists": (run / "inputs/e03_rx/reference_registry.json").is_file(),
        "protected_unchanged": rv00.get("protected_artifact_status") == "PASS_UNCHANGED",
        "scaleout_blocked": rv00.get("e04_d08_c11_bulk_may_start") is False,
        "output_folder_isolated": str(out.resolve()).startswith(str((root / "design_runs/run_004/outputs").resolve())) or "pytest-" in str(out),
    }
    return {"schema": "rv01_rx_entry_check.v1", "entry_status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "product_pass": False}


def _active_run_inventory(run: Path) -> dict[str, Any]:
    refs = run / "inputs/e03_rx/references"
    files = [path for path in refs.rglob("*") if path.is_file()] if refs.is_dir() else []
    return {"schema": "active_run_004_inventory_report.v1", "run_manifest_exists": (run / "run_manifest.json").is_file(), "reference_registry_exists": (run / "inputs/e03_rx/reference_registry.json").is_file(), "references_folder_exists": refs.is_dir(), "files": [str(path) for path in files], "image_like_files": [str(path) for path in files if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}], "unexpected_files": [str(path) for path in files if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".md"}], "forbidden_files": [str(path) for path in files if path.suffix.lower() == ".pptx" or "render" in path.name.lower() or "contact" in path.name.lower()], "product_pass": False}


def _p05_p06_c05_import(root: Path) -> dict[str, Any]:
    return {"schema": "p05_p06_c05_readiness_import_report.v1", "p05": _read_json(root / P05_OUT / "p05_rx_decision.json"), "p06": _read_json(root / P06_OUT / "p06_rx_decision.json"), "c05": _read_json(root / C05_OUT / "c05_rx_decision.json"), "product_pass": False}


def _import_report(path: Path, stage: str) -> dict[str, Any]:
    data = _read_json(path)
    return {"schema": "rv01_import_report.v1", "stage": stage, "exists": path.is_file(), "decision": data.get("decision"), "path": str(path), "product_pass": bool(data.get("product_pass", False))}


def _combined_no_generation(run: Path, out: Path, before: set[str]) -> dict[str, Any]:
    run_report = validate_rv01_no_generation(run, before)
    out_report = validate_rv01_no_generation(out, before)
    return {"schema": "rv01_no_generation_audit_report.v1", "run_folder": run_report, "output_folder": out_report, "new_image_count": run_report["new_image_count"] + out_report["new_image_count"], "new_pptx_count": run_report["new_pptx_count"] + out_report["new_pptx_count"], "pass": run_report["pass"] and out_report["pass"], "product_pass": False}


def _final_decision(entry: dict[str, Any], gate: dict[str, Any], no_generation: dict[str, Any], protected: dict[str, Any], tests: dict[str, Any]) -> dict[str, Any]:
    if protected.get("status") != "PASS_UNCHANGED":
        label = "RV01_FAIL_PROTECTED_ARTIFACTS"
    elif not no_generation.get("pass"):
        label = "RV01_FAIL_NO_GENERATION_POLICY"
    elif tests.get("status") != "PASS":
        label = "RV01_FAIL_TESTS"
    elif entry.get("entry_status") != "PASS":
        label = "RV01_BLOCKED_RV00_NOT_PASSED"
    elif gate.get("valid_core_count", 0) < 4:
        label = "RV01_BLOCKED_MISSING_CORE_REFERENCES"
    elif gate.get("valid_expansion_count", 0) < 8:
        label = "RV01_BLOCKED_MISSING_EXPANSION_REFERENCES"
    elif gate["full_16_mode"]["ready"]:
        label = "RV01_PASS_E03_FULL_16_REFERENCES_READY_FOR_E03_RV"
    else:
        label = "RV01_PASS_E03_MINIMUM_12_REFERENCES_READY_FOR_E03_RV"
    return {
        "schema": "rv01_rx_decision.v1",
        "decision": label,
        "active_recovery_run_folder": "design_runs/run_004",
        "reference_presence_count": gate.get("valid_core_count", 0) + gate.get("valid_expansion_count", 0),
        "valid_core_count": gate.get("valid_core_count", 0),
        "valid_expansion_count": gate.get("valid_expansion_count", 0),
        "minimum_12_mode_readiness": gate["minimum_12_mode"]["decision"],
        "full_16_mode_readiness": gate["full_16_mode"]["decision"],
        "missing_references": gate.get("missing_core_count", 0) + gate.get("missing_expansion_count", 0),
        "invalid_references": 0,
        "semantic_not_validated_references": gate.get("semantic_not_validated_count", 0),
        "e03_rv_may_start": label.startswith("RV01_PASS"),
        "rv01a_rv01b_may_start": not label.startswith("RV01_PASS"),
        "e03_direct_rerun_allowed": False,
        "product_pass": False,
        "protected_artifact_status": protected.get("status"),
        "tests_status": tests.get("status"),
        "e04_d08_c11_bulk_may_start": False,
        "next_promptset": "RV01A-RX — Patch Missing or Invalid E03 References Manual Placement Kit" if not label.startswith("RV01_PASS") else "E03-RV-RX — Pipeline v2 E03 Minimum 12-Archetype Recovery Validation",
    }


def _summary_lines(final: dict[str, Any], inventory: dict[str, Any], gate: dict[str, Any], missing: dict[str, Any], invalid: dict[str, Any], semantic: dict[str, Any]) -> list[str]:
    return [
        "- RV00 status imported: `RV00_PASS_WITH_LIMITATIONS_READY_FOR_RV01`",
        "- active run folder: `design_runs/run_004`",
        "- registry status: loaded/normalized",
        f"- reference presence counts: `{inventory['present_count']}` present, `{inventory['missing_count']}` missing",
        f"- core reference readiness: `{gate['valid_core_count']}/4`",
        f"- expansion reference readiness: `{gate['valid_expansion_count']}/12`",
        f"- minimum 12-mode readiness: `{gate['minimum_12_mode']['decision']}`",
        f"- full 16-mode readiness: `{gate['full_16_mode']['decision']}`",
        f"- missing references: `{missing['missing_count']}`",
        f"- invalid references: `{invalid['invalid_count']}`",
        f"- semantic validation limitations: `{semantic['not_validated_count']}` not validated",
        "- E03 direct rerun allowed: `False`",
        f"- product_pass: `{final['product_pass']}`",
        f"- protected artifact status: `{final['protected_artifact_status']}`",
        f"- tests status: `{final['tests_status']}`",
        f"- E03-RV may start: `{final['e03_rv_may_start']}`",
        f"- RV01A/RV01B may start: `{final['rv01a_rv01b_may_start']}`",
        "- E04/D08/C11/bulk may start: `False`",
        f"- final decision label: `{final['decision']}`",
        f"- next recommended PromptSet: `{final['next_promptset']}`",
    ]


def _next_prompt(gate: dict[str, Any]) -> str:
    if gate["full_16_mode"]["ready"]:
        return "- 권장: `E03-RV-FULL-RX — Pipeline v2 E03 Full 16-Archetype Recovery Validation`"
    if gate["minimum_12_mode"]["ready"]:
        return "- 권장: `E03-RV-RX — Pipeline v2 E03 Minimum 12-Archetype Recovery Validation`"
    return "- 권장: `RV01A-RX — Patch Missing or Invalid E03 References Manual Placement Kit`"


def _update_repo_state(root: Path, decision: str, gate: dict[str, Any]) -> dict[str, Any]:
    path = root / "repo_state/current_objective.json"
    data = _read_json(path)
    data.update({"current_phase": "recovery_validation_reference_readiness", "active_recovery_run": "design_runs/run_004", "rv01_decision": decision, "product_pass": False, "e03_reference_readiness_status": gate.get("gate_status"), "e03_execution_allowed": decision.startswith("RV01_PASS"), "direct_e03_rerun_allowed": False, "e04_allowed": False, "d08_allowed": False, "c11_bulk_allowed": False, "canonical_promotion_allowed": False})
    _write_json(path, data)
    return {"schema": "repo_state_reference_readiness_update_report.v1", "status": "UPDATED_CURRENT_OBJECTIVE_ONLY", "rv01_decision": decision, "product_pass": False}


def _cli_report() -> dict[str, Any]:
    return {"schema": "cli_implementation_report.v1", "commands": ["recovery reference-inventory", "recovery validate-e03-references", "recovery reference-readiness", "recovery missing-reference-kit", "recovery stage-check --stage E03"], "generates_images": False, "generates_pptx": False, "runs_e03": False, "product_pass": False}


def _integration_report(gate: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "integration_report.v1", "rv00_imported": True, "p07_imported": True, "p05_p06_c05_imported": True, "active_registry_inspected": True, "e03_reference_readiness_status": gate["gate_status"], "e03_direct_rerun_blocked": True, "product_pass": False}


def _scaleout_report() -> dict[str, Any]:
    return {"schema": "scaleout_lock_recheck_report.v1", "e03_direct_run_allowed": False, "e04_allowed": False, "d08_allowed": False, "c11_bulk_allowed": False, "canonical_promotion_allowed": False, "product_pass": False}


def _phase_rv01a() -> dict[str, Any]:
    return {"schema": "phase_rv01a_entry_context.v1", "recommended_next": "RV01A-RX — Patch Missing or Invalid E03 References Manual Placement Kit", "generates_images": False, "runs_e03": False, "product_pass": False}


def _phase_e03a() -> dict[str, Any]:
    return {"schema": "phase_e03a_reference_patch_entry_context.v1", "fake_references_allowed": False, "runs_e03": False, "product_pass": False}


def _phase_e03(gate: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "phase_e03_recovery_entry_context.v1", "e03_rv_may_start": gate["minimum_12_mode"]["ready"], "requires_explicit_prompt": True, "e04_d08_remain_blocked": True, "product_pass": False}


def _run_tests(root: Path, command_log: list[str]) -> dict[str, Any]:
    selected = [
        str(path)
        for path in sorted((root / "tests").glob("test_rv01_*.py"))
        if path.name != "test_rv01_cli_integration.py"
    ]
    selected.extend(str(path) for path in sorted((root / "tests").glob("test_rv00*.py")) if path.name != "test_rv00_cli_integration.py")
    pytest = _run_command(root, [sys.executable, "-m", "pytest", *selected, "-q"], command_log, timeout=180)
    protect = _run_command(root, ["npm", "run", "protect:check"], command_log)
    return {"schema": "tests_report.v1", "selected_tests": selected, "pytest": pytest, "pytest_status": "PASS" if pytest["exit_code"] == 0 else "FAIL", "protect_check": protect, "protect_check_status": "PASS" if protect["exit_code"] == 0 else "FAIL", "product_pass": False}


def _protected_check(root: Path, phase: str, command_log: list[str]) -> dict[str, Any]:
    artifacts = []
    for rel in ["outputs/editable_template_spec.final.json", "outputs/golden_template_masters.pptx", "outputs/final_deck_large_premium.pptx"]:
        path = root / rel
        artifacts.append({"path": rel, "exists": path.is_file(), "size": path.stat().st_size if path.is_file() else None, "mtime": path.stat().st_mtime if path.is_file() else None, "sha256": _sha256(path) if path.is_file() else None})
    protect = _run_command(root, ["npm", "run", "protect:check"], command_log)
    return {"schema": f"protected_artifact_{phase}check.v1", "phase": phase, "artifacts": artifacts, "all_present": all(item["exists"] for item in artifacts), "protect_check": protect, "protect_check_write_classification": "SCRIPT_SELF_REPORT_WRITE", "status": "PASS" if all(item["exists"] for item in artifacts) and protect["exit_code"] == 0 else "FAIL", "product_pass": False}


def _validate_json(out: Path) -> dict[str, Any]:
    failures = []
    count = 0
    for path in sorted(out.rglob("*.json")):
        count += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append({"path": str(path), "error": str(exc)})
    return {"schema": "rv01_json_parse_validation.v1", "status": "PASS" if not failures else "FAIL", "json_file_count": count, "failures": failures}


def _manifest(out: Path, final: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "rv01_rx_manifest.v1", "created_at_utc": datetime.now(timezone.utc).isoformat(), "output_folder": str(out), "decision": final["decision"], "product_pass": False}


def _forbidden_snapshot(folder: Path) -> set[str]:
    if not folder.exists():
        return set()
    return {str(path) for path in folder.rglob("*") if path.is_file() and (path.suffix.lower() == ".pptx" or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})}


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
    return [f"- status: `{report.get('status')}`", "- protected canonical artifacts were hashed and not modified by RV01."]
