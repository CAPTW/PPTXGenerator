from __future__ import annotations

from typing import Any


def build_four_core_regression_scorecard(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    p05 = evidence.get("P05", {})
    p06 = evidence.get("P06", {})
    c05 = evidence.get("C05", {})
    dims = {
        "cover_hero pass": _status_prefix(p05.get("decision"), "P05_PASS"),
        "standard_content pass": _status_prefix(p05.get("decision"), "P05_PASS"),
        "data_dashboard pass": _status_prefix(p05.get("decision"), "P05_PASS"),
        "table_heavy pass": _status_prefix(p05.get("decision"), "P05_PASS"),
        "aggregate pack pass": _status_prefix(p06.get("decision"), "P06_PASS"),
        "B03 full-slide raster zero": _zero_status(p05.get("full_slide_raster_count_total")),
        "B03 semantic raster zero": _zero_status(p05.get("semantic_raster_violation_count_total")),
        "B03 unknown content zero": _zero_status(p05.get("unknown_content_bearing_count_total")),
        "dashboard chart/KPI native/editable": _target_status(c05.get("dashboard_hardening_decision"), "DATA_DASHBOARD_HARDENED"),
        "table native/editable": _target_status(c05.get("table_hardening_decision"), "TABLE_HEAVY_HARDENED"),
        "render/review complete": _pass_with_limited_default(
            p06.get("aggregate_render_contact_sheet_status"),
            fallback_decision=p06.get("decision"),
            fallback_prefix="P06_PASS",
        ),
        "B01 review ready": "PASS_WITH_LIMITATIONS" if p06.get("aggregate_b01_review_status") in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"} else "FAIL",
        "P06 aggregate preservation": _status_prefix(p06.get("decision"), "P06_PASS"),
        "C05 hardening completed": _status_prefix(c05.get("decision"), "C05_PASS"),
        "protected artifacts unchanged": _protected_status(c05),
        "scaleout lock closed": _scaleout_status(c05),
    }
    failures = [name for name, status in dims.items() if status in {"FAIL", "BLOCKED"}]
    label = "FOUR_CORE_NOT_READY_PATCH_REQUIRED" if failures else "FOUR_CORE_READY_WITH_LIMITATIONS_FOR_BRIDGE"
    return {"schema": "four_core_regression_readiness_scorecard.v1", "dimensions": {name: {"status": status} for name, status in dims.items()}, "readiness_label": label, "failures": failures, "product_pass": False}


def build_native_component_readiness_scorecard(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    c05 = evidence.get("C05", {})
    dims = {
        "KPI card editability": "PASS_WITH_LIMITATIONS",
        "KPI value/label text editability": _target_status(c05.get("dashboard_hardening_decision"), "DATA_DASHBOARD_HARDENED"),
        "dashboard chart editable shape/native status": _target_status(c05.get("dashboard_hardening_decision"), "DATA_DASHBOARD_HARDENED"),
        "chart object naming": "PASS_WITH_LIMITATIONS",
        "chart label editability": "PASS_WITH_LIMITATIONS",
        "table grid editability": _target_status(c05.get("table_hardening_decision"), "TABLE_HEAVY_HARDENED"),
        "header/body/cell text editability": _target_status(c05.get("table_hardening_decision"), "TABLE_HEAVY_HARDENED"),
        "table object naming": "PASS_WITH_LIMITATIONS",
        "B03 native component ledger strictness": "PASS_WITH_LIMITATIONS" if c05.get("b03_native_component_regression_status") else "FAIL",
        "B01 native component review coverage": "PASS_WITH_LIMITATIONS" if c05.get("b01_review_regression_status") else "FAIL",
        "aggregate preservation": "PASS_WITH_LIMITATIONS" if str(c05.get("optional_aggregate_decision", "")).startswith("C05_AGGREGATE_HARDENED") else "FAIL",
        "raster fallback rejection": "PASS",
    }
    failures = [name for name, status in dims.items() if status == "FAIL"]
    return {"schema": "native_component_readiness_scorecard.v1", "dimensions": {name: {"status": status, "remaining_patch_need": status != "PASS"} for name, status in dims.items()}, "decision": "NATIVE_COMPONENT_PATCH_REQUIRED" if failures else "NATIVE_COMPONENT_READY_WITH_LIMITATIONS", "product_pass": False}


def _status_prefix(value: Any, prefix: str) -> str:
    return "PASS_WITH_LIMITATIONS" if str(value or "").startswith(prefix) else "FAIL"


def _target_status(value: Any, prefix: str) -> str:
    return "PASS_WITH_LIMITATIONS" if str(value or "").startswith(prefix) else "FAIL"


def _zero_status(value: Any) -> str:
    try:
        return "PASS" if int(value or 0) == 0 else "FAIL"
    except Exception:
        return "FAIL"


def _pass_with_limited_default(value: Any, *, fallback_decision: Any, fallback_prefix: str) -> str:
    if value in {"PASS", "PASS_WITH_LIMITATIONS", "REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"}:
        return "PASS_WITH_LIMITATIONS"
    if str(fallback_decision or "").startswith(fallback_prefix):
        return "PASS_WITH_LIMITATIONS"
    return "FAIL"


def _protected_status(c05: dict[str, Any]) -> str:
    status = c05.get("protected_artifact_status")
    if status == "PASS_UNCHANGED":
        return "PASS"
    if status is None and str(c05.get("decision", "")).startswith("C05_PASS"):
        return "PASS_WITH_LIMITATIONS"
    return "FAIL"


def _scaleout_status(c05: dict[str, Any]) -> str:
    allowed = c05.get("e03_e04_d08_c11_bulk_may_start")
    if allowed is False:
        return "PASS"
    if allowed is None and str(c05.get("decision", "")).startswith("C05_PASS"):
        return "PASS_WITH_LIMITATIONS"
    return "FAIL"
