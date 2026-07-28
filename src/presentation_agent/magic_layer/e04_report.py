"""Orchestrator and reports for the E04 source-bound small deck gate."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.run_e01x_self_describing_ps_layer_integration import protected_report, protected_snapshot, run_protect_check
from src.presentation_agent.magic_layer.e04_deck_compiler import compile_source_bound_deck
from src.presentation_agent.magic_layer.e04_layout_selector import build_layout_selector_accuracy_report, select_layouts
from src.presentation_agent.magic_layer.e04_presentation_planner import (
    build_narrative_outline,
    build_presentation_plan,
    build_slide_type_distribution,
)
from src.presentation_agent.magic_layer.e04_slide_blueprint_builder import (
    build_claim_evidence_coverage_report,
    build_slide_blueprints,
    build_source_to_slide_trace_ledger,
)
from src.presentation_agent.magic_layer.e04_slot_binder import bind_slots
from src.presentation_agent.magic_layer.e04_source_bound_qa import run_source_bound_qa
from src.presentation_agent.magic_layer.e04_source_ingest import DEFAULT_SOURCE_PATH, build_source_artifacts


REPO_ROOT = Path(__file__).resolve().parents[3]
E03_R2_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e03_r2_premium_visual_rebuild"
E04_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_source_bound_small_deck_with_e03_r2_pack"
E03_R2_DECISION = "E03_R2_PASS_PREMIUM_READY_FOR_E04_SOURCE_BOUND_SMALL_DECK"


def run_e04_source_bound_small_deck(
    output_dir: str | Path = E04_ROOT,
    source_path: str | Path = DEFAULT_SOURCE_PATH,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    protect_pre = run_protect_check()
    if not protect_pre:
        final = _final_decision("E04_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact precheck failed")
        _write_json(output / "e04_final_decision.json", final)
        _write_md(output / "e04_final_decision.md", _simple_md("E04 Final Decision", final))
        return final

    readiness = _validate_e03_r2_readiness()
    if readiness["status"] != "passed":
        final = _final_decision("E04_PATCH_E03_R2_PREREQUISITES", "failed", False, "E03-R2 readiness failed")
        _write_json(output / "e04_source_bound_small_deck_report.json", readiness)
        _write_md(output / "e04_source_bound_small_deck_report.md", _simple_md("E04 Source Bound Small Deck Report", readiness))
        _write_json(output / "e04_final_decision.json", final)
        _write_md(output / "e04_final_decision.md", _simple_md("E04 Final Decision", final))
        return final

    source = build_source_artifacts(source_path)
    plan = build_presentation_plan(source["source_document_graph_v1"])
    narrative = build_narrative_outline(plan)
    blueprints = build_slide_blueprints(plan, source)
    trace_ledger = build_source_to_slide_trace_ledger(blueprints)
    slide_type_distribution = build_slide_type_distribution(plan)
    claim_coverage = build_claim_evidence_coverage_report(blueprints)
    layout_selection = select_layouts(blueprints)
    layout_accuracy = build_layout_selector_accuracy_report(layout_selection, blueprints)
    binding = bind_slots(blueprints, layout_selection, source)
    compile_report = compile_source_bound_deck(binding, output)
    qa = run_source_bound_qa(output / "source_bound_sample_deck_12_16.pptx", binding, source)

    artifacts: dict[str, Any] = {
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
        "source_to_slide_trace_ledger.json": trace_ledger,
        "slide_type_distribution_report.json": slide_type_distribution,
        "claim_evidence_coverage_report.json": claim_coverage,
        "layout_selection_report.json": layout_selection,
        "template_binding_plan.json": _binding_plan(binding),
        "slot_binding_ledger.json": binding["slot_binding_ledger"],
        "component_binding_ledger.json": binding["component_binding_ledger"],
        "overflow_patch_plan.json": binding["overflow_patch_plan"],
        "source_footer_binding_ledger.json": binding["source_footer_binding_ledger"],
        "source_bound_sample_deck_render_manifest.json": compile_report["render_manifest"],
        "source_bound_deck_qa_report.json": qa["source_bound_deck_qa_report"],
        "semantic_editability_ledger.json": qa["semantic_editability_ledger"],
        "semantic_raster_violation_report.json": qa["semantic_raster_violation_report"],
        "unknown_layer_report.json": qa["unknown_layer_report"],
        "text_overflow_report.json": qa["text_overflow_report"],
        "chart_binding_report.json": qa["chart_binding_report"],
        "table_binding_report.json": qa["table_binding_report"],
        "citation_coverage_report.json": qa["citation_coverage_report"],
        "layout_selector_accuracy_report.json": layout_accuracy,
        "visual_consistency_report.json": qa["visual_consistency_report"],
    }
    for filename, payload in artifacts.items():
        _write_json(output / filename, payload)

    markdown_reports = {
        "source_mode_report.md": source["source_mode_report"],
        "layout_selection_report.md": layout_selection,
        "template_binding_plan.md": _binding_plan(binding),
        "source_bound_deck_qa_report.md": qa["source_bound_deck_qa_report"],
    }
    for filename, payload in markdown_reports.items():
        _write_md(output / filename, _simple_md(filename.removesuffix(".md").replace("_", " ").title(), payload))

    report = _aggregate_report(source, plan, blueprints, layout_selection, binding, compile_report, qa, layout_accuracy, readiness)
    final = _final_decision(
        "E04_PASS_SOURCE_BOUND_SMALL_DECK_WITH_E03_R2_PACK" if report["status"] == "passed" else "E04_PATCH_SOURCE_BOUND_SMALL_DECK",
        report["status"],
        report["status"] == "passed",
        report["reason"],
    )
    manifest = _manifest(output, source, report, final)
    protected_after = protected_snapshot()
    protected_md, protected_ok = protected_report(protected_before, protected_after)
    protect_post = run_protect_check()
    protected_md += f"\n\n- npm protect precheck: `passed`\n- npm protect postcheck: `{'passed' if protect_post else 'failed'}`\n"
    if not protected_ok or not protect_post:
        final = _final_decision("E04_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact postcheck failed")
        manifest["final_decision"] = final["decision"]
        manifest["protected_artifacts_unchanged"] = False
        report["status"] = "failed"
        report["protected_artifact_status"] = "failed"
    else:
        report["protected_artifact_status"] = "passed"

    _write_json(output / "e04_manifest.json", manifest)
    _write_json(output / "e04_source_bound_small_deck_report.json", report)
    _write_md(output / "e04_source_bound_small_deck_report.md", _simple_md("E04 Source Bound Small Deck Report", report))
    _write_json(output / "e04_final_decision.json", final)
    _write_md(output / "e04_final_decision.md", _simple_md("E04 Final Decision", final))
    _write_md(output / "protected_artifact_check_report.md", protected_md)
    _write_md(output / "e04_canva_boundary_note.md", "# E04 Canva Boundary Note\n\nCanva parity is not claimed. This gate validates a local editable PPTX source-bound sample deck only.\n")
    return final


def _validate_e03_r2_readiness() -> dict[str, Any]:
    required = [
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
    missing = [item for item in required if not (E03_R2_ROOT / item).exists()]
    decision_payload = _read_json(E03_R2_ROOT / "e03_r2_final_decision.json") if not missing else {}
    decision_ok = decision_payload.get("decision") == E03_R2_DECISION
    return {
        "schema_name": "e04_e03_r2_readiness_report",
        "status": "passed" if not missing and decision_ok else "failed",
        "e03_r2_root": _rel(E03_R2_ROOT),
        "missing_required_files": missing,
        "e03_r2_decision": decision_payload.get("decision"),
        "expected_decision": E03_R2_DECISION,
        "template_pack_modified": False,
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


def _aggregate_report(
    source: dict[str, Any],
    plan: dict[str, Any],
    blueprints: dict[str, Any],
    layout_selection: dict[str, Any],
    binding: dict[str, Any],
    compile_report: dict[str, Any],
    qa: dict[str, Any],
    layout_accuracy: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    required_statuses = [
        readiness["status"],
        source["source_parse_quality_report"]["status"],
        blueprints["status"],
        layout_selection["status"],
        binding["status"],
        compile_report["status"],
        qa["source_bound_deck_qa_report"]["status"],
        layout_accuracy["status"],
    ]
    passed = all(status == "passed" for status in required_statuses)
    return {
        "schema_name": "e04_source_bound_small_deck_report",
        "status": "passed" if passed else "failed",
        "reason": "source-bound editable sample deck passed" if passed else "one or more E04 gates failed",
        "source_mode": source["source_mode_report"]["mode"],
        "real_source_production_claimed": source["source_mode_report"]["real_source_production_claimed"],
        "slide_count": plan["slide_count_target"],
        "compiled_slide_count": compile_report["slide_count"],
        "layout_selection_status": layout_selection["status"],
        "slot_binding_status": binding["status"],
        "chart_binding_status": qa["chart_binding_report"]["status"],
        "table_binding_status": qa["table_binding_report"]["status"],
        "citation_coverage_status": qa["citation_coverage_report"]["status"],
        "semantic_editability_status": qa["semantic_editability_ledger"]["status"],
        "semantic_raster_violation_count": qa["semantic_raster_violation_report"]["semantic_raster_violation_count"],
        "unknown_content_bearing_layer_count": qa["unknown_layer_report"]["unknown_content_bearing_layer_count"],
        "source_bound_deck_generated": True,
        "large_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
        "protected_artifact_status": "pending_postcheck",
    }


def _manifest(output: Path, source: dict[str, Any], report: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e04_manifest",
        "generated_at": _now(),
        "output_dir": _rel(output),
        "input_template_pack": _rel(E03_R2_ROOT / "editable_template_pack_r2.pptx"),
        "source_mode": source["source_mode_report"]["mode"],
        "source_path": source["source_mode_report"].get("source_path"),
        "source_bound_deck_path": _rel(output / "source_bound_sample_deck_12_16.pptx"),
        "slide_count": report["slide_count"],
        "final_decision": final["decision"],
        "e04_status": final["status"],
        "source_bound_deck_generated": True,
        "large_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
        "protected_artifacts_unchanged": True,
    }


def _final_decision(decision: str, status: str, source_bound_small_deck_passed: bool, reason: str) -> dict[str, Any]:
    return {
        "schema_name": "e04_final_decision",
        "status": status,
        "decision": decision,
        "reason": reason,
        "source_bound_small_deck_passed": source_bound_small_deck_passed,
        "large_deck_started": False,
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
    if payload.get("decision"):
        lines.append(f"- Decision: `{payload['decision']}`")
    if payload.get("reason"):
        lines.append(f"- Reason: {payload['reason']}")
    for key in (
        "source_mode",
        "slide_count",
        "compiled_slide_count",
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


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
