from __future__ import annotations

import hashlib
import os
import traceback
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str | None:
    file_path = Path(path)
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_powerpoint_com_diagnostics(
    pptx_path: str | Path,
    *,
    force_unavailable: bool = False,
    allow_open: bool = True,
) -> dict[str, Any]:
    """Probe PowerPoint COM without rendering or modifying the source PPTX."""

    pptx = Path(pptx_path)
    before = sha256_file(pptx)
    result: dict[str, Any] = {
        "schema": "powerpoint_com_diagnostics.v1",
        "pptx_path": str(pptx),
        "pptx_exists": pptx.is_file(),
        "source_hash_before": before,
        "source_hash_after": before,
        "source_hash_unchanged": True,
        "win32com_available": False,
        "dispatch_success": False,
        "version": None,
        "open_success": False,
        "slide_count": None,
        "exceptions": [],
        "cleanup_success": False,
        "leftover_process_risk": "unknown",
    }
    if force_unavailable:
        result["exceptions"].append({"stage": "import", "message": "Forced unavailable for controlled test."})
        result.update(classify_powerpoint_diagnostics(result))
        return result
    if os.name != "nt":
        result["exceptions"].append({"stage": "platform", "message": "PowerPoint COM is Windows-only."})
        result.update(classify_powerpoint_diagnostics(result))
        return result
    try:
        import pythoncom
        import win32com.client
    except Exception as exc:  # pragma: no cover - environment-dependent
        result["exceptions"].append({"stage": "import", "message": repr(exc)})
        result.update(classify_powerpoint_diagnostics(result))
        return result

    result["win32com_available"] = True
    pythoncom.CoInitialize()
    app = None
    deck = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        result["dispatch_success"] = True
        try:
            result["version"] = str(app.Version)
        except Exception as exc:  # pragma: no cover - environment-dependent
            result["exceptions"].append({"stage": "version", "message": repr(exc)})
        if allow_open and pptx.is_file():
            try:
                deck = app.Presentations.Open(str(pptx.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
                result["open_success"] = True
                result["slide_count"] = int(deck.Slides.Count)
                try:
                    _ = deck.Slides(1)
                    result["slide_1_access_success"] = True
                except Exception as exc:  # pragma: no cover - environment-dependent
                    result["slide_1_access_success"] = False
                    result["exceptions"].append({"stage": "slide_access", "message": repr(exc)})
            except Exception as exc:  # pragma: no cover - environment-dependent
                result["open_error"] = repr(exc)
                result["open_trace"] = traceback.format_exc()[-1200:]
                result["exceptions"].append({"stage": "open", "message": repr(exc)})
    except Exception as exc:  # pragma: no cover - environment-dependent
        result["dispatch_error"] = repr(exc)
        result["exceptions"].append({"stage": "dispatch", "message": repr(exc)})
    finally:
        cleanup_errors = []
        if deck is not None:
            try:
                deck.Close()
            except Exception as exc:  # pragma: no cover - environment-dependent
                cleanup_errors.append(repr(exc))
        if app is not None:
            try:
                app.Quit()
            except Exception as exc:  # pragma: no cover - environment-dependent
                cleanup_errors.append(repr(exc))
        try:
            pythoncom.CoUninitialize()
        except Exception as exc:  # pragma: no cover - environment-dependent
            cleanup_errors.append(repr(exc))
        result["cleanup_success"] = not cleanup_errors
        if cleanup_errors:
            result["cleanup_errors"] = cleanup_errors
    after = sha256_file(pptx)
    result["source_hash_after"] = after
    result["source_hash_unchanged"] = before == after
    result.update(classify_powerpoint_diagnostics(result))
    return result


def classify_powerpoint_diagnostics(diagnostics: dict[str, Any]) -> dict[str, str]:
    if not diagnostics.get("win32com_available"):
        return {
            "diagnostics_status": "POWERPOINT_COM_UNAVAILABLE",
            "failure_classification": "RENDER_BACKEND_UNAVAILABLE",
        }
    if not diagnostics.get("dispatch_success"):
        return {
            "diagnostics_status": "POWERPOINT_COM_UNKNOWN",
            "failure_classification": "POWERPOINT_COM_UNKNOWN_FAILURE",
        }
    if diagnostics.get("open_success") is False:
        return {
            "diagnostics_status": "POWERPOINT_COM_AVAILABLE_BUT_OPEN_FAILS",
            "failure_classification": "PPTX_NOT_OPENABLE_IN_POWERPOINT",
        }
    if diagnostics.get("export_success") is False or diagnostics.get("export_error"):
        return {
            "diagnostics_status": "POWERPOINT_COM_AVAILABLE_BUT_EXPORT_FAILS",
            "failure_classification": "POWERPOINT_COM_EXPORT_FAILURE",
        }
    return {
        "diagnostics_status": "POWERPOINT_COM_READY",
        "failure_classification": "NONE",
    }


def diagnose_prior_powerpoint_failure(render_execution_report: dict[str, Any]) -> dict[str, Any]:
    errors = render_execution_report.get("stdout_stderr_summary", {}).get("errors", [])
    message = ""
    if errors:
        first = errors[0]
        message = str(first.get("details", {}).get("error") or first.get("message") or first)
    classification = "POWERPOINT_COM_UNKNOWN_FAILURE"
    if "-2147023504" in message or "Open" in message or "-2147352567" in message:
        classification = "POWERPOINT_COM_OPEN_FAILURE"
    elif "permission" in message.lower() or "path" in message.lower():
        classification = "POWERPOINT_COM_PATH_OR_PERMISSION_FAILURE"
    elif "export" in message.lower():
        classification = "POWERPOINT_COM_EXPORT_FAILURE"
    return {
        "schema": "render_failure_diagnosis.v1",
        "prior_backend": render_execution_report.get("renderer"),
        "exception_message": message,
        "classification": classification,
        "source_hash_unchanged": render_execution_report.get("source_hash_unchanged"),
        "product_pass": False,
    }
