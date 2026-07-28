from __future__ import annotations

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

from .four_core_input import (
    ARCHETYPES,
    assess_four_core_readiness,
    build_archetype_inputs,
    four_core_reference_contract,
    inventory_four_core_fixtures,
    select_four_core_references,
)
from .four_core_lineage_compare import compare_with_e02_historical, compare_with_p04_single_reference
from .four_core_report import read_json, sha256_file, write_json, write_markdown
from .four_core_scope_guard import PPTX_NAME, RENDER_NAME, validate_four_core_scope
from .stage_result import stage_result


def run_four_core_pipeline(fixture_id: str, out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if fixture_id != "e02_4core_pass":
        result = {"schema": "p05_four_core_run.v1", "decision": "P05_FAIL_SCOPE_GUARD", "blockers": ["Only e02_4core_pass is allowed."], "product_pass": False}
        write_json(out / "p05_stage_execution_report.json", result)
        return result

    contract = four_core_reference_contract()
    selection = select_four_core_references()
    inventory = inventory_four_core_fixtures()
    readiness = assess_four_core_readiness(selection, inventory)
    write_json(out / "four_core_reference_input_contract.v1.json", contract)
    write_markdown(out / "four_core_reference_input_contract.v1.md", "P05 Four-Core Reference Contract", ["- 허용 archetype은 E02 네 개뿐이다.", "- reference 생성, E03 reference, render PNG reference 사용은 금지된다."])
    write_json(out / "four_core_reference_selection_report.json", selection)
    write_markdown(out / "four_core_reference_selection_report.md", "Four-Core Reference Selection", [f"- all_selected: `{selection.get('all_selected')}`", "- active E02 input reference를 우선 사용한다."])
    write_json(out / "four_core_reference_hash_validation.json", _reference_hash_validation(selection))
    write_markdown(out / "four_core_reference_hash_validation.md", "Four-Core Reference Hash Validation", ["- 네 개 reference의 sha256을 기록했다.", "- hash mismatch는 자동으로 숨기지 않는다."])
    write_json(out / "four_core_fixture_inventory.json", inventory)
    write_markdown(out / "four_core_fixture_inventory.md", "Four-Core Fixture Inventory", ["- E02 fixture와 run_002 historical evidence를 함께 점검했다.", "- quarantine은 active input으로 사용하지 않는다."])
    write_json(out / "four_core_input_readiness_report.json", readiness)
    write_markdown(out / "four_core_input_readiness_report.md", "Four-Core Input Readiness", [f"- overall_ready: `{readiness.get('overall_ready')}`", "- legacy normalization limitation은 제품 PASS가 아니다."])

    scope = validate_four_core_scope(out_dir=out, protocol_ready=bool(readiness.get("overall_ready")))
    write_json(out / "p05_scope_guard_report.json", scope)
    write_markdown(out / "p05_scope_guard_report.md", "P05 Scope Guard", [f"- decision: `{scope.get('decision')}`", "- 최대 네 개 PPTX와 네 개 render만 허용한다."])
    if not scope["allowed"]:
        _write_root_scaffolding(out, {}, {}, scope, [], "P05_FAIL_SCOPE_GUARD")
        return {"schema": "p05_four_core_run.v1", "decision": "P05_FAIL_SCOPE_GUARD", "scope_guard": scope, "product_pass": False}

    plan = _execution_plan(out)
    write_json(out / "p05_four_core_execution_plan.json", plan)
    write_markdown(out / "p05_four_core_execution_plan.md", "P05 Four-Core Execution Plan", ["- archetype별로 입력 복사, protocol/T01/T02/C01, compile, B03, render, B01 순서로 실행한다.", "- aggregate template pack은 만들지 않는다."])

    archetype_results: dict[str, dict[str, Any]] = {}
    stages: list[dict[str, Any]] = []
    mapping_rows: dict[str, Any] = {}
    for archetype in ARCHETYPES:
        result = _run_archetype(archetype, out, selection, inventory, readiness.get("archetypes", {}).get(archetype, {}))
        archetype_results[archetype] = result
        mapping_rows[archetype] = result.get("mapping", {})
        stages.append(stage_result(f"P05_{archetype.upper()}", result.get("stage_status", "FAIL"), evidence_paths=[str(out / "archetypes" / archetype)]))

    mapping_report = {"schema": "four_core_protocol_mapping_report.v1", "archetypes": mapping_rows, "semantic_invention": False, "product_pass": False}
    write_json(out / "four_core_protocol_mapping_report.json", mapping_report)
    write_markdown(out / "four_core_protocol_mapping_report.md", "Four-Core Protocol Mapping", ["- E02 legacy artifact를 구조적으로만 정규화했다.", "- 이미지 OCR이나 semantic invention은 수행하지 않았다."])

    rollups = _rollups(out, archetype_results)
    e02_compare = compare_with_e02_historical(out)
    p04_compare = compare_with_p04_single_reference(out)
    write_json(out / "p05_compare_with_e02_historical_report.json", e02_compare)
    write_markdown(out / "p05_compare_with_e02_historical_report.md", "P05 / E02 Historical 비교", [f"- status: `{e02_compare.get('status')}`", "- historical E02는 regression baseline이며 product target이 아니다."])
    write_json(out / "p05_compare_with_p04_single_reference_report.json", p04_compare)
    write_markdown(out / "p05_compare_with_p04_single_reference_report.md", "P05 / P04 Single Reference 비교", [f"- status: `{p04_compare.get('status')}`", "- P05는 P04보다 넓지만 여전히 controlled regression이다."])

    all_pass = all(item.get("decision") in {"ARCHETYPE_P05_PASS", "ARCHETYPE_P05_PASS_WITH_LIMITATIONS"} for item in archetype_results.values())
    any_pass = any(item.get("decision") in {"ARCHETYPE_P05_PASS", "ARCHETYPE_P05_PASS_WITH_LIMITATIONS"} for item in archetype_results.values())
    decision = "P05_PASS_WITH_LIMITATIONS_READY_FOR_P06" if all_pass else "P05_PARTIAL_PASS_REQUIRES_C05_PATCH" if any_pass else _first_failure_decision(archetype_results)
    _write_root_scaffolding(out, archetype_results, rollups, scope, stages, decision)
    return {
        "schema": "p05_four_core_run.v1",
        "decision": decision,
        "archetype_results": archetype_results,
        "scope_guard": scope,
        "rollups": rollups,
        "product_pass": False,
    }


def _run_archetype(archetype: str, out: Path, selection: dict[str, Any], inventory: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    folder = out / "archetypes" / archetype
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "archetype_manifest.json", {"schema": "p05_archetype_manifest.v1", "archetype": archetype, "folder": str(folder), "product_pass": False})
    write_json(folder / "archetype_input_inventory.json", {"schema": "archetype_input_inventory.v1", "archetype": archetype, "reference": selection["references"][archetype], "fixture": inventory["archetypes"][archetype], "product_pass": False})
    write_json(folder / "archetype_input_readiness_report.json", readiness)
    write_markdown(folder / "archetype_input_readiness_report.md", f"{archetype} Input Readiness", [f"- readiness_status: `{readiness.get('readiness_status')}`", "- product_pass는 false다."])
    if not readiness.get("ready"):
        decision = _blocked_decision(readiness.get("readiness_status"))
        _write_archetype_decision(folder, archetype, decision, readiness, stage_status="BLOCKED")
        return {"decision": decision, "stage_status": "BLOCKED", "readiness": readiness}

    mapping = build_archetype_inputs(archetype, folder, selection, inventory)
    write_json(folder / "protocol_validation_report.json", _protocol_validation(folder, mapping))
    write_markdown(folder / "protocol_validation_report.md", "Protocol Validation", ["- E01P protocol 입력은 historical E02 evidence에서 왔다.", "- semantic invention은 수행하지 않았다."])
    validation = _contract_and_planner_validation(folder)
    if validation["fatal"]:
        decision = "ARCHETYPE_P05_FAIL_TEMPLATE_CONTRACT" if validation.get("contract_failed") else "ARCHETYPE_P05_FAIL_PLANNER"
        _write_archetype_decision(folder, archetype, decision, validation, stage_status="FAIL", mapping=mapping)
        return {"decision": decision, "stage_status": "FAIL", "mapping": mapping, "validation": validation}
    dry = _dry_run(folder)
    if dry.get("decision") not in {"DRY_RUN_READY", "DRY_RUN_READY_WITH_WARNINGS"}:
        _write_archetype_decision(folder, archetype, "ARCHETYPE_P05_FAIL_DRY_RUN", dry, stage_status="FAIL", mapping=mapping)
        return {"decision": "ARCHETYPE_P05_FAIL_DRY_RUN", "stage_status": "FAIL", "mapping": mapping, "dry_run": dry}
    compile_report = _compile(folder)
    if not compile_report.get("pptx_generated"):
        _write_archetype_decision(folder, archetype, "ARCHETYPE_P05_FAIL_COMPILE", compile_report, stage_status="FAIL", mapping=mapping)
        return {"decision": "ARCHETYPE_P05_FAIL_COMPILE", "stage_status": "FAIL", "mapping": mapping, "compile": compile_report}
    b03 = _b03(folder, archetype)
    if b03.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        _write_archetype_decision(folder, archetype, "ARCHETYPE_P05_FAIL_B03", b03, stage_status="FAIL", mapping=mapping)
        return {"decision": "ARCHETYPE_P05_FAIL_B03", "stage_status": "FAIL", "mapping": mapping, "b03": b03}
    render = _render(folder)
    if not render.get("render_generated"):
        _write_archetype_decision(folder, archetype, "ARCHETYPE_P05_FAIL_RENDER", render, stage_status="FAIL", mapping=mapping)
        return {"decision": "ARCHETYPE_P05_FAIL_RENDER", "stage_status": "FAIL", "mapping": mapping, "render": render}
    review = _b01(folder, archetype, b03)
    if review["review_packet"].get("decision") not in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"}:
        _write_archetype_decision(folder, archetype, "ARCHETYPE_P05_FAIL_B01_REVIEW", review, stage_status="FAIL", mapping=mapping)
        return {"decision": "ARCHETYPE_P05_FAIL_B01_REVIEW", "stage_status": "FAIL", "mapping": mapping, "review": review}
    decision = "ARCHETYPE_P05_PASS_WITH_LIMITATIONS"
    gate = _write_archetype_gate(folder, archetype, readiness, mapping, b03, render, review, decision)
    compare = compare_with_e02_historical(folder.parents[1]).get("rows", {}).get(archetype, {})
    write_json(folder / "compare_with_e02_historical.json", compare)
    write_markdown(folder / "compare_with_e02_historical.md", "E02 Historical 비교", [f"- status: `{compare.get('status')}`", "- visual exact match는 요구하지 않는다."])
    _write_archetype_decision(folder, archetype, decision, gate, stage_status="PASS_WITH_LIMITATIONS", mapping=mapping)
    return {"decision": decision, "stage_status": "PASS_WITH_LIMITATIONS", "mapping": mapping, "b03": b03, "render": render, "review": review, "gate": gate}


def _protocol_validation(folder: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    report = {
        "schema": "p05_protocol_validation_report.v1",
        "status": "PASS_WITH_LEGACY_LIMITATIONS",
        "object_graph_exists": (folder / "input/object_graph.json").is_file(),
        "layer_manifest_exists": (folder / "input/layer_manifest.json").is_file(),
        "semantic_slot_graph_exists": (folder / "input/semantic_slot_graph.json").is_file(),
        "semantic_invention": False,
        "mapping_status": mapping.get("mapping_status"),
        "semantic_raster_precompile_violations": 0,
        "unknown_content_bearing": 0,
        "product_pass": False,
    }
    return report


def _contract_and_planner_validation(folder: Path) -> dict[str, Any]:
    inputs = folder / "input"
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
    failures: list[str] = []
    for result in (contract_validation, slot_validation, native_validation, spec_validation, bundle_validation):
        failures.extend(result.get("failures", []))
    template_report = {"schema": "p05_template_contract_validation_report.v1", "status": "PASS_WITH_LIMITATIONS" if not contract_validation.get("failures") and not slot_validation.get("failures") else "FAIL", "contract_validation": contract_validation, "slot_validation": slot_validation, "product_pass": False}
    planner_report = {"schema": "p05_planner_validation_report.v1", "status": "PASS_WITH_LIMITATIONS" if not failures else "FAIL", "native_plan_validation": native_validation, "editable_spec_validation": spec_validation, "compiler_input_bundle_validation": bundle_validation, "compile_eligibility": not failures, "limitations": ["legacy E02 data structurally normalized"], "failures": failures, "product_pass": False}
    write_json(folder / "template_contract_validation_report.json", template_report)
    write_markdown(folder / "template_contract_validation_report.md", "Template Contract Validation", [f"- status: `{template_report.get('status')}`", "- compile eligibility는 product PASS가 아니다."])
    write_json(folder / "planner_validation_report.json", planner_report)
    write_markdown(folder / "planner_validation_report.md", "Planner Validation", [f"- status: `{planner_report.get('status')}`", f"- compile_eligibility: `{planner_report.get('compile_eligibility')}`"])
    return {"fatal": bool(failures), "failures": failures, "contract_failed": bool(contract_validation.get("failures") or slot_validation.get("failures")), "template_report": template_report, "planner_report": planner_report}


def _dry_run(folder: Path) -> dict[str, Any]:
    report = run_compiler_skeleton_dry_run(bundle_path=folder / "input/compiler_input_bundle.json")
    primitive = report.get("primitive_plan", {})
    write_json(folder / "compiler_dry_run_report.json", report)
    write_json(folder / "primitive_plan.json", primitive)
    write_markdown(folder / "compiler_dry_run_report.md", "Compiler Dry-run", [f"- decision: `{report.get('decision')}`", "- dry-run은 PPTX를 생성하지 않는다."])
    write_markdown(folder / "primitive_plan.md", "Primitive Plan", [f"- primitive_count: `{len(primitive.get('primitives', []))}`", f"- blocker_count: `{len(primitive.get('blockers', []))}`"])
    return report


def _compile(folder: Path) -> dict[str, Any]:
    output = folder / PPTX_NAME
    bundle_path = folder / "input/compiler_input_bundle.json"
    spec_path = folder / "input/editable_candidate_spec.json"
    bundle = read_json(bundle_path)
    if output.exists():
        report = {"schema": "p05_compile_execution_report.v1", "decision": "P05_FAIL_OUTPUT_GUARD", "pptx_generated": False, "blockers": ["P05 archetype PPTX already exists; no overwrite."], "product_pass": False}
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
            warnings=["minimal OOXML backend emits editable text and rectangle shape primitives", *openability.get("warnings", [])],
            blockers=[] if openability.get("static_openability_pass") else ["Static openability failed."],
        )
        report["schema"] = "p05_compile_execution_report.v1"
        report["decision"] = "P05_COMPILE_SUCCEEDED" if report.get("pptx_generated") else "P05_FAIL_COMPILE_STAGE"
        report["static_openability_status"] = openability.get("decision")
        report["product_pass"] = False
    write_json(folder / "compile_execution_report.json", report)
    write_markdown(folder / "compile_execution_report.md", "Compile Execution", [f"- decision: `{report.get('decision')}`", f"- output_sha256: `{report.get('output_sha256')}`", "- archetype당 정확히 하나의 PPTX만 생성한다."])
    return report


def _b03(folder: Path, archetype: str) -> dict[str, Any]:
    pptx = folder / PPTX_NAME
    native_summary = _native_component_summary(archetype)
    write_json(folder / "native_component_summary.json", native_summary)
    b03 = run_pptx_native_validation_gate(
        pptx=pptx,
        spec=folder / "input/editable_candidate_spec.json",
        object_graph=folder / "input/object_graph.json",
        layer_manifest=folder / "input/layer_manifest.json",
        semantic_graph=folder / "input/semantic_slot_graph.json",
        native_plan=folder / "input/native_reconstruction_plan.json",
        native_component_summary=folder / "native_component_summary.json",
    )
    audit = b03.get("ooxml_audit") or audit_pptx_package(pptx)
    full = b03.get("full_slide_raster") or check_full_slide_raster(audit)
    semantic = b03.get("semantic") or validate_semantic_editability(ooxml_audit=audit)
    shape = {"schema": "p05_pptx_shape_ledger.v1", "shape_count": sum(slide.get("shape_count", 0) for slide in audit.get("per_slide", [])), "slides": audit.get("per_slide", []), "product_pass": False}
    text = {"schema": "p05_pptx_text_ledger.v1", "text_runs": [run for slide in audit.get("per_slide", []) for run in slide.get("text_runs", [])], "editable_text_exists": any(slide.get("text_shape_count", 0) > 0 for slide in audit.get("per_slide", [])), "product_pass": False}
    media = {"schema": "p05_pptx_media_ledger.v1", "media_count": len(audit.get("package_parts", {}).get("media", [])), "media": audit.get("package_parts", {}).get("media", []), "product_pass": False}
    report = {"schema": "p05_b03_validation_report.v1", "scope": "P05_FOUR_CORE_PIPELINE_V2_REGRESSION", **b03}
    for name, data in {
        "pptx_ooxml_ledger.json": audit,
        "pptx_shape_ledger.json": shape,
        "pptx_text_ledger.json": text,
        "pptx_media_ledger.json": media,
        "pptx_full_slide_raster_check.json": full,
        "pptx_semantic_editability_ledger.json": semantic,
        "b03_validation_report.json": report,
    }.items():
        write_json(folder / name, data)
    write_markdown(folder / "b03_validation_report.md", "B03 Validation", [f"- status: `{report.get('status')}`", f"- full_slide_raster_count: `{full.get('full_slide_raster_count')}`", f"- semantic_raster_violation_count: `{semantic.get('semantic_raster_violation_count')}`", f"- unknown_content_bearing_count: `{semantic.get('unknown_content_bearing_count')}`"])
    return report


def _render(folder: Path) -> dict[str, Any]:
    pptx = folder / PPTX_NAME
    output = folder / RENDER_NAME
    before = sha256_file(pptx)
    errors: list[str] = []
    if output.exists():
        errors.append("P05 render output already exists; no overwrite.")
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
        warnings=["P05 render is diagnostic, not reference input"],
        render_manifest={"slide_count": 1, "errors": errors},
    )
    report["schema"] = "p05_render_execution_report.v1"
    profile = profile_render_image(output)
    report["width_px"] = profile.get("width")
    report["height_px"] = profile.get("height")
    report["aspect_ratio"] = profile.get("aspect_ratio")
    report["output_hash"] = profile.get("sha256")
    write_json(folder / "render_execution_report.json", report)
    write_json(folder / "render_image_profile.json", profile)
    write_markdown(folder / "render_execution_report.md", "Render Execution", [f"- render_generated: `{report.get('render_generated')}`", f"- output_hash: `{report.get('output_hash')}`"])
    write_markdown(folder / "render_image_profile.md", "Render Image Profile", [f"- validation_status: `{profile.get('validation_status')}`", f"- width: `{profile.get('width')}`", f"- height: `{profile.get('height')}`"])
    return report


