"""Contact sheets for E05 product review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e05_review_contact_sheet.png",
    "e05_slide_scorecard_contact_sheet.png",
    "e05_icon_micro_placement_review_contact_sheet.png",
    "e05_text_readability_contact_sheet.png",
    "e05_table_chart_readability_contact_sheet.png",
    "e05_source_citation_review_contact_sheet.png",
    "e05_semantic_editability_contact_sheet.png",
    "e05_visual_rhythm_contact_sheet.png",
    "e05_patch_queue_contact_sheet.png",
)


def build_e05_contact_sheets(output_root: Path, rendered_paths: list[Path], summaries: dict[str, Any]) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _render_grid(render_dir / "e05_review_contact_sheet.png", rendered_paths, "E05 product review: actual PPTX renders")
    _scorecard_sheet(render_dir / "e05_slide_scorecard_contact_sheet.png", summaries.get("scorecard", {}))
    _summary_sheet(render_dir / "e05_icon_micro_placement_review_contact_sheet.png", "Icon Micro-Placement Review", summaries.get("icon", {}))
    _summary_sheet(render_dir / "e05_text_readability_contact_sheet.png", "Text Readability Review", summaries.get("text", {}))
    _summary_sheet(render_dir / "e05_table_chart_readability_contact_sheet.png", "Table/Chart Readability Review", summaries.get("chart_table", {}))
    _summary_sheet(render_dir / "e05_source_citation_review_contact_sheet.png", "Source/Citation Review", summaries.get("source", {}))
    _summary_sheet(render_dir / "e05_semantic_editability_contact_sheet.png", "Semantic Editability Review", summaries.get("editability", {}))
    _summary_sheet(render_dir / "e05_visual_rhythm_contact_sheet.png", "Visual Rhythm Review", summaries.get("rhythm", {}))
    _patch_sheet(render_dir / "e05_patch_queue_contact_sheet.png", summaries.get("patch_queue", {}))
    return {
        "schema_name": "e05_contact_sheet_manifest",
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


def _scorecard_sheet(output: Path, scorecard: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), "E05 Slide Scorecard", fill="#F8FAFC", font=font)
    draw.text((24, 54), f"average: {scorecard.get('average_product_score')}  minimum: {scorecard.get('minimum_slide_score')}", fill="#F2A900", font=font)
    y = 92
    for row in scorecard.get("rows", [])[:16]:
        score = row.get("product_score")
        fill = "#38D99E" if score >= 4 else "#F2A900"
        text = f"{row['slide_number']:02d} {row['archetype_id']:<24} score={score} severity={row['severity']} {row['patch_recommendation']}"
        draw.text((24, y), text[:170], fill=fill, font=font)
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


def _patch_sheet(output: Path, patch_queue: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), "E05 Patch Queue", fill="#F8FAFC", font=font)
    draw.text((24, 54), f"items: {patch_queue.get('item_count')}  high: {patch_queue.get('high_product_risk_count')}  medium: {patch_queue.get('medium_polish_count')}", fill="#F2A900", font=font)
    y = 92
    for item in patch_queue.get("items", [])[:16]:
        text = f"{item['patch_id']} slide {item.get('slide_number')} {item.get('severity')} {item.get('patch_type')}: {item.get('issue')}"
        draw.text((24, y), text[:170], fill="#F8FAFC", font=font)
        y += 36
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste(sheet: Image.Image, path: Path, x: int, y: int, width: int, height: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))

