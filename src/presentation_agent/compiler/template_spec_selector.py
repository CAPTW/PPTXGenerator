"""Select the editable template spec source for layout matching and deck compilation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from ..generator_contracts import validateEditableTemplateSpec


DEFAULT_BASE_TEMPLATE_SPEC_PATH = Path("outputs/editable_template_spec.json")
DEFAULT_FINAL_TEMPLATE_SPEC_PATH = Path("outputs/editable_template_spec.final.json")


@dataclass(frozen=True, slots=True)
class TemplateSpecSelection:
    path: Path
    spec: dict[str, Any]
    source: dict[str, Any]


def select_template_spec(
    *,
    base_template_spec_path: str | Path = DEFAULT_BASE_TEMPLATE_SPEC_PATH,
    final_template_spec_path: str | Path = DEFAULT_FINAL_TEMPLATE_SPEC_PATH,
    prefer_final: bool = True,
) -> TemplateSpecSelection:
    base_path = Path(base_template_spec_path)
    final_path = Path(final_template_spec_path)
    warnings: list[dict[str, Any]] = []

    if prefer_final and final_path.exists():
        try:
            final_spec = _load_valid_spec(final_path)
            return TemplateSpecSelection(
                path=final_path,
                spec=final_spec,
                source={
                    "path": _display_path(final_path),
                    "selection": "final",
                    "fallback_reason": None,
                    "warnings": [],
                },
            )
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            warnings.append(
                {
                    "code": "TEMPLATE_SPEC_FINAL_INVALID_FALLBACK",
                    "message": f"Final editable template spec was invalid or unreadable; using base spec. Detail: {exc}",
                    "severity": "warning",
                    "template_spec_path": _display_path(final_path),
                }
            )

    base_spec = _load_valid_spec(base_path)
    return TemplateSpecSelection(
        path=base_path,
        spec=base_spec,
        source={
            "path": _display_path(base_path),
            "selection": "base",
            "fallback_reason": "final_invalid_or_missing" if warnings else None,
            "warnings": warnings,
        },
    )


def load_explicit_template_spec(template_spec_path: str | Path) -> TemplateSpecSelection:
    path = Path(template_spec_path)
    spec = _load_valid_spec(path)
    selection = "final" if path.name == DEFAULT_FINAL_TEMPLATE_SPEC_PATH.name else "base" if path.name == DEFAULT_BASE_TEMPLATE_SPEC_PATH.name else "explicit"
    return TemplateSpecSelection(
        path=path,
        spec=spec,
        source={
            "path": _display_path(path),
            "selection": selection,
            "fallback_reason": None,
            "warnings": [],
        },
    )


def _load_valid_spec(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validateEditableTemplateSpec(payload)
    return payload


def _display_path(path: Path) -> str:
    return str(path.as_posix())
