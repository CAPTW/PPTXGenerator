"""Contact sheets for E06.2.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.presentation_agent.magic_layer.e06_2_1_visual_diff_gate import build_visual_delta_contact_sheet


CONTACTS = (
    "e06_baseline_vs_e06_2_vs_e06_2_1_contact_sheet.png",
    "e06_2_1_contract_recompiled_deck_contact_sheet.png",
    "e06_2_1_text_content_preservation_contact_sheet.png",
    "e06_2_1_style_preservation_contact_sheet.png",
    "e06_2_1_media_preservation_contact_sheet.png",
    "e06_2_1_dense_slide_preservation_contact_sheet.png",
    "e06_2_1_icon_theme_preservation_contact_sheet.png",
    "e06_2_1_render_diff_contact_sheet.png",
    "e06_2_1_mutation_smoke_test_contact_sheet.png",
    "e06_2_1_failure_or_patch_queue_contact_sheet.png",
)


def build_e06_2_1_contact_sheets(output_root: Path, baseline_render_dir: Path, e06_2_render_dir: Path, summaries: dict[str, Any]) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    build_visual_delta_contact_sheet(render_dir / CONTACTS[0], baseline_render_dir, e06_2_render_dir, render_dir)
    _grid(render_dir / CONTACTS[1], [render_dir / f"v2-{idx:03d}.png" for idx in range(1, 17)], "E06.2.1 contract recompiled deck")
    _summary(render_dir / CONTACTS[2], "Text Content Preservation", summaries.get("text", {}))
    _summary(render_dir / CONTACTS[3], "Style Preservation", summaries.get("style", {}))
    _summary(render_dir / CONTACTS[4], "Media Preservation", summaries.get("media", {}))
    _summary(render_dir / CONTACTS[5], "Dense Slide Preservation", summaries.get("dense", {}))
    _summary(render_dir / CONTACTS[6], "Icon Theme Preservation", summaries.get("icon", {}))
    _summary(render_dir / CONTACTS[7], "Render Diff", summaries.get("render", {}))
    _grid(render_dir / CONTACTS[8], [render_dir / f"mutation_v2-{idx:03d}.png" for idx in range(1, 17)], "Mutation smoke test v2")
    _summary(render_dir / CONTACTS[9], "Failure/Patch Queue", summaries.get("patch_queue", {}))
    return {
        "schema_name": "e06_2_1_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACTS) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACTS},
    }


def _grid(output: Path, images: list[Path], title: str) -> None:
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


def _summary(output: Path, title: str, payload: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            draw.text((24, y), f"{key}: {value}"[:170], fill="#F2A900", font=font)
            y += 26
        if y > 690:
            break
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste(sheet: Image.Image, path: Path, x: int, y: int, width: int, height: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
