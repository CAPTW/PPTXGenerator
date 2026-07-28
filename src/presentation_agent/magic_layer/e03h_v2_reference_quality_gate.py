"""Reference quality gate before E03H-V2 conversion."""

from __future__ import annotations

from typing import Any


def evaluate_reference_quality(signals: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if signals.get("semantic_slot_count", 0) < 3:
        failures.append("weak_semantic_slots")
    if signals.get("segmented_backplate_count", 0) <= 0:
        failures.append("missing_visual_backplate_value")
    if signals.get("archetype_identity") in {None, "", "generic"}:
        failures.append("weak_archetype_identity")
    if signals.get("requires_native_component") and not signals.get("has_required_native_component"):
        failures.append("missing_required_native_component")
    return {
        "schema_name": "reference_quality_report",
        "status": "passed" if not failures else "failed",
        "reference_id": signals.get("reference_id"),
        "failures": failures,
        "semantic_slot_count": signals.get("semantic_slot_count", 0),
        "segmented_backplate_count": signals.get("segmented_backplate_count", 0),
        "archetype_identity": signals.get("archetype_identity"),
        "wireframe_like": bool(failures),
        "canva_parity_claimed": False,
    }
