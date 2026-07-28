from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..backends.backend_selector import backend_selection_report, select_backend
from ..validators.compiled_pptx_smoke_validator import validate_compiled_minimal_pptx
from ..ooxml.openability_validator import run_powerpoint_open_only_check, validate_powerpoint_openability_static
from ...gates.pptx_native_validation_gate import run_pptx_native_validation_gate
from .compile_execution_report import build_compile_execution_report, sha256_file
from .compile_scope_guard import validate_compile_scope


OUTPUT_NAME = "controlled_minimal_editable_candidate.pptx"
C02B_OUTPUT_NAME = "controlled_minimal_editable_candidate_c02b.pptx"


def compile_controlled_minimal(
    bundle: dict[str, Any],
    out_dir: str | Path,
    *,
    bundle_path: str | Path | None = None,
    editable_spec_path: str | Path | None = None,
    allow_existing: bool = False,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / OUTPUT_NAME
    warnings: list[str] = []

    if output_path.exists() and not allow_existing:
        report = build_compile_execution_report(
            backend_selected="not_selected",
            bundle_path=bundle_path,
            input_bundle_hash=sha256_file(bundle_path) if bundle_path else None,
            editable_spec_hash=sha256_file(editable_spec_path) if editable_spec_path else None,
            output_path=output_path,
            expected_object_count=_object_count(bundle),
            blockers=["PPTX output already exists; C02 does not overwrite existing PPTX outputs."],
        )
        report["decision"] = "C02_FAIL_OUTPUT_GUARD"
        return report

    scope = validate_compile_scope(bundle, out, output_path)
    if not scope["allowed"]:
        report = build_compile_execution_report(
            backend_selected="not_selected",
            bundle_path=bundle_path,
            input_bundle_hash=sha256_file(bundle_path) if bundle_path else None,
            editable_spec_hash=sha256_file(editable_spec_path) if editable_spec_path else None,
            output_path=output_path,
            expected_object_count=_object_count(bundle),
            blockers=scope["blockers"],
        )
        report["decision"] = "C02_FAIL_COMPILE_SCOPE_GUARD"
        report["scope_guard"] = scope
        return report

    selection = select_backend(bundle)
    selection.backend.compile_minimal(bundle, output_path)
    report = build_compile_execution_report(
        backend_selected=selection.backend_name,
        bundle_path=bundle_path,
        input_bundle_hash=sha256_file(bundle_path) if bundle_path else None,
        editable_spec_hash=sha256_file(editable_spec_path) if editable_spec_path else None,
        output_path=output_path,
        expected_object_count=_object_count(bundle),
        warnings=warnings,
    )
    report["decision"] = "COMPILE_SUCCEEDED" if report["pptx_generated"] else "C02_FAIL_MINIMAL_COMPILE"
    report["scope_guard"] = scope
    report["backend_selection"] = selection.to_dict()
    return report


def compile_controlled_minimal_compatible(
    bundle: dict[str, Any],
    out_dir: str | Path,
    *,
    bundle_path: str | Path | None = None,
    editable_spec_path: str | Path | None = None,
    allow_existing: bool = False,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / C02B_OUTPUT_NAME

    if output_path.exists() and not allow_existing:
        report = build_compile_execution_report(
            backend_selected="not_selected",
            bundle_path=bundle_path,
            input_bundle_hash=sha256_file(bundle_path) if bundle_path else None,
            editable_spec_hash=sha256_file(editable_spec_path) if editable_spec_path else None,
            output_path=output_path,
            expected_object_count=_object_count(bundle),
            blockers=["PPTX output already exists; C02B does not overwrite existing PPTX outputs."],
        )
        report["decision"] = "C02B_FAIL_OUTPUT_GUARD"
        report["compatibility_patch_applied"] = False
        return report

    scope = validate_compile_scope(bundle, out, output_path)
    if not scope["allowed"]:
        report = build_compile_execution_report(
            backend_selected="not_selected",
            bundle_path=bundle_path,
            input_bundle_hash=sha256_file(bundle_path) if bundle_path else None,
            editable_spec_hash=sha256_file(editable_spec_path) if editable_spec_path else None,
            output_path=output_path,
            expected_object_count=_object_count(bundle),
            blockers=scope["blockers"],
        )
        report["decision"] = "C02B_FAIL_COMPILE_SCOPE_GUARD"
        report["scope_guard"] = scope
        report["compatibility_patch_applied"] = False
        return report

    selection = select_backend(bundle)
    selection.backend.compile_minimal(bundle, output_path)
    static_openability = validate_powerpoint_openability_static(output_path)
    report = build_compile_execution_report(
        backend_selected=selection.backend_name,
        bundle_path=bundle_path,
        input_bundle_hash=sha256_file(bundle_path) if bundle_path else None,
        editable_spec_hash=sha256_file(editable_spec_path) if editable_spec_path else None,
        output_path=output_path,
        expected_object_count=_object_count(bundle),
        warnings=static_openability.get("warnings", []),
        blockers=[] if static_openability.get("static_openability_pass") else ["Static PowerPoint openability preflight failed."],
    )
    report["decision"] = "COMPILE_SUCCEEDED" if report["pptx_generated"] else "C02B_FAIL_PATCHED_MINIMAL_COMPILE"
    report["scope_guard"] = scope
    report["backend_selection"] = selection.to_dict()
    report["compatibility_patch_applied"] = True
    report["static_openability_status"] = static_openability.get("decision")
    return report


def run_controlled_smoke_test(
    bundle: dict[str, Any],
    out_dir: str | Path,
    *,
    bundle_path: str | Path | None = None,
    editable_spec_path: str | Path | None = None,
    force_b03_failure: bool = False,
    allow_existing: bool = False,
) -> dict[str, Any]:
    compile_report = compile_controlled_minimal(
        bundle,
        out_dir,
        bundle_path=bundle_path,
        editable_spec_path=editable_spec_path,
        allow_existing=allow_existing,
    )
    output_path = Path(compile_report["output_path"])
    if not compile_report.get("pptx_generated"):
        return {
            "schema": "c02_controlled_smoke_test.v1",
            "decision": compile_report.get("decision", "C02_FAIL_MINIMAL_COMPILE"),
            "compile_report": compile_report,
            "b03_validation_ran": False,
            "product_pass": False,
            "pptx_generated": False,
            "render_generated": False,
        }

    smoke = validate_compiled_minimal_pptx(output_path)
    b03 = run_pptx_native_validation_gate(pptx=output_path)
    if force_b03_failure:
        b03 = dict(b03)
        b03["status"] = "FAIL"
        b03.setdefault("failures", []).append("Forced B03 failure for integration test.")

    b03_ok = b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"}
    smoke_ok = smoke.get("pass") is True
    decision = (
        "C02_PASS_WITH_LIMITED_BACKEND_READY_FOR_C03"
        if b03_ok and smoke_ok and compile_report.get("backend_selected") == "minimal_ooxml"
        else "C02_PASS_CONTROLLED_MINIMAL_PPTX_COMPILE_READY_FOR_C03_RENDER_REVIEW"
        if b03_ok and smoke_ok
        else "C02_FAIL_B03_OOXML_VALIDATION"
    )
    if force_b03_failure:
        decision = "C02_FAIL_B03_OOXML_VALIDATION"
    return {
        "schema": "c02_controlled_smoke_test.v1",
        "decision": decision,
        "compile_report": compile_report,
        "b03_validation_ran": True,
        "b03_gate_status": b03.get("status"),
        "b03_gate_report": b03,
        "smoke_validation": smoke,
        "product_pass": False,
        "pptx_generated": True,
        "render_generated": False,
    }


def run_controlled_compatibility_test(
    bundle: dict[str, Any],
    out_dir: str | Path,
    *,
    bundle_path: str | Path | None = None,
    editable_spec_path: str | Path | None = None,
    run_com_open_check: bool = False,
    allow_existing: bool = False,
) -> dict[str, Any]:
    compile_report = compile_controlled_minimal_compatible(
        bundle,
        out_dir,
        bundle_path=bundle_path,
        editable_spec_path=editable_spec_path,
        allow_existing=allow_existing,
    )
    output_path = Path(compile_report["output_path"])
    if not compile_report.get("pptx_generated"):
        return {
            "schema": "c02b_controlled_compatibility_test.v1",
            "decision": compile_report.get("decision", "C02B_FAIL_PATCHED_MINIMAL_COMPILE"),
            "compile_report": compile_report,
            "static_openability": {},
            "powerpoint_open_only": {},
            "b03_validation": {},
            "product_pass": False,
            "pptx_generated": False,
            "render_generated": False,
        }

    static = validate_powerpoint_openability_static(output_path)
    open_only = run_powerpoint_open_only_check(output_path, force_unavailable=not run_com_open_check)
    b03 = run_pptx_native_validation_gate(pptx=output_path)
    b03_ok = b03.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"}
    static_ok = static.get("static_openability_pass") is True
    com_status = open_only.get("openability_status")
    if static_ok and b03_ok and com_status == "POWERPOINT_OPENABLE":
        decision = "C02B_PASS_POWERPOINT_OPENABLE_READY_FOR_C03A_RENDER_RETRY"
    elif static_ok and b03_ok and com_status == "STATIC_OPENABILITY_PASS_COM_UNAVAILABLE":
        decision = "C02B_PASS_STATIC_OPENABILITY_BUT_COM_UNAVAILABLE_READY_FOR_C03A"
    elif not static_ok:
        decision = "C02B_FAIL_STATIC_OPENABILITY"
    elif not b03_ok:
        decision = "C02B_FAIL_B03_OOXML_VALIDATION"
    else:
        decision = "C02B_FAIL_POWERPOINT_OPEN_COMPATIBILITY"
    return {
        "schema": "c02b_controlled_compatibility_test.v1",
        "decision": decision,
        "compile_report": compile_report,
        "static_openability": static,
        "powerpoint_open_only": open_only,
        "b03_validation": b03,
        "product_pass": False,
        "pptx_generated": True,
        "render_generated": False,
    }


def load_bundle(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_backend_selection_report(bundle: dict[str, Any]) -> dict[str, Any]:
    return backend_selection_report(bundle)


def _object_count(bundle: dict[str, Any]) -> int:
    spec = bundle.get("editable_candidate_spec") if isinstance(bundle.get("editable_candidate_spec"), dict) else bundle
    return len([item for item in spec.get("objects", []) if isinstance(item, dict)])
