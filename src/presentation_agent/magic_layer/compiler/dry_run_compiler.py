from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.presentation_agent.magic_layer.compiler.backend_capability import resolve_backend_capability
from src.presentation_agent.magic_layer.compiler.chart_table_mapper import map_chart_or_table
from src.presentation_agent.magic_layer.compiler.compile_blocker import detect_compile_blockers
from src.presentation_agent.magic_layer.compiler.dry_run_report import build_dry_run_report
from src.presentation_agent.magic_layer.compiler.image_frame_mapper import map_image_frame
from src.presentation_agent.magic_layer.compiler.instruction_normalizer import normalize_instruction
from src.presentation_agent.magic_layer.compiler.pptx_primitive import map_instruction_to_primitive
from src.presentation_agent.magic_layer.compiler.shape_text_mapper import map_shape_or_text
from src.presentation_agent.magic_layer.compiler.suppression_shape_mapper import map_suppression_shape
from src.presentation_agent.magic_layer.compiler.unsupported_instruction import evaluate_unsupported_instruction
from src.presentation_agent.magic_layer.compiler.validators.compiler_input_validator import validate_compiler_input
from src.presentation_agent.magic_layer.compiler.validators.primitive_plan_validator import validate_primitive_plan


def dry_run_compile_bundle(bundle: dict[str, Any], backend_name: str = "dry_run_only", input_bundle_path: str | None = None) -> dict[str, Any]:
    data = deepcopy(bundle)
    input_validation = validate_compiler_input(data)
    if not input_validation["pass"]:
        decision = _decision_from_failures(input_validation["failures"])
        primitive_plan = _empty_plan(data, input_validation["blockers"])
        return build_dry_run_report(report_id=f"{data.get('bundle_id', 'bundle')}_dry_run", input_bundle_path=input_bundle_path, backend_capability=resolve_backend_capability(backend_name), primitive_plan=primitive_plan, decision=decision, limitations=["invalid compiler input"])
    capability = resolve_backend_capability(backend_name)
    spec = data.get("editable_candidate_spec", {})
    primitives: list[dict[str, Any]] = []
    unsupported_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[dict[str, Any]] = []
    for instruction in spec.get("objects", []):
        normalized = normalize_instruction(instruction)
        if normalized["blockers"]:
            blockers.extend({"blocker_type": "instruction_normalization", "message": item, "instruction_id": instruction.get("instruction_id")} for item in normalized["blockers"])
            continue
        item = normalized["instruction"]
        unsupported = evaluate_unsupported_instruction(item, capability)
        if unsupported["warning_or_fatal"] == "warning":
            warnings.append(unsupported["reason"])
            unsupported_items.append(unsupported)
        if unsupported["blocks_compile"]:
            unsupported_items.append(unsupported)
            blockers.append({"blocker_type": "unsupported_required_instruction", "message": unsupported["reason"], "instruction_id": item.get("instruction_id")})
            continue
        mapped = _map_instruction(item, capability)
        if not mapped["pass"]:
            blockers.extend({"blocker_type": "mapping_failure", "message": failure, "instruction_id": item.get("instruction_id")} for failure in mapped["failures"])
            continue
        primitives.append(mapped["primitive"])
    primitive_plan = {
        "schema": "pptx_primitive_plan.v1",
        "plan_id": f"{data.get('bundle_id', 'bundle')}_primitive_plan",
        "source_bundle_id": data.get("bundle_id"),
        "slides": [{"slide_index": 0, "object_count": len(primitives)}],
        "primitives": primitives,
        "unsupported_items": unsupported_items,
        "blockers": blockers,
        "warnings": warnings,
        "downstream_gates": data.get("downstream_gates", []),
        "expected_outputs": data.get("expected_outputs", []),
        "forbidden_outputs": data.get("forbidden_outputs", []),
        "object_instruction_count": len(spec.get("objects", [])),
    }
    blocker_report = detect_compile_blockers({"objects": spec.get("objects", []), "expected_outputs": data.get("expected_outputs", []), "downstream_gates": data.get("downstream_gates", [])})
    primitive_plan["blockers"].extend(blocker_report["blockers"])
    primitive_plan.update({key: blocker_report[key] for key in ("semantic_raster_blocker_count", "full_slide_raster_blocker_count", "unknown_content_bearing_blocker_count", "protected_output_blocker_count")})
    plan_validation = validate_primitive_plan(primitive_plan)
    if not plan_validation["pass"]:
        primitive_plan["blockers"].extend({"blocker_type": "primitive_plan_validation", "message": failure} for failure in plan_validation["failures"])
    decision = "DRY_RUN_READY"
    if primitive_plan["blockers"]:
        decision = "DRY_RUN_BLOCKED_COMPILE_POLICY"
    elif warnings:
        decision = "DRY_RUN_READY_WITH_WARNINGS"
    return build_dry_run_report(report_id=f"{data.get('bundle_id', 'bundle')}_dry_run", input_bundle_path=input_bundle_path, backend_capability=capability, primitive_plan=primitive_plan, decision=decision, limitations=data.get("limitations", []))


