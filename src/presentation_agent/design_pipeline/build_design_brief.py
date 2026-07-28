"""Build a design-only brief from existing presentation planning artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from ..generator_contracts import validateDesignBrief


DEFAULT_CONSTRAINTS = {
    "editable_text": True,
    "editable_tables": True,
    "editable_charts": True,
    "no_full_slide_image_background": True,
    "image_allowed_only_in_photo_frames": True,
    "gpt_image_used_as_reference_only": True,
}

FORBIDDEN_DESIGN_BEHAVIORS = [
    "Do not use GPT-Image outputs as full-slide final backgrounds.",
    "Do not rasterize full final slides.",
    "Do not flatten editable text into images.",
    "Do not flatten editable tables or charts into static screenshots.",
    "Do not override user-approved planning content or slide copy.",
]


def build_design_brief(
    presentation_plan: dict[str, Any],
    slide_blueprint: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, Any]:
    slides = _normalize_slides(slide_blueprint)
    archetypes = _slide_archetypes(presentation_plan, slides)
    density = _density_profile(slides)
    chart_table = _chart_table_frequency(slides)
    photo_needs = _photo_needs(slides)
    icon_needs = _icon_needs(slides)
    footer_meta = _footer_meta_requirements(slides)
    visual_keywords = _visual_keywords(presentation_plan, slides, density["overall"])
    forbidden_outputs = _forbidden_outputs(presentation_plan)
    brief = {
        "schema_name": "design_brief",
        "schema_version": "1.0",
        "topic": _topic(presentation_plan),
        "audience": _audience(presentation_plan),
        "tone": _tone(presentation_plan),
        "visual_keywords": visual_keywords,
        "industry_context": _industry_context(presentation_plan),
        "deck_size": {
            "slide_count_target": _slide_count_target(presentation_plan, slides),
            "format": _slide_format(presentation_plan),
        },
        "slide_archetypes_needed": archetypes,
        "density_profile": density,
        "chart_table_frequency": chart_table,
        "photo_needs": photo_needs,
        "icon_needs": icon_needs,
        "footer_meta_requirements": footer_meta,
        "reference_style": _reference_style(presentation_plan),
        "constraints": dict(DEFAULT_CONSTRAINTS),
        "forbidden_design_behaviors": FORBIDDEN_DESIGN_BEHAVIORS,
        "forbidden_outputs": forbidden_outputs,
    }
    validateDesignBrief(brief)
    return brief


def build_design_brief_from_files(
    *,
    presentation_plan_path: str | Path,
    slide_blueprint_path: str | Path,
    output_path: str | Path,
) -> Path:
    presentation_plan = _load_json(presentation_plan_path)
    slide_blueprint = _load_json(slide_blueprint_path)
    brief = build_design_brief(presentation_plan, slide_blueprint)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(brief, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build outputs/design_brief.json from presentation_plan and slide_blueprint artifacts."
    )
    parser.add_argument(
        "--presentation-plan",
        dest="presentation_plan",
        type=Path,
        default=Path("outputs/schema_samples/valid/presentation_plan.json"),
    )
    parser.add_argument(
        "--slide-blueprint",
        dest="slide_blueprint",
        type=Path,
        default=Path("outputs/schema_samples/valid/slide_blueprint.json"),
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/design_brief.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = build_design_brief_from_files(
            presentation_plan_path=args.presentation_plan,
            slide_blueprint_path=args.slide_blueprint,
            output_path=args.output,
        )
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"BUILD_DESIGN_BRIEF_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_slides(slide_blueprint: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(slide_blueprint, list):
        return [slide for slide in slide_blueprint if isinstance(slide, dict)]
    if not isinstance(slide_blueprint, dict):
        raise ValueError("slide_blueprint must be an object or array")
    if isinstance(slide_blueprint.get("slides"), list):
        return [slide for slide in slide_blueprint["slides"] if isinstance(slide, dict)]
    if isinstance(slide_blueprint.get("slide_blueprints"), list):
        return [slide for slide in slide_blueprint["slide_blueprints"] if isinstance(slide, dict)]
    return [slide_blueprint]


def _topic(plan: dict[str, Any]) -> str:
    return _first_text(plan.get("deck_title"), plan.get("title"), plan.get("topic"), default="Untitled presentation")


def _audience(plan: dict[str, Any]) -> str:
    audience = plan.get("audience")
    if isinstance(audience, dict):
        return _first_text(audience.get("label"), audience.get("expertise_level"), default="general audience")
    return _first_text(audience, default="general audience")


def _tone(plan: dict[str, Any]) -> str:
    profile = plan.get("design_profile")
    if isinstance(profile, dict):
        return _first_text(plan.get("tone"), profile.get("tone"), plan.get("design_mode"), default="Academic + Professional + Creative")
    return _first_text(plan.get("tone"), plan.get("design_mode"), default="Academic + Professional + Creative")


def _industry_context(plan: dict[str, Any]) -> str:
    source_summary = str(plan.get("source_summary") or "").strip()
    objective = str(plan.get("objective") or "").strip()
    if isinstance(plan.get("objective"), dict):
        objective = " ".join(str(item) for item in plan["objective"].values() if item)
    if source_summary:
        return _truncate(source_summary, 180)
    if objective:
        return _truncate(objective, 180)
    return "General presentation context"


def _slide_count_target(plan: dict[str, Any], slides: list[dict[str, Any]]) -> int:
    raw = plan.get("slide_count_target") or plan.get("target_slide_count")
    if isinstance(raw, int) and raw > 0:
        return raw
    return max(1, len(slides))


def _slide_format(plan: dict[str, Any]) -> str:
    raw = plan.get("slide_ratio")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "16:9"


def _slide_archetypes(plan: dict[str, Any], slides: list[dict[str, Any]]) -> list[str]:
    raw = plan.get("slide_archetypes_needed")
    archetypes = _string_list(raw)
    for slide in slides:
        archetypes.extend(
            _string_list(
                [
                    slide.get("slide_type"),
                    slide.get("slide_role"),
                    slide.get("visual_type"),
                    slide.get("layout_pattern_id"),
                ]
            )
        )
    return _dedupe(archetypes) or ["content"]


def _density_profile(slides: list[dict[str, Any]]) -> dict[str, int | str]:
    counter: Counter[str] = Counter()
    for slide in slides:
        density = str(slide.get("content_density") or "").strip().lower()
        if density not in {"low", "medium", "high"}:
            density = _infer_density(slide)
        counter[density] += 1
    overall = "medium"
    if counter:
        overall = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return {
        "overall": overall,
        "low_count": counter.get("low", 0),
        "medium_count": counter.get("medium", 0),
        "high_count": counter.get("high", 0),
    }


def _infer_density(slide: dict[str, Any]) -> str:
    block_count = len(slide.get("content_blocks") or slide.get("core_content") or [])
    text_len = sum(len(str(item)) for item in _string_list(slide.get("content_blocks") or slide.get("core_content")))
    if block_count >= 5 or text_len > 700:
        return "high"
    if block_count <= 1 and text_len < 180:
        return "low"
    return "medium"


def _chart_table_frequency(slides: list[dict[str, Any]]) -> dict[str, int]:
    chart_count = 0
    table_count = 0
    for slide in slides:
        slide_text = json.dumps(slide, sort_keys=True).lower()
        if _has_payload(slide.get("chart_data")) or "chart" in slide_text:
            chart_count += 1
        if _has_payload(slide.get("table_data")) or "table" in slide_text:
            table_count += 1
    return {
        "chart_slide_count": chart_count,
        "table_slide_count": table_count,
        "total_slide_count": max(1, len(slides)),
    }


def _photo_needs(slides: list[dict[str, Any]]) -> list[str]:
    needs: list[str] = []
    for slide in slides:
        slide_id = str(slide.get("slide_id") or slide.get("id") or "slide")
        for image_need in slide.get("image_needs") or []:
            if isinstance(image_need, dict):
                needs.append(f"{slide_id}: {image_need.get('slot', 'image')} - {image_need.get('purpose', 'photo frame')}")
            elif isinstance(image_need, str):
                needs.append(f"{slide_id}: {image_need}")
        visual = str(slide.get("visual_type") or slide.get("slide_type") or "").lower()
        if visual in {"photo", "image", "document-crop"} and not needs:
            needs.append(f"{slide_id}: framed image or document crop")
    return _dedupe(needs)


def _icon_needs(slides: list[dict[str, Any]]) -> list[str]:
    needs: list[str] = []
    for slide in slides:
        slide_id = str(slide.get("slide_id") or slide.get("id") or "slide")
        slots = " ".join(_string_list(slide.get("required_slots"))).lower()
        intent = str(slide.get("design_intent") or "").lower()
        if "icon" in slots or "icon" in intent:
            needs.append(f"{slide_id}: editable SVG icon or ornament")
    return _dedupe(needs)


def _footer_meta_requirements(slides: list[dict[str, Any]]) -> list[str]:
    requirements = ["Use editable footer text for slide numbering and source notes."]
    if any(slide.get("citations") for slide in slides):
        requirements.append("Reserve footer/meta space for citations.")
    if any(slide.get("speaker_notes") or slide.get("presenter_notes") for slide in slides):
        requirements.append("Preserve speaker notes outside visible slide design.")
    return _dedupe(requirements)


def _visual_keywords(plan: dict[str, Any], slides: list[dict[str, Any]], density: str) -> list[str]:
    keywords = ["editable", "template-ready", density]
    keywords.extend(_split_keywords(plan.get("tone")))
    keywords.extend(_split_keywords(plan.get("design_mode")))
    keywords.extend(_string_list(plan.get("slide_archetypes_needed")))
    for slide in slides:
        keywords.extend(_string_list([slide.get("slide_type"), slide.get("visual_type"), slide.get("content_density")]))
    return _dedupe([keyword.lower() for keyword in keywords if keyword])[:12]


def _reference_style(plan: dict[str, Any]) -> dict[str, str]:
    tone = _tone(plan)
    return {
        "description": f"Premium editable PowerPoint template reference interpreted for {tone} delivery.",
        "source": "derived-from-presentation-plan-and-slide-blueprint",
    }


def _forbidden_outputs(plan: dict[str, Any]) -> list[str]:
    outputs = [
        "full-slide raster backgrounds",
        "flattened text",
        "uneditable tables",
        "uneditable charts",
        "GPT-Image output used as final slide art",
    ]
    outputs.extend(_string_list(plan.get("forbidden_outputs")))
    outputs.extend(_string_list(plan.get("constraints")))
    return _dedupe(outputs)


def _has_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return True


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [str(item) for item in value.values() if isinstance(item, (str, int, float)) and str(item).strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item)
            elif isinstance(item, dict):
                result.extend(_string_list(item))
            elif item is not None and not isinstance(item, (list, tuple, set)):
                result.append(str(item))
        return result
    return [str(value)]


def _split_keywords(value: Any) -> list[str]:
    result: list[str] = []
    for item in _string_list(value):
        result.extend(part.strip() for part in item.replace("+", ",").split(",") if part.strip())
    return result


def _first_text(*values: Any, default: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple, set)):
            text = str(value).strip()
            if text:
                return text
    return default


def _truncate(text: str, length: int) -> str:
    return text if len(text) <= length else text[: length - 3].rstrip() + "..."


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = " ".join(str(item).split())
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

