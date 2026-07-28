from __future__ import annotations

from typing import Any


ACCEPTED_CONTENT_TYPES = {
    "title",
    "subtitle",
    "body_text",
    "bullet_list",
    "metric_value",
    "metric_label",
    "chart_data",
    "table_data",
    "citation",
    "source",
    "footnote",
    "image_asset",
    "icon_asset",
}


def validate_binding_rule(rule: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if not rule.get("binding_rule_id"):
        failures.append("binding_rule_id is required")
    if not rule.get("slot_id"):
        failures.append("slot_id is required")
    for content_type in rule.get("accepted_content_types", []):
        if content_type not in ACCEPTED_CONTENT_TYPES:
            failures.append(f"invalid accepted_content_type: {content_type}")
    if rule.get("source_traceability_required") and not rule.get("validation_rules"):
        failures.append("source traceability requires validation_rules")
    return {"pass": not failures, "failures": failures, "source_binding_readiness": False}