def dry_run_compile_spec(editable_spec: dict[str, Any], backend_name: str = "dry_run_only") -> dict[str, Any]:
    bundle = {
        "schema": "compiler_input_bundle.v1",
        "bundle_id": f"{editable_spec.get('spec_id', 'spec')}_dry_run_bundle",
        "editable_candidate_spec": editable_spec,
        "asset_manifest": [],
        "expected_outputs": ["editable_candidate.pptx", "pptx_ooxml_ledger.json", "B03 validation report"],
        "downstream_gates": ["B03_native_validation_gate", "B01_render_review_optional"],
        "forbidden_outputs": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback", "source_bound_deck", "canonical_artifact_overwrite"],
        "created_pptx": False,
    }
    return dry_run_compile_bundle(bundle, backend_name)


def _map_instruction(instruction: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    instruction_type = str(instruction.get("pptx_object_type", ""))
    if instruction_type in {"text_box", "shape", "group", "freeform_shape", "svg_icon", "editable_timeline", "editable_matrix", "editable_roadmap"}:
        if instruction_type in {"editable_timeline", "editable_matrix", "editable_roadmap"}:
            primitive = map_instruction_to_primitive(instruction, capability.get("backend_name", "dry_run_only"))
            return {"pass": True, "primitive": primitive, "failures": []}
        return map_shape_or_text(instruction)
    if instruction_type in {"native_chart", "native_table", "editable_shape_chart", "editable_shape_grid_table"}:
        return map_chart_or_table(instruction, capability)
    if instruction_type == "replaceable_image_frame":
        return map_image_frame(instruction)
    if instruction_type == "suppression_shape":
        return map_suppression_shape(instruction)
    primitive = map_instruction_to_primitive(instruction, capability.get("backend_name", "dry_run_only"))
    return {"pass": primitive["primitive_type"] != "unsupported", "primitive": primitive, "failures": primitive.get("limitations", [])}


def _empty_plan(bundle: dict[str, Any], blocker_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "pptx_primitive_plan.v1",
        "plan_id": f"{bundle.get('bundle_id', 'bundle')}_primitive_plan",
        "source_bundle_id": bundle.get("bundle_id"),
        "slides": [],
        "primitives": [],
        "unsupported_items": [],
        "blockers": blocker_report.get("blockers", []),
        "warnings": [],
        "downstream_gates": bundle.get("downstream_gates", []),
        "expected_outputs": bundle.get("expected_outputs", []),
        "forbidden_outputs": bundle.get("forbidden_outputs", []),
        "object_instruction_count": len(bundle.get("editable_candidate_spec", {}).get("objects", [])),
        "semantic_raster_blocker_count": blocker_report.get("semantic_raster_blocker_count", 0),
        "full_slide_raster_blocker_count": blocker_report.get("full_slide_raster_blocker_count", 0),
        "unknown_content_bearing_blocker_count": blocker_report.get("unknown_content_bearing_blocker_count", 0),
        "protected_output_blocker_count": blocker_report.get("protected_output_blocker_count", 0),
    }


def _decision_from_failures(failures: list[str]) -> str:
    if any("semantic raster" in failure.lower() or "semantic_raster" in failure.lower() for failure in failures):
        return "DRY_RUN_BLOCKED_COMPILE_POLICY"
    if any("required slot without editable instruction" in failure or "editable candidate spec is invalid" in failure for failure in failures):
        return "DRY_RUN_BLOCKED_INVALID_INPUT"
    if any("protected" in failure or "canonical" in failure for failure in failures):
        return "DRY_RUN_BLOCKED_PROTECTED_ARTIFACT_POLICY"
    return "DRY_RUN_BLOCKED_COMPILE_POLICY"
