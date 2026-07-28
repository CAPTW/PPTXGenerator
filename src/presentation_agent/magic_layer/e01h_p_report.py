"""PromptSet E01H-P semantic icon and micro-component fidelity patch."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.run_e01x_self_describing_ps_layer_integration import protected_report, protected_snapshot, run_protect_check
from src.presentation_agent.magic_layer.e01h_canva_plus_hybrid_gate import build_semantic_editability_reports
from src.presentation_agent.magic_layer.e01h_p_candidate_patcher import build_patched_candidate
from src.presentation_agent.magic_layer.e01h_p_gate import (
    build_e02h_readiness_after_e01h_p,
    build_patched_canva_plus_hybrid_gate_report,
    e02h_readiness_after_e01h_p_markdown,
    patched_canva_plus_hybrid_gate_report_markdown,
)
from src.presentation_agent.magic_layer.e01h_p_icon_inventory import (
    build_semantic_icon_inventory_report,
    semantic_icon_inventory_report_markdown,
)
from src.presentation_agent.magic_layer.e01h_p_icon_vectorizer import (
    build_icon_vectorization_plan,
    build_semantic_icon_svg_manifest,
    icon_vectorization_plan_markdown,
    semantic_icon_svg_manifest_markdown,
)
from src.presentation_agent.magic_layer.e01h_p_micro_component_detector import (
    build_checklist_component_report,
    build_micro_component_inventory_report,
    build_micro_label_fidelity_report,
    build_safety_bar_component_report,
    build_thumbnail_region_fidelity_report,
    micro_component_inventory_report_markdown,
    simple_component_report_markdown,
)
from src.presentation_agent.magic_layer.e01h_p_micro_component_gate import (
    build_micro_component_fidelity_gate_report,
    micro_component_fidelity_gate_report_markdown,
)
from src.presentation_agent.magic_layer.e01h_p_semantic_icon_gate import (
    build_patched_semantic_icon_vector_report,
    build_semantic_icon_fidelity_report,
    semantic_icon_fidelity_report_markdown,
)
from src.presentation_agent.magic_layer.e01h_visual_fidelity_gate import (
    build_visual_fidelity_report,
    build_visual_richness_retention_report,
    visual_fidelity_report_markdown,
    visual_richness_retention_report_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
E01H_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01h_high_fidelity_hybrid_canva_plus_single_reference"
E01H_P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01h_p_semantic_icon_microcomponent_fidelity_patch"
E01P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_photoshop_layer_protocol"
E01PV_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_v_cross_ledger_validator"


def run_e01h_semantic_icon_microcomponent_fidelity_patch(output_dir: str | Path = E01H_P_ROOT) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    if not run_protect_check():
        final = _final("E01H_P_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact precheck failed")
        _write_json(output / "e01h_p_final_decision.json", final)
        return final

    prerequisites = _validate_inputs()
    if prerequisites["status"] != "passed":
        final = _final("E01H_P_PATCH_ICON_VECTORIZATION", "failed", False, "required E01H/E01P-V inputs missing")
        _write_json(output / "e01h_p_manifest.json", _manifest(output, final, prerequisites))
        _write_json(output / "e01h_p_final_decision.json", final)
        _write_md(output / "e01h_p_final_decision.md", _simple_md("E01H-P Final Decision", final))
        return final

    icon_inventory = build_semantic_icon_inventory_report(E01H_ROOT)
    micro_inventory = build_micro_component_inventory_report(E01H_ROOT)
    vector_plan = build_icon_vectorization_plan(icon_inventory)
    svg_manifest = build_semantic_icon_svg_manifest(vector_plan)
    semantic_icon_fidelity = build_semantic_icon_fidelity_report(icon_inventory, vector_plan)
    micro_label = build_micro_label_fidelity_report(micro_inventory)
    thumbnail = build_thumbnail_region_fidelity_report(micro_inventory)
    safety_bar = build_safety_bar_component_report(micro_inventory)
    checklist = build_checklist_component_report(micro_inventory)
    micro_gate = build_micro_component_fidelity_gate_report(micro_inventory)

    patch = build_patched_candidate(E01H_ROOT, vector_plan, output)
    _write_patch_artifacts(output, patch)

    reference = E01H_ROOT / "reference_image.png"
    visual_fidelity = build_visual_fidelity_report(reference, output / "patched_rendered_candidate.png")
    visual_richness = build_visual_richness_retention_report(patch["patched_payload"], visual_fidelity)
    inventory = patch["ledgers"]["patched_pptx_inventory"]
    semantic_reports = _prefix_semantic_reports(build_semantic_editability_reports(patch["patched_payload"], inventory))
    icon_vector_report = build_patched_semantic_icon_vector_report(inventory, vector_plan)
    unknown_report = _patched_unknown_report(patch["patched_payload"])

    protected_after = protected_snapshot()
    protected_md, protected_ok = protected_report(protected_before, protected_after)
    patched_gate = build_patched_canva_plus_hybrid_gate_report(
        candidate_exists=(output / "patched_editable_candidate.pptx").exists(),
        candidate_rendered=(output / "patched_rendered_candidate.png").exists(),
        visual_richness=visual_richness,
        payload=patch["patched_payload"],
        semantic_reports=_unprefix_semantic_reports(semantic_reports),
        icon_report=icon_vector_report,
        micro_component_report=micro_gate,
        protected_artifacts_unchanged=protected_ok,
    )
    e02h_readiness = build_e02h_readiness_after_e01h_p(
        patched_gate,
        icon_vector_report,
        _unprefix_semantic_reports(semantic_reports),
        unknown_report,
    )
    final = _final(e02h_readiness["decision"], "passed" if patched_gate["status"] == "passed" else "failed", e02h_readiness["e02h_unlocked"], e02h_readiness["reason"])
    protect_post = run_protect_check()
    protected_md += f"\n\n- npm protect precheck: `passed`\n- npm protect postcheck: `{'passed' if protect_post else 'failed'}`\n"
    if not protected_ok or not protect_post:
        final = _final("E01H_P_FAIL_PROTECTED_ARTIFACTS", "failed", False, "protected artifact postcheck failed")
        patched_gate["status"] = "failed"
        patched_gate["checks"]["protected_artifacts_unchanged"] = False
        e02h_readiness["status"] = "failed"
        e02h_readiness["decision"] = "E01H_P_FAIL_PROTECTED_ARTIFACTS"
        e02h_readiness["e02h_unlocked"] = False

    patch_report = _patch_report(final, icon_inventory, semantic_icon_fidelity, icon_vector_report, micro_gate, visual_richness, patched_gate)
    manifest = _manifest(output, final, prerequisites)
    _write_reports(
        output,
        manifest,
        patch_report,
        final,
        icon_inventory,
        semantic_icon_fidelity,
        micro_inventory,
        micro_label,
        thumbnail,
        safety_bar,
        checklist,
        vector_plan,
        svg_manifest,
        visual_fidelity,
        visual_richness,
        semantic_reports,
        icon_vector_report,
        micro_gate,
        patched_gate,
        e02h_readiness,
        unknown_report,
        protected_md,
    )
    return final


def _validate_inputs() -> dict[str, Any]:
    required = [
        E01H_ROOT / "reference_image.png",
        E01H_ROOT / "editable_candidate.pptx",
        E01H_ROOT / "editable_candidate_spec.json",
        E01H_ROOT / "rendered_candidate.png",
        E01H_ROOT / "object_graph_v2.json",
        E01H_ROOT / "layer_manifest_v5.json",
        E01H_ROOT / "semantic_slot_graph.json",
        E01H_ROOT / "visual_layer_graph.json",
        E01H_ROOT / "hybrid_visual_backplate_manifest.json",
        E01H_ROOT / "semantic_native_layer_manifest.json",
        E01H_ROOT / "visual_backplate_raster_allowlist.json",
        E01H_ROOT / "semantic_native_reconstruction_plan.json",
        E01H_ROOT / "visual_richness_retention_report.json",
        E01H_ROOT / "semantic_editability_ledger.json",
        E01H_ROOT / "semantic_raster_violation_report.json",
        E01H_ROOT / "canva_plus_hybrid_gate_report.json",
        E01H_ROOT / "e02h_readiness_report.json",
        E01H_ROOT / "e04_r3_scaleout_override.json",
        E01P_ROOT,
        E01PV_ROOT,
    ]
    missing = [path.as_posix() for path in required if not path.exists()]
    return {"schema_name": "e01h_p_prerequisite_report", "status": "passed" if not missing else "failed", "missing": missing, "canva_parity_claimed": False}


def _write_patch_artifacts(output: Path, patch: dict[str, Any]) -> None:
    for filename, payload in {
        "patched_object_graph_v2.json": patch["patched_object_graph_v2"],
        "patched_layer_manifest_v5.json": patch["patched_layer_manifest_v5"],
        "patched_semantic_slot_graph.json": patch["patched_semantic_slot_graph"],
        "patched_semantic_native_reconstruction_plan.json": patch["patched_semantic_native_reconstruction_plan"],
        "patched_editable_candidate_spec.json": patch["patched_editable_candidate_spec"],
        "patched_render_manifest.json": patch["patched_render_manifest"],
    }.items():
        _write_json(output / filename, payload)
    ledgers_dir = output / "ledgers"
    for key, ledger in patch["ledgers"].items():
        _write_json(ledgers_dir / f"{key}.json", ledger)


def _write_reports(
    output: Path,
    manifest: dict[str, Any],
    patch_report: dict[str, Any],
    final: dict[str, Any],
    icon_inventory: dict[str, Any],
    semantic_icon_fidelity: dict[str, Any],
    micro_inventory: dict[str, Any],
    micro_label: dict[str, Any],
    thumbnail: dict[str, Any],
    safety_bar: dict[str, Any],
    checklist: dict[str, Any],
    vector_plan: dict[str, Any],
    svg_manifest: dict[str, Any],
    visual_fidelity: dict[str, Any],
    visual_richness: dict[str, Any],
    semantic_reports: dict[str, dict[str, Any]],
    icon_vector_report: dict[str, Any],
    micro_gate: dict[str, Any],
    patched_gate: dict[str, Any],
    e02h_readiness: dict[str, Any],
    unknown_report: dict[str, Any],
    protected_md: str,
) -> None:
    json_payloads: dict[str, Any] = {
        "e01h_p_manifest.json": manifest,
        "e01h_p_patch_report.json": patch_report,
        "e01h_p_final_decision.json": final,
        "semantic_icon_inventory_report.json": icon_inventory,
        "semantic_icon_fidelity_report.json": semantic_icon_fidelity,
        "micro_component_inventory_report.json": micro_inventory,
        "micro_label_fidelity_report.json": micro_label,
        "thumbnail_region_fidelity_report.json": thumbnail,
        "safety_bar_component_report.json": safety_bar,
        "checklist_component_report.json": checklist,
        "icon_vectorization_plan.json": vector_plan,
        "semantic_icon_svg_manifest.json": svg_manifest,
        "patched_visual_fidelity_report.json": _rename_schema(visual_fidelity, "patched_visual_fidelity_report"),
        "patched_visual_richness_retention_report.json": _rename_schema(visual_richness, "patched_visual_richness_retention_report"),
        "patched_semantic_icon_vector_report.json": icon_vector_report,
        "patched_micro_component_fidelity_gate_report.json": micro_gate,
        "patched_canva_plus_hybrid_gate_report.json": patched_gate,
        "e02h_readiness_after_e01h_p.json": e02h_readiness,
        "patched_unknown_layer_report.json": unknown_report,
        "patch_queue_e01h_p.json": _patch_queue(final),
    }
    for key, report in semantic_reports.items():
        json_payloads[f"{key}.json"] = report
    for filename, payload in json_payloads.items():
        _write_json(output / filename, payload)

    md_payloads = {
        "e01h_p_patch_report.md": _simple_md("E01H-P Patch Report", patch_report),
        "e01h_p_final_decision.md": _simple_md("E01H-P Final Decision", final),
        "semantic_icon_inventory_report.md": semantic_icon_inventory_report_markdown(icon_inventory),
        "semantic_icon_fidelity_report.md": semantic_icon_fidelity_report_markdown(semantic_icon_fidelity),
        "micro_component_inventory_report.md": micro_component_inventory_report_markdown(micro_inventory),
        "micro_label_fidelity_report.md": simple_component_report_markdown("Micro-Label Fidelity Report", micro_label),
        "thumbnail_region_fidelity_report.md": simple_component_report_markdown("Thumbnail Region Fidelity Report", thumbnail),
        "safety_bar_component_report.md": simple_component_report_markdown("Safety-Bar Component Report", safety_bar),
        "checklist_component_report.md": simple_component_report_markdown("Checklist Component Report", checklist),
        "icon_vectorization_plan.md": icon_vectorization_plan_markdown(vector_plan),
        "semantic_icon_svg_manifest.md": semantic_icon_svg_manifest_markdown(svg_manifest),
        "patched_visual_fidelity_report.md": visual_fidelity_report_markdown(visual_fidelity).replace("# Visual Fidelity Report", "# Patched Visual Fidelity Report"),
        "patched_visual_richness_retention_report.md": visual_richness_retention_report_markdown(visual_richness).replace("# Visual Richness Retention Report", "# Patched Visual Richness Retention Report"),
        "patched_canva_plus_hybrid_gate_report.md": patched_canva_plus_hybrid_gate_report_markdown(patched_gate),
        "e02h_readiness_after_e01h_p.md": e02h_readiness_after_e01h_p_markdown(e02h_readiness),
        "patch_queue_e01h_p.md": _simple_md("Patch Queue E01H-P", _patch_queue(final)),
        "protected_artifact_check_report.md": protected_md,
    }
    for filename, content in md_payloads.items():
        _write_md(output / filename, content)


def _prefix_semantic_reports(reports: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f"patched_{key}": _rename_schema(value, f"patched_{key}") for key, value in reports.items()}


def _unprefix_semantic_reports(reports: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {key.replace("patched_", "", 1): value for key, value in reports.items()}


def _patched_unknown_report(payload: dict[str, Any]) -> dict[str, Any]:
    report = dict(payload["unknown_layer_report"])
    report["schema_name"] = "patched_unknown_layer_report"
    return report


def _patch_report(
    final: dict[str, Any],
    icon_inventory: dict[str, Any],
    semantic_icon_fidelity: dict[str, Any],
    icon_vector_report: dict[str, Any],
    micro_gate: dict[str, Any],
    visual_richness: dict[str, Any],
    patched_gate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_name": "e01h_p_patch_report",
        "status": final["status"],
        "decision": final["decision"],
        "baseline_icon_inventory_status": icon_inventory["status"],
        "planned_icon_fidelity_status": semantic_icon_fidelity["status"],
        "patched_icon_vector_status": icon_vector_report["status"],
        "semantic_icon_vector_coverage": icon_vector_report["semantic_icon_vector_coverage"],
        "required_semantic_icon_missing_count": icon_vector_report["semantic_icon_missing_count"],
        "semantic_icon_raster_violation_count": icon_vector_report["semantic_icon_raster_violation_count"],
        "micro_component_gate_status": micro_gate["status"],
        "visual_richness_status": visual_richness["status"],
        "patched_canva_plus_gate_status": patched_gate["status"],
        "e02h_unlocked": final["e02h_unlocked"],
        "e05_locked": True,
        "canva_parity_claimed": False,
    }


def _manifest(output: Path, final: dict[str, Any], prerequisites: dict[str, Any]) -> dict[str, Any]:
    original_final = _read_json(E01H_ROOT / "e01h_final_decision.json")
    original_e02h = _read_json(E01H_ROOT / "e02h_readiness_report.json")
    return {
        "schema_name": "e01h_p_manifest",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "output_dir": _rel(output),
        "input_e01h_dir": _rel(E01H_ROOT),
        "prerequisite_status": prerequisites["status"],
        "original_e01h_decision": original_final.get("decision"),
        "original_e02h_unlocked": bool(original_e02h.get("e02h_unlocked")),
        "e01h_p_reason_for_soft_block": "semantic_icon_microcomponent_fidelity_not_proven",
        "e02h_unlocked_before_patch": False,
        "e02h_unlocked_after_patch": final["e02h_unlocked"],
        "e05_locked": True,
        "e05_started": False,
        "large_deck_generated": False,
        "source_bound_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def _final(decision: str, status: str, e02h_unlocked: bool, reason: str) -> dict[str, Any]:
    return {
        "schema_name": "e01h_p_final_decision",
        "status": status,
        "decision": decision,
        "reason": reason,
        "e02h_unlocked": e02h_unlocked,
        "e05_unlocked": False,
        "e05_locked": True,
        "e02h_started": False,
        "e05_started": False,
        "large_deck_generated": False,
        "source_bound_deck_generated": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
        "canva_parity_scope": "single_reference_e01h_p_pass" if status == "passed" else "not_claimed",
    }


def _patch_queue(final: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "patch_queue_e01h_p",
        "status": "empty" if final["status"] == "passed" else "open",
        "patch_count": 0 if final["status"] == "passed" else 1,
        "patches": [] if final["status"] == "passed" else [{"decision": final["decision"], "reason": final["reason"]}],
        "canva_parity_claimed": False,
    }


def _rename_schema(report: dict[str, Any], schema_name: str) -> dict[str, Any]:
    patched = dict(report)
    patched["schema_name"] = schema_name
    return patched


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
        "semantic_icon_vector_coverage",
        "required_semantic_icon_missing_count",
        "semantic_icon_raster_violation_count",
        "micro_component_gate_status",
        "visual_richness_status",
        "patched_canva_plus_gate_status",
        "e02h_unlocked",
        "e05_locked",
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
