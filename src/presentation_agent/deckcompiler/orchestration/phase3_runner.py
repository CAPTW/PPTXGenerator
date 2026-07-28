"""Deterministic Phase 3 runner ending at planning-level creative architecture."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...compiler.blueprint_adapter import validate_slide_blueprint_collection
from ...generator_contracts import (
    validateCreativeTemplateArchitecture,
    validatePresentationArchitecture,
    validatePresentationPlan,
)
from ..architecture.creative_frontend_adapter import ArchitectureArtifacts, build_architecture_artifacts
from ..architecture.validation import validate_phase3_architecture_graph
from ..errors import DeckCompilerError
from ..identity import stable_id
from ..intake.config import Phase3Config, load_phase3_config
from ..intake.multi_source import IntakeArtifacts, build_intake_artifacts
from ..manifest_io import write_json
from ..planning.strict_adapter import StrictPlanningArtifacts, build_strict_planning
from ..provenance import (
    BUILD_BASELINE,
    current_source_commit,
    seal_artifact,
    semantic_content_sha256,
    verify_artifact_content_hash,
)
from ..schemas import REPO_ROOT
from ..validation import validate_artifact


ACTIVE_STAGES = (
    "config_validation",
    "source_preflight",
    "prompt_intake",
    "pdf_intake",
    "source_normalization",
    "evidence_normalization",
    "source_coverage",
    "workflow_resolution",
    "strict_planning",
    "blueprint_collection",
    "presentation_architecture",
    "module_batch_slide",
    "design_invariants",
    "module_art_direction",
    "creative_template_planning",
    "fit_decision_validation",
    "artifact_graph_validation",
)
DEFERRED_STAGES = (
    "live_image_generation",
    "visual_target_generation",
    "semantic_sidecar_finalization",
    "pngtopptx_reconstruction",
    "scene_graph_generation",
    "template_materialization",
    "pptx_compilation",
    "html_compilation",
    "rendering",
    "visual_qa",
    "repair_execution",
    "packaging",
)
PHASE_BOUNDARY = {stage: "not_executed" for stage in DEFERRED_STAGES}


@dataclass(frozen=True, slots=True)
class Phase3RunResult:
    output_dir: Path
    run_id: str
    manifest: dict[str, Any]
    validation_report: dict[str, Any]


def run_phase3(config_path: str | Path, output_dir: str | Path) -> Phase3RunResult:
    """Build the Phase 3 contract graph without downstream generation side effects."""

    output = _prepare_output_directory(Path(output_dir))
    started_at = _utc_now()
    passed: set[str] = set()
    mode_skips: set[str] = set()
    config: Phase3Config | None = None
    try:
        config = load_phase3_config(config_path)
        passed.add("config_validation")
        intake = build_intake_artifacts(config)
        passed.update(
            {
                "source_preflight",
                "prompt_intake",
                "source_normalization",
                "evidence_normalization",
                "source_coverage",
            }
        )
        if config.pdf_paths:
            passed.add("pdf_intake")
        else:
            mode_skips.add("pdf_intake")

        planning = build_strict_planning(config, intake)
        passed.update({"workflow_resolution", "strict_planning", "blueprint_collection"})
        architecture = build_architecture_artifacts(config, intake, planning)
        passed.update(
            {
                "presentation_architecture",
                "module_batch_slide",
                "design_invariants",
                "module_art_direction",
                "creative_template_planning",
                "fit_decision_validation",
            }
        )

        core = _core_artifacts(intake, planning, architecture)
        _validate_core_artifacts(intake, planning, architecture, core)
        references = [_artifact_reference(filename, payload) for filename, payload in core]
        graph = _build_artifact_graph(intake.input_request["run_id"], core, references)
        graph_report = validate_artifact(graph, schema_name="phase3_artifact_graph")
        if not graph_report.valid:
            raise DeckCompilerError(
                "DC_ARTIFACT_GRAPH_INVALID",
                "artifact_graph_validation",
                graph_report.to_human(),
            )
        passed.add("artifact_graph_validation")

        validation_report = _build_validation_report(
            intake.input_request["run_id"],
            core,
            graph,
            registered_count=sum(1 for _, payload in core if payload["schema_name"] in _REGISTERED_CORE_SCHEMAS),
        )
        report_validation = validate_artifact(validation_report, schema_name="phase3_validation_report")
        if not report_validation.valid:
            raise DeckCompilerError(
                "DC_PHASE3_REPORT_INVALID",
                "artifact_graph_validation",
                report_validation.to_human(),
            )

        graph_reference = _artifact_reference("artifact_graph.json", graph)
        report_reference = _artifact_reference("phase3_validation_report.json", validation_report)
        all_references = [*references, graph_reference, report_reference]
        completed_at = _utc_now()
        manifest = _build_manifest(
            config=config,
            run_id=intake.input_request["run_id"],
            started_at=started_at,
            completed_at=completed_at,
            passed=passed,
            mode_skips=mode_skips,
            artifacts=all_references,
            errors=[],
            run_status="completed",
        )
        manifest_validation = validate_artifact(manifest, schema_name="phase3_run_manifest")
        if not manifest_validation.valid:
            raise DeckCompilerError(
                "DC_RUN_MANIFEST_INVALID",
                "artifact_graph_validation",
                manifest_validation.to_human(),
            )

        for filename, payload in core:
            write_json(output / filename, payload)
        write_json(output / "artifact_graph.json", graph)
        write_json(output / "phase3_validation_report.json", validation_report)
        write_json(output / "deckcompiler_run_manifest.json", manifest)
        return Phase3RunResult(output, intake.input_request["run_id"], manifest, validation_report)
    except DeckCompilerError as exc:
        if exc.code != "DC_OUTPUT_PROTECTED":
            _write_failed_manifest(
                output=output,
                config=config,
                config_path=Path(config_path),
                started_at=started_at,
                passed=passed,
                mode_skips=mode_skips,
                error=exc,
            )
        raise
    except (OSError, TypeError, ValueError) as exc:
        wrapped = DeckCompilerError(
            "DC_PHASE3_VALIDATION_FAILED",
            "artifact_graph_validation",
            str(exc),
            remediation_hint="Inspect the machine-readable Phase 3 failure manifest and correct the producing adapter.",
        )
        _write_failed_manifest(
            output=output,
            config=config,
            config_path=Path(config_path),
            started_at=started_at,
            passed=passed,
            mode_skips=mode_skips,
            error=wrapped,
        )
        raise wrapped from exc


def _core_artifacts(
    intake: IntakeArtifacts,
    planning: StrictPlanningArtifacts,
    architecture: ArchitectureArtifacts,
) -> list[tuple[str, dict[str, Any]]]:
    return [
        ("input_request.json", intake.input_request),
        ("source_corpus.json", intake.source_corpus),
        ("source_locators.json", intake.source_locator_registry),
        ("evidence_unit_registry.json", intake.evidence_unit_registry),
        ("source_coverage_report.json", intake.source_coverage_report),
        ("workflow_resolution.json", planning.workflow_resolution),
        ("source_gap_report.json", planning.source_gap_report),
        ("presentation_plan.json", planning.presentation_plan),
        ("slide_blueprint_collection.json", planning.slide_blueprint_collection),
        ("evidence_allocation_report.json", planning.evidence_allocation_report),
        ("presentation_architecture.json", architecture.presentation_architecture),
        ("design_invariants.json", architecture.design_invariants),
        ("module_art_directions.json", architecture.module_art_directions),
        ("creative_template_architecture.json", architecture.creative_template_architecture),
        ("creative_fit_report.json", architecture.creative_fit_report),
        ("architecture_validation_report.json", architecture.architecture_validation_report),
    ]


_REGISTERED_CORE_SCHEMAS = {
    "input_request",
    "source_corpus",
    "source_locator_registry",
    "phase3_evidence_unit_registry",
    "source_coverage_report",
    "workflow_resolution",
    "source_gap_report",
    "slide_blueprint_collection",
    "evidence_allocation_report",
    "design_invariants",
    "module_art_directions",
    "creative_fit_report",
    "architecture_validation_report",
}


def _validate_core_artifacts(
    intake: IntakeArtifacts,
    planning: StrictPlanningArtifacts,
    architecture: ArchitectureArtifacts,
    core: list[tuple[str, dict[str, Any]]],
) -> None:
    for filename, payload in core:
        schema_name = str(payload["schema_name"])
        if schema_name not in _REGISTERED_CORE_SCHEMAS:
            continue
        report = validate_artifact(payload, schema_name=schema_name, artifact_path=filename)
        if not report.valid:
            raise DeckCompilerError("DC_SCHEMA_VALIDATION_FAILED", "artifact_graph_validation", report.to_human(), filename)
    validatePresentationPlan(planning.presentation_plan)
    validate_slide_blueprint_collection(planning.slide_blueprint_collection)
    validatePresentationArchitecture(architecture.presentation_architecture)
    validateCreativeTemplateArchitecture(architecture.creative_template_architecture)
    validate_phase3_architecture_graph(intake, planning, architecture)
    _validate_source_evidence_bindings(intake)


def _validate_source_evidence_bindings(intake: IntakeArtifacts) -> None:
    source_ids = {item["source_id"] for item in intake.source_corpus["sources"]}
    locator_ids = {item["locator_id"] for item in intake.source_locator_registry["locators"]}
    for item in intake.evidence_unit_registry["evidence_units"]:
        if item["source_id"] not in source_ids:
            raise DeckCompilerError(
                "DC_UNKNOWN_SOURCE_REFERENCE",
                "evidence_normalization",
                f"evidence {item['evidence_id']} references an unknown source",
                related_ids=(item["evidence_id"], item["source_id"]),
            )
        unknown_locators = set(item["source_locator_ids"]) - locator_ids
        if unknown_locators:
            raise DeckCompilerError(
                "DC_UNKNOWN_LOCATOR_REFERENCE",
                "evidence_normalization",
                f"evidence {item['evidence_id']} references unknown source locators",
                related_ids=(item["evidence_id"], *sorted(unknown_locators)),
            )


def _artifact_reference(filename: str, payload: dict[str, Any]) -> dict[str, Any]:
    envelope = payload.get("artifact")
    schema_name = str(payload["schema_name"])
    if isinstance(envelope, dict):
        artifact_type = str(envelope["artifact_type"])
        artifact_id = str(envelope["artifact_id"])
        digest = str(envelope["content_sha256"])
        provenance_mode = "embedded_envelope"
        verify_artifact_content_hash(payload)
    else:
        artifact_type = schema_name
        digest = semantic_content_sha256(payload)
        artifact_id = stable_id("art", artifact_type, digest)
        provenance_mode = "manifest_reference"
    return {
        "artifact_type": artifact_type,
        "schema_name": schema_name,
        "artifact_id": artifact_id,
        "path": filename,
        "semantic_content_sha256": digest,
        "provenance_mode": provenance_mode,
        "required": True,
    }


def _build_artifact_graph(
    run_id: str,
    core: list[tuple[str, dict[str, Any]]],
    references: list[dict[str, Any]],
) -> dict[str, Any]:
    reference_by_schema = {item["schema_name"]: item for item in references}
    known_ids = {item["artifact_id"] for item in references}
    edges: set[tuple[str, str, str]] = set()
    for (_, payload), reference in zip(core, references, strict=True):
        for input_id in payload.get("artifact", {}).get("provenance", {}).get("input_artifact_ids", []):
            if input_id not in known_ids:
                raise DeckCompilerError(
                    "DC_UNKNOWN_PROVENANCE_INPUT",
                    "artifact_graph_validation",
                    f"unknown provenance input artifact_id: {input_id}",
                    related_ids=(input_id, reference["artifact_id"]),
                )
            edges.add((input_id, reference["artifact_id"], "provenance_input"))

    logical_inputs = {
        "workflow_resolution": ("input_request",),
        "presentation_plan": ("phase3_evidence_unit_registry", "workflow_resolution"),
        "presentation_architecture": ("presentation_plan", "slide_blueprint_collection"),
        "creative_template_architecture": (
            "presentation_architecture",
            "design_invariants",
            "module_art_directions",
        ),
    }
    for target_schema, input_schemas in logical_inputs.items():
        target = reference_by_schema[target_schema]["artifact_id"]
        for input_schema in input_schemas:
            edges.add((reference_by_schema[input_schema]["artifact_id"], target, "logical_input"))

    nodes = [
        {
            key: reference[key]
            for key in (
                "artifact_id",
                "artifact_type",
                "schema_name",
                "path",
                "semantic_content_sha256",
                "provenance_mode",
            )
        }
        for reference in references
    ]
    edge_rows = [
        {"from": source, "to": target, "relation": relation}
        for source, target, relation in sorted(edges)
    ]
    incoming = {edge["to"] for edge in edge_rows}
    roots = sorted(node["artifact_id"] for node in nodes if node["artifact_id"] not in incoming)
    expected_root = reference_by_schema["input_request"]["artifact_id"]
    orphans = sorted(set(roots) - {expected_root})
    if orphans:
        raise DeckCompilerError(
            "DC_ORPHAN_ARTIFACT",
            "artifact_graph_validation",
            "Phase 3 artifact graph contains orphan artifacts",
            related_ids=tuple(orphans),
        )
    payload = {
        "schema_name": "phase3_artifact_graph",
        "schema_version": "1.0.0",
        "graph_id": stable_id("graph", nodes, edge_rows),
        "run_id": run_id,
        "nodes": sorted(nodes, key=lambda item: item["artifact_id"]),
        "edges": edge_rows,
        "root_artifact_ids": roots,
        "orphan_artifact_ids": orphans,
        "validation_status": "valid",
    }
    return seal_artifact(
        payload,
        artifact_type="artifact_graph",
        input_artifact_ids=(reference_by_schema["architecture_validation_report"]["artifact_id"],),
    )


def _build_validation_report(
    run_id: str,
    core: list[tuple[str, dict[str, Any]]],
    graph: dict[str, Any],
    *,
    registered_count: int,
) -> dict[str, Any]:
    hashes = {
        filename: _artifact_reference(filename, payload)["semantic_content_sha256"]
        for filename, payload in core
    }
    payload = {
        "schema_name": "phase3_validation_report",
        "schema_version": "1.0.0",
        "report_id": stable_id("phase3validation", hashes, graph["graph_id"]),
        "run_id": run_id,
        "verdict": "GO",
        "determinism_ready": True,
        "deterministic_artifact_hashes": dict(sorted(hashes.items())),
        "schema_validation": {"status": "passed", "checked_count": registered_count, "error_count": 0},
        "semantic_validation": {"status": "passed", "checked_count": len(core), "error_count": 0},
        "artifact_graph_validation": {
            "status": "passed",
            "checked_count": len(graph["nodes"]),
            "error_count": 0,
        },
        "checks": [
            "all registered Phase 3 artifacts satisfy Draft 2020-12 schemas",
            "all evidence source and locator references resolve",
            "strict blueprint order and evidence bindings resolve",
            "module-batch-slide coverage is contiguous and complete",
            "creative fit decisions pass semantic, capacity, and editability planning thresholds",
            "artifact provenance graph has one declared root and no orphans",
        ],
        "phase_boundary": PHASE_BOUNDARY,
        "warnings": [
            "Creative Template Architecture is planning-level only; geometry-aware template proof is deferred to Phase 4."
        ],
    }
    return seal_artifact(
        payload,
        artifact_type="phase3_validation_report",
        input_artifact_ids=(graph["artifact"]["artifact_id"],),
    )


def _build_manifest(
    *,
    config: Phase3Config | None,
    run_id: str,
    started_at: str,
    completed_at: str,
    passed: set[str],
    mode_skips: set[str],
    artifacts: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    run_status: str,
) -> dict[str, Any]:
    stages = _stage_records(passed, mode_skips, errors[0]["stage"] if errors else None)
    source_commit = current_source_commit()
    payload = {
        "schema_name": "phase3_run_manifest",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "started_at": started_at,
        "updated_at": completed_at,
        "completed_at": completed_at,
        "run_status": run_status,
        "build_baseline": BUILD_BASELINE,
        "source_commit": source_commit,
        "inputs": {
            "config": config.config_path.as_posix() if config else "unresolved-config",
            "prompt": config.prompt_reference if config else None,
            "pdfs": list(config.pdf_references) if config else [],
        },
        "stages": stages,
        "passed_stage_count": sum(item["status"] == "passed" for item in stages),
        "artifacts": artifacts,
        "retry_history": [],
        "warnings": [],
        "errors": errors,
        "validation_status": "valid" if run_status == "completed" else "invalid",
        "phase_boundary": PHASE_BOUNDARY,
    }
    input_ids = tuple(item["artifact_id"] for item in artifacts[-2:]) if artifacts else ()
    return seal_artifact(
        payload,
        artifact_type="deckcompiler_run_manifest",
        input_artifact_ids=input_ids,
        source_commit=source_commit,
    )


def _stage_records(
    passed: set[str],
    mode_skips: set[str],
    failed_stage: str | None,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for stage in ACTIVE_STAGES:
        if stage in passed:
            status = "passed"
        elif stage in mode_skips:
            status = "skipped_by_mode"
        elif stage == failed_stage:
            status = "failed"
        elif failed_stage is not None:
            status = "blocked"
        else:
            status = "not_started"
        records.append({"stage": stage, "status": status})
    records.extend({"stage": stage, "status": "skipped_by_phase"} for stage in DEFERRED_STAGES)
    if failed_stage and failed_stage not in ACTIVE_STAGES:
        records.append({"stage": failed_stage, "status": "failed"})
    return records


def _write_failed_manifest(
    *,
    output: Path,
    config: Phase3Config | None,
    config_path: Path,
    started_at: str,
    passed: set[str],
    mode_skips: set[str],
    error: DeckCompilerError,
) -> None:
    completed_at = _utc_now()
    run_id = stable_id("run", "phase3-failed", config_path.resolve().as_posix())
    manifest = _build_manifest(
        config=config,
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        passed=passed,
        mode_skips=mode_skips,
        artifacts=[],
        errors=[error.to_dict()],
        run_status="failed",
    )
    report = validate_artifact(manifest, schema_name="phase3_run_manifest")
    if not report.valid:
        raise RuntimeError(report.to_human())
    write_json(output / "deckcompiler_run_manifest.json", manifest)


def _prepare_output_directory(path: Path) -> Path:
    output = path.resolve()
    repo_root = REPO_ROOT.resolve()
    if output == repo_root or output.is_relative_to(repo_root):
        raise DeckCompilerError(
            "DC_OUTPUT_PROTECTED",
            "config_validation",
            "Phase 3 runtime output must be an isolated user-specified directory outside the repository",
            output.as_posix(),
            remediation_hint="Choose a new empty directory outside the repository workspace.",
        )
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise DeckCompilerError(
            "DC_OUTPUT_NOT_EMPTY",
            "config_validation",
            "Phase 3 output directory must be new or empty",
            output.as_posix(),
            remediation_hint="Choose a new empty output directory; the runner does not delete existing files.",
        )
    output.mkdir(parents=True, exist_ok=True)
    return output


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["ACTIVE_STAGES", "DEFERRED_STAGES", "Phase3RunResult", "run_phase3"]
