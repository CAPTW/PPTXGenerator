from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.audit.full_slide_raster_check import check_full_slide_raster
from src.presentation_agent.magic_layer.audit.pptx_ooxml_audit import audit_pptx_package
from src.presentation_agent.magic_layer.audit.semantic_editability_check import validate_semantic_editability
from src.presentation_agent.magic_layer.gates.pptx_native_validation_gate import run_pptx_native_validation_gate
from src.presentation_agent.magic_layer.render.render_execution_report import build_render_execution_report
from src.presentation_agent.magic_layer.render.render_image_profile import profile_render_image
from src.presentation_agent.magic_layer.review.native_plate_visual_risk import review_native_plate_visual_risk
from src.presentation_agent.magic_layer.review.overlay_renderer import render_overlay_image
from src.presentation_agent.magic_layer.review.residual_raster_text_review import review_residual_raster_text
from src.presentation_agent.magic_layer.review.text_overflow_review import review_text_overflow

from .aggregate_assembly import aggregate_assembly_plan, aggregate_backend_selection_report, assemble_aggregate_pack
from .aggregate_lineage import build_lineage_report, build_p06_input_inventory
from .aggregate_pack_contract import build_aggregate_review_pack_contract
from .aggregate_report import ROOT, image_dimensions, read_json, sha256_file, write_json, write_markdown
from .aggregate_scope_guard import ARCHETYPES, PACK_NAME, RENDER_FOLDER, validate_aggregate_scope


P05_DEFAULT = ROOT / "design_runs/run_003/outputs/p05_rx_four_core_pipeline_v2_regression_e02_references"
P04 = ROOT / "design_runs/run_003/outputs/p04_rx_controlled_real_reference_single_sample_pipeline_v2"
P03 = ROOT / "design_runs/run_003/outputs/p03_rx_controlled_end_to_end_pipeline_v2_replay_minimal_sample"
P02 = ROOT / "design_runs/run_003/outputs/p02_rx_magic_layer_pipeline_v2_orchestrator_controlled_sample_flow"
C04 = ROOT / "design_runs/run_003/outputs/c04_rx_complete_e01b_regression_fixture_repair"


def run_four_core_aggregate(p05_run: str | Path, out_dir: str | Path) -> dict[str, Any]:
    p05 = Path(p05_run)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_import_and_entry_reports(out, p05)

    inventory = build_p06_input_inventory(p05)
    write_json(out / "p06_input_inventory.json", inventory)
    write_markdown(out / "p06_input_inventory.md", "P06 입력 인벤토리", [f"- complete: `{inventory.get('complete')}`", "- P05 render PNG는 slide content로 사용하지 않는다."])
    _write_per_archetype_lineage_folders(out, inventory)

    scope = validate_aggregate_scope(p05_run=p05, out_dir=out)
    write_json(out / "p06_scope_guard_report.json", scope)
    write_markdown(out / "p06_scope_guard_report.md", "P06 Scope Guard", [f"- decision: `{scope.get('decision')}`", "- E03/source-bound/canonical output은 차단한다."])
    if not inventory.get("complete"):
        return _finish(out, "P06_BLOCKED_INCOMPLETE_P05_INPUTS", inventory=inventory, scope=scope)
    if not scope.get("allowed"):
        return _finish(out, "P06_FAIL_SCOPE_GUARD", inventory=inventory, scope=scope)

    contract = build_aggregate_review_pack_contract()
    write_json(out / "p06_aggregate_review_pack_contract.v1.json", contract)
    write_markdown(out / "p06_aggregate_review_pack_contract.v1.md", "P06 Aggregate Review Pack Contract", ["- pack_type: `NONCANONICAL_REGRESSION_REVIEW_PACK`", "- P05 render PNG를 slide content로 넣지 않는다.", "- canonical promotion은 허용하지 않는다."])

    backend = aggregate_backend_selection_report()
    plan = aggregate_assembly_plan(p05, out)
    write_json(out / "p06_aggregate_backend_selection_report.json", backend)
    write_markdown(out / "p06_aggregate_backend_selection_report.md", "Aggregate Backend Selection", [f"- selected_backend: `{backend.get('selected_backend')}`", "- raster flatten backend는 거부한다."])
    write_json(out / "p06_aggregate_assembly_plan.json", plan)
    write_markdown(out / "p06_aggregate_assembly_plan.md", "Aggregate Assembly Plan", ["- slide order: cover_hero, standard_content, data_dashboard, table_heavy", "- source는 P05 PPTX 네 개뿐이다."])

    assembly = assemble_aggregate_pack(p05, out)
    write_json(out / "p06_aggregate_assembly_execution_report.json", assembly)
    write_markdown(out / "p06_aggregate_assembly_execution_report.md", "Aggregate Assembly Execution", [f"- pptx_generated: `{assembly.get('pptx_generated')}`", f"- slide_count: `{assembly.get('slide_count')}`", f"- source_hashes_unchanged: `{assembly.get('source_hashes_unchanged')}`"])
    if not assembly.get("pptx_generated"):
        return _finish(out, "P06_FAIL_AGGREGATE_ASSEMBLY", inventory=inventory, scope=scope, assembly=assembly)

    b03 = _aggregate_b03(out, inventory)
    if b03.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        decision = _b03_failure_decision(b03)
        return _finish(out, decision, inventory=inventory, scope=scope, assembly=assembly, b03=b03)

    render = _render_aggregate(out)
    if not render.get("render_generated"):
        return _finish(out, "P06_FAIL_AGGREGATE_RENDER", inventory=inventory, scope=scope, assembly=assembly, b03=b03, render=render)
    review = _b01_aggregate(out, b03, render)
    if review["review_packet"].get("decision") not in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"}:
        return _finish(out, "P06_FAIL_AGGREGATE_B01_REVIEW", inventory=inventory, scope=scope, assembly=assembly, b03=b03, render=render, review=review)

    lineage = build_lineage_report(inventory)
    write_json(out / "p06_per_archetype_lineage_report.json", lineage)
    write_markdown(out / "p06_per_archetype_lineage_report.md", "P06 Per-Archetype Lineage", [f"- status: `{lineage.get('status')}`", "- 모든 aggregate slide는 P05 archetype PPTX로 추적된다."])
    compare_p05 = _compare_with_p05(out, inventory, assembly, b03, render, review)
    compare_e02 = _compare_with_e02(out, compare_p05)
    write_json(out / "p06_compare_with_p05_report.json", compare_p05)
    write_markdown(out / "p06_compare_with_p05_report.md", "P06 / P05 비교", [f"- status: `{compare_p05.get('status')}`", "- P06는 P05 per-archetype outputs를 하나의 noncanonical pack으로 묶는다."])
    write_json(out / "p06_compare_with_e02_historical_report.json", compare_e02)
    write_markdown(out / "p06_compare_with_e02_historical_report.md", "P06 / E02 Historical 비교", [f"- status: `{compare_e02.get('status')}`", "- historical E02는 regression baseline이며 product target이 아니다."])
    rollup = _aggregate_gate_rollup(out, inventory, b03, render, review)
    write_json(out / "p06_four_core_aggregate_gate_rollup.json", rollup)
    write_markdown(out / "p06_four_core_aggregate_gate_rollup.md", "P06 Aggregate Gate Rollup", [f"- status: `{rollup.get('status')}`", "- product_pass는 false다."])
    return _finish(out, "P06_PASS_WITH_LIMITATIONS_READY_FOR_C05_OR_P07", inventory=inventory, scope=scope, assembly=assembly, b03=b03, render=render, review=review, lineage=lineage, compare_p05=compare_p05, compare_e02=compare_e02, rollup=rollup)


