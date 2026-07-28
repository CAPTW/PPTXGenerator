"""Object overlay rendering for E01X QA artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def render_overlay_images(reference_image: Path, objects: list[dict[str, Any]], overlay_path: Path, comparison_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover - Pillow is a project dependency.
        return {"status": "unavailable", "error": str(exc)}

    if not reference_image.is_file():
        return {"status": "missing_reference_image", "error": str(reference_image)}

    image = Image.open(reference_image).convert("RGB")
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    colors = ["red", "blue", "green", "orange", "purple", "cyan"]
    for index, obj in enumerate(objects):
        bbox = obj.get("bbox_px") or {}
        x = int(round(float(bbox.get("x", 0))))
        y = int(round(float(bbox.get("y", 0))))
        w = int(round(float(bbox.get("w", 0))))
        h = int(round(float(bbox.get("h", 0))))
        color = colors[index % len(colors)]
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        draw.text((x + 3, y + 3), obj.get("object_id", "object"), fill=color, font=font)

    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(overlay_path)

    comparison = Image.new("RGB", (image.width * 2, image.height), "white")
    comparison.paste(image, (0, 0))
    comparison.paste(overlay, (image.width, 0))
    comparison.save(comparison_path)
    return {"status": "rendered", "overlay_path": str(overlay_path), "comparison_path": str(comparison_path), "object_count": len(objects)}
