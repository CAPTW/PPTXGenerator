"""Contact sheets for E03.5 icon-v7.1 batch object placement."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


REQUIRED_CONTACTS = (
    "e03_3_vs_e03_5_reference_vs_render_contact_sheet.png",
    "e03_5_16_reference_vs_render_contact_sheet.png",
    "e03_5_icon_visibility_contact_sheet.png",
    "e03_5_icon_v7_1_usage_contact_sheet.png",
    "e03_5_svg_media_ooxml_contact_sheet.png",
    "e03_5_bbox_overlay_contact_sheet.png",
    "e03_5_region_iou_contact_sheet.png",
    "e03_5_object_overlay_contact_sheet.png",
    "e03_5_z_order_contact_sheet.png",
    "e03_5_semantic_editability_contact_sheet.png",
    "e03_5_chart_table_component_contact_sheet.png",
    "e03_5_raster_policy_contact_sheet.png",
    "e03_5_visual_rhythm_contact_sheet.png",
    "e03_5_failures_or_patch_queue_contact_sheet.png",
)


def build_e03_5_contact_sheets(output_root: Path, rows: dict[str, dict[str, Any]], summaries: dict[str, Any], *, pack_created: bool) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _image_grid(render_dir / "e03_3_vs_e03_5_reference_vs_render_contact_sheet.png", rows, "previous_e03_3_render", "rendered_candidate", "E03.3 vs E03.5")
    _image_grid(render_dir / "e03_5_16_reference_vs_render_contact_sheet.png", rows, "reference_image", "rendered_candidate", "Reference vs E03.5")
    _image_grid(render_dir / "e03_5_icon_visibility_contact_sheet.png", rows, "rendered_candidate", "icon_visibility_overlay", "Icon Visibility")
    _summary_sheet(render_dir / "e03_5_icon_v7_1_usage_contact_sheet.png", "Icon v7.1 Usage", summaries.get("icon_usage_summary", {}))
    _summary_sheet(render_dir / "e03_5_svg_media_ooxml_contact_sheet.png", "SVG Media OOXML", summaries.get("icon_ooxml_summary", {}))
    _image_grid(render_dir / "e03_5_bbox_overlay_contact_sheet.png", rows, "reference_image", "object_overlay", "Bbox Overlay")
    _summary_sheet(render_dir / "e03_5_region_iou_contact_sheet.png", "Region IoU", summaries.get("region_iou_summary", {}))
    _image_grid(render_dir / "e03_5_object_overlay_contact_sheet.png", rows, "rendered_candidate", "object_overlay", "Object Overlay")
    _summary_sheet(render_dir / "e03_5_z_order_contact_sheet.png", "Z Order", summaries.get("z_order_summary", {}))
    _summary_sheet(render_dir / "e03_5_semantic_editability_contact_sheet.png", "Semantic Editability", summaries.get("semantic_editability_summary", {}))
    _summary_sheet(render_dir / "e03_5_chart_table_component_contact_sheet.png", "Chart/Table", summaries.get("chart_table_summary", {}))
    _summary_sheet(render_dir / "e03_5_raster_policy_contact_sheet.png", "Raster Policy", summaries.get("raster_policy_summary", {}))
    _summary_sheet(render_dir / "e03_5_visual_rhythm_contact_sheet.png", "Visual Rhythm", summaries.get("visual_rhythm_summary", {}))
    _summary_sheet(render_dir / "e03_5_failures_or_patch_queue_contact_sheet.png", "Patch Queue", summaries.get("patch_queue", {}))
    if pack_created and not (render_dir / "e03_5_16_candidate_pack_contact_sheet.png").exists():
        _image_grid(render_dir / "e03_5_16_candidate_pack_contact_sheet.png", rows, "rendered_candidate", "rendered_candidate", "E03.5 Pack")
    paths = {name.removesuffix(".png"): (render_dir / name).as_posix() for name in REQUIRED_CONTACTS}
    if pack_created:
        paths["e03_5_16_candidate_pack_contact_sheet"] = (render_dir / "e03_5_16_candidate_pack_contact_sheet.png").as_posix()
    return {
        "schema_name": "e03_5_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in REQUIRED_CONTACTS) else "failed",
        "paths": paths,
    }


def _image_grid(output: Path, rows: dict[str, dict[str, Any]], left_key: str, right_key: str, title: str) -> None:
    cell_w, cell_h = 360, 230
    cols = 2
    sheet = Image.new("RGB", (cols * cell_w, 8 * cell_h + 42), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), title, fill="#F8FAFC", font=font)
    for idx, (archetype, row) in enumerate(rows.items()):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h + 42
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 8, y + 8), archetype[:34], fill="#F5A623", font=font)
        _paste(sheet, Path(row.get(left_key, "")), x + 8, y + 34, 164, 92)
        _paste(sheet, Path(row.get(right_key, "")), x + 188, y + 34, 164, 92)
        draw.text((x + 8, y + 136), f"status: {row.get('status')}", fill="#9EC4C8", font=font)
        draw.text((x + 8, y + 156), f"icons: {row.get('icon_v7_1_usage_count', 0)} invisible: {row.get('invisible_icon_count', 0)}", fill="#CBD5E1", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _summary_sheet(output: Path, title: str, payload: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (960, 540), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            draw.text((24, y), f"{key}: {value}"[:125], fill="#F5A623", font=font)
            y += 24
            if y > 510:
                break
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste(sheet: Image.Image, path: Path, x: int, y: int, width: int, height: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
