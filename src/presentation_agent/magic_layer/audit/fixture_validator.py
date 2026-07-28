from __future__ import annotations

from pathlib import Path
from typing import Any

from .chart_table_native_check import validate_chart_table_native
from .full_slide_raster_check import check_full_slide_raster
from .pptx_ooxml_audit import audit_pptx_package
from .semantic_editability_check import validate_semantic_editability
from .text_overflow_check import validate_text_overflow


def validate_fixture(fixture_path: str | Path, fixture_name: str | None = None) -> dict[str, Any]:
    folder = Path(fixture_path)
    name = fixture_name or folder.name
    if name == "e01_semantic_raster_fail":
        return _validate_e01(folder)
    if name == "e01b_single_reference_pass":
        return _validate_e01b(folder)
    if name == "e02_4core_pass":
        return _validate_e02(folder)
    if name == "canva_benchmark":
        return _validate_canva(folder)
    return {
        "fixture_name": name,
        "fixture_path": str(folder),
        "actual_status": "UNKNOWN_FIXTURE",
        "validation_scope_possible": "MISSING" if not folder.exists() else "UNKNOWN",
        "product_success_claim_allowed": False,
    }


def validate_fixture_root(fixtures_root: str | Path) -> dict[str, Any]:
    root = Path(fixtures_root)
    fixtures = [
        validate_fixture(root / "e01_semantic_raster_fail", "e01_semantic_raster_fail"),
        validate_fixture(root / "e01b_single_reference_pass", "e01b_single_reference_pass"),
        validate_fixture(root / "e02_4core_pass", "e02_4core_pass"),
        validate_fixture(root / "canva_benchmark", "canva_benchmark"),
    ]
    e01 = fixtures[0]
    e02 = fixtures[2]
    limitations = [
        fixture
        for fixture in fixtures
        if fixture.get("actual_status") in {"BLOCKED_MISSING_INPUT", "PARTIAL_NO_PPTX", "UNKNOWN_FIXTURE"}
    ]
    e01_failure_detected = bool(e01.get("expected_failure_detected"))
    pass_core = e01_failure_detected and e02.get("actual_status") in {"PASS", "PASS_WITH_LIMITATIONS"}
    return {
        "schema_name": "b03_fixture_check_report",
        "fixtures_root": str(root),
        "fixtures": fixtures,
        "expected_negative_fixture_detected": e01_failure_detected,
        "e02_bounded_scope_preserved": e02.get("e04_unlock_allowed") is False and e02.get("d08_unlock_allowed") is False,
        "overall_status": "PASS_WITH_FIXTURE_LIMITATIONS" if pass_core and limitations else "PASS" if pass_core else "FAIL",
        "limitations": limitations,
    }


def _validation_scope(folder: Path) -> str:
    if not folder.exists():
        return "MISSING"
    if not list(folder.rglob("*.pptx")):
        return "PARTIAL_NO_PPTX"
    if not list(folder.rglob("*ledger*.json")) and not list(folder.rglob("*ooxml*.json")):
        return "PARTIAL_NO_LEDGER"
    if not list(folder.rglob("*spec*.json")):
        return "PARTIAL_NO_SPEC"
    return "FULL"


def _validate_e01(folder: Path) -> dict[str, Any]:
    pptx = folder / "editable_candidate.pptx"
    audit = audit_pptx_package(pptx)
    full = check_full_slide_raster(audit)
    semantic = validate_semantic_editability(
        ooxml_audit=audit,
        object_graph=folder / "object_graph_v1.json",
        layer_manifest=folder / "layer_manifest_v5.json",
        semantic_slot_graph=folder / "semantic_slot_graph.json",
        native_reconstruction_plan=folder / "native_reconstruction_plan.json",
        editable_candidate_spec=folder / "editable_candidate_spec.json",
        existing_semantic_editability_ledger=folder / "pptx_semantic_editability_ledger.json",
        semantic_raster_violation_report=folder / "semantic_raster_violation_report.json",
        gate_report=folder / "canva_plus_gate_report.json",
    )
    actual = "FAIL" if not semantic["pass"] or not full["pass"] else "PASS"
    return {
        "schema_name": "b03_fixture_validation_result",
        "fixture_name": "e01_semantic_raster_fail",
        "fixture_path": str(folder),
        "expected_status": "FAIL",
        "expected_failure_class": "SEMANTIC_RASTER_OR_NATIVE_GATE",
        "actual_status": actual,
        "failure_class": semantic.get("failure_class"),
        "expected_failure_detected": actual == "FAIL",
        "validation_scope_possible": _validation_scope(folder),
        "product_success_claim_allowed": False,
        "full_slide_raster": full,
        "semantic_editability": semantic,
    }


