"""Contact sheets for E04.1 icon micro-placement."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e04_1_source_bound_deck_contact_sheet.png",
    "e04_vs_e04_1_icon_micro_placement_contact_sheet.png",
    "e04_1_icon_slot_overlay_contact_sheet.png",
    "e04_1_icon_anchor_overlay_contact_sheet.png",
    "e04_1_icon_size_token_contact_sheet.png",
    "e04_1_icon_text_collision_contact_sheet.png",
    "e04_1_icon_local_contrast_contact_sheet.png",
    "e04_1_diagnostic_icon_leakage_contact_sheet.png",
    "e04_1_source_citation_overlay_contact_sheet.png",
    "e04_1_failures_or_patch_queue_contact_sheet.png",
)


def build_e04_1_contact_sheets(output_root: Path, previous_paths: list[Path], rendered_paths: list[Path], summaries: dict[str, Any]) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _render_grid(render_dir / "e04_1_source_bound_deck_contact_sheet.png", rendered_paths, "E04.1 source-bound deck")
    _before_after(render_dir / "e04_vs_e04_1_icon_micro_placement_contact_sheet.png", previous_paths, rendered_paths, "E04 vs E04.1 icon placement")
    _render_grid(render_dir / "e04_1_icon_slot_overlay_contact_sheet.png", rendered_paths, "Icon slot overlay")
    _render_grid(render_dir / "e04_1_icon_anchor_overlay_contact_sheet.png", rendered_paths, "Icon anchor overlay")
    _summary_sheet(render_dir / "e04_1_icon_size_token_contact_sheet.png", "Icon Size Tokens", summaries.get("size", {}))
    _summary_sheet(render_dir / "e04_1_icon_text_collision_contact_sheet.png", "Icon Text Collision", summaries.get("collision", {}))
    _summary_sheet(render_dir / "e04_1_icon_local_contrast_contact_sheet.png", "Icon Local Contrast", summaries.get("contrast", {}))
    _summary_sheet(render_dir / "e04_1_diagnostic_icon_leakage_contact_sheet.png", "Diagnostic Icon Leakage", summaries.get("diagnostic", {}))
    _summary_sheet(render_dir / "e04_1_source_citation_overlay_contact_sheet.png", "Source/Citation Regression", summaries.get("binding_regression", {}))
    _summary_sheet(render_dir / "e04_1_failures_or_patch_queue_contact_sheet.png", "Patch Queue", summaries.get("patch_queue", {}))
    return {
        "schema_name": "e04_1_contact_sheet_manifest",
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
        draw.text((x + 8, y + 8), f"slide {idx + 1}", fill="#F2A900", font=font)
        _paste(sheet, path, x + 8, y + 28, cell_w - 16, cell_h - 34)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _before_after(output: Path, before: list[Path], after: list[Path], title: str) -> None:
    cell_w, cell_h = 360, 230
    cols = 2
    sheet = Image.new("RGB", (cols * cell_w, 8 * cell_h + 42), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), title, fill="#F8FAFC", font=font)
    for idx in range(min(16, len(after))):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h + 42
        draw.text((x + 8, y + 8), f"slide {idx + 1}", fill="#F2A900", font=font)
        if idx < len(before):
            _paste(sheet, before[idx], x + 8, y + 30, 164, 100)
        _paste(sheet, after[idx], x + 188, y + 30, 164, 100)
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


def _paste(sheet: Image.Image, path: Path, x: int, y: int, width: int, height: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
