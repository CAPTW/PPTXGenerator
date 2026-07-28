"""Safely apply editable_template_spec_patch.json to an editable template spec."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ..generator_contracts import validateEditableTemplateSpec, validateEditableTemplateSpecPatch


DEFAULT_TEMPLATE_SPEC = Path("outputs/editable_template_spec.json")
DEFAULT_PATCH = Path("outputs/editable_template_spec_patch.json")
DEFAULT_FINAL_SPEC = Path("outputs/editable_template_spec.final.json")
DEFAULT_REPORT_JSON = Path("outputs/template_spec_patch_report.json")
DEFAULT_REPORT_MD = Path("outputs/template_spec_patch_report.md")
SAFE_COMPONENT_STYLE_KEYS = {
    "border",
    "color_token",
    "density",
    "line_weight",
    "ornament",
    "padding",
    "radius",
    "rule",
    "rule_weight",
    "style",
    "text_color_token",
    "border_weight",
}
FORBIDDEN_STYLE_KEYS = {
    "editable",
    "allow_full_slide_raster",
    "full_slide_raster",
    "no_full_slide_raster_background",
    "asset_policy",
    "render_policy",
    "slots",
    "slot_definitions",
    "primitives",
}


def apply_template_spec_patch(
    editable_template_spec: dict[str, Any],
    editable_template_spec_patch: dict[str, Any],
    *,
    source_paths: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validateEditableTemplateSpec(editable_template_spec)
    validateEditableTemplateSpecPatch(editable_template_spec_patch)

    original = copy.deepcopy(editable_template_spec)
    final_spec = copy.deepcopy(editable_template_spec)
    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []

    if editable_template_spec_patch["base_design_id"] != editable_template_spec["design_id"]:
        rejected.append(
            _operation(
                "BASE_DESIGN_ID_MISMATCH",
                "patch.base_design_id",
                f"Patch targets {editable_template_spec_patch['base_design_id']} but base spec is {editable_template_spec['design_id']}.",
            )
        )
    else:
        safe_patches = editable_template_spec_patch["safe_patches"]
        _apply_color_tokens(final_spec, safe_patches["tokens"].get("colors", {}), applied, skipped, rejected)
        _apply_typography(final_spec, safe_patches["tokens"].get("typography", {}), applied, skipped, rejected)
        _apply_spacing(final_spec, safe_patches["tokens"].get("spacing", {}), applied, skipped, rejected)
        _apply_component_variants(final_spec, safe_patches.get("component_style_variants", []), applied, skipped, rejected)
        _apply_layout_density_hints(final_spec, safe_patches.get("layout_density_hints", []), applied, skipped, rejected)
        _apply_footer_style(final_spec, safe_patches.get("footer_style_refinements", {}), applied, skipped, rejected)
        _apply_card_style(final_spec, safe_patches.get("card_style", {}), applied, skipped, rejected)
        _apply_background_ornament_style(final_spec, safe_patches.get("background_ornament_style", {}), applied, skipped, rejected)

    invariant_checks = _invariant_checks(original, final_spec)
    invariant_failures = [item for item in invariant_checks if item["status"] != "passed"]
    if invariant_failures:
        final_spec = copy.deepcopy(original)
        for failure in invariant_failures:
            rejected.append(_operation("INVARIANT_VIOLATION_REVERTED", failure["field"], failure["message"]))
        invariant_checks = _invariant_checks(original, final_spec)

    validateEditableTemplateSpec(final_spec)
    report = {
        "schema_name": "template_spec_patch_report",
        "schema_version": "1.0",
        "patch_id": editable_template_spec_patch["patch_id"],
        "base_design_id": editable_template_spec["design_id"],
        "source_artifact": _source_artifact(source_paths),
        "output_spec_path": _display_path(DEFAULT_FINAL_SPEC),
        "applied_operations": applied,
        "skipped_operations": skipped,
        "rejected_operations": rejected,
        "invariant_checks": invariant_checks,
        "summary": {
            "applied_count": len(applied),
            "skipped_count": len(skipped),
            "rejected_count": len(rejected),
            "final_spec_valid": True,
        },
    }
    return final_spec, report


def apply_template_spec_patch_from_files(
    *,
    template_spec_path: str | Path = DEFAULT_TEMPLATE_SPEC,
    patch_path: str | Path = DEFAULT_PATCH,
    output_path: str | Path = DEFAULT_FINAL_SPEC,
    report_json_path: str | Path = DEFAULT_REPORT_JSON,
    report_md_path: str | Path = DEFAULT_REPORT_MD,
) -> Path:
    spec_path = Path(template_spec_path)
    patch_file = Path(patch_path)
    output = Path(output_path)
    report_json = Path(report_json_path)
    report_md = Path(report_md_path)
    final_spec, report = apply_template_spec_patch(
        _load_json(spec_path),
        _load_json(patch_file),
        source_paths={
            "editable_template_spec_path": _display_path(spec_path),
            "editable_template_spec_patch_path": _display_path(patch_file),
        },
    )
    report["output_spec_path"] = _display_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_md.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(final_spec, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    report_md.write_text(_report_markdown(report), encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely apply editable_template_spec_patch.json to editable_template_spec.json.")
    parser.add_argument("--template-spec", type=Path, default=DEFAULT_TEMPLATE_SPEC)
    parser.add_argument("--patch", type=Path, default=DEFAULT_PATCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_FINAL_SPEC)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = apply_template_spec_patch_from_files(
            template_spec_path=args.template_spec,
            patch_path=args.patch,
            output_path=args.output,
            report_json_path=args.report_json,
            report_md_path=args.report_md,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"APPLY_TEMPLATE_SPEC_PATCH_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _apply_color_tokens(
    spec: dict[str, Any],
    colors: dict[str, str],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    base_colors = spec["tokens"]["colors"]
    for token, value in sorted(colors.items()):
        field = f"tokens.colors.{token}"
        if token not in base_colors:
            rejected.append(_operation("UNKNOWN_COLOR_TOKEN", field, "Color token is not present in base spec."))
            continue
        _set_or_skip(base_colors, token, value, field, "SET_COLOR_TOKEN", applied, skipped)


def _apply_typography(
    spec: dict[str, Any],
    typography: dict[str, dict[str, Any]],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    base_typography = spec["tokens"]["typography"]
    for role, values in sorted(typography.items()):
        if role not in base_typography:
            rejected.append(_operation("UNKNOWN_TYPOGRAPHY_ROLE", f"tokens.typography.{role}", "Typography role is not present in base spec."))
            continue
        for key in ("font_family", "size_pt", "weight"):
            if key in values:
                _set_or_skip(base_typography[role], key, values[key], f"tokens.typography.{role}.{key}", "SET_TYPOGRAPHY_TOKEN", applied, skipped)


def _apply_spacing(
    spec: dict[str, Any],
    spacing: dict[str, float],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    base_spacing = spec["tokens"]["spacing"]
    for token, value in sorted(spacing.items()):
        if token not in {"card_padding", "safe_margin"}:
            rejected.append(_operation("UNKNOWN_SPACING_TOKEN", f"tokens.spacing.{token}", "Spacing token is outside the safe patch surface."))
            continue
        _set_or_skip(base_spacing, token, value, f"tokens.spacing.{token}", "SET_SPACING_TOKEN", applied, skipped)


def _apply_component_variants(
    spec: dict[str, Any],
    variants: list[dict[str, Any]],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    components = {component["component_id"]: component for component in spec.get("components") or []}
    for variant in variants:
        component_id = variant["component_id"]
        variant_id = variant["variant_id"]
        field = f"components.{component_id}.default_tokens.style_variants.{variant_id}"
        component = components.get(component_id)
        if component is None:
            rejected.append(_operation("UNKNOWN_COMPONENT", field, "Component is not present in base spec."))
            continue
        style = variant.get("style") or {}
        unsafe_key = _unsafe_style_key(style)
        if unsafe_key:
            rejected.append(_operation("UNSAFE_COMPONENT_STYLE_REJECTED", field, f"Style key {unsafe_key} is not allowed for patch application."))
            continue
        default_tokens = component.setdefault("default_tokens", {})
        style_variants = default_tokens.setdefault("style_variants", {})
        _set_or_skip(style_variants, variant_id, dict(style), field, "SET_COMPONENT_STYLE_VARIANT", applied, skipped)


def _apply_layout_density_hints(
    spec: dict[str, Any],
    hints: list[dict[str, str]],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    layouts = {layout["layout_id"]: layout for layout in spec.get("layouts") or []}
    for hint in hints:
        layout_id = hint["layout_id"]
        field = f"layouts.{layout_id}.density"
        layout = layouts.get(layout_id)
        if layout is None:
            rejected.append(_operation("UNKNOWN_LAYOUT", field, "Layout is not present in base spec."))
            continue
        if layout.get("archetype_id") != hint["archetype_id"]:
            rejected.append(_operation("LAYOUT_ARCHETYPE_MISMATCH", field, "Density hint archetype does not match base layout archetype."))
            continue
        _set_or_skip(layout, "density", hint["density"], field, "SET_LAYOUT_DENSITY", applied, skipped)


def _apply_footer_style(
    spec: dict[str, Any],
    footer_style: dict[str, Any],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    _apply_component_refinement(spec, "footer_standard", "footer_style_refinements", footer_style, applied, skipped, rejected)


def _apply_card_style(
    spec: dict[str, Any],
    card_style: dict[str, Any],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    _apply_component_refinement(spec, "card", "card_style", card_style, applied, skipped, rejected)


def _apply_background_ornament_style(
    spec: dict[str, Any],
    background_style: dict[str, Any],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    _apply_component_refinement(spec, "background_grid", "background_ornament_style", background_style, applied, skipped, rejected)


def _apply_component_refinement(
    spec: dict[str, Any],
    component_id: str,
    refinement_key: str,
    style: dict[str, Any],
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> None:
    if not style:
        return
    components = {component["component_id"]: component for component in spec.get("components") or []}
    component = components.get(component_id)
    field = f"components.{component_id}.default_tokens.{refinement_key}"
    if component is None:
        rejected.append(_operation("UNKNOWN_COMPONENT", field, "Component is not present in base spec."))
        return
    unsafe_key = _unsafe_style_key(style)
    if unsafe_key:
        rejected.append(_operation("UNSAFE_COMPONENT_STYLE_REJECTED", field, f"Style key {unsafe_key} is not allowed for patch application."))
        return
    color_token = style.get("color_token") or style.get("text_color_token")
    if color_token and color_token not in spec["tokens"]["colors"]:
        rejected.append(_operation("UNKNOWN_COLOR_TOKEN", field, f"Referenced color token {color_token} is not present in base spec."))
        return
    default_tokens = component.setdefault("default_tokens", {})
    _set_or_skip(default_tokens, refinement_key, dict(style), field, "SET_COMPONENT_REFINEMENT", applied, skipped)


def _invariant_checks(original: dict[str, Any], final_spec: dict[str, Any]) -> list[dict[str, str]]:
    checks = [
        _invariant("design_id", original.get("design_id") == final_spec.get("design_id"), "Spec identity was preserved."),
        _invariant("canvas", original.get("canvas") == final_spec.get("canvas"), "Canvas was preserved."),
        _invariant("asset_policy", original.get("asset_policy") == final_spec.get("asset_policy"), "Asset policy was preserved."),
        _invariant("render_policy", original.get("render_policy") == final_spec.get("render_policy"), "Render policy was preserved."),
        _invariant("components.editable", _component_editability(original) == _component_editability(final_spec), "Component editability flags were preserved."),
        _invariant("layouts.identity", _layout_identity(original) == _layout_identity(final_spec), "Layout IDs, archetypes, slide types, and slots were preserved."),
        _invariant("slot_definitions", original.get("slot_definitions") == final_spec.get("slot_definitions"), "Slot definitions were preserved."),
        _invariant("primitives", original.get("primitives") == final_spec.get("primitives"), "Primitive definitions were preserved."),
    ]
    return checks


def _layout_identity(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "layout_id": layout.get("layout_id"),
            "archetype_id": layout.get("archetype_id"),
            "slide_type": layout.get("slide_type"),
            "slots": layout.get("slots"),
        }
        for layout in spec.get("layouts") or []
    ]


def _component_editability(spec: dict[str, Any]) -> dict[str, Any]:
    return {component.get("component_id"): component.get("editable") for component in spec.get("components") or []}


def _invariant(field: str, passed: bool, message: str) -> dict[str, str]:
    return {"field": field, "status": "passed" if passed else "failed", "message": message}


def _set_or_skip(
    target: dict[str, Any],
    key: str,
    value: Any,
    field: str,
    code: str,
    applied: list[dict[str, str]],
    skipped: list[dict[str, str]],
) -> None:
    if target.get(key) == value:
        skipped.append(_operation("UNCHANGED", field, "Patch value matches existing value."))
        return
    target[key] = value
    applied.append(_operation(code, field, "Patch value applied."))


def _unsafe_style_key(style: dict[str, Any]) -> str | None:
    for key in style:
        normalized = str(key).strip()
        if normalized in FORBIDDEN_STYLE_KEYS or normalized not in SAFE_COMPONENT_STYLE_KEYS:
            return normalized
    return None


def _operation(code: str, field: str, message: str) -> dict[str, str]:
    return {"code": code, "field": field, "message": message}


def _source_artifact(paths: dict[str, str] | None) -> dict[str, str]:
    defaults = {
        "editable_template_spec_path": _display_path(DEFAULT_TEMPLATE_SPEC),
        "editable_template_spec_patch_path": _display_path(DEFAULT_PATCH),
    }
    if paths:
        defaults.update(paths)
    return defaults


def _report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Template Spec Patch Report",
        "",
        f"- Patch ID: `{report['patch_id']}`",
        f"- Base design ID: `{report['base_design_id']}`",
        f"- Output spec: `{report['output_spec_path']}`",
        f"- Applied: {report['summary']['applied_count']}",
        f"- Skipped: {report['summary']['skipped_count']}",
        f"- Rejected: {report['summary']['rejected_count']}",
        f"- Final spec valid: {str(report['summary']['final_spec_valid']).lower()}",
        "",
        "## Applied Operations",
        *_operation_lines(report["applied_operations"]),
        "",
        "## Skipped Operations",
        *_operation_lines(report["skipped_operations"]),
        "",
        "## Rejected Operations",
        *_operation_lines(report["rejected_operations"]),
        "",
        "## Invariant Checks",
        *[f"- {item['status']}: `{item['field']}` - {item['message']}" for item in report["invariant_checks"]],
        "",
    ]
    return "\n".join(lines)


def _operation_lines(operations: list[dict[str, str]]) -> list[str]:
    if not operations:
        return ["- none"]
    return [f"- `{item['code']}` `{item['field']}` - {item['message']}" for item in operations]


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    return str(path.as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
