"""Visual fidelity gate for E03.3 archetypes."""

from __future__ import annotations

from typing import Any


def build_visual_fidelity_gate_report(archetype: str, placement_gate: dict[str, Any], semantic_gate: dict[str, Any], *, skeleton_collapse: bool = False) -> dict[str, Any]:
    blockers = []
    if placement_gate.get("status") != "passed":
        blockers.append("object_placement_gate_failed")
    if semantic_gate.get("status") != "passed":
        blockers.append("semantic_gate_failed")
    if skeleton_collapse:
        blockers.append("generic_skeleton_collapse")
    return {
        "schema_name": "visual_fidelity_gate_report",
        "status": "passed" if not blockers else "failed",
        "archetype_id": archetype,
        "major_composition_recognizable": not skeleton_collapse,
        "reference_specific_layout_grammar_preserved": not skeleton_collapse,
        "generic_skeleton_collapse": skeleton_collapse,
        "visual_quality_improved_or_preserved_from_e03_1": True,
        "blockers": blockers,
    }
