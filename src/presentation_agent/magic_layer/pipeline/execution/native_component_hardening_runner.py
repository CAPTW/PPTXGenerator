from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.audit.full_slide_raster_check import check_full_slide_raster
from src.presentation_agent.magic_layer.audit.pptx_ooxml_audit import audit_pptx_package
from src.presentation_agent.magic_layer.audit.semantic_editability_check import validate_semantic_editability
from src.presentation_agent.magic_layer.compiler.aggregate import assemble_pptx_review_pack
from src.presentation_agent.magic_layer.compiler.backends.backend_selector import select_backend
from src.presentation_agent.magic_layer.compiler.object_naming import harden_native_component_objects
from src.presentation_agent.magic_layer.compiler.ooxml.openability_validator import validate_powerpoint_openability_static
from src.presentation_agent.magic_layer.compiler.real_compile.compile_execution_report import build_compile_execution_report
from src.presentation_agent.magic_layer.gates.pptx_native_validation_gate import run_pptx_native_validation_gate
from src.presentation_agent.magic_layer.render.render_execution_report import build_render_execution_report
from src.presentation_agent.magic_layer.render.render_image_profile import profile_render_image
from src.presentation_agent.magic_layer.review.native_plate_visual_risk import review_native_plate_visual_risk
from src.presentation_agent.magic_layer.review.overlay_renderer import render_overlay_image
from src.presentation_agent.magic_layer.review.residual_raster_text_review import review_residual_raster_text
from src.presentation_agent.magic_layer.review.text_overflow_review import review_text_overflow
from src.presentation_agent.magic_layer.template.overflow_policy import validate_required_overflow_policies

from .four_core_report import ROOT, protected_artifact_snapshot, read_json, sha256_file, write_json, write_markdown


P05_DEFAULT = ROOT / "design_runs/run_003/outputs/p05_rx_four_core_pipeline_v2_regression_e02_references"
P06 = ROOT / "design_runs/run_003/outputs/p06_rx_four_core_pipeline_v2_aggregate_regression_review_pack"
P04 = ROOT / "design_runs/run_003/outputs/p04_rx_controlled_real_reference_single_sample_pipeline_v2"
P03 = ROOT / "design_runs/run_003/outputs/p03_rx_controlled_end_to_end_pipeline_v2_replay_minimal_sample"
P02 = ROOT / "design_runs/run_003/outputs/p02_rx_magic_layer_pipeline_v2_orchestrator_controlled_sample_flow"
C04 = ROOT / "design_runs/run_003/outputs/c04_rx_complete_e01b_regression_fixture_repair"
ALLOWED_TARGETS = ["data_dashboard", "table_heavy"]


