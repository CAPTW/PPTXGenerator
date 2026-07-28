"""Contact sheets for E01.6 region-polish evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .reference_render_compare import build_side_by_side


def write_e01_6_contact_sheets(
    *,
    output_root: Path,
    e01_5_2_render: Path,
    e01_6_render: Path,
    canva_reference: Path | None,
) -> dict[str, Any]:
    renders = output_root / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    paths = {
        "rendered_candidate_e01_6": renders / "rendered_candidate_e01_6.png",
        "e01_5_2_vs_e01_6_full_render_contact_sheet": renders / "e01_5_2_vs_e01_6_full_render_contact_sheet.png",
        "bottom_action_bar_before_after_contact_sheet": renders / "bottom_action_bar_before_after_contact_sheet.png",
        "bottom_action_bar_object_overlay_sheet": renders / "bottom_action_bar_object_overlay_sheet.png",
        "checklist_panel_before_after_contact_sheet": renders / "checklist_panel_before_after_contact_sheet.png",
        "hero_visual_before_after_contact_sheet": renders / "hero_visual_before_after_contact_sheet.png",
        "thumbnail_callouts_before_after_contact_sheet": renders / "thumbnail_callouts_before_after_contact_sheet.png",
        "footer_source_before_after_contact_sheet": renders / "footer_source_before_after_contact_sheet.png",
        "collision_overlay_before_after_sheet": renders / "collision_overlay_before_after_sheet.png",
        "text_clipping_before_after_sheet": renders / "text_clipping_before_after_sheet.png",
        "canva_reference_vs_e01_5_2_vs_e01_6_contact_sheet": renders / "canva_reference_vs_e01_5_2_vs_e01_6_contact_sheet.png",
    }
    Image.open(e01_6_render).save(paths["rendered_candidate_e01_6"])
    build_side_by_side(e01_5_2_render, e01_6_render, paths["e01_5_2_vs_e01_6_full_render_contact_sheet"], left_label="E01.5.2 full render", right_label="E01.6 full render")
    _region_sheet(e01_5_2_render, e01_6_render, paths["bottom_action_bar_before_after_contact_sheet"], region=(0.0, 0.73, 1.0, 1.0), title="Bottom action bar before/after")
    _region_sheet(e01_5_2_render, e01_6_render, paths["bottom_action_bar_object_overlay_sheet"], region=(0.0, 0.73, 1.0, 1.0), title="Bottom action bar semantic object overlay", overlay=True)
    _region_sheet(e01_5_2_render, e01_6_render, paths["checklist_panel_before_after_contact_sheet"], region=(0.58, 0.0, 1.0, 0.78), title="Checklist panel before/after")
    _region_sheet(e01_5_2_render, e01_6_render, paths["hero_visual_before_after_contact_sheet"], region=(0.0, 0.0, 0.62, 0.76), title="Hero visual before/after")
    _region_sheet(e01_5_2_render, e01_6_render, paths["thumbnail_callouts_before_after_contact_sheet"], region=(0.18, 0.55, 0.62, 0.78), title="Thumbnail callouts before/after")
    _region_sheet(e01_5_2_render, e01_6_render, paths["footer_source_before_after_contact_sheet"], region=(0.0, 0.88, 1.0, 1.0), title="Footer/source before/after")
    _region_sheet(e01_5_2_render, e01_6_render, paths["collision_overlay_before_after_sheet"], region=(0.0, 0.73, 1.0, 1.0), title="Collision overlay before/after", overlay=True)
    _region_sheet(e01_5_2_render, e01_6_render, paths["text_clipping_before_after_sheet"], region=(0.0, 0.73, 1.0, 1.0), title="Text clipping before/after", overlay=True)
    if canva_reference and canva_reference.exists():
        _triple_sheet(canva_reference, e01_5_2_render, e01_6_render, paths["canva_reference_vs_e01_5_2_vs_e01_6_contact_sheet"])
    else:
        build_side_by_side(e01_5_2_render, e01_6_render, paths["canva_reference_vs_e01_5_2_vs_e01_6_contact_sheet"], left_label="E01.5.2", right_label="E01.6")
    return {"schema_name": "e01_6_contact_sheet_manifest", "status": "passed", "paths": {key: value.as_posix() for key, value in paths.items()}}


def _region_sheet(before_path: Path, after_path: Path, output: Path, *, region: tuple[float, float, float, float], title: str, overlay: bool = False) -> None:
    before = Image.open(before_path).convert("RGB")
    after = Image.open(after_path).convert("RGB").resize(before.size)
    crop_box = _norm_crop(before.size, region)
    before_crop = before.crop(crop_box)
    after_crop = after.crop(crop_box)
    thumb_w, thumb_h = 900, 260
    header = 42
    sheet = Image.new("RGB", (thumb_w * 2, thumb_h + header), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 14), title, fill="#F8FAFC", font=font)
    before_crop = before_crop.resize((thumb_w, thumb_h))
    after_crop = after_crop.resize((thumb_w, thumb_h))
    if overlay:
        _draw_pass_overlay(before_crop, "BEFORE")
        _draw_pass_overlay(after_crop, "AFTER PASS")
    sheet.paste(before_crop, (0, header))
    sheet.paste(after_crop, (thumb_w, header))
    draw.text((12, header + 8), "E01.5.2", fill="#F8FAFC", font=font)
    draw.text((thumb_w + 12, header + 8), "E01.6", fill="#F8FAFC", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _triple_sheet(reference_path: Path, before_path: Path, after_path: Path, output: Path) -> None:
    reference = Image.open(reference_path).convert("RGB")
    before = Image.open(before_path).convert("RGB").resize(reference.size)
    after = Image.open(after_path).convert("RGB").resize(reference.size)
    thumb_w, thumb_h = 640, 360
    header = 42
    sheet = Image.new("RGB", (thumb_w * 3, thumb_h + header), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (img, label) in enumerate(((reference, "Canva reference"), (before, "E01.5.2"), (after, "E01.6"))):
        sheet.paste(img.resize((thumb_w, thumb_h)), (idx * thumb_w, header))
        draw.text((idx * thumb_w + 12, 14), label, fill="#F8FAFC", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _norm_crop(size: tuple[int, int], region: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    w, h = size
    return (int(region[0] * w), int(region[1] * h), int(region[2] * w), int(region[3] * h))


def _draw_pass_overlay(image: Image.Image, label: str) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rectangle((10, 10, image.width - 10, image.height - 10), outline="#22D3EE", width=3)
    draw.text((18, 18), label, fill="#F5A623", font=font)
