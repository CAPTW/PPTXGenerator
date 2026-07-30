"""Resumable prompt/PDF entrypoint connecting DeckCompiler Phases 3 through 6."""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from ..errors import DeckCompilerError
from ..identity import content_sha256, stable_id
from ..intake.config import MAX_GENERAL_PDFS
from ..manifest_io import read_json, write_json
from ..pngtopptx_handoff import (
    export_phase4_handoff,
    validate_phase4_bundle,
)
from ..planning.strict_adapter import WORKFLOW_ALIASES as PHASE3_WORKFLOW_ALIASES
from ..provenance import current_source_commit
from ..qa import run_composite_qa
from ..schemas import REPO_ROOT, validator_for
from ..visuals.preparation import prepare_visuals
from .phase3_runner import run_phase3


MANIFEST_NAME = "generate_workflow_manifest.json"
WORKFLOW_SCHEMA = "general_generate_workflow_manifest"
WORKFLOW_OPTIONS = tuple(PHASE3_WORKFLOW_ALIASES)


@dataclass(frozen=True, slots=True)
class GenerateWorkflowResult:
    workflow_id: str
    runtime_root: Path
    manifest_path: Path
    status: str
    exit_code: int
    required_action: dict[str, Any] | None


def start_generate_workflow(
    *,
    output_dir: Path,
    prompt: str | None,
    prompt_file: Path | None,
    pdf_paths: Iterable[Path],
    audience: str,
    purpose: str,
    language: str,
    tone: Iterable[str],
    workflow: str,
) -> GenerateWorkflowResult:
    """Collect arbitrary local inputs and execute deterministic Phase 3 and Phase 4 preparation."""

    root = _prepare_runtime_root(output_dir)
    manifest: dict[str, Any] | None = None
    try:
        prompt_text = _resolve_prompt(prompt, prompt_file)
        pdf_sources = _resolve_pdfs(pdf_paths)
        tone_values = tuple(value.strip() for value in tone if value.strip())
        if not tone_values:
            raise _workflow_error("DC_GENERATE_INPUT_INVALID", "At least one non-empty tone is required.")
        if workflow not in PHASE3_WORKFLOW_ALIASES:
            raise _workflow_error(
                "DC_GENERATE_INPUT_INVALID",
                f"Unsupported workflow alias: {workflow}",
                remediation_hint=f"Choose one of: {', '.join(WORKFLOW_OPTIONS)}.",
            )

        inputs_dir = root / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=False)
        prompt_path = inputs_dir / "prompt.txt"
        _atomic_write_text(prompt_path, prompt_text.strip() + "\n")
        copied_pdfs = _copy_pdf_inputs(pdf_sources, inputs_dir)
        mode = "prompt_with_pdfs" if copied_pdfs else "prompt_only"
        presentation = {
            "slide_count": 6,
            "audience": audience.strip(),
            "purpose": purpose.strip(),
            "language": language.strip(),
            "tone": list(tone_values),
            "workflow": workflow,
        }
        if not all((presentation["audience"], presentation["purpose"], presentation["language"])):
            raise _workflow_error(
                "DC_GENERATE_INPUT_INVALID",
                "Audience, purpose, and language must be non-empty.",
            )
        config_path = inputs_dir / "deckcompiler.yaml"
        config_payload = _config_payload(mode, copied_pdfs, presentation)
        _atomic_write_text(
            config_path,
            yaml.safe_dump(config_payload, allow_unicode=True, sort_keys=False),
        )
        created_at = _now()
        workflow_id = stable_id(
            "generate",
            prompt_text,
            [_sha256_file(path) for path in copied_pdfs],
            presentation,
        )
        input_contract = {
            "mode": mode,
            "prompt": _artifact_reference(root, prompt_path, "user_prompt"),
            "pdfs": [_artifact_reference(root, path, "pdf") for path in copied_pdfs],
            "presentation": presentation,
        }
        manifest = _initial_manifest(root, workflow_id, created_at, input_contract, config_path)
        _write_workflow_manifest(root, manifest)

        phase3 = _stage(manifest, "phase3")
        phase3["status"] = "RUNNING"
        _record(manifest, "phase3_started", "RUNNING")
        _write_workflow_manifest(root, manifest)
        phase3_result = run_phase3(config_path, root / "phase3")
        phase3["status"] = "COMPLETED"
        phase3["required_action"] = None
        phase3["details"] = {
            "run_id": phase3_result.run_id,
            "verdict": phase3_result.validation_report["verdict"],
        }
        phase3["artifacts"] = [
            _artifact_reference(root, root / "phase3", "phase3_bundle", directory=True)
        ]
        _record(manifest, "phase3_completed", "COMPLETED")

        phase4 = _stage(manifest, "phase4")
        phase4["status"] = "RUNNING"
        _record(manifest, "phase4_preparation_started", "RUNNING")
        _write_workflow_manifest(root, manifest)
        phase4_result = prepare_visuals(root / "phase3", root / "phase4_preparation")
        action = {
            "code": "PROVIDE_PHASE4_BUNDLE",
            "message": (
                "Execute the prepared platform image requests, assemble an accepted Phase 4 bundle, "
                "then resume with --phase4-bundle."
            ),
            "prompt_directory": _path_value(root, root / "phase4_preparation" / "preparation" / "prompts"),
            "expected_slide_visual_count": 6,
        }
        phase4["status"] = "AWAITING_EXTERNAL"
        phase4["required_action"] = action
        phase4["details"] = {
            "preparation_status": "COMPLETED",
            "semantic_sidecar_count": len(phase4_result.sidecar_paths),
            "prompt_count": len(phase4_result.prompt_paths),
        }
        phase4["artifacts"] = [
            _artifact_reference(
                root,
                root / "phase4_preparation",
                "phase4_visual_preparation",
                directory=True,
            )
        ]
        manifest["status"] = "AWAITING_PHASE4_VISUALS"
        _record(manifest, "phase4_preparation_completed", "AWAITING_EXTERNAL")
        _sync_artifacts(manifest)
        _write_workflow_manifest(root, manifest)
        return _result(root, manifest, exit_code=2)
    except Exception as exc:
        if manifest is not None:
            _block_manifest(root, manifest, exc)
        raise


