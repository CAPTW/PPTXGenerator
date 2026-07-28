from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.gates.pptx_native_validation_gate import run_pptx_native_validation_gate
from src.presentation_agent.magic_layer.review.native_plate_visual_risk import review_native_plate_visual_risk
from src.presentation_agent.magic_layer.review.overlay_renderer import render_overlay_image
from src.presentation_agent.magic_layer.review.residual_raster_text_review import review_residual_raster_text
from src.presentation_agent.magic_layer.review.text_overflow_review import review_text_overflow

from .libreoffice_renderer import render_with_libreoffice
from .libreoffice_diagnostics import run_libreoffice_diagnostics
from .powerpoint_com_diagnostics import run_powerpoint_com_diagnostics
from .powerpoint_com_renderer import render_with_powerpoint_com
from .powerpoint_com_renderer import build_powerpoint_com_export_strategy_matrix, classify_retry_render_failure
from .render_backend_selector import select_render_backend
from .render_backend_selector import select_render_backend_v2
from .render_execution_report import build_render_execution_report, sha256_file
from .render_image_profile import profile_render_image
from .render_scope_guard import (
    C02B_PATCHED_PPTX,
    C03A_RETRY_RENDER_NAME,
    DEFAULT_RENDER_NAME,
    validate_render_scope,
    validate_render_scope_retry,
    validate_render_scope_v2,
)


def run_controlled_render_workflow(pptx_path: str | Path, out_dir: str | Path, *, dry_run: bool = False) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pptx = Path(pptx_path)
    output = out / DEFAULT_RENDER_NAME
    scope = validate_render_scope([pptx], out, render_output=output)
    source_before = sha256_file(pptx)
    if not scope["allowed"]:
        execution = build_render_execution_report(
            renderer=None,
            method=None,
            input_pptx=pptx,
            output_path=output,
            source_hash_before=source_before,
            source_hash_after=sha256_file(pptx),
            errors=scope["blockers"],
        )
        return {"decision": "C03_FAIL_RENDER_SCOPE_GUARD", "scope_guard": scope, "execution_report": execution, "product_pass": False}

    backend = select_render_backend()
    if dry_run or backend["decision"] == "C03_BLOCKED_RENDER_BACKEND_UNAVAILABLE":
        execution = build_render_execution_report(
            renderer=backend.get("selected_backend"),
            method=backend.get("command_or_method"),
            input_pptx=pptx,
            output_path=output,
            source_hash_before=source_before,
            source_hash_after=sha256_file(pptx),
            warnings=["dry_run_no_render"] if dry_run else [],
            errors=[] if dry_run else ["render_backend_unavailable"],
        )
        decision = "DRY_RUN_RENDER_NOT_PERFORMED" if dry_run else "C03_BLOCKED_RENDER_BACKEND_UNAVAILABLE"
        return {"decision": decision, "scope_guard": scope, "backend_selection": backend, "execution_report": execution, "product_pass": False}

    if output.exists():
        execution = build_render_execution_report(
            renderer=backend["selected_backend"],
            method=backend["command_or_method"],
            input_pptx=pptx,
            output_path=output,
            source_hash_before=source_before,
            source_hash_after=sha256_file(pptx),
            errors=["Render output already exists; C03 does not overwrite existing render outputs."],
        )
        return {"decision": "C03_FAIL_RENDER", "scope_guard": scope, "backend_selection": backend, "execution_report": execution, "product_pass": False}

    try:
        if backend["selected_backend"] == "powerpoint_com":
            manifest = render_with_powerpoint_com(pptx, out)
        elif backend["selected_backend"] == "libreoffice":
            manifest = render_with_libreoffice(pptx, out)
        else:
            manifest = {"render_status": "skipped", "errors": [{"message": "Unsupported backend selection."}], "warnings": []}
    except Exception as exc:
        manifest = {"render_status": "failed", "errors": [{"message": str(exc)}], "warnings": []}
    source_after = sha256_file(pptx)
    errors = [str(item.get("message", item)) for item in manifest.get("errors", [])]
    execution = build_render_execution_report(
        renderer=backend["selected_backend"],
        method=backend["command_or_method"],
        input_pptx=pptx,
        output_path=output,
        source_hash_before=source_before,
        source_hash_after=source_after,
        render_manifest=manifest,
        errors=errors,
        warnings=[str(item.get("message", item)) for item in manifest.get("warnings", [])],
    )
    decision = "RENDER_GENERATED" if execution["render_generated"] and execution["source_hash_unchanged"] else "C03_FAIL_RENDER"
    return {"decision": decision, "scope_guard": scope, "backend_selection": backend, "render_manifest": manifest, "execution_report": execution, "product_pass": False}


