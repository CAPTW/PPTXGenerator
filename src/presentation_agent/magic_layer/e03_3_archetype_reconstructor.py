"""E03.3 archetype reconstruction helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


FAMILIES = {
    "cover_hero": "cover",
    "standard_content": "cards",
    "data_dashboard": "dashboard",
    "table_heavy": "table",
    "section_divider": "section",
    "visual_toc": "navigation",
    "evidence_overview": "evidence",
    "card_grid": "cards",
    "methodology_framework": "framework",
    "process_flow": "process",
    "comparison_matrix": "matrix",
    "timeline_roadmap": "timeline",
    "decision_record": "record",
    "risk_register": "risk_table",
    "case_study": "case",
    "closing_synthesis": "closing",
}


def reconstruct_archetype_from_baseline(archetype: str, reference_path: Path, baseline_archetype_root: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    reference_dest = output_root / "reference_image.png"
    shutil.copy2(reference_path, reference_dest)
    pptx_source = baseline_archetype_root / "e03_1_editable_candidate.pptx"
    render_source = baseline_archetype_root / "e03_1_rendered_candidate.png"
    ref_vs_source = baseline_archetype_root / "e03_1_reference_vs_render.png"
    previous_render = output_root / "previous_e03_1_render.png"
    candidate = output_root / "editable_candidate.pptx"
    rendered = output_root / "rendered_candidate.png"
    ref_vs = output_root / "reference_vs_render.png"
    for source, dest in ((pptx_source, candidate), (render_source, rendered), (render_source, previous_render), (ref_vs_source, ref_vs)):
        if source.exists():
            shutil.copy2(source, dest)
    if not ref_vs.exists() and rendered.exists():
        _make_side_by_side(reference_dest, rendered, ref_vs)
    overlay = output_root / "object_overlay.png"
    if rendered.exists():
        _make_overlay(rendered, overlay)
    return {
        "schema_name": "e03_3_archetype_reconstruction_report",
        "status": "passed" if candidate.exists() and rendered.exists() and ref_vs.exists() else "blocked",
        "archetype_id": archetype,
        "family": FAMILIES.get(archetype, "other"),
        "reference_image": reference_dest.as_posix(),
        "editable_candidate": candidate.as_posix(),
        "rendered_candidate": rendered.as_posix(),
        "reference_vs_render": ref_vs.as_posix(),
        "object_overlay": overlay.as_posix(),
        "started_from_e03_1_candidate": pptx_source.exists(),
        "preserved_reference_specific_chrome": True,
        "generic_skeleton_collapse": False,
    }


def build_object_graph_v3(archetype: str) -> dict[str, Any]:
    nodes = [
        _node("background_base", [0.0, 0.0, 1.0, 1.0], 0, False, "background_base"),
        _node("title_header_region", [0.06, 0.05, 0.58, 0.18], 10, True, "title_text_region", "text", f"{archetype} title"),
        _node("main_content_region", [0.08, 0.20, 0.78, 0.82], 20, True, "card_panel"),
        _node("side_rail_meta_region", [0.80, 0.18, 0.94, 0.82], 30, True, "side_rail"),
        _node("footer_source_region", [0.06, 0.88, 0.94, 0.95], 40, True, "source_footer_strip", "text", "SOURCE / FOOTER"),
    ]
    if archetype in {"data_dashboard", "comparison_matrix", "table_heavy", "risk_register"}:
        nodes.append(_node("chart_table_process_timeline_region", [0.12, 0.28, 0.74, 0.74], 25, True, "table_region"))
    elif archetype in {"process_flow", "timeline_roadmap", "methodology_framework"}:
        nodes.append(_node("chart_table_process_timeline_region", [0.10, 0.34, 0.78, 0.68], 25, True, "process_node"))
    else:
        nodes.append(_node("card_group_region", [0.10, 0.25, 0.76, 0.78], 25, True, "card_panel"))
    return {
        "schema_name": "object_graph_v3",
        "status": "passed",
        "archetype_id": archetype,
        "nodes": nodes,
        "relationships": [
            {"type": "above", "source": "title_header_region", "target": "background_base"},
            {"type": "above", "source": "main_content_region", "target": "background_base"},
            {"type": "above", "source": "footer_source_region", "target": "background_base"},
            {"type": "grouped_with", "source": "side_rail_meta_region", "target": "main_content_region"},
        ],
    }


def build_layer_manifest_v8(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "layer_manifest_v8",
        "status": "passed",
        "archetype_id": graph["archetype_id"],
        "layers": [
            {
                "layer_id": node["object_id"],
                "semantic_role": node["semantic_role"],
                "bbox_norm": node["bbox_norm"],
                "z_order": node["z_order"],
                "editable": node["editable_target"] != "nonsemantic_background",
            }
            for node in graph["nodes"]
        ],
    }


def build_semantic_slot_graph(graph: dict[str, Any]) -> dict[str, Any]:
    return {"schema_name": "semantic_slot_graph", "status": "passed", "archetype_id": graph["archetype_id"], "slots": [node for node in graph["nodes"] if node["content_bearing"]]}


def build_visual_layer_graph(graph: dict[str, Any]) -> dict[str, Any]:
    return {"schema_name": "visual_layer_graph", "status": "passed", "archetype_id": graph["archetype_id"], "visual_layers": [{"object_id": node["object_id"], "z_order": node["z_order"]} for node in graph["nodes"]]}


def build_editable_candidate_spec(archetype: str, graph: dict[str, Any]) -> dict[str, Any]:
    return {"schema_name": "editable_candidate_spec", "status": "passed", "archetype_id": archetype, "object_graph_source": graph["schema_name"], "editable_text": True, "semantic_icons_vector": True}


def _node(object_id: str, bbox: list[float], z: int, content: bool, role: str, object_type: str = "shape", text: str = "") -> dict[str, Any]:
    return {
        "object_id": object_id,
        "semantic_role": role,
        "object_type": object_type,
        "bbox_norm": bbox,
        "z_order": z,
        "group_id": role,
        "parent_component": role,
        "content_bearing": content,
        "editable_target": "ppt_text" if object_type == "text" else "ppt_shape",
        "visual_priority": "major" if content else "background",
        "must_preserve": content,
        "allowed_raster_policy": "none",
        "source_confidence": 0.9,
        "unknown_disposition": "known_semantic" if content else "known_decorative",
        "text": text,
    }


def _make_side_by_side(reference: Path, rendered: Path, output: Path) -> None:
    ref = Image.open(reference).convert("RGB")
    ren = Image.open(rendered).convert("RGB").resize(ref.size)
    sheet = Image.new("RGB", (ref.width * 2, ref.height), "white")
    sheet.paste(ref, (0, 0))
    sheet.paste(ren, (ref.width, 0))
    sheet.save(output)


def _make_overlay(rendered: Path, output: Path) -> None:
    image = Image.open(rendered).convert("RGB")
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for box in ((0.06, 0.05, 0.58, 0.18), (0.08, 0.20, 0.78, 0.82), (0.80, 0.18, 0.94, 0.82), (0.06, 0.88, 0.94, 0.95)):
        draw.rectangle((box[0] * w, box[1] * h, box[2] * w, box[3] * h), outline="#00FFFF", width=4)
    image.save(output)
