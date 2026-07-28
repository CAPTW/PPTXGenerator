"""Semantic role voting and prefix mapping for E01X fused objects."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .schemas import ROLE_ONTOLOGY


PREFIX_BY_ROLE = {
    "title_text_region": "T",
    "subtitle_text_region": "T",
    "body_text_region": "T",
    "source_footer_strip": "F",
    "card_panel": "S",
    "checklist_panel": "S",
    "icon_region": "I",
    "chart_region": "C",
    "table_region": "TB",
    "matrix_region": "S",
    "process_node": "S",
    "timeline_phase": "S",
    "connector": "S",
    "technical_overlay": "S",
    "hero_visual_field": "IMG",
    "replaceable_image_frame": "IMG",
    "background_base": "S",
    "decorative_texture": "D",
    "accent_line": "D",
    "shadow_or_glow": "D",
    "unknown": "UNKNOWN",
}

SEMANTIC_ROLES = {
    "title_text_region",
    "subtitle_text_region",
    "body_text_region",
    "source_footer_strip",
    "card_panel",
    "checklist_panel",
    "icon_region",
    "chart_region",
    "table_region",
    "matrix_region",
    "process_node",
    "timeline_phase",
    "connector",
    "technical_overlay",
}


def role_prefix(role: str) -> str:
    return PREFIX_BY_ROLE.get(role, "UNKNOWN")


def is_semantic_role(role: str) -> bool:
    return role in SEMANTIC_ROLES


def is_text_role(role: str) -> bool:
    return role in {"title_text_region", "subtitle_text_region", "body_text_region", "source_footer_strip"}


def vote_role(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    scores: dict[str, float] = defaultdict(float)
    evidence: list[dict[str, Any]] = []
    for proposal in proposals:
        for candidate in proposal.get("role_candidates", []):
            role = candidate.get("role", "unknown")
            if role not in ROLE_ONTOLOGY:
                role = "unknown"
            score = float(candidate.get("confidence", proposal.get("confidence", 0)))
            scores[role] += score
            evidence.append(
                {
                    "proposal_id": proposal.get("proposal_id"),
                    "source_adapter": proposal.get("source_adapter"),
                    "role": role,
                    "confidence": score,
                }
            )
    winning_role = max(scores.items(), key=lambda item: item[1])[0] if scores else "unknown"
    return {
        "winning_role": winning_role,
        "scores": dict(sorted(scores.items())),
        "evidence": evidence,
    }
