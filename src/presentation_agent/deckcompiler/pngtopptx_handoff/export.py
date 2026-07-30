"""Validate and export an immutable Phase 4 bundle to the official PNGtoPPTX layout."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from ..manifest_io import read_json, write_json
from ..platform_image_execution.contracts import verify_hash_bound_payload
from ..pngtopptx_pinning import PinningError, validate_external_skillset_pin
from ..schemas import validator_for
from .crop_contract import (
    ASSET_MANIFEST_RELATIVE_PATH,
    CROP_PLAN_RELATIVE_PATH,
    CropContractError,
    build_zero_crop_plan,
    validate_crop_plan,
    validate_project_crop_artifacts,
)


PROTECTED_OUTPUT_NAMES = {
    "editable_template_spec.final.json",
    "golden_template_masters.pptx",
    "final_deck_large_premium.pptx",
}
REQUIRED_SUPPORT_FILES = (
    "input_provenance.json",
    "visual_dna.json",
    "design_system.json",
    "editable_template_spec.json",
    "generation_provenance.json",
    "geometry_fit_report.json",
    "regeneration_history.json",
)
REQUIRED_SKILLS = (
    "slide-editable-deck-orchestrator",
    "slide-text-layer-inpaint",
    "slide-image-dual-render",
    "slide-visual-polish-qa",
)
REQUIRED_NODE_PACKAGES = ("pptxgenjs", "sharp", "react", "react-dom", "react-icons")


class HandoffError(RuntimeError):
    """Fail-closed handoff contract error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class HandoffResult:
    output_dir: Path
    handoff_root: Path
    project_root: Path
    handoff_manifest: Path
    reconstruction_constraints: Path
    expected_output_contract: Path
    invocation_plan: Path
    crop_plan: Path
    asset_manifest: Path


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _aggregate_snapshot(snapshot: dict[str, str]) -> str:
    rows = "".join(f"{name}\0{digest}\n" for name, digest in sorted(snapshot.items()))
    return _sha256_bytes(rows.encode("utf-8"))


def _require_object(path: Path, code: str = "INVALID_PHASE4_BUNDLE") -> dict[str, Any]:
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HandoffError(code, f"cannot read {path}: {exc}") from exc


def _resolve_output(output_dir: Path, repository_root: Path) -> Path:
    output = output_dir.resolve()
    repository = repository_root.resolve()
    if output.name in PROTECTED_OUTPUT_NAMES and output.parent == repository / "outputs":
        raise HandoffError("PROTECTED_OUTPUT_PATH", str(output))
    if output == repository or output.is_relative_to(repository):
        raise HandoffError("OUTPUT_INSIDE_REPOSITORY", str(output))
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise HandoffError("OUTPUT_ROOT_NOT_EMPTY", str(output))
    return output


def _validate_pin(pin_path: Path, external_skill_root: Path) -> dict[str, Any]:
    pin = _require_object(pin_path, "EXTERNAL_PIN_INVALID")
    required = {
        "pin_id",
        "pin_hash",
        "combined_aggregate_sha256",
        "expected_orchestrator",
        "execution_allowed",
        "installation_bundle_verified",
        "external_skill_modified",
        "validation_status",
    }
    if not required.issubset(pin):
        raise HandoffError("EXTERNAL_PIN_INVALID", "required pin fields are absent")
    if (
        pin["expected_orchestrator"] != "slide-editable-deck-orchestrator"
        or pin["execution_allowed"] is not True
        or pin["installation_bundle_verified"] is not True
        or pin["external_skill_modified"] is not False
        or pin["validation_status"] != "PASS"
    ):
        raise HandoffError("EXTERNAL_PIN_INVALID", "pin is not execution eligible")
    if "inventory" in pin:
        try:
            validate_external_skillset_pin(external_skill_root, pin)
        except PinningError as exc:
            raise HandoffError("EXTERNAL_PIN_INVALID", str(exc)) from exc
    return pin