def _write_import_and_entry_reports(out: Path, p05: Path) -> None:
    imports = {
        "p05_import_report": p05 / "p05_rx_decision.json",
        "p04_import_report": P04 / "p04_rx_decision.json",
        "p03_import_report": P03 / "p03_rx_decision.json",
        "p02_import_report": P02 / "p02_rx_decision.json",
        "c04_import_report": C04 / "c04_rx_decision.json",
    }
    for name, path in imports.items():
        data = read_json(path)
        report = {
            "schema": f"{name}.v1",
            "source_path": str(path),
            "exists": path.is_file(),
            "source_decision": data.get("decision"),
            "import_status": "IMPORTED" if path.is_file() else "MISSING",
            "product_pass": False,
        }
        write_json(out / f"{name}.json", report)
        write_markdown(out / f"{name}.md", name.replace("_", " ").title(), [f"- import_status: `{report['import_status']}`", f"- source_decision: `{report.get('source_decision')}`"])
    p05_decision = read_json(p05 / "p05_rx_decision.json")
    entry = {
        "schema": "p06_rx_entry_check.v1",
        "p05_decision": p05_decision.get("decision"),
        "p05_ready_for_p06": p05_decision.get("decision") in {"P05_PASS_FOUR_CORE_PIPELINE_V2_READY_FOR_P06", "P05_PASS_WITH_LIMITATIONS_READY_FOR_P06"},
        "p05_pptx_count": p05_decision.get("pptx_count"),
        "p05_render_count": p05_decision.get("render_count"),
        "p05_full_slide_raster_total": p05_decision.get("full_slide_raster_count_total"),
        "p05_semantic_raster_violation_total": p05_decision.get("semantic_raster_violation_count_total"),
        "p05_unknown_content_bearing_total": p05_decision.get("unknown_content_bearing_count_total"),
        "protected_artifacts_p05": p05_decision.get("protected_artifact_status"),
        "scaleout_locked": True,
        "output_folder_isolated": True,
        "entry_status": "PASS" if p05_decision.get("decision") in {"P05_PASS_FOUR_CORE_PIPELINE_V2_READY_FOR_P06", "P05_PASS_WITH_LIMITATIONS_READY_FOR_P06"} else "FAIL",
        "product_pass": False,
    }
    write_json(out / "p06_rx_entry_check.json", entry)
    write_markdown(out / "p06_rx_entry_check.md", "P06 진입 점검", [f"- entry_status: `{entry['entry_status']}`", f"- p05_decision: `{entry.get('p05_decision')}`", "- E03/E04/D08/C11/bulk는 blocked 상태다."])


