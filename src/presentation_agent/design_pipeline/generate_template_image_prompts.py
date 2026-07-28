"""Generate deterministic GPT-Image-2 prompt files for template references."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .template_archetypes import (
    DEFAULT_ARCHETYPE_ID,
    load_template_archetype_registry,
    selectRequiredArchetypes,
)


ALLOWED_PLACEHOLDER_LABELS = "TITLE, KPI, CHART, TABLE, IMAGE, FOOTER"
BOARD_PROMPT_FILE = "template_board.prompt.txt"
MANIFEST_FILE = "template_prompt_manifest.json"


def generate_template_image_prompts(
    design_brief: dict[str, Any],
    selected_template_archetypes: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, Any]:
    """Return prompt text and a manifest without performing image generation."""

    archetypes, selection_warnings = _normalize_selected_archetypes(selected_template_archetypes)
    board_prompt = _build_board_prompt(design_brief, archetypes)
    archetype_prompts = {
        archetype["id"]: _build_archetype_prompt(design_brief, archetype)
        for archetype in archetypes
    }
    manifest = _build_manifest(design_brief, archetypes, selection_warnings)
    manifest["prompt_digest"] = _prompt_digest(board_prompt, archetype_prompts)
    return {
        "template_board_prompt": board_prompt,
        "archetype_prompts": archetype_prompts,
        "manifest": manifest,
    }


def generate_template_image_prompts_from_files(
    *,
    design_brief_path: str | Path,
    output_dir: str | Path,
    archetype_selection_path: str | Path | None = None,
    slide_blueprint_path: str | Path | None = None,
    archetype_ids: list[str] | None = None,
) -> Path:
    design_brief = _load_json(design_brief_path)
    selection = _load_or_select_archetypes(
        design_brief=design_brief,
        archetype_selection_path=archetype_selection_path,
        slide_blueprint_path=slide_blueprint_path,
        archetype_ids=archetype_ids,
    )
    payload = generate_template_image_prompts(design_brief, selection)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / BOARD_PROMPT_FILE).write_text(payload["template_board_prompt"] + "\n", encoding="utf-8")
    for archetype_id, prompt in payload["archetype_prompts"].items():
        (output / _prompt_filename(archetype_id)).write_text(prompt + "\n", encoding="utf-8")
    (output / MANIFEST_FILE).write_text(
        json.dumps(payload["manifest"], indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return output / MANIFEST_FILE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build GPT-Image-2 template reference prompt files from design-pipeline artifacts."
    )
    parser.add_argument("--design-brief", type=Path, default=Path("outputs/design_brief.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/template_image_prompts"))
    parser.add_argument(
        "--archetype-selection",
        type=Path,
        default=None,
        help="Optional JSON containing a template_pack payload from selectRequiredArchetypes.",
    )
    parser.add_argument(
        "--slide-blueprint",
        type=Path,
        default=_default_slide_blueprint_path(),
        help="Optional slide_blueprint JSON used to derive the selected archetypes.",
    )
    parser.add_argument(
        "--archetype-id",
        action="append",
        default=None,
        help="Explicit archetype id to include. Can be supplied more than once.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manifest_path = generate_template_image_prompts_from_files(
            design_brief_path=args.design_brief,
            output_dir=args.output_dir,
            archetype_selection_path=args.archetype_selection,
            slide_blueprint_path=args.slide_blueprint,
            archetype_ids=args.archetype_id,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"GENERATE_TEMPLATE_IMAGE_PROMPTS_FAILED {exc}")
        return 1
    print(f"WROTE {manifest_path}")
    return 0


def _load_or_select_archetypes(
    *,
    design_brief: dict[str, Any],
    archetype_selection_path: str | Path | None,
    slide_blueprint_path: str | Path | None,
    archetype_ids: list[str] | None,
) -> dict[str, Any] | list[dict[str, Any]]:
    if archetype_selection_path is not None:
        return _load_json(archetype_selection_path)
    if archetype_ids:
        return _select_by_ids(archetype_ids)
    if slide_blueprint_path is not None and Path(slide_blueprint_path).exists():
        return selectRequiredArchetypes(design_brief, _load_json(slide_blueprint_path))
    return _select_from_design_brief(design_brief)


def _select_by_ids(archetype_ids: list[str]) -> dict[str, Any]:
    registry = {item["id"]: item for item in load_template_archetype_registry()}
    selected: list[dict[str, Any]] = []
    warnings: list[str] = []
    for archetype_id in _dedupe(archetype_ids):
        if archetype_id in registry:
            selected.append(registry[archetype_id])
        else:
            warnings.append(f"Unknown template archetype id {archetype_id}; ignored.")
    if not selected:
        selected.append(registry[DEFAULT_ARCHETYPE_ID])
        warnings.append(f"No known template archetypes were selected; using {DEFAULT_ARCHETYPE_ID}.")
    return {"template_pack": selected, "slide_layout_bindings": [], "warnings": warnings}


def _select_from_design_brief(design_brief: dict[str, Any]) -> dict[str, Any]:
    registry = load_template_archetype_registry()
    by_id = {item["id"]: item for item in registry}
    by_slide_type: dict[str, str] = {}
    for archetype in registry:
        by_slide_type[_normalize_key(archetype["id"])] = archetype["id"]
        for slide_type in archetype.get("compatible_slide_types", []):
            by_slide_type.setdefault(_normalize_key(slide_type), archetype["id"])

    selected: list[dict[str, Any]] = []
    warnings: list[str] = []
    for requested in _string_list(design_brief.get("slide_archetypes_needed")):
        archetype_id = by_slide_type.get(_normalize_key(requested))
        if archetype_id is None:
            warnings.append(f"Design brief requested {requested}, but no template archetype mapping exists.")
            continue
        if archetype_id not in {item["id"] for item in selected}:
            selected.append(by_id[archetype_id])
    if not selected:
        selected.append(by_id[DEFAULT_ARCHETYPE_ID])
        warnings.append(f"No design brief archetypes were selected; using {DEFAULT_ARCHETYPE_ID}.")
    return {"template_pack": selected, "slide_layout_bindings": [], "warnings": warnings}


def _normalize_selected_archetypes(
    selected_template_archetypes: dict[str, Any] | list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if isinstance(selected_template_archetypes, dict):
        raw_pack = selected_template_archetypes.get("template_pack") or selected_template_archetypes.get("archetypes")
        warnings.extend(_string_list(selected_template_archetypes.get("warnings")))
    else:
        raw_pack = selected_template_archetypes

    if not isinstance(raw_pack, list):
        raise ValueError("selected template archetypes must be a list or an object with template_pack")

    registry_items = load_template_archetype_registry()
    registry = {item["id"]: item for item in registry_items}
    registry_order = {item["id"]: index for index, item in enumerate(registry_items)}
    archetypes: list[dict[str, Any]] = []
    for item in raw_pack:
        archetype_id = item.get("id") if isinstance(item, dict) else str(item)
        if archetype_id not in registry:
            warnings.append(f"Unknown template archetype id {archetype_id}; ignored.")
            continue
        if archetype_id not in {entry["id"] for entry in archetypes}:
            archetypes.append(registry[archetype_id])

    if not archetypes:
        archetypes.append(registry[DEFAULT_ARCHETYPE_ID])
        warnings.append(f"No known template archetypes were selected; using {DEFAULT_ARCHETYPE_ID}.")
    archetypes.sort(key=lambda entry: registry_order[entry["id"]])
    return archetypes, _dedupe(warnings)


def _build_board_prompt(design_brief: dict[str, Any], archetypes: list[dict[str, Any]]) -> str:
    archetype_lines = "\n".join(
        f"- {item['id']}: {item['purpose']} Required slots: {', '.join(item['required_slots'])}."
        for item in archetypes
    )
    return "\n".join(
        [
            "Target model: GPT-Image-2.",
            "Create one 16:9 premium PowerPoint template design reference board.",
            "This is an internal design reference only, not a final presentation slide.",
            "Do not render real presentation text. Use placeholder blocks instead of paragraphs.",
            f"Use only these simple labels if needed: {ALLOWED_PLACEHOLDER_LABELS}.",
            "Design a cohesive visual system across the selected template archetypes.",
            "The style must feel professional + academic + creative.",
            "Show editable-looking layout structure: clear cards, panels, grid, footer, charts, table frames, and image masks.",
            f"Deck topic: {_brief_value(design_brief, 'topic')}",
            f"Audience: {_brief_value(design_brief, 'audience')}",
            f"Tone: {_brief_value(design_brief, 'tone')}",
            f"Industry context: {_brief_value(design_brief, 'industry_context')}",
            f"Visual keywords: {', '.join(_string_list(design_brief.get('visual_keywords'))) or 'premium editable template system'}",
            "Selected archetypes:",
            archetype_lines,
            "Design constraints:",
            "- Text, charts, tables, cards, labels, and titles must look editable in PowerPoint.",
            "- Images may appear only as framed image masks or photo-frame placeholders.",
            "- GPT-Image-2 output is only a premium design reference for later editable PPTX construction.",
            "Prohibit poster-like outputs.",
            "Prohibit full-slide text rendering.",
            "Prohibit cluttered illegible body copy.",
            "Prohibit full-slide raster background art.",
        ]
    )


def _build_archetype_prompt(design_brief: dict[str, Any], archetype: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Target model: GPT-Image-2.",
            f"Create a 16:9 premium PowerPoint template design reference image for archetype: {archetype['id']}.",
            "This is an internal design reference only, not a final presentation slide.",
            "Do not render real presentation text. Use placeholder blocks instead of paragraphs.",
            f"Use only these simple labels if needed: {ALLOWED_PLACEHOLDER_LABELS}.",
            "Request a cohesive visual system that can be translated into editable PowerPoint shapes and text boxes.",
            "Request editable-looking layout structure with clear cards, panels, grid, footer, charts, table frames, and image masks.",
            "The style must feel professional + academic + creative.",
            f"Deck topic: {_brief_value(design_brief, 'topic')}",
            f"Audience: {_brief_value(design_brief, 'audience')}",
            f"Visual keywords: {', '.join(_string_list(design_brief.get('visual_keywords'))) or 'premium editable template system'}",
            f"Archetype purpose: {archetype['purpose']}",
            f"Required slots: {', '.join(archetype['required_slots'])}.",
            f"Optional slots: {', '.join(archetype['optional_slots'])}.",
            f"Density range: {', '.join(archetype['density_range'])}.",
            f"Recommended components: {', '.join(archetype['recommended_components'])}.",
            f"Image policy: {archetype['image_policy']}",
            f"Chart policy: {archetype['chart_policy']}",
            f"Table policy: {archetype['table_policy']}",
            f"Fallback layout id: {archetype['fallback_layout_id']}.",
            "Visible structure should communicate where editable PPT title boxes, body slots, native charts, native tables, SVG icons, ornaments, and framed images will go.",
            "Prohibit poster-like outputs.",
            "Prohibit full-slide text rendering.",
            "Prohibit cluttered illegible body copy.",
            "Prohibit final-slide artwork or full-slide raster backgrounds.",
        ]
    )


def _build_manifest(
    design_brief: dict[str, Any],
    archetypes: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema_name": "template_prompt_manifest",
        "schema_version": "1.0",
        "prompt_model_target": "GPT-Image-2",
        "reference_only": True,
        "no_api_call_performed": True,
        "design_topic": _brief_value(design_brief, "topic"),
        "design_tone": _brief_value(design_brief, "tone"),
        "allowed_placeholder_labels": ALLOWED_PLACEHOLDER_LABELS.split(", "),
        "template_board_prompt_path": BOARD_PROMPT_FILE,
        "archetype_prompts": [
            {
                "archetype_id": archetype["id"],
                "prompt_path": _prompt_filename(archetype["id"]),
                "fallback_layout_id": archetype["fallback_layout_id"],
                "required_slots": archetype["required_slots"],
                "optional_slots": archetype["optional_slots"],
            }
            for archetype in archetypes
        ],
        "warnings": warnings,
    }


def _prompt_digest(board_prompt: str, archetype_prompts: dict[str, str]) -> str:
    digest_input = json.dumps(
        {"board": board_prompt, "archetypes": archetype_prompts},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


def _default_slide_blueprint_path() -> Path | None:
    primary = Path("outputs/slide_blueprint.json")
    if primary.exists():
        return primary
    sample = Path("outputs/schema_samples/valid/slide_blueprint.json")
    return sample if sample.exists() else None


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _prompt_filename(archetype_id: str) -> str:
    return f"{_normalize_key(archetype_id)}.prompt.txt"


def _brief_value(design_brief: dict[str, Any], key: str) -> str:
    value = design_brief.get(key)
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    if value is not None and not isinstance(value, (dict, list, tuple, set)):
        return str(value)
    return "unspecified"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [str(item) for item in value.values() if str(item).strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item)
            elif item is not None and not isinstance(item, (list, tuple, set)):
                result.append(str(item))
        return result
    return [str(value)]


def _normalize_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    keep = [character if character.isalnum() else "_" for character in text]
    return "_".join("".join(keep).split("_")).strip("_")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = " ".join(str(item).split())
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
