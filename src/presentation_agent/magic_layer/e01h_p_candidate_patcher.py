"""Candidate patching helpers for E01H-P."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e01h_hybrid_candidate_compiler import (
    audit_hybrid_pptx,
    build_editable_candidate_spec,
    build_inventory_ledgers,
    compile_hybrid_candidate,
    render_hybrid_candidate_preview,
)
from src.presentation_agent.magic_layer.e01h_hybrid_orchestrator import build_e01h_conversion_payload


def build_patched_candidate(e01h_root: str | Path, icon_vectorization_plan: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    root = Path(e01h_root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    reference = root / "reference_image.png"
    payload = build_e01h_conversion_payload(reference)
    patched_payload = _patch_payload_for_icons(payload, icon_vectorization_plan)

    compile_report = compile_hybrid_candidate(patched_payload, output)
    render_manifest = render_hybrid_candidate_preview(patched_payload, output)
    _copy_if_exists(output / "editable_candidate.pptx", output / "patched_editable_candidate.pptx")
    _copy_if_exists(output / "rendered_candidate.png", output / "patched_rendered_candidate.png")
    _copy_if_exists(output / "reference_vs_render.png", output / "patched_reference_vs_render.png")
    _copy_if_exists(output / "visual_diff_overlay.png", output / "patched_visual_diff_overlay.png")
    _copy_if_exists(output / "semantic_overlay_preview.png", output / "patched_semantic_overlay_preview.png")
    _copy_if_exists(output / "backplate_overlay_preview.png", output / "patched_backplate_overlay_preview.png")

    patched_pptx = output / "patched_editable_candidate.pptx"
    inventory = audit_hybrid_pptx(patched_pptx)
    ledgers = _prefix_ledgers(build_inventory_ledgers(inventory, patched_payload))
    render_manifest = _patched_render_manifest(render_manifest, output)
    return {
        "patched_payload": patched_payload,
        "patched_object_graph_v2": patched_payload["object_graph_v2"],
        "patched_layer_manifest_v5": patched_payload["layer_manifest_v5"],
        "patched_semantic_slot_graph": patched_payload["semantic_slot_graph"],
        "patched_semantic_native_reconstruction_plan": patched_payload["semantic_native_reconstruction_plan"],
        "patched_editable_candidate_spec": _patched_candidate_spec(patched_payload),
        "compile_report": {
            **compile_report,
            "pptx_path": patched_pptx.as_posix(),
            "semantic_icon_patch_applied": True,
            "semantic_icon_vector_plan_count": icon_vectorization_plan["required_icon_plan_count"],
        },
        "patched_render_manifest": render_manifest,
        "ledgers": ledgers,
    }


def _patch_payload_for_icons(payload: dict[str, Any], icon_vectorization_plan: dict[str, Any]) -> dict[str, Any]:
    patched = copy.deepcopy(payload)
    plan_index = {row["object_id"]: row for row in icon_vectorization_plan["plans"]}
    for node in patched["object_graph_v2"]["nodes"]:
        plan = plan_index.get(node["object_id"])
        if not plan:
            continue
        node["glyph_kind"] = plan["glyph_kind"]
        node["layer_class"] = "semantic_editable"
        node["object_type"] = "semantic_icon"
        node["editability_target"] = "native_vector"
        node["raster_policy"] = {"final_use": "ppt_native_vector", "semantic_raster_allowed": False, "bounded": True}
        node["semantic_icon_patch"] = {"status": "planned", "plan_id": plan["plan_id"], "empty_circle_allowed": False}
    _patch_layer_manifest(patched["layer_manifest_v5"], plan_index)
    _patch_semantic_slot_graph(patched["semantic_slot_graph"], plan_index)
    _patch_native_plan(patched["semantic_native_reconstruction_plan"], plan_index)
    patched["semantic_native_layer_manifest"]["native_icon_layer_count"] = len(plan_index)
    patched["native_component_promotion_report"]["promoted_icon_count"] = len(plan_index)
    return patched


def _patch_layer_manifest(layer_manifest: dict[str, Any], plan_index: dict[str, dict[str, Any]]) -> None:
    for layer in layer_manifest.get("layers", []):
        plan = plan_index.get(layer.get("object_id"))
        if not plan:
            continue
        layer["editability_target"] = "native_vector"
        layer["glyph_kind"] = plan["glyph_kind"]
        layer["semantic_icon_patch_status"] = "planned"
        layer["raster_allowed"] = False


def _patch_semantic_slot_graph(slot_graph: dict[str, Any], plan_index: dict[str, dict[str, Any]]) -> None:
    for slot in slot_graph.get("slots", []):
        plan = plan_index.get(slot.get("object_id"))
        if not plan:
            continue
        slot["primitive_target"] = "native_vector"
        slot["glyph_kind"] = plan["glyph_kind"]
        slot["semantic_icon_patch_status"] = "planned"


def _patch_native_plan(native_plan: dict[str, Any], plan_index: dict[str, dict[str, Any]]) -> None:
    for action in native_plan.get("actions", []):
        plan = plan_index.get(action.get("source_object_id"))
        if not plan:
            continue
        action["target_ppt_object_type"] = "native_vector"
        action["glyph_kind"] = plan["glyph_kind"]
        action["raster_allowed"] = False
        action["status"] = "passed"
        action["semantic_icon_patch_status"] = "planned"


def _patched_candidate_spec(payload: dict[str, Any]) -> dict[str, Any]:
    spec = build_editable_candidate_spec(payload)
    spec["schema_name"] = "patched_editable_candidate_spec"
    spec["semantic_icon_patch_applied"] = True
    spec["semantic_icon_target"] = "native_vector"
    return spec


def _prefix_ledgers(ledgers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    prefixed: dict[str, dict[str, Any]] = {}
    for key, ledger in ledgers.items():
        patched_key = f"patched_{key}"
        prefixed[patched_key] = {**ledger, "schema_name": patched_key}
    return prefixed


def _patched_render_manifest(render_manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    return {
        **render_manifest,
        "schema_name": "patched_render_manifest",
        "rendered_candidate": (output / "patched_rendered_candidate.png").as_posix(),
        "reference_vs_render": (output / "patched_reference_vs_render.png").as_posix(),
        "visual_diff_overlay": (output / "patched_visual_diff_overlay.png").as_posix(),
        "semantic_overlay_preview": (output / "patched_semantic_overlay_preview.png").as_posix(),
        "backplate_overlay_preview": (output / "patched_backplate_overlay_preview.png").as_posix(),
    }


def _copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copy2(source, target)
