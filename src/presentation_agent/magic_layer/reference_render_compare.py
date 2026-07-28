"""Reference-vs-render comparison helpers for D05."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .visual_similarity_metrics import compare_images


def build_reference_vs_render(reference_path: Path, render_path: Path, output_path: Path, *, label: str) -> dict[str, Any]:
    reference = Image.open(reference_path).convert("RGB")
    render = Image.open(render_path).convert("RGB").resize(reference.size)
    header_h = 32
    sheet = Image.new("RGB", (reference.width * 2, reference.height + header_h), "#111827")
    sheet.paste(reference, (0, header_h))
    sheet.paste(render, (reference.width, header_h))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((8, 10), f"{label}: reference", fill="#F8FAFC", font=font)
    draw.text((reference.width + 8, 10), "editable candidate render", fill="#F8FAFC", font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    metrics = compare_images(reference_path, render_path)
    return {**metrics, "reference_vs_render_path": output_path.as_posix()}


def build_contact_sheet(image_paths: list[Path], output_path: Path, *, label: str, columns: int = 3) -> dict[str, Any]:
    images = [Image.open(path).convert("RGB") for path in image_paths if path.exists()]
    if not images:
        raise ValueError("No images available for contact sheet.")
    thumb_w = 480
    thumb_h = 270
    header_h = 38
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + header_h)), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (path, image) in enumerate(zip([p for p in image_paths if p.exists()], images)):
        row = index // columns
        col = index % columns
        x = col * thumb_w
        y = row * (thumb_h + header_h)
        sheet.paste(image.resize((thumb_w, thumb_h)), (x, y + header_h))
        draw.text((x + 8, y + 12), path.parent.name, fill="#F8FAFC", font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return {"schema_name": "contact_sheet", "label": label, "image_count": len(images), "path": output_path.as_posix()}


def build_side_by_side(left_path: Path, right_path: Path, output_path: Path, *, left_label: str, right_label: str) -> dict[str, Any]:
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB").resize(left.size)
    header_h = 32
    sheet = Image.new("RGB", (left.width * 2, left.height + header_h), "#111827")
    sheet.paste(left, (0, header_h))
    sheet.paste(right, (left.width, header_h))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((8, 10), left_label, fill="#F8FAFC", font=font)
    draw.text((left.width + 8, 10), right_label, fill="#F8FAFC", font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return {"schema_name": "side_by_side_comparison", "path": output_path.as_posix(), "left": left_path.as_posix(), "right": right_path.as_posix()}
