"""Deterministic, isolated Phase 6B fault injection and detection evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from ..identity import content_sha256, stable_id
from ..manifest_io import read_json, write_json
from ..qa.contracts import (
    TIMEZONE,
    now_iso,
    sha256_file,
    verify_finding_hash,
    verify_report_hash,
    with_report_hash,
)
from ..schemas import validator_for


PROHIBITED_TARGET_SUFFIXES = {".htm", ".html", ".ppt", ".pptx"}
PROHIBITED_INJECTION_TYPES = {"random_corruption", "binary_corruption", "package_corruption"}
ALLOWED_INJECTION_TYPE = "replace_exact_layout_fragment"


class FaultFixtureError(RuntimeError):
    """Fail-closed intentional-fixture contract error."""


@dataclass(frozen=True)
class FaultApplication:
    fixture_id: str
    target_path: str
    target_field: str
    canonical_owner_path: str
    canonical_owner_sha256: str
    expected_detector_owner: str
    before_sha256: str
    after_sha256: str
    changed_paths: tuple[str, ...]
    original_occurrence_count: int
    mutation_count: int
    semantic_content_changed: bool
    evidence_binding_changed: bool
    visual_target_changed: bool
    runtime_isolated: bool
    application_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hash_without(payload: dict[str, Any], field: str) -> str:
    return content_sha256({key: value for key, value in payload.items() if key != field})


def verify_bound_hash(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    return isinstance(value, str) and value == _hash_without(payload, field)


def bind_hash(payload: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(payload)
    result[field] = _hash_without(result, field)
    return result


def _schema_errors(schema_name: str, payload: dict[str, Any]) -> list[str]:
    return [error.message for error in sorted(validator_for(schema_name).iter_errors(payload), key=lambda item: list(item.path))]


def validate_fault_fixture(payload: dict[str, Any]) -> None:
    errors = _schema_errors("fault_injection_spec", payload)
    if errors:
        raise FaultFixtureError("INVALID_FAULT_FIXTURE_SCHEMA: " + "; ".join(errors))
    if not verify_bound_hash(payload, "fixture_hash"):
        raise FaultFixtureError("INVALID_FAULT_FIXTURE_HASH")
    if payload["injection_type"] != ALLOWED_INJECTION_TYPE:
        if payload["injection_type"] in PROHIBITED_INJECTION_TYPES:
            raise FaultFixtureError("PROHIBITED_NONDETERMINISTIC_OR_CORRUPTING_INJECTION")
        raise FaultFixtureError(f"UNSUPPORTED_INJECTION_TYPE: {payload['injection_type']}")
    for field in ("semantic_content_changed", "evidence_binding_changed", "visual_target_changed"):
        if payload[field] is not False:
            raise FaultFixtureError(f"PROTECTED_AUTHORITY_MUTATION_REJECTED: {field}")
    if payload["deterministic_seed"] != "not_applicable":
        raise FaultFixtureError("DETERMINISTIC_FRAGMENT_REPLACEMENT_MUST_NOT_DECLARE_RANDOM_SEED")
    target = PurePosixPath(payload["target_upstream_artifact"]["path"])
    if target.is_absolute() or ".." in target.parts:
        raise FaultFixtureError("TARGET_PATH_MUST_BE_PROJECT_RELATIVE")
    if target.suffix.lower() in PROHIBITED_TARGET_SUFFIXES or target.parts[0].lower() == "out":
        raise FaultFixtureError("DIRECT_FINAL_OUTPUT_MUTATION_REJECTED")
    owner = payload["canonical_repair_owner"]
    owner_path = PurePosixPath(owner["path"])
    if owner_path.is_absolute() or ".." in owner_path.parts:
        raise FaultFixtureError("CANONICAL_OWNER_PATH_MUST_BE_REPOSITORY_RELATIVE")
    if owner_path.as_posix() == target.as_posix():
        raise FaultFixtureError("DERIVATIVE_CANNOT_BE_CANONICAL_REPAIR_OWNER")
    if payload["expected_owner"] != owner_path.as_posix():
        raise FaultFixtureError("EXPECTED_OWNER_MUST_MATCH_CANONICAL_REPAIR_OWNER")
    if owner["derivative_path"] != target.as_posix():
        raise FaultFixtureError("CANONICAL_OWNER_DERIVATIVE_PATH_MISMATCH")
    if owner["field"] != payload["target_field"]:
        raise FaultFixtureError("CANONICAL_OWNER_FIELD_MISMATCH")
    if owner["sha256"] != payload["target_upstream_artifact"]["sha256"]:
        raise FaultFixtureError("CANONICAL_OWNER_DERIVATIVE_HASH_MISMATCH")
    expected_detector_owner = f"handoff/project/{target.as_posix()}"
    if payload["expected_detector_owner"] != expected_detector_owner:
        raise FaultFixtureError("EXPECTED_DETECTOR_OWNER_MISMATCH")
    mutation = payload["mutation"]
    if mutation["original_fragment"] == mutation["injected_fragment"]:
        raise FaultFixtureError("INJECTION_MUST_CHANGE_EXACTLY_ONE_FRAGMENT")


def _project_inventory(project_root: Path) -> dict[str, str]:
    return {
        path.relative_to(project_root).as_posix(): sha256_file(path)
        for path in sorted((item for item in project_root.rglob("*") if item.is_file()), key=lambda item: item.as_posix())
    }


def _resolve_isolated_target(project_root: Path, repository_root: Path, relative: str) -> tuple[Path, bool]:
    project = project_root.resolve()
    repository = repository_root.resolve()
    try:
        project.relative_to(repository)
    except ValueError:
        runtime_isolated = True
    else:
        runtime_isolated = False
    if not runtime_isolated:
        raise FaultFixtureError("FAULT_RUNTIME_MUST_BE_OUTSIDE_REPOSITORY")
    target = (project / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        target.relative_to(project)
    except ValueError as exc:
        raise FaultFixtureError("TARGET_ESCAPES_ISOLATED_PROJECT") from exc
    return target, runtime_isolated


def apply_fault_fixture(
    spec_path: str | Path,
    project_root: str | Path,
    repository_root: str | Path,
    *,
    output_path: str | Path | None = None,
) -> FaultApplication:
    spec = read_json(spec_path)
    validate_fault_fixture(spec)
    project = Path(project_root)
    repository = Path(repository_root).resolve()
    target_ref = spec["target_upstream_artifact"]
    target, runtime_isolated = _resolve_isolated_target(project, repository, target_ref["path"])
    if not target.is_file():
        raise FaultFixtureError(f"TARGET_UPSTREAM_ARTIFACT_MISSING: {target_ref['path']}")

    owner_ref = spec["canonical_repair_owner"]
    canonical_owner = (repository / Path(*PurePosixPath(owner_ref["path"]).parts)).resolve()
    try:
        canonical_owner.relative_to(repository)
    except ValueError as exc:
        raise FaultFixtureError("CANONICAL_OWNER_ESCAPES_REPOSITORY") from exc
    if not canonical_owner.is_file():
        raise FaultFixtureError(f"CANONICAL_REPAIR_OWNER_MISSING: {owner_ref['path']}")
    canonical_owner_hash = sha256_file(canonical_owner)
    if canonical_owner_hash != owner_ref["sha256"]:
        raise FaultFixtureError(f"CANONICAL_REPAIR_OWNER_HASH_MISMATCH: {canonical_owner_hash}")

    before_inventory = _project_inventory(project)
    before_hash = sha256_file(target)
    if before_hash != target_ref["sha256"]:
        raise FaultFixtureError(f"TARGET_UPSTREAM_HASH_MISMATCH: {before_hash}")
    if before_hash != canonical_owner_hash:
        raise FaultFixtureError("MATERIALIZED_DERIVATIVE_DOES_NOT_MATCH_CANONICAL_OWNER")
    source = target.read_text(encoding="utf-8")
    mutation = spec["mutation"]
    original = mutation["original_fragment"]
    injected = mutation["injected_fragment"]
    occurrences = source.count(original)
    if occurrences != 1:
        raise FaultFixtureError(f"ORIGINAL_FRAGMENT_OCCURRENCE_COUNT_MUST_EQUAL_ONE: {occurrences}")
    if injected in source:
        raise FaultFixtureError("INJECTED_FRAGMENT_ALREADY_PRESENT")
    target.write_text(source.replace(original, injected, 1), encoding="utf-8", newline="")

    after_inventory = _project_inventory(project)
    changed_paths = tuple(
        sorted(
            path
            for path in set(before_inventory) | set(after_inventory)
            if before_inventory.get(path) != after_inventory.get(path)
        )
    )
    if changed_paths != (target_ref["path"],):
        raise FaultFixtureError(f"UNCONTROLLED_UPSTREAM_MUTATION: {changed_paths}")
    after_hash = sha256_file(target)
    application_payload = {
        "fixture_id": spec["fixture_id"],
        "target_path": target_ref["path"],
        "target_field": spec["target_field"],
        "canonical_owner_path": owner_ref["path"],
        "canonical_owner_sha256": canonical_owner_hash,
        "expected_detector_owner": spec["expected_detector_owner"],
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "changed_paths": changed_paths,
        "original_occurrence_count": occurrences,
        "mutation_count": 1,
        "semantic_content_changed": False,
        "evidence_binding_changed": False,
        "visual_target_changed": False,
        "runtime_isolated": runtime_isolated,
    }
    application = FaultApplication(**application_payload, application_hash=content_sha256(application_payload))
    if output_path is not None:
        payload = {
            "schema_name": "phase6_fault_application_record",
            "schema_version": "1.0.0",
            **application.to_dict(),
            "changed_paths": list(application.changed_paths),
        }
        schema_errors = _schema_errors("fault_application_record", payload)
        if schema_errors:
            raise FaultFixtureError("INVALID_FAULT_APPLICATION_RECORD: " + "; ".join(schema_errors))
        write_json(output_path, payload)
    return application


def _assert_expected_finding_contract(expected: dict[str, Any]) -> None:
    errors = _schema_errors("expected_finding", expected)
    if errors:
        raise FaultFixtureError("INVALID_EXPECTED_FINDING_SCHEMA: " + "; ".join(errors))
    if not verify_bound_hash(expected, "contract_hash"):
        raise FaultFixtureError("INVALID_EXPECTED_FINDING_HASH")


def _bound_visual_hashes(
    records: list[dict[str, Any]],
    *,
    parent_field: str,
    parent_sha256: Any,
) -> dict[str, str] | None:
    if not isinstance(parent_sha256, str) or len(parent_sha256) != 64 or len(records) != 6:
        return None
    rows: dict[str, str] = {}
    for record in records:
        slide = record.get("slide")
        digest = record.get("sha256")
        if (
            not isinstance(slide, int)
            or slide not in range(1, 7)
            or not isinstance(digest, str)
            or len(digest) != 64
            or record.get(parent_field) != parent_sha256
        ):
            return None
        rows[f"slide-{slide:03d}"] = digest
    return rows if len(rows) == 6 else None


def evaluate_fault_detection(
    composite_report: dict[str, Any],
    expected: dict[str, Any],
    application: dict[str, Any] | FaultApplication,
    *,
    evidence_capsule: dict[str, Any],
    external_reconciliation: dict[str, Any],
    official_final_gate_status: str,
    renderer_status: str,
    canonical_baseline_unchanged: bool,
    created_at: str | None = None,
    deckcompiler_commit: str,
) -> dict[str, Any]:
    _assert_expected_finding_contract(expected)
    if not verify_bound_hash(evidence_capsule, "manifest_hash"):
        raise FaultFixtureError("BLOCKED_FAULT_FIXTURE_UNCONTROLLED: EVIDENCE_CAPSULE_HASH_INVALID")
    if evidence_capsule.get("fault_state") != "faulty":
        raise FaultFixtureError("FRESH_FAULT_CAPSULE_REQUIRED")
    pptx_sha256 = evidence_capsule.get("pptx_sha256")
    html_sha256 = evidence_capsule.get("html_sha256")
    pptx_render_hashes = _bound_visual_hashes(
        evidence_capsule.get("pptx_raster_evidence_records", []),
        parent_field="parent_pptx_sha256",
        parent_sha256=pptx_sha256,
    )
    html_screenshot_hashes = _bound_visual_hashes(
        evidence_capsule.get("html_screenshot_evidence_records", []),
        parent_field="parent_html_sha256",
        parent_sha256=html_sha256,
    )
    capture_manifest = evidence_capsule.get("html_screenshot_capture_manifest_record", {})
    capsule_checks = {
        "capsule_status": evidence_capsule.get("capsule_status") == "COMPOSITE_QA_COMPLETE",
        "missing_artifact_count": evidence_capsule.get("missing_artifact_count") == 0,
        "stale_artifact_count": evidence_capsule.get("stale_artifact_count") == 0,
        "hash_mismatch_count": evidence_capsule.get("hash_mismatch_count") == 0,
        "crop_evidence": len(evidence_capsule.get("per_slide_crop_plan_records", [])) == 6,
        "pptx_raster_evidence": len(evidence_capsule.get("pptx_raster_evidence_records", [])) == 6,
        "html_screenshot_evidence": len(evidence_capsule.get("html_screenshot_evidence_records", [])) == 6,
        "pptx_render_hash_binding": pptx_render_hashes is not None,
        "html_screenshot_hash_binding": html_screenshot_hashes is not None,
        "html_capture_manifest": capture_manifest.get("status") == "PASS"
        and isinstance(capture_manifest.get("manifest_hash"), str)
        and len(capture_manifest["manifest_hash"]) == 64,
        "objective_evidence": evidence_capsule.get("objective_evidence", {}).get("status") == "EVIDENCE_VALID",
        "score_consistency": evidence_capsule.get("reconstruction_score_record", {}).get("status") == "pass",
        "official_final_gate": evidence_capsule.get("official_final_gate_record", {}).get("status") == "PASS",
        "composite_qa_reached": evidence_capsule.get("composite_qa_record", {}).get("status") == "NEEDS_REPAIR",
    }
    if not all(capsule_checks.values()):
        raise FaultFixtureError(f"BLOCKED_FAULT_FIXTURE_UNCONTROLLED: capsule={capsule_checks}")
    if not verify_bound_hash(external_reconciliation, "report_hash"):
        raise FaultFixtureError("BLOCKED_FAULT_FIXTURE_UNCONTROLLED: EXTERNAL_RECONCILIATION_HASH_INVALID")
    reconciliation_checks = {
        "status": external_reconciliation.get("status") == "NEEDS_REPAIR",
        "coverage": external_reconciliation.get("mapped_coverage_ratio") == 1.0,
        "mapped_count": external_reconciliation.get("mapped_nonpass_covered_count")
        == external_reconciliation.get("reported_nonpass_count"),
        "controlled_unresolved_count": external_reconciliation.get("unresolved_external_finding_count") == 1,
    }
    if not all(reconciliation_checks.values()):
        raise FaultFixtureError(
            f"BLOCKED_FAULT_FIXTURE_UNCONTROLLED: EXTERNAL_RECONCILIATION={reconciliation_checks}"
        )
    if not verify_report_hash(composite_report):
        raise FaultFixtureError("FAULTY_COMPOSITE_REPORT_HASH_INVALID")
    if composite_report.get("status") != "NEEDS_REPAIR":
        raise FaultFixtureError("FAULTY_COMPOSITE_MUST_BE_NEEDS_REPAIR")
    composite_checks = composite_report.get("checks", {})
    if (
        composite_report.get("schema_name") != "phase6_composite_qa_report"
        or composite_report.get("implementation_provenance", {}).get("component") != "presentation_agent.deckcompiler.qa"
        or composite_checks.get("composite_dimension_checks") != "NEEDS_REPAIR"
        or composite_checks.get("external_visual_reconciliation") != "NEEDS_REPAIR"
        or composite_checks.get("composite_acceptance") != "NEEDS_REPAIR"
    ):
        raise FaultFixtureError("FAULT_DETECTOR_PROVENANCE_INVALID")
    application_payload = application.to_dict() if isinstance(application, FaultApplication) else application
    findings = composite_report.get("findings", [])
    detected = [item for item in findings if item.get("finding_id") == expected["finding_id"]]
    if len(detected) != 1:
        raise FaultFixtureError("BLOCKED_INTENTIONAL_FAILURE_NOT_DETECTED")
    finding = detected[0]
    if not verify_finding_hash(finding):
        raise FaultFixtureError("DETECTED_FINDING_HASH_INVALID")
    bbox = finding.get("evidence", {}).get("bbox_emu", {})
    slide_width = finding.get("evidence", {}).get("slide_width_emu")
    slide_height = finding.get("evidence", {}).get("slide_height_emu")
    detector_geometry_valid = (
        finding.get("detector") == "DeckCompiler composite QA"
        and str(finding.get("artifact_id") or "").startswith("pptx-slide-001-shape-")
        and isinstance(bbox, dict)
        and isinstance(slide_width, int)
        and isinstance(slide_height, int)
        and any(
            (
                isinstance(bbox.get("left"), int) and bbox["left"] < 0,
                isinstance(bbox.get("top"), int) and bbox["top"] < 0,
                isinstance(bbox.get("right"), int) and bbox["right"] > slide_width,
                isinstance(bbox.get("bottom"), int) and bbox["bottom"] > slide_height,
            )
        )
    )
    if not detector_geometry_valid:
        raise FaultFixtureError("FAULT_DETECTOR_PROVENANCE_INVALID")
    exact_fields = {
        "finding_id": expected["finding_id"],
        "rule_id": expected["rule_id"],
        "gate": expected["gate"],
        "severity": expected["severity"],
        "slide_id": expected["slide_id"],
        "owning_artifact": expected["owning_artifact"],
    }
    mismatches = {key: {"expected": value, "detected": finding.get(key)} for key, value in exact_fields.items() if finding.get(key) != value}
    if mismatches:
        raise FaultFixtureError(f"EXPECTED_FINDING_CONTRACT_MISMATCH: {mismatches}")
    uncontrolled = [
        item["finding_id"]
        for item in findings
        if item.get("severity") == "severe" and not item.get("resolved", False) and item.get("finding_id") != expected["finding_id"]
    ]
    if uncontrolled:
        raise FaultFixtureError(f"BLOCKED_FAULT_FIXTURE_UNCONTROLLED: {uncontrolled}")
    semantic_corruption = [item["finding_id"] for item in findings if item.get("gate") in {"semantic", "source_coverage"} and item.get("severity") in {"error", "severe"}]
    package_corruption = [item["finding_id"] for item in findings if item.get("gate") == "package_render" and item.get("severity") in {"error", "severe"}]
    if semantic_corruption or package_corruption:
        raise FaultFixtureError(
            f"BLOCKED_FAULT_FIXTURE_UNCONTROLLED: semantic={semantic_corruption} package={package_corruption}"
        )
    if application_payload.get("changed_paths") != (expected["injection_surface"],) and application_payload.get("changed_paths") != [expected["injection_surface"]]:
        raise FaultFixtureError("FAULT_APPLICATION_OWNER_MISMATCH")
    if application_payload.get("canonical_owner_path") != expected["canonical_repair_owner"]:
        raise FaultFixtureError("CANONICAL_REPAIR_OWNER_MISMATCH")
    if application_payload.get("expected_detector_owner") != expected["owning_artifact"]:
        raise FaultFixtureError("EXPECTED_DETECTOR_OWNER_MISMATCH")
    if application_payload.get("target_field") != expected["target_field"]:
        raise FaultFixtureError("EXPECTED_TARGET_FIELD_MISMATCH")
    if not canonical_baseline_unchanged:
        raise FaultFixtureError("BLOCKED_CANONICAL_BASELINE_MUTATION")
    if official_final_gate_status != "PASS" or renderer_status != "PASS":
        raise FaultFixtureError("BLOCKED_FAULT_FIXTURE_UNCONTROLLED: DETECTOR_PREREQUISITE_STATUS")

    timestamp = created_at or now_iso()
    payload = {
        "schema_name": "phase6_failure_detection_report",
        "schema_version": "1.0.0",
        "report_id": stable_id("report", "phase6-failure-detection", composite_report.get("report_hash"), expected["contract_hash"]),
        "fixture_id": expected["fixture_id"],
        "composite_report_hash": composite_report["report_hash"],
        "fault_application_hash": application_payload["application_hash"],
        "expected_finding_contract_hash": expected["contract_hash"],
        "evidence_capsule_manifest_hash": evidence_capsule["manifest_hash"],
        "external_reconciliation_report_hash": external_reconciliation["report_hash"],
        "detected_finding": finding,
        "injection_surface": expected["injection_surface"],
        "canonical_repair_owner": expected["canonical_repair_owner"],
        "target_object": expected["object_id"],
        "target_slot": expected["slot_id"],
        "target_field": expected["target_field"],
        "current_faulty_evidence": {
            "pptx_sha256": pptx_sha256,
            "html_sha256": html_sha256,
            "html_screenshot_capture_manifest_hash": capture_manifest["manifest_hash"],
            "pptx_render_sha256_by_slide": pptx_render_hashes,
            "html_screenshot_sha256_by_slide": html_screenshot_hashes,
        },
        "checks": {
            **capsule_checks,
            "external_reconciliation_complete": True,
            "external_source_result_coverage": 1.0,
            "expected_finding_detected": True,
            "expected_finding_exact": True,
            "detector_provenance_valid": True,
            "repair_owner_proven": True,
            "uncontrolled_severe_finding_count": 0,
            "unexpected_semantic_corruption_count": 0,
            "package_corruption_count": 0,
            "canonical_baseline_unchanged": True,
            "official_final_gate_status": official_final_gate_status,
            "real_renderer_status": renderer_status,
            "phase6_can_self_accept": False,
        },
        "status": "NEEDS_REPAIR",
        "phase6_accepted": False,
        "final_release_eligible": False,
        "created_at": timestamp,
        "timezone": TIMEZONE,
        "implementation_provenance": {
            "component": "presentation_agent.deckcompiler.repair.fixture",
            "deckcompiler_commit": deckcompiler_commit,
            "finding_source": "actual DeckCompiler Composite QA report",
            "synthetic_finding_insertion_allowed": False,
        },
    }
    report = with_report_hash(payload)
    errors = _schema_errors("failure_detection_report", report)
    if errors:
        raise FaultFixtureError("INVALID_FAILURE_DETECTION_REPORT: " + "; ".join(errors))
    return report


__all__ = [
    "ALLOWED_INJECTION_TYPE",
    "FaultApplication",
    "FaultFixtureError",
    "apply_fault_fixture",
    "bind_hash",
    "evaluate_fault_detection",
    "validate_fault_fixture",
    "verify_bound_hash",
]