def _verify_phase4_matches_head(phase4: Path, repository_root: Path) -> str:
    if not phase4.is_relative_to(repository_root):
        return "NOT_APPLICABLE_EXTERNAL_FIXTURE"
    relative = phase4.relative_to(repository_root).as_posix()
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", relative],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise HandoffError("PHASE4_HEAD_VERIFICATION_FAILED", completed.stderr.strip())
    if completed.stdout.strip():
        raise HandoffError("PHASE4_HEAD_MISMATCH", completed.stdout.strip())
    return "MATCHES_HEAD"


def _validate_phase4(phase4_bundle: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    phase4 = phase4_bundle.resolve()
    required = [
        phase4 / "visual_target_manifest.json",
        phase4 / "phase4_bundle_acceptance.json",
        *(phase4 / name for name in REQUIRED_SUPPORT_FILES),
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise HandoffError("INVALID_PHASE4_BUNDLE", f"missing required files: {missing}")
    acceptance = _require_object(phase4 / "phase4_bundle_acceptance.json")
    if (
        acceptance.get("phase4_accepted") is not True
        or acceptance.get("bundle_status") != "ELIGIBLE_FOR_PNGTOPPTX_HANDOFF"
        or acceptance.get("final_release_eligible") is not False
    ):
        raise HandoffError("INVALID_PHASE4_BUNDLE", "acceptance is not handoff eligible")

    manifest = _require_object(phase4 / "visual_target_manifest.json")
    targets = manifest.get("targets")
    if not isinstance(targets, list) or len(targets) != 6 or manifest.get("selected_target_count") != 6:
        raise HandoffError("INVALID_PHASE4_BUNDLE", "exactly six selected targets are required")
    slide_ids = [str(target.get("slide_id", "")) for target in targets]
    if len(set(slide_ids)) != 6:
        raise HandoffError("DUPLICATE_SLIDE", "slide ids must be unique")
    order = []
    for slide_id in slide_ids:
        match = re.match(r"^slide-(\d+)(?:-|$)", slide_id)
        if match is None:
            raise HandoffError("SLIDE_ORDER_MISMATCH", f"unrecognized slide id: {slide_id}")
        order.append(int(match.group(1)))
    if order != list(range(1, 7)):
        raise HandoffError("SLIDE_ORDER_MISMATCH", f"expected 1..6, got {order}")

    sidecar_paths = sorted((phase4 / "semantic_sidecars").glob("*.semantic.json"))
    if len(sidecar_paths) != 6:
        raise HandoffError("SIDECAR_COUNT_MISMATCH", f"expected 6, got {len(sidecar_paths)}")

    mappings: list[dict[str, Any]] = []
    for index, (target, sidecar_path) in enumerate(zip(targets, sidecar_paths, strict=True), start=1):
        target_path = phase4 / str(target.get("image_relative_path", ""))
        if not target_path.is_file():
            raise HandoffError("MISSING_TARGET", str(target_path))
        actual_hash = _sha256_file(target_path)
        if actual_hash != target.get("sha256"):
            raise HandoffError("TARGET_HASH_MISMATCH", str(target_path))
        try:
            with Image.open(target_path) as image:
                width, height = image.size
                image_format = image.format
        except OSError as exc:
            raise HandoffError("INVALID_TARGET_IMAGE", str(target_path)) from exc
        if (width, height) != (1664, 936) or width * 9 != height * 16:
            raise HandoffError("INVALID_TARGET_DIMENSIONS", f"{width}x{height}")
        if target.get("dimensions") != {"width": width, "height": height} or image_format != "PNG":
            raise HandoffError("INVALID_TARGET_DIMENSIONS", "manifest/image dimensions or format differ")
        if target.get("validation_status") != "PASS" or target.get("final_surface_role_prohibited") is not True:
            raise HandoffError("FINAL_SURFACE_PERMISSION", str(target_path))

        sidecar = _require_object(sidecar_path)
        if sidecar.get("sidecar_id") != target.get("sidecar_id"):
            raise HandoffError("SIDECAR_ID_MISMATCH", str(sidecar_path))
        if sidecar.get("expected_visual_target_id") != target.get("visual_target_id"):
            raise HandoffError("TARGET_SIDECAR_MISMATCH", str(sidecar_path))
        if sidecar.get("sidecar", {}).get("slide_id") != target.get("slide_id"):
            raise HandoffError("TARGET_SIDECAR_MISMATCH", "slide ids differ")
        metadata = sidecar.get("phase4_metadata", {})
        if metadata.get("full_slide_raster_forbidden") is not True:
            raise HandoffError("FULL_SLIDE_RASTER_PERMISSION", str(sidecar_path))
        if metadata.get("ocr_canonical_text_forbidden") is not True:
            raise HandoffError("OCR_CANONICAL_TEXT_PERMISSION", str(sidecar_path))
        if metadata.get("visual_target_is_not_semantic_source") is not True:
            raise HandoffError("VISUAL_TARGET_SEMANTIC_PERMISSION", str(sidecar_path))
        native = set(metadata.get("native_required_slot_ids", []))
        raster = set(metadata.get("raster_allowed_slot_ids", []))
        if native & raster:
            raise HandoffError("NATIVE_RASTER_OVERLAP", str(sidecar_path))
        mappings.append(
            {
                "sequence": index,
                "slide_id": target["slide_id"],
                "visual_target_id": target["visual_target_id"],
                "sidecar_id": target["sidecar_id"],
                "source_target_path": str(target_path),
                "source_target_relative_path": target_path.relative_to(phase4).as_posix(),
                "source_sidecar_path": str(sidecar_path),
                "source_sidecar_relative_path": sidecar_path.relative_to(phase4).as_posix(),
                "source_target_sha256": actual_hash,
                "source_sidecar_semantic_sha256": _sha256_bytes(_canonical_json_bytes(sidecar)),
                "dimensions": {"width": width, "height": height},
                "sidecar": sidecar,
            }
        )
    return manifest, mappings


def validate_phase4_bundle(phase4_bundle: Path) -> dict[str, Any]:
    """Validate an accepted Phase 4 bundle without creating a Phase 5 handoff."""

    root = phase4_bundle.resolve()
    manifest, mappings = _validate_phase4(root)
    schema_files = (
        ("visual_target_manifest.json", "phase4_visual_target_manifest", "manifest_hash"),
        ("input_provenance.json", "phase4_input_provenance", None),
        ("visual_dna.json", "visual_dna", None),
        ("design_system.json", "phase4_design_system", None),
        ("editable_template_spec.json", "phase4_editable_template_spec", None),
        ("generation_provenance.json", "phase4_generation_provenance", "provenance_hash"),
        ("geometry_fit_report.json", "phase4_geometry_fit_report", "report_hash"),
        ("regeneration_history.json", "phase4_regeneration_history", "history_hash"),
        ("phase4_validation_report.json", "phase4_validation_report", "report_hash"),
        ("phase4_bundle_acceptance.json", "phase4_visual_bundle_acceptance", "acceptance_hash"),
    )
    for filename, schema_name, hash_field in schema_files:
        path = root / filename
        if not path.is_file():
            raise HandoffError("INVALID_PHASE4_BUNDLE", f"missing required file: {path}")
        payload = _require_object(path)
        errors = sorted(
            validator_for(schema_name).iter_errors(payload),
            key=lambda item: list(item.absolute_path),
        )
        if errors:
            location = "/".join(str(item) for item in errors[0].absolute_path) or "$"
            raise HandoffError(
                "INVALID_PHASE4_BUNDLE",
                f"{filename} {location}: {errors[0].message}",
            )
        if hash_field and not verify_hash_bound_payload(payload, hash_field):
            raise HandoffError(
                "INVALID_PHASE4_BUNDLE",
                f"{filename} has an invalid {hash_field}",
            )
    return {
        "valid": True,
        "manifest_id": manifest["manifest_id"],
        "selected_target_count": manifest["selected_target_count"],
        "slide_ids": [mapping["slide_id"] for mapping in mappings],
    }


def _constraints(created_at: str, timezone: str) -> dict[str, Any]:
    return {
        "schema_name": "reconstruction_constraints",
        "schema_version": "1.0.0",
        "created_at": created_at,
        "timezone": timezone,
        "canvas": {"width_px": 1664, "height_px": 936, "aspect_ratio": "16:9"},
        "semantic_authority": "phase4_semantic_sidecar",
        "visual_reference_role": "design_reference_only",
        "full_slide_raster": "forbidden",
        "screenshot_slide": "forbidden",
        "ocr_as_canonical_text": "forbidden",
        "generated_microtext_as_canonical_text": "forbidden",
        "required_editable_categories": [
            "text",
            "tables",
            "charts",
            "cards",
            "captions",
            "replaceable_image_frames",
            "footers",
            "kpis",
        ],
        "native_required_slot_categories": [
            "title",
            "body",
            "table",
            "chart",
            "kpi",
            "card",
            "caption",
            "citation",
            "footer",
        ],
        "native_required_policy": "sidecar_native_required_slot_ids",
        "raster_allowed_policy": "sidecar_raster_allowed_slot_ids_only",
        "bounded_illustration_policy": "declared_raster_allowed_slots_only",
        "crop_source_trace_required": True,
        "source_evidence_immutable": True,
        "slot_based_binding_required": True,
        "official_skill_modification_forbidden": True,
        "fallback_reconstruction_forbidden": True,
        "silent_legacy_fallback_forbidden": True,
        "internal_converter_fallback_forbidden": True,
        "exact_slide_count": 6,
        "exact_slide_order_required": True,
        "repair_wave_limit": 3,
        "raster_coverage_thresholds": {
            "non_cover_union_maximum": 0.35,
            "explicit_cover_hero_union_maximum": 0.60,
            "default_union_maximum": 0.35,
            "single_raster_component_maximum": 0.90,
            "semantic_slot_raster_coverage": 0.0,
        },
        "validation_thresholds": {
            "pptx_package_valid": True,
            "html_slide_count": 6,
            "native_semantic_coverage": 1.0,
            "full_slide_raster_count": 0,
        },
    }


def _expected_outputs(created_at: str, timezone: str) -> dict[str, Any]:
    return {
        "schema_name": "expected_output_contract",
        "schema_version": "1.0.0",
        "created_at": created_at,
        "timezone": timezone,
        "slide_count": 6,
        "outputs": {
            "pptx": "project/out/deckcompiler_phase5.pptx",
            "html": "project/out/deckcompiler_phase5.html",
            "native_manifest": "project/work/native_object_manifest.json",
            "reconstruction_manifest": "project/work/reconstruction_manifest.json",
            "crop_source_trace_manifest": "project/work/crop_source_trace_manifest.json",
            "visual_qa_summary": "project/work/visual_qa_summary.json",
            "repair_history": "project/work/repair_history.json",
            "package_openability_report": "project/work/package_openability_report.json",
            "orchestrator_execution_record": "pngtopptx_execution_record.json",
            "execution_record": "pngtopptx_execution_record.json",
        },
        "pptx_must_be_editable": True,
        "html_required": True,
        "protected_outputs_must_remain_untouched": True,
        "runtime_root_must_be_repository_external": True,
    }


def _invocation_plan(
    *,
    project_root: Path,
    external_skill_root: Path,
    profile_path: Path,
    node_path: Path,
    pin: dict[str, Any],
    deckcompiler_commit: str,
    created_at: str,
    timezone: str,
) -> dict[str, Any]:
    orchestrator = external_skill_root / "slide-editable-deck-orchestrator"
    renderer = external_skill_root / "slide-image-dual-render"
    qa = external_skill_root / "slide-visual-polish-qa"
    entrypoints = {
        "orchestration_plan": str(orchestrator / "scripts" / "plan_deck_workflow.js"),
        "crop_generator": str(renderer / "scripts" / "make_crops.py"),
        "pipeline": str(renderer / "scripts" / "slide_pipeline.js"),
        "final_gate": str(renderer / "scripts" / "final_gate.js"),
        "visual_qa": str(qa / "scripts" / "enforce_visual_qa.js"),
    }
    common = [
        "node",
        entrypoints["pipeline"],
        "--project",
        str(project_root),
        "--target",
        "both",
        "--profile",
        str(profile_path),
        "--node-path",
        str(node_path),
        "--pxw",
        "1664",
        "--pxh",
        "936",
        "--crop-plan",
        str(project_root / CROP_PLAN_RELATIVE_PATH),
    ]
    return {
        "schema_name": "pngtopptx_invocation_plan",
        "schema_version": "1.0.0",
        "created_at": created_at,
        "timezone": timezone,
        "exact_orchestrator_skill": "slide-editable-deck-orchestrator",
        "companion_skills": list(REQUIRED_SKILLS[1:]),
        "official_entrypoints": entrypoints,
        "exact_official_invocation_mode": "official_node_cli",
        "project_root": "project",
        "input_paths": {
            "source_png_pattern": "project/src/slideN.png",
            "semantic_sidecar_pattern": "project/work/slideNN/semantic_sidecar.json",
            "crop_plan": "project/work/crop_plan.json",
            "asset_manifest": "project/assets/manifest.json",
        },
        "output_root": "project/out",
        "profile_path": str(profile_path),
        "node_path": str(node_path),
        "external_skillset_pin": {"pin_id": pin["pin_id"], "pin_hash": pin["pin_hash"]},
        "deckcompiler_commit": deckcompiler_commit,
        "environment_prerequisites": {
            "node_runtime": "required",
            "node_dependency_path": str(node_path),
            "api_credentials": "not_required_by_official_docs",
            "network": "not_required_for_execution_with_preinstalled_dependencies",
        },
        "external_invocation_performed": False,
        "preflight_status": "PLANNED_NOT_EXECUTED",
        "canary_capability": "single_slide_canary",
        "dry_run_capability": True,
        "repair_wave_limit": 3,
        "prohibited_fallback": [
            "repo_local_pngtopptx_skill",
            "internal_converter",
            "legacy_backend",
            "direct_pptx_fallback",
        ],
        "planned_environment": {
            "crop_preparation": {
                "CROP_PLAN": str(project_root / CROP_PLAN_RELATIVE_PATH),
                "SRC_DIR": str(project_root / "src"),
                "DECK_ASSETS": str(project_root / "assets"),
            }
        },
        "planned_commands": {
            "orchestration_plan": [
                "node",
                entrypoints["orchestration_plan"],
                "--project",
                str(project_root),
                "--slides",
                "1,2,3,4,5,6",
                "--quality-level",
                "blocking-zero",
                "--max-iterations",
                "3",
            ],
            "crop_preparation": ["python", entrypoints["crop_generator"]],
            "dry_run": [
                *common,
                "--slides",
                "1,2,3,4,5,6",
                "--quality",
                "reconstruction",
                "--allow-large-batch",
                "--dry-run",
            ],
            "canary": [*common, "--slides", "1", "--quality", "canary"],
            "full_reconstruction": [
                *common,
                "--slides",
                "1,2,3,4,5,6",
                "--quality",
                "reconstruction",
                "--require-qa",
                "--require-reconstruction",
                "--allow-large-batch",
                "--pptx-out",
                str(project_root / "out" / "deckcompiler_phase5.pptx"),
                "--html-out",
                str(project_root / "out" / "deckcompiler_phase5.html"),
            ],
        },
    }


def export_phase4_handoff(
    *,
    phase4_bundle: Path,
    external_skillset_pin: Path,
    output_dir: Path,
    deckcompiler_commit: str,
    external_skill_root: Path,
    profile_path: Path,
    node_path: Path,
    created_at: str,
    timezone: str,
    repository_root: Path,
) -> HandoffResult:
    """Export validated Phase 4 inputs without invoking or copying the external SkillSet."""
    output = _resolve_output(output_dir, repository_root)
    phase4 = phase4_bundle.resolve()
    external = external_skill_root.resolve()
    pin = _validate_pin(external_skillset_pin, external)
    manifest, mappings = _validate_phase4(phase4)
    phase4_head_status = _verify_phase4_matches_head(phase4, repository_root.resolve())
    if not profile_path.resolve().is_file() or not node_path.resolve().is_dir():
        raise HandoffError("PNGTOPPTX_RUNTIME_PREREQUISITE_MISSING", "profile or node path is absent")
    missing_skills = [skill for skill in REQUIRED_SKILLS if not (external / skill / "SKILL.md").is_file()]
    if missing_skills:
        raise HandoffError("PNGTOPPTX_RUNTIME_PREREQUISITE_MISSING", str(missing_skills))
    required_entrypoints = (
        external / "slide-editable-deck-orchestrator" / "scripts" / "plan_deck_workflow.js",
        external / "slide-image-dual-render" / "scripts" / "make_crops.py",
        external / "slide-image-dual-render" / "scripts" / "slide_pipeline.js",
        external / "slide-image-dual-render" / "scripts" / "final_gate.js",
        external / "slide-visual-polish-qa" / "scripts" / "enforce_visual_qa.js",
    )
    missing_entrypoints = [str(path) for path in required_entrypoints if not path.is_file()]
    required_node_modules = tuple(node_path.resolve() / package for package in REQUIRED_NODE_PACKAGES)
    missing_node_modules = [str(path) for path in required_node_modules if not path.is_dir()]
    if missing_entrypoints or missing_node_modules:
        raise HandoffError(
            "PNGTOPPTX_RUNTIME_PREREQUISITE_MISSING",
            f"entrypoints={missing_entrypoints} node_modules={missing_node_modules}",
        )
    if (external / "image-to-editable-ppt-template").exists():
        raise HandoffError("REMOVED_SKILL_PRESENT", "removed Skill exists in the checked installation root")

    phase4_before = _snapshot(phase4)
    external_before = _snapshot(external)
    handoff_root = output / "handoff"
    project_root = handoff_root / "project"
    for directory in (
        project_root / "src",
        project_root / "lib",
        project_root / "assets",
        project_root / "out",
        project_root / "work",
        handoff_root / "visual_targets",
        handoff_root / "semantic_sidecars",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    exported_mappings: list[dict[str, Any]] = []
    for mapping in mappings:
        sequence = mapping["sequence"]
        exported_target = project_root / "src" / f"slide{sequence}.png"
        exported_sidecar = project_root / "work" / f"slide{sequence:02d}" / "semantic_sidecar.json"
        content_target = handoff_root / "visual_targets" / f"{mapping['source_target_sha256']}.png"
        content_sidecar = handoff_root / "semantic_sidecars" / f"{mapping['source_sidecar_semantic_sha256']}.json"
        exported_sidecar.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(mapping["source_target_path"], content_target)
        shutil.copyfile(content_target, exported_target)
        write_json(content_sidecar, mapping["sidecar"])
        shutil.copyfile(content_sidecar, exported_sidecar)
        exported_mappings.append(
            {
                "sequence": sequence,
                "slide_id": mapping["slide_id"],
                "visual_target_id": mapping["visual_target_id"],
                "sidecar_id": mapping["sidecar_id"],
                "role": "slide_visual_target_design_reference",
                "source_target_relative_path": mapping["source_target_relative_path"],
                "content_addressed_target_relative_path": content_target.relative_to(handoff_root).as_posix(),
                "exported_target_relative_path": exported_target.relative_to(handoff_root).as_posix(),
                "source_target_sha256": mapping["source_target_sha256"],
                "exported_target_sha256": _sha256_file(exported_target),
                "target_byte_equal": mapping["source_target_sha256"] == _sha256_file(exported_target),
                "source_sidecar_relative_path": mapping["source_sidecar_relative_path"],
                "content_addressed_sidecar_relative_path": content_sidecar.relative_to(handoff_root).as_posix(),
                "exported_sidecar_relative_path": exported_sidecar.relative_to(handoff_root).as_posix(),
                "sidecar_semantic_sha256": mapping["source_sidecar_semantic_sha256"],
                "exported_sidecar_semantic_sha256": _sha256_bytes(_canonical_json_bytes(read_json(exported_sidecar))),
                "dimensions": mapping["dimensions"],
            }
        )

    phase4_aggregate = _aggregate_snapshot(phase4_before)
    seed = f"{manifest.get('manifest_hash')}:{pin['pin_hash']}:{phase4_aggregate}:{deckcompiler_commit}"
    handoff_id = f"pnghandoff_{_sha256_bytes(seed.encode('utf-8'))[:20]}"
    crop_plan_path = project_root / CROP_PLAN_RELATIVE_PATH
    asset_manifest_path = project_root / ASSET_MANIFEST_RELATIVE_PATH
    write_json(
        crop_plan_path,
        build_zero_crop_plan(
            handoff_id=handoff_id,
            mappings=mappings,
            created_at=created_at,
            timezone=timezone,
        ),
    )
    try:
        validate_crop_plan(crop_plan_path, project_root, expected_slides=exported_mappings)
    except CropContractError as exc:
        raise HandoffError(exc.code, exc.detail) from exc

    constraints_path = handoff_root / "reconstruction_constraints.json"
    expected_path = handoff_root / "expected_output_contract.json"
    invocation_path = handoff_root / "pngtopptx_invocation_plan.json"
    write_json(constraints_path, _constraints(created_at, timezone))
    write_json(expected_path, _expected_outputs(created_at, timezone))
    write_json(
        invocation_path,
        _invocation_plan(
            project_root=project_root,
            external_skill_root=external,
            profile_path=profile_path.resolve(),
            node_path=node_path.resolve(),
            pin=pin,
            deckcompiler_commit=deckcompiler_commit,
            created_at=created_at,
            timezone=timezone,
        ),
    )
    handoff_path = handoff_root / "pngtopptx_handoff_manifest.json"
    write_json(
        handoff_path,
        {
            "schema_name": "pngtopptx_handoff_manifest",
            "schema_version": "1.0.0",
            "handoff_id": handoff_id,
            "created_at": created_at,
            "timezone": timezone,
            "deckcompiler_commit": deckcompiler_commit,
            "phase4_source_commit": _require_object(phase4 / "input_provenance.json").get("source_commit"),
            "phase4_bundle": {
                "path": str(phase4),
                "manifest_id": manifest.get("manifest_id"),
                "manifest_hash": manifest.get("manifest_hash"),
                "aggregate_sha256": phase4_aggregate,
            },
            "external_skillset_pin": {
                "pin_id": pin["pin_id"],
                "pin_hash": pin["pin_hash"],
                "combined_aggregate_sha256": pin["combined_aggregate_sha256"],
            },
            "official_project_root": "project",
            "output_root": ".",
            "slide_count": 6,
            "ordered_slide_ids": [mapping["slide_id"] for mapping in exported_mappings],
            "slides": exported_mappings,
            "artifact_paths": {
                "constraints": constraints_path.relative_to(handoff_root).as_posix(),
                "expected_outputs": expected_path.relative_to(handoff_root).as_posix(),
                "invocation_plan": invocation_path.relative_to(handoff_root).as_posix(),
                "crop_plan": crop_plan_path.relative_to(handoff_root).as_posix(),
                "asset_manifest": asset_manifest_path.relative_to(handoff_root).as_posix(),
            },
            "implementation_provenance": {
                "implementation": "DeckCompiler thin handoff adapter",
                "external_skill_implementation_copied": False,
                "external_skill_implementation_modified": False,
                "fallback_converter_present": False,
            },
            "phase4_head_status": phase4_head_status,
            "source_bundle_unchanged": phase4_before == _snapshot(phase4),
            "external_skillset_unchanged": external_before == _snapshot(external),
            "external_skill_files_copied": False,
            "external_invocation_performed": False,
            "validation_status": "PASS",
        },
    )
    result = HandoffResult(
        output_dir=output,
        handoff_root=handoff_root,
        project_root=project_root,
        handoff_manifest=handoff_path,
        reconstruction_constraints=constraints_path,
        expected_output_contract=expected_path,
        invocation_plan=invocation_path,
        crop_plan=crop_plan_path,
        asset_manifest=asset_manifest_path,
    )
    validate_handoff(handoff_root, require_asset_manifest=False)
    return result


def validate_handoff(
    handoff_root: Path,
    *,
    require_asset_manifest: bool = True,
) -> dict[str, Any]:
    """Validate schema, mapping hashes, and non-execution assertions for a handoff."""
    root = handoff_root.resolve()
    artifacts = {
        "pngtopptx_handoff_manifest": root / "pngtopptx_handoff_manifest.json",
        "reconstruction_constraints": root / "reconstruction_constraints.json",
        "expected_output_contract": root / "expected_output_contract.json",
        "pngtopptx_invocation_plan": root / "pngtopptx_invocation_plan.json",
    }
    loaded: dict[str, dict[str, Any]] = {}
    for schema_name, path in artifacts.items():
        payload = _require_object(path, "INVALID_HANDOFF")
        errors = sorted(validator_for(schema_name).iter_errors(payload), key=lambda item: list(item.path))
        if errors:
            raise HandoffError("INVALID_HANDOFF", f"{schema_name}: {errors[0].message}")
        loaded[schema_name] = payload
    manifest = loaded["pngtopptx_handoff_manifest"]
    for slide in manifest["slides"]:
        target = root / slide["exported_target_relative_path"]
        sidecar = root / slide["exported_sidecar_relative_path"]
        if _sha256_file(target) != slide["exported_target_sha256"]:
            raise HandoffError("INVALID_HANDOFF", f"target hash mismatch: {target}")
        if _sha256_bytes(_canonical_json_bytes(read_json(sidecar))) != slide["exported_sidecar_semantic_sha256"]:
            raise HandoffError("INVALID_HANDOFF", f"sidecar hash mismatch: {sidecar}")
    if manifest["external_invocation_performed"] is not False:
        raise HandoffError("INVALID_HANDOFF", "preflight must not invoke external SkillSet")
    try:
        crop_report = validate_project_crop_artifacts(
            root / "project",
            expected_slides=manifest["slides"],
            require_asset_manifest=require_asset_manifest,
        )
    except CropContractError as exc:
        raise HandoffError(exc.code, exc.detail) from exc
    return {
        "valid": True,
        "handoff_id": manifest["handoff_id"],
        "slide_count": manifest["slide_count"],
        "external_invocation_performed": False,
        "crop_contract_status": crop_report["status"],
        "crop_plan_sha256": crop_report["crop_plan"]["crop_plan_sha256"],
        "asset_manifest_sha256": (
            crop_report["asset_manifest"]["asset_manifest_sha256"]
            if crop_report["asset_manifest"] is not None
            else None
        ),
    }