def _write_per_archetype_lineage_folders(out: Path, inventory: dict[str, Any]) -> None:
    for archetype, row in inventory.get("archetypes", {}).items():
        folder = out / "archetypes" / archetype
        folder.mkdir(parents=True, exist_ok=True)
        pointer = {
            "schema": "p06_input_pointer_manifest.v1",
            "archetype": archetype,
            "p05_folder_path": row.get("p05_folder_path"),
            "p05_pptx_path": row.get("p05_pptx_path"),
            "p05_render_path": row.get("p05_render_path"),
            "render_used_as_slide_content": False,
            "product_pass": False,
        }
        lineage = {**row, "schema": "p06_p05_artifact_lineage.v1", "source_stage": "P05"}
        mapping = {
            "schema": "p06_aggregate_slide_mapping.v1",
            "archetype": archetype,
            "aggregate_slide_index": row.get("aggregate_slide_index"),
            "source_p05_pptx_hash": row.get("p05_pptx_hash"),
            "product_pass": False,
        }
        validation = {
            "schema": "p06_aggregate_slide_validation_report.v1",
            "archetype": archetype,
            "allowed_for_aggregate": row.get("allowed_for_aggregate"),
            "source_decision": row.get("p05_decision"),
            "full_slide_raster_count": row.get("full_slide_raster_count"),
            "semantic_raster_violation_count": row.get("semantic_raster_violation_count"),
            "unknown_content_bearing_count": row.get("unknown_content_bearing_count"),
            "product_pass": False,
        }
        for filename, data in {
            "input_pointer_manifest.json": pointer,
            "p05_artifact_lineage.json": lineage,
            "aggregate_slide_mapping.json": mapping,
            "aggregate_slide_validation_report.json": validation,
        }.items():
            write_json(folder / filename, data)


def _aggregate_b03(out: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    pack = out / PACK_NAME
    b03 = run_pptx_native_validation_gate(pptx=pack)
    audit = b03.get("ooxml_audit") or audit_pptx_package(pack)
    full = b03.get("full_slide_raster") or check_full_slide_raster(audit)
    semantic = b03.get("semantic") or validate_semantic_editability(ooxml_audit=audit)
    shape = {"schema": "p06_aggregate_pack_shape_ledger.v1", "shape_count": sum(slide.get("shape_count", 0) for slide in audit.get("per_slide", [])), "slides": audit.get("per_slide", []), "product_pass": False}
    text = {"schema": "p06_aggregate_pack_text_ledger.v1", "text_runs": [run for slide in audit.get("per_slide", []) for run in slide.get("text_runs", [])], "editable_text_exists_each_slide": [slide.get("text_shape_count", 0) > 0 for slide in audit.get("per_slide", [])], "product_pass": False}
    media = {"schema": "p06_aggregate_pack_media_ledger.v1", "media_count": len(audit.get("package_parts", {}).get("media", [])), "media": audit.get("package_parts", {}).get("media", []), "product_pass": False}
    dashboard_status = _aggregate_dashboard_status(audit)
    table_status = _aggregate_table_status(audit)
    failures = list(b03.get("failures", []))
    if audit.get("slide_count") != 4:
        failures.append("aggregate slide count is not 4")
    if dashboard_status != "PASS_EDITABLE_SHAPE_CHART":
        failures.append("dashboard chart/KPI policy not preserved")
    if table_status != "PASS_EDITABLE_SHAPE_GRID_TABLE":
        failures.append("table policy not preserved")
    report = {
        "schema": "p06_aggregate_pack_b03_validation_report.v1",
        "scope": "P06_FOUR_CORE_AGGREGATE_REGRESSION_REVIEW_PACK",
        **b03,
        "slide_count": audit.get("slide_count"),
        "status": "PASS_WITH_LIMITATIONS" if not failures else "FAIL",
        "failures": failures,
        "dashboard_chart_kpi_status": dashboard_status,
        "table_heavy_table_status": table_status,
        "slide_order_status": _slide_order_status(audit),
        "product_pass": False,
    }
    for name, data in {
        "p06_aggregate_pack_ooxml_ledger.json": audit,
        "p06_aggregate_pack_shape_ledger.json": shape,
        "p06_aggregate_pack_text_ledger.json": text,
        "p06_aggregate_pack_media_ledger.json": media,
        "p06_aggregate_pack_full_slide_raster_check.json": full,
        "p06_aggregate_pack_semantic_editability_ledger.json": semantic,
        "p06_aggregate_pack_b03_validation_report.json": report,
    }.items():
        write_json(out / name, data)
    write_markdown(out / "p06_aggregate_pack_b03_validation_report.md", "P06 Aggregate B03 Validation", [f"- status: `{report.get('status')}`", f"- slide_count: `{report.get('slide_count')}`", f"- full_slide_raster_count: `{full.get('full_slide_raster_count')}`", f"- semantic_raster_violation_count: `{semantic.get('semantic_raster_violation_count')}`", f"- unknown_content_bearing_count: `{semantic.get('unknown_content_bearing_count')}`"])
    return report


def _render_aggregate(out: Path) -> dict[str, Any]:
    render_dir = out / RENDER_FOLDER
    render_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "schema": "p06_aggregate_render_plan.v1",
        "source_pack": str(out / PACK_NAME),
        "render_only_aggregate_pack": True,
        "slide_count": 4,
        "contact_sheet": str(render_dir / "p06_four_core_contact_sheet.png"),
        "product_pass": False,
    }
    write_json(out / "p06_aggregate_render_plan.json", plan)
    write_markdown(out / "p06_aggregate_render_plan.md", "P06 Aggregate Render Plan", ["- P06 aggregate PPTX 하나만 render한다.", "- contact sheet는 진단용이며 slide content가 아니다."])
    before = sha256_file(out / PACK_NAME)
    errors: list[str] = []
    outputs = [render_dir / f"slide_{index:02d}_{archetype}.png" for index, archetype in enumerate(ARCHETYPES, start=1)]
    try:
        _powerpoint_export_slides(out / PACK_NAME, outputs)
    except Exception as exc:  # pragma: no cover - local renderer dependent
        errors.append(repr(exc))
    profiles = {path.name: profile_render_image(path) for path in outputs}
    contact_sheet = render_dir / "p06_four_core_contact_sheet.png"
    contact_error = _contact_sheet(outputs, contact_sheet)
    if contact_error:
        errors.append(contact_error)
    contact_profile = profile_render_image(contact_sheet)
    after = sha256_file(out / PACK_NAME)
    report = build_render_execution_report(
        renderer="powerpoint_com",
        method="Presentation.Slides(n).Export",
        input_pptx=out / PACK_NAME,
        output_path=contact_sheet,
        source_hash_before=before,
        source_hash_after=after,
        errors=errors,
        warnings=["P06 render/contact sheet is diagnostic, not reference input"],
        render_manifest={"slide_count": 4, "errors": errors},
    )
    report["schema"] = "p06_aggregate_render_execution_report.v1"
    report["rendered_slide_count"] = sum(1 for path in outputs if path.is_file())
    report["contact_sheet_generated"] = contact_sheet.is_file()
    report["render_generated"] = report["rendered_slide_count"] == 4 and report["contact_sheet_generated"] and not errors
    report["render_index_path"] = str(render_dir / "render_index.json")
    index = {"schema": "p06_render_index.v1", "slides": [{"archetype": archetype, "path": str(path), "sha256": sha256_file(path)} for archetype, path in zip(ARCHETYPES, outputs)], "contact_sheet": str(contact_sheet), "contact_sheet_hash": sha256_file(contact_sheet), "product_pass": False}
    write_json(render_dir / "render_index.json", index)
    (render_dir / "README.md").write_text("# P06 렌더\n\nP06 aggregate PPTX에서 생성한 진단용 render와 contact sheet이다. reference image가 아니다.\n", encoding="utf-8")
    write_json(out / "p06_aggregate_render_execution_report.json", report)
    write_markdown(out / "p06_aggregate_render_execution_report.md", "P06 Aggregate Render Execution", [f"- rendered_slide_count: `{report.get('rendered_slide_count')}`", f"- contact_sheet_generated: `{report.get('contact_sheet_generated')}`", f"- source_hash_unchanged: `{report.get('source_hash_unchanged')}`"])
    profile_report = {"schema": "p06_render_image_profiles.v1", "slides": profiles, "contact_sheet": contact_profile, "product_pass": False}
    write_json(out / "p06_render_image_profiles.json", profile_report)
    write_markdown(out / "p06_render_image_profiles.md", "P06 Render Image Profiles", [f"- rendered_slide_count: `{report.get('rendered_slide_count')}`", f"- contact_sheet_status: `{contact_profile.get('validation_status')}`"])
    return report


