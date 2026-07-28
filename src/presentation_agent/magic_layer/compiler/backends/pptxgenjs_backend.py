from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PptxGenJsBackend:
    backend_name: str = "pptxgenjs"
    available: bool = False
