"""Deterministic Phase 4B Semantic Sidecar and visual-request preparation."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..errors import DeckCompilerError
from ..identity import content_sha256, stable_id
from ..manifest_io import read_json, write_json
from ..platform_image_execution import build_capability_attestation
from ..provenance import current_source_commit
from ..schemas import REPO_ROOT, validator_for


REQUIRED_PHASE3_FILES = (
    "input_request.json",
    "source_corpus.json",
    "source_locators.json",
    "evidence_unit_registry.json",
    "source_coverage_report.json",
    "workflow_resolution.json",
    "source_gap_report.json",
    "presentation_plan.json",
    "slide_blueprint_collection.json",
    "evidence_allocation_report.json",
    "presentation_architecture.json",
    "design_invariants.json",
    "module_art_directions.json",
    "creative_template_architecture.json",
    "creative_fit_report.json",
    "architecture_validation_report.json",
    "artifact_graph.json",
    "phase3_validation_report.json",
    "deckcompiler_run_manifest.json",
)

PROMPT_FILENAMES = (
    "design_board.prompt.json",
    "module-001.prompt.json",
    "module-002.prompt.json",
    "module-003.prompt.json",
    "batch-001.prompt.json",
    "batch-002.prompt.json",
    "batch-003.prompt.json",
    "slide-001.prompt.json",
    "slide-002.prompt.json",
    "slide-003.prompt.json",
    "slide-004.prompt.json",
    "slide-005.prompt.json",
    "slide-006.prompt.json",
)

FORBIDDEN_RASTER_SLOT_MARKERS = ("full_slide", "background", "screenshot", "clean_plate", "canvas")


@dataclass(frozen=True, slots=True)
class Phase4VisualPreparationValidation:
    valid: bool
    issues: tuple[str, ...]
    checks: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Phase4VisualPreparationResult:
    output_dir: Path
    sidecar_paths: tuple[Path, ...]
    prompt_paths: tuple[Path, ...]
    visual_dna_path: Path
    design_system_path: Path
    editable_template_spec_path: Path
    pending_manifest_path: Path
    capability_attestation_path: Path
    validation_report_path: Path
    evidence_ids: frozenset[str]


def prepare_visuals(phase3_run: str | Path, output_dir: str | Path) -> Phase4VisualPreparationResult:
    """Create Phase 4B artifacts without invoking any image or network tool."""

    phase3_root = Path(phase3_run).resolve()
    artifacts = _load_phase3_input(phase3_root)
    source_commit = _validate_phase3_input(artifacts)
    output = _prepare_output_directory(Path(output_dir))

    preparation = output / "preparation"
    sidecar_dir = preparation / "semantic_sidecars"
    prompt_dir = preparation / "prompts"
    capability_dir = output / "records" / "capability"
    reports_dir = output / "reports"
    manifests_dir = output / "manifests"
    for directory in (sidecar_dir, prompt_dir, capability_dir, reports_dir, manifests_dir, output / "phase3_input"):
        directory.mkdir(parents=True, exist_ok=True)

    evidence_units = artifacts["evidence_unit_registry.json"]["evidence_units"]
    evidence_by_id = {item["evidence_id"]: item for item in evidence_units}
    evidence_ids = frozenset(evidence_by_id)
    blueprints = artifacts["slide_blueprint_collection.json"]["slides"]
    architecture_slides = sorted(artifacts["presentation_architecture.json"]["slides"], key=lambda item: item["order"])
    architecture_by_slide = {item["slide_id"]: item for item in architecture_slides}
    fit_by_slide = {
        item["slide_id"]: item
        for item in artifacts["creative_template_architecture.json"]["slide_fit_decisions"]
    }

    sidecars: list[dict[str, Any]] = []
    sidecar_paths: list[Path] = []
    for index, blueprint in enumerate(blueprints, start=1):
        sidecar = _build_sidecar(
            blueprint=blueprint,
            architecture_slide=architecture_by_slide[blueprint["slide_id"]],
            fit=fit_by_slide[blueprint["slide_id"]],
            evidence_by_id=evidence_by_id,
            source_commit=source_commit,
        )
        validate_semantic_sidecar(sidecar, evidence_ids)
        path = sidecar_dir / f"slide-{index:03d}.semantic.json"
        write_json(path, sidecar)
        sidecars.append(sidecar)
        sidecar_paths.append(path)

    visual_dna = _build_visual_dna(artifacts, source_commit)
    design_system = _build_design_system(source_commit)
    template_spec = _build_template_spec(blueprints, architecture_by_slide, fit_by_slide, sidecars, source_commit)
    _validate_schema(visual_dna, "visual_dna")
    _validate_schema(design_system, "phase4_design_system")
    _validate_schema(template_spec, "phase4_editable_template_spec")
    visual_dna_path = write_json(preparation / "visual_dna.json", visual_dna)
    design_system_path = write_json(preparation / "design_system.json", design_system)
    editable_template_spec_path = write_json(preparation / "editable_template_spec.json", template_spec)

    prompts = _build_prompts(artifacts, sidecars, visual_dna, design_system)
    prompt_paths: list[Path] = []
    for filename, prompt in zip(PROMPT_FILENAMES, prompts, strict=True):
        _validate_schema(prompt, "platform_image_request")
        prompt_paths.append(write_json(prompt_dir / filename, prompt))

    pending_manifest = _build_pending_manifest(prompts[-6:], sidecars, source_commit)
    _validate_schema(pending_manifest, "phase4_pending_visual_target_manifest")
    pending_manifest_path = write_json(manifests_dir / "pending_visual_target_manifest.json", pending_manifest)

    capability = build_capability_attestation()
    _validate_schema(capability, "platform_image_capability_attestation")
    capability_attestation_path = write_json(capability_dir / "capability_attestation.json", capability)

    phase3_provenance = {
        "schema_name": "phase4_input_provenance",
        "schema_version": "1.0.0",
        "source_commit": source_commit,
        "phase3_run_id": artifacts["deckcompiler_run_manifest.json"]["run_id"],
        "phase3_artifact_hashes": artifacts["phase3_validation_report.json"]["deterministic_artifact_hashes"],
        "phase3_verdict": "GO",
        "evidence_unit_ids": sorted(evidence_ids),
        "source_count": len(artifacts["source_corpus.json"]["sources"]),
        "evidence_unit_count": len(evidence_units),
        "module_count": len(artifacts["presentation_architecture.json"]["modules"]),
        "batch_count": sum(len(item["batches"]) for item in artifacts["presentation_architecture.json"]["modules"]),
        "slide_count": len(blueprints),
    }
    _validate_schema(phase3_provenance, "phase4_input_provenance")
    write_json(output / "phase3_input" / "input_provenance.json", phase3_provenance)

    run_manifest = {
        "schema_name": "phase4b_run_manifest",
        "schema_version": "1.0.0",
        "run_id": stable_id("phase4b", artifacts["deckcompiler_run_manifest.json"]["run_id"], source_commit),
        "source_commit": source_commit,
        "phase3_run_id": artifacts["deckcompiler_run_manifest.json"]["run_id"],
        "artifact_counts": {"semantic_sidecars": 6, "prompts": 13, "generated_images": 0},
        "execution_counts": {
            "external_provider_transport_calls": 0,
            "repository_network_calls": 0,
            "credential_lookups": 0,
            "platform_tool_invocations": 0,
            "pngtopptx_invocations": 0,
        },
        "status": "PREPARED_NO_IMAGE_EXECUTION",
        "final_release_eligible": False,
    }
    write_json(output / "deckcompiler_run_manifest.json", run_manifest)

    validation = validate_visual_preparation(output)
    if not validation.valid:
        raise DeckCompilerError(
            "DC_PHASE4B_VALIDATION_FAILED",
            "visual_preparation_validation",
            "; ".join(validation.issues),
        )
    validation_payload = {
        "schema_name": "phase4b_visual_preparation_validation_report",
        "schema_version": "1.0.0",
        "report_id": stable_id("phase4breport", source_commit, validation.checks),
        "source_commit": source_commit,
        "verdict": "GO",
        "checks": validation.checks,
        "execution_counts": run_manifest["execution_counts"],
        "final_release_eligible": False,
    }
    validation_report_path = write_json(reports_dir / "phase4b_validation_report.json", validation_payload)
    return Phase4VisualPreparationResult(
        output_dir=output,
        sidecar_paths=tuple(sidecar_paths),
        prompt_paths=tuple(prompt_paths),
        visual_dna_path=visual_dna_path,
        design_system_path=design_system_path,
        editable_template_spec_path=editable_template_spec_path,
        pending_manifest_path=pending_manifest_path,
        capability_attestation_path=capability_attestation_path,
        validation_report_path=validation_report_path,
        evidence_ids=evidence_ids,
    )


def validate_semantic_sidecar(sidecar: dict[str, Any], evidence_ids: Iterable[str]) -> None:
    """Fail closed on Sidecar schema, evidence, raster, OCR, or hash violations."""

    metadata_candidate = sidecar.get("phase4_metadata", {})
    if (
        metadata_candidate.get("ocr_canonical_text_forbidden") is not True
        or metadata_candidate.get("visual_target_is_not_semantic_source") is not True
    ):
        raise DeckCompilerError(
            "DC_PHASE4B_OCR_CANONICAL_TEXT",
            "semantic_sidecar_validation",
            "OCR or the Visual Target cannot become canonical semantic content",
        )
    _validate_schema(sidecar, "phase4_semantic_sidecar")
    known_evidence = set(evidence_ids)
    core = sidecar["sidecar"]
    metadata = sidecar["phase4_metadata"]
    referenced = {
        evidence_id
        for binding in core["source_bindings"]
        for evidence_id in binding["evidence_ids"]
    }
    unknown = referenced - known_evidence
    if unknown:
        raise DeckCompilerError(
            "DC_PHASE4B_UNKNOWN_EVIDENCE",
            "semantic_sidecar_validation",
            f"Sidecar references unknown Evidence Unit IDs: {sorted(unknown)}",
        )
    bound_elements = {binding["element"] for binding in core["source_bindings"]}
    unbound = set(metadata["factual_content_item_ids"]) - bound_elements
    if unbound:
        raise DeckCompilerError(
            "DC_PHASE4B_FACTUAL_CONTENT_UNBOUND",
            "semantic_sidecar_validation",
            f"Factual content items are not evidence-bound: {sorted(unbound)}",
        )
    native = {item["slot_id"] for item in core["native_required"]}
    raster = {item["slot_id"] for item in core["raster_allowed"]}
    overlap = native & raster
    if overlap:
        raise DeckCompilerError(
            "DC_PHASE4B_NATIVE_RASTER_OVERLAP",
            "semantic_sidecar_validation",
            f"Native and raster slot sets overlap: {sorted(overlap)}",
        )
    forbidden = sorted(
        slot_id
        for slot_id in raster
        if any(marker in slot_id.lower() for marker in FORBIDDEN_RASTER_SLOT_MARKERS)
    )
    if forbidden or not metadata["full_slide_raster_forbidden"]:
        raise DeckCompilerError(
            "DC_PHASE4B_FULL_SLIDE_RASTER",
            "semantic_sidecar_validation",
            f"Forbidden full-slide raster slot or policy: {forbidden}",
        )
    if core["content_hash"] != content_sha256(core["canonical_content"]):
        raise DeckCompilerError(
            "DC_PHASE4B_CONTENT_HASH_MISMATCH",
            "semantic_sidecar_validation",
            "Sidecar canonical content hash does not match",
        )
    expected_artifact_hash = sidecar["artifact_hash"]
    value = copy.deepcopy(sidecar)
    value.pop("artifact_hash", None)
    if expected_artifact_hash != content_sha256(value):
        raise DeckCompilerError(
            "DC_PHASE4B_ARTIFACT_HASH_MISMATCH",
            "semantic_sidecar_validation",
            "Sidecar wrapper artifact hash does not match",
        )


def validate_visual_preparation(phase4_run: str | Path) -> Phase4VisualPreparationValidation:
    root = Path(phase4_run).resolve()
    issues: list[str] = []
    checks: dict[str, Any] = {}
    sidecar_dir = root / "preparation" / "semantic_sidecars"
    prompt_dir = root / "preparation" / "prompts"
    sidecar_paths = sorted(sidecar_dir.glob("*.semantic.json")) if sidecar_dir.is_dir() else []
    prompt_paths = [prompt_dir / name for name in PROMPT_FILENAMES if (prompt_dir / name).is_file()]
    checks["semantic_sidecar_count"] = len(sidecar_paths)
    checks["prompt_artifact_count"] = len(prompt_paths)
    if len(sidecar_paths) != 6:
        issues.append(f"semantic_sidecar_count={len(sidecar_paths)}")
    if len(prompt_paths) != 13:
        issues.append(f"prompt_artifact_count={len(prompt_paths)}")

    evidence_path = root / "phase3_input" / "input_provenance.json"
    input_provenance = read_json(evidence_path) if evidence_path.is_file() else {}
    source_commit = input_provenance.get("source_commit")
    checks["source_commit_present"] = isinstance(source_commit, str) and len(source_commit) == 40
    if not checks["source_commit_present"]:
        issues.append("source_commit_missing")

    evidence_ids = set(input_provenance.get("evidence_unit_ids", []))
    manifest_path = root / "manifests" / "pending_visual_target_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    for path in sidecar_paths:
        try:
            validate_semantic_sidecar(read_json(path), evidence_ids)
        except (DeckCompilerError, ValueError) as exc:
            issues.append(f"{path.name}: {exc}")

    for path, schema_name in (
        (root / "preparation" / "visual_dna.json", "visual_dna"),
        (root / "preparation" / "design_system.json", "phase4_design_system"),
        (root / "preparation" / "editable_template_spec.json", "phase4_editable_template_spec"),
        (manifest_path, "phase4_pending_visual_target_manifest"),
        (root / "records" / "capability" / "capability_attestation.json", "platform_image_capability_attestation"),
    ):
        if not path.is_file():
            issues.append(f"missing:{path.name}")
            continue
        try:
            _validate_schema(read_json(path), schema_name)
        except DeckCompilerError as exc:
            issues.append(str(exc))

    prompt_hash_mismatch_count = 0
    for path in prompt_paths:
        prompt = read_json(path)
        try:
            _validate_schema(prompt, "platform_image_request")
        except DeckCompilerError as exc:
            issues.append(str(exc))
        expected = prompt.get("prompt_hash")
        value = copy.deepcopy(prompt)
        value.pop("prompt_hash", None)
        if expected != content_sha256(value):
            prompt_hash_mismatch_count += 1
    checks["prompt_hash_mismatch_count"] = prompt_hash_mismatch_count
    if prompt_hash_mismatch_count:
        issues.append(f"prompt_hash_mismatch_count={prompt_hash_mismatch_count}")

    targets = manifest.get("targets", [])
    checks["pending_visual_target_count"] = len(targets)
    checks["actual_generation_count"] = sum(bool(item.get("actual_generation")) for item in targets)
    checks["selected_target_count"] = sum(bool(item.get("selected")) for item in targets)
    if len(targets) != 6:
        issues.append(f"pending_visual_target_count={len(targets)}")
    if checks["actual_generation_count"] or checks["selected_target_count"]:
        issues.append("pending_manifest_contains_generated_or_selected_target")

    sidecar_pairs = {
        payload["expected_visual_target_id"]: payload["sidecar_id"]
        for payload in (read_json(path) for path in sidecar_paths)
    }
    manifest_pairs = {
        item.get("visual_target_id"): item.get("expected_sidecar_id") for item in targets
    }
    checks["target_sidecar_pairing_valid"] = sidecar_pairs == manifest_pairs
    if not checks["target_sidecar_pairing_valid"]:
        issues.append("target_sidecar_pairing_invalid")

    generated_files = [
        path for path in (root / "preparation").rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".pptx", ".html"}
    ] if (root / "preparation").exists() else []
    checks["forbidden_generated_file_count"] = len(generated_files)
    if generated_files:
        issues.append("preparation_contains_png_pptx_or_html")
    checks["external_provider_transport_calls"] = manifest.get("external_transport_calls", -1)
    checks["platform_tool_calls"] = manifest.get("platform_tool_calls", -1)
    if checks["external_provider_transport_calls"] != 0 or checks["platform_tool_calls"] != 0:
        issues.append("execution_count_nonzero")
    return Phase4VisualPreparationValidation(not issues, tuple(issues), checks)


def _load_phase3_input(root: Path) -> dict[str, dict[str, Any]]:
    if not root.is_dir():
        raise DeckCompilerError(
            "DC_PHASE4B_INPUT_INVALID",
            "visual_preparation_input",
            f"Phase 3 run directory does not exist: {root}",
        )
    missing = [name for name in REQUIRED_PHASE3_FILES if not (root / name).is_file()]
    if missing:
        raise DeckCompilerError(
            "DC_PHASE4B_INPUT_INVALID",
            "visual_preparation_input",
            f"Phase 3 run is missing required artifacts: {missing}",
        )
    forbidden = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".pptx", ".html"}
    ]
    if forbidden:
        raise DeckCompilerError(
            "DC_PHASE4B_INPUT_INVALID",
            "visual_preparation_input",
            f"Phase 3 run contains forbidden downstream files: {forbidden}",
        )
    try:
        return {name: read_json(root / name) for name in REQUIRED_PHASE3_FILES}
    except (OSError, ValueError) as exc:
        raise DeckCompilerError(
            "DC_PHASE4B_INPUT_INVALID",
            "visual_preparation_input",
            str(exc),
        ) from exc


def _validate_phase3_input(artifacts: dict[str, dict[str, Any]]) -> str:
    manifest = artifacts["deckcompiler_run_manifest.json"]
    report = artifacts["phase3_validation_report.json"]
    graph = artifacts["artifact_graph.json"]
    if manifest.get("run_status") != "completed" or report.get("verdict") != "GO" or graph.get("validation_status") != "valid":
        raise DeckCompilerError("DC_PHASE4B_INPUT_INVALID", "visual_preparation_input", "Phase 3 run is not GO/valid")
    source_commit = str(manifest.get("source_commit") or "")
    current_commit = current_source_commit()
    if source_commit != current_commit:
        raise DeckCompilerError(
            "DC_PHASE4B_SOURCE_COMMIT_MISMATCH",
            "visual_preparation_input",
            f"Phase 3 source_commit {source_commit} does not equal current HEAD {current_commit}",
        )
    blueprints = artifacts["slide_blueprint_collection.json"]["slides"]
    source_count = len(artifacts["source_corpus.json"]["sources"])
    evidence_count = len(artifacts["evidence_unit_registry.json"]["evidence_units"])
    modules = artifacts["presentation_architecture.json"]["modules"]
    batch_count = sum(len(item["batches"]) for item in modules)
    input_request = artifacts["input_request.json"]
    if input_request.get("mode") == "prompt_plus_two_pdfs":
        if (source_count, evidence_count, len(modules), batch_count) != (3, 29, 3, 3):
            raise DeckCompilerError(
                "DC_PHASE4B_INPUT_INVALID",
                "visual_preparation_input",
                "Canonical Phase 3 run counts must be sources/evidence/modules/batches = 3/29/3/3",
            )
    else:
        expected_source_count = 1 + len(input_request.get("pdfs", []))
        if (
            source_count != expected_source_count
            or evidence_count < 1
            or len(modules) != 3
            or batch_count != 3
        ):
            raise DeckCompilerError(
                "DC_PHASE4B_INPUT_INVALID",
                "visual_preparation_input",
                "General Phase 3 source/evidence/module/batch counts are inconsistent",
            )
    if len(blueprints) != 6:
        raise DeckCompilerError("DC_PHASE4B_SLIDE_COUNT", "visual_preparation_input", "Phase 4B requires exactly six slides")
    architecture = sorted(artifacts["presentation_architecture.json"]["slides"], key=lambda item: item["order"])
    blueprint_order = [item["slide_id"] for item in blueprints]
    architecture_order = [item["slide_id"] for item in architecture]
    if blueprint_order != architecture_order:
        raise DeckCompilerError(
            "DC_PHASE4B_SLIDE_ORDER",
            "visual_preparation_input",
            "Blueprint and Presentation Architecture slide order differ",
        )
    if len(graph.get("nodes", [])) != 16 or len(graph.get("edges", [])) != 24 or graph.get("orphan_artifact_ids"):
        raise DeckCompilerError("DC_PHASE4B_INPUT_INVALID", "visual_preparation_input", "Phase 3 graph is not 16/24/0")
    return source_commit


def _prepare_output_directory(path: Path) -> Path:
    output = path.resolve()
    repo_root = REPO_ROOT.resolve()
    protected_names = {
        "editable_template_spec.final.json",
        "golden_template_masters.pptx",
        "final_deck_large_premium.pptx",
    }
    if output == repo_root or output.is_relative_to(repo_root) or output.name in protected_names:
        raise DeckCompilerError(
            "DC_PHASE4B_OUTPUT_PROTECTED",
            "visual_preparation_output",
            "Phase 4 runtime output must be a new directory outside the repository and protected outputs",
            output.as_posix(),
        )
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise DeckCompilerError(
            "DC_PHASE4B_OUTPUT_NOT_EMPTY",
            "visual_preparation_output",
            "Phase 4 runtime output must be new or empty",
            output.as_posix(),
        )
    output.mkdir(parents=True, exist_ok=True)
    return output


def _build_sidecar(
    *,
    blueprint: dict[str, Any],
    architecture_slide: dict[str, Any],
    fit: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    source_commit: str,
) -> dict[str, Any]:
    evidence_ids = [item["citation_id"] for item in blueprint["citations"]]
    sidecar_id = stable_id("sidecar", blueprint["slide_id"], source_commit, evidence_ids)
    target_id = stable_id("visualtarget", blueprint["slide_id"], source_commit)
    content_items: list[dict[str, Any]] = [
        {"slot_id": "title", "kind": "text", "value": blueprint["title"]},
        {"slot_id": "subtitle", "kind": "text", "value": blueprint.get("subtitle") or ""},
    ]
    source_bindings: list[dict[str, Any]] = []
    factual_ids: list[str] = []
    content_hashes: dict[str, str] = {
        "title": content_sha256(blueprint["title"]),
        "subtitle": content_sha256(blueprint.get("subtitle") or ""),
    }
    body_blocks: list[dict[str, Any]] = []
    for index, block in enumerate(blueprint["content_blocks"]):
        item_id = block["block_id"]
        body_blocks.append({"content_item_id": item_id, "slot": block["slot"], "type": block["type"], "text": block["content"]})
        content_items.append({"slot_id": block["slot"], "kind": "text", "value": block["content"]})
        bound_id = evidence_ids[index] if index < len(evidence_ids) else evidence_ids[-1]
        source_bindings.append({"element": item_id, "evidence_ids": [bound_id]})
        factual_ids.append(item_id)
        content_hashes[item_id] = content_sha256(block["content"])
    for index, citation in enumerate(blueprint["citations"], start=1):
        citation_id = f"citation-{index:02d}"
        content_items.append({"slot_id": "footer", "kind": "citation", "value": citation})
        source_bindings.append({"element": citation_id, "evidence_ids": [citation["citation_id"]]})
        content_hashes[citation_id] = content_sha256(citation)
    if blueprint.get("speaker_notes"):
        content_items.append({"slot_id": "speaker_notes", "kind": "speaker_notes", "value": blueprint["speaker_notes"]})
        content_hashes["speaker_notes"] = content_sha256(blueprint["speaker_notes"])

    native_slots = _native_slot_ids(blueprint)
    raster_slots = [] if blueprint["slide_type"] == "option_comparison" else ["bounded_illustration"]
    native_required = [
        {"slot_id": slot_id, "object_type": _native_object_type(slot_id)} for slot_id in native_slots
    ]
    raster_allowed = [
        {"slot_id": slot_id, "usage": "replaceable_image_frame"} for slot_id in raster_slots
    ]
    exact_numbers = []
    for evidence_id in evidence_ids:
        data = evidence_by_id[evidence_id].get("canonical_content", {}).get("data")
        if isinstance(data, dict):
            exact_numbers.append({"evidence_id": evidence_id, **data})
    exact_units = sorted({str(item["unit"]) for item in exact_numbers if item.get("unit") is not None})
    diagram_nodes = []
    diagram_edges = []
    if blueprint["slide_type"] in {"process_explainer", "implementation_roadmap"}:
        diagram_nodes = [
            {"node_id": f"node-{index:02d}", "exact_label": block["content"], "evidence_id": evidence_ids[index - 1]}
            for index, block in enumerate(blueprint["content_blocks"], start=1)
        ]
        diagram_edges = [
            {"edge_id": f"edge-{index:02d}", "from": diagram_nodes[index - 1]["node_id"], "to": diagram_nodes[index]["node_id"], "exact_label": ""}
            for index in range(1, len(diagram_nodes))
        ]
    table_data = blueprint.get("table_data")
    if table_data is None and blueprint["slide_type"] == "option_comparison":
        table_data = {
            "columns": ["evidence_statement"],
            "rows": [{"row_id": item["content_item_id"], "cells": [item["text"]]} for item in body_blocks],
        }
    chart_data = blueprint.get("chart_data") or {"series": []}
    core = {
        "schema_name": "slide_semantic_sidecar",
        "schema_version": "1.0.0",
        "slide_id": blueprint["slide_id"],
        "module_id": architecture_slide["module_id"],
        "batch_id": architecture_slide["batch_id"],
        "template_family_id": fit["template_family_id"],
        "layout_id": fit["layout_id"],
        "canonical_content": content_items,
        "native_required": native_required,
        "raster_allowed": raster_allowed,
        "source_bindings": source_bindings,
        "editability_policy": {
            "full_slide_raster": "forbidden",
            "text": "native_required",
            "tables": "native_required",
            "charts": "native_required",
            "cards": "native_required",
            "image_frames": "replaceable",
            "speaker_notes": "native_required",
        },
        "content_hash": content_sha256(content_items),
    }
    metadata = {
        "slide_role": blueprint["slide_type"],
        "primary_message": blueprint["design_intent"],
        "exact_title": blueprint["title"],
        "exact_subtitle": blueprint.get("subtitle") or "",
        "exact_body_blocks": body_blocks,
        "exact_labels": [slot_id.upper() for slot_id in native_slots],
        "exact_numbers": exact_numbers,
        "exact_units": exact_units,
        "structured_table_data": table_data,
        "structured_chart_data": chart_data,
        "diagram_nodes": diagram_nodes,
        "diagram_edges": diagram_edges,
        "citations": blueprint["citations"],
        "evidence_unit_bindings": sorted(set(evidence_ids)),
        "canonical_content_hashes": dict(sorted(content_hashes.items())),
        "source_note_policy": "Visible native footer/source-note region; exact citation text remains Sidecar authority.",
        "native_required_slot_ids": native_slots,
        "raster_allowed_slot_ids": raster_slots,
        "accessibility_description": f"{blueprint['title']}. {blueprint['design_intent']}",
        "speaker_note_candidates": [blueprint["speaker_notes"]] if blueprint.get("speaker_notes") else [],
        "factual_content_item_ids": factual_ids,
        "full_slide_raster_forbidden": True,
        "ocr_canonical_text_forbidden": True,
        "visual_target_is_not_semantic_source": True,
    }
    wrapper = {
        "schema_name": "phase4_semantic_sidecar",
        "schema_version": "1.0.0",
        "sidecar_id": sidecar_id,
        "expected_visual_target_id": target_id,
        "source_commit": source_commit,
        "sidecar": core,
        "phase4_metadata": metadata,
    }
    wrapper["artifact_hash"] = content_sha256(wrapper)
    return wrapper


def _native_slot_ids(blueprint: dict[str, Any]) -> list[str]:
    ordered = ["title", "subtitle", *blueprint["required_slots"], "source_notes", "page_number"]
    return list(dict.fromkeys(ordered))


def _native_object_type(slot_id: str) -> str:
    if slot_id == "table":
        return "table"
    if slot_id in {"chart", "kpi"}:
        return "chart"
    if slot_id in {"process", "timeline"}:
        return "connector"
    if slot_id in {"footer", "source_notes", "page_number"}:
        return "footer"
    return "text_box"


def _build_visual_dna(artifacts: dict[str, dict[str, Any]], source_commit: str) -> dict[str, Any]:
    modules = artifacts["module_art_directions.json"]["modules"]
    fixed = {
        "tone": ["professional", "academic", "authoritative technical", "contemporary editorial"],
        "readability": "High readability at presentation distance; no microtext.",
        "hierarchy": "One dominant focal point with clear title, evidence, and source-note tiers.",
        "palette_relationship": "Restrained cool-neutral field with limited risk and action accents.",
        "typography_character": "Contemporary editorial sans-serif with technical restraint.",
        "citation_treatment": "Visible quiet native footer rail with strong contrast and safe margins.",
        "diagram_grammar": "Native nodes, connectors, matrices, and roadmap stages with explicit reading direction.",
        "illustration_grammar": "Bounded continuous-tone technical editorial illustration; never a final slide surface.",
        "spacing_rhythm": "Generous outer margins, stable baseline gaps, and intentional negative space.",
        "safe_areas": ["title", "footer", "source_notes", "page_number"],
        "native_editability_intent": True,
        "forbidden": [
            "microtext", "full-slide screenshot", "full-slide raster", "random logo", "watermark",
            "repetitive dashboard template", "generic corporate card wall", "decorative blob collage",
        ],
    }
    freedom = [
        "composition archetype", "visual metaphor", "asymmetry", "focal point", "negative space",
        "layering", "depth", "panel geometry", "diagram arrangement", "title placement",
        "reading direction", "transition energy", "illustration composition",
    ]
    differentiation = [
        {
            "module_id": item["module_id"],
            "visual_metaphor": item["visual_metaphor"],
            "composition_energy": item["composition_energy"],
            "focal_behavior": item["focal_behavior"],
            "spatial_direction": item["spatial_direction"],
            "density_range": item["density_range"],
        }
        for item in modules
    ]
    semantic = {"source_commit": source_commit, "fixed_constraints": fixed, "creative_degrees_of_freedom": freedom, "module_differentiation": differentiation}
    return {
        "schema_name": "visual_dna",
        "schema_version": "1.0.0",
        "visual_dna_id": stable_id("visualdna", semantic),
        **semantic,
        "implementation_provenance": "build_week_new",
    }


def _build_design_system(source_commit: str) -> dict[str, Any]:
    typography = {
        "title": {"font_family": "Aptos Display", "size_pt": 30, "weight": 650, "color": "#102A43", "line_height": 1.05},
        "section_title": {"font_family": "Aptos Display", "size_pt": 22, "weight": 600, "color": "#102A43", "line_height": 1.1},
        "body": {"font_family": "Aptos", "size_pt": 16, "weight": 400, "color": "#243B53", "line_height": 1.25},
        "label": {"font_family": "Aptos", "size_pt": 12, "weight": 600, "color": "#486581", "line_height": 1.15},
        "footer": {"font_family": "Aptos", "size_pt": 9, "weight": 400, "color": "#627D98", "line_height": 1.1},
    }
    base = {
        "schema_version": "1.0.0",
        "design_system_id": stable_id("designsystem", source_commit, typography),
        "canvas": {"width_in": 13.333333333333334, "height_in": 7.5, "aspect_ratio": "16:9"},
        "colors": {"background": "#F5F8FA", "surface": "#FFFFFF", "text": "#102A43", "muted_text": "#627D98", "accent": "#087E8B", "risk": "#C44536", "action": "#2A6F97"},
        "typography": typography,
        "spacing": {"page_margin_x_in": 0.6, "page_margin_y_in": 0.38, "grid_gap_in": 0.22, "card_padding_in": 0.22},
        "shape_style": {"card_radius_in": 0.08, "hairline_pt": 0.8, "shadow_style": "subtle elevation only"},
        "components": {
            "source_rail": {"component_type": "footer_component", "allowed_slots": ["footer", "source_notes"]},
            "bounded_illustration_frame": {"component_type": "image_frame", "allowed_slots": ["bounded_illustration"]},
        },
    }
    policy = {
        "line_weight_families": [0.8, 1.5, 2.5],
        "citation_footer_policy": "Native, visible, quiet, and never rasterized.",
        "minimum_legibility": {"body_pt": 16, "label_pt": 12, "footer_pt": 9, "microtext_forbidden": True},
        "safe_area_rules": {"title_top": 0.05, "footer_bottom": 0.03, "outer_margin": 0.05},
        "native_raster_policy": {"semantic_slots": "native_required", "bounded_continuous_tone": "raster_allowed", "overlap_allowed": False},
        "full_slide_raster_prohibited": True,
        "module_differentiation_range": "composition, metaphor, focal behavior, density, and directional energy may vary by module",
        "composition_freedom": ["title placement", "panel count", "focal point", "negative space", "diagram type", "density level", "reading direction"],
    }
    wrapper = {"schema_name": "phase4_design_system", "schema_version": "1.0.0", "source_commit": source_commit, "design_system": base, "policy": policy}
    wrapper["content_hash"] = content_sha256(wrapper)
    return wrapper


def _build_template_spec(
    blueprints: list[dict[str, Any]],
    architecture_by_slide: dict[str, dict[str, Any]],
    fit_by_slide: dict[str, dict[str, Any]],
    sidecars: list[dict[str, Any]],
    source_commit: str,
) -> dict[str, Any]:
    sidecar_by_slide = {item["sidecar"]["slide_id"]: item for item in sidecars}
    layouts = []
    assignments = []
    capacity_limits: dict[str, Any] = {}
    for blueprint in blueprints:
        slide_id = blueprint["slide_id"]
        fit = fit_by_slide[slide_id]
        sidecar = sidecar_by_slide[slide_id]
        native_slots = sidecar["phase4_metadata"]["native_required_slot_ids"]
        raster_slots = sidecar["phase4_metadata"]["raster_allowed_slot_ids"]
        slots = _layout_slots(native_slots, raster_slots)
        layout = {
            "layout_id": fit["layout_id"],
            "archetype": _layout_archetype(blueprint["slide_type"]),
            "background": {"type": "solid_native_shape", "bounds": {"x": 0, "y": 0, "w": 1, "h": 1}, "editable": True, "full_slide": False},
            "bounds": {"x": 0, "y": 0, "w": 1, "h": 1},
            "slots": slots,
            "components": [],
            "confidence": 0.92,
            "assumptions": ["Normalized planning geometry only; actual PPTX geometry is out of Phase 4B scope."],
            "fallback_layout": fit["layout_id"],
            "hierarchy": [slot["slot_id"] for slot in slots],
            "notes": "All real semantic content is native/editable; bounded illustration is replaceable and never full-canvas.",
        }
        layouts.append(layout)
        assignments.append({
            "slide_id": slide_id,
            "module_id": architecture_by_slide[slide_id]["module_id"],
            "batch_id": architecture_by_slide[slide_id]["batch_id"],
            "template_family_id": fit["template_family_id"],
            "layout_id": fit["layout_id"],
            "required_slot_ids": native_slots,
        })
        capacity_limits[fit["layout_id"]] = {
            "content_density": blueprint["content_density"],
            "body_block_count": len(blueprint["content_blocks"]),
            "citation_count": len(blueprint["citations"]),
            "microtext_forbidden": True,
        }
    base = {
        "schema_version": "1.0.0",
        "template_id": stable_id("template", source_commit, [item["layout_id"] for item in layouts]),
        "design_system_ref": "design_system.json",
        "canvas": {"width_in": 13.333333333333334, "height_in": 7.5, "aspect_ratio": "16:9"},
        "layouts": layouts,
    }
    planning = {
        "geometry_level": "planning_normalized",
        "slide_layout_assignments": assignments,
        "safe_areas": {"title": {"top": 0.05}, "footer": {"bottom": 0.03}, "source_notes": {"bottom": 0.08}},
        "capacity_limits": capacity_limits,
        "native_raster_policy": {"native_raster_overlap": 0, "full_canvas_raster_components": 0, "semantic_raster_slots": 0},
        "prohibited_uses": ["full-slide screenshot", "full-canvas raster", "raster semantic text", "raster citation", "slot outside canvas", "microtext capacity workaround"],
    }
    wrapper = {"schema_name": "phase4_editable_template_spec", "schema_version": "1.0.0", "source_commit": source_commit, "template_spec": base, "planning_contract": planning}
    wrapper["content_hash"] = content_sha256(wrapper)
    return wrapper


def _layout_slots(native_slots: list[str], raster_slots: list[str]) -> list[dict[str, Any]]:
    fixed_bounds = {
        "title": {"x": 0.06, "y": 0.05, "w": 0.78, "h": 0.10},
        "subtitle": {"x": 0.06, "y": 0.16, "w": 0.68, "h": 0.06},
        "source_notes": {"x": 0.06, "y": 0.85, "w": 0.78, "h": 0.045},
        "footer": {"x": 0.06, "y": 0.91, "w": 0.78, "h": 0.04},
        "page_number": {"x": 0.90, "y": 0.91, "w": 0.04, "h": 0.04},
    }
    main = [slot for slot in native_slots if slot not in fixed_bounds]
    main_width = 0.52 if raster_slots else 0.88
    main_height = 0.54 / max(1, len(main))
    slots = []
    for slot_id in native_slots:
        if slot_id in fixed_bounds:
            bounds = fixed_bounds[slot_id]
        else:
            index = main.index(slot_id)
            bounds = {"x": 0.06, "y": 0.26 + index * main_height, "w": main_width, "h": max(0.10, main_height - 0.025)}
        slots.append({
            "slot_id": slot_id,
            "type": _template_slot_type(slot_id),
            "role": slot_id,
            "bounds": bounds,
            "editable": True,
            "density": "normal",
            "style_ref": "native-semantic",
            "confidence": 0.92,
            "fallback_behavior": "fail_closed_recompose",
            "hierarchy": len(slots),
            "allowed_input_types": ["semantic_sidecar"],
        })
    for slot_id in raster_slots:
        slots.append({
            "slot_id": slot_id,
            "type": "image",
            "role": "bounded non-semantic illustration",
            "bounds": {"x": 0.62, "y": 0.26, "w": 0.32, "h": 0.54},
            "editable": True,
            "density": "sparse",
            "style_ref": "replaceable-bounded-raster",
            "confidence": 0.90,
            "fallback_behavior": "omit_without_semantic_loss",
            "hierarchy": len(slots),
            "allowed_input_types": ["bounded_technical_illustration", "continuous_tone_artwork"],
        })
    return slots


def _template_slot_type(slot_id: str) -> str:
    if slot_id == "table":
        return "table"
    if slot_id == "chart":
        return "chart"
    if slot_id == "kpi":
        return "kpi"
    if slot_id in {"footer", "source_notes", "page_number"}:
        return "footer"
    if slot_id in {"process", "timeline"}:
        return "card_group"
    if slot_id == "callout":
        return "callout"
    return "text"


def _layout_archetype(slide_type: str) -> str:
    return {
        "decision_framing": "cover_hero",
        "process_explainer": "process_timeline",
        "risk_findings": "card_grid",
        "option_comparison": "comparison_matrix",
        "recommendation": "case_study",
        "implementation_roadmap": "agenda_roadmap",
    }[slide_type]


def _build_prompts(
    artifacts: dict[str, dict[str, Any]],
    sidecars: list[dict[str, Any]],
    visual_dna: dict[str, Any],
    design_system: dict[str, Any],
) -> list[dict[str, Any]]:
    visual_ref = {"path": "visual_dna.json", "sha256": content_sha256(visual_dna)}
    design_ref = {"path": "design_system.json", "sha256": design_system["content_hash"]}
    prompts: list[dict[str, Any]] = []
    design_board_id = stable_id("designboard", visual_ref, design_ref)
    prompts.append(_build_prompt(
        target_id=design_board_id,
        artifact_type="design_board",
        visual_ref=visual_ref,
        design_ref=design_ref,
        prompt_text=(
            "Create one spacious landscape 16:9 contemporary technical-editorial design board for a professional academic presentation. "
            "Show palette relationships, typography character, shape and line-weight language, diagram and chart grammar, citation/footer treatment, negative-space behavior, and three visibly distinct module moods. "
            "Use only generic semantic placeholders such as TITLE, PRIMARY VISUAL, PROCESS, EVIDENCE, COMPARISON, RECOMMENDATION, IMPLEMENTATION, and SOURCE NOTES. "
            "No source claims, statistics, citations, paragraphs, microtext, logos, watermarks, screenshots, dashboards, blob collages, or generic card walls. Make the grammar reconstructable with native slide objects."
        ),
        composition_goals=["one coherent design language", "three differentiated module moods", "reconstructable editorial primitives"],
        hierarchy_goals=["clear title tier", "visual grammar tier", "quiet citation/footer tier"],
        negative_space_target="generous and intentionally distributed",
        prior_refs=[],
    ))

    module_directions = artifacts["module_art_directions.json"]["modules"]
    module_target_by_id: dict[str, str] = {}
    for direction in module_directions:
        target_id = stable_id("moduleanchor", direction["module_id"], design_board_id)
        module_target_by_id[direction["module_id"]] = target_id
        prompt_text = (
            "Create a landscape 16:9 module art-direction anchor, not a final slide. Preserve the selected design-board language while expressing this module's visual metaphor, composition energy, focal behavior, illustration language, diagram language, density range, and directional movement. "
            f"Visual metaphor: {direction['visual_metaphor']}. Composition energy: {direction['composition_energy']}. Focal behavior: {direction['focal_behavior']}. "
            f"Illustration language: {direction['illustration_language']}. Diagram language: {direction['diagram_language']}. Spatial direction: {direction['spatial_direction']}. Density: {direction['density_range']}. "
            "Use only generic placeholders TITLE, PRIMARY VISUAL, PROCESS, EVIDENCE, COMPARISON, RECOMMENDATION, IMPLEMENTATION, SOURCE NOTES. No final facts, statistics, citations, paragraphs, microtext, logos, or watermarks."
        )
        prompts.append(_build_prompt(
            target_id=target_id, artifact_type="module_anchor", module_id=direction["module_id"],
            visual_ref=visual_ref, design_ref=design_ref, prompt_text=prompt_text,
            composition_goals=[direction["visual_metaphor"], direction["composition_energy"], direction["spatial_direction"]],
            hierarchy_goals=[direction["focal_behavior"], direction["contrast_strategy"]],
            negative_space_target=f"compatible with {direction['density_range']} density",
            prior_refs=[design_board_id],
        ))

    candidate_by_family = {item["family_id"]: item for item in artifacts["creative_fit_report.json"]["candidate_families"]}
    fit_by_slide = {item["slide_id"]: item for item in artifacts["creative_template_architecture.json"]["slide_fit_decisions"]}
    architecture_slides = sorted(artifacts["presentation_architecture.json"]["slides"], key=lambda item: item["order"])
    first_slide_by_batch: dict[str, dict[str, Any]] = {}
    for slide in architecture_slides:
        first_slide_by_batch.setdefault(slide["batch_id"], slide)
    batch_target_by_id: dict[str, str] = {}
    for batch_id, slide in first_slide_by_batch.items():
        fit = fit_by_slide[slide["slide_id"]]
        family = candidate_by_family[fit["template_family_id"]]
        target_id = stable_id("batchreference", batch_id, fit["template_family_id"], module_target_by_id[slide["module_id"]])
        batch_target_by_id[batch_id] = target_id
        prompt_text = (
            "Create a landscape 16:9 batch template composition reference, not a final slide. Show focal, title-safe, evidence/data, diagram/table/chart, and source-note regions with clear reading direction, native editability, and bounded non-semantic raster intent. "
            f"Selected family composition archetype: {family['composition_archetype']}. Capacity intent: {family['capacity_intent']}. Expected visual regions: {', '.join(family['expected_visual_regions'])}. "
            "Use only placeholder labels TITLE, PRIMARY VISUAL, PROCESS, EVIDENCE, COMPARISON, RECOMMENDATION, IMPLEMENTATION, SOURCE NOTES. No final factual copy, statistics, citations, dense labels, microtext, logos, watermarks, screenshots, or full-slide raster."
        )
        prompts.append(_build_prompt(
            target_id=target_id, artifact_type="batch_template_reference", module_id=slide["module_id"], batch_id=batch_id,
            selected_family=fit["template_family_id"], selected_layout=fit["layout_id"], visual_ref=visual_ref, design_ref=design_ref,
            prompt_text=prompt_text, composition_goals=[family["composition_archetype"], *family["expected_visual_regions"]],
            hierarchy_goals=[family["capacity_intent"], family["editability_intent"]], negative_space_target="enough open area for native semantic reconstruction",
            prior_refs=[design_board_id, module_target_by_id[slide["module_id"]]],
        ))

    sidecar_by_slide = {item["sidecar"]["slide_id"]: item for item in sidecars}
    blueprint_by_slide = {item["slide_id"]: item for item in artifacts["slide_blueprint_collection.json"]["slides"]}
    for slide in architecture_slides:
        fit = fit_by_slide[slide["slide_id"]]
        sidecar = sidecar_by_slide[slide["slide_id"]]
        blueprint = blueprint_by_slide[slide["slide_id"]]
        role_goals = _slide_role_goals(blueprint["slide_type"])
        sidecar_ref = {"path": f"semantic_sidecars/slide-{slide['order']:03d}.semantic.json", "sidecar_id": sidecar["sidecar_id"], "sha256": sidecar["artifact_hash"]}
        prompt_text = (
            f"Create a landscape 16:9 full-slide visual reconstruction target for role {blueprint['slide_type']}. This is visual truth only, never the final slide surface. "
            f"Composition requirements: {', '.join(role_goals)}. Treat the linked Semantic Sidecar as the sole authority for exact wording, numbers, units, data, citations, accessibility, and native/raster policy. "
            "Reserve clean native reconstruction regions for title, subtitle, labels, body, structured data, citations, footer, and page number. Prefer no rendered text beyond large generic semantic labels. "
            "No paragraphs, full citations, tiny source notes, dense table text, tiny chart labels, pseudo-language, invented numbers, quotations, logos, watermarks, screenshots, dashboard walls, or full-slide raster background."
        )
        prompts.append(_build_prompt(
            target_id=sidecar["expected_visual_target_id"], artifact_type="slide_visual_target", slide_id=slide["slide_id"], module_id=slide["module_id"], batch_id=slide["batch_id"],
            selected_family=fit["template_family_id"], selected_layout=fit["layout_id"], visual_ref=visual_ref, design_ref=design_ref, sidecar_ref=sidecar_ref,
            prompt_text=prompt_text, composition_goals=role_goals, hierarchy_goals=[blueprint["design_intent"], "one dominant focal narrative"],
            negative_space_target="sufficient for native title, semantic objects, and visible source notes",
            prior_refs=[design_board_id, module_target_by_id[slide["module_id"]], batch_target_by_id[slide["batch_id"]]],
        ))
    if len(prompts) != 13:
        raise RuntimeError(f"Phase 4B prompt count must be 13, got {len(prompts)}")
    return prompts


def _slide_role_goals(slide_type: str) -> list[str]:
    return {
        "decision_framing": ["sparse hero composition", "strong focal visual", "generous negative space", "minimal annotation", "title and citation safe regions"],
        "process_explainer": ["diagram-led technical editorial composition", "clear directional process", "visible component relationships", "native connector and label space", "bounded technical illustration"],
        "risk_findings": ["evidence-led analytical composition", "prioritized causal risk field", "strong hierarchy among risks", "native data-callout regions", "readable focal risk narrative"],
        "option_comparison": ["comparative editorial composition", "visually distinct options", "balanced comparison geometry", "native table regions", "clear decision-criteria space"],
        "recommendation": ["decisive focal composition", "dominant recommendation region", "rationale hierarchy", "evidence-backed sparse structure", "transition into implementation"],
        "implementation_roadmap": ["directional roadmap", "visibly ordered phases and actions", "native steps and connectors", "explicit source-note region", "clear professional closing state"],
    }[slide_type]


def _build_prompt(
    *,
    target_id: str,
    artifact_type: str,
    visual_ref: dict[str, Any],
    design_ref: dict[str, Any],
    prompt_text: str,
    composition_goals: list[str],
    hierarchy_goals: list[str],
    negative_space_target: str,
    prior_refs: list[str],
    slide_id: str | None = None,
    module_id: str | None = None,
    batch_id: str | None = None,
    selected_family: str | None = None,
    selected_layout: str | None = None,
    sidecar_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt_id = stable_id("prompt", target_id, prompt_text)
    payload = {
        "schema_name": "platform_image_request",
        "schema_version": "1.0.0",
        "request_id": stable_id("imagerequest", prompt_id, target_id),
        "prompt_id": prompt_id,
        "target_artifact_id": target_id,
        "artifact_type": artifact_type,
        "slide_id": slide_id,
        "module_id": module_id,
        "batch_id": batch_id,
        "selected_family": selected_family,
        "selected_layout": selected_layout,
        "visual_dna_reference": visual_ref,
        "design_system_reference": design_ref,
        "semantic_sidecar_reference": sidecar_ref,
        "prior_selected_visual_reference_ids": prior_refs,
        "composition_goals": composition_goals,
        "hierarchy_goals": hierarchy_goals,
        "negative_space_target": negative_space_target,
        "native_raster_intent": {"semantic_slots": "native_required", "continuous_tone_art": "bounded_raster_allowed", "full_slide_raster": "forbidden"},
        "text_policy": {"reference_prompts": "generic_placeholders_only", "slide_prompts": "sidecar_authoritative_native_text_regions", "ocr_canonical_text": "forbidden"},
        "forbidden_elements": ["full-slide raster background", "screenshot slide", "microtext", "invented fact", "invented number", "invented citation", "random logo", "watermark", "pseudo-language"],
        "requested_orientation": "landscape",
        "requested_aspect_ratio": "16:9",
        "requested_dimensions": {"width": 2048, "height": 1152},
        "fallback_normalization_policy": {"allowed": ["aspect_preserving_crop", "aspect_preserving_pad", "uniform_resize_after_crop_or_pad"], "forbidden": ["stretch", "nonuniform_resize", "critical_content_clipping"], "minimum_final_dimensions": {"width": 1600, "height": 900}},
        "prompt_text": prompt_text,
        "implementation_provenance": "build_week_new",
        "execution_mode": "platform_managed_tool",
        "external_provider_id": None,
        "external_transport_used": False,
        "credential_lookup": False,
    }
    payload["prompt_hash"] = content_sha256(payload)
    return payload


def _build_pending_manifest(
    slide_prompts: list[dict[str, Any]],
    sidecars: list[dict[str, Any]],
    source_commit: str,
) -> dict[str, Any]:
    sidecar_by_slide = {item["sidecar"]["slide_id"]: item for item in sidecars}
    targets = []
    for prompt in slide_prompts:
        sidecar = sidecar_by_slide[prompt["slide_id"]]
        targets.append({
            "slide_id": prompt["slide_id"],
            "module_id": prompt["module_id"],
            "batch_id": prompt["batch_id"],
            "visual_target_id": prompt["target_artifact_id"],
            "expected_sidecar_id": sidecar["sidecar_id"],
            "prompt_id": prompt["prompt_id"],
            "selected_family": prompt["selected_family"],
            "selected_layout": prompt["selected_layout"],
            "generation_status": "PENDING",
            "actual_generation": False,
            "selected": False,
            "expected_aspect_ratio": "16:9",
            "final_surface_role_prohibited": True,
            "source_commit": source_commit,
            "validation_status": "valid",
        })
    payload = {
        "schema_name": "phase4_pending_visual_target_manifest",
        "schema_version": "1.0.0",
        "manifest_id": stable_id("pendingtargets", source_commit, targets),
        "source_commit": source_commit,
        "targets": targets,
        "external_transport_calls": 0,
        "platform_tool_calls": 0,
        "generated_image_count": 0,
        "validation_status": "valid",
    }
    payload["manifest_hash"] = content_sha256(payload)
    return payload


def _validate_schema(payload: dict[str, Any], schema_name: str) -> None:
    errors = sorted(validator_for(schema_name).iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        details = "; ".join(f"{'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}" for error in errors[:5])
        raise DeckCompilerError(
            "DC_PHASE4B_SCHEMA_INVALID",
            "visual_preparation_validation",
            f"{schema_name}: {details}",
        )
