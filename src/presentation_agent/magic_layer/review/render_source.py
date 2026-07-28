from __future__ import annotations

from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def discover_render_sources(artifact_group: str | Path, render_if_missing: bool = False) -> dict[str, Any]:
    group = Path(artifact_group)
    files = [path for path in group.rglob("*") if path.is_file()] if group.exists() else []
    rendered = [path for path in files if path.suffix.lower() in IMAGE_SUFFIXES and ("render" in path.name.lower() or "candidate" in path.name.lower())]
    references = [path for path in files if path.suffix.lower() in IMAGE_SUFFIXES and "reference_image" in path.name.lower()]
    contact_sheets = [path for path in files if path.suffix.lower() in IMAGE_SUFFIXES and "contact_sheet" in path.name.lower()]
    pptx = [path for path in files if path.suffix.lower() == ".pptx"]
    if rendered:
        status = "EXISTING_RENDER_AVAILABLE"
    elif contact_sheets:
        status = "EXISTING_CONTACT_SHEET_AVAILABLE"
    elif pptx and render_if_missing:
        status = "RENDER_BACKEND_UNAVAILABLE"
    elif pptx:
        status = "RENDER_OPTIONAL_NOT_RUN"
    else:
        status = "RENDER_MISSING"
    return {
        "schema": "render_source_discovery.v1",
        "artifact_group": str(group),
        "render_source_status": status,
        "render_if_missing_requested": render_if_missing,
        "existing_render_images": [str(path) for path in rendered],
        "existing_reference_images": [str(path) for path in references],
        "existing_contact_sheets": [str(path) for path in contact_sheets],
        "pptx_files": [str(path) for path in pptx],
        "selected_review_image": str((rendered or contact_sheets or references or [None])[0]) if (rendered or contact_sheets or references) else None,
        "default_render_performed": False,
    }


def render_if_missing(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {
        "schema": "render_backend_report.v1",
        "status": "RENDER_BACKEND_UNAVAILABLE",
        "pass": False,
        "default_render_performed": False,
        "message": "B01 does not render by default; local renderer is not required for B01 pass.",
    }
