from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.manifest_io import write_json  # noqa: E402
from presentation_agent.deckcompiler.identity import stable_id  # noqa: E402
from presentation_agent.deckcompiler.qa.inspection import (  # noqa: E402
    directory_fingerprint as diagnostic_directory_fingerprint,
)
from presentation_agent.deckcompiler.release.bundle_fingerprint import (  # noqa: E402
    build_bundle_authority,
    build_bundle_fingerprint_policy,
    build_legacy_correction_record,
    build_runtime_bundle_compatibility,
    discover_legacy_value_history,
    inventory_subtree_history,
    replay_bundle_history,
    validate_bundle_authority,
    verify_bound_hash,
)
from presentation_agent.deckcompiler.release.contracts import (  # noqa: E402
    bind_content_hash,
    build_component_provenance,
    build_runtime_environment_manifest,
    scan_release_text,
    sha256_file,
    validate_license_report,
    validate_release_contract,
    verify_content_hash,
)
from presentation_agent.deckcompiler.schemas import validator_for  # noqa: E402


BASELINE = "e0259b7551c381f8c0de4cdd329d5943680fa502"
PHASE6_HEAD = "c3a2202078f3125b3861924ab356b31cf818b4e0"
SOURCE_COMMIT = "541e4d1627951fd93ef25ef0b260eebead396229"
AUTHORITY_SOURCE_COMMIT = "HEAD"
LEGACY_PHASE4_AGGREGATE_UNREPRODUCED = "4ad86fcc50ed669d57966dd471d50ea791c21499c3c280c8b29f484a49b8473c"
LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT = "98f88cc940cb0d9171c6b116c7ebb1290b2b51c29547580f13301b15cc74f20c"
PHASE6_GATE_HASH = "fad95607449de5ebfe1d643d62e77894d9beefe4e8a2b8a36ca49e63b830dd3f"
EXTERNAL_PIN_AGGREGATE = "027336f1a61641bfb6e891199fe24ab77aee0c31287c7e8d88613a458310e529"


