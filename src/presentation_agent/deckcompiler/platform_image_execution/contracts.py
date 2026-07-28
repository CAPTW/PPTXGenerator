"""Versioned records for Codex platform-managed image generation.

This module contains no provider client, credential resolver, endpoint, or network
transport.  The actual tool invocation remains an orchestrator action; repository
code only prepares requests and verifies local artifacts returned by that action.
"""

from __future__ import annotations

import copy
from typing import Any

from ..identity import content_sha256, stable_id


def hash_bound_payload(payload: dict[str, Any], hash_field: str) -> dict[str, Any]:
    """Return a copy with ``hash_field`` bound to the canonical remaining payload."""

    value = copy.deepcopy(payload)
    value.pop(hash_field, None)
    value[hash_field] = content_sha256(value)
    return value


def verify_hash_bound_payload(payload: dict[str, Any], hash_field: str) -> bool:
    expected = payload.get(hash_field)
    if not isinstance(expected, str):
        return False
    value = copy.deepcopy(payload)
    value.pop(hash_field, None)
    return content_sha256(value) == expected


def build_capability_attestation() -> dict[str, Any]:
    """Describe only capabilities exposed by the current built-in tool interface.

    No generation is performed here. Values that require a live result remain
    explicitly unobserved until the Phase 4C canary.
    """

    observed = {
        "execution_mode": "platform_managed_tool",
        "tool_available": True,
        "platform_tool_id": "image_gen.imagegen",
        "platform_tool_channel": "commentary",
        "image_model": "not_exposed_by_tool",
        "result_contract_exposes_bytes": True,
        "actual_output_bytes_observed": False,
        "reference_image_support": True,
        "landscape_generation_support": True,
        "requested_dimension_support": "prompt_only_not_parameterized",
        "output_format": "not_observed_before_canary",
        "tool_call_id_exposure": "not_exposed",
        "platform_managed_credential_status": "not_exposed",
        "external_provider_id": None,
        "external_transport_used": False,
        "repository_network_calls": 0,
        "credential_lookups": 0,
        "platform_tool_invocations": 0,
        "capability_status": "READY_FOR_CANARY",
    }
    return {
        "schema_name": "platform_image_capability_attestation",
        "schema_version": "1.0.0",
        "attestation_id": stable_id("capability", observed),
        **observed,
    }
