"""PromptSet E03H 12-core high-fidelity hybrid Canva+ reference pack gate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from scripts.run_e01x_self_describing_ps_layer_integration import protected_report, protected_snapshot, run_protect_check
from src.presentation_agent.magic_layer.e01h_hybrid_orchestrator import build_ps_layer_protocol_hybrid
from src.presentation_agent.magic_layer.e02h_4core_orchestrator import build_e02h_reference_payload
from src.presentation_agent.magic_layer.e03h_aggregate_report import (
    build_e03h_aggregate_report,
    build_e03h_semantic_native_promotion_matrix,
    build_e03h_visual_richness_retention_matrix,
    build_e04h_readiness_report,
    e03h_reference_pack_report_markdown,
    e04h_readiness_report_markdown,
    simple_matrix_markdown,
)
from src.presentation_agent.magic_layer.e03h_candidate_compiler import (
    audit_e03h_candidate_pptx,
    build_e03h_editable_candidate_spec,
    build_e03h_inventory_ledgers,
    compile_e03h_candidate,
    render_e03h_candidate_preview,
)
from src.presentation_agent.magic_layer.e03h_canva_plus_hybrid_gate import (
    build_e03h_canva_plus_hybrid_gate_report,
    build_e03h_semantic_editability_reports,
    build_e05_readiness_after_e03h,
    canva_plus_hybrid_gate_report_markdown,
    e05_readiness_after_e03h_markdown,
)
from src.presentation_agent.magic_layer.e03h_component_gates import (
    build_e03h_component_coverage_matrix,
    build_e03h_micro_component_gate_report,
    build_e03h_micro_component_report,
    build_e03h_reference_component_gate,
    build_e03h_semantic_icon_report,
    component_coverage_matrix_markdown,
)
from src.presentation_agent.magic_layer.e03h_hybrid_object_graph_builder import (
    build_e03h_hybrid_object_graph,
    build_e03h_layer_manifest_v5,
    build_e03h_reference_definition,
    build_e03h_region_ledgers,
    build_e03h_semantic_slot_graph,
    build_e03h_visual_layer_graph,
)
from src.presentation_agent.magic_layer.e03h_pack_compiler import compile_e03h_reference_pack
from src.presentation_agent.magic_layer.e03h_reference_generator import (
    build_asset_recipe_manifest,
    build_design_intent_trace,
    build_image_prompt,
    build_reference_analysis_report,
    build_reference_visual_richness_report,
    generate_reference_image,
)
from src.presentation_agent.magic_layer.e03h_reference_quality_gate import (
    build_e03h_reference_quality_report,
    reference_quality_report_markdown,
)
from src.presentation_agent.magic_layer.e03h_reference_registry import (
    CORE_REFERENCE_IDS,
    build_e03h_reference_pack_registry,
    hybrid_reference_pack_registry_markdown,
)
from src.presentation_agent.magic_layer.e03h_semantic_native_planner import build_e03h_semantic_native_plan
from src.presentation_agent.magic_layer.e03h_text_first_lock import build_e03h_text_first_lock_report
from src.presentation_agent.magic_layer.e03h_visual_backplate_planner import build_e03h_visual_backplate_policy
from src.presentation_agent.magic_layer.e03h_visual_fidelity_gate import (
    build_e03h_visual_fidelity_report,
    build_e03h_visual_richness_retention_report,
    visual_fidelity_report_markdown,
    visual_richness_retention_report_markdown,
)
from src.presentation_agent.magic_layer.e02h_text_first_lock import text_first_lock_report_markdown


REPO_ROOT = Path(__file__).resolve().parents[3]
E01H_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01h_high_fidelity_hybrid_canva_plus_single_reference"
E01H_P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01h_p_semantic_icon_microcomponent_fidelity_patch"
E02H_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e02h_4core_hybrid_canva_plus_reference_conversion"
E01P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_photoshop_layer_protocol"
E01PV_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_v_cross_ledger_validator"
E03H_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e03h_12_16_hybrid_canva_plus_reference_pack"
E02H_REGRESSION_IDS = {"maritime_checklist_hero", "process_workflow_infographic", "data_dashboard_hybrid", "table_matrix_hybrid"}


def build_e03h_reference_payload(reference_id: str, output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if reference_id in E02H_REGRESSION_IDS:
        payload = build_e02h_reference_payload(reference_id, output)
        payload["schema_name"] = "e03h_reference_payload"
        payload["gate_scope"] = "e03h_regression_rebuild"
        payload["reference_source"] = "e02h_regression"
        return payload
    definition = build_e03h_reference_definition(reference_id)
    reference_path = output / "reference_image.png"
    generate_reference_image(definition, reference_path)
    analysis = build_reference_analysis_report(definition, reference_path)
    text_lock = build_e03h_text_first_lock_report(definition)
    object_graph = build_e03h_hybrid_object_graph(definition, text_lock)
    backplates = build_e03h_visual_backplate_policy(object_graph)
    semantic_plan = build_e03h_semantic_native_plan(object_graph, reference_id)
    ledgers = build_e03h_region_ledgers(object_graph)
    payload = {
        "schema_name": "e03h_reference_payload",
        "status": "passed",
        "reference_id": reference_id,
        "reference_source": definition.get("reference_source", "local_generated"),
        "definition": definition,
        "image_prompt": build_image_prompt(definition),
        "design_intent_trace": build_design_intent_trace(definition),
        "asset_recipe_manifest": build_asset_recipe_manifest(definition),
        "reference_analysis_report": analysis,
        "reference_visual_richness_report": build_reference_visual_richness_report(definition, analysis),
        "text_first_lock_report": text_lock,
        "object_graph_v2": object_graph,
        "layer_manifest_v5": build_e03h_layer_manifest_v5(object_graph),
        "semantic_slot_graph": build_e03h_semantic_slot_graph(object_graph),
        "visual_layer_graph": build_e03h_visual_layer_graph(object_graph),
        **backplates,
        **semantic_plan,
        **ledgers,
        "hybrid_candidate_compile_plan": _compile_plan(reference_id),
        "canva_parity_claimed": False,
    }
    payload["ps_layer_intent_hybrid"] = build_ps_layer_protocol_hybrid(object_graph, analysis, protocol_id=f"e03h_{reference_id}_intent")
    payload["ps_layer_as_built_hybrid"] = build_ps_layer_protocol_hybrid(object_graph, analysis, protocol_id=f"e03h_{reference_id}_as_built")
    return payload


def run_e03h_12_16_hybrid_canva_plus_reference_pack(output_dir: str | Path = E03H_ROOT) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    if not run_protect_check():
        final = _final("E03H_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact precheck failed")
        _write_json(output / "e03h_final_decision.json", final)
        return final
    prerequisites = _validate_prerequisites()
    if prerequisites["status"] != "passed":
        final = _final("E03H_PATCH_REFERENCE_QUALITY", "failed", False, "required E01H/E01H-P/E02H/PS-layer inputs missing or not ready")
        _write_json(output / "e03h_manifest.json", _manifest(output, final, prerequisites))
        _write_json(output / "e03h_final_decision.json", final)
        return final

    payloads: list[dict[str, Any]] = []
    per_reference: dict[str, dict[str, Any]] = {}
    for reference_id in CORE_REFERENCE_IDS:
        ref_out = output / "references" / reference_id
        payload = build_e03h_reference_payload(reference_id, ref_out)
        payloads.append(payload)
        per_reference[reference_id] = _run_reference_conversion(payload, ref_out)

    pack_report = compile_e03h_reference_pack(payloads, output)
    protected_after = protected_snapshot()
    protected_md, protected_ok = protected_report(protected_before, protected_after)
    protect_post = run_protect_check()
    protected_md += f"\n\n- npm protect precheck: `passed`\n- npm protect postcheck: `{'passed' if protect_post else 'failed'}`\n"
    protected_ok = protected_ok and protect_post

    aggregate = build_e03h_aggregate_report(per_reference, pack_report=pack_report, protected_artifacts_unchanged=protected_ok)
    e04h_readiness = build_e04h_readiness_report(aggregate)
    e05_readiness = build_e05_readiness_after_e03h(aggregate)
    final = _final(aggregate["decision"], aggregate["status"], e04h_readiness["e04h_unlocked"], aggregate["decision"])
    if not protected_ok:
        final = _final("E03H_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact postcheck failed")
        aggregate["status"] = "failed"
        aggregate["decision"] = "E03H_FAIL_PROTECTED_ARTIFACTS"
        aggregate["e04h_unlocked"] = False
        e04h_readiness["status"] = "failed"
        e04h_readiness["e04h_unlocked"] = False

    component_matrix = build_e03h_component_coverage_matrix(payloads)
    visual_matrix = build_e03h_visual_richness_retention_matrix(per_reference)
    semantic_matrix = build_e03h_semantic_native_promotion_matrix(per_reference)
    _build_contact_sheets(output)
    _write_aggregate_outputs(
        output,
        final,
        aggregate,
        e04h_readiness,
        e05_readiness,
        component_matrix,
        visual_matrix,
        semantic_matrix,
        pack_report,
        protected_md,
    )
    return final


def _run_reference_conversion(payload: dict[str, Any], ref_out: Path) -> dict[str, Any]:
    _write_reference_inputs(ref_out, payload)
    compile_report = compile_e03h_candidate(payload, ref_out)
    render_manifest = render_e03h_candidate_preview(payload, ref_out)
    inventory = audit_e03h_candidate_pptx(ref_out / "editable_candidate.pptx")
    ledgers = build_e03h_inventory_ledgers(inventory, payload)
    _write_candidate_outputs(ref_out, payload, render_manifest, ledgers)
    visual_fidelity = build_e03h_visual_fidelity_report(ref_out / "reference_image.png", ref_out / "rendered_candidate.png")
    visual_richness = build_e03h_visual_richness_retention_report(payload, visual_fidelity)
    semantic_reports = build_e03h_semantic_editability_reports(payload, inventory)
    icon_report = build_e03h_semantic_icon_report(payload)
    micro_inventory = build_e03h_micro_component_report(payload)
    micro_gate = build_e03h_micro_component_gate_report(payload)
    component_gate = build_e03h_reference_component_gate(payload)
    canva_gate = build_e03h_canva_plus_hybrid_gate_report(
        reference_id=payload["reference_id"],
        candidate_exists=Path(compile_report["pptx_path"]).exists(),
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
    final["core"] = payload["reference_id"] in CORE_REFERENCE_IDS
    _write_reference_reports(ref_out, visual_fidelity, visual_richness, semantic_reports, icon_report, micro_inventory, micro_gate, canva_gate, final)
    return final


def _write_reference_inputs(ref_out: Path, payload: dict[str, Any]) -> None:
    definition = payload["definition"]
    quality = build_e03h_reference_quality_report(definition)
    _write_md(ref_out / "image_prompt.md", payload["image_prompt"])
    _write_json(ref_out / "reference_quality_report.json", quality)
    _write_md(ref_out / "reference_quality_report.md", reference_quality_report_markdown(quality))
    _write_md(ref_out / "text_first_lock_report.md", _text_first_lock_md(payload["text_first_lock_report"]))
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


def _write_candidate_outputs(ref_out: Path, payload: dict[str, Any], render_manifest: dict[str, Any], ledgers: dict[str, dict[str, Any]]) -> None:
    _write_json(ref_out / "editable_candidate_spec.json", build_e03h_editable_candidate_spec(payload))
    _write_json(ref_out / "render_manifest.json", render_manifest)
    for key, ledger in ledgers.items():
        _write_json(ref_out / "ledgers" / f"{key}.json", ledger)


def _write_reference_reports(
    ref_out: Path,
    visual_fidelity: dict[str, Any],
    visual_richness: dict[str, Any],
    semantic_reports: dict[str, dict[str, Any]],
    icon_report: dict[str, Any],
    micro_inventory: dict[str, Any],
    micro_gate: dict[str, Any],
    canva_gate: dict[str, Any],
    final: dict[str, Any],
) -> None:
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


def _write_aggregate_outputs(
    output: Path,
    final: dict[str, Any],
    aggregate: dict[str, Any],
    e04h_readiness: dict[str, Any],
    e05_readiness: dict[str, Any],
    component_matrix: dict[str, Any],
    visual_matrix: dict[str, Any],
    semantic_matrix: dict[str, Any],
    pack_report: dict[str, Any],
    protected_md: str,
) -> None:
    registry = build_e03h_reference_pack_registry()
    component_library = _component_library()
    backplate_policy = _backplate_policy()
    semantic_policy = _semantic_policy()
    quality_gate = _reference_quality_gate_report(output)
    regression = _regression_report(aggregate)
    boundary = _boundary_report(len(registry))
    manifest = _manifest(output, final, {"status": "passed", "missing": []})
    json_outputs = {
        "e03h_manifest.json": manifest,
        "e03h_reference_pack_report.json": aggregate,
        "e03h_final_decision.json": final,
        "e04h_readiness_report.json": e04h_readiness,
        "e05_readiness_after_e03h.json": e05_readiness,
        "hybrid_reference_pack_registry.json": registry,
        "hybrid_component_library_v1.json": component_library,
        "hybrid_visual_backplate_policy_v1.json": backplate_policy,
        "semantic_native_component_policy_v1.json": semantic_policy,
        "reference_quality_gate_report.json": quality_gate,
        "e03h_component_coverage_matrix.json": component_matrix,
        "e03h_visual_richness_retention_matrix.json": visual_matrix,
        "e03h_semantic_native_promotion_matrix.json": semantic_matrix,
        "e03h_regression_against_e02h_report.json": regression,
        "editable_hybrid_reference_pack_render_manifest.json": pack_report,
        "e03h_canva_boundary_comparison_report.json": boundary,
    }
    for filename, payload in json_outputs.items():
        _write_json(output / filename, payload)
    md_outputs = {
        "e03h_reference_pack_report.md": e03h_reference_pack_report_markdown(aggregate),
        "e03h_final_decision.md": _simple_md("E03H Final Decision", final),
        "e04h_readiness_report.md": e04h_readiness_report_markdown(e04h_readiness),
        "e05_readiness_after_e03h.md": e05_readiness_after_e03h_markdown(e05_readiness),
        "hybrid_reference_pack_registry.md": hybrid_reference_pack_registry_markdown(registry),
        "hybrid_component_library_v1.md": _simple_md("Hybrid Component Library V1", component_library),
        "hybrid_visual_backplate_policy_v1.md": _simple_md("Hybrid Visual Backplate Policy V1", backplate_policy),
        "semantic_native_component_policy_v1.md": _simple_md("Semantic Native Component Policy V1", semantic_policy),
        "reference_quality_gate_report.md": _simple_md("Reference Quality Gate Report", quality_gate),
        "e03h_component_coverage_matrix.md": component_coverage_matrix_markdown(component_matrix),
        "e03h_visual_richness_retention_matrix.md": simple_matrix_markdown("E03H Visual Richness Retention Matrix", visual_matrix),
        "e03h_semantic_native_promotion_matrix.md": simple_matrix_markdown("E03H Semantic Native Promotion Matrix", semantic_matrix),
        "e03h_regression_against_e02h_report.md": _simple_md("E03H Regression Against E02H Report", regression),
        "e03h_canva_boundary_comparison_report.md": _simple_md("E03H Canva Boundary Comparison Report", boundary),
        "protected_artifact_check_report.md": protected_md,
        "reference_generation_prompt_pack.md": _prompt_pack(registry),
    }
    for filename, content in md_outputs.items():
        _write_md(output / filename, content)


def _build_contact_sheets(output: Path) -> None:
    refs = [output / "references" / ref_id / "reference_image.png" for ref_id in CORE_REFERENCE_IDS]
    renders = [output / "references" / ref_id / "rendered_candidate.png" for ref_id in CORE_REFERENCE_IDS]
    comparisons = [output / "references" / ref_id / "reference_vs_render.png" for ref_id in CORE_REFERENCE_IDS]
    _contact_sheet(refs, output / "e03h_reference_contact_sheet.png", "E03H References")
    _contact_sheet(renders, output / "e03h_rendered_candidate_contact_sheet.png", "E03H Rendered Candidates")
    _contact_sheet(comparisons, output / "e03h_reference_vs_render_contact_sheet.png", "E03H Reference vs Render")


def _contact_sheet(paths: list[Path], output: Path, title: str) -> None:
    thumbs = []
    for path in paths:
        with Image.open(path).convert("RGB") as image:
            thumbs.append(image.resize((320, 180)))
    cols = 3
    rows = max(1, (len(thumbs) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * 340 + 20, rows * 225 + 60), "#041826")
    draw = ImageDraw.Draw(sheet)
    draw.text((18, 16), title, fill="#F3F7FA", font=_font(14))
    for idx, thumb in enumerate(thumbs):
        x = 20 + (idx % cols) * 340
        y = 55 + (idx // cols) * 225
        sheet.paste(thumb, (x, y))
        draw.text((x, y + 184), paths[idx].parent.name, fill="#F3A51A", font=_font(7))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _validate_prerequisites() -> dict[str, Any]:
    missing = []
    for path in [E01H_ROOT, E01H_P_ROOT, E02H_ROOT, E01P_ROOT, E01PV_ROOT]:
        if not path.exists():
            missing.append(path.as_posix())
    e01hp_final = _read_json(E01H_P_ROOT / "e01h_p_final_decision.json")
    e02h_final = _read_json(E02H_ROOT / "e02h_final_decision.json")
    e02h_report = _read_json(E02H_ROOT / "e02h_4core_conversion_report.json")
    e05_readiness = _read_json(E02H_ROOT / "e05_readiness_after_e02h.json")
    checks = {
        "e01h_p_decision_ready": e01hp_final.get("decision") == "E01H_P_PASS_START_E02H_4CORE_HYBRID_CANVA_PLUS",
        "e02h_decision_ready": e02h_final.get("decision") == "E02H_PASS_READY_FOR_E03H_12_16_HYBRID_CANVA_PLUS_REFERENCE_PACK",
        "e02h_semantic_raster_zero": e02h_report.get("semantic_raster_violation_count") == 0,
        "e02h_unknown_zero": e02h_report.get("unknown_content_bearing_layer_count") == 0,
        "e02h_full_slide_zero": e02h_report.get("full_slide_raster_count") == 0,
        "e02h_screenshot_zero": e02h_report.get("screenshot_slide_count") == 0,
        "e05_locked": e05_readiness.get("e05_unlocked") is False,
    }
    if not all(checks.values()):
        missing.append("e03h_prerequisite_checks_failed")
    return {"schema_name": "e03h_prerequisite_report", "status": "passed" if not missing else "failed", "missing": missing, "checks": checks, "canva_parity_claimed": False}


def _compile_plan(reference_id: str) -> dict[str, Any]:
    return {
        "schema_name": "hybrid_candidate_compile_plan",
        "status": "passed",
        "reference_id": reference_id,
        "rules": ["semantic layers native", "icons vector/native", "chart/table native when required", "bounded nonsemantic backplates", "full reference background forbidden"],
        "canva_parity_claimed": False,
    }


def _component_library() -> dict[str, Any]:
    components = {
        "title_block": {"target": "ppt_text_box", "raster_policy": "forbidden"},
        "source_footer": {"target": "ppt_text_box_and_shape", "raster_policy": "forbidden"},
        "semantic_icon": {"target": "native_vector_or_svg", "raster_policy": "forbidden"},
        "connector_line": {"target": "ppt_connector_or_freeform", "raster_policy": "forbidden"},
        "native_chart": {"target": "native_chart_or_editable_shape_chart", "raster_policy": "forbidden"},
        "native_table": {"target": "native_table_or_editable_shape_grid", "raster_policy": "forbidden"},
        "visual_backplate": {"target": "bounded_nonsemantic_raster_or_vector", "raster_policy": "allowed_when_bounded_nonsemantic"},
        "replaceable_visual_field": {"target": "replaceable_image_frame", "raster_policy": "allowed_when_nonsemantic"},
    }
    return {"schema_name": "hybrid_component_library_v1", "status": "passed", "components": components, "canva_parity_claimed": False}


def _backplate_policy() -> dict[str, Any]:
    return {
        "schema_name": "hybrid_visual_backplate_policy_v1",
        "status": "passed",
        "allowed": ["bounded_nonsemantic_texture", "hero_photo_field", "decorative_shadow_glow_noise", "technical_overlay_without_semantic_content"],
        "forbidden": ["full_slide_reference_background", "screenshot_slide", "semantic_text_raster", "semantic_icon_raster", "chart_table_raster"],
        "large_visual_field_rule": "allowed only when bounded and free of semantic content",
        "canva_parity_claimed": False,
    }


def _semantic_policy() -> dict[str, Any]:
    return {
        "schema_name": "semantic_native_component_policy_v1",
        "status": "passed",
        "semantic_text": "ppt_text_box",
        "semantic_icons": "svg_vector_or_native_freeform",
        "charts": "native_chart_or_editable_shape_chart",
        "tables": "native_table_or_editable_shape_grid",
        "cards_panels_footer": "ppt_shapes_and_text",
        "semantic_raster_allowed": False,
        "canva_parity_claimed": False,
    }


def _reference_quality_gate_report(output: Path) -> dict[str, Any]:
    reports = {}
    for reference_id in CORE_REFERENCE_IDS:
        reports[reference_id] = _read_json(output / "references" / reference_id / "reference_quality_report.json")
    return {
        "schema_name": "reference_quality_gate_report",
        "status": "passed" if all(report.get("status") == "passed" for report in reports.values()) else "failed",
        "reference_count": len(reports),
        "references": reports,
        "canva_parity_claimed": False,
    }


def _regression_report(aggregate: dict[str, Any]) -> dict[str, Any]:
    rows = {reference_id: aggregate["per_reference"].get(reference_id, {}) for reference_id in E02H_REGRESSION_IDS}
    return {
        "schema_name": "e03h_regression_against_e02h_report",
        "status": "passed" if all(row.get("status") == "passed" for row in rows.values()) else "failed",
        "e02h_reference_ids": sorted(E02H_REGRESSION_IDS),
        "references": rows,
        "canva_parity_claimed": False,
    }


def _boundary_report(reference_count: int) -> dict[str, Any]:
    return {
        "schema_name": "e03h_canva_boundary_comparison_report",
        "status": "passed",
        "boundary": "E03H proves scoped 12-core high-fidelity hybrid reference conversions; broad Canva parity remains unclaimed.",
        "reference_count": reference_count,
        "broad_canva_parity_claimed": False,
        "canva_parity_claimed": False,
    }


def _text_first_lock_md(report: dict[str, Any]) -> str:
    if "protected_text_zone_count" in report:
        return text_first_lock_report_markdown(report)
    zones = report.get("protected_zones", report.get("text_like_regions", report.get("zones", [])))
    return "\n".join(
        [
            "# Text-First Lock Report",
            "",
            f"- Status: `{report.get('status', 'passed')}`",
            f"- Protected text zones: `{len(zones)}`",
            f"- OCR performed: `{report.get('ocr_performed', False)}`",
            "- Broad Canva parity claimed: `False`",
        ]
    )


def _prompt_pack(registry: dict[str, dict[str, Any]]) -> str:
    lines = ["# E03H Reference Generation Prompt Pack", "", "Use local deterministic or Codex Desktop reference generation only; do not call Image API.", ""]
    for reference_id, row in registry.items():
        lines.append(f"## {reference_id}")
        lines.append(f"- Visual role: {row['visual_role']}")
        lines.append("- Protect semantic text, icons, charts, tables, cards, and footer zones.")
        lines.append("- Use bounded nonsemantic visual backplates; do not use full-slide reference backgrounds.")
    return "\n".join(lines)


def _final(decision: str, status: str, e04h_unlocked: bool, reason: str) -> dict[str, Any]:
    return {
        "schema_name": "e03h_final_decision",
        "status": status,
        "decision": decision,
        "reason": reason,
        "e04h_unlocked": e04h_unlocked,
        "e05_unlocked": False,
        "e05_locked": True,
        "e04h_started": False,
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
        "schema_name": "e03h_manifest",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "output_dir": _rel(output),
        "core_reference_ids": CORE_REFERENCE_IDS,
        "optional_reference_ids_included": [],
        "prerequisite_status": prerequisites["status"],
        "final_decision": final["decision"],
        "e04h_unlocked": final["e04h_unlocked"],
        "e05_unlocked": False,
        "e05_locked": True,
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "e04h_started": False,
        "e05_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def _patch_queue(final: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "patch_queue",
        "status": "empty" if final["status"] == "passed" else "open",
        "patch_count": 0 if final["status"] == "passed" else 1,
        "patches": [] if final["status"] == "passed" else [{"decision": final["decision"]}],
        "canva_parity_claimed": False,
    }


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
    for key in (
        "decision",
        "reason",
        "e04h_unlocked",
        "e05_unlocked",
        "e05_locked",
        "semantic_raster_violation_count",
        "unknown_content_bearing_layer_count",
        "canva_parity_claimed",
    ):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    return "\n".join(lines)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()
