"""Base classes for optional local segmentation/model adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AdapterConfig:
    allow_model_downloads: bool = False
    enable_hf_adapters: bool = False
    model_cache_dir: str | None = None
    device: str = "auto"


@dataclass
class ProposalResult:
    adapter_id: str
    display_name: str
    status: str
    proposals: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    download_attempted: bool = False
    download_allowed: bool = False

    @property
    def real_model_proposal_count(self) -> int:
        return sum(1 for proposal in self.proposals if proposal.get("source_type") == "real_model")

    @property
    def heuristic_proposal_count(self) -> int:
        return sum(1 for proposal in self.proposals if proposal.get("source_type") == "heuristic_smoke_only")

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "display_name": self.display_name,
            "status": self.status,
            "proposal_count": len(self.proposals),
            "real_model_proposal_count": self.real_model_proposal_count,
            "heuristic_proposal_count": self.heuristic_proposal_count,
            "proposals": self.proposals,
            "warnings": self.warnings,
            "errors": self.errors,
            "download_attempted": self.download_attempted,
            "download_allowed": self.download_allowed,
            "canva_parity_claimed": False,
        }


class BaseAdapter:
    adapter_id: str
    display_name: str
    required_python_packages: list[str]
    required_model_ids_or_paths: list[str]

    def detect_availability(self, config: AdapterConfig) -> dict[str, Any]:
        raise NotImplementedError

    def run(self, reference_image_path: Path, output_dir: Path, config: AdapterConfig) -> ProposalResult:
        raise NotImplementedError