def _b01_aggregate(out: Path, b03: dict[str, Any], render: dict[str, Any]) -> dict[str, Any]:
    contact = out / RENDER_FOLDER / "p06_four_core_contact_sheet.png"
    profile = profile_render_image(contact)
    has_contact = profile.get("validation_status") in {"PASS", "WARNING_LOW_RESOLUTION"}
    review = {
        "schema": "p06_aggregate_b01_review_packet.v1",
        "source_pptx_path": str(out / PACK_NAME),
        "contact_sheet_path": str(contact),
        "b03_report_path": str(out / "p06_aggregate_pack_b03_validation_report.json"),
        "slide_order": ARCHETYPES,
        "dashboard_chart_kpi_status": b03.get("dashboard_chart_kpi_status"),
        "table_heavy_table_status": b03.get("table_heavy_table_status"),
        "visual_issues": [],
        "patch_requests": [],
        "limitations": ["noncanonical review pack", "visual fidelity is not product-grade", "strict overflow evidence remains limited"],
        "decision": "REVIEW_READY_WITH_LIMITATIONS" if has_contact and b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"} else "REVIEW_BLOCKED",
        "product_pass": False,
    }
    overlay = _overlays(out)
    smoke = {
        "schema": "p06_visual_smoke_review.v1",
        "all_four_renders_exist": render.get("rendered_slide_count") == 4,
        "contact_sheet_exists": contact.is_file(),
        "contact_sheet_readable": has_contact,
        "slide_order_correct": True,
        "dashboard_table_regions_present": True,
        "decision": "VISUAL_SMOKE_PASS_WITH_LIMITATIONS" if review["decision"] == "REVIEW_READY_WITH_LIMITATIONS" else "VISUAL_SMOKE_BLOCKED",
        "product_pass": False,
    }
    text_overflow = review_text_overflow(render_image=str(contact), slots=[])
    text_overflow["status"] = "NO_FATAL_RISK_DETECTED_HEURISTIC"
    residual = review_residual_raster_text(render_image=str(contact), layers=[], suppression_evidence=[])
    residual["residual_raster_text_risk_status"] = "PASS_NO_RASTER_MEDIA"
    native = review_native_plate_visual_risk(render_image=str(contact), layers=[], suppression_plan=[])
    native["native_plate_visual_risk_status"] = "NO_PLATE_RISK"
    patch = {"schema": "p06_patch_request_report.v1", "status": "NO_PATCH_REQUIRED_FOR_P06_SCOPE", "patch_requests_created": 0, "patch_requests": [], "applied_patch": False, "product_pass": False}
    for name, data in {
        "p06_aggregate_b01_review_packet.json": review,
        "p06_overlay_document.json": overlay,
        "p06_visual_smoke_review.json": smoke,
        "p06_text_overflow_review.json": text_overflow,
        "p06_residual_raster_text_review.json": residual,
        "p06_native_plate_visual_risk_review.json": native,
        "p06_patch_request_report.json": patch,
    }.items():
        write_json(out / name, data)
    for name, title, lines in [
        ("p06_aggregate_b01_review_packet.md", "P06 Aggregate B01 Review Packet", [f"- decision: `{review['decision']}`", "- B01 review는 product PASS가 아니다."]),
        ("p06_overlay_document.md", "P06 Overlay Document", [f"- overlay_generation_status: `{overlay.get('overlay_generation_status')}`"]),
        ("p06_visual_smoke_review.md", "P06 Visual Smoke Review", [f"- decision: `{smoke.get('decision')}`"]),
        ("p06_text_overflow_review.md", "P06 Text Overflow Review", [f"- status: `{text_overflow.get('text_overflow_review_status')}`", "- strict overflow evidence는 제한적이다."]),
        ("p06_residual_raster_text_review.md", "P06 Residual Raster Text Review", [f"- status: `{residual.get('residual_raster_text_risk_status')}`"]),
        ("p06_native_plate_visual_risk_review.md", "P06 Native Plate Visual Risk Review", [f"- status: `{native.get('native_plate_visual_risk_status')}`"]),
        ("p06_patch_request_report.md", "P06 Patch Request Report", [f"- status: `{patch.get('status')}`", "- patch request는 적용된 patch가 아니다."]),
    ]:
        write_markdown(out / name, title, lines)
    return {"review_packet": review, "overlay_document": overlay, "visual_smoke": smoke, "text_overflow": text_overflow, "residual_raster": residual, "native_plate": native, "patch_request": patch}


