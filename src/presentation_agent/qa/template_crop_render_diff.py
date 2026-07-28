"""Compare design-board crops with rendered editable template preview layouts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageStat

from ..compiler.template_compiler import compile_template_pack_from_files
from .render_pptx_preview import render_pptx_preview


DEFAULT_CROP_MANIFEST = Path("outputs/template_design_board/design_board_crop_manifest.json")
DEFAULT_TEMPLATE_SPEC = Path("outputs/editable_template_spec.final.json")
DEFAULT_TEMPLATE_PREVIEW = Path("outputs/template_preview.pptx")
DEFAULT_TEMPLATE_PREVIEW_MANIFEST = Path("outputs/template_preview_manifest.json")
DEFAULT_RENDER_DIR = Path("outputs/template_preview_png")
DEFAULT_RENDER_MANIFEST = Path("outputs/render_preview_manifest.json")
DEFAULT_OUTPUT_DIR = Path("outputs/template_fidelity")
DEFAULT_JSON_REPORT = DEFAULT_OUTPUT_DIR / "template_crop_render_diff_report.json"
DEFAULT_MD_REPORT = DEFAULT_OUTPUT_DIR / "template_crop_render_diff_report.md"
DEFAULT_CONTACT_SHEET = DEFAULT_OUTPUT_DIR / "contact_sheet_template_crop_vs_render.png"


SLIDE_TYPE_BY_CROP_ROLE = {
    "hero_cover": "creative_cover",
    "hero_main_content": "section_divider",
    "slide_thumbnail_01_creative_cover": "creative_cover",
    "slide_thumbnail_02_visual_table_of_contents": "visual_table_of_contents",
    "slide_thumbnail_03_section_divider": "section_divider",
    "slide_thumbnail_04_research_overview": "research_overview",
    "slide_thumbnail_05_problem_statement": "problem_statement",
    "slide_thumbnail_06_research_gap": "research_gap",
    "slide_thumbnail_07_literature_map": "literature_map",
    "slide_thumbnail_08_methodology_framework": "methodology_framework",
    "slide_thumbnail_09_technical_flow_chart": "technical_flow_chart",
    "slide_thumbnail_10_work_support_sequence": "work_support_sequence",
    "slide_thumbnail_11_photo_caption_grid": "photo_caption_grid",
    "slide_thumbnail_12_comparison_matrix": "comparison_matrix",
    "slide_thumbnail_13_concept_relationship_venn": "concept_relationship_venn",
    "slide_thumbnail_14_three_level_explanation": "three_level_explanation",
    "slide_thumbnail_15_circular_process": "circular_process",
    "slide_thumbnail_16_kpi_donut_chart": "kpi_donut_chart",
    "slide_thumbnail_17_timeline_roadmap": "timeline_roadmap",
    "slide_thumbnail_18_data_table_appendix": "data_table_appendix",
}

NON_LAYOUT_CROP_ROLES = {
    "component_library",
    "master_layout_system",
    "storytelling_plan",
    "style_tokens",
}


def build_template_crop_render_diff_from_files(
    *,
    crop_manifest_path: str | Path = DEFAULT_CROP_MANIFEST,
    template_spec_path: str | Path = DEFAULT_TEMPLATE_SPEC,
    template_preview_pptx_path: str | Path = DEFAULT_TEMPLATE_PREVIEW,
    template_preview_manifest_path: str | Path = DEFAULT_TEMPLATE_PREVIEW_MANIFEST,
    render_dir: str | Path = DEFAULT_RENDER_DIR,
    render_manifest_path: str | Path = DEFAULT_RENDER_MANIFEST,
    json_report_path: str | Path = DEFAULT_JSON_REPORT,
    md_report_path: str | Path = DEFAULT_MD_REPORT,
    contact_sheet_path: str | Path = DEFAULT_CONTACT_SHEET,
    renderer: str = "auto",
) -> Path:
    """Compile/render final-spec template previews and compare them with board crops."""

    spec_path = Path(template_spec_path)
    preview_path = Path(template_preview_pptx_path)
    preview_manifest_path = Path(template_preview_manifest_path)
    compile_template_pack_from_files(
        spec_path=spec_path,
        output_path=preview_path,
        manifest_path=preview_manifest_path,
    )
    render_report = render_pptx_preview(
        pptx_path=preview_path,
        output_dir=render_dir,
        report_path=render_manifest_path,
        backend=renderer,
    )

    report = build_template_crop_render_diff_report(
        crop_manifest_path=crop_manifest_path,
        template_spec_path=spec_path,
        template_preview_pptx_path=preview_path,
        template_preview_manifest_path=preview_manifest_path,
        render_dir=render_dir,
        render_report=render_report,
    )
    json_path = Path(json_report_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    Path(md_report_path).write_text(_markdown_report(report), encoding="utf-8")
    _write_contact_sheet(report, contact_sheet_path)
    return json_path


def build_template_crop_render_diff_report(
    *,
    crop_manifest_path: str | Path = DEFAULT_CROP_MANIFEST,
    template_spec_path: str | Path = DEFAULT_TEMPLATE_SPEC,
    template_preview_pptx_path: str | Path = DEFAULT_TEMPLATE_PREVIEW,
    template_preview_manifest_path: str | Path = DEFAULT_TEMPLATE_PREVIEW_MANIFEST,
    render_dir: str | Path = DEFAULT_RENDER_DIR,
    render_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    crop_manifest = _load_json(crop_manifest_path)
    spec = _load_json(template_spec_path)
    preview_manifest = _load_json(template_preview_manifest_path)
    render_report = render_report or _load_json(DEFAULT_RENDER_MANIFEST)
    preview_rendering_path = str(preview_manifest.get("rendering_path") or "unknown")

    layouts_by_archetype = _layouts_by_archetype(spec)
    layouts_by_id = {str(layout.get("layout_id")): layout for layout in spec.get("layouts") or []}
    rendered_by_layout = _rendered_paths_by_layout(preview_manifest, render_report, Path(render_dir))

    comparisons: list[dict[str, Any]] = []
    unmapped_crops: list[dict[str, Any]] = []
    for crop in crop_manifest.get("crops") or []:
        if not isinstance(crop, dict):
            continue
        crop_role = str(crop.get("crop_role") or crop.get("crop_id") or "")
        crop_path = Path(str(crop.get("path") or ""))
        slide_type = SLIDE_TYPE_BY_CROP_ROLE.get(crop_role)
        if not slide_type:
            if crop_role in NON_LAYOUT_CROP_ROLES:
                unmapped_crops.append(_component_crop_record(crop_role, crop_path))
            continue
        layout = layouts_by_archetype.get(slide_type)
        if not layout:
            comparisons.append(_missing_layout_comparison(crop_role, slide_type, crop_path))
            continue
        layout_id = str(layout.get("layout_id"))
        rendered_path = rendered_by_layout.get(layout_id) or Path(render_dir) / f"slide-{_layout_slide_number(preview_manifest, layout_id):03d}.png"
        comparisons.append(
            _compare_crop_to_render(
                crop_role,
                slide_type,
                crop_path,
                layout,
                rendered_path,
                preview_rendering_path=preview_rendering_path,
            )
        )

    family_summary = _family_summary(comparisons)
    recommendations = _deck_recommendations(comparisons, unmapped_crops)
    limitation_summary = _limitation_summary(comparisons)
    severe_count = sum(1 for item in comparisons for warning in item.get("warnings", []) if warning.get("severity") == "severe")
    warning_count = sum(1 for item in comparisons for warning in item.get("warnings", []) if warning.get("severity") == "warning")
    return {
        "schema_name": "template_crop_render_diff_report",
        "schema_version": "1.0",
        "crop_manifest_path": _display_path(Path(crop_manifest_path)),
        "template_spec_path": _display_path(Path(template_spec_path)),
        "template_preview_pptx_path": _display_path(Path(template_preview_pptx_path)),
        "template_preview_manifest_path": _display_path(Path(template_preview_manifest_path)),
        "render_dir": _display_path(Path(render_dir)),
        "render_status": render_report.get("render_status"),
        "render_backend": render_report.get("backend"),
        "preview_rendering_path": preview_rendering_path,
        "layout_crop_comparison_count": len(comparisons),
        "unmapped_component_crop_count": len(unmapped_crops),
        "status": "issues_reported" if severe_count or warning_count else "passed",
        "findings_summary": {
            "severe": severe_count,
            "warning": warning_count,
            "total": severe_count + warning_count,
        },
        "best_matching_layout_families": family_summary["best"],
        "least_matching_layout_families": family_summary["least"],
        "limitation_summary": limitation_summary,
        "layout_comparisons": comparisons,
        "component_reference_crops": unmapped_crops,
        "recommendations": recommendations,
    }


def _compare_crop_to_render(
    crop_role: str,
    slide_type: str,
    crop_path: Path,
    layout: dict[str, Any],
    rendered_path: Path,
    *,
    preview_rendering_path: str,
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    if not crop_path.exists():
        return _comparison_shell(crop_role, slide_type, crop_path, layout, rendered_path, None, [_warning("CROP_MISSING", "Design board crop is missing.", "severe")])
    if not rendered_path.exists():
        return _comparison_shell(crop_role, slide_type, crop_path, layout, rendered_path, None, [_warning("RENDERED_TEMPLATE_MISSING", "Rendered template preview is missing.", "severe")])

    crop_metrics = _image_metrics(crop_path)
    render_metrics = _image_metrics(rendered_path)
    metrics = _comparison_metrics(crop_metrics, render_metrics)
    warnings.extend(_metric_warnings(crop_role, slide_type, layout, metrics, preview_rendering_path))
    score = _match_score(metrics)
    recommendations = _recommendations_for_comparison(slide_type, layout, metrics, warnings)
    return _comparison_shell(crop_role, slide_type, crop_path, layout, rendered_path, metrics, warnings, score, recommendations)


def _comparison_shell(
    crop_role: str,
    slide_type: str,
    crop_path: Path,
    layout: dict[str, Any],
    rendered_path: Path,
    metrics: dict[str, Any] | None,
    warnings: list[dict[str, Any]],
    score: float = 0.0,
    recommendations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "crop_role": crop_role,
        "crop_path": _display_path(crop_path),
        "slide_type": slide_type,
        "layout_id": layout.get("layout_id"),
        "layout_family_id": layout.get("layout_family_id"),
        "archetype_id": layout.get("archetype_id"),
        "rendered_template_path": _display_path(rendered_path),
        "similarity_score": round(score, 6),
        "metrics": metrics,
        "warnings": warnings,
        "recommendations": recommendations or [],
    }


def _missing_layout_comparison(crop_role: str, slide_type: str, crop_path: Path) -> dict[str, Any]:
    return {
        "crop_role": crop_role,
        "crop_path": _display_path(crop_path),
        "slide_type": slide_type,
        "layout_id": None,
        "layout_family_id": None,
        "archetype_id": None,
        "rendered_template_path": None,
        "similarity_score": 0.0,
        "metrics": None,
        "warnings": [_warning("LAYOUT_MAPPING_MISSING", "No editable template layout maps to this crop role.", "severe")],
        "recommendations": [{"category": "layout_geometry", "message": f"Add a board-derived layout for `{slide_type}`."}],
    }


def _component_crop_record(crop_role: str, crop_path: Path) -> dict[str, Any]:
    metrics = _image_metrics(crop_path) if crop_path.exists() else None
    return {
        "crop_role": crop_role,
        "crop_path": _display_path(crop_path),
        "mapped_to_rendered_layout": False,
        "purpose": "component/style reference, not a single slide layout",
        "metrics": _metrics_without_image(metrics) if metrics else None,
        "recommendations": _component_crop_recommendations(crop_role),
    }


def _comparison_metrics(crop: dict[str, Any], rendered: dict[str, Any]) -> dict[str, Any]:
    return {
        "palette_similarity": round(1.0 - _palette_distance(crop["mean_rgb"], rendered["mean_rgb"]), 6),
        "dominant_palette_similarity": round(1.0 - _palette_distance(crop["dominant_rgb"], rendered["dominant_rgb"]), 6),
        "dark_area_delta": round(rendered["dark_area_ratio"] - crop["dark_area_ratio"], 6),
        "light_area_delta": round(rendered["light_area_ratio"] - crop["light_area_ratio"], 6),
        "blank_area_delta": round(rendered["blank_area_ratio"] - crop["blank_area_ratio"], 6),
        "edge_density_delta": round(rendered["edge_density"] - crop["edge_density"], 6),
        "footer_occupancy_delta": round(rendered["regions"]["footer"]["occupancy"] - crop["regions"]["footer"]["occupancy"], 6),
        "title_zone_occupancy_delta": round(rendered["regions"]["title"]["occupancy"] - crop["regions"]["title"]["occupancy"], 6),
        "card_region_density_delta": round(rendered["regions"]["content"]["occupancy"] - crop["regions"]["content"]["occupancy"], 6),
        "ornament_density_delta": round(rendered["edge_density"] - crop["edge_density"], 6),
        "diagonal_panel_presence_delta": round(rendered["diagonal_edge_density"] - crop["diagonal_edge_density"], 6),
        "section_number_index_rail_presence_delta": round(
            rendered["regions"]["left_rail"]["occupancy"] - crop["regions"]["left_rail"]["occupancy"],
            6,
        ),
        "chart_table_module_presence_delta": round(rendered["regions"]["data_module"]["occupancy"] - crop["regions"]["data_module"]["occupancy"], 6),
        "crop_metrics": _metrics_without_image(crop),
        "rendered_metrics": _metrics_without_image(rendered),
    }


def _metric_warnings(
    crop_role: str,
    slide_type: str,
    layout: dict[str, Any],
    metrics: dict[str, Any],
    preview_rendering_path: str,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    mismatch_type = "real_design_mismatch" if preview_rendering_path == "deck_compiler_component_primitives" else "preview_renderer_limitation"
    if metrics["palette_similarity"] < 0.72:
        warnings.append(_warning("PALETTE_MISMATCH", "Rendered template palette diverges from the board crop.", "warning", mismatch_type))
    if metrics["dark_area_delta"] < -0.16 and slide_type in {"creative_cover", "section_divider"}:
        warnings.append(_warning("DARK_HERO_AREA_UNDERREPRESENTED", "Rendered hero/divider has less dark/navy treatment than the board crop.", "warning", mismatch_type))
    if metrics["edge_density_delta"] < -0.045:
        warnings.append(_warning("ORNAMENT_DENSITY_LOW", "Rendered template has lower line/ornament density than the crop.", "warning", mismatch_type))
    if metrics["footer_occupancy_delta"] < -0.05:
        warnings.append(_warning("FOOTER_MICROSYSTEM_WEAK", "Footer/source band is less occupied than the board reference.", "warning", mismatch_type))
    if metrics["section_number_index_rail_presence_delta"] < -0.08 and slide_type in {"visual_table_of_contents", "section_divider"}:
        warnings.append(_warning("INDEX_OR_SECTION_MARKER_WEAK", "Index rail or section marker is weaker than the board crop.", "warning", mismatch_type))
    if metrics["diagonal_panel_presence_delta"] < -0.04 and "photo" in crop_role:
        warnings.append(_warning("DIAGONAL_PHOTO_FRAME_WEAK", "Diagonal/photo-frame edge pattern is weaker than the board crop.", "warning", mismatch_type))
    if metrics["chart_table_module_presence_delta"] < -0.07 and slide_type in {"kpi_donut_chart", "data_table_appendix", "comparison_matrix"}:
        warnings.append(_warning("DATA_MODULE_DENSITY_LOW", "Chart/table/matrix module presence is lower than the board crop.", "warning", mismatch_type))
    if str(layout.get("layout_family_id") or "").strip() == "":
        warnings.append(_warning("LAYOUT_FAMILY_MISSING", "Layout has no layout_family_id for production-plan matching.", "severe", "final_deck_renderer_limitation"))
    return warnings


def _recommendations_for_comparison(
    slide_type: str,
    layout: dict[str, Any],
    metrics: dict[str, Any],
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    codes = {str(warning.get("code")) for warning in warnings}
    recommendations: list[dict[str, Any]] = []
    if "PALETTE_MISMATCH" in codes or "DARK_HERO_AREA_UNDERREPRESENTED" in codes:
        recommendations.append(
            {
                "category": "component_style",
                "message": "Tune layout tone tokens and background panels to preserve board crop navy/cream balance without using raster backgrounds.",
            }
        )
    if "ORNAMENT_DENSITY_LOW" in codes:
        recommendations.append(
            {
                "category": "ornament_density",
                "message": "Increase editable topology/grid/connector ornaments for this layout family.",
            }
        )
    if "FOOTER_MICROSYSTEM_WEAK" in codes:
        recommendations.append(
            {
                "category": "footer_index",
                "message": "Reserve stronger footer/source strip geometry and render source ticks as editable shapes/text.",
            }
        )
    if "INDEX_OR_SECTION_MARKER_WEAK" in codes:
        recommendations.append(
            {
                "category": "footer_index",
                "message": "Promote INDEX rail and section number slots to primary geometry for navigation layouts.",
            }
        )
    if "DATA_MODULE_DENSITY_LOW" in codes:
        recommendations.append(
            {
                "category": "component_style",
                "message": "Wrap editable charts/tables in denser board-derived frames, headers, KPI chips, and citation strips.",
            }
        )
    if metrics["title_zone_occupancy_delta"] < -0.09:
        recommendations.append(
            {
                "category": "layout_geometry",
                "message": "Increase title-zone hierarchy or add editable eyebrow/section label elements.",
            }
        )
    return recommendations


def _deck_recommendations(comparisons: list[dict[str, Any]], component_crops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_category: dict[str, int] = {}
    for comparison in comparisons:
        for recommendation in comparison.get("recommendations") or []:
            category = str(recommendation.get("category") or "general")
            by_category[category] = by_category.get(category, 0) + 1
    return [
        {
            "category": category,
            "affected_layout_count": count,
            "message": _category_message(category),
        }
        for category, count in sorted(by_category.items(), key=lambda item: (-item[1], item[0]))
    ] + [
        {
            "category": "component_reference",
            "affected_layout_count": len(component_crops),
            "message": "Use component/style crop metrics as cross-layout style targets; they are not one-to-one slide previews.",
        }
    ]


def _category_message(category: str) -> str:
    return {
        "layout_geometry": "Adjust slot geometry and visual hierarchy in editable_template_spec.final.json generation.",
        "component_style": "Add richer editable component variants in component_translation_plan and compiler renderers.",
        "ornament_density": "Increase topology/grid/connector ornament density with editable PPT/SVG primitives.",
        "footer_index": "Strengthen INDEX rail, footer, and citation micro-system geometry.",
    }.get(category, "Review this category for spec/compiler adjustments.")


def _component_crop_recommendations(crop_role: str) -> list[dict[str, Any]]:
    if crop_role == "component_library":
        return [{"category": "component_style", "message": "Compare card/chart/table/icon variants against rendered layout components."}]
    if crop_role == "style_tokens":
        return [{"category": "component_style", "message": "Use crop palette/typography/spacing metrics as global token guardrails."}]
    if crop_role == "master_layout_system":
        return [{"category": "layout_geometry", "message": "Use master grid crop to tune safe margins, rails, footer height, and slot bands."}]
    if crop_role == "storytelling_plan":
        return [{"category": "footer_index", "message": "Use storytelling crop to tune section rhythm, navigation markers, and flow connectors."}]
    return []


def _family_summary(comparisons: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[float]] = {}
    for item in comparisons:
        family = str(item.get("layout_family_id") or "unknown")
        grouped.setdefault(family, []).append(float(item.get("similarity_score") or 0.0))
    summary = [
        {
            "layout_family_id": family,
            "comparison_count": len(scores),
            "average_similarity_score": round(sum(scores) / max(1, len(scores)), 6),
        }
        for family, scores in grouped.items()
    ]
    ordered = sorted(summary, key=lambda item: item["average_similarity_score"], reverse=True)
    return {"best": ordered[:5], "least": list(reversed(ordered[-5:]))}


def _limitation_summary(comparisons: list[dict[str, Any]]) -> dict[str, int]:
    result = {
        "real_design_mismatch": 0,
        "preview_renderer_limitation": 0,
        "final_deck_renderer_limitation": 0,
        "unknown": 0,
    }
    for item in comparisons:
        for warning in item.get("warnings") or []:
            mismatch_type = str(warning.get("mismatch_type") or "unknown")
            result[mismatch_type] = result.get(mismatch_type, 0) + 1
    return result


def _image_metrics(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        small = rgb.resize((320, max(1, int(320 * rgb.height / max(1, rgb.width)))))
        stat = ImageStat.Stat(small)
        mean_rgb = tuple(float(v) for v in stat.mean[:3])
        dominant_rgb = _dominant_rgb(small)
        gray = small.convert("L")
        pixels = list(small.getdata())
        total = max(1, len(pixels))
        dark = sum(1 for r, g, b in pixels if (r + g + b) / 3 < 72)
        light = sum(1 for r, g, b in pixels if (r + g + b) / 3 > 230)
        blank = sum(1 for r, g, b in pixels if min(r, g, b) > 232 and max(r, g, b) - min(r, g, b) < 18)
        edge_density = _edge_density(gray)
        return {
            "path": _display_path(path),
            "width_px": rgb.width,
            "height_px": rgb.height,
            "mean_rgb": mean_rgb,
            "dominant_rgb": dominant_rgb,
            "dark_area_ratio": round(dark / total, 6),
            "light_area_ratio": round(light / total, 6),
            "blank_area_ratio": round(blank / total, 6),
            "edge_density": edge_density,
            "diagonal_edge_density": _diagonal_edge_density(gray),
            "regions": {
                "title": _region_occupancy(small, (0.08, 0.03, 0.84, 0.22)),
                "footer": _region_occupancy(small, (0.02, 0.86, 0.96, 0.12)),
                "content": _region_occupancy(small, (0.08, 0.25, 0.84, 0.52)),
                "left_rail": _region_occupancy(small, (0.0, 0.0, 0.14, 1.0)),
                "data_module": _region_occupancy(small, (0.12, 0.28, 0.76, 0.48)),
            },
        }


def _metrics_without_image(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metrics.items()
        if key not in {"image"} and key not in {"mean_rgb", "dominant_rgb"}
    } | {
        "mean_rgb": [round(float(v), 2) for v in metrics["mean_rgb"]],
        "dominant_rgb": [int(v) for v in metrics["dominant_rgb"]],
    }


def _dominant_rgb(image: Image.Image) -> tuple[int, int, int]:
    quantized = image.resize((96, max(1, int(96 * image.height / max(1, image.width))))).quantize(colors=8)
    palette = quantized.getpalette() or []
    counts = sorted(quantized.getcolors() or [], reverse=True)
    for _, index in counts:
        r, g, b = palette[index * 3 : index * 3 + 3]
        if not (r > 242 and g > 242 and b > 242):
            return int(r), int(g), int(b)
    return 255, 255, 255


def _edge_density(gray: Image.Image) -> float:
    width, height = gray.size
    pixels = gray.load()
    hits = 0
    total = 0
    for y in range(0, height - 1, 2):
        for x in range(0, width - 1, 2):
            total += 1
            if abs(int(pixels[x, y]) - int(pixels[x + 1, y])) + abs(int(pixels[x, y]) - int(pixels[x, y + 1])) > 38:
                hits += 1
    return round(hits / max(1, total), 6)


def _diagonal_edge_density(gray: Image.Image) -> float:
    width, height = gray.size
    pixels = gray.load()
    hits = 0
    total = 0
    for x in range(1, width - 1, 2):
        y = int((x / max(1, width - 1)) * (height - 1))
        for offset in (-8, 0, 8):
            yy = min(height - 2, max(1, y + offset))
            total += 1
            if abs(int(pixels[x, yy]) - int(pixels[min(width - 1, x + 1), max(0, yy - 1)])) > 28:
                hits += 1
    return round(hits / max(1, total), 6)


def _region_occupancy(image: Image.Image, box: tuple[float, float, float, float]) -> dict[str, float]:
    width, height = image.size
    x, y, w, h = box
    crop = image.crop((int(x * width), int(y * height), int((x + w) * width), int((y + h) * height))).convert("RGB")
    pixels = list(crop.getdata())
    total = max(1, len(pixels))
    nonblank = sum(1 for r, g, b in pixels if not (min(r, g, b) > 235 and max(r, g, b) - min(r, g, b) < 16))
    dark = sum(1 for r, g, b in pixels if (r + g + b) / 3 < 80)
    return {"occupancy": round(nonblank / total, 6), "dark_ratio": round(dark / total, 6)}


def _match_score(metrics: dict[str, Any]) -> float:
    score = 0.0
    score += max(0.0, min(1.0, metrics["palette_similarity"])) * 0.28
    score += max(0.0, 1.0 - abs(metrics["dark_area_delta"]) * 2.4) * 0.16
    score += max(0.0, 1.0 - abs(metrics["edge_density_delta"]) * 7.5) * 0.16
    score += max(0.0, 1.0 - abs(metrics["footer_occupancy_delta"]) * 2.5) * 0.12
    score += max(0.0, 1.0 - abs(metrics["title_zone_occupancy_delta"]) * 2.2) * 0.10
    score += max(0.0, 1.0 - abs(metrics["card_region_density_delta"]) * 1.8) * 0.10
    score += max(0.0, 1.0 - abs(metrics["diagonal_panel_presence_delta"]) * 4.0) * 0.08
    return score


def _palette_distance(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return round(math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second))) / 441.67295593, 6)


def _layouts_by_archetype(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for layout in spec.get("layouts") or []:
        if not isinstance(layout, dict):
            continue
        archetype = str(layout.get("archetype_id") or "")
        result.setdefault(archetype, layout)
    return result


def _rendered_paths_by_layout(preview_manifest: dict[str, Any], render_report: dict[str, Any], render_dir: Path) -> dict[str, Path]:
    slide_path_by_number: dict[int, Path] = {}
    for record in render_report.get("slides") or []:
        if isinstance(record, dict) and record.get("rendered_image_path"):
            slide_path_by_number[int(record.get("slide_index") or len(slide_path_by_number) + 1)] = Path(str(record["rendered_image_path"]))
    output_paths = render_report.get("output_paths") or []
    for index, path in enumerate(output_paths, start=1):
        slide_path_by_number.setdefault(index, Path(str(path)))

    result: dict[str, Path] = {}
    for record in preview_manifest.get("compiled_layouts") or []:
        if not isinstance(record, dict):
            continue
        layout_id = str(record.get("layout_id") or "")
        slide_number = int(record.get("slide_number") or 0)
        result[layout_id] = slide_path_by_number.get(slide_number, render_dir / f"slide-{slide_number:03d}.png")
    return result


def _layout_slide_number(preview_manifest: dict[str, Any], layout_id: str) -> int:
    for record in preview_manifest.get("compiled_layouts") or []:
        if isinstance(record, dict) and str(record.get("layout_id") or "") == layout_id:
            return int(record.get("slide_number") or 0)
    return 0


def _write_contact_sheet(report: dict[str, Any], output_path: str | Path) -> None:
    comparisons = [item for item in report.get("layout_comparisons") or [] if item.get("crop_path") and item.get("rendered_template_path")]
    cell_w, cell_h = 330, 220
    label_h = 42
    pair_w = cell_w * 2 + 30
    rows = max(1, len(comparisons))
    width = pair_w
    height = 70 + rows * (cell_h + label_h + 18)
    sheet = Image.new("RGB", (width, height), "#F4F7FA")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), "Template crop vs rendered editable template preview", fill="#0F172A", font=font)
    y = 58
    for item in comparisons:
        crop_path = Path(str(item["crop_path"]))
        rendered_path = Path(str(item["rendered_template_path"]))
        _paste_thumb(sheet, crop_path, 18, y + label_h, cell_w, cell_h)
        _paste_thumb(sheet, rendered_path, 18 + cell_w + 30, y + label_h, cell_w, cell_h)
        label = f"{item['crop_role']} -> {item['layout_id']} | score {item['similarity_score']:.3f}"
        draw.text((18, y), label[:140], fill="#0F172A", font=font)
        draw.text((18, y + 18), "Board crop", fill="#475569", font=font)
        draw.text((18 + cell_w + 30, y + 18), "Rendered editable template", fill="#475569", font=font)
        y += cell_h + label_h + 18
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste_thumb(sheet: Image.Image, path: Path, x: int, y: int, w: int, h: int) -> None:
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((x - 1, y - 1, x + w + 1, y + h + 1), outline="#CBD5E1")
    if not path.exists():
        draw.text((x + 8, y + 8), f"Missing: {path}", fill="#991B1B")
        return
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((w, h), Image.Resampling.LANCZOS)
        px = x + (w - rgb.width) // 2
        py = y + (h - rgb.height) // 2
        sheet.paste(rgb, (px, py))


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Template Crop Render Diff Report",
        "",
        "This report compares GPT-Image-2 design board crops with rendered editable template preview layouts. It is stricter than generic QA and does not inspect final deck content.",
        "",
        f"Status: `{report['status']}`",
        f"Render status: `{report.get('render_status')}` via `{report.get('render_backend')}`",
        f"Preview rendering path: `{report.get('preview_rendering_path')}`",
        f"Layout comparisons: `{report['layout_crop_comparison_count']}`",
        f"Findings: `{report['findings_summary']['total']}` total, `{report['findings_summary']['severe']}` severe",
        "",
        "## Mismatch Classification",
        "",
        f"- Real design mismatch: `{report.get('limitation_summary', {}).get('real_design_mismatch', 0)}`",
        f"- Preview-renderer limitation: `{report.get('limitation_summary', {}).get('preview_renderer_limitation', 0)}`",
        f"- Final-deck-renderer limitation: `{report.get('limitation_summary', {}).get('final_deck_renderer_limitation', 0)}`",
        "",
        "## Best Matching Layout Families",
        "",
    ]
    for item in report.get("best_matching_layout_families") or []:
        lines.append(f"- `{item['layout_family_id']}`: score `{item['average_similarity_score']}` across `{item['comparison_count']}` comparison(s)")
    lines.extend(["", "## Least Matching Layout Families", ""])
    for item in report.get("least_matching_layout_families") or []:
        lines.append(f"- `{item['layout_family_id']}`: score `{item['average_similarity_score']}` across `{item['comparison_count']}` comparison(s)")
    lines.extend(
        [
            "",
            "## Layout Comparisons",
            "",
            "| Crop | Layout | Family | Score | Palette | Dark delta | Edge delta | Footer delta | Warnings |",
            "|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in report.get("layout_comparisons") or []:
        metrics = item.get("metrics") or {}
        warnings = ", ".join(str(w.get("code")) for w in item.get("warnings") or []) or "none"
        lines.append(
            f"| `{item['crop_role']}` | `{item.get('layout_id')}` | `{item.get('layout_family_id')}` | "
            f"{item.get('similarity_score', 0):.3f} | {_metric(metrics.get('palette_similarity'))} | "
            f"{_metric(metrics.get('dark_area_delta'))} | {_metric(metrics.get('edge_density_delta'))} | "
            f"{_metric(metrics.get('footer_occupancy_delta'))} | {warnings} |"
        )
    lines.extend(["", "## Recommendations", ""])
    for recommendation in report.get("recommendations") or []:
        lines.append(f"- `{recommendation['category']}` ({recommendation['affected_layout_count']}): {recommendation['message']}")
    lines.extend(["", "## Component Reference Crops", ""])
    for crop in report.get("component_reference_crops") or []:
        lines.append(f"- `{crop['crop_role']}`: {crop['purpose']}")
    return "\n".join(lines) + "\n"


def _metric(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _warning(code: str, message: str, severity: str = "warning", mismatch_type: str = "unknown") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message, "mismatch_type": mismatch_type}


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare design-board crops against rendered editable template preview layouts.")
    parser.add_argument("--crop-manifest", type=Path, default=DEFAULT_CROP_MANIFEST)
    parser.add_argument("--template-spec", type=Path, default=DEFAULT_TEMPLATE_SPEC)
    parser.add_argument("--pptx", type=Path, default=DEFAULT_TEMPLATE_PREVIEW)
    parser.add_argument("--preview-manifest", type=Path, default=DEFAULT_TEMPLATE_PREVIEW_MANIFEST)
    parser.add_argument("--render-dir", type=Path, default=DEFAULT_RENDER_DIR)
    parser.add_argument("--render-manifest", type=Path, default=DEFAULT_RENDER_MANIFEST)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--md-report", type=Path, default=DEFAULT_MD_REPORT)
    parser.add_argument("--contact-sheet", type=Path, default=DEFAULT_CONTACT_SHEET)
    parser.add_argument("--renderer", choices=("auto", "powerpoint_com", "libreoffice", "none"), default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = build_template_crop_render_diff_from_files(
            crop_manifest_path=args.crop_manifest,
            template_spec_path=args.template_spec,
            template_preview_pptx_path=args.pptx,
            template_preview_manifest_path=args.preview_manifest,
            render_dir=args.render_dir,
            render_manifest_path=args.render_manifest,
            json_report_path=args.json_report,
            md_report_path=args.md_report,
            contact_sheet_path=args.contact_sheet,
            renderer=args.renderer,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"TEMPLATE_CROP_RENDER_DIFF_FAILED {exc}")
        return 1
    report = _load_json(output)
    print(f"WROTE {output}")
    print(f"TEMPLATE_CROP_RENDER_DIFF {report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
