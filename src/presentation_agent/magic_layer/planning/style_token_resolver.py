from __future__ import annotations

from copy import deepcopy
from typing import Any


def resolve_style_tokens(style: dict[str, Any] | None, tokens: dict[str, Any] | None = None, required: bool = False) -> dict[str, Any]:
    source = deepcopy(style or {})
    token_map = tokens or {}
    warnings: list[str] = []
    blockers: list[str] = []
    resolved: dict[str, Any] = {}
    for key, value in source.items():
        if isinstance(value, str) and value.startswith("token:"):
            token_name = value.split(":", 1)[1]
            if token_name in token_map:
                resolved[key] = token_map[token_name]
            else:
                message = f"unresolved style token: {token_name}"
                (blockers if required else warnings).append(message)
                resolved[key] = value
        else:
            resolved[key] = value
    return {
        "schema": "style_token_resolution.v1",
        "pass": not blockers,
        "resolved_style": resolved,
        "warnings": warnings,
        "blockers": blockers,
    }
