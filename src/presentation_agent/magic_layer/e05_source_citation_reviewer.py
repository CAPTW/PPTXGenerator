"""Source and citation readability/binding review for E05."""

from __future__ import annotations

from typing import Any


def review_source_citation(binding_regression: dict[str, Any], text_review: dict[str, Any]) -> dict[str, Any]:
    issues = []
    source_count = int(binding_regression.get("source_binding_count", 0))
    citation_count = int(binding_regression.get("citation_binding_count", 0))
    slot_count = int(binding_regression.get("slot_binding_count", 0))
    if binding_regression.get("status") != "passed":
        issues.append(
            {
                "slide_number": None,
                "archetype_id": "deck",
                "issue": "source/citation/slot binding regression detected",
                "severity": "critical",
                "patch_type": "citation_binding_patch",
                "recommended_action": "Restore missing source, citation, and slot bindings before product review.",
            }
        )
    for row in text_review.get("slide_reviews", []):
        if row.get("minimum_font_pt", 99) and row.get("minimum_font_pt", 99) < 6.0:
            issues.append(
                {
                    "slide_number": row["slide_number"],
                    "archetype_id": row["archetype_id"],
                    "issue": "visible source/data support text is below product legibility target",
                    "severity": "medium",
                    "patch_type": "source_footer_readability_patch",
                    "recommended_action": "Increase source/footer support text or simplify surrounding density.",
                }
            )
    return {
        "schema_name": "e05_source_citation_review",
        "status": "failed" if binding_regression.get("status") != "passed" else ("patch_recommended" if issues else "passed"),
        "source_binding_count": source_count,
        "citation_binding_count": citation_count,
        "slot_binding_count": slot_count,
        "source_binding_regression_count": binding_regression.get("source_binding_regression_count", 0),
        "citation_binding_regression_count": binding_regression.get("citation_binding_regression_count", 0),
        "slot_binding_regression_count": binding_regression.get("slot_binding_regression_count", 0),
        "missing_source_binding_count": binding_regression.get("source_binding_regression_count", 0),
        "missing_citation_binding_count": binding_regression.get("citation_binding_regression_count", 0),
        "missing_slot_binding_count": binding_regression.get("slot_binding_regression_count", 0),
        "issues": issues,
    }