def resume_generate_workflow(
    *,
    resume: Path,
    phase4_bundle: Path | None = None,
    external_skillset_pin: Path | None = None,
    external_skill_root: Path | None = None,
    profile: Path | None = None,
    node_path: Path | None = None,
    phase5_bundle: Path | None = None,
    renders_dir: Path | None = None,
    renderer_version: str | None = None,
    external_visual_summary: Path | None = None,
    external_visual_exit_code: int | None = None,
    pptx: Path | None = None,
    html: Path | None = None,
    deckcompiler_commit: str | None = None,
) -> GenerateWorkflowResult:
    """Resume at the next incomplete external boundary and continue through Phase 6."""

    root, manifest = _load_workflow(resume)
    if manifest["status"] == "COMPLETED":
        return _result(root, manifest, exit_code=0)
    try:
        commit = deckcompiler_commit or manifest["source_commit"]
        phase4 = _stage(manifest, "phase4")
        stored_phase4 = _stored_external_path(phase4, "bundle_path")
        resolved_phase4 = phase4_bundle.resolve() if phase4_bundle is not None else stored_phase4
        if phase4["status"] != "COMPLETED":
            if resolved_phase4 is None:
                manifest["status"] = "AWAITING_PHASE4_VISUALS"
                _write_workflow_manifest(root, manifest)
                return _result(root, manifest, exit_code=2)
            validation = validate_phase4_bundle(resolved_phase4)
            _validate_phase4_link(root, manifest, resolved_phase4)
            phase4["status"] = "COMPLETED"
            phase4["required_action"] = None
            phase4["details"] = {
                **phase4["details"],
                "bundle_path": resolved_phase4.as_posix(),
                "manifest_id": validation["manifest_id"],
                "selected_target_count": validation["selected_target_count"],
            }
            phase4["artifacts"].append(
                _artifact_reference(root, resolved_phase4, "phase4_accepted_bundle", directory=True)
            )
            _record(manifest, "phase4_bundle_accepted", "COMPLETED")
            _sync_artifacts(manifest)
            _write_workflow_manifest(root, manifest)

        phase5 = _stage(manifest, "phase5")
        stored_phase5 = _stored_external_path(phase5, "bundle_path")
        resolved_phase5 = phase5_bundle.resolve() if phase5_bundle is not None else stored_phase5
        handoff_arguments = {
            "external_skillset_pin": external_skillset_pin,
            "external_skill_root": external_skill_root,
            "profile": profile,
            "node_path": node_path,
        }
        supplied_handoff = {name for name, value in handoff_arguments.items() if value is not None}
        if supplied_handoff and len(supplied_handoff) != len(handoff_arguments):
            missing = sorted(set(handoff_arguments) - supplied_handoff)
            raise _workflow_error(
                "DC_GENERATE_PHASE5_CONFIGURATION",
                f"Incomplete Phase 5 handoff configuration; missing: {', '.join(missing)}.",
            )

        if phase5["status"] in {"PENDING", "AWAITING_CONFIGURATION"} and resolved_phase5 is None:
            if not supplied_handoff:
                action = {
                    "code": "CONFIGURE_PHASE5_HANDOFF",
                    "message": (
                        "Resume with the external SkillSet pin/root, profile, and Node dependency path "
                        "to export the official editable reconstruction handoff."
                    ),
                    "required_options": [
                        "--external-skillset-pin",
                        "--external-skill-root",
                        "--profile",
                        "--node-path",
                    ],
                }
                phase5["status"] = "AWAITING_CONFIGURATION"
                phase5["required_action"] = action
                manifest["status"] = "AWAITING_PHASE5_CONFIGURATION"
                _record(manifest, "phase5_configuration_required", "AWAITING_CONFIGURATION")
                _write_workflow_manifest(root, manifest)
                return _result(root, manifest, exit_code=2)
            phase5["status"] = "RUNNING"
            _record(manifest, "phase5_handoff_started", "RUNNING")
            _write_workflow_manifest(root, manifest)
            handoff = export_phase4_handoff(
                phase4_bundle=resolved_phase4,
                external_skillset_pin=external_skillset_pin,
                output_dir=root / "phase5_handoff",
                deckcompiler_commit=commit,
                external_skill_root=external_skill_root,
                profile_path=profile,
                node_path=node_path,
                created_at=_now(),
                timezone="Asia/Seoul",
                repository_root=REPO_ROOT,
            )
            handoff_manifest = read_json(handoff.handoff_manifest)
            action = {
                "code": "EXECUTE_PHASE5_RECONSTRUCTION",
                "message": (
                    "Execute the generated PNGtoPPTX invocation plan with the pinned external SkillSet, "
                    "package its outputs as a Phase 5 bundle, then resume with --phase5-bundle."
                ),
                "invocation_plan": _path_value(root, handoff.invocation_plan),
            }
            phase5["status"] = "AWAITING_EXTERNAL"
            phase5["required_action"] = action
            phase5["details"] = {
                "handoff_id": handoff_manifest["handoff_id"],
                "handoff_root": handoff.handoff_root.as_posix(),
            }
            phase5["artifacts"] = [
                _artifact_reference(root, root / "phase5_handoff", "phase5_handoff", directory=True)
            ]
            manifest["status"] = "AWAITING_PHASE5_RECONSTRUCTION"
            _record(manifest, "phase5_handoff_completed", "AWAITING_EXTERNAL")
            _sync_artifacts(manifest)
            _write_workflow_manifest(root, manifest)
            return _result(root, manifest, exit_code=2)

        if resolved_phase5 is None:
            manifest["status"] = (
                "AWAITING_PHASE5_CONFIGURATION"
                if phase5["status"] == "AWAITING_CONFIGURATION"
                else "AWAITING_PHASE5_RECONSTRUCTION"
            )
            _write_workflow_manifest(root, manifest)
            return _result(root, manifest, exit_code=2)

        if phase5["status"] != "COMPLETED":
            _validate_phase5_link(root, phase5, resolved_phase5)
            phase5["status"] = "COMPLETED"
            phase5["required_action"] = None
            phase5["details"] = {
                **phase5["details"],
                "bundle_path": resolved_phase5.as_posix(),
            }
            phase5["artifacts"].append(
                _artifact_reference(root, resolved_phase5, "phase5_reconstruction_bundle", directory=True)
            )
            _record(manifest, "phase5_bundle_accepted", "COMPLETED")
            _sync_artifacts(manifest)
            _write_workflow_manifest(root, manifest)

        phase6 = _stage(manifest, "phase6")
        if external_visual_summary is None or external_visual_exit_code is None:
            action = {
                "code": "CONFIGURE_PHASE6_QA",
                "message": (
                    "Run the official read-only visual QA and resume with --external-visual-summary "
                    "and --external-visual-exit-code. Supply --renders-dir when PowerPoint rendering "
                    "has already been completed."
                ),
                "required_options": [
                    "--external-visual-summary",
                    "--external-visual-exit-code",
                ],
            }
            phase6["status"] = "AWAITING_CONFIGURATION"
            phase6["required_action"] = action
            manifest["status"] = "AWAITING_PHASE6_CONFIGURATION"
            _record(manifest, "phase6_configuration_required", "AWAITING_CONFIGURATION")
            _write_workflow_manifest(root, manifest)
            return _result(root, manifest, exit_code=2)

        phase6["status"] = "RUNNING"
        phase6["required_action"] = None
        _record(manifest, "phase6_composite_qa_started", "RUNNING")
        _write_workflow_manifest(root, manifest)
        qa = run_composite_qa(
            resolved_phase4,
            resolved_phase5,
            root / "phase6",
            deckcompiler_commit=commit,
            renders_dir=renders_dir,
            renderer_version=renderer_version,
            external_visual_summary=external_visual_summary,
            external_visual_exit_code=external_visual_exit_code,
            pptx_path=pptx,
            html_path=html,
            baseline=False,
            active_output_set="phase5_baseline",
            created_at=_now(),
            authority_mode="runtime",
        )
        phase6["status"] = "COMPLETED" if qa.status == "PASS" else "NEEDS_REPAIR"
        phase6["details"] = {
            "run_id": qa.run_id,
            "composite_status": qa.status,
            "renderer_version": qa.renderer_version,
        }
        phase6["artifacts"] = [
            _artifact_reference(root, qa.output_dir, "phase6_composite_qa", directory=True)
        ]
        manifest["status"] = "COMPLETED" if qa.status == "PASS" else "NEEDS_REPAIR"
        _record(manifest, "phase6_composite_qa_completed", qa.status)
        _sync_artifacts(manifest)
        _write_workflow_manifest(root, manifest)
        return _result(root, manifest, exit_code=0 if qa.status == "PASS" else 1)
    except Exception as exc:
        _block_manifest(root, manifest, exc)
        raise