def _validate_e01b(folder: Path) -> dict[str, Any]:
    pptx_files = list(folder.rglob("*.pptx")) if folder.exists() else []
    if not pptx_files:
        return {
            "schema_name": "b03_fixture_validation_result",
            "fixture_name": "e01b_single_reference_pass",
            "fixture_path": str(folder),
            "expected_status": "PASS_OR_PASS_WITH_LIMITATIONS",
            "actual_status": "BLOCKED_MISSING_INPUT",
            "validation_scope_possible": "PARTIAL_NO_PPTX" if folder.exists() else "MISSING",
            "scope": "SINGLE_REFERENCE_MAGIC_LAYER_PLUS_REGRESSION",
            "product_success_claim_allowed": False,
            "e03_unlock_allowed": False,
            "d08_unlock_allowed": False,
            "limitations": ["E01B compact fixture folder exists but contains no PPTX or ledger files."],
        }
    audit = audit_pptx_package(pptx_files[0])
    full = check_full_slide_raster(audit)
    semantic = validate_semantic_editability(
        ooxml_audit=audit,
        existing_semantic_editability_ledger=_first(folder, ["*editability_ledger*.json", "*ledger*.json"]),
        semantic_raster_violation_report=_first(folder, ["*semantic_raster_violation*.json"]),
    )
    status = "PASS" if full["pass"] and semantic["pass"] else "FAIL"
    if semantic.get("warnings"):
        status = "PASS_WITH_LIMITATIONS" if status == "PASS" else status
    return {
        "schema_name": "b03_fixture_validation_result",
        "fixture_name": "e01b_single_reference_pass",
        "fixture_path": str(folder),
        "expected_status": "PASS_OR_PASS_WITH_LIMITATIONS",
        "actual_status": status,
        "validation_scope_possible": _validation_scope(folder),
        "scope": "SINGLE_REFERENCE_MAGIC_LAYER_PLUS_REGRESSION",
        "product_success_claim_allowed": status in {"PASS", "PASS_WITH_LIMITATIONS"},
        "e03_unlock_allowed": False,
        "d08_unlock_allowed": False,
        "full_slide_raster": full,
        "semantic_editability": semantic,
    }


def _validate_e02(folder: Path) -> dict[str, Any]:
    pptx = folder / "editable_4core_template_masters_candidate.pptx"
    audit = audit_pptx_package(pptx)
    full = check_full_slide_raster(audit)
    semantic = validate_semantic_editability(
        ooxml_audit=audit,
        existing_semantic_editability_ledger=folder / "editable_4core_template_masters_candidate_editability_ledger.json",
    )
    chart_table = validate_chart_table_native(
        ooxml_audit=audit,
        native_component_summary=folder / "e02_native_component_summary.json",
        semantic_summary=folder / "e02_semantic_editability_summary.json",
    )
    overflow = validate_text_overflow(ooxml_audit=audit, semantic_ledger=folder / "e02_native_component_summary.json")
    pass_core = audit["exists"] and not audit["errors"] and full["pass"] and semantic["pass"] and chart_table["chart_table_pass"]
    status = "PASS_WITH_LIMITATIONS" if pass_core and overflow["strictness"] != "STRICT_LEDGER_BASED" else "PASS" if pass_core else "FAIL"
    return {
        "schema_name": "b03_fixture_validation_result",
        "fixture_name": "e02_4core_pass",
        "fixture_path": str(folder),
        "expected_status": "PASS_OR_PASS_WITH_LIMITATIONS",
        "actual_status": status,
        "validation_scope_possible": _validation_scope(folder),
        "scope": "FOUR_CORE_TEMPLATE_CONVERSION_REGRESSION",
        "expected_archetype_count": 4,
        "actual_archetype_count": len([path for path in (folder / "archetypes").iterdir() if path.is_dir()]) if (folder / "archetypes").is_dir() else 0,
        "product_success_claim_allowed": status in {"PASS", "PASS_WITH_LIMITATIONS"},
        "e03_unlock_allowed": False,
        "e04_unlock_allowed": False,
        "d08_unlock_allowed": False,
        "full_slide_raster": full,
        "semantic_editability": semantic,
        "chart_table_native": chart_table,
        "text_overflow": overflow,
    }


def _validate_canva(folder: Path) -> dict[str, Any]:
    pptx = folder / "assets/canva_magic_layer_output.pptx"
    audit = audit_pptx_package(pptx)
    return {
        "schema_name": "b03_fixture_validation_result",
        "fixture_name": "canva_benchmark",
        "fixture_path": str(folder),
        "expected_status": "BENCHMARK_ONLY",
        "actual_status": "BENCHMARK_ONLY_NOT_PRODUCT_PASS",
        "validation_scope_possible": _validation_scope(folder),
        "product_success_claim_allowed": False,
        "audit_summary": {
            "exists": audit["exists"],
            "slide_count": audit["slide_count"],
            "errors": audit["errors"],
        },
    }


def _first(folder: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        matches = list(folder.rglob(pattern))
        if matches:
            return matches[0]
    return None
