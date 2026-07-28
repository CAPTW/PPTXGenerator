"""Data-driven template archetype registry and selector."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any


REGISTRY_RESOURCE = "template_archetypes.json"
DEFAULT_ARCHETYPE_ID = "standard_content"


@dataclass(frozen=True, slots=True)
class TemplateArchetypeSelection:
    template_pack: list[dict[str, Any]]
    slide_layout_bindings: list[dict[str, str]]
    warnings: list[str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "template_pack": self.template_pack,
            "slide_layout_bindings": self.slide_layout_bindings,
            "warnings": self.warnings,
        }


def load_template_archetype_registry() -> list[dict[str, Any]]:
    with resources.files(__package__).joinpath(REGISTRY_RESOURCE).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("template archetype registry must be a list")
    return [_validate_archetype(item) for item in payload]


def selectRequiredArchetypes(
    design_brief: dict[str, Any],
    slide_blueprints: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, Any]:
    selection = select_required_archetypes(design_brief, slide_blueprints)
    return selection.to_payload()


def select_required_archetypes(
    design_brief: dict[str, Any],
    slide_blueprints: dict[str, Any] | list[dict[str, Any]],
) -> TemplateArchetypeSelection:
    registry = load_template_archetype_registry()
    by_id = {item["id"]: item for item in registry}
    by_slide_type = _index_by_slide_type(registry)
    slides = _normalize_slides(slide_blueprints)
    requested_archetypes = _dedupe(_string_list(design_brief.get("slide_archetypes_needed")))
    warnings: list[str] = []
    selected_ids: list[str] = []
    bindings: list[dict[str, str]] = []

    for index, slide in enumerate(slides, start=1):
        slide_id = str(slide.get("slide_id") or slide.get("id") or f"slide-{index:03d}")
        slide_type = _normalize_key(slide.get("slide_type") or slide.get("slide_role") or slide.get("visual_type"))
        archetype_id = _archetype_for_slide(slide, slide_type, by_slide_type)
        if archetype_id is None:
            archetype_id = DEFAULT_ARCHETYPE_ID
            warnings.append(
                f"Slide {slide_id} has no template archetype mapping for slide_type {slide_type or '<missing>'}; "
                f"using {DEFAULT_ARCHETYPE_ID}."
            )
        _append_unique(selected_ids, archetype_id)
        bindings.append(
            {
                "slide_id": slide_id,
                "slide_type": slide_type or "",
                "archetype_id": archetype_id,
                "fallback_layout_id": by_id[archetype_id]["fallback_layout_id"],
            }
        )

    for requested in requested_archetypes:
        normalized = _normalize_key(requested)
        archetype_id = by_slide_type.get(normalized) or (normalized if normalized in by_id else None)
        if archetype_id is not None:
            _append_unique(selected_ids, archetype_id)

    if not selected_ids:
        selected_ids.append(DEFAULT_ARCHETYPE_ID)

    return TemplateArchetypeSelection(
        template_pack=[by_id[archetype_id] for archetype_id in selected_ids],
        slide_layout_bindings=bindings,
        warnings=warnings,
    )


def _validate_archetype(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("template archetype entries must be objects")
    required = {
        "id",
        "purpose",
        "required_slots",
        "optional_slots",
        "density_range",
        "compatible_slide_types",
        "recommended_components",
        "image_policy",
        "chart_policy",
        "table_policy",
        "fallback_layout_id",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"template archetype {value.get('id', '<unknown>')} missing fields: {', '.join(missing)}")
    return dict(value)


def _index_by_slide_type(registry: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for archetype in registry:
        archetype_id = str(archetype["id"])
        index[_normalize_key(archetype_id)] = archetype_id
        for slide_type in archetype.get("compatible_slide_types", []):
            index.setdefault(_normalize_key(slide_type), archetype_id)
    return index


def _archetype_for_slide(slide: dict[str, Any], slide_type: str, by_slide_type: dict[str, str]) -> str | None:
    visual_text = _slide_text(slide)
    if _has_payload(slide.get("table_data")):
        return "table_heavy"
    if _has_payload(slide.get("chart_data")):
        return "data_dashboard"
    if "table" in visual_text and slide_type not in {"comparison", "comparison_matrix"}:
        return "table_heavy"
    if any(token in visual_text for token in ("chart", "metric", "kpi", "dashboard")):
        return "data_dashboard"
    return by_slide_type.get(slide_type)


def _normalize_slides(slide_blueprints: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(slide_blueprints, list):
        return [slide for slide in slide_blueprints if isinstance(slide, dict)]
    if not isinstance(slide_blueprints, dict):
        return []
    if isinstance(slide_blueprints.get("slides"), list):
        return [slide for slide in slide_blueprints["slides"] if isinstance(slide, dict)]
    if isinstance(slide_blueprints.get("slide_blueprints"), list):
        return [slide for slide in slide_blueprints["slide_blueprints"] if isinstance(slide, dict)]
    return [slide_blueprints]


def _slide_text(slide: dict[str, Any]) -> str:
    keys = ("slide_type", "visual_type", "design_intent", "required_slots", "content_blocks")
    return " ".join(json.dumps(slide.get(key, ""), sort_keys=True).lower() for key in keys)


def _has_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return True


def _normalize_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text.replace("-", "_").replace(" ", "_")


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
