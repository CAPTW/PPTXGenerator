"""Canonical JSON readers and atomic writers for DeckCompiler manifests."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: str | Path) -> dict[str, Any]:
    artifact_path = Path(path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {artifact_path}")
    return payload


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    artifact_path = Path(path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        dir=artifact_path.parent,
        prefix=f".{artifact_path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(artifact_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return artifact_path


__all__ = ["read_json", "write_json"]
