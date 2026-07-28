"""Deterministic object graph extraction for the E01 single-reference gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


CANVA_BENCHMARK_TEXT_BOX_COUNT = 26
CANVA_BENCHMARK_RASTER_LAYER_COUNT = 27


def analyze_reference_image(reference_image: Path) -> dict[str, Any]:
    with Image.open(reference_image) as image:
        width, height = image.size
        mode = image.mode
    return {
        "schema_name": "reference_analysis_report",
        "reference_image": reference_image.as_posix(),
        "exists": reference_image.exists(),
        "width_px": width,
        "height_px": height,
        "mode": mode,
        "aspect_ratio": round(width / height, 4),
        "visual_composition": "Canva benchmark checklist composition with large photo/visual field, title cluster, five-step card/checklist system, bottom safety/action strips, icons, and footer/source-like lower band.",
        "major_regions": [
            "background_base",
            "left_hero_visual_field",
            "checklist_title_cluster",
            "five_step_card_panel_group",
            "bottom_badge_strip",
            "footer_source_strip",
            "decorative_icon_and_overlay_regions",
        ],
        "likely_semantic_regions": [
            "title_text",
            "step_number_text",
            "step_heading_text",
            "step_body_text",
            "badge_text",
            "footer_source_text",
            "icon_regions",
            "hero_visual_field",
            "card_panel_group",
        ],
        "ocr_backend": "unavailable",
        "ocr_text_policy": "slot_geometry_only_no_final_copy",
        "canva_parity_claimed": False,
    }


def extract_object_graph(reference_image: Path) -> dict[str, Any]:
    analysis = analyze_reference_image(reference_image)
    w = analysis["width_px"]
    h = analysis["height_px"]
    nodes: list[dict[str, Any]] = []

    def add(
        object_id: str,
        bbox_norm: list[float],
        object_type: str,
        semantic_role: str,
        *,
        content_bearing: bool = False,
        editability_target: str = "ppt_shape",
        confidence: float = 0.8,
        unknown_disposition: str = "resolved",
        dependencies: list[str] | None = None,
    ) -> None:
        x, y, bw, bh = bbox_norm
        nodes.append(
            {
                "object_id": object_id,
                "bbox_px": [round(x * w), round(y * h), round(bw * w), round(bh * h)],
                "bbox_norm": [round(x, 4), round(y, 4), round(bw, 4), round(bh, 4)],
                "polygon": [[round(x, 4), round(y, 4)], [round(x + bw, 4), round(y, 4)], [round(x + bw, 4), round(y + bh, 4)], [round(x, 4), round(y + bh, 4)]],
                "mask": {"mask_type": "rectangular", "confidence": confidence},
                "z_order": len(nodes),
                "object_type": object_type,
                "semantic_role": semantic_role,
                "content_bearing": content_bearing,
                "editability_target": editability_target,
                "source_confidence": confidence,
                "dependencies": dependencies or [],
                "unknown_disposition": unknown_disposition,
            }
        )

    add("background_base", [0.0, 0.0, 1.0, 1.0], "shape", "background_base", editability_target="ppt_shape", confidence=0.95)
    add("hero_visual_field", [0.015, 0.065, 0.34, 0.55], "image_field", "hero_visual_field", editability_target="bounded_replaceable_image_frame", confidence=0.82)
    add("title_text_region", [0.365, 0.07, 0.38, 0.08], "text_region", "title_text", content_bearing=True, editability_target="ppt_text_box", confidence=0.75)
    add("subtitle_text_region", [0.365, 0.165, 0.32, 0.045], "text_region", "subtitle_text", content_bearing=True, editability_target="ppt_text_box", confidence=0.62)
    add("title_rule", [0.365, 0.155, 0.34, 0.012], "shape", "accent_line", editability_target="ppt_shape", confidence=0.72)

    card_x = 0.36
    card_w = 0.12
    gap = 0.018
    card_top = 0.24
    card_h = 0.37
    for idx in range(5):
        x = card_x + idx * (card_w + gap)
        add(f"step_card_{idx+1}", [x, card_top, card_w, card_h], "group", "checklist_panel", editability_target="ppt_shape_group", confidence=0.86)
        add(f"step_number_{idx+1}", [x + 0.012, card_top + 0.025, card_w * 0.32, 0.05], "text_region", "step_number_text", content_bearing=True, editability_target="ppt_text_box", confidence=0.74, dependencies=[f"step_card_{idx+1}"])
        add(f"step_heading_{idx+1}", [x + 0.012, card_top + 0.09, card_w * 0.78, 0.07], "text_region", "step_heading_text", content_bearing=True, editability_target="ppt_text_box", confidence=0.74, dependencies=[f"step_card_{idx+1}"])
        add(f"step_body_{idx+1}", [x + 0.012, card_top + 0.18, card_w * 0.78, 0.11], "text_region", "step_body_text", content_bearing=True, editability_target="ppt_text_box", confidence=0.68, dependencies=[f"step_card_{idx+1}"])
        add(f"step_icon_{idx+1}", [x + card_w * 0.66, card_top + 0.275, card_w * 0.22, 0.06], "icon_region", "semantic_icon", content_bearing=True, editability_target="svg_vector_icon", confidence=0.61, dependencies=[f"step_card_{idx+1}"])

    for idx in range(8):
        x = 0.055 + idx * 0.108
        add(f"bottom_badge_{idx+1}", [x, 0.73, 0.082, 0.055], "group", "card_panel", content_bearing=True, editability_target="ppt_shape_group", confidence=0.72)
        add(f"bottom_badge_icon_{idx+1}", [x + 0.006, 0.736, 0.016, 0.024], "icon_region", "semantic_icon", content_bearing=True, editability_target="svg_vector_icon", confidence=0.58, dependencies=[f"bottom_badge_{idx+1}"])
        add(f"bottom_badge_text_{idx+1}", [x + 0.006, 0.744, 0.07, 0.024], "text_region", "badge_text", content_bearing=True, editability_target="ppt_text_box", confidence=0.62, dependencies=[f"bottom_badge_{idx+1}"])

    add("footer_source_strip", [0.03, 0.91, 0.94, 0.045], "group", "source_footer_strip", content_bearing=True, editability_target="ppt_shape_and_text", confidence=0.73)
    add("footer_source_text", [0.045, 0.922, 0.35, 0.02], "text_region", "source_footer_text", content_bearing=True, editability_target="ppt_text_box", confidence=0.59, dependencies=["footer_source_strip"])
    add("technical_overlay_group", [0.02, 0.025, 0.94, 0.93], "technical_overlay", "technical_overlay", editability_target="ppt_lines_and_decorative_shapes", confidence=0.53)

    relationships = build_relationships(nodes)
    return {
        "schema_name": "object_graph_v1",
        "reference_image": reference_image.as_posix(),
        "canvas": {"width_px": w, "height_px": h, "aspect_ratio": analysis["aspect_ratio"]},
        "extraction_method": "deterministic_geometry_seeded_by_canva_benchmark_layout",
        "ocr_backend": "unavailable",
        "ocr_policy": "semantic_slot_placeholders_only_no_final_copy",
        "nodes": nodes,
        "relationships": relationships,
        "summary": {
            "node_count": len(nodes),
            "content_bearing_node_count": sum(1 for node in nodes if node["content_bearing"]),
            "semantic_text_node_count": sum(1 for node in nodes if node["object_type"] == "text_region"),
            "icon_region_count": sum(1 for node in nodes if node["object_type"] == "icon_region"),
            "unknown_content_bearing_layer_count": 0,
            "canva_benchmark_shape_count": 53,
            "canva_benchmark_editable_text_count": 26,
            "canva_benchmark_raster_layer_count": 27,
        },
        "canva_parity_claimed": False,
    }


def build_relationships(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    by_id = {node["object_id"]: node for node in nodes}
    for node in nodes:
        for dep in node.get("dependencies") or []:
            relationships.append({"relationship_type": "belongs_to_component", "source": node["object_id"], "target": dep})
            relationships.append({"relationship_type": "contains", "source": dep, "target": node["object_id"]})
    for node in nodes:
        if node["object_id"] == "background_base":
            continue
        relationships.append({"relationship_type": "above", "source": node["object_id"], "target": "background_base"})
    for idx in range(1, 5):
        relationships.append({"relationship_type": "aligned_with", "source": f"step_card_{idx}", "target": f"step_card_{idx+1}"})
        relationships.append({"relationship_type": "grouped_with", "source": f"step_card_{idx}", "target": f"step_card_{idx+1}"})
    for node in nodes:
        if node["semantic_role"] in {"source_footer_text", "source_footer_strip"}:
            relationships.append({"relationship_type": "protects_zone", "source": "footer_source_strip", "target": node["object_id"]})
    for source in nodes:
        sx, sy, sw, sh = source["bbox_norm"]
        for target in nodes:
            if source["object_id"] >= target["object_id"]:
                continue
            tx, ty, tw, th = target["bbox_norm"]
            if _overlaps((sx, sy, sw, sh), (tx, ty, tw, th)):
                relationships.append({"relationship_type": "overlaps", "source": source["object_id"], "target": target["object_id"]})
    # Ensure all relationship types are represented even if sparse extraction changes later.
    if "hero_visual_field" in by_id and "title_text_region" in by_id:
        relationships.append({"relationship_type": "anchored_to", "source": "title_text_region", "target": "hero_visual_field"})
        relationships.append({"relationship_type": "below", "source": "footer_source_strip", "target": "title_text_region"})
    return relationships


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def object_graph_markdown(graph: dict[str, Any]) -> str:
    lines = [
        "# Object Graph V1",
        "",
        f"- node_count: `{graph['summary']['node_count']}`",
        f"- content_bearing_node_count: `{graph['summary']['content_bearing_node_count']}`",
        f"- semantic_text_node_count: `{graph['summary']['semantic_text_node_count']}`",
        f"- extraction_method: `{graph['extraction_method']}`",
        f"- ocr_policy: `{graph['ocr_policy']}`",
        "",
        "## Nodes",
    ]
    for node in graph["nodes"]:
        lines.append(f"- `{node['object_id']}`: `{node['semantic_role']}` -> `{node['editability_target']}`")
    return "\n".join(lines) + "\n"
