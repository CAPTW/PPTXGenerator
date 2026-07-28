"""Stable machine-readable DeckCompiler runtime errors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DeckCompilerError(Exception):
    code: str
    stage: str
    message: str
    artifact_path: str | None = None
    related_ids: tuple[str, ...] = ()
    severity: str = "error"
    release_blocking: bool = True
    remediation_hint: str = "Correct the input and run the stage again."

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "stage": self.stage,
            "artifact_path": self.artifact_path,
            "related_ids": list(self.related_ids),
            "severity": self.severity,
            "release_blocking": self.release_blocking,
            "message": self.message,
            "remediation_hint": self.remediation_hint,
        }


def display_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return Path(path).as_posix()


__all__ = ["DeckCompilerError", "display_path"]
