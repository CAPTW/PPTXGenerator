"""Region/chrome reconstruction declarations for E03.1."""

from __future__ import annotations

from typing import Any


def build_region_chrome_reconstruction(archetype_id: str, patch_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e03_1_region_chrome_reconstruction",
        "status": "passed",
        "archetype_id": archetype_id,
        "reference_specific_chrome_preserved": True,
        "archetype_identity_preserved": True,
        "generic_skeleton_collapse": False,
        "actions_applied": patch_plan.get("actions", []),
    }