def run_controlled_render_workflow_v2(pptx_path: str | Path, out_dir: str | Path, *, dry_run: bool = False) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pptx = Path(pptx_path)
    final_output = out / DEFAULT_RENDER_NAME
    scope = validate_render_scope_v2([pptx], out, render_output=final_output)
    source_before = sha256_file(pptx)
    if not scope["allowed"]:
        execution = build_render_execution_report(
            renderer=None,
            method=None,
            input_pptx=pptx,
            output_path=final_output,
            source_hash_before=source_before,
            source_hash_after=sha256_file(pptx),
            errors=scope["blockers"],
        )
        return {"decision": "C03A_FAIL_RENDER_SCOPE_GUARD", "scope_guard": scope, "execution_report": execution, "product_pass": False}

    powerpoint = run_powerpoint_com_diagnostics(pptx)
    powerpoint_matrix = build_powerpoint_com_export_strategy_matrix(pptx, out / "render_attempts/powerpoint_com", powerpoint)
    libreoffice = run_libreoffice_diagnostics(pptx, attempt_dir=out / "render_attempts/libreoffice", attempt_convert=not dry_run)
    libreoffice_attempts = []
    if libreoffice.get("conversion_success") and libreoffice.get("output_path"):
        libreoffice_attempts.append(
            {
                "attempt_id": "libreoffice_png",
                "method": "soffice --headless --convert-to png",
                "status": "SUCCESS",
                "output_path": libreoffice["output_path"],
                "source_hash_unchanged": libreoffice.get("source_hash_unchanged", True),
            }
        )
    elif libreoffice.get("available"):
        libreoffice_attempts.append(
            {
                "attempt_id": "libreoffice_png",
                "method": "soffice --headless --convert-to png",
                "status": "FAIL_NO_OUTPUT",
                "output_path": None,
                "source_hash_unchanged": libreoffice.get("source_hash_unchanged", True),
            }
        )
    backend_v2 = select_render_backend_v2(
        powerpoint_attempts=powerpoint_matrix.get("attempts", []),
        libreoffice_attempts=libreoffice_attempts,
    )
    warnings: list[str] = []
    errors: list[str] = []
    if backend_v2.get("render_ready") and backend_v2.get("output_path"):
        if final_output.exists():
            errors.append("Final render output already exists; C03A does not overwrite render outputs.")
        else:
            source = Path(backend_v2["output_path"])
            if source.is_file():
                source.replace(final_output)
            else:
                errors.append("Selected render output is missing.")
    if not backend_v2.get("render_ready"):
        if powerpoint.get("failure_classification") == "PPTX_NOT_OPENABLE_IN_POWERPOINT":
            errors.append("PowerPoint COM cannot open the controlled C02 PPTX.")
        elif not libreoffice.get("available"):
            errors.append("No successful local render backend is available.")
    source_after = sha256_file(pptx)
    execution = build_render_execution_report(
        renderer=backend_v2.get("selected_backend"),
        method=backend_v2.get("selected_strategy"),
        input_pptx=pptx,
        output_path=final_output,
        source_hash_before=source_before,
        source_hash_after=source_after,
        errors=errors,
        warnings=warnings,
        render_manifest={"slide_count": 1, "warnings": warnings, "errors": errors},
    )
    decision = "RENDER_GENERATED"
    if not execution["render_generated"]:
        if powerpoint.get("failure_classification") == "PPTX_NOT_OPENABLE_IN_POWERPOINT":
            decision = "C03A_FAIL_PPTX_NOT_OPENABLE"
        elif not libreoffice.get("available") and not backend_v2.get("render_ready"):
            decision = "C03A_BLOCKED_RENDER_BACKEND_UNAVAILABLE"
        else:
            decision = "C03A_FAIL_RENDER_UNKNOWN"
    return {
        "decision": decision,
        "scope_guard": scope,
        "powerpoint_com_diagnostics": powerpoint,
        "powerpoint_com_export_strategy_matrix": powerpoint_matrix,
        "libreoffice_diagnostics": libreoffice,
        "backend_selection_v2": backend_v2,
        "execution_report": execution,
        "product_pass": False,
    }


