"""Source-binding policy for E04."""

from __future__ import annotations

from typing import Any


def build_e04_source_binding_policy() -> dict[str, Any]:
    return {
        "schema_name": "e04_source_binding_policy",
        "status": "passed",
        "required_for": ["claims", "metrics", "table_rows", "chart_values", "citation_visible_text", "footer_source_text"],
        "fatal_codes": [
            "SOURCE_BINDING_MISSING",
            "CITATION_BINDING_MISSING",
            "SLOT_BINDING_MISSING",
            "UNBOUND_VISIBLE_CLAIM",
            "FABRICATED_METRIC",
            "FABRICATED_SOURCE",
        ],
        "synthetic_fixture_allowed": False,
        "broad_canva_parity_claimed": False,
    }
