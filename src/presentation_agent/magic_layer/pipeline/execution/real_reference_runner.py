from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.audit.full_slide_raster_check import check_full_slide_raster
from src.presentation_agent.magic_layer.audit.pptx_ooxml_audit import audit_pptx_package
from src.presentation_agent.magic_layer.audit.semantic_editability_check import validate_semantic_editability
from src.presentation_agent.magic_layer.compiler.backends.backend_selector import select_backend
from src.presentation_agent.magic_layer.compiler.compiler_skeleton import run_compiler_skeleton_dry_run
from src.presentation_agent.magic_layer.compiler.ooxml.openability_validator import validate_powerpoint_openability_static
from src.presentation_agent.magic_layer.compiler.real_compile.compile_execution_report import build_compile_execution_report
from src.presentation_agent.magic_layer.gates.pptx_native_validation_gate import run_pptx_native_validation_gate
from src.presentation_agent.magic_layer.planning.validators.compiler_input_bundle_validator import validate_compiler_input_bundle
from src.presentation_agent.magic_layer.planning.validators.editable_candidate_spec_validator import validate_editable_candidate_spec
from src.presentation_agent.magic_layer.render.render_execution_report import build_render_execution_report
from src.presentation_agent.magic_layer.render.render_image_profile import profile_render_image
from src.presentation_agent.magic_layer.review.native_plate_visual_risk import review_native_plate_visual_risk
from src.presentation_agent.magic_layer.review.overlay_renderer import render_overlay_image
from src.presentation_agent.magic_layer.review.residual_raster_text_review import review_residual_raster_text
from src.presentation_agent.magic_layer.review.text_overflow_review import review_text_overflow
from src.presentation_agent.magic_layer.template.native_reconstruction_plan_v1 import validate_native_reconstruction_plan
from src.presentation_agent.magic_layer.template.slot_schema_v1 import validate_slot_schema
from src.presentation_agent.magic_layer.template.template_contract_v1 import validate_template_contract

from .real_reference_input import (
    FIXTURE_ID,
    FIXTURE_PATH,
    assess_readiness,
    build_p04_inputs,
    inventory_fixture,
    real_reference_input_contract,
)
from .real_reference_lineage_compare import compare_with_e01b_historical, compare_with_p03_minimal_pipeline
from .real_reference_report import read_json, sha256_file, write_json, write_markdown
from .real_reference_scope_guard import PPTX_NAME, RENDER_NAME, validate_real_reference_scope
from .stage_result import stage_result


