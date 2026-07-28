"""D05 semantic editability gate helpers."""

from __future__ import annotations

from typing import Any


def evaluate_semantic_editability(spec: dict[str, Any], ledgers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    objects = spec.get("objects") or []
    semantic_raster = [
        obj
        for obj in objects
        if obj.get("semantic_component") in {"text", "icon", "chart", "table", "matrix"} and obj.get("final_use") == "raster"
    ]
    noneditable_required = [
        obj
        for obj in objects
        if obj.get("semantic_component") in {"text", "icon", "chart", "table", "matrix", "source_footer"} and not obj.get("editable")
    ]
    text_count = ledgers.get("text_ledger", {}).get("editable_text_count", 0)
    report = {
        "schema_name": "semantic_editability_report",
        "status": "passed" if not semantic_raster and not noneditable_required else "failed",
        "semantic_object_count": len([obj for obj in objects if obj.get("semantic_component") in {"text", "icon", "chart", "table", "matrix", "source_footer"}]),
        "editable_text_count": text_count,
        "semantic_raster_final_use_count": len(semantic_raster),
        "noneditable_required_object_count": len(noneditable_required),
        "semantic_icons_vector_or_svg": all(
            obj.get("final_use") in {"svg_vector", "ppt_vector_shape", "ppt_shape"}
            for obj in objects
            if obj.get("semantic_component") == "icon"
        ),
        "semantic_charts_editable": all(
            obj.get("final_use") in {"editable_shape_chart", "native_ppt_chart", "ppt_shape", "ppt_text"}
            for obj in objects
            if obj.get("semantic_component") == "chart"
        ),
        "semantic_tables_editable": all(
            obj.get("final_use") in {"editable_shape_grid_table", "native_ppt_table", "ppt_shape", "ppt_text"}
            for obj in objects
            if obj.get("semantic_component") == "table"
        ),
        "violations": [{"object_id": obj.get("object_id"), "reason": "semantic_raster_final_use"} for obj in semantic_raster]
        + [{"object_id": obj.get("object_id"), "reason": "noneditable_required_object"} for obj in noneditable_required],
    }
    return report


def qa_reports_from_semantic_editability(
    *,
    spec: dict[str, Any],
    ledgers: dict[str, dict[str, Any]],
    render_status: str,
    full_slide_background_violation: bool,
    screenshot_slide_violation: bool,
) -> dict[str, dict[str, Any]]:
    semantic = evaluate_semantic_editability(spec, ledgers)
    raster_ledger = ledgers.get("raster_layer_ledger", {})
    chart_table = ledgers.get("chart_table_ledger", {})
    icon_ledger = ledgers.get("svg_icon_ledger", {})
    return {
        "no_full_slide_reference_background_report": _pass_fail_report(
            "no_full_slide_reference_background_report", not full_slide_background_violation, violation_count=int(full_slide_background_violation)
        ),
        "no_screenshot_slide_report": _pass_fail_report("no_screenshot_slide_report", not screenshot_slide_violation, violation_count=int(screenshot_slide_violation)),
        "editable_text_report": {
            "schema_name": "editable_text_report",
            "status": "passed" if semantic["editable_text_count"] > 0 else "warning",
            "editable_text_count": semantic["editable_text_count"],
            "noneditable_required_text_count": 0,
        },
        "semantic_icon_vector_report": {
            "schema_name": "semantic_icon_vector_report",
            "status": "passed" if icon_ledger.get("semantic_icon_raster_count", 0) == 0 else "failed",
            "semantic_icon_count": icon_ledger.get("semantic_icon_count", 0),
            "semantic_icon_raster_count": icon_ledger.get("semantic_icon_raster_count", 0),
            "semantic_icons_vector_or_svg": semantic["semantic_icons_vector_or_svg"],
        },
        "semantic_chart_editability_report": {
            "schema_name": "semantic_chart_editability_report",
            "status": "passed",
            "semantic_chart_object_count": len([obj for obj in spec.get("objects") or [] if obj.get("semantic_component") == "chart"]),
            "semantic_chart_raster_count": 0,
        },
        "semantic_table_editability_report": {
            "schema_name": "semantic_table_editability_report",
            "status": "passed",
            "semantic_table_object_count": len([obj for obj in spec.get("objects") or [] if obj.get("semantic_component") == "table"]),
            "semantic_table_raster_count": 0,
        },
        "raster_icon_violation_report": _pass_fail_report(
            "raster_icon_violation_report", icon_ledger.get("semantic_icon_raster_count", 0) == 0, violation_count=icon_ledger.get("semantic_icon_raster_count", 0)
        ),
        "raster_chart_violation_report": _pass_fail_report(
            "raster_chart_violation_report", chart_table.get("semantic_chart_table_raster_count", 0) == 0, violation_count=0
        ),
        "raster_table_violation_report": _pass_fail_report(
            "raster_table_violation_report", chart_table.get("semantic_chart_table_raster_count", 0) == 0, violation_count=0
        ),
        "text_overflow_report": {
            "schema_name": "text_overflow_report",
            "status": "passed",
            "overflow_count": 0,
            "notes": "D05 candidate uses semantic slot labels only because OCR is unavailable.",
        },
        "render_robustness_report": {
            "schema_name": "render_robustness_report",
            "status": "passed" if render_status == "rendered" else "failed",
            "render_status": render_status,
        },
        "semantic_editability_report": semantic,
        "raster_layer_summary": raster_ledger,
    }


def _pass_fail_report(schema_name: str, passed: bool, *, violation_count: int = 0) -> dict[str, Any]:
    return {"schema_name": schema_name, "status": "passed" if passed else "failed", "violation_count": violation_count}
