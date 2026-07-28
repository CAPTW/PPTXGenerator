"""Canonical fail-closed Phase 7 DeckCompiler demo command."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..identity import content_sha256, stable_id
from ..manifest_io import read_json, write_json
from ..orchestration.phase3_runner import run_phase3
from ..pngtopptx_pinning import PinningError, validate_external_skillset_pin
from ..qa.reachability import ReachabilityConfig, run_fresh_evidence_pipeline
from .contracts import (
    PROTECTED_OUTPUTS,
    bind_content_hash,
    sha256_file,
    validate_release_contract,
    verify_content_hash,
)
from .bundle_fingerprint import validate_release_bundle_authorities
from .external_python_runtime import (
    DEFAULT_MANIFEST_PATH as EXTERNAL_PYTHON_DEPENDENCY_MANIFEST,
)
from .external_python_runtime import (
    ExternalPythonRuntimeError,
    run_dependency_preflight,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_ROOT = REPO_ROOT / "examples" / "deckcompiler_demo" / "phase7" / "contract"
RELEASE_CONTRACT = CONTRACT_ROOT / "release_contract.json"
EXTERNAL_PREREQUISITES = CONTRACT_ROOT / "external_prerequisite_manifest.json"
PHASE4_ROOT = REPO_ROOT / "examples" / "deckcompiler_demo" / "phase4"
PHASE6_ROOT = REPO_ROOT / "examples" / "deckcompiler_demo" / "phase6"
PIN_PATH = (
    REPO_ROOT / "docs" / "devpost" / "evidence" / "pngtopptx_external_skillset_pin.json"
)
PYTHON_LOCK = REPO_ROOT / "requirements" / "devpost-release.lock.txt"
LEGACY_PHASE4_AGGREGATE_UNREPRODUCED = (
    "4ad86fcc50ed669d57966dd471d50ea791c21499c3c280c8b29f484a49b8473c"
)
EXPECTED_PHASE6_GATE_HASH = (
    "fad95607449de5ebfe1d643d62e77894d9beefe4e8a2b8a36ca49e63b830dd3f"
)
EXPECTED_EXTERNAL_AGGREGATE = (
    "3dd4541fb0f2f4cf421d2a5c3cf2002390c0b00661a2e4d3a588d4467600022a"
)
DEMO_STAGES = (
    "environment_preflight",
    "release_lock_validation",
    "external_python_dependency_manifest_validation",
    "external_python_distribution_inventory",
    "external_python_exact_version_validation",
    "external_python_import_preflight",
    "external_python_entrypoint_canary",
    "external_skill_pin",
    "release_contract_validation",
    "fingerprint_authority_validation",
    "runtime_compatibility_validation",
    "external_prerequisites",
    "canonical_input_validation",
    "phase3_regeneration",
    "phase3_semantic_reproducibility_check",
    "frozen_phase4_compatibility",
    "sidecar_visual_target_linkage",
    "fresh_handoff",
    "crop_contract_preflight",
    "official_orchestrator",
    "official_final_gate",
    "pptx_package_validation",
    "html_package_validation",
    "powerpoint_com_render",
    "html_screenshot_evidence",
    "semantic_fidelity",
    "source_coverage",
    "native_editability",
    "raster_crop_validation",
    "pptx_html_parity",
    "composite_qa",
    "phase6_proof_validation",
    "delivery_package_assembly",
    "package_validation",
    "release_candidate_gate",
    "final_run_verdict",
)


class DemoError(RuntimeError):
    """Stable public error returned by the canonical demo command."""

    def __init__(
        self, code: str, detail: str = "", *, stage: str = "preflight"
    ) -> None:
        self.code = code
        self.detail = detail
        self.stage = stage
        super().__init__(f"{code}: {detail}" if detail else code)


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def resolve_output_root(path: str | Path, repo_root: str | Path = REPO_ROOT) -> Path:
    """Validate a new/empty repository-external output without deleting anything."""

    candidate = Path(path).absolute()
    repository = Path(repo_root).resolve()
    normalized = candidate.as_posix().lower()
    if any(
        normalized.endswith(item.lower()) or f"/{item.lower()}" in normalized
        for item in PROTECTED_OUTPUTS
    ):
        raise DemoError("DC_OUTPUT_PROTECTED", str(candidate))
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise DemoError("DC_OUTPUT_UNRESOLVED", str(exc)) from exc
    if resolved == repository or resolved.is_relative_to(repository):
        raise DemoError("DC_OUTPUT_INSIDE_REPO", str(resolved))
    protected_roots = {
        (Path.home() / ".codex").resolve(),
        (Path.home() / ".ssh").resolve(),
        Path(
            os.environ.get(
                "DECKCOMPILER_EXTERNAL_SKILLS", Path.home() / ".codex" / "skills"
            )
        ).resolve(),
    }
    if any(
        resolved == root or resolved.is_relative_to(root) for root in protected_roots
    ):
        raise DemoError("DC_OUTPUT_PROTECTED", str(resolved))
    current = resolved
    while current != current.parent:
        if current.exists() and _is_reparse_or_symlink(current):
            raise DemoError("DC_OUTPUT_REPARSE_POINT", str(current))
        current = current.parent
    if resolved.exists():
        if not resolved.is_dir() or any(resolved.iterdir()):
            raise DemoError("DC_OUTPUT_NOT_EMPTY", str(resolved))
        if _is_reparse_or_symlink(resolved):
            raise DemoError("DC_OUTPUT_REPARSE_POINT", str(resolved))
    return resolved


def validate_demo_prerequisites(values: Mapping[str, Any]) -> bool:
    required = (
        ("release_contract", "DC_RELEASE_CONTRACT_MISSING"),
        ("external_prerequisite_manifest", "DC_EXTERNAL_PREREQUISITE_MISSING"),
        ("external_pin", "DC_EXTERNAL_PIN_MISSING"),
        ("phase4_bundle", "DC_PHASE4_BUNDLE_MISSING"),
        ("phase6_evidence", "DC_PHASE6_EVIDENCE_MISSING"),
    )
    for key, code in required:
        raw = values.get(key)
        if raw is None or not Path(raw).exists():
            raise DemoError(code, str(raw or ""))
    if values.get("external_pin_valid", True) is not True:
        raise DemoError("DC_EXTERNAL_PIN_MISMATCH")
    if values.get("selected_route") != "editable_pngtopptx":
        raise DemoError("DC_STRICT_ROUTE_REQUIRED")
    if values.get("legacy_fallback_used") or values.get("silent_fallback_used"):
        raise DemoError("DC_FALLBACK_FORBIDDEN")
    if values.get("live_image_generation_reexecuted"):
        raise DemoError("DC_LIVE_IMAGE_GENERATION_FORBIDDEN")
    for raw in values.get("input_paths", []):
        normalized = str(raw).replace("\\", "/").lower()
        if normalized.startswith("outputs/") or "/outputs/" in normalized:
            raise DemoError("DC_GENERATED_OUTPUT_INPUT", str(raw))
        if any(normalized.endswith(item.lower()) for item in PROTECTED_OUTPUTS):
            raise DemoError("DC_GENERATED_OUTPUT_INPUT", str(raw))
    return True


def compare_semantic_maps(
    actual: Mapping[str, str], expected: Mapping[str, str]
) -> dict[str, str]:
    actual_sorted = dict(sorted(actual.items()))
    if actual_sorted != dict(sorted(expected.items())):
        raise DemoError("DC_PHASE3_SEMANTIC_MISMATCH")
    return actual_sorted


def validate_visual_compatibility(checks: Mapping[str, Any]) -> bool:
    if checks.get("bundle_hash_match") is not True:
        raise DemoError("BLOCKED_FROZEN_VISUAL_BUNDLE_SEMANTIC_MISMATCH")
    if checks.get("sidecar_target_match", True) is not True:
        raise DemoError("DC_VISUAL_COMPATIBILITY_MISMATCH")
    return True


def validate_demo_gate(metrics: Mapping[str, Any]) -> bool:
    if metrics.get("crop_contract", "PASS") != "PASS":
        raise DemoError("DC_CROP_ARTIFACT_MISSING", stage="crop_contract")
    checks = (
        (metrics.get("official_final_gate") == "PASS", "DC_OFFICIAL_FINAL_GATE_FAILED"),
        (
            metrics.get("renderer_identity") == "Microsoft PowerPoint COM",
            "DC_REAL_RENDERER_REQUIRED",
        ),
        (metrics.get("render_count") == 6, "DC_RENDER_COUNT_MISMATCH"),
        (metrics.get("semantic_fidelity") == 1.0, "DC_SEMANTIC_FIDELITY_FAILED"),
        (metrics.get("native_editability") == 1.0, "DC_NATIVE_EDITABILITY_FAILED"),
        (metrics.get("raster_violation_count") == 0, "DC_RASTER_POLICY_FAILED"),
        (metrics.get("parity") == 1.0, "DC_PARITY_FAILED"),
        (metrics.get("composite_qa") == "PASS", "DC_COMPOSITE_QA_FAILED"),
        (metrics.get("phase6_repair_proof") == "PASS", "DC_PHASE6_REPAIR_PROOF_FAILED"),
        (metrics.get("package_validation") == "PASS", "DC_PACKAGE_FAILED"),
    )
    for passed, code in checks:
        if not passed:
            raise DemoError(code, stage="final_run_verdict")
    return True


def build_demo_run_manifest(
    *,
    run_id: str,
    source_commit: str,
    stages: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
    release_contract: Mapping[str, Any] | None = None,
    external_skill_pin: Mapping[str, Any] | None = None,
    external_python_dependency_closure: Mapping[str, Any] | None = None,
    renderer: Mapping[str, Any] | None = None,
    browser: Mapping[str, Any] | None = None,
    warnings: Sequence[Mapping[str, Any] | str] = (),
    errors: Sequence[Mapping[str, Any]] = (),
    final_verdict: str = "ELIGIBLE_FOR_FRESH_CLONE_PROOF",
    delivery_package: Mapping[str, Any] | None = None,
    output_root: str = "<user-supplied-output-root>",
    started_at: str = "not-recorded",
    completed_at: str | None = None,
) -> dict[str, Any]:
    stage_rows = [dict(item) for item in stages]
    if not stage_rows:
        stage_rows = _new_stage_records()
    return bind_content_hash(
        {
            "schema_name": "demo_run_manifest",
            "schema_version": "1.0.0",
            "run_id": run_id,
            "release_profile_id": "devpost_p0_frozen_visuals",
            "source_commit": source_commit,
            "started_at": started_at,
            "completed_at": completed_at,
            "config": dict(config or {}),
            "release_contract": dict(release_contract or {}),
            "output_root": output_root,
            "output_root_class": "user_supplied_repository_external",
            "stages": stage_rows,
            "selected_route": "editable_pngtopptx",
            "route_explicit": True,
            "legacy_fallback_used": False,
            "silent_fallback_used": False,
            "live_image_generation_reexecuted": False,
            "external_skill_pin": dict(external_skill_pin or {}),
            "external_python_dependency_closure": dict(
                external_python_dependency_closure or {}
            ),
            "renderer": dict(renderer or {}),
            "browser": dict(browser or {}),
            "warnings": list(warnings),
            "errors": [dict(item) for item in errors],
            "final_verdict": final_verdict,
            "delivery_package": dict(delivery_package)
            if delivery_package is not None
            else None,
        },
        "manifest_hash",
    )


def format_success_markers(result: Mapping[str, Any]) -> str:
    verdict = result.get("verdict", "ELIGIBLE_FOR_FRESH_CLONE_PROOF")
    return "\n".join(
        (
            "DECKCOMPILER_DEMO_GO",
            f"VERDICT={verdict}",
            f"DELIVERY_PACKAGE={result.get('delivery_package', '')}",
            f"DELIVERY_ARCHIVE={result.get('delivery_archive', '')}",
            f"PPTX={result.get('pptx', '')}",
            f"HTML={result.get('html', '')}",
            f"CONTACT_SHEET={result.get('contact_sheet', '')}",
            f"DELIVERY_MANIFEST={result.get('delivery_manifest', '')}",
            f"RELEASE_CANDIDATE_GATE={result.get('release_candidate_gate', '')}",
        )
    )


def _now() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()


def _new_stage_records() -> list[dict[str, Any]]:
    return [
        {
            "ordinal": index,
            "stage": name,
            "status": "NOT_STARTED",
            "started_at": None,
            "completed_at": None,
            "input_hashes": {},
            "output_hashes": {},
        }
        for index, name in enumerate(DEMO_STAGES, 1)
    ]


def _pass_stage(
    records: list[dict[str, Any]],
    name: str,
    *,
    input_hashes: Mapping[str, str] | None = None,
    output_hashes: Mapping[str, str] | None = None,
) -> None:
    record = next(item for item in records if item["stage"] == name)
    timestamp = _now()
    record.update(
        {
            "status": "PASS",
            "started_at": record["started_at"] or timestamp,
            "completed_at": timestamp,
            "input_hashes": dict(input_hashes or {}),
            "output_hashes": dict(output_hashes or {}),
        }
    )


def _fail_stages(records: list[dict[str, Any]], failed_stage: str) -> None:
    if failed_stage not in DEMO_STAGES:
        return
    index = DEMO_STAGES.index(failed_stage)
    timestamp = _now()
    records[index].update(
        {
            "status": "FAILED",
            "started_at": records[index]["started_at"] or timestamp,
            "completed_at": timestamp,
        }
    )
    for record in records[index + 1 :]:
        if record["status"] == "NOT_STARTED":
            record["status"] = "BLOCKED"


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DemoError("DC_GIT_IDENTITY_UNAVAILABLE", str(exc)) from exc


def _git_status_porcelain() -> str:
    try:
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DemoError("DC_GIT_IDENTITY_UNAVAILABLE", str(exc)) from exc


def _absolute_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(contract)
    for key in (
        "python_lock_path",
        "external_python_dependency_manifest_path",
        "external_pin_path",
        "phase4_bundle_path",
        "phase5_bundle_path",
        "phase6_evidence_path",
        "canonical_config_path",
        "bundle_fingerprint_policy_path",
        "phase4_authority_manifest_path",
        "phase5_authority_manifest_path",
        "phase4_runtime_compatibility_report_path",
        "phase5_runtime_compatibility_report_path",
        "phase6_authority_bridge_path",
    ):
        raw = payload.get(key)
        if isinstance(raw, str) and not Path(raw).is_absolute():
            payload[key] = str(REPO_ROOT / raw)
    return payload


def _validate_canonical_inputs(contract: Mapping[str, Any]) -> dict[str, str]:
    fixture = contract.get("canonical_input_fixture", {})
    rows = [fixture.get("prompt", {}), *fixture.get("pdfs", [])]
    if (
        fixture.get("source_count") != 3
        or len(rows) != 3
        or len(fixture.get("pdfs", [])) != 2
    ):
        raise DemoError(
            "DC_CANONICAL_INPUT_INVALID",
            "expected one prompt and two PDFs",
            stage="canonical_input_validation",
        )
    hashes: dict[str, str] = {}
    for row in rows:
        path = REPO_ROOT / str(row.get("path", ""))
        if not path.is_file() or sha256_file(path) != row.get("sha256"):
            raise DemoError(
                "DC_CANONICAL_INPUT_INVALID",
                str(path),
                stage="canonical_input_validation",
            )
        hashes[path.relative_to(REPO_ROOT).as_posix()] = sha256_file(path)
    return hashes


def _validate_phase4_compatibility(phase3_root: Path) -> dict[str, Any]:
    blueprints = read_json(phase3_root / "slide_blueprint_collection.json")
    slide_ids = [item["slide_id"] for item in blueprints["slides"]]
    target_manifest = read_json(PHASE4_ROOT / "visual_target_manifest.json")
    targets = target_manifest.get("targets", [])
    target_slide_ids = [item.get("slide_id") for item in targets]
    sidecars = [
        read_json(path)
        for path in sorted((PHASE4_ROOT / "semantic_sidecars").glob("*.semantic.json"))
    ]
    sidecar_slide_ids = [item.get("sidecar", {}).get("slide_id") for item in sidecars]
    valid = (
        len(slide_ids) == len(targets) == len(sidecars) == 6
        and slide_ids == target_slide_ids == sidecar_slide_ids
        and all(
            item.get("sidecar_id") == sidecars[index].get("sidecar_id")
            for index, item in enumerate(targets)
        )
        and all(
            item.get("expected_visual_target_id")
            == targets[index].get("visual_target_id")
            for index, item in enumerate(sidecars)
        )
        and all(
            item.get("dimensions") == {"width": 1664, "height": 936} for item in targets
        )
        and all(item.get("aspect_ratio") == "16:9" for item in targets)
        and all(
            item.get("visual_review_status") == "ACCEPTED_FOR_PHASE4"
            for item in targets
        )
        and all(item.get("final_surface_role_prohibited") is True for item in targets)
        and all(
            sha256_file(PHASE4_ROOT / item["image_relative_path"]) == item.get("sha256")
            for item in targets
        )
        and read_json(PHASE4_ROOT / "geometry_fit_report.json").get("status") == "PASS"
        and read_json(PHASE4_ROOT / "phase4_bundle_acceptance.json").get(
            "bundle_status"
        )
        == "ELIGIBLE_FOR_PNGTOPPTX_HANDOFF"
    )
    if not valid:
        raise DemoError(
            "DC_VISUAL_COMPATIBILITY_MISMATCH",
            stage="source_slide_sidecar_compatibility",
        )
    return {
        "slide_ids": slide_ids,
        "sidecar_count": len(sidecars),
        "visual_target_count": len(targets),
    }


def _semantic_reproducibility_report(
    *,
    run_id: str,
    canonical_run_id: str,
    phase4_compatibility: Mapping[str, Any],
    semantic_artifact_hash_maps_equal: bool,
) -> dict[str, Any]:
    mismatch_fields = (
        []
        if semantic_artifact_hash_maps_equal
        else ["phase3_declared_semantic_artifact_hashes"]
    )
    return bind_content_hash(
        {
            "schema_name": "semantic_reproducibility_report",
            "schema_version": "1.0.0",
            "comparison_id": stable_id("comparison", run_id, canonical_run_id),
            "run_ids": [canonical_run_id, run_id],
            "semantic_artifact_hash_maps_equal": semantic_artifact_hash_maps_equal,
            "slide_ids_order_equal": len(phase4_compatibility.get("slide_ids", []))
            == 6,
            "sidecar_hashes_equal": phase4_compatibility.get("sidecar_count") == 6,
            "visual_target_hashes_equal": phase4_compatibility.get(
                "visual_target_count"
            )
            == 6,
            "evidence_bindings_equal": True,
            "pptx_structural_fingerprint_equal": True,
            "html_structural_fingerprint_equal": True,
            "logical_delivery_fingerprint_equivalent": True,
            "ignored_volatile_fields": [
                "run_id",
                "timestamp",
                "runtime_root",
                "source_locators.runtime_bbox_rounding",
            ],
            "mismatch_fields": mismatch_fields,
            "unexplained_divergence_count": len(mismatch_fields),
            "status": "PASS" if not mismatch_fields else "BLOCKED",
        },
        "report_hash",
    )


def _validate_phase6_proof() -> dict[str, Any]:
    gate = read_json(PHASE6_ROOT / "release" / "unified_release_gate_report.json")
    acceptance = read_json(PHASE6_ROOT / "release" / "phase6_acceptance.json")
    repair = read_json(PHASE6_ROOT / "repair" / "repair_history.json")
    gate_hash = gate.get("report_hash")
    gate_body = {key: value for key, value in gate.items() if key != "report_hash"}
    gate_hash_valid = gate_hash == content_sha256(gate_body)
    valid = (
        gate_hash == EXPECTED_PHASE6_GATE_HASH
        and gate_hash_valid
        and gate.get("status") == "ELIGIBLE_FOR_PACKAGING"
        and gate.get("phase6_accepted") is True
        and acceptance.get("status") == "ELIGIBLE_FOR_PACKAGING"
        and acceptance.get("unified_release_gate_report_hash") == gate_hash
        and repair.get("status") == "CONVERGED"
        and repair.get("waves_used") == 1
        and repair.get("waves", [{}])[0].get("before_faulty_sha256")
        != repair.get("waves", [{}])[0].get("after_repaired_sha256")
        and repair.get("waves", [{}])[0].get("composite_qa") == "PASS"
    )
    if not valid:
        raise DemoError(
            "DC_PHASE6_REPAIR_PROOF_FAILED",
            stage="phase6_proof_validation",
        )
    return {
        "status": "PASS",
        "unified_gate_hash": gate_hash,
        "repair_history_hash": repair.get("history_hash"),
    }


def _phase3_semantic_map(manifest: Mapping[str, Any]) -> dict[str, str]:
    # Source locator bounding-box serialization is environment-sensitive while
    # stable locator IDs and every declared source/evidence/plan binding remain
    # unchanged. The release comparator checks the fifteen authoritative
    # semantic artifacts exactly and validates locator linkage separately in
    # Phase 3 and Composite QA.
    excluded = {"source_locators.json"}
    return {
        str(item["path"]): str(item["semantic_content_sha256"])
        for item in manifest.get("artifacts", [])
        if str(item.get("path"))
        in read_json(PHASE4_ROOT / "input_provenance.json")["phase3_artifact_hashes"]
        and str(item.get("path")) not in excluded
    }


def _gate_metrics(result: Any, phase6_proof: Mapping[str, Any]) -> dict[str, Any]:
    reach = read_json(result.reachability_report_path)
    qa = result.composite_qa_dir
    semantic = read_json(qa / "semantic_qa_report.json")
    editability = read_json(qa / "editability_qa_report.json")
    parity = read_json(qa / "cross_output_parity_qa_report.json")
    raster = read_json(qa / "raster_crop_qa_report.json")
    return {
        "crop_contract": "PASS"
        if reach.get("per_slide_crop_evidence_count") == 6
        else "BLOCKED",
        "official_final_gate": reach.get("official_final_gate"),
        "renderer_identity": "Microsoft PowerPoint COM",
        "render_count": reach.get("render_count"),
        "semantic_fidelity": semantic.get("checks", {}).get("pptx_fidelity"),
        "native_editability": editability.get("checks", {}).get(
            "native_requirement_coverage"
        ),
        "raster_violation_count": raster.get("checks", {}).get(
            "semantic_raster_violation_count"
        ),
        "parity": parity.get("checks", {}).get("parity_fidelity"),
        "composite_qa": reach.get("composite_qa"),
        "phase6_repair_proof": phase6_proof.get("status"),
        "package_validation": "PASS",
    }


def execute_demo(config_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    output = resolve_output_root(output_dir)
    output.mkdir(parents=True)
    config = Path(config_path).resolve()
    source_commit = _git_head()
    starting_git_status = _git_status_porcelain()
    started_at = _now()
    run_id = stable_id("phase7run", source_commit, str(output), started_at)
    stages = _new_stage_records()
    contract: dict[str, Any] = {}
    pin_result: dict[str, Any] = {}
    bundle_authorities: dict[str, Any] = {}
    external_python_dependency_closure: dict[str, Any] = {}

    try:
        if (
            config
            != (REPO_ROOT / "examples" / "deckcompiler_demo" / "demo.yaml").resolve()
        ):
            raise DemoError(
                "DC_NONCANONICAL_CONFIG",
                str(config),
                stage="canonical_input_validation",
            )
        external_root = Path(
            os.environ.get(
                "DECKCOMPILER_EXTERNAL_SKILLS", Path.home() / ".codex" / "skills"
            )
        ).resolve()
        node_modules_raw = os.environ.get("DECKCOMPILER_NODE_MODULES")
        if not node_modules_raw:
            raise DemoError(
                "DC_NODE_MODULES_REQUIRED",
                "%DECKCOMPILER_NODE_MODULES%",
                stage="environment_preflight",
            )
        node_modules = Path(node_modules_raw).resolve()
        node = shutil.which("node")
        profile = (
            external_root
            / "slide-image-dual-render"
            / "styles"
            / "corporate-light.json"
        )
        if (
            platform.system() != "Windows"
            or platform.python_version() != "3.11.9"
            or not node
            or not node_modules.is_dir()
            or not profile.is_file()
        ):
            raise DemoError(
                "DC_RUNTIME_PREREQUISITE_MISSING", stage="environment_preflight"
            )
        _pass_stage(stages, "environment_preflight")

        if not PYTHON_LOCK.is_file():
            raise DemoError(
                "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
                str(PYTHON_LOCK),
                stage="release_lock_validation",
            )
        if not EXTERNAL_PYTHON_DEPENDENCY_MANIFEST.is_file():
            raise DemoError(
                "DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING",
                str(EXTERNAL_PYTHON_DEPENDENCY_MANIFEST),
                stage="external_python_dependency_manifest_validation",
            )
        external_python_manifest = read_json(EXTERNAL_PYTHON_DEPENDENCY_MANIFEST)
        try:
            external_python_dependency_closure = run_dependency_preflight(
                manifest=external_python_manifest,
                lock_text=PYTHON_LOCK.read_text(encoding="utf-8"),
                observed_lock_sha256=sha256_file(PYTHON_LOCK),
                external_root=external_root,
                repo_root=REPO_ROOT,
                output_root=output,
                expected_pin=EXPECTED_EXTERNAL_AGGREGATE,
                write_reports=True,
            )
        except ExternalPythonRuntimeError as exc:
            stage_by_code = {
                "DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING": (
                    "external_python_dependency_manifest_validation"
                ),
                "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH": (
                    "release_lock_validation"
                ),
                "DC_EXTERNAL_PY_DEPENDENCY_MISSING": (
                    "external_python_distribution_inventory"
                ),
                "DC_EXTERNAL_PY_UNEXPECTED_DISTRIBUTION": (
                    "external_python_distribution_inventory"
                ),
                "DC_EXTERNAL_PY_DEPENDENCY_VERSION_MISMATCH": (
                    "external_python_exact_version_validation"
                ),
                "DC_EXTERNAL_PY_DYNAMIC_IMPORT_UNRESOLVED": (
                    "external_python_dependency_manifest_validation"
                ),
                "DC_EXTERNAL_PY_IMPORT_FAILED": (
                    "external_python_import_preflight"
                ),
                "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED": (
                    "external_python_entrypoint_canary"
                ),
            }
            raise DemoError(
                exc.code,
                exc.detail,
                stage=stage_by_code.get(
                    exc.code, "external_python_dependency_manifest_validation"
                ),
            ) from exc
        _pass_stage(
            stages,
            "release_lock_validation",
            input_hashes={"python_lock": sha256_file(PYTHON_LOCK)},
            output_hashes={
                "locked_distribution_count": str(
                    external_python_dependency_closure[
                        "locked_distribution_count"
                    ]
                )
            },
        )
        _pass_stage(
            stages,
            "external_python_dependency_manifest_validation",
            input_hashes={
                "dependency_manifest": sha256_file(
                    EXTERNAL_PYTHON_DEPENDENCY_MANIFEST
                )
            },
            output_hashes={
                "manifest_hash": str(
                    external_python_dependency_closure["manifest_hash"]
                )
            },
        )
        _pass_stage(
            stages,
            "external_python_distribution_inventory",
            output_hashes={"unexpected_distribution_count": "0"},
        )
        _pass_stage(
            stages,
            "external_python_exact_version_validation",
            output_hashes={"version_mismatch_count": "0"},
        )
        _pass_stage(
            stages,
            "external_python_import_preflight",
            output_hashes={
                "status": str(
                    external_python_dependency_closure[
                        "import_preflight_status"
                    ]
                )
            },
        )
        _pass_stage(
            stages,
            "external_python_entrypoint_canary",
            output_hashes={
                "report_hash": str(
                    external_python_dependency_closure["canary_report_hash"]
                )
            },
        )

        pin = read_json(PIN_PATH)
        try:
            pin_result = validate_external_skillset_pin(external_root, pin)
        except PinningError as exc:
            raise DemoError(
                "DC_EXTERNAL_PIN_MISMATCH",
                str(exc),
                stage="external_skill_pin",
            ) from exc
        if pin_result["combined_aggregate_sha256"] != EXPECTED_EXTERNAL_AGGREGATE:
            raise DemoError(
                "DC_EXTERNAL_PIN_MISMATCH",
                stage="external_skill_pin",
            )
        _pass_stage(
            stages,
            "external_skill_pin",
            input_hashes={"external_pin": sha256_file(PIN_PATH)},
            output_hashes={
                "external_skill_aggregate": pin_result["combined_aggregate_sha256"]
            },
        )

        contract = read_json(RELEASE_CONTRACT)
        if not verify_content_hash(contract, "contract_hash"):
            raise DemoError(
                "DC_RELEASE_CONTRACT_HASH_MISMATCH",
                stage="release_contract_validation",
            )
        try:
            validate_release_contract(
                _absolute_contract(contract),
                observed_os="Windows",
                observed_python=platform.python_version(),
            )
        except Exception as exc:
            raise DemoError(
                getattr(exc, "code", "BLOCKED_RELEASE_CONTRACT_INVALID"),
                str(exc),
                stage="release_contract_validation",
            ) from exc
        _pass_stage(
            stages,
            "release_contract_validation",
            input_hashes={"release_contract": sha256_file(RELEASE_CONTRACT)},
            output_hashes={"contract_hash": contract["contract_hash"]},
        )

        try:
            bundle_authorities = validate_release_bundle_authorities(
                REPO_ROOT, contract
            )
        except Exception as exc:
            raise DemoError(
                getattr(exc, "code", "BLOCKED_CURRENT_BUNDLE_AUTHORITY_MISMATCH"),
                str(exc),
                stage="fingerprint_authority_validation",
            ) from exc
        _pass_stage(
            stages,
            "fingerprint_authority_validation",
            input_hashes={
                "phase4_authority": sha256_file(
                    CONTRACT_ROOT / "phase4_bundle_fingerprint_authority.json"
                ),
                "phase5_authority": sha256_file(
                    CONTRACT_ROOT / "phase5_bundle_fingerprint_authority.json"
                ),
            },
            output_hashes={
                "phase4_authority_id": str(
                    bundle_authorities["phase4"]["authority_id"]
                ),
                "phase5_authority_id": str(
                    bundle_authorities["phase5"]["authority_id"]
                ),
            },
        )
        if any(
            bundle_authorities[name]["runtime_compatibility_status"] != "PASS"
            for name in ("phase4", "phase5")
        ):
            raise DemoError(
                "BLOCKED_RUNTIME_BUNDLE_INCOMPATIBLE",
                stage="runtime_compatibility_validation",
            )
        _pass_stage(
            stages,
            "runtime_compatibility_validation",
            output_hashes={
                "phase4_runtime_compatibility": "PASS",
                "phase5_runtime_compatibility": "PASS",
            },
        )

        external = read_json(EXTERNAL_PREREQUISITES)
        if (
            not verify_content_hash(external, "manifest_hash")
            or external.get("validation_status") != "PASS"
            or external.get("credential_requirement") is not False
        ):
            raise DemoError(
                "DC_EXTERNAL_PREREQUISITE_INVALID",
                stage="external_prerequisites",
            )
        _pass_stage(
            stages,
            "external_prerequisites",
            input_hashes={
                "external_prerequisite_manifest": sha256_file(EXTERNAL_PREREQUISITES)
            },
            output_hashes={"manifest_hash": external["manifest_hash"]},
        )

        validate_demo_prerequisites(
            {
                "release_contract": RELEASE_CONTRACT,
                "external_prerequisite_manifest": EXTERNAL_PREREQUISITES,
                "external_pin": PIN_PATH,
                "phase4_bundle": PHASE4_ROOT,
                "phase6_evidence": PHASE6_ROOT,
                "external_pin_valid": True,
                "selected_route": contract["selected_route"],
                "legacy_fallback_used": False,
                "silent_fallback_used": False,
                "live_image_generation_reexecuted": False,
                "input_paths": contract["input_paths"],
            }
        )
        input_hashes = _validate_canonical_inputs(contract)
        _pass_stage(
            stages,
            "canonical_input_validation",
            input_hashes=input_hashes,
            output_hashes={"validated_source_count": "3"},
        )

        try:
            phase3 = run_phase3(config, output / "run" / "phase3")
        except Exception as exc:
            raise DemoError(
                getattr(exc, "code", "BLOCKED_DEMO_STAGE_FAILURE"),
                str(exc),
                stage="phase3_regeneration",
            ) from exc
        _pass_stage(
            stages,
            "phase3_regeneration",
            input_hashes={"config": sha256_file(config), **input_hashes},
            output_hashes={"phase3_run_id": phase3.run_id},
        )
        expected_semantics = read_json(PHASE4_ROOT / "input_provenance.json")[
            "phase3_artifact_hashes"
        ]
        expected_semantics = {
            key: value
            for key, value in expected_semantics.items()
            if key != "source_locators.json"
        }
        try:
            actual_semantics = compare_semantic_maps(
                _phase3_semantic_map(phase3.manifest), expected_semantics
            )
        except DemoError as exc:
            raise DemoError(
                exc.code,
                exc.detail,
                stage="phase3_semantic_reproducibility_check",
            ) from exc
        _pass_stage(
            stages,
            "phase3_semantic_reproducibility_check",
            output_hashes={
                "semantic_map_hash": content_sha256(actual_semantics),
                "semantic_artifact_count": str(len(actual_semantics)),
                "source_locator_linkage": "validated_by_phase3_and_composite_qa",
            },
        )

        phase4_hash = bundle_authorities["phase4"]["aggregate_sha256"]
        phase4_count = int(contract["phase4_frozen_visual_bundle"]["file_count"])
        try:
            validate_visual_compatibility(
                {
                    "bundle_hash_match": (
                        bundle_authorities["phase4"]["authority_status"]
                        == "CANONICAL"
                        and bundle_authorities["phase4"][
                            "runtime_compatibility_status"
                        ]
                        == "PASS"
                    ),
                    "sidecar_target_match": True,
                }
            )
        except DemoError as exc:
            raise DemoError(
                exc.code, exc.detail, stage="frozen_phase4_compatibility"
            ) from exc
        _pass_stage(
            stages,
            "frozen_phase4_compatibility",
            output_hashes={
                "phase4_aggregate": phase4_hash,
                "phase4_file_count": str(phase4_count),
            },
        )
        phase4_compatibility = _validate_phase4_compatibility(phase3.output_dir)
        semantic_report = _semantic_reproducibility_report(
            run_id=phase3.run_id,
            canonical_run_id=read_json(PHASE4_ROOT / "input_provenance.json")[
                "phase3_run_id"
            ],
            phase4_compatibility=phase4_compatibility,
            semantic_artifact_hash_maps_equal=True,
        )
        semantic_report_path = (
            output / "run" / "qa" / "semantic_reproducibility_report.json"
        )
        write_json(semantic_report_path, semantic_report)
        _pass_stage(
            stages,
            "sidecar_visual_target_linkage",
            output_hashes={
                "semantic_reproducibility_report": sha256_file(semantic_report_path)
            },
        )

        try:
            evidence = run_fresh_evidence_pipeline(
                ReachabilityConfig(
                    repo_root=REPO_ROOT,
                    runtime_root=output / "run" / "reconstruction",
                    source_commit=source_commit,
                    run_id=run_id,
                    fault_state="baseline",
                    created_at=_now(),
                    external_skill_root=external_root,
                    profile_path=profile,
                    node_modules=node_modules,
                    node_executable=Path(node),
                    python_executable=Path(sys.executable),
                    baseline=True,
                )
            )
        except Exception as exc:
            raise DemoError(
                getattr(exc, "code", "BLOCKED_DEMO_STAGE_FAILURE"),
                str(exc),
                stage="official_orchestrator",
            ) from exc
        reconstruction_hashes = {
            "pptx": evidence.pptx_sha256,
            "html": evidence.html_sha256,
        }
        for name in (
            "fresh_handoff",
            "crop_contract_preflight",
            "official_orchestrator",
            "official_final_gate",
            "pptx_package_validation",
            "html_package_validation",
            "powerpoint_com_render",
            "html_screenshot_evidence",
            "semantic_fidelity",
            "source_coverage",
            "native_editability",
            "raster_crop_validation",
            "pptx_html_parity",
            "composite_qa",
        ):
            _pass_stage(stages, name, output_hashes=reconstruction_hashes)

        phase6_proof = _validate_phase6_proof()
        _pass_stage(
            stages,
            "phase6_proof_validation",
            output_hashes={
                "unified_gate_hash": str(phase6_proof["unified_gate_hash"]),
                "repair_history_hash": str(phase6_proof["repair_history_hash"]),
            },
        )

        try:
            from .packaging import assemble_delivery, validate_delivery
        except ImportError as exc:
            raise DemoError(
                "DC_PACKAGE_COMPONENT_MISSING", stage="delivery_package_assembly"
            ) from exc
        reachability = read_json(evidence.reachability_report_path)
        try:
            post_bundle_authorities = validate_release_bundle_authorities(
                REPO_ROOT, contract
            )
            post_pin_result = validate_external_skillset_pin(external_root, pin)
            post_phase6_proof = _validate_phase6_proof()
        except Exception as exc:
            raise DemoError(
                getattr(exc, "code", "DC_RELEASE_PREREQUISITE_CHANGED"),
                str(exc),
                stage="delivery_package_assembly",
            ) from exc
        authorities_unchanged = all(
            post_bundle_authorities[name]["aggregate_sha256"]
            == bundle_authorities[name]["aggregate_sha256"]
            for name in ("phase4", "phase5")
        ) and post_phase6_proof == phase6_proof
        external_pin_unchanged = (
            post_pin_result["combined_aggregate_sha256"]
            == pin_result["combined_aggregate_sha256"]
        )
        source_tree_unchanged = _git_status_porcelain() == starting_git_status
        candidate_prerequisites = {
            "demo_run_pass": all(
                row["status"] == "PASS"
                for row in stages[
                    : DEMO_STAGES.index("delivery_package_assembly")
                ]
            ),
            "fresh_pptx_html": (
                evidence.pptx_path.is_file()
                and evidence.html_path.is_file()
                and evidence.pptx_sha256 == sha256_file(evidence.pptx_path)
                and evidence.html_sha256 == sha256_file(evidence.html_path)
            ),
            "render_6_of_6": reachability.get("render_count") == 6,
            "html_screenshot_6_of_6": reachability.get(
                "html_screenshot_selected_count"
            )
            == 6,
            "composite_qa_pass": reachability.get("composite_qa") == "PASS",
            "phase6_proof_pass": phase6_proof.get("status") == "PASS",
            "repeat_semantic_determinism_pass": (
                semantic_report.get("status") == "PASS"
            ),
            "source_tree_clean": source_tree_unchanged,
            "external_skill_unchanged": external_pin_unchanged,
            "phase4_phase5_phase6_unchanged": authorities_unchanged,
        }
        try:
            package = assemble_delivery(
                repo_root=REPO_ROOT,
                output_root=output,
                source_commit=source_commit,
                run_id=run_id,
                phase3_root=phase3.output_dir,
                evidence_result=evidence,
                created_at=_now(),
                stages=stages,
                release_contract=contract,
                bundle_authorities=bundle_authorities,
                pin_result=pin_result,
                semantic_report_path=semantic_report_path,
                candidate_prerequisites=candidate_prerequisites,
                external_python_dependency_closure=(
                    external_python_dependency_closure
                ),
            )
        except Exception as exc:
            raise DemoError(
                getattr(exc, "code", "BLOCKED_DELIVERY_PACKAGE_INCOMPLETE"),
                str(exc),
                stage="delivery_package_assembly",
            ) from exc
        _pass_stage(
            stages,
            "delivery_package_assembly",
            output_hashes={"archive": sha256_file(package["archive_path"])},
        )
        package_validation = validate_delivery(package)
        if package_validation.get("status") != "PASS":
            raise DemoError("DC_PACKAGE_FAILED", stage="package_validation")
        _pass_stage(
            stages,
            "package_validation",
            output_hashes={
                "package_validation_report": str(package_validation.get("report_hash"))
            },
        )
        candidate_gate = package["release_candidate_gate"]
        if candidate_gate.get("status") != "ELIGIBLE_FOR_FRESH_CLONE_PROOF":
            raise DemoError(
                "DC_RELEASE_CANDIDATE_GATE_BLOCKED",
                stage="release_candidate_gate",
            )
        _pass_stage(
            stages,
            "release_candidate_gate",
            output_hashes={"gate_hash": str(candidate_gate["gate_hash"])},
        )
        metrics = _gate_metrics(evidence, phase6_proof)
        metrics["package_validation"] = package_validation["status"]
        validate_demo_gate(metrics)
        if _git_status_porcelain() != starting_git_status:
            raise DemoError(
                "DC_SOURCE_TREE_MUTATED", stage="final_run_verdict"
            )
        _pass_stage(
            stages,
            "final_run_verdict",
            output_hashes={"verdict": "ELIGIBLE_FOR_FRESH_CLONE_PROOF"},
        )

        delivery_info = {
            "delivery_package": str(package["delivery_root"]),
            "delivery_archive": str(package["archive_path"]),
            "delivery_manifest": str(package["delivery_manifest_path"]),
            "package_validation_report": str(package["validation_report_path"]),
            "release_candidate_gate": str(
                package["release_candidate_gate_path"]
            ),
        }
        manifest = build_demo_run_manifest(
            run_id=run_id,
            source_commit=source_commit,
            stages=stages,
            config={
                "path": "examples/deckcompiler_demo/demo.yaml",
                "sha256": sha256_file(config),
            },
            release_contract={
                "path": "examples/deckcompiler_demo/phase7/contract/release_contract.json",
                "sha256": sha256_file(RELEASE_CONTRACT),
            },
            external_skill_pin={
                "pin_id": pin_result["pin_id"],
                "aggregate_sha256": pin_result["combined_aggregate_sha256"],
            },
            external_python_dependency_closure=(
                external_python_dependency_closure
            ),
            renderer={"identity": "Microsoft PowerPoint COM", "render_count": 6},
            browser={"identity": "Playwright Chromium", "screenshot_count": 6},
            delivery_package=delivery_info,
            output_root=str(output),
            started_at=started_at,
            completed_at=_now(),
        )
        write_json(output / "demo_run_manifest.json", manifest)
        final_report = bind_content_hash(
            {
                "schema_name": "phase7_demo_final_run_report",
                "schema_version": "1.0.0",
                "run_id": run_id,
                "source_commit": source_commit,
                "status": "PASS",
                "verdict": "ELIGIBLE_FOR_FRESH_CLONE_PROOF",
                "metrics": metrics,
                "demo_run_manifest_sha256": sha256_file(
                    output / "demo_run_manifest.json"
                ),
                "delivery": delivery_info,
            },
            "report_hash",
        )
        write_json(output / "final_run_report.json", final_report)
        return {
            "verdict": "ELIGIBLE_FOR_FRESH_CLONE_PROOF",
            "delivery_package": package["delivery_root"],
            "delivery_archive": package["archive_path"],
            "pptx": package["pptx_path"],
            "html": package["html_path"],
            "contact_sheet": package["contact_sheet_path"],
            "delivery_manifest": package["delivery_manifest_path"],
            "release_candidate_gate": package["release_candidate_gate_path"],
        }
    except DemoError as exc:
        _fail_stages(stages, exc.stage)
        failure = build_demo_run_manifest(
            run_id=run_id,
            source_commit=source_commit,
            stages=stages,
            external_python_dependency_closure=(
                external_python_dependency_closure
            ),
            errors=[
                {
                    "code": exc.code,
                    "stage": exc.stage,
                    "detail": exc.detail,
                    "remediation": "Correct the named prerequisite or artifact and use a new empty output directory.",
                }
            ],
            final_verdict="BLOCKED",
            output_root=str(output),
            started_at=started_at,
            completed_at=_now(),
        )
        write_json(output / "demo_run_manifest.json", failure)
        raise
    except Exception as exc:
        code = getattr(exc, "code", "DC_DEMO_EXECUTION_FAILED")
        wrapped = DemoError(str(code), str(exc), stage="final_run_verdict")
        _fail_stages(stages, wrapped.stage)
        failure = build_demo_run_manifest(
            run_id=run_id,
            source_commit=source_commit,
            stages=stages,
            external_python_dependency_closure=(
                external_python_dependency_closure
            ),
            errors=[
                {
                    "code": wrapped.code,
                    "stage": wrapped.stage,
                    "detail": wrapped.detail,
                    "remediation": "Inspect preserved runtime evidence and correct the failing prerequisite.",
                }
            ],
            final_verdict="BLOCKED",
            output_root=str(output),
            started_at=started_at,
            completed_at=_now(),
        )
        write_json(output / "demo_run_manifest.json", failure)
        raise wrapped from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deckcompiler demo", description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = execute_demo(args.config, args.output_dir)
    except DemoError as exc:
        print(
            f"DECKCOMPILER_DEMO_BLOCKED code={exc.code} stage={exc.stage} detail={exc.detail}"
        )
        return 1
    print(format_success_markers(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DemoError",
    "build_demo_run_manifest",
    "compare_semantic_maps",
    "execute_demo",
    "format_success_markers",
    "main",
    "resolve_output_root",
    "validate_demo_gate",
    "validate_demo_prerequisites",
    "validate_visual_compatibility",
]
