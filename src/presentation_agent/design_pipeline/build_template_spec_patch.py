"""Build a safe editable_template_spec patch from extracted design-system observations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ..generator_contracts import (
    validateDesignBrief,
    validateEditableTemplateSpec,
    validateEditableTemplateSpecPatch,
    validateExtractedDesignSystem,
)


DEFAULT_EXTRACTED_DESIGN_SYSTEM = Path("outputs/extracted_design_system.json")
DEFAULT_MERGED_EXTRACTED_DESIGN_SYSTEM = Path("outputs/extracted_design_system.merged.json")
DEFAULT_TEMPLATE_SPEC = Path("outputs/editable_template_spec.json")
DEFAULT_DESIGN_BRIEF = Path("outputs/design_brief.json")
DEFAULT_OUTPUT = Path("outputs/editable_template_spec_patch.json")
ALLOWED_FIELDS = [
    "tokens.colors",
    "tokens.typography",
    "tokens.spacing",
    "components.default_tokens",
    "layouts.density",
    "footer_style",
    "card_style",
    "background_ornament_style",
]
FORBIDDEN_FIELDS = [
    "design_id",
    "canvas",
    "asset_policy",
    "render_policy",
    "layout_id",
    "layout.archetype_id",
    "layout.slide_type",
    "layout.slots",
    "slot_definitions",
    "primitives",
    "components.editable",
    "full_slide_raster",
]
TYPE_SIZE_LIMITS = {
    "title": (24.0, 38.0),
    "body": (10.0, 16.0),
    "footer": (6.5, 9.5),
}
CARD_PADDING_LIMITS = (0.08, 0.4)
MARGIN_LIMITS = (0.35, 0.8)
SAFE_COLOR_ROLES = {
    "background": "background",
    "surface": "surface",
    "primary text": "text",
    "text": "text",
    "muted text": "muted_text",
    "accent": "accent",
    "accent and rules": "accent",
    "line": "line",
}


def build_template_spec_patch(
    extracted_design_system: dict[str, Any],
    editable_template_spec: dict[str, Any],
    design_brief: dict[str, Any],
    *,
    source_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    validateExtractedDesignSystem(extracted_design_system)
    validateEditableTemplateSpec(editable_template_spec)
    validateDesignBrief(design_brief)

    clamp_report: list[dict[str, Any]] = []
    safety_warnings: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    colors = _color_patches(extracted_design_system, editable_template_spec, safety_warnings, ignored)
    typography = _typography_patches(extracted_design_system, editable_template_spec, clamp_report, ignored)
    spacing = _spacing_patches(extracted_design_system, clamp_report)
    component_variants = _component_style_variants(extracted_design_system, editable_template_spec)
    layout_density_hints = _layout_density_hints(extracted_design_system, editable_template_spec, safety_warnings, ignored)
    footer_style = _footer_style(extracted_design_system)
    card_style = _card_style(extracted_design_system, clamp_report)
    background_style = _background_ornament_style(extracted_design_system)

    _contrast_warnings(colors, editable_template_spec, safety_warnings)
    _maximum_density_warning(layout_density_hints, safety_warnings)
    _record_forbidden_field_guards(ignored)

    patch = {
        "schema_name": "editable_template_spec_patch",
        "schema_version": "1.0",
        "patch_id": _patch_id(extracted_design_system, editable_template_spec, design_brief),
        "base_design_id": editable_template_spec["design_id"],
        "source_artifact": _source_artifact(source_paths),
        "patch_policy": {
            "mode": "safe_patch_only",
            "allowed_fields": ALLOWED_FIELDS,
            "forbidden_fields": FORBIDDEN_FIELDS,
        },
        "safe_patches": {
            "tokens": {
                "colors": colors,
                "typography": typography,
                "spacing": spacing,
            },
            "component_style_variants": component_variants,
            "layout_density_hints": layout_density_hints,
            "footer_style_refinements": footer_style,
            "card_style": card_style,
            "background_ornament_style": background_style,
        },
        "clamp_report": clamp_report,
        "safety_warnings": _dedupe_warnings(safety_warnings),
        "ignored_unsafe_attempts": _dedupe_warnings(ignored),
    }
    validateEditableTemplateSpec(editable_template_spec)
    validateEditableTemplateSpecPatch(patch)
    return patch


def build_template_spec_patch_from_files(
    *,
    extracted_design_system_path: str | Path = DEFAULT_EXTRACTED_DESIGN_SYSTEM,
    template_spec_path: str | Path = DEFAULT_TEMPLATE_SPEC,
    design_brief_path: str | Path = DEFAULT_DESIGN_BRIEF,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    requested_extracted_path = Path(extracted_design_system_path)
    extracted_path = _preferred_extracted_design_system_path(requested_extracted_path)
    spec_path = Path(template_spec_path)
    brief_path = Path(design_brief_path)
    patch = build_template_spec_patch(
        _load_json(extracted_path),
        _load_json(spec_path),
        _load_json(brief_path),
        source_paths={
            "extracted_design_system_path": _display_path(extracted_path),
            "editable_template_spec_path": _display_path(spec_path),
            "design_brief_path": _display_path(brief_path),
        },
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(patch, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a safe editable_template_spec_patch.json from extracted design observations.")
    parser.add_argument("--extracted-design-system", type=Path, default=DEFAULT_EXTRACTED_DESIGN_SYSTEM)
    parser.add_argument("--template-spec", type=Path, default=DEFAULT_TEMPLATE_SPEC)
    parser.add_argument("--design-brief", type=Path, default=DEFAULT_DESIGN_BRIEF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def _preferred_extracted_design_system_path(requested_path: Path) -> Path:
    sibling_merged = requested_path.with_name("extracted_design_system.merged.json")
    if sibling_merged.exists():
        return sibling_merged
    if requested_path == DEFAULT_EXTRACTED_DESIGN_SYSTEM and DEFAULT_MERGED_EXTRACTED_DESIGN_SYSTEM.exists():
        return DEFAULT_MERGED_EXTRACTED_DESIGN_SYSTEM
    return requested_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = build_template_spec_patch_from_files(
            extracted_design_system_path=args.extracted_design_system,
            template_spec_path=args.template_spec,
            design_brief_path=args.design_brief,
            output_path=args.output,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BUILD_TEMPLATE_SPEC_PATCH_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _color_patches(
    extracted: dict[str, Any],
    spec: dict[str, Any],
    safety_warnings: list[dict[str, Any]],
    ignored: list[dict[str, Any]],
) -> dict[str, str]:
    patches: dict[str, str] = {}
    base_colors = spec["tokens"]["colors"]
    for item in extracted.get("detected_palette") or []:
        role = str(item.get("role") or "").strip().lower()
        token = SAFE_COLOR_ROLES.get(role)
        if token is None:
            ignored.append(_warning("UNSAFE_COLOR_ROLE_IGNORED", f"Color role {role or '<missing>'} is not a safe token patch target.", "warning", "tokens.colors"))
            continue
        if token not in base_colors:
            ignored.append(_warning("UNKNOWN_COLOR_TOKEN_IGNORED", f"Color token {token} does not exist in the base spec.", "warning", "tokens.colors"))
            continue
        patches[token] = str(item["hex"]).upper()
    if not patches:
        safety_warnings.append(_warning("NO_COLOR_PATCHES_EMITTED", "No safe color token patches were derived.", "info", "tokens.colors"))
    return patches


def _typography_patches(
    extracted: dict[str, Any],
    spec: dict[str, Any],
    clamp_report: list[dict[str, Any]],
    ignored: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    base_typography = spec["tokens"]["typography"]
    for item in extracted.get("typography_estimates") or []:
        role = str(item.get("role") or "").strip().lower()
        if role not in TYPE_SIZE_LIMITS or role not in base_typography:
            ignored.append(_warning("UNSAFE_TYPOGRAPHY_ROLE_IGNORED", f"Typography role {role or '<missing>'} is not a safe patch target.", "warning", "tokens.typography"))
            continue
        size = _clamp(float(item.get("size_pt") or base_typography[role].get("size_pt") or TYPE_SIZE_LIMITS[role][0]), *TYPE_SIZE_LIMITS[role], f"tokens.typography.{role}.size_pt", clamp_report)
        result[role] = {
            "font_family": str(item.get("estimated_font_family") or base_typography[role].get("font_family") or "Aptos"),
            "size_pt": size,
            "weight": str(item.get("weight") or base_typography[role].get("weight") or "regular"),
        }
    return result


def _spacing_patches(extracted: dict[str, Any], clamp_report: list[dict[str, Any]]) -> dict[str, float]:
    margins = extracted.get("safe_margins") or {}
    numeric_margins = [float(margins.get(key, 0.6)) for key in ("top", "right", "bottom", "left")]
    safe_margin = _clamp(sum(numeric_margins) / max(1, len(numeric_margins)), *MARGIN_LIMITS, "tokens.spacing.safe_margin", clamp_report)
    card_count = len(extracted.get("card_observations") or [])
    raw_padding = 0.16 + min(0.08, card_count * 0.01)
    card_padding = _clamp(raw_padding, *CARD_PADDING_LIMITS, "tokens.spacing.card_padding", clamp_report)
    return {"safe_margin": safe_margin, "card_padding": card_padding}


def _component_style_variants(extracted: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    component_ids = {component["component_id"] for component in spec.get("components") or []}
    variants: list[dict[str, Any]] = []
    if "footer_standard" in component_ids and extracted.get("footer_observations"):
        variants.append(
            {
                "component_id": "footer_standard",
                "variant_id": "observed-footer-rule",
                "style": {"rule": "thin"},
            }
        )
    if "card" in component_ids and extracted.get("card_observations"):
        variants.append(
            {
                "component_id": "card",
                "variant_id": "observed-card-soft-border",
                "style": {"border": "visible", "padding": 0.18},
            }
        )
    if "background_grid" in component_ids and extracted.get("background_ornament_observations"):
        variants.append(
            {
                "component_id": "background_grid",
                "variant_id": "observed-subtle-grid",
                "style": {"ornament": "vector_lines", "density": "subtle"},
            }
        )
    return variants


def _layout_density_hints(
    extracted: dict[str, Any],
    spec: dict[str, Any],
    safety_warnings: list[dict[str, Any]],
    ignored: list[dict[str, Any]],
) -> list[dict[str, str]]:
    density_by_archetype = extracted.get("density_profile", {}).get("by_archetype") or {}
    layouts_by_archetype = {layout["archetype_id"]: layout for layout in spec.get("layouts") or []}
    hints: list[dict[str, str]] = []
    for archetype_id, density in sorted(density_by_archetype.items()):
        layout = layouts_by_archetype.get(archetype_id)
        if layout is None:
            ignored.append(_warning("UNKNOWN_ARCHETYPE_DENSITY_IGNORED", f"Density hint for unknown archetype {archetype_id} was ignored.", "warning", "layouts.density"))
            continue
        normalized_density = str(density).lower()
        if normalized_density not in {"low", "medium", "high"}:
            ignored.append(_warning("INVALID_DENSITY_IGNORED", f"Density hint {density} for {archetype_id} was ignored.", "warning", "layouts.density"))
            continue
        hints.append({"layout_id": layout["layout_id"], "archetype_id": archetype_id, "density": normalized_density})
    if not hints:
        safety_warnings.append(_warning("NO_DENSITY_HINTS_EMITTED", "No safe layout density hints were derived.", "info", "layouts.density"))
    return hints


def _footer_style(extracted: dict[str, Any]) -> dict[str, Any]:
    observations = extracted.get("footer_observations") or []
    return {"rule_weight": 0.8 if observations else 0.6, "text_color_token": "muted_text"}


def _card_style(extracted: dict[str, Any], clamp_report: list[dict[str, Any]]) -> dict[str, float]:
    count = len(extracted.get("card_observations") or [])
    radius = _clamp(0.12 + min(0.06, count * 0.01), 0.06, 0.28, "card_style.radius", clamp_report)
    border = _clamp(0.8, 0.5, 1.8, "card_style.border_weight", clamp_report)
    padding = _clamp(0.16 + min(0.08, count * 0.01), *CARD_PADDING_LIMITS, "card_style.padding", clamp_report)
    return {"radius": radius, "border_weight": border, "padding": padding}


def _background_ornament_style(extracted: dict[str, Any]) -> dict[str, Any]:
    observations = extracted.get("background_ornament_observations") or []
    return {
        "style": "subtle_grid" if observations else "minimal",
        "line_weight": 0.5,
        "color_token": "grid",
    }


def _contrast_warnings(colors: dict[str, str], spec: dict[str, Any], safety_warnings: list[dict[str, Any]]) -> None:
    base_colors = spec["tokens"]["colors"]
    background = colors.get("background") or base_colors.get("background") or "#FFFFFF"
    text = colors.get("text") or base_colors.get("text") or "#111827"
    if _contrast_ratio(background, text) < 4.5:
        safety_warnings.append(_warning("COLOR_CONTRAST_WARNING", "Text/background contrast is below 4.5:1; patch should be reviewed before application.", "warning", "tokens.colors"))


def _maximum_density_warning(layout_density_hints: list[dict[str, str]], safety_warnings: list[dict[str, Any]]) -> None:
    if not layout_density_hints:
        return
    high_count = sum(1 for item in layout_density_hints if item["density"] == "high")
    if high_count / len(layout_density_hints) > 0.65:
        safety_warnings.append(_warning("MAXIMUM_DENSITY_WARNING", "More than 65 percent of layout density hints are high; keep Stage 4 layouts reviewable.", "warning", "layouts.density"))


def _record_forbidden_field_guards(ignored: list[dict[str, Any]]) -> None:
    ignored.append(
        _warning(
            "FORBIDDEN_FIELDS_NOT_PATCHED",
            "Patch builder never emits design_id, canvas, asset_policy, render_policy, layout slots, slot definitions, primitives, editability flags, or full-slide raster settings.",
            "info",
            "patch_policy.forbidden_fields",
        )
    )


def _source_artifact(paths: dict[str, str] | None) -> dict[str, str]:
    defaults = {
        "extracted_design_system_path": _display_path(DEFAULT_EXTRACTED_DESIGN_SYSTEM),
        "editable_template_spec_path": _display_path(DEFAULT_TEMPLATE_SPEC),
        "design_brief_path": _display_path(DEFAULT_DESIGN_BRIEF),
    }
    if paths:
        defaults.update(paths)
    return defaults


def _clamp(value: float, min_value: float, max_value: float, field: str, clamp_report: list[dict[str, Any]]) -> float:
    output = min(max(value, min_value), max_value)
    if output != value:
        clamp_report.append({"field": field, "input": value, "output": output, "min": min_value, "max": max_value})
    return round(output, 3)


def _patch_id(extracted: dict[str, Any], spec: dict[str, Any], design_brief: dict[str, Any]) -> str:
    seed = json.dumps(
        {
            "base_design_id": spec.get("design_id"),
            "source_count": len(extracted.get("source_template_images") or []),
            "topic": design_brief.get("topic"),
            "palette": extracted.get("detected_palette"),
            "density": extracted.get("density_profile"),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return f"editable-template-spec-patch-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    lum_a = _relative_luminance(hex_a)
    lum_b = _relative_luminance(hex_b)
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(hex_color: str) -> float:
    rgb = [int(hex_color.strip().lstrip("#")[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _warning(code: str, message: str, severity: str, field: str) -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity, "field": field}


def _dedupe_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for warning in warnings:
        key = (warning["code"], warning.get("field", ""))
        if key not in seen:
            seen.add(key)
            result.append(warning)
    return result


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    return str(path.as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
