"""Contact sheets for E06.1 layout contract precision gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACTS = (
    "e06_1_layout_contract_overview_contact_sheet.png",
    "e06_1_pptx_vs_contract_bbox_overlay_contact_sheet.png",
    "e06_1_render_vs_contract_bbox_overlay_contact_sheet.png",
    "e06_1_icon_anchor_overlay_contact_sheet.png",
    "e06_1_icon_size_token_contact_sheet.png",
    "e06_1_text_collision_overlay_contact_sheet.png",
    "e06_1_source_footer_overlay_contact_sheet.png",
    "e06_1_drift_failures_contact_sheet.png",
)


def build_e06_1_contact_sheets(output_root: Path, render_dir: Path, contract: dict[str, Any], summaries: dict[str, Any]) -> dict[str, Any]:
    target = output_root / "renders"
    target.mkdir(parents=True, exist_ok=True)
    rendered_paths = [render_dir / f"slide-{idx:03d}.png" for idx in range(1, 17)]
    _overview_grid(target / CONTACTS[0], rendered_paths, "E06.1 layout contract overview")
    _overlay_grid(target / CONTACTS[1], rendered_paths, contract, "PPTX vs contract bbox overlay", {"semantic_icon", "text", "source_footer"})
    _overlay_grid(target / CONTACTS[2], rendered_paths, contract, "Rendered vs contract bbox overlay", {"semantic_icon", "table_region", "chart_region", "card_region"})
    _overlay_grid(target / CONTACTS[3], rendered_paths, contract, "Semantic icon anchors", {"semantic_icon", "icon_background"})
    _summary_sheet(target / CONTACTS[4], "Icon Size Tokens", summaries.get("icon_size", {}))
    _summary_sheet(target / CONTACTS[5], "Text Collision Gate", summaries.get("text_collision", {}))
    _overlay_grid(target / CONTACTS[6], rendered_paths, contract, "Source/footer coordinate overlay", {"source_footer"})
    _risk_sheet(target / CONTACTS[7], summaries.get("risk", {}))
    return {
        "schema_name": "e06_1_contact_sheet_manifest",
        "status": "passed" if all((target / name).exists() for name in CONTACTS) else "failed",
        "paths": {name.removesuffix(".png"): (target / name).as_posix() for name in CONTACTS},
    }


def _overview_grid(output: Path, images: list[Path], title: str) -> None:
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


def _overlay_grid(output: Path, images: list[Path], contract: dict[str, Any], title: str, categories: set[str]) -> None:
    thumbs: list[Image.Image] = []
    for slide, path in zip(contract.get("slides", []), images, strict=False):
        if path.exists():
            image = Image.open(path).convert("RGB")
        else:
            image = Image.new("RGB", (2304, 1296), "#071018")
        draw = ImageDraw.Draw(image)
        for obj in slide.get("objects", []):
            if obj.get("object_type") not in categories:
                continue
            color = _color_for(obj.get("object_type"))
            b = obj.get("bbox_norm", {})
            box = (
                int(b.get("x", 0) * image.width),
                int(b.get("y", 0) * image.height),
                int((b.get("x", 0) + b.get("w", 0)) * image.width),
                int((b.get("y", 0) + b.get("h", 0)) * image.height),
            )
            draw.rectangle(box, outline=color, width=3)
        image.thumbnail((300, 170), Image.Resampling.LANCZOS)
        thumbs.append(image.copy())
    cell_w, cell_h = 320, 205
    cols = 4
    rows = max(1, (len(thumbs) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + 44), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), title, fill="#F8FAFC", font=font)
    for idx, thumb in enumerate(thumbs):
        x = (idx % cols) * cell_w + 10
        y = (idx // cols) * cell_h + 72
        draw.text((x, y - 20), f"slide {idx + 1}", fill="#F2A900", font=font)
        sheet.paste(thumb, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _summary_sheet(output: Path, title: str, payload: dict[str, Any]) -> None:
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


def _risk_sheet(output: Path, payload: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), "E06.1 Coordinate Drift Risk Register", fill="#F8FAFC", font=font)
    y = 64
    for risk in payload.get("risks", [])[:16]:
        text = f"{risk.get('risk_id')}: {risk.get('risk_level')} - {risk.get('issue')}"
        draw.text((24, y), text[:180], fill="#F2A900", font=font)
        y += 34
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste(sheet: Image.Image, path: Path, x: int, y: int, width: int, height: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))


def _color_for(object_type: str | None) -> str:
    return {
        "semantic_icon": "#28D7E8",
        "icon_background": "#94A3B8",
        "text": "#38D99E",
        "source_footer": "#F2A900",
        "table_region": "#C084FC",
        "chart_region": "#60A5FA",
        "card_region": "#F87171",
    }.get(object_type or "", "#FFFFFF")