def validate_generate_workflow(path: Path) -> dict[str, Any]:
    manifest_path = path / MANIFEST_NAME if path.is_dir() else path
    payload = read_json(manifest_path)
    issues = _manifest_issues(payload)
    return {
        "valid": not issues,
        "status": payload.get("status"),
        "workflow_id": payload.get("workflow_id"),
        "issues": issues,
    }


def _initial_manifest(
    root: Path,
    workflow_id: str,
    created_at: str,
    input_contract: dict[str, Any],
    config_path: Path,
) -> dict[str, Any]:
    phase3_action = {
        "code": "RUN_PHASE3",
        "message": "Execute deterministic intake, planning, and creative architecture.",
    }
    return {
        "schema_name": WORKFLOW_SCHEMA,
        "schema_version": "1.0.0",
        "workflow_id": workflow_id,
        "entrypoint": "deckcompiler generate",
        "source_commit": current_source_commit(),
        "runtime_root": root.as_posix(),
        "created_at": created_at,
        "updated_at": created_at,
        "status": "RUNNING",
        "input_contract": input_contract,
        "stages": [
            {
                "phase": "phase3",
                "status": "PENDING",
                "artifacts": [_artifact_reference(root, config_path, "phase3_config")],
                "required_action": phase3_action,
                "details": {},
            },
            {
                "phase": "phase4",
                "status": "PENDING",
                "artifacts": [],
                "required_action": None,
                "details": {},
            },
            {
                "phase": "phase5",
                "status": "PENDING",
                "artifacts": [],
                "required_action": None,
                "details": {},
            },
            {
                "phase": "phase6",
                "status": "PENDING",
                "artifacts": [],
                "required_action": None,
                "details": {},
            },
        ],
        "artifacts": [],
        "history": [{"timestamp": created_at, "event": "workflow_created", "status": "RUNNING"}],
        "errors": [],
        "manifest_hash": "0" * 64,
    }


