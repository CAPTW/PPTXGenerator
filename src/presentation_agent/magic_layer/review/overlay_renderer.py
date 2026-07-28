from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .overlay_schema import bbox_norm_to_px, validate_overlay_document


COLORS = {
    "info": (52, 122, 235),
    "warning": (245, 171, 53),
    "high": (220, 93, 32),
    "fatal": (210, 45, 45),
}


def render_overlay_image(source_image: str | Path, overlay_document: dict[str, Any], out_png: str | Path) -> dict[str, Any]:
    source = Path(source_image)
    out = Path(out_png)
    if not source.is_file():
        return {"schema": "overlay_render_report.v1", "status": "ERROR_MISSING_IMAGE", "pass": False, "source_image": str(source), "out_png": str(out), "errors": ["source image missing"]}
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return {
            "schema": "overlay_render_report.v1",
            "status": "OVERLAY_RENDER_UNSUPPORTED",
            "pass": True,
            "overlay_json_only": True,
            "source_image": str(source),
            "out_png": str(out),
            "errors": [],
            "warnings": ["Pillow is unavailable; overlay PNG was not rendered."],
        }

    validation = validate_overlay_document(overlay_document)
    if not validation["pass"]:
        return {"schema": "overlay_render_report.v1", "status": "ERROR_INVALID_OVERLAY", "pass": False, "errors": validation["failures"], "warnings": validation["warnings"]}

    image = Image.open(source).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    for item in validation["overlays"]:
        bbox = item.get("bbox_px")
        if bbox is None and item.get("bbox_norm") is not None:
            bbox = bbox_norm_to_px(item["bbox_norm"], width, height)
        if bbox is None:
            continue
        x, y, w, h = [int(value) for value in bbox]
        color = COLORS.get(item.get("severity", "info"), COLORS["info"])
        outline = (*color, 255)
        fill = (*color, 48)
        if item.get("draw_style") == "filled_translucent":
            draw.rectangle([x, y, x + w, y + h], outline=outline, fill=fill, width=3)
        elif item.get("draw_style") == "crosshatch":
            draw.rectangle([x, y, x + w, y + h], outline=outline, width=3)
            step = max(6, min(w, h) // 8 if min(w, h) > 0 else 6)
            for offset in range(-h, w + h, step):
                draw.line([x + offset, y, x + offset + h, y + h], fill=(*color, 120), width=1)
        elif item.get("draw_style") != "label_only":
            draw.rectangle([x, y, x + w, y + h], outline=outline, width=3)
        label = str(item.get("label") or item.get("overlay_item_id"))
        if label:
            label_y = max(0, y - 14)
            draw.rectangle([x, label_y, min(width, x + max(60, len(label) * 7)), label_y + 14], fill=(*color, 220))
            draw.text((x + 2, label_y), label, fill=(255, 255, 255, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    return {
        "schema": "overlay_render_report.v1",
        "status": "OVERLAY_RENDERED",
        "pass": True,
        "overlay_json_only": False,
        "source_image": str(source),
        "out_png": str(out),
        "item_count": len(validation["overlays"]),
        "warnings": validation["warnings"],
        "errors": [],
    }


def write_overlay_json(path: str | Path, overlay_document: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(overlay_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
