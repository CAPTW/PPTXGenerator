from __future__ import annotations

import hashlib
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


def build_render_execution_report(
    *,
    renderer: str | None,
    method: str | None,
    input_pptx: str | Path,
    output_path: str | Path,
    source_hash_before: str | None,
    source_hash_after: str | None,
    render_manifest: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    manifest = render_manifest or {}
    width = None
    height = None
    slides = manifest.get("slides", [])
    if slides:
        width = slides[0].get("width_px")
        height = slides[0].get("height_px")
    return {
        "schema": "controlled_minimal_render_execution_report.v1",
        "renderer": renderer,
        "command_or_method": method,
        "input_pptx": str(input_pptx),
        "input_hash": source_hash_before,
        "output_path": str(output),
        "output_exists": output.is_file(),
        "output_hash": sha256_file(output),
        "output_size": output.stat().st_size if output.is_file() else None,
        "width_px": width,
        "height_px": height,
        "render_count": 1 if output.is_file() else 0,
        "slide_count": manifest.get("slide_count"),
        "renderer_modifies_source": False,
        "source_hash_before": source_hash_before,
        "source_hash_after": source_hash_after,
        "source_hash_unchanged": source_hash_before == source_hash_after,
        "stdout_stderr_summary": {"warnings": manifest.get("warnings", []), "errors": manifest.get("errors", [])},
        "exit_code": 0 if output.is_file() and not errors else 2,
        "warnings": warnings or [],
        "errors": errors or [],
        "render_generated": output.is_file(),
        "pptx_generated": False,
        "product_pass": False,
    }