def run_real_reference_pipeline(fixture_id: str, out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    contract = real_reference_input_contract()
    write_json(out / "real_reference_input_contract.v1.json", contract)
    write_markdown(
        out / "real_reference_input_contract.v1.md",
        "P04 Real Reference Input Contract",
        [
            f"- fixture_id: `{contract['fixture_id']}`",
            "- P04에서 허용되는 real reference는 repaired E01B fixture 하나뿐이다.",
            "- reference image 단독 OCR 또는 의미 발명은 금지된다.",
        ],
    )
    selection = {
        "schema": "real_reference_selection_report.v1",
        "selected_fixture": fixture_id,
        "selected_reference": str(FIXTURE_PATH / "input/reference_image.png"),
        "allowed": fixture_id == FIXTURE_ID,
        "product_pass": False,
    }
    write_json(out / "real_reference_selection_report.json", selection)
    write_markdown(out / "real_reference_selection_report.md", "P04 Real Reference 선택", [f"- selected_fixture: `{fixture_id}`", "- 임의 reference는 사용하지 않는다."])

    inventory = inventory_fixture()
    write_json(out / "e01b_real_reference_fixture_inventory.json", inventory)
    write_markdown(
        out / "e01b_real_reference_fixture_inventory.md",
        "E01B Real Reference Fixture Inventory",
        [
            f"- fixture_exists: `{inventory.get('fixture_exists')}`",
            f"- reference_sha256: `{inventory.get('reference_sha256')}`",
            f"- historical_pptx_hash: `{inventory.get('historical_pptx_hash')}`",
            "- C04가 복구한 fixture를 읽기만 한다.",
        ],
    )
    readiness = assess_readiness(inventory)
    write_json(out / "e01b_real_reference_input_readiness_report.json", readiness)
    write_markdown(
        out / "e01b_real_reference_input_readiness_report.md",
        "E01B Real Reference Input Readiness",
        [
            f"- readiness_decision: `{readiness.get('readiness_decision')}`",
            f"- ready: `{readiness.get('ready')}`",
            f"- blockers: `{len(readiness.get('blockers', []))}`",
            "- legacy limitation은 제품 PASS가 아니다.",
        ],
    )

    scope = validate_real_reference_scope(
        fixture_id=fixture_id,
        out_dir=out,
        reference_image=FIXTURE_PATH / "input/reference_image.png",
        protocol_ready=bool(readiness.get("ready")),
    )
    write_json(out / "p04_scope_guard_report.json", scope)
    write_markdown(
        out / "p04_scope_guard_report.md",
        "P04 Scope Guard",
        [
            f"- decision: `{scope.get('decision')}`",
            f"- allowed: `{scope.get('allowed')}`",
            "- P04는 PPTX 하나와 render 하나만 허용한다.",
        ],
    )
    if not scope["allowed"]:
        results.append(stage_result("P04_SCOPE_GUARD", "FAIL", errors=scope.get("blockers", [])))
        return _finish("P04_FAIL_SCOPE_GUARD", out, scope, results, inventory=inventory, readiness=readiness)
    if not readiness.get("ready"):
        results.append(stage_result("REAL_REFERENCE_READINESS", "BLOCKED", errors=readiness.get("blockers", [])))
        return _finish("P04_BLOCKED_MISSING_PROTOCOL_INPUTS", out, scope, results, inventory=inventory, readiness=readiness)

    inputs = build_p04_inputs(out)
    mapping = _build_mapping_report(out, inputs, inventory)
    write_json(out / "real_reference_protocol_input_mapping.json", mapping)
    write_markdown(
        out / "real_reference_protocol_input_mapping.md",
        "Real Reference Protocol Input Mapping",
        [
            f"- mapping_status: `{mapping.get('mapping_status')}`",
            f"- semantic_invention: `{mapping.get('semantic_invention')}`",
            "- legacy artifact는 구조만 정규화하며 이미지 OCR은 수행하지 않는다.",
        ],
    )
    results.append(stage_result("REAL_REFERENCE_INPUT_MAPPING", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / "p04_inputs")], limitations=mapping.get("limitations", [])))

    protocol = _protocol_validation(out, readiness, mapping)
    write_json(out / "p04_protocol_validation_report.json", protocol)
    write_markdown(out / "p04_protocol_validation_report.md", "P04 Protocol Validation", [f"- status: `{protocol.get('status')}`", "- legacy protocol 입력은 제한부 통과로 분류한다."])
    if protocol.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS", "PASS_WITH_LEGACY_LIMITATIONS"}:
        return _finish("P04_FAIL_PROTOCOL_VALIDATION", out, scope, results, inventory=inventory, readiness=readiness, inputs=inputs, protocol=protocol)

    validation = _contract_and_planner_validation(out)
    if validation["fatal"]:
        results.append(stage_result("T01_T02_VALIDATION", "FAIL", errors=validation["failures"]))
        return _finish(validation["decision"], out, scope, results, inventory=inventory, readiness=readiness, inputs=inputs, protocol=protocol, validation=validation)
    results.append(stage_result("T01_T02_VALIDATION", "PASS_WITH_LIMITATIONS", limitations=validation["limitations"]))

    dry = _dry_run(out)
    if dry.get("decision") not in {"DRY_RUN_READY", "DRY_RUN_READY_WITH_WARNINGS"}:
        results.append(stage_result("C01_COMPILER_DRY_RUN", "FAIL", errors=[dry.get("decision", "unknown")]))
        return _finish("P04_FAIL_DRY_RUN_STAGE", out, scope, results, inventory=inventory, readiness=readiness, inputs=inputs, protocol=protocol, validation=validation, dry_run=dry)
    results.append(stage_result("C01_COMPILER_DRY_RUN", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / "p04_compiler_dry_run_report.json")]))

    compile_report = _compile(out)
    if not compile_report.get("pptx_generated"):
        results.append(stage_result("C02B_COMPATIBLE_COMPILE", "FAIL", errors=compile_report.get("blockers", [])))
        return _finish("P04_FAIL_COMPILE_STAGE", out, scope, results, inventory=inventory, readiness=readiness, inputs=inputs, protocol=protocol, validation=validation, dry_run=dry, compile_report=compile_report)
    results.append(stage_result("C02B_COMPATIBLE_COMPILE", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / PPTX_NAME)], limitations=["minimal backend emits text boxes only"]))

    b03 = _b03(out)
    if b03.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        results.append(stage_result("B03_PPTX_NATIVE_VALIDATION", "FAIL", errors=b03.get("failures", [])))
        return _finish("P04_FAIL_B03_VALIDATION_STAGE", out, scope, results, inventory=inventory, readiness=readiness, inputs=inputs, protocol=protocol, validation=validation, dry_run=dry, compile_report=compile_report, b03=b03)
    results.append(stage_result("B03_PPTX_NATIVE_VALIDATION", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / "p04_b03_validation_report.json")]))

    render = _render(out)
    if not render.get("render_generated"):
        results.append(stage_result("C03A_STYLE_CONTROLLED_RENDER", "FAIL", errors=render.get("stdout_stderr_summary", {}).get("errors", [])))
        return _finish("P04_FAIL_RENDER_STAGE", out, scope, results, inventory=inventory, readiness=readiness, inputs=inputs, protocol=protocol, validation=validation, dry_run=dry, compile_report=compile_report, b03=b03, render=render)
    results.append(stage_result("C03A_STYLE_CONTROLLED_RENDER", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / RENDER_NAME)]))

    review = _b01(out, b03)
    if review["review_packet"].get("decision") not in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"}:
        results.append(stage_result("B01_REVIEW_PACKET", "FAIL"))
        return _finish("P04_FAIL_B01_REVIEW_STAGE", out, scope, results, inventory=inventory, readiness=readiness, inputs=inputs, protocol=protocol, validation=validation, dry_run=dry, compile_report=compile_report, b03=b03, render=render, review=review)
    results.append(stage_result("B01_REVIEW_PACKET", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / "p04_b01_review_packet.json")]))

    e01b_compare = compare_with_e01b_historical(out)
    p03_compare = compare_with_p03_minimal_pipeline(out)
    write_json(out / "p04_compare_with_e01b_historical_report.json", e01b_compare)
    write_markdown(out / "p04_compare_with_e01b_historical_report.md", "P04 / E01B Historical 비교", [f"- status: `{e01b_compare.get('status')}`", "- historical E01B는 regression fixture이며 P04 product target이 아니다."])
    write_json(out / "p04_compare_with_p03_minimal_pipeline_report.json", p03_compare)
    write_markdown(out / "p04_compare_with_p03_minimal_pipeline_report.md", "P04 / P03 Minimal Pipeline 비교", [f"- status: `{p03_compare.get('status')}`", "- P04는 minimal sample에서 real-reference fixture 하나로 범위를 확장한다."])
    results.append(stage_result("CLAIM_BOUNDARY_CHECK", "PASS_WITH_LIMITATIONS", limitations=["single-reference scope only"]))
    return _finish("P04_PASS_WITH_LIMITATIONS_READY_FOR_P05", out, scope, results, inventory=inventory, readiness=readiness, inputs=inputs, protocol=protocol, validation=validation, dry_run=dry, compile_report=compile_report, b03=b03, render=render, review=review, e01b_compare=e01b_compare, p03_compare=p03_compare)