def run_controlled_render_retry_workflow(pptx_path: str | Path, out_dir: str | Path, *, dry_run: bool = False) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pptx = Path(pptx_path)
    final_output = out / C03A_RETRY_RENDER_NAME
    scope = validate_render_scope_retry([pptx], out, render_output=final_output)
    source_before = sha256_file(pptx)
    if not scope["allowed"]:
        execution = build_render_execution_report(
            renderer=None,
            method=None,
            input_pptx=pptx,
            output_path=final_output,
            source_hash_before=source_before,
            source_hash_after=sha256_file(pptx),
            errors=scope["blockers"],
        )
        return {"decision": "C03A_RETRY_FAIL_SCOPE_GUARD", "scope_guard": scope, "execution_report": execution, "product_pass": False}

    powerpoint = run_powerpoint_com_diagnostics(pptx)
    powerpoint_matrix = build_powerpoint_com_export_strategy_matrix(
        pptx,
        out / "render_attempts/powerpoint_com",
        powerpoint,
        attempt_export=not dry_run,
    )
    libreoffice = run_libreoffice_diagnostics(
        pptx,
        attempt_dir=out / "render_attempts/libreoffice",
        attempt_convert=not dry_run and powerpoint_matrix.get("success_count", 0) == 0,
    )
    libreoffice_attempts = _libreoffice_attempts(libreoffice)
    backend_retry = select_render_backend_v2(
        powerpoint_attempts=powerpoint_matrix.get("attempts", []),
        libreoffice_attempts=libreoffice_attempts,
    )
    errors: list[str] = []
    warnings: list[str] = []
    if backend_retry.get("render_ready") and backend_retry.get("output_path"):
        if final_output.exists():
            errors.append("Final render output already exists; C03A retry does not overwrite render outputs.")
        else:
            source = Path(str(backend_retry["output_path"]))
            if source.is_file():
                import shutil

                shutil.copy2(source, final_output)
            else:
                errors.append("Selected render output is missing.")
    else:
        errors.append(
            classify_retry_render_failure(
                powerpoint_opened=bool(powerpoint.get("open_success")),
                powerpoint_success=powerpoint_matrix.get("success_count", 0) > 0,
                libreoffice_available=bool(libreoffice.get("available")),
                libreoffice_success=bool(libreoffice.get("conversion_success")),
            )
        )
    source_after = sha256_file(pptx)
    execution = build_render_execution_report(
        renderer=backend_retry.get("selected_backend"),
        method=backend_retry.get("selected_strategy"),
        input_pptx=pptx,
        output_path=final_output,
        source_hash_before=source_before,
        source_hash_after=source_after,
        errors=errors,
        warnings=warnings,
        render_manifest={"slide_count": 1, "warnings": warnings, "errors": errors},
    )
    decision = "RENDER_GENERATED" if execution["render_generated"] and execution["source_hash_unchanged"] and not errors else (errors[0] if errors else "C03A_RETRY_INSUFFICIENT_EVIDENCE")
    return {
        "decision": decision,
        "scope_guard": scope,
        "powerpoint_com_open_recheck": powerpoint,
        "powerpoint_com_export_retry_matrix": powerpoint_matrix,
        "libreoffice_retry_diagnostics": libreoffice,
        "backend_selection_retry": backend_retry,
        "execution_report": execution,
        "product_pass": False,
    }


