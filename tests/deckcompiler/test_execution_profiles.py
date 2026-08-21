from __future__ import annotations

import pytest

from presentation_agent.deckcompiler.cli import build_parser
from presentation_agent.deckcompiler.orchestration.execution_profiles import (
    execution_profile_payload,
    resolve_execution_profile,
)


def test_sol_medium_is_the_explicit_default_contract() -> None:
    profile = resolve_execution_profile(None)
    payload = profile.payload()

    assert (profile.name, profile.model, profile.reasoning_effort) == (
        "sol-medium",
        "gpt-5.6-sol",
        "medium",
    )
    assert payload["max_imagegen_parallel_slides"] == 20
    assert payload["max_reconstruction_workers"] == 6
    assert payload["fallback_policy"]["profile_name"] is None
    assert payload["worker_context"]["mode"] == "minimal_locked"
    assert payload["worker_context"]["full_skill_catalog_forbidden"] is True


def test_luna_max_changes_only_runtime_routing_and_failed_slide_fallback() -> None:
    sol = execution_profile_payload("sol-medium")
    luna = execution_profile_payload("luna-max")

    assert (luna["target_model"], luna["target_reasoning_effort"]) == (
        "gpt-5.6-luna",
        "max",
    )
    assert luna["determinism_contract"] == sol["determinism_contract"]
    assert luna["worker_context"] == sol["worker_context"]
    assert luna["fallback_policy"]["profile_name"] == "sol-medium"
    assert luna["fallback_policy"]["scope"] == "failed_slide_only"
    assert luna["fallback_policy"]["quality_gate_bypass_forbidden"] is True


def test_legacy_profile_alias_resolves_but_is_not_a_public_cli_choice() -> None:
    assert resolve_execution_profile("fast-quality-20").name == "sol-medium"
    parser = build_parser()
    parsed = parser.parse_args(["generate", "--prompt", "deck"])
    assert parsed.execution_profile == "sol-medium"
    parsed = parser.parse_args(
        ["generate", "--prompt", "deck", "--execution-profile", "luna-max"]
    )
    assert parsed.execution_profile == "luna-max"
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["generate", "--prompt", "deck", "--execution-profile", "fast-quality-20"]
        )


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown execution profile"):
        resolve_execution_profile("auto")
