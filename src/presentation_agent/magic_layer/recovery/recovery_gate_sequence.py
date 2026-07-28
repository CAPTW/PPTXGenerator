from __future__ import annotations

from typing import Any


def build_e03_recovery_gate_sequence() -> dict[str, Any]:
    return {
        "schema": "e03_recovery_gate_sequence.v1",
        "stages": [
            {"stage": "RV01-RX", "purpose": "E03 Reference Inventory and Readiness Revalidation", "generates_pptx": False, "runs_e03": False},
            {"stage": "E03A-RV", "purpose": "Patch Missing/Invalid E03 References", "fake_references_allowed": False},
            {"stage": "E03-RV", "purpose": "Pipeline v2 E03 12-16 Archetype Recovery Validation", "requires_reference_readiness": True, "noncanonical_only": True},
            {"stage": "E04-RV", "purpose": "Source-bound Small Deck Recovery Validation", "requires_e03_pass": True},
            {"stage": "D08-RV/C11/bulk", "purpose": "Scaleout only after E04 pass", "requires_e04_pass": True},
        ],
        "transitions": {
            "RV00_to_RV01": {"allowed": True, "requires": "RV00_pass"},
            "RV01_to_E03_RV": {"allowed": False, "requires": "reference_readiness_pass"},
            "E03_RV_to_E04": {"allowed": False, "requires": "E03_RV_pass"},
            "E04_to_D08": {"allowed": False, "requires": "E04_pass"},
        },
        "product_pass": False,
    }
