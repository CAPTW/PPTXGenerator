"""Phase 3 semantic content hashing and artifact provenance envelopes."""

from __future__ import annotations

import copy
import datetime as dt
import platform
import subprocess
from pathlib import Path
from typing import Any

from .identity import content_sha256, stable_id


BUILD_BASELINE = "e0259b7551c381f8c0de4cdd329d5943680fa502"
PRODUCER_NAME = "presentation_agent.deckcompiler.phase3"
PRODUCER_VERSION = "3.0.0"
RUNTIME_FIELDS = {
    "run_id",
    "started_at",
    "updated_at",
    "completed_at",
    "runtime_duration_ms",
}


def semantic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the producer-owned semantic payload, excluding runtime/envelope data."""

    value = copy.deepcopy(payload)
    value.pop("artifact", None)
    for field in RUNTIME_FIELDS:
        value.pop(field, None)
    return value


def semantic_content_sha256(payload: dict[str, Any]) -> str:
    return content_sha256(semantic_payload(payload))


def seal_artifact(
    payload: dict[str, Any],
    *,
    artifact_type: str,
    input_artifact_ids: tuple[str, ...] = (),
    source_commit: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Attach a deterministic Phase 3 envelope whose hash binds actual content."""

    if "artifact" in payload:
        raise ValueError("payload is already sealed")
    digest = semantic_content_sha256(payload)
    artifact = {
        "artifact_id": stable_id("art", artifact_type, digest),
        "artifact_type": artifact_type,
        "artifact_version": "1.1.0",
        "product": {
            "product_name": "PPTX Generator",
            "product_slug": "pptx-generator",
            "system_name": "DeckCompiler",
            "system_id": "deckcompiler",
            "reconstruction_engine": "PNGtoPPTX",
        },
        "provenance": {
            "created_at": created_at or _utc_now(),
            "producer": {
                "tool_name": PRODUCER_NAME,
                "tool_version": PRODUCER_VERSION,
                "runtime": f"Python {platform.python_version()}",
            },
            "build_baseline": BUILD_BASELINE,
            "source_commit": source_commit or current_source_commit(),
            "input_artifact_ids": list(input_artifact_ids),
        },
        "content_sha256": digest,
    }
    return {**payload, "artifact": artifact}


def verify_artifact_content_hash(payload: dict[str, Any]) -> None:
    expected = str(payload.get("artifact", {}).get("content_sha256") or "")
    actual = semantic_content_sha256(payload)
    if expected != actual:
        raise ValueError(
            "DC_PRODUCER_CONTENT_HASH_MISMATCH: "
            f"artifact content_sha256 {expected or '<missing>'} does not match semantic payload {actual}"
        )


def current_source_commit() -> str:
    root = Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return BUILD_BASELINE
    candidate = result.stdout.strip().lower()
    return candidate if len(candidate) == 40 and all(char in "0123456789abcdef" for char in candidate) else BUILD_BASELINE


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "BUILD_BASELINE",
    "PRODUCER_NAME",
    "PRODUCER_VERSION",
    "current_source_commit",
    "seal_artifact",
    "semantic_content_sha256",
    "semantic_payload",
    "verify_artifact_content_hash",
]
