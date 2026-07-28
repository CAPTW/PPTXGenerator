"""Adapt the neutral template-reference contract to the canonical compiler spec.

The Creative Front-End compatibility contract is a compact reference-extraction
shape.  The compiler consumes the richer canonical
``schemas/editable_template_spec.schema.json`` contract.  This module is the
single compatibility boundary between those two shapes.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
from pathlib import Path
from typing import Any

from ..generator_contracts import validateEditableTemplateSpec


TEMPLATE_REFERENCE_CONTRACT_ID = "creative-frontend-template-reference-v1"


REQUIRED_SLOTS_BY_ARCHETYPE: dict[str, set[str]] = {
    "cover_hero": {"title", "subtitle", "footer"},
    "standard_content": {"title", "body", "footer"},
    "data_dashboard": {"title", "primary_chart", "metric_panels", "footer"},
    "table_heavy": {"title", "table", "footer"},
    "section_divider": {"title", "footer"},
    "agenda_roadmap": {"title", "body", "footer"},
    "two_column_analysis": {"title", "body", "footer"},
    "card_grid": {"title", "cards", "footer"},
    "process_timeline": {"title", "process_visual", "footer"},
    "comparison_matrix": {"title", "table", "footer"},
    "case_study": {"title", "body", "footer"},
    "closing": {"title", "footer"},
}

_CONTENT_SLOT_TYPES = {"text", "image", "chart", "table", "kpi", "card_group", "callout", "footer", "icon"}
_RASTER_BACKGROUND_TYPES = {"raster", "raster_background", "image", "image_background", "photo", "bitmap"}
_RASTER_CAPABLE_SLOT_TYPES = {"image"}
_RASTER_CAPABLE_COMPONENT_TYPES = {"image_frame"}
_FULL_SLIDE_RASTER_AREA_RATIO = 0.88
_CONTENT_COMPONENT_TYPES = {"text_box", "image_frame", "chart_frame", "table_frame", "footer_component"}
_PRIMITIVE_KIND = {
    "text": "text_box",
    "footer": "text_box",
    "kpi": "shape",
    "card_group": "shape",
    "callout": "shape",
    "decorative": "shape",
    "image": "image_frame",
    "chart": "chart",
    "table": "table",
    "icon": "svg_icon",
}


def adapt_image_template_spec(
    template_reference_spec: dict[str, Any],
    design_system: dict[str, Any],
) -> dict[str, Any]:
    """Return a compiler-ready editable template spec.

    The adapter rejects full-slide raster backgrounds and non-editable required
    content before it translates fields.  It never imports placeholder text from
    the reference image; only semantic slot roles and editable geometry cross the
    boundary.
    """

    _validate_template_reference_inputs(template_reference_spec, design_system)
    canvas = template_reference_spec["canvas"]
    canonical_components: dict[str, dict[str, Any]] = {}
    canonical_layouts: list[dict[str, Any]] = []
    slot_definitions: dict[str, dict[str, Any]] = {}
    primitives: list[dict[str, Any]] = []
    family_layouts: dict[str, list[str]] = {}
    family_slots: dict[str, set[str]] = {}

    for layout in template_reference_spec["layouts"]:
        layout_id = str(layout["layout_id"])
        archetype = _normalize_key(layout["archetype"])
        component_contexts = list(_walk_components_with_context(layout.get("components") or []))
        component_by_slot = {
            str(component.get("slot_ref")): component
            for component, _parent_id, _effective_slot_ref in component_contexts
            if component.get("slot_ref")
        }
        used_slot_ids: set[str] = set()
        source_to_canonical_slot: dict[str, str] = {}
        slots: list[dict[str, Any]] = []
        component_bindings: dict[str, str] = {}
        required_roles = REQUIRED_SLOTS_BY_ARCHETYPE.get(archetype, {"title", "footer"})

        for source_slot in layout.get("slots") or []:
            slot_id = _unique_slot_id(_canonical_slot_id(source_slot), used_slot_ids)
            used_slot_ids.add(slot_id)
            source_to_canonical_slot[str(source_slot.get("slot_id"))] = slot_id
            slot_type = _canonical_slot_type(source_slot)
            role = _canonical_role(source_slot)
            required = role in required_roles or slot_id in required_roles
            source_component = component_by_slot.get(str(source_slot.get("slot_id")))
            component_id = _component_id(layout_id, slot_id, source_component)
            component_type = str((source_component or {}).get("type") or _default_component_type(slot_type))
            component_editable = bool((source_component or source_slot).get("editable", True))
            if required and not component_editable:
                raise ValueError(f"{layout_id}.{slot_id}: required content component must be editable")

            canonical_components.setdefault(
                component_id,
                {
                    "component_id": component_id,
                    "type": component_type,
                    "editable": component_editable,
                    "default_tokens": {
                        "style_ref": str(source_slot.get("style_ref") or ""),
                        "role": role,
                        "confidence": float(source_slot.get("confidence", 1.0)),
                        "fallback_behavior": str(source_slot.get("fallback_behavior") or "reflow"),
                    },
                },
            )
            bounds = _bounds(source_slot["bounds"])
            slots.append(
                {
                    "slot_id": slot_id,
                    "slot_type": slot_type,
                    "required": required,
                    "component_id": component_id,
                    "bounds": bounds,
                }
            )
            component_bindings[slot_id] = component_id
            slot_definitions[f"{layout_id}.{slot_id}"] = {
                "slot_type": slot_type,
                "required": required,
                "bounds": bounds,
            }
            if source_component is None:
                primitives.append(
                    {
                        "primitive_id": f"primitive-{_normalize_key(layout_id)}-{slot_id}",
                        "kind": _PRIMITIVE_KIND.get(str(source_slot.get("type")), "shape"),
                        "editable": component_editable,
                        "bounds": bounds,
                    }
                )

        adapted_component_primitives: list[dict[str, Any]] = []
        for z_index, (source_component, parent_id, effective_slot_ref) in enumerate(component_contexts):
            canonical_slot_id = source_to_canonical_slot.get(str(effective_slot_ref or ""))
            component_id = _component_id(layout_id, canonical_slot_id or "decorative", source_component)
            component_type = str(source_component.get("type") or "rect")
            editable = bool(source_component.get("editable", True))
            component_bounds = _bounds(
                source_component.get("bounds") or {},
                allow_zero=_normalize_key(component_type) == "line",
            )
            if _normalize_key(component_type) == "line":
                component_bounds = {
                    **component_bounds,
                    "w": max(0.001, component_bounds["w"]),
                    "h": max(0.001, component_bounds["h"]),
                }
            component_record = canonical_components.setdefault(
                component_id,
                {
                    "component_id": component_id,
                    "type": component_type,
                    "editable": editable,
                    "default_tokens": {},
                },
            )
            component_record["default_tokens"].update(
                {
                    "layout_id": layout_id,
                    "source_component_id": str(source_component.get("component_id") or ""),
                    "source_component_type": component_type,
                    "semantic_slot_id": canonical_slot_id,
                    "parent_component_id": str(parent_id or "") or None,
                    "confidence": float(source_component.get("confidence", 1.0)),
                    "decorative_svg": bool(source_component.get("decorative_svg", False)),
                    "non_raster": bool(source_component.get("non_raster", False)),
                    "metadata": source_component.get("metadata") or {},
                }
            )
            primitive_id = f"primitive-{_normalize_key(layout_id)}-{_normalize_key(source_component.get('component_id'))}"
            primitive = {
                "primitive_id": primitive_id,
                "kind": _primitive_kind_for_component_type(component_type),
                "editable": editable,
                "bounds": component_bounds,
            }
            primitives.append(primitive)
            adapted_component_primitives.append(
                {
                    **primitive,
                    "component_id": component_id,
                    "source_component_id": str(source_component.get("component_id") or ""),
                    "source_component_type": component_type,
                    "semantic_slot_id": canonical_slot_id,
                    "parent_component_id": str(parent_id or "") or None,
                    "z_index": z_index,
                    "render_before_slots": not bool(source_component.get("slot_ref")) or parent_id is not None,
                }
            )

        present_roles = {_canonical_role(slot) for slot in layout.get("slots") or []}
        missing_roles = sorted(required_roles - present_roles - used_slot_ids)
        if missing_roles:
            raise ValueError(f"{layout_id}: missing required semantic slots: {', '.join(missing_roles)}")

        density = _layout_density(layout.get("slots") or [])
        family_id = f"reference-{archetype}"
        family_layouts.setdefault(family_id, []).append(layout_id)
        family_slots.setdefault(family_id, set()).update(used_slot_ids)
        canonical_layouts.append(
            {
                "layout_id": layout_id,
                "archetype_id": archetype,
                "slide_type": archetype,
                "density": density,
                "compatible_slide_types": [archetype],
                "required_slots": sorted(slot["slot_id"] for slot in slots if slot["required"]),
                "optional_slots": sorted(slot["slot_id"] for slot in slots if not slot["required"]),
                "density_range": sorted({_density_to_canonical(str(slot.get("density") or "normal")) for slot in layout.get("slots") or []}),
                "component_bindings": component_bindings,
                "image_policy": "Images are allowed only in replaceable image frames; no full-slide image background.",
                "chart_table_policy": "Charts and tables compile as native PowerPoint objects.",
                "fallback_layout": str(layout.get("fallback_layout") or "standard_content"),
                "layout_geometry_description": "Geometry adapted from a template reference; no placeholder copy was imported.",
                "extraction_geometry_source": TEMPLATE_REFERENCE_CONTRACT_ID,
                "layout_family_id": family_id,
                "source_archetype_ids": [archetype],
                "geometry_strategy": {
                    "contract_id": TEMPLATE_REFERENCE_CONTRACT_ID,
                    "source": TEMPLATE_REFERENCE_CONTRACT_ID,
                    "source_hierarchy": list(layout.get("hierarchy") or []),
                    "adapter_component_primitives": adapted_component_primitives,
                },
                "editable_primitive_mapping": {
                    slot["slot_id"]: _PRIMITIVE_KIND.get(_reference_type_for_slot(slot["slot_id"], layout), "shape")
                    for slot in slots
                },
                "variation_rules": list(layout.get("assumptions") or []),
                "slots": slots,
            }
        )

    canonical = {
        "schema_name": "editable_template_spec",
        "schema_version": "1.0",
        "design_id": str(template_reference_spec["template_id"]),
        "layout_families": [
            {
                "family_id": family_id,
                "name": family_id.replace("reference-", "").replace("_", " ").title(),
                "layout_ids": sorted(layout_ids),
                "required_slots": sorted(family_slots[family_id]),
                "optional_slots": [],
                "components": sorted(family_slots[family_id]),
            }
            for family_id, layout_ids in sorted(family_layouts.items())
        ],
        "production_notes": [
            f"Adapted from {TEMPLATE_REFERENCE_CONTRACT_ID}; references remain design inputs only.",
            "Placeholder labels were treated as semantic roles and were not imported as final copy.",
            f"Source design-system reference: {template_reference_spec['design_system_ref']} ({design_system['design_system_id']}).",
        ],
        "deck_scale_rules": {
            "small": "Rotate across at least 2 layout families when content permits.",
            "medium": "Rotate across at least 3 layout families when content permits.",
            "large": "Rotate across at least 4 layout families with section-aware batching.",
            "very_large": "Rotate across at least 5 layout families with bounded repetition.",
        },
        "canvas": {
            "width": float(canvas["width_in"]),
            "height": float(canvas["height_in"]),
            "unit": "in",
            "ratio": str(canvas["aspect_ratio"]),
        },
        "tokens": _canonical_tokens(design_system),
        "components": list(canonical_components.values()),
        "layouts": canonical_layouts,
        "slot_definitions": slot_definitions,
        "primitives": primitives,
        "asset_policy": {
            "allow_full_slide_raster": False,
            "image_usage": "Only source photos or figures inside explicit replaceable image frames.",
            "text_editable": True,
            "tables_editable": True,
            "charts_editable": True,
            "icons": "SVG",
            "ornaments": "SVG or PowerPoint primitives only",
            "photos": "Only inside image frames",
            "no_full_slide_raster_background": True,
        },
        "render_policy": {
            "editable_text": True,
            "editable_tables": True,
            "editable_charts": True,
            "editable_titles": True,
        },
    }
    validateEditableTemplateSpec(canonical)
    return canonical


def adapt_image_template_spec_from_files(
    *,
    template_spec_path: str | Path,
    design_system_path: str | Path,
    output_path: str | Path,
) -> Path:
    template_spec = _load_json(template_spec_path)
    design_system = _load_json(design_system_path)
    canonical = adapt_image_template_spec(template_spec, design_system)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(canonical, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def _validate_template_reference_inputs(
    template_reference_spec: dict[str, Any],
    design_system: dict[str, Any],
) -> None:
    for key in ("schema_version", "template_id", "design_system_ref", "canvas", "layouts"):
        if key not in template_reference_spec:
            raise ValueError(f"image template spec missing required field: {key}")
    for key in ("schema_version", "design_system_id", "canvas", "colors", "typography", "spacing", "shape_style"):
        if key not in design_system:
            raise ValueError(f"design system missing required field: {key}")
    if not template_reference_spec.get("layouts"):
        raise ValueError("image template spec must contain at least one layout")
    design_system_ref = str(template_reference_spec.get("design_system_ref") or "")
    if re.match(r"^[a-z][a-z0-9+.-]*://", design_system_ref, re.IGNORECASE):
        raise ValueError("design_system_ref must identify a local JSON artifact, not a remote URI")
    if not design_system_ref.lower().endswith(".json"):
        raise ValueError("design_system_ref must identify a JSON artifact")

    template_canvas = template_reference_spec["canvas"]
    system_canvas = design_system["canvas"]
    for dimension in ("width_in", "height_in"):
        if not math.isclose(float(template_canvas[dimension]), float(system_canvas[dimension]), rel_tol=0, abs_tol=1e-3):
            raise ValueError(f"template/design-system canvas mismatch for {dimension}")
    if not math.isclose(_aspect_ratio(template_canvas["aspect_ratio"]), _aspect_ratio(system_canvas["aspect_ratio"]), rel_tol=0, abs_tol=1e-4):
        raise ValueError("template/design-system canvas aspect ratio mismatch")

    for layout in template_reference_spec["layouts"]:
        layout_id = str(layout.get("layout_id") or "unnamed-layout")
        background = layout.get("background") or {}
        background_type = _normalize_key(background.get("type"))
        non_raster = bool(background.get("non_raster")) or background_type in {"solid_fill", "shape", "svg_layer", "vector"}
        if background_type in _RASTER_BACKGROUND_TYPES:
            raise ValueError(f"{layout_id}: full-slide raster background type is forbidden even when marked non_raster")
        if background.get("full_slide") and not non_raster:
            raise ValueError(f"{layout_id}: full-slide raster background is forbidden")
        flat_components = list(_walk_components_with_context(layout.get("components") or []))
        for component, _parent_id, effective_slot_ref in flat_components:
            component_type = _normalize_key(component.get("type"))
            if component_type in {"full_slide_image", "raster_background", "screenshot_background"}:
                raise ValueError(f"{layout_id}: forbidden raster component {component_type}")
            component_bounds = _bounds(
                component.get("bounds") or {},
                allow_zero=component_type == "line",
            )
            _validate_bounds_within_canvas(component_bounds, template_canvas, f"{layout_id}.{component.get('component_id')}")
            if component_type in _RASTER_CAPABLE_COMPONENT_TYPES and _is_full_slide_bounds(component_bounds, template_canvas):
                raise ValueError(f"{layout_id}.{component.get('component_id')}: full-slide raster-capable component is forbidden")
            if component_type in _CONTENT_COMPONENT_TYPES and not effective_slot_ref:
                raise ValueError(f"{layout_id}.{component.get('component_id')}: content-bearing component must bind to a semantic slot")
        for slot in layout.get("slots") or []:
            slot_type = str(slot.get("type") or "")
            if slot_type in _CONTENT_SLOT_TYPES and not bool(slot.get("editable")):
                raise ValueError(f"{layout_id}.{slot.get('slot_id')}: content slot must be editable")
            slot_bounds = _bounds(slot.get("bounds") or {})
            _validate_bounds_within_canvas(slot_bounds, template_canvas, f"{layout_id}.{slot.get('slot_id')}")
            if slot_type in _RASTER_CAPABLE_SLOT_TYPES and _is_full_slide_bounds(slot_bounds, template_canvas):
                raise ValueError(f"{layout_id}.{slot.get('slot_id')}: full-slide raster-capable slot is forbidden")
            referenced = [
                component
                for component, _parent_id, effective_slot_ref in flat_components
                if effective_slot_ref == str(slot.get("slot_id"))
            ]
            if slot_type in _CONTENT_SLOT_TYPES and any(not bool(component.get("editable", True)) for component in referenced):
                raise ValueError(f"{layout_id}.{slot.get('slot_id')}: referenced content components must be editable")


def _canonical_tokens(design_system: dict[str, Any]) -> dict[str, Any]:
    colors = {str(key): _color_to_hex(value) for key, value in (design_system.get("colors") or {}).items()}
    typography = {
        str(key): {
            "font_family": str(value.get("font_family") or "Aptos"),
            "size_pt": float(value.get("size_pt") or 12),
            "weight": value.get("weight", "regular"),
            "line_height": float(value.get("line_height") or 1.2),
            "color": _color_to_hex(value.get("color")),
        }
        for key, value in (design_system.get("typography") or {}).items()
        if isinstance(value, dict)
    }
    spacing = {str(key): float(value) for key, value in (design_system.get("spacing") or {}).items()}
    shape_style = design_system.get("shape_style") or {}
    return {
        "colors": colors,
        "typography": typography,
        "spacing": spacing,
        "radius": {"card": float(shape_style.get("card_radius_in") or 0)},
        "line_weights": {"hairline": float(shape_style.get("hairline_pt") or 0.5)},
        "shadows": {"default": {"style": str(shape_style.get("shadow_style") or "none")}},
    }


def _canonical_slot_id(slot: dict[str, Any]) -> str:
    role = _canonical_role(slot)
    slot_type = str(slot.get("type") or "text")
    if role in {"title", "section_title"}:
        return "title"
    if role == "subtitle":
        return "subtitle"
    if role == "footer":
        return "footer"
    if slot_type == "chart":
        return "primary_chart" if "primary" in role or role == "chart" else _normalize_key(role)
    if slot_type == "table":
        return "table" if "table" in role else _normalize_key(role)
    if slot_type == "kpi":
        return "metric_panels"
    if slot_type == "card_group":
        return "cards"
    if slot_type == "image":
        return "hero_image" if "hero" in role else "photo_frame"
    if slot_type == "callout":
        return "insight"
    if slot_type == "text" and role in {"body", "content"}:
        return "body"
    return _normalize_key(role or slot.get("slot_id") or slot_type)


def _canonical_role(slot: dict[str, Any]) -> str:
    role = _normalize_key(slot.get("role") or slot.get("slot_id") or slot.get("type"))
    if role.endswith("_title") or role in {"headline", "cover_title"}:
        return "title"
    if role.endswith("_subtitle"):
        return "subtitle"
    if "footer" in role:
        return "footer"
    if "primary_chart" in role:
        return "primary_chart"
    if role.endswith("_table") or "table" in role:
        return "table"
    if role in {"kpi_block", "kpi_strip", "kpi"}:
        return "metric_panels"
    if role in {"hero_image", "image"}:
        return role
    return role


def _canonical_slot_type(slot: dict[str, Any]) -> str:
    slot_type = str(slot.get("type") or "text")
    return {
        "card_group": "content",
        "callout": "content",
        "kpi": "content",
        "footer": "footer",
        "decorative": "shape",
        "icon": "icon",
    }.get(slot_type, slot_type)


def _default_component_type(slot_type: str) -> str:
    return {
        "text": "text_box",
        "footer": "footer_component",
        "content": "group",
        "image": "image_frame",
        "chart": "chart_frame",
        "table": "table_frame",
        "icon": "svg_icon",
        "shape": "rect",
    }.get(slot_type, "group")


def _primitive_kind_for_component_type(component_type: str) -> str:
    normalized = _normalize_key(component_type)
    if normalized in {"text_box", "footer_component"}:
        return "text_box"
    if normalized == "image_frame":
        return "image_frame"
    if normalized == "chart_frame":
        return "chart"
    if normalized == "table_frame":
        return "table"
    if normalized in {"svg_icon", "svg_layer"}:
        return "svg_icon"
    return "shape"


def _component_id(layout_id: str, slot_id: str, component: dict[str, Any] | None) -> str:
    raw = str((component or {}).get("component_id") or f"component_{slot_id}")
    return f"{_normalize_key(layout_id)}.{_normalize_key(raw)}"


def _layout_density(slots: list[dict[str, Any]]) -> str:
    levels = [_density_to_canonical(str(slot.get("density") or "normal")) for slot in slots]
    if "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    return "low"


def _density_to_canonical(value: str) -> str:
    return {"sparse": "low", "normal": "medium", "dense": "high", "low": "low", "medium": "medium", "high": "high"}.get(_normalize_key(value), "medium")


def _reference_type_for_slot(canonical_slot_id: str, layout: dict[str, Any]) -> str:
    for source_slot in layout.get("slots") or []:
        if _canonical_slot_id(source_slot) == canonical_slot_id:
            return str(source_slot.get("type") or "")
    return ""


def _unique_slot_id(base: str, used: set[str]) -> str:
    if base not in used:
        return base
    index = 2
    while f"{base}_{index}" in used:
        index += 1
    return f"{base}_{index}"


def _bounds(value: dict[str, Any], *, allow_zero: bool = False) -> dict[str, float]:
    if not all(key in value for key in ("x", "y", "w", "h")):
        raise ValueError("slot bounds require x, y, w, h")
    bounds = {key: float(value[key]) for key in ("x", "y", "w", "h")}
    invalid = (
        bounds["w"] < 0
        or bounds["h"] < 0
        or (allow_zero and bounds["w"] == 0 and bounds["h"] == 0)
        or (not allow_zero and (bounds["w"] == 0 or bounds["h"] == 0))
    )
    if invalid:
        raise ValueError("slot bounds must have positive width and height")
    return bounds


def _walk_components(components: list[dict[str, Any]]):
    for component in components:
        yield component
        children = component.get("children") or []
        if children:
            yield from _walk_components(children)


def _walk_components_with_context(
    components: list[dict[str, Any]],
    *,
    parent_id: str | None = None,
    inherited_slot_ref: str | None = None,
):
    for component in components:
        slot_ref = str(component.get("slot_ref") or inherited_slot_ref or "") or None
        yield component, parent_id, slot_ref
        children = component.get("children") or []
        if children:
            yield from _walk_components_with_context(
                children,
                parent_id=str(component.get("component_id") or parent_id or "") or None,
                inherited_slot_ref=slot_ref,
            )


def _validate_bounds_within_canvas(
    bounds: dict[str, float],
    canvas: dict[str, Any],
    label: str,
) -> None:
    width = float(canvas["width_in"])
    height = float(canvas["height_in"])
    tolerance = 1e-3
    if bounds["x"] < -tolerance or bounds["y"] < -tolerance:
        raise ValueError(f"{label}: bounds must start within the canvas")
    if bounds["x"] + bounds["w"] > width + tolerance or bounds["y"] + bounds["h"] > height + tolerance:
        raise ValueError(f"{label}: bounds exceed the canvas")


def _is_full_slide_bounds(bounds: dict[str, float], canvas: dict[str, Any]) -> bool:
    width = float(canvas["width_in"])
    height = float(canvas["height_in"])
    area_ratio = bounds["w"] * bounds["h"] / max(0.01, width * height)
    return (
        area_ratio >= _FULL_SLIDE_RASTER_AREA_RATIO
        and bounds["x"] <= 0.2
        and bounds["y"] <= 0.2
        and bounds["w"] >= width * 0.9
        and bounds["h"] >= height * 0.9
    )


def _aspect_ratio(value: Any) -> float:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*", str(value or ""))
    if not match or float(match.group(2)) == 0:
        raise ValueError(f"invalid aspect ratio: {value!r}")
    return float(match.group(1)) / float(match.group(2))


def _color_to_hex(value: Any) -> str:
    text = str(value or "").strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", text):
        return text.upper()
    short_hex = re.fullmatch(r"#([0-9a-f])([0-9a-f])([0-9a-f])", text)
    if short_hex:
        return "#" + "".join(channel * 2 for channel in short_hex.groups()).upper()
    rgb = re.fullmatch(r"rgba?\((.+)\)", text)
    if rgb:
        parts = [part.strip() for part in re.split(r"\s*,\s*|\s+", rgb.group(1).replace("/", " ")) if part.strip()]
        if len(parts) not in {3, 4}:
            raise ValueError(f"invalid rgb color token: {value!r}")
        channels = [_css_rgb_channel(part) for part in parts[:3]]
        return _rgb_hex(*channels)
    hsl = re.fullmatch(r"hsla?\((.+)\)", text)
    if hsl:
        parts = [part.strip() for part in re.split(r"\s*,\s*|\s+", hsl.group(1).replace("/", " ")) if part.strip()]
        if len(parts) not in {3, 4}:
            raise ValueError(f"invalid hsl color token: {value!r}")
        hue = float(parts[0].removesuffix("deg")) % 360 / 360
        saturation = _css_percent(parts[1])
        lightness = _css_percent(parts[2])
        red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
        return _rgb_hex(red * 255, green * 255, blue * 255)
    oklch = re.fullmatch(r"oklch\((.+)\)", text)
    if oklch:
        parts = [part.strip() for part in oklch.group(1).replace("/", " ").split() if part.strip()]
        if len(parts) not in {3, 4}:
            raise ValueError(f"invalid oklch color token: {value!r}")
        lightness = _css_percent(parts[0]) if parts[0].endswith("%") else float(parts[0])
        chroma = float(parts[1])
        hue = math.radians(float(parts[2].removesuffix("deg")) % 360)
        return _oklch_to_hex(lightness, chroma, hue)
    named = {
        "black": "#000000",
        "white": "#FFFFFF",
        "red": "#FF0000",
        "green": "#008000",
        "blue": "#0000FF",
        "transparent": "#FFFFFF",
    }
    if text in named:
        return named[text]
    raise ValueError(f"unsupported color token for canonical compiler: {value!r}")


def _css_rgb_channel(value: str) -> float:
    if value.endswith("%"):
        return max(0.0, min(100.0, float(value[:-1]))) * 2.55
    return max(0.0, min(255.0, float(value)))


def _css_percent(value: str) -> float:
    if not value.endswith("%"):
        raise ValueError(f"expected percentage color channel, got {value!r}")
    return max(0.0, min(100.0, float(value[:-1]))) / 100


def _rgb_hex(red: float, green: float, blue: float) -> str:
    return f"#{round(red):02X}{round(green):02X}{round(blue):02X}"


def _oklch_to_hex(lightness: float, chroma: float, hue: float) -> str:
    a = chroma * math.cos(hue)
    b = chroma * math.sin(hue)
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    l_value, m_value, s_value = l_**3, m_**3, s_**3
    linear = (
        4.0767416621 * l_value - 3.3077115913 * m_value + 0.2309699292 * s_value,
        -1.2684380046 * l_value + 2.6097574011 * m_value - 0.3413193965 * s_value,
        -0.0041960863 * l_value - 0.7034186147 * m_value + 1.7076147010 * s_value,
    )
    srgb = [12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055 for channel in linear]
    return _rgb_hex(*(max(0.0, min(1.0, channel)) * 255 for channel in srgb))


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Adapt the neutral Creative Front-End template-reference contract to the canonical editable template spec."
    )
    parser.add_argument("--template-spec", type=Path, required=True)
    parser.add_argument("--design-system", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = adapt_image_template_spec_from_files(
            template_spec_path=args.template_spec,
            design_system_path=args.design_system,
            output_path=args.output,
        )
    except Exception as exc:
        print(f"TEMPLATE_SPEC_ADAPT_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
