"""Contact sheets for E06.4."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e06_2_1_vs_e06_3_vs_e06_4_contact_sheet.png",
    "e06_4_human_tuned_candidate_contact_sheet.png",
    "e06_4_target_slides_before_after_contact_sheet.png",
    "e06_4_slide_02_visual_toc_before_after.png",
    "e06_4_slide_09_comparison_matrix_before_after.png",
    "e06_4_slide_10_data_dashboard_before_after.png",
    "e06_4_slide_11_table_heavy_before_after.png",
    "e06_4_slide_14_risk_register_before_after.png",
    "e06_4_visual_acceptance_scorecard_contact_sheet.png",
    "e06_4_contract_diff_contact_sheet.png",
    "e06_4_failure_or_no_acceptance_contact_sheet.png",
)


def build_e06_4_contact_sheets(output_root: Path, baseline_render_dir: Path, e06_3_render_dir: Path, summaries: dict[str, Any]) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    triple = []
    for idx in [2, 9, 10, 11, 14]:
        triple.extend([baseline_render_dir / f"v2-{idx:03d}.png", e06_3_render_dir / f"variant_c-{idx:03d}.png", render_dir / f"human_tuned-{idx:03d}.png"])
    build_grid_contact_sheet(render_dir / CONTACTS[0], triple, "E06.2.1 vs E06.3 vs E06.4 target slides")
    build_grid_contact_sheet(render_dir / CONTACTS[1], [render_dir / f"human_tuned-{idx:03d}.png" for idx in range(1, 17)], "E06.4 human-tuned candidate")
    before_after = []
    for idx in [2, 9, 10, 11, 14]:
        before_after.extend([baseline_render_dir / f"v2-{idx:03d}.png", render_dir / f"human_tuned-{idx:03d}.png"])
    build_grid_contact_sheet(render_dir / CONTACTS[2], before_after, "Target slides before/after")
    slide_names = {
        2: "visual_toc",
        9: "comparison_matrix",
        10: "data_dashboard",
        11: "table_heavy",
        14: "risk_register",
    }
    for idx, name in slide_names.items():
        build_grid_contact_sheet(render_dir / f"e06_4_slide_{idx:02d}_{name}_before_after.png", [baseline_render_dir / f"v2-{idx:03d}.png", render_dir / f"human_tuned-{idx:03d}.png"], f"Slide {idx:02d} {name} before/after")
    _summary(render_dir / CONTACTS[8], "Visual Acceptance Scorecard", summaries.get("visual", {}))
    _summary(render_dir / CONTACTS[9], "Contract Diff", summaries.get("diff", {}))
    _summary(render_dir / CONTACTS[10], "Failure Or No Acceptance", summaries.get("patch_queue", {}))
    return {
        "schema_name": "e06_4_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACTS) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACTS},
    }


def build_grid_contact_sheet(output: Path, images: list[Path], title: str) -> None:
    cell_w, cell_h = 320, 205
    cols = 3 if len(images) <= 15 else 4
    rows = max(1, (len(images) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + 44), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), title, fill="#F8FAFC", font=font)
    for idx, path in enumerate(images):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h + 44
        draw.text((x + 8, y + 8), path.stem if path else str(idx + 1), fill="#F2A900", font=font)
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
        if isinstance(value, list):
            draw.text((24, y), f"{key}: {len(value)} items", fill="#F2A900", font=font)
        elif isinstance(value, dict):
            draw.text((24, y), f"{key}: {', '.join(str(k) for k in list(value)[:8])}", fill="#F2A900", font=font)
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