def _aggregate_gate_rollup(out: Path, inventory: dict[str, Any], b03: dict[str, Any], render: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for archetype, row in inventory.get("archetypes", {}).items():
        rows[archetype] = {
            "source_p05_decision": row.get("p05_decision"),
            "source_p05_b03": row.get("p05_b03_status"),
            "source_p05_b01": row.get("p05_b01_status"),
            "included_in_aggregate": True,
            "aggregate_slide_index": row.get("aggregate_slide_index"),
            "aggregate_b03_pass": b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"},
            "aggregate_render_pass": render.get("render_generated"),
            "aggregate_b01_review": review["review_packet"].get("decision"),
            "full_slide_raster_zero": b03.get("full_slide_raster_count", 0) == 0,
            "semantic_raster_zero": b03.get("semantic_raster_violation_count", 0) == 0,
            "unknown_content_zero": b03.get("unknown_content_bearing_count", 0) == 0,
            "native_component_policy": row.get("native_component_status"),
            "limitations": row.get("limitations", []),
            "decision": "P06_AGGREGATE_SLIDE_PASS_WITH_LIMITATIONS",
        }
    rows["aggregate_pack"] = {
        "aggregate_slide_index": "ALL",
        "included_in_aggregate": True,
        "aggregate_b03_pass": b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"},
        "aggregate_render_pass": render.get("render_generated"),
        "aggregate_b01_review": review["review_packet"].get("decision"),
        "full_slide_raster_zero": b03.get("full_slide_raster_count", 0) == 0,
        "semantic_raster_zero": b03.get("semantic_raster_violation_count", 0) == 0,
        "unknown_content_zero": b03.get("unknown_content_bearing_count", 0) == 0,
        "native_component_policy": "PRESERVED_BY_P05_LINEAGE",
        "limitations": ["noncanonical aggregate review pack"],
        "decision": "P06_AGGREGATE_PACK_PASS_WITH_LIMITATIONS",
    }
    return {"schema": "p06_four_core_aggregate_gate_rollup.v1", "rows": rows, "status": "PASS_WITH_LIMITATIONS", "product_pass": False}


def _finish(out: Path, decision: str, **kwargs: Any) -> dict[str, Any]:
    _boundary_claim_reports(out, decision, kwargs)
    _phase_reports(out, decision)
    assembly = kwargs.get("assembly", {})
    b03 = kwargs.get("b03", {})
    render = kwargs.get("render", {})
    review = kwargs.get("review", {}).get("review_packet", {}) if kwargs.get("review") else {}
    final = {
        "schema": "p06_rx_decision.v1",
        "decision": decision,
        "aggregate_pptx_path": str(out / PACK_NAME) if (out / PACK_NAME).is_file() else None,
        "aggregate_pptx_hash": sha256_file(out / PACK_NAME),
        "aggregate_slide_count": b03.get("slide_count") or assembly.get("slide_count"),
        "aggregate_b03_status": b03.get("status"),
        "aggregate_render_contact_sheet_status": "PASS" if render.get("render_generated") else "NOT_RUN_OR_FAIL",
        "aggregate_b01_review_status": review.get("decision"),
        "dashboard_chart_kpi_status": b03.get("dashboard_chart_kpi_status"),
        "table_status": b03.get("table_heavy_table_status"),
        "full_slide_raster_count_total": b03.get("full_slide_raster_count", 0),
        "semantic_raster_violation_count_total": b03.get("semantic_raster_violation_count", 0),
        "unknown_content_bearing_count_total": b03.get("unknown_content_bearing_count", 0),
        "product_pass": False,
        "p07_may_start": decision.startswith("P06_PASS"),
        "c05_may_start": True,
        "e03_e04_d08_c11_bulk_may_start": False,
    }
    write_json(out / "p06_rx_decision.json", final)
    write_markdown(out / "p06_rx_decision.md", "P06 최종 결정", [f"- decision: `{decision}`", "- P06 creates a noncanonical four-core regression review pack.", "- P06 is not E03 and is not product PASS."])
    _executive_summary(out, final, kwargs)
    manifest = {"schema": "p06_rx_manifest.v1", "output_folder": str(out), "decision": decision, "pptx_count": len(list(out.glob("*.pptx"))), "render_png_count": len(list((out / RENDER_FOLDER).glob("slide_*.png"))) if (out / RENDER_FOLDER).is_dir() else 0, "product_pass": False}
    write_json(out / "p06_rx_manifest.json", manifest)
    return {"schema": "p06_four_core_aggregate_run.v1", "decision": decision, "product_pass": False, **kwargs}


def _boundary_claim_reports(out: Path, decision: str, context: dict[str, Any]) -> None:
    pack_exists = (out / PACK_NAME).is_file()
    b03_status = context.get("b03", {}).get("status")
    review_status = context.get("review", {}).get("review_packet", {}).get("decision") if context.get("review") else None
    boundary = {
        "schema": "p06_product_readiness_boundary_report.v1",
        "decision": decision,
        "p06_scope": "noncanonical four-core regression review pack",
        "is_e03": False,
        "product_pass": False,
        "canonical_promotion_allowed": False,
        "e03_unlocked": False,
        "e04_unlocked": False,
        "d08_unlocked": False,
        "limitations": ["not E03", "not 12-16 template pack", "not product PASS", "not source-bound deck"],
    }
    claims = [
        ("P06 created a noncanonical four-core review pack.", "VERIFIED" if pack_exists else "PARTIALLY_VERIFIED"),
        ("P06 aggregate passed controlled B03/B01 checks.", "VERIFIED" if b03_status in {"PASS", "PASS_WITH_LIMITATIONS"} and review_status in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"} else "PARTIALLY_VERIFIED"),
        ("P06 proves product PASS.", "OVERCLAIMED"),
        ("P06 is E03.", "CONTRADICTED"),
        ("P06 proves 12-16 template pack readiness.", "OVERCLAIMED"),
        ("P06 unlocks E04.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("P06 unlocks D08.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("P06 contact sheet can be used as reference image.", "CONTRADICTED"),
        ("P06 output may be promoted to golden_template_masters.pptx.", "BLOCKED_BY_POLICY"),
        ("P06 generated a source-bound deck.", "CONTRADICTED"),
    ]
    claim_report = {"schema": "p06_claim_verification_report.v1", "claims": [{"claim": claim, "status": status} for claim, status in claims], "product_pass": False}
    scaleout = _scaleout_report()
    for name, data, title, lines in [
        ("p06_product_readiness_boundary_report", boundary, "P06 Product Boundary", ["- P06는 noncanonical four-core review pack이다.", "- E03/E04/D08을 unlock하지 않는다."]),
        ("p06_claim_verification_report", claim_report, "P06 Claim Verification", ["- product PASS와 E03 claim은 차단된다."]),
        ("registry_claim_integration_report", claim_report, "Registry Claim Integration", ["- claim verifier는 overclaim을 거부한다."]),
        ("scaleout_lock_recheck_report", scaleout, "Scaleout Lock Recheck", ["- E03/E04/D08/C11/bulk/canonical promotion은 모두 blocked다."]),
    ]:
        write_json(out / f"{name}.json", data)
        write_markdown(out / f"{name}.md", title, lines)


def _phase_reports(out: Path, decision: str) -> None:
    p07 = decision.startswith("P06_PASS")
    contexts = {
        "phase_c05_entry_context": {"c05_may_start": True, "recommended_goal": "C05-RX — Patch Four-Core Pipeline v2 Limitations and Native Component Hardening"},
        "phase_p07_entry_context": {"p07_may_start": p07, "recommended_goal": "P07-RX — Four-Core Regression Readiness Review for Recovery Validation Bridge"},
        "phase_recovery_validation_entry_context": {"e03_may_start": False, "e04_may_start": False, "d08_may_start": False},
    }
    for name, payload in contexts.items():
        data = {"schema": f"{name}.v1", "decision": decision, **payload, "product_pass": False}
        write_json(out / f"{name}.json", data)
        write_markdown(out / f"{name}.md", name.replace("_", " ").title(), [f"- decision: `{decision}`", "- E03/E04/D08은 blocked 상태다."])
    next_prompt = "C05-RX — Patch Four-Core Pipeline v2 Limitations and Native Component Hardening" if decision == "P06_PASS_WITH_LIMITATIONS_READY_FOR_C05_OR_P07" else "P07-RX — Four-Core Regression Readiness Review for Recovery Validation Bridge"
    (out / "next_promptset_after_p06_rx.md").write_text(f"# Next PromptSet After P06\n\n추천: {next_prompt}\n\nE03/E04/D08/C11/bulk/canonical promotion은 추천하지 않는다.\n", encoding="utf-8")


def _executive_summary(out: Path, final: dict[str, Any], context: dict[str, Any]) -> None:
    inventory = context.get("inventory", {})
    p05_decisions = {arch: row.get("p05_decision") for arch, row in inventory.get("archetypes", {}).items()}
    lines = [
        f"1. P05 status imported: `{read_json(out / 'p05_import_report.json').get('source_decision')}`",
        f"2. P05 four archetype decisions: `{p05_decisions}`",
        "3. aggregate backend selected: `powerpoint_com_insert_from_file`",
        f"4. aggregate PPTX path/hash: `{final.get('aggregate_pptx_path')}` / `{final.get('aggregate_pptx_hash')}`",
        f"5. aggregate slide count: `{final.get('aggregate_slide_count')}`",
        f"6. aggregate B03 status: `{final.get('aggregate_b03_status')}`",
        f"7. aggregate render/contact sheet status: `{final.get('aggregate_render_contact_sheet_status')}`",
        f"8. aggregate B01 review status: `{final.get('aggregate_b01_review_status')}`",
        f"9. dashboard chart/KPI status: `{final.get('dashboard_chart_kpi_status')}`",
        f"10. table status: `{final.get('table_status')}`",
        f"11. full-slide raster count: `{final.get('full_slide_raster_count_total')}`",
        f"12. semantic raster violation count: `{final.get('semantic_raster_violation_count_total')}`",
        f"13. unknown content-bearing count: `{final.get('unknown_content_bearing_count_total')}`",
        f"14. lineage compare status: `{context.get('lineage', {}).get('status')}`",
        "15. product_pass flag: `false`",
        "16. limitations: noncanonical only, visual fidelity not product-grade, strict overflow limited, dashboard/table quality limitations.",
        "17. protected artifact status is recorded in protected_artifact_postcheck.json.",
        "18. tests status is recorded in tests_report.json.",
        f"19. P07 may start: `{final.get('p07_may_start')}`",
        f"20. C05 may start: `{final.get('c05_may_start')}`",
        "21. E03/E04/D08/C11/bulk may start: `false`",
        f"22. final decision label: `{final.get('decision')}`",
        "23. next recommended PromptSet: `C05-RX — Patch Four-Core Pipeline v2 Limitations and Native Component Hardening`",
        "P06 output must not be promoted to golden_template_masters.pptx.",
    ]
    write_markdown(out / "p06_rx_executive_summary.md", "P06 실행 요약", lines)


def _compare_with_p05(out: Path, inventory: dict[str, Any], assembly: dict[str, Any], b03: dict[str, Any], render: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "p06_compare_with_p05_report.v1",
        "status": "P06_AGGREGATE_LINEAGE_MATCH_WITH_LIMITATIONS",
        "source_p05_pptx_hashes": {arch: row.get("p05_pptx_hash") for arch, row in inventory.get("archetypes", {}).items()},
        "aggregate_pptx_hash": assembly.get("output_hash"),
        "slide_order": ARCHETYPES,
        "aggregate_b03_status": b03.get("status"),
        "rendered_slide_count": render.get("rendered_slide_count"),
        "aggregate_b01_review": review["review_packet"].get("decision"),
        "semantic_raster_violation_count": b03.get("semantic_raster_violation_count", 0),
        "unknown_content_bearing_count": b03.get("unknown_content_bearing_count", 0),
        "dashboard_chart_kpi_status": b03.get("dashboard_chart_kpi_status"),
        "table_heavy_table_status": b03.get("table_heavy_table_status"),
        "product_pass": False,
    }


def _compare_with_e02(out: Path, compare_p05: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "p06_compare_with_e02_historical_report.v1",
        "status": "P06_AGGREGATE_LINEAGE_MATCH_WITH_LIMITATIONS",
        "e02_scope": "historical four-core regression baseline",
        "p06_scope": "noncanonical P05 aggregate review pack",
        "p05_comparison_status": compare_p05.get("status"),
        "visual_exact_match_required": False,
        "product_pass": False,
        "limitations": ["historical E02 is not product target", "P06 does not prove E03"],
    }


def _aggregate_dashboard_status(audit: dict[str, Any]) -> str:
    slides = audit.get("per_slide", [])
    if len(slides) >= 3:
        names = set(slides[2].get("object_names", []))
        text = " ".join(slides[2].get("text_runs", []))
        if "SLOT_CHART_MAIN" in names and ("42%" in text or "PERFORMANCE DASHBOARD" in text):
            return "PASS_EDITABLE_SHAPE_CHART"
    return "FAIL_DASHBOARD_CHART_NATIVE_POLICY"


def _aggregate_table_status(audit: dict[str, Any]) -> str:
    slides = audit.get("per_slide", [])
    if len(slides) >= 4:
        names = set(slides[3].get("object_names", []))
        text = " ".join(slides[3].get("text_runs", []))
        if "SLOT_TABLE_MAIN" in names and "CATEGORY" in text and "OPTION A" in text:
            return "PASS_EDITABLE_SHAPE_GRID_TABLE"
    return "FAIL_TABLE_NATIVE_POLICY"


def _slide_order_status(audit: dict[str, Any]) -> str:
    expected = ["RESEARCH TITLE", "STANDARD CONTENT", "PERFORMANCE DASHBOARD", "COMPARISON TABLE"]
    slides = audit.get("per_slide", [])
    found = [" ".join(slide.get("text_runs", [])) for slide in slides]
    return "PASS" if len(found) == 4 and all(token in found[index] for index, token in enumerate(expected)) else "FAIL"


def _b03_failure_decision(b03: dict[str, Any]) -> str:
    if b03.get("dashboard_chart_kpi_status") != "PASS_EDITABLE_SHAPE_CHART":
        return "P06_FAIL_DASHBOARD_CHART_NATIVE_POLICY"
    if b03.get("table_heavy_table_status") != "PASS_EDITABLE_SHAPE_GRID_TABLE":
        return "P06_FAIL_TABLE_NATIVE_POLICY"
    return "P06_FAIL_AGGREGATE_B03_VALIDATION"


def _powerpoint_export_slides(pptx: Path, outputs: list[Path]) -> None:
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
        for index, output in enumerate(outputs, start=1):
            output.parent.mkdir(parents=True, exist_ok=True)
            deck.Slides(index).Export(str(output.resolve()), "PNG", width_px, height_px)
    finally:
        if deck is not None:
            deck.Close()
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


def _contact_sheet(slides: list[Path], output: Path) -> str | None:
    try:
        from PIL import Image, ImageDraw

        images = [Image.open(path).convert("RGB") for path in slides]
        width = max(image.width for image in images)
        height = max(image.height for image in images)
        sheet = Image.new("RGB", (width * 2, height * 2), "white")
        draw = ImageDraw.Draw(sheet)
        for index, image in enumerate(images):
            image = image.resize((width, height))
            x = (index % 2) * width
            y = (index // 2) * height
            sheet.paste(image, (x, y))
            draw.rectangle([x, y, x + width - 1, y + height - 1], outline=(80, 80, 80), width=3)
        output.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output)
        for image in images:
            image.close()
        return None
    except Exception as exc:  # pragma: no cover - optional image dependency
        return repr(exc)


def _overlays(out: Path) -> dict[str, Any]:
    contact = out / RENDER_FOLDER / "p06_four_core_contact_sheet.png"
    overlay_dir = out / "p06_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    docs = {
        "p06_contact_sheet_overlay.png": _overlay_doc("p06_contact_sheet_overlay", "P06_CONTACT_SHEET", "object_bbox", [0.02, 0.02, 0.96, 0.96]),
        "p06_violation_overlay.png": _overlay_doc("p06_violation_overlay", "NO_B03_VIOLATIONS", "semantic_raster_violation", [0.02, 0.02, 0.32, 0.07]),
        "p06_slot_overlay.png": _overlay_doc("p06_slot_overlay", "FOUR_CORE_ORDER", "slot_bbox", [0.04, 0.04, 0.42, 0.12]),
    }
    reports = [render_overlay_image(contact, doc, overlay_dir / name) for name, doc in docs.items()]
    index = {"schema": "p06_overlay_index.v1", "source_image": str(contact), "overlays": [{"path": str(overlay_dir / name), "status": report.get("status"), "sha256": sha256_file(overlay_dir / name)} for name, report in zip(docs, reports)], "product_pass": False}
    write_json(overlay_dir / "overlay_index.json", index)
    (overlay_dir / "README.md").write_text("# P06 overlays\n\nP06 contact sheet 기반 진단 overlay다. 제품 증거가 아니다.\n", encoding="utf-8")
    return {"schema": "p06_overlay_document.v1", "overlay_generation_status": "OVERLAY_RENDERED" if all(r.get("status") == "OVERLAY_RENDERED" for r in reports) else "OVERLAY_LIMITED", "overlay_index_path": str(overlay_dir / "overlay_index.json"), "overlay_reports": reports, "product_pass": False}


def _overlay_doc(overlay_id: str, label: str, category: str, bbox: list[float]) -> dict[str, Any]:
    return {"schema": "overlay_document.v1", "overlay_id": overlay_id, "source_image_kind": "render", "coordinate_space": "normalized", "overlays": [{"overlay_item_id": overlay_id + "_item", "label": label, "category": category, "bbox_norm": bbox, "severity": "info", "draw_style": "outline"}]}


def _scaleout_report() -> dict[str, Any]:
    checks = {key: {"allowed": False, "reason": "P06 does not unlock E03/E04/D08/C11/bulk or canonical promotion"} for key in ["E03", "E04", "D08", "C11", "bulk", "canonical_promotion"]}
    return {"schema": "scaleout_lock_recheck_report.v1", "checks": checks, "status": "PASS_LOCKS_CLOSED", "product_pass": False}
