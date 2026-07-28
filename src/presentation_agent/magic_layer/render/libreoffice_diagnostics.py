from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .powerpoint_com_diagnostics import sha256_file


def find_soffice() -> Path | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for candidate in (
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    ):
        if candidate.is_file():
            return candidate
    return None


def run_libreoffice_diagnostics(pptx_path: str | Path, *, attempt_dir: str | Path | None = None, attempt_convert: bool = False) -> dict[str, Any]:
    pptx = Path(pptx_path)
    soffice = find_soffice()
    before = sha256_file(pptx)
    result: dict[str, Any] = {
        "schema": "libreoffice_render_backend_diagnostics.v1",
        "pptx_path": str(pptx),
        "pptx_exists": pptx.is_file(),
        "available": soffice is not None,
        "soffice_path": str(soffice) if soffice else None,
        "version": None,
        "headless_conversion_supported": None,
        "attempted_conversion": False,
        "conversion_success": False,
        "output_path": None,
        "source_hash_before": before,
        "source_hash_after": before,
        "source_hash_unchanged": True,
        "diagnostics_status": "LIBREOFFICE_UNAVAILABLE",
        "limitations": [],
        "errors": [],
    }
    if soffice is None:
        result["errors"].append("LibreOffice soffice executable was not found locally.")
        return result
    try:
        proc = subprocess.run([str(soffice), "--version"], capture_output=True, text=True, timeout=20, check=False)
        result["version"] = (proc.stdout or proc.stderr).strip()
        result["headless_conversion_supported"] = proc.returncode == 0
    except Exception as exc:  # pragma: no cover - environment-dependent
        result["errors"].append(repr(exc))
    if attempt_convert and attempt_dir:
        out = Path(attempt_dir)
        out.mkdir(parents=True, exist_ok=True)
        result["attempted_conversion"] = True
        try:
            proc = subprocess.run(
                [str(soffice), "--headless", "--convert-to", "png", "--outdir", str(out), str(pptx.resolve())],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            result["command"] = " ".join([str(soffice), "--headless", "--convert-to", "png", "--outdir", str(out), str(pptx.resolve())])
            result["exit_code"] = proc.returncode
            result["stdout"] = proc.stdout[-1000:]
            result["stderr"] = proc.stderr[-1000:]
            pngs = sorted(out.glob("*.png"))
            if proc.returncode == 0 and pngs:
                result["conversion_success"] = True
                result["output_path"] = str(pngs[0])
        except Exception as exc:  # pragma: no cover - environment-dependent
            result["errors"].append(repr(exc))
    after = sha256_file(pptx)
    result["source_hash_after"] = after
    result["source_hash_unchanged"] = before == after
    if result["conversion_success"]:
        result["diagnostics_status"] = "LIBREOFFICE_RENDER_READY"
    elif result["available"]:
        result["diagnostics_status"] = "LIBREOFFICE_AVAILABLE"
    return result
