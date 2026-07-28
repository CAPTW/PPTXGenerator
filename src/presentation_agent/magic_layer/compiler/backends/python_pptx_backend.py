from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PythonPptxBackend:
    backend_name: str = "python_pptx"
    available: bool = False
