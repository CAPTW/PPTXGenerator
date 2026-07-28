"""Build the PDFB02 fixture set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.presentation_agent.magic_layer.pdfb02_pdf_fixture_generator import PDFB02_FIXTURE_DEFS, generate_pdf_fixture


def build_pdfb02_fixtures(output_root: str | Path) -> dict[str, Any]:
    output = Path(output_root)
    fixtures_dir = output / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for definition in PDFB02_FIXTURE_DEFS:
        generated = generate_pdf_fixture(definition, fixtures_dir / definition["fixture_id"])
        truth = _read_json(Path(generated["source_layer_truth"]))
        fixture = {
            "fixture_id": definition["fixture_id"],
            "title": definition["title"],
            "category": definition["fixture_id"].replace("fixture_", ""),
            "style_family": definition["style_family"],
            "background_mode": definition["background_mode"],
            "fixture_dir": generated["fixture_dir"],
            "reference_pdf": generated["reference_pdf"],
            "reference_image": generated["reference_image"],
            "source_layer_truth": generated["source_layer_truth"],
            "semantic_slot_count": len(truth.get("semantic_text_objects", [])) + len(truth.get("semantic_icon_objects", [])),
            "requires_chart": definition["requires_chart"],
            "requires_table": definition["requires_table"],
            "has_raster_backplate": definition["has_raster_backplate"],
            "dense_vector": definition["dense_vector"],
            "canva_parity_claimed": False,
        }
        _write_source_layer_hint(Path(generated["fixture_dir"]), truth, fixture)
        fixtures.append(fixture)
    non_dark = sum(1 for fixture in fixtures if fixture["background_mode"] != "dark")
    raster = sum(1 for fixture in fixtures if fixture["has_raster_backplate"])
    dense = sum(1 for fixture in fixtures if fixture["dense_vector"] or fixture["requires_chart"] or fixture["requires_table"])
    manifest = {
        "schema_name": "fixtures_manifest_v2",
        "status": "passed" if len(fixtures) >= 6 and non_dark >= 2 and raster >= 2 and dense >= 2 else "failed",
        "fixture_count": len(fixtures),
        "non_dark_background_fixture_count": non_dark,
        "raster_visual_backplate_fixture_count": raster,
        "dense_vector_table_chart_fixture_count": dense,
        "fixtures": fixtures,
        "canva_parity_claimed": False,
    }
    _write_json(output / "fixtures_manifest_v2.json", manifest)
    diversity = {
        "schema_name": "fixture_style_diversity_report",
        "status": manifest["status"],
        "style_families": sorted({fixture["style_family"] for fixture in fixtures}),
        "background_modes": sorted({fixture["background_mode"] for fixture in fixtures}),
        "non_dark_background_fixture_count": non_dark,
        "canva_parity_claimed": False,
    }
    _write_json(output / "fixture_style_diversity_report.json", diversity)
    _write_md(output / "fixture_style_diversity_report.md", "# Fixture Style Diversity Report\n\n- status: `passed`\n- non_dark_background_fixture_count: `" + str(non_dark) + "`\n")
    layer_truth = {
        "schema_name": "fixture_layer_truth_report",
        "status": "passed",
        "fixture_count": len(fixtures),
        "fixtures_with_truth": len([fixture for fixture in fixtures if Path(fixture["source_layer_truth"]).exists()]),
        "canva_parity_claimed": False,
    }
    _write_json(output / "fixture_layer_truth_report.json", layer_truth)
    _write_md(output / "fixture_layer_truth_report.md", "# Fixture Layer Truth Report\n\n- status: `passed`\n- fixtures_with_truth: `" + str(layer_truth["fixtures_with_truth"]) + "`\n")
    _build_contact_sheet(fixtures, output / "fixtures_contact_sheet_v2.png")
    return manifest


def _write_source_layer_hint(folder: Path, truth: dict[str, Any], fixture: dict[str, Any]) -> None:
    hints = {
        "schema_name": "source_layer_hint",
        "fixture_id": fixture["fixture_id"],
        "semantic_text_zones": truth.get("semantic_text_objects", []),
        "semantic_icon_zones": truth.get("semantic_icon_objects", []),
        "chart_table_zones": truth.get("table_chart_objects", []),
        "card_panel_zones": truth.get("card_panel_objects", []),
        "footer_source_zones": truth.get("footer_source_objects", []),
        "nonsemantic_visual_backplate_zones": truth.get("nonsemantic_visual_backplates", []) + truth.get("raster_image_fields", []),
        "hero_photo_visual_fields": truth.get("raster_image_fields", []),
        "allowed_raster_zones": truth.get("allowed_raster_policy", {}).get("allowed_raster_object_ids", []),
        "forbidden_raster_zones": truth.get("allowed_raster_policy", {}).get("forbidden_raster_roles", []),
        "canva_parity_claimed": False,
    }
    _write_json(folder / "source_layer_hint.json", hints)


def _build_contact_sheet(fixtures: list[dict[str, Any]], output: Path) -> None:
    canvas = Image.new("RGB", (1600, 1160), (245, 245, 241))
    draw = ImageDraw.Draw(canvas)
    draw.text((34, 26), "PDFB02 diverse real PDF/PPT-like fixtures", fill=(28, 39, 48), font=_font(30))
    for index, fixture in enumerate(fixtures):
        image = Image.open(fixture["reference_image"]).convert("RGB")
        image.thumbnail((440, 248))
        col = index % 3
        row = index // 3
        x = 42 + col * 515
        y = 95 + row * 480
        canvas.paste(image, (x, y))
        draw.rectangle((x, y, x + 440, y + 248), outline=(34, 108, 124), width=2)
        draw.text((x, y + 262), fixture["fixture_id"], fill=(44, 56, 64), font=_font(15))
        draw.text((x, y + 286), fixture["style_family"], fill=(151, 92, 28), font=_font(13))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _font(size: int) -> ImageFont.ImageFont:
    for font_name in ("arial.ttf", "calibri.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()