def _config_payload(
    mode: str,
    copied_pdfs: tuple[Path, ...],
    presentation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "product": {"name": "PPTX Generator", "slug": "pptx-generator"},
        "system": {"name": "DeckCompiler", "id": "deckcompiler"},
        "mode": mode,
        "inputs": {
            "prompt": "prompt.txt",
            "pdfs": [path.name for path in copied_pdfs],
        },
        "presentation": presentation,
        "policies": {
            "remote_sources": "forbidden",
            "scanned_pdf_ocr": "unsupported",
            "full_slide_raster": "forbidden",
            "silent_source_omission": "forbidden",
            "invented_citations": "forbidden",
        },
        "phase": {"stop_after": "creative_architecture"},
    }


def _prepare_runtime_root(path: Path) -> Path:
    root = path.resolve()
    repository = REPO_ROOT.resolve()
    if root == repository or root.is_relative_to(repository):
        raise _workflow_error(
            "DC_GENERATE_OUTPUT_PROTECTED",
            "Generate runtime output must be outside the repository.",
            artifact_path=root,
        )
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise _workflow_error(
            "DC_GENERATE_OUTPUT_NOT_EMPTY",
            "Generate runtime output must be new or empty.",
            artifact_path=root,
        )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if (prompt is None) == (prompt_file is None):
        raise _workflow_error(
            "DC_GENERATE_INPUT_INVALID",
            "Provide exactly one of --prompt or --prompt-file.",
        )
    if prompt_file is not None:
        source = prompt_file.resolve()
        if not source.is_file():
            raise _workflow_error(
                "DC_GENERATE_INPUT_MISSING",
                f"Prompt file is missing: {source}",
                artifact_path=source,
            )
        try:
            value = source.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise _workflow_error(
                "DC_GENERATE_INPUT_INVALID",
                "Prompt file must be UTF-8 text.",
                artifact_path=source,
            ) from exc
    else:
        value = prompt or ""
    if not value.strip():
        raise _workflow_error("DC_GENERATE_INPUT_INVALID", "Prompt must not be empty.")
    return value


