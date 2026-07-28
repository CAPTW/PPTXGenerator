"""Deterministic identity and content hashing for DeckCompiler artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Return the stable UTF-8 JSON representation used by all identity helpers."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def content_sha256(value: Any) -> str:
    """Hash JSON-compatible content independently of mapping insertion order."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def stable_id(prefix: str, *components: Any) -> str:
    """Create a namespaced, deterministic identifier from canonical components."""

    if not prefix or not prefix.replace("_", "").isalnum() or not prefix.islower():
        raise ValueError("stable ID prefix must contain lowercase alphanumeric characters or underscores")
    digest = content_sha256({"namespace": "deckcompiler", "components": components})
    return f"{prefix}_{digest[:20]}"


def stable_source_id(source_type: str, stable_identity: Any) -> str:
    return stable_id("src", source_type, stable_identity)


def stable_evidence_id(source_id: str, source_locator: Any, canonical_content: Any) -> str:
    return stable_id("ev", source_id, source_locator, canonical_content)


__all__ = [
    "canonical_json_bytes",
    "content_sha256",
    "stable_evidence_id",
    "stable_id",
    "stable_source_id",
]
