"""Visual rhythm gate for patched E03.1 pack."""

from __future__ import annotations

from typing import Any

from .e03_16_orchestrator import ARCHETYPES
from .e03_visual_rhythm_gate import build_visual_rhythm_report


def build_e03_1_visual_rhythm_report(archetype_statuses: dict[str, str]) -> dict[str, Any]:
    base = build_visual_rhythm_report(archetype_statuses)
    base["schema_name"] = "e03_1_visual_rhythm_summary"
    base["e03_1_patch_context"] = "expansion_reference_fidelity_patch"
    base["no_generic_skeleton_collapse"] = all(status == "passed" for status in archetype_statuses.values()) and set(archetype_statuses) == set(ARCHETYPES)
    if not base["no_generic_skeleton_collapse"]:
        base["status"] = "failed"
        base["visual_rhythm_verdict"] = "patch"
        base.setdefault("critical_blockers", []).append("generic_skeleton_collapse")
    return base