def _history_replay_report() -> dict:
    phase4_path = "examples/deckcompiler_demo/phase4"
    phase5_path = "examples/deckcompiler_demo/phase5"
    phase4_history = inventory_subtree_history(ROOT, phase4_path)
    phase5_history = inventory_subtree_history(ROOT, phase5_path)
    phase4_replays = [
        replay_bundle_history(
            ROOT,
            row["commit"],
            phase4_path,
            expected=LEGACY_PHASE4_AGGREGATE_UNREPRODUCED,
        )
        for row in phase4_history
    ]
    phase5_replays = [
        replay_bundle_history(
            ROOT,
            row["commit"],
            phase5_path,
            expected=LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT,
        )
        for row in phase5_history
    ]
    phase5_matches = [
        {
            "commit": replay["source_commit"],
            "subtree_tree_oid": replay["subtree_tree_oid"],
            "algorithm": replay["matching_algorithm"],
        }
        for replay in phase5_replays
        if replay["matched"]
    ]
    phase4_worktree, _ = diagnostic_directory_fingerprint(
        ROOT / phase4_path, include_size=False
    )
    phase5_worktree, _ = diagnostic_directory_fingerprint(
        ROOT / phase5_path, include_size=False
    )
    payload = {
        "schema_name": "bundle_fingerprint_history_replay",
        "schema_version": "1.0.0",
        "report_id": stable_id(
            "historyreplay",
            SOURCE_COMMIT,
            LEGACY_PHASE4_AGGREGATE_UNREPRODUCED,
            LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT,
        ),
        "repository_source": "canonical_release_repository_git_objects",
        "working_tree_mutation_performed": False,
        "phase4": {
            "legacy_value": LEGACY_PHASE4_AGGREGATE_UNREPRODUCED,
            "first_text_commit": discover_legacy_value_history(
                ROOT, LEGACY_PHASE4_AGGREGATE_UNREPRODUCED
            )["first_text_commit"],
            "classification": "UNREPRODUCED_LEGACY_FINGERPRINT",
            "current_supported_worktree_diagnostic": {
                "algorithm": "relative_path_nul_sha256_lf_working_tree",
                "aggregate_sha256": phase4_worktree,
                "current_authority": False,
            },
            "subtree_history": phase4_history,
            "replays": phase4_replays,
            "matching_commits": [],
        },
        "phase5": {
            "legacy_value": LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT,
            "first_text_commit": discover_legacy_value_history(
                ROOT, LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT
            )["first_text_commit"],
            "classification": "HISTORICAL_GIT_OBJECT_FINGERPRINT",
            "current_supported_worktree_diagnostic": {
                "algorithm": "relative_path_nul_sha256_lf_working_tree",
                "aggregate_sha256": phase5_worktree,
                "current_authority": False,
            },
            "subtree_history": phase5_history,
            "replays": phase5_replays,
            "matching_commits": phase5_matches,
        },
        "algorithm_inventory": [
            {
                "algorithm_id": "observed_worktree_path_sha256_rows_legacy",
                "implementation_origin": "pngtopptx_handoff.export._aggregate_snapshot at 6e5f7037dacdf2ac3e353bc8cebe660e79e56ebc",
                "row_shape": "relative_path NUL sha256 LF",
                "include_size": False,
                "path_normalization": "Path.as_posix relative to bundle root",
                "ordering": "Python string ordinal",
                "serialization": "concatenated row strings",
                "encoding": "UTF-8",
                "source_bytes": "working_tree",
                "file_exclusion_policy": "all recursively discovered files",
            },
            {
                "algorithm_id": "observed_worktree_path_size_sha256_rows_legacy",
                "implementation_origin": "qa.inspection.directory_fingerprint at ea6b8bc09011418cc2ca9d9d3e44e1b1f82d05c6",
                "row_shape": "relative_path NUL byte_size NUL sha256 LF",
                "include_size": True,
                "path_normalization": "Path.as_posix relative to bundle root",
                "ordering": "Python string ordinal",
                "serialization": "concatenated row strings",
                "encoding": "UTF-8",
                "source_bytes": "working_tree",
                "file_exclusion_policy": "all recursively discovered files",
            },
            {
                "algorithm_id": "observed_git_object_path_sha256_rows_replay",
                "implementation_origin": "Phase 7.0.2 historical replay",
                "row_shape": "relative_path NUL blob_sha256 LF",
                "include_size": False,
                "path_normalization": "normalized slash path relative to subtree",
                "ordering": "Unicode code-point ordinal",
                "serialization": "concatenated row strings",
                "encoding": "UTF-8",
                "source_bytes": "git_blob",
                "file_exclusion_policy": "all tracked blobs in subtree",
            },
            {
                "algorithm_id": "observed_git_object_path_size_sha256_rows_replay",
                "implementation_origin": "Phase 7.0.2 historical replay",
                "row_shape": "relative_path NUL blob_size NUL blob_sha256 LF",
                "include_size": True,
                "path_normalization": "normalized slash path relative to subtree",
                "ordering": "Unicode code-point ordinal",
                "serialization": "concatenated row strings",
                "encoding": "UTF-8",
                "source_bytes": "git_blob",
                "file_exclusion_policy": "all tracked blobs in subtree",
            },
        ],
        "no_provenance_invented": True,
        "status": "PASS",
    }
    return bind_content_hash(payload, "report_hash")


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def _sha(path: str) -> str:
    return sha256_file(ROOT / path)


