"""Contact sheets for E04."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e04_source_bound_deck_contact_sheet.png",
    "e04_source_bound_reference_vs_render_contact_sheet.png",
    "e04_icon_visibility_contact_sheet.png",
    "e04_text_capacity_contact_sheet.png",
    "e04_chart_table_binding_contact_sheet.png",
    "e04_source_citation_overlay_contact_sheet.png",
    "e04_semantic_editability_contact_sheet.png",
    "e04_raster_policy_contact_sheet.png",
    "e04_failures_or_patch_queue_contact_sheet.png",
)


def build_e04_contact_sheets(output_root: Path, rendered_paths: list[Path], summaries: dict[str, Any]) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _render_grid(render_dir / "e04_source_bound_deck_contact_sheet.png", rendered_paths, "E04 source-bound deck")
    _render_grid(render_dir / "e04_source_bound_reference_vs_render_contact_sheet.png", rendered_paths, "E04 rendered slides")
    _render_grid(render_dir / "e04_icon_visibility_contact_sheet.png", rendered_paths, "E04 icon visibility")
    _summary_sheet(render_dir / "e04_text_capacity_contact_sheet.png", "Text Capacity", summaries.get("text_overflow", {}))
    _summary_sheet(render_dir / "e04_chart_table_binding_contact_sheet.png", "Chart/Table Binding", summaries.get("chart_table", {}))
    _summary_sheet(render_dir / "e04_source_citation_overlay_contact_sheet.png", "Source/Citation Binding", summaries.get("source_citation", {}))
    _summary_sheet(render_dir / "e04_semantic_editability_contact_sheet.png", "Semantic Editability", summaries.get("semantic_editability", {}))
    _summary_sheet(render_dir / "e04_raster_policy_contact_sheet.png", "Raster Policy", summaries.get("raster_policy", {}))
    _summary_sheet(render_dir / "e04_failures_or_patch_queue_contact_sheet.png", "Patch Queue", summaries.get("patch_queue", {}))
    return {
        "schema_name": "e04_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACTS) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACTS},
    }


def _render_grid(output: Path, images: list[Path], title: str) -> None:
    cell_w, cell_h = 320, 205
    cols = 4
    rows = max(1, (len(images) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + 42), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), title, fill="#F8FAFC", font=font)
    for idx, path in enumerate(images):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h + 42
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 8, y + 8), f"slide {idx + 1}", fill="#F2A900", font=font)
        if path.exists():
            image = Image.open(path).convert("RGB")
            image.thumbnail((cell_w - 22, cell_h - 32), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (cell_w - image.width) // 2, y + 26))
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
            draw.text((24, y), f"{key}: {value}"[:130], fill="#F5A623", font=font)
            y += 24
            if y > 510:
                break
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
