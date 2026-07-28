from __future__ import annotations

from typing import Any

from .e03_reference_contract import CORE_ARCHETYPES


def validate_semantic_contract(archetype_id: str, registry_entry: dict[str, Any], *, prior_core_available: bool) -> dict[str, Any]:
    assertion = registry_entry.get("semantic_assertion") if isinstance(registry_entry, dict) else None
    if archetype_id in CORE_ARCHETYPES and prior_core_available:
        decision = "SEMANTIC_VALIDATED_BY_PRIOR_CORE_EVIDENCE"
    elif isinstance(assertion, dict) and assertion.get("archetype_confirmed") is True and assertion.get("notes"):
        decision = "SEMANTIC_VALIDATED_BY_REGISTRY_ASSERTION"
    elif isinstance(assertion, dict) and assertion.get("archetype_confirmed") is False:
        decision = "SEMANTIC_INVALID_GENERIC_SLIDE"
    elif registry_entry.get("manual_review_required"):
        decision = "SEMANTIC_PRESENT_BUT_MANUAL_REVIEW_REQUIRED"
    else:
        decision = "SEMANTIC_NOT_VALIDATED"
    return {"schema": "e03_reference_semantic_contract_report.v1", "archetype_id": archetype_id, "decision": decision, "uses_ocr": False, "uses_pixel_semantic_inference": False, "product_pass": False}
