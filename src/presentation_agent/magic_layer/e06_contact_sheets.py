"""Contact sheets for E06 controlled baseline review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e06_baseline_review_contact_sheet.png",
    "e06_slide_scorecard_contact_sheet.png",
    "e06_dense_slide_final_review_contact_sheet.png",
    "e06_icon_system_review_contact_sheet.png",
    "e06_source_citation_review_contact_sheet.png",
    "e06_semantic_editability_review_contact_sheet.png",
    "e06_visual_rhythm_review_contact_sheet.png",
    "e06_product_risk_contact_sheet.png",
    "e06_patch_queue_contact_sheet.png",
)


def build_e06_contact_sheets(output_root: Path, rendered_paths: list[Path], summaries: dict[str, Any]) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _render_grid(render_dir / "e06_baseline_review_contact_sheet.png", rendered_paths, "E06 baseline review: E04.2 renders")
    _scorecard_sheet(render_dir / "e06_slide_scorecard_contact_sheet.png", summaries.get("slide_matrix", {}))
    _summary_sheet(render_dir / "e06_dense_slide_final_review_contact_sheet.png", "Dense Slide Readability", summaries.get("dense", {}))
    _summary_sheet(render_dir / "e06_icon_system_review_contact_sheet.png", "Icon System", summaries.get("icon", {}))
    _summary_sheet(render_dir / "e06_source_citation_review_contact_sheet.png", "Source/Citation", summaries.get("source", {}))
    _summary_sheet(render_dir / "e06_semantic_editability_review_contact_sheet.png", "Semantic Editability", summaries.get("editability", {}))
    _summary_sheet(render_dir / "e06_visual_rhythm_review_contact_sheet.png", "Visual Rhythm", summaries.get("rhythm", {}))
    _risk_sheet(render_dir / "e06_product_risk_contact_sheet.png", summaries.get("risk", {}))
    _risk_sheet(render_dir / "e06_patch_queue_contact_sheet.png", summaries.get("patch_queue", {}))
    return {
        "schema_name": "e06_contact_sheet_manifest",
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


def _scorecard_sheet(output: Path, matrix: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), "E06 Slide Baseline Scorecard", fill="#F8FAFC", font=font)
    draw.text((24, 54), f"average: {matrix.get('average_baseline_score')}  minimum: {matrix.get('minimum_slide_score')}", fill="#F2A900", font=font)
    y = 92
    for row in matrix.get("rows", [])[:16]:
        fill = "#38D99E" if row.get("product_baseline_score", 0) >= 4.35 else "#F2A900"
        text = f"{row['slide_number']:02d} {row['archetype_id']:<24} score={row['product_baseline_score']} severity={row['severity']}"
        draw.text((24, y), text[:160], fill=fill, font=font)
        y += 36
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


def _risk_sheet(output: Path, payload: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), payload.get("schema_name", "risk").replace("_", " ").title(), fill="#F8FAFC", font=font)
    y = 64
    rows = payload.get("risks") or payload.get("items") or []
    for row in rows[:14]:
        text = f"{row.get('risk_id', row.get('patch_id', 'item'))} {row.get('risk_level', row.get('severity', ''))}: {row.get('issue')}"
        draw.text((24, y), text[:170], fill="#F2A900", font=font)
        y += 38
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste(sheet: Image.Image, path: Path, x: int, y: int, width: int, height: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))

