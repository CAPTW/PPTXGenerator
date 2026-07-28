"""Generate diverse real PDF/PPT-like fixtures for PDFB02."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageDraw
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from src.presentation_agent.magic_layer.pdfb02_layer_truth_builder import build_layer_truth


PAGE_W, PAGE_H = landscape((720, 405))


PDFB02_FIXTURE_DEFS = [
    {"fixture_id": "fixture_01_pdf_visual_infographic", "title": "Field Conversion Flow", "style_family": "navy_teal", "background_mode": "dark", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": True},
    {"fixture_id": "fixture_02_pdf_cards_icons", "title": "Evidence Card Stack", "style_family": "warm_gradient", "background_mode": "warm_light", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": False},
    {"fixture_id": "fixture_03_pdf_dashboard_chart", "title": "Quarterly Signal Dashboard", "style_family": "blueprint_light", "background_mode": "light", "requires_chart": True, "requires_table": False, "has_raster_backplate": False, "dense_vector": True},
    {"fixture_id": "fixture_04_pdf_table_matrix", "title": "Operating Matrix", "style_family": "ivory_report", "background_mode": "ivory", "requires_chart": False, "requires_table": True, "has_raster_backplate": False, "dense_vector": True},
    {"fixture_id": "fixture_05_pdf_photo_caption_hero", "title": "Field Notes and Captions", "style_family": "photo_editorial", "background_mode": "light_photo", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": False},
    {"fixture_id": "fixture_06_pdf_light_editorial_report", "title": "Executive Research Brief", "style_family": "ivory_editorial", "background_mode": "ivory", "requires_chart": True, "requires_table": True, "has_raster_backplate": False, "dense_vector": True},
]


def generate_pdf_fixture(definition: dict[str, Any], fixture_dir: str | Path) -> dict[str, Any]:
    folder = Path(fixture_dir)
    folder.mkdir(parents=True, exist_ok=True)
    truth = build_layer_truth(definition)
    raster_asset = folder / "raster_backplate_asset.png"
    _make_raster_asset(raster_asset, definition)
    pdf_path = folder / "reference.pdf"
    image_path = folder / "reference_image.png"
    _draw_pdf(definition, truth, raster_asset, pdf_path)
    _render_pdf(pdf_path, image_path)
    _write_json(folder / "source_layer_truth.json", truth)
    _write_json(folder / "expected_semantic_slots.json", {"schema_name": "expected_semantic_slots", "slots": truth["semantic_text_objects"] + truth["semantic_icon_objects"] + truth["footer_source_objects"], "canva_parity_claimed": False})
    _write_json(folder / "expected_visual_backplates.json", {"schema_name": "expected_visual_backplates", "backplates": truth["nonsemantic_visual_backplates"] + truth["raster_image_fields"], "canva_parity_claimed": False})
    _write_json(folder / "expected_native_components.json", {"schema_name": "expected_native_components", "components": truth["table_chart_objects"] + truth["card_panel_objects"], "canva_parity_claimed": False})
    _write_json(folder / "expected_raster_policy.json", {"schema_name": "expected_raster_policy", **truth["allowed_raster_policy"], "canva_parity_claimed": False})
    quality = {
        "schema_name": "fixture_quality_report",
        "status": "passed",
        "fixture_id": definition["fixture_id"],
        "background_mode": definition["background_mode"],
        "has_raster_backplate": definition["has_raster_backplate"],
        "dense_vector": definition["dense_vector"],
        "real_pdf_created": True,
        "canva_parity_claimed": False,
    }
    _write_json(folder / "fixture_quality_report.json", quality)
    return {
        "schema_name": "pdfb02_fixture_generation_report",
        "status": "passed",
        "fixture_id": definition["fixture_id"],
        "fixture_dir": folder.as_posix(),
        "reference_pdf": pdf_path.as_posix(),
        "reference_image": image_path.as_posix(),
        "source_layer_truth": (folder / "source_layer_truth.json").as_posix(),
        "truth_summary": {
            "semantic_text_object_count": len(truth["semantic_text_objects"]),
            "vector_object_count": len(truth["vector_objects"]),
            "table_chart_object_count": len(truth["table_chart_objects"]),
            "raster_image_field_count": len(truth["raster_image_fields"]),
        },
        "canva_parity_claimed": False,
    }


def _draw_pdf(definition: dict[str, Any], truth: dict[str, Any], raster_asset: Path, pdf_path: Path) -> None:
    c = canvas.Canvas(str(pdf_path), pagesize=(PAGE_W, PAGE_H))
    palette = _palette(definition)
    c.setFillColor(HexColor(palette["bg"]))
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    if definition["has_raster_backplate"]:
        c.drawImage(ImageReader(str(raster_asset)), PAGE_W * 0.52, PAGE_H * 0.18, PAGE_W * 0.38, PAGE_H * 0.52, mask="auto")
    c.setFillColor(HexColor(palette["title"]))
    c.setFont("Helvetica-Bold", 21)
    c.drawString(PAGE_W * 0.06, PAGE_H * 0.88, definition["title"])
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor(palette["text"]))
    c.drawString(PAGE_W * 0.06, PAGE_H * 0.82, "Controlled PDF fixture with primitives, images, vectors, and semantic text.")
    c.setStrokeColor(HexColor(palette["accent"]))
    c.setLineWidth(1.2)
    c.roundRect(PAGE_W * 0.06, PAGE_H * 0.20, PAGE_W * 0.86, PAGE_H * 0.58, 8, stroke=1, fill=0)
    _draw_fixture_body(c, definition, palette)
    c.setStrokeColor(HexColor(palette["gold"]))
    c.line(PAGE_W * 0.06, PAGE_H * 0.11, PAGE_W * 0.92, PAGE_H * 0.11)
    c.setFillColor(HexColor(palette["gold"]))
    c.setFont("Helvetica", 7)
    c.drawString(PAGE_W * 0.06, PAGE_H * 0.075, "Source: PDFB02 controlled local fixture")
    c.showPage()
    c.save()


def _draw_fixture_body(c: Any, definition: dict[str, Any], palette: dict[str, str]) -> None:
    c.setStrokeColor(HexColor(palette["accent"]))
    c.setFillColor(HexColor(palette["panel"]))
    if definition["requires_table"]:
        x, y, w, h = PAGE_W * 0.10, PAGE_H * 0.28, PAGE_W * 0.58, PAGE_H * 0.38
        c.rect(x, y, w, h, stroke=1, fill=0)
        for i in range(1, 6):
            c.line(x, y + h * i / 6, x + w, y + h * i / 6)
        for i in range(1, 5):
            c.line(x + w * i / 5, y, x + w * i / 5, y + h)
        c.setFont("Helvetica", 6)
        c.setFillColor(HexColor(palette["text"]))
        for r in range(4):
            c.drawString(x + 8, y + h - 20 - r * 24, f"Row {r+1}")
    if definition["requires_chart"]:
        x, y = PAGE_W * 0.14, PAGE_H * 0.30
        c.setFillColor(HexColor(palette["accent"]))
        for i, val in enumerate([90, 64, 78, 52]):
            c.rect(x + i * 34, y, 18, val, stroke=0, fill=1)
    if not definition["requires_chart"] and not definition["requires_table"]:
        for i in range(4):
            x = PAGE_W * (0.10 + i * 0.13)
            y = PAGE_H * 0.47
            c.roundRect(x, y, 70, 42, 5, stroke=1, fill=0)
            c.circle(x + 15, y + 21, 7, stroke=1, fill=0)
            if i < 3:
                c.line(x + 70, y + 21, x + 92, y + 21)


def _render_pdf(pdf_path: Path, image_path: Path) -> None:
    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(1600 / PAGE_W, 900 / PAGE_H), alpha=False)
    pix.save(image_path)
    doc.close()


def _make_raster_asset(path: Path, definition: dict[str, Any]) -> None:
    image = Image.new("RGB", (520, 360), _palette(definition)["photo_bg"])
    draw = ImageDraw.Draw(image)
    for i in range(18):
        draw.arc((20 + i * 10, 20 + i * 5, 460, 330), 205, 320, fill=(255, 255, 255), width=1)
    for i in range(30):
        draw.ellipse((20 + i * 15 % 460, 30 + i * 23 % 300, 24 + i * 15 % 460, 34 + i * 23 % 300), fill=(236, 180, 70))
    image.save(path)


def _palette(definition: dict[str, Any]) -> dict[str, str]:
    mode = definition["background_mode"]
    if mode in {"ivory", "warm_light"}:
        return {"bg": "#F2EEE4", "title": "#20313A", "text": "#425057", "accent": "#2B7A78", "gold": "#B17628", "panel": "#FFF8EA", "photo_bg": "#CFC7B2"}
    if mode in {"light", "light_photo"}:
        return {"bg": "#EAF2F7", "title": "#172B3A", "text": "#344955", "accent": "#247BA0", "gold": "#C5922A", "panel": "#FFFFFF", "photo_bg": "#A7C5D8"}
    return {"bg": "#081B27", "title": "#FFFFFF", "text": "#DDEBF0", "accent": "#2ACADA", "gold": "#EDC55D", "panel": "#0B3744", "photo_bg": "#123B4A"}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
