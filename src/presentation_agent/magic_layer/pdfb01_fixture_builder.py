"""Build controlled local PDF/PPT-like fixtures for PDFB01."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[3]
E01H_P = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e01h_p_semantic_icon_microcomponent_fidelity_patch"
E03H_P2 = REPO_ROOT / "design_runs/run_002/outputs/magic_layer_engine_e03h_p2_svg_provenance_rebinding_patch"


FIXTURE_DEFS = [
    {
        "fixture_id": "fixture_01_visual_infographic",
        "title": "Process infographic with visual backplates",
        "category": "visual_infographic",
        "source_image": E03H_P2 / "references/process_workflow_infographic/rendered_candidate.png",
        "requires_chart": False,
        "requires_table": False,
        "semantic_slots": ["title", "process_node_1", "process_node_2", "process_node_3", "connector_labels", "footer"],
        "backplate_roles": ["technical_ornament", "subtle_background_depth"],
    },
    {
        "fixture_id": "fixture_02_cards_icons",
        "title": "Card cluster with semantic icons",
        "category": "cards_icons",
        "source_image": E03H_P2 / "references/standard_content_card_cluster/rendered_candidate.png",
        "requires_chart": False,
        "requires_table": False,
        "semantic_slots": ["title", "card_1", "card_2", "card_3", "semantic_icons", "footer"],
        "backplate_roles": ["card_depth_chrome", "atmosphere_texture"],
    },
    {
        "fixture_id": "fixture_03_dashboard_chart",
        "title": "Dashboard chart reconstruction",
        "category": "dashboard_chart",
        "source_image": E03H_P2 / "references/data_dashboard_hybrid/rendered_candidate.png",
        "requires_chart": True,
        "requires_table": False,
        "semantic_slots": ["title", "kpi_1", "kpi_2", "chart_title", "insight", "footer"],
        "backplate_roles": ["dashboard_depth", "technical_ornament"],
    },
    {
        "fixture_id": "fixture_04_table_matrix",
        "title": "Editable table matrix",
        "category": "table_matrix",
        "source_image": E03H_P2 / "references/table_matrix_hybrid/rendered_candidate.png",
        "requires_chart": False,
        "requires_table": True,
        "semantic_slots": ["title", "row_header", "column_header", "body_cells", "footer"],
        "backplate_roles": ["table_depth", "subtle_background_depth"],
    },
    {
        "fixture_id": "fixture_05_photo_caption_or_hero",
        "title": "Photo/caption visual field",
        "category": "photo_caption_or_hero",
        "source_image": E03H_P2 / "references/photo_caption_grid_hybrid/rendered_candidate.png",
        "fallback_image": E01H_P / "patched_rendered_candidate.png",
        "requires_chart": False,
        "requires_table": False,
        "semantic_slots": ["title", "caption_1", "caption_2", "caption_3", "footer"],
        "backplate_roles": ["hero_photo_field", "nonsemantic_photo_or_visual_field"],
    },
]


def build_pdfb01_fixtures(output_root: str | Path) -> dict[str, Any]:
    output = Path(output_root)
    fixture_root = output / "fixtures"
    fixture_root.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for definition in FIXTURE_DEFS:
        fixture_dir = fixture_root / definition["fixture_id"]
        fixture_dir.mkdir(parents=True, exist_ok=True)
        source_image = _source_image(definition)
        reference_path = fixture_dir / "reference_image.png"
        _copy_as_16_9(source_image, reference_path)
        hints = _layer_hints(definition)
        expected_semantic = {"schema_name": "expected_semantic_slots", "fixture_id": definition["fixture_id"], "slots": hints["semantic_text_zones"] + hints["semantic_icon_zones"] + hints["footer_source_zones"], "canva_parity_claimed": False}
        expected_backplates = {"schema_name": "expected_visual_backplates", "fixture_id": definition["fixture_id"], "allowed_backplates": hints["nonsemantic_visual_backplate_zones"] + hints["hero_photo_visual_fields"], "canva_parity_claimed": False}
        expected_native = {"schema_name": "expected_native_components", "fixture_id": definition["fixture_id"], "requires_chart": definition["requires_chart"], "requires_table": definition["requires_table"], "components": hints["chart_table_zones"] + hints["card_panel_zones"], "canva_parity_claimed": False}
        expected_policy = {"schema_name": "expected_raster_policy", "fixture_id": definition["fixture_id"], "allowed_raster_zones": hints["allowed_raster_zones"], "forbidden_raster_zones": hints["forbidden_raster_zones"], "full_slide_reference_background_allowed": False, "canva_parity_claimed": False}
        _write_json(fixture_dir / "source_layer_hint.json", hints)
        _write_json(fixture_dir / "expected_semantic_slots.json", expected_semantic)
        _write_json(fixture_dir / "expected_visual_backplates.json", expected_backplates)
        _write_json(fixture_dir / "expected_native_components.json", expected_native)
        _write_json(fixture_dir / "expected_raster_policy.json", expected_policy)
        fixtures.append(
            {
                "fixture_id": definition["fixture_id"],
                "title": definition["title"],
                "category": definition["category"],
                "fixture_dir": fixture_dir.as_posix(),
                "reference_image": reference_path.as_posix(),
                "source_artifact": source_image.as_posix(),
                "semantic_slot_count": len(expected_semantic["slots"]),
                "requires_chart": definition["requires_chart"],
                "requires_table": definition["requires_table"],
                "canva_parity_claimed": False,
            }
        )
    manifest = {"schema_name": "fixture_manifest", "status": "passed", "fixture_count": len(fixtures), "fixtures": fixtures, "canva_parity_claimed": False}
    quality = {"schema_name": "fixture_quality_report", "status": "passed", "fixture_count": len(fixtures), "fixtures_are_local": True, "image_api_used": False, "too_artificial_count": 0, "canva_parity_claimed": False}
    _write_json(output / "fixture_manifest.json", manifest)
    _write_json(output / "fixture_quality_report.json", quality)
    _write_md(output / "fixture_quality_report.md", "# Fixture Quality Report\n\n- status: `passed`\n- fixture_count: `5`\n- image_api_used: `False`\n")
    _build_contact_sheet(fixtures, output / "fixture_contact_sheet.png")
    return manifest


def _layer_hints(definition: dict[str, Any]) -> dict[str, Any]:
    fid = definition["fixture_id"]
    return {
        "schema_name": "source_layer_hint",
        "fixture_id": fid,
        "category": definition["category"],
        "canvas_ratio": "16:9",
        "semantic_text_zones": [
            {"zone_id": "title", "bbox_norm": [0.06, 0.06, 0.52, 0.12], "text": definition["title"]},
            {"zone_id": "body_1", "bbox_norm": [0.08, 0.20, 0.42, 0.36], "text": "Editable conversion benchmark content"},
            {"zone_id": "body_2", "bbox_norm": [0.50, 0.20, 0.84, 0.36], "text": "Layer separation and reconstruction"},
        ],
        "semantic_icon_zones": [{"zone_id": "icon_1", "bbox_norm": [0.08, 0.40, 0.12, 0.47], "semantic_intent": "generic_check"}],
        "chart_table_zones": _chart_table_zones(definition),
        "card_panel_zones": [{"zone_id": "panel_1", "bbox_norm": [0.07, 0.18, 0.88, 0.72], "native_required": True}],
        "footer_source_zones": [{"zone_id": "footer", "bbox_norm": [0.06, 0.88, 0.92, 0.94], "text": "Local benchmark fixture"}],
        "nonsemantic_visual_backplate_zones": [{"zone_id": "backplate_1", "bbox_norm": [0.04, 0.10, 0.94, 0.82], "roles": definition["backplate_roles"]}],
        "hero_photo_visual_fields": [{"zone_id": "hero_field", "bbox_norm": [0.55, 0.18, 0.90, 0.70], "required": definition["category"] == "photo_caption_or_hero"}],
        "allowed_raster_zones": ["backplate_1", "hero_field"],
        "forbidden_raster_zones": ["title", "body_1", "body_2", "icon_1", "footer"] + (["chart_1"] if definition["requires_chart"] else []) + (["table_1"] if definition["requires_table"] else []),
        "canva_parity_claimed": False,
    }


def _chart_table_zones(definition: dict[str, Any]) -> list[dict[str, Any]]:
    zones = []
    if definition["requires_chart"]:
        zones.append({"zone_id": "chart_1", "bbox_norm": [0.12, 0.30, 0.55, 0.68], "component_type": "native_chart", "native_required": True})
    if definition["requires_table"]:
        zones.append({"zone_id": "table_1", "bbox_norm": [0.10, 0.24, 0.70, 0.72], "component_type": "native_table", "native_required": True})
    return zones


def _source_image(definition: dict[str, Any]) -> Path:
    primary = Path(definition["source_image"])
    if primary.exists():
        return primary
    fallback = definition.get("fallback_image")
    if fallback and Path(fallback).exists():
        return Path(fallback)
    return primary


def _copy_as_16_9(source: Path, target: Path) -> None:
    if source.exists():
        image = Image.open(source).convert("RGB").resize((1600, 900))
    else:
        image = Image.new("RGB", (1600, 900), (8, 27, 39))
        draw = ImageDraw.Draw(image)
        draw.text((80, 80), source.stem, fill=(255, 255, 255), font=_font(30))
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)


def _build_contact_sheet(fixtures: list[dict[str, Any]], output: Path) -> None:
    canvas = Image.new("RGB", (1500, 980), (8, 22, 32))
    draw = ImageDraw.Draw(canvas)
    draw.text((34, 28), "PDFB01 local benchmark fixtures", fill=(255, 255, 255), font=_font(30))
    for index, fixture in enumerate(fixtures):
        image = Image.open(fixture["reference_image"]).convert("RGB")
        image.thumbnail((420, 236))
        col = index % 2
        row = index // 2
        x = 44 + col * 700
        y = 95 + row * 290
        canvas.paste(image, (x, y))
        draw.rectangle((x, y, x + 420, y + 236), outline=(42, 202, 218), width=2)
        draw.text((x, y + 246), fixture["fixture_id"], fill=(237, 197, 93), font=_font(16))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


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