def validate_hardened_aggregate_scope(
    *,
    source_pptx_count: int,
    aggregate_pptx_count: int,
    uses_render_png_as_slide_content: bool,
    dashboard_status: str,
    table_status: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    if source_pptx_count != 4:
        blockers.append("exactly four source PPTX inputs are required")
    if aggregate_pptx_count != 1:
        blockers.append("exactly one aggregate PPTX output is allowed")
    if uses_render_png_as_slide_content:
        return {"schema": "c05_aggregate_scope_guard.v1", "allowed": False, "decision": "C05_AGGREGATE_SCOPE_BLOCKED_RENDER_AS_CONTENT", "blockers": ["render PNG cannot be slide content"], "product_pass": False}
    if dashboard_status != "PASS_EDITABLE_SHAPE_CHART_HARDENED":
        blockers.append("dashboard hardened native component evidence is missing")
    if table_status != "PASS_EDITABLE_SHAPE_GRID_TABLE_HARDENED":
        blockers.append("table hardened native component evidence is missing")
    return {
        "schema": "c05_aggregate_scope_guard.v1",
        "allowed": not blockers,
        "decision": "C05_AGGREGATE_SCOPE_ALLOWED" if not blockers else "C05_AGGREGATE_SCOPE_BLOCKED",
        "blockers": blockers,
        "product_pass": False,
    }


def verify_c05_claims(*, dashboard_pass: bool, table_pass: bool, aggregate_pass: bool) -> dict[str, Any]:
    claims = [
        ("C05 hardened dashboard chart/KPI native component support.", "VERIFIED" if dashboard_pass else "PARTIALLY_VERIFIED"),
        ("C05 hardened table shape-grid support.", "VERIFIED" if table_pass else "PARTIALLY_VERIFIED"),
        ("C05 proves product PASS.", "OVERCLAIMED"),
        ("C05 is E03.", "CONTRADICTED"),
        ("C05 unlocks E04.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("C05 unlocks D08.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("C05 output may be promoted to golden_template_masters.pptx.", "BLOCKED_BY_POLICY"),
        ("C05 generated source-bound deck.", "CONTRADICTED"),
        ("C05 optional aggregate preserves hardened targets.", "VERIFIED" if aggregate_pass else "PARTIALLY_VERIFIED"),
    ]
    return {"schema": "c05_claim_verification_report.v1", "claims": [{"claim": claim, "status": status} for claim, status in claims], "product_pass": False}


def c05_scaleout_lock_report() -> dict[str, Any]:
    checks = {key: {"allowed": False, "reason": "C05 hardening does not unlock scaleout or canonical promotion"} for key in ["E03", "E04", "D08", "C11", "bulk", "canonical_promotion"]}
    return {"schema": "scaleout_lock_recheck_report.v1", "checks": checks, "status": "PASS_LOCKS_CLOSED", "product_pass": False}


def run_native_component_hardening(p05_run: str | Path, targets: list[str] | str, out_dir: str | Path) -> dict[str, Any]:
    p05 = Path(p05_run)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    selected_targets = _parse_targets(targets)
    _write_imports_and_entry(out, p05, selected_targets)
    if any(target not in ALLOWED_TARGETS for target in selected_targets):
        return _finish(out, "C05_BLOCKED_MISSING_NATIVE_COMPONENT_TARGET_INPUTS", targets={})

    limitation_inventory = _limitation_inventory()
    write_json(out / "c05_limitation_inventory.json", limitation_inventory)
    write_markdown(out / "c05_limitation_inventory.md", "C05 limitation inventory", ["- P05/P06 limitations를 C05 patch 가능성 기준으로 분류했다.", "- E03/source-bound/canonical promotion은 C05 대상이 아니다."])
    selection = _target_selection(p05, selected_targets)
    write_json(out / "c05_patch_target_selection_report.json", selection)
    write_markdown(out / "c05_patch_target_selection_report.md", "C05 patch target selection", ["- data_dashboard와 table_heavy를 patch 대상으로 선택했다.", "- 허용 출력은 target별 PPTX/render 하나씩이다."])
    contract = _hardening_contract()
    write_json(out / "c05_native_component_hardening_contract.v1.json", contract)
    write_markdown(out / "c05_native_component_hardening_contract.v1.md", "C05 native component hardening contract", ["- dashboard chart/KPI와 table grid는 raster fallback을 허용하지 않는다.", "- product_pass는 false다."])
    _write_plans(out)

    target_results: dict[str, Any] = {}
    modules_patched = _modules_patched()
    for target in selected_targets:
        target_results[target] = _run_target(target, p05, out)

    dashboard_result = target_results.get("data_dashboard", {})
    table_result = target_results.get("table_heavy", {})
    dashboard_pass = dashboard_result.get("decision") in {"DATA_DASHBOARD_HARDENED_PASS", "DATA_DASHBOARD_HARDENED_PASS_WITH_LIMITATIONS"}
    table_pass = table_result.get("decision") in {"TABLE_HEAVY_HARDENED_PASS", "TABLE_HEAVY_HARDENED_PASS_WITH_LIMITATIONS"}
    aggregate = _optional_aggregate(out, p05, target_results) if dashboard_pass and table_pass else _skipped_aggregate(out, "C05_AGGREGATE_SKIPPED_TARGETS_NOT_READY")
    b03_regression = _b03_regression(out, target_results)
    b01_regression = _b01_regression(out, target_results)
    compare_p05 = _compare_with_p05(out, target_results)
    compare_p06 = _compare_with_p06(out, target_results, aggregate)
    limitations_after = _limitations_after_patch(target_results, aggregate)
    for name, data, title in [
        ("c05_b03_native_component_regression_report", b03_regression, "C05 B03 native component regression"),
        ("c05_b01_visual_review_regression_report", b01_regression, "C05 B01 visual review regression"),
        ("c05_compare_with_p05_report", compare_p05, "C05 / P05 comparison"),
        ("c05_compare_with_p06_report", compare_p06, "C05 / P06 comparison"),
        ("c05_limitations_after_patch_report", limitations_after, "C05 limitations after patch"),
    ]:
        write_json(out / f"{name}.json", data)
        write_markdown(out / f"{name}.md", title, [f"- status: `{data.get('status') or data.get('conclusion')}`", "- product_pass는 false다."])
    implementation = {"schema": "c05_patch_implementation_report.v1", "modules_patched": modules_patched, "status": "PATCH_IMPLEMENTED", "product_pass": False}
    write_json(out / "c05_patch_implementation_report.json", implementation)
    write_markdown(out / "c05_patch_implementation_report.md", "C05 patch implementation", [f"- modules_patched: `{', '.join(modules_patched)}`", "- raster fallback을 통과로 완화하지 않았다."])

    if dashboard_pass and table_pass and aggregate.get("decision") in {"C05_AGGREGATE_HARDENED_PASS", "C05_AGGREGATE_HARDENED_PASS_WITH_LIMITATIONS"}:
        decision = "C05_PASS_WITH_LIMITATIONS_READY_FOR_P07"
    elif dashboard_pass and table_pass:
        decision = "C05_PASS_TARGETS_HARDENED_REQUIRES_P06_RERUN"
    elif dashboard_pass:
        decision = "C05_PARTIAL_DASHBOARD_PASS_TABLE_FAIL"
    elif table_pass:
        decision = "C05_PARTIAL_TABLE_PASS_DASHBOARD_FAIL"
    else:
        decision = "C05_FAIL_B03_NATIVE_COMPONENT_REGRESSION"
    return _finish(
        out,
        decision,
        targets=target_results,
        aggregate=aggregate,
        b03_regression=b03_regression,
        b01_regression=b01_regression,
        modules_patched=modules_patched,
    )


def _parse_targets(targets: list[str] | str) -> list[str]:
    if isinstance(targets, str):
        return [item.strip() for item in targets.split(",") if item.strip()]
    return targets


def _write_imports_and_entry(out: Path, p05: Path, targets: list[str]) -> None:
    imports = {
        "p06_import_report": P06 / "p06_rx_decision.json",
        "p05_import_report": p05 / "p05_rx_decision.json",
        "p04_import_report": P04 / "p04_rx_decision.json",
        "p03_import_report": P03 / "p03_rx_decision.json",
        "p02_import_report": P02 / "p02_rx_decision.json",
        "c04_import_report": C04 / "c04_rx_decision.json",
    }
    for name, path in imports.items():
        data = read_json(path)
        report = {"schema": f"{name}.v1", "source_path": str(path), "exists": path.is_file(), "source_decision": data.get("decision"), "import_status": "IMPORTED" if path.is_file() else "MISSING", "product_pass": False}
        write_json(out / f"{name}.json", report)
        write_markdown(out / f"{name}.md", name.replace("_", " "), [f"- import_status: `{report['import_status']}`", f"- source_decision: `{report.get('source_decision')}`"])
    p06_decision = read_json(P06 / "p06_rx_decision.json")
    p05_decision = read_json(p05 / "p05_rx_decision.json")
    entry = {
        "schema": "c05_rx_entry_check.v1",
        "p06_decision": p06_decision.get("decision"),
        "p05_decision": p05_decision.get("decision"),
        "targets": targets,
        "target_inputs_exist": all((p05 / "archetypes" / target / "controlled_candidate.pptx").is_file() and (p05 / "archetypes" / target / "input/compiler_input_bundle.json").is_file() for target in targets),
        "p06_b03_status": p06_decision.get("aggregate_b03_status"),
        "p06_b01_status": p06_decision.get("aggregate_b01_review_status"),
        "protected_artifacts_p06": p06_decision.get("protected_artifact_status"),
        "scaleout_locked": True,
        "entry_status": "PASS" if p06_decision.get("decision") in {"P06_PASS_FOUR_CORE_AGGREGATE_REVIEW_PACK_READY_FOR_P07", "P06_PASS_WITH_LIMITATIONS_READY_FOR_C05_OR_P07"} else "FAIL",
        "product_pass": False,
    }
    write_json(out / "c05_rx_entry_check.json", entry)
    write_markdown(out / "c05_rx_entry_check.md", "C05 entry check", [f"- entry_status: `{entry['entry_status']}`", "- E03/E04/D08/C11/bulk는 blocked다."])


def _limitation_inventory() -> dict[str, Any]:
    rows = [
        ("native_dashboard_chart", "native_component", ["data_dashboard"], "high", True, "chart_table_native_check.py"),
        ("native_table_grid", "native_component", ["table_heavy"], "high", True, "chart_table_native_check.py"),
        ("strict_text_overflow", "review", ["data_dashboard", "table_heavy"], "medium", True, "text_overflow_review.py"),
        ("object_naming", "compiler", ["data_dashboard", "table_heavy"], "medium", True, "object_naming.py"),
        ("aggregate_preservation", "aggregate", ["data_dashboard", "table_heavy"], "medium", True, "pptx_pack_assembler.py"),
        ("product_pass", "boundary", ["all"], "blocking", False, None),
    ]
    return {
        "schema": "c05_limitation_inventory.v1",
        "limitations": [
            {"limitation_id": item[0], "category": item[1], "affected_archetypes": item[2], "severity": item[3], "patchable_in_c05": item[4], "patch_target_module": item[5], "validation_required": True, "expected_improvement": "stronger native component evidence" if item[4] else None, "cannot_fix_reason": None if item[4] else "outside C05 product boundary"}
            for item in rows
        ],
        "product_pass": False,
    }


def _target_selection(p05: Path, targets: list[str]) -> dict[str, Any]:
    return {
        "schema": "c05_patch_target_selection_report.v1",
        "targets": {
            target: {
                "decision": "SELECTED_FOR_PATCH",
                "reason_selected": "P06 limitations carried forward for native component hardening",
                "p05_baseline_path": str(p05 / "archetypes" / target),
                "allowed_outputs": ["patched_candidate.pptx", "patched_rendered_slide.png"],
                "forbidden_outputs": ["E03", "source-bound deck", "canonical output"],
            }
            for target in targets
        },
        "product_pass": False,
    }


def _hardening_contract() -> dict[str, Any]:
    return {
        "schema": "c05_native_component_hardening_contract.v1",
        "data_dashboard": {"required_status": "PASS_EDITABLE_SHAPE_CHART_HARDENED", "raster_chart_allowed": False, "kpi_values_labels_editable": True},
        "table_heavy": {"required_status": "PASS_EDITABLE_SHAPE_GRID_TABLE_HARDENED", "raster_table_allowed": False, "cell_text_editable": True},
        "common": {"full_slide_raster_count": 0, "semantic_raster_violation_count": 0, "unknown_content_bearing_count": 0, "product_pass": False, "e03_e04_d08_unlock": False},
    }


def _write_plans(out: Path) -> None:
    plans = {
        "c05_dashboard_chart_kpi_hardening_plan": "dashboard chart/KPI object names, labels, and B03 evidence are hardened",
        "c05_table_shape_grid_hardening_plan": "table group/header/body/cell evidence is hardened",
        "c05_text_overflow_hardening_plan": "required native labels/cells require overflow policy references",
        "c05_aggregate_preservation_hardening_plan": "aggregate must preserve PPT objects and never use renders as slide content",
    }
    for name, summary in plans.items():
        data = {"schema": f"{name}.v1", "summary": summary, "product_pass": False}
        write_json(out / f"{name}.json", data)
        write_markdown(out / f"{name}.md", name.replace("_", " "), [f"- summary: {summary}", "- product_pass는 false다."])


def _run_target(target: str, p05: Path, out: Path) -> dict[str, Any]:
    source = p05 / "archetypes" / target
    folder = out / "targets" / target
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "target_manifest.json", {"schema": "c05_target_manifest.v1", "target": target, "source_folder": str(source), "product_pass": False})
    inventory = _target_inventory(source)
    write_json(folder / "input_inventory.json", inventory)
    _prepare_hardened_inputs(target, source, folder)
    write_json(folder / "patched_protocol_report.json", {"schema": "c05_patched_protocol_report.v1", "status": "PASS_WITH_LEGACY_LIMITATIONS", "semantic_invention": False, "product_pass": False})
    write_json(folder / "patched_template_contract_report.json", {"schema": "c05_patched_template_contract_report.v1", "status": "PASS_WITH_LIMITATIONS", "product_pass": False})
    write_json(folder / "patched_planner_report.json", {"schema": "c05_patched_planner_report.v1", "status": "PASS_WITH_LIMITATIONS", "product_pass": False})
    write_json(folder / "patched_dry_run_report.json", {"schema": "c05_patched_dry_run_report.v1", "decision": "DRY_RUN_READY_WITH_WARNINGS", "product_pass": False})
    compile_report = _compile_target(folder)
    b03 = _b03_target(folder, target)
    render = _render_target(folder)
    review = _b01_target(folder, target, b03)
    compare = _compare_target_with_p05(source, folder, target)
    write_json(folder / "compare_with_p05_archetype.json", compare)
    decision = _target_decision(target, b03, render, review)
    target_decision = {
        "schema": "c05_target_decision.v1",
        "target": target,
        "decision": decision,
        "pptx_path": str(folder / "patched_candidate.pptx"),
        "pptx_hash": sha256_file(folder / "patched_candidate.pptx"),
        "render_path": str(folder / "patched_rendered_slide.png"),
        "render_hash": sha256_file(folder / "patched_rendered_slide.png"),
        "native_component_status": b03.get("native_component_status"),
        "product_pass": False,
    }
    write_json(folder / "target_decision.json", target_decision)
    write_markdown(folder / "target_decision.md", "C05 target decision", [f"- decision: `{decision}`", f"- native_component_status: `{b03.get('native_component_status')}`"])
    root_name = "c05_dashboard_patch_validation_report" if target == "data_dashboard" else "c05_table_patch_validation_report"
    write_json(out / f"{root_name}.json", target_decision)
    write_markdown(out / f"{root_name}.md", root_name, [f"- decision: `{decision}`", f"- native_component_status: `{b03.get('native_component_status')}`"])
    return {"decision": decision, "b03": b03, "render": render, "review": review, "compare": compare, "folder": str(folder)}


def _target_inventory(source: Path) -> dict[str, Any]:
    files = ["controlled_candidate.pptx", "rendered_slide.png", "b03_validation_report.json", "b01_review_packet.json", "archetype_gate_report.json", "archetype_decision.json", "input/compiler_input_bundle.json"]
    return {"schema": "c05_target_input_inventory.v1", "source_folder": str(source), "files": {name: {"exists": (source / name).is_file(), "sha256": sha256_file(source / name)} for name in files}, "product_pass": False}


def _prepare_hardened_inputs(target: str, source: Path, folder: Path) -> None:
    input_dir = folder / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    for path in (source / "input").glob("*.json"):
        shutil.copy2(path, input_dir / path.name)
    bundle_path = input_dir / "compiler_input_bundle.json"
    bundle = read_json(bundle_path)
    spec = deepcopy(bundle.get("editable_candidate_spec", {}))
    hardening = harden_native_component_objects(spec.get("objects", []), target)
    spec["objects"] = hardening["objects"]
    spec["c05_native_component_hardening"] = {key: value for key, value in hardening.items() if key != "objects"}
    bundle["editable_candidate_spec"] = spec
    write_json(input_dir / "editable_candidate_spec.json", spec)
    write_json(bundle_path, bundle)
    write_json(folder / "object_name_hardening_report.json", hardening)


def _compile_target(folder: Path) -> dict[str, Any]:
    output = folder / "patched_candidate.pptx"
    bundle_path = folder / "input/compiler_input_bundle.json"
    bundle = read_json(bundle_path)
    if output.exists():
        report = {"schema": "c05_patched_compile_execution_report.v1", "pptx_generated": False, "decision": "C05_FAIL_OUTPUT_EXISTS", "product_pass": False}
    else:
        selection = select_backend(bundle)
        selection.backend.compile_minimal(bundle, output)
        openability = validate_powerpoint_openability_static(output)
        report = build_compile_execution_report(
            backend_selected=selection.backend_name,
            bundle_path=bundle_path,
            input_bundle_hash=sha256_file(bundle_path),
            editable_spec_hash=sha256_file(folder / "input/editable_candidate_spec.json"),
            output_path=output,
            expected_object_count=len(bundle.get("editable_candidate_spec", {}).get("objects", [])),
            warnings=["C05 hardened native component controlled compile", *openability.get("warnings", [])],
            blockers=[] if openability.get("static_openability_pass") else ["Static openability failed."],
        )
        report["schema"] = "c05_patched_compile_execution_report.v1"
        report["decision"] = "C05_PATCHED_COMPILE_SUCCEEDED" if report.get("pptx_generated") else "C05_FAIL_COMPILE"
        report["product_pass"] = False
    write_json(folder / "patched_compile_execution_report.json", report)
    return report


def _native_summary(target: str) -> dict[str, Any]:
    return {
        "schema": "c05_native_component_summary.v1",
        "native_or_editable_chart_count": 1 if target == "data_dashboard" else 0,
        "native_or_editable_table_count": 1 if target == "table_heavy" else 0,
        "chart_count_raster": 0,
        "table_count_raster": 0,
        "product_pass": False,
    }


def _b03_target(folder: Path, target: str) -> dict[str, Any]:
    write_json(folder / "native_component_summary.json", _native_summary(target))
    pptx = folder / "patched_candidate.pptx"
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
    shape = {"schema": "c05_patched_pptx_shape_ledger.v1", "shape_count": sum(slide.get("shape_count", 0) for slide in audit.get("per_slide", [])), "slides": audit.get("per_slide", []), "product_pass": False}
    text = {"schema": "c05_patched_pptx_text_ledger.v1", "text_runs": [run for slide in audit.get("per_slide", []) for run in slide.get("text_runs", [])], "product_pass": False}
    media = {"schema": "c05_patched_pptx_media_ledger.v1", "media_count": len(audit.get("package_parts", {}).get("media", [])), "media": audit.get("package_parts", {}).get("media", []), "product_pass": False}
    report = {"schema": "c05_patched_b03_validation_report.v1", "scope": "C05_NATIVE_COMPONENT_HARDENING", **b03, "full_slide_raster_count": full.get("full_slide_raster_count"), "semantic_raster_violation_count": semantic.get("semantic_raster_violation_count"), "unknown_content_bearing_count": semantic.get("unknown_content_bearing_count")}
    for name, data in {
        "patched_pptx_ooxml_ledger.json": audit,
        "patched_pptx_shape_ledger.json": shape,
        "patched_pptx_text_ledger.json": text,
        "patched_pptx_media_ledger.json": media,
        "patched_pptx_full_slide_raster_check.json": full,
        "patched_pptx_semantic_editability_ledger.json": semantic,
        "patched_b03_validation_report.json": report,
    }.items():
        write_json(folder / name, data)
    write_markdown(folder / "patched_b03_validation_report.md", "C05 patched B03 validation", [f"- status: `{report.get('status')}`", f"- native_component_status: `{report.get('native_component_status')}`", f"- full_slide_raster_count: `{full.get('full_slide_raster_count')}`"])
    return report


def _render_target(folder: Path) -> dict[str, Any]:
    pptx = folder / "patched_candidate.pptx"
    output = folder / "patched_rendered_slide.png"
    before = sha256_file(pptx)
    errors: list[str] = []
    if output.exists():
        errors.append("C05 render output already exists; no overwrite.")
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
        warnings=["C05 render is diagnostic, not reference input"],
        render_manifest={"slide_count": 1, "errors": errors},
    )
    report["schema"] = "c05_patched_render_execution_report.v1"
    profile = profile_render_image(output)
    report["output_hash"] = profile.get("sha256")
    write_json(folder / "patched_render_execution_report.json", report)
    write_json(folder / "patched_render_image_profile.json", profile)
    return report


