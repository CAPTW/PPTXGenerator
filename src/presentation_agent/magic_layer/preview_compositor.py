"""Debug overlays and preview composition for Magic Layer D01."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .image_asset import load_rgb


LAYER_COLORS = {
    "background_base": (120, 120, 120),
    "title_text_region": (255, 214, 84),
    "subtitle_text_region": (255, 214, 84),
    "body_text_region": (255, 214, 84),
    "source_footer_strip": (71, 214, 232),
    "icon_region": (230, 169, 58),
    "chart_region": (82, 202, 214),
    "table_region": (82, 202, 214),
    "matrix_region": (82, 202, 214),
    "hero_visual_field": (120, 220, 180),
    "image_frame": (120, 220, 180),
    "card_panel": (244, 241, 232),
    "unknown": (255, 80, 80),
}


def _font() -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def draw_overlay(image_path: Path, layers: list[dict[str, Any]], out_path: Path, *, mode: str) -> None:
    image = load_rgb(image_path).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font()
    for layer in layers:
        if mode == "unknown" and layer["layer_type"] != "unknown":
            continue
        x, y, w, h = layer["bbox_px"]
        color = LAYER_COLORS.get(layer["layer_type"], (255, 255, 255))
        alpha = 105 if mode == "layer_type" else 70
        if mode == "z_order":
            label = f"z{layer['z_order']} {layer['layer_type']}"
        elif mode == "unknown":
            label = f"{layer['layer_id']} {layer['unknown_disposition']}"
        else:
            label = f"{layer['layer_id']} {layer['layer_type']}"
        draw.rectangle((x, y, x + w, y + h), outline=color + (255,), width=3)
        draw.rectangle((x, y, min(x + max(120, len(label) * 6), image.width), y + 18), fill=color + (alpha,))
        draw.text((x + 4, y + 3), label, fill=(0, 0, 0, 255), font=font)
    composed = Image.alpha_composite(image, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(out_path)


def create_decomposed_preview(image_path: Path, layers: list[dict[str, Any]], out_path: Path) -> None:
    source = load_rgb(image_path)
    width, height = source.size
    bg = source.resize((1, 1), Image.Resampling.BILINEAR).getpixel((0, 0))
    preview = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(preview)
    for layer in sorted(layers, key=lambda item: item["z_order"]):
        if layer["layer_type"] == "background_base" or not layer.get("crop_path"):
            continue
        x, y, w, h = layer["bbox_px"]
        crop = Image.open(layer["crop_path"]).convert("RGB")
        preview.paste(crop, (x, y))
        color = LAYER_COLORS.get(layer["layer_type"], (255, 255, 255))
        draw.rectangle((x, y, x + w, y + h), outline=color, width=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(out_path)


def create_reference_vs_preview(reference_path: Path, preview_path: Path, out_path: Path) -> None:
    reference = load_rgb(reference_path)
    preview = load_rgb(preview_path)
    width = reference.width + preview.width
    height = max(reference.height, preview.height) + 28
    sheet = Image.new("RGB", (width, height), (3, 14, 21))
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 8), "reference", fill=(244, 241, 232), font=_font())
    draw.text((reference.width + 8, 8), "decomposed debug preview", fill=(244, 241, 232), font=_font())
    sheet.paste(reference, (0, 28))
    sheet.paste(preview, (reference.width, 28))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def write_previews(image_path: Path, layers: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    overlays = output_dir / "overlays"
    previews = output_dir / "previews"
    bbox = overlays / "bbox_overlay.png"
    layer_type = overlays / "layer_type_overlay.png"
    z_order = overlays / "z_order_overlay.png"
    unknown = overlays / "unknown_layer_overlay.png"
    for path, mode in ((bbox, "bbox"), (layer_type, "layer_type"), (z_order, "z_order"), (unknown, "unknown")):
        draw_overlay(image_path, layers, path, mode=mode)
    decomposed = previews / "decomposed_preview.png"
    comparison = previews / "reference_vs_preview.png"
    create_decomposed_preview(image_path, layers, decomposed)
    create_reference_vs_preview(image_path, decomposed, comparison)
    return {
        "schema_name": "preview_composition_report",
        "status": "passed",
        "purpose": "debug-only layer separation and approximate z-order preview; not final PPT output",
        "overlays": {
            "bbox_overlay": str(bbox),
            "layer_type_overlay": str(layer_type),
            "z_order_overlay": str(z_order),
            "unknown_layer_overlay": str(unknown),
        },
        "previews": {
            "decomposed_preview": str(decomposed),
            "reference_vs_preview": str(comparison),
        },
    }
