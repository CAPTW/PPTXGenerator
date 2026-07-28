from __future__ import annotations

from typing import Any


P02_ALLOWED_MODES = {"IMPORT_EXISTING", "DRY_RUN_ONLY"}


def build_pipeline_mode_policy() -> dict[str, Any]:
    modes = {
        "IMPORT_EXISTING": {
            "read_existing_artifacts": True,
            "validate_lineage_and_gates": True,
            "generation_allowed": False,
            "compile_allowed": False,
            "render_allowed": False,
            "allowed_in_p02": True,
        },
        "DRY_RUN_ONLY": {
            "read_existing_artifacts": True,
            "simulate_stage_ordering": True,
            "generation_allowed": False,
            "compile_allowed": False,
            "render_allowed": False,
            "allowed_in_p02": True,
        },
        "CONTROLLED_COMPILE": {
            "may_create_one_controlled_pptx": True,
            "allowed_in_p02": False,
            "requires_explicit_prompt": True,
        },
        "CONTROLLED_RENDER": {
            "may_render_one_controlled_pptx": True,
            "allowed_in_p02": False,
            "requires_explicit_prompt": True,
        },
        "RECOVERY_VALIDATION": {"allowed_in_p02": False, "requires_explicit_future_prompt": True},
        "SOURCE_BOUND": {"allowed_in_p02": False, "requires_e03_pass": True},
        "SCALEOUT": {"allowed_in_p02": False, "requires_e04_pass": True},
    }
    return {
        "schema": "pipeline_mode_policy.v1",
        "default_mode": "IMPORT_EXISTING",
        "p02_allowed_modes": sorted(P02_ALLOWED_MODES),
        "modes": modes,
        "product_pass": False,
        "scaleout_allowed": False,
        "canonical_promotion_allowed": False,
    }


def normalize_mode(mode: str) -> str:
    return mode.upper().replace("-", "_")


def check_mode_allowed(mode: str, *, phase: str = "P02") -> dict[str, Any]:
    normalized = normalize_mode(mode)
    allowed = normalized in P02_ALLOWED_MODES if phase.upper() == "P02" else normalized in P02_ALLOWED_MODES
    reason = "Mode is allowed for P02 import/dry-run orchestration." if allowed else "P02 blocks generation, compile, render, source-bound, recovery, and scaleout modes."
    return {"schema": "pipeline_mode_check.v1", "mode": normalized, "phase": phase, "allowed": allowed, "reason": reason, "product_pass": False}
