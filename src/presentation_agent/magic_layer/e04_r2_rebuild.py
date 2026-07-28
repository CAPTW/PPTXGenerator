"""Isolated E04-R2 source-bound deck art-direction rebuild."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.run_e01x_self_describing_ps_layer_integration import protected_report, protected_snapshot, run_protect_check
from src.presentation_agent.magic_layer.e04_design_quality_gate import (
    build_object_complexity_vs_design_quality_report,
    build_source_content_visual_interpretation_report,
)
from src.presentation_agent.magic_layer.e04_focal_object_gate import build_focal_object_report
from src.presentation_agent.magic_layer.e04_layout_selector import build_layout_selector_accuracy_report, select_layouts
from src.presentation_agent.magic_layer.e04_presentation_planner import build_narrative_outline, build_presentation_plan, build_slide_type_distribution
from src.presentation_agent.magic_layer.e04_r2_art_direction import build_e04_r2_art_direction_plan
from src.presentation_agent.magic_layer.e04_r2_deck_compiler import compile_e04_r2_art_directed_deck
from src.presentation_agent.magic_layer.e04_skeleton_similarity import build_skeleton_similarity_report
from src.presentation_agent.magic_layer.e04_slide_blueprint_builder import (
    build_claim_evidence_coverage_report,
    build_slide_blueprints,
    build_source_to_slide_trace_ledger,
)
from src.presentation_agent.magic_layer.e04_slide_rhythm import build_slide_rhythm_report
from src.presentation_agent.magic_layer.e04_slot_binder import bind_slots
from src.presentation_agent.magic_layer.e04_source_bound_qa import run_source_bound_qa
from src.presentation_agent.magic_layer.e04_source_ingest import DEFAULT_SOURCE_PATH, build_source_artifacts
from src.presentation_agent.magic_layer.e04_visual_hierarchy_gate import build_visual_hierarchy_report


REPO_ROOT = Path(__file__).resolve().parents[3]
E04_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_source_bound_small_deck_with_e03_r2_pack"
E04_DQ_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_dq_source_bound_design_quality_gate"
E04_R2_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_r2_source_bound_art_direction_rebuild"


def run_e04_r2_art_direction_rebuild(output_dir: str | Path = E04_R2_ROOT) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    if not run_protect_check():
        final = _final("E04_R2_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact precheck failed")
        _write_json(output / "e04_r2_final_decision.json", final)
        return final

    prerequisites = _validate_prerequisites()
    source = build_source_artifacts(DEFAULT_SOURCE_PATH)
    plan = build_presentation_plan(source["source_document_graph_v1"])
    narrative = build_narrative_outline(plan)
    blueprints = build_slide_blueprints(plan, source)
    art_direction = build_e04_r2_art_direction_plan(E04_ROOT)
    layout_selection = select_layouts(blueprints)
    binding = bind_slots(blueprints, layout_selection, source)
    compile_report = compile_e04_r2_art_directed_deck(binding, art_direction, output)
    qa = run_source_bound_qa(output / "source_bound_sample_deck_r2_12_16.pptx", binding, source)

    artifacts: dict[str, Any] = {
        "e04_r2_art_direction_plan.json": art_direction,
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
        "layout_selection_report.json": layout_selection,
        "layout_selector_accuracy_report.json": build_layout_selector_accuracy_report(layout_selection, blueprints),
        "template_binding_plan.json": _binding_plan(binding),
        "slot_binding_ledger.json": binding["slot_binding_ledger"],
        "component_binding_ledger.json": binding["component_binding_ledger"],
        "overflow_patch_plan.json": binding["overflow_patch_plan"],
        "source_footer_binding_ledger.json": binding["source_footer_binding_ledger"],
        "source_bound_sample_deck_r2_render_manifest.json": compile_report["render_manifest"],
        "source_bound_deck_qa_report.json": qa["source_bound_deck_qa_report"],
        "semantic_editability_ledger.json": qa["semantic_editability_ledger"],
        "semantic_raster_violation_report.json": qa["semantic_raster_violation_report"],
        "unknown_layer_report.json": qa["unknown_layer_report"],
        "text_overflow_report.json": qa["text_overflow_report"],
        "chart_binding_report.json": qa["chart_binding_report"],
        "table_binding_report.json": qa["table_binding_report"],
        "citation_coverage_report.json": qa["citation_coverage_report"],
        "visual_consistency_report.json": qa["visual_consistency_report"],
    }
    for filename, payload in artifacts.items():
        _write_json(output / filename, payload)
    _write_md(output / "e04_r2_art_direction_plan.md", _simple_md("E04 R2 Art Direction Plan", art_direction))
    _write_md(output / "layout_selection_report.md", _simple_md("E04 R2 Layout Selection Report", layout_selection))
    _write_md(output / "template_binding_plan.md", _simple_md("E04 R2 Template Binding Plan", artifacts["template_binding_plan.json"]))
    _write_md(output / "source_bound_deck_qa_report.md", _simple_md("E04 R2 Source-Bound Deck QA Report", qa["source_bound_deck_qa_report"]))

    skeleton = build_skeleton_similarity_report(output)
    rhythm = build_slide_rhythm_report(output, skeleton)
    focal = build_focal_object_report(output)
    hierarchy = build_visual_hierarchy_report(output)
    complexity = build_object_complexity_vs_design_quality_report(output, hierarchy)
    interpretation = build_source_content_visual_interpretation_report(output)
    dq_pass = all(report["status"] == "passed" for report in (skeleton, rhythm, focal, hierarchy, complexity, interpretation))
    quality_report = {
        "schema_name": "e04_r2_design_quality_gate_report",
        "status": "passed" if dq_pass else "failed",
        "skeleton_similarity_status": skeleton["status"],
        "slide_rhythm_status": rhythm["status"],
        "focal_object_status": focal["status"],
        "visual_hierarchy_status": hierarchy["status"],
        "object_complexity_vs_design_quality_status": complexity["status"],
        "source_content_visual_interpretation_status": interpretation["status"],
        "canva_parity_claimed": False,
    }
    for filename, payload in {
        "skeleton_similarity_report.json": skeleton,
        "slide_rhythm_report.json": rhythm,
        "focal_object_report.json": focal,
        "visual_hierarchy_report.json": hierarchy,
        "object_complexity_vs_design_quality_report.json": complexity,
        "source_content_visual_interpretation_report.json": interpretation,
        "e04_r2_design_quality_gate_report.json": quality_report,
    }.items():
        _write_json(output / filename, payload)
        _write_md(output / filename.replace(".json", ".md"), _simple_md(filename.removesuffix(".json").replace("_", " ").title(), payload))

    status_ok = (
        prerequisites["status"] == "passed"
        and compile_report["status"] == "passed"
        and qa["source_bound_deck_qa_report"]["status"] == "passed"
        and qa["semantic_raster_violation_report"]["semantic_raster_violation_count"] == 0
        and qa["unknown_layer_report"]["unknown_content_bearing_layer_count"] == 0
        and dq_pass
    )
    final = _final(
        "E04_R2_PASS_READY_FOR_E05_SOURCE_BOUND_SMALL_DECK" if status_ok else "E04_R2_PATCH_ART_DIRECTION_REQUIRED",
        "passed" if status_ok else "failed",
        bool(status_ok),
        "art-directed source-bound rebuild passed" if status_ok else "art-directed rebuild still needs patching",
    )
    manifest = {
        "schema_name": "e04_r2_manifest",
        "generated_at": _now(),
        "output_dir": _rel(output),
        "input_e04_root": _rel(E04_ROOT),
        "input_e04_dq_root": _rel(E04_DQ_ROOT),
        "source_bound_deck_path": _rel(output / "source_bound_sample_deck_r2_12_16.pptx"),
        "contact_sheet_path": _rel(output / "source_bound_sample_deck_r2_contact_sheet.png"),
        "slide_count": compile_report["slide_count"],
        "final_decision": final["decision"],
        "e05_started": False,
        "large_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }
    report = {
        "schema_name": "e04_r2_art_direction_rebuild_report",
        "status": final["status"],
        "decision": final["decision"],
        "source_mode": source["source_mode_report"]["mode"],
        "slide_count": compile_report["slide_count"],
        "composition_signature_count": compile_report["composition_signature_count"],
        "native_chart_count": qa["chart_binding_report"]["native_chart_count"],
        "native_table_count": qa["table_binding_report"]["native_table_count"],
        "semantic_raster_violation_count": qa["semantic_raster_violation_report"]["semantic_raster_violation_count"],
        "unknown_content_bearing_layer_count": qa["unknown_layer_report"]["unknown_content_bearing_layer_count"],
        "citation_coverage_status": qa["citation_coverage_report"]["status"],
        "design_quality_status": quality_report["status"],
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
        report["status"] = "failed"
        report["decision"] = final["decision"]
        manifest["final_decision"] = final["decision"]

    _write_json(output / "e04_r2_prerequisite_report.json", prerequisites)
    _write_json(output / "e04_r2_manifest.json", manifest)
    _write_json(output / "e04_r2_art_direction_rebuild_report.json", report)
    _write_md(output / "e04_r2_art_direction_rebuild_report.md", _simple_md("E04 R2 Art Direction Rebuild Report", report))
    _write_json(output / "e04_r2_final_decision.json", final)
    _write_md(output / "e04_r2_final_decision.md", _simple_md("E04 R2 Final Decision", final))
    _write_md(output / "protected_artifact_check_report.md", protected_md)
    return final


def _validate_prerequisites() -> dict[str, Any]:
    required_e04 = [
        "source_bound_sample_deck_12_16.pptx",
        "e04_final_decision.json",
        "slide_blueprint_v1.json",
        "semantic_editability_ledger.json",
        "citation_coverage_report.json",
    ]
    missing_e04 = [item for item in required_e04 if not (E04_ROOT / item).exists()]
    dq = _read_json(E04_DQ_ROOT / "e04_design_quality_override.json") if (E04_DQ_ROOT / "e04_design_quality_override.json").exists() else {}
    return {
        "schema_name": "e04_r2_prerequisite_report",
        "status": "passed" if not missing_e04 and dq.get("decision") == "E04_DQ_PATCH_DECK_ART_DIRECTION_REQUIRED" else "failed",
        "missing_e04_inputs": missing_e04,
        "e04_dq_decision": dq.get("decision"),
        "expected_e04_dq_decision": "E04_DQ_PATCH_DECK_ART_DIRECTION_REQUIRED",
        "canva_parity_claimed": False,
    }


def _binding_plan(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "template_binding_plan",
        "status": binding["status"],
        "selected_template_pack": binding["selected_template_pack"],
        "slide_count": binding["slide_count"],
        "slides": [
            {
                "slide_id": slide["slide_id"],
                "slide_number": slide["slide_number"],
                "archetype_id": slide["archetype_id"],
                "layout_id": slide["layout_id"],
                "slot_count": len(slide["slots"]),
                "footer_citation_ids": slide["footer"]["citation_ids"],
                "chart_bound": bool(slide.get("chart_data")),
                "table_bound": bool(slide.get("table_data")),
            }
            for slide in binding["slides"]
        ],
        "canva_parity_claimed": False,
    }


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
    for key in (
        "decision",
        "reason",
        "source_mode",
        "slide_count",
        "composition_signature_count",
        "max_shared_composition_ratio",
        "semantic_raster_violation_count",
        "unknown_content_bearing_layer_count",
        "design_quality_status",
        "e05_unlocked",
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


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
