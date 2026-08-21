"""Explicit, sealed runtime profiles for Codex slide reconstruction workers.

The profile controls only model routing and bounded concurrency.  Prompts,
Semantic Sidecars, renderer inputs, compilation, and QA remain deterministic and
identical across profiles so a model change cannot silently change the workflow
contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_EXECUTION_PROFILE = "sol-medium"
EXECUTION_PROFILE_NAMES = ("sol-medium", "luna-max")
_LEGACY_ALIASES = {
    "fast-quality-20": "sol-medium",
    "fast-quality-streaming-20": "sol-medium",
}


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    name: str
    model: str
    reasoning_effort: str
    max_imagegen_parallel_slides: int = 20
    max_reconstruction_workers: int = 6
    fallback_profile: str | None = None

    def payload(self) -> dict[str, Any]:
        fallback_triggers = (
            [
                "authoring_contract_failure",
                "reconstruction_hardlock_failure",
                "visual_qa_blocking",
            ]
            if self.fallback_profile
            else []
        )
        return {
            "profile_name": self.name,
            "target_model": self.model,
            "target_reasoning_effort": self.reasoning_effort,
            "max_imagegen_parallel_slides": self.max_imagegen_parallel_slides,
            "max_reconstruction_workers": self.max_reconstruction_workers,
            "fallback_policy": {
                "profile_name": self.fallback_profile,
                "scope": "failed_slide_only",
                "max_attempts": 1 if self.fallback_profile else 0,
                "triggers": fallback_triggers,
                "quality_gate_bypass_forbidden": True,
            },
            "determinism_contract": {
                "architect_blueprint_shared": True,
                "image_prompts_shared": True,
                "semantic_sidecars_shared": True,
                "renderer_contract_shared": True,
                "vector_policy_id": "vector-first-v1",
                "compiler_and_qa_shared": True,
            },
            "worker_context": {
                "mode": "minimal_locked",
                "codex_argv": [
                    "--ephemeral",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--disable",
                    "plugins",
                    "--disable",
                    "apps",
                    "--disable",
                    "memories",
                    "--disable",
                    "multi_agent",
                    "--disable",
                    "image_generation",
                ],
                "sealed_single_slide_job_only": True,
                "full_skill_catalog_forbidden": True,
                "explicit_renderer_skill_path_required": True,
            },
        }


_PROFILES = {
    "sol-medium": ExecutionProfile(
        name="sol-medium",
        model="gpt-5.6-sol",
        reasoning_effort="medium",
    ),
    "luna-max": ExecutionProfile(
        name="luna-max",
        model="gpt-5.6-luna",
        reasoning_effort="max",
        fallback_profile="sol-medium",
    ),
}


def resolve_execution_profile(name: str | None) -> ExecutionProfile:
    """Resolve a public profile name and reject silent model fallbacks."""

    normalized = (name or DEFAULT_EXECUTION_PROFILE).strip().lower()
    normalized = _LEGACY_ALIASES.get(normalized, normalized)
    try:
        return _PROFILES[normalized]
    except KeyError as exc:
        supported = ", ".join(EXECUTION_PROFILE_NAMES)
        raise ValueError(
            f"unknown execution profile {name!r}; expected one of: {supported}"
        ) from exc


def execution_profile_payload(name: str | None) -> dict[str, Any]:
    return resolve_execution_profile(name).payload()


__all__ = [
    "DEFAULT_EXECUTION_PROFILE",
    "EXECUTION_PROFILE_NAMES",
    "ExecutionProfile",
    "execution_profile_payload",
    "resolve_execution_profile",
]