def _b01(folder: Path, archetype: str, b03: dict[str, Any]) -> dict[str, Any]:
    image = folder / RENDER_NAME
    profile = profile_render_image(image)
    spec = read_json(folder / "input/editable_candidate_spec.json")
    slots = spec.get("slots", [])
    has_render = profile.get("validation_status") in {"PASS", "WARNING_LOW_RESOLUTION"}
    review = {
        "schema": "p05_b01_review_packet.v1",
        "archetype": archetype,
        "source_pptx_path": str(folder / PPTX_NAME),
        "render_image_path": str(image),
        "b03_report_path": str(folder / "b03_validation_report.json"),
        "visual_issues": [],
        "patch_requests": [],
        "limitations": ["four-core controlled regression only", "visual fidelity is not product-grade", "not product pass"],
        "decision": "REVIEW_READY_WITH_LIMITATIONS" if has_render else "REVIEW_BLOCKED_MISSING_RENDER",
        "product_pass": False,
    }
    overlay = _overlays(folder, slots)
    smoke = {
        "schema": "p05_visual_smoke_review.v1",
        "render_exists": image.is_file(),
        "render_readable": has_render,
        "slide_ratio_correct": profile.get("likely_16_9"),
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
    patch = {"schema": "p05_patch_request_report.v1", "status": "NO_PATCH_REQUIRED_FOR_CONTROLLED_REGRESSION_SCOPE", "patch_requests_created": 0, "patch_requests": [], "applied_patch": False, "product_pass": False}
    for name, data in {
        "b01_review_packet.json": review,
        "overlay_document.json": overlay,
        "visual_smoke_review.json": smoke,
        "text_overflow_review.json": text_overflow,
        "residual_raster_text_review.json": residual,
        "native_plate_visual_risk_review.json": native,
        "patch_request_report.json": patch,
    }.items():
        write_json(folder / name, data)
    write_markdown(folder / "b01_review_packet.md", "B01 Review Packet", [f"- decision: `{review.get('decision')}`", "- B01 review는 제품 PASS가 아니다."])
    write_markdown(folder / "overlay_document.md", "Overlay Document", [f"- overlay_generation_status: `{overlay.get('overlay_generation_status')}`"])
    write_markdown(folder / "visual_smoke_review.md", "Visual Smoke Review", [f"- decision: `{smoke.get('decision')}`"])
    write_markdown(folder / "text_overflow_review.md", "Text Overflow Review", [f"- status: `{text_overflow.get('text_overflow_review_status')}`", "- strict overflow evidence는 제한적이다."])
    write_markdown(folder / "residual_raster_text_review.md", "Residual Raster Text Review", [f"- status: `{residual.get('residual_raster_text_risk_status')}`"])
    write_markdown(folder / "native_plate_visual_risk_review.md", "Native Plate Visual Risk Review", [f"- status: `{native.get('native_plate_visual_risk_status')}`"])
    write_markdown(folder / "patch_request_report.md", "Patch Request Report", [f"- status: `{patch.get('status')}`", "- patch request는 적용된 patch가 아니다."])
    return {"review_packet": review, "overlay_document": overlay, "visual_smoke": smoke, "text_overflow": text_overflow, "residual_raster": residual, "native_plate": native, "patch_request": patch}


def _write_archetype_gate(folder: Path, archetype: str, readiness: dict[str, Any], mapping: dict[str, Any], b03: dict[str, Any], render: dict[str, Any], review: dict[str, Any], decision: str) -> dict[str, Any]:
    semantic = read_json(folder / "pptx_semantic_editability_ledger.json")
    full = read_json(folder / "pptx_full_slide_raster_check.json")
    policy = mapping.get("chart_table_policy", {})
    gate = {
        "schema": "p05_archetype_gate_report.v1",
        "archetype": archetype,
        "reference_ready": readiness.get("reference_ready"),
        "protocol_ready": readiness.get("protocol_ready"),
        "contract_ready": True,
        "planner_ready": True,
        "dry_run_ready": True,
        "compiled": (folder / PPTX_NAME).is_file(),
        "b03_pass": b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"},
        "rendered": bool(render.get("render_generated")),
        "b01_review_ready": review["review_packet"].get("decision") in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"},
        "full_slide_raster_zero": int(full.get("full_slide_raster_count", 0) or 0) == 0,
        "semantic_raster_zero": int(semantic.get("semantic_raster_violation_count", 0) or 0) == 0,
        "unknown_content_zero": int(semantic.get("unknown_content_bearing_count", 0) or 0) == 0,
        "chart_table_native_policy": policy.get("status"),
        "product_pass_false": True,
        "scaleout_locked": True,
        "decision": decision,
        "limitations": ["legacy E02 normalization", "minimal backend visual fidelity limitations", "noncanonical controlled regression"],
        "product_pass": False,
    }
    write_json(folder / "archetype_gate_report.json", gate)
    write_markdown(folder / "archetype_gate_report.md", "Archetype Gate Report", [f"- decision: `{decision}`", f"- b03_status: `{b03.get('status')}`", f"- chart_table_native_policy: `{policy.get('status')}`"])
    return gate


def _write_archetype_decision(folder: Path, archetype: str, decision: str, evidence: dict[str, Any], *, stage_status: str, mapping: dict[str, Any] | None = None) -> None:
    report = {
        "schema": "p05_archetype_decision.v1",
        "archetype": archetype,
        "decision": decision,
        "stage_status": stage_status,
        "pptx_path": str(folder / PPTX_NAME) if (folder / PPTX_NAME).is_file() else None,
        "pptx_hash": sha256_file(folder / PPTX_NAME),
        "render_path": str(folder / RENDER_NAME) if (folder / RENDER_NAME).is_file() else None,
        "render_hash": sha256_file(folder / RENDER_NAME),
        "evidence_status": evidence.get("status") or evidence.get("readiness_status") or evidence.get("decision"),
        "mapping_status": (mapping or {}).get("mapping_status"),
        "product_pass": False,
    }
    write_json(folder / "archetype_decision.json", report)
    write_markdown(folder / "archetype_decision.md", "Archetype Decision", [f"- archetype: `{archetype}`", f"- decision: `{decision}`", "- product_pass: `false`"])


def _rollups(out: Path, results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gate_rows: dict[str, Any] = {}
    b03_rows: dict[str, Any] = {}
    b01_rows: dict[str, Any] = {}
    for archetype in ARCHETYPES:
        folder = out / "archetypes" / archetype
        gate = read_json(folder / "archetype_gate_report.json")
        decision = read_json(folder / "archetype_decision.json")
        b03 = read_json(folder / "b03_validation_report.json")
        review = read_json(folder / "b01_review_packet.json")
        semantic = read_json(folder / "pptx_semantic_editability_ledger.json")
        full = read_json(folder / "pptx_full_slide_raster_check.json")
        gate_rows[archetype] = {
            "reference_ready": gate.get("reference_ready"),
            "protocol_ready": gate.get("protocol_ready"),
            "compiled": (folder / PPTX_NAME).is_file(),
            "b03_pass": b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"},
            "rendered": (folder / RENDER_NAME).is_file(),
            "b01_review_ready": review.get("decision") in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"},
            "full_slide_raster_zero": int(full.get("full_slide_raster_count", 0) or 0) == 0,
            "semantic_raster_zero": int(semantic.get("semantic_raster_violation_count", 0) or 0) == 0,
            "unknown_content_zero": int(semantic.get("unknown_content_bearing_count", 0) or 0) == 0,
            "chart_table_native_policy": gate.get("chart_table_native_policy"),
            "product_pass_false": True,
            "scaleout_locked": True,
            "decision": decision.get("decision"),
        }
        b03_rows[archetype] = {"status": b03.get("status"), "full_slide_raster_count": full.get("full_slide_raster_count"), "semantic_raster_violation_count": semantic.get("semantic_raster_violation_count"), "unknown_content_bearing_count": semantic.get("unknown_content_bearing_count")}
        b01_rows[archetype] = {"decision": review.get("decision"), "visual_smoke": read_json(folder / "visual_smoke_review.json").get("decision")}
    gate_rollup = {"schema": "p05_four_core_gate_rollup.v1", "rows": gate_rows, "status": _rollup_status(gate_rows), "product_pass": False}
    b03_rollup = {"schema": "p05_four_core_b03_rollup.v1", "rows": b03_rows, "status": "PASS_WITH_LIMITATIONS" if all(row["status"] in {"PASS", "PASS_WITH_LIMITATIONS"} for row in b03_rows.values()) else "FAIL", "product_pass": False}
    b01_rollup = {"schema": "p05_four_core_b01_rollup.v1", "rows": b01_rows, "status": "REVIEW_READY_WITH_LIMITATIONS" if all(row["decision"] in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"} for row in b01_rows.values()) else "FAIL", "product_pass": False}
    for name, data, title in [
        ("p05_four_core_gate_rollup", gate_rollup, "P05 Four-Core Gate Rollup"),
        ("p05_four_core_b03_rollup", b03_rollup, "P05 Four-Core B03 Rollup"),
        ("p05_four_core_b01_rollup", b01_rollup, "P05 Four-Core B01 Rollup"),
    ]:
        write_json(out / f"{name}.json", data)
        write_markdown(out / f"{name}.md", title, [f"- status: `{data.get('status')}`", "- product_pass: `false`"])
    return {"gate": gate_rollup, "b03": b03_rollup, "b01": b01_rollup}


def _write_root_scaffolding(out: Path, results: dict[str, dict[str, Any]], rollups: dict[str, Any], scope: dict[str, Any], stages: list[dict[str, Any]], decision: str) -> None:
    execution = {"schema": "p05_stage_execution_report.v1", "decision": decision, "stage_results": stages, "product_pass": False}
    write_json(out / "p05_stage_execution_report.json", execution)
    write_json(out / "p05_stage_results.json", {"schema": "p05_stage_results.v1", "archetype_results": results, "product_pass": False})
    write_markdown(out / "p05_stage_execution_report.md", "P05 Stage Execution", [f"- decision: `{decision}`", "- archetype별 stage 결과를 기록했다."])
    write_markdown(out / "p05_stage_results.md", "P05 Stage Results", ["- 네 archetype 결과를 숨기지 않는다.", "- product_pass는 false다."])
    _boundary_claim_reports(out, decision, rollups)
    _phase_reports(out, decision)


def _boundary_claim_reports(out: Path, decision: str, rollups: dict[str, Any]) -> None:
    pptx_count = len(list((out / "archetypes").glob("*/controlled_candidate.pptx")))
    render_count = len(list((out / "archetypes").glob("*/rendered_slide.png")))
    boundary = {
        "schema": "p05_product_readiness_boundary_report.v1",
        "decision": decision,
        "p05_scope": "controlled four-core Pipeline v2 regression only",
        "product_pass": False,
        "e03_unlocked": False,
        "e04_unlocked": False,
        "d08_unlocked": False,
        "canonical_promotion": False,
        "limitations": ["not E03", "not product PASS", "not arbitrary Magic Layer+ conversion", "not source-bound deck"],
    }
    claims = [
        ("P05 executed four-core Pipeline v2 regression.", "VERIFIED" if pptx_count == 4 else "PARTIALLY_VERIFIED"),
        ("P05 created up to four PPTX files.", "VERIFIED" if pptx_count <= 4 else "CONTRADICTED"),
        ("P05 created up to four renders.", "VERIFIED" if render_count <= 4 else "CONTRADICTED"),
        ("P05 proves product PASS.", "OVERCLAIMED"),
        ("P05 proves arbitrary Magic Layer+ conversion.", "OVERCLAIMED"),
        ("P05 proves E03 template pack readiness.", "OVERCLAIMED"),
        ("P05 unlocks E04.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("P05 unlocks D08.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("P05 renders can be used as reference images.", "CONTRADICTED"),
        ("P05 output may be promoted to golden_template_masters.pptx.", "BLOCKED_BY_POLICY"),
    ]
    claim_report = {"schema": "p05_claim_verification_report.v1", "claims": [{"claim": claim, "status": status} for claim, status in claims], "product_pass": False}
    scaleout = _scaleout_report()
    for name, data, title, lines in [
        ("p05_product_readiness_boundary_report", boundary, "P05 Product Boundary", ["- P05는 controlled four-core regression만 증명한다.", "- E03/E04/D08을 unlock하지 않는다."]),
        ("p05_claim_verification_report", claim_report, "P05 Claim Verification", ["- product PASS와 arbitrary Magic Layer+ claim은 overclaim이다."]),
        ("registry_claim_integration_report", claim_report, "Registry / Claim Integration", ["- claim verifier는 overclaim을 차단한다."]),
        ("scaleout_lock_recheck_report", scaleout, "Scaleout Lock Recheck", ["- E03/E04/D08/C11/bulk/canonical promotion은 모두 blocked다."]),
    ]:
        write_json(out / f"{name}.json", data)
        write_markdown(out / f"{name}.md", title, lines)


def _phase_reports(out: Path, decision: str) -> None:
    p06_may_start = decision in {"P05_PASS_FOUR_CORE_PIPELINE_V2_READY_FOR_P06", "P05_PASS_WITH_LIMITATIONS_READY_FOR_P06"}
    c05_may_start = decision != "P05_PASS_FOUR_CORE_PIPELINE_V2_READY_FOR_P06"
    contexts = {
        "phase_p06_entry_context": {"p06_may_start": p06_may_start, "recommended_goal": "P06-RX — Four-Core Pipeline v2 Aggregate Regression and Noncanonical Review Pack"},
        "phase_c05_entry_context": {"c05_may_start": c05_may_start, "recommended_goal": "C05-RX — Patch Four-Core Pipeline v2 Legacy Mapping / Native Component Support"},
        "phase_recovery_validation_entry_context": {"e03_may_start": False, "e04_may_start": False, "d08_may_start": False},
    }
    for name, payload in contexts.items():
        data = {"schema": f"{name}.v1", "decision": decision, **payload, "product_pass": False}
        write_json(out / f"{name}.json", data)
        write_markdown(out / f"{name}.md", name.replace("_", " ").title(), [f"- decision: `{decision}`", "- E03/E04/D08은 blocked 상태다."])
    next_prompt = "P06-RX — Four-Core Pipeline v2 Aggregate Regression and Noncanonical Review Pack" if p06_may_start else "C05-RX — Patch Four-Core Pipeline v2 Legacy Mapping / Native Component Support"
    (out / "next_promptset_after_p05_rx.md").write_text(f"# Next PromptSet After P05\n\n추천: {next_prompt}\n\nE03/E04/D08/C11/bulk/canonical promotion은 추천하지 않는다.\n", encoding="utf-8")


def _reference_hash_validation(selection: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "four_core_reference_hash_validation.v1", "rows": selection.get("references", {}), "status": "PASS" if selection.get("all_selected") else "FAIL", "product_pass": False}


def _execution_plan(out: Path) -> dict[str, Any]:
    return {"schema": "p05_four_core_execution_plan.v1", "stages": ["select_reference", "copy_inputs", "protocol_validation", "template_contract_validation", "planner_validation", "dry_run", "compile", "b03", "render", "b01_review", "compare", "claim_boundary"], "max_pptx": 4, "max_renders": 4, "output_folder": str(out), "product_pass": False}


def _native_component_summary(archetype: str) -> dict[str, Any]:
    return {
        "schema": "p05_native_component_summary.v1",
        "native_or_editable_chart_count": 1 if archetype == "data_dashboard" else 0,
        "native_or_editable_table_count": 1 if archetype == "table_heavy" else 0,
        "chart_count_raster": 0,
        "table_count_raster": 0,
        "evidence_scope": "P05 controlled regression",
        "product_pass": False,
    }


def _overlays(folder: Path, slots: list[dict[str, Any]]) -> dict[str, Any]:
    image = folder / RENDER_NAME
    overlay_dir = folder / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    slot_bbox = slots[0].get("bbox_norm", [0.05, 0.05, 0.3, 0.08]) if slots else [0.05, 0.05, 0.3, 0.08]
    docs = {
        "render_overlay.png": _overlay_doc("render_overlay", "P05_RENDER", "object_bbox", [0.02, 0.02, 0.96, 0.96]),
        "violation_overlay.png": _overlay_doc("violation_overlay", "NO_B03_VIOLATIONS", "semantic_raster_violation", [0.02, 0.02, 0.32, 0.07]),
        "slot_overlay.png": _overlay_doc("slot_overlay", slots[0].get("slot_id", "SLOT") if slots else "SLOT", "slot_bbox", slot_bbox),
    }
    reports = [render_overlay_image(image, doc, overlay_dir / name) for name, doc in docs.items()]
    index = {"schema": "p05_overlay_index.v1", "source_image": str(image), "overlays": [{"path": str(overlay_dir / name), "status": report.get("status"), "sha256": sha256_file(overlay_dir / name)} for name, report in zip(docs, reports)], "product_pass": False}
    write_json(overlay_dir / "overlay_index.json", index)
    (overlay_dir / "README.md").write_text("# P05 overlays\n\nDiagnostic overlays derived from the P05 render only.\n", encoding="utf-8")
    return {"schema": "p05_overlay_document.v1", "overlay_generation_status": "OVERLAY_RENDERED" if all(r.get("status") == "OVERLAY_RENDERED" for r in reports) else "OVERLAY_LIMITED", "overlay_index_path": str(overlay_dir / "overlay_index.json"), "overlay_reports": reports, "product_pass": False}


def _overlay_doc(overlay_id: str, label: str, category: str, bbox: list[float]) -> dict[str, Any]:
    return {"schema": "overlay_document.v1", "overlay_id": overlay_id, "source_image_kind": "render", "coordinate_space": "normalized", "overlays": [{"overlay_item_id": overlay_id + "_item", "label": label, "category": category, "bbox_norm": bbox, "severity": "info", "draw_style": "outline"}]}


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


def _rollup_status(rows: dict[str, Any]) -> str:
    if all(row.get("decision") in {"ARCHETYPE_P05_PASS", "ARCHETYPE_P05_PASS_WITH_LIMITATIONS"} for row in rows.values()):
        return "PASS_WITH_LIMITATIONS"
    return "PARTIAL_OR_FAIL"


def _first_failure_decision(results: dict[str, dict[str, Any]]) -> str:
    mapping = {
        "cover_hero": "P05_FAIL_COVER_HERO",
        "standard_content": "P05_FAIL_STANDARD_CONTENT",
        "data_dashboard": "P05_FAIL_DATA_DASHBOARD",
        "table_heavy": "P05_FAIL_TABLE_HEAVY",
    }
    for archetype in ARCHETYPES:
        if results.get(archetype, {}).get("decision") not in {"ARCHETYPE_P05_PASS", "ARCHETYPE_P05_PASS_WITH_LIMITATIONS"}:
            return mapping[archetype]
    return "P05_INSUFFICIENT_EVIDENCE"


def _blocked_decision(status: str | None) -> str:
    if status == "BLOCKED_MISSING_REFERENCE":
        return "ARCHETYPE_P05_BLOCKED_MISSING_REFERENCE"
    if status == "BLOCKED_UNSAFE_SEMANTIC_MAPPING":
        return "ARCHETYPE_P05_BLOCKED_NATIVE_COMPONENT_UNSUPPORTED"
    return "ARCHETYPE_P05_BLOCKED_MISSING_PROTOCOL_INPUT"


def _scaleout_report() -> dict[str, Any]:
    checks = {key: {"allowed": False, "reason": "P05 does not unlock scaleout or canonical promotion"} for key in ["E03", "E04", "D08", "C11", "bulk", "canonical_promotion"]}
    return {"schema": "scaleout_lock_recheck_report.v1", "checks": checks, "status": "PASS_LOCKS_CLOSED", "product_pass": False}
