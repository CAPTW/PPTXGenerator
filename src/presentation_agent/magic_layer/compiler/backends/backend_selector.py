from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
from typing import Any

from .minimal_ooxml_backend import MinimalOoxmlBackend
from .pptxgenjs_backend import PptxGenJsBackend
from .python_pptx_backend import PythonPptxBackend


@dataclass(frozen=True)
class BackendSelection:
    backend_name: str
    backend: Any
    dependency_install_attempted: bool
    candidates: list[dict[str, Any]]
    selected_reason: str
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["backend"] = {"backend_name": self.backend_name}
        return data


def select_backend(bundle: dict[str, Any] | None = None) -> BackendSelection:
    """Select a local backend without installing dependencies."""

    candidates: list[dict[str, Any]] = []

    pptxgen = PptxGenJsBackend(available=False)
    candidates.append(
        {
            "backend_name": pptxgen.backend_name,
            "available": pptxgen.available,
            "dependency_evidence": "Node package availability is not required for C02 minimal smoke test.",
            "can_create_minimal_cover_hero": False,
            "dependency_install_attempted": False,
        }
    )

    python_pptx_available = find_spec("pptx") is not None
    python_pptx = PythonPptxBackend(available=python_pptx_available)
    candidates.append(
        {
            "backend_name": python_pptx.backend_name,
            "available": python_pptx.available,
            "dependency_evidence": "importlib.util.find_spec('pptx')",
            "can_create_minimal_cover_hero": False,
            "dependency_install_attempted": False,
        }
    )

    minimal = MinimalOoxmlBackend()
    candidates.append(
        {
            "backend_name": minimal.backend_name,
            "available": True,
            "dependency_evidence": "stdlib zipfile/xml only",
            "can_create_minimal_cover_hero": True,
            "dependency_install_attempted": False,
        }
    )

    return BackendSelection(
        backend_name=minimal.backend_name,
        backend=minimal,
        dependency_install_attempted=False,
        candidates=candidates,
        selected_reason="Minimal deterministic OOXML backend is sufficient for the one-slide C02 smoke test and requires no dependency install.",
        limitations=[
            "minimal_cover_hero_only",
            "no_images",
            "no_charts",
            "no_tables",
            "not_general_pptx_compiler",
        ],
    )


def backend_selection_report(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    selection = select_backend(bundle)
    return {
        "schema": "compiler_backend_selection_report.v1",
        "backend_candidates": selection.candidates,
        "selected_backend": selection.backend_name,
        "reason": selection.selected_reason,
        "limitations": selection.limitations,
        "supported_object_types": selection.backend.supported_object_types,
        "unsupported_object_types": selection.backend.unsupported_object_types,
        "can_create_minimal_cover_hero_sample": True,
        "can_set_stable_object_names": True,
        "can_avoid_full_slide_raster": True,
        "can_avoid_semantic_raster": True,
        "writes_only_c02_output_folder": True,
        "dependency_install_attempted": False,
    }