def _resolve_pdfs(paths: Iterable[Path]) -> tuple[Path, ...]:
    resolved = tuple(Path(path).resolve() for path in paths)
    if len(resolved) > MAX_GENERAL_PDFS:
        raise _workflow_error(
            "DC_GENERATE_INPUT_INVALID",
            f"At most {MAX_GENERAL_PDFS} PDFs may be supplied to the six-slide workflow.",
        )
    for path in resolved:
        if not path.is_file():
            raise _workflow_error(
                "DC_GENERATE_INPUT_MISSING",
                f"PDF input is missing: {path}",
                artifact_path=path,
            )
        if path.suffix.lower() != ".pdf":
            raise _workflow_error(
                "DC_GENERATE_INPUT_INVALID",
                f"Document input must use the .pdf extension: {path}",
                artifact_path=path,
            )
    hashes = [_sha256_file(path) for path in resolved]
    if len(hashes) != len(set(hashes)):
        raise _workflow_error(
            "DC_SOURCE_DUPLICATE_CONFLICT",
            "Duplicate PDF bytes are not silently deduplicated.",
        )
    return resolved


def _copy_pdf_inputs(paths: tuple[Path, ...], inputs_dir: Path) -> tuple[Path, ...]:
    copied: list[Path] = []
    for index, source in enumerate(paths, start=1):
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip("-._") or "source"
        destination = inputs_dir / f"source-{index:02d}-{stem[:48]}.pdf"
        shutil.copy2(source, destination)
        copied.append(destination)
    return tuple(copied)


def _validate_phase4_link(root: Path, manifest: dict[str, Any], phase4_bundle: Path) -> None:
    provenance_path = phase4_bundle / "input_provenance.json"
    if not provenance_path.is_file():
        raise _workflow_error(
            "DC_GENERATE_PHASE4_LINK_MISSING",
            "Accepted Phase 4 bundle is missing input_provenance.json.",
            artifact_path=provenance_path,
        )
    provenance = read_json(provenance_path)
    phase3_run = read_json(root / "phase3" / "deckcompiler_run_manifest.json")
    if provenance.get("phase3_run_id") != phase3_run.get("run_id"):
        raise _workflow_error(
            "DC_GENERATE_PHASE4_LINK_MISMATCH",
            "Phase 4 bundle was not produced from this workflow's Phase 3 run.",
            artifact_path=provenance_path,
        )
    expected_hashes = read_json(root / "phase3" / "phase3_validation_report.json").get(
        "deterministic_artifact_hashes"
    )
    if provenance.get("phase3_artifact_hashes") != expected_hashes:
        raise _workflow_error(
            "DC_GENERATE_PHASE4_LINK_MISMATCH",
            "Phase 4 provenance does not bind the exact Phase 3 artifact hashes.",
            artifact_path=provenance_path,
        )


