"""Match slide blueprints to editable template layouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..generator_contracts import validateDeckAssemblyPlan, validateEditableTemplateSpec
from .blueprint_adapter import load_valid_slide_blueprints
from .template_spec_selector import (
    DEFAULT_FINAL_TEMPLATE_SPEC_PATH,
    load_explicit_template_spec,
    select_template_spec,
)


DEFAULT_BLUEPRINT_PATH = Path("outputs/slide_blueprint.json")
DEFAULT_TEMPLATE_SPEC_PATH = Path("outputs/editable_template_spec.json")
DEFAULT_OUTPUT_PATH = Path("outputs/deck_assembly_plan.json")
FALLBACK_ARCHETYPE = "standard_content"


def build_deck_assembly_plan(
    slide_blueprints: dict[str, Any] | list[dict[str, Any]],
    editable_template_spec: dict[str, Any],
    template_spec_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validateEditableTemplateSpec(editable_template_spec)
    slides = _normalize_slides(slide_blueprints)
    layouts = editable_template_spec.get("layouts") or []
    if not layouts:
        raise ValueError("editable_template_spec.layouts must contain at least one layout")

    bindings: list[dict[str, Any]] = []
    missing_slot_warnings: list[dict[str, Any]] = []
    overflow_warnings: list[dict[str, Any]] = []
    source = template_spec_source or {"path": "in_memory", "selection": "in_memory", "fallback_reason": None, "warnings": []}
    render_warnings: list[dict[str, Any]] = list(source.get("warnings") or [])
    deck_scale = _deck_scale(len(slides))
    selected_tone = _selected_tone_variant(editable_template_spec)

    for index, slide in enumerate(slides, start=1):
        binding = _match_slide(slide, layouts, index)
        binding.setdefault("deck_scale", deck_scale)
        binding.setdefault("selected_tone_variant", selected_tone)
        bindings.append(binding)
        for warning in binding["warnings"]:
            code = warning["code"]
            if code.startswith("MISSING_SLOT"):
                missing_slot_warnings.append(warning)
            elif code.startswith("OVERFLOW"):
                overflow_warnings.append(warning)
            else:
                render_warnings.append(warning)

    plan = {
        "schema_name": "deck_assembly_plan",
        "schema_version": "1.0",
        "deck_id": _deck_id(slides, editable_template_spec),
        "selected_template_pack": editable_template_spec["design_id"],
        "deck_scale": deck_scale,
        "selected_tone_variant": selected_tone,
        "template_spec_source": source,
        "slide_layout_bindings": bindings,
        "missing_slot_warnings": missing_slot_warnings,
        "overflow_warnings": overflow_warnings,
        "render_warnings": render_warnings,
    }
    validateDeckAssemblyPlan(plan)
    return plan


def build_deck_assembly_plan_from_files(
    *,
    slide_blueprint_path: str | Path = DEFAULT_BLUEPRINT_PATH,
    template_spec_path: str | Path = DEFAULT_TEMPLATE_SPEC_PATH,
    final_template_spec_path: str | Path = DEFAULT_FINAL_TEMPLATE_SPEC_PATH,
    prefer_final_template_spec: bool = True,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    slide_blueprints, _blueprint_path = load_valid_slide_blueprints(slide_blueprint_path)
    if Path(template_spec_path) == DEFAULT_TEMPLATE_SPEC_PATH:
        selection = select_template_spec(
            base_template_spec_path=template_spec_path,
            final_template_spec_path=final_template_spec_path,
            prefer_final=prefer_final_template_spec,
        )
    else:
        selection = load_explicit_template_spec(template_spec_path)
    plan = build_deck_assembly_plan(slide_blueprints, selection.spec, template_spec_source=selection.source)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Match slide_blueprint content to editable template layouts.")
    parser.add_argument("--slide-blueprint", type=Path, default=DEFAULT_BLUEPRINT_PATH)
    parser.add_argument("--template-spec", type=Path, default=DEFAULT_TEMPLATE_SPEC_PATH)
    parser.add_argument("--final-template-spec", type=Path, default=DEFAULT_FINAL_TEMPLATE_SPEC_PATH)
    parser.add_argument("--use-base-template-spec", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = build_deck_assembly_plan_from_files(
            slide_blueprint_path=args.slide_blueprint,
            template_spec_path=args.template_spec,
            final_template_spec_path=args.final_template_spec,
            prefer_final_template_spec=not args.use_base_template_spec,
            output_path=args.output,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"MATCH_LAYOUTS_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _match_slide(slide: dict[str, Any], layouts: list[dict[str, Any]], index: int) -> dict[str, Any]:
    slide_id = str(slide.get("slide_id") or slide.get("id") or f"slide-{index:03d}")
    slide_type = _normalize_key(slide.get("slide_type") or slide.get("slide_role") or slide.get("visual_type"))
    target_archetype = _target_archetype(slide, slide_type)
    needs = _slide_needs(slide)
    scored = sorted(
        (_score_layout(slide, layout, target_archetype, needs, order) for order, layout in enumerate(layouts)),
        key=lambda item: (-item["score"], item["order"]),
    )
    selected = scored[0]["layout"] if scored else None
    if selected is None:
        return {
            "slide_id": slide_id,
            "slide_type": slide_type,
            "layout_id": "NO_LAYOUT",
            "selected_layout_id": "NO_LAYOUT",
            "slot_bindings": {},
            "component_bindings": {},
            "warnings": [
                _warning("NO_LAYOUT_AVAILABLE", slide_id, "No editable template layout was available.", severity="error")
            ],
            "failure_reason": "NO_LAYOUT_AVAILABLE",
        }

    slot_bindings, component_bindings, warnings = _bind_slots(slide, selected, needs)
    if selected.get("archetype_id") != target_archetype:
        warnings.append(
            _warning(
                "FALLBACK_LAYOUT_USED",
                slide_id,
                f"Requested archetype {target_archetype}; selected {selected.get('archetype_id')}.",
                layout_id=selected["layout_id"],
            )
        )
    warnings.extend(_support_warnings(slide_id, selected, needs))
    warnings.extend(_overflow_warnings(slide_id, selected, slide))
    warnings = _dedupe_warnings(warnings)
    failure_reason = "UNSUPPORTED_REQUIRED_NEEDS" if any(item.get("severity") == "error" for item in warnings) else None
    return {
        "slide_id": slide_id,
        "slide_type": slide_type,
        "layout_id": selected["layout_id"],
        "selected_layout_id": selected["layout_id"],
        "selection_reason": f"matched {slide_type or '<missing>'} to {selected.get('archetype_id')}",
        "slot_bindings": slot_bindings,
        "component_bindings": component_bindings,
        "warnings": warnings,
        "failure_reason": failure_reason,
    }


def _score_layout(
    slide: dict[str, Any],
    layout: dict[str, Any],
    target_archetype: str,
    needs: dict[str, bool],
    order: int,
) -> dict[str, Any]:
    score = 0
    layout_archetype = layout.get("archetype_id")
    slot_ids = _layout_slot_ids(layout)
    slot_types = _layout_slot_types(layout)
    density = _normalize_key(layout.get("density"))
    slide_density = _normalize_key(slide.get("content_density") or "medium")

    if layout_archetype == target_archetype:
        score += 100
    elif layout_archetype == FALLBACK_ARCHETYPE:
        score += 35
    if slide_density == density:
        score += 20
    elif slide_density == "high" and density == "medium":
        score += 5
    elif slide_density == "low" and density == "medium":
        score += 4
    if needs["chart"] and "chart" in slot_types:
        score += 35
    if needs["table"] and "table" in slot_types:
        score += 35
    if needs["image"] and "image" in slot_types:
        score += 35
    for required_slot in _string_list(slide.get("required_slots")):
        if _slot_supported(required_slot, slot_ids, slot_types):
            score += 6
        else:
            score -= 8
    if needs["chart"] and "chart" not in slot_types:
        score -= 40
    if needs["table"] and "table" not in slot_types:
        score -= 40
    if needs["image"] and "image" not in slot_types:
        score -= 30
    return {"layout": layout, "score": score, "order": order}


def _bind_slots(
    slide: dict[str, Any],
    layout: dict[str, Any],
    needs: dict[str, bool],
) -> tuple[dict[str, str], dict[str, str], list[dict[str, Any]]]:
    slide_id = str(slide.get("slide_id") or slide.get("id") or "slide")
    slots = layout.get("slots") or []
    slot_ids = _layout_slot_ids(layout)
    slot_bindings: dict[str, str] = {}
    component_bindings: dict[str, str] = {}
    warnings: list[dict[str, Any]] = []

    for slot in slots:
        slot_id = slot["slot_id"]
        component_bindings[slot_id] = slot.get("component_id", "")
        source = _source_for_slot(slide, slot)
        if source is not None:
            slot_bindings[slot_id] = source

    for required_slot in _string_list(slide.get("required_slots")):
        if _slot_supported(required_slot, slot_ids, _layout_slot_types(layout)):
            slot_bindings.setdefault(_matching_slot_id(required_slot, slot_ids) or required_slot, required_slot)
        else:
            warnings.append(
                _warning(
                    "MISSING_SLOT_REQUIRED",
                    slide_id,
                    f"Required blueprint slot {required_slot} is not present in selected layout.",
                    layout_id=layout["layout_id"],
                    slot_id=required_slot,
                )
            )
    if needs["chart"] and not any(slot.get("slot_type") == "chart" for slot in slots):
        warnings.append(_warning("UNSUPPORTED_CHART_NEED", slide_id, "Slide has chart_data but selected layout has no chart slot.", layout["layout_id"], severity="error"))
    if needs["table"] and not any(slot.get("slot_type") == "table" for slot in slots):
        warnings.append(_warning("UNSUPPORTED_TABLE_NEED", slide_id, "Slide has table_data but selected layout has no table slot.", layout["layout_id"], severity="error"))
    if needs["image"] and not any(slot.get("slot_type") == "image" for slot in slots):
        warnings.append(_warning("UNSUPPORTED_IMAGE_NEED", slide_id, "Slide has image needs but selected layout has no image slot.", layout["layout_id"], severity="error"))
    return slot_bindings, component_bindings, warnings


def _source_for_slot(slide: dict[str, Any], slot: dict[str, Any]) -> str | None:
    slot_id = slot["slot_id"]
    slot_type = slot["slot_type"]
    if slot_id == "title":
        return "title"
    if slot_id == "subtitle":
        return "subtitle"
    if slot_id == "footer":
        return "citations"
    if slot_type == "chart" and _has_payload(slide.get("chart_data")):
        return "chart_data"
    if slot_type == "table" and _has_payload(slide.get("table_data")):
        return "table_data"
    if slot_type == "image" and _has_payload(slide.get("image_needs")):
        return "image_needs"
    if slot_id in {"cards", "metric_panels"}:
        return "content_blocks"
    for block in slide.get("content_blocks") or []:
        if isinstance(block, dict) and _normalize_key(block.get("slot")) == _normalize_key(slot_id):
            return f"content_blocks.{block.get('block_id') or slot_id}"
    if slot_id in {"body", "cards", "roadmap_items", "case_context", "case_evidence", "takeaway", "next_steps", "supporting_panel"}:
        return "content_blocks"
    if slot_id in {"summary_callout", "claim"}:
        return "content_blocks"
    return None


def _support_warnings(slide_id: str, layout: dict[str, Any], needs: dict[str, bool]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    slot_types = _layout_slot_types(layout)
    if needs["chart"] and "chart" not in slot_types:
        warnings.append(_warning("UNSUPPORTED_CHART_NEED", slide_id, "Chart need requires a chart layout or chart_frame slot.", layout["layout_id"], severity="error"))
    if needs["table"] and "table" not in slot_types:
        warnings.append(_warning("UNSUPPORTED_TABLE_NEED", slide_id, "Table need requires a table layout or table_frame slot.", layout["layout_id"], severity="error"))
    if needs["image"] and "image" not in slot_types:
        warnings.append(_warning("UNSUPPORTED_IMAGE_NEED", slide_id, "Image need requires an image frame slot.", layout["layout_id"], severity="error"))
    return warnings


def _overflow_warnings(slide_id: str, layout: dict[str, Any], slide: dict[str, Any]) -> list[dict[str, Any]]:
    slide_density = _normalize_key(slide.get("content_density") or "medium")
    layout_density = _normalize_key(layout.get("density") or "medium")
    block_count = len(slide.get("content_blocks") or [])
    text_size = len(json.dumps(slide.get("content_blocks") or [], sort_keys=True))
    if slide_density == "high" and layout_density in {"low", "medium"}:
        return [_warning("OVERFLOW_DENSITY_RISK", slide_id, "High-density slide is assigned to a lower-density layout.", layout["layout_id"])]
    if block_count > 5 or text_size > 1100:
        return [_warning("OVERFLOW_CONTENT_VOLUME_RISK", slide_id, "Content block volume may exceed available layout slots.", layout["layout_id"])]
    return []


def _target_archetype(slide: dict[str, Any], slide_type: str) -> str:
    text = _slide_text(slide)
    if slide_type in {"comparison", "comparison_matrix", "matrix", "decision", "options"}:
        return "comparison_matrix"
    if _has_payload(slide.get("table_data")):
        return "table_heavy"
    if _has_payload(slide.get("chart_data")):
        return "data_dashboard"
    if _has_payload(slide.get("image_needs")) and slide_type in {"case", "case_study", "example", "story"}:
        return "case_study"
    mapping = {
        "cover": "cover_hero",
        "title": "cover_hero",
        "opening": "cover_hero",
        "hero": "cover_hero",
        "section": "section_divider",
        "section_divider": "section_divider",
        "divider": "section_divider",
        "agenda": "agenda_roadmap",
        "roadmap": "agenda_roadmap",
        "overview": "agenda_roadmap",
        "two_column": "two_column_analysis",
        "analysis": "two_column_analysis",
        "comparison": "comparison_matrix",
        "matrix": "comparison_matrix",
        "dashboard": "data_dashboard",
        "metrics": "data_dashboard",
        "kpi": "data_dashboard",
        "chart": "data_dashboard",
        "table": "table_heavy",
        "table_heavy": "table_heavy",
        "case": "case_study",
        "case_study": "case_study",
        "example": "case_study",
        "closing": "closing",
        "close": "closing",
        "takeaways": "closing",
        "summary": "closing",
        "timeline": "process_timeline",
        "process": "process_timeline",
        "workflow": "process_timeline",
        "card_grid": "card_grid",
        "cards": "card_grid",
        "framework": "card_grid",
        "content": "standard_content",
        "standard": "standard_content",
        "evidence": "standard_content",
        "text": "standard_content",
    }
    if _has_word(text, "table") and slide_type not in {"comparison", "comparison_matrix"}:
        return "table_heavy"
    if any(_has_word(text, token) for token in ("chart", "metric", "kpi", "dashboard")):
        return "data_dashboard"
    return mapping.get(slide_type, FALLBACK_ARCHETYPE)


def _slide_needs(slide: dict[str, Any]) -> dict[str, bool]:
    text = _slide_text(slide)
    return {
        "chart": _has_payload(slide.get("chart_data")) or _has_word(text, "chart") or _has_word(text, "kpi"),
        "table": _has_payload(slide.get("table_data")) or _has_word(text, "table"),
        "image": _has_payload(slide.get("image_needs")) or _has_word(text, "photo") or _has_word(text, "image"),
    }


def _layout_slot_ids(layout: dict[str, Any]) -> set[str]:
    return {_normalize_key(slot.get("slot_id")) for slot in layout.get("slots") or []}


def _layout_slot_types(layout: dict[str, Any]) -> set[str]:
    return {_normalize_key(slot.get("slot_type")) for slot in layout.get("slots") or []}


def _slot_supported(required_slot: str, slot_ids: set[str], slot_types: set[str]) -> bool:
    normalized = _normalize_key(required_slot)
    aliases = {
        "claim": {"body", "summary_callout", "takeaway", "supporting_panel"},
        "body": {"body", "cards", "roadmap_items", "case_context", "case_evidence", "takeaway", "next_steps"},
        "content": {"body", "cards", "roadmap_items", "case_context", "case_evidence"},
        "image": {"hero_image", "photo_frame"},
        "photo": {"hero_image", "photo_frame"},
        "chart": {"primary_chart", "secondary_chart"},
        "table": {"table", "matrix"},
        "section_title": {"title"},
    }
    return normalized in slot_ids or bool(aliases.get(normalized, set()) & slot_ids) or normalized in slot_types


def _matching_slot_id(required_slot: str, slot_ids: set[str]) -> str | None:
    normalized = _normalize_key(required_slot)
    if normalized in slot_ids:
        return normalized
    aliases = {
        "claim": ["summary_callout", "body", "takeaway"],
        "body": ["body", "cards", "roadmap_items", "case_evidence"],
        "content": ["body", "cards", "roadmap_items", "case_context"],
        "image": ["hero_image", "photo_frame"],
        "photo": ["hero_image", "photo_frame"],
        "chart": ["primary_chart", "secondary_chart"],
        "table": ["table", "matrix"],
        "section_title": ["title"],
    }
    for alias in aliases.get(normalized, []):
        if alias in slot_ids:
            return alias
    return None


def _normalize_slides(slide_blueprints: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(slide_blueprints, list):
        return [slide for slide in slide_blueprints if isinstance(slide, dict)]
    if not isinstance(slide_blueprints, dict):
        raise ValueError("slide_blueprint must be an object or array")
    if isinstance(slide_blueprints.get("slides"), list):
        return [slide for slide in slide_blueprints["slides"] if isinstance(slide, dict)]
    if isinstance(slide_blueprints.get("slide_blueprints"), list):
        return [slide for slide in slide_blueprints["slide_blueprints"] if isinstance(slide, dict)]
    return [slide_blueprints]


def _warning(
    code: str,
    slide_id: str,
    message: str,
    layout_id: str | None = None,
    slot_id: str | None = None,
    severity: str = "warning",
) -> dict[str, Any]:
    payload = {"code": code, "slide_id": slide_id, "message": message, "severity": severity}
    if layout_id is not None:
        payload["layout_id"] = layout_id
    if slot_id is not None:
        payload["slot_id"] = slot_id
    return payload


def _dedupe_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for warning in warnings:
        key = (warning.get("code", ""), warning.get("slide_id", ""), warning.get("layout_id", ""))
        if key not in seen:
            seen.add(key)
            result.append(warning)
    return result


def _deck_id(slides: list[dict[str, Any]], template_spec: dict[str, Any]) -> str:
    seed = json.dumps(
        {
            "design_id": template_spec.get("design_id"),
            "slides": [slide.get("slide_id") or slide.get("id") for slide in slides],
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return f"deck-assembly-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"


def _deck_scale(slide_count: int) -> str:
    if slide_count <= 12:
        return "small"
    if slide_count <= 30:
        return "medium"
    if slide_count <= 80:
        return "large"
    return "very_large"


def _selected_tone_variant(template_spec: dict[str, Any]) -> str:
    tone_variants = ((template_spec.get("tokens") or {}).get("typography") or {}).get("tone_variants") or {}
    for tone in ("creative", "academic", "professional"):
        if tone in tone_variants:
            return tone
    return "creative"


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _has_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return bool(value)
    return True


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _slide_text(slide: dict[str, Any]) -> str:
    values = [
        slide.get("slide_type"),
        slide.get("slide_role"),
        slide.get("visual_type"),
        slide.get("required_slots"),
        slide.get("content_blocks"),
        slide.get("design_intent"),
    ]
    if _has_payload(slide.get("image_needs")):
        values.append(slide.get("image_needs"))
    return json.dumps(values, sort_keys=True).lower()


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


if __name__ == "__main__":
    raise SystemExit(main())
