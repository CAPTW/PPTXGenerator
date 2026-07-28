"""Contact sheets for E06.3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e06_2_1_vs_e06_3_variants_contact_sheet.png",
    "e06_3_variant_scorecard_contact_sheet.png",
    "e06_3_layout_contract_variant_diff_contact_sheet.png",
    "e06_3_icon_size_anchor_delta_contact_sheet.png",
    "e06_3_dense_slide_delta_contact_sheet.png",
    "e06_3_visual_hierarchy_delta_contact_sheet.png",
    "e06_3_selected_candidate_contact_sheet.png",
    "e06_3_failure_or_no_improvement_contact_sheet.png",
)


def build_e06_3_contact_sheets(
    output_root: Path,
    summaries: dict[str, Any],
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    variant_paths = []
    for prefix in ("variant_a", "variant_b", "variant_c"):
        variant_paths.extend(render_dir / f"{prefix}-{idx:03d}.png" for idx in range(1, 5))
    build_grid_contact_sheet(render_dir / CONTACTS[0], variant_paths, "E06.2.1 baseline vs E06.3 variants")
    _summary(render_dir / CONTACTS[1], "Variant Scorecards", summaries.get("score", {}))
    _summary(render_dir / CONTACTS[2], "Layout Contract Variant Diffs", summaries.get("diff", {}))
    _summary(render_dir / CONTACTS[3], "Icon Size/Anchor Delta", summaries.get("icon", {}))
    _summary(render_dir / CONTACTS[4], "Dense Slide Delta", summaries.get("dense", {}))
    _summary(render_dir / CONTACTS[5], "Visual Hierarchy Delta", summaries.get("opportunities", {}))
    selected = [render_dir / f"{summaries.get('selected_variant_id', 'variant_c')}-{idx:03d}.png" for idx in range(1, 17)]
    build_grid_contact_sheet(render_dir / CONTACTS[6], selected, "E06.3 selected candidate")
    _summary(render_dir / CONTACTS[7], "Failure Or No Improvement", summaries.get("patch_queue", {}))
    return {
        "schema_name": "e06_3_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACTS) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACTS},
    }


def build_grid_contact_sheet(output: Path, images: list[Path], title: str) -> None:
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
        draw.text((x + 8, y + 8), f"{idx + 1}", fill="#F2A900", font=font)
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
        if isinstance(value, dict):
            draw.text((24, y), f"{key}: {', '.join(str(k) for k in value.keys())}"[:170], fill="#F2A900", font=font)
            y += 24
        elif isinstance(value, list):
            draw.text((24, y), f"{key}: {len(value)} items", fill="#F2A900", font=font)
            y += 24
        elif isinstance(value, (str, int, float, bool)) or value is None:
            draw.text((24, y), f"{key}: {value}"[:170], fill="#F2A900", font=font)
            y += 24
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