def _validate_phase5_link(root: Path, phase5: dict[str, Any], phase5_bundle: Path) -> None:
    if not phase5_bundle.is_dir():
        raise _workflow_error(
            "DC_GENERATE_PHASE5_BUNDLE_MISSING",
            f"Phase 5 bundle is unavailable: {phase5_bundle}",
            artifact_path=phase5_bundle,
        )
    candidate = phase5_bundle / "handoff" / "pngtopptx_handoff_manifest.json"
    if not candidate.is_file():
        raise _workflow_error(
            "DC_GENERATE_PHASE5_LINK_MISSING",
            "Phase 5 bundle is missing its handoff manifest.",
            artifact_path=candidate,
        )
    expected_path = root / "phase5_handoff" / "handoff" / "pngtopptx_handoff_manifest.json"
    if not expected_path.is_file():
        raise _workflow_error(
            "DC_GENERATE_PHASE5_LINK_MISSING",
            "This workflow has no exported Phase 5 handoff to bind.",
            artifact_path=expected_path,
        )
    expected = read_json(expected_path)
    observed = read_json(candidate)
    if observed.get("handoff_id") != expected.get("handoff_id"):
        raise _workflow_error(
            "DC_GENERATE_PHASE5_LINK_MISMATCH",
            "Phase 5 reconstruction bundle does not match this workflow's handoff.",
            artifact_path=candidate,
        )
    if phase5.get("details", {}).get("handoff_id") not in {None, observed.get("handoff_id")}:
        raise _workflow_error(
            "DC_GENERATE_PHASE5_LINK_MISMATCH",
            "Stored Phase 5 handoff identity differs from the reconstruction bundle.",
            artifact_path=candidate,
        )


def _load_workflow(resume: Path) -> tuple[Path, dict[str, Any]]:
    candidate = resume.resolve()
    manifest_path = candidate / MANIFEST_NAME if candidate.is_dir() else candidate
    if not manifest_path.is_file():
        raise _workflow_error(
            "DC_GENERATE_MANIFEST_MISSING",
            f"Generate workflow manifest is missing: {manifest_path}",
            artifact_path=manifest_path,
        )
    manifest = read_json(manifest_path)
    issues = _manifest_issues(manifest)
    if issues:
        raise _workflow_error(
            "DC_GENERATE_MANIFEST_INVALID",
            "; ".join(issues[:5]),
            artifact_path=manifest_path,
        )
    root = manifest_path.parent
    if Path(str(manifest["runtime_root"])).resolve() != root:
        raise _workflow_error(
            "DC_GENERATE_MANIFEST_RELOCATED",
            "Workflow manifest runtime_root does not match its current directory.",
            artifact_path=manifest_path,
        )
    phases = [stage["phase"] for stage in manifest["stages"]]
    if phases != ["phase3", "phase4", "phase5", "phase6"]:
        raise _workflow_error(
            "DC_GENERATE_MANIFEST_INVALID",
            f"Unexpected phase order: {phases}",
            artifact_path=manifest_path,
        )
    return root, manifest


def _manifest_issues(payload: dict[str, Any]) -> list[str]:
    issues = []
    for error in validator_for(WORKFLOW_SCHEMA).iter_errors(payload):
        location = "/".join(str(item) for item in error.absolute_path) or "$"
        issues.append(f"{location}: {error.message}")
    expected = payload.get("manifest_hash")
    value = dict(payload)
    value.pop("manifest_hash", None)
    if expected != content_sha256(value):
        issues.append("manifest_hash: content hash mismatch")
    return sorted(issues)


def _write_workflow_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = _now()
    value = dict(manifest)
    value.pop("manifest_hash", None)
    manifest["manifest_hash"] = content_sha256(value)
    issues = _manifest_issues(manifest)
    if issues:
        raise _workflow_error(
            "DC_GENERATE_MANIFEST_INVALID",
            "; ".join(issues[:5]),
            artifact_path=root / MANIFEST_NAME,
        )
    write_json(root / MANIFEST_NAME, manifest)