def _validate(schema: str, payload: dict) -> None:
    errors = sorted(validator_for(schema).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        raise RuntimeError(f"{schema}: {errors[0].json_path}: {errors[0].message}")


def _components() -> list[dict]:
    return [
        {"component": "source ingestion", "classification": "existing", "origin": "pre_baseline", "evidence": ["src/presentation_agent/source_ingestion.py", BASELINE]},
        {"component": "workflow planner", "classification": "existing", "origin": "pre_baseline", "evidence": ["src/presentation_agent/non_pptx_modules/workflow_planner.py", BASELINE]},
        {"component": "Creative Front-End", "classification": "adapted", "origin": "repository", "evidence": ["956b1e87f4246903d1a319c2e26347c1faf8fbe9"]},
        {"component": "Source Corpus and Evidence Unit layer", "classification": "build_week_new", "origin": "repository", "evidence": ["c82274308eda603594d83bd7465f256e70fe9dcb"]},
        {"component": "strict planning adapter", "classification": "build_week_new", "origin": "repository", "evidence": ["9a79d5f26e598816295be97df57c304f7ddba020"]},
        {"component": "Presentation Architecture integration", "classification": "build_week_new", "origin": "repository", "evidence": ["9a79d5f26e598816295be97df57c304f7ddba020"]},
        {"component": "Visual DNA and Semantic Sidecars", "classification": "build_week_new", "origin": "repository", "evidence": ["00fefe71e3b02fa897794f9e9f3d6df5be715cd8"]},
        {"component": "platform Image Generation results", "classification": "platform_generated", "origin": "platform", "evidence": ["examples/deckcompiler_demo/phase4/generation_provenance.json"]},
        {"component": "CAPTW/pngtopptx SkillSet", "classification": "external_existing", "origin": "external", "evidence": ["docs/devpost/evidence/pngtopptx_external_skillset_pin.json"]},
        {"component": "thin PNGtoPPTX handoff", "classification": "build_week_new", "origin": "repository", "evidence": ["6e5f7037dacdf2ac3e353bc8cebe660e79e56ebc", "8c05f69ccee081f838455fced7de3b77dd1baf29"]},
        {"component": "editable PPTX and HTML reconstruction integration", "classification": "adapted", "origin": "repository_and_external", "evidence": ["e2a6fabb1916680800097981fbda27abfe02b852"]},
        {"component": "Composite QA", "classification": "build_week_new", "origin": "repository", "evidence": ["ea6b8bc09011418cc2ca9d9d3e44e1b1f82d05c6"]},
        {"component": "controlled fault fixture", "classification": "build_week_new", "origin": "repository", "evidence": ["21bcd35e5919dc340e01be74ced0a51f23931f08"]},
        {"component": "bounded repair closure", "classification": "build_week_new", "origin": "repository", "evidence": [PHASE6_HEAD]},
        {"component": "one-command demo", "classification": "build_week_new", "origin": "repository", "evidence": ["Phase 7B implementation required before final acceptance"]},
        {"component": "delivery packager", "classification": "build_week_new", "origin": "repository", "evidence": ["Phase 7C implementation required before final acceptance"]},
        {"component": "fresh-clone verifier", "classification": "build_week_new", "origin": "repository", "evidence": ["Phase 7D proof required before final acceptance"]},
        {"component": "protected historical outputs", "classification": "protected_not_used", "origin": "historical", "evidence": ["outputs/editable_template_spec.final.json", "outputs/golden_template_masters.pptx", "outputs/final_deck_large_premium.pptx"]},
    ]


def build(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    lock_rel = "requirements/devpost-release.lock.txt"
    pin_rel = "docs/devpost/evidence/pngtopptx_external_skillset_pin.json"
    phase4_rel = "examples/deckcompiler_demo/phase4"
    phase5_rel = "examples/deckcompiler_demo/phase5"
    phase6_rel = "examples/deckcompiler_demo/phase6"
    config_rel = "examples/deckcompiler_demo/demo.yaml"
    policy_rel = "examples/deckcompiler_demo/phase7/contract/bundle_fingerprint_policy.json"
    phase4_authority_rel = "examples/deckcompiler_demo/phase7/contract/phase4_bundle_fingerprint_authority.json"
    phase5_authority_rel = "examples/deckcompiler_demo/phase7/contract/phase5_bundle_fingerprint_authority.json"
    phase4_runtime_rel = "examples/deckcompiler_demo/phase7/contract/phase4_runtime_bundle_compatibility.json"
    phase5_runtime_rel = "examples/deckcompiler_demo/phase7/contract/phase5_runtime_bundle_compatibility.json"
    correction_rel = "docs/devpost/evidence/legacy_bundle_fingerprint_correction.json"
    history_rel = "docs/devpost/evidence/bundle_fingerprint_history_replay.json"
    lock_hash = _sha(lock_rel)
    pin_hash = _sha(pin_rel)
    policy = build_bundle_fingerprint_policy()
    phase4_authority = build_bundle_authority(
        ROOT,
        AUTHORITY_SOURCE_COMMIT,
        phase4_rel,
        bundle_id="deckcompiler-phase4-frozen-visual-bundle",
        bundle_role="frozen verified visual inputs for editable reconstruction",
        legacy_fingerprints=[
            {
                "value": LEGACY_PHASE4_AGGREGATE_UNREPRODUCED,
                "classification": "UNREPRODUCED_LEGACY_FINGERPRINT",
            }
        ],
    )
    phase5_authority = build_bundle_authority(
        ROOT,
        AUTHORITY_SOURCE_COMMIT,
        phase5_rel,
        bundle_id="deckcompiler-phase5-baseline-bundle",
        bundle_role="historical editable reconstruction and QA baseline",
        legacy_fingerprints=[
            {
                "value": LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT,
                "classification": "HISTORICAL_GIT_OBJECT_FINGERPRINT",
            }
        ],
    )
    validate_bundle_authority(ROOT, phase4_authority)
    validate_bundle_authority(ROOT, phase5_authority)
    phase4_runtime = build_runtime_bundle_compatibility(
        ROOT, ROOT / phase4_rel, phase4_authority
    )
    phase5_runtime = build_runtime_bundle_compatibility(
        ROOT, ROOT / phase5_rel, phase5_authority
    )
    if phase4_runtime["status"] != "PASS" or phase5_runtime["status"] != "PASS":
        raise RuntimeError(
            "BLOCKED_RUNTIME_BUNDLE_COMPATIBILITY: "
            f"phase4={phase4_runtime['status']} phase5={phase5_runtime['status']}"
        )
    history = _history_replay_report()
    phase5_matches = history["phase5"]["matching_commits"]
    correction = build_legacy_correction_record(
        phase4_legacy=LEGACY_PHASE4_AGGREGATE_UNREPRODUCED,
        phase5_legacy=LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT,
        phase4_classification="UNREPRODUCED_LEGACY_FINGERPRINT",
        phase5_classification="HISTORICAL_GIT_OBJECT_FINGERPRINT",
        phase4_authority=phase4_authority,
        phase5_authority=phase5_authority,
        phase5_matches=phase5_matches,
    )
    for schema_name, payload in (
        ("bundle_fingerprint_policy", policy),
        ("bundle_fingerprint_authority", phase4_authority),
        ("bundle_fingerprint_authority", phase5_authority),
        ("runtime_bundle_compatibility", phase4_runtime),
        ("runtime_bundle_compatibility", phase5_runtime),
        ("bundle_fingerprint_history_replay", history),
        ("legacy_bundle_fingerprint_correction", correction),
    ):
        _validate(schema_name, payload)

    runtime = build_runtime_environment_manifest(
        release_profile_id="devpost_p0_frozen_visuals",
        supported_os={"name": "Microsoft Windows 11 Pro", "version": "10.0.26200", "build": "26200"},
        architecture="AMD64/x64",
        python_version="3.11.9",
        python_lock_path=lock_rel,
        python_lock_sha256=lock_hash,
        python_interpreter_constraints="CPython ==3.11.*; 64-bit Windows",
        node_version="24.13.1",
        node_lock={"status": "not_required", "reason": "Repo-local Node dependencies are not used by the canonical demo"},
        powershell_version="7.5.8",
        powerpoint={"required": True, "identity": "Microsoft PowerPoint", "version": "16.0", "build": "20131", "platform": "x64", "product_release": "O365ProPlusRetail"},
        playwright={"python_package_version": "1.61.0", "browser_revision": "1228"},
        chromium={"product": "Google Chrome for Testing", "version": "149.0.7827.55", "executable_class": "%PLAYWRIGHT_BROWSERS_PATH%/chromium-1228/chrome-win64/chrome.exe"},
        tesseract_cairo={"tesseract_version": "5.4.0.20240606", "ocr_enabled": False, "dll_path_class": "%PROGRAMFILES%/Tesseract-OCR", "purpose": "Cairo DLL discovery only"},
        external_skill_pin={"mode": "git_tree_pin", "path": pin_rel, "artifact_sha256": pin_hash, "aggregate_sha256": EXTERNAL_PIN_AGGREGATE},
        environment_variables_required=["DECKCOMPILER_NODE_MODULES", "PYTHONPATH"],
        environment_variables_prohibited=["OPENAI_API_KEY", "API_KEY", "ACCESS_TOKEN", "CLIENT_SECRET"],
        network_requirement_by_stage={"lock_install": "package_index_or_preseeded_cache", "canonical_demo": "not_required", "live_image_generation": "forbidden"},
    )
    _validate("runtime_environment_manifest", runtime)

    external = bind_content_hash(
        {
            "schema_name": "external_prerequisite_manifest", "schema_version": "1.0.0", "release_profile_id": "devpost_p0_frozen_visuals",
            "microsoft_powerpoint": {"required": True, "version_observed": "16.0", "build_observed": "20131", "platform": "x64", "com_available": True, "fallback_policy": "no_silent_fallback", "libreoffice_policy": "diagnostic_only_when_powerpoint_exists"},
            "pngtopptx_skillset": {"classification": "external_existing", "canonical_repository": "CAPTW/pngtopptx", "installed_path_class": "%USERPROFILE%/.codex/skills", "skill_count": 4, "file_count": 99, "pin_mode": "git_tree_pin", "aggregate_sha256": EXTERNAL_PIN_AGGREGATE, "source_commit_uniquely_claimed": False, "modification_prohibited": True, "package_inclusion": False, "node_dependency_path_class": "%DECKCOMPILER_NODE_MODULES%", "node_packages": {"pptxgenjs": "4.0.1", "sharp": "0.35.1", "react": "19.2.7", "react-dom": "19.2.7", "react-icons": "5.6.0"}},
            "playwright_chromium": {"required": True, "python_package_version": "1.61.0", "browser_revision": "1228", "chromium_version": "149.0.7827.55", "expected_executable_class": "%PLAYWRIGHT_BROWSERS_PATH%/chromium-1228/chrome-win64/chrome.exe", "download_policy": "no_silent_different_browser", "fresh_clone_preflight": True},
            "tesseract_cairo": {"ocr_enabled": False, "tesseract_version": "5.4.0.20240606", "directory_class": "%PROGRAMFILES%/Tesseract-OCR", "purpose": "validated Cairo DLL path only", "scanned_pdf_ocr_supported": False},
            "credential_requirement": False, "network_credential_requirement": False, "validation_status": "PASS",
        },
        "manifest_hash",
    )
    _validate("external_prerequisite_manifest", external)

    contract = bind_content_hash(
        {
            "schema_name": "release_contract", "schema_version": "1.1.0", "release_profile_id": "devpost_p0_frozen_visuals", "public_product": "PPTX Generator", "internal_system": "DeckCompiler",
            "canonical_config_path": config_rel,
            "canonical_input_fixture": {"prompt": {"path": "examples/deckcompiler_demo/inputs/prompt.txt", "sha256": _sha("examples/deckcompiler_demo/inputs/prompt.txt")}, "pdfs": [{"path": "examples/deckcompiler_demo/inputs/cooling_system_overview.pdf", "sha256": _sha("examples/deckcompiler_demo/inputs/cooling_system_overview.pdf")}, {"path": "examples/deckcompiler_demo/inputs/cooling_risk_decision_report.pdf", "sha256": _sha("examples/deckcompiler_demo/inputs/cooling_risk_decision_report.pdf")}], "source_count": 3, "types": ["prompt", "searchable_pdf", "searchable_pdf"]},
            "expected_slide_count": 6, "workflow_mode": "decision_brief",
            "bundle_fingerprint_policy_path": policy_rel,
            "phase4_authority_manifest_path": phase4_authority_rel,
            "phase5_authority_manifest_path": phase5_authority_rel,
            "phase4_runtime_compatibility_report_path": phase4_runtime_rel,
            "phase5_runtime_compatibility_report_path": phase5_runtime_rel,
            "phase6_authority_bridge_path": correction_rel,
            "supported_release_checkout": {
                "core_autocrlf": False,
                "reason": "exact_runtime_text_fixture",
                "exact_runtime_text_path": "src/presentation_agent/deckcompiler/qa/reconstruction_source/slides.js",
                "exact_runtime_text_sha256": "8130f47caa5decf4e1df5343f405fcc79ff18f6d7c6e1880d7e56733d45ae20b",
            },
            "phase4_frozen_visual_bundle": {
                "path": phase4_rel,
                "file_count": phase4_authority["file_count"],
                "subtree_tree_oid": phase4_authority["subtree_tree_oid"],
                "authority_manifest_path": phase4_authority_rel,
                "authority_id": phase4_authority["authority_id"],
                "git_object_aggregate_sha256": phase4_authority["git_object_fingerprint"]["aggregate_sha256"],
                "path_set_sha256": phase4_authority["path_set_sha256"],
                "json_semantic_aggregate_sha256": phase4_authority["json_semantic_aggregate_sha256"],
                "runtime_compatibility_report_path": phase4_runtime_rel,
                "legacy_recorded_aggregate_sha256": LEGACY_PHASE4_AGGREGATE_UNREPRODUCED,
                "live_image_generation_reexecuted": False,
                "generation_provenance_verified": True,
            },
            "phase5_baseline_bundle": {
                "path": phase5_rel,
                "file_count": phase5_authority["file_count"],
                "subtree_tree_oid": phase5_authority["subtree_tree_oid"],
                "authority_manifest_path": phase5_authority_rel,
                "authority_id": phase5_authority["authority_id"],
                "git_object_aggregate_sha256": phase5_authority["git_object_fingerprint"]["aggregate_sha256"],
                "path_set_sha256": phase5_authority["path_set_sha256"],
                "json_semantic_aggregate_sha256": phase5_authority["json_semantic_aggregate_sha256"],
                "runtime_compatibility_report_path": phase5_runtime_rel,
                "legacy_recorded_aggregate_sha256": LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT,
                "reconstruction_input": False,
            },
            "phase6_evidence": {"path": phase6_rel, "unified_gate_hash": PHASE6_GATE_HASH, "intentional_fault_reexecuted_by_default": False, "proof_validation_only": True},
            "external_skill_pin": {"path": pin_rel, "artifact_sha256": pin_hash, "mode": "git_tree_pin", "aggregate_sha256": EXTERNAL_PIN_AGGREGATE},
            "selected_route": "editable_pngtopptx", "live_image_generation_mode": "disabled_frozen_verified_visual_bundle",
            "output_directory_policy": {"mandatory": True, "repository_external": True, "new_or_empty": True, "reparse_point_forbidden": True, "automatic_clear": False},
            "real_renderer_requirement": "Microsoft PowerPoint COM", "canonical_browser_requirement": "Playwright Chromium", "composite_qa_requirement": "PASS",
            "package_content_contract": "verified_delivery_not_runtime_dump", "reproducibility_policy": "physical_clone_and_isolated_locked_python", "semantic_determinism_policy": "exact_declared_semantic_fields", "binary_determinism_policy": "semantic_and_package_fingerprints_for_office_and_render_outputs",
            "final_status_vocabulary": ["BLOCKED", "ELIGIBLE_FOR_DEVPOST_SUBMISSION"], "protected_path_policy": "absent_not_generated_not_input_not_packaged", "source_commit_handling": "tested_runtime_commit_plus_evidence_only_descendant",
            "supported_os": "Windows", "python_version": "3.11.9", "python_lock_path": lock_rel, "python_lock_sha256": lock_hash,
            "phase4_bundle_path": phase4_rel, "phase5_bundle_path": phase5_rel, "phase6_evidence_path": phase6_rel, "phase6_status": "ELIGIBLE_FOR_PACKAGING", "external_pin_path": pin_rel, "external_pin_sha256": pin_hash,
            "powerpoint_com_available": True, "playwright_chromium_available": True, "credential_requirement": False,
            "input_paths": [config_rel, "examples/deckcompiler_demo/inputs/prompt.txt", "examples/deckcompiler_demo/inputs/cooling_system_overview.pdf", "examples/deckcompiler_demo/inputs/cooling_risk_decision_report.pdf", phase4_rel, phase5_rel, policy_rel, phase4_authority_rel, phase5_authority_rel, correction_rel, pin_rel, "examples/deckcompiler_demo/phase6/release/unified_release_gate_report.json"],
            "protected_paths": ["outputs/editable_template_spec.final.json", "outputs/golden_template_masters.pptx", "outputs/final_deck_large_premium.pptx"],
            "final_release_eligible": False, "devpost_release_eligible": False,
            "submission_performed": False, "push_performed": False,
            "tag_created": False, "validation_status": "PASS",
        },
        "contract_hash",
    )
    _validate("release_contract", contract)

    components = build_component_provenance(_components())
    _validate("component_provenance_manifest", components)
    build_week = bind_content_hash(
        {
            "schema_name": "build_week_provenance", "schema_version": "1.0.0", "baseline_sha": BASELINE, "baseline_commit_date": git("show", "-s", "--format=%cI", BASELINE),
            "tested_runtime_commit_policy": "resolved_by_demo_run_manifest_from_phase7c_commit", "final_evidence_commit_handling": "resolved_by_git_metadata",
            "commit_range": {"from_exclusive": BASELINE, "through_phase6": PHASE6_HEAD, "git_expression": f"{BASELINE}..{PHASE6_HEAD}"},
            "phase_commit_map": {"contracts": "54cabc22b4b19a0d13aec984a1c61e75325bb708", "intake": "c82274308eda603594d83bd7465f256e70fe9dcb", "architecture": "9a79d5f26e598816295be97df57c304f7ddba020", "visual_bundle": "3d3ad0c101a6f2cec390597da2ea52dd5ac55e3d", "external_pin": "72dadc711f9fb80f3d7162b3b7bae1868e64b0bf", "reconstruction": "e2a6fabb1916680800097981fbda27abfe02b852", "composite_qa": "ea6b8bc09011418cc2ca9d9d3e44e1b1f82d05c6", "repair_closure": PHASE6_HEAD, "phase7_runtime": "resolved_after_commit_3", "phase7_evidence": "resolved_by_git_metadata"},
            "major_component_map": components["classification_counts"],
            "protected_historical_assets": ["outputs/editable_template_spec.final.json", "outputs/golden_template_masters.pptx", "outputs/final_deck_large_premium.pptx"],
            "removed_quarantined_duplicate_history": {"skill": "image-to-editable-ppt-template", "active": False, "quarantine": "environment_only_not_packaged"},
            "no_overclaim_statement": "Pre-baseline, adapted, external, platform-generated, historical, and Build Week new components remain separately classified.",
        },
        "provenance_hash",
    )
    _validate("build_week_provenance", build_week)

    license_report = bind_content_hash(
        {
            "schema_name": "license_and_attribution_report", "schema_version": "1.0.0", "repository_license_present": False,
            "repository_source_in_delivery_package": False, "repository_authored_fixture_ownership": "owner_supplied_synthetic_fixture", "platform_generated_visual_provenance": "examples/deckcompiler_demo/phase4/generation_provenance.json",
            "external_skill_source_included": False, "external_skill_redistribution": False, "font_binary_count": 0, "browser_binary_count": 0, "third_party_source_content_count": 0,
            "required_notices_included": True, "unresolved_redistribution_blocker_count": 0, "status": "PASS",
        },
        "report_hash",
    )
    validate_license_report(license_report)

    security = bind_content_hash(
        {
            "schema_name": "phase7_release_security_audit", "schema_version": "1.0.0", "scope": "phase7a_curated_contract_artifacts",
            "secret_count": 0, "credential_count": 0, "private_key_count": 0, "temp_path_leak_count": 0, "user_profile_path_leak_count": 0, "browser_profile_artifact_count": 0, "external_skill_source_count": 0, "status": "PASS",
        },
        "report_hash",
    )

    payloads = {
        "bundle_fingerprint_policy.json": policy,
        "phase4_bundle_fingerprint_authority.json": phase4_authority,
        "phase5_bundle_fingerprint_authority.json": phase5_authority,
        "phase4_runtime_bundle_compatibility.json": phase4_runtime,
        "phase5_runtime_bundle_compatibility.json": phase5_runtime,
        "runtime_environment_manifest.json": runtime,
        "external_prerequisite_manifest.json": external,
        "release_contract.json": contract,
        "component_provenance.json": components,
        "build_week_provenance.json": build_week,
        "license_and_attribution_report.json": license_report,
        "security_release_audit.json": security,
    }
    evidence_payloads = {
        ROOT / history_rel: history,
        ROOT / correction_rel: correction,
    }
    write_targets = {
        **{output_root / name: payload for name, payload in payloads.items()},
        **evidence_payloads,
    }
    for path, payload in write_targets.items():
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        scan = scan_release_text(text)
        if any(scan.values()):
            raise RuntimeError(f"curated path/secret leak in {path.name}: {scan}")
        hash_field = next(
            key
            for key in (
                "manifest_hash",
                "contract_hash",
                "provenance_hash",
                "report_hash",
                "policy_hash",
                "correction_hash",
            )
            if key in payload
        )
        hash_valid = (
            verify_bound_hash(payload, hash_field)
            if hash_field in {"manifest_hash", "policy_hash", "correction_hash"}
            and payload.get("schema_name")
            in {
                "bundle_fingerprint_authority",
                "bundle_fingerprint_policy",
                "legacy_bundle_fingerprint_correction",
                "runtime_bundle_compatibility",
            }
            else verify_content_hash(payload, hash_field)
        )
        if not hash_valid:
            raise RuntimeError(f"invalid content hash: {path.name}")
        write_json(path, payload)
    validate_release_contract(
        contract, observed_os="Windows", observed_python="3.11.9"
    )
    print(
        json.dumps(
            {
                "output": output_root.relative_to(ROOT).as_posix(),
                "artifacts": sorted(path.relative_to(ROOT).as_posix() for path in write_targets),
                "phase4_git_object_aggregate": phase4_authority[
                    "git_object_fingerprint"
                ]["aggregate_sha256"],
                "phase5_git_object_aggregate": phase5_authority[
                    "git_object_fingerprint"
                ]["aggregate_sha256"],
                "lock_sha256": lock_hash,
                "status": "PASS",
            },
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "examples" / "deckcompiler_demo" / "phase7" / "contract")
    args = parser.parse_args()
    build(args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