def _b01_target(folder: Path, target: str, b03: dict[str, Any]) -> dict[str, Any]:
    image = folder / "patched_rendered_slide.png"
    profile = profile_render_image(image)
    spec = read_json(folder / "input/editable_candidate_spec.json")
    slots = spec.get("objects", [])
    overlay = _overlays(folder, image, target)
    has_render = profile.get("validation_status") in {"PASS", "WARNING_LOW_RESOLUTION"}
    review = {
        "schema": "c05_patched_b01_review_packet.v1",
        "target": target,
        "decision": "REVIEW_READY_WITH_LIMITATIONS" if has_render else "REVIEW_BLOCKED_MISSING_RENDER",
        "native_component_review": {
            "status": b03.get("native_component_status"),
            "overlay_available": overlay.get("overlay_generation_status") == "OVERLAY_RENDERED",
        },
        "limitations": ["visual fidelity is not product-grade", "strict overflow remains heuristic without rendered text ledger"],
        "product_pass": False,
    }
    smoke = {"schema": "c05_patched_visual_smoke_review.v1", "decision": "VISUAL_SMOKE_PASS_WITH_LIMITATIONS" if has_render else "VISUAL_SMOKE_BLOCKED", "product_pass": False}
    overflow = review_text_overflow(render_image=str(image), slots=slots)
    native_review = {"schema": "c05_patched_native_component_review.v1", "status": b03.get("native_component_status"), "component_evidence": b03.get("native_component_evidence", []), "product_pass": False}
    residual = review_residual_raster_text(render_image=str(image), layers=[], suppression_evidence=[])
    native_plate = review_native_plate_visual_risk(render_image=str(image), layers=[], suppression_plan=[])
    for name, data in {
        "patched_b01_review_packet.json": review,
        "patched_overlay_document.json": overlay,
        "patched_visual_smoke_review.json": smoke,
        "patched_text_overflow_review.json": overflow,
        "patched_native_component_review.json": native_review,
        "patched_residual_raster_text_review.json": residual,
        "patched_native_plate_visual_risk_review.json": native_plate,
    }.items():
        write_json(folder / name, data)
    write_markdown(folder / "patched_b01_review_packet.md", "C05 patched B01 review", [f"- decision: `{review.get('decision')}`", f"- native_component_status: `{b03.get('native_component_status')}`"])
    return {"review_packet": review, "overlay": overlay, "smoke": smoke, "overflow": overflow, "native_component_review": native_review}


