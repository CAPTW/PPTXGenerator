"""CLI helpers for state validation and deterministic planning flows."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .asset_derivation import derive_assets_from_files, write_asset_derivation_outputs
from .approved_apply import apply_approved_fixes_from_files, write_approved_apply_outputs
from .deck_qa import run_deck_qa_from_files, write_deck_qa_outputs
from .document_asset_crop import (
    load_document_crop_file,
    run_document_asset_crop_from_files,
    run_document_crop_review_from_files,
    write_document_crop_outputs,
)
from .gate2_planner import plan_gate2_from_files, write_gate2_outputs
from .large_deck_orchestration import orchestrate_large_deck_from_files, write_large_deck_outputs
from .post_apply_closure import close_approved_fixes_from_files, write_post_apply_closure_outputs
from ..pptx_compiler import adapt_blueprint_to_slide_ir, compile_pptx_from_files, load_pptx_compile_file, write_pptx_compile_outputs
from ..pptx_scene_compiler import (
    compile_pptx_from_scene_deck_file,
    summarize_scene_pptx_compile,
    write_scene_pptx_compile_report,
)
from ..slide_scene import scene_deck_to_stable_json
from ..slide_scene_adapter import adapt_slide_ir_document_to_scene_deck, summarize_scene_deck_adapter
from ..pipeline.pptx_object_validation import (
    summarize_pptx_object_validation,
    validate_pptx_objects_from_files,
    write_pptx_object_validation_report,
)
from ..pipeline.scene_readiness_gate import (
    run_scene_readiness_gate_from_file,
    summarize_scene_readiness_report,
    write_scene_readiness_report,
)
from ..pipeline.scene_migration_readiness import (
    build_scene_migration_readiness_report,
    summarize_scene_migration_readiness_report,
    write_migration_readiness_artifacts,
)
from ..pipeline.scene_migration_history import (
    build_scene_migration_history,
    summarize_scene_migration_history_report,
    write_scene_migration_history_artifacts,
)
from ..pipeline.scene_default_comparison import (
    run_default_vs_scene_poc,
    summarize_default_vs_scene_report,
)
from ..pipeline.experimental_scene_compile import (
    compile_pptx_with_experimental_scene_renderer,
    experimental_scene_compile_failed,
    summarize_experimental_scene_compile,
)
from ..pipeline.presentation_plan_validation import (
    summarize_presentation_plan_validation,
    validate_presentation_plan,
    write_presentation_plan_validation_report,
)
from ..presentation_plan_bridge import (
    build_state_from_presentation_plan,
    build_state_from_presentation_plan_files,
    summarize_bridge_report,
)
from ..presentation_plan_repair import (
    PresentationPlanRepairPolicy,
    repair_presentation_plan,
    repair_presentation_plan_from_files,
    summarize_repair_report,
    write_repaired_plan_artifacts,
)
from ..source_deck_planner import plan_deck_from_source_document, write_presentation_plan
from ..source_ingestion import ingest_source_file, write_source_document
from ..source_planning import load_source_document
from ..style_prior import NullStylePriorProvider
from .remediation_execution import apply_bounded_remediation_from_files, write_remediation_execution_outputs
from .reference_scanner import load_reference_brief_context, scan_reference_pack
from .ship_readiness import assess_ship_readiness_from_files, write_ship_readiness_outputs
from .reviewed_surrogate_policy import (
    evaluate_reviewed_surrogate_policy,
    write_reviewed_surrogate_policy_reports,
)
from ..compat.legacy_non_pptx import STATE_SCHEMA_NAMES
from ..compat.legacy_non_pptx import (
    DEFAULT_STATE_FILENAMES,
    SCHEMA_REGISTRY,
    generate_state_model,
    load_state_file,
    save_state_file,
    schema_expectations,
    schema_summaries,
    validate_state_file,
)
from .structured_visuals import run_structured_visuals_from_files, write_structured_visual_outputs
from .upstream_fix_authoring import author_upstream_fixes_from_files, write_upstream_fix_outputs
from .workflow_evaluation import evaluate_workflow_harness, write_workflow_evaluation_report
from .workflow_planner import plan_workflow_from_file


def _artifact_root_for_cli(output_dir: Path) -> Path:
    return output_dir.resolve().parent

def _iter_state_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file() and candidate.suffix.lower() in {".json", ".yaml", ".yml"}
        )
    raise FileNotFoundError(path)


def _validate_paths(paths: list[Path]) -> int:
    failures = 0
    for root in paths:
        for file_path in _iter_state_files(root):
            try:
                model = validate_state_file(file_path)
            except Exception as exc:  # pragma: no cover - exercised by tests via return code
                try:
                    model = load_document_crop_file(file_path)
                except Exception:
                    try:
                        model = load_pptx_compile_file(file_path)
                    except Exception:
                        failures += 1
                        print(f"INVALID {file_path}: {exc}")
                    else:
                        print(f"VALID   {file_path} -> {model.schema_name}")
                else:
                    print(f"VALID   {file_path} -> {model.schema_name}")
            else:
                print(f"VALID   {file_path} -> {model.schema_name}")
    return 1 if failures else 0


def _print_summary(schema_name: str | None = None) -> int:
    rows = schema_expectations(schema_name) if schema_name is not None else schema_summaries()
    for row in rows:
        print(f"{row['schema_name']}: {row['filename']}")
        print(f"  {row['summary']}")
        if "required_fields" in row:
            required = ", ".join(row["required_fields"]) if row["required_fields"] else "(defaults only)"
            print(f"  required: {required}")
        if "collection_fields" in row:
            collections = ", ".join(row["collection_fields"]) if row["collection_fields"] else "(none)"
            print(f"  collections: {collections}")
    return 0


def _write_generated(schema: str, mode: str, output: Path) -> None:
    model = generate_state_model(schema, mode=mode)
    save_state_file(model, output)
    print(f"WROTE {output}")


def _parse_delta_option_args(values: list[str] | None) -> dict[str, str]:
    selections: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"delta option selections must use DELTA_ID=OPTION_ID form: {item}")
        delta_id, option_id = item.split("=", 1)
        delta_id = delta_id.strip()
        option_id = option_id.strip()
        if not delta_id or not option_id:
            raise ValueError(f"delta option selections must include both ids: {item}")
        selections[delta_id] = option_id
    return selections


def _generate(schema: str, mode: str, output: Path) -> int:
    if schema == "all":
        output.mkdir(parents=True, exist_ok=True)
        for schema_name in STATE_SCHEMA_NAMES:
            _write_generated(schema_name, mode, output / DEFAULT_STATE_FILENAMES[schema_name])
        return 0
    if schema not in SCHEMA_REGISTRY:
        raise KeyError(f"unknown schema {schema!r}")
    if output.suffix.lower() not in {".json", ".yaml", ".yml"}:
        output.mkdir(parents=True, exist_ok=True)
        output = output / DEFAULT_STATE_FILENAMES[schema]
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
    _write_generated(schema, mode, output)
    return 0


def _plan_workflow(brief: Path, output: Path) -> int:
    model = plan_workflow_from_file(brief)
    save_state_file(model, output)
    print(f"WROTE {output}")
    return 0


def _ingest_source(source: Path, output: Path) -> int:
    document = ingest_source_file(source)
    output_path = write_source_document(document, output)
    print(
        "SOURCE_INGESTION "
        f"document_id={document.document_id} "
        f"source_type={document.source_type} "
        f"chunks={len(document.chunks)} "
        f"outline_quality={document.outline.structure_quality} "
        f"warnings={len(document.warnings)}"
    )
    print(f"WROTE {output_path}")
    return 0


def _plan_deck_from_source(
    source_document: Path,
    design_mode: str,
    target_slides: int,
    output: Path,
    validation_output: Path,
) -> int:
    document = load_source_document(source_document)
    plan = plan_deck_from_source_document(
        document,
        design_mode=design_mode,  # type: ignore[arg-type]
        target_slide_count=target_slides,
    )
    plan_path = write_presentation_plan(plan, output)
    report = validate_presentation_plan(plan, document)
    report_path = write_presentation_plan_validation_report(report, validation_output)
    print(
        "SOURCE_DECK_PLAN "
        f"plan_id={plan.plan_id} "
        f"design_mode={plan.design_mode} "
        f"target_slides={plan.target_slide_count} "
        f"planned_slides={len(plan.slides)} "
        f"sections={len(plan.sections)} "
        f"validation_status={report.status}"
    )
    for line in summarize_presentation_plan_validation(report):
        print(line)
    print(f"WROTE {plan_path}")
    print(f"WROTE {report_path}")
    return 1 if report.status == "failed" else 0


def _source_plan_poc(source: Path, design_mode: str, target_slides: int, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_document = ingest_source_file(source)
    source_document_path = write_source_document(source_document, output_dir / "source-document.json")
    plan = plan_deck_from_source_document(
        source_document,
        design_mode=design_mode,  # type: ignore[arg-type]
        target_slide_count=target_slides,
    )
    plan_path = write_presentation_plan(plan, output_dir / "presentation-plan.json")
    validation_report = validate_presentation_plan(plan, source_document)
    validation_path = write_presentation_plan_validation_report(
        validation_report,
        output_dir / "presentation-plan-validation.json",
    )
    summary = _build_source_plan_summary(
        source=source,
        output_dir=output_dir,
        source_document_path=source_document_path,
        presentation_plan_path=plan_path,
        validation_report_path=validation_path,
        source_document=source_document,
        plan=plan,
        validation_report=validation_report,
    )
    summary_path = output_dir / "source-plan-summary.json"
    summary_path.write_text(_stable_json(summary) + "\n", encoding="utf-8")
    print(
        "SOURCE_PLAN_POC "
        f"status={validation_report.status} "
        f"design_mode={plan.design_mode} "
        f"target_slides={plan.target_slide_count} "
        f"planned_slides={len(plan.slides)} "
        f"sections={len(plan.sections)} "
        f"findings={validation_report.finding_count} "
        f"warnings={validation_report.warning_count}"
    )
    print(f"WROTE {source_document_path}")
    print(f"WROTE {plan_path}")
    print(f"WROTE {validation_path}")
    print(f"WROTE {summary_path}")
    return 1 if validation_report.status == "failed" else 0


def _build_state_from_plan(source_document: Path, presentation_plan: Path, output_state_dir: Path) -> int:
    outputs = build_state_from_presentation_plan_files(
        source_document_path=source_document,
        presentation_plan_path=presentation_plan,
        output_state_dir=output_state_dir,
    )
    for line in summarize_bridge_report(outputs.report):
        print(line)
    for key, path in outputs.artifact_paths.items():
        print(f"WROTE {path}")
    return 1 if any(finding.severity == "error" for finding in outputs.report.findings) else 0


def _repair_presentation_plan(source_document: Path, presentation_plan: Path, output_dir: Path, write_markdown: bool = False) -> int:
    raw_payload = json.loads(presentation_plan.read_text(encoding="utf-8"))
    result = repair_presentation_plan_from_files(
        source_document_path=source_document,
        presentation_plan_path=presentation_plan,
        policy=PresentationPlanRepairPolicy(),
    )
    paths = write_repaired_plan_artifacts(
        result,
        original_plan_payload=raw_payload,
        output_dir=output_dir,
        write_markdown=write_markdown,
    )
    for line in summarize_repair_report(result.repair_report):
        print(line)
    for path in paths.values():
        print(f"WROTE {path}")
    return 1 if result.repaired_validation_report.status == "failed" else 0


def _source_to_state_poc(source: Path, design_mode: str, target_slides: int, output_dir: Path) -> int:
    paths = _build_source_to_state_artifacts(
        source=source,
        design_mode=design_mode,
        target_slides=target_slides,
        output_dir=output_dir,
    )
    validation_report = paths["validation_report"]
    bridge_report = paths["bridge_outputs"].report
    summary = _build_source_to_state_summary(
        source=source,
        output_dir=output_dir,
        source_document_path=paths["source_document_path"],
        presentation_plan_path=paths["presentation_plan_path"],
        validation_report_path=paths["validation_report_path"],
        state_dir=paths["state_dir"],
        validation_report=validation_report,
        bridge_report=bridge_report,
    )
    summary_path = output_dir / "source-to-state-summary.json"
    summary_path.write_text(_stable_json(summary) + "\n", encoding="utf-8")
    print(
        "SOURCE_TO_STATE_POC "
        f"status={validation_report.status} "
        f"design_mode={design_mode} "
        f"planned_slides={bridge_report.generated_slide_count} "
        f"bridge_findings={len(bridge_report.findings)}"
    )
    print(f"WROTE {paths['source_document_path']}")
    print(f"WROTE {paths['presentation_plan_path']}")
    print(f"WROTE {paths['validation_report_path']}")
    print(f"WROTE {paths['state_dir'] / 'bridge-report.json'}")
    print(f"WROTE {summary_path}")
    return 1 if validation_report.status == "failed" or any(f.severity == "error" for f in bridge_report.findings) else 0


def _source_to_pptx_poc(
    source: Path,
    design_mode: str,
    target_slides: int,
    output_dir: Path,
    experimental_scene_renderer: bool,
    scene_profile: str,
    scene_validation_mode: str,
    style_policy: Path | None,
    adapter_policy: Path | None,
    repair_plan: bool = False,
) -> int:
    if not experimental_scene_renderer:
        raise ValueError("source-to-pptx-poc requires --experimental-scene-renderer")
    paths = _build_source_to_state_artifacts(
        source=source,
        design_mode=design_mode,
        target_slides=target_slides,
        output_dir=output_dir,
        repair_plan=repair_plan,
    )
    state_dir = paths["state_dir"]
    pptx_dir = output_dir / "pptx"
    compile_outputs = compile_pptx_with_experimental_scene_renderer(
        blueprint_path=state_dir / "blueprint.json",
        design_system_path=state_dir / "design-system.json",
        deck_constitution_path=state_dir / "deck-constitution.json",
        layout_library_path=state_dir / "layout-library.json",
        slide_ledger_path=state_dir / "slide-ledger.json",
        asset_manifest_path=state_dir / "asset-manifest.json",
        viz_manifest_path=state_dir / "viz-manifest.json",
        output_dir=pptx_dir,
        root=state_dir,
        style_prior_provider=NullStylePriorProvider(),
        scene_validate=True,
        scene_profile=scene_profile,  # type: ignore[arg-type]
        scene_validation_mode=scene_validation_mode,  # type: ignore[arg-type]
        style_policy_path=style_policy,
        adapter_policy_path=adapter_policy,
        fixture_or_state_id="source-to-pptx-poc",
    )
    summary = _build_source_to_pptx_summary(
        source=source,
        output_dir=output_dir,
        state_dir=state_dir,
        paths=paths,
        compile_outputs=compile_outputs,
    )
    summary_path = output_dir / "source-to-pptx-summary.json"
    summary_path.write_text(_stable_json(summary) + "\n", encoding="utf-8")
    for line in summarize_experimental_scene_compile(compile_outputs):
        print(line)
    print(
        "SOURCE_TO_PPTX_POC "
        f"validation_status={paths['validation_report'].status} "
        f"bridge_findings={len(paths['bridge_outputs'].report.findings)} "
        f"renderer_path={compile_outputs.report.renderer_path} "
        f"curated_strict_status={compile_outputs.report.curated_strict_status or 'disabled'}"
    )
    print(f"WROTE {compile_outputs.scene_outputs.pptx_path}")
    print(f"WROTE {pptx_dir / 'scene-deck.json'}")
    print(f"WROTE {pptx_dir / 'scene-compile-report.json'}")
    if compile_outputs.validation_report is not None:
        print(f"WROTE {pptx_dir / 'pptx-object-report.json'}")
    print(f"WROTE {pptx_dir / 'experimental-scene-compile-report.json'}")
    print(f"WROTE {summary_path}")
    bridge_failed = any(finding.severity == "error" for finding in paths["bridge_outputs"].report.findings)
    return 1 if bridge_failed or experimental_scene_compile_failed(compile_outputs.report) else 0


def _build_source_to_state_artifacts(
    *,
    source: Path,
    design_mode: str,
    target_slides: int,
    output_dir: Path,
    repair_plan: bool = False,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_document = ingest_source_file(source)
    source_document_path = write_source_document(source_document, output_dir / "source-document.json")
    plan = plan_deck_from_source_document(
        source_document,
        design_mode=design_mode,  # type: ignore[arg-type]
        target_slide_count=target_slides,
    )
    presentation_plan_path = write_presentation_plan(plan, output_dir / "presentation-plan.json")
    validation_report = validate_presentation_plan(plan, source_document)
    validation_report_path = write_presentation_plan_validation_report(
        validation_report,
        output_dir / "presentation-plan-validation.json",
    )
    repair_result = None
    repair_report_path = None
    if repair_plan:
        repair_result = repair_presentation_plan(
            source_document=source_document,
            raw_plan=plan,
            source_document_path=str(source_document_path.resolve()),
            original_plan_path=str(presentation_plan_path.resolve()),
            policy=PresentationPlanRepairPolicy(),
        )
        repair_paths = write_repaired_plan_artifacts(
            repair_result,
            original_plan_payload=plan.model_dump(mode="json", exclude_none=True),
            output_dir=output_dir / "plan-repair",
            write_markdown=True,
        )
        repair_report_path = repair_paths["repair_report"]
        if repair_result.repaired_plan is not None:
            plan = repair_result.repaired_plan
            presentation_plan_path = repair_paths["repaired_plan"]
            validation_report = repair_result.repaired_validation_report
            validation_report_path = repair_paths["repaired_validation_report"]
    if validation_report.status == "failed":
        raise ValueError("presentation plan validation failed; refusing to build draft state")
    state_dir = output_dir / "state"
    bridge_outputs = build_state_from_presentation_plan(
        source_document=source_document,
        presentation_plan=plan,
        source_document_path=source_document_path,
        presentation_plan_path=presentation_plan_path,
        output_state_dir=state_dir,
    )
    return {
        "source_document": source_document,
        "plan": plan,
        "validation_report": validation_report,
        "bridge_outputs": bridge_outputs,
        "source_document_path": source_document_path,
        "presentation_plan_path": presentation_plan_path,
        "validation_report_path": validation_report_path,
        "state_dir": state_dir,
        "repair_result": repair_result,
        "repair_report_path": repair_report_path,
    }


def _build_source_to_state_summary(
    *,
    source: Path,
    output_dir: Path,
    source_document_path: Path,
    presentation_plan_path: Path,
    validation_report_path: Path,
    state_dir: Path,
    validation_report,
    bridge_report,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "report_version": "0.1",
        "command": "source-to-state-poc",
        "source_path": str(source.resolve()),
        "output_dir": str(output_dir.resolve()),
        "source_document_path": str(source_document_path.resolve()),
        "presentation_plan_path": str(presentation_plan_path.resolve()),
        "validation_report_path": str(validation_report_path.resolve()),
        "state_dir": str(state_dir.resolve()),
        "design_mode": bridge_report.design_mode,
        "target_slide_count": bridge_report.target_slide_count,
        "generated_slide_count": bridge_report.generated_slide_count,
        "section_count": bridge_report.section_count,
        "evidence_anchor_count": bridge_report.evidence_anchor_count,
        "validation_status": validation_report.status,
        "validation_findings": validation_report.finding_count,
        "bridge_findings": len(bridge_report.findings),
        "structural_hash": "",
    }
    return _summary_with_hash(summary)


def _build_source_to_pptx_summary(
    *,
    source: Path,
    output_dir: Path,
    state_dir: Path,
    paths: dict[str, object],
    compile_outputs,
) -> dict[str, object]:
    bridge_report = paths["bridge_outputs"].report
    validation_report = paths["validation_report"]
    summary: dict[str, object] = {
        "report_version": "0.1",
        "command": "source-to-pptx-poc",
        "source_path": str(source.resolve()),
        "output_dir": str(output_dir.resolve()),
        "state_dir": str(state_dir.resolve()),
        "pptx_dir": str((output_dir / "pptx").resolve()),
        "deck_pptx_path": compile_outputs.report.output_pptx_path,
        "scene_deck_path": compile_outputs.report.scene_deck_path,
        "scene_compile_report_path": compile_outputs.report.scene_compile_report_path,
        "object_validation_report_path": compile_outputs.report.object_validation_report_path,
        "experimental_scene_compile_report_path": compile_outputs.report_path,
        "design_mode": bridge_report.design_mode,
        "target_slide_count": bridge_report.target_slide_count,
        "generated_slide_count": bridge_report.generated_slide_count,
        "evidence_anchor_count": bridge_report.evidence_anchor_count,
        "validation_status": validation_report.status,
        "repair_report_path": str(paths["repair_report_path"].resolve()) if paths.get("repair_report_path") is not None else None,
        "repair_action_count": paths["repair_result"].repair_report.repair_action_count if paths.get("repair_result") is not None else 0,
        "repair_unresolved_finding_count": paths["repair_result"].repair_report.unresolved_finding_count if paths.get("repair_result") is not None else 0,
        "bridge_findings": len(bridge_report.findings),
        "bridge_error_count": sum(1 for finding in bridge_report.findings if finding.severity == "error"),
        "warnings_count": compile_outputs.report.warnings_count,
        "renderer_path": compile_outputs.report.renderer_path,
        "scene_profile": compile_outputs.report.scene_profile,
        "scene_validation_mode": compile_outputs.report.scene_validation_mode,
        "object_validation_status": compile_outputs.report.object_validation_status,
        "curated_strict_status": compile_outputs.report.curated_strict_status,
        "style_status": compile_outputs.report.style_status,
        "adapter_status": compile_outputs.report.adapter_status,
        "findings_count": compile_outputs.report.findings_count,
        "enforceable_count": compile_outputs.report.enforceable_count,
        "structural_hash": "",
    }
    return _summary_with_hash(summary)


def _summary_with_hash(summary: dict[str, object]) -> dict[str, object]:
    hash_payload = dict(summary)
    for key in (
        "source_path",
        "output_dir",
        "source_document_path",
        "presentation_plan_path",
        "validation_report_path",
        "state_dir",
        "pptx_dir",
        "deck_pptx_path",
        "scene_deck_path",
        "scene_compile_report_path",
        "object_validation_report_path",
        "experimental_scene_compile_report_path",
        "repair_report_path",
        "structural_hash",
    ):
        hash_payload.pop(key, None)
    summary["structural_hash"] = hashlib.sha256(_stable_json(hash_payload).encode("utf-8")).hexdigest()
    return summary


def _build_source_plan_summary(
    *,
    source: Path,
    output_dir: Path,
    source_document_path: Path,
    presentation_plan_path: Path,
    validation_report_path: Path,
    source_document,
    plan,
    validation_report,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "report_version": "0.1",
        "command": "source-plan-poc",
        "source_path": str(source.resolve()),
        "output_dir": str(output_dir.resolve()),
        "source_document_path": str(source_document_path.resolve()),
        "presentation_plan_path": str(presentation_plan_path.resolve()),
        "validation_report_path": str(validation_report_path.resolve()),
        "document_id": source_document.document_id,
        "design_mode": plan.design_mode,
        "target_slide_count": plan.target_slide_count,
        "planned_slide_count": len(plan.slides),
        "section_count": len(plan.sections),
        "source_chunk_count": len(source_document.chunks),
        "validation_status": validation_report.status,
        "finding_count": validation_report.finding_count,
        "warning_count": validation_report.warning_count,
        "error_count": validation_report.error_count,
        "structural_hash": "",
    }
    hash_payload = dict(summary)
    for key in ("source_path", "output_dir", "source_document_path", "presentation_plan_path", "validation_report_path", "structural_hash"):
        hash_payload.pop(key, None)
    summary["structural_hash"] = hashlib.sha256(_stable_json(hash_payload).encode("utf-8")).hexdigest()
    return summary


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _scan_reference_pack(
    pack: Path,
    output: Path,
    workflow_plan_path: Path | None,
    brief_context_path: Path | None,
) -> int:
    workflow_plan = None
    if workflow_plan_path is not None:
        loaded = load_state_file(workflow_plan_path)
        if loaded.schema_name != "workflow_plan":
            raise TypeError(f"expected workflow_plan for --workflow-plan, found {loaded.schema_name}")
        workflow_plan = loaded
    brief_context = load_reference_brief_context(brief_context_path) if brief_context_path is not None else None
    model = scan_reference_pack(pack, workflow_plan=workflow_plan, brief_context=brief_context)
    save_state_file(model, output)
    print(f"WROTE {output}")
    return 0


def _plan_blueprint(
    workflow_plan: Path,
    output_dir: Path,
    brief: Path | None,
    reference_dna: Path | None,
    brand_inputs: Path | None,
) -> int:
    outputs = plan_gate2_from_files(
        workflow_plan_path=workflow_plan,
        brief_path=brief,
        reference_dna_path=reference_dna,
        brand_inputs_path=brand_inputs,
    )
    written = write_gate2_outputs(outputs, output_dir)
    for schema_name in (
        "blueprint",
        "concept_graph",
        "teaching_plan",
        "blueprint_preview",
        "design_system",
        "deck_constitution",
        "layout_library",
        "slide_ledger",
        "asset_requests",
    ):
        print(f"WROTE {written[schema_name]}")
    return 0


def _evaluate_workflow(output_dir: Path) -> int:
    report = evaluate_workflow_harness(output_dir)
    report_path = write_workflow_evaluation_report(report, output_dir / "workflow-evaluation-report.json")
    print(f"WROTE {report_path}")
    return 0


def _summarize_governance(qa_governance_path: Path) -> int:
    governance = load_state_file(qa_governance_path)
    if governance.schema_name != "qa_governance":
        raise TypeError(f"expected qa_governance, found {governance.schema_name}")
    summary = governance.summary
    print(
        "GOVERNANCE "
        f"posture={summary.release_readiness_posture.value} "
        f"total_findings={summary.total_findings} "
        f"unresolved={summary.unresolved_findings} "
        f"remediated={summary.remediated_findings} "
        f"waived={summary.waived_findings} "
        f"accepted_risk={summary.accepted_risk_findings} "
        f"blocking_open={summary.blocking_findings_still_open}"
    )
    print(
        "GOVERNANCE_ISSUES "
        f"expired_waivers={summary.expired_waiver_count} "
        f"orphan_waivers={summary.orphan_waiver_count} "
        f"orphan_remediations={summary.orphan_remediation_count} "
        f"remediation_mismatches={summary.remediation_mismatch_count} "
        f"operator_exceptions={summary.depends_on_operator_exceptions} "
        f"qa_improvement_source={summary.qa_improvement_source}"
    )
    return 0


def _summarize_ship_readiness(ship_readiness_report_path: Path) -> int:
    report = load_state_file(ship_readiness_report_path)
    if report.schema_name != "ship_readiness_report":
        raise TypeError(f"expected ship_readiness_report, found {report.schema_name}")
    readiness = report.release_readiness
    print(
        "SHIP_READINESS "
        f"decision={report.decision.value} "
        f"ship_ready={readiness.ship_ready} "
        f"release_posture={readiness.release_posture.value} "
        f"operator_exception_dependency={readiness.operator_exception_dependency} "
        f"blocking_open={readiness.blocking_findings_open_count}"
    )
    print(
        "SHIP_READINESS_ISSUES "
        f"waived={readiness.waived_findings_count} "
        f"accepted_risk={readiness.accepted_risk_count} "
        f"remediated={readiness.remediated_findings_count} "
        f"expired_waivers={readiness.expired_waiver_count} "
        f"orphan_waivers={readiness.orphan_waiver_count} "
        f"orphan_remediations={readiness.orphan_remediation_count} "
        f"remediation_mismatches={readiness.remediation_mismatch_count}"
    )
    print(f"REASON {readiness.rationale_summary}")
    return 0


def _run_document_crop(
    asset_requests: Path,
    slide_ledger: Path,
    output_dir: Path,
    asset_manifest: Path | None,
    dpi: int,
    max_candidates_per_source: int,
    max_review_rounds: int,
) -> int:
    outputs = run_document_asset_crop_from_files(
        asset_requests_path=asset_requests,
        slide_ledger_path=slide_ledger,
        asset_manifest_path=asset_manifest,
        output_dir=output_dir,
        dpi=dpi,
        max_candidates_per_source=max_candidates_per_source,
        max_review_rounds=max_review_rounds,
        root=_artifact_root_for_cli(output_dir),
    )
    written = write_document_crop_outputs(outputs, output_dir)
    for schema_name in (
        "crop_candidates",
        "crop_review_inputs",
        "crop_review_decisions",
        "selected_crops",
        "asset_manifest",
        "slide_ledger",
    ):
        print(f"WROTE {written[schema_name]}")
    return 0


def _review_document_crops(
    asset_requests: Path,
    slide_ledger: Path,
    crop_candidates: Path,
    asset_manifest: Path,
    output_dir: Path,
    crop_review_inputs: Path | None,
    crop_review_decisions: Path | None,
    selected_crops: Path | None,
    max_review_rounds: int,
) -> int:
    outputs = run_document_crop_review_from_files(
        asset_requests_path=asset_requests,
        slide_ledger_path=slide_ledger,
        crop_candidates_path=crop_candidates,
        asset_manifest_path=asset_manifest,
        output_dir=output_dir,
        crop_review_inputs_path=crop_review_inputs,
        crop_review_decisions_path=crop_review_decisions,
        selected_crops_path=selected_crops,
        max_review_rounds=max_review_rounds,
        root=_artifact_root_for_cli(output_dir),
    )
    written = write_document_crop_outputs(outputs, output_dir)
    for schema_name in (
        "crop_candidates",
        "crop_review_inputs",
        "crop_review_decisions",
        "selected_crops",
        "asset_manifest",
        "slide_ledger",
    ):
        print(f"WROTE {written[schema_name]}")
    return 0


def _prepare_production_handoff(
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    slide_ledger: Path,
    output_dir: Path,
    asset_requests: Path | None,
) -> int:
    outputs = derive_assets_from_files(
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        slide_ledger_path=slide_ledger,
        asset_requests_path=asset_requests,
    )
    written = write_asset_derivation_outputs(outputs, output_dir)
    for schema_name in ("asset_requests", "viz_spec", "slide_ledger"):
        print(f"WROTE {written[schema_name]}")
    return 0


def _run_structured_visuals(
    viz_spec: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    slide_ledger: Path,
    output_dir: Path,
    asset_requests: Path | None,
    asset_manifest: Path | None,
    viz_manifest: Path | None,
) -> int:
    outputs = run_structured_visuals_from_files(
        viz_spec_path=viz_spec,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        slide_ledger_path=slide_ledger,
        output_dir=output_dir,
        asset_requests_path=asset_requests,
        asset_manifest_path=asset_manifest,
        viz_manifest_path=viz_manifest,
        root=_artifact_root_for_cli(output_dir),
    )
    written = write_structured_visual_outputs(outputs, output_dir)
    for schema_name in ("viz_manifest", "asset_manifest", "slide_ledger"):
        print(f"WROTE {written[schema_name]}")
    return 0


def _compile_pptx(
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    slide_ledger: Path,
    asset_manifest: Path,
    viz_manifest: Path,
    output_dir: Path,
    batch_manifest: Path | None,
    state_capsule: Path | None,
    notes: Path | None,
    pptx_name: str,
    disable_layout_critic: bool,
    root: Path | None,
    experimental_scene_renderer: bool,
    scene_validate: bool,
    scene_profile: str,
    scene_validation_mode: str,
    style_policy: Path | None,
    adapter_policy: Path | None,
) -> int:
    if experimental_scene_renderer:
        outputs = compile_pptx_with_experimental_scene_renderer(
            blueprint_path=blueprint,
            design_system_path=design_system,
            deck_constitution_path=deck_constitution,
            layout_library_path=layout_library,
            slide_ledger_path=slide_ledger,
            asset_manifest_path=asset_manifest,
            viz_manifest_path=viz_manifest,
            output_dir=output_dir,
            root=root,
            pptx_name=pptx_name,
            enable_layout_critic=not disable_layout_critic,
            scene_validate=scene_validate,
            scene_profile=scene_profile,  # type: ignore[arg-type]
            scene_validation_mode=scene_validation_mode,  # type: ignore[arg-type]
            style_policy_path=style_policy,
            adapter_policy_path=adapter_policy,
        )
        for line in summarize_experimental_scene_compile(outputs):
            print(line)
        print(f"WROTE {outputs.scene_outputs.pptx_path}")
        print(f"WROTE {output_dir / 'scene-deck.json'}")
        print(f"WROTE {output_dir / 'scene-compile-report.json'}")
        if outputs.validation_report is not None:
            print(f"WROTE {output_dir / 'pptx-object-report.json'}")
        print(f"WROTE {output_dir / 'experimental-scene-compile-report.json'}")
        return 1 if experimental_scene_compile_failed(outputs.report) else 0

    outputs = compile_pptx_from_files(
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        slide_ledger_path=slide_ledger,
        asset_manifest_path=asset_manifest,
        viz_manifest_path=viz_manifest,
        output_dir=output_dir,
        batch_manifest_path=batch_manifest,
        state_capsule_path=state_capsule,
        notes_path=notes,
        pptx_name=pptx_name,
        enable_layout_critic=not disable_layout_critic,
        root=root,
    )
    written = write_pptx_compile_outputs(outputs, output_dir)
    print(f"WROTE {outputs.pptx_path}")
    for schema_name in ("build_manifest", "slide_build_linkage", "slide_ledger"):
        print(f"WROTE {written[schema_name]}")
    if "layout_critic_report" in written:
        print(f"WROTE {written['layout_critic_report']}")
    if "batch_manifest" in written:
        print(f"WROTE {written['batch_manifest']}")
    if "state_capsule" in written:
        print(f"WROTE {written['state_capsule']}")
    return 0


def _inspect_scene_deck(
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    slide_ledger: Path,
    asset_manifest: Path,
    viz_manifest: Path,
    output: Path,
    disable_layout_critic: bool,
) -> int:
    slide_ir = adapt_blueprint_to_slide_ir(
        blueprint=load_state_file(blueprint),
        design_system=load_state_file(design_system),
        deck_constitution=load_state_file(deck_constitution),
        layout_library=load_state_file(layout_library),
        slide_ledger=load_state_file(slide_ledger),
        asset_manifest=load_state_file(asset_manifest),
        viz_manifest=load_state_file(viz_manifest),
        enable_layout_critic=not disable_layout_critic,
    )
    scene_deck = adapt_slide_ir_document_to_scene_deck(slide_ir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(scene_deck_to_stable_json(scene_deck) + "\n", encoding="utf-8")
    for line in summarize_scene_deck_adapter(scene_deck):
        print(line)
    print(f"WROTE {output}")
    return 0


def _validate_pptx_objects(
    pptx: Path,
    output: Path,
    scene_deck: Path | None,
    mode: str,
    profile: str,
) -> int:
    report = validate_pptx_objects_from_files(
        pptx_path=pptx,
        scene_deck_path=scene_deck,
        mode=mode,  # type: ignore[arg-type]
        profile=profile,  # type: ignore[arg-type]
    )
    report_path = write_pptx_object_validation_report(report, output)
    for line in summarize_pptx_object_validation(report):
        print(line)
    print(f"WROTE {report_path}")
    return 1 if report.mode_result == "failed" else 0


def _scene_readiness_gate(
    manifest: Path,
    output_dir: Path,
    fixture: list[str] | None,
    mode: str,
    profile: str,
    screenshots: bool,
    screenshot_mode: str,
    screenshot_exporter: str,
    screenshot_output_format: str,
    visual_diff: bool,
    visual_baseline_dir: Path | None,
    update_visual_baselines: bool,
    visual_mode: str,
    visual_threshold: str,
    require_visual_baselines: bool,
    write_diff_images: bool,
    visual_policy: Path | None,
    style_policy: Path | None,
    style_profile: str | None,
    enforce_style_policy: bool,
    adapter_policy: Path | None,
    adapter_profile: str | None,
    enforce_adapter_policy: bool,
) -> int:
    report = run_scene_readiness_gate_from_file(
        manifest_path=manifest,
        output_dir=output_dir,
        fixture_ids=fixture,
        mode=mode,  # type: ignore[arg-type]
        profile=profile,  # type: ignore[arg-type]
        screenshots=screenshots,
        screenshot_mode=screenshot_mode,  # type: ignore[arg-type]
        screenshot_exporter=screenshot_exporter,  # type: ignore[arg-type]
        screenshot_output_format=screenshot_output_format,  # type: ignore[arg-type]
        visual_diff=visual_diff,
        visual_baseline_dir=visual_baseline_dir,
        update_visual_baselines_flag=update_visual_baselines,
        visual_mode=visual_mode,  # type: ignore[arg-type]
        visual_threshold=visual_threshold,  # type: ignore[arg-type]
        require_visual_baselines=require_visual_baselines,
        write_diff_images=write_diff_images,
        visual_policy_path=visual_policy,
        style_policy_path=style_policy,
        style_profile=style_profile,
        enforce_style_policy=enforce_style_policy,
        adapter_policy_path=adapter_policy,
        adapter_profile=adapter_profile,
        enforce_adapter_policy=enforce_adapter_policy,
    )
    report_path = write_scene_readiness_report(report, output_dir / "scene-readiness-report.json")
    for line in summarize_scene_readiness_report(report):
        print(line)
    print(f"WROTE {report_path}")
    return 1 if report.mode_result == "failed" else 0


def _scene_migration_readiness(
    artifacts_root: Path,
    output: Path,
    previous_report: Path | None,
    markdown: Path | None,
) -> int:
    report = build_scene_migration_readiness_report(
        artifacts_root=artifacts_root,
        previous_report_path=previous_report,
    )
    report_path, markdown_path = write_migration_readiness_artifacts(
        report,
        output_path=output,
        markdown_path=markdown,
    )
    for line in summarize_scene_migration_readiness_report(report):
        print(line)
    print(f"WROTE {report_path}")
    if markdown_path is not None:
        print(f"WROTE {markdown_path}")
    return 1 if report.default_migration_recommendation in {"no_go", "not_yet"} else 0


def _scene_migration_history(
    current_report: Path,
    previous_report: Path | None,
    output: Path,
    markdown: Path | None,
) -> int:
    report = build_scene_migration_history(
        current_report_path=current_report,
        previous_report_path=previous_report,
    )
    report, report_path, markdown_path = write_scene_migration_history_artifacts(
        report,
        output_path=output,
        markdown_path=markdown,
    )
    for line in summarize_scene_migration_history_report(report):
        print(line)
    print(f"WROTE {report_path}")
    if markdown_path is not None:
        print(f"WROTE {markdown_path}")
    return 0


def _default_vs_scene_poc(
    manifest: Path,
    output_dir: Path,
    style_policy: Path | None,
    adapter_policy: Path | None,
    fixture: list[str] | None,
    write_markdown: bool,
) -> int:
    report = run_default_vs_scene_poc(
        manifest_path=manifest,
        output_dir=output_dir,
        style_policy_path=style_policy,
        adapter_policy_path=adapter_policy,
        fixture_ids=fixture,
        write_markdown=write_markdown,
    )
    for line in summarize_default_vs_scene_report(report):
        print(line)
    print(f"WROTE {output_dir / 'default-vs-scene-report.json'}")
    if write_markdown:
        print(f"WROTE {output_dir / 'default-vs-scene-summary.md'}")
    return 1 if report.recommendation in {"no_go", "not_yet"} else 0


def _compile_scene_pptx(
    scene_deck: Path,
    output_dir: Path,
    root: Path | None,
    pptx_name: str,
) -> int:
    outputs = compile_pptx_from_scene_deck_file(
        scene_deck_path=scene_deck,
        output_dir=output_dir,
        root=root,
        pptx_name=pptx_name,
    )
    report_path = write_scene_pptx_compile_report(outputs.report, output_dir / "scene-compile-report.json")
    for line in summarize_scene_pptx_compile(outputs.report):
        print(line)
    print(f"WROTE {outputs.pptx_path}")
    print(f"WROTE {report_path}")
    return 0


def _qa_deck(
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    slide_ledger: Path,
    asset_manifest: Path,
    viz_manifest: Path,
    build_manifest: Path,
    slide_build_linkage: Path,
    output_dir: Path,
    state_capsule: Path | None,
    prior_report: Path | None,
    qa_governance: Path | None,
) -> int:
    outputs = run_deck_qa_from_files(
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        slide_ledger_path=slide_ledger,
        asset_manifest_path=asset_manifest,
        viz_manifest_path=viz_manifest,
        build_manifest_path=build_manifest,
        slide_build_linkage_path=slide_build_linkage,
        state_capsule_path=state_capsule,
        prior_report_path=prior_report,
        qa_governance_path=qa_governance,
        artifact_root=Path.cwd(),
    )
    written = write_deck_qa_outputs(outputs, output_dir)
    for schema_name in ("qa_report", "slide_ledger", "slide_build_linkage"):
        print(f"WROTE {written[schema_name]}")
    if "qa_governance" in written:
        print(f"WROTE {written['qa_governance']}")
    if outputs.qa_governance is not None:
        summary = outputs.qa_governance.summary
        print(
            "GOVERNANCE "
            f"posture={summary.release_readiness_posture.value} "
            f"blocking_open={summary.blocking_findings_still_open} "
            f"waived={summary.waived_findings} "
            f"remediated={summary.remediated_findings}"
        )
    if "state_capsule" in written:
        print(f"WROTE {written['state_capsule']}")
    return 0


def _orchestrate_large_deck(
    workflow_plan: Path,
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    slide_ledger: Path,
    build_manifest: Path | None,
    slide_build_linkage: Path | None,
    qa_report: Path | None,
    output_dir: Path,
) -> int:
    outputs = orchestrate_large_deck_from_files(
        workflow_plan_path=workflow_plan,
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        slide_ledger_path=slide_ledger,
        build_manifest_path=build_manifest,
        slide_build_linkage_path=slide_build_linkage,
        qa_report_path=qa_report,
        pointer_root=output_dir.as_posix(),
        canonical_state_root=output_dir.as_posix(),
    )
    written = write_large_deck_outputs(outputs, output_dir)
    for schema_name in ("batch_manifest", "context_lock", "handoff_packet", "state_capsule", "remediation_plan", "slide_ledger"):
        print(f"WROTE {written[schema_name]}")
    if "slide_build_linkage" in written:
        print(f"WROTE {written['slide_build_linkage']}")
    return 0


def _apply_remediation(
    remediation_plan: Path,
    batch_manifest: Path,
    context_lock: Path,
    state_capsule: Path,
    slide_ledger: Path,
    slide_build_linkage: Path,
    qa_report: Path,
    build_manifest: Path,
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    asset_manifest: Path,
    viz_manifest: Path,
    output_dir: Path,
    workflow_plan: Path | None,
    handoff_packet: Path | None,
    asset_requests: Path | None,
    viz_spec: Path | None,
    notes: Path | None,
    build_output_dir: Path | None,
    visual_output_dir: Path | None,
) -> int:
    outputs = apply_bounded_remediation_from_files(
        remediation_plan_path=remediation_plan,
        batch_manifest_path=batch_manifest,
        context_lock_path=context_lock,
        state_capsule_path=state_capsule,
        slide_ledger_path=slide_ledger,
        slide_build_linkage_path=slide_build_linkage,
        qa_report_path=qa_report,
        build_manifest_path=build_manifest,
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        asset_manifest_path=asset_manifest,
        viz_manifest_path=viz_manifest,
        workflow_plan_path=workflow_plan,
        handoff_packet_path=handoff_packet,
        asset_requests_path=asset_requests,
        viz_spec_path=viz_spec,
        notes_path=notes,
        artifact_root=Path.cwd(),
        state_output_dir=output_dir,
        build_output_dir=build_output_dir or output_dir,
        visual_output_dir=visual_output_dir or output_dir,
    )
    written = write_remediation_execution_outputs(
        outputs,
        output_dir,
        build_output_dir=build_output_dir or output_dir,
    )
    ordered = (
        "remediation_execution_report",
        "qa_report",
        "slide_ledger",
        "build_manifest",
        "slide_build_linkage",
        "batch_manifest",
        "context_lock",
        "handoff_packet",
        "state_capsule",
        "remediation_plan",
        "asset_manifest",
        "viz_manifest",
    )
    for schema_name in ordered:
        if schema_name in written:
            print(f"WROTE {written[schema_name]}")
    if "pptx" in written:
        print(f"WROTE {written['pptx']}")
    return 0


def _author_upstream_fixes(
    remediation_plan: Path,
    remediation_execution_report: Path,
    batch_manifest: Path,
    context_lock: Path,
    handoff_packet: Path,
    state_capsule: Path,
    slide_ledger: Path,
    slide_build_linkage: Path,
    qa_report: Path,
    build_manifest: Path,
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    asset_manifest: Path,
    viz_manifest: Path,
    output_dir: Path,
    asset_requests: Path | None,
    viz_spec: Path | None,
) -> int:
    outputs = author_upstream_fixes_from_files(
        remediation_plan_path=remediation_plan,
        remediation_execution_report_path=remediation_execution_report,
        batch_manifest_path=batch_manifest,
        context_lock_path=context_lock,
        handoff_packet_path=handoff_packet,
        state_capsule_path=state_capsule,
        slide_ledger_path=slide_ledger,
        slide_build_linkage_path=slide_build_linkage,
        qa_report_path=qa_report,
        build_manifest_path=build_manifest,
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        asset_manifest_path=asset_manifest,
        viz_manifest_path=viz_manifest,
        asset_requests_path=asset_requests,
        viz_spec_path=viz_spec,
        pointer_root=output_dir.as_posix(),
    )
    written = write_upstream_fix_outputs(outputs, output_dir)
    for schema_name in ("upstream_fix_plan", "approval_packet", "authoring_deltas", "state_capsule", "handoff_packet"):
        print(f"WROTE {written[schema_name]}")
    return 0


def _apply_approved_fixes(
    approval_packet: Path,
    authoring_deltas: Path,
    upstream_fix_plan: Path,
    remediation_plan: Path,
    remediation_execution_report: Path,
    batch_manifest: Path,
    context_lock: Path,
    state_capsule: Path,
    slide_ledger: Path,
    slide_build_linkage: Path,
    qa_report: Path,
    build_manifest: Path,
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    asset_manifest: Path,
    viz_manifest: Path,
    output_dir: Path,
    handoff_packet: Path | None,
    workflow_plan: Path | None,
    asset_requests: Path | None,
    viz_spec: Path | None,
    approve_packet_id: list[str] | None,
    approve_fix_id: list[str] | None,
    select_option: list[str] | None,
    artifact_root: Path | None,
    build_output_dir: Path | None,
    asset_output_dir: Path | None,
    visual_output_dir: Path | None,
    notes: Path | None,
) -> int:
    outputs = apply_approved_fixes_from_files(
        approval_packet_path=approval_packet,
        authoring_deltas_path=authoring_deltas,
        upstream_fix_plan_path=upstream_fix_plan,
        remediation_plan_path=remediation_plan,
        remediation_execution_report_path=remediation_execution_report,
        batch_manifest_path=batch_manifest,
        context_lock_path=context_lock,
        state_capsule_path=state_capsule,
        slide_ledger_path=slide_ledger,
        slide_build_linkage_path=slide_build_linkage,
        qa_report_path=qa_report,
        build_manifest_path=build_manifest,
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        asset_manifest_path=asset_manifest,
        viz_manifest_path=viz_manifest,
        handoff_packet_path=handoff_packet,
        workflow_plan_path=workflow_plan,
        asset_requests_path=asset_requests,
        viz_spec_path=viz_spec,
        approved_packet_ids=approve_packet_id,
        approved_fix_ids=approve_fix_id,
        selected_delta_options=_parse_delta_option_args(select_option),
        artifact_root=artifact_root,
        state_output_dir=output_dir,
        build_output_dir=build_output_dir,
        asset_output_dir=asset_output_dir,
        visual_output_dir=visual_output_dir,
        notes_path=notes,
    )
    written = write_approved_apply_outputs(
        outputs,
        output_dir,
        build_output_dir=build_output_dir,
    )
    ordered = (
        "approved_apply_report",
        "blueprint",
        "design_system",
        "deck_constitution",
        "layout_library",
        "asset_requests",
        "viz_spec",
        "asset_manifest",
        "viz_manifest",
        "qa_report",
        "slide_ledger",
        "batch_manifest",
        "context_lock",
        "handoff_packet",
        "state_capsule",
        "remediation_plan",
        "upstream_fix_plan",
        "approval_packet",
        "authoring_deltas",
        "build_manifest",
        "slide_build_linkage",
    )
    for schema_name in ordered:
        if schema_name in written:
            print(f"WROTE {written[schema_name]}")
    if "pptx" in written:
        print(f"WROTE {written['pptx']}")
    return 0


def _close_approved_fixes(
    approved_apply_report: Path,
    approval_packet: Path,
    authoring_deltas: Path,
    upstream_fix_plan: Path,
    remediation_plan: Path,
    remediation_execution_report: Path,
    batch_manifest: Path,
    context_lock: Path,
    handoff_packet: Path,
    state_capsule: Path,
    slide_ledger: Path,
    slide_build_linkage: Path,
    qa_report: Path,
    build_manifest: Path,
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    asset_manifest: Path,
    viz_manifest: Path,
    output_dir: Path,
    asset_requests: Path | None,
    viz_spec: Path | None,
    pointer_root: str | None,
) -> int:
    outputs = close_approved_fixes_from_files(
        approved_apply_report_path=approved_apply_report,
        approval_packet_path=approval_packet,
        authoring_deltas_path=authoring_deltas,
        upstream_fix_plan_path=upstream_fix_plan,
        remediation_plan_path=remediation_plan,
        remediation_execution_report_path=remediation_execution_report,
        batch_manifest_path=batch_manifest,
        context_lock_path=context_lock,
        handoff_packet_path=handoff_packet,
        state_capsule_path=state_capsule,
        slide_ledger_path=slide_ledger,
        slide_build_linkage_path=slide_build_linkage,
        qa_report_path=qa_report,
        build_manifest_path=build_manifest,
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        asset_manifest_path=asset_manifest,
        viz_manifest_path=viz_manifest,
        asset_requests_path=asset_requests,
        viz_spec_path=viz_spec,
        pointer_root=pointer_root,
    )
    written = write_post_apply_closure_outputs(outputs, output_dir)
    for schema_name in (
        "closure_report",
        "remaining_backlog",
        "approval_packet",
        "authoring_deltas",
        "upstream_fix_plan",
        "state_capsule",
        "handoff_packet",
    ):
        if schema_name in written:
            print(f"WROTE {written[schema_name]}")
    return 0


def _assess_ship_readiness(
    closure_report: Path,
    remaining_backlog: Path,
    approval_packet: Path,
    authoring_deltas: Path,
    upstream_fix_plan: Path,
    approved_apply_report: Path,
    remediation_plan: Path,
    remediation_execution_report: Path,
    batch_manifest: Path,
    context_lock: Path,
    handoff_packet: Path,
    state_capsule: Path,
    slide_ledger: Path,
    slide_build_linkage: Path,
    qa_report: Path,
    qa_governance: Path,
    build_manifest: Path,
    blueprint: Path,
    design_system: Path,
    deck_constitution: Path,
    layout_library: Path,
    asset_manifest: Path,
    viz_manifest: Path,
    output_dir: Path,
    artifact_root: Path | None,
) -> int:
    outputs = assess_ship_readiness_from_files(
        closure_report_path=closure_report,
        remaining_backlog_path=remaining_backlog,
        approval_packet_path=approval_packet,
        authoring_deltas_path=authoring_deltas,
        upstream_fix_plan_path=upstream_fix_plan,
        approved_apply_report_path=approved_apply_report,
        remediation_plan_path=remediation_plan,
        remediation_execution_report_path=remediation_execution_report,
        batch_manifest_path=batch_manifest,
        context_lock_path=context_lock,
        handoff_packet_path=handoff_packet,
        state_capsule_path=state_capsule,
        slide_ledger_path=slide_ledger,
        slide_build_linkage_path=slide_build_linkage,
        qa_report_path=qa_report,
        qa_governance_path=qa_governance,
        build_manifest_path=build_manifest,
        blueprint_path=blueprint,
        design_system_path=design_system,
        deck_constitution_path=deck_constitution,
        layout_library_path=layout_library,
        asset_manifest_path=asset_manifest,
        viz_manifest_path=viz_manifest,
        artifact_root=artifact_root,
        state_output_dir=output_dir,
    )
    written = write_ship_readiness_outputs(outputs, output_dir)
    for schema_name in ("ship_readiness_report", "cycle_reset_plan", "state_capsule", "handoff_packet"):
        if schema_name in written:
            print(f"WROTE {written[schema_name]}")
    if "release_candidate" in written:
        print(f"WROTE {written['release_candidate']}")
    readiness = outputs.ship_readiness_report.release_readiness
    print(
        "SHIP_READINESS "
        f"ship_ready={readiness.ship_ready} "
        f"release_posture={readiness.release_posture.value} "
        f"operator_exception_dependency={readiness.operator_exception_dependency}"
    )
    return 0


def _evaluate_reviewed_surrogate_policy(
    gate_artifact: Path,
    registry: Path,
    target_id: str,
    context: str,
    output_dir: Path,
    context_root: Path | None,
) -> int:
    outputs = evaluate_reviewed_surrogate_policy(
        gate_artifact_path=gate_artifact,
        registry_path=registry,
        target_id=target_id,
        context=context,
        context_root=context_root,
    )
    written = write_reviewed_surrogate_policy_reports(outputs, output_dir)
    for policy_context, report_path in written.items():
        print(f"WROTE {report_path}")
        report = outputs[policy_context]
        print(f"{policy_context}: decision={report.policy_decision.value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="State contract utilities for the presentation agent repository.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summary", help="Print top-level schema summaries.")
    summary_parser.add_argument("--schema", choices=list(SCHEMA_REGISTRY), help="Print details for one schema.")

    validate_parser = subparsers.add_parser("validate", help="Validate one or more state files or directories.")
    validate_parser.add_argument("paths", nargs="+", type=Path)

    generate_parser = subparsers.add_parser("generate", help="Generate empty or sample state files.")
    generate_parser.add_argument("--schema", required=True, choices=["all", *SCHEMA_REGISTRY.keys()])
    generate_parser.add_argument("--mode", default="sample", choices=["empty", "sample"])
    generate_parser.add_argument("--output", required=True, type=Path)

    plan_parser = subparsers.add_parser("plan-workflow", help="Generate a workflow_plan from a brief file.")
    plan_parser.add_argument("--brief", required=True, type=Path)
    plan_parser.add_argument("--output", required=True, type=Path)

    ingest_source_parser = subparsers.add_parser(
        "ingest-source",
        help="Ingest a local .txt, .md, .pdf, or .docx source into deterministic source-document JSON.",
    )
    ingest_source_parser.add_argument("--source", required=True, type=Path)
    ingest_source_parser.add_argument("--output", required=True, type=Path)

    source_plan_parser = subparsers.add_parser(
        "plan-deck-from-source",
        help="Build a deterministic PresentationPlan JSON from a source-document artifact.",
    )
    source_plan_parser.add_argument("--source-document", dest="source_document", required=True, type=Path)
    source_plan_parser.add_argument("--design-mode", dest="design_mode", required=True, choices=["academic", "professional", "creative"])
    source_plan_parser.add_argument("--target-slides", dest="target_slides", required=True, type=int)
    source_plan_parser.add_argument("--output", required=True, type=Path)
    source_plan_parser.add_argument("--validation-output", dest="validation_output", required=True, type=Path)

    source_plan_poc_parser = subparsers.add_parser(
        "source-plan-poc",
        help="Run local source ingestion, deterministic deck planning, and plan validation without compiling PPTX.",
    )
    source_plan_poc_parser.add_argument("--source", required=True, type=Path)
    source_plan_poc_parser.add_argument("--design-mode", dest="design_mode", required=True, choices=["academic", "professional", "creative"])
    source_plan_poc_parser.add_argument("--target-slides", dest="target_slides", required=True, type=int)
    source_plan_poc_parser.add_argument("--output-dir", required=True, type=Path)

    build_state_from_plan_parser = subparsers.add_parser(
        "build-state-from-plan",
        help="Convert a validated PresentationPlan and SourceDocument into local draft state artifacts.",
    )
    build_state_from_plan_parser.add_argument("--source-document", dest="source_document", required=True, type=Path)
    build_state_from_plan_parser.add_argument("--presentation-plan", dest="presentation_plan", required=True, type=Path)
    build_state_from_plan_parser.add_argument("--output-state-dir", dest="output_state_dir", required=True, type=Path)

    repair_plan_parser = subparsers.add_parser(
        "repair-presentation-plan",
        help="Repair a local PresentationPlan deterministically against a SourceDocument.",
    )
    repair_plan_parser.add_argument("--source-document", dest="source_document", required=True, type=Path)
    repair_plan_parser.add_argument("--presentation-plan", dest="presentation_plan", required=True, type=Path)
    repair_plan_parser.add_argument("--output-dir", required=True, type=Path)
    repair_plan_parser.add_argument("--write-markdown", action="store_true", help="Write presentation-plan-repair-summary.md.")

    validate_repair_parser = subparsers.add_parser(
        "validate-repair-presentation-plan",
        help="Validate and repair a local PresentationPlan using the conservative deterministic policy.",
    )
    validate_repair_parser.add_argument("--source-document", dest="source_document", required=True, type=Path)
    validate_repair_parser.add_argument("--presentation-plan", dest="presentation_plan", required=True, type=Path)
    validate_repair_parser.add_argument("--output-dir", required=True, type=Path)
    validate_repair_parser.add_argument("--policy", default="conservative", choices=["conservative"])
    validate_repair_parser.add_argument("--write-markdown", action="store_true", help="Write presentation-plan-repair-summary.md.")

    source_to_state_parser = subparsers.add_parser(
        "source-to-state-poc",
        help="Run local source ingestion, deterministic planning, validation, and draft state bridge.",
    )
    source_to_state_parser.add_argument("--source", required=True, type=Path)
    source_to_state_parser.add_argument("--design-mode", dest="design_mode", required=True, choices=["academic", "professional", "creative"])
    source_to_state_parser.add_argument("--target-slides", dest="target_slides", required=True, type=int)
    source_to_state_parser.add_argument("--output-dir", required=True, type=Path)

    source_to_pptx_parser = subparsers.add_parser(
        "source-to-pptx-poc",
        help="Run the local source-to-state bridge and explicitly flagged experimental SceneDeck PPTX compile path.",
    )
    source_to_pptx_parser.add_argument("--source", required=True, type=Path)
    source_to_pptx_parser.add_argument("--design-mode", dest="design_mode", required=True, choices=["academic", "professional", "creative"])
    source_to_pptx_parser.add_argument("--target-slides", dest="target_slides", required=True, type=int)
    source_to_pptx_parser.add_argument("--output-dir", required=True, type=Path)
    source_to_pptx_parser.add_argument(
        "--experimental-scene-renderer",
        action="store_true",
        help="Required experimental opt-in; source-to-pptx-poc never changes default compile-pptx routing.",
    )
    source_to_pptx_parser.add_argument(
        "--scene-profile",
        default="curated-strict",
        choices=["none", "scene-strict", "curated-strict"],
        help="Optional scene validation profile attached to the experimental scene compile.",
    )
    source_to_pptx_parser.add_argument(
        "--scene-validation-mode",
        default="enforce",
        choices=["inspect", "warn", "enforce"],
        help="Validation mode for the experimental scene compile postflight.",
    )
    source_to_pptx_parser.add_argument("--style-policy", type=Path, help="Optional style policy for curated-strict source-to-PPTX POC.")
    source_to_pptx_parser.add_argument("--adapter-policy", type=Path, help="Optional adapter policy for curated-strict source-to-PPTX POC.")
    source_to_pptx_parser.add_argument("--repair-plan", action="store_true", help="Run the deterministic PresentationPlan repair loop before bridging to state.")

    scan_parser = subparsers.add_parser("scan-reference-pack", help="Scan a local reference pack into reference_dna.")
    scan_parser.add_argument("--pack", required=True, type=Path)
    scan_parser.add_argument("--output", required=True, type=Path)
    scan_parser.add_argument("--workflow-plan", dest="workflow_plan", type=Path)
    scan_parser.add_argument("--brief-context", dest="brief_context", type=Path)

    blueprint_parser = subparsers.add_parser(
        "plan-blueprint",
        help="Generate Gate 2 blueprint, design-system, constitution, layout, ledger, and asset-request artifacts.",
    )
    blueprint_parser.add_argument("--workflow-plan", dest="workflow_plan", required=True, type=Path)
    blueprint_parser.add_argument("--output-dir", required=True, type=Path)
    blueprint_parser.add_argument("--brief", type=Path)
    blueprint_parser.add_argument("--reference-dna", dest="reference_dna", type=Path)
    blueprint_parser.add_argument("--brand-inputs", dest="brand_inputs", type=Path)

    evaluation_parser = subparsers.add_parser(
        "evaluate-workflow",
        help="Run the fixed-brief workflow robustness harness across Gate 1, Gate 2, compile, and QA.",
    )
    evaluation_parser.add_argument("--output-dir", required=True, type=Path)

    governance_parser = subparsers.add_parser(
        "summarize-governance",
        help="Print the persisted waiver/remediation posture from a qa-governance artifact.",
    )
    governance_parser.add_argument("--qa-governance", dest="qa_governance", required=True, type=Path)

    ship_summary_parser = subparsers.add_parser(
        "summarize-ship-readiness",
        help="Print the persisted release posture from a ship-readiness report.",
    )
    ship_summary_parser.add_argument("--ship-readiness-report", dest="ship_readiness_report", required=True, type=Path)

    crop_parser = subparsers.add_parser(
        "crop-document-assets",
        help="Render local source documents, generate crop candidates, normalize reusable assets, and write downstream manifests.",
    )
    crop_parser.add_argument("--asset-requests", dest="asset_requests", required=True, type=Path)
    crop_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    crop_parser.add_argument("--output-dir", required=True, type=Path)
    crop_parser.add_argument("--asset-manifest", dest="asset_manifest", type=Path)
    crop_parser.add_argument("--dpi", type=int, default=144)
    crop_parser.add_argument("--max-candidates-per-source", dest="max_candidates_per_source", type=int, default=6)
    crop_parser.add_argument(
        "--max-review-rounds",
        dest="max_review_rounds",
        type=int,
        default=2,
        help="Compatibility flag for the later review phase; accepted values stay within 0 to 2, but the extraction worker ignores this setting.",
    )

    review_parser = subparsers.add_parser(
        "review-crops",
        help="Run the bounded crop review loop, promote accepted crops, and synchronize crop manifests.",
    )
    review_parser.add_argument("--asset-requests", dest="asset_requests", required=True, type=Path)
    review_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    review_parser.add_argument("--crop-candidates", dest="crop_candidates", required=True, type=Path)
    review_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    review_parser.add_argument("--output-dir", required=True, type=Path)
    review_parser.add_argument("--crop-review-inputs", dest="crop_review_inputs", type=Path)
    review_parser.add_argument("--crop-review-decisions", dest="crop_review_decisions", type=Path)
    review_parser.add_argument("--selected-crops", dest="selected_crops", type=Path)
    review_parser.add_argument(
        "--max-review-rounds",
        dest="max_review_rounds",
        type=int,
        default=2,
        help="Bounded crop review loop limit (0-2). Use 0 to skip reviewer calls and terminate deterministically with the current candidate.",
    )

    handoff_parser = subparsers.add_parser(
        "prepare-production-handoff",
        help="Normalize Gate 2 asset requests, generate viz-spec handoff state, and synchronize the slide ledger.",
    )
    handoff_parser.add_argument("--blueprint", required=True, type=Path)
    handoff_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    handoff_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    handoff_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    handoff_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    handoff_parser.add_argument("--output-dir", required=True, type=Path)
    handoff_parser.add_argument("--asset-requests", dest="asset_requests", type=Path)

    visuals_parser = subparsers.add_parser(
        "render-structured-visuals",
        help="Render slide-native structured visuals from viz_spec and update viz-manifest, asset-manifest, and slide-ledger state.",
    )
    visuals_parser.add_argument("--viz-spec", dest="viz_spec", required=True, type=Path)
    visuals_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    visuals_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    visuals_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    visuals_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    visuals_parser.add_argument("--output-dir", required=True, type=Path)
    visuals_parser.add_argument("--asset-requests", dest="asset_requests", type=Path)
    visuals_parser.add_argument("--asset-manifest", dest="asset_manifest", type=Path)
    visuals_parser.add_argument("--viz-manifest", dest="viz_manifest", type=Path)

    compile_parser = subparsers.add_parser(
        "compile-pptx",
        help="Compile an approved blueprint, design system, assets, and structured visuals into a PPTX deck plus build manifests.",
    )
    compile_parser.add_argument("--blueprint", required=True, type=Path)
    compile_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    compile_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    compile_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    compile_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    compile_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    compile_parser.add_argument("--viz-manifest", dest="viz_manifest", required=True, type=Path)
    compile_parser.add_argument("--output-dir", required=True, type=Path)
    compile_parser.add_argument("--batch-manifest", dest="batch_manifest", type=Path)
    compile_parser.add_argument("--state-capsule", dest="state_capsule", type=Path)
    compile_parser.add_argument("--notes", type=Path)
    compile_parser.add_argument("--pptx-name", dest="pptx_name", default="deck.pptx")
    compile_parser.add_argument(
        "--root",
        type=Path,
        help="Resolve relative asset and visual paths from this root instead of the current working directory.",
    )
    compile_parser.add_argument(
        "--disable-layout-critic",
        dest="disable_layout_critic",
        action="store_true",
        help="Skip bounded layout candidate scoring and use the rule-based SlideIR fallback directly.",
    )
    compile_parser.add_argument(
        "--experimental-scene-renderer",
        action="store_true",
        help="EXPERIMENTAL opt-in: compile through the SceneDeck renderer instead of the default PPTX compiler for this run only.",
    )
    compile_parser.add_argument(
        "--scene-validate",
        action="store_true",
        help="When using --experimental-scene-renderer, run scene-strict object validation and emit pptx-object-report.json.",
    )
    compile_parser.add_argument(
        "--scene-profile",
        default="none",
        choices=["none", "scene-strict", "curated-strict"],
        help="Optional experimental scene validation profile for --experimental-scene-renderer.",
    )
    compile_parser.add_argument(
        "--scene-validation-mode",
        default="inspect",
        choices=["inspect", "warn", "enforce"],
        help="Validation mode for experimental scene validation.",
    )
    compile_parser.add_argument("--style-policy", type=Path, help="Optional scene style policy for --scene-profile curated-strict.")
    compile_parser.add_argument("--adapter-policy", type=Path, help="Optional scene adapter policy for --scene-profile curated-strict.")

    scene_parser = subparsers.add_parser(
        "inspect-scene-deck",
        help="Emit renderer-facing SceneDeck JSON from approved state without compiling PPTX.",
    )
    scene_parser.add_argument("--blueprint", required=True, type=Path)
    scene_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    scene_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    scene_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    scene_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    scene_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    scene_parser.add_argument("--viz-manifest", dest="viz_manifest", required=True, type=Path)
    scene_parser.add_argument("--output", required=True, type=Path)
    scene_parser.add_argument(
        "--disable-layout-critic",
        dest="disable_layout_critic",
        action="store_true",
        help="Skip bounded layout candidate scoring and use the rule-based SlideIR fallback directly.",
    )

    validate_pptx_parser = subparsers.add_parser(
        "validate-pptx-objects",
        help="Inspect a compiled PPTX object tree and optionally compare it against SceneDeck expectations.",
    )
    validate_pptx_parser.add_argument("--pptx", required=True, type=Path)
    validate_pptx_parser.add_argument("--output", required=True, type=Path)
    validate_pptx_parser.add_argument("--scene-deck", dest="scene_deck", type=Path)
    validate_pptx_parser.add_argument(
        "--mode",
        choices=("inspect", "warn", "enforce"),
        default="inspect",
        help="Validation mode. inspect and warn are non-breaking; enforce returns non-zero when enforceable findings exist.",
    )
    validate_pptx_parser.add_argument(
        "--profile",
        choices=("basic", "scene-strict"),
        default="basic",
        help="Validation profile. basic keeps checks non-invasive; scene-strict adds trace and text-fit enforcement for scene-rendered fixtures.",
    )

    scene_gate_parser = subparsers.add_parser(
        "scene-readiness-gate",
        help="Run a curated opt-in SceneDeck readiness gate across stable fixtures and emit aggregate readiness artifacts.",
    )
    scene_gate_parser.add_argument("--manifest", required=True, type=Path)
    scene_gate_parser.add_argument("--output-dir", required=True, type=Path)
    scene_gate_parser.add_argument("--fixture", action="append")
    scene_gate_parser.add_argument(
        "--mode",
        choices=("inspect", "warn", "enforce"),
        default="inspect",
        help="Gate mode. inspect and warn are non-breaking; enforce returns non-zero when curated fixtures fail readiness checks.",
    )
    scene_gate_parser.add_argument(
        "--profile",
        choices=(
            "basic",
            "scene-strict",
            "structural",
            "style-strict",
            "adapter-strict",
            "curated-strict",
            "visual-smoke",
            "visual-diff-local",
            "visual-diff-pinned",
            "baseline-refresh",
        ),
        default="scene-strict",
        help="Validation profile or named scene readiness profile. Existing basic/scene-strict values remain supported.",
    )
    scene_gate_parser.add_argument("--visual-policy", dest="visual_policy", type=Path)
    scene_gate_parser.add_argument("--style-policy", dest="style_policy", type=Path)
    scene_gate_parser.add_argument("--style-profile", dest="style_profile")
    scene_gate_parser.add_argument("--enforce-style-policy", action="store_true")
    scene_gate_parser.add_argument("--adapter-policy", dest="adapter_policy", type=Path)
    scene_gate_parser.add_argument("--adapter-profile", dest="adapter_profile")
    scene_gate_parser.add_argument("--enforce-adapter-policy", action="store_true")
    scene_gate_parser.add_argument("--screenshots", action="store_true")
    scene_gate_parser.add_argument(
        "--screenshot-mode",
        choices=("inspect", "warn", "enforce"),
        default="inspect",
        help="Screenshot QA mode. inspect and warn are non-breaking; enforce returns non-zero when screenshot findings are enforceable.",
    )
    scene_gate_parser.add_argument(
        "--screenshot-exporter",
        choices=("auto", "powerpoint", "libreoffice", "none"),
        default="auto",
        help="Screenshot exporter strategy. auto prefers PowerPoint on supported Windows environments.",
    )
    scene_gate_parser.add_argument(
        "--screenshot-output-format",
        choices=("png",),
        default="png",
    )
    scene_gate_parser.add_argument("--visual-diff", action="store_true")
    scene_gate_parser.add_argument("--visual-baseline-dir", dest="visual_baseline_dir", type=Path)
    scene_gate_parser.add_argument("--update-visual-baselines", action="store_true")
    scene_gate_parser.add_argument(
        "--visual-mode",
        choices=("inspect", "warn", "enforce"),
        default="inspect",
        help="Visual regression mode. enforce is opt-in and fails on enforceable visual findings.",
    )
    scene_gate_parser.add_argument(
        "--visual-threshold",
        choices=("lenient", "default", "strict"),
        default="default",
        help="Visual diff threshold preset.",
    )
    scene_gate_parser.add_argument("--require-visual-baselines", action="store_true")
    scene_gate_parser.add_argument("--write-diff-images", action="store_true")

    migration_parser = subparsers.add_parser(
        "scene-migration-readiness",
        help="Aggregate existing scene readiness profile artifacts into a migration-readiness dashboard report.",
    )
    migration_parser.add_argument("--artifacts-root", required=True, type=Path)
    migration_parser.add_argument("--output", required=True, type=Path)
    migration_parser.add_argument("--previous-report", type=Path)
    migration_parser.add_argument("--write-markdown", type=Path)

    migration_history_parser = subparsers.add_parser(
        "scene-migration-history",
        help="Build a deterministic history and release-note artifact from migration-readiness dashboard reports.",
    )
    migration_history_parser.add_argument("--current-report", required=True, type=Path)
    migration_history_parser.add_argument("--previous-report", type=Path)
    migration_history_parser.add_argument("--output", required=True, type=Path)
    migration_history_parser.add_argument("--write-markdown", type=Path)

    default_vs_scene_parser = subparsers.add_parser(
        "default-vs-scene-poc",
        help="Build side-by-side default-path and SceneDeck-path PPTX artifacts for curated fixtures.",
    )
    default_vs_scene_parser.add_argument("--manifest", required=True, type=Path)
    default_vs_scene_parser.add_argument("--output-dir", required=True, type=Path)
    default_vs_scene_parser.add_argument("--style-policy", type=Path)
    default_vs_scene_parser.add_argument("--adapter-policy", type=Path)
    default_vs_scene_parser.add_argument("--fixture", action="append", dest="fixture")
    default_vs_scene_parser.add_argument("--write-markdown", action="store_true")

    scene_compile_parser = subparsers.add_parser(
        "compile-scene-pptx",
        help="Compile a renderer-facing SceneDeck JSON directly to PPTX using the bounded scene renderers.",
    )
    scene_compile_parser.add_argument("--scene-deck", dest="scene_deck", required=True, type=Path)
    scene_compile_parser.add_argument("--output-dir", required=True, type=Path)
    scene_compile_parser.add_argument("--pptx-name", dest="pptx_name", default="deck.pptx")
    scene_compile_parser.add_argument(
        "--root",
        type=Path,
        help="Resolve relative image source paths from this root instead of the SceneDeck file directory.",
    )

    qa_parser = subparsers.add_parser(
        "qa-deck",
        help="Audit a compiled PPTX plus build artifacts and persist qa-report, synced slide-ledger, and QA-enriched slide-build-linkage outputs.",
    )
    qa_parser.add_argument("--blueprint", required=True, type=Path)
    qa_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    qa_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    qa_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    qa_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    qa_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    qa_parser.add_argument("--viz-manifest", dest="viz_manifest", required=True, type=Path)
    qa_parser.add_argument("--build-manifest", dest="build_manifest", required=True, type=Path)
    qa_parser.add_argument("--slide-build-linkage", dest="slide_build_linkage", required=True, type=Path)
    qa_parser.add_argument("--output-dir", required=True, type=Path)
    qa_parser.add_argument("--state-capsule", dest="state_capsule", type=Path)
    qa_parser.add_argument("--prior-report", dest="prior_report", type=Path)
    qa_parser.add_argument("--qa-governance", dest="qa_governance", type=Path)

    orchestration_parser = subparsers.add_parser(
        "orchestrate-large-deck",
        help="Generate batch-manifest, context-lock, handoff-packet, state-capsule, and a continuity-safe slide-ledger.",
    )
    orchestration_parser.add_argument("--workflow-plan", dest="workflow_plan", required=True, type=Path)
    orchestration_parser.add_argument("--blueprint", required=True, type=Path)
    orchestration_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    orchestration_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    orchestration_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    orchestration_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    orchestration_parser.add_argument("--build-manifest", dest="build_manifest", type=Path)
    orchestration_parser.add_argument("--slide-build-linkage", dest="slide_build_linkage", type=Path)
    orchestration_parser.add_argument("--qa-report", dest="qa_report", type=Path)
    orchestration_parser.add_argument("--output-dir", required=True, type=Path)

    remediation_parser = subparsers.add_parser(
        "apply-remediation",
        help="Apply bounded remediation actions, rerun only required downstream stages, and refresh canonical state artifacts.",
    )
    remediation_parser.add_argument("--remediation-plan", dest="remediation_plan", required=True, type=Path)
    remediation_parser.add_argument("--batch-manifest", dest="batch_manifest", required=True, type=Path)
    remediation_parser.add_argument("--context-lock", dest="context_lock", required=True, type=Path)
    remediation_parser.add_argument("--state-capsule", dest="state_capsule", required=True, type=Path)
    remediation_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    remediation_parser.add_argument("--slide-build-linkage", dest="slide_build_linkage", required=True, type=Path)
    remediation_parser.add_argument("--qa-report", dest="qa_report", required=True, type=Path)
    remediation_parser.add_argument("--build-manifest", dest="build_manifest", required=True, type=Path)
    remediation_parser.add_argument("--blueprint", required=True, type=Path)
    remediation_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    remediation_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    remediation_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    remediation_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    remediation_parser.add_argument("--viz-manifest", dest="viz_manifest", required=True, type=Path)
    remediation_parser.add_argument("--output-dir", required=True, type=Path)
    remediation_parser.add_argument("--workflow-plan", dest="workflow_plan", type=Path)
    remediation_parser.add_argument("--handoff-packet", dest="handoff_packet", type=Path)
    remediation_parser.add_argument("--asset-requests", dest="asset_requests", type=Path)
    remediation_parser.add_argument("--viz-spec", dest="viz_spec", type=Path)
    remediation_parser.add_argument("--notes", type=Path)
    remediation_parser.add_argument("--build-output-dir", dest="build_output_dir", type=Path)
    remediation_parser.add_argument("--visual-output-dir", dest="visual_output_dir", type=Path)

    upstream_fix_parser = subparsers.add_parser(
        "author-upstream-fixes",
        help="Prepare bounded upstream approval packets and machine-readable deltas from the remaining remediation backlog.",
    )
    upstream_fix_parser.add_argument("--remediation-plan", dest="remediation_plan", required=True, type=Path)
    upstream_fix_parser.add_argument("--remediation-execution-report", dest="remediation_execution_report", required=True, type=Path)
    upstream_fix_parser.add_argument("--batch-manifest", dest="batch_manifest", required=True, type=Path)
    upstream_fix_parser.add_argument("--context-lock", dest="context_lock", required=True, type=Path)
    upstream_fix_parser.add_argument("--handoff-packet", dest="handoff_packet", required=True, type=Path)
    upstream_fix_parser.add_argument("--state-capsule", dest="state_capsule", required=True, type=Path)
    upstream_fix_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    upstream_fix_parser.add_argument("--slide-build-linkage", dest="slide_build_linkage", required=True, type=Path)
    upstream_fix_parser.add_argument("--qa-report", dest="qa_report", required=True, type=Path)
    upstream_fix_parser.add_argument("--build-manifest", dest="build_manifest", required=True, type=Path)
    upstream_fix_parser.add_argument("--blueprint", required=True, type=Path)
    upstream_fix_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    upstream_fix_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    upstream_fix_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    upstream_fix_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    upstream_fix_parser.add_argument("--viz-manifest", dest="viz_manifest", required=True, type=Path)
    upstream_fix_parser.add_argument("--output-dir", required=True, type=Path)
    upstream_fix_parser.add_argument("--asset-requests", dest="asset_requests", type=Path)
    upstream_fix_parser.add_argument("--viz-spec", dest="viz_spec", type=Path)

    approved_apply_parser = subparsers.add_parser(
        "apply-approved-fixes",
        help="Apply only explicitly approved upstream deltas, rerun the minimum downstream stages, and refresh canonical state.",
    )
    approved_apply_parser.add_argument("--approval-packet", dest="approval_packet", required=True, type=Path)
    approved_apply_parser.add_argument("--authoring-deltas", dest="authoring_deltas", required=True, type=Path)
    approved_apply_parser.add_argument("--upstream-fix-plan", dest="upstream_fix_plan", required=True, type=Path)
    approved_apply_parser.add_argument("--remediation-plan", dest="remediation_plan", required=True, type=Path)
    approved_apply_parser.add_argument("--remediation-execution-report", dest="remediation_execution_report", required=True, type=Path)
    approved_apply_parser.add_argument("--batch-manifest", dest="batch_manifest", required=True, type=Path)
    approved_apply_parser.add_argument("--context-lock", dest="context_lock", required=True, type=Path)
    approved_apply_parser.add_argument("--state-capsule", dest="state_capsule", required=True, type=Path)
    approved_apply_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    approved_apply_parser.add_argument("--slide-build-linkage", dest="slide_build_linkage", required=True, type=Path)
    approved_apply_parser.add_argument("--qa-report", dest="qa_report", required=True, type=Path)
    approved_apply_parser.add_argument("--build-manifest", dest="build_manifest", required=True, type=Path)
    approved_apply_parser.add_argument("--blueprint", required=True, type=Path)
    approved_apply_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    approved_apply_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    approved_apply_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    approved_apply_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    approved_apply_parser.add_argument("--viz-manifest", dest="viz_manifest", required=True, type=Path)
    approved_apply_parser.add_argument("--output-dir", required=True, type=Path)
    approved_apply_parser.add_argument("--handoff-packet", dest="handoff_packet", type=Path)
    approved_apply_parser.add_argument("--workflow-plan", dest="workflow_plan", type=Path)
    approved_apply_parser.add_argument("--asset-requests", dest="asset_requests", type=Path)
    approved_apply_parser.add_argument("--viz-spec", dest="viz_spec", type=Path)
    approved_apply_parser.add_argument("--approve-packet-id", dest="approve_packet_id", action="append")
    approved_apply_parser.add_argument("--approve-fix-id", dest="approve_fix_id", action="append")
    approved_apply_parser.add_argument("--select-option", dest="select_option", action="append")
    approved_apply_parser.add_argument("--artifact-root", dest="artifact_root", type=Path)
    approved_apply_parser.add_argument("--build-output-dir", dest="build_output_dir", type=Path)
    approved_apply_parser.add_argument("--asset-output-dir", dest="asset_output_dir", type=Path)
    approved_apply_parser.add_argument("--visual-output-dir", dest="visual_output_dir", type=Path)
    approved_apply_parser.add_argument("--notes", type=Path)

    close_apply_parser = subparsers.add_parser(
        "close-approved-fixes",
        help="Close applied approval packets, emit a deterministic remaining backlog view, and synchronize control-state after Phase 14.",
    )
    close_apply_parser.add_argument("--approved-apply-report", dest="approved_apply_report", required=True, type=Path)
    close_apply_parser.add_argument("--approval-packet", dest="approval_packet", required=True, type=Path)
    close_apply_parser.add_argument("--authoring-deltas", dest="authoring_deltas", required=True, type=Path)
    close_apply_parser.add_argument("--upstream-fix-plan", dest="upstream_fix_plan", required=True, type=Path)
    close_apply_parser.add_argument("--remediation-plan", dest="remediation_plan", required=True, type=Path)
    close_apply_parser.add_argument("--remediation-execution-report", dest="remediation_execution_report", required=True, type=Path)
    close_apply_parser.add_argument("--batch-manifest", dest="batch_manifest", required=True, type=Path)
    close_apply_parser.add_argument("--context-lock", dest="context_lock", required=True, type=Path)
    close_apply_parser.add_argument("--handoff-packet", dest="handoff_packet", required=True, type=Path)
    close_apply_parser.add_argument("--state-capsule", dest="state_capsule", required=True, type=Path)
    close_apply_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    close_apply_parser.add_argument("--slide-build-linkage", dest="slide_build_linkage", required=True, type=Path)
    close_apply_parser.add_argument("--qa-report", dest="qa_report", required=True, type=Path)
    close_apply_parser.add_argument("--build-manifest", dest="build_manifest", required=True, type=Path)
    close_apply_parser.add_argument("--blueprint", required=True, type=Path)
    close_apply_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    close_apply_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    close_apply_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    close_apply_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    close_apply_parser.add_argument("--viz-manifest", dest="viz_manifest", required=True, type=Path)
    close_apply_parser.add_argument("--output-dir", required=True, type=Path)
    close_apply_parser.add_argument("--asset-requests", dest="asset_requests", type=Path)
    close_apply_parser.add_argument("--viz-spec", dest="viz_spec", type=Path)
    close_apply_parser.add_argument("--pointer-root", dest="pointer_root")

    readiness_parser = subparsers.add_parser(
        "assess-ship-readiness",
        help="Assess whether the current canonical deck may ship now or must continue into another bounded approval/apply cycle.",
    )
    readiness_parser.add_argument("--closure-report", dest="closure_report", required=True, type=Path)
    readiness_parser.add_argument("--remaining-backlog", dest="remaining_backlog", required=True, type=Path)
    readiness_parser.add_argument("--approval-packet", dest="approval_packet", required=True, type=Path)
    readiness_parser.add_argument("--authoring-deltas", dest="authoring_deltas", required=True, type=Path)
    readiness_parser.add_argument("--upstream-fix-plan", dest="upstream_fix_plan", required=True, type=Path)
    readiness_parser.add_argument("--approved-apply-report", dest="approved_apply_report", required=True, type=Path)
    readiness_parser.add_argument("--remediation-plan", dest="remediation_plan", required=True, type=Path)
    readiness_parser.add_argument("--remediation-execution-report", dest="remediation_execution_report", required=True, type=Path)
    readiness_parser.add_argument("--batch-manifest", dest="batch_manifest", required=True, type=Path)
    readiness_parser.add_argument("--context-lock", dest="context_lock", required=True, type=Path)
    readiness_parser.add_argument("--handoff-packet", dest="handoff_packet", required=True, type=Path)
    readiness_parser.add_argument("--state-capsule", dest="state_capsule", required=True, type=Path)
    readiness_parser.add_argument("--slide-ledger", dest="slide_ledger", required=True, type=Path)
    readiness_parser.add_argument("--slide-build-linkage", dest="slide_build_linkage", required=True, type=Path)
    readiness_parser.add_argument("--qa-report", dest="qa_report", required=True, type=Path)
    readiness_parser.add_argument("--qa-governance", dest="qa_governance", required=True, type=Path)
    readiness_parser.add_argument("--build-manifest", dest="build_manifest", required=True, type=Path)
    readiness_parser.add_argument("--blueprint", required=True, type=Path)
    readiness_parser.add_argument("--design-system", dest="design_system", required=True, type=Path)
    readiness_parser.add_argument("--deck-constitution", dest="deck_constitution", required=True, type=Path)
    readiness_parser.add_argument("--layout-library", dest="layout_library", required=True, type=Path)
    readiness_parser.add_argument("--asset-manifest", dest="asset_manifest", required=True, type=Path)
    readiness_parser.add_argument("--viz-manifest", dest="viz_manifest", required=True, type=Path)
    readiness_parser.add_argument("--output-dir", required=True, type=Path)
    readiness_parser.add_argument("--artifact-root", dest="artifact_root", type=Path)

    policy_parser = subparsers.add_parser(
        "evaluate-reviewed-surrogate-policy",
        help="Evaluate a reviewed-surrogate gate artifact against an approved target registry entry for PR/release governance.",
    )
    policy_parser.add_argument("--gate-artifact", required=True, type=Path)
    policy_parser.add_argument("--registry", required=True, type=Path)
    policy_parser.add_argument("--target-id", required=True)
    policy_parser.add_argument("--context", default="both", choices=["both", "pr", "release"])
    policy_parser.add_argument("--output-dir", required=True, type=Path)
    policy_parser.add_argument("--context-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "summary":
        return _print_summary(args.schema)
    if args.command == "validate":
        return _validate_paths(args.paths)
    if args.command == "generate":
        return _generate(args.schema, args.mode, args.output)
    if args.command == "plan-workflow":
        return _plan_workflow(args.brief, args.output)
    if args.command == "ingest-source":
        return _ingest_source(args.source, args.output)
    if args.command == "plan-deck-from-source":
        return _plan_deck_from_source(
            source_document=args.source_document,
            design_mode=args.design_mode,
            target_slides=args.target_slides,
            output=args.output,
            validation_output=args.validation_output,
        )
    if args.command == "source-plan-poc":
        return _source_plan_poc(
            source=args.source,
            design_mode=args.design_mode,
            target_slides=args.target_slides,
            output_dir=args.output_dir,
        )
    if args.command == "build-state-from-plan":
        return _build_state_from_plan(
            source_document=args.source_document,
            presentation_plan=args.presentation_plan,
            output_state_dir=args.output_state_dir,
        )
    if args.command == "repair-presentation-plan":
        return _repair_presentation_plan(
            source_document=args.source_document,
            presentation_plan=args.presentation_plan,
            output_dir=args.output_dir,
            write_markdown=args.write_markdown,
        )
    if args.command == "validate-repair-presentation-plan":
        return _repair_presentation_plan(
            source_document=args.source_document,
            presentation_plan=args.presentation_plan,
            output_dir=args.output_dir,
            write_markdown=args.write_markdown,
        )
    if args.command == "source-to-state-poc":
        return _source_to_state_poc(
            source=args.source,
            design_mode=args.design_mode,
            target_slides=args.target_slides,
            output_dir=args.output_dir,
        )
    if args.command == "source-to-pptx-poc":
        return _source_to_pptx_poc(
            source=args.source,
            design_mode=args.design_mode,
            target_slides=args.target_slides,
            output_dir=args.output_dir,
            experimental_scene_renderer=args.experimental_scene_renderer,
            scene_profile=args.scene_profile,
            scene_validation_mode=args.scene_validation_mode,
            style_policy=args.style_policy,
            adapter_policy=args.adapter_policy,
            repair_plan=args.repair_plan,
        )
    if args.command == "scan-reference-pack":
        return _scan_reference_pack(args.pack, args.output, args.workflow_plan, args.brief_context)
    if args.command == "plan-blueprint":
        return _plan_blueprint(
            workflow_plan=args.workflow_plan,
            output_dir=args.output_dir,
            brief=args.brief,
            reference_dna=args.reference_dna,
            brand_inputs=args.brand_inputs,
        )
    if args.command == "evaluate-workflow":
        return _evaluate_workflow(args.output_dir)
    if args.command == "summarize-governance":
        return _summarize_governance(args.qa_governance)
    if args.command == "summarize-ship-readiness":
        return _summarize_ship_readiness(args.ship_readiness_report)
    if args.command == "crop-document-assets":
        return _run_document_crop(
            asset_requests=args.asset_requests,
            slide_ledger=args.slide_ledger,
            output_dir=args.output_dir,
            asset_manifest=args.asset_manifest,
            dpi=args.dpi,
            max_candidates_per_source=args.max_candidates_per_source,
            max_review_rounds=args.max_review_rounds,
        )
    if args.command == "review-crops":
        return _review_document_crops(
            asset_requests=args.asset_requests,
            slide_ledger=args.slide_ledger,
            crop_candidates=args.crop_candidates,
            asset_manifest=args.asset_manifest,
            output_dir=args.output_dir,
            crop_review_inputs=args.crop_review_inputs,
            crop_review_decisions=args.crop_review_decisions,
            selected_crops=args.selected_crops,
            max_review_rounds=args.max_review_rounds,
        )
    if args.command == "prepare-production-handoff":
        return _prepare_production_handoff(
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            slide_ledger=args.slide_ledger,
            output_dir=args.output_dir,
            asset_requests=args.asset_requests,
        )
    if args.command == "render-structured-visuals":
        return _run_structured_visuals(
            viz_spec=args.viz_spec,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            slide_ledger=args.slide_ledger,
            output_dir=args.output_dir,
            asset_requests=args.asset_requests,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
        )
    if args.command == "compile-pptx":
        return _compile_pptx(
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            slide_ledger=args.slide_ledger,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
            output_dir=args.output_dir,
            batch_manifest=args.batch_manifest,
            state_capsule=args.state_capsule,
            notes=args.notes,
            pptx_name=args.pptx_name,
            disable_layout_critic=args.disable_layout_critic,
            root=args.root,
            experimental_scene_renderer=args.experimental_scene_renderer,
            scene_validate=args.scene_validate,
            scene_profile=args.scene_profile,
            scene_validation_mode=args.scene_validation_mode,
            style_policy=args.style_policy,
            adapter_policy=args.adapter_policy,
        )
    if args.command == "inspect-scene-deck":
        return _inspect_scene_deck(
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            slide_ledger=args.slide_ledger,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
            output=args.output,
            disable_layout_critic=args.disable_layout_critic,
        )
    if args.command == "validate-pptx-objects":
        return _validate_pptx_objects(
            pptx=args.pptx,
            output=args.output,
            scene_deck=args.scene_deck,
            mode=args.mode,
            profile=args.profile,
        )
    if args.command == "scene-readiness-gate":
        return _scene_readiness_gate(
            manifest=args.manifest,
            output_dir=args.output_dir,
            fixture=args.fixture,
            mode=args.mode,
            profile=args.profile,
            screenshots=args.screenshots,
            screenshot_mode=args.screenshot_mode,
            screenshot_exporter=args.screenshot_exporter,
            screenshot_output_format=args.screenshot_output_format,
            visual_diff=args.visual_diff,
            visual_baseline_dir=args.visual_baseline_dir,
            update_visual_baselines=args.update_visual_baselines,
            visual_mode=args.visual_mode,
            visual_threshold=args.visual_threshold,
            require_visual_baselines=args.require_visual_baselines,
            write_diff_images=args.write_diff_images,
            visual_policy=args.visual_policy,
            style_policy=args.style_policy,
            style_profile=args.style_profile,
            enforce_style_policy=args.enforce_style_policy,
            adapter_policy=args.adapter_policy,
            adapter_profile=args.adapter_profile,
            enforce_adapter_policy=args.enforce_adapter_policy,
        )
    if args.command == "scene-migration-readiness":
        return _scene_migration_readiness(
            artifacts_root=args.artifacts_root,
            output=args.output,
            previous_report=args.previous_report,
            markdown=args.write_markdown,
        )
    if args.command == "scene-migration-history":
        return _scene_migration_history(
            current_report=args.current_report,
            previous_report=args.previous_report,
            output=args.output,
            markdown=args.write_markdown,
        )
    if args.command == "default-vs-scene-poc":
        return _default_vs_scene_poc(
            manifest=args.manifest,
            output_dir=args.output_dir,
            style_policy=args.style_policy,
            adapter_policy=args.adapter_policy,
            fixture=args.fixture,
            write_markdown=args.write_markdown,
        )
    if args.command == "compile-scene-pptx":
        return _compile_scene_pptx(
            scene_deck=args.scene_deck,
            output_dir=args.output_dir,
            root=args.root,
            pptx_name=args.pptx_name,
        )
    if args.command == "qa-deck":
        return _qa_deck(
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            slide_ledger=args.slide_ledger,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
            build_manifest=args.build_manifest,
            slide_build_linkage=args.slide_build_linkage,
            output_dir=args.output_dir,
            state_capsule=args.state_capsule,
            prior_report=args.prior_report,
            qa_governance=args.qa_governance,
        )
    if args.command == "orchestrate-large-deck":
        return _orchestrate_large_deck(
            workflow_plan=args.workflow_plan,
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            slide_ledger=args.slide_ledger,
            build_manifest=args.build_manifest,
            slide_build_linkage=args.slide_build_linkage,
            qa_report=args.qa_report,
            output_dir=args.output_dir,
        )
    if args.command == "apply-remediation":
        return _apply_remediation(
            remediation_plan=args.remediation_plan,
            batch_manifest=args.batch_manifest,
            context_lock=args.context_lock,
            state_capsule=args.state_capsule,
            slide_ledger=args.slide_ledger,
            slide_build_linkage=args.slide_build_linkage,
            qa_report=args.qa_report,
            build_manifest=args.build_manifest,
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
            output_dir=args.output_dir,
            workflow_plan=args.workflow_plan,
            handoff_packet=args.handoff_packet,
            asset_requests=args.asset_requests,
            viz_spec=args.viz_spec,
            notes=args.notes,
            build_output_dir=args.build_output_dir,
            visual_output_dir=args.visual_output_dir,
        )
    if args.command == "author-upstream-fixes":
        return _author_upstream_fixes(
            remediation_plan=args.remediation_plan,
            remediation_execution_report=args.remediation_execution_report,
            batch_manifest=args.batch_manifest,
            context_lock=args.context_lock,
            handoff_packet=args.handoff_packet,
            state_capsule=args.state_capsule,
            slide_ledger=args.slide_ledger,
            slide_build_linkage=args.slide_build_linkage,
            qa_report=args.qa_report,
            build_manifest=args.build_manifest,
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
            output_dir=args.output_dir,
            asset_requests=args.asset_requests,
            viz_spec=args.viz_spec,
        )
    if args.command == "apply-approved-fixes":
        return _apply_approved_fixes(
            approval_packet=args.approval_packet,
            authoring_deltas=args.authoring_deltas,
            upstream_fix_plan=args.upstream_fix_plan,
            remediation_plan=args.remediation_plan,
            remediation_execution_report=args.remediation_execution_report,
            batch_manifest=args.batch_manifest,
            context_lock=args.context_lock,
            state_capsule=args.state_capsule,
            slide_ledger=args.slide_ledger,
            slide_build_linkage=args.slide_build_linkage,
            qa_report=args.qa_report,
            build_manifest=args.build_manifest,
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
            output_dir=args.output_dir,
            handoff_packet=args.handoff_packet,
            workflow_plan=args.workflow_plan,
            asset_requests=args.asset_requests,
            viz_spec=args.viz_spec,
            approve_packet_id=args.approve_packet_id,
            approve_fix_id=args.approve_fix_id,
            select_option=args.select_option,
            artifact_root=args.artifact_root,
            build_output_dir=args.build_output_dir,
            asset_output_dir=args.asset_output_dir,
            visual_output_dir=args.visual_output_dir,
            notes=args.notes,
        )
    if args.command == "close-approved-fixes":
        return _close_approved_fixes(
            approved_apply_report=args.approved_apply_report,
            approval_packet=args.approval_packet,
            authoring_deltas=args.authoring_deltas,
            upstream_fix_plan=args.upstream_fix_plan,
            remediation_plan=args.remediation_plan,
            remediation_execution_report=args.remediation_execution_report,
            batch_manifest=args.batch_manifest,
            context_lock=args.context_lock,
            handoff_packet=args.handoff_packet,
            state_capsule=args.state_capsule,
            slide_ledger=args.slide_ledger,
            slide_build_linkage=args.slide_build_linkage,
            qa_report=args.qa_report,
            build_manifest=args.build_manifest,
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
            output_dir=args.output_dir,
            asset_requests=args.asset_requests,
            viz_spec=args.viz_spec,
            pointer_root=args.pointer_root,
        )
    if args.command == "assess-ship-readiness":
        return _assess_ship_readiness(
            closure_report=args.closure_report,
            remaining_backlog=args.remaining_backlog,
            approval_packet=args.approval_packet,
            authoring_deltas=args.authoring_deltas,
            upstream_fix_plan=args.upstream_fix_plan,
            approved_apply_report=args.approved_apply_report,
            remediation_plan=args.remediation_plan,
            remediation_execution_report=args.remediation_execution_report,
            batch_manifest=args.batch_manifest,
            context_lock=args.context_lock,
            handoff_packet=args.handoff_packet,
            state_capsule=args.state_capsule,
            slide_ledger=args.slide_ledger,
            slide_build_linkage=args.slide_build_linkage,
            qa_report=args.qa_report,
            qa_governance=args.qa_governance,
            build_manifest=args.build_manifest,
            blueprint=args.blueprint,
            design_system=args.design_system,
            deck_constitution=args.deck_constitution,
            layout_library=args.layout_library,
            asset_manifest=args.asset_manifest,
            viz_manifest=args.viz_manifest,
            output_dir=args.output_dir,
            artifact_root=args.artifact_root,
        )
    if args.command == "evaluate-reviewed-surrogate-policy":
        return _evaluate_reviewed_surrogate_policy(
            gate_artifact=args.gate_artifact,
            registry=args.registry,
            target_id=args.target_id,
            context=args.context,
            output_dir=args.output_dir,
            context_root=args.context_root,
        )
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())


