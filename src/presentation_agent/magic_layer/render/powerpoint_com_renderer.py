from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.qa.render_pptx_preview import render_pptx_preview

from .render_image_profile import profile_render_image
from .render_scope_guard import DEFAULT_RENDER_NAME
from .powerpoint_com_diagnostics import sha256_file


def render_with_powerpoint_com(pptx_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    return _render_backend(pptx_path, out_dir, "powerpoint_com")


def _render_backend(pptx_path: str | Path, out_dir: str | Path, backend: str) -> dict[str, Any]:
    out = Path(out_dir)
    report = render_pptx_preview(pptx_path=pptx_path, output_dir=out, manifest_path=out / "render_preview_manifest.json", backend=backend, dpi=144)
    final = out / DEFAULT_RENDER_NAME
    rendered = [Path(path) for path in report.get("output_paths", [])]
    if report.get("render_status") == "rendered" and len(rendered) == 1 and rendered[0].is_file():
        if final.exists() and final != rendered[0]:
            raise FileExistsError(f"Render output already exists: {final}")
        rendered[0].replace(final)
        report["output_paths"] = [str(final)]
        report["slides"][0]["rendered_image_path"] = str(final)
    return report


def summarize_attempt_matrix(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    success = next((item for item in attempts if item.get("status") == "SUCCESS" and item.get("output_path")), None)
    return {
        "schema": "controlled_render_attempt_matrix_summary.v1",
        "attempt_count": len(attempts),
        "success_count": sum(1 for item in attempts if item.get("status") == "SUCCESS"),
        "failure_count": sum(1 for item in attempts if str(item.get("status", "")).startswith("FAIL")),
        "selected_attempt_id": success.get("attempt_id") if success else None,
        "selected_output_path": success.get("output_path") if success else None,
        "fake_render_created": False,
        "source_hash_unchanged": all(item.get("source_hash_unchanged", True) for item in attempts),
        "attempts": attempts,
        "product_pass": False,
    }


def build_powerpoint_com_export_strategy_matrix(
    pptx_path: str | Path,
    out_dir: str | Path,
    diagnostics: dict[str, Any],
    *,
    attempt_export: bool = False,
) -> dict[str, Any]:
    """Build or run a conservative PowerPoint export matrix for one PPTX."""

    pptx = Path(pptx_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    attempts: list[dict[str, Any]] = []
    if not diagnostics.get("open_success"):
        for attempt_id, method in [
            ("powerpoint_com_strategy_a", "Presentation.Slides(1).Export"),
            ("powerpoint_com_strategy_b", "Presentation.Export"),
            ("powerpoint_com_strategy_c", "Presentation.SaveAs(ppSaveAsPNG)"),
            ("powerpoint_com_strategy_d", "ExportAsFixedFormat(PDF diagnostic)"),
        ]:
            attempts.append(
                {
                    "attempt_id": attempt_id,
                    "method": method,
                    "input_path": str(pptx),
                    "output_path": None,
                    "output_exists": False,
                    "output_hash": None,
                    "source_hash_before": diagnostics.get("source_hash_before"),
                    "source_hash_after": diagnostics.get("source_hash_after"),
                    "source_hash_unchanged": diagnostics.get("source_hash_unchanged", True),
                    "status": "SKIPPED",
                    "notes": "Skipped because PowerPoint COM could not open the PPTX safely.",
                }
            )
        return {**summarize_attempt_matrix(attempts), "schema": "powerpoint_com_export_strategy_matrix.v1", "attempts": attempts}
    if not attempt_export:
        attempts.append(
            {
                "attempt_id": "powerpoint_com_strategy_a",
                "method": "Presentation.Slides(1).Export",
                "input_path": str(pptx),
                "output_path": None,
                "output_exists": False,
                "output_hash": None,
                "source_hash_before": diagnostics.get("source_hash_before"),
                "source_hash_after": diagnostics.get("source_hash_after"),
                "source_hash_unchanged": diagnostics.get("source_hash_unchanged", True),
                "status": "SKIPPED",
                "notes": "Export was not requested for this diagnostic matrix.",
            }
        )
        return {**summarize_attempt_matrix(attempts), "schema": "powerpoint_com_export_strategy_matrix.v1", "attempts": attempts}

    attempts.append(_attempt_slide_export(pptx, out / "powerpoint_com_strategy_a"))
    if attempts[-1].get("status") == "SUCCESS":
        for attempt_id, method in [
            ("powerpoint_com_strategy_b", "Presentation.Export"),
            ("powerpoint_com_strategy_c", "Presentation.SaveAs(ppSaveAsPNG)"),
            ("powerpoint_com_strategy_d", "ExportAsFixedFormat(PDF diagnostic)"),
        ]:
            attempts.append(_skipped_after_success(pptx, out / attempt_id, attempt_id, method, attempts[0]))
        return {**summarize_attempt_matrix(attempts), "schema": "powerpoint_com_export_strategy_matrix.v1", "attempts": attempts}

    attempts.append(_attempt_presentation_export(pptx, out / "powerpoint_com_strategy_b"))
    if attempts[-1].get("status") == "SUCCESS":
        for attempt_id, method in [
            ("powerpoint_com_strategy_c", "Presentation.SaveAs(ppSaveAsPNG)"),
            ("powerpoint_com_strategy_d", "ExportAsFixedFormat(PDF diagnostic)"),
        ]:
            attempts.append(_skipped_after_success(pptx, out / attempt_id, attempt_id, method, attempts[-1]))
        return {**summarize_attempt_matrix(attempts), "schema": "powerpoint_com_export_strategy_matrix.v1", "attempts": attempts}

    for attempt_id, method in [
        ("powerpoint_com_strategy_c", "Presentation.SaveAs(ppSaveAsPNG)"),
        ("powerpoint_com_strategy_d", "ExportAsFixedFormat(PDF diagnostic)"),
    ]:
        attempts.append(
            {
                "attempt_id": attempt_id,
                "method": method,
                "input_path": str(pptx),
                "output_path": None,
                "output_exists": False,
                "output_hash": None,
                "source_hash_before": sha256_file(pptx),
                "source_hash_after": sha256_file(pptx),
                "source_hash_unchanged": True,
                "status": "SKIPPED",
                "notes": "Skipped by conservative retry policy after direct export strategies failed.",
            }
        )
    return {**summarize_attempt_matrix(attempts), "schema": "powerpoint_com_export_strategy_matrix.v1", "attempts": attempts}


def classify_retry_render_failure(*, powerpoint_opened: bool, powerpoint_success: bool, libreoffice_available: bool, libreoffice_success: bool = False) -> str:
    if not powerpoint_opened:
        return "C03A_RETRY_FAIL_PPTX_NOT_OPENABLE"
    if powerpoint_success or libreoffice_success:
        return "RENDER_GENERATED"
    if libreoffice_available:
        return "C03A_RETRY_FAIL_LIBREOFFICE_RENDER"
    return "C03A_RETRY_FAIL_POWERPOINT_COM_EXPORT"


def _attempt_slide_export(pptx: Path, attempt_dir: Path) -> dict[str, Any]:
    attempt_dir.mkdir(parents=True, exist_ok=True)
    output = attempt_dir / "slide1.png"
    before = sha256_file(pptx)
    try:
        from pptx import Presentation

        import pythoncom
        import win32com.client

        prs = Presentation(str(pptx))
        width_px = max(1, round(int(prs.slide_width) / 914400 * 144))
        height_px = max(1, round(int(prs.slide_height) / 914400 * 144))
        pythoncom.CoInitialize()
        app = None
        deck = None
        try:
            app = win32com.client.DispatchEx("PowerPoint.Application")
            deck = app.Presentations.Open(str(pptx.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
            deck.Slides(1).Export(str(output.resolve()), "PNG", width_px, height_px)
        finally:
            if deck is not None:
                deck.Close()
            if app is not None:
                app.Quit()
            pythoncom.CoUninitialize()
        return _attempt_result("powerpoint_com_strategy_a", "Presentation.Slides(1).Export", pptx, output, before, None)
    except Exception as exc:  # pragma: no cover - depends on local PowerPoint
        return _attempt_result("powerpoint_com_strategy_a", "Presentation.Slides(1).Export", pptx, output, before, exc)


def _attempt_presentation_export(pptx: Path, attempt_dir: Path) -> dict[str, Any]:
    attempt_dir.mkdir(parents=True, exist_ok=True)
    before = sha256_file(pptx)
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        app = None
        deck = None
        try:
            app = win32com.client.DispatchEx("PowerPoint.Application")
            deck = app.Presentations.Open(str(pptx.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
            deck.Export(str(attempt_dir.resolve()), "PNG")
        finally:
            if deck is not None:
                deck.Close()
            if app is not None:
                app.Quit()
            pythoncom.CoUninitialize()
        pngs = sorted(attempt_dir.glob("*.PNG")) + sorted(attempt_dir.glob("*.png"))
        output = pngs[0] if pngs else attempt_dir / "slide1.png"
        return _attempt_result("powerpoint_com_strategy_b", "Presentation.Export", pptx, output, before, None)
    except Exception as exc:  # pragma: no cover - depends on local PowerPoint
        return _attempt_result("powerpoint_com_strategy_b", "Presentation.Export", pptx, attempt_dir / "slide1.png", before, exc)


def _attempt_result(attempt_id: str, method: str, pptx: Path, output: Path, source_hash_before: str | None, exc: Exception | None) -> dict[str, Any]:
    profile = profile_render_image(output)
    exists = output.is_file()
    valid = profile.get("validation_status") in {"PASS", "WARNING_LOW_RESOLUTION"}
    if exc is not None:
        status = "FAIL_EXPORT"
    elif not exists:
        status = "FAIL_NO_OUTPUT"
    elif not valid:
        status = "FAIL_INVALID_IMAGE"
    else:
        status = "SUCCESS"
    after = sha256_file(pptx)
    return {
        "attempt_id": attempt_id,
        "method": method,
        "input_path": str(pptx),
        "output_path": str(output) if exists else None,
        "output_exists": exists,
        "output_hash": sha256_file(output) if exists else None,
        "width": profile.get("width"),
        "height": profile.get("height"),
        "source_hash_before": source_hash_before,
        "source_hash_after": after,
        "source_hash_unchanged": source_hash_before == after,
        "exception": repr(exc) if exc is not None else None,
        "status": status,
        "validation_status": profile.get("validation_status"),
        "limitations": ["controlled_single_slide_only"],
    }


def _skipped_after_success(pptx: Path, attempt_dir: Path, attempt_id: str, method: str, successful_attempt: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt_id": attempt_id,
        "method": method,
        "input_path": str(pptx),
        "output_path": None,
        "output_exists": False,
        "output_hash": None,
        "source_hash_before": successful_attempt.get("source_hash_before"),
        "source_hash_after": successful_attempt.get("source_hash_after"),
        "source_hash_unchanged": successful_attempt.get("source_hash_unchanged", True),
        "status": "SKIPPED",
        "notes": f"Skipped after successful {successful_attempt.get('attempt_id')} output.",
    }
