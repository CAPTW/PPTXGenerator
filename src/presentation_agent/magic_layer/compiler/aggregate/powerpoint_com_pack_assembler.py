from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.audit.pptx_ooxml_audit import audit_pptx_package
from src.presentation_agent.magic_layer.pipeline.execution.aggregate_report import sha256_file


def assemble_with_powerpoint_com(source_pptx: list[str | Path], output_path: str | Path) -> dict[str, Any]:
    sources = [Path(path) for path in source_pptx]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(sources) != 4:
        return _failed(output, sources, ["exactly four source PPTX files are required"])
    if output.exists():
        return _failed(output, sources, ["aggregate output already exists; no overwrite"])
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        return _failed(output, sources, ["missing source PPTX: " + ", ".join(missing)])

    before = {str(path): sha256_file(path) for path in sources}
    shutil.copy2(sources[0], output)
    errors: list[str] = []
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        app = None
        deck = None
        try:
            app = win32com.client.DispatchEx("PowerPoint.Application")
            deck = app.Presentations.Open(str(output.resolve()), ReadOnly=False, Untitled=False, WithWindow=False)
            for source in sources[1:]:
                deck.Slides.InsertFromFile(str(source.resolve()), deck.Slides.Count, 1, 1)
            deck.Save()
        finally:
            if deck is not None:
                deck.Close()
            if app is not None:
                app.Quit()
            pythoncom.CoUninitialize()
    except Exception as exc:  # pragma: no cover - local PowerPoint dependent
        errors.append(repr(exc))

    after = {str(path): sha256_file(path) for path in sources}
    audit = audit_pptx_package(output) if output.is_file() else {}
    return {
        "schema": "p06_aggregate_assembly_execution_report.v1",
        "selected_backend": "powerpoint_com_insert_from_file",
        "source_pptx_paths": [str(path) for path in sources],
        "source_hashes_before": before,
        "source_hashes_after": after,
        "source_hashes_unchanged": before == after,
        "output_path": str(output),
        "output_hash": sha256_file(output),
        "slide_count": audit.get("slide_count", 0),
        "errors": errors,
        "warnings": ["aggregate pack is noncanonical and not product PASS"],
        "limitations": ["PowerPoint COM slide import preserves editable objects as supported by local PowerPoint"],
        "pptx_generated": output.is_file() and not errors,
        "product_pass": False,
    }


def _failed(output: Path, sources: list[Path], errors: list[str]) -> dict[str, Any]:
    return {
        "schema": "p06_aggregate_assembly_execution_report.v1",
        "selected_backend": "powerpoint_com_insert_from_file",
        "source_pptx_paths": [str(path) for path in sources],
        "source_hashes_before": {str(path): sha256_file(path) for path in sources},
        "source_hashes_after": {str(path): sha256_file(path) for path in sources},
        "source_hashes_unchanged": True,
        "output_path": str(output),
        "output_hash": sha256_file(output),
        "slide_count": 0,
        "errors": errors,
        "warnings": [],
        "limitations": [],
        "pptx_generated": False,
        "product_pass": False,
    }
