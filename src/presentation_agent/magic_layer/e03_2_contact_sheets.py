"""Contact sheet and overlay generation for E03.2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = (
    "e03_1_vs_e03_2_target_contact_sheet.png",
    "e03_2_reference_vs_render_contact_sheet.png",
    "e03_2_bbox_overlay_contact_sheet.png",
    "e03_2_object_region_before_after_contact_sheet.png",
    "e03_2_failure_or_patch_queue_contact_sheet.png",
)


def build_e03_2_object_overlay(reference: Path, rendered: Path, graph: dict[str, Any], output: Path) -> None:
    with Image.open(rendered) as image:
        canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    width, height = canvas.size
    for node in graph["nodes"]:
        if not node["must_preserve"]:
            continue
        x0, y0, x1, y1 = node["bbox_norm"]
        box = (int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height))
        color = "#F5A623" if node["visual_priority"] == "high" else "#4AD6E8"
        draw.rectangle(box, outline=color, width=3)
        draw.text((box[0] + 4, box[1] + 4), node["object_id"], fill=color, font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def build_e03_2_contact_sheets(
    output_root: Path,
    *,
    reference: Path,
    e03_1_render: Path,
    e03_2_render: Path,
    object_overlay: Path,
    reference_vs_render: Path,
    gate_report: dict[str, Any],
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _triple_sheet(render_dir / "e03_1_vs_e03_2_target_contact_sheet.png", reference, e03_1_render, e03_2_render)
    _pair_sheet(render_dir / "e03_2_reference_vs_render_contact_sheet.png", reference, e03_2_render, "reference", "E03.2 render")
    _pair_sheet(render_dir / "e03_2_bbox_overlay_contact_sheet.png", e03_2_render, object_overlay, "E03.2 render", "bbox overlay")
    _pair_sheet(render_dir / "e03_2_object_region_before_after_contact_sheet.png", e03_1_render, object_overlay, "E03.1 target", "E03.2 object overlay")
    _failure_sheet(render_dir / "e03_2_failure_or_patch_queue_contact_sheet.png", reference_vs_render, gate_report)
    paths = {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACT_NAMES}
    return {"schema_name": "e03_2_contact_sheet_manifest", "status": "passed" if all((render_dir / name).exists() for name in CONTACT_NAMES) else "failed", "paths": paths}


def _triple_sheet(output: Path, reference: Path, before: Path, after: Path) -> None:
    images = [(_load(reference), "reference"), (_load(before), "E03.1 target"), (_load(after), "E03.2 golden")]
    thumb_w, thumb_h = 520, 292
    header = 42
    sheet = Image.new("RGB", (thumb_w * 3, thumb_h + header), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (image, label) in enumerate(images):
        x = idx * thumb_w
        draw.rectangle((x, 0, x + thumb_w, header), fill="#111827")
        draw.text((x + 10, 8), label, fill="#F8FAFC", font=font)
        draw.text((x + 10, 24), "visual_toc placement gate", fill="#F5A623", font=font)
        if image:
            image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (thumb_w - image.width) // 2, header + (thumb_h - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _pair_sheet(output: Path, left: Path, right: Path, left_label: str, right_label: str) -> None:
    images = [(_load(left), left_label), (_load(right), right_label)]
    thumb_w, thumb_h = 760, 428
    header = 42
    sheet = Image.new("RGB", (thumb_w * 2, thumb_h + header), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (image, label) in enumerate(images):
        x = idx * thumb_w
        draw.rectangle((x, 0, x + thumb_w, header), fill="#111827")
        draw.text((x + 10, 10), label, fill="#F8FAFC", font=font)
        if image:
            image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (thumb_w - image.width) // 2, header + (thumb_h - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _failure_sheet(output: Path, comparison: Path, gate_report: dict[str, Any]) -> None:
    image = _load(comparison)
    thumb_w, thumb_h = 900, 506
    side_w = 420
    sheet = Image.new("RGB", (thumb_w + side_w, thumb_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    if image:
        image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(image, ((thumb_w - image.width) // 2, (thumb_h - image.height) // 2))
    x = thumb_w
    draw.rectangle((x, 0, x + side_w, thumb_h), fill="#111827")
    draw.text((x + 16, 20), f"Gate: {gate_report['status']}", fill="#F5A623", font=font)
    draw.text((x + 16, 48), f"Decision failures: {len(gate_report.get('hard_gate_failures', []))}", fill="#F8FAFC", font=font)
    y = 80
    for failure in gate_report.get("hard_gate_failures", [])[:12]:
        draw.text((x + 16, y), f"- {failure}", fill="#EF6B5A", font=font)
        y += 22
    if not gate_report.get("hard_gate_failures"):
        draw.text((x + 16, y), "No open patch queue items.", fill="#9EC4C8", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _load(path: Path) -> Image.Image | None:
    if not path.exists():
        return None
    return Image.open(path).convert("RGB")
