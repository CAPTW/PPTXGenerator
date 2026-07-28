"""PromptSet E01H high-fidelity hybrid Canva+ single-reference gate."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts.run_e01x_self_describing_ps_layer_integration import protected_report, protected_snapshot, run_protect_check
from src.presentation_agent.magic_layer.e01h_canva_plus_hybrid_gate import (
    build_canva_plus_hybrid_gate_report,
    build_semantic_editability_reports,
    canva_plus_hybrid_gate_report_markdown,
)
from src.presentation_agent.magic_layer.e01h_hybrid_candidate_compiler import (
    audit_hybrid_pptx,
    build_editable_candidate_spec,
    build_inventory_ledgers,
    compile_hybrid_candidate,
    render_hybrid_candidate_preview,
)
from src.presentation_agent.magic_layer.e01h_hybrid_orchestrator import build_e01h_conversion_payload
from src.presentation_agent.magic_layer.e01h_reference_analyzer import (
    build_canva_benchmark_boundary_report,
    build_reference_asset_manifest,
    build_reference_visual_richness_report,
)
from src.presentation_agent.magic_layer.e01h_scaleout_override import (
    build_e04_r3_scaleout_override,
    build_e05_readiness_after_e01h,
    e05_readiness_markdown,
    scaleout_override_markdown,
)
from src.presentation_agent.magic_layer.e01h_text_first_lock import text_first_lock_report_markdown
from src.presentation_agent.magic_layer.e01h_visual_fidelity_gate import (
    build_visual_fidelity_report,
    build_visual_richness_retention_report,
    visual_fidelity_report_markdown,
    visual_richness_retention_report_markdown,
)
from src.presentation_agent.magic_layer.ps_layer_validator import (
    validate_layer_cleanup,
    validate_layer_records,
    validate_masks,
    validate_smart_objects,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
REFERENCE = REPO_ROOT / "design_runs/benchmarks/canva_magic_layer/assets/reference_image.png"
BENCHMARK_ROOT = REPO_ROOT / "design_runs/benchmarks/canva_magic_layer"
E01P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_photoshop_layer_protocol"
E01PV_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_v_cross_ledger_validator"
E04_R3_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_r3_editorial_integrity_production_polish"
E04_DQ_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e04_dq_source_bound_design_quality_gate"
E01H_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01h_high_fidelity_hybrid_canva_plus_single_reference"


def run_e01h_high_fidelity_hybrid_canva_plus_gate(output_dir: str | Path = E01H_ROOT) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    if not run_protect_check():
        final = _final("E01H_FAIL_PROTECTED_ARTIFACTS", "failed", False, False, "protected artifact precheck failed")
        _write_json(output / "e01h_final_decision.json", final)
        return final

    prerequisites = _validate_prerequisites()
    if prerequisites["status"] != "passed":
        final = _final("E01H_PATCH_OBJECT_GRAPH_EXTRACTION", "failed", False, False, "required inputs missing")
        _write_json(output / "e01h_final_decision.json", final)
        _write_json(output / "e01h_manifest.json", _manifest(output, final, prerequisites))
        return final

    reference_copy = output / "reference_image.png"
    shutil.copy2(REFERENCE, reference_copy)
    payload = build_e01h_conversion_payload(REFERENCE)
    reference_manifest = build_reference_asset_manifest(payload["reference_analysis_report"], reference_copy)
    reference_richness = build_reference_visual_richness_report(payload["reference_analysis_report"])
    canva_boundary = build_canva_benchmark_boundary_report(BENCHMARK_ROOT)
    scaleout_override = build_e04_r3_scaleout_override(E04_R3_ROOT)

    _write_reference_artifacts(output, payload, reference_manifest, reference_richness, canva_boundary)
    _write_hybrid_layer_artifacts(output, payload)
    _write_planning_artifacts(output, payload)

    compile_report = compile_hybrid_candidate(payload, output)
    render_manifest = render_hybrid_candidate_preview(payload, output)
    inventory = audit_hybrid_pptx(output / "editable_candidate.pptx")
    ledgers = build_inventory_ledgers(inventory, payload)
    _write_candidate_artifacts(output, payload, compile_report, render_manifest, inventory, ledgers)

    visual_fidelity = build_visual_fidelity_report(reference_copy, output / "rendered_candidate.png")
    visual_richness_retention = build_visual_richness_retention_report(payload, visual_fidelity)
    semantic_reports = build_semantic_editability_reports(payload, inventory)
    _write_qa_artifacts(output, visual_fidelity, visual_richness_retention, semantic_reports)

    protected_after = protected_snapshot()
    protected_md, protected_ok = protected_report(protected_before, protected_after)
    gate_report = build_canva_plus_hybrid_gate_report(
        candidate_exists=(output / "editable_candidate.pptx").exists(),
        candidate_rendered=(output / "rendered_candidate.png").exists(),
        visual_richness=visual_richness_retention,
        payload=payload,
        semantic_reports=semantic_reports,
        protected_artifacts_unchanged=protected_ok,
    )
    e02h_readiness = _e02h_readiness(gate_report)
    e05_readiness = build_e05_readiness_after_e01h(gate_report)
    decision = e02h_readiness["decision"]
    final = _final(decision, "passed" if gate_report["status"] == "passed" else "failed", e02h_readiness["e02h_unlocked"], False, e02h_readiness["reason"])

    protect_post = run_protect_check()
    protected_md += f"\n\n- npm protect precheck: `passed`\n- npm protect postcheck: `{'passed' if protect_post else 'failed'}`\n"
    if not protected_ok or not protect_post:
        final = _final("E01H_FAIL_PROTECTED_ARTIFACTS", "failed", False, False, "protected artifact postcheck failed")
        gate_report["status"] = "failed"
        gate_report["checks"]["protected_artifacts_unchanged"] = False
        e02h_readiness["status"] = "failed"
        e02h_readiness["e02h_unlocked"] = False

    conversion_report = _conversion_report(final, payload, compile_report, render_manifest, visual_fidelity, visual_richness_retention, gate_report)
    manifest = _manifest(output, final, prerequisites)
    for filename, payload_obj in {
        "e04_r3_scaleout_override.json": scaleout_override,
        "e05_readiness_after_e01h.json": e05_readiness,
        "canva_plus_hybrid_gate_report.json": gate_report,
        "e02h_readiness_report.json": e02h_readiness,
        "e01h_conversion_report.json": conversion_report,
        "e01h_manifest.json": manifest,
        "e01h_final_decision.json": final,
        "patch_queue_e01h.json": _patch_queue(final),
    }.items():
        _write_json(output / filename, payload_obj)
    for filename, content in {
        "e04_r3_scaleout_override.md": scaleout_override_markdown(scaleout_override),
        "e05_readiness_after_e01h.md": e05_readiness_markdown(e05_readiness),
        "canva_plus_hybrid_gate_report.md": canva_plus_hybrid_gate_report_markdown(gate_report),
        "e02h_readiness_report.md": _simple_md("E02H Readiness Report", e02h_readiness),
        "e01h_conversion_report.md": _simple_md("E01H Conversion Report", conversion_report),
        "e01h_final_decision.md": _simple_md("E01H Final Decision", final),
        "patch_queue_e01h.md": _simple_md("Patch Queue E01H", _patch_queue(final)),
        "protected_artifact_check_report.md": protected_md,
    }.items():
        _write_md(output / filename, content)
    return final


def _validate_prerequisites() -> dict[str, Any]:
    required = [REFERENCE, E01P_ROOT, E01PV_ROOT, E04_R3_ROOT, E04_DQ_ROOT]
    missing = [path.as_posix() for path in required if not path.exists()]
    return {"schema_name": "e01h_prerequisite_report", "status": "passed" if not missing else "failed", "missing": missing, "canva_parity_claimed": False}


def _write_reference_artifacts(output: Path, payload: dict[str, Any], reference_manifest: dict[str, Any], richness: dict[str, Any], canva_boundary: dict[str, Any]) -> None:
    _write_json(output / "reference_asset_manifest.json", reference_manifest)
    _write_json(output / "reference_analysis_report.json", payload["reference_analysis_report"])
    _write_md(output / "reference_analysis_report.md", _simple_md("Reference Analysis Report", payload["reference_analysis_report"]))
    _write_json(output / "reference_visual_richness_report.json", richness)
    _write_md(output / "reference_visual_richness_report.md", _simple_md("Reference Visual Richness Report", richness))
    _write_json(output / "canva_benchmark_boundary_report.json", canva_boundary)
    _write_md(output / "canva_benchmark_boundary_report.md", _simple_md("Canva Benchmark Boundary Report", canva_boundary))


def _write_hybrid_layer_artifacts(output: Path, payload: dict[str, Any]) -> None:
    keys = [
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
    ]
    for key in keys:
        _write_json(output / f"{key}.json", payload[key])


def _write_planning_artifacts(output: Path, payload: dict[str, Any]) -> None:
    _write_json(output / "text_first_lock_report.json", payload["text_first_lock_report"])
    _write_md(output / "text_first_lock_report.md", text_first_lock_report_markdown(payload["text_first_lock_report"]))
    for key in [
        "semantic_native_reconstruction_plan",
        "visual_backplate_reconstruction_plan",
        "native_component_promotion_report",
        "raster_policy_report_hybrid",
        "reference_crop_policy_report",
    ]:
        _write_json(output / f"{key}.json", payload[key])
    _write_json(
        output / "hybrid_candidate_compile_plan.json",
        {
            "schema_name": "hybrid_candidate_compile_plan",
            "status": "passed",
            "rules": ["semantic layers native", "backplates bounded", "full reference background forbidden"],
            "canva_parity_claimed": False,
        },
    )


def _write_candidate_artifacts(output: Path, payload: dict[str, Any], compile_report: dict[str, Any], render_manifest: dict[str, Any], inventory: dict[str, Any], ledgers: dict[str, dict[str, Any]]) -> None:
    _write_json(output / "editable_candidate_spec.json", build_editable_candidate_spec(payload))
    _write_json(output / "render_manifest.json", render_manifest)
    ledgers_dir = output / "ledgers"
    for filename, ledger in ledgers.items():
        _write_json(ledgers_dir / f"{filename}.json", ledger)


def _write_qa_artifacts(output: Path, visual_fidelity: dict[str, Any], visual_richness: dict[str, Any], semantic_reports: dict[str, dict[str, Any]]) -> None:
    _write_json(output / "visual_fidelity_report.json", visual_fidelity)
    _write_md(output / "visual_fidelity_report.md", visual_fidelity_report_markdown(visual_fidelity))
    _write_json(output / "visual_richness_retention_report.json", visual_richness)
    _write_md(output / "visual_richness_retention_report.md", visual_richness_retention_report_markdown(visual_richness))
    for key, report in semantic_reports.items():
        _write_json(output / f"{key}.json", report)


def _e02h_readiness(gate_report: dict[str, Any]) -> dict[str, Any]:
    passed = gate_report["status"] == "passed"
    return {
        "schema_name": "e02h_readiness_report",
        "status": "passed" if passed else "failed",
        "decision": "E01H_PASS_START_E02H_4CORE_HYBRID_CANVA_PLUS" if passed else "E01H_PATCH_RENDER_FIDELITY",
        "e02h_unlocked": passed,
        "e05_unlocked": False,
        "reason": "E01H single-reference hybrid conversion passed; unlock E02H only." if passed else "E01H hybrid gate did not pass.",
        "canva_parity_claimed": False,
    }


def _conversion_report(final: dict[str, Any], payload: dict[str, Any], compile_report: dict[str, Any], render_manifest: dict[str, Any], visual_fidelity: dict[str, Any], visual_richness: dict[str, Any], gate_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e01h_conversion_report",
        "status": final["status"],
        "decision": final["decision"],
        "reference_width": payload["reference_analysis_report"]["width"],
        "reference_height": payload["reference_analysis_report"]["height"],
        "object_graph_node_count": len(payload["object_graph_v2"]["nodes"]),
        "semantic_native_layer_count": payload["semantic_native_layer_manifest"]["semantic_layer_count"],
        "visual_backplate_count": payload["hybrid_visual_backplate_manifest"]["backplate_count"],
        "editable_candidate_pptx": compile_report["pptx_path"],
        "rendered_candidate": render_manifest["rendered_candidate"],
        "composition_similarity_score": visual_fidelity["composition_similarity_score"],
        "visual_richness_status": visual_richness["status"],
        "hybrid_gate_status": gate_report["status"],
        "e02h_unlocked": final["e02h_unlocked"],
        "e05_unlocked": False,
        "canva_parity_claimed": False,
    }


def _final(decision: str, status: str, e02h_unlocked: bool, e05_unlocked: bool, reason: str) -> dict[str, Any]:
    return {
        "schema_name": "e01h_final_decision",
        "status": status,
        "decision": decision,
        "reason": reason,
        "e02h_unlocked": e02h_unlocked,
        "e05_unlocked": e05_unlocked,
        "e05_started": False,
        "large_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
        "canva_parity_scope": "single_reference_e01h_pass" if status == "passed" else "not_claimed",
    }


def _manifest(output: Path, final: dict[str, Any], prerequisites: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e01h_manifest",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "output_dir": _rel(output),
        "reference_input": _rel(REFERENCE),
        "prerequisite_status": prerequisites["status"],
        "final_decision": final["decision"],
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "e05_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def _patch_queue(final: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "patch_queue_e01h",
        "status": "empty" if final["status"] == "passed" else "open",
        "patch_count": 0 if final["status"] == "passed" else 1,
        "patches": [] if final["status"] == "passed" else [{"decision": final["decision"], "reason": final["reason"]}],
        "canva_parity_claimed": False,
    }


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
        "width",
        "height",
        "visual_density_estimate",
        "likely_semantic_object_count",
        "likely_visual_backplate_candidate_count",
        "visual_backplate_count",
        "semantic_native_layer_count",
        "composition_similarity_score",
        "e02h_unlocked",
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
