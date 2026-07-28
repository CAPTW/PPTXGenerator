"""Build a deterministic editable template specification MVP."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ..generator_contracts import validateEditableTemplateSpec
from .template_archetypes import load_template_archetype_registry


DEFAULT_DESIGN_BRIEF = Path("outputs/design_brief.json")
DEFAULT_TEMPLATE_IMAGE_MANIFEST = Path("outputs/template_images/template_image_manifest.json")
DEFAULT_OUTPUT = Path("outputs/editable_template_spec.json")
CANVAS = {"width": 13.333, "height": 7.5, "unit": "in", "ratio": "16:9"}
REQUIRED_COMPONENT_IDS = [
    "footer_standard",
    "title_block",
    "card",
    "kpi_card",
    "chart_frame",
    "table_frame",
    "image_frame",
    "diagonal_photo_panel",
    "section_marker",
    "background_grid",
]
CORE_TEMPLATE_PACK_ARCHETYPES = [
    "cover_hero",
    "section_divider",
    "standard_content",
    "card_grid",
    "comparison_matrix",
    "data_dashboard",
    "table_heavy",
    "closing",
]


def build_editable_template_spec(
    design_brief: dict[str, Any],
    template_image_manifest: dict[str, Any],
) -> dict[str, Any]:
    registry = {item["id"]: item for item in load_template_archetype_registry()}
    selected_ids = _selected_archetype_ids(template_image_manifest, registry)
    selected_ids = _ensure_acceptance_coverage(selected_ids, registry)
    reference_images = _reference_images_by_archetype(template_image_manifest)

    layouts = [_layout_for_archetype(registry[archetype_id], reference_images.get(archetype_id)) for archetype_id in selected_ids]
    slot_definitions = _slot_definitions(layouts)
    spec = {
        "schema_name": "editable_template_spec",
        "schema_version": "1.0",
        "design_id": _design_id(design_brief, selected_ids),
        "canvas": dict(CANVAS),
        "tokens": _tokens(design_brief),
        "components": _components(),
        "layouts": layouts,
        "slot_definitions": slot_definitions,
        "primitives": _primitives(layouts),
        "asset_policy": _asset_policy(),
        "render_policy": {
            "editable_text": True,
            "editable_tables": True,
            "editable_charts": True,
            "editable_titles": True,
        },
    }
    validateEditableTemplateSpec(spec)
    return spec


def build_editable_template_spec_from_files(
    *,
    design_brief_path: str | Path = DEFAULT_DESIGN_BRIEF,
    template_image_manifest_path: str | Path = DEFAULT_TEMPLATE_IMAGE_MANIFEST,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    design_brief = _load_json(design_brief_path)
    template_image_manifest = _load_json(template_image_manifest_path)
    spec = build_editable_template_spec(design_brief, template_image_manifest)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build outputs/editable_template_spec.json from design brief and template reference images."
    )
    parser.add_argument("--design-brief", type=Path, default=DEFAULT_DESIGN_BRIEF)
    parser.add_argument("--template-image-manifest", type=Path, default=DEFAULT_TEMPLATE_IMAGE_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = build_editable_template_spec_from_files(
            design_brief_path=args.design_brief,
            template_image_manifest_path=args.template_image_manifest,
            output_path=args.output,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"BUILD_EDITABLE_TEMPLATE_SPEC_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _selected_archetype_ids(template_image_manifest: dict[str, Any], registry: dict[str, dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for record in template_image_manifest.get("images") or []:
        if not isinstance(record, dict):
            continue
        archetype_id = str(record.get("archetype_id") or "").strip()
        if archetype_id in registry and archetype_id not in ids:
            ids.append(archetype_id)
    if not ids:
        ids.append("standard_content")
    return ids


def _ensure_acceptance_coverage(selected_ids: list[str], registry: dict[str, dict[str, Any]]) -> list[str]:
    result = list(selected_ids)
    for archetype_id in CORE_TEMPLATE_PACK_ARCHETYPES:
        result.append(archetype_id)
    return _dedupe([item for item in result if item in registry])


def _reference_images_by_archetype(template_image_manifest: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for record in template_image_manifest.get("images") or []:
        if isinstance(record, dict) and record.get("archetype_id") and record.get("image_output_path"):
            result[str(record["archetype_id"])] = str(record["image_output_path"])
    return result


def _layout_for_archetype(archetype: dict[str, Any], reference_image_path: str | None) -> dict[str, Any]:
    archetype_id = archetype["id"]
    layout = {
        "layout_id": f"layout-{archetype_id.replace('_', '-')}-mvp",
        "archetype_id": archetype_id,
        "slide_type": archetype_id,
        "density": _density(archetype),
        "slots": _slots_for_archetype(archetype_id),
    }
    if reference_image_path:
        layout["reference_image_path"] = reference_image_path
    if not any(slot["slot_id"] == "title" for slot in layout["slots"]):
        layout["explicitly_omits_title"] = True
    if not any(slot["slot_id"] == "footer" for slot in layout["slots"]):
        layout["explicitly_omits_footer"] = True
    return layout


def _slots_for_archetype(archetype_id: str) -> list[dict[str, Any]]:
    title = _slot("title", "text", True, "title_block", 0.6, 0.42, 8.6, 0.72)
    footer = _slot("footer", "text", False, "footer_standard", 0.6, 6.88, 12.1, 0.28)
    if archetype_id == "cover_hero":
        return [
            title,
            _slot("subtitle", "text", False, "title_block", 0.6, 1.25, 5.9, 0.55),
            _slot("hero_image", "image", False, "diagonal_photo_panel", 7.15, 0.42, 5.58, 5.82),
            _slot("section_marker", "shape", False, "section_marker", 0.6, 6.28, 2.4, 0.32),
            footer,
        ]
    if archetype_id == "section_divider":
        return [
            _slot("section_marker", "shape", True, "section_marker", 0.6, 1.15, 1.6, 0.24),
            _slot("title", "text", True, "title_block", 0.6, 2.25, 8.5, 0.9),
            _slot("progress_marker", "shape", False, "section_marker", 0.6, 4.15, 5.2, 0.32),
            footer,
        ]
    if archetype_id == "agenda_roadmap":
        return [
            title,
            _slot("roadmap_items", "content", True, "card", 0.8, 1.45, 11.75, 4.85),
            footer,
        ]
    if archetype_id == "two_column_analysis":
        return [
            title,
            _slot("left_column", "content", True, "card", 0.6, 1.45, 5.8, 4.95),
            _slot("right_column", "content", True, "card", 6.95, 1.45, 5.78, 4.95),
            footer,
        ]
    if archetype_id == "card_grid":
        return [
            title,
            _slot("cards", "content", True, "card", 0.6, 1.35, 12.1, 5.05),
            footer,
        ]
    if archetype_id == "process_timeline":
        return [
            title,
            _slot("timeline_steps", "content", True, "card", 0.75, 2.0, 11.85, 2.85),
            _slot("phase_labels", "text", False, "section_marker", 0.75, 5.12, 11.85, 0.75),
            footer,
        ]
    if archetype_id == "comparison_matrix":
        return [
            title,
            _slot("matrix", "table", True, "table_frame", 0.6, 1.35, 12.1, 5.15),
            footer,
        ]
    if archetype_id == "data_dashboard":
        return [
            title,
            _slot("metric_panels", "content", True, "kpi_card", 0.6, 1.32, 4.1, 2.2),
            _slot("primary_chart", "chart", False, "chart_frame", 5.02, 1.32, 7.68, 3.05),
            _slot("secondary_chart", "chart", False, "chart_frame", 0.6, 4.75, 12.1, 1.7),
            footer,
        ]
    if archetype_id == "table_heavy":
        return [
            title,
            _slot("summary_callout", "text", False, "card", 0.6, 1.26, 12.1, 0.72),
            _slot("table", "table", True, "table_frame", 0.6, 2.16, 12.1, 4.32),
            footer,
        ]
    if archetype_id == "case_study":
        return [
            title,
            _slot("photo_frame", "image", False, "image_frame", 0.65, 1.36, 4.55, 4.85),
            _slot("case_context", "content", True, "card", 5.55, 1.36, 3.25, 4.85),
            _slot("case_evidence", "content", True, "card", 9.1, 1.36, 3.55, 4.85),
            footer,
        ]
    if archetype_id == "closing":
        return [
            title,
            _slot("takeaway", "text", True, "card", 1.05, 1.55, 11.15, 2.15),
            _slot("next_steps", "content", False, "card", 1.05, 4.15, 11.15, 1.95),
            footer,
        ]
    return [
        title,
        _slot("body", "content", True, "card", 0.6, 1.35, 8.1, 5.05),
        _slot("supporting_panel", "content", False, "card", 9.05, 1.35, 3.65, 5.05),
        footer,
    ]


def _slot(slot_id: str, slot_type: str, required: bool, component_id: str, x: float, y: float, w: float, h: float) -> dict[str, Any]:
    return {
        "slot_id": slot_id,
        "slot_type": slot_type,
        "required": required,
        "component_id": component_id,
        "bounds": {"x": x, "y": y, "w": w, "h": h},
    }


def _tokens(design_brief: dict[str, Any]) -> dict[str, Any]:
    keywords = " ".join(str(item).lower() for item in design_brief.get("visual_keywords") or [])
    accent = "#2563EB"
    secondary = "#0F766E"
    if "creative" in keywords:
        accent = "#7C3AED"
        secondary = "#0F766E"
    return {
        "colors": {
            "background": "#F8FAFC",
            "surface": "#FFFFFF",
            "surface_alt": "#EEF2F7",
            "text": "#111827",
            "muted_text": "#475569",
            "accent": accent,
            "accent_secondary": secondary,
            "line": "#CBD5E1",
            "grid": "#E2E8F0",
            "shadow": "#0F172A",
        },
        "typography": {
            "title": {"font_family": "Aptos Display", "size_pt": 30, "weight": "bold"},
            "subtitle": {"font_family": "Aptos", "size_pt": 17, "weight": "regular"},
            "body": {"font_family": "Aptos", "size_pt": 13, "weight": "regular"},
            "label": {"font_family": "Aptos", "size_pt": 9, "weight": "semibold"},
            "footer": {"font_family": "Aptos", "size_pt": 7.5, "weight": "regular"},
            "kpi": {"font_family": "Aptos Display", "size_pt": 24, "weight": "bold"},
        },
        "spacing": {"xs": 0.08, "sm": 0.14, "md": 0.24, "lg": 0.42, "xl": 0.68},
        "radius": {"none": 0, "sm": 0.08, "md": 0.14, "lg": 0.22},
        "line_weights": {"hairline": 0.5, "standard": 1.0, "emphasis": 2.0},
        "shadows": {
            "none": {"enabled": False},
            "card": {"enabled": True, "color": "#0F172A", "opacity": 0.12, "blur": 0.14, "offset_y": 0.04},
        },
    }


def _components() -> list[dict[str, Any]]:
    return [
        {
            "component_id": "footer_standard",
            "type": "footer",
            "editable": True,
            "default_tokens": {
                "typography": "footer",
                "style_variants": {
                    "dense_footer": {"rule": "double", "density": "compact", "text_color_token": "muted_text"},
                },
            },
        },
        {"component_id": "title_block", "type": "text", "editable": True, "default_tokens": {"typography": "title"}},
        {
            "component_id": "card",
            "type": "shape_group",
            "editable": True,
            "default_tokens": {
                "fill": "surface",
                "radius": "md",
                "style_variants": {
                    "premium_card": {"border": "visible", "border_weight": 0.8, "padding": 0.18, "radius": 0.16},
                },
            },
        },
        {
            "component_id": "kpi_card",
            "type": "shape_group",
            "editable": True,
            "default_tokens": {
                "typography": "kpi",
                "style_variants": {
                    "kpi_card_compact": {"border": "visible", "padding": 0.14, "density": "compact"},
                },
            },
        },
        {"component_id": "chart_frame", "type": "chart_frame", "editable": True, "default_tokens": {"line": "standard"}},
        {
            "component_id": "table_frame",
            "type": "table_frame",
            "editable": True,
            "default_tokens": {
                "line": "standard",
                "style_variants": {
                    "thin_grid_table": {"line_weight": 0.5, "density": "compact", "border": "visible"},
                },
            },
        },
        {"component_id": "image_frame", "type": "image_frame", "editable": True, "default_tokens": {"radius": "md"}},
        {
            "component_id": "diagonal_photo_panel",
            "type": "image_frame",
            "editable": True,
            "default_tokens": {
                "mask": "diagonal",
                "style_variants": {
                    "diagonal_image_frame": {"style": "diagonal", "border": "visible", "padding": 0.12},
                },
            },
        },
        {
            "component_id": "section_marker",
            "type": "shape",
            "editable": True,
            "default_tokens": {
                "fill": "accent",
                "style_variants": {
                    "navy_section_band": {"color_token": "text", "style": "band"},
                },
            },
        },
        {
            "component_id": "background_grid",
            "type": "shape",
            "editable": True,
            "default_tokens": {
                "line": "hairline",
                "style_variants": {
                    "subtle_background_grid": {"color_token": "grid", "density": "subtle", "line_weight": 0.5},
                },
            },
        },
    ]


def _slot_definitions(layouts: list[dict[str, Any]]) -> dict[str, Any]:
    definitions: dict[str, Any] = {}
    for layout in layouts:
        for slot in layout["slots"]:
            key = f"{layout['layout_id']}.{slot['slot_id']}"
            definitions[key] = {
                "slot_type": slot["slot_type"],
                "required": slot["required"],
                "bounds": slot["bounds"],
            }
    return definitions


def _primitives(layouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    primitives: list[dict[str, Any]] = []
    for layout in layouts:
        for slot in layout["slots"]:
            kind = _primitive_kind(slot["slot_type"])
            key = (slot["component_id"], kind)
            if key in seen:
                continue
            seen.add(key)
            primitives.append(
                {
                    "primitive_id": f"primitive-{slot['component_id']}-{kind}",
                    "kind": kind,
                    "editable": True,
                    "bounds": slot["bounds"],
                }
            )
    return primitives


def _primitive_kind(slot_type: str) -> str:
    return {
        "text": "text_box",
        "content": "shape",
        "shape": "shape",
        "table": "table",
        "chart": "chart",
        "image": "image_frame",
    }.get(slot_type, "shape")


def _asset_policy() -> dict[str, Any]:
    return {
        "allow_full_slide_raster": False,
        "image_usage": "Images may appear only inside explicit image_frame or photo/crop frame slots.",
        "text_editable": True,
        "tables_editable": True,
        "charts_editable": True,
        "icons": "SVG",
        "ornaments": "SVG or PPT lines",
        "photos": "Only inside image frames",
        "no_full_slide_raster_background": True,
    }


def _density(archetype: dict[str, Any]) -> str:
    density_range = archetype.get("density_range") or []
    return "high" if "high" in density_range else str(density_range[-1] if density_range else "medium")


def _design_id(design_brief: dict[str, Any], selected_ids: list[str]) -> str:
    seed = json.dumps(
        {"topic": design_brief.get("topic"), "tone": design_brief.get("tone"), "archetypes": selected_ids},
        sort_keys=True,
        ensure_ascii=True,
    )
    return f"editable-template-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
