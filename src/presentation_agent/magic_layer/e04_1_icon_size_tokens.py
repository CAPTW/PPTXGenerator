"""Role/context-specific icon size token policy for E04.1."""

from __future__ import annotations


SIZE_TOKENS: dict[str, dict[str, float | str]] = {
    "icon_micro_qa": {"min_in": 0.10, "max_in": 0.16, "default_in": 0.13, "semantic_use": "qa_only"},
    "icon_header_micro": {"min_in": 0.12, "max_in": 0.18, "default_in": 0.16, "semantic_use": "header"},
    "icon_table_header": {"min_in": 0.12, "max_in": 0.20, "default_in": 0.18, "semantic_use": "table"},
    "icon_footer_source": {"min_in": 0.14, "max_in": 0.22, "default_in": 0.18, "semantic_use": "footer"},
    "icon_kpi": {"min_in": 0.18, "max_in": 0.28, "default_in": 0.24, "semantic_use": "kpi"},
    "icon_card_small": {"min_in": 0.20, "max_in": 0.30, "default_in": 0.26, "semantic_use": "card"},
    "icon_card_primary": {"min_in": 0.28, "max_in": 0.44, "default_in": 0.34, "semantic_use": "primary_card"},
    "icon_side_rail": {"min_in": 0.24, "max_in": 0.40, "default_in": 0.32, "semantic_use": "rail"},
    "icon_process_node": {"min_in": 0.18, "max_in": 0.32, "default_in": 0.24, "semantic_use": "process"},
    "icon_timeline_marker": {"min_in": 0.14, "max_in": 0.24, "default_in": 0.20, "semantic_use": "timeline"},
    "icon_decision_marker": {"min_in": 0.22, "max_in": 0.36, "default_in": 0.30, "semantic_use": "decision"},
    "icon_hero_meta": {"min_in": 0.18, "max_in": 0.30, "default_in": 0.24, "semantic_use": "hero_meta"},
}


def build_semantic_icon_size_token_policy_v1() -> dict[str, object]:
    return {
        "schema_name": "semantic_icon_size_token_policy_v1",
        "status": "passed",
        "tokens": SIZE_TOKENS,
        "rules": [
            "semantic icons must use context-specific size tokens",
            "qa diagnostic icons must not count as semantic icons",
            "semantic icon sizes must not all collapse to one 0.17 inch diagnostic size",
        ],
    }


def size_for_token(token: str) -> float:
    return float(SIZE_TOKENS[token]["default_in"])


def token_pass(token: str, size_in: float) -> bool:
    spec = SIZE_TOKENS[token]
    return float(spec["min_in"]) <= size_in <= float(spec["max_in"])
