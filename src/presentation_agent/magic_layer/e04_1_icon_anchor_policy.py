"""Semantic component anchor policy for E04.1 icons."""

from __future__ import annotations


ANCHOR_COMPONENTS = (
    "card bbox",
    "table header cell bbox",
    "table row/status cell bbox",
    "KPI card bbox",
    "side rail bbox",
    "process node bbox",
    "timeline milestone bbox",
    "footer/source bbox",
    "title/meta bar bbox",
    "chart/legend marker bbox",
    "note/insight panel bbox",
)


ANCHOR_POSITIONS = (
    "top_left",
    "center_left",
    "center",
    "top_right",
    "badge_corner",
    "inline_before_text",
    "footer_lead",
    "side_rail_center",
    "timeline_node_center",
)


def build_semantic_icon_anchor_policy_v1() -> dict[str, object]:
    return {
        "schema_name": "semantic_icon_anchor_policy_v1",
        "status": "passed",
        "allowed_anchor_components": ANCHOR_COMPONENTS,
        "allowed_anchor_positions": ANCHOR_POSITIONS,
        "requirements": {
            "anchor_component_id_required": True,
            "anchor_bbox_required": True,
            "anchor_position_required": True,
            "padding_required": True,
            "semantic_unanchored_is_fatal": True,
            "z_order": "above component background; below unrelated overlay; never hidden behind panels",
        },
    }
