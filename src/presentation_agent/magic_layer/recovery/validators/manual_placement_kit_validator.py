from __future__ import annotations

from typing import Any


def validate_manual_placement_kit(kit: dict[str, Any]) -> dict[str, Any]:
    placements = kit.get("placements", [])
    filenames = [item.get("expected_filename") for item in placements if isinstance(item, dict)]
    return {
        "schema": "manual_placement_kit_validator.v1",
        "pass": len(placements) == 16 and all(str(name).endswith(".png") for name in filenames),
        "placement_count": len(placements),
        "image_files_created": kit.get("image_files_created", 0),
        "product_pass": False,
    }
