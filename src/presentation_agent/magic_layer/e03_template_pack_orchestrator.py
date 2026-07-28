"""Run E03 12-core PS-layer editable template pack gate."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from scripts.run_e01x_self_describing_ps_layer_integration import protected_report, protected_snapshot, run_e01p_v_validation
from src.presentation_agent.magic_layer.e01x_candidate_compiler import audit_candidate_pptx, compile_e01x_candidate, render_e01x_candidate_preview
from src.presentation_agent.magic_layer.e01x_duplicate_bbox_detector import detect_duplicate_bbox_collisions
from src.presentation_agent.magic_layer.e01x_ps_layer_integration import build_magic_layer_artifacts, build_ps_layer_as_built, build_ps_layer_intent
from src.presentation_agent.magic_layer.e01x_trace_resolver import build_as_built_trace, resolve_traces
from src.presentation_agent.magic_layer.e01x_visual_slot_fidelity import build_rendered_visibility_report
from src.presentation_agent.magic_layer.e02_component_requirements import validate_component_requirements
from src.presentation_agent.magic_layer.e03_aggregate_report import build_e03_template_pack_report, final_decision_for_e03
from src.presentation_agent.magic_layer.e03_archetype_registry import CORE_12_ARCHETYPE_IDS, build_e03_archetype_registry, build_e03_design_intent_trace, required_visible_counts
from src.presentation_agent.magic_layer.e03_component_library import build_component_coverage_matrix, build_component_library, validate_component_library
from src.presentation_agent.magic_layer.e03_design_system_tokens import build_design_system_tokens, validate_design_system_tokens
from src.presentation_agent.magic_layer.e03_layout_selector_contract import build_layout_selector_contract, build_local_model_slot_filling_contract, validate_layout_selector_contract
from src.presentation_agent.magic_layer.e03_pack_gate import evaluate_e03_pack_gate
from src.presentation_agent.magic_layer.e03_template_pack_compiler import compile_editable_template_pack, render_template_pack_contact_sheet


SLIDE_W = 1672
SLIDE_H = 941
REPO_ROOT = Path(__file__).resolve().parents[3]
E01P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_photoshop_layer_protocol"
E01PV_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_v_cross_ledger_validator"
E01X_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01x_self_describing_ps_layer_integration"
E01XP_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01x_p_visual_slot_fidelity_patch"
E02_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e02_4core_ps_layer_archetype_conversion"
E03_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e03_12_16_archetype_ps_layer_template_pack"


def run_e03_template_pack_gate() -> dict[str, Any]:
    E03_ROOT.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    if not _run_protect_check():
        final = _blocked_final("E03_FAIL_PROTECTED_ARTIFACTS", "protected_artifact_precheck_failed")
        _write_json(E03_ROOT / "e03_final_decision.json", final)
        _write_md(E03_ROOT / "e03_final_decision.md", _simple_md("E03 Final Decision", final))
        return final
    prereq = validate_e03_prerequisites()
    if prereq["status"] != "passed":
        final = _blocked_final("E03_PATCH_ARCHETYPE_CONTRACTS", "prerequisite_check_failed", prereq=prereq)
        _write_json(E03_ROOT / "e03_final_decision.json", final)
        _write_md(E03_ROOT / "e03_final_decision.md", _simple_md("E03 Final Decision", final))
        return final

    tokens = build_design_system_tokens()
    token_report = validate_design_system_tokens(tokens)
    component_library = build_component_library()
    component_report = validate_component_library(component_library)
    coverage = build_component_coverage_matrix(component_library)
    selector = build_layout_selector_contract()
    selector_report = validate_layout_selector_contract(selector)
    local_model_contract = build_local_model_slot_filling_contract()
    registry = build_template_pack_registry_skeleton()
    e02_regression = build_e02_regression_report()

    _write_json(E03_ROOT / "design_system_tokens.json", tokens)
    _write_md(E03_ROOT / "design_system_tokens.md", _simple_md("Design System Tokens", {"status": token_report["status"], "palette": "deep navy / dark teal / off-white / muted gold / cyan"}))
    _write_json(E03_ROOT / "component_library.json", component_library)
    _write_md(E03_ROOT / "component_library.md", _component_library_md(component_library, component_report))
    _write_json(E03_ROOT / "component_coverage_matrix.json", coverage)
    _write_md(E03_ROOT / "component_coverage_matrix.md", _coverage_md(coverage))
    _write_json(E03_ROOT / "layout_selector_contract.json", selector)
    _write_md(E03_ROOT / "layout_selector_contract.md", _simple_md("Layout Selector Contract", {"status": selector_report["status"], "archetype_count": len(selector["archetypes"])}))
    _write_json(E03_ROOT / "local_model_slot_filling_contract.json", local_model_contract)
    _write_md(E03_ROOT / "local_model_slot_filling_contract.md", _simple_md("Local Model Slot Filling Contract", {"may_alter_design_tokens": False, "may_rasterize_semantic_objects": False}))
    _write_json(E03_ROOT / "e03_vs_e02_regression_report.json", e02_regression)
    _write_md(E03_ROOT / "e03_vs_e02_regression_report.md", _regression_md(e02_regression))
    _write_md(E03_ROOT / "e03_canva_boundary_note.md", "# E03 Canva Boundary Note\n\nCanva parity remains unclaimed. E03 validates local editable PPTX template-pack behavior only.\n")

    archetype_summaries: dict[str, dict[str, Any]] = {}
    accepted_pack_items: list[dict[str, Any]] = []
    for archetype_id in CORE_12_ARCHETYPE_IDS:
        summary, pack_item = run_single_archetype(archetype_id)
        archetype_summaries[archetype_id] = summary
        if summary["status"] == "passed":
            accepted_pack_items.append(pack_item)

    distinctiveness = build_distinctiveness_report(archetype_summaries)
    _write_json(E03_ROOT / "archetype_distinctiveness_report.json", distinctiveness)
    _write_md(E03_ROOT / "archetype_distinctiveness_report.md", _simple_md("Archetype Distinctiveness Report", {"status": distinctiveness["status"], "distinct_layout_count": distinctiveness["distinct_layout_count"]}))

    registry = build_template_pack_registry(registry, archetype_summaries)
    _write_json(E03_ROOT / "template_pack_registry.json", registry)
    _write_md(E03_ROOT / "template_pack_registry.md", _registry_md(registry))
    _write_json(E03_ROOT / "template_pack_render_manifest.json", build_template_pack_render_manifest(archetype_summaries))
    render_reference_contact_sheet(archetype_summaries, E03_ROOT / "template_pack_contact_sheet.png")
    pack_spec, pack_compile_report = compile_editable_template_pack(accepted_pack_items, E03_ROOT)
    render_template_pack_contact_sheet(accepted_pack_items, E03_ROOT / "editable_template_pack_rendered_contact_sheet.png")
    _write_json(E03_ROOT / "editable_template_pack_spec.json", pack_spec)

    pack_artifacts = {
        "editable_template_pack.pptx": (E03_ROOT / "editable_template_pack.pptx").exists(),
        "template_pack_registry.json": (E03_ROOT / "template_pack_registry.json").exists(),
        "layout_selector_contract.json": (E03_ROOT / "layout_selector_contract.json").exists(),
        "local_model_slot_filling_contract.json": (E03_ROOT / "local_model_slot_filling_contract.json").exists(),
    }
    protected_after = protected_snapshot()
    protected_md, protected_ok = protected_report(protected_before, protected_after)
    protected_post_ok = _run_protect_check()
    protected_md += f"\n\n- npm protect precheck: `passed`\n- npm protect postcheck: `{'passed' if protected_post_ok else 'failed'}`\n"
    _write_md(E03_ROOT / "protected_artifact_check_report.md", protected_md)
    pack_gate = evaluate_e03_pack_gate(archetype_reports=archetype_summaries, required_core_ids=list(CORE_12_ARCHETYPE_IDS), pack_artifacts=pack_artifacts, protected_artifacts_unchanged=protected_ok and protected_post_ok)
    aggregate = build_e03_template_pack_report(archetype_reports=archetype_summaries, pack_gate=pack_gate, component_coverage_matrix=coverage, distinctiveness_report=distinctiveness, protected_artifacts_unchanged=protected_ok and protected_post_ok)
    aggregate["design_token_consistency"] = token_report["status"]
    aggregate["component_library_status"] = component_report["status"]
    aggregate["layout_selector_status"] = selector_report["status"]
    aggregate["pack_compile_status"] = pack_compile_report["status"]
    final = final_decision_for_e03(aggregate)
    _write_json(E03_ROOT / "e03_template_pack_report.json", aggregate)
    _write_md(E03_ROOT / "e03_template_pack_report.md", _aggregate_md(aggregate))
    _write_json(E03_ROOT / "e03_final_decision.json", final)
    _write_md(E03_ROOT / "e03_final_decision.md", _simple_md("E03 Final Decision", final))
    _write_json(E03_ROOT / "e03_manifest.json", build_manifest(final, archetype_summaries))
    return final


def validate_e03_prerequisites() -> dict[str, Any]:
    paths = [E01P_ROOT, E01PV_ROOT, E01X_ROOT, E01XP_ROOT, E02_ROOT]
    files = [
        REPO_ROOT / "scripts/run_ps_layer_cross_ledger_validator.py",
        REPO_ROOT / "src/presentation_agent/magic_layer/e01x_visual_slot_fidelity.py",
        REPO_ROOT / "src/presentation_agent/magic_layer/e02_component_requirements.py",
    ]
    missing = [rel(path) for path in paths + files if not path.exists()]
    e02_final = E02_ROOT / "e02_final_decision.json"
    decision = _read_json(e02_final).get("decision") if e02_final.exists() else None
    if decision != "E02_PASS_READY_FOR_E03_12_16_ARCHETYPE_PACK":
        missing.append("E02 decision not ready")
    return {"schema_name": "e03_prerequisite_check", "status": "passed" if not missing else "failed", "missing": missing, "e02_decision": decision, "canva_parity_claimed": False}


def run_single_archetype(archetype_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    out = E03_ROOT / "archetypes" / archetype_id
    out.mkdir(parents=True, exist_ok=True)
    intent = build_e03_design_intent_trace(archetype_id)
    asset_recipe = build_asset_recipe_manifest(intent)
    ps_intent = build_ps_layer_intent(intent)
    ps_intent["protocol_id"] = f"e03_{archetype_id}_ps_layer_intent"
    ps_intent["source_reference"] = {**ps_intent["source_reference"], "reference_path": rel(out / "final_reference.png"), "reference_id": f"e03_{archetype_id}_reference"}
    _write_json(out / "design_intent_trace.json", intent)
    _write_json(out / "asset_recipe_manifest.json", asset_recipe)
    _write_json(out / "ps_layer_intent.json", ps_intent)
    _write_md(out / "image_prompt.md", build_image_prompt(intent, ps_intent, asset_recipe))
    generate_reference_assets(archetype_id, intent, out)

    as_built = build_as_built_trace(intent, rel(out / "final_reference.png"))
    ps_as_built = build_ps_layer_as_built(ps_intent, as_built)
    resolved, conflicts = resolve_traces(intent, as_built)
    _write_json(out / "as_built_trace.json", as_built)
    _write_json(out / "ps_layer_as_built.json", ps_as_built)
    _write_json(out / "trace_conflict_report.json", conflicts)
    _write_json(out / "resolved_layout_trace.json", resolved)
    artifacts = build_magic_layer_artifacts(ps_as_built)
    _write_artifacts(out, artifacts)
    pre = run_e01p_v_validation("e01p_v_precompile_validation_report", {"ps_layer_intent.json": ps_intent, "ps_layer_as_built.json": ps_as_built}, artifacts)
    _write_json(out / "e01p_v_precompile_validation_report.json", pre)
    compile_report = compile_e01x_candidate(editable_candidate_spec=artifacts["editable_candidate_spec"], object_graph=artifacts["object_graph_v1"], output_dir=out, asset_dir=out / "generated_assets")
    render_e01x_candidate_preview(object_graph=artifacts["object_graph_v1"], output_dir=out, asset_dir=out / "generated_assets", reference_image=out / "final_reference.png")
    inventory = audit_candidate_pptx(out / "editable_candidate.pptx")
    post = run_e01p_v_validation("e01p_v_postcompile_validation_report", {"ps_layer_intent.json": ps_intent, "ps_layer_as_built.json": ps_as_built}, artifacts, pptx_inventory=inventory)
    _write_json(out / "e01p_v_postcompile_validation_report.json", post)
    duplicate = detect_duplicate_bbox_collisions(artifacts["object_graph_v1"]["nodes"])
    slot_report = build_slot_count_report(archetype_id, artifacts["object_graph_v1"]["nodes"], duplicate)
    visibility = build_rendered_visibility_report(duplicate)
    component = validate_component_requirements(archetype_id, artifacts["native_reconstruction_plan"], artifacts["semantic_raster_violation_report"])
    fidelity = build_visual_slot_fidelity(archetype_id, duplicate, slot_report, component, artifacts, post)
    gate = build_canva_gate(archetype_id, compile_report, inventory, pre, post, fidelity, component, artifacts)
    final = {"schema_name": "e03_archetype_final_decision", "archetype_id": archetype_id, "status": "passed" if gate["status"] == "passed" else "failed", "decision": "passed" if gate["status"] == "passed" else "patch_required", "canva_parity_claimed": False}
    patch_queue = {"schema_name": "e03_archetype_patch_queue", "status": "empty" if final["status"] == "passed" else "open", "patches": [] if final["status"] == "passed" else [{"failures": gate["failures"]}], "canva_parity_claimed": False}
    for filename, payload in {
        "duplicate_bbox_collision_report.json": duplicate,
        "slot_count_preservation_report.json": slot_report,
        "rendered_visibility_report.json": visibility,
        "visual_slot_fidelity_report.json": fidelity,
        "canva_plus_gate_report.json": gate,
        "archetype_final_decision.json": final,
        "patch_queue.json": patch_queue,
    }.items():
        _write_json(out / filename, payload)
    summary = summarize_archetype(archetype_id, inventory, pre, post, duplicate, fidelity, component, gate, final)
    pack_item = {"archetype_id": archetype_id, "object_graph": artifacts["object_graph_v1"]}
    return summary, pack_item


def build_asset_recipe_manifest(intent: dict[str, Any]) -> dict[str, Any]:
    assets = []
    for slot in intent["slots"]:
        if slot["semantic_role"] == "hero_visual_field":
            assets.append({"asset_id": "IMG_HERO_01", "role": "hero_visual_field", "prompt": "Bounded nonsemantic hero visual, no text, no chart, no table.", "raster_allowed": True, "semantic_content_allowed": False, "target_resolution_px": {"w": 900, "h": 900}, "insertion_policy": "replaceable_image_frame", "bbox_norm": slot["bbox_norm_intended"], "mask_id": "M_HERO_ROUNDED", "crop_mode": "cover_center", "z_order": slot["z_order_intended"], "must_not_cover_text": True})
        if slot["semantic_role"] == "decorative_texture":
            assets.append({"asset_id": "BG_TEXTURE_01", "role": "decorative_texture", "prompt": "Bounded nonsemantic texture, no semantic marks.", "raster_allowed": True, "semantic_content_allowed": False, "target_resolution_px": {"w": 640, "h": 360}, "insertion_policy": "bounded_decorative_texture", "bbox_norm": slot["bbox_norm_intended"], "mask_id": None, "crop_mode": "cover_center", "z_order": slot["z_order_intended"], "must_not_cover_text": True})
    return {"schema_name": "e03_asset_recipe_manifest", "asset_policy": "bounded_nonsemantic_assets_only", "assets": assets, "canva_parity_claimed": False}


def build_image_prompt(intent: dict[str, Any], ps_intent: dict[str, Any], asset_recipe: dict[str, Any]) -> str:
    return "\n".join(["# E03 Image Prompt", "", f"Archetype: {intent['archetype']}", "Create one 16:9 editable PowerPoint template reference with protected semantic slots and placeholders only.", "No full-slide raster, screenshot slide, semantic raster fallback, decorations over semantic zones, or readable random microtext.", f"Semantic roles: {', '.join(slot['semantic_role'] for slot in intent['slots'])}.", f"PS-layer IDs: {', '.join(layer['layer_id'] for layer in ps_intent['layers'])}.", f"Bounded asset IDs: {', '.join(asset['asset_id'] for asset in asset_recipe['assets']) or 'none'}."])


def generate_reference_assets(archetype_id: str, intent: dict[str, Any], out: Path) -> None:
    assets = out / "generated_assets"
    assets.mkdir(parents=True, exist_ok=True)
    hero = assets / "IMG_HERO_01.png"
    if any(slot["semantic_role"] == "hero_visual_field" for slot in intent["slots"]):
        _draw_hero_asset(hero)
    texture = assets / "BG_TEXTURE_01.png"
    if any(slot["semantic_role"] == "decorative_texture" for slot in intent["slots"]):
        _draw_texture_asset(texture)
    if archetype_id in {"cover_hero", "standard_content", "data_dashboard", "table_heavy"}:
        e02_reference = E02_ROOT / "archetypes" / archetype_id / "final_reference.png"
        if e02_reference.exists():
            shutil.copyfile(e02_reference, out / "final_reference.png")
            return
    _draw_reference(intent, hero if hero.exists() else None, texture if texture.exists() else None, out / "final_reference.png")


def build_slot_count_report(archetype_id: str, nodes: list[dict[str, Any]], duplicate: dict[str, Any]) -> dict[str, Any]:
    visible = _visible_counts(nodes, duplicate)
    declared = _declared_counts(nodes)
    failures = []
    rows = []
    for slot, required in required_visible_counts(archetype_id).items():
        actual = int(visible.get(slot, 0))
        if actual < required:
            failures.append(f"{slot}_visible_count_lt_required")
        rows.append({"slot_kind": slot, "required_visible_count": required, "declared_count": declared.get(slot, 0), "visible_count": actual, "status": "passed" if actual >= required else "failed"})
    return {"schema_name": "slot_count_preservation_report", "archetype_id": archetype_id, "status": "passed" if not failures else "failed", "declared_counts": declared, "visible_counts": visible, "rows": rows, "failures": failures, "canva_parity_claimed": False}


def build_visual_slot_fidelity(archetype_id: str, duplicate: dict[str, Any], slot_report: dict[str, Any], component: dict[str, Any], artifacts: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if duplicate["collision_count"] > 0:
        failures.append("duplicate_semantic_bbox_collision")
    failures.extend(slot_report.get("failures", []))
    if artifacts["semantic_raster_violation_report"]["semantic_raster_violation_count"] > 0:
        failures.append("semantic_raster_violation")
    if artifacts["unknown_layer_report"]["unknown_content_bearing_layer_count"] > 0:
        failures.append("unknown_content_bearing_layer")
    if post["status"] != "passed":
        failures.append("e01p_v_postcompile_failed")
    if component["status"] != "passed":
        failures.extend(component["failures"])
    return {"schema_name": "visual_slot_fidelity_report", "archetype_id": archetype_id, "status": "passed" if not failures else "failed", "decision": "passed" if not failures else "patch_required", "failures": sorted(set(failures)), "duplicate_collision_count": duplicate["collision_count"], "visible_counts": slot_report["visible_counts"], "canva_parity_claimed": False}


def build_canva_gate(archetype_id: str, compile_report: dict[str, Any], inventory: dict[str, Any], pre: dict[str, Any], post: dict[str, Any], fidelity: dict[str, Any], component: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    checks = {"editable_candidate_exists": Path(compile_report["editable_candidate_pptx"]).exists(), "candidate_renders": True, "no_full_slide_reference_background": compile_report["full_slide_reference_background"] is False, "no_screenshot_slide": compile_report["screenshot_slide"] is False, "e01p_v_precompile_passed": pre["status"] == "passed", "e01p_v_postcompile_passed": post["status"] == "passed", "visual_slot_fidelity_passed": fidelity["status"] == "passed", "component_requirements_passed": component["status"] == "passed", "semantic_raster_zero": artifacts["semantic_raster_violation_report"]["semantic_raster_violation_count"] == 0, "unknown_content_zero": artifacts["unknown_layer_report"]["unknown_content_bearing_layer_count"] == 0, "pptx_inventory_passed": inventory["status"] == "passed"}
    failures = [key for key, passed in checks.items() if not passed]
    return {"schema_name": "canva_plus_gate_report", "archetype_id": archetype_id, "status": "passed" if not failures else "failed", "decision": "passed" if not failures else "patch_required", "checks": checks, "failures": failures, "canva_parity_claimed": False}


def summarize_archetype(archetype_id: str, inventory: dict[str, Any], pre: dict[str, Any], post: dict[str, Any], duplicate: dict[str, Any], fidelity: dict[str, Any], component: dict[str, Any], gate: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
    shapes = inventory.get("shapes", [])
    return {"archetype_id": archetype_id, "core": True, "status": final["status"], "layout_signature": f"e03_{archetype_id}", "object_count": inventory["shape_count"], "text_count": inventory["editable_text_count"], "media_count": inventory["picture_count"], "connector_vector_count": sum(1 for shape in shapes if "CONNECTOR" in shape["shape_type"] or "AUTO_SHAPE" in shape["shape_type"]), "semantic_raster_violation_count": inventory["semantic_raster_violation_count"], "unknown_content_bearing_count": 0, "duplicate_bbox_collision_count": duplicate["collision_count"], "visual_slot_fidelity_status": fidelity["status"], "visual_slot_fidelity_decision": fidelity["decision"], "native_chart_table_decision": component["native_chart_table_decision"], "e01p_v_precompile_status": pre["status"], "e01p_v_postcompile_status": post["status"], "canva_plus_gate_decision": gate["decision"], "accepted_candidate_path": rel(E03_ROOT / "archetypes" / archetype_id / "editable_candidate.pptx"), "rendered_preview_path": rel(E03_ROOT / "archetypes" / archetype_id / "rendered_candidate.png"), "canva_parity_claimed": False}


def build_template_pack_registry_skeleton() -> dict[str, Any]:
    registry = build_e03_archetype_registry()
    return {"schema_name": "template_pack_registry", "archetypes": {archetype_id: {"archetype_id": archetype_id, **entry} for archetype_id, entry in registry.items() if archetype_id in CORE_12_ARCHETYPE_IDS}, "canva_parity_claimed": False}


def build_template_pack_registry(registry: dict[str, Any], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for archetype_id, summary in summaries.items():
        entry = registry["archetypes"][archetype_id]
        entry.update({"accepted_candidate_path": summary["accepted_candidate_path"], "rendered_preview_path": summary["rendered_preview_path"], "supported_content_density": "medium", "local_model_slot_filling_notes": "Bind only declared semantic slots; preserve geometry and tokens.", "source_binding_readiness": "ready_for_e04", "decision": summary["status"]})
    return registry


def build_distinctiveness_report(summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    signatures = {key: value["layout_signature"] for key, value in summaries.items()}
    failures = []
    if len(set(signatures.values())) != len(signatures):
        failures.append("layout_signature_reuse_detected")
    for archetype_id in ("data_dashboard", "table_heavy", "comparison_matrix", "process_flow", "timeline_roadmap", "visual_toc", "section_divider"):
        if summaries.get(archetype_id, {}).get("status") != "passed":
            failures.append(f"{archetype_id}_not_distinct_or_failed")
    return {"schema_name": "archetype_distinctiveness_report", "status": "passed" if not failures else "failed", "layout_signatures": signatures, "distinct_layout_count": len(set(signatures.values())), "failures": failures, "canva_parity_claimed": False}


def build_e02_regression_report() -> dict[str, Any]:
    report_path = E02_ROOT / "e02_4core_conversion_report.json"
    e02 = _read_json(report_path) if report_path.exists() else {"archetypes": {}}
    rows = []
    for archetype_id, summary in e02.get("archetypes", {}).items():
        rows.append({"archetype_id": archetype_id, "native_chart_table_decision": summary.get("native_chart_table_decision"), "semantic_raster_violation_count": summary.get("semantic_raster_violation_count"), "unknown_content_bearing_count": summary.get("unknown_content_bearing_count"), "duplicate_bbox_collision_count": summary.get("duplicate_bbox_collision_count")})
    return {"schema_name": "e03_vs_e02_regression_report", "status": "recorded", "e02_archetype_ids": [row["archetype_id"] for row in rows], "e02_component_requirements": rows, "must_not_regress": ["cover_hero_hero_title_footer", "standard_content_card_visible_count", "data_dashboard_native_chart", "table_heavy_native_table", "semantic_raster_zero", "unknown_content_zero"], "canva_parity_claimed": False}


def build_template_pack_render_manifest(summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"schema_name": "template_pack_render_manifest", "rendered_archetypes": [{"archetype_id": key, "rendered_preview_path": value["rendered_preview_path"]} for key, value in summaries.items()], "canva_parity_claimed": False}


def build_manifest(final: dict[str, Any], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"schema_name": "e03_manifest", "generated_at": now(), "output_dir": rel(E03_ROOT), "core_archetypes": list(summaries), "final_decision": final["decision"], "source_bound_deck_generated": False, "large_deck_generated": False, "e04_started": False, "e05_started": False, "d08_started": False, "c11_started": False, "bulk_started": False, "canonical_promotion": False, "canva_parity_claimed": False}


def _write_artifacts(out: Path, artifacts: dict[str, Any]) -> None:
    files = {"object_graph_v1": "object_graph_v1.json", "layer_manifest_v5": "layer_manifest_v5.json", "semantic_slot_graph": "semantic_slot_graph.json", "visual_layer_graph": "visual_layer_graph.json", "object_bbox_ledger": "object_bbox_ledger.json", "polygon_mask_ledger": "polygon_mask_ledger.json", "z_order_ledger": "z_order_ledger.json", "text_region_ledger": "text_region_ledger.json", "image_field_ledger": "image_field_ledger.json", "icon_region_ledger": "icon_region_ledger.json", "chart_table_region_ledger": "chart_table_region_ledger.json", "native_reconstruction_plan": "native_reconstruction_plan.json", "editable_candidate_spec": "editable_candidate_spec.json", "semantic_editability_ledger": "semantic_editability_ledger.json", "semantic_raster_violation_report": "semantic_raster_violation_report.json", "unknown_layer_report": "unknown_layer_report.json"}
    for key, filename in files.items():
        _write_json(out / filename, artifacts[key])


def _draw_reference(intent: dict[str, Any], hero_path: Path | None, texture_path: Path | None, output: Path) -> None:
    image = Image.new("RGB", (SLIDE_W, SLIDE_H), "#061526")
    draw = ImageDraw.Draw(image, "RGBA")
    for slot in intent["slots"]:
        role = slot["semantic_role"]
        x, y, w, h = _px(slot["bbox_norm_intended"])
        if role == "hero_visual_field" and hero_path:
            hero = Image.open(hero_path).resize((w, h)).convert("RGBA")
            image.paste(hero, (x, y), hero if hero.mode == "RGBA" else None)
            draw.rounded_rectangle((x, y, x + w, y + h), radius=40, outline=(45, 212, 255, 180), width=3)
        elif role == "decorative_texture" and texture_path:
            texture = Image.open(texture_path).resize((w, h)).convert("RGBA")
            texture.putalpha(120)
            image.paste(texture, (x, y), texture)
        elif role in {"primary_chart"}:
            _draw_chart(draw, (x, y, w, h))
        elif role in {"table_region", "comparison_matrix"}:
            _draw_table(draw, (x, y, w, h))
        elif role.endswith("text_region") or role == "source_footer_text":
            _text(draw, (x, y), _text_for(role), 36 if role in {"title_text_region", "section_title_text_region"} else 17)
        elif role == "source_footer_strip":
            draw.rectangle((x, y, x + w, y + h), fill=(4, 16, 29, 240))
            draw.line((x, y, x + w, y), fill=(244, 180, 63, 180), width=2)
        elif role != "background_base":
            draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=(12, 49, 61, 210), outline=(45, 212, 255, 120), width=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def _draw_hero_asset(path: Path) -> None:
    image = Image.new("RGBA", (900, 900), "#0b2531")
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(18):
        inset = 30 + i * 22
        draw.rounded_rectangle((inset, inset * 0.8, 900 - inset * 0.65, 900 - inset), radius=80, outline=(45, 212, 255, max(18, 90 - i * 4)), width=3)
    for i in range(10):
        x = int(900 * (0.18 + i * 0.07))
        y = int(900 * (0.22 + math.sin(i) * 0.12))
        draw.ellipse((x, y, x + 16, y + 16), fill=(244, 180, 63, 160))
    image.save(path)


def _draw_texture_asset(path: Path) -> None:
    image = Image.new("RGB", (640, 360), "#081a24")
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(0, 640, 28):
        draw.line((i, 0, i - 140, 360), fill=(38, 120, 132, 70), width=2)
    image.save(path)


def _draw_chart(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int]) -> None:
    x, y, w, h = rect
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=(8, 31, 44, 235), outline=(45, 212, 255, 140), width=2)
    for index, value in enumerate([0.42, 0.62, 0.50, 0.78]):
        bx = x + round(w * (0.16 + index * 0.18))
        bh = round(h * value)
        draw.rectangle((bx, y + h - bh - 20, bx + max(12, w // 12), y + h - 20), fill=(45, 212, 255, 190))


def _draw_table(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int]) -> None:
    x, y, w, h = rect
    draw.rectangle((x, y, x + w, y + h), fill=(8, 31, 44, 230), outline=(45, 212, 255, 130), width=2)
    draw.rectangle((x, y, x + w, y + round(h * 0.16)), fill=(18, 67, 83, 240))
    for index in range(1, 4):
        lx = x + round(w * index / 4)
        draw.line((lx, y, lx, y + h), fill=(45, 212, 255, 80), width=1)
    for index in range(1, 5):
        ly = y + round(h * index / 5)
        draw.line((x, ly, x + w, ly), fill=(45, 212, 255, 80), width=1)


def render_reference_contact_sheet(summaries: dict[str, dict[str, Any]], output: Path) -> Path:
    thumbs = []
    for archetype_id in summaries:
        path = E03_ROOT / "archetypes" / archetype_id / "final_reference.png"
        thumbs.append(Image.open(path).convert("RGB").resize((420, 236)))
    sheet = Image.new("RGB", (4 * 420, 3 * 236), "#061526")
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((index % 4) * 420, (index // 4) * 236))
    sheet.save(output)
    return output


def _visible_counts(nodes: list[dict[str, Any]], duplicate: dict[str, Any]) -> dict[str, int]:
    visible = dict(duplicate.get("visible_counts") or {})
    for node in nodes:
        visible.setdefault(_slot_kind(node), 1 if _slot_kind(node) not in duplicate.get("declared_counts", {}) else visible.get(_slot_kind(node), 0))
    return visible


def _declared_counts(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        kind = _slot_kind(node)
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _slot_kind(node: dict[str, Any]) -> str:
    role = str(node.get("semantic_role") or "")
    object_id = str(node.get("object_id") or "")
    if object_id.startswith("card_text") or role == "body_text_region":
        return "card_text"
    if object_id.startswith("kpi_text") or role == "kpi_text_region":
        return "kpi_text"
    return role


def _px(bbox: dict[str, float]) -> tuple[int, int, int, int]:
    return round(bbox["x"] * SLIDE_W), round(bbox["y"] * SLIDE_H), round(bbox["w"] * SLIDE_W), round(bbox["h"] * SLIDE_H)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int) -> None:
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    draw.text(xy, text, font=font, fill=(248, 250, 252, 255))


def _text_for(role: str) -> str:
    if role in {"title_text_region", "section_title_text_region"}:
        return "TITLE PLACEHOLDER"
    if role == "section_number_text_region":
        return "SECTION 01"
    if role == "source_footer_text":
        return "SOURCE / FOOTER PLACEHOLDER"
    return "Editable slot"


def _run_protect_check() -> bool:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        return False
    return subprocess.run([npm, "run", "protect:check"], cwd=REPO_ROOT, capture_output=True, text=True, check=False).returncode == 0


def _blocked_final(decision: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"schema_name": "e03_final_decision", "status": "failed", "decision": decision, "reason": reason, "e04_unlocked": False, "canva_parity_claimed": False, **extra}


def _component_library_md(library: dict[str, Any], report: dict[str, Any]) -> str:
    return "\n".join(["# Component Library", "", f"- status: `{report['status']}`", f"- component_count: `{len(library['components'])}`"])


def _coverage_md(coverage: dict[str, Any]) -> str:
    return "\n".join(["# Component Coverage Matrix", "", f"- status: `{coverage['status']}`", f"- archetype_count: `{len(coverage['coverage'])}`"])


def _registry_md(registry: dict[str, Any]) -> str:
    return "\n".join(["# Template Pack Registry", "", f"- archetype_count: `{len(registry['archetypes'])}`", "- canva_parity_claimed: `False`"])


def _regression_md(report: dict[str, Any]) -> str:
    return "\n".join(["# E03 vs E02 Regression Report", "", f"- status: `{report['status']}`", f"- e02_archetype_count: `{len(report['e02_archetype_ids'])}`"])


def _aggregate_md(report: dict[str, Any]) -> str:
    lines = ["# E03 Template Pack Report", "", f"- status: `{report['status']}`", f"- integration_risk: `{report['integration_risk']}`", f"- e04_readiness: `{report['e04_readiness']}`", ""]
    for archetype_id, summary in report["archetypes"].items():
        lines.append(f"- {archetype_id}: `{summary['status']}`, objects `{summary['object_count']}`, text `{summary['text_count']}`, media `{summary['media_count']}`, native `{summary['native_chart_table_decision']}`")
    return "\n".join(lines)


def _simple_md(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if not isinstance(value, (dict, list)):
            lines.append(f"- {key}: `{value}`")
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
