"""Contact sheets for E03.2.3 complex icon vectorization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = (
    "stricter_hygiene_before_after_contact_sheet.png",
    "revised_auto_reject_non_icons.png",
    "complex_icon_clusters_contact_sheet.png",
    "complex_icon_review_queue_contact_sheet.png",
    "glyph_container_refinement_contact_sheet.png",
    "complex_crop_vs_vector_trace_candidates.png",
    "complex_crop_vs_vision_repair_candidates.png",
    "approved_svg_contact_sheet.png",
    "rejected_svg_variant_contact_sheet.png",
    "curated_v4_vs_v5_contact_sheet.png",
    "e03_3_icon_readiness_contact_sheet.png",
)


def build_e03_2_3_contact_sheets(
    output_root: Path,
    *,
    strict_report: dict[str, Any],
    cluster_manifest: dict[str, Any],
    review_queue: dict[str, Any],
    refinement_report: dict[str, Any],
    local_trace_manifest: dict[str, Any],
    vision_repair_manifest: dict[str, Any],
    quality_report: dict[str, Any],
    coverage: dict[str, Any],
    readiness: dict[str, Any],
    v4_root: Path,
    v5_root: Path,
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _candidate_grid(render_dir / "stricter_hygiene_before_after_contact_sheet.png", strict_report.get("candidates", []), "strict")
    _candidate_grid(render_dir / "revised_auto_reject_non_icons.png", strict_report.get("auto_reject_non_icons_v2", []), "reject")
    _cluster_grid(render_dir / "complex_icon_clusters_contact_sheet.png", cluster_manifest.get("clusters", []))
    _review_grid(render_dir / "complex_icon_review_queue_contact_sheet.png", review_queue.get("icons", []))
    _refinement_grid(render_dir / "glyph_container_refinement_contact_sheet.png", refinement_report.get("icons", []))
    _trace_grid(render_dir / "complex_crop_vs_vector_trace_candidates.png", local_trace_manifest.get("candidates", []))
    _trace_grid(render_dir / "complex_crop_vs_vision_repair_candidates.png", vision_repair_manifest.get("candidates", []))
    _approved_grid(render_dir / "approved_svg_contact_sheet.png", quality_report.get("approved_svgs", []))
    _approved_grid(render_dir / "rejected_svg_variant_contact_sheet.png", quality_report.get("rejected_variants", []))
    _v4_v5_grid(render_dir / "curated_v4_vs_v5_contact_sheet.png", coverage.get("roles", []), v4_root, v5_root)
    _readiness_sheet(render_dir / "e03_3_icon_readiness_contact_sheet.png", readiness)
    return {
        "schema_name": "e03_2_3_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACT_NAMES) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACT_NAMES},
    }


def _candidate_grid(output: Path, rows: list[dict[str, Any]], label: str) -> None:
    cell_w, cell_h = 178, 118
    cols = 5
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:80]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 4), row.get("likely_role", "")[:22], fill="#F8FAFC", font=font)
        draw.text((x + 5, y + 19), row.get("strict_hygiene_classification", label)[:28], fill="#F5A623", font=font)
        _paste_image(sheet, Path(row.get("normalized_crop_path") or row.get("crop_path") or ""), x + 50, y + 42, 64)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _cluster_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 260, 76
    sheet = Image.new("RGB", (cell_w * 3, max(1, ((len(rows) + 2) // 3)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows):
        x = (idx % 3) * cell_w
        y = (idx // 3) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 6, y + 6), row["likely_role"][:24], fill="#F8FAFC", font=font)
        draw.text((x + 6, y + 22), f"members {row['member_count']} vector {row['requires_vectorization']}", fill="#F5A623", font=font)
        draw.text((x + 6, y + 40), ",".join(row.get("complexity_classes", []))[:34], fill="#9EC4C8", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _review_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    _simple_text_sheet(output, "Complex icon review queue", [f"{row.get('review_id')} {row.get('role')} {row.get('review_status')}" for row in rows] or ["No human review required"])


def _refinement_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 220, 118
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), row["likely_role"][:20], fill="#F5A623", font=font)
        variants = row.get("crop_variants", {})
        _paste_image(sheet, Path(variants.get("glyph_with_safe_padding", "")), x + 20, y + 36, 58)
        _paste_image(sheet, Path(variants.get("high_contrast_mask", "")), x + 120, y + 36, 58)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _trace_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 210, 110
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), f"{row.get('likely_role','')[:14]} {row.get('variant','')[:12]}", fill="#F5A623", font=font)
        _paste_image(sheet, Path(row.get("source_crop_path") or ""), x + 14, y + 36, 54)
        _paste_svg(sheet, Path(row.get("svg_path") or ""), x + 116, y + 36)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _approved_grid(output: Path, rows: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 180, 104
    cols = 5
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:80]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), row.get("likely_role", "")[:20], fill="#F8FAFC", font=font)
        draw.text((x + 5, y + 20), str(row.get("final_candidate_score", row.get("rejection_reason", "")))[:20], fill="#F5A623", font=font)
        _paste_svg(sheet, Path(row.get("svg_path") or ""), x + 62, y + 42)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _v4_v5_grid(output: Path, rows: list[dict[str, Any]], v4_root: Path, v5_root: Path) -> None:
    cell_w, cell_h = 176, 94
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:64]):
        role = row["role"]
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 5), role[:22], fill="#F8FAFC", font=font)
        _paste_svg(sheet, v4_root / f"{role}.svg", x + 22, y + 34)
        _paste_svg(sheet, v5_root / f"{role}.svg", x + 102, y + 34)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _readiness_sheet(output: Path, readiness: dict[str, Any]) -> None:
    rows = [f"{key}: {readiness.get(key)}" for key in ("decision", "e03_3_unlocked", "unresolved_p0_count", "unresolved_p1_count", "semantic_raster_icon_count", "protected_artifacts_unchanged")]
    _simple_text_sheet(output, "E03.3 complex icon readiness", rows)


def _simple_text_sheet(output: Path, title: str, rows: list[str]) -> None:
    sheet = Image.new("RGB", (920, 360), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 60
    for row in rows[:11]:
        draw.text((24, y), row, fill="#F5A623", font=font)
        y += 26
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
    temp = svg_path.with_suffix(".e03_2_3_tmp.png")
    try:
        cairosvg.svg2png(url=svg_path.as_posix(), write_to=temp.as_posix(), output_width=54, output_height=54)
        image = Image.open(temp).convert("RGBA")
        sheet.paste(Image.new("RGB", image.size, "#F8FAFC"), (x, y))
        sheet.paste(image, (x, y), image)
    finally:
        temp.unlink(missing_ok=True)
