"""Scaleout override for E04-R3 after E01H re-focus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_e04_r3_scaleout_override(e04_r3_root: str | Path) -> dict[str, Any]:
    root = Path(e04_r3_root)
    final_path = root / "e04_r3_final_decision.json"
    final = json.loads(final_path.read_text(encoding="utf-8")) if final_path.exists() else {}
    return {
        "schema_name": "e04_r3_scaleout_override",
        "status": "blocked",
        "original_e04_r3_decision": final.get("decision", "missing"),
        "e04_r3_source_bound_generation_pass": final.get("status") == "passed",
        "e04_r3_editorial_integrity_pass": final.get("decision") == "E04_R3_PASS_READY_FOR_E05_34_SLIDE_SCALEOUT",
        "e04_r3_magic_layer_conversion_pass": False,
        "e05_unlocked": False,
        "reason": "E04-R3 proves source-bound editable deck generation, not reference-image-to-editable-layer conversion.",
        "next_required_stage": "E01H_HIGH_FIDELITY_HYBRID_CANVA_PLUS_SINGLE_REFERENCE",
        "e05_started": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }


def build_e05_readiness_after_e01h(e01h_gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "e05_readiness_after_e01h",
        "status": "blocked",
        "e05_unlocked": False,
        "e02h_unlocked": e01h_gate.get("status") == "passed",
        "reason": "E01H is a single-reference Magic Layer conversion gate; it unlocks E02H only, not 34-slide E05 scaleout.",
        "e05_started": False,
        "large_deck_generated": False,
        "canva_parity_claimed": False,
    }


def scaleout_override_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E04-R3 Scaleout Override",
            "",
            f"- Status: `{report['status']}`",
            f"- Original E04-R3 decision: `{report['original_e04_r3_decision']}`",
            f"- E05 unlocked: `{report['e05_unlocked']}`",
            f"- Next required stage: `{report['next_required_stage']}`",
            f"- Reason: {report['reason']}",
        ]
    )


def e05_readiness_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E05 Readiness After E01H",
            "",
            f"- Status: `{report['status']}`",
            f"- E02H unlocked: `{report['e02h_unlocked']}`",
            f"- E05 unlocked: `{report['e05_unlocked']}`",
            f"- Reason: {report['reason']}",
        ]
    )