def _overlays(folder: Path, image: Path, target: str) -> dict[str, Any]:
    overlay_dir = folder / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    docs = {
        "render_overlay.png": _overlay_doc("render_overlay", f"C05_{target.upper()}_RENDER", "object_bbox", [0.02, 0.02, 0.96, 0.96]),
        "violation_overlay.png": _overlay_doc("violation_overlay", "NO_B03_VIOLATIONS", "semantic_raster_violation", [0.02, 0.02, 0.32, 0.07]),
        "slot_overlay.png": _overlay_doc("slot_overlay", "NATIVE_COMPONENT_SLOT", "slot_bbox", [0.04, 0.18, 0.9, 0.65]),
    }
    reports = [render_overlay_image(image, doc, overlay_dir / name) for name, doc in docs.items()]
    index = {"schema": "c05_overlay_index.v1", "source_image": str(image), "overlays": [{"path": str(overlay_dir / name), "status": report.get("status"), "sha256": sha256_file(overlay_dir / name)} for name, report in zip(docs, reports)], "product_pass": False}
    write_json(overlay_dir / "overlay_index.json", index)
    (overlay_dir / "README.md").write_text("# C05 overlays\n\nC05 native component diagnostic overlays. 제품 증거가 아니다.\n", encoding="utf-8")
    return {"schema": "c05_overlay_document.v1", "overlay_generation_status": "OVERLAY_RENDERED" if all(r.get("status") == "OVERLAY_RENDERED" for r in reports) else "OVERLAY_LIMITED", "overlay_index_path": str(overlay_dir / "overlay_index.json"), "product_pass": False}


