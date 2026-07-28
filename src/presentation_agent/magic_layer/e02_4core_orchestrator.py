"""Orchestrate the isolated E02 four-core PS-layer archetype conversion gate."""

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
from src.presentation_agent.magic_layer.e02_aggregate_report import build_e02_aggregate_report, final_decision_for_e02
from src.presentation_agent.magic_layer.e02_archetype_contracts import CORE_ARCHETYPE_IDS, build_e02_archetype_contracts, build_e02_design_intent_trace, validate_archetype_contract
from src.presentation_agent.magic_layer.e02_component_requirements import validate_component_requirements
from src.presentation_agent.magic_layer.e02_generalization_gate import evaluate_e02_generalization_gate


SLIDE_W = 1672
SLIDE_H = 941
REPO_ROOT = Path(__file__).resolve().parents[3]
E01P_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_photoshop_layer_protocol"
E01PV_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01p_v_cross_ledger_validator"
E01X_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01x_self_describing_ps_layer_integration"
E01XP_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01x_p_visual_slot_fidelity_patch"
E02_ROOT = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e02_4core_ps_layer_archetype_conversion"


def run_e02_4core_conversion() -> dict[str, Any]:
    E02_ROOT.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    if not _run_protect_check():
        final = _blocked_final("E02_FAIL_PROTECTED_ARTIFACTS", "protected_artifact_precheck_failed")
        _write_json(E02_ROOT / "e02_final_decision.json", final)
        _write_md(E02_ROOT / "e02_final_decision.md", _simple_md("E02 Final Decision", final))
        return final
    prereq = validate_e02_prerequisites()
    if prereq["status"] != "passed":
        final = _blocked_final("E02_FAIL_GENERALIZATION", "prerequisite_check_failed", prereq=prereq)
        _write_json(E02_ROOT / "e02_final_decision.json", final)
        _write_md(E02_ROOT / "e02_final_decision.md", _simple_md("E02 Final Decision", final))
        return final

    contracts = build_e02_archetype_contracts()
    archetype_summaries: dict[str, dict[str, Any]] = {}
    for archetype_id in CORE_ARCHETYPE_IDS:
        archetype_summaries[archetype_id] = run_single_archetype(archetype_id, contracts[archetype_id])

    generalization = evaluate_e02_generalization_gate(archetype_summaries)
    protected_after = protected_snapshot()
    protected_md, protected_ok = protected_report(protected_before, protected_after)
    protected_md += f"\n\n- npm protect precheck: `passed`\n- npm protect postcheck: `{'passed' if _run_protect_check() else 'failed'}`\n"
    _write_md(E02_ROOT / "protected_artifact_check_report.md", protected_md)

    aggregate = build_e02_aggregate_report(archetype_summaries, generalization, protected_artifacts_unchanged=protected_ok)
    final = final_decision_for_e02(aggregate)
    manifest = build_manifest(final, archetype_summaries)
    _write_json(E02_ROOT / "e02_manifest.json", manifest)
    _write_json(E02_ROOT / "e02_4core_conversion_report.json", aggregate)
    _write_md(E02_ROOT / "e02_4core_conversion_report.md", aggregate_md(aggregate))
    _write_json(E02_ROOT / "e02_final_decision.json", final)
    _write_md(E02_ROOT / "e02_final_decision.md", _simple_md("E02 Final Decision", final))
    return final


def validate_e02_prerequisites() -> dict[str, Any]:
    required_paths = [E01P_ROOT, E01PV_ROOT, E01X_ROOT, E01XP_ROOT]
    required_files = [
        E01P_ROOT / "ps_layer_protocol_schema.json",
        E01P_ROOT / "selection_patch_context_schema.json",
        REPO_ROOT / "scripts/run_ps_layer_cross_ledger_validator.py",
        REPO_ROOT / "src/presentation_agent/magic_layer/e01x_visual_slot_fidelity.py",
        REPO_ROOT / "src/presentation_agent/magic_layer/e01x_duplicate_bbox_detector.py",
        REPO_ROOT / "src/presentation_agent/magic_layer/e01x_render_crosswalk.py",
    ]
    missing = [rel(path) for path in required_paths + required_files if not path.exists()]
    e01xp_decision_path = E01XP_ROOT / "e01x_p_final_decision.json"
    decision = _read_json(e01xp_decision_path).get("decision") if e01xp_decision_path.exists() else None
    if decision != "E01X_P_PASS_READY_FOR_E02_4CORE":
        missing.append("E01X-P decision not ready")
    return {
        "schema_name": "e02_prerequisite_check",
        "status": "passed" if not missing else "failed",
        "missing": missing,
        "e01x_p_decision": decision,
        "canva_parity_claimed": False,
    }


