from __future__ import annotations

from copy import deepcopy
from typing import Any

from .archetype_taxonomy import known_archetype, validate_archetype_contract


REQUIRED_FIELDS = [
    "contract_id",
    "template_id",
    "archetype_id",
    "template_name",
    "intended_use",
    "canvas",
    "design_tokens",
    "fixed_style_elements",
    "editable_content_slots",
    "replaceable_visual_slots",
    "native_component_slots",
    "structural_shapes",
    "protected_zones",
    "optional_slots",
    "forbidden_slots",
    "slot_binding_rules",
    "overflow_policy",
    "raster_policy",
    "native_component_policy",
    "review_hooks",
    "patch_hooks",
    "source_binding_preparation",
    "compile_eligibility",
]


def validate_template_contract(contract: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(contract)
    failures: list[str] = []
    if data.get("schema", "template_contract.v1") != "template_contract.v1":
        failures.append("schema must be template_contract.v1")
    for field in REQUIRED_FIELDS:
        if field not in data:
            failures.append(f"{field} is required")
    archetype_id = data.get("archetype_id")
    if not archetype_id:
        failures.append("archetype_id is required")
    elif not known_archetype(archetype_id):
        failures.append(f"{archetype_id} must be a known archetype")
    elif data.get("editable_content_slots") or data.get("native_component_slots") or data.get("replaceable_visual_slots"):
        taxonomy_result = validate_archetype_contract(archetype_id, data)
        failures.extend(taxonomy_result["failures"])
    forbidden = set(str(item) for item in data.get("forbidden_slots", []))
    if "full_slide_raster" not in forbidden:
        failures.append("forbidden_slots must include full_slide_raster")
    if "screenshot_slide" not in forbidden:
        failures.append("forbidden_slots must include screenshot_slide")
    source_prep = data.get("source_binding_preparation", {})
    if source_prep.get("source_bound_deck_generated") is True:
        failures.append("source_bound_deck_generated must be false in T01")
    if data.get("compile_eligibility", {}).get("canonical_promotion_allowed") is True:
        failures.append("canonical_promotion_allowed must be false")
    if not data.get("slot_binding_rules") and source_prep.get("source_binding_preparedness") is True:
        failures.append("source_binding_preparation requires slot binding rules")
    return {"schema": "template_contract_validation.v1", "pass": not failures, "failures": failures, "contract": data}
