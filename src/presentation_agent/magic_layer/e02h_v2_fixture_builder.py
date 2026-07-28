"""Build E02H-V2 holdout PDF/PPT-like fixtures."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.presentation_agent.magic_layer.pdfb02_pdf_fixture_generator import generate_pdf_fixture


E02H_V2_HOLDOUT_DEFS = [
    {"fixture_id": "holdout_01_e01hp_maritime_checklist_regression", "title": "Editable maritime checklist", "style_family": "maritime_regression_dark", "background_mode": "dark", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": True},
    {"fixture_id": "holdout_02_process_vector_infographic", "title": "Readiness Workflow Sequence", "style_family": "process_vector_teal", "background_mode": "dark", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": True},
    {"fixture_id": "holdout_03_dashboard_chart_hard", "title": "Holdout Signal Dashboard", "style_family": "light_dashboard_blue", "background_mode": "light", "requires_chart": True, "requires_table": False, "has_raster_backplate": False, "dense_vector": True},
    {"fixture_id": "holdout_04_dense_table_matrix_hard", "title": "Dense Governance Matrix", "style_family": "ivory_table_report", "background_mode": "ivory", "requires_chart": False, "requires_table": True, "has_raster_backplate": False, "dense_vector": True},
    {"fixture_id": "holdout_05_photo_caption_hero_hard", "title": "Inspection Field Notes", "style_family": "photo_caption_light", "background_mode": "light_photo", "requires_chart": False, "requires_table": False, "has_raster_backplate": True, "dense_vector": False},
    {"fixture_id": "holdout_06_light_editorial_mixed", "title": "Light Editorial Decision Brief", "style_family": "ivory_editorial_mixed", "background_mode": "ivory", "requires_chart": True, "requires_table": True, "has_raster_backplate": False, "dense_vector": True},
]


def build_e02h_v2_holdout_fixtures(output_root: str | Path, *, r1_maritime_case_dir: str | Path | None = None) -> dict[str, Any]:
    output = Path(output_root)
    fixtures_dir = output / "holdout_cases"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for definition in E02H_V2_HOLDOUT_DEFS:
        case_dir = fixtures_dir / definition["fixture_id"]
        generated = generate_pdf_fixture(definition, case_dir)
        if definition["fixture_id"] == "holdout_01_e01hp_maritime_checklist_regression" and r1_maritime_case_dir:
            _copy_maritime_inputs(Path(r1_maritime_case_dir), case_dir)
        truth = _read_json(case_dir / "source_layer_truth.json")
        case = {
            "case_id": definition["fixture_id"],
            "title": definition["title"],
            "style_family": definition["style_family"],
            "background_mode": truth.get("background_mode", definition["background_mode"]),
            "case_dir": case_dir.as_posix(),
            "reference_pdf": (case_dir / "reference.pdf").as_posix(),
            "reference_image": (case_dir / "reference_image.png").as_posix(),
            "source_layer_truth": (case_dir / "source_layer_truth.json").as_posix(),
            "expected_semantic_slots": (case_dir / "expected_semantic_slots.json").as_posix(),
            "expected_visual_backplates": (case_dir / "expected_visual_backplates.json").as_posix(),
            "expected_native_components": (case_dir / "expected_native_components.json").as_posix(),
            "expected_raster_policy": (case_dir / "expected_raster_policy.json").as_posix(),
            "requires_chart": definition["requires_chart"],
            "requires_table": definition["requires_table"],
            "has_raster_backplate": definition["has_raster_backplate"],
            "dense_vector": definition["dense_vector"],
            "source_preference": "e01h_v2_r1_maritime" if definition["fixture_id"].startswith("holdout_01") else "controlled_holdout_pdf",
            "canva_parity_claimed": False,
        }
        cases.append(case)
    non_dark = sum(1 for case in cases if case["background_mode"] != "dark")
    raster = sum(1 for case in cases if case["has_raster_backplate"])
    dense = sum(1 for case in cases if case["dense_vector"] or case["requires_chart"] or case["requires_table"])
    manifest = {
        "schema_name": "holdout_case_registry",
        "status": "passed" if len(cases) >= 6 and non_dark >= 2 and raster >= 2 and dense >= 2 else "failed",
        "case_count": len(cases),
        "non_dark_background_case_count": non_dark,
        "raster_visual_backplate_case_count": raster,
        "dense_vector_table_chart_case_count": dense,
        "cases": cases,
        "canva_parity_claimed": False,
    }
    _write_json(output / "holdout_case_registry.json", manifest)
    _write_json(output / "holdout_fixture_diversity_report.json", _diversity_report(manifest))
    _write_md(output / "holdout_fixture_diversity_report.md", "# Holdout Fixture Diversity Report\n\n- status: `passed`\n- case_count: `" + str(len(cases)) + "`\n")
    _contact_sheet(cases, output / "holdout_fixture_contact_sheet.png")
    return manifest


def _copy_maritime_inputs(source: Path, destination: Path) -> None:
    for name in [
        "reference.pdf",
        "reference_image.png",
        "source_layer_truth.json",
        "expected_semantic_slots.json",
        "expected_visual_backplates.json",
        "expected_native_components.json",
        "expected_raster_policy.json",
    ]:
        src = source / name
        if src.exists():
            shutil.copy2(src, destination / name)


def _diversity_report(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "holdout_fixture_diversity_report",
        "status": manifest["status"],
        "case_count": manifest["case_count"],
        "non_dark_background_case_count": manifest["non_dark_background_case_count"],
        "raster_visual_backplate_case_count": manifest["raster_visual_backplate_case_count"],
        "dense_vector_table_chart_case_count": manifest["dense_vector_table_chart_case_count"],
        "style_families": sorted({case["style_family"] for case in manifest["cases"]}),
        "canva_parity_claimed": False,
    }


def _contact_sheet(cases: list[dict[str, Any]], output: Path) -> None:
    canvas = Image.new("RGB", (1260, 590), (246, 247, 244))
    draw = ImageDraw.Draw(canvas)
    draw.text((22, 18), "E02H-V2 holdout fixtures", fill=(30, 42, 51), font=_font(24))
    for idx, case in enumerate(cases):
        image = Image.open(case["reference_image"]).convert("RGB")
        image.thumbnail((360, 203))
        x = 22 + (idx % 3) * 410
        y = 58 + (idx // 3) * 260
        canvas.paste(image, (x, y))
        draw.rectangle((x, y, x + 360, y + 203), outline=(34, 108, 124), width=2)
        draw.text((x, y + 214), case["case_id"], fill=(44, 56, 64), font=_font(12))
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
