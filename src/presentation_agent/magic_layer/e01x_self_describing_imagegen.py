"""Local self-describing image/reference generation for E01X.

This module deliberately does not call remote image APIs. It creates deterministic
design-reference and bounded visual assets from the self-describing intent so the
integration gate can exercise the PS-layer control artifacts locally.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


SLIDE_W = 1672
SLIDE_H = 941


def build_design_intent_trace() -> dict[str, Any]:
    slots = [
        _slot("background_base", "background_base", (0, 0, 1, 1), "ppt_shape_background", False, False, 0.95, 0),
        _slot("bg_texture", "decorative_texture", (0.70, 0.04, 0.24, 0.26), "bounded_nonsemantic_raster", False, True, 0.86, 4),
        _slot("hero", "hero_visual_field", (0.63, 0.17, 0.29, 0.55), "replaceable_image_frame", False, True, 0.92, 12),
        _slot("title", "title_text_region", (0.07, 0.10, 0.48, 0.11), "ppt_text_box", True, False, 0.93, 30, min_capacity_chars=54),
        _slot("subtitle", "subtitle_text_region", (0.075, 0.225, 0.44, 0.07), "ppt_text_box", True, False, 0.90, 31, min_capacity_chars=90),
        _slot("card_panel_1", "card_panel", (0.07, 0.36, 0.16, 0.25), "ppt_shape", True, False, 0.9, 20),
        _slot("card_panel_2", "card_panel", (0.255, 0.36, 0.16, 0.25), "ppt_shape", True, False, 0.9, 20),
        _slot("card_panel_3", "card_panel", (0.44, 0.36, 0.16, 0.25), "ppt_shape", True, False, 0.9, 20),
        _slot("card_text_1", "body_text_region", (0.085, 0.40, 0.13, 0.14), "ppt_text_box", True, False, 0.88, 34, min_capacity_chars=80),
        _slot("card_text_2", "body_text_region", (0.27, 0.40, 0.13, 0.14), "ppt_text_box", True, False, 0.88, 34, min_capacity_chars=80),
        _slot("card_text_3", "body_text_region", (0.455, 0.40, 0.13, 0.14), "ppt_text_box", True, False, 0.88, 34, min_capacity_chars=80),
        _slot("semantic_icon_1", "semantic_icon", (0.083, 0.645, 0.05, 0.08), "native_vector", True, False, 0.82, 35),
        _slot("source_footer_strip", "source_footer_strip", (0.04, 0.91, 0.92, 0.05), "ppt_shape", True, False, 0.92, 45),
        _slot("source_footer_text", "source_footer_text", (0.055, 0.925, 0.60, 0.025), "ppt_text_box", True, False, 0.86, 46, min_capacity_chars=100),
        _slot("technical_overlay", "technical_overlay", (0.02, 0.02, 0.94, 0.86), "ppt_shape", False, False, 0.78, 8),
    ]
    return {
        "schema_name": "e01x_design_intent_trace",
        "archetype": "standard_content_with_hero_visual_field",
        "slide_size": {"width_px": SLIDE_W, "height_px": SLIDE_H, "aspect_ratio": "16:9"},
        "style": {
            "maturity": "creative academic professional",
            "palette": ["deep navy", "dark teal", "off-white", "muted gold", "cyan"],
            "deck_feel": "premium consulting deck",
            "layout_notes": "clean protected text zones, elegant but not over-decorated",
            "avoid": "website/SaaS dashboard look",
        },
        "forbidden": [
            "full_slide_raster",
            "screenshot_slide",
            "semantic_raster_fallback",
            "decorations_over_text",
            "unreadable_microtext",
            "website/SaaS_dashboard_look",
        ],
        "slots": slots,
        "canva_parity_claimed": False,
    }


def build_asset_recipe_manifest(intent: dict[str, Any]) -> dict[str, Any]:
    hero_bbox = _slot_by_role(intent, "hero_visual_field")["bbox_norm_intended"]
    texture_bbox = _slot_by_role(intent, "decorative_texture")["bbox_norm_intended"]
    return {
        "schema_name": "e01x_asset_recipe_manifest",
        "asset_policy": "asset_first_bounded_nonsemantic_only",
        "assets": [
            {
                "asset_id": "IMG_HERO_01",
                "role": "hero_visual_field",
                "prompt": "Abstract academic research artifact: layered translucent topographic contours and soft light beams, no text, no icons, no charts.",
                "raster_allowed": True,
                "semantic_content_allowed": False,
                "target_resolution_px": {"w": 900, "h": 900},
                "insertion_policy": "replaceable_image_frame",
                "bbox_norm": hero_bbox,
                "mask_id": "M_HERO_ROUNDED",
                "crop_mode": "cover_center",
                "z_order": 12,
                "must_not_cover_text": True,
            },
            {
                "asset_id": "BG_TEXTURE_01",
                "role": "decorative_texture",
                "prompt": "Subtle dark teal grain and topology texture, no text, no symbols, no semantic marks.",
                "raster_allowed": True,
                "semantic_content_allowed": False,
                "target_resolution_px": {"w": 640, "h": 360},
                "insertion_policy": "bounded_decorative_texture",
                "bbox_norm": texture_bbox,
                "mask_id": None,
                "crop_mode": "cover_center",
                "z_order": 4,
                "must_not_cover_text": True,
            },
            {
                "asset_id": "optional_DECORATIVE_TEXTURE_01",
                "role": "decorative_margin_overlay",
                "prompt": "Sparse cyan topology linework, margin-only, no labels.",
                "raster_allowed": True,
                "semantic_content_allowed": False,
                "target_resolution_px": {"w": 640, "h": 360},
                "insertion_policy": "optional_bounded_margin_texture",
                "bbox_norm": {"x": 0.02, "y": 0.02, "w": 0.18, "h": 0.18},
                "mask_id": None,
                "crop_mode": "contain",
                "z_order": 5,
                "must_not_cover_text": True,
            },
        ],
        "canva_parity_claimed": False,
    }


def build_image_prompt(intent: dict[str, Any], ps_layer_intent: dict[str, Any], asset_recipe: dict[str, Any]) -> str:
    slots = ", ".join(slot["semantic_role"] for slot in intent["slots"])
    layers = ", ".join(layer["layer_id"] for layer in ps_layer_intent["layers"])
    assets = ", ".join(asset["asset_id"] for asset in asset_recipe["assets"])
    return "\n".join(
        [
            "# E01X Image Prompt",
            "",
            "Create one 16:9 PowerPoint template reference image. This is a design reference only, not final slide content.",
            "Style: creative academic professional, premium consulting, deep navy, dark teal, off-white, muted gold, cyan.",
            "Composition: protected editable text/card/footer zones on the left and lower rail; smart-object-like hero frame on the right.",
            f"Semantic slots: {slots}.",
            f"PS-layer control IDs: {layers}.",
            f"Bounded nonsemantic assets: {assets}.",
            "Use placeholders only. Do not include readable long body copy, tiny random labels, charts, tables, captions, semantic icons inside the hero image, or a website/SaaS dashboard look.",
            "Do not create a full-slide poster composition. Do not put semantic content inside raster visual fields.",
        ]
    )


def generate_local_reference_assets(intent: dict[str, Any], asset_recipe: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    assets_dir = output_dir / "generated_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    hero = _draw_hero_asset(assets_dir / "IMG_HERO_01.png", (900, 900))
    texture = _draw_texture_asset(assets_dir / "BG_TEXTURE_01.png", (640, 360))
    optional = _draw_optional_texture(assets_dir / "optional_DECORATIVE_TEXTURE_01.png", (640, 360))
    final_reference = output_dir / "final_reference.png"
    _draw_final_reference(intent, hero, texture, final_reference)
    return {
        "schema_name": "e01x_local_reference_generation_report",
        "status": "passed",
        "image_api_used": False,
        "openai_api_key_required": False,
        "final_reference": final_reference.as_posix(),
        "assets": [hero.as_posix(), texture.as_posix(), optional.as_posix()],
        "canva_parity_claimed": False,
    }


def _slot(
    slot_id: str,
    role: str,
    bbox: tuple[float, float, float, float],
    target: str,
    semantic_allowed: bool,
    raster_allowed: bool,
    confidence: float,
    z_order: int,
    *,
    min_capacity_chars: int | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "slot_id": slot_id,
        "semantic_role": role,
        "bbox_norm_intended": {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]},
        "primitive_target": target,
        "editable_required": True,
        "raster_allowed": raster_allowed,
        "semantic_content_allowed": semantic_allowed,
        "z_order_intended": z_order,
        "confidence": confidence,
    }
    if min_capacity_chars is not None:
        record["min_capacity_chars"] = min_capacity_chars
    return record


def _slot_by_role(intent: dict[str, Any], role: str) -> dict[str, Any]:
    return next(slot for slot in intent["slots"] if slot["semantic_role"] == role)


def _draw_hero_asset(path: Path, size: tuple[int, int]) -> Path:
    image = Image.new("RGB", size, "#0b2531")
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(18):
        inset = 30 + i * 22
        color = (45, 212, 255, max(18, 90 - i * 4))
        draw.rounded_rectangle((inset, inset * 0.8, size[0] - inset * 0.65, size[1] - inset), radius=80, outline=color, width=3)
    for i in range(10):
        x = int(size[0] * (0.18 + i * 0.07))
        y = int(size[1] * (0.22 + math.sin(i) * 0.12))
        draw.ellipse((x, y, x + 16, y + 16), fill=(244, 180, 63, 160))
    image = image.filter(ImageFilter.GaussianBlur(radius=0.3))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _draw_texture_asset(path: Path, size: tuple[int, int]) -> Path:
    image = Image.new("RGB", size, "#081a24")
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(0, size[0], 28):
        alpha = 28 + (i % 90)
        draw.line((i, 0, i - 140, size[1]), fill=(38, 120, 132, alpha), width=2)
    for y in range(20, size[1], 42):
        draw.arc((20, y - 80, size[0] - 20, y + 120), start=185, end=355, fill=(45, 212, 255, 30), width=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _draw_optional_texture(path: Path, size: tuple[int, int]) -> Path:
    image = Image.new("RGB", size, "#0d222e")
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(12):
        x = 30 + i * 45
        draw.line((x, 40, x + 100, 240), fill=(45, 212, 255, 70), width=2)
        draw.ellipse((x + 96, 236, x + 108, 248), fill=(244, 180, 63, 130))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _draw_final_reference(intent: dict[str, Any], hero_path: Path, texture_path: Path, output_path: Path) -> None:
    image = Image.new("RGB", (SLIDE_W, SLIDE_H), "#061526")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, SLIDE_W, SLIDE_H), fill=(6, 21, 38, 255))
    texture = Image.open(texture_path).resize((402, 245)).convert("RGBA")
    texture.putalpha(135)
    image.paste(texture, (int(0.70 * SLIDE_W), int(0.04 * SLIDE_H)), texture)

    hero_bbox = _px(_slot_by_role(intent, "hero_visual_field")["bbox_norm_intended"])
    hero = Image.open(hero_path).resize((hero_bbox[2], hero_bbox[3])).convert("RGBA")
    mask = Image.new("L", (hero_bbox[2], hero_bbox[3]), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, hero_bbox[2], hero_bbox[3]), radius=40, fill=255)
    image.paste(hero, (hero_bbox[0], hero_bbox[1]), mask)
    draw.rounded_rectangle((hero_bbox[0], hero_bbox[1], hero_bbox[0] + hero_bbox[2], hero_bbox[1] + hero_bbox[3]), radius=40, outline=(45, 212, 255, 180), width=3)

    for slot in intent["slots"]:
        role = slot["semantic_role"]
        x, y, w, h = _px(slot["bbox_norm_intended"])
        if role == "title_text_region":
            _text(draw, (x, y), "TITLE PLACEHOLDER", 46, fill=(248, 250, 252, 255))
        elif role == "subtitle_text_region":
            _text(draw, (x, y), "Subtitle / context placeholder", 24, fill=(196, 219, 220, 255))
        elif role == "card_panel":
            draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=(12, 49, 61, 215), outline=(45, 212, 255, 95), width=2)
        elif role == "body_text_region":
            _text(draw, (x, y), "Editable body slot", 19, fill=(238, 242, 232, 255))
            draw.rectangle((x, y + 42, x + int(w * 0.76), y + 47), fill=(244, 180, 63, 180))
        elif role == "semantic_icon":
            draw.ellipse((x, y, x + w, y + h), fill=(45, 212, 255, 210))
            draw.polygon([(x + w * 0.50, y + h * 0.20), (x + w * 0.78, y + h * 0.70), (x + w * 0.22, y + h * 0.70)], fill=(6, 21, 38, 255))
        elif role == "source_footer_strip":
            draw.rectangle((x, y, x + w, y + h), fill=(4, 16, 29, 240))
            draw.line((x, y, x + w, y), fill=(244, 180, 63, 180), width=2)
        elif role == "source_footer_text":
            _text(draw, (x, y), "SOURCE / FOOTER PLACEHOLDER", 15, fill=(196, 219, 220, 255))
    for i in range(10):
        x = int(SLIDE_W * (0.05 + i * 0.075))
        y = int(SLIDE_H * (0.79 + math.sin(i * 1.7) * 0.025))
        draw.ellipse((x, y, x + 8, y + 8), fill=(45, 212, 255, 95))
        if i > 0:
            px = int(SLIDE_W * (0.05 + (i - 1) * 0.075)) + 4
            py = int(SLIDE_H * (0.79 + math.sin((i - 1) * 1.7) * 0.025)) + 4
            draw.line((px, py, x + 4, y + 4), fill=(45, 212, 255, 55), width=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _px(bbox: dict[str, float]) -> tuple[int, int, int, int]:
    return round(bbox["x"] * SLIDE_W), round(bbox["y"] * SLIDE_H), round(bbox["w"] * SLIDE_W), round(bbox["h"] * SLIDE_H)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, *, fill: tuple[int, int, int, int]) -> None:
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    draw.text(xy, text, font=font, fill=fill)
