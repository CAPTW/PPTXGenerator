"""Visual priority matrix for E04-R2 slot binding."""

from __future__ import annotations

from typing import Any


def build_visual_priority_matrix(deck_art_direction_plan: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for slide in deck_art_direction_plan["slides"]:
        rows.extend(
            [
                {
                    "slide_id": slide["slide_id"],
                    "slide_number": slide["slide_number"],
                    "semantic_region": "primary_claim_or_object",
                    "visual_priority": "primary",
                    "binding_rule": "bind the main source-backed claim to the focal object region",
                    "focal_object": slide["focal_object"],
                },
                {
                    "slide_id": slide["slide_id"],
                    "slide_number": slide["slide_number"],
                    "semantic_region": "supporting_detail",
                    "visual_priority": "secondary",
                    "binding_rule": "bind supporting evidence as concise labels, chips, rows, nodes, or notes",
                    "focal_object": slide["focal_object"],
                },
                {
                    "slide_id": slide["slide_id"],
                    "slide_number": slide["slide_number"],
                    "semantic_region": "source_footer",
                    "visual_priority": "footer",
                    "binding_rule": "preserve citations in editable footer/source layer",
                    "focal_object": slide["focal_object"],
                },
            ]
        )
    return {
        "schema_name": "visual_priority_matrix",
        "status": "passed",
        "row_count": len(rows),
        "rows": rows,
        "canva_parity_claimed": False,
    }


def visual_priority_matrix_markdown(matrix: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Visual Priority Matrix",
            "",
            f"- Status: `{matrix['status']}`",
            f"- Row count: `{matrix['row_count']}`",
            "- Primary claims bind to focal object regions; citations remain footer-bound.",
        ]
    )
