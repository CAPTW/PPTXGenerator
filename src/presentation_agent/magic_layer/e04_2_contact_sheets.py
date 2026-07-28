"""Contact sheets for E04.2 product polish."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e04_2_source_bound_deck_contact_sheet.png",
    "e04_1_vs_e04_2_product_polish_contact_sheet.png",
    "e04_2_dense_slides_before_after_contact_sheet.png",
    "e04_2_slide_09_before_after_contact_sheet.png",
    "e04_2_slide_11_before_after_contact_sheet.png",
    "e04_2_slide_14_before_after_contact_sheet.png",
    "e04_2_text_readability_overlay_contact_sheet.png",
    "e04_2_table_density_overlay_contact_sheet.png",
    "e04_2_source_footer_readability_contact_sheet.png",
    "e04_2_icon_visibility_contact_sheet.png",
    "e04_2_source_citation_overlay_contact_sheet.png",
    "e04_2_semantic_editability_contact_sheet.png",
    "e04_2_residual_patch_queue_contact_sheet.png",
)


def build_e04_2_contact_sheets(output_root: Path, previous_paths: list[Path], rendered_paths: list[Path], summaries: dict[str, Any]) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _render_grid(render_dir / "e04_2_source_bound_deck_contact_sheet.png", rendered_paths, "E04.2 product-polished deck")
    _before_after(render_dir / "e04_1_vs_e04_2_product_polish_contact_sheet.png", previous_paths, rendered_paths, "E04.1 vs E04.2")
    dense_indexes = [8, 10, 13]
    _before_after(render_dir / "e04_2_dense_slides_before_after_contact_sheet.png", [previous_paths[i] for i in dense_indexes], [rendered_paths[i] for i in dense_indexes], "Dense slides before/after")
    for slide_number, idx in [(9, 8), (11, 10), (14, 13)]:
        _before_after(render_dir / f"e04_2_slide_{slide_number:02d}_before_after_contact_sheet.png", [previous_paths[idx]], [rendered_paths[idx]], f"Slide {slide_number} before/after")
    _summary_sheet(render_dir / "e04_2_text_readability_overlay_contact_sheet.png", "Text Readability", summaries.get("text", {}))
    _summary_sheet(render_dir / "e04_2_table_density_overlay_contact_sheet.png", "Table Density", summaries.get("table_density", {}))
    _summary_sheet(render_dir / "e04_2_source_footer_readability_contact_sheet.png", "Source/Footer", summaries.get("source_footer", {}))
    _summary_sheet(render_dir / "e04_2_icon_visibility_contact_sheet.png", "Icon Visibility", summaries.get("icon", {}))
    _summary_sheet(render_dir / "e04_2_source_citation_overlay_contact_sheet.png", "Source/Citation", summaries.get("source", {}))
    _summary_sheet(render_dir / "e04_2_semantic_editability_contact_sheet.png", "Semantic Editability", summaries.get("editability", {}))
    _summary_sheet(render_dir / "e04_2_residual_patch_queue_contact_sheet.png", "Residual Patch Queue", summaries.get("residual", {}))
    return {
        "schema_name": "e04_2_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACTS) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACTS},
    }


def _render_grid(output: Path, images: list[Path], title: str) -> None:
    cell_w, cell_h = 320, 205
    cols = 4
    rows = max(1, (len(images) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + 44), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), title, fill="#F8FAFC", font=font)
    for idx, path in enumerate(images):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h + 44
        draw.text((x + 8, y + 8), f"slide {idx + 1}", fill="#F2A900", font=font)
        _paste(sheet, path, x + 8, y + 28, cell_w - 16, cell_h - 34)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _before_after(output: Path, before: list[Path], after: list[Path], title: str) -> None:
    cell_w, cell_h = 420, 245
    rows = max(len(after), 1)
    sheet = Image.new("RGB", (cell_w * 2, rows * cell_h + 44), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), title, fill="#F8FAFC", font=font)
    for idx in range(rows):
        y = idx * cell_h + 44
        draw.text((12, y + 8), "before", fill="#F2A900", font=font)
        draw.text((cell_w + 12, y + 8), "after", fill="#38D99E", font=font)
        if idx < len(before):
            _paste(sheet, before[idx], 12, y + 28, cell_w - 24, cell_h - 36)
        if idx < len(after):
            _paste(sheet, after[idx], cell_w + 12, y + 28, cell_w - 24, cell_h - 36)
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
            draw.text((24, y), f"{key}: {value}"[:130], fill="#F2A900", font=font)
            y += 24
        if y > 508:
            break
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste(sheet: Image.Image, path: Path, x: int, y: int, width: int, height: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))

