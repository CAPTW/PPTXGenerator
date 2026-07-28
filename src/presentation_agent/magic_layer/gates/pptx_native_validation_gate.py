from __future__ import annotations

from pathlib import Path
from typing import Any

from ..audit.chart_table_native_check import validate_chart_table_native
from ..audit.full_slide_raster_check import check_full_slide_raster
from ..audit.pptx_ooxml_audit import audit_pptx_package
from ..audit.semantic_editability_check import validate_semantic_editability
from ..audit.text_overflow_check import validate_text_overflow


def run_pptx_native_validation_gate(
    *,
    pptx: str | Path,
    spec: str | Path | None = None,
    object_graph: str | Path | None = None,
    layer_manifest: str | Path | None = None,
    semantic_graph: str | Path | None = None,
    native_plan: str | Path | None = None,
    expected_ledger: str | Path | None = None,
    semantic_raster_report: str | Path | None = None,
    gate_report: str | Path | None = None,
    native_component_summary: str | Path | None = None,
    semantic_summary: str | Path | None = None,
) -> dict[str, Any]:
    pptx_path = Path(pptx)
    if not pptx_path.is_file():
        return {
            "schema_name": "pptx_native_validation_gate.v1",
            "status": "BLOCKED_MISSING_INPUT",
            "pptx_exists": False,
            "failures": ["PPTX input is missing."],
            "native_component_status": "BLOCKED_MISSING_INPUT",
            "semantic_raster_zero": False,
            "unknown_content_bearing_zero": False,
        }
    audit = audit_pptx_package(pptx_path)
    if audit["errors"]:
        return {
            "schema_name": "pptx_native_validation_gate.v1",
            "status": "ERROR",
            "pptx_exists": True,
            "ooxml_parse": False,
            "failures": audit["errors"],
            "ooxml_audit": audit,
            "native_component_status": "ERROR",
            "semantic_raster_zero": False,
            "unknown_content_bearing_zero": False,
        }
    raster = check_full_slide_raster(audit)
    semantic = validate_semantic_editability(
        ooxml_audit=audit,
        object_graph=object_graph,
        layer_manifest=layer_manifest,
        semantic_slot_graph=semantic_graph,
        native_reconstruction_plan=native_plan,
        editable_candidate_spec=spec,
        existing_semantic_editability_ledger=expected_ledger,
        semantic_raster_violation_report=semantic_raster_report,
        gate_report=gate_report,
    )
    chart_table = validate_chart_table_native(
        ooxml_audit=audit,
        object_graph=object_graph,
        editable_spec=spec,
        native_component_summary=native_component_summary,
        semantic_summary=semantic_summary,
    )
    overflow = validate_text_overflow(ooxml_audit=audit, semantic_ledger=expected_ledger)
    failures: list[str] = []
    if not raster["pass"]:
        failures.extend(raster["violations"])
    if not semantic["pass"]:
        failures.extend(semantic["failures"])
    if not chart_table["chart_table_pass"]:
        failures.extend(chart_table["failures"])
    if failures:
        status = "FAIL"
    elif overflow["strictness"] != "STRICT_LEDGER_BASED":
        status = "PASS_WITH_LIMITATIONS"
    else:
        status = "PASS"
    return {
        "schema_name": "pptx_native_validation_gate.v1",
        "status": status,
        "pptx_exists": True,
        "ooxml_parse": True,
        "no_full_slide_raster": raster["full_slide_raster_count"] == 0,
        "no_screenshot_slide": raster["screenshot_like_count"] == 0,
        "semantic_editability": semantic["pass"],
        "chart_table_native_editability": chart_table["chart_table_pass"],
        "unknown_content_bearing_zero": semantic["unknown_content_bearing_count"] == 0,
        "semantic_raster_zero": semantic["semantic_raster_violation_count"] == 0,
        "text_overflow_policy": overflow["text_overflow_status"],
        "object_slot_name_coverage": "LEDGER_DEPENDENT",
        "native_component_status": chart_table.get("native_component_status"),
        "native_component_evidence": chart_table.get("component_evidence", []),
        "protected_artifact_integrity": "NOT_CHECKED_BY_GATE",
        "registry_claim_scope": "LOCAL_VALIDATION_ONLY",
        "failures": failures,
        "ooxml_audit": audit,
        "full_slide_raster": raster,
        "semantic": semantic,
        "chart_table": chart_table,
        "text_overflow": overflow,
    }


def discover_artifact_group_inputs(folder: str | Path) -> dict[str, Path | None]:
    root = Path(folder)
    pptx = _first(root, ["*.pptx"])
    return {
        "pptx": pptx,
        "spec": _first(root, ["*spec*.json", "*native_reconstruction_plan*.json"]),
        "object_graph": _first(root, ["*object_graph*.json"]),
        "layer_manifest": _first(root, ["*layer_manifest*.json"]),
        "semantic_graph": _first(root, ["*semantic_slot_graph*.json", "*semantic_graph*.json"]),
        "native_plan": _first(root, ["*native_reconstruction_plan*.json", "*native_plan*.json"]),
        "expected_ledger": _first(root, ["*editability_ledger*.json", "*semantic_editability_ledger*.json", "*ledger*.json"]),
        "semantic_raster_report": _first(root, ["*semantic_raster_violation*.json"]),
        "gate_report": _first(root, ["*gate_report*.json", "*canva_plus_gate_report*.json"]),
        "native_component_summary": _first(root, ["*native_component_summary*.json"]),
        "semantic_summary": _first(root, ["*semantic_editability_summary*.json"]),
    }


def _first(root: Path, patterns: list[str]) -> Path | None:
    if not root.exists():
        return None
    for pattern in patterns:
        matches = list(root.rglob(pattern))
        if matches:
            return matches[0]
    return None
