"""Resolve D07.2 visual-field asset prompts to exact slot filenames."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PROMPT_RESTRICTIONS = [
    "bounded visual-field asset, not a full slide",
    "no readable text",
    "no UI labels",
    "no chart, table, or data visualization",
    "no source, citation, or footer text",
    "no logos or watermarks",
    "not a screenshot and not a presentation slide",
    "no semantic icon content",
]


def parse_prompt_pack(prompt_pack: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", prompt_pack, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prompt_pack)
        sections[name] = prompt_pack[start:end].strip()
    return sections


def resolve_visual_asset_slots(slot_map: dict[str, Any], prompt_pack: str, import_dir: Path) -> dict[str, Any]:
    prompt_sections = parse_prompt_pack(prompt_pack)
    resolved: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for entry in slot_map.get("entries") or []:
        expected = entry.get("expected_import_filenames") or []
        png = [name for name in expected if name.endswith(".png")]
        if len(png) != 1:
            ambiguous.append({"slot_id": entry["slot_id"], "expected_import_filenames": expected})
            selected = expected[0] if expected else None
        else:
            selected = png[0]
        prompt = prompt_sections.get(entry["slot_id"], "")
        resolved_prompt = build_resolved_prompt(entry, prompt)
        resolved.append(
            {
                "slot_id": entry["slot_id"],
                "slide_id": entry["slide_id"],
                "slide_number": entry.get("slide_number"),
                "archetype_id": entry["archetype_id"],
                "role": entry["role"],
                "bbox_norm": entry["bbox_norm"],
                "required_or_optional": entry["required_or_optional"],
                "expected_import_filename": selected,
                "expected_import_path": (import_dir / selected).as_posix() if selected else None,
                "accepted_alternative_filenames": expected,
                "target_aspect_ratio": _target_aspect_ratio(entry["bbox_norm"]),
                "source_prompt_section": entry["slot_id"],
                "resolved_prompt": resolved_prompt,
                "semantic_restrictions": PROMPT_RESTRICTIONS,
            }
        )
    return {
        "schema_name": "visual_asset_slot_to_expected_filename_resolved",
        "status": "passed" if resolved and not ambiguous else "blocked",
        "slot_count": len(resolved),
        "ambiguous_slot_count": len(ambiguous),
        "ambiguous_slots": ambiguous,
        "slots": resolved,
        "canva_parity_claimed": False,
    }


def build_resolved_prompt(entry: dict[str, Any], base_prompt: str) -> str:
    role = entry["role"]
    guidance = {
        "hero_visual_field": (
            "Premium abstract evidence-memory / AI governance / decision-infrastructure visual field. "
            "Layered network, source traceability, subtle document/evidence nodes, faint technical geometry. "
            "Rich depth and cinematic lighting. No people, logos, dashboard UI, or readable labels."
        ),
        "section_texture": (
            "Premium chapter divider texture for an operating-model section transition. "
            "Abstract diagonal geometry, evidence paths, subtle governance and decision motif. "
            "Enrich the section visual area without competing with native title/subtitle text."
        ),
        "case_study_image": (
            "Professional case-study visual field for governance review workflow. "
            "Abstract enterprise review room, evidence archive, AI governance control environment, or document/evidence workspace. "
            "No readable screens, UI text, logos, identifiable people, or final slide copy."
        ),
    }.get(role, "Premium bounded abstract visual field for a PowerPoint image frame.")
    restrictions = " ".join(f"Must have {item}." for item in PROMPT_RESTRICTIONS)
    return (
        f"{base_prompt}\n\n"
        f"Resolved D07.2.2 guidance for {entry['slot_id']}: {guidance} "
        "Match the deck style: dark navy, deep teal, cyan technical linework, restrained gold accents, off-white integration if needed. "
        "Avoid copying Canva maritime, safety, ship, ocean, worker, checklist, or benchmark-specific content. "
        f"{restrictions}"
    ).strip()


def write_resolved_prompt_files(resolved_map: dict[str, Any], prompt_dir: Path) -> list[dict[str, str]]:
    prompt_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for slot in resolved_map.get("slots") or []:
        path = prompt_dir / f"{slot['slot_id']}.prompt.md"
        path.write_text(f"# {slot['slot_id']}\n\n{slot['resolved_prompt']}\n", encoding="utf-8")
        written.append({"slot_id": slot["slot_id"], "path": path.as_posix()})
    return written


def build_resolved_prompt_pack_md(resolved_map: dict[str, Any]) -> str:
    lines = ["# D07.2.2 Resolved Visual Asset Prompt Pack", ""]
    for slot in resolved_map.get("slots") or []:
        lines.extend(
            [
                f"## {slot['slot_id']}",
                "",
                f"- expected_import_filename: `{slot['expected_import_filename']}`",
                f"- role: `{slot['role']}`",
                f"- target_aspect_ratio: `{slot['target_aspect_ratio']}`",
                "",
                slot["resolved_prompt"],
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _target_aspect_ratio(bbox_norm: list[float]) -> float:
    if not bbox_norm or len(bbox_norm) != 4 or float(bbox_norm[3]) == 0:
        return 1.7778
    return round((float(bbox_norm[2]) * 16) / (float(bbox_norm[3]) * 9), 4)
