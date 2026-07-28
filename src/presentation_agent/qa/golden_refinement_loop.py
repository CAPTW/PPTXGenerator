"""Recommend editable golden-master refinements against full-size layout refs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .template_crop_render_diff import _comparison_metrics, _image_metrics, _match_score


DEFAULT_LAYOUT_REF_DIR = Path("outputs/template_design_board/layout_refs")
DEFAULT_RENDER_DIR = Path("outputs/golden_template_masters_png")
DEFAULT_FIDELITY_REPORT = Path("outputs/golden_template_fidelity_report.json")
DEFAULT_GOLDEN_REPORT = Path("outputs/golden_template_masters_report.json")
DEFAULT_MASTER_SPECS_DIR = Path("outputs/golden_master_specs")
DEFAULT_OUTPUT_DIR = Path("outputs/golden_refinement")
DEFAULT_JSON_REPORT = DEFAULT_OUTPUT_DIR / "golden_refinement_report.json"
DEFAULT_MD_REPORT = DEFAULT_OUTPUT_DIR / "golden_refinement_report.md"

PATCH_TYPES = {
    "increase_dark_panel_ratio",
    "strengthen_footer_strip",
    "add_topology_ornaments",
    "add_index_markers",
    "adjust_photo_mask_geometry",
    "increase_card_density",
    "increase_table_chrome",
    "improve_chart_module_density",
    "reduce_white_space",
}

PRIORITY_ARCHETYPES = (
    "creative_cover",
    "visual_table_of_contents",
    "section_divider",
    "research_overview",
    "methodology_framework",
    "data_table_appendix",
)


def build_golden_refinement_report_from_files(
    *,
    layout_ref_dir: str | Path = DEFAULT_LAYOUT_REF_DIR,
    render_dir: str | Path = DEFAULT_RENDER_DIR,
    fidelity_report_path: str | Path = DEFAULT_FIDELITY_REPORT,
    golden_report_path: str | Path = DEFAULT_GOLDEN_REPORT,
    master_specs_dir: str | Path = DEFAULT_MASTER_SPECS_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    json_report_path: str | Path = DEFAULT_JSON_REPORT,
    md_report_path: str | Path = DEFAULT_MD_REPORT,
    apply: bool = False,
) -> dict[str, Any]:
    report = build_golden_refinement_report(
        layout_ref_dir=layout_ref_dir,
        render_dir=render_dir,
        fidelity_report_path=fidelity_report_path,
        golden_report_path=golden_report_path,
        master_specs_dir=master_specs_dir,
        output_dir=output_dir,
        apply=apply,
    )
    json_path = Path(json_report_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    Path(md_report_path).write_text(_markdown_report(report), encoding="utf-8")
    return report


def build_golden_refinement_report(
    *,
    layout_ref_dir: str | Path,
    render_dir: str | Path,
    fidelity_report_path: str | Path,
    golden_report_path: str | Path,
    master_specs_dir: str | Path,
    output_dir: str | Path,
    apply: bool = False,
) -> dict[str, Any]:
    layout_refs = Path(layout_ref_dir)
    rendered_dir = Path(render_dir)
    specs_dir = Path(master_specs_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    fidelity = _load_json(fidelity_report_path) if Path(fidelity_report_path).exists() else {}
    golden = _load_json(golden_report_path) if Path(golden_report_path).exists() else {}
    records = _slide_records(fidelity, golden)

    patch_records: list[dict[str, Any]] = []
    for record in records:
        archetype_id = str(record.get("archetype_id") or "")
        if not archetype_id:
            continue
        patch_record = _build_patch_record(
            archetype_id=archetype_id,
            slide_number=int(record.get("slide_number") or len(patch_records) + 1),
            record=record,
            layout_ref_dir=layout_refs,
            render_dir=rendered_dir,
            master_specs_dir=specs_dir,
        )
        patch_path = output / f"{archetype_id}.patch.json"
        if apply and patch_record.get("status") in {"recommended", "ready"}:
            patch_record["apply_result"] = apply_refinement_patches(patch_record, master_specs_dir=specs_dir)
            patch_record["mode"] = "applied"
        else:
            patch_record["mode"] = "recommendation_only"
        patch_record["patch_path"] = _display_path(patch_path)
        patch_path.write_text(json.dumps(patch_record, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        patch_records.append(patch_record)

    recommendation_count = sum(len(item.get("patches") or []) for item in patch_records)
    missing_refs = [item["archetype_id"] for item in patch_records if "layout_ref" in item.get("missing_inputs", [])]
    applied_count = sum(1 for item in patch_records if item.get("apply_result", {}).get("applied"))
    status = "applied" if apply and applied_count else "recommendations_ready" if recommendation_count else "NEEDS_REFERENCE_ASSET" if missing_refs else "no_patches_needed"
    return {
        "schema_name": "golden_refinement_report",
        "schema_version": "1.0",
        "status": status,
        "mode": "apply" if apply else "recommendation_only",
        "layout_ref_dir": _display_path(Path(layout_ref_dir)),
        "render_dir": _display_path(Path(render_dir)),
        "golden_template_fidelity_report_path": _display_path(Path(fidelity_report_path)),
        "golden_template_masters_report_path": _display_path(Path(golden_report_path)),
        "golden_master_specs_dir": _display_path(specs_dir),
        "output_dir": _display_path(output),
        "patch_type_allowlist": sorted(PATCH_TYPES),
        "slide_count": len(patch_records),
        "recommendation_count": recommendation_count,
        "applied_count": applied_count,
        "missing_reference_count": len(missing_refs),
        "missing_reference_archetypes": missing_refs,
        "no_raster_policy": _no_raster_policy(),
        "patches": [
            {
                "archetype_id": item.get("archetype_id"),
                "slide_number": item.get("slide_number"),
                "status": item.get("status"),
                "patch_path": item.get("patch_path"),
                "patch_count": len(item.get("patches") or []),
                "patch_types": [patch.get("patch_type") for patch in item.get("patches") or []],
            }
            for item in patch_records
        ],
    }


def apply_refinement_patches(patch_record: dict[str, Any], *, master_specs_dir: str | Path = DEFAULT_MASTER_SPECS_DIR) -> dict[str, Any]:
    patches = [patch for patch in patch_record.get("patches") or [] if patch.get("patch_type") in PATCH_TYPES]
    if not patches:
        return {"applied": False, "reason": "NO_PATCHES"}
    archetype_id = str(patch_record.get("archetype_id") or "")
    spec_path = Path(master_specs_dir) / f"{archetype_id}.json"
    if not spec_path.exists():
        return {"applied": False, "reason": "MASTER_SPEC_MISSING", "path": _display_path(spec_path)}
    spec = _load_json(spec_path)
    before = {
        "minimum_visual_features": dict(spec.get("minimum_visual_features") or {}),
        "ornament_system": dict(spec.get("ornament_system") or {}),
        "expected_density": spec.get("expected_density"),
    }
    directives = list(spec.get("refinement_patch_directives") or [])
    applied_types: list[str] = []
    for patch in patches:
        patch_type = str(patch.get("patch_type"))
        _apply_patch_to_spec(spec, patch_type, patch)
        directives.append(
            {
                "patch_type": patch_type,
                "source": "golden_refinement_loop",
                "editable_ppt_objects_only": True,
                "no_raster_background": True,
            }
        )
        applied_types.append(patch_type)
    spec["refinement_patch_directives"] = _dedupe_directives(directives)
    spec["refinement_patch_history"] = {
        "last_source": "golden_refinement_loop",
        "applied_patch_types": sorted(set(applied_types)),
        "reference_path": patch_record.get("reference_path"),
        "rendered_path": patch_record.get("rendered_path"),
    }
    constraints = spec.setdefault("production_master_constraints", {})
    constraints["editable_objects_only"] = True
    constraints["no_full_slide_background_image"] = True
    constraints["no_rasterized_text"] = True
    constraints["no_source_backed_planning_artifacts"] = True
    spec_path.write_text(json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return {
        "applied": True,
        "path": _display_path(spec_path),
        "applied_patch_types": sorted(set(applied_types)),
        "before_spec_summary": before,
        "after_spec_summary": {
            "minimum_visual_features": spec.get("minimum_visual_features"),
            "ornament_system": spec.get("ornament_system"),
            "expected_density": spec.get("expected_density"),
            "refinement_patch_directive_count": len(spec.get("refinement_patch_directives") or []),
        },
    }


def _build_patch_record(
    *,
    archetype_id: str,
    slide_number: int,
    record: dict[str, Any],
    layout_ref_dir: Path,
    render_dir: Path,
    master_specs_dir: Path,
) -> dict[str, Any]:
    reference_path = layout_ref_dir / f"{archetype_id}.png"
    rendered_path = _rendered_path(record, render_dir, slide_number)
    spec_path = master_specs_dir / f"{archetype_id}.json"
    missing_inputs: list[str] = []
    if not reference_path.exists():
        missing_inputs.append("layout_ref")
    if not rendered_path.exists():
        missing_inputs.append("rendered_golden_master_png")
    if missing_inputs:
        before_metrics = _safe_metrics(rendered_path)
        return {
            "schema_name": "golden_refinement_patch",
            "schema_version": "1.0",
            "archetype_id": archetype_id,
            "slide_number": slide_number,
            "status": "NEEDS_REFERENCE_ASSET" if "layout_ref" in missing_inputs else "MISSING_RENDER",
            "reference_path": _display_path(reference_path),
            "rendered_path": _display_path(rendered_path),
            "master_spec_path": _display_path(spec_path),
            "missing_inputs": missing_inputs,
            "before_metrics": before_metrics,
            "reference_metrics": None,
            "after_metrics": before_metrics,
            "after_metrics_source": "unchanged_missing_inputs",
            "patches": [],
            "no_raster_policy": _no_raster_policy(),
            "recommended_fix": "Add a full-size 16:9 layout reference asset before running metric-based refinement." if "layout_ref" in missing_inputs else "Render golden master PNGs before running refinement.",
        }

    reference_metrics = _derived_metrics(reference_path)
    before_metrics = _derived_metrics(rendered_path)
    comparison = _comparison_metrics(reference_metrics["raw"], before_metrics["raw"])
    patches = _recommend_patches(archetype_id, reference_metrics, before_metrics, comparison, record)
    after_metrics = _project_after_metrics(before_metrics, reference_metrics, patches)
    status = "recommended" if patches else "ready"
    return {
        "schema_name": "golden_refinement_patch",
        "schema_version": "1.0",
        "archetype_id": archetype_id,
        "slide_number": slide_number,
        "status": status,
        "reference_path": _display_path(reference_path),
        "rendered_path": _display_path(rendered_path),
        "master_spec_path": _display_path(spec_path),
        "missing_inputs": [],
        "similarity_score": round(_match_score(comparison), 6),
        "reference_metrics": reference_metrics["summary"],
        "before_metrics": before_metrics["summary"],
        "after_metrics": after_metrics,
        "after_metrics_source": "projected_recommendation",
        "comparison_metrics": _comparison_summary(comparison),
        "patches": patches,
        "no_raster_policy": _no_raster_policy(),
        "recommended_fix": _recommended_fix_text(patches),
    }


def _recommend_patches(
    archetype_id: str,
    reference_metrics: dict[str, Any],
    before_metrics: dict[str, Any],
    comparison: dict[str, Any],
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    ref = reference_metrics["summary"]
    before = before_metrics["summary"]
    patches: list[dict[str, Any]] = []
    if before["dark_panel_ratio"] < ref["dark_panel_ratio"] - 0.05 and (ref["dark_panel_ratio"] > 0.18 or archetype_id in {"creative_cover", "section_divider"}):
        patches.append(_patch("increase_dark_panel_ratio", "Rendered dark field is weaker than the layout reference.", "minimum_visual_features.dark_area_ratio", ref, before))
    if before["footer_strip_strength"] < ref["footer_strip_strength"] - 0.08 or comparison.get("footer_occupancy_delta", 0) < -0.08:
        patches.append(_patch("strengthen_footer_strip", "Footer/source microsystem is underrepresented.", "footer_source_geometry", ref, before))
    if before["topology_ornament_density"] < ref["topology_ornament_density"] - 0.025 or comparison.get("ornament_density_delta", 0) < -0.035:
        patches.append(_patch("add_topology_ornaments", "Topology, contour, or connector ornament density is lower than reference.", "ornament_system", ref, before))
    if archetype_id in {"visual_table_of_contents", "section_divider"} and before["index_marker_strength"] < max(0.12, ref["index_marker_strength"] - 0.06):
        patches.append(_patch("add_index_markers", "Index or section navigation markers are too weak.", "minimum_visual_features.index_presence", ref, before))
    if archetype_id in {"creative_cover", "section_divider", "photo_caption_grid"} and before["photo_mask_geometry_score"] < max(0.10, ref["photo_mask_geometry_score"] - 0.05):
        patches.append(_patch("adjust_photo_mask_geometry", "Declared photo mask geometry should be strengthened with editable frame objects.", "image_photo_zone_geometry", ref, before))
    if archetype_id in {"research_overview", "methodology_framework"} and before["card_density_score"] < ref["card_density_score"] - 0.07:
        patches.append(_patch("increase_card_density", "Content/card module density is below the reference.", "minimum_visual_features.card_density", ref, before))
    if archetype_id == "data_table_appendix" and before["table_chrome_score"] < max(0.16, ref["table_chrome_score"] - 0.05):
        patches.append(_patch("increase_table_chrome", "Appendix table chrome lacks enough grid/header/source density.", "minimum_visual_features.table_density", ref, before))
    if archetype_id in {"kpi_donut_chart", "technical_flow_chart"} and before["chart_module_density_score"] < ref["chart_module_density_score"] - 0.06:
        patches.append(_patch("improve_chart_module_density", "Chart/module area is too sparse against the reference.", "card_chart_table_chrome_style", ref, before))
    if before["white_space_ratio"] > ref["white_space_ratio"] + 0.08 and str(record.get("expected_density") or "") != "low":
        patches.append(_patch("reduce_white_space", "Rendered master has materially more blank white space than reference.", "expected_density", ref, before))
    return patches


def _patch(patch_type: str, reason: str, target_field: str, ref: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        "patch_type": patch_type,
        "reason": reason,
        "target_field": target_field,
        "no_raster_policy": _no_raster_policy(),
        "before_metrics": before,
        "target_metrics": ref,
        "apply_plan": _apply_plan(patch_type),
    }


def _apply_patch_to_spec(spec: dict[str, Any], patch_type: str, patch: dict[str, Any]) -> None:
    features = spec.setdefault("minimum_visual_features", {})
    ornaments = spec.setdefault("ornament_system", {"density_mode": "medium", "motifs": []})
    motifs = ornaments.setdefault("motifs", [])
    if patch_type == "increase_dark_panel_ratio":
        target = float((patch.get("target_metrics") or {}).get("dark_panel_ratio") or features.get("dark_area_ratio") or 0.1)
        features["dark_area_ratio"] = round(max(float(features.get("dark_area_ratio") or 0), min(0.75, target)), 4)
        ornaments["density_mode"] = "high"
    elif patch_type == "strengthen_footer_strip":
        features["footer_presence"] = True
        _strengthen_footer_geometry(spec)
    elif patch_type == "add_topology_ornaments":
        ornaments["density_mode"] = "high"
        motifs.append("refinement topology ornaments")
    elif patch_type == "add_index_markers":
        features["index_presence"] = True
    elif patch_type == "adjust_photo_mask_geometry":
        features["image_mask_presence"] = True
        _ensure_photo_zone(spec)
    elif patch_type == "increase_card_density":
        features["card_density"] = "high" if spec.get("expected_density") == "high" else "medium"
        spec["expected_density"] = "high" if spec.get("expected_density") == "high" else "medium"
    elif patch_type == "increase_table_chrome":
        features["table_density"] = "high"
        spec["expected_density"] = "high"
        chrome = spec.setdefault("card_chart_table_chrome_style", {})
        chrome["mode"] = "dense editable appendix table chrome"
    elif patch_type == "improve_chart_module_density":
        spec["expected_density"] = "high"
        chrome = spec.setdefault("card_chart_table_chrome_style", {})
        chrome["mode"] = "dense editable chart module chrome"
    elif patch_type == "reduce_white_space":
        if spec.get("expected_density") == "low":
            spec["expected_density"] = "medium"
        features["card_density"] = "medium" if features.get("card_density") == "low" else features.get("card_density", "medium")
    ornaments["motifs"] = sorted(set(str(item) for item in motifs if item))


def _strengthen_footer_geometry(spec: dict[str, Any]) -> None:
    geometry = spec.setdefault("footer_source_geometry", {"coordinate_system": "inches_16_9", "mode": "defined", "slots": []})
    slots = geometry.setdefault("slots", [])
    if not slots:
        slots.append({"slot_id": "footer", "slot_type": "text", "component_id": "citation_micro_footer", "bounds": {"x": 0.45, "y": 6.74, "w": 12.4, "h": 0.46}})
    for slot in slots:
        bounds = slot.setdefault("bounds", {})
        bounds["h"] = round(max(float(bounds.get("h") or 0.0), 0.42), 3)
        bounds["y"] = round(min(float(bounds.get("y") or 6.82), 6.76), 3)


def _ensure_photo_zone(spec: dict[str, Any]) -> None:
    geometry = spec.setdefault("image_photo_zone_geometry", {"coordinate_system": "inches_16_9", "mode": "defined", "slots": []})
    slots = geometry.setdefault("slots", [])
    if not slots:
        slots.append(
            {
                "slot_id": "hero_image",
                "slot_type": "image",
                "component_id": "diagonal_hero_panel",
                "bounds": {"x": 7.45, "y": 1.18, "w": 3.85, "h": 4.25},
            }
        )


def _dedupe_directives(directives: list[Any]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for directive in directives:
        if not isinstance(directive, dict):
            continue
        patch_type = str(directive.get("patch_type") or "")
        if patch_type in PATCH_TYPES:
            result[patch_type] = directive
    return [result[key] for key in sorted(result)]


def _derived_metrics(path: Path) -> dict[str, Any]:
    raw = _image_metrics(path)
    regions = raw["regions"]
    summary = {
        "path": _display_path(path),
        "width_px": raw["width_px"],
        "height_px": raw["height_px"],
        "dark_panel_ratio": raw["dark_area_ratio"],
        "footer_strip_strength": round((regions["footer"]["occupancy"] + regions["footer"]["dark_ratio"]) / 2, 6),
        "topology_ornament_density": raw["edge_density"],
        "index_marker_strength": round((regions["left_rail"]["occupancy"] + regions["left_rail"]["dark_ratio"]) / 2, 6),
        "photo_mask_geometry_score": round((raw["diagonal_edge_density"] + regions["content"]["occupancy"]) / 2, 6),
        "card_density_score": regions["content"]["occupancy"],
        "table_chrome_score": round((regions["data_module"]["occupancy"] + raw["edge_density"]) / 2, 6),
        "chart_module_density_score": round((regions["data_module"]["occupancy"] + raw["diagonal_edge_density"]) / 2, 6),
        "white_space_ratio": raw["blank_area_ratio"],
    }
    return {"raw": raw, "summary": summary}


def _safe_metrics(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return _derived_metrics(path)["summary"]
    except OSError:
        return None


def _project_after_metrics(before_metrics: dict[str, Any], reference_metrics: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    after = dict(before_metrics["summary"])
    ref = reference_metrics["summary"]
    projection_fields = {
        "increase_dark_panel_ratio": "dark_panel_ratio",
        "strengthen_footer_strip": "footer_strip_strength",
        "add_topology_ornaments": "topology_ornament_density",
        "add_index_markers": "index_marker_strength",
        "adjust_photo_mask_geometry": "photo_mask_geometry_score",
        "increase_card_density": "card_density_score",
        "increase_table_chrome": "table_chrome_score",
        "improve_chart_module_density": "chart_module_density_score",
        "reduce_white_space": "white_space_ratio",
    }
    for patch in patches:
        field = projection_fields.get(str(patch.get("patch_type")))
        if not field:
            continue
        if field == "white_space_ratio":
            after[field] = round(max(ref[field], before_metrics["summary"][field] - abs(before_metrics["summary"][field] - ref[field]) * 0.65), 6)
        else:
            after[field] = round(min(ref[field], before_metrics["summary"][field] + abs(ref[field] - before_metrics["summary"][field]) * 0.65), 6)
    return after


def _comparison_summary(comparison: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "palette_similarity",
        "dark_area_delta",
        "edge_density_delta",
        "footer_occupancy_delta",
        "card_region_density_delta",
        "ornament_density_delta",
        "section_number_index_rail_presence_delta",
        "chart_table_module_presence_delta",
    )
    return {key: comparison.get(key) for key in keys}


def _slide_records(fidelity: dict[str, Any], golden: dict[str, Any]) -> list[dict[str, Any]]:
    comparisons = [item for item in fidelity.get("layout_comparisons") or [] if isinstance(item, dict)]
    if comparisons:
        return sorted(comparisons, key=lambda item: int(item.get("slide_number") or 0))
    compiled = [item for item in golden.get("compiled_layouts") or [] if isinstance(item, dict)]
    if compiled:
        return sorted(compiled, key=lambda item: int(item.get("slide_number") or 0))
    return [{"archetype_id": archetype, "slide_number": index} for index, archetype in enumerate(PRIORITY_ARCHETYPES, start=1)]


def _rendered_path(record: dict[str, Any], render_dir: Path, slide_number: int) -> Path:
    path = str(record.get("rendered_image_path") or "")
    return Path(path) if path else render_dir / f"slide-{slide_number:03d}.png"


def _apply_plan(patch_type: str) -> str:
    return {
        "increase_dark_panel_ratio": "Increase editable dark panel or partial hero field primitives; never insert a raster background.",
        "strengthen_footer_strip": "Enlarge editable footer/source strip geometry and add rule/tick shapes.",
        "add_topology_ornaments": "Add editable connector, node, contour, or SVG/PPT ornament primitives.",
        "add_index_markers": "Enable editable index rail or progress markers in the master spec.",
        "adjust_photo_mask_geometry": "Adjust declared photo/image frame slot geometry and editable mask chrome.",
        "increase_card_density": "Increase editable card scaffold density inside content zones.",
        "increase_table_chrome": "Strengthen editable table header, grid rules, and appendix source chrome.",
        "improve_chart_module_density": "Increase editable chart module frame, grid, legend, and KPI chrome.",
        "reduce_white_space": "Increase editable component occupancy without rasterizing text or visuals.",
    }[patch_type]


def _recommended_fix_text(patches: list[dict[str, Any]]) -> str:
    if not patches:
        return "No refinement patch recommended; rendered metrics are close to the full-size layout reference."
    return "Apply the recommended editable-object patch directives with --apply, then rebuild and rerun the premium gate."


def _no_raster_policy() -> dict[str, Any]:
    return {
        "full_slide_picture_background": "forbidden",
        "reference_image_insertion": "forbidden",
        "rasterized_text_table_chart": "forbidden",
        "allowed_outputs": ["ppt_text", "ppt_shape", "ppt_table", "ppt_chart", "svg_ornament", "declared_photo_frame_image"],
    }


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recommend editable golden-master refinements against full-size layout refs.")
    parser.add_argument("--layout-ref-dir", type=Path, default=DEFAULT_LAYOUT_REF_DIR)
    parser.add_argument("--render-dir", type=Path, default=DEFAULT_RENDER_DIR)
    parser.add_argument("--fidelity-report", type=Path, default=DEFAULT_FIDELITY_REPORT)
    parser.add_argument("--golden-report", type=Path, default=DEFAULT_GOLDEN_REPORT)
    parser.add_argument("--master-specs-dir", type=Path, default=DEFAULT_MASTER_SPECS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--md-report", type=Path, default=DEFAULT_MD_REPORT)
    parser.add_argument("--apply", action="store_true", help="Apply recommended patch directives to golden master specs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_golden_refinement_report_from_files(
            layout_ref_dir=args.layout_ref_dir,
            render_dir=args.render_dir,
            fidelity_report_path=args.fidelity_report,
            golden_report_path=args.golden_report,
            master_specs_dir=args.master_specs_dir,
            output_dir=args.output_dir,
            json_report_path=args.json_report,
            md_report_path=args.md_report,
            apply=args.apply,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"GOLDEN_REFINEMENT_FAILED {exc}")
        return 1
    print(f"WROTE {args.json_report}")
    print(f"GOLDEN_REFINEMENT {report['status']} recommendations={report['recommendation_count']} applied={report['applied_count']}")
    return 0


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Golden Refinement Report",
        "",
        f"Status: `{report['status']}`",
        f"Mode: `{report['mode']}`",
        f"Recommendations: `{report['recommendation_count']}`",
        f"Applied: `{report['applied_count']}`",
        f"Missing full-size references: `{report['missing_reference_count']}`",
        "",
        "This report recommends editable-object refinements only. It does not insert design-board or layout-reference images into PPTX files.",
        "",
        "## Patch Summary",
        "",
        "| Slide | Archetype | Status | Patch count | Patch types |",
        "|---:|---|---|---:|---|",
    ]
    for item in report.get("patches") or []:
        patch_types = ", ".join(f"`{patch_type}`" for patch_type in item.get("patch_types") or []) or ""
        lines.append(
            f"| {item.get('slide_number')} | `{item.get('archetype_id')}` | `{item.get('status')}` | {item.get('patch_count')} | {patch_types} |"
        )
    if report.get("missing_reference_archetypes"):
        lines.extend(["", "## Missing References", ""])
        for archetype_id in report["missing_reference_archetypes"]:
            lines.append(f"- `{archetype_id}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
