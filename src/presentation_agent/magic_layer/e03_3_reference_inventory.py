"""Reference inventory for E03.3 16-archetype batch placement."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image

from .e03_16_orchestrator import ARCHETYPES, CORE_ARCHETYPES


def inventory_e03_3_references(run_root: Path) -> dict[str, Any]:
    selected: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for archetype in ARCHETYPES:
        folder = "harness_v3_4core" if archetype in CORE_ARCHETYPES else "harness_v3_12_16"
        path = run_root / "refs" / folder / f"{archetype}.png"
        if not path.exists():
            missing.append(path.as_posix())
            continue
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
        selected[archetype] = {
            "path": path.as_posix(),
            "width": width,
            "height": height,
            "mode": mode,
            "aspect_ratio": round(width / height, 4),
            "near_16_9": abs((width / height) - (16 / 9)) <= 0.08,
            "file_size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_folder": folder,
        }
    return {
        "schema_name": "e03_3_reference_inventory",
        "status": "passed" if not missing and len(selected) == 16 and all(row["near_16_9"] for row in selected.values()) else "blocked",
        "reference_count": len(selected),
        "missing": missing,
        "selected_references": selected,
    }
