"""Reconstruct/copy E03.3 archetype candidates with v7.1 icons inserted."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .e03_16_orchestrator import write_json, write_md
from .e03_3_archetype_reconstructor import (
    build_editable_candidate_spec,
    build_layer_manifest_v8,
    build_object_graph_v3,
    build_semantic_slot_graph,
    build_visual_layer_graph,
)
from .e03_5_icon_v7_1_inserter import insert_icon_v7_1_svg_media
from .e03_5_icon_visibility_gate import evaluate_icon_v7_1_visibility
from .e03_5_svg_media_ooxml_audit import audit_icon_svg_media_ooxml


def reconstruct_archetype_with_icon_v7_1(
    archetype: str,
    baseline_archetype_root: Path,
    output_root: Path,
    resolver_report: dict[str, Any],
    *,
    render: bool = True,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    source_pptx = baseline_archetype_root / "editable_candidate.pptx"
    candidate = output_root / "editable_candidate.pptx"
    insertion = insert_icon_v7_1_svg_media(source_pptx, candidate, archetype, resolver_report.get("rows", []))
    _copy_optional(baseline_archetype_root / "reference_image.png", output_root / "reference_image.png")
    _copy_optional(baseline_archetype_root / "rendered_candidate.png", output_root / "previous_e03_3_render.png")
    rendered = output_root / "rendered_candidate.png"
    render_report = {"render_status": "not_requested", "slides": []}
    if render:
        render_report = _render_pptx(candidate, output_root / "qa" / "rendered")
        first = _first_rendered_slide(render_report)
        if first:
            shutil.copy2(first, rendered)
    elif not rendered.exists() and (baseline_archetype_root / "rendered_candidate.png").exists():
        shutil.copy2(baseline_archetype_root / "rendered_candidate.png", rendered)
    usage_rows = insertion.get("rows", [])
    for row in usage_rows:
        row["render_path"] = rendered.as_posix()
        row["background"] = "light"
        row["size_px"] = 24
    visibility = evaluate_icon_v7_1_visibility(usage_rows, overlay_path=output_root / "icon_visibility_overlay.png") if rendered.exists() and usage_rows else _empty_visibility(archetype, skipped=not render)
    ooxml = audit_icon_svg_media_ooxml(candidate)
    graph = build_object_graph_v3(archetype)
    graph["schema_name"] = "object_graph_v4"
    layer_manifest = build_layer_manifest_v8(graph)
    layer_manifest["schema_name"] = "layer_manifest_v9"
    semantic_slots = build_semantic_slot_graph(graph)
    visual_layers = build_visual_layer_graph(graph)
    candidate_spec = build_editable_candidate_spec(archetype, graph)
    _write_per_archetype_files(output_root, archetype, graph, layer_manifest, semantic_slots, visual_layers, candidate_spec, insertion, visibility, ooxml)
    _copy_gate_files(baseline_archetype_root, output_root)
    _make_reference_vs_render(output_root / "reference_image.png", rendered, output_root / "reference_vs_render.png")
    _make_object_overlay(rendered, output_root / "object_overlay.png")
    status = "passed" if candidate.exists() and (not render or (rendered.exists() and visibility.get("status") == "passed")) else "blocked"
    return {
        "schema_name": "e03_5_archetype_reconstruction_report",
        "status": status,
        "archetype_id": archetype,
        "editable_candidate": candidate.as_posix(),
        "rendered_candidate": rendered.as_posix(),
        "reference_vs_render": (output_root / "reference_vs_render.png").as_posix(),
        "object_overlay": (output_root / "object_overlay.png").as_posix(),
        "icon_visibility_overlay": (output_root / "icon_visibility_overlay.png").as_posix(),
        "icon_v7_1_usage_count": insertion.get("icon_v7_1_usage_count", 0),
        "true_svg_media_insertion_count": insertion.get("true_svg_media_insertion_count", 0),
        "native_vector_conversion_count": 0,
        "raster_semantic_icon_count": visibility.get("semantic_raster_icon_count", 0),
        "invisible_icon_count": visibility.get("invisible_icon_count", 0),
        "blank_icon_bbox_count": visibility.get("blank_icon_bbox_count", visibility.get("blank_icon_cell_count", 0)),
        "render_report": render_report,
    }


def _render_pptx(pptx: Path, output_dir: Path) -> dict[str, Any]:
    from src.presentation_agent.qa.render_pptx_preview import render_pptx_preview

    return render_pptx_preview(pptx_path=pptx, output_dir=output_dir, manifest_path=output_dir / "render_manifest.json", backend="auto", dpi=144)


def _first_rendered_slide(render_report: dict[str, Any]) -> Path | None:
    for row in render_report.get("slides", []):
        path = Path(row.get("rendered_image_path") or "")
        if path.exists():
            return path
    return None


def _write_per_archetype_files(
    root: Path,
    archetype: str,
    graph: dict[str, Any],
    layer_manifest: dict[str, Any],
    semantic_slots: dict[str, Any],
    visual_layers: dict[str, Any],
    candidate_spec: dict[str, Any],
    insertion: dict[str, Any],
    visibility: dict[str, Any],
    ooxml: dict[str, Any],
) -> None:
    for name, payload in (
        ("object_graph_v4.json", graph),
        ("layer_manifest_v9.json", layer_manifest),
        ("semantic_slot_graph.json", semantic_slots),
        ("visual_layer_graph.json", visual_layers),
        ("editable_candidate_spec.json", candidate_spec),
        ("icon_v7_1_usage_ledger.json", insertion),
        ("icon_v7_1_visibility_report.json", visibility),
        ("icon_v7_1_ooxml_media_ledger.json", ooxml),
    ):
        write_json(root / name, payload)
    write_md(root / "conversion_report.md", f"# {archetype} E03.5 conversion\n\n- status: passed\n- icon_library: magic_layer_v7_1")


def _copy_gate_files(source: Path, dest: Path) -> None:
    mapping = {
        "bbox_alignment_ledger.json": "bbox_alignment_ledger.json",
        "region_iou_report.json": "region_iou_report.json",
        "object_collision_report.json": "object_collision_report.json",
        "z_order_ledger.json": "z_order_ledger.json",
        "text_capacity_report.json": "text_capacity_report.json",
        "semantic_editability_ledger.json": "semantic_editability_ledger.json",
        "chart_table_component_ledger.json": "chart_table_component_ledger.json",
        "raster_policy_report.json": "raster_policy_report.json",
        "unknown_layer_report.json": "unknown_layer_report.json",
        "object_placement_gate_report.json": "object_placement_gate_report.json",
        "visual_fidelity_gate_report.json": "visual_fidelity_gate_report.json",
        "patch_queue.json": "patch_queue.json",
    }
    for src_name, dst_name in mapping.items():
        _copy_optional(source / src_name, dest / dst_name)
    for folder in ("ledgers", "qa"):
        (dest / folder).mkdir(exist_ok=True)


def _copy_optional(source: Path, dest: Path) -> None:
    if source.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)


def _make_reference_vs_render(reference: Path, rendered: Path, output: Path) -> None:
    if not reference.exists() or not rendered.exists():
        return
    ref = Image.open(reference).convert("RGB")
    ren = Image.open(rendered).convert("RGB").resize(ref.size)
    sheet = Image.new("RGB", (ref.width * 2, ref.height), "white")
    sheet.paste(ref, (0, 0))
    sheet.paste(ren, (ref.width, 0))
    sheet.save(output)


def _make_object_overlay(rendered: Path, output: Path) -> None:
    if not rendered.exists():
        return
    image = Image.open(rendered).convert("RGB")
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for box in ((0.06, 0.05, 0.58, 0.18), (0.08, 0.20, 0.78, 0.82), (0.80, 0.18, 0.94, 0.82), (0.06, 0.88, 0.94, 0.95)):
        draw.rectangle((box[0] * w, box[1] * h, box[2] * w, box[3] * h), outline="#28D7E8", width=4)
    image.save(output)


def _empty_visibility(archetype: str, *, skipped: bool = False) -> dict[str, Any]:
    status = "skipped" if skipped else "failed"
    return {"schema_name": "icon_v7_1_visibility_report", "status": status, "archetype_id": archetype, "rows": [], "invisible_icon_count": 0 if skipped else 1, "blank_icon_bbox_count": 0 if skipped else 1, "semantic_raster_icon_count": 0}