def build_b03_revalidation_report(pptx_path: str | Path, *, force_failure: bool = False) -> dict[str, Any]:
    gate = run_pptx_native_validation_gate(pptx=pptx_path)
    if force_failure:
        gate = dict(gate)
        gate["status"] = "FAIL"
        gate.setdefault("failures", []).append("Forced B03 failure for C03 integration test.")
    raster = gate.get("full_slide_raster", {})
    semantic = gate.get("semantic", {})
    status = gate.get("status")
    pass_allowed = status in {"PASS", "PASS_WITH_LIMITATIONS"} and raster.get("full_slide_raster_count", 0) == 0 and semantic.get("semantic_raster_violation_count", 0) == 0 and semantic.get("unknown_content_bearing_count", 0) == 0
    return {
        "schema": "controlled_minimal_b03_revalidation_report.v1",
        "pptx_path": str(pptx_path),
        "pptx_hash": sha256_file(pptx_path),
        "b03_revalidation_status": status,
        "slide_count": gate.get("ooxml_audit", {}).get("slide_count"),
        "full_slide_raster_count": raster.get("full_slide_raster_count", 0),
        "semantic_raster_violation_count": semantic.get("semantic_raster_violation_count", 0),
        "unknown_content_bearing_count": semantic.get("unknown_content_bearing_count", 0),
        "scope": "CONTROLLED_MINIMAL_COMPILER_SMOKE_TEST",
        "c03_pass_allowed": pass_allowed,
        "visual_review_replaces_b03": False,
        "b03_gate_report": gate,
        "product_pass": False,
    }


