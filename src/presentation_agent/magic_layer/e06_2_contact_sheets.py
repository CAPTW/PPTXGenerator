"""Contact sheet generation for E06.2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e06_2_contract_recompiled_deck_contact_sheet.png",
    "e06_baseline_vs_e06_2_contract_recompile_contact_sheet.png",
    "e06_2_contract_vs_recompiled_pptx_overlay_contact_sheet.png",
    "e06_2_contract_vs_recompiled_render_overlay_contact_sheet.png",
    "e06_2_icon_anchor_preservation_contact_sheet.png",
    "e06_2_dense_slide_preservation_contact_sheet.png",
    "e06_2_source_citation_preservation_contact_sheet.png",
    "e06_2_mutation_smoke_test_contact_sheet.png",
    "e06_2_patch_queue_contact_sheet.png",
)


def build_e06_2_contact_sheets(output_root: Path, baseline_render_dir: Path, summaries: dict[str, Any]) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    recompiled = [render_dir / f"recompiled-{idx:03d}.png" for idx in range(1, 17)]
    mutation = [render_dir / f"mutation-{idx:03d}.png" for idx in range(1, 17)]
    baseline = [baseline_render_dir / f"slide-{idx:03d}.png" for idx in range(1, 17)]
    _grid(render_dir / CONTACTS[0], recompiled, "E06.2 contract recompiled deck")
    _before_after(render_dir / CONTACTS[1], baseline, recompiled, "E06 baseline vs E06.2 contract recompile")
    _summary(render_dir / CONTACTS[2], "Contract vs Recompiled PPTX", summaries.get("coordinate_diff", {}))
    _summary(render_dir / CONTACTS[3], "Contract vs Recompiled Render", summaries.get("render_diff", {}))
    _summary(render_dir / CONTACTS[4], "Icon Anchor Preservation", summaries.get("icon_anchor", {}))
    _summary(render_dir / CONTACTS[5], "Dense Slide Preservation", summaries.get("dense", {}))
    _summary(render_dir / CONTACTS[6], "Source/Citation Preservation", summaries.get("binding", {}))
    _grid(render_dir / CONTACTS[7], mutation, "Mutation smoke-test render")
    _summary(render_dir / CONTACTS[8], "E06.2 Patch Queue", summaries.get("patch_queue", {}))
    return {
        "schema_name": "e06_2_contact_sheet_manifest",
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


def _before_after(output: Path, before: list[Path], after: list[Path], title: str) -> None:
    cell_w, cell_h = 360, 150
    sheet = Image.new("RGB", (cell_w * 2, cell_h * 16 + 44), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), title, fill="#F8FAFC", font=font)
    for idx, (b, a) in enumerate(zip(before, after, strict=False)):
        y = idx * cell_h + 44
        draw.text((8, y + 4), f"{idx+1:02d} baseline", fill="#F2A900", font=font)
        draw.text((cell_w + 8, y + 4), f"{idx+1:02d} contract", fill="#28D7E8", font=font)
        _paste(sheet, b, 8, y + 22, cell_w - 16, cell_h - 28)
        _paste(sheet, a, cell_w + 8, y + 22, cell_w - 16, cell_h - 28)
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
