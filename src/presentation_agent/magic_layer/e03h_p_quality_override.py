"""Quality override record for E03H-P."""

from __future__ import annotations


def build_e03h_p_quality_override(original_decision: str) -> dict[str, object]:
    return {
        "schema_name": "e03h_p_quality_override",
        "status": "active",
        "original_e03h_decision": original_decision,
        "structural_hybrid_pass": True,
        "semantic_editability_pass": True,
        "visual_reference_pack_quality_pass": False,
        "e04h_unlocked": False,
        "e05_unlocked": False,
        "reason": "E03H accepted several sparse or skeleton-like references.",
        "next_required_stage": "E03H_P_WEAK_REFERENCE_QUALITY_PATCH",
        "canva_parity_claimed": False,
    }


def e03h_p_quality_override_markdown(report: dict[str, object]) -> str:
    return "\n".join(
        [
            "# E03H-P Quality Override",
            "",
            f"- Original E03H decision: `{report['original_e03h_decision']}`",
            f"- Visual reference pack quality pass: `{report['visual_reference_pack_quality_pass']}`",
            f"- E04H unlocked: `{report['e04h_unlocked']}`",
            f"- E05 unlocked: `{report['e05_unlocked']}`",
            f"- Reason: {report['reason']}",
            "- Broad Canva parity claimed: `False`",
        ]
    )
