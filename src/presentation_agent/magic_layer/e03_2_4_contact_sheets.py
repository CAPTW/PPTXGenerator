"""Contact sheets for E03.2.4 human-reviewed complex icon authoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = (
    "e03_2_3_bad_svg_quarantine_contact_sheet.png",
    "generic_placeholder_svg_contact_sheet.png",
    "p0_p1_complex_icon_review_queue_contact_sheet.png",
    "human_review_resolution_contact_sheet.png",
    "crop_vs_authored_svg_contact_sheet.png",
    "authored_svg_quality_contact_sheet.png",
    "curated_v5_vs_v6_contact_sheet.png",
    "e03_3_icon_readiness_v6_contact_sheet.png",
)


def build_e03_2_4_contact_sheets(
    output_root: Path,
    *,
    quarantine_report: dict[str, Any],
    placeholder_report: dict[str, Any],
    review_queue: dict[str, Any],
    review_resolution: dict[str, Any],
    authored_quality: dict[str, Any],
    curated_coverage: dict[str, Any],
    readiness: dict[str, Any],
    v5_root: Path,
    v6_root: Path,
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _svg_rows(render_dir / "e03_2_3_bad_svg_quarantine_contact_sheet.png", quarantine_report.get("quarantined_svgs", []), "quarantined")
    _svg_rows(render_dir / "generic_placeholder_svg_contact_sheet.png", placeholder_report.get("placeholders", []), "placeholder")
    _review_queue_sheet(render_dir / "p0_p1_complex_icon_review_queue_contact_sheet.png", review_queue.get("items", []))
    _resolution_sheet(render_dir / "human_review_resolution_contact_sheet.png", review_resolution)
    _crop_vs_authored_sheet(render_dir / "crop_vs_authored_svg_contact_sheet.png", authored_quality.get("icons", []))
    _svg_rows(render_dir / "authored_svg_quality_contact_sheet.png", authored_quality.get("icons", []), "authored")
    _v5_v6_sheet(render_dir / "curated_v5_vs_v6_contact_sheet.png", curated_coverage.get("roles", []), v5_root, v6_root)
    _readiness_sheet(render_dir / "e03_3_icon_readiness_v6_contact_sheet.png", readiness)
    return {
        "schema_name": "e03_2_4_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACT_NAMES) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACT_NAMES},
    }


def _svg_rows(output: Path, rows: list[dict[str, Any]], label: str) -> None:
    cell_w, cell_h = 220, 114
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:80]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        role = row.get("role") or row.get("likely_role") or Path(row.get("svg_path", "")).stem
        draw.text((x + 5, y + 5), str(role)[:24], fill="#F8FAFC", font=font)
        reason = ",".join(row.get("quarantine_reasons", [])) or row.get("status", label)
        draw.text((x + 5, y + 21), reason[:32], fill="#F5A623", font=font)
        _paste_svg(sheet, Path(row.get("quarantine_path") or row.get("svg_path") or ""), x + 78, y + 46)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _review_queue_sheet(output: Path, rows: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 290, 112
    cols = 3
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:60]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 6, y + 6), row["review_id"][:34], fill="#F8FAFC", font=font)
        draw.text((x + 6, y + 22), f"{row['role_guess']} {row['priority']}"[:38], fill="#F5A623", font=font)
        draw.text((x + 6, y + 40), row["recommended_action"][:40], fill="#9EC4C8", font=font)
        _paste_image(sheet, Path(row.get("cleaned_glyph_crop") or row.get("raw_crop") or ""), x + 206, y + 42, 58)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _resolution_sheet(output: Path, resolution: dict[str, Any]) -> None:
    rows = [
        f"status: {resolution.get('status')}",
        f"annotations_present: {resolution.get('human_annotations_present')}",
        f"review_required: {resolution.get('human_review_required_count')}",
        f"resolved: {resolution.get('resolved_count')}",
        f"unresolved_p0: {resolution.get('unresolved_p0_count')}",
        f"unresolved_p1: {resolution.get('unresolved_p1_count')}",
    ]
    _text_sheet(output, "Human review resolution", rows)


def _crop_vs_authored_sheet(output: Path, rows: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 220, 110
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:60]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), row.get("role", "")[:24], fill="#F5A623", font=font)
        _paste_image(sheet, Path(row.get("source_crop_path") or ""), x + 20, y + 38, 54)
        _paste_svg(sheet, Path(row.get("svg_path") or ""), x + 134, y + 38)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _v5_v6_sheet(output: Path, roles: list[dict[str, Any]], v5_root: Path, v6_root: Path) -> None:
    if not roles:
        roles = [{"role": path.stem} for path in list(v5_root.glob("*.svg"))[:40]]
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
        _paste_svg(sheet, v5_root / f"{role}.svg", x + 22, y + 34)
        _paste_svg(sheet, v6_root / f"{role}.svg", x + 104, y + 34)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _readiness_sheet(output: Path, readiness: dict[str, Any]) -> None:
    rows = [f"{key}: {readiness.get(key)}" for key in ("decision", "e03_3_unlocked", "human_review_required_count", "unresolved_p0_count", "unresolved_p1_count", "semantic_raster_icon_count", "protected_artifacts_unchanged")]
    _text_sheet(output, "E03.3 v6 icon readiness", rows)


def _text_sheet(output: Path, title: str, rows: list[str]) -> None:
    sheet = Image.new("RGB", (920, 360), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for row in rows:
        draw.text((24, y), row, fill="#F5A623", font=font)
        y += 28
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
    temp = svg_path.with_suffix(".e03_2_4_tmp.png")
    try:
        cairosvg.svg2png(url=svg_path.as_posix(), write_to=temp.as_posix(), output_width=54, output_height=54)
        image = Image.open(temp).convert("RGBA")
        sheet.paste(Image.new("RGB", image.size, "#F8FAFC"), (x, y))
        sheet.paste(image, (x, y), image)
    finally:
        temp.unlink(missing_ok=True)
