"""Plan and collect Codex Desktop Imagen skill outputs for D07.2.6."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .codex_imagen_skill_contract import REQUIRED_CODEX_IMAGEN_FILENAMES
from .image_generation_provider import select_requested_size


def harden_codex_imagen_prompt(prompt: str) -> str:
    hardening = (
        "\n\nCodex Desktop Imagen generation constraints: Generate a bounded visual-field asset only. "
        "This is not a full PowerPoint slide. This is not a presentation screenshot. "
        "Do not render readable text. No letters. No numbers. No UI labels. No charts. No tables. "
        "No semantic icons. No logo. No watermark. No source/citation/footer text. "
        "Match the deck system: dark navy, deep teal, cyan technical linework, restrained gold accents, "
        "professional / academic / creative. Keep important visual energy away from edges. "
        "Leave crop-safe margins. Do not copy Canva maritime, safety, ship, ocean, worker, checklist, "
        "or benchmark-specific content."
    )
    return prompt.strip() + hardening


def build_codex_imagen_generation_plan(resolved_map: dict[str, Any], *, generated_originals_dir: Path) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for slot in resolved_map.get("slots") or []:
        expected_filename = slot["expected_import_filename"]
        prompt = harden_codex_imagen_prompt(slot["resolved_prompt"])
        requested_size = select_requested_size(float(slot["target_aspect_ratio"]))
        tasks.append(
            {
                "slot_id": slot["slot_id"],
                "slide_id": slot["slide_id"],
                "archetype_id": slot["archetype_id"],
                "role": slot["role"],
                "target_aspect_ratio": slot["target_aspect_ratio"],
                "expected_filename": expected_filename,
                "expected_original_path": (generated_originals_dir / expected_filename).as_posix(),
                "import_path": slot["expected_import_path"],
                "requested_size": requested_size,
                "prompt": prompt,
                "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "semantic_restrictions": slot["semantic_restrictions"],
                "generation_route": "codex_desktop_imagen_skill",
            }
        )
    return {
        "schema_name": "codex_imagen_generation_plan",
        "status": "ready" if tasks and [task["expected_filename"] for task in tasks] == REQUIRED_CODEX_IMAGEN_FILENAMES else "blocked",
        "generation_route": "codex_desktop_imagen_skill",
        "repo_api_call_required": False,
        "api_key_required": False,
        "slot_count": len(tasks),
        "exact_required_filenames": [task["expected_filename"] for task in tasks],
        "required_filenames_match": [task["expected_filename"] for task in tasks] == REQUIRED_CODEX_IMAGEN_FILENAMES,
        "tasks": tasks,
        "canva_parity_claimed": False,
    }


def build_codex_imagen_prompt_pack(plan: dict[str, Any]) -> str:
    lines = [
        "# Codex Imagen Prompt Pack",
        "",
        "Generate one bounded visual-field image per section using the Codex Desktop Imagen / GPT-Image-2 skill.",
        "Do not use repo Python API clients, API keys, or external manual generation as the primary path.",
        "",
    ]
    for task in plan.get("tasks") or []:
        lines.extend(
            [
                f"## {task['expected_filename']}",
                "",
                f"- slot_id: `{task['slot_id']}`",
                f"- slide_id: `{task['slide_id']}`",
                f"- archetype_id: `{task['archetype_id']}`",
                f"- role: `{task['role']}`",
                f"- requested_size_hint: `{task['requested_size']}`",
                "",
                task["prompt"],
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def write_codex_imagen_prompt_files(plan: dict[str, Any], prompt_dir: Path) -> list[dict[str, str]]:
    prompt_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for task in plan.get("tasks") or []:
        path = prompt_dir / f"{task['slot_id']}.prompt.md"
        path.write_text(f"# {task['slot_id']}\n\n{task['prompt']}\n", encoding="utf-8")
        written.append({"slot_id": task["slot_id"], "path": path.as_posix()})
    return written