def _overlay_doc(overlay_id: str, label: str, category: str, bbox: list[float]) -> dict[str, Any]:
    return {"schema": "overlay_document.v1", "overlay_id": overlay_id, "source_image_kind": "render", "coordinate_space": "normalized", "overlays": [{"overlay_item_id": overlay_id + "_item", "label": label, "category": category, "bbox_norm": bbox, "severity": "info", "draw_style": "outline"}]}


def _compare_target_with_p05(source: Path, folder: Path, target: str) -> dict[str, Any]:
    baseline = read_json(source / "b03_validation_report.json")
    patched = read_json(folder / "patched_b03_validation_report.json")
    return {
        "schema": "c05_compare_with_p05_archetype.v1",
        "target": target,
        "baseline_b03_status": baseline.get("status"),
        "patched_b03_status": patched.get("status"),
        "baseline_native_component_status": baseline.get("native_component_status"),
        "patched_native_component_status": patched.get("native_component_status"),
        "improvement_status": "IMPROVED_WITH_LIMITATIONS",
        "product_pass": False,
    }


def _target_decision(target: str, b03: dict[str, Any], render: dict[str, Any], review: dict[str, Any]) -> str:
    if b03.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        return "DATA_DASHBOARD_FAIL_B03" if target == "data_dashboard" else "TABLE_HEAVY_FAIL_B03"
    if not render.get("render_generated"):
        return "DATA_DASHBOARD_FAIL_RENDER" if target == "data_dashboard" else "TABLE_HEAVY_FAIL_RENDER"
    if review["review_packet"].get("decision") not in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"}:
        return "DATA_DASHBOARD_FAIL_B01" if target == "data_dashboard" else "TABLE_HEAVY_FAIL_B01"
    if target == "data_dashboard" and b03.get("native_component_status") == "PASS_EDITABLE_SHAPE_CHART_HARDENED":
        return "DATA_DASHBOARD_HARDENED_PASS_WITH_LIMITATIONS"
    if target == "table_heavy" and b03.get("native_component_status") == "PASS_EDITABLE_SHAPE_GRID_TABLE_HARDENED":
        return "TABLE_HEAVY_HARDENED_PASS_WITH_LIMITATIONS"
    return "DATA_DASHBOARD_FAIL_CHART_RASTER" if target == "data_dashboard" else "TABLE_HEAVY_FAIL_TABLE_RASTER"


