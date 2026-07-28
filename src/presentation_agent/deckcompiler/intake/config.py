"""Strict local configuration loading for the Phase 3 intake modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..errors import DeckCompilerError


class Phase3Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    config_path: Path
    mode: Literal["prompt_only", "prompt_plus_two_pdfs"]
    prompt_path: Path
    prompt_reference: str
    pdf_paths: tuple[Path, ...]
    pdf_references: tuple[str, ...]
    slide_count: int = Field(ge=5, le=6)
    audience: str
    purpose: str
    language: str
    tone: tuple[str, ...]
    workflow: str
    policies: dict[str, str]
    stop_after: Literal["creative_architecture"]

    @property
    def presentation(self) -> dict[str, Any]:
        return {
            "slide_count": self.slide_count,
            "audience": self.audience,
            "purpose": self.purpose,
            "language": self.language,
            "tone": list(self.tone),
            "workflow": self.workflow,
        }


def load_phase3_config(path: str | Path) -> Phase3Config:
    config_path = Path(path).resolve()
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DeckCompilerError(
            "DC_INPUT_MISSING",
            "config_validation",
            f"configuration file is unavailable: {config_path}",
            config_path.as_posix(),
        ) from exc
    except yaml.YAMLError as exc:
        raise DeckCompilerError(
            "DC_CONFIG_INVALID",
            "config_validation",
            f"configuration is not valid YAML: {exc}",
            config_path.as_posix(),
        ) from exc
    if not isinstance(payload, dict):
        raise DeckCompilerError("DC_CONFIG_INVALID", "config_validation", "configuration root must be an object")
    try:
        _validate_identity(payload)
        mode = str(payload["mode"])
        inputs = _mapping(payload, "inputs")
        presentation = _mapping(payload, "presentation")
        policies = _mapping(payload, "policies")
        phase = _mapping(payload, "phase")
        prompt_reference = _local_reference(inputs.get("prompt"), "inputs.prompt")
        pdf_references = tuple(_local_reference(value, "inputs.pdfs[]") for value in inputs.get("pdfs", []))
        if mode == "prompt_plus_two_pdfs" and len(pdf_references) != 2:
            raise ValueError("prompt_plus_two_pdfs requires exactly two PDFs")
        if mode == "prompt_only" and pdf_references:
            raise ValueError("prompt_only does not accept PDF inputs")
        if mode not in {"prompt_only", "prompt_plus_two_pdfs"}:
            raise ValueError(f"unsupported mode: {mode}")
        tone = presentation.get("tone") or []
        if not isinstance(tone, list) or not tone:
            raise ValueError("presentation.tone must be a non-empty list")
        return Phase3Config(
            config_path=config_path,
            mode=mode,
            prompt_path=(config_path.parent / prompt_reference).resolve(),
            prompt_reference=prompt_reference,
            pdf_paths=tuple((config_path.parent / item).resolve() for item in pdf_references),
            pdf_references=pdf_references,
            slide_count=int(presentation["slide_count"]),
            audience=str(presentation["audience"]),
            purpose=str(presentation["purpose"]),
            language=str(presentation["language"]),
            tone=tuple(str(item) for item in tone),
            workflow=str(presentation["workflow"]),
            policies={str(key): str(value) for key, value in policies.items()},
            stop_after=str(phase["stop_after"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DeckCompilerError(
            "DC_CONFIG_INVALID",
            "config_validation",
            str(exc),
            config_path.as_posix(),
            remediation_hint="Use the documented Phase 3 config fields and local relative paths.",
        ) from exc


def _validate_identity(payload: dict[str, Any]) -> None:
    product = _mapping(payload, "product")
    system = _mapping(payload, "system")
    if product != {"name": "PPTX Generator", "slug": "pptx-generator"}:
        raise ValueError("product identity must be PPTX Generator / pptx-generator")
    if system != {"name": "DeckCompiler", "id": "deckcompiler"}:
        raise ValueError("system identity must be DeckCompiler / deckcompiler")


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _local_reference(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty local path")
    candidate = value.strip().replace("\\", "/")
    if "://" in candidate or Path(candidate).is_absolute() or ".." in Path(candidate).parts:
        raise ValueError(f"{field} must be a safe relative local path")
    return candidate


__all__ = ["Phase3Config", "load_phase3_config"]