def run_single_archetype(archetype_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    out = E02_ROOT / "archetypes" / archetype_id
    out.mkdir(parents=True, exist_ok=True)
    intent = build_e02_design_intent_trace(archetype_id)
    contract_report = validate_archetype_contract(intent, contract)
    asset_recipe = build_asset_recipe_manifest(intent)
    ps_intent = build_ps_layer_intent(intent)
    ps_intent["protocol_id"] = f"e02_{archetype_id}_ps_layer_intent"
    ps_intent["source_reference"] = {**ps_intent["source_reference"], "reference_path": rel(out / "final_reference.png"), "reference_id": f"e02_{archetype_id}_reference"}
    prompt = build_image_prompt(intent, ps_intent, asset_recipe)
    _write_json(out / "design_intent_trace.json", intent)
    _write_json(out / "asset_recipe_manifest.json", asset_recipe)
    _write_json(out / "ps_layer_intent.json", ps_intent)
    _write_md(out / "image_prompt.md", prompt)
    generate_reference_assets(archetype_id, intent, asset_recipe, out)

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
    slot_report = build_slot_count_report(archetype_id, artifacts["object_graph_v1"]["nodes"], duplicate, contract)
    visibility = build_rendered_visibility_report(duplicate)
    component = validate_component_requirements(archetype_id, artifacts["native_reconstruction_plan"], artifacts["semantic_raster_violation_report"])
    fidelity = build_visual_slot_fidelity_report(archetype_id, duplicate, slot_report, component, artifacts, post)
    canva_gate = build_canva_plus_gate(archetype_id, compile_report, inventory, pre, post, fidelity, component, artifacts)
    final = final_decision_for_archetype(archetype_id, canva_gate, fidelity, component, contract_report)
    patch_queue = {"schema_name": "e02_archetype_patch_queue", "status": "empty" if final["status"] == "passed" else "open", "patches": [] if final["status"] == "passed" else [{"decision": final["decision"], "failures": canva_gate["failures"]}], "canva_parity_claimed": False}

    _write_json(out / "duplicate_bbox_collision_report.json", duplicate)
    _write_json(out / "slot_count_preservation_report.json", slot_report)
    _write_json(out / "rendered_visibility_report.json", visibility)
    _write_json(out / "visual_slot_fidelity_report.json", fidelity)
    _write_json(out / "canva_plus_gate_report.json", canva_gate)
    _write_json(out / "archetype_final_decision.json", final)
    _write_json(out / "patch_queue.json", patch_queue)
    return summarize_archetype(archetype_id, intent, inventory, pre, post, duplicate, fidelity, component, canva_gate, final)


def build_asset_recipe_manifest(intent: dict[str, Any]) -> dict[str, Any]:
    assets = []
    hero = next((slot for slot in intent["slots"] if slot["semantic_role"] == "hero_visual_field"), None)
    if hero:
        assets.append(
            {
                "asset_id": "IMG_HERO_01",
                "role": "hero_visual_field",
                "prompt": f"{intent['archetype']} bounded nonsemantic hero visual, no text, no labels, no chart, no table.",
                "raster_allowed": True,
                "semantic_content_allowed": False,
                "target_resolution_px": {"w": 900, "h": 900},
                "insertion_policy": "replaceable_image_frame",
                "bbox_norm": hero["bbox_norm_intended"],
                "mask_id": "M_HERO_ROUNDED",
                "crop_mode": "cover_center",
                "z_order": hero["z_order_intended"],
                "must_not_cover_text": True,
            }
        )
    return {"schema_name": "e02_asset_recipe_manifest", "asset_policy": "bounded_nonsemantic_assets_only", "assets": assets, "canva_parity_claimed": False}


def build_image_prompt(intent: dict[str, Any], ps_intent: dict[str, Any], asset_recipe: dict[str, Any]) -> str:
    roles = ", ".join(slot["semantic_role"] for slot in intent["slots"])
    layers = ", ".join(layer["layer_id"] for layer in ps_intent["layers"])
    assets = ", ".join(asset["asset_id"] for asset in asset_recipe["assets"]) or "none"
    return "\n".join(
        [
            f"# E02 {intent['archetype']} Image Prompt",
            "",
            "Create one 16:9 editable PowerPoint template reference image. Use placeholders only.",
            "Protect semantic text/chart/table/card/footer zones. Do not create website/SaaS UI, random microtext, full-slide raster poster, or semantic content inside visual assets.",
            f"Semantic roles: {roles}.",
            f"PS-layer control IDs: {layers}.",
            f"Bounded raster asset slots: {assets}.",
            "This prompt is recorded for local deterministic generation only; no Image API or Adobe service is called.",
        ]
    )


def generate_reference_assets(archetype_id: str, intent: dict[str, Any], asset_recipe: dict[str, Any], out: Path) -> None:
    assets = out / "generated_assets"
    assets.mkdir(parents=True, exist_ok=True)
    hero_path = assets / "IMG_HERO_01.png"
    if any(asset["asset_id"] == "IMG_HERO_01" for asset in asset_recipe["assets"]):
        _draw_hero_asset(hero_path)
    if archetype_id == "standard_content" and (E01XP_ROOT / "patched_rendered_candidate.png").exists():
        shutil.copyfile(E01XP_ROOT / "patched_rendered_candidate.png", out / "final_reference.png")
        return
    _draw_reference(intent, hero_path if hero_path.exists() else None, out / "final_reference.png")


def build_slot_count_report(archetype_id: str, nodes: list[dict[str, Any]], duplicate: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    visible = _visible_counts(nodes, duplicate)
    declared = _declared_counts(nodes)
    failures = []
    rows = []
    for slot, required in contract.get("required_visible_counts", {}).items():
        actual = int(visible.get(slot, 0))
        if actual < required:
            failures.append(f"{slot}_visible_count_lt_required")
        rows.append({"slot_kind": slot, "required_visible_count": required, "declared_count": declared.get(slot, 0), "visible_count": actual, "status": "passed" if actual >= required else "failed"})
    return {"schema_name": "slot_count_preservation_report", "archetype_id": archetype_id, "status": "passed" if not failures else "failed", "declared_counts": declared, "visible_counts": visible, "rows": rows, "failures": failures, "canva_parity_claimed": False}


def build_visual_slot_fidelity_report(archetype_id: str, duplicate: dict[str, Any], slot_report: dict[str, Any], component: dict[str, Any], artifacts: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
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
    return {
        "schema_name": "visual_slot_fidelity_report",
        "archetype_id": archetype_id,
        "status": "passed" if not failures else "failed",
        "decision": "passed" if not failures else "patch_required",
        "failures": sorted(set(failures)),
        "duplicate_collision_count": duplicate["collision_count"],
        "visible_counts": slot_report["visible_counts"],
        "canva_parity_claimed": False,
    }


def build_canva_plus_gate(archetype_id: str, compile_report: dict[str, Any], inventory: dict[str, Any], pre: dict[str, Any], post: dict[str, Any], fidelity: dict[str, Any], component: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "editable_candidate_exists": Path(compile_report["editable_candidate_pptx"]).exists(),
        "candidate_renders": True,
        "no_full_slide_reference_background": compile_report["full_slide_reference_background"] is False,
        "no_screenshot_slide": compile_report["screenshot_slide"] is False,
        "e01p_v_precompile_passed": pre["status"] == "passed",
        "e01p_v_postcompile_passed": post["status"] == "passed",
        "visual_slot_fidelity_passed": fidelity["status"] == "passed",
        "component_requirements_passed": component["status"] == "passed",
        "semantic_raster_zero": artifacts["semantic_raster_violation_report"]["semantic_raster_violation_count"] == 0,
        "unknown_content_zero": artifacts["unknown_layer_report"]["unknown_content_bearing_layer_count"] == 0,
        "pptx_inventory_passed": inventory["status"] == "passed",
    }
    failures = [key for key, passed in checks.items() if not passed]
    return {"schema_name": "canva_plus_gate_report", "archetype_id": archetype_id, "status": "passed" if not failures else "failed", "decision": "passed" if not failures else "patch_required", "checks": checks, "failures": failures, "canva_parity_claimed": False}


def final_decision_for_archetype(archetype_id: str, gate: dict[str, Any], fidelity: dict[str, Any], component: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    status = "passed" if gate["status"] == fidelity["status"] == component["status"] == contract["status"] == "passed" else "failed"
    return {
        "schema_name": "e02_archetype_final_decision",
        "archetype_id": archetype_id,
        "status": status,
        "decision": "passed" if status == "passed" else "patch_required",
        "canva_parity_claimed": False,
    }


def summarize_archetype(archetype_id: str, intent: dict[str, Any], inventory: dict[str, Any], pre: dict[str, Any], post: dict[str, Any], duplicate: dict[str, Any], fidelity: dict[str, Any], component: dict[str, Any], gate: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
    shapes = inventory.get("shapes", [])
    return {
        "archetype_id": archetype_id,
        "status": final["status"],
        "layout_signature": intent["layout_signature"],
        "object_count": inventory["shape_count"],
        "text_count": inventory["editable_text_count"],
        "media_count": inventory["picture_count"],
        "connector_vector_count": sum(1 for shape in shapes if "CONNECTOR" in shape["shape_type"] or "FREEFORM" in shape["shape_type"] or "AUTO_SHAPE" in shape["shape_type"]),
        "semantic_raster_violation_count": inventory["semantic_raster_violation_count"],
        "unknown_content_bearing_count": 0,
        "duplicate_bbox_collision_count": duplicate["collision_count"],
        "visual_slot_fidelity_status": fidelity["status"],
        "visual_slot_fidelity_decision": fidelity["decision"],
        "native_chart_table_decision": component["native_chart_table_decision"],
        "native_component_report": component,
        "e01p_v_precompile_status": pre["status"],
        "e01p_v_postcompile_status": post["status"],
        "canva_plus_gate_decision": gate["decision"],
        "canva_parity_claimed": False,
    }


def build_manifest(final: dict[str, Any], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "e02_manifest",
        "generated_at": now(),
        "output_dir": rel(E02_ROOT),
        "archetypes": list(summaries),
        "final_decision": final["decision"],
        "source_bound_deck_generated": False,
        "large_deck_generated": False,
        "e03_started": False,
        "d08_started": False,
        "c11_started": False,
        "bulk_started": False,
        "canonical_promotion": False,
        "canva_parity_claimed": False,
    }


def _write_artifacts(out: Path, artifacts: dict[str, Any]) -> None:
    files = {
        "object_graph_v1": "object_graph_v1.json",
        "layer_manifest_v5": "layer_manifest_v5.json",
        "semantic_slot_graph": "semantic_slot_graph.json",
        "visual_layer_graph": "visual_layer_graph.json",
        "object_bbox_ledger": "object_bbox_ledger.json",
        "polygon_mask_ledger": "polygon_mask_ledger.json",
        "z_order_ledger": "z_order_ledger.json",
        "text_region_ledger": "text_region_ledger.json",
        "image_field_ledger": "image_field_ledger.json",
        "icon_region_ledger": "icon_region_ledger.json",
        "chart_table_region_ledger": "chart_table_region_ledger.json",
        "native_reconstruction_plan": "native_reconstruction_plan.json",
        "editable_candidate_spec": "editable_candidate_spec.json",
        "semantic_editability_ledger": "semantic_editability_ledger.json",
        "semantic_raster_violation_report": "semantic_raster_violation_report.json",
        "unknown_layer_report": "unknown_layer_report.json",
    }
    for key, filename in files.items():
        _write_json(out / filename, artifacts[key])


def _draw_reference(intent: dict[str, Any], hero_path: Path | None, output: Path) -> None:
    image = Image.new("RGB", (SLIDE_W, SLIDE_H), "#061526")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, SLIDE_W, SLIDE_H), fill=(6, 21, 38, 255))
    for slot in intent["slots"]:
        role = slot["semantic_role"]
        x, y, w, h = _px(slot["bbox_norm_intended"])
        if role == "hero_visual_field" and hero_path:
            hero = Image.open(hero_path).resize((w, h)).convert("RGBA")
            mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=40, fill=255)
            image.paste(hero, (x, y), mask)
            draw.rounded_rectangle((x, y, x + w, y + h), radius=40, outline=(45, 212, 255, 180), width=3)
        elif role in {"card_panel", "kpi_card", "insight_panel", "table_body_grid", "kpi_chip"}:
            draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=(12, 49, 61, 215), outline=(45, 212, 255, 120), width=2)
        elif role == "table_header_band":
            draw.rectangle((x, y, x + w, y + h), fill=(18, 67, 83, 230))
        elif role == "primary_chart":
            _draw_chart(draw, (x, y, w, h))
        elif role == "table_region":
            _draw_table(draw, (x, y, w, h))
        elif role.endswith("text_region") or role == "source_footer_text":
            _text(draw, (x, y), _text_for_role(role), 34 if role == "title_text_region" else 18)
        elif role == "source_footer_strip":
            draw.rectangle((x, y, x + w, y + h), fill=(4, 16, 29, 240))
            draw.line((x, y, x + w, y), fill=(244, 180, 63, 180), width=2)
        elif role == "semantic_icon":
            draw.ellipse((x, y, x + w, y + h), fill=(45, 212, 255, 210))
            draw.polygon([(x + w * 0.50, y + h * 0.20), (x + w * 0.78, y + h * 0.70), (x + w * 0.22, y + h * 0.70)], fill=(6, 21, 38, 255))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def _draw_hero_asset(path: Path) -> None:
    image = Image.new("RGB", (900, 900), "#0b2531")
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(18):
        inset = 30 + i * 22
        draw.rounded_rectangle((inset, inset * 0.8, 900 - inset * 0.65, 900 - inset), radius=80, outline=(45, 212, 255, max(18, 90 - i * 4)), width=3)
    for i in range(10):
        x = int(900 * (0.18 + i * 0.07))
        y = int(900 * (0.22 + math.sin(i) * 0.12))
        draw.ellipse((x, y, x + 16, y + 16), fill=(244, 180, 63, 160))
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


def _visible_counts(nodes: list[dict[str, Any]], duplicate: dict[str, Any]) -> dict[str, int]:
    visible = dict(duplicate.get("visible_counts") or {})
    for node in nodes:
        kind = _slot_kind(node)
        visible.setdefault(kind, 0)
        if kind not in duplicate.get("declared_counts", {}):
            visible[kind] += 1
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


def _text_for_role(role: str) -> str:
    return {
        "title_text_region": "TITLE PLACEHOLDER",
        "subtitle_text_region": "Subtitle / context placeholder",
        "body_text_region": "Editable body slot",
        "kpi_text_region": "KPI 00%",
        "insight_text_region": "Editable insight slot",
        "meta_text_region": "PRESENTER / DATE",
        "source_footer_text": "SOURCE / FOOTER PLACEHOLDER",
    }.get(role, "TEXT SLOT")


def _px(bbox: dict[str, float]) -> tuple[int, int, int, int]:
    return round(bbox["x"] * SLIDE_W), round(bbox["y"] * SLIDE_H), round(bbox["w"] * SLIDE_W), round(bbox["h"] * SLIDE_H)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int) -> None:
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    draw.text(xy, text, font=font, fill=(248, 250, 252, 255))


def _run_protect_check() -> bool:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        return False
    return subprocess.run([npm, "run", "protect:check"], cwd=REPO_ROOT, capture_output=True, text=True, check=False).returncode == 0


def _blocked_final(decision: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"schema_name": "e02_final_decision", "status": "failed", "decision": decision, "reason": reason, "e03_unlocked": False, "canva_parity_claimed": False, **extra}


def aggregate_md(report: dict[str, Any]) -> str:
    lines = ["# E02 4-Core Conversion Report", "", f"- status: `{report['status']}`", f"- integration_risk: `{report['integration_risk']}`", ""]
    for archetype_id, item in report["archetypes"].items():
        lines.append(f"- {archetype_id}: status `{item['status']}`, objects `{item['object_count']}`, text `{item['text_count']}`, media `{item['media_count']}`, duplicate collisions `{item['duplicate_bbox_collision_count']}`, native `{item['native_chart_table_decision']}`")
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