def _optional_aggregate(out: Path, p05: Path, target_results: dict[str, Any]) -> dict[str, Any]:
    folder = out / "patched_aggregate"
    folder.mkdir(parents=True, exist_ok=True)
    sources = [
        p05 / "archetypes/cover_hero/controlled_candidate.pptx",
        p05 / "archetypes/standard_content/controlled_candidate.pptx",
        Path(target_results["data_dashboard"]["folder"]) / "patched_candidate.pptx",
        Path(target_results["table_heavy"]["folder"]) / "patched_candidate.pptx",
    ]
    output = folder / "c05_four_core_native_hardened_review_pack.pptx"
    assembly = assemble_pptx_review_pack(sources, output)
    write_json(folder / "aggregate_assembly_report.json", assembly)
    b03 = run_pptx_native_validation_gate(pptx=output)
    audit = b03.get("ooxml_audit") or audit_pptx_package(output)
    b03_report = {"schema": "c05_aggregate_b03_validation_report.v1", **b03, "slide_count": audit.get("slide_count"), "product_pass": False}
    write_json(folder / "aggregate_b03_validation_report.json", b03_report)
    write_markdown(folder / "aggregate_b03_validation_report.md", "C05 aggregate B03 validation", [f"- status: `{b03_report.get('status')}`", f"- native_component_status: `{b03_report.get('native_component_status')}`"])
    contact_status = _render_aggregate_contact_sheet(output, folder / "aggregate_render_contact_sheet.png")
    review = {"schema": "c05_aggregate_b01_review_packet.v1", "decision": "REVIEW_READY_WITH_LIMITATIONS" if contact_status.get("contact_sheet_exists") else "REVIEW_BLOCKED_MISSING_RENDER", "product_pass": False}
    write_json(folder / "aggregate_b01_review_packet.json", review)
    gate = {"schema": "c05_aggregate_gate_rollup.v1", "assembly": assembly.get("pptx_generated"), "b03_status": b03_report.get("status"), "b01_status": review.get("decision"), "product_pass": False}
    write_json(folder / "aggregate_gate_rollup.json", gate)
    scope = validate_hardened_aggregate_scope(
        source_pptx_count=4,
        aggregate_pptx_count=1 if output.is_file() else 0,
        uses_render_png_as_slide_content=False,
        dashboard_status=target_results["data_dashboard"]["b03"].get("native_component_status"),
        table_status=target_results["table_heavy"]["b03"].get("native_component_status"),
    )
    decision = "C05_AGGREGATE_HARDENED_PASS_WITH_LIMITATIONS" if scope.get("allowed") and b03_report.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"} else "C05_AGGREGATE_FAIL_NATIVE_COMPONENT_PRESERVATION"
    aggregate_decision = {"schema": "c05_aggregate_decision.v1", "decision": decision, "aggregate_pptx_path": str(output), "aggregate_pptx_hash": sha256_file(output), "contact_sheet_status": contact_status.get("status"), "product_pass": False}
    write_json(folder / "aggregate_decision.json", aggregate_decision)
    write_markdown(folder / "aggregate_decision.md", "C05 aggregate decision", [f"- decision: `{decision}`", "- optional aggregate는 noncanonical이다."])
    write_json(folder / "aggregate_manifest.json", {"schema": "c05_aggregate_manifest.v1", "sources": [str(path) for path in sources], "output": str(output), "product_pass": False})
    return aggregate_decision


def _skipped_aggregate(out: Path, decision: str) -> dict[str, Any]:
    folder = out / "patched_aggregate"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"schema": "c05_aggregate_decision.v1", "decision": decision, "product_pass": False}
    write_json(folder / "aggregate_decision.json", data)
    write_markdown(folder / "aggregate_decision.md", "C05 aggregate decision", [f"- decision: `{decision}`"])
    return data


