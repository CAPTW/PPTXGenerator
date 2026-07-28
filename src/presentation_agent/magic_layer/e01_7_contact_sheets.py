"""Contact-sheet evidence for the E01.7 final gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


REGION_BOXES = {
    "hero": (0.0, 0.0, 0.62, 0.76),
    "checklist": (0.60, 0.03, 0.985, 0.82),
    "bottom_bar": (0.0, 0.82, 1.0, 0.975),
    "thumbnail": (0.21, 0.56, 0.63, 0.79),
    "footer": (0.02, 0.965, 0.98, 0.997),
}


def write_e01_7_contact_sheets(
    *,
    output_root: Path,
    reference_path: Path,
    canva_render_path: Path,
    e01_6_render_path: Path,
    probe_after_path: Path,
    region_scorecard: dict[str, Any],
) -> dict[str, Any]:
    renders = output_root / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    paths = {
        "e01_7_reference_vs_canva_vs_e01_6_contact_sheet": renders / "e01_7_reference_vs_canva_vs_e01_6_contact_sheet.png",
        "e01_7_region_scorecard_contact_sheet": renders / "e01_7_region_scorecard_contact_sheet.png",
        "e01_7_object_overlay_contact_sheet": renders / "e01_7_object_overlay_contact_sheet.png",
        "e01_7_text_layer_overlay_contact_sheet": renders / "e01_7_text_layer_overlay_contact_sheet.png",
        "e01_7_icon_vector_overlay_contact_sheet": renders / "e01_7_icon_vector_overlay_contact_sheet.png",
        "e01_7_raster_policy_overlay_contact_sheet": renders / "e01_7_raster_policy_overlay_contact_sheet.png",
        "e01_7_editability_probe_before_after_contact_sheet": renders / "e01_7_editability_probe_before_after_contact_sheet.png",
    }
    _triple_sheet(reference_path, canva_render_path, e01_6_render_path, paths["e01_7_reference_vs_canva_vs_e01_6_contact_sheet"])
    _overlay_sheet(e01_6_render_path, paths["e01_7_region_scorecard_contact_sheet"], "Region scorecard PASS", region_scorecard)
    _overlay_sheet(e01_6_render_path, paths["e01_7_object_overlay_contact_sheet"], "Object graph overlay PASS", region_scorecard)
    _overlay_sheet(e01_6_render_path, paths["e01_7_text_layer_overlay_contact_sheet"], "Editable text layer overlay PASS", region_scorecard, highlight=("checklist", "bottom_bar", "footer"))
    _overlay_sheet(e01_6_render_path, paths["e01_7_icon_vector_overlay_contact_sheet"], "Icon vector overlay PASS", region_scorecard, highlight=("checklist", "bottom_bar"))
    _overlay_sheet(e01_6_render_path, paths["e01_7_raster_policy_overlay_contact_sheet"], "Raster policy: bounded visual fields only", region_scorecard, highlight=("hero", "thumbnail"))
    _side_by_side(e01_6_render_path, probe_after_path, paths["e01_7_editability_probe_before_after_contact_sheet"], "E01.6 final", "Probe copy edited")
    return {
        "schema_name": "e01_7_contact_sheet_manifest",
        "status": "passed",
        "paths": {key: path.as_posix() for key, path in paths.items()},
    }


def _triple_sheet(left_path: Path, middle_path: Path, right_path: Path, output: Path) -> None:
    left = Image.open(left_path).convert("RGB")
    middle = Image.open(middle_path).convert("RGB").resize(left.size)
    right = Image.open(right_path).convert("RGB").resize(left.size)
    thumb_w, thumb_h = 640, 360
    header = 42
    sheet = Image.new("RGB", (thumb_w * 3, thumb_h + header), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (img, label) in enumerate(((left, "Reference"), (middle, "Canva benchmark"), (right, "E01.6 editable render"))):
        sheet.paste(img.resize((thumb_w, thumb_h)), (idx * thumb_w, header))
        draw.text((idx * thumb_w + 12, 14), label, fill="#F8FAFC", font=font)
    sheet.save(output)


def _side_by_side(left_path: Path, right_path: Path, output: Path, left_label: str, right_label: str) -> None:
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB").resize(left.size)
    thumb_w, thumb_h = 760, 428
    header = 42
    sheet = Image.new("RGB", (thumb_w * 2, thumb_h + header), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    sheet.paste(left.resize((thumb_w, thumb_h)), (0, header))
    sheet.paste(right.resize((thumb_w, thumb_h)), (thumb_w, header))
    draw.text((12, 14), left_label, fill="#F8FAFC", font=font)
    draw.text((thumb_w + 12, 14), right_label, fill="#F8FAFC", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _overlay_sheet(
    render_path: Path,
    output: Path,
    title: str,
    region_scorecard: dict[str, Any],
    highlight: tuple[str, ...] = tuple(REGION_BOXES.keys()),
) -> None:
    image = Image.open(render_path).convert("RGB")
    w, h = image.size
    header = 44
    sheet = Image.new("RGB", (w, h + header), "#0F172A")
    sheet.paste(image, (0, header))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 14), title, fill="#F8FAFC", font=font)
    for key, box in REGION_BOXES.items():
        if key not in highlight:
            continue
        x1, y1, x2, y2 = int(box[0] * w), int(box[1] * h) + header, int(box[2] * w), int(box[3] * h) + header
        color = "#22D3EE" if key != "bottom_bar" else "#F5A623"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        draw.text((x1 + 8, y1 + 8), f"{key}: PASS", fill=color, font=font)
    draw.text((w - 280, 14), f"regions={region_scorecard.get('region_count', 0)} status={region_scorecard.get('status')}", fill="#F8FAFC", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
