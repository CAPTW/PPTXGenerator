"""Contact sheets for E03.2.2 icon hygiene outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = (
    "icon_candidate_hygiene_overview.png",
    "auto_reject_non_icon_candidates.png",
    "auto_accept_clean_icons.png",
    "human_review_required_contact_sheet.png",
    "glyph_split_before_after_contact_sheet.png",
    "normalized_glyph_crop_contact_sheet.png",
    "observed_glyph_vs_library_match_contact_sheet.png",
    "observed_glyph_vs_generated_svg_v2_contact_sheet.png",
    "curated_v3_vs_v4_contact_sheet.png",
    "e03_3_readiness_icon_gate_contact_sheet.png",
)


def build_e03_2_2_contact_sheets(
    output_root: Path,
    *,
    hygiene: dict[str, Any],
    split_report: dict[str, Any],
    glyph_manifest: dict[str, Any],
    rematch_report: dict[str, Any],
    human_review: dict[str, Any],
    quality_report: dict[str, Any],
    coverage: dict[str, Any],
    readiness: dict[str, Any],
    v3_root: Path,
    v4_root: Path,
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _candidate_grid(render_dir / "icon_candidate_hygiene_overview.png", hygiene.get("candidates", []), "all")
    _candidate_grid(render_dir / "auto_reject_non_icon_candidates.png", hygiene.get("auto_reject_non_icons", []), "reject")
    _candidate_grid(render_dir / "auto_accept_clean_icons.png", hygiene.get("auto_accept_clean_icons", []), "accept")
    _candidate_grid(render_dir / "human_review_required_contact_sheet.png", human_review.get("icons", []), "review")
    _split_grid(render_dir / "glyph_split_before_after_contact_sheet.png", split_report.get("icons", []))
    _normalized_grid(render_dir / "normalized_glyph_crop_contact_sheet.png", glyph_manifest.get("icons", []))
    _match_grid(render_dir / "observed_glyph_vs_library_match_contact_sheet.png", rematch_report.get("decisions", []))
    _generated_grid(render_dir / "observed_glyph_vs_generated_svg_v2_contact_sheet.png", quality_report.get("icons", []))
    _v3_v4_grid(render_dir / "curated_v3_vs_v4_contact_sheet.png", coverage.get("roles", []), v3_root, v4_root)
    _readiness_sheet(render_dir / "e03_3_readiness_icon_gate_contact_sheet.png", readiness)
    return {
        "schema_name": "e03_2_2_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACT_NAMES) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACT_NAMES},
    }


def _candidate_grid(output: Path, rows: list[dict[str, Any]], label: str) -> None:
    cell = (150, 120)
    cols = 5
    sheet = Image.new("RGB", (cols * cell[0], max(1, ((len(rows) + cols - 1) // cols)) * cell[1]), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:80]):
        x = (idx % cols) * cell[0]
        y = (idx // cols) * cell[1]
        draw.rectangle((x, y, x + cell[0], y + cell[1]), fill="#111827")
        draw.text((x + 5, y + 5), (row.get("likely_role") or row.get("proposed_role") or "")[:20], fill="#F8FAFC", font=font)
        draw.text((x + 5, y + 20), (row.get("hygiene_classification") or row.get("review_status") or label)[:24], fill="#F5A623", font=font)
        path = Path(row.get("normalized_crop_path") or row.get("glyph_only_crop") or row.get("raw_crop") or "")
        _paste_image(sheet, path, x + 36, y + 42, 72)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _split_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    cell = (190, 112)
    cols = 4
    sheet = Image.new("RGB", (cols * cell[0], max(1, ((len(rows) + cols - 1) // cols)) * cell[1]), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        x = (idx % cols) * cell[0]
        y = (idx // cols) * cell[1]
        draw.rectangle((x, y, x + cell[0], y + cell[1]), fill="#111827")
        draw.text((x + 5, y + 5), row["likely_role"][:20], fill="#F5A623", font=font)
        _paste_image(sheet, Path(row["context_crop_path"]), x + 10, y + 32, 64)
        _paste_image(sheet, Path(row["glyph_crop_path"]), x + 104, y + 32, 64)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _normalized_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    _candidate_grid(output, [{**row, "normalized_crop_path": row.get("normalized_128_path")} for row in rows], "normalized")


def _match_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    cell = (220, 118)
    cols = 4
    sheet = Image.new("RGB", (cols * cell[0], max(1, ((len(rows) + cols - 1) // cols)) * cell[1]), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        x = (idx % cols) * cell[0]
        y = (idx // cols) * cell[1]
        draw.rectangle((x, y, x + cell[0], y + cell[1]), fill="#111827")
        draw.text((x + 5, y + 5), row["likely_role"][:20], fill="#F8FAFC", font=font)
        draw.text((x + 5, y + 20), row["classification"][:28], fill="#F5A623", font=font)
        _paste_image(sheet, Path(row.get("normalized_128_path", "")), x + 8, y + 42, 58)
        _paste_svg(sheet, Path(row.get("selected_svg_path") or ""), x + 106, y + 42)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _generated_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    cell = (190, 106)
    cols = 4
    sheet = Image.new("RGB", (cols * cell[0], max(1, ((len(rows) + cols - 1) // cols)) * cell[1]), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:48]):
        x = (idx % cols) * cell[0]
        y = (idx // cols) * cell[1]
        draw.rectangle((x, y, x + cell[0], y + cell[1]), fill="#111827")
        draw.text((x + 5, y + 5), row.get("role_slug", row.get("likely_role", ""))[:20], fill="#F5A623", font=font)
        _paste_image(sheet, Path(row.get("source_clean_glyph_path") or ""), x + 10, y + 32, 58)
        _paste_image(sheet, Path(row.get("preview_path") or ""), x + 104, y + 32, 58)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _v3_v4_grid(output: Path, rows: list[dict[str, Any]], v3_root: Path, v4_root: Path) -> None:
    cell = (180, 96)
    cols = 4
    sheet = Image.new("RGB", (cols * cell[0], max(1, ((len(rows) + cols - 1) // cols)) * cell[1]), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        x = (idx % cols) * cell[0]
        y = (idx // cols) * cell[1]
        draw.rectangle((x, y, x + cell[0], y + cell[1]), fill="#111827")
        draw.text((x + 5, y + 5), row["role"][:22], fill="#F8FAFC", font=font)
        _paste_svg(sheet, v3_root / f"{row['role']}.svg", x + 20, y + 34)
        _paste_svg(sheet, v4_root / f"{row['role']}.svg", x + 102, y + 34)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _readiness_sheet(output: Path, readiness: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (900, 360), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), "E03.3 icon gate readiness", fill="#F8FAFC", font=font)
    y = 64
    for key in ("decision", "e03_3_unlocked", "unresolved_p0_count", "unresolved_p1_count", "semantic_raster_icon_count", "protected_artifacts_unchanged"):
        draw.text((24, y), f"{key}: {readiness.get(key)}", fill="#F5A623" if key == "decision" else "#9EC4C8", font=font)
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
    temp = svg_path.with_suffix(".e03_2_2_tmp.png")
    try:
        cairosvg.svg2png(url=svg_path.as_posix(), write_to=temp.as_posix(), output_width=54, output_height=54)
        image = Image.open(temp).convert("RGBA")
        sheet.paste(Image.new("RGB", image.size, "#F8FAFC"), (x, y))
        sheet.paste(image, (x, y), image)
    finally:
        temp.unlink(missing_ok=True)