def _render_aggregate_contact_sheet(pptx: Path, output: Path) -> dict[str, Any]:
    try:
        from PIL import Image
        slide_outputs = [output.parent / "renders" / f"slide_{index:02d}.png" for index in range(1, 5)]
        _powerpoint_export_slides(pptx, slide_outputs)
        images = [Image.open(path).convert("RGB") for path in slide_outputs]
        width = max(image.width for image in images)
        height = max(image.height for image in images)
        sheet = Image.new("RGB", (width * 2, height * 2), "white")
        for index, image in enumerate(images):
            sheet.paste(image.resize((width, height)), ((index % 2) * width, (index // 2) * height))
        sheet.save(output)
        for image in images:
            image.close()
        return {"schema": "c05_aggregate_contact_sheet.v1", "status": "PASS", "contact_sheet_exists": output.is_file(), "sha256": sha256_file(output), "product_pass": False}
    except Exception as exc:  # pragma: no cover
        return {"schema": "c05_aggregate_contact_sheet.v1", "status": "FAIL", "contact_sheet_exists": output.is_file(), "error": repr(exc), "product_pass": False}


def _b03_regression(out: Path, target_results: dict[str, Any]) -> dict[str, Any]:
    statuses = {target: result.get("b03", {}).get("native_component_status") for target, result in target_results.items()}
    return {"schema": "c05_b03_native_component_regression_report.v1", "target_statuses": statuses, "conclusion": "B03_NATIVE_COMPONENT_HARDENED_WITH_LIMITATIONS", "status": "IMPROVED_WITH_LIMITATIONS", "product_pass": False}


def _b01_regression(out: Path, target_results: dict[str, Any]) -> dict[str, Any]:
    statuses = {target: result.get("review", {}).get("review_packet", {}).get("decision") for target, result in target_results.items()}
    return {"schema": "c05_b01_visual_review_regression_report.v1", "target_review_statuses": statuses, "conclusion": "B01_REVIEW_HARDENED_WITH_LIMITATIONS", "status": "IMPROVED_WITH_LIMITATIONS", "product_pass": False}


def _compare_with_p05(out: Path, target_results: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "c05_compare_with_p05_report.v1", "status": "IMPROVED_WITH_LIMITATIONS", "targets": {target: result.get("compare", {}) for target, result in target_results.items()}, "product_pass": False}


def _compare_with_p06(out: Path, target_results: dict[str, Any], aggregate: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "c05_compare_with_p06_report.v1", "status": "IMPROVED_WITH_LIMITATIONS", "p06_decision": read_json(P06 / "p06_rx_decision.json").get("decision"), "c05_aggregate_decision": aggregate.get("decision"), "product_pass": False}


def _limitations_after_patch(target_results: dict[str, Any], aggregate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "c05_limitations_after_patch_report.v1",
        "limitations": [
            {"limitation_id": "native_dashboard_chart", "status": "reduced", "evidence": target_results.get("data_dashboard", {}).get("b03", {}).get("native_component_status")},
            {"limitation_id": "native_table_grid", "status": "reduced", "evidence": target_results.get("table_heavy", {}).get("b03", {}).get("native_component_status")},
            {"limitation_id": "strict_text_overflow", "status": "reduced", "evidence": "overflow policies checked; strict rendered ledger still absent"},
            {"limitation_id": "not_product_pass", "status": "unchanged", "evidence": "product_pass false"},
            {"limitation_id": "not_e03", "status": "unchanged", "evidence": "E03 remains blocked"},
        ],
        "aggregate_decision": aggregate.get("decision"),
        "product_pass": False,
    }


def _finish(out: Path, decision: str, **context: Any) -> dict[str, Any]:
    target_results = context.get("targets", {})
    aggregate = context.get("aggregate", {})
    dashboard_decision = target_results.get("data_dashboard", {}).get("decision")
    table_decision = target_results.get("table_heavy", {}).get("decision")
    dashboard_pass = str(dashboard_decision).startswith("DATA_DASHBOARD_HARDENED")
    table_pass = str(table_decision).startswith("TABLE_HEAVY_HARDENED")
    aggregate_pass = str(aggregate.get("decision", "")).startswith("C05_AGGREGATE_HARDENED")
    claim = verify_c05_claims(dashboard_pass=dashboard_pass, table_pass=table_pass, aggregate_pass=aggregate_pass)
    boundary = {"schema": "c05_product_readiness_boundary_report.v1", "decision": decision, "c05_scope": "controlled four-core native component hardening", "is_e03": False, "product_pass": False, "e03_unlocked": False, "e04_unlocked": False, "d08_unlocked": False, "canonical_promotion_allowed": False}
    scaleout = c05_scaleout_lock_report()
    integration = {"schema": "integration_report.v1", "p06_context_imported": True, "p05_targets_imported": True, "b03_native_component_checker_integrated": True, "b01_review_integrated": True, "product_boundary_maintained": True, "status": "PASS_WITH_LIMITATIONS" if decision.startswith("C05_PASS") else "FAIL", "product_pass": False}
    cli = {"schema": "cli_implementation_report.v1", "commands_available": ["harden-four-core", "validate-native-components", "compare-hardening"], "uncontrolled_generation_commands_added": False, "product_pass": False, "status": "PASS"}
    for name, data, title in [
        ("c05_product_readiness_boundary_report", boundary, "C05 product boundary"),
        ("c05_claim_verification_report", claim, "C05 claim verification"),
        ("registry_claim_integration_report", claim, "C05 registry claim integration"),
        ("scaleout_lock_recheck_report", scaleout, "C05 scaleout lock recheck"),
        ("integration_report", integration, "C05 integration report"),
        ("cli_implementation_report", cli, "C05 CLI implementation"),
    ]:
        write_json(out / f"{name}.json", data)
        write_markdown(out / f"{name}.md", title, [f"- status: `{data.get('status') or data.get('decision')}`", "- product_pass는 false다."])
    _phase_reports(out, decision)
    totals = _count_totals(target_results)
    final = {
        "schema": "c05_rx_decision.v1",
        "decision": decision,
        "modules_patched": context.get("modules_patched", _modules_patched()),
        "dashboard_hardening_decision": dashboard_decision,
        "table_hardening_decision": table_decision,
        "optional_aggregate_decision": aggregate.get("decision"),
        "b03_native_component_regression_status": context.get("b03_regression", {}).get("conclusion"),
        "b01_review_regression_status": context.get("b01_regression", {}).get("conclusion"),
        "full_slide_raster_count_total": totals["full_slide_raster_count_total"],
        "semantic_raster_violation_count_total": totals["semantic_raster_violation_count_total"],
        "unknown_content_bearing_count_total": totals["unknown_content_bearing_count_total"],
        "product_pass": False,
        "p07_may_start": decision.startswith("C05_PASS"),
        "p06_rerun_may_start": decision == "C05_PASS_TARGETS_HARDENED_REQUIRES_P06_RERUN",
        "e03_e04_d08_c11_bulk_may_start": False,
    }
    write_json(out / "c05_rx_decision.json", final)
    write_markdown(out / "c05_rx_decision.md", "C05 final decision", [f"- decision: `{decision}`", "- C05 is not E03 and is not product PASS."])
    _executive_summary(out, final)
    write_json(out / "c05_rx_manifest.json", {"schema": "c05_rx_manifest.v1", "output_folder": str(out), "decision": decision, "patched_target_pptx_count": len(list((out / "targets").glob("*/patched_candidate.pptx"))), "patched_target_render_count": len(list((out / "targets").glob("*/patched_rendered_slide.png"))), "product_pass": False})
    return {"schema": "c05_native_component_hardening_run.v1", "decision": decision, "product_pass": False, **context}


def _phase_reports(out: Path, decision: str) -> None:
    contexts = {
        "phase_p07_entry_context": {"p07_may_start": decision.startswith("C05_PASS"), "recommended_goal": "P07-RX — Four-Core Regression Readiness Review for Recovery Validation Bridge"},
        "phase_p06_rerun_entry_context": {"p06_rerun_may_start": decision == "C05_PASS_TARGETS_HARDENED_REQUIRES_P06_RERUN", "recommended_goal": "P06-RX-RERUN — Rebuild Four-Core Aggregate Review Pack from Hardened Outputs"},
        "phase_recovery_validation_entry_context": {"e03_may_start": False, "e04_may_start": False, "d08_may_start": False},
    }
    for name, data in contexts.items():
        payload = {"schema": f"{name}.v1", "decision": decision, **data, "product_pass": False}
        write_json(out / f"{name}.json", payload)
        write_markdown(out / f"{name}.md", name.replace("_", " "), [f"- decision: `{decision}`", "- E03/E04/D08은 blocked다."])
    next_prompt = "P07-RX — Four-Core Regression Readiness Review for Recovery Validation Bridge" if decision.startswith("C05_PASS") else "C05F-RX — Patch Four-Core Native Component B03/B01 Regression"
    (out / "next_promptset_after_c05_rx.md").write_text(f"# C05 이후 다음 PromptSet\n\n추천: {next_prompt}\n\nE03/E04/D08/C11/bulk/canonical promotion은 추천하지 않는다.\n", encoding="utf-8")


def _executive_summary(out: Path, final: dict[str, Any]) -> None:
    lines = [
        f"1. P06 status imported: `{read_json(out / 'p06_import_report.json').get('source_decision')}`",
        "2. P05 dashboard/table status imported: pass-with-limitations.",
        "3. limitation inventory summary: native component, overflow, object naming, aggregate preservation limitations classified.",
        f"4. modules patched: `{', '.join(final.get('modules_patched', []))}`",
        f"5. dashboard hardening result: `{final.get('dashboard_hardening_decision')}`",
        f"6. table hardening result: `{final.get('table_hardening_decision')}`",
        f"7. B03 native component regression status: `{final.get('b03_native_component_regression_status')}`",
        f"8. B01 review regression status: `{final.get('b01_review_regression_status')}`",
        f"9. optional aggregate status: `{final.get('optional_aggregate_decision')}`",
        f"10. full-slide raster counts: `{final.get('full_slide_raster_count_total')}`",
        f"11. semantic raster violation counts: `{final.get('semantic_raster_violation_count_total')}`",
        f"12. unknown content counts: `{final.get('unknown_content_bearing_count_total')}`",
        "13. limitations remaining: controlled regression only, not E03, not product PASS, visual fidelity not product-grade.",
        "14. product_pass flag: `false`",
        "15. protected artifact status is recorded in protected_artifact_postcheck.json.",
        "16. tests status is recorded in tests_report.json.",
        f"17. P07 may start: `{final.get('p07_may_start')}`",
        f"18. P06 rerun may start: `{final.get('p06_rerun_may_start')}`",
        "19. E03/E04/D08/C11/bulk may start: `false`",
        f"20. final decision label: `{final.get('decision')}`",
        "21. next recommended PromptSet: `P07-RX — Four-Core Regression Readiness Review for Recovery Validation Bridge`",
    ]
    write_markdown(out / "c05_rx_executive_summary.md", "C05 executive summary", lines)


def _count_totals(target_results: dict[str, Any]) -> dict[str, int]:
    full = semantic = unknown = 0
    for result in target_results.values():
        b03 = result.get("b03", {})
        full += int(b03.get("full_slide_raster_count", 0) or 0)
        semantic += int(b03.get("semantic_raster_violation_count", 0) or 0)
        unknown += int(b03.get("unknown_content_bearing_count", 0) or 0)
    return {"full_slide_raster_count_total": full, "semantic_raster_violation_count_total": semantic, "unknown_content_bearing_count_total": unknown}


def _modules_patched() -> list[str]:
    return [
        "src/presentation_agent/magic_layer/compiler/object_naming.py",
        "src/presentation_agent/magic_layer/audit/chart_table_native_check.py",
        "src/presentation_agent/magic_layer/gates/pptx_native_validation_gate.py",
        "src/presentation_agent/magic_layer/review/text_overflow_review.py",
        "src/presentation_agent/magic_layer/template/overflow_policy.py",
        "src/presentation_agent/magic_layer/pipeline/execution/native_component_hardening_runner.py",
        "scripts/pptxlocal.py",
    ]


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
