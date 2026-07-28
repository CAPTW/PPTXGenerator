"""Adapt legacy blueprint.json artifacts into slide_blueprint.json contracts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from ..generator_contracts import validateSlideBlueprint


DEFAULT_BLUEPRINT_PATH = Path("outputs/blueprint.json")
DEFAULT_SLIDE_BLUEPRINT_PATH = Path("outputs/slide_blueprint.json")
DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH = Path("outputs/slide_blueprint.adapted.json")
DEFAULT_REPORT_JSON_PATH = Path("outputs/blueprint_adapter_report.json")
DEFAULT_REPORT_MD_PATH = Path("outputs/blueprint_adapter_report.md")
FALLBACK_SLIDE_TYPE = "standard_content"


def adapt_blueprint_artifacts_from_files(
    *,
    blueprint_path: str | Path = DEFAULT_BLUEPRINT_PATH,
    slide_blueprint_path: str | Path = DEFAULT_SLIDE_BLUEPRINT_PATH,
    output_path: str | Path = DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH,
    report_json_path: str | Path = DEFAULT_REPORT_JSON_PATH,
    report_md_path: str | Path = DEFAULT_REPORT_MD_PATH,
) -> Path:
    blueprint_file = Path(blueprint_path)
    slide_blueprint_file = Path(slide_blueprint_path)
    warnings: list[dict[str, Any]] = []

    if blueprint_file.exists():
        source_path = blueprint_file
        source_payload = _load_json(blueprint_file)
        output_payload = blueprint_to_slide_blueprint_collection(source_payload, warnings=warnings)
        mode = "converted_blueprint"
    elif slide_blueprint_file.exists():
        source_path = slide_blueprint_file
        source_payload = _load_json(slide_blueprint_file)
        output_payload = slide_blueprint_passthrough(source_payload, warnings=warnings)
        mode = "slide_blueprint_passthrough"
    else:
        raise FileNotFoundError(
            f"no blueprint artifact found; expected {blueprint_file.as_posix()} or {slide_blueprint_file.as_posix()}"
        )

    validate_slide_blueprint_collection(output_payload)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")

    report = _build_report(
        mode=mode,
        source_path=source_path,
        output_path=output,
        slide_count=len(_normalize_slides(output_payload)),
        warnings=warnings,
    )
    Path(report_json_path).write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    Path(report_md_path).write_text(_markdown_report(report), encoding="utf-8")
    return output


def blueprint_to_slide_blueprint_collection(
    blueprint: dict[str, Any],
    *,
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(blueprint, dict):
        raise ValueError("blueprint must be an object")
    raw_slides = blueprint.get("slides")
    if not isinstance(raw_slides, list) or not raw_slides:
        raise ValueError("blueprint.slides must contain at least one slide")
    sink = warnings if warnings is not None else []
    section_lookup = _section_lookup(blueprint)
    slides = [_convert_slide(slide, index, section_lookup, sink) for index, slide in enumerate(raw_slides, start=1)]
    payload = {
        "schema_name": "slide_blueprint_collection",
        "schema_version": "1.0",
        "source_schema_name": str(blueprint.get("schema_name") or "blueprint"),
        "source_deck_title": str(blueprint.get("deck_title") or ""),
        "slides": slides,
    }
    validate_slide_blueprint_collection(payload)
    return payload


def slide_blueprint_passthrough(
    slide_blueprint: dict[str, Any] | list[dict[str, Any]],
    *,
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    slides = _normalize_slides(slide_blueprint)
    if not slides:
        raise ValueError("slide_blueprint must contain at least one slide")
    payload = {
        "schema_name": "slide_blueprint_collection",
        "schema_version": "1.0",
        "source_schema_name": "slide_blueprint",
        "slides": slides,
    }
    validate_slide_blueprint_collection(payload)
    if warnings is not None:
        warnings.append(
            _warning(
                "SLIDE_BLUEPRINT_PASSTHROUGH",
                "input",
                "Existing slide_blueprint artifact was validated and passed through.",
                severity="info",
            )
        )
    return payload


def validate_slide_blueprint_collection(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]]:
    slides = _normalize_slides(payload)
    if not slides:
        raise ValueError("slide_blueprint collection must contain at least one slide")
    for index, slide in enumerate(slides, start=1):
        try:
            validateSlideBlueprint(slide)
        except ValidationError as exc:
            slide_id = slide.get("slide_id") if isinstance(slide, dict) else None
            raise ValueError(f"slide_blueprint validation failed at slide {index} ({slide_id or 'unknown'}): {exc.message}") from exc
    return payload


def resolve_slide_blueprint_path(
    requested_path: str | Path = DEFAULT_SLIDE_BLUEPRINT_PATH,
    adapted_path: str | Path = DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH,
) -> Path:
    requested = Path(requested_path)
    adapted = Path(adapted_path)
    candidates = [requested]
    if adapted != requested:
        candidates.append(adapted)
    failures: list[str] = []
    for candidate in candidates:
        if not candidate.exists():
            failures.append(f"{candidate.as_posix()}: missing")
            continue
        try:
            validate_slide_blueprint_collection(_load_json(candidate))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            failures.append(f"{candidate.as_posix()}: invalid ({exc})")
            continue
        return candidate
    raise FileNotFoundError(
        "no valid slide blueprint artifact found; expected outputs/slide_blueprint.json or "
        f"outputs/slide_blueprint.adapted.json. Details: {'; '.join(failures)}"
    )


def load_valid_slide_blueprints(
    requested_path: str | Path = DEFAULT_SLIDE_BLUEPRINT_PATH,
    adapted_path: str | Path = DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH,
) -> tuple[dict[str, Any] | list[dict[str, Any]], Path]:
    selected = resolve_slide_blueprint_path(requested_path, adapted_path)
    payload = _load_json(selected)
    validate_slide_blueprint_collection(payload)
    return payload, selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adapt legacy blueprint.json into slide_blueprint.adapted.json.")
    parser.add_argument("--blueprint", type=Path, default=DEFAULT_BLUEPRINT_PATH)
    parser.add_argument("--slide-blueprint", type=Path, default=DEFAULT_SLIDE_BLUEPRINT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON_PATH)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = adapt_blueprint_artifacts_from_files(
            blueprint_path=args.blueprint,
            slide_blueprint_path=args.slide_blueprint,
            output_path=args.output,
            report_json_path=args.report_json,
            report_md_path=args.report_md,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ADAPT_BLUEPRINT_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _convert_slide(
    slide: dict[str, Any],
    index: int,
    section_lookup: dict[str, str],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(slide, dict):
        raise ValueError(f"blueprint slide {index} must be an object")
    slide_id = _first_text(slide.get("slide_id"), slide.get("id"), default=f"slide-{index:03d}")
    section_id = _section_id(slide, section_lookup)
    title = _first_text(slide.get("title"), default="")
    if not title:
        title = f"Slide {index}"
        warnings.append(_warning("MISSING_TITLE_FILLED", slide_id, "Missing title was filled deterministically."))
    slide_type = _slide_type(slide, slide_id, warnings)
    content_blocks = _content_blocks(slide, slide_id, warnings)
    citations = _citations(slide, slide_id)
    image_needs = _image_needs(slide)
    chart_data = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else None
    table_data = slide.get("table_data") if isinstance(slide.get("table_data"), dict) else None
    required_slots = _required_slots(slide_type, content_blocks, chart_data, table_data, image_needs)

    if slide.get("visual_type") == "chart" and chart_data is None:
        warnings.append(_warning("MISSING_CHART_DATA", slide_id, "Chart visual type had no chart_data; compiler fallback may be used."))
    if slide.get("visual_type") == "table" and table_data is None:
        warnings.append(_warning("MISSING_TABLE_DATA", slide_id, "Table visual type had no table_data; compiler fallback may be used."))
    if not citations:
        warnings.append(_warning("MISSING_CITATIONS", slide_id, "No citation/source anchors were available.", severity="info"))

    return {
        "schema_name": "slide_blueprint",
        "schema_version": "1.0",
        "slide_id": slide_id,
        "section_id": section_id,
        "slide_type": slide_type,
        "title": title,
        "subtitle": _subtitle(slide),
        "content_density": _content_density(slide, content_blocks, chart_data, table_data, image_needs),
        "required_slots": required_slots,
        "content_blocks": content_blocks,
        "chart_data": chart_data,
        "table_data": table_data,
        "image_needs": image_needs,
        "speaker_notes": _first_text(slide.get("speaker_notes"), slide.get("presenter_notes"), default=""),
        "citations": citations,
        "design_intent": _design_intent(slide, slide_type),
    }


def _slide_type(slide: dict[str, Any], slide_id: str, warnings: list[dict[str, Any]]) -> str:
    raw = _normalize_key(_first_text(slide.get("slide_type"), slide.get("slide_role"), slide.get("visual_type"), default=""))
    visual = _normalize_key(slide.get("visual_type"))
    if visual == "table":
        return "table"
    if visual == "chart":
        return "dashboard"
    if visual in {"process", "timeline"}:
        return "process"
    if visual in {"document_crop", "image", "photo"}:
        return "evidence"
    mapping = {
        "title": "title",
        "cover": "title",
        "executive_summary": "evidence",
        "summary": "closing",
        "section_divider": "section-divider",
        "analysis": "evidence",
        "evidence": "evidence",
        "recommendation": "closing",
        "comparison": "comparison",
        "appendix_evidence": "table",
        "references": "table",
        "process": "process",
    }
    if raw in mapping:
        return mapping[raw]
    if raw:
        warnings.append(
            _warning(
                "UNSUPPORTED_SLIDE_TYPE_FALLBACK",
                slide_id,
                f"Unsupported slide role/type {raw!r} mapped to {FALLBACK_SLIDE_TYPE}.",
            )
        )
    return FALLBACK_SLIDE_TYPE


def _content_blocks(slide: dict[str, Any], slide_id: str, warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = slide.get("content_blocks")
    if isinstance(existing, list) and existing:
        blocks = []
        for index, block in enumerate(existing, start=1):
            if not isinstance(block, dict):
                continue
            blocks.append(
                {
                    "block_id": _first_text(block.get("block_id"), default=f"{slide_id}-block-{index:02d}"),
                    "slot": _first_text(block.get("slot"), default="body"),
                    "type": _first_text(block.get("type"), default="text"),
                    "content": block.get("content"),
                }
            )
        if blocks:
            return blocks

    blocks: list[dict[str, Any]] = []
    claim = _first_text(slide.get("main_message"), slide.get("one_line_takeaway"), default="")
    if claim:
        blocks.append({"block_id": f"{slide_id}-claim", "slot": "claim", "type": "text", "content": claim})
    body_items = _body_items(slide)
    if body_items:
        blocks.append({"block_id": f"{slide_id}-body", "slot": "body", "type": "bullets", "content": body_items})
    if not blocks:
        warnings.append(_warning("MISSING_BODY_BLOCKS", slide_id, "No body blocks were available; inserted title-derived body text."))
        blocks.append({"block_id": f"{slide_id}-body", "slot": "body", "type": "text", "content": claim or slide.get("title") or ""})
    return blocks


def _body_items(slide: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for value in slide.get("core_content") or []:
        if str(value).strip():
            items.append(str(value))
    for value in slide.get("required_evidence_assets") or []:
        if str(value).strip():
            items.append(str(value))
    bridge = slide.get("production_bridge") if isinstance(slide.get("production_bridge"), dict) else {}
    for ref in bridge.get("source_material_refs") or []:
        if isinstance(ref, dict):
            label = _first_text(ref.get("label"), ref.get("source_id"), ref.get("path"), default="")
            if label:
                items.append(f"Source: {label}")
    return _dedupe(items)[:6]


def _citations(slide: dict[str, Any], slide_id: str) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    raw = slide.get("citations")
    if isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            if isinstance(item, dict):
                label = _first_text(item.get("label"), item.get("source"), default="")
                if label:
                    citations.append(
                        {
                            "citation_id": _first_text(item.get("citation_id"), default=f"{slide_id}-citation-{index:02d}"),
                            "label": label,
                            "source": _first_text(item.get("source"), default=label),
                        }
                    )
    bridge = slide.get("production_bridge") if isinstance(slide.get("production_bridge"), dict) else {}
    for index, ref in enumerate(bridge.get("source_material_refs") or [], start=1):
        if isinstance(ref, dict):
            label = _first_text(ref.get("label"), ref.get("source_id"), ref.get("path"), default="")
            if label:
                citations.append(
                    {
                        "citation_id": _first_text(ref.get("source_id"), default=f"{slide_id}-source-{index:02d}"),
                        "label": label,
                        "source": _first_text(ref.get("path"), ref.get("source_id"), default=label),
                    }
                )
    return _dedupe_citations(citations)


def _image_needs(slide: dict[str, Any]) -> list[dict[str, str]]:
    raw = slide.get("image_needs")
    if isinstance(raw, list):
        result = []
        for item in raw:
            if isinstance(item, dict) and item.get("slot") and item.get("purpose"):
                payload = {"slot": str(item["slot"]), "purpose": str(item["purpose"])}
                if item.get("source_policy"):
                    payload["source_policy"] = str(item["source_policy"])
                result.append(payload)
        if result:
            return result
    visual_type = _normalize_key(slide.get("visual_type"))
    bridge = slide.get("production_bridge") if isinstance(slide.get("production_bridge"), dict) else {}
    preference = _normalize_key(bridge.get("visual_source_preference"))
    if visual_type in {"document_crop", "image", "photo"} or preference == "document_crop":
        return [
            {
                "slot": "photo_frame",
                "purpose": _first_text(slide.get("title"), bridge.get("crop_subject_hint"), default="Source visual evidence"),
                "source_policy": "source crop or approved photo only inside declared image frame",
            }
        ]
    return []


def _required_slots(
    slide_type: str,
    content_blocks: list[dict[str, Any]],
    chart_data: dict[str, Any] | None,
    table_data: dict[str, Any] | None,
    image_needs: list[dict[str, str]],
) -> list[str]:
    slots = ["title"]
    if slide_type == "section-divider":
        slots = ["section_title"]
    elif slide_type == "card_grid":
        slots.append("cards")
    elif slide_type == "comparison":
        slots.append("matrix")
    elif slide_type == "dashboard" or chart_data is not None:
        slots.append("chart")
    elif slide_type == "table" or table_data is not None:
        slots.append("table")
    elif image_needs:
        slots.append("image")
    elif any(block.get("slot") == "claim" for block in content_blocks):
        slots.extend(["claim", "body"])
    else:
        slots.append("body")
    slots.append("footer")
    return _dedupe(slots)


def _content_density(
    slide: dict[str, Any],
    content_blocks: list[dict[str, Any]],
    chart_data: dict[str, Any] | None,
    table_data: dict[str, Any] | None,
    image_needs: list[dict[str, str]],
) -> str:
    raw = _normalize_key(slide.get("content_density"))
    if raw in {"low", "medium", "high"}:
        return raw
    text_size = len(json.dumps(content_blocks, sort_keys=True, ensure_ascii=True))
    if table_data is not None or chart_data is not None or len(content_blocks) > 3 or text_size > 650:
        return "high"
    if image_needs or text_size > 250:
        return "medium"
    return "low"


def _subtitle(slide: dict[str, Any]) -> str:
    subtitle = _first_text(slide.get("subtitle"), slide.get("one_line_takeaway"), default="")
    title = _first_text(slide.get("title"), default="")
    return "" if subtitle == title else subtitle


def _design_intent(slide: dict[str, Any], slide_type: str) -> str:
    existing = _first_text(slide.get("design_intent"), default="")
    if existing:
        return existing
    visual_type = _first_text(slide.get("visual_type"), default="text")
    pattern = _first_text(slide.get("layout_pattern_id"), default="editable-template-layout")
    return f"Adapted from legacy blueprint as {slide_type}; preserve {visual_type} intent using {pattern}."


def _section_lookup(blueprint: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for section in blueprint.get("story_architecture") or []:
        if isinstance(section, dict):
            title = _first_text(section.get("title"), section.get("section_id"), default="")
            if title:
                lookup[_normalize_key(title)] = _first_text(section.get("section_id"), default=_slug(title))
    return lookup


def _section_id(slide: dict[str, Any], lookup: dict[str, str]) -> str:
    raw = _first_text(slide.get("section_id"), default="")
    if raw:
        return raw
    section = _first_text(slide.get("section"), default="")
    if not section:
        return "sec-unknown"
    return lookup.get(_normalize_key(section), _slug(section))


def _normalize_slides(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [slide for slide in payload if isinstance(slide, dict)]
    if not isinstance(payload, dict):
        raise ValueError("slide_blueprint must be an object or array")
    if isinstance(payload.get("slides"), list):
        return [slide for slide in payload["slides"] if isinstance(slide, dict)]
    if isinstance(payload.get("slide_blueprints"), list):
        return [slide for slide in payload["slide_blueprints"] if isinstance(slide, dict)]
    return [payload]


def _valid_existing_slide_blueprint_path(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    validate_slide_blueprint_collection(_load_json(path))
    return path


def _build_report(
    *,
    mode: str,
    source_path: Path,
    output_path: Path,
    slide_count: int,
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_name": "blueprint_adapter_report",
        "schema_version": "1.0",
        "status": "passed",
        "mode": mode,
        "source_path": _display_path(source_path),
        "output_path": _display_path(output_path),
        "slide_count": slide_count,
        "warning_count": sum(1 for item in warnings if item.get("severity") == "warning"),
        "info_count": sum(1 for item in warnings if item.get("severity") == "info"),
        "warnings": warnings,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Blueprint Adapter Report",
        "",
        f"Status: `{report['status']}`",
        f"Mode: `{report['mode']}`",
        f"Source: `{report['source_path']}`",
        f"Output: `{report['output_path']}`",
        f"Slides: `{report['slide_count']}`",
        f"Warnings: `{report['warning_count']}`",
        "",
    ]
    if report["warnings"]:
        lines.extend(["## Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- `{warning['severity']}` `{warning['code']}` `{warning['slide_id']}`: {warning['message']}")
    return "\n".join(lines) + "\n"


def _warning(code: str, slide_id: str, message: str, *, severity: str = "warning") -> dict[str, Any]:
    return {"code": code, "slide_id": slide_id, "severity": severity, "message": message}


def _first_text(*values: Any, default: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple)):
            text = str(value).strip()
            if text:
                return text
    return default


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _dedupe_citations(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in items:
        key = item["citation_id"]
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    return str(path.as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