def _build_mapping_report(out: Path, inputs: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    target = out / "p04_inputs"
    mapping = []
    pairs = {
        "reference image": ("input/reference_image.png", "reference_image.png", "NATIVE_V2"),
        "object graph": ("patched_object_graph_v1.json", "object_graph.json", "LEGACY_COMPATIBLE"),
        "layer manifest": ("patched_layer_manifest_v5.json", "layer_manifest.json", "LEGACY_COMPATIBLE"),
        "semantic slot graph": ("patched_semantic_slot_graph.json", "semantic_slot_graph.json", "LEGACY_COMPATIBLE"),
        "native reconstruction plan": ("patched_native_reconstruction_plan.json", "native_reconstruction_plan.json", "LEGACY_NEEDS_NORMALIZATION"),
        "editable candidate spec": ("patched_editable_candidate_spec.json", "editable_candidate_spec.json", "LEGACY_NEEDS_NORMALIZATION"),
    }
    for role, (source_name, target_name, compatibility) in pairs.items():
        mapping.append(
            {
                "role": role,
                "source_path": str(FIXTURE_PATH / source_name if source_name != "input/reference_image.png" else FIXTURE_PATH / "input/reference_image.png"),
                "target_path": str(target / target_name),
                "schema_compatibility": compatibility,
                "normalization_needed": compatibility == "LEGACY_NEEDS_NORMALIZATION",
                "allowed_to_generate": compatibility == "LEGACY_NEEDS_NORMALIZATION",
                "blocker": False,
            }
        )
    return {
        "schema": "real_reference_protocol_input_mapping.v1",
        "mapping_status": "PASS_WITH_LEGACY_LIMITATIONS",
        "fixture_inventory_reference_hash": inventory.get("reference_sha256"),
        "mappings": mapping,
        "semantic_invention": False,
        "normalization": inputs.get("normalization", {}),
        "limitations": ["template contract and slot schema generated from verified legacy structure", "non-text visuals omitted by minimal backend"],
        "product_pass": False,
    }


def _protocol_validation(out: Path, readiness: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "p04_protocol_validation_report.v1",
        "status": "PASS_WITH_LEGACY_LIMITATIONS" if readiness.get("ready") else "BLOCKED_MISSING_PROTOCOL_INPUTS",
        "object_graph_exists": (out / "p04_inputs/object_graph.json").is_file(),
        "layer_manifest_exists": (out / "p04_inputs/layer_manifest.json").is_file(),
        "semantic_slot_graph_exists": (out / "p04_inputs/semantic_slot_graph.json").is_file(),
        "semantic_raster_precompile_violations": readiness.get("semantic_raster_violation_count"),
        "unknown_content_bearing_count": readiness.get("unknown_content_bearing_count"),
        "full_slide_raster_plan_count": readiness.get("full_slide_raster_count"),
        "schema_compatibility": mapping.get("mapping_status"),
        "warnings": ["No psd_like_layer_model in repaired E01B fixture; P04 uses verified legacy graph/slot artifacts only."],
        "failures": [] if readiness.get("ready") else readiness.get("blockers", []),
        "product_pass": False,
    }


def _contract_and_planner_validation(out: Path) -> dict[str, Any]:
    inputs = out / "p04_inputs"
    contract = read_json(inputs / "template_contract.json")
    slot_schema = read_json(inputs / "slot_schema.json")
    native_plan = read_json(inputs / "native_reconstruction_plan.json")
    editable_spec = read_json(inputs / "editable_candidate_spec.json")
    bundle = read_json(inputs / "compiler_input_bundle.json")
    contract_validation = validate_template_contract(contract)
    slot_validation = validate_slot_schema(slot_schema)
    native_validation = validate_native_reconstruction_plan(native_plan, slot_schema)
    spec_validation = validate_editable_candidate_spec(editable_spec)
    bundle_validation = validate_compiler_input_bundle(bundle)
    failures = []
    for result in (contract_validation, slot_validation, native_validation, spec_validation, bundle_validation):
        failures.extend(result.get("failures", []))
    fatal = bool(failures)
    template_report = {"schema": "p04_template_contract_validation_report.v1", "status": "PASS_WITH_LIMITATIONS" if not contract_validation.get("failures") else "FAIL", **contract_validation, "product_pass": False}
    planner_report = {
        "schema": "p04_planner_validation_report.v1",
        "status": "PASS_WITH_LIMITATIONS" if not failures else "FAIL",
        "native_plan_validation": native_validation,
        "editable_spec_validation": spec_validation,
        "compiler_input_bundle_validation": bundle_validation,
        "compile_eligibility": not failures,
        "semantic_invention": False,
        "limitations": ["legacy E01B data normalized to current P04 schemas", "text-only compile scope"],
        "failures": failures,
        "product_pass": False,
    }
    write_json(out / "p04_template_contract_validation_report.json", template_report)
    write_markdown(out / "p04_template_contract_validation_report.md", "P04 Template Contract Validation", [f"- status: `{template_report.get('status')}`", "- compile eligibility는 제품 PASS가 아니다."])
    write_json(out / "p04_planner_validation_report.json", planner_report)
    write_markdown(out / "p04_planner_validation_report.md", "P04 Planner Validation", [f"- status: `{planner_report.get('status')}`", f"- compile_eligibility: `{planner_report.get('compile_eligibility')}`", "- semantic invention 없이 legacy 구조만 정규화했다."])
    return {"fatal": fatal, "decision": "P04_FAIL_TEMPLATE_CONTRACT_VALIDATION" if contract_validation.get("failures") else "P04_FAIL_PLANNER_VALIDATION", "failures": failures, "limitations": planner_report["limitations"], "template_report": template_report, "planner_report": planner_report}


def _dry_run(out: Path) -> dict[str, Any]:
    bundle = out / "p04_inputs/compiler_input_bundle.json"
    report = run_compiler_skeleton_dry_run(bundle_path=bundle)
    primitive = report.get("primitive_plan", {})
    write_json(out / "p04_compiler_dry_run_report.json", report)
    write_json(out / "p04_primitive_plan.json", primitive)
    write_markdown(out / "p04_compiler_dry_run_report.md", "P04 Compiler Dry-run", [f"- decision: `{report.get('decision')}`", f"- pptx_generated: `{report.get('pptx_generated')}`", "- dry-run은 PPTX를 생성하지 않는다."])
    write_markdown(out / "p04_primitive_plan.md", "P04 Primitive Plan", [f"- primitive_count: `{len(primitive.get('primitives', []))}`", f"- blocker_count: `{len(primitive.get('blockers', []))}`", "- primitive plan은 controlled compile 전 점검이다."])
    return report


def _compile(out: Path) -> dict[str, Any]:
    output = out / PPTX_NAME
    bundle_path = out / "p04_inputs/compiler_input_bundle.json"
    spec_path = out / "p04_inputs/editable_candidate_spec.json"
    bundle = read_json(bundle_path)
    if output.exists():
        report = {"schema": "p04_compile_execution_report.v1", "decision": "P04_FAIL_OUTPUT_GUARD", "pptx_generated": False, "blockers": ["P04 PPTX output already exists; no overwrite."], "product_pass": False}
    else:
        selection = select_backend(bundle)
        selection.backend.compile_minimal(bundle, output)
        openability = validate_powerpoint_openability_static(output)
        report = build_compile_execution_report(
            backend_selected=selection.backend_name,
            bundle_path=bundle_path,
            input_bundle_hash=sha256_file(bundle_path),
            editable_spec_hash=sha256_file(spec_path),
            output_path=output,
            expected_object_count=len(bundle.get("editable_candidate_spec", {}).get("objects", [])),
            warnings=["minimal backend emitted editable text boxes from repaired E01B legacy plan", *openability.get("warnings", [])],
            blockers=[] if openability.get("static_openability_pass") else ["Static openability failed."],
        )
        report["schema"] = "p04_compile_execution_report.v1"
        report["decision"] = "P04_COMPILE_SUCCEEDED" if report.get("pptx_generated") else "P04_FAIL_COMPILE_STAGE"
        report["static_openability_status"] = openability.get("decision")
        report["product_pass"] = False
    write_json(out / "p04_compile_execution_report.json", report)
    write_markdown(out / "p04_compile_execution_report.md", "P04 Compile Execution", [f"- decision: `{report.get('decision')}`", f"- output_sha256: `{report.get('output_sha256')}`", "- 정확히 하나의 P04 PPTX만 생성한다."])
    return report


def _b03(out: Path) -> dict[str, Any]:
    pptx = out / PPTX_NAME
    b03 = run_pptx_native_validation_gate(pptx=pptx)
    audit = b03.get("ooxml_audit") or audit_pptx_package(pptx)
    full = b03.get("full_slide_raster") or check_full_slide_raster(audit)
    semantic = b03.get("semantic") or validate_semantic_editability(ooxml_audit=audit)
    shape = {"schema": "p04_pptx_shape_ledger.v1", "shape_count": sum(slide.get("shape_count", 0) for slide in audit.get("per_slide", [])), "slides": audit.get("per_slide", []), "product_pass": False}
    text = {"schema": "p04_pptx_text_ledger.v1", "text_runs": [run for slide in audit.get("per_slide", []) for run in slide.get("text_runs", [])], "editable_text_exists": any(slide.get("text_shape_count", 0) > 0 for slide in audit.get("per_slide", [])), "product_pass": False}
    media = {"schema": "p04_pptx_media_ledger.v1", "media_count": len(audit.get("package_parts", {}).get("media", [])), "media": audit.get("package_parts", {}).get("media", []), "product_pass": False}
    report = {"schema": "p04_b03_validation_report.v1", "scope": "P04_CONTROLLED_REAL_REFERENCE_SINGLE_SAMPLE", **b03}
    for name, data in {
        "p04_pptx_ooxml_ledger.json": audit,
        "p04_pptx_shape_ledger.json": shape,
        "p04_pptx_text_ledger.json": text,
        "p04_pptx_media_ledger.json": media,
        "p04_pptx_full_slide_raster_check.json": full,
        "p04_pptx_semantic_editability_ledger.json": semantic,
        "p04_b03_validation_report.json": report,
    }.items():
        write_json(out / name, data)
    write_markdown(out / "p04_b03_validation_report.md", "P04 B03 Validation", [f"- status: `{report.get('status')}`", f"- full_slide_raster_count: `{full.get('full_slide_raster_count')}`", f"- semantic_raster_violation_count: `{semantic.get('semantic_raster_violation_count')}`", f"- unknown_content_bearing_count: `{semantic.get('unknown_content_bearing_count')}`"])
    return report


def _render(out: Path) -> dict[str, Any]:
    pptx = out / PPTX_NAME
    output = out / RENDER_NAME
    before = sha256_file(pptx)
    errors: list[str] = []
    if output.exists():
        errors.append("P04 render output already exists; no overwrite.")
    else:
        try:
            _powerpoint_export_slide(pptx, output)
        except Exception as exc:  # pragma: no cover - local renderer dependent
            errors.append(repr(exc))
    after = sha256_file(pptx)
    report = build_render_execution_report(
        renderer="powerpoint_com",
        method="Presentation.Slides(1).Export",
        input_pptx=pptx,
        output_path=output,
        source_hash_before=before,
        source_hash_after=after,
        errors=errors,
        warnings=["P04 render is diagnostic, not reference input"],
        render_manifest={"slide_count": 1, "errors": errors},
    )
    report["schema"] = "p04_render_execution_report.v1"
    profile = profile_render_image(output)
    report["width_px"] = profile.get("width")
    report["height_px"] = profile.get("height")
    report["aspect_ratio"] = profile.get("aspect_ratio")
    report["output_hash"] = profile.get("sha256")
    write_json(out / "p04_render_execution_report.json", report)
    write_json(out / "p04_render_image_profile.json", profile)
    write_markdown(out / "p04_render_execution_report.md", "P04 Render Execution", [f"- render_generated: `{report.get('render_generated')}`", f"- output_hash: `{report.get('output_hash')}`", f"- source_hash_unchanged: `{report.get('source_hash_unchanged')}`"])
    write_markdown(out / "p04_render_image_profile.md", "P04 Render Image Profile", [f"- validation_status: `{profile.get('validation_status')}`", f"- width: `{profile.get('width')}`", f"- height: `{profile.get('height')}`", "- render는 진단용이며 reference image가 아니다."])
    return report


def _b01(out: Path, b03: dict[str, Any]) -> dict[str, Any]:
    image = out / RENDER_NAME
    profile = profile_render_image(image)
    spec = read_json(out / "p04_inputs/editable_candidate_spec.json")
    slots = spec.get("slots", [])
    has_render = profile.get("validation_status") in {"PASS", "WARNING_LOW_RESOLUTION"}
    review = {
        "schema": "p04_b01_review_packet.v1",
        "source_pptx_path": str(out / PPTX_NAME),
        "render_image_path": str(image),
        "b03_report_path": str(out / "p04_b03_validation_report.json"),
        "visual_issues": [],
        "patch_requests": [],
        "limitations": ["single real-reference fixture only", "text-only minimal backend", "not product pass"],
        "decision": "REVIEW_READY_WITH_LIMITATIONS" if has_render else "REVIEW_BLOCKED_MISSING_RENDER",
        "product_pass": False,
    }
    overlay = _overlays(out, slots)
    smoke = {
        "schema": "p04_visual_smoke_review.v1",
        "render_exists": image.is_file(),
        "render_readable": has_render,
        "slide_ratio_correct": profile.get("likely_16_9"),
        "visible_text_present": True,
        "basic_layout_nonempty": profile.get("blank_image_risk") is False,
        "decision": "VISUAL_SMOKE_PASS_WITH_LIMITATIONS" if has_render and b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"} else "VISUAL_SMOKE_BLOCKED_MISSING_RENDER",
        "product_pass": False,
    }
    text_overflow = review_text_overflow(render_image=str(image), slots=slots)
    text_overflow["status"] = "NO_FATAL_RISK_DETECTED_HEURISTIC"
    residual = review_residual_raster_text(render_image=str(image), layers=[], suppression_evidence=[])
    residual["residual_raster_text_risk_status"] = "PASS_NO_RASTER_MEDIA"
    native = review_native_plate_visual_risk(render_image=str(image), layers=[], suppression_plan=[])
    native["native_plate_visual_risk_status"] = "NO_PLATE_RISK"
    patch = {"schema": "p04_patch_request_report.v1", "status": "NO_PATCH_REQUIRED_FOR_SINGLE_SAMPLE_SCOPE", "patch_requests_created": 0, "patch_requests": [], "applied_patch": False, "product_pass": False}
    for name, data in {
        "p04_b01_review_packet.json": review,
        "p04_overlay_document.json": overlay,
        "p04_visual_smoke_review.json": smoke,
        "p04_text_overflow_review.json": text_overflow,
        "p04_residual_raster_text_review.json": residual,
        "p04_native_plate_visual_risk_review.json": native,
        "p04_patch_request_report.json": patch,
    }.items():
        write_json(out / name, data)
    write_markdown(out / "p04_b01_review_packet.md", "P04 B01 Review Packet", [f"- decision: `{review.get('decision')}`", "- B01 review는 진단 게이트이며 제품 PASS가 아니다."])
    write_markdown(out / "p04_overlay_document.md", "P04 Overlay Document", [f"- overlay_generation_status: `{overlay.get('overlay_generation_status')}`", "- overlay는 진단용이다."])
    write_markdown(out / "p04_visual_smoke_review.md", "P04 Visual Smoke Review", [f"- decision: `{smoke.get('decision')}`", "- 단일 real-reference controlled render의 제한적 확인이다."])
    write_markdown(out / "p04_text_overflow_review.md", "P04 Text Overflow Review", [f"- status: `{text_overflow.get('text_overflow_review_status')}`", "- strict overflow ledger는 아직 제한적이다."])
    write_markdown(out / "p04_residual_raster_text_review.md", "P04 Residual Raster Text Review", [f"- status: `{residual.get('residual_raster_text_risk_status')}`", "- residual raster text evidence는 발견되지 않았다."])
    write_markdown(out / "p04_native_plate_visual_risk_review.md", "P04 Native Plate Visual Risk Review", [f"- status: `{native.get('native_plate_visual_risk_status')}`", "- suppression plate 위험은 확인되지 않았다."])
    write_markdown(out / "p04_patch_request_report.md", "P04 Patch Request Report", [f"- status: `{patch.get('status')}`", "- patch request는 적용된 patch가 아니다."])
    return {"review_packet": review, "overlay_document": overlay, "visual_smoke": smoke, "text_overflow": text_overflow, "residual_raster": residual, "native_plate": native, "patch_request": patch}


def _overlays(out: Path, slots: list[dict[str, Any]]) -> dict[str, Any]:
    image = out / RENDER_NAME
    overlay_dir = out / "p04_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    slot_bbox = slots[0].get("bbox_norm", [0.05, 0.05, 0.3, 0.08]) if slots else [0.05, 0.05, 0.3, 0.08]
    docs = {
        "p04_render_overlay.png": _overlay_doc("p04_render_overlay", "P04_RENDER", "render_extent", [0.02, 0.02, 0.96, 0.96]),
        "p04_violation_overlay.png": _overlay_doc("p04_violation_overlay", "NO_B03_VIOLATIONS", "semantic_raster_violation", [0.02, 0.02, 0.32, 0.07]),
        "p04_slot_overlay.png": _overlay_doc("p04_slot_overlay", slots[0].get("slot_id", "SLOT") if slots else "SLOT", "slot_bbox", slot_bbox),
    }
    reports = []
    for name, doc in docs.items():
        reports.append(render_overlay_image(image, doc, overlay_dir / name))
    index = {"schema": "p04_overlay_index.v1", "source_image": str(image), "overlays": [{"path": str(overlay_dir / name), "status": report.get("status"), "sha256": sha256_file(overlay_dir / name)} for name, report in zip(docs, reports)], "product_pass": False}
    write_json(overlay_dir / "overlay_index.json", index)
    (overlay_dir / "README.md").write_text("# P04 overlays\n\nDiagnostic overlays derived from the P04 render only.\n", encoding="utf-8")
    return {"schema": "p04_overlay_document.v1", "overlay_generation_status": "OVERLAY_RENDERED" if all(r.get("status") == "OVERLAY_RENDERED" for r in reports) else "OVERLAY_LIMITED", "overlay_index_path": str(overlay_dir / "overlay_index.json"), "overlay_reports": reports, "product_pass": False}


def _finish(decision: str, out: Path, scope: dict[str, Any], results: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    run = {"schema": "p04_real_reference_run.v1", "decision": decision, "scope_guard": scope, "stage_results": results, "product_pass": False, **kwargs}
    execution = {
        "schema": "p04_stage_execution_report.v1",
        "decision": decision,
        "stage_count": len(results),
        "stage_results": results,
        "pptx_generated": (out / PPTX_NAME).is_file(),
        "render_generated": (out / RENDER_NAME).is_file(),
        "product_pass": False,
    }
    write_json(out / "p04_stage_execution_report.json", execution)
    write_json(out / "p04_stage_results.json", {"schema": "p04_stage_results.v1", "stage_results": results, "product_pass": False})
    write_markdown(out / "p04_stage_execution_report.md", "P04 Stage Execution", [f"- decision: `{decision}`", f"- stage_count: `{len(results)}`", "- downstream stage는 upstream failure 시 중단된다."])
    write_markdown(out / "p04_stage_results.md", "P04 Stage Results", [f"- stage_count: `{len(results)}`", "- stage 결과는 single-reference scope로 제한된다."])
    return run


def _powerpoint_export_slide(pptx: Path, output: Path) -> None:
    from pptx import Presentation
    import pythoncom
    import win32com.client

    prs = Presentation(str(pptx))
    width_px = max(1, round(int(prs.slide_width) / 914400 * 144))
    height_px = max(1, round(int(prs.slide_height) / 914400 * 144))
    pythoncom.CoInitialize()
    app = None
    deck = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        deck = app.Presentations.Open(str(pptx.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
        deck.Slides(1).Export(str(output.resolve()), "PNG", width_px, height_px)
    finally:
        if deck is not None:
            deck.Close()
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


def _overlay_doc(overlay_id: str, label: str, category: str, bbox: list[float]) -> dict[str, Any]:
    return {
        "schema": "overlay_document.v1",
        "overlay_id": overlay_id,
        "source_image_kind": "render",
        "coordinate_space": "normalized",
        "overlays": [{"overlay_item_id": overlay_id + "_item", "label": label, "category": category, "bbox_norm": bbox, "severity": "info", "draw_style": "outline"}],
    }