def _block_manifest(root: Path, manifest: dict[str, Any], exc: Exception) -> None:
    error = (
        exc.to_dict()
        if isinstance(exc, DeckCompilerError)
        else {
            "code": getattr(exc, "code", "DC_GENERATE_FAILED"),
            "stage": "general_generate_workflow",
            "message": str(exc),
            "severity": "error",
            "release_blocking": True,
        }
    )
    manifest["errors"].append(error)
    active = next(
        (
            stage
            for stage in manifest["stages"]
            if stage["status"] == "RUNNING"
        ),
        None,
    )
    if active is not None:
        active["status"] = "BLOCKED"
        active["required_action"] = {
            "code": str(error.get("code", "DC_GENERATE_FAILED")),
            "message": str(error.get("message", exc)),
        }
    manifest["status"] = "BLOCKED"
    _record(manifest, "workflow_blocked", "BLOCKED")
    _sync_artifacts(manifest)
    try:
        _write_workflow_manifest(root, manifest)
    except (DeckCompilerError, OSError, ValueError):
        pass


def _stage(manifest: dict[str, Any], phase: str) -> dict[str, Any]:
    return next(stage for stage in manifest["stages"] if stage["phase"] == phase)


def _record(manifest: dict[str, Any], event: str, status: str) -> None:
    manifest["history"].append({"timestamp": _now(), "event": event, "status": status})


def _sync_artifacts(manifest: dict[str, Any]) -> None:
    manifest["artifacts"] = [
        artifact
        for stage in manifest["stages"]
        for artifact in stage["artifacts"]
    ]


def _stored_external_path(stage: dict[str, Any], key: str) -> Path | None:
    value = stage.get("details", {}).get(key)
    return Path(value).resolve() if isinstance(value, str) and value else None


def _current_action(manifest: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            stage["required_action"]
            for stage in manifest["stages"]
            if stage["required_action"] is not None
        ),
        None,
    )


def _result(root: Path, manifest: dict[str, Any], *, exit_code: int) -> GenerateWorkflowResult:
    return GenerateWorkflowResult(
        workflow_id=manifest["workflow_id"],
        runtime_root=root,
        manifest_path=root / MANIFEST_NAME,
        status=manifest["status"],
        exit_code=exit_code,
        required_action=_current_action(manifest),
    )


def _artifact_reference(
    root: Path,
    path: Path,
    kind: str,
    *,
    directory: bool = False,
) -> dict[str, Any]:
    resolved = path.resolve()
    scope = "workflow" if resolved == root or resolved.is_relative_to(root) else "external"
    reference: dict[str, Any] = {
        "kind": kind,
        "path": _path_value(root, resolved),
        "scope": scope,
    }
    if directory:
        fingerprint = _directory_fingerprint(resolved)
        reference.update(fingerprint)
    elif resolved.is_file():
        reference["sha256"] = _sha256_file(resolved)
    return reference


def _path_value(root: Path, path: Path) -> str:
    resolved = path.resolve()
    if resolved == root:
        return "."
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return resolved.as_posix()


def _directory_fingerprint(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise _workflow_error(
            "DC_GENERATE_ARTIFACT_MISSING",
            f"Artifact directory is missing: {root}",
            artifact_path=root,
        )
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise _workflow_error(
                "DC_GENERATE_ARTIFACT_UNSAFE",
                f"Symlinks are forbidden in workflow bundles: {path}",
                artifact_path=path,
            )
        if path.is_file():
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": _sha256_file(path),
                    "byte_size": path.stat().st_size,
                }
            )
    return {"aggregate_sha256": content_sha256(rows), "file_count": len(rows)}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _workflow_error(
    code: str,
    message: str,
    *,
    artifact_path: Path | None = None,
    remediation_hint: str = "Correct the workflow input or resume option and try again.",
) -> DeckCompilerError:
    return DeckCompilerError(
        code,
        "general_generate_workflow",
        message,
        artifact_path.as_posix() if artifact_path else None,
        remediation_hint=remediation_hint,
    )


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "GenerateWorkflowResult",
    "MANIFEST_NAME",
    "WORKFLOW_OPTIONS",
    "resume_generate_workflow",
    "start_generate_workflow",
    "validate_generate_workflow",
]
