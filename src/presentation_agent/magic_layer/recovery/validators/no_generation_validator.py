from __future__ import annotations

from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def validate_no_generation(folder: str | Path) -> dict[str, Any]:
    root = Path(folder)
    files = list(root.rglob("*")) if root.exists() else []
    pptx = [path for path in files if path.is_file() and path.suffix.lower() == ".pptx"]
    images = [path for path in files if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
    render_like = [path for path in images if "render" in path.name.lower()]
    forbidden = [*pptx, *images]
    return {
        "schema": "rv00_no_generation_audit_report.v1",
        "folder": str(root),
        "pptx_count": len(pptx),
        "image_count": len(images),
        "render_image_count": len(render_like),
        "forbidden_artifacts": [str(path) for path in forbidden],
        "source_bound_deck_count": len([path for path in pptx if "source" in path.name.lower() and "bound" in path.name.lower()]),
        "template_pack_count": len([path for path in pptx if "template" in path.name.lower() and "pack" in path.name.lower()]),
        "canonical_artifact_count": len([path for path in forbidden if path.name in {"golden_template_masters.pptx", "final_deck_large_premium.pptx"}]),
        "pass": not forbidden,
        "product_pass": False,
    }


def validate_rv01_no_generation(folder: str | Path, initial_snapshot: set[str] | list[str]) -> dict[str, Any]:
    root = Path(folder)
    before = {str(Path(item)) for item in initial_snapshot}
    files = list(root.rglob("*")) if root.exists() else []
    current_forbidden = [
        path
        for path in files
        if path.is_file() and (path.suffix.lower() == ".pptx" or path.suffix.lower() in IMAGE_SUFFIXES)
    ]
    new_forbidden = [path for path in current_forbidden if str(path) not in before]
    new_images = [path for path in new_forbidden if path.suffix.lower() in IMAGE_SUFFIXES]
    new_pptx = [path for path in new_forbidden if path.suffix.lower() == ".pptx"]
    return {
        "schema": "rv01_no_generation_audit_report.v1",
        "folder": str(root),
        "initial_forbidden_snapshot_count": len(before),
        "new_forbidden_artifacts": [str(path) for path in new_forbidden],
        "new_image_count": len(new_images),
        "new_pptx_count": len(new_pptx),
        "pass": not new_forbidden,
        "product_pass": False,
    }


def validate_rv01a_no_generation(folder: str | Path, initial_snapshot: set[str] | list[str]) -> dict[str, Any]:
    report = validate_rv01_no_generation(folder, initial_snapshot)
    report["schema"] = "rv01a_no_generation_audit_report.v1"
    return report
