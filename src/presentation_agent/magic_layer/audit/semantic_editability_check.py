from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_semantic_editability(
    *,
    ooxml_audit: dict[str, Any] | None = None,
    object_graph: dict[str, Any] | str | Path | None = None,
    layer_manifest: dict[str, Any] | str | Path | None = None,
    semantic_slot_graph: dict[str, Any] | str | Path | None = None,
    native_reconstruction_plan: dict[str, Any] | str | Path | None = None,
    editable_candidate_spec: dict[str, Any] | str | Path | None = None,
    existing_semantic_editability_ledger: dict[str, Any] | str | Path | None = None,
    semantic_raster_violation_report: dict[str, Any] | str | Path | None = None,
    gate_report: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    graph = _load(object_graph)
    manifest = _load(layer_manifest)
    semantic_graph = _load(semantic_slot_graph)
    plan = _load(native_reconstruction_plan)
    spec = _load(editable_candidate_spec)
    ledger = _load(existing_semantic_editability_ledger)
    violation = _load(semantic_raster_violation_report)
    gate = _load(gate_report)

    failures: list[str] = []
    warnings: list[str] = []
    evidence = {
        "object_graph_loaded": bool(graph),
        "layer_manifest_loaded": bool(manifest),
        "semantic_slot_graph_loaded": bool(semantic_graph),
        "native_reconstruction_plan_loaded": bool(plan),
        "editable_candidate_spec_loaded": bool(spec),
        "semantic_ledger_loaded": bool(ledger),
        "semantic_raster_violation_report_loaded": bool(violation),
        "gate_report_loaded": bool(gate),
        "ooxml_audit_loaded": bool(ooxml_audit),
    }

    if ledger.get("report_only") is True:
        return _base_result(
            pass_value=False,
            status="BLOCKED_INSUFFICIENT_LEDGER",
            failure_class="REPORT_ONLY",
            failures=["Report-only PASS is not sufficient semantic editability evidence."],
            warnings=warnings,
            evidence=evidence,
        )

    semantic_text_expected = _count_semantic_text_expected(graph, semantic_graph, plan, spec)
    semantic_text_editable = _int_first(ledger, ["editable_text_count", "semantic_text_editable_count"])
    semantic_text_rasterized = _int_first(ledger, ["semantic_text_rasterized_count", "rasterized_text_count"])
    semantic_raster_count = max(
        _int_first(violation, ["semantic_raster_violation_count", "violation_count"]),
        _int_first(ledger, ["semantic_raster_violation_count"]),
        _int_first(spec, ["semantic_raster_final_use_count"]),
    )
    unknown_count = max(
        _int_first(manifest, ["unknown_content_bearing_count", "unknown_content_bearing_layer_count"]),
        _int_first(gate.get("candidate", {}) if isinstance(gate.get("candidate"), dict) else {}, ["unknown_content_bearing_layer_count"]),
        _int_first(gate, ["unknown_content_bearing_layer_count"]),
    )
    icon_expected = _count_role(graph, "icon") or _count_role(plan, "icon")
    icon_editable = _int_first(ledger, ["svg_icon_region_count", "semantic_vector_icon_count", "semantic_icon_vector_or_editable_count"])
    chart_expected = _count_role(graph, "chart") or _count_role(plan, "chart")
    chart_editable = _int_first(ledger, ["native_chart_table_region_count", "native_or_editable_chart_count"])
    table_expected = _count_role(graph, "table") or _count_role(plan, "table")
    table_editable = _int_first(ledger, ["native_or_editable_table_count"])
    panel_expected = _count_any_role(graph, ["card", "panel", "footer", "source"]) or _count_any_role(plan, ["card", "panel", "footer", "source"])
    panel_native = panel_expected

    gate_failed = gate.get("status") == "failed"
    if semantic_raster_count > 0:
        failures.append("Semantic raster violation count is greater than zero.")
        failure_class = "SEMANTIC_RASTER"
    elif semantic_text_rasterized > 0:
        failures.append("Semantic text is rasterized.")
        failure_class = "SEMANTIC_RASTER"
    elif unknown_count > 0:
        failures.append("Unknown content-bearing layer count is greater than zero.")
        failure_class = "UNKNOWN_CONTENT_BEARING"
    elif gate_failed:
        risks = gate.get("high_product_risks", [])
        failures.append("Semantic/native gate report failed; report-only or render-only success cannot be treated as product PASS.")
        if risks:
            failures.append("Gate risks: " + ", ".join(str(risk) for risk in risks))
        failure_class = "SEMANTIC_NATIVE_GATE_FAILED"
    else:
        failure_class = "NONE"

    if semantic_text_expected and semantic_text_editable and semantic_text_editable < semantic_text_expected:
        failures.append("Editable semantic text count is below expected semantic text count.")
        failure_class = "MISSING_SEMANTIC_TEXT"

    if not evidence["semantic_ledger_loaded"] and not evidence["ooxml_audit_loaded"] and not evidence["gate_report_loaded"]:
        warnings.append("No strict semantic ledger, OOXML audit, or gate report was provided.")

    return {
        "schema_name": "semantic_editability_check.v1",
        "semantic_text_expected_count": semantic_text_expected,
        "semantic_text_editable_count": semantic_text_editable,
        "semantic_text_rasterized_count": semantic_text_rasterized,
        "semantic_icon_expected_count": icon_expected,
        "semantic_icon_vector_or_editable_count": icon_editable,
        "semantic_icon_rasterized_count": _int_first(ledger, ["semantic_icon_rasterized_count"]),
        "semantic_chart_expected_count": chart_expected,
        "semantic_chart_native_or_editable_count": chart_editable,
        "semantic_chart_rasterized_count": _int_first(ledger, ["semantic_chart_rasterized_count"]),
        "semantic_table_expected_count": table_expected,
        "semantic_table_native_or_editable_count": table_editable,
        "semantic_table_rasterized_count": _int_first(ledger, ["semantic_table_rasterized_count"]),
        "card_panel_footer_source_expected_count": panel_expected,
        "card_panel_footer_source_native_count": panel_native,
        "unknown_content_bearing_count": unknown_count,
        "semantic_raster_violation_count": semantic_raster_count,
        "pass": not failures,
        "status": "PASS" if not failures else "FAIL",
        "failure_class": failure_class,
        "failures": failures,
        "warnings": warnings,
        "evidence": evidence,
    }


def _base_result(
    *,
    pass_value: bool,
    status: str,
    failure_class: str,
    failures: list[str],
    warnings: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_name": "semantic_editability_check.v1",
        "semantic_text_expected_count": 0,
        "semantic_text_editable_count": 0,
        "semantic_text_rasterized_count": 0,
        "semantic_icon_expected_count": 0,
        "semantic_icon_vector_or_editable_count": 0,
        "semantic_icon_rasterized_count": 0,
        "semantic_chart_expected_count": 0,
        "semantic_chart_native_or_editable_count": 0,
        "semantic_chart_rasterized_count": 0,
        "semantic_table_expected_count": 0,
        "semantic_table_native_or_editable_count": 0,
        "semantic_table_rasterized_count": 0,
        "card_panel_footer_source_expected_count": 0,
        "card_panel_footer_source_native_count": 0,
        "unknown_content_bearing_count": 0,
        "semantic_raster_violation_count": 0,
        "pass": pass_value,
        "status": status,
        "failure_class": failure_class,
        "failures": failures,
        "warnings": warnings,
        "evidence": evidence,
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


def _iter_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("nodes", "layers", "objects", "slots", "steps", "components"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _count_semantic_text_expected(*items: dict[str, Any]) -> int:
    count = 0
    for data in items:
        for record in _iter_records(data):
            role = str(record.get("semantic_role") or record.get("role") or record.get("layer_category") or "").lower()
            target = str(record.get("editability_target") or record.get("target_ppt_object_type") or "").lower()
            if "text" in role and ("text" in target or record.get("content_bearing")):
                count += 1
    return count


def _count_role(data: dict[str, Any], token: str) -> int:
    return sum(
        1
        for record in _iter_records(data)
        if token in str(record.get("semantic_role") or record.get("role") or record.get("layer_category") or "").lower()
    )


def _count_any_role(data: dict[str, Any], tokens: list[str]) -> int:
    return sum(
        1
        for record in _iter_records(data)
        if any(token in str(record.get("semantic_role") or record.get("role") or record.get("layer_category") or "").lower() for token in tokens)
    )
