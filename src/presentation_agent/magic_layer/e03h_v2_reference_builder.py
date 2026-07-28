"""Build the E03H-V2 12-core reference input set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.presentation_agent.magic_layer.pdfb02_pdf_fixture_generator import generate_pdf_fixture


E03H_V2_REFERENCE_DEFS = [
    {"fixture_id": "maritime_checklist_hero", "title": "Editable maritime checklist", "style_family": "maritime_dark", "background_mode": "dark", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": True, "archetype": "hero_checklist"},
    {"fixture_id": "process_workflow_infographic", "title": "Process Workflow Infographic", "style_family": "process_teal_dark", "background_mode": "dark", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": True, "archetype": "process"},
    {"fixture_id": "data_dashboard_hybrid", "title": "Signal Dashboard Hybrid", "style_family": "dashboard_light", "background_mode": "light", "requires_chart": True, "requires_table": False, "has_raster_backplate": False, "dense_vector": True, "archetype": "dashboard"},
    {"fixture_id": "table_matrix_hybrid", "title": "Operating Table Matrix", "style_family": "ivory_table", "background_mode": "ivory", "requires_chart": False, "requires_table": True, "has_raster_backplate": False, "dense_vector": True, "archetype": "table_matrix"},
    {"fixture_id": "cover_hero_photo_editorial", "title": "Editorial Hero Cover", "style_family": "photo_editorial_light", "background_mode": "light_photo", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": False, "archetype": "hero_photo"},
    {"fixture_id": "standard_content_card_cluster", "title": "Content Card Cluster", "style_family": "warm_cards", "background_mode": "warm_light", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": False, "archetype": "cards"},
    {"fixture_id": "evidence_stack_visual", "title": "Evidence Stack Visual", "style_family": "evidence_warm", "background_mode": "warm_light", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": True, "archetype": "evidence"},
    {"fixture_id": "comparison_matrix_hybrid", "title": "Comparison Matrix Hybrid", "style_family": "comparison_light", "background_mode": "light", "requires_chart": False, "requires_table": True, "has_raster_backplate": False, "dense_vector": True, "archetype": "comparison_matrix"},
    {"fixture_id": "methodology_framework_layered", "title": "Layered Methodology Framework", "style_family": "framework_dark", "background_mode": "dark", "requires_chart": False, "requires_table": False, "has_raster_backplate": False, "dense_vector": True, "archetype": "framework"},
    {"fixture_id": "timeline_roadmap_hybrid", "title": "Timeline Roadmap Hybrid", "style_family": "roadmap_light", "background_mode": "light", "requires_chart": False, "requires_table": False, "has_raster_backplate": False, "dense_vector": True, "archetype": "timeline"},
    {"fixture_id": "visual_toc_navigation", "title": "Visual TOC Navigation", "style_family": "navigation_ivory", "background_mode": "ivory", "requires_chart": False, "requires_table": False, "has_raster_backplate": False, "dense_vector": False, "archetype": "navigation"},
    {"fixture_id": "photo_caption_grid_hybrid", "title": "Photo Caption Grid Hybrid", "style_family": "photo_grid_light", "background_mode": "light_photo", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": False, "archetype": "photo_caption"},
]


def build_e03h_v2_references(output_root: str | Path) -> dict[str, Any]:
    output = Path(output_root)
    refs_dir = output / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    refs = []
    for definition in E03H_V2_REFERENCE_DEFS:
        ref_dir = refs_dir / definition["fixture_id"]
        generate_pdf_fixture(definition, ref_dir)
        truth = _read_json(ref_dir / "source_layer_truth.json")
        ref = {
            "reference_id": definition["fixture_id"],
            "title": definition["title"],
            "category": definition["fixture_id"],
            "archetype": definition["archetype"],
            "is_core": True,
            "reference_dir": ref_dir.as_posix(),
            "reference_pdf": (ref_dir / "reference.pdf").as_posix(),
            "reference_image": (ref_dir / "reference_image.png").as_posix(),
            "source_layer_truth": (ref_dir / "source_layer_truth.json").as_posix(),
            "expected_semantic_slots": (ref_dir / "expected_semantic_slots.json").as_posix(),
            "expected_visual_backplates": (ref_dir / "expected_visual_backplates.json").as_posix(),
            "expected_native_components": (ref_dir / "expected_native_components.json").as_posix(),
            "expected_raster_policy": (ref_dir / "expected_raster_policy.json").as_posix(),
            "background_mode": truth.get("background_mode", definition["background_mode"]),
            "style_family": definition["style_family"],
            "requires_chart": definition["requires_chart"],
            "requires_table": definition["requires_table"],
            "has_raster_backplate": definition["has_raster_backplate"],
            "dense_vector": definition["dense_vector"],
            "semantic_icon_required": True,
            "semantic_slot_count": len(truth.get("semantic_text_objects", [])) + len(truth.get("semantic_icon_objects", [])) + len(truth.get("footer_source_objects", [])),
            "canva_parity_claimed": False,
        }
        refs.append(ref)
    manifest = _manifest(refs)
    _write_json(output / "e03h_v2_reference_registry.json", manifest)
    _contact_sheet(refs, output / "e03h_v2_reference_contact_sheet.png")
    return manifest


def _manifest(refs: list[dict[str, Any]]) -> dict[str, Any]:
    non_dark = sum(1 for ref in refs if ref["background_mode"] != "dark")
    raster = sum(1 for ref in refs if ref["has_raster_backplate"])
    dense = sum(1 for ref in refs if ref["dense_vector"] or ref["requires_chart"] or ref["requires_table"])
    table = sum(1 for ref in refs if ref["requires_table"])
    chart = sum(1 for ref in refs if ref["requires_chart"])
    icons = sum(1 for ref in refs if ref["semantic_icon_required"])
    return {
        "schema_name": "e03h_v2_reference_registry",
        "status": "passed" if len(refs) >= 12 and non_dark >= 3 and raster >= 3 and dense >= 3 and table >= 2 and chart >= 1 and icons >= 4 else "failed",
        "reference_count": len(refs),
        "core_reference_count": len([ref for ref in refs if ref["is_core"]]),
        "accepted_reference_count": len(refs),
        "non_dark_reference_count": non_dark,
        "raster_visual_backplate_reference_count": raster,
        "dense_vector_table_chart_reference_count": dense,
        "native_table_reference_count": table,
        "native_chart_reference_count": chart,
        "semantic_svg_icon_reference_count": icons,
        "references": refs,
        "canva_parity_claimed": False,
    }


def _contact_sheet(refs: list[dict[str, Any]], output: Path) -> None:
    canvas = Image.new("RGB", (1600, 1260), (246, 247, 244))
    draw = ImageDraw.Draw(canvas)
    draw.text((28, 18), "E03H-V2 core reference inputs", fill=(30, 42, 51), font=_font(26))
    for idx, ref in enumerate(refs):
        image = Image.open(ref["reference_image"]).convert("RGB")
        image.thumbnail((360, 203))
        x = 28 + (idx % 4) * 390
        y = 62 + (idx // 4) * 385
        canvas.paste(image, (x, y))
        draw.rectangle((x, y, x + 360, y + 203), outline=(34, 108, 124), width=2)
        draw.text((x, y + 214), ref["reference_id"], fill=(44, 56, 64), font=_font(12))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _font(size: int) -> ImageFont.ImageFont:
    for font_name in ("arial.ttf", "calibri.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()
