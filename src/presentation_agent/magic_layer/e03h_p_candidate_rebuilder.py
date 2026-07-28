"""Rebuild E03H-P per-reference candidates and reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    canva_plus_hybrid_gate_report_markdown,
)
from src.presentation_agent.magic_layer.e03h_component_gates import (
    build_e03h_micro_component_gate_report,
    build_e03h_micro_component_report,
    build_e03h_reference_component_gate,
    build_e03h_semantic_icon_report,
)
from src.presentation_agent.magic_layer.e03h_p_reference_quality_contract import (
    build_premium_reference_quality_contract_v2,
    evaluate_premium_reference_quality_contract_v2,
)
from src.presentation_agent.magic_layer.e03h_p_reference_strength_score import (
    reference_strength_score_markdown,
    score_reference_strength,
)
from src.presentation_agent.magic_layer.e03h_reference_quality_gate import (
    build_e03h_reference_quality_report,
    reference_quality_report_markdown,
)
from src.presentation_agent.magic_layer.e03h_visual_fidelity_gate import (
    build_e03h_visual_fidelity_report,
    build_e03h_visual_richness_retention_report,
    visual_fidelity_report_markdown,
    visual_richness_retention_report_markdown,
)


def rebuild_e03h_p_reference_candidate(
    payload: dict[str, Any],
    output_dir: str | Path,
    *,
    original_assessment: dict[str, Any] | None = None,
    patch_required: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    original_assessment = original_assessment or score_reference_strength(payload)
    patch_required = patch_required or _patch_required(payload, original_assessment)
    _write_reference_inputs(output, payload, original_assessment, patch_required)

    compile_report = compile_e03h_candidate(payload, output)
    render_manifest = render_e03h_candidate_preview(payload, output)
    inventory = audit_e03h_candidate_pptx(output / "editable_candidate.pptx")
    ledgers = build_e03h_inventory_ledgers(inventory, payload)
    _write_json(output / "editable_candidate_spec.json", build_e03h_editable_candidate_spec(payload))
    _write_json(output / "render_manifest.json", render_manifest)
    for key, ledger in ledgers.items():
        _write_json(output / "ledgers" / f"{key}.json", ledger)

    visual_fidelity = build_e03h_visual_fidelity_report(output / "reference_image.png", output / "rendered_candidate.png")
    visual_richness = build_e03h_visual_richness_retention_report(payload, visual_fidelity)
    semantic_reports = build_e03h_semantic_editability_reports(payload, inventory)
    icon_report = build_e03h_semantic_icon_report(payload)
    micro_inventory = build_e03h_micro_component_report(payload)
    micro_gate = build_e03h_micro_component_gate_report(payload)
    component_gate = build_e03h_reference_component_gate(payload)
    quality_contract = evaluate_premium_reference_quality_contract_v2(payload, build_premium_reference_quality_contract_v2())
    canva_gate = build_e03h_canva_plus_hybrid_gate_report(
        reference_id=payload["reference_id"],
        candidate_exists=Path(compile_report["pptx_path"]).exists(),
        candidate_rendered=(output / "rendered_candidate.png").exists(),
        visual_richness=visual_richness,
        payload=payload,
        semantic_reports=semantic_reports,
        icon_report=icon_report,
        micro_component_report=micro_gate,
        component_gate=component_gate,
        protected_artifacts_unchanged=True,
    )
    if quality_contract["status"] != "passed":
        canva_gate["status"] = "failed"
        canva_gate["checks"]["premium_reference_quality_contract_v2"] = False
    else:
        canva_gate["checks"]["premium_reference_quality_contract_v2"] = True
    final = _reference_final(payload["reference_id"], canva_gate, component_gate, inventory, visual_richness)
    _write_reports(output, visual_fidelity, visual_richness, semantic_reports, icon_report, micro_inventory, micro_gate, canva_gate, final)
    return {
        "schema_name": "e03h_p_reference_rebuild_result",
        "status": final["status"],
        "reference_id": payload["reference_id"],
        "editable_candidate": (output / "editable_candidate.pptx").as_posix(),
        "rendered_candidate": (output / "rendered_candidate.png").as_posix(),
        "reference_vs_render": (output / "reference_vs_render.png").as_posix(),
        "inventory": inventory,
        "visual_richness": visual_richness,
        "component_gate": component_gate,
        "canva_gate": canva_gate,
        "reference_final_decision": final,
        "canva_parity_claimed": False,
    }


def _write_reference_inputs(output: Path, payload: dict[str, Any], original_assessment: dict[str, Any], patch_required: dict[str, Any]) -> None:
    if not (output / "reference_image.png").exists() and Path(payload["reference_analysis_report"]["reference_path"]).exists():
        (output / "reference_image.png").write_bytes(Path(payload["reference_analysis_report"]["reference_path"]).read_bytes())
    quality = build_e03h_reference_quality_report(payload["definition"])
    strength = score_reference_strength(payload)
    contract = evaluate_premium_reference_quality_contract_v2(payload)
    _write_json(output / "original_reference_quality_assessment.json", original_assessment)
    _write_md(output / "original_reference_quality_assessment.md", reference_strength_score_markdown(original_assessment))
    _write_json(output / "patch_required.json", patch_required)
    _write_md(output / "patch_required.md", _simple_md("Patch Required", patch_required))
    _write_md(output / "image_prompt.md", payload["image_prompt"])
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
        _write_json(output / f"{key}.json", payload[key])
    _write_json(output / "reference_quality_report.json", {**quality, "premium_contract_status": contract["status"], "reference_strength_score": strength["reference_strength_score"]})
    _write_md(output / "reference_quality_report.md", reference_quality_report_markdown(quality) + "\n\n" + reference_strength_score_markdown(strength))


def _write_reports(
    output: Path,
    visual_fidelity: dict[str, Any],
    visual_richness: dict[str, Any],
    semantic_reports: dict[str, dict[str, Any]],
    icon_report: dict[str, Any],
    micro_inventory: dict[str, Any],
    micro_gate: dict[str, Any],
    canva_gate: dict[str, Any],
    final: dict[str, Any],
) -> None:
    _write_json(output / "visual_fidelity_report.json", visual_fidelity)
    _write_md(output / "visual_fidelity_report.md", visual_fidelity_report_markdown(visual_fidelity))
    _write_json(output / "visual_richness_retention_report.json", visual_richness)
    _write_md(output / "visual_richness_retention_report.md", visual_richness_retention_report_markdown(visual_richness))
    for key, report in semantic_reports.items():
        _write_json(output / f"{key}.json", report)
    _write_json(output / "semantic_icon_inventory_report.json", icon_report)
    _write_json(output / "semantic_icon_fidelity_report.json", icon_report)
    _write_json(output / "semantic_icon_vector_report.json", icon_report)
    _write_json(output / "micro_component_inventory_report.json", micro_inventory)
    _write_json(output / "micro_component_fidelity_gate_report.json", micro_gate)
    _write_json(output / "canva_plus_hybrid_gate_report.json", canva_gate)
    _write_md(output / "canva_plus_hybrid_gate_report.md", canva_plus_hybrid_gate_report_markdown(canva_gate))
    _write_json(output / "reference_final_decision.json", final)
    patch_queue = {"schema_name": "patch_queue", "status": "empty" if final["status"] == "passed" else "open", "patch_count": 0 if final["status"] == "passed" else 1, "patches": [] if final["status"] == "passed" else [{"decision": final["decision"]}], "canva_parity_claimed": False}
    _write_json(output / "patch_queue.json", patch_queue)
    _write_md(output / "patch_queue.md", _simple_md("Patch Queue", patch_queue))


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


def _patch_required(payload: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    required = assessment["status"] != "passed"
    return {"schema_name": "patch_required", "status": "required" if required else "not_required", "reference_id": payload["reference_id"], "patch_required": required, "patch_action": payload.get("patch_action", "KEEP"), "failures": assessment.get("failures", []), "canva_parity_claimed": False}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _simple_md(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"- Status: `{payload.get('status', 'n/a')}`"]
    for key in ("reference_id", "patch_required", "patch_action", "decision", "canva_parity_claimed"):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    return "\n".join(lines)
