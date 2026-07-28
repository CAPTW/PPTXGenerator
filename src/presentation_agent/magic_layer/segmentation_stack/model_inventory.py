"""Availability-aware optional model inventory for E01X."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapter_base import AdapterConfig, BaseAdapter, ProposalResult


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    display_name: str
    required_python_packages: list[str]
    required_model_ids_or_paths: list[str]
    proposal_family: str


DEFAULT_ADAPTER_SPECS = [
    AdapterSpec("paddleocr_vl", "PaddleOCR-VL / PaddleOCR-VL-1.5", ["paddleocr"], ["PaddlePaddle/PaddleOCR-VL"], "text_first_lock"),
    AdapterSpec("doclayout_yolo", "DocLayout-YOLO / Docling / DiT DocLayNet", ["docling"], ["doclayout-yolo-or-doclaynet-local"], "layout"),
    AdapterSpec("grounding_dino", "Grounding DINO", ["groundingdino"], ["grounding-dino-local"], "grounding"),
    AdapterSpec("sam2", "SAM2.1 / SAM-HQ", ["sam2"], ["sam2-local"], "masks"),
    AdapterSpec("qwen_image_layered", "Qwen-Image-Layered", ["transformers"], ["qwen-image-layered-local"], "layers"),
    AdapterSpec("layerd_birefnet", "LayerD / cyberagent layerd-birefnet", ["transformers"], ["cyberagent/layerd-birefnet"], "layers"),
    AdapterSpec("birefnet_rmbg", "BiRefNet / RMBG", ["transformers"], ["birefnet-or-rmbg-local"], "matting"),
    AdapterSpec("table_transformer", "Table Transformer", ["transformers"], ["microsoft/table-transformer-structure-recognition"], "chart_table"),
    AdapterSpec("deplot", "DePlot-style chart-to-data", ["transformers"], ["google/deplot-local"], "chart_table"),
    AdapterSpec("florence_2", "Florence-2 auxiliary OCR/OD/regions", ["transformers"], ["microsoft/Florence-2-local"], "auxiliary"),
]


class InventoryAdapter(BaseAdapter):
    def __init__(self, spec: AdapterSpec, availability: dict[str, Any]) -> None:
        self.spec = spec
        self.availability = availability
        self.adapter_id = spec.adapter_id
        self.display_name = spec.display_name
        self.required_python_packages = spec.required_python_packages
        self.required_model_ids_or_paths = spec.required_model_ids_or_paths

    def detect_availability(self, config: AdapterConfig) -> dict[str, Any]:
        return detect_adapter_availability(self.spec, config)

    def run(self, reference_image_path: Path, output_dir: Path, config: AdapterConfig) -> ProposalResult:
        status = self.detect_availability(config)["status"]
        if status != "available":
            return ProposalResult(
                adapter_id=self.adapter_id,
                display_name=self.display_name,
                status=status,
                proposals=[],
                warnings=["adapter unavailable; no proposals emitted"],
            )
        return ProposalResult(
            adapter_id=self.adapter_id,
            display_name=self.display_name,
            status="failed_runtime",
            proposals=[],
            errors=["adapter package/weights appear available but no local inference runner is implemented in this harness"],
            download_allowed=config.allow_model_downloads,
            download_attempted=False,
        )


def config_from_env() -> AdapterConfig:
    return AdapterConfig(
        allow_model_downloads=os.environ.get("ML_ALLOW_MODEL_DOWNLOADS") == "1",
        enable_hf_adapters=os.environ.get("ML_ENABLE_HF_ADAPTERS") == "1",
        model_cache_dir=os.environ.get("ML_HF_CACHE_DIR") or None,
        device=os.environ.get("ML_MODEL_DEVICE") or "auto",
    )


def detect_adapter_availability(spec: AdapterSpec, config: AdapterConfig) -> dict[str, Any]:
    if not config.enable_hf_adapters:
        status = "unavailable_disabled"
        missing_packages: list[str] = []
        missing_weights = list(spec.required_model_ids_or_paths)
    else:
        missing_packages = [package for package in spec.required_python_packages if importlib.util.find_spec(package) is None]
        missing_weights = _missing_weights(spec.required_model_ids_or_paths, config)
        if missing_packages:
            status = "unavailable_missing_package"
        elif missing_weights and not config.allow_model_downloads:
            status = "unavailable_missing_weights"
        else:
            status = "available"
    return {
        "adapter_id": spec.adapter_id,
        "display_name": spec.display_name,
        "proposal_family": spec.proposal_family,
        "required_python_packages": spec.required_python_packages,
        "required_model_ids_or_paths": spec.required_model_ids_or_paths,
        "status": status,
        "missing_python_packages": missing_packages,
        "missing_model_ids_or_paths": missing_weights,
        "downloads_allowed": config.allow_model_downloads,
        "download_attempted": False,
        "produces_fake_proposals": False,
        "canva_parity_claimed": False,
    }


def collect_model_inventory(config: AdapterConfig | None = None, specs: list[AdapterSpec] | None = None) -> dict[str, Any]:
    resolved_config = config or config_from_env()
    resolved_specs = specs or DEFAULT_ADAPTER_SPECS
    adapters = [detect_adapter_availability(spec, resolved_config) for spec in resolved_specs]
    return {
        "schema_name": "model_inventory",
        "schema_version": "1.0",
        "config": {
            "allow_model_downloads": resolved_config.allow_model_downloads,
            "enable_hf_adapters": resolved_config.enable_hf_adapters,
            "model_cache_dir": resolved_config.model_cache_dir,
            "device": resolved_config.device,
        },
        "adapters": adapters,
        "summary": {
            "adapter_count": len(adapters),
            "available_count": sum(1 for adapter in adapters if adapter["status"] == "available"),
            "unavailable_count": sum(1 for adapter in adapters if adapter["status"] != "available"),
            "downloads_attempted": 0,
            "fake_proposals_emitted": False,
        },
        "canva_parity_claimed": False,
    }


def instantiate_adapters(specs: list[AdapterSpec] | None = None, config: AdapterConfig | None = None) -> list[InventoryAdapter]:
    resolved_config = config or config_from_env()
    resolved_specs = specs or DEFAULT_ADAPTER_SPECS
    return [InventoryAdapter(spec, detect_adapter_availability(spec, resolved_config)) for spec in resolved_specs]


def adapter_availability_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Adapter Availability Report",
        "",
        f"- HF adapters enabled: `{inventory['config']['enable_hf_adapters']}`",
        f"- Model downloads allowed: `{inventory['config']['allow_model_downloads']}`",
        f"- Available adapters: `{inventory['summary']['available_count']}`",
        f"- Unavailable adapters: `{inventory['summary']['unavailable_count']}`",
        "- Fake proposals emitted: `False`",
        "- Canva parity claimed: `False`",
        "",
        "| Adapter | Family | Status | Missing packages | Missing weights/paths |",
        "|---|---|---|---|---|",
    ]
    for adapter in inventory["adapters"]:
        lines.append(
            "| `{adapter_id}` | `{family}` | `{status}` | `{packages}` | `{weights}` |".format(
                adapter_id=adapter["adapter_id"],
                family=adapter["proposal_family"],
                status=adapter["status"],
                packages=", ".join(adapter.get("missing_python_packages", [])) or "-",
                weights=", ".join(adapter.get("missing_model_ids_or_paths", [])) or "-",
            )
        )
    return "\n".join(lines) + "\n"


def _missing_weights(required: list[str], config: AdapterConfig) -> list[str]:
    missing: list[str] = []
    cache_dir = Path(config.model_cache_dir).resolve() if config.model_cache_dir else None
    for model_id_or_path in required:
        candidate = Path(model_id_or_path)
        if candidate.exists():
            continue
        if cache_dir is not None and (cache_dir / model_id_or_path.replace("/", os.sep)).exists():
            continue
        missing.append(model_id_or_path)
    return missing
