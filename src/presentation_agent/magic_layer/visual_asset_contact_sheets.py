"""Diagnostic contact sheets for D07.2 visual-field asset import state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def build_render_lookup(render_manifest: dict[str, Any]) -> dict[int, Path]:
    lookup: dict[int, Path] = {}
    for slide in render_manifest.get("slides") or []:
        path = Path(slide.get("rendered_image_path") or "")
        if path.exists():
            lookup[int(slide["slide_index"])] = path
    return lookup


def create_visual_field_slot_inventory_contact_sheet(slot_file_map: dict[str, Any], render_lookup: dict[int, Path], output_path: Path) -> dict[str, Any]:
    return _create_diagnostic_sheet(
        slot_file_map.get("entries") or [],
        render_lookup,
        output_path,
        title="D07.2 visual field slot inventory",
        status_by_slot={entry["slot_id"]: "SLOT_INVENTORY" for entry in slot_file_map.get("entries") or []},
    )


def create_asset_import_missing_contact_sheet(slot_file_map: dict[str, Any], validation_report: dict[str, Any], render_lookup: dict[int, Path], output_path: Path) -> dict[str, Any]:
    missing = {item["slot_id"]: "MISSING_IMPORT" for item in validation_report.get("missing_assets") or []}
    return _create_diagnostic_sheet(
        slot_file_map.get("entries") or [],
        render_lookup,
        output_path,
        title="D07.2 missing visual-field imports",
        status_by_slot=missing,
    )


def create_asset_import_validation_contact_sheet(slot_file_map: dict[str, Any], validation_report: dict[str, Any], render_lookup: dict[int, Path], output_path: Path) -> dict[str, Any]:
    status_by_slot: dict[str, str] = {}
    for item in validation_report.get("accepted_assets") or []:
        status_by_slot[item["slot_id"]] = "ACCEPTED"
    for item in validation_report.get("missing_assets") or []:
        status_by_slot[item["slot_id"]] = "MISSING_IMPORT"
    for item in validation_report.get("rejected_assets") or []:
        status_by_slot[item["slot_id"]] = "REJECTED"
    return _create_diagnostic_sheet(
        slot_file_map.get("entries") or [],
        render_lookup,
        output_path,
        title="D07.2 visual-field import validation",
        status_by_slot=status_by_slot,
    )


def _create_diagnostic_sheet(
    entries: list[dict[str, Any]],
    render_lookup: dict[int, Path],
    output_path: Path,
    *,
    title: str,
    status_by_slot: dict[str, str],
) -> dict[str, Any]:
    if not entries:
        raise ValueError("No visual-field slots available for diagnostic sheet.")
    thumb_w = 480
    thumb_h = 270
    header_h = 64
    columns = 2
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + header_h)), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, entry in enumerate(entries):
        row = index // columns
        col = index % columns
        x = col * thumb_w
        y = row * (thumb_h + header_h)
        slide_path = render_lookup.get(int(entry.get("slide_number") or 0))
        if slide_path and slide_path.exists():
            image = Image.open(slide_path).convert("RGB").resize((thumb_w, thumb_h))
        else:
            image = Image.new("RGB", (thumb_w, thumb_h), "#1F2937")
        bbox = entry.get("bbox_norm") or [0, 0, 0, 0]
        box = [
            x + int(float(bbox[0]) * thumb_w),
            y + header_h + int(float(bbox[1]) * thumb_h),
            x + int((float(bbox[0]) + float(bbox[2])) * thumb_w),
            y + header_h + int((float(bbox[1]) + float(bbox[3])) * thumb_h),
        ]
        sheet.paste(image, (x, y + header_h))
        draw.rectangle(box, outline="#F59E0B", width=4)
        status = status_by_slot.get(entry["slot_id"], "NOT_REQUIRED")
        draw.rectangle([x, y, x + thumb_w, y + header_h], fill="#111827")
        draw.text((x + 8, y + 8), f"{title}", fill="#E5E7EB", font=font)
        draw.text((x + 8, y + 24), f"{entry['slide_id']} | {entry['role']} | {status}", fill="#F8FAFC", font=font)
        draw.text((x + 8, y + 42), f"{entry['slot_id']}", fill="#93C5FD", font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return {
        "schema_name": "visual_asset_diagnostic_contact_sheet",
        "status": "created",
        "title": title,
        "slot_count": len(entries),
        "path": output_path.as_posix(),
    }
