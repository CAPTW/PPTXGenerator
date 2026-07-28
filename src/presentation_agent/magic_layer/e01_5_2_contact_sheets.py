"""Contact sheet generation for E01.5.2 rendered SVG glyph evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .reference_render_compare import build_side_by_side


def write_e01_5_2_contact_sheets(
    *,
    output_root: Path,
    v1_audit: dict[str, Any],
    v2_audit: dict[str, Any],
    observed_similarity: dict[str, Any],
    e01_5_1_render: Path,
    e01_5_2_render: Path,
    canva_reference: Path,
) -> dict[str, Any]:
    renders = output_root / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    paths = {
        "curated_icon_v1_defect_contact_sheet": renders / "curated_icon_v1_defect_contact_sheet.png",
        "curated_icon_v2_library_contact_sheet": renders / "curated_icon_v2_library_contact_sheet.png",
        "observed_crop_vs_v1_vs_v2_svg_contact_sheet": renders / "observed_crop_vs_v1_vs_v2_svg_contact_sheet.png",
        "observed_crop_vs_v2_svg_overlay_diff_sheet": renders / "observed_crop_vs_v2_svg_overlay_diff_sheet.png",
        "e01_5_1_vs_e01_5_2_icon_region_contact_sheet": renders / "e01_5_1_vs_e01_5_2_icon_region_contact_sheet.png",
        "e01_5_2_full_candidate_render": renders / "e01_5_2_full_candidate_render.png",
        "canva_reference_vs_e01_5_2_contact_sheet": renders / "canva_reference_vs_e01_5_2_contact_sheet.png",
    }
    _v1_defect_sheet(v1_audit, paths["curated_icon_v1_defect_contact_sheet"])
    _library_sheet(v2_audit, paths["curated_icon_v2_library_contact_sheet"])
    _observed_triptych(observed_similarity, paths["observed_crop_vs_v1_vs_v2_svg_contact_sheet"])
    _observed_overlay_diff(observed_similarity, paths["observed_crop_vs_v2_svg_overlay_diff_sheet"])
    build_side_by_side(e01_5_1_render, e01_5_2_render, paths["e01_5_1_vs_e01_5_2_icon_region_contact_sheet"], left_label="E01.5.1 render", right_label="E01.5.2 render")
    Image.open(e01_5_2_render).save(paths["e01_5_2_full_candidate_render"])
    build_side_by_side(canva_reference, e01_5_2_render, paths["canva_reference_vs_e01_5_2_contact_sheet"], left_label="Canva reference", right_label="E01.5.2 render")
    return {"schema_name": "e01_5_2_contact_sheet_manifest", "status": "passed", "paths": {key: value.as_posix() for key, value in paths.items()}}


def _v1_defect_sheet(audit: dict[str, Any], output: Path) -> None:
    defects = [record for record in audit.get("records", []) if record["render_quality_status"] != "passed"]
    records = defects or audit.get("records", [])[:24]
    _grid(records, output, title="V1 render audit: defects shown first; if none, passing sample glyphs are shown")


def _library_sheet(audit: dict[str, Any], output: Path) -> None:
    _grid(audit.get("records", [])[:128], output, title="Curated Magic Layer v2 real rendered SVG glyphs")


def _grid(records: list[dict[str, Any]], output: Path, *, title: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    cols = 8
    cell_w, cell_h = 190, 150
    rows = max(1, (len(records) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + 36), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 12), title, fill="#F8FAFC", font=font)
    for idx, record in enumerate(records):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h + 36
        render_path = Path(record["rendered_sizes"]["128"]["render_path"])
        icon = Image.open(render_path).convert("RGBA")
        tile = Image.new("RGB", (84, 84), "#111827")
        tile.paste(icon.resize((72, 72)), (6, 6), icon.resize((72, 72)).getchannel("A"))
        sheet.paste(tile, (x + 8, y + 10))
        draw.text((x + 8, y + 100), record["role"][:28], fill="#F8FAFC", font=font)
        draw.text((x + 8, y + 118), record["render_quality_status"], fill="#38BDF8" if record["render_quality_status"] == "passed" else "#F87171", font=font)
    sheet.save(output)


def _observed_triptych(similarity: dict[str, Any], output: Path) -> None:
    rows = similarity.get("rows", [])
    cell_w, cell_h = 520, 138
    sheet = Image.new("RGB", (cell_w * 2, max(1, len(rows) // 2 + len(rows) % 2) * cell_h + 34), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 12), "Observed crop vs v1 render vs v2 render", fill="#F8FAFC", font=font)
    for idx, row in enumerate(rows):
        x = (idx % 2) * cell_w
        y = (idx // 2) * cell_h + 34
        _paste_icon(sheet, row["observed_crop_path"], x + 8, y + 28, size=70)
        _paste_icon(sheet, row["v1_render_path"], x + 92, y + 28, size=70)
        _paste_icon(sheet, row["v2_render_path"], x + 176, y + 28, size=70)
        draw.text((x + 8, y + 8), row["role"][:48], fill="#F8FAFC", font=font)
        draw.text((x + 258, y + 42), f"v2 {row['comparison']} score={row['v2_similarity']}", fill="#38BDF8", font=font)
        draw.text((x + 258, y + 62), row["final_match_decision"], fill="#F5A623", font=font)
    sheet.save(output)


def _observed_overlay_diff(similarity: dict[str, Any], output: Path) -> None:
    rows = similarity.get("rows", [])
    cell_w, cell_h = 360, 126
    sheet = Image.new("RGB", (cell_w * 2, max(1, len(rows) // 2 + len(rows) % 2) * cell_h + 34), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 12), "Observed crop vs v2 overlay/diff", fill="#F8FAFC", font=font)
    for idx, row in enumerate(rows):
        x = (idx % 2) * cell_w
        y = (idx // 2) * cell_h + 34
        crop = _load_square(row["observed_crop_path"], 72)
        v2 = _load_square(row["v2_render_path"], 72)
        diff = ImageChops.difference(crop.convert("RGB"), v2.convert("RGB"))
        sheet.paste(crop.convert("RGB"), (x + 8, y + 26))
        sheet.paste(v2.convert("RGB"), (x + 88, y + 26))
        sheet.paste(diff, (x + 168, y + 26))
        draw.text((x + 8, y + 8), row["role"][:34], fill="#F8FAFC", font=font)
        draw.text((x + 248, y + 48), f"{row['v2_similarity']}", fill="#38BDF8", font=font)
    sheet.save(output)


def _paste_icon(sheet: Image.Image, path: str, x: int, y: int, *, size: int) -> None:
    icon = _load_square(path, size).convert("RGBA")
    bg = Image.new("RGB", (size, size), "#111827")
    bg.paste(icon, (0, 0), icon.getchannel("A") if icon.mode == "RGBA" else None)
    sheet.paste(bg, (x, y))


def _load_square(path: str, size: int) -> Image.Image:
    image = Image.open(path).convert("RGBA").resize((size, size))
    return image
