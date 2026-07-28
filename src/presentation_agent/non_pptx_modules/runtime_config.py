"""Runtime configuration for local phase-by-phase and end-to-end execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator, model_validator

from ..compat.presentation_contracts import ContractModel


class ProviderSettings(ContractModel):
    provider: str = "local-none"
    model: str | None = None
    endpoint: str | None = None
    profile: str | None = None
    options: dict[str, str] = Field(default_factory=dict)


def parse_provider_option_items(values: list[str] | None) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"provider options must use KEY=VALUE form: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("provider option key must not be empty")
        options[key] = value.strip()
    return options


class BatchParameters(ContractModel):
    extended_max_slides: int = 8
    large_deck_max_slides: int = 6
    mega_deck_max_slides: int = 5

    @field_validator("extended_max_slides", "large_deck_max_slides", "mega_deck_max_slides")
    @classmethod
    def _validate_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("batch parameters must be positive integers")
        return value

    def as_override_map(self) -> dict[str, int]:
        return {
            "extended": self.extended_max_slides,
            "large-deck": self.large_deck_max_slides,
            "mega-deck": self.mega_deck_max_slides,
        }


class RuntimePaths(ContractModel):
    brief_path: str
    reference_pack_path: str | None = None
    brand_inputs_path: str | None = None
    notes_path: str | None = None
    state_dir: str = "state"
    output_root: str = "outputs/runtime"
    gate2_dir: str | None = None
    orchestration_dir: str | None = None
    asset_dir: str | None = None
    visual_dir: str | None = None
    deck_build_dir: str | None = None

    @model_validator(mode="after")
    def _default_output_dirs(self) -> "RuntimePaths":
        output_root = self.output_root.rstrip("/\\")
        if self.gate2_dir is None:
            self.gate2_dir = f"{output_root}/gate2"
        if self.orchestration_dir is None:
            self.orchestration_dir = f"{output_root}/orchestration"
        if self.asset_dir is None:
            self.asset_dir = f"{output_root}/assets"
        if self.visual_dir is None:
            self.visual_dir = f"{output_root}/visuals"
        if self.deck_build_dir is None:
            self.deck_build_dir = f"{output_root}/deck-build"
        return self


class RuntimePipelineConfig(ContractModel):
    schema_name: str = "runtime_pipeline_config"
    schema_version: str = "1.0"
    paths: RuntimePaths
    slide_ratio: str = "16:9"
    render_dpi: int = 144
    crop_review_loop_limit: int = 2
    max_crop_candidates_per_source: int = 6
    blueprint_approved: bool = False
    resume_skip_completed: bool = True
    pptx_name: str = "deck.pptx"
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    batch_parameters: BatchParameters = Field(default_factory=BatchParameters)

    @field_validator("slide_ratio")
    @classmethod
    def _validate_ratio(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("slide_ratio must use W:H format")
        width, height = parts
        if float(width) <= 0 or float(height) <= 0:
            raise ValueError("slide_ratio values must be positive")
        return value

    @field_validator("render_dpi")
    @classmethod
    def _validate_dpi(cls, value: int) -> int:
        if value < 36:
            raise ValueError("render_dpi must be at least 36")
        return value

    @field_validator("crop_review_loop_limit")
    @classmethod
    def _validate_review_limit(cls, value: int) -> int:
        if value < 0 or value > 2:
            raise ValueError("crop_review_loop_limit must stay within the bounded range of 0 to 2")
        return value

    @field_validator("max_crop_candidates_per_source")
    @classmethod
    def _validate_candidate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_crop_candidates_per_source must be at least 1")
        return value


def load_runtime_config(path: str | Path) -> RuntimePipelineConfig:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
    else:
        payload = json.loads(text)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"runtime config must contain a top-level object: {config_path}")
    return RuntimePipelineConfig.model_validate(payload)


def save_runtime_config(config: RuntimePipelineConfig, path: str | Path) -> Path:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = config.model_dump(mode="json", exclude_none=True)
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    else:
        text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    config_path.write_text(text, encoding="utf-8")
    return config_path

