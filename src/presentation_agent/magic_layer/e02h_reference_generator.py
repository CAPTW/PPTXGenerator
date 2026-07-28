"""Local deterministic reference generation for E02H."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.presentation_agent.magic_layer.e02h_hybrid_object_graph_builder import SLIDE_H_PX, SLIDE_W_PX


COLORS = {
    "navy": "041826",
    "teal": "092D37",
    "cyan": "39D4E7",
    "gold": "F3A51A",
    "white": "F3F7FA",
    "muted": "B8CBD2",
    "panel": "061D2A",
}


def build_design_intent_trace(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "design_intent_trace",
        "status": "passed",
        "reference_id": definition["reference_id"],
        "canvas_ratio": "16:9",
        "style_tokens": definition["style_tokens"],
        "semantic_slots": [
            {
                "slot_id": region["object_id"],
                "semantic_role": region["semantic_role"],
                "bbox_norm_intended": region["bbox_norm"],
                "primitive_target": region.get("editability_target"),
                "editable_required": region["layer_class"] in {"semantic_editable", "semantic_vector", "semantic_native_component"},
                "raster_allowed": region["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"},
            }
            for region in definition.get("regions", [])
        ],
        "raster_policy": "semantic_raster_forbidden_bounded_nonsemantic_backplates_allowed",
        "full_slide_reference_background_allowed": False,
        "screenshot_slide_allowed": False,
        "canva_parity_claimed": False,
    }


def build_asset_recipe_manifest(definition: dict[str, Any]) -> dict[str, Any]:
    assets = [
        {
            "asset_id": region["object_id"],
            "role": region["semantic_role"],
            "raster_allowed": True,
            "semantic_content_allowed": False,
            "bbox_norm": region["bbox_norm"],
            "insertion_policy": "bounded_nonsemantic_backplate_or_replaceable_visual_field",
            "must_not_cover_text": True,
        }
        for region in definition.get("regions", [])
        if region["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"}
    ]
    return {"schema_name": "asset_recipe_manifest", "status": "passed", "reference_id": definition["reference_id"], "assets": assets, "canva_parity_claimed": False}


def build_image_prompt(definition: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# E02H Reference Prompt: {definition['display_name']}",
            "",
            "Create one 16:9 premium editable PowerPoint template reference image.",
            "Use deep navy, dark teal, cyan, muted gold, and off-white.",
            "Keep semantic text, icons, charts, tables, cards, and footer zones protected for PPT-native reconstruction.",
            "Use bounded nonsemantic visual backplates for richness; do not use a full-slide reference screenshot.",
            "Do not include unreadable microtext or website/SaaS dashboard styling.",
        ]
    )


def generate_reference_image(definition: dict[str, Any], output_path: str | Path) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if definition["reference_id"] == "maritime_checklist_hero":
        return {"schema_name": "reference_generation_report", "status": "skipped_regression_fixture", "reference_image": output.as_posix(), "canva_parity_claimed": False}
    image = Image.new("RGB", (SLIDE_W_PX, SLIDE_H_PX), f"#{COLORS['navy']}")
    draw = ImageDraw.Draw(image, "RGBA")
    _texture(draw)
    for region in sorted(definition["regions"], key=lambda row: row["z_order"]):
        bbox = _px(region["bbox_norm"])
        if region["object_type"] == "background_base":
            continue
        if region["layer_class"] in {"nonsemantic_visual_backplate", "bounded_decorative_raster"}:
            draw.rounded_rectangle(bbox, radius=24, fill=(*_rgb(COLORS["teal"]), 120), outline=(*_rgb(COLORS["cyan"]), 75), width=2)
            _motif(draw, bbox)
        elif region["object_type"] in {"card", "panel"}:
            draw.rounded_rectangle(bbox, radius=14, fill=(*_rgb(COLORS["panel"]), 230), outline=(*_rgb(COLORS["cyan"]), 180), width=2)
        elif region["object_type"] == "connector":
            x1, y1, x2, y2 = _connector_points(bbox)
            draw.line((x1, y1, x2, y2), fill=(*_rgb(COLORS["cyan"]), 230), width=5)
            draw.polygon([(x2, y2), (x2 - 14, y2 - 8), (x2 - 14, y2 + 8)], fill=(*_rgb(COLORS["cyan"]), 230))
        elif region["object_type"] == "semantic_icon":
            _preview_icon(draw, bbox, region.get("glyph_kind") or "shield", COLORS["cyan"])
        elif region["object_type"] == "chart":
            _draw_reference_chart(draw, bbox)
        elif region["object_type"] == "table":
            _draw_reference_table(draw, bbox)
        elif region["object_type"] == "text":
            _draw_text(draw, bbox[0], bbox[1], region.get("text") or region["semantic_role"].upper(), 18 if region["semantic_role"] == "title_text" else 10, COLORS["white"], bold=region["semantic_role"] == "title_text")
    draw.line((0, 790, 1600, 790), fill=(*_rgb(COLORS["gold"]), 230), width=3)
    image.save(output)
    return {"schema_name": "reference_generation_report", "status": "passed", "reference_image": output.as_posix(), "local_generation": "deterministic_pil", "image_api_used": False, "canva_parity_claimed": False}


def build_reference_analysis_report(definition: dict[str, Any], reference_path: str | Path) -> dict[str, Any]:
    path = Path(reference_path)
    semantic = [row for row in definition["regions"] if row["layer_class"] in {"semantic_editable", "semantic_vector", "semantic_native_component"}]
    visual = [row for row in definition["regions"] if row["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"}]
    return {
        "schema_name": "reference_analysis_report",
        "status": "passed",
        "reference_id": definition["reference_id"],
        "reference_path": path.as_posix(),
        "width": SLIDE_W_PX,
        "height": SLIDE_H_PX,
        "aspect_ratio": round(SLIDE_W_PX / SLIDE_H_PX, 6),
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
        "image_mode": "RGB",
        "visual_density_estimate": "high",
        "likely_semantic_object_count": len(semantic),
        "likely_visual_backplate_candidate_count": len(visual),
        "regions": definition["regions"],
        "ocr_performed": False,
        "ocr_claimed": False,
        "canva_parity_claimed": False,
    }


def build_reference_visual_richness_report(definition: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "reference_visual_richness_report",
        "status": "passed",
        "reference_id": definition["reference_id"],
        "visual_density_estimate": analysis["visual_density_estimate"],
        "major_visual_regions": [row["object_id"] for row in definition["regions"] if row["layer_class"] in {"replaceable_visual_field", "nonsemantic_visual_backplate", "bounded_decorative_raster"}],
        "semantic_object_count": analysis["likely_semantic_object_count"],
        "visual_backplate_candidate_count": analysis["likely_visual_backplate_candidate_count"],
        "requires_hybrid_backplates": True,
        "native_only_skeleton_risk": "high",
        "canva_parity_claimed": False,
    }


def _texture(draw: ImageDraw.ImageDraw) -> None:
    for x in range(0, SLIDE_W_PX, 80):
        draw.line((x, 0, x, SLIDE_H_PX), fill=(*_rgb(COLORS["teal"]), 45), width=1)
    for y in range(0, SLIDE_H_PX, 80):
        draw.line((0, y, SLIDE_W_PX, y), fill=(*_rgb(COLORS["teal"]), 45), width=1)


def _motif(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = bbox
    for index in range(4):
        x = x1 + 24 + index * 44
        draw.ellipse((x, y2 - 54, x + 9, y2 - 45), outline=(*_rgb(COLORS["gold"]), 120), width=2)


def _draw_reference_chart(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(bbox, radius=16, fill=(*_rgb(COLORS["panel"]), 235), outline=(*_rgb(COLORS["cyan"]), 210), width=2)
    x1, y1, x2, y2 = bbox
    base = y2 - 42
    for idx, value in enumerate([62, 70, 76, 86]):
        x = x1 + 50 + idx * 110
        h = round(value * 2.4)
        draw.rectangle((x, base - h, x + 46, base), fill=(*_rgb(COLORS["cyan"]), 220))
        _draw_text(draw, x - 4, base + 8, f"Q{idx + 1}", 8, COLORS["muted"], bold=False)


def _draw_reference_table(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(bbox, radius=10, fill=(*_rgb(COLORS["panel"]), 235), outline=(*_rgb(COLORS["cyan"]), 210), width=2)
    x1, y1, x2, y2 = bbox
    cols, rows = 4, 5
    for col in range(1, cols):
        x = x1 + round((x2 - x1) * col / cols)
        draw.line((x, y1, x, y2), fill=(*_rgb(COLORS["cyan"]), 120), width=2)
    for row in range(1, rows):
        y = y1 + round((y2 - y1) * row / rows)
        color = COLORS["gold"] if row == 1 else COLORS["cyan"]
        draw.line((x1, y, x2, y), fill=(*_rgb(color), 140), width=3 if row == 1 else 2)


def _preview_icon(draw: ImageDraw.ImageDraw, bbox: tuple[int, int, int, int], glyph: str, color: str) -> None:
    x1, y1, x2, y2 = bbox
    size = min(x2 - x1, y2 - y1)
    draw.ellipse((x1, y1, x1 + size, y1 + size), outline=(*_rgb(color), 230), width=max(2, size // 16))
    draw.line((x1 + size * 0.30, y1 + size * 0.55, x1 + size * 0.48, y1 + size * 0.70, x1 + size * 0.72, y1 + size * 0.33), fill=(*_rgb(color), 230), width=max(2, size // 20))
    if glyph in {"gauge", "valve"}:
        draw.ellipse((x1 + size * 0.34, y1 + size * 0.25, x1 + size * 0.66, y1 + size * 0.57), outline=(*_rgb(color), 230), width=max(1, size // 24))


def _px(bbox: dict[str, float]) -> tuple[int, int, int, int]:
    return (round(bbox["x"] * SLIDE_W_PX), round(bbox["y"] * SLIDE_H_PX), round((bbox["x"] + bbox["w"]) * SLIDE_W_PX), round((bbox["y"] + bbox["h"]) * SLIDE_H_PX))


def _connector_points(bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return x1, (y1 + y2) // 2, x2, (y1 + y2) // 2


def _draw_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, size: int, color: str, *, bold: bool) -> None:
    try:
        font = ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", max(8, size * 2))
    except OSError:
        font = ImageFont.load_default()
    draw.multiline_text((x, y), text, fill=(*_rgb(color), 255), font=font, spacing=4)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[index : index + 2], 16) for index in (0, 2, 4))
