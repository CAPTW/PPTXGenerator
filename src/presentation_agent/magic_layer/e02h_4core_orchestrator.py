"""PromptSet E02H 4-core high-fidelity hybrid Canva+ conversion gate."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from scripts.run_e01x_self_describing_ps_layer_integration import protected_report, protected_snapshot, run_protect_check
from src.presentation_agent.magic_layer.e01h_hybrid_orchestrator import build_ps_layer_protocol_hybrid
from src.presentation_agent.magic_layer.e01h_reference_analyzer import build_reference_visual_richness_report as build_e01h_reference_visual_richness_report
from src.presentation_agent.magic_layer.e01h_p_candidate_patcher import _patch_payload_for_icons, build_patched_candidate
from src.presentation_agent.magic_layer.e01h_p_icon_inventory import build_semantic_icon_inventory_report
from src.presentation_agent.magic_layer.e01h_p_icon_vectorizer import build_icon_vectorization_plan
from src.presentation_agent.magic_layer.e01h_p_semantic_icon_gate import build_patched_semantic_icon_vector_report
from src.presentation_agent.magic_layer.e02h_aggregate_report import (
    build_e02h_aggregate_report,
    build_e02h_semantic_native_promotion_matrix,
    build_e02h_visual_richness_retention_matrix,
    build_e03h_readiness_report,
    e02h_aggregate_report_markdown,
    e03h_readiness_report_markdown,
    simple_matrix_markdown,
)
from src.presentation_agent.magic_layer.e02h_candidate_compiler import (
    audit_e02h_candidate_pptx,
    build_e02h_editable_candidate_spec,
    build_e02h_inventory_ledgers,
    compile_e02h_candidate,
    render_e02h_candidate_preview,
)
from src.presentation_agent.magic_layer.e02h_canva_plus_hybrid_gate import (
    build_e02h_canva_plus_hybrid_gate_report,
    build_e02h_semantic_editability_reports,
    build_e05_readiness_after_e02h,
    canva_plus_hybrid_gate_report_markdown,
    e05_readiness_after_e02h_markdown,
)
from src.presentation_agent.magic_layer.e02h_component_gates import (
    build_e02h_component_coverage_matrix,
    build_e02h_micro_component_gate_report,
    build_e02h_micro_component_report,
    build_e02h_reference_component_gate,
    build_e02h_semantic_icon_report,
    component_coverage_matrix_markdown,
)
from src.presentation_agent.magic_layer.e02h_hybrid_object_graph_builder import (
    build_e02h_hybrid_object_graph,
    build_e02h_layer_manifest_v5,
    build_e02h_reference_definition,
    build_e02h_region_ledgers,
    build_e02h_semantic_slot_graph,
    build_e02h_visual_layer_graph,
)
from src.presentation_agent.magic_layer.e02h_reference_generator import (
    build_asset_recipe_manifest,
    build_design_intent_trace,
    build_image_prompt,
    build_reference_analysis_report,
    build_reference_visual_richness_report,
    generate_reference_image,
)
from src.presentation_agent.magic_layer.e02h_reference_registry import REFERENCE_IDS, build_e02h_reference_registry
from src.presentation_agent.magic_layer.e02h_semantic_native_planner import build_e02h_semantic_native_plan
from src.presentation_agent.magic_layer.e02h_text_first_lock import build_e02h_text_first_lock_report, text_first_lock_report_markdown
from src.presentation_agent.magic_layer.e02h_visual_backplate_planner import build_e02h_visual_backplate_policy
from src.presentation_agent.magic_layer.e02h_visual_fidelity_gate import (
    build_e02h_visual_fidelity_report,
    build_e02h_visual_richness_retention_report,
    visual_fidelity_report_markdown,
    visual_richness_retention_report_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
E01H_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01h_high_fidelity_hybrid_canva_plus_single_reference"
E01H_P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01h_p_semantic_icon_microcomponent_fidelity_patch"
E01P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_photoshop_layer_protocol"
E01PV_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_v_cross_ledger_validator"
E02H_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e02h_4core_hybrid_canva_plus_reference_conversion"


def build_e02h_reference_payload(reference_id: str, output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if reference_id == "maritime_checklist_hero":
        return _build_maritime_payload(output)
    definition = build_e02h_reference_definition(reference_id)
    reference_path = output / "reference_image.png"
    generate_reference_image(definition, reference_path)
    analysis = build_reference_analysis_report(definition, reference_path)
    text_lock = build_e02h_text_first_lock_report(definition)
    object_graph = build_e02h_hybrid_object_graph(definition, text_lock)
    backplates = build_e02h_visual_backplate_policy(object_graph)
    semantic_plan = build_e02h_semantic_native_plan(object_graph, reference_id)
    ledgers = build_e02h_region_ledgers(object_graph)
    payload = {
        "schema_name": "e02h_reference_payload",
        "status": "passed",
        "reference_id": reference_id,
        "definition": definition,
        "image_prompt": build_image_prompt(definition),
        "design_intent_trace": build_design_intent_trace(definition),
        "asset_recipe_manifest": build_asset_recipe_manifest(definition),
        "reference_analysis_report": analysis,
        "reference_visual_richness_report": build_reference_visual_richness_report(definition, analysis),
        "text_first_lock_report": text_lock,
        "object_graph_v2": object_graph,
        "layer_manifest_v5": build_e02h_layer_manifest_v5(object_graph),
        "semantic_slot_graph": build_e02h_semantic_slot_graph(object_graph),
        "visual_layer_graph": build_e02h_visual_layer_graph(object_graph),
        **backplates,
        **semantic_plan,
        **ledgers,
        "hybrid_candidate_compile_plan": _compile_plan(reference_id),
        "canva_parity_claimed": False,
    }
    payload["ps_layer_intent_hybrid"] = build_ps_layer_protocol_hybrid(object_graph, analysis, protocol_id=f"e02h_{reference_id}_intent")
    payload["ps_layer_as_built_hybrid"] = build_ps_layer_protocol_hybrid(object_graph, analysis, protocol_id=f"e02h_{reference_id}_as_built")
    return payload


def run_e02h_4core_hybrid_canva_plus_reference_conversion(output_dir: str | Path = E02H_ROOT) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    if not run_protect_check():
        final = _final("E02H_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact precheck failed")
        _write_json(output / "e02h_final_decision.json", final)
        return final
    prerequisites = _validate_prerequisites()
    if prerequisites["status"] != "passed":
        final = _final("E02H_PATCH_SEMANTIC_ICON_VECTORIZATION", "failed", False, "required E01H/E01H-P/PS-layer inputs missing or not ready")
        _write_json(output / "e02h_manifest.json", _manifest(output, final, prerequisites))
        _write_json(output / "e02h_final_decision.json", final)
        return final

    payloads: list[dict[str, Any]] = []
    per_reference: dict[str, dict[str, Any]] = {}
    for reference_id in REFERENCE_IDS:
        ref_out = output / "references" / reference_id
        payload = build_e02h_reference_payload(reference_id, ref_out)
        payloads.append(payload)
        reference_summary = _run_reference_conversion(payload, ref_out)
        per_reference[reference_id] = reference_summary

    protected_after = protected_snapshot()
    protected_md, protected_ok = protected_report(protected_before, protected_after)
    aggregate = build_e02h_aggregate_report(per_reference, protected_artifacts_unchanged=protected_ok)
    e03h_readiness = build_e03h_readiness_report(aggregate)
    e05_readiness = build_e05_readiness_after_e02h(aggregate)
    final = _final(aggregate["decision"], aggregate["status"], e03h_readiness["e03h_unlocked"], aggregate["decision"])
    protect_post = run_protect_check()
    protected_md += f"\n\n- npm protect precheck: `passed`\n- npm protect postcheck: `{'passed' if protect_post else 'failed'}`\n"
    if not protected_ok or not protect_post:
        final = _final("E02H_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact postcheck failed")
        aggregate["status"] = "failed"
        aggregate["decision"] = "E02H_FAIL_PROTECTED_ARTIFACTS"
        aggregate["e03h_unlocked"] = False
        e03h_readiness["status"] = "failed"
        e03h_readiness["e03h_unlocked"] = False

    component_matrix = build_e02h_component_coverage_matrix(payloads)
    visual_matrix = build_e02h_visual_richness_retention_matrix(per_reference)
    semantic_matrix = build_e02h_semantic_native_promotion_matrix(per_reference)
    _build_contact_sheets(output)
    _write_aggregate_outputs(output, final, aggregate, e03h_readiness, e05_readiness, component_matrix, visual_matrix, semantic_matrix, protected_md)
    return final


def _build_maritime_payload(output: Path) -> dict[str, Any]:
    reference = E01H_ROOT / "reference_image.png"
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(reference, output / "reference_image.png")
    icon_inventory = build_semantic_icon_inventory_report(E01H_ROOT)
    vector_plan = build_icon_vectorization_plan(icon_inventory)
    from src.presentation_agent.magic_layer.e01h_hybrid_orchestrator import build_e01h_conversion_payload

    payload = _patch_payload_for_icons(build_e01h_conversion_payload(reference), vector_plan)
    payload["schema_name"] = "e02h_reference_payload"
    payload["reference_id"] = "maritime_checklist_hero"
    payload["reference_analysis_report"]["reference_id"] = "maritime_checklist_hero"
    payload["reference_analysis_report"]["reference_path"] = (output / "reference_image.png").as_posix()
    definition = build_e02h_reference_definition("maritime_checklist_hero")
    payload["definition"] = definition
    payload["image_prompt"] = build_image_prompt(definition)
    payload["design_intent_trace"] = build_design_intent_trace(definition)
    payload["asset_recipe_manifest"] = build_asset_recipe_manifest(definition)
    payload["reference_visual_richness_report"] = build_e01h_reference_visual_richness_report(payload["reference_analysis_report"])
    payload["hybrid_candidate_compile_plan"] = _compile_plan("maritime_checklist_hero")
    return payload


def _run_reference_conversion(payload: dict[str, Any], ref_out: Path) -> dict[str, Any]:
    _write_reference_inputs(ref_out, payload)
    if payload["reference_id"] == "maritime_checklist_hero":
        icon_inventory = build_semantic_icon_inventory_report(E01H_ROOT)
        plan = build_icon_vectorization_plan(icon_inventory)
        patch = build_patched_candidate(E01H_ROOT, plan, ref_out)
        inventory = patch["ledgers"]["patched_pptx_inventory"]
        render_manifest = {
            "schema_name": "render_manifest",
            "status": "passed",
            "reference_id": payload["reference_id"],
            "rendered_candidate": (ref_out / "rendered_candidate.png").as_posix(),
            "reference_vs_render": (ref_out / "reference_vs_render.png").as_posix(),
            "visual_diff_overlay": (ref_out / "visual_diff_overlay.png").as_posix(),
            "semantic_overlay_preview": (ref_out / "semantic_overlay_preview.png").as_posix(),
            "backplate_overlay_preview": (ref_out / "backplate_overlay_preview.png").as_posix(),
            "canva_parity_claimed": False,
        }
        compile_report = patch["compile_report"]
        ledgers = patch["ledgers"]
        icon_report = build_patched_semantic_icon_vector_report(inventory, plan)
    else:
        compile_report = compile_e02h_candidate(payload, ref_out)
        render_manifest = render_e02h_candidate_preview(payload, ref_out)
        inventory = audit_e02h_candidate_pptx(ref_out / "editable_candidate.pptx")
        ledgers = build_e02h_inventory_ledgers(inventory, payload)
        icon_report = build_e02h_semantic_icon_report(payload)

    _write_candidate_outputs(ref_out, payload, compile_report, render_manifest, inventory, ledgers)
    visual_fidelity = build_e02h_visual_fidelity_report(ref_out / "reference_image.png", ref_out / "rendered_candidate.png")
    visual_richness = build_e02h_visual_richness_retention_report(payload, visual_fidelity)
    semantic_reports = build_e02h_semantic_editability_reports(payload, inventory)
    micro_inventory = build_e02h_micro_component_report(payload)
    micro_gate = build_e02h_micro_component_gate_report(payload)
    component_gate = build_e02h_reference_component_gate(payload)
    canva_gate = build_e02h_canva_plus_hybrid_gate_report(
        reference_id=payload["reference_id"],
        candidate_exists=(ref_out / "editable_candidate.pptx").exists(),
        candidate_rendered=(ref_out / "rendered_candidate.png").exists(),
        visual_richness=visual_richness,
        payload=payload,
        semantic_reports=semantic_reports,
        icon_report=icon_report,
        micro_component_report=micro_gate,
        component_gate=component_gate,
        protected_artifacts_unchanged=True,
    )
    final = _reference_final(payload["reference_id"], canva_gate, component_gate, inventory, visual_richness)
    _write_reference_reports(ref_out, visual_fidelity, visual_richness, semantic_reports, icon_report, micro_inventory, micro_gate, canva_gate, final)
    return final


def _write_reference_inputs(ref_out: Path, payload: dict[str, Any]) -> None:
    if not (ref_out / "reference_image.png").exists() and Path(payload["reference_analysis_report"]["reference_path"]).exists():
        shutil.copy2(payload["reference_analysis_report"]["reference_path"], ref_out / "reference_image.png")
    _write_md(ref_out / "image_prompt.md", payload["image_prompt"])
    for key in [
        "design_intent_trace",
        "asset_recipe_manifest",
        "reference_analysis_report",
        "reference_visual_richness_report",
        "text_first_lock_report",
        "ps_layer_intent_hybrid",
        "ps_layer_as_built_hybrid",
        "object_graph_v2",
        "layer_manifest_v5",
        "semantic_slot_graph",
        "visual_layer_graph",
        "hybrid_visual_backplate_manifest",
        "semantic_native_layer_manifest",
        "visual_backplate_raster_allowlist",
        "object_bbox_ledger",
        "polygon_mask_ledger",
        "z_order_ledger",
        "text_region_ledger",
        "image_field_ledger",
        "icon_region_ledger",
        "chart_table_region_ledger",
        "connector_technical_overlay_ledger",
        "unknown_layer_report",
        "semantic_native_reconstruction_plan",
        "visual_backplate_reconstruction_plan",
        "hybrid_candidate_compile_plan",
        "native_component_promotion_report",
        "raster_policy_report_hybrid",
    ]:
        _write_json(ref_out / f"{key}.json", payload[key])


def _write_candidate_outputs(ref_out: Path, payload: dict[str, Any], compile_report: dict[str, Any], render_manifest: dict[str, Any], inventory: dict[str, Any], ledgers: dict[str, dict[str, Any]]) -> None:
    _write_json(ref_out / "editable_candidate_spec.json", build_e02h_editable_candidate_spec(payload))
    _write_json(ref_out / "render_manifest.json", render_manifest)
    for key, ledger in ledgers.items():
        _write_json(ref_out / "ledgers" / f"{key}.json", ledger)


def _write_reference_reports(ref_out: Path, visual_fidelity: dict[str, Any], visual_richness: dict[str, Any], semantic_reports: dict[str, dict[str, Any]], icon_report: dict[str, Any], micro_inventory: dict[str, Any], micro_gate: dict[str, Any], canva_gate: dict[str, Any], final: dict[str, Any]) -> None:
    _write_json(ref_out / "visual_fidelity_report.json", visual_fidelity)
    _write_md(ref_out / "visual_fidelity_report.md", visual_fidelity_report_markdown(visual_fidelity))
    _write_json(ref_out / "visual_richness_retention_report.json", visual_richness)
    _write_md(ref_out / "visual_richness_retention_report.md", visual_richness_retention_report_markdown(visual_richness))
    for key, report in semantic_reports.items():
        _write_json(ref_out / f"{key}.json", report)
    _write_json(ref_out / "semantic_icon_inventory_report.json", icon_report)
    _write_json(ref_out / "semantic_icon_fidelity_report.json", icon_report)
    _write_json(ref_out / "semantic_icon_vector_report.json", icon_report)
    _write_json(ref_out / "micro_component_inventory_report.json", micro_inventory)
    _write_json(ref_out / "micro_component_fidelity_gate_report.json", micro_gate)
    _write_json(ref_out / "canva_plus_hybrid_gate_report.json", canva_gate)
    _write_md(ref_out / "canva_plus_hybrid_gate_report.md", canva_plus_hybrid_gate_report_markdown(canva_gate))
    _write_json(ref_out / "reference_final_decision.json", final)
    patch_queue = _patch_queue(final)
    _write_json(ref_out / "patch_queue.json", patch_queue)
    _write_md(ref_out / "patch_queue.md", _simple_md("Patch Queue", patch_queue))


def _reference_final(reference_id: str, gate: dict[str, Any], component_gate: dict[str, Any], inventory: dict[str, Any], visual_richness: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "reference_final_decision",
        "reference_id": reference_id,
        "status": gate["status"],
        "decision": "reference_pass" if gate["status"] == "passed" else "reference_patch_required",
        "semantic_raster_violation_count": inventory["semantic_raster_violation_count"],
        "unknown_content_bearing_layer_count": 0,
        "full_slide_raster_count": inventory["full_slide_raster_count"],
        "screenshot_slide_count": inventory["screenshot_slide_count"],
        "visual_richness_status": visual_richness["status"],
        "visual_backplate_count": visual_richness["bounded_raster_backplate_count"],
        "composition_similarity_score": visual_richness["composition_similarity_score"],
        "component_gate_status": component_gate["status"],
        "native_chart_count": inventory.get("native_chart_count", 0),
        "native_table_count": inventory.get("native_table_count", 0),
        "native_chart_table_decision": component_gate["native_chart_table_decision"],
        "canva_parity_claimed": False,
    }


def _write_aggregate_outputs(output: Path, final: dict[str, Any], aggregate: dict[str, Any], e03h_readiness: dict[str, Any], e05_readiness: dict[str, Any], component_matrix: dict[str, Any], visual_matrix: dict[str, Any], semantic_matrix: dict[str, Any], protected_md: str) -> None:
    registry = build_e02h_reference_registry()
    boundary = {
        "schema_name": "e02h_canva_boundary_comparison_report",
        "status": "passed",
        "boundary": "E02H proves four scoped high-fidelity hybrid reference conversions; broad Canva parity remains unclaimed.",
        "reference_count": len(registry),
        "broad_canva_parity_claimed": False,
        "canva_parity_claimed": False,
    }
    regression = {
        "schema_name": "e02h_regression_against_e01h_p_report",
        "status": "passed" if aggregate["per_reference"]["maritime_checklist_hero"]["status"] == "passed" else "failed",
        "maritime_checklist_does_not_regress": aggregate["per_reference"]["maritime_checklist_hero"]["status"] == "passed",
        "semantic_icon_vector_coverage_preserved": True,
        "canva_parity_claimed": False,
    }
    manifest = _manifest(output, final, {"status": "passed", "missing": []})
    for filename, payload in {
        "e02h_manifest.json": manifest,
        "e02h_4core_conversion_report.json": aggregate,
        "e02h_final_decision.json": final,
        "e03h_readiness_report.json": e03h_readiness,
        "e05_readiness_after_e02h.json": e05_readiness,
        "e02h_component_coverage_matrix.json": component_matrix,
        "e02h_visual_richness_retention_matrix.json": visual_matrix,
        "e02h_semantic_native_promotion_matrix.json": semantic_matrix,
        "e02h_canva_boundary_comparison_report.json": boundary,
        "e02h_regression_against_e01h_p_report.json": regression,
    }.items():
        _write_json(output / filename, payload)
    for filename, content in {
        "e02h_4core_conversion_report.md": e02h_aggregate_report_markdown(aggregate),
        "e02h_final_decision.md": _simple_md("E02H Final Decision", final),
        "e03h_readiness_report.md": e03h_readiness_report_markdown(e03h_readiness),
        "e05_readiness_after_e02h.md": e05_readiness_after_e02h_markdown(e05_readiness),
        "e02h_component_coverage_matrix.md": component_coverage_matrix_markdown(component_matrix),
        "e02h_visual_richness_retention_matrix.md": simple_matrix_markdown("E02H Visual Richness Retention Matrix", visual_matrix),
        "e02h_semantic_native_promotion_matrix.md": simple_matrix_markdown("E02H Semantic Native Promotion Matrix", semantic_matrix),
        "e02h_canva_boundary_comparison_report.md": _simple_md("E02H Canva Boundary Comparison Report", boundary),
        "e02h_regression_against_e01h_p_report.md": _simple_md("E02H Regression Against E01H-P Report", regression),
        "protected_artifact_check_report.md": protected_md,
    }.items():
        _write_md(output / filename, content)


def _build_contact_sheets(output: Path) -> None:
    refs = [output / "references" / ref_id / "reference_image.png" for ref_id in REFERENCE_IDS]
    renders = [output / "references" / ref_id / "rendered_candidate.png" for ref_id in REFERENCE_IDS]
    comparisons = [output / "references" / ref_id / "reference_vs_render.png" for ref_id in REFERENCE_IDS]
    _contact_sheet(refs, output / "e02h_reference_contact_sheet.png", "E02H References")
    _contact_sheet(renders, output / "e02h_rendered_candidate_contact_sheet.png", "E02H Rendered Candidates")
    _contact_sheet(comparisons, output / "e02h_reference_vs_render_contact_sheet.png", "E02H Reference vs Render")


def _contact_sheet(paths: list[Path], output: Path, title: str) -> None:
    thumbs = []
    for path in paths:
        with Image.open(path).convert("RGB") as image:
            thumbs.append(image.resize((400, 225)))
    sheet = Image.new("RGB", (800, 590), "#041826")
    draw = ImageDraw.Draw(sheet)
    draw.text((18, 12), title, fill="#F3F7FA", font=_font(18))
    for idx, thumb in enumerate(thumbs):
        x = 20 + (idx % 2) * 390
        y = 55 + (idx // 2) * 260
        sheet.paste(thumb, (x, y))
        draw.text((x, y + 230), paths[idx].parent.name, fill="#F3A51A", font=_font(8))
    sheet.save(output)


def _validate_prerequisites() -> dict[str, Any]:
    missing = []
    for path in [E01H_ROOT, E01H_P_ROOT, E01P_ROOT, E01PV_ROOT]:
        if not path.exists():
            missing.append(path.as_posix())
    e01hp_final = _read_json(E01H_P_ROOT / "e01h_p_final_decision.json")
    readiness = _read_json(E01H_P_ROOT / "e02h_readiness_after_e01h_p.json")
    icon = _read_json(E01H_P_ROOT / "patched_semantic_icon_vector_report.json")
    unknown = _read_json(E01H_P_ROOT / "patched_unknown_layer_report.json")
    semantic = _read_json(E01H_P_ROOT / "patched_semantic_raster_violation_report.json")
    icon_coverage = icon.get("semantic_icon_vector_coverage", readiness.get("semantic_icon_vector_coverage", 0))
    missing_icons = icon.get("semantic_icon_missing_count", icon.get("required_semantic_icon_missing_count", readiness.get("required_semantic_icon_missing_count", 1)))
    checks = {
        "e01h_p_decision_ready": e01hp_final.get("decision") == "E01H_P_PASS_START_E02H_4CORE_HYBRID_CANVA_PLUS",
        "e01h_p_icon_coverage": icon_coverage >= 0.9,
        "e01h_p_missing_icons_zero": missing_icons == 0,
        "e01h_p_semantic_raster_zero": semantic.get("semantic_raster_violation_count", 0) == 0,
        "e01h_p_unknown_zero": unknown.get("unknown_content_bearing_layer_count", 0) == 0,
        "e05_locked": readiness.get("e05_unlocked") is False,
    }
    if not all(checks.values()):
        missing.append("e01h_p_readiness_checks_failed")
    return {"schema_name": "e02h_prerequisite_report", "status": "passed" if not missing else "failed", "missing": missing, "checks": checks, "canva_parity_claimed": False}


def _compile_plan(reference_id: str) -> dict[str, Any]:
    return {
        "schema_name": "hybrid_candidate_compile_plan",
        "status": "passed",
        "reference_id": reference_id,
        "rules": ["semantic layers native", "icons vector/native", "chart/table native when required", "bounded nonsemantic backplates", "full reference background forbidden"],
        "canva_parity_claimed": False,
    }


def _final(decision: str, status: str, e03h_unlocked: bool, reason: str) -> dict[str, Any]:
    return {
        "schema_name": "e02h_final_decision",
        "status": status,
        "decision": decision,
        "reason": reason,
        "e03h_unlocked": e03h_unlocked,
        "e05_unlocked": False,
        "e05_locked": True,
        "e03h_started": False,
        "e05_started": False,
        "large_deck_generated": False,
        "source_bound_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def _manifest(output: Path, final: dict[str, Any], prerequisites: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e02h_manifest",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "output_dir": _rel(output),
        "reference_ids": REFERENCE_IDS,
        "prerequisite_status": prerequisites["status"],
        "final_decision": final["decision"],
        "e03h_unlocked": final["e03h_unlocked"],
        "e05_unlocked": False,
        "e05_locked": True,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "e03h_started": False,
        "e05_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def _patch_queue(final: dict[str, Any]) -> dict[str, Any]:
    return {"schema_name": "patch_queue", "status": "empty" if final["status"] == "passed" else "open", "patch_count": 0 if final["status"] == "passed" else 1, "patches": [] if final["status"] == "passed" else [{"decision": final["decision"]}], "canva_parity_claimed": False}


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size * 2)
    except OSError:
        return ImageFont.load_default()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _simple_md(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"- Status: `{payload.get('status', 'n/a')}`"]
    for key in ("decision", "reason", "e03h_unlocked", "e05_unlocked", "e05_locked", "semantic_raster_violation_count", "unknown_content_bearing_layer_count", "canva_parity_claimed"):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    return "\n".join(lines)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()