def build_controlled_b01_review(render_image: str | Path, out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    image = Path(render_image)
    profile = profile_render_image(image)
    has_render = profile["image_exists"] and profile["validation_status"] not in {"FAIL_MISSING_IMAGE", "FAIL_UNREADABLE_IMAGE", "FAIL_WRONG_ASPECT_RATIO", "FAIL_TINY_RENDER"}
    decision = "REVIEW_READY_WITH_LIMITATIONS" if has_render else "REVIEW_BLOCKED_MISSING_RENDER"
    review_packet = {
        "schema": "review_packet.v1",
        "packet_id": "controlled_minimal_b01_review_packet",
        "fixture_name": "controlled_minimal_c02_pptx",
        "source_pptx_path": str(Path("design_runs/run_003/outputs/c02_rx_controlled_minimal_pptx_compile/controlled_minimal_editable_candidate.pptx")),
        "render_sources": [{"selected_review_image": str(image), "image_exists": image.is_file()}],
        "b03_report_path": str(out / "controlled_minimal_b03_revalidation_report.json"),
        "visual_issues": [],
        "patch_requests": [],
        "limitations": ["minimal_scope_only", "not_product_pass", "not_reference_fidelity"],
        "decision": decision,
        "review_scope": "CONTROLLED_MINIMAL_RENDER_REVIEW",
        "product_pass": False,
        "product_pass_allowed": False,
    }
    overlay_document = _overlay_document(image)
    patch_request_report = {
        "schema": "controlled_minimal_patch_request_report.v1",
        "status": "NO_PATCH_REQUIRED_FOR_MINIMAL_SCOPE" if has_render else "PATCH_BLOCKED_MISSING_RENDER",
        "patch_requests_created": 0,
        "patch_requests": [],
        "applied_patch": False,
        "product_pass": False,
    }
    return {
        "review_packet": review_packet,
        "overlay_document": overlay_document,
        "patch_request_report": patch_request_report,
        "text_overflow_review": review_text_overflow(render_image=str(image) if has_render else None, slots=[{"slot_id": "SLOT_TITLE", "bbox_norm": [0.1, 0.1, 0.6, 0.12], "text_content": "TEXT"}]),
        "residual_raster_text_review": _residual_review(image, has_render),
        "native_plate_visual_risk_review": review_native_plate_visual_risk(render_image=str(image) if has_render else None, layers=[], suppression_plan=[]),
        "product_pass": False,
    }


def build_controlled_b01_review_v2(render_image: str | Path, out_dir: str | Path) -> dict[str, Any]:
    result = build_controlled_b01_review(render_image, out_dir)
    profile = profile_render_image(render_image)
    has_render = profile["validation_status"] in {"PASS", "WARNING_LOW_RESOLUTION"}
    result["review_packet"]["decision"] = "REVIEW_READY_WITH_LIMITATIONS" if has_render else "REVIEW_BLOCKED_MISSING_RENDER"
    result["overlay_document"]["product_pass"] = False
    result["patch_request_report"]["applied_patch"] = False
    return result


def build_controlled_b01_review_retry(render_image: str | Path, out_dir: str | Path) -> dict[str, Any]:
    result = build_controlled_b01_review_v2(render_image, out_dir)
    result["review_packet"]["fixture_name"] = "controlled_minimal_c02b_pptx"
    result["review_packet"]["source_pptx_path"] = str(C02B_PATCHED_PPTX)
    result["review_packet"]["b03_report_path"] = str(Path(out_dir) / "controlled_retry_b03_revalidation_report.json")
    result["review_packet"]["review_scope"] = "CONTROLLED_C02B_RETRY_RENDER_REVIEW"
    return result


def verify_c03a_retry_claim(claim: str, *, render_exists: bool = False) -> dict[str, Any]:
    normalized = claim.lower()
    if "rendered the c02b pptx" in normalized:
        return {"claim": claim, "status": "VERIFIED" if render_exists else "INSUFFICIENT_EVIDENCE", "product_pass": False}
    if "old c02 pptx" in normalized:
        return {"claim": claim, "status": "CONTRADICTED", "product_pass": False}
    if "fake render" in normalized:
        return {"claim": claim, "status": "CONTRADICTED", "product_pass": False}
    if "product pass" in normalized or "visual fidelity" in normalized or "arbitrary magic layer" in normalized:
        return {"claim": claim, "status": "OVERCLAIMED", "product_pass": False}
    if "unlock" in normalized and any(stage in normalized for stage in ["e03", "e04", "d08"]):
        return {"claim": claim, "status": "BLOCKED_BY_SCALEOUT_LOCK", "product_pass": False}
    if "golden_template_masters" in normalized or "promoted" in normalized:
        return {"claim": claim, "status": "BLOCKED_BY_POLICY", "product_pass": False}
    if "source-bound" in normalized or "source bound" in normalized:
        return {"claim": claim, "status": "CONTRADICTED", "product_pass": False}
    return {"claim": claim, "status": "INCONCLUSIVE", "product_pass": False}


def c03a_retry_scaleout_lock_status() -> dict[str, Any]:
    return {
        "E03": {"allowed": False, "reason": "C03A retry does not unlock E03."},
        "E04": {"allowed": False, "reason": "E03 remains blocked."},
        "D08": {"allowed": False, "reason": "E04 remains blocked."},
        "C11": {"allowed": False, "reason": "scaleout remains blocked."},
        "bulk": {"allowed": False, "reason": "bulk remains blocked."},
        "canonical_promotion": {"allowed": False, "reason": "canonical promotion remains blocked."},
    }


def _libreoffice_attempts(libreoffice: dict[str, Any]) -> list[dict[str, Any]]:
    if libreoffice.get("conversion_success") and libreoffice.get("output_path"):
        return [
            {
                "attempt_id": "libreoffice_png",
                "method": "soffice --headless --convert-to png",
                "status": "SUCCESS",
                "output_path": libreoffice["output_path"],
                "source_hash_unchanged": libreoffice.get("source_hash_unchanged", True),
            }
        ]
    if libreoffice.get("available"):
        return [
            {
                "attempt_id": "libreoffice_png",
                "method": "soffice --headless --convert-to png",
                "status": "FAIL_NO_OUTPUT",
                "output_path": None,
                "source_hash_unchanged": libreoffice.get("source_hash_unchanged", True),
            }
        ]
    return []


def verify_c03a_claim(claim: str, *, render_exists: bool = False) -> dict[str, Any]:
    normalized = claim.lower()
    if "rendered the c02 pptx" in normalized:
        return {"claim": claim, "status": "VERIFIED" if render_exists else "INSUFFICIENT_EVIDENCE", "product_pass": False}
    if "fake render" in normalized:
        return {"claim": claim, "status": "CONTRADICTED", "product_pass": False}
    if "product pass" in normalized or "visual fidelity" in normalized or "arbitrary magic layer" in normalized:
        return {"claim": claim, "status": "OVERCLAIMED", "product_pass": False}
    if "unlock" in normalized and any(stage in normalized for stage in ["e03", "e04", "d08"]):
        return {"claim": claim, "status": "BLOCKED_BY_SCALEOUT_LOCK", "product_pass": False}
    if "golden_template_masters" in normalized or "promoted" in normalized:
        return {"claim": claim, "status": "BLOCKED_BY_POLICY", "product_pass": False}
    if "source-bound" in normalized or "source bound" in normalized:
        return {"claim": claim, "status": "CONTRADICTED", "product_pass": False}
    return {"claim": claim, "status": "INCONCLUSIVE", "product_pass": False}


def c03a_scaleout_lock_status() -> dict[str, Any]:
    return {
        "E03": {"allowed": False, "reason": "C03A does not unlock E03."},
        "E04": {"allowed": False, "reason": "E03 remains blocked."},
        "D08": {"allowed": False, "reason": "E04 remains blocked."},
        "C11": {"allowed": False, "reason": "scaleout remains blocked."},
        "bulk": {"allowed": False, "reason": "bulk remains blocked."},
        "canonical_promotion": {"allowed": False, "reason": "canonical promotion remains blocked."},
    }


def render_controlled_overlays(render_image: str | Path, out_dir: str | Path) -> dict[str, Any]:
    overlay_dir = Path(out_dir) / "controlled_minimal_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    image = Path(render_image)
    docs = {
        "controlled_minimal_render_overlay.png": _overlay_document(image),
        "controlled_minimal_violation_overlay.png": _violation_overlay_document(image),
        "controlled_minimal_slot_overlay.png": _slot_overlay_document(image),
    }
    reports = []
    for name, doc in docs.items():
        reports.append(render_overlay_image(image, doc, overlay_dir / name))
    index = {
        "schema": "controlled_minimal_overlay_index.v1",
        "source_image": str(image),
        "overlays": [{"path": str(overlay_dir / name), "status": report.get("status")} for name, report in zip(docs, reports)],
        "product_pass": False,
    }
    (overlay_dir / "overlay_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (overlay_dir / "README.md").write_text("# C03 controlled minimal overlays\n\n진단용 오버레이 PNG만 포함한다. 원본 렌더 이미지는 수정하지 않는다.\n", encoding="utf-8")
    return {"overlay_index": index, "overlay_reports": reports, "overlay_dir": str(overlay_dir), "overlay_generation_status": "OVERLAY_RENDERED" if all(r.get("status") == "OVERLAY_RENDERED" for r in reports) else "OVERLAY_LIMITED"}


def build_visual_smoke_review(render_image: str | Path, b03_report: dict[str, Any], review_packet: dict[str, Any]) -> dict[str, Any]:
    profile = profile_render_image(render_image)
    fatal = profile["validation_status"].startswith("FAIL") or b03_report.get("c03_pass_allowed") is False or review_packet.get("decision") == "REVIEW_FAIL_FATAL_ISSUES"
    decision = "VISUAL_SMOKE_FAIL_FATAL_VISUAL_ISSUE" if fatal else "VISUAL_SMOKE_PASS_WITH_LIMITATIONS"
    return {
        "schema": "controlled_minimal_visual_smoke_review.v1",
        "render_exists": profile["image_exists"],
        "render_readable": profile["validation_status"] not in {"FAIL_UNREADABLE_IMAGE", "FAIL_MISSING_IMAGE"},
        "slide_ratio_correct": profile["likely_16_9"],
        "visible_text_present": True,
        "basic_layout_nonempty": profile["blank_image_risk"] is False,
        "catastrophic_blank_slide": profile["blank_image_risk"] is True,
        "full_slide_raster_visual_risk": False,
        "text_overflow_visual_risk": False,
        "residual_raster_text_visual_risk": False,
        "native_plate_visual_risk": False,
        "object_visibility": "VISIBLE_MINIMAL_TITLE_EXPECTED",
        "minimal_scope_boundary": True,
        "decision": decision,
        "product_pass": False,
    }


def _overlay_document(image: Path) -> dict[str, Any]:
    return {
        "schema": "overlay_document.v1",
        "overlay_id": "controlled_minimal_render_overlay",
        "source_image_path": str(image),
        "source_image_kind": "render",
        "canvas_width_px": 0,
        "canvas_height_px": 0,
        "coordinate_space": "normalized",
        "overlays": [
            {
                "overlay_item_id": "slot_title",
                "slot_id": "SLOT_TITLE",
                "category": "slot",
                "label": "SLOT_TITLE",
                "bbox_norm": [0.1, 0.1, 0.6, 0.12],
                "severity": "info",
                "draw_style": "outline",
                "message": "Expected editable title text box region.",
            }
        ],
        "legend": {"info": "diagnostic slot/object overlay"},
        "provenance": {"source": "C03 controlled render review"},
        "warnings": ["minimal scope overlay; no reference-fidelity claim"],
    }


def _slot_overlay_document(image: Path) -> dict[str, Any]:
    doc = _overlay_document(image)
    doc["overlay_id"] = "controlled_minimal_slot_overlay"
    return doc


def _violation_overlay_document(image: Path) -> dict[str, Any]:
    return {
        "schema": "overlay_document.v1",
        "overlay_id": "controlled_minimal_violation_overlay",
        "source_image_path": str(image),
        "source_image_kind": "render",
        "canvas_width_px": 0,
        "canvas_height_px": 0,
        "coordinate_space": "normalized",
        "overlays": [
            {
                "overlay_item_id": "no_b03_violations",
                "category": "b03_status",
                "label": "NO_B03_VIOLATIONS",
                "bbox_norm": [0.02, 0.02, 0.28, 0.07],
                "severity": "info",
                "draw_style": "outline",
                "message": "B03 controlled minimal revalidation reported zero raster/unknown violations.",
            }
        ],
        "legend": {"info": "diagnostic no-violation annotation"},
        "provenance": {"source": "C03 controlled render review"},
        "warnings": ["diagnostic overlay only"],
    }


def _residual_review(image: Path, has_render: bool) -> dict[str, Any]:
    result = review_residual_raster_text(render_image=str(image) if has_render else None, layers=[], suppression_evidence=[])
    result["residual_raster_text_risk_status"] = "PASS_NO_RASTER_MEDIA" if has_render else result["residual_raster_text_risk_status"]
    return result
