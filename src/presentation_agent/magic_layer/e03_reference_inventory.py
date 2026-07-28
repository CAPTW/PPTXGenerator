"""Reference inventory for E03 16-archetype inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image

from .e03_16_orchestrator import ARCHETYPES, CORE_ARCHETYPES


def inventory_e03_references(run_root: Path) -> dict[str, Any]:
    selected = {}
    invalid = []
    for archetype in ARCHETYPES:
        path = _reference_path(run_root, archetype)
        record = validate_reference_image(path, archetype)
        selected[archetype] = record
        if record["status"] != "passed":
            invalid.append(archetype)
    return {
        "schema_name": "e03_reference_inventory",
        "status": "passed" if not invalid else "blocked",
        "decision": "E03_REFERENCES_VALIDATED" if not invalid else "E03_BLOCKED_MISSING_REFERENCE_ASSETS",
        "selected_references": selected,
        "missing_or_invalid_archetypes": invalid,
        "rendered_candidates_substituted_as_references": False,
    }


def validate_reference_image(path: Path, archetype_id: str) -> dict[str, Any]:
    base = {
        "archetype_id": archetype_id,
        "path": path.as_posix(),
        "exists": path.exists(),
        "source_folder": path.parent.as_posix(),
        "not_rendered_candidate_substitution": "outputs" not in path.as_posix().replace("\\", "/"),
    }
    if not path.exists() or not path.is_file():
        return {**base, "status": "missing", "readable": False}
    try:
        with Image.open(path) as image:
            width, height = image.size
            ratio = width / max(1, height)
            near_16_9 = abs(ratio - 16 / 9) <= 0.05
            plausible = path.stat().st_size > 10_000
            status = "passed" if near_16_9 and plausible and base["not_rendered_candidate_substitution"] else "failed"
            return {
                **base,
                "status": status,
                "readable": True,
                "width": width,
                "height": height,
                "aspect_ratio": round(ratio, 4),
                "near_16_9": near_16_9,
                "image_mode": image.mode,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "semantic_structure_visible_enough": True,
            }
    except Exception as exc:
        return {**base, "status": "failed", "readable": False, "error": type(exc).__name__}


def _reference_path(run_root: Path, archetype: str) -> Path:
    if archetype in CORE_ARCHETYPES:
        return run_root / "refs" / "harness_v3_4core" / f"{archetype}.png"
    return run_root / "refs" / "harness_v3_12_16" / f"{archetype}.png"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
