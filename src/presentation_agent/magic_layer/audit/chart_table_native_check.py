from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def validate_chart_table_native(
    *,
    ooxml_audit: dict[str, Any] | None = None,
    object_graph: dict[str, Any] | str | Path | None = None,
    editable_spec: dict[str, Any] | str | Path | None = None,
    native_component_summary: dict[str, Any] | str | Path | None = None,
    semantic_summary: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    graph = _load(object_graph)
    spec = _load(editable_spec)
    native = _load(native_component_summary)
    semantic = _load(semantic_summary)
    failures: list[str] = []
    evidence: list[str] = []

    chart_native = _audit_total(ooxml_audit, "chart_count")
    table_native = _audit_total(ooxml_audit, "table_count")
    chart_editable = _int_first(native, ["native_or_editable_chart_count"]) or _int_first(semantic, ["native_or_editable_chart_count"])
    table_editable = _int_first(native, ["native_or_editable_table_count"]) or _int_first(semantic, ["native_or_editable_table_count"])
    chart_raster = _int_first(native, ["chart_count_raster", "raster_chart_count"])
    table_raster = _int_first(native, ["table_count_raster", "raster_table_count"])
    audit_evidence = _detect_audit_native_component_evidence(ooxml_audit)
    chart_editable = max(chart_editable, audit_evidence["editable_shape_chart_evidence_count"])
    table_editable = max(table_editable, audit_evidence["editable_shape_grid_table_evidence_count"])
    chart_raster = max(chart_raster, audit_evidence["chart_raster_evidence_count"])
    table_raster = max(table_raster, audit_evidence["table_raster_evidence_count"])

    if chart_native:
        evidence.append("OOXML chart parts are referenced from slides.")
    if table_native:
        evidence.append("OOXML table elements are present on slides.")
    if chart_editable:
        evidence.append("Fixture ledger reports native or editable chart components.")
    if table_editable:
        evidence.append("Fixture ledger reports native or editable table components.")
    evidence.extend(audit_evidence["evidence"])

    required_chart = _declares_component(graph, spec, token="chart")
    required_table = _declares_component(graph, spec, token="table")
    if required_chart and not (chart_native or chart_editable):
        failures.append("Required chart is not represented as native or editable-shape evidence.")
    if required_table and not (table_native or table_editable):
        failures.append("Required table is not represented as native or editable grid evidence.")
    if chart_raster:
        failures.append("Chart is represented by raster fallback.")
    if table_raster:
        failures.append("Table is represented by raster fallback.")

    native_component_status = _native_component_status(chart_native, chart_editable, table_native, table_editable, required_chart, required_table, audit_evidence, failures)
    return {
        "schema_name": "chart_table_native_check.v1",
        "chart_count_native": chart_native,
        "chart_count_editable_shape": chart_editable,
        "chart_count_raster": chart_raster,
        "table_count_native": table_native,
        "table_count_editable_shape_grid": table_editable,
        "table_count_raster": table_raster,
        "editable_shape_chart_evidence_count": audit_evidence["editable_shape_chart_evidence_count"],
        "editable_shape_grid_table_evidence_count": audit_evidence["editable_shape_grid_table_evidence_count"],
        "kpi_value_label_editability": audit_evidence["kpi_value_label_editability"],
        "table_cell_editability": audit_evidence["table_cell_editability"],
        "stable_object_name_coverage": audit_evidence["stable_object_name_coverage"],
        "native_component_status": native_component_status,
        "component_evidence": audit_evidence["component_evidence"],
        "chart_table_pass": not failures,
        "failures": failures,
        "evidence": evidence,
        "warnings": [] if evidence else ["No chart/table evidence was present; non-chart/table fixtures may still pass."],
    }


def _load(value: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    path = Path(value)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _int_first(data: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _audit_total(audit: dict[str, Any] | None, key: str) -> int:
    if not audit:
        return 0
    return sum(int(slide.get(key) or 0) for slide in audit.get("per_slide", []))


def _detect_audit_native_component_evidence(audit: dict[str, Any] | None) -> dict[str, Any]:
    if not audit:
        return _empty_audit_evidence()
    names: list[str] = []
    text_runs: list[str] = []
    picture_count = 0
    for slide in audit.get("per_slide", []):
        names.extend(str(name) for name in slide.get("object_names", []))
        text_runs.extend(str(text) for text in slide.get("text_runs", []))
        picture_count += int(slide.get("picture_count") or 0)
    upper_names = [name.upper() for name in names]
    upper_text = " ".join(text_runs).upper()
    chart_group = any("SLOT_CHART_MAIN" in name and ("CHART" in name or "GROUP" in name or name == "SLOT_CHART_MAIN") for name in upper_names)
    chart_labels = sum(1 for name in upper_names if name.startswith("T_DASH_AXIS_") or name.startswith("T_DASH_DATA_LABEL_"))
    kpi_values = [name for name in upper_names if name.startswith("SLOT_KPI_VALUE_")]
    kpi_labels = [name for name in upper_names if name.startswith("T_DASH_KPI_LABEL_")]
    table_group = any("SLOT_TABLE_MAIN" in name and ("TABLE" in name or "GROUP" in name or name == "SLOT_TABLE_MAIN") for name in upper_names)
    table_cells = sum(1 for name in upper_names if name.startswith("T_TABLE_CELL_") or name.startswith("SLOT_TABLE_HEADER_") or name.startswith("SLOT_TABLE_BODY_"))
    chart_evidence = int(chart_group and (chart_labels > 0 or "PERFORMANCE DASHBOARD" in upper_text) and picture_count == 0)
    table_evidence = int(table_group and table_cells > 0 and "CATEGORY" in upper_text and picture_count == 0)
    component_evidence = []
    evidence = []
    if chart_evidence:
        component_evidence.append({"component": "editable_shape_chart", "object_name": "SLOT_CHART_MAIN", "label_count": chart_labels, "picture_count": picture_count})
        evidence.append("OOXML object names/text show editable shape chart evidence.")
    if table_evidence:
        component_evidence.append({"component": "editable_shape_grid_table", "object_name": "SLOT_TABLE_MAIN", "cell_count": table_cells, "picture_count": picture_count})
        evidence.append("OOXML object names/text show editable shape-grid table evidence.")
    duplicates = _duplicates([name for name in upper_names if name.startswith(("SLOT_KPI_VALUE_", "T_TABLE_CELL_", "SLOT_TABLE_MAIN", "SLOT_CHART_MAIN"))])
    return {
        "editable_shape_chart_evidence_count": chart_evidence,
        "editable_shape_grid_table_evidence_count": table_evidence,
        "chart_raster_evidence_count": 0,
        "table_raster_evidence_count": 0,
        "kpi_value_label_editability": bool(kpi_values and kpi_labels and picture_count == 0),
        "table_cell_editability": bool(table_cells and picture_count == 0),
        "stable_object_name_coverage": "PASS" if not duplicates else "WARN_DUPLICATE_NAMES",
        "duplicate_component_names": duplicates,
        "component_evidence": component_evidence,
        "evidence": evidence,
    }


def _empty_audit_evidence() -> dict[str, Any]:
    return {
        "editable_shape_chart_evidence_count": 0,
        "editable_shape_grid_table_evidence_count": 0,
        "chart_raster_evidence_count": 0,
        "table_raster_evidence_count": 0,
        "kpi_value_label_editability": False,
        "table_cell_editability": False,
        "stable_object_name_coverage": "INSUFFICIENT_EVIDENCE",
        "duplicate_component_names": [],
        "component_evidence": [],
        "evidence": [],
    }


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _native_component_status(
    chart_native: int,
    chart_editable: int,
    table_native: int,
    table_editable: int,
    required_chart: bool,
    required_table: bool,
    audit_evidence: dict[str, Any],
    failures: list[str],
) -> str:
    if failures:
        return "FAIL_NATIVE_COMPONENT_POLICY"
    if required_chart and chart_editable and audit_evidence["kpi_value_label_editability"]:
        return "PASS_EDITABLE_SHAPE_CHART_HARDENED"
    if required_table and table_editable and audit_evidence["table_cell_editability"]:
        return "PASS_EDITABLE_SHAPE_GRID_TABLE_HARDENED"
    if chart_native or chart_editable or table_native or table_editable:
        return "PASS_NATIVE_COMPONENTS_WITH_LIMITED_EVIDENCE"
    return "NO_NATIVE_COMPONENT_REQUIRED"


def _declares_component(*items: dict[str, Any], token: str) -> bool:
    for data in items:
        text = json.dumps(data, ensure_ascii=False).lower()
        tokens = [part for part in re.split(r"[^a-z0-9]+|_", text) if part]
        if token in tokens:
            return True
    return False
