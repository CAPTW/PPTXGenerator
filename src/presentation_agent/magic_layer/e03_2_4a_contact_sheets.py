"""Contact sheets for E03.2.4A annotation application."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = (
    "annotation_application_contact_sheet.png",
    "human_review_resolution_contact_sheet.png",
    "rejected_crop_resolution_contact_sheet.png",
    "p0_p1_role_resolution_contact_sheet.png",
    "crop_vs_authored_svg_contact_sheet.png",
    "approved_library_matches_contact_sheet.png",
    "curated_v5_vs_v6_contact_sheet.png",
    "e03_3_icon_readiness_v6_contact_sheet.png",
)


def build_e03_2_4a_contact_sheets(
    output_root: Path,
    *,
    review_resolution: dict[str, Any],
    role_resolution: dict[str, Any],
    authored_quality: dict[str, Any],
    approved_library_report: dict[str, Any],
    curated_coverage: dict[str, Any],
    readiness: dict[str, Any],
    v5_root: Path,
    v6_root: Path,
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _text_sheet(render_dir / "annotation_application_contact_sheet.png", "Annotation Application", _resolution_lines(review_resolution))
    _text_sheet(render_dir / "human_review_resolution_contact_sheet.png", "Human Review Resolution", _resolution_lines(review_resolution))
    _crop_rows(render_dir / "rejected_crop_resolution_contact_sheet.png", review_resolution.get("rejected_crops", []), "rejected")
    _text_sheet(render_dir / "p0_p1_role_resolution_contact_sheet.png", "P0/P1 Role Resolution", _role_lines(role_resolution))
    _crop_vs_svg_sheet(render_dir / "crop_vs_authored_svg_contact_sheet.png", authored_quality.get("passed_icons", []))
    _svg_rows(render_dir / "approved_library_matches_contact_sheet.png", approved_library_report.get("approved_library_matches", []), "approved library")
    _v5_v6_sheet(render_dir / "curated_v5_vs_v6_contact_sheet.png", curated_coverage.get("roles", []), v5_root, v6_root)
    _text_sheet(render_dir / "e03_3_icon_readiness_v6_contact_sheet.png", "E03.3 Readiness", _readiness_lines(readiness))
    return {
        "schema_name": "e03_2_4a_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACT_NAMES) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACT_NAMES},
    }


def _resolution_lines(report: dict[str, Any]) -> list[str]:
    return [f"{key}: {report.get(key)}" for key in ("status", "resolved_count", "approved_library_match_count", "approved_for_authoring_count", "rejected_crop_count", "unresolved_p0_count", "unresolved_p1_count")]


def _role_lines(report: dict[str, Any]) -> list[str]:
    return [f"{key}: {report.get(key)}" for key in ("status", "role_count", "resolved_library_count", "resolved_authored_svg_count", "unresolved_p0_count", "unresolved_required_p1_count")]


def _readiness_lines(report: dict[str, Any]) -> list[str]:
    return [f"{key}: {report.get(key)}" for key in ("decision", "e03_3_unlocked", "unresolved_p0_count", "unresolved_required_p1_count", "semantic_raster_icon_count", "protected_artifacts_unchanged")]


def _text_sheet(output: Path, title: str, rows: list[str]) -> None:
    sheet = Image.new("RGB", (980, 360), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for row in rows:
        draw.text((24, y), row[:120], fill="#F5A623", font=font)
        y += 28
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _crop_rows(output: Path, rows: list[dict[str, Any]], label: str) -> None:
    cell_w, cell_h = 250, 104
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), str(row.get("review_id", ""))[:30], fill="#F8FAFC", font=font)
        draw.text((x + 5, y + 22), f"{row.get('role') or row.get('role_guess')} {label}"[:34], fill="#F5A623", font=font)
        _paste_image(sheet, Path(row.get("cleaned_glyph_crop") or row.get("raw_crop") or ""), x + 178, y + 36, 58)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _crop_vs_svg_sheet(output: Path, rows: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 230, 110
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), str(row.get("role", ""))[:24], fill="#F5A623", font=font)
        _paste_image(sheet, Path(row.get("source_crop_path") or row.get("cleaned_glyph_crop") or ""), x + 20, y + 38, 54)
        _paste_svg(sheet, Path(row.get("svg_path") or ""), x + 135, y + 38)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _svg_rows(output: Path, rows: list[dict[str, Any]], label: str) -> None:
    cell_w, cell_h = 220, 100
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), str(row.get("role", ""))[:24], fill="#F8FAFC", font=font)
        draw.text((x + 5, y + 22), label[:28], fill="#9EC4C8", font=font)
        _paste_svg(sheet, Path(row.get("source_path") or row.get("svg_path") or ""), x + 82, y + 40)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _v5_v6_sheet(output: Path, roles: list[dict[str, Any]], v5_root: Path, v6_root: Path) -> None:
    if not roles:
        roles = [{"role": path.stem} for path in list(v5_root.glob("*.svg"))[:48]]
    cell_w, cell_h = 180, 96
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(roles) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(roles[:64]):
        role = row["role"]
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), role[:22], fill="#F8FAFC", font=font)
        _paste_svg(sheet, v5_root / f"{role}.svg", x + 24, y + 34)
        _paste_svg(sheet, v6_root / f"{role}.svg", x + 106, y + 34)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste_image(sheet: Image.Image, path: Path, x: int, y: int, max_size: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (max_size - image.width) // 2, y + (max_size - image.height) // 2))


def _paste_svg(sheet: Image.Image, svg_path: Path, x: int, y: int) -> None:
    if not svg_path.exists():
        return
    temp = svg_path.with_suffix(".e03_2_4a_tmp.png")
    try:
        cairosvg.svg2png(url=svg_path.as_posix(), write_to=temp.as_posix(), output_width=54, output_height=54)
        image = Image.open(temp).convert("RGBA")
        sheet.paste(Image.new("RGB", image.size, "#F8FAFC"), (x, y))
        sheet.paste(image, (x, y), image)
    finally:
        temp.unlink(missing_ok=True)
