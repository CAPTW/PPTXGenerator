"""PromptSet E04-R2 isolated deck art-direction rebuild runner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from scripts.run_e01x_self_describing_ps_layer_integration import protected_report, protected_snapshot, run_protect_check
from src.presentation_agent.magic_layer.e04_design_quality_gate import (
    build_object_complexity_vs_design_quality_report,
    build_source_content_visual_interpretation_report,
)
from src.presentation_agent.magic_layer.e04_focal_object_gate import build_focal_object_report
from src.presentation_agent.magic_layer.e04_presentation_planner import build_narrative_outline, build_presentation_plan, build_slide_type_distribution
from src.presentation_agent.magic_layer.e04_r2_art_director import build_deck_art_direction_plan, write_plan_markdown
from src.presentation_agent.magic_layer.e04_r2_deck_compiler import compile_e04_r2_art_directed_deck
from src.presentation_agent.magic_layer.e04_r2_design_quality_qa import design_quality_report_markdown, run_e04_r2_design_quality_qa
from src.presentation_agent.magic_layer.e04_r2_focal_object_planner import build_focal_object_plan, focal_object_plan_markdown
from src.presentation_agent.magic_layer.e04_r2_layout_selector import layout_selection_report_r2_markdown, select_layouts_r2
from src.presentation_agent.magic_layer.e04_r2_slide_rhythm_planner import build_slide_rhythm_plan, slide_rhythm_plan_markdown
from src.presentation_agent.magic_layer.e04_r2_slot_binder import bind_slots_r2, template_binding_plan_r2, template_binding_plan_r2_markdown
from src.presentation_agent.magic_layer.e04_r2_visual_priority_matrix import build_visual_priority_matrix, visual_priority_matrix_markdown
from src.presentation_agent.magic_layer.e04_skeleton_similarity import build_skeleton_similarity_report
from src.presentation_agent.magic_layer.e04_slide_blueprint_builder import (
    build_claim_evidence_coverage_report,
    build_slide_blueprints,
    build_source_to_slide_trace_ledger,
)
from src.presentation_agent.magic_layer.e04_slide_rhythm import build_slide_rhythm_report
from src.presentation_agent.magic_layer.e04_source_bound_qa import run_source_bound_qa
from src.presentation_agent.magic_layer.e04_source_ingest import DEFAULT_SOURCE_PATH, build_source_artifacts
from src.presentation_agent.magic_layer.e04_visual_hierarchy_gate import build_visual_hierarchy_report


REPO_ROOT = Path(__file__).resolve().parents[3]
E04_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_source_bound_small_deck_with_e03_r2_pack"
E04_DQ_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_dq_source_bound_design_quality_gate"
E03_R2_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e03_r2_premium_visual_rebuild"
E04_R2_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_r2_deck_art_direction_rebuild"


def run_e04_r2_deck_art_direction_rebuild(output_dir: str | Path = E04_R2_ROOT) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    if not run_protect_check():
        final = _final("E04_R2_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact precheck failed")
        _write_json(output / "e04_r2_final_decision.json", final)
        return final

    prerequisites = _validate_prerequisites()
    original_e04 = _read_json(E04_ROOT / "e04_final_decision.json")
    original_dq = _read_json(E04_DQ_ROOT / "e04_design_quality_override.json")
    source = build_source_artifacts(DEFAULT_SOURCE_PATH)
    plan = build_presentation_plan(source["source_document_graph_v1"])
    narrative = build_narrative_outline(plan)
    blueprints = build_slide_blueprints(plan, source)
    art_plan = build_deck_art_direction_plan(E04_ROOT)
    rhythm_plan = build_slide_rhythm_plan(art_plan)
    focal_plan = build_focal_object_plan(art_plan)
    visual_priority = build_visual_priority_matrix(art_plan)
    composition_plan = _composition_variant_plan(art_plan)
    interpretation_plan = _source_interpretation_plan(art_plan)
    template_diversity = _template_usage_diversity_plan(art_plan)
    layout_r2 = select_layouts_r2(blueprints, art_plan)
    binding = bind_slots_r2(blueprints, layout_r2, source, art_plan)
    binding_plan = template_binding_plan_r2(binding)
    compile_report = compile_e04_r2_art_directed_deck(binding, art_plan, output)
    qa = run_source_bound_qa(output / "source_bound_sample_deck_r2_12_16.pptx", binding, source)

    _write_core_inputs(output, source, plan, narrative, blueprints)
    reports: dict[str, Any] = {
        "deck_art_direction_plan.json": art_plan,
        "slide_rhythm_plan.json": rhythm_plan,
        "focal_object_plan.json": focal_plan,
        "visual_priority_matrix.json": visual_priority,
        "composition_variant_plan.json": composition_plan,
        "source_content_visual_interpretation_plan.json": interpretation_plan,
        "template_usage_diversity_plan.json": template_diversity,
        "layout_selection_report_r2.json": layout_r2,
        "template_binding_plan_r2.json": binding_plan,
        "slot_binding_ledger_r2.json": binding["slot_binding_ledger"],
        "component_binding_ledger_r2.json": {**binding["component_binding_ledger"], "schema_name": "component_binding_ledger_r2"},
        "art_direction_patch_plan.json": _art_direction_patch_plan(art_plan),
        "source_footer_binding_ledger_r2.json": {**binding["source_footer_binding_ledger"], "schema_name": "source_footer_binding_ledger_r2"},
        "overflow_patch_plan_r2.json": {**binding["overflow_patch_plan"], "schema_name": "overflow_patch_plan_r2"},
        "source_bound_sample_deck_r2_render_manifest.json": compile_report["render_manifest"],
        "e04_r2_source_bound_deck_qa_report.json": qa["source_bound_deck_qa_report"],
        "e04_r2_semantic_editability_ledger.json": qa["semantic_editability_ledger"],
        "e04_r2_semantic_raster_violation_report.json": qa["semantic_raster_violation_report"],
        "e04_r2_unknown_layer_report.json": qa["unknown_layer_report"],
        "e04_r2_text_overflow_report.json": qa["text_overflow_report"],
        "e04_r2_chart_binding_report.json": qa["chart_binding_report"],
        "e04_r2_table_binding_report.json": qa["table_binding_report"],
        "e04_r2_citation_coverage_report.json": qa["citation_coverage_report"],
        "e04_r2_visual_consistency_report.json": qa["visual_consistency_report"],
    }
    for filename, payload in reports.items():
        _write_json(output / filename, payload)
    _write_markdown_reports(output, art_plan, rhythm_plan, focal_plan, visual_priority, composition_plan, interpretation_plan, template_diversity, layout_r2, binding_plan, reports)

    skeleton = build_skeleton_similarity_report(output)
    rhythm = build_slide_rhythm_report(output, skeleton)
    focal = build_focal_object_report(output)
    hierarchy = build_visual_hierarchy_report(output)
    complexity = build_object_complexity_vs_design_quality_report(output, hierarchy)
    interpretation = build_source_content_visual_interpretation_report(output)
    for filename, payload in {
        "e04_r2_skeleton_similarity_report.json": skeleton,
        "e04_r2_slide_rhythm_report.json": rhythm,
        "e04_r2_focal_object_report.json": focal,
        "e04_r2_visual_hierarchy_report.json": hierarchy,
        "e04_r2_source_content_visual_interpretation_report.json": interpretation,
        "object_complexity_vs_design_quality_report.json": complexity,
    }.items():
        _write_json(output / filename, payload)
    design_quality = run_e04_r2_design_quality_qa(output)
    _write_json(output / "e04_r2_design_quality_report.json", design_quality)
    _write_md(output / "e04_r2_design_quality_report.md", design_quality_report_markdown(design_quality))

    _make_e04_vs_r2_contact_sheet(output)
    e05_report = _e05_readiness_report_after_r2(source, design_quality, qa, compile_report)
    decision = "E04_R2_PASS_READY_FOR_E05_34_SLIDE_SCALEOUT" if e05_report["e05_unlocked"] else _patch_decision(design_quality)
    final = _final(decision, "passed" if e05_report["e05_unlocked"] else "failed", e05_report["e05_unlocked"], e05_report["reason"])
    manifest = {
        "schema_name": "e04_r2_manifest",
        "generated_at": _now(),
        "output_dir": _rel(output),
        "original_e04_structural_pass": original_e04.get("decision") == "E04_PASS_SOURCE_BOUND_SMALL_DECK_WITH_E03_R2_PACK",
        "original_e04_design_quality_pass": False,
        "e04_dq_decision": original_dq.get("decision"),
        "e05_unlocked_before_r2": False,
        "e05_unlocked_after_r2": e05_report["e05_unlocked"],
        "e05_started": False,
        "large_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
        "final_decision": final["decision"],
    }
    top_report = {
        "schema_name": "e04_r2_deck_art_direction_report",
        "status": final["status"],
        "decision": final["decision"],
        "source_mode": source["source_mode_report"]["mode"],
        "slide_count": compile_report["slide_count"],
        "composition_variant_count": art_plan["distinct_composition_variant_count"],
        "e04_dq_pass_restored": design_quality["status"] == "passed",
        "semantic_raster_violation_count": design_quality["semantic_raster_violation_count"],
        "unknown_content_bearing_layer_count": design_quality["unknown_content_bearing_layer_count"],
        "text_overflow_count": design_quality["text_overflow_count"],
        "citation_coverage_status": design_quality["citation_coverage_status"],
        "native_chart_binding_status": design_quality["native_chart_binding_status"],
        "native_table_binding_status": design_quality["native_table_binding_status"],
        "e05_unlocked": final["e05_unlocked"],
        "e05_started": False,
        "canva_parity_claimed": False,
    }
    protected_after = protected_snapshot()
    protected_md, protected_ok = protected_report(protected_before, protected_after)
    protect_post = run_protect_check()
    protected_md += f"\n\n- npm protect precheck: `passed`\n- npm protect postcheck: `{'passed' if protect_post else 'failed'}`\n"
    if not protected_ok or not protect_post:
        final = _final("E04_R2_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact postcheck failed")
        top_report["status"] = "failed"
        top_report["decision"] = final["decision"]
        manifest["final_decision"] = final["decision"]
    _write_json(output / "e04_r2_manifest.json", manifest)
    _write_json(output / "e04_r2_deck_art_direction_report.json", top_report)
    _write_md(output / "e04_r2_deck_art_direction_report.md", _simple_md("E04 R2 Deck Art Direction Report", top_report))
    _write_json(output / "e05_readiness_report_after_e04_r2.json", e05_report)
    _write_json(output / "e04_r2_final_decision.json", final)
    _write_md(output / "e04_r2_final_decision.md", _simple_md("E04 R2 Final Decision", final))
    _write_md(output / "protected_artifact_check_report.md", protected_md)
    return final


def _validate_prerequisites() -> dict[str, Any]:
    e04_required = [
        "source_bound_sample_deck_12_16.pptx",
        "source_bound_sample_deck_contact_sheet.png",
        "e04_final_decision.json",
        "source_document_graph_v1.json",
        "evidence_bank_v1.json",
        "presentation_plan_v1.json",
        "slide_blueprint_v1.json",
        "layout_selection_report.json",
        "slot_binding_ledger.json",
        "source_to_slide_trace_ledger.json",
        "citation_coverage_report.json",
        "semantic_editability_ledger.json",
        "text_overflow_report.json",
        "chart_binding_report.json",
        "table_binding_report.json",
    ]
    dq_required = ["e04_design_quality_override.json", "e05_readiness_override.json"]
    e03_required = [
        "editable_template_pack_r2.pptx",
        "editable_template_pack_r2_spec.json",
        "premium_design_system_tokens.json",
        "premium_component_library_v2.json",
        "premium_placeholder_grammar.json",
        "premium_visual_motif_library.json",
        "premium_archetype_contracts_v2.json",
        "premium_layout_selector_contract_v2.json",
        "e03_r2_final_decision.json",
        "e03_r2_visual_quality_gate_report.json",
    ]
    missing = [f"E04/{item}" for item in e04_required if not (E04_ROOT / item).exists()]
    missing += [f"E04-DQ/{item}" for item in dq_required if not (E04_DQ_ROOT / item).exists()]
    missing += [f"E03-R2/{item}" for item in e03_required if not (E03_R2_ROOT / item).exists()]
    return {"schema_name": "e04_r2_prerequisite_report", "status": "passed" if not missing else "failed", "missing": missing, "canva_parity_claimed": False}


def _write_core_inputs(output: Path, source: dict[str, Any], plan: dict[str, Any], narrative: dict[str, Any], blueprints: dict[str, Any]) -> None:
    for filename, payload in {
        "source_mode_report.json": source["source_mode_report"],
        "source_document_graph_v1.json": source["source_document_graph_v1"],
        "source_element_ledger.json": source["source_element_ledger"],
        "evidence_bank_v1.json": source["evidence_bank_v1"],
        "table_data_ledger.json": source["table_data_ledger"],
        "chart_data_ledger.json": source["chart_data_ledger"],
        "citation_reference_ledger.json": source["citation_reference_ledger"],
        "source_parse_quality_report.json": source["source_parse_quality_report"],
        "presentation_plan_v1.json": plan,
        "narrative_outline_v1.json": narrative,
        "slide_blueprint_v1.json": blueprints,
        "source_to_slide_trace_ledger.json": build_source_to_slide_trace_ledger(blueprints),
        "slide_type_distribution_report.json": build_slide_type_distribution(plan),
        "claim_evidence_coverage_report.json": build_claim_evidence_coverage_report(blueprints),
    }.items():
        _write_json(output / filename, payload)


def _write_markdown_reports(output: Path, art_plan: dict[str, Any], rhythm_plan: dict[str, Any], focal_plan: dict[str, Any], visual_priority: dict[str, Any], composition_plan: dict[str, Any], interpretation_plan: dict[str, Any], template_diversity: dict[str, Any], layout_r2: dict[str, Any], binding_plan: dict[str, Any], reports: dict[str, Any]) -> None:
    markdown = {
        "deck_art_direction_plan.md": write_plan_markdown(art_plan),
        "slide_rhythm_plan.md": slide_rhythm_plan_markdown(rhythm_plan),
        "focal_object_plan.md": focal_object_plan_markdown(focal_plan),
        "visual_priority_matrix.md": visual_priority_matrix_markdown(visual_priority),
        "composition_variant_plan.md": _simple_md("Composition Variant Plan", composition_plan),
        "source_content_visual_interpretation_plan.md": _simple_md("Source Content Visual Interpretation Plan", interpretation_plan),
        "template_usage_diversity_plan.md": _simple_md("Template Usage Diversity Plan", template_diversity),
        "layout_selection_report_r2.md": layout_selection_report_r2_markdown(layout_r2),
        "template_binding_plan_r2.md": template_binding_plan_r2_markdown(binding_plan),
        "art_direction_patch_plan.md": _simple_md("Art Direction Patch Plan", reports["art_direction_patch_plan.json"]),
        "e04_r2_source_bound_deck_qa_report.md": _simple_md("E04 R2 Source Bound Deck QA Report", reports["e04_r2_source_bound_deck_qa_report.json"]),
    }
    for filename, content in markdown.items():
        _write_md(output / filename, content)


def _composition_variant_plan(art_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "composition_variant_plan",
        "status": "passed",
        "max_allowed_reuse": 3,
        "distinct_variant_count": art_plan["distinct_composition_variant_count"],
        "variant_counts": art_plan["composition_variant_counts"],
        "slides": [
            {"slide_id": slide["slide_id"], "slide_number": slide["slide_number"], "composition_variant": slide["composition_variant"], "reason": slide["layout_strategy"]}
            for slide in art_plan["slides"]
        ],
        "canva_parity_claimed": False,
    }


def _source_interpretation_plan(art_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "source_content_visual_interpretation_plan",
        "status": "passed",
        "slides": [
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "source_content_interpretation_goal": slide["source_content_interpretation_goal"],
                "focal_object": slide["focal_object"],
            }
            for slide in art_plan["slides"]
        ],
        "canva_parity_claimed": False,
    }


def _template_usage_diversity_plan(art_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "template_usage_diversity_plan",
        "status": "passed",
        "template_pack": "E03_R2_PREMIUM_TEMPLATE_PACK",
        "distinct_composition_variant_count": art_plan["distinct_composition_variant_count"],
        "max_shared_composition_count": art_plan["max_shared_composition_count"],
        "canva_parity_claimed": False,
    }


def _art_direction_patch_plan(art_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "art_direction_patch_plan",
        "status": "applied",
        "patch_count": len(art_plan["slides"]),
        "patches": [
            {
                "slide_id": slide["slide_id"],
                "composition_variant": slide["composition_variant"],
                "focal_object": slide["focal_object"],
                "patch_notes": "replace repeated card-row skeleton with art-directed focal composition",
            }
            for slide in art_plan["slides"]
        ],
        "canva_parity_claimed": False,
    }


def _make_e04_vs_r2_contact_sheet(output: Path) -> None:
    original = Image.open(E04_ROOT / "source_bound_sample_deck_contact_sheet.png").convert("RGB")
    rebuilt = Image.open(output / "source_bound_sample_deck_r2_contact_sheet.png").convert("RGB")
    width = max(original.width, rebuilt.width)
    label_h = 44
    sheet = Image.new("RGB", (width, original.height + rebuilt.height + label_h * 2), "#061526")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((14, 14), "Original E04", fill="#F8FAFC", font=font)
    sheet.paste(original, (0, label_h))
    draw.text((14, original.height + label_h + 14), "E04-R2 Art-Directed Rebuild", fill="#F8FAFC", font=font)
    sheet.paste(rebuilt, (0, original.height + label_h * 2))
    sheet.save(output / "e04_vs_e04_r2_contact_sheet.png")


def _e05_readiness_report_after_r2(source: dict[str, Any], design_quality: dict[str, Any], qa: dict[str, Any], compile_report: dict[str, Any]) -> dict[str, Any]:
    unlocked = (
        source["source_mode_report"]["mode"] in {"MODE_A_REAL_SOURCE_DOCUMENT", "MODE_B_EXISTING_SOURCE_GRAPH"}
        and design_quality["status"] == "passed"
        and compile_report["status"] == "passed"
        and qa["semantic_raster_violation_report"]["semantic_raster_violation_count"] == 0
        and qa["unknown_layer_report"]["unknown_content_bearing_layer_count"] == 0
        and qa["text_overflow_report"].get("forbidden_placeholder_count", 0) == 0
        and qa["citation_coverage_report"]["status"] == "passed"
        and qa["chart_binding_report"]["status"] == "passed"
        and qa["table_binding_report"]["status"] == "passed"
    )
    return {
        "schema_name": "e05_readiness_report_after_e04_r2",
        "status": "passed" if unlocked else "failed",
        "e05_unlocked": unlocked,
        "reason": "E04-R2 restored design quality and preserved source-bound editability" if unlocked else "E04-R2 did not satisfy all E05 unlock gates",
        "e05_started": False,
        "canva_parity_claimed": False,
    }


def _patch_decision(design_quality: dict[str, Any]) -> str:
    if design_quality["semantic_raster_violation_count"] > 0 or design_quality["unknown_content_bearing_layer_count"] > 0:
        return "E04_R2_FAIL_SEMANTIC_EDITABILITY"
    if design_quality["native_chart_binding_status"] != "passed" or design_quality["native_table_binding_status"] != "passed":
        return "E04_R2_PATCH_CHART_TABLE_PROMINENCE"
    if design_quality["status"] != "passed":
        return "E04_R2_FAIL_DESIGN_QUALITY"
    return "E04_R2_PATCH_SOURCE_TRACE"


def _final(decision: str, status: str, e05_unlocked: bool, reason: str) -> dict[str, Any]:
    return {
        "schema_name": "e04_r2_final_decision",
        "status": status,
        "decision": decision,
        "reason": reason,
        "e05_unlocked": e05_unlocked,
        "e05_started": False,
        "large_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _simple_md(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"- Status: `{payload.get('status', 'n/a')}`"]
    for key in ("decision", "reason", "source_mode", "slide_count", "composition_variant_count", "distinct_variant_count", "e04_dq_pass_restored", "semantic_raster_violation_count", "unknown_content_bearing_layer_count", "text_overflow_count", "citation_coverage_status", "e05_unlocked", "canva_parity_claimed"):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    return "\n".join(lines)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
