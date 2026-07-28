"""D07.2.2 visual asset generation planning and mode detection."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_CANDIDATES = [
    "config/image_generation.json",
    "configs/image_generation.json",
    "design_runs/run_002/config/image_generation.json",
]


def detect_visual_asset_generation_mode(repo_root: Path) -> dict[str, Any]:
    configs_found: list[str] = []
    approved_config: str | None = None
    enabled = False
    for relative in CONFIG_CANDIDATES:
        path = repo_root / relative
        if not path.exists():
            continue
        configs_found.append(path.as_posix())
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if payload.get("image_generation_enabled") is True and (
            payload.get("approved_for_d07_2_2") is True or payload.get("approved_for_d07_2") is True
        ):
            enabled = True
            approved_config = path.as_posix()
            break
    env_enabled = os.environ.get("PPTXLOCAL_IMAGE_GENERATION_ENABLED") == "true"
    env_approved = os.environ.get("PPTXLOCAL_D07_2_2_IMAGE_GENERATION_APPROVED") == "true"
    if env_enabled and env_approved:
        enabled = True
        approved_config = approved_config or "environment:PPTXLOCAL_IMAGE_GENERATION_ENABLED"
    return {
        "schema_name": "visual_asset_generation_mode",
        "mode": "api_configured" if enabled else "unavailable",
        "image_generation_enabled": enabled,
        "approved_config_path": approved_config,
        "configs_found": configs_found,
        "remote_generation_called": False,
        "secrets_stored": False,
    }


def build_visual_asset_generation_plan(resolved_map: dict[str, Any], generation_mode: dict[str, Any]) -> dict[str, Any]:
    tasks = []
    for slot in resolved_map.get("slots") or []:
        tasks.append(
            {
                "slot_id": slot["slot_id"],
                "slide_id": slot["slide_id"],
                "archetype_id": slot["archetype_id"],
                "role": slot["role"],
                "expected_import_filename": slot["expected_import_filename"],
                "target_aspect_ratio": slot["target_aspect_ratio"],
                "prompt_available": bool(slot.get("resolved_prompt")),
                "generation_status": "blocked_image_generation_unavailable" if generation_mode["mode"] == "unavailable" else "ready_for_generation",
            }
        )
    return {
        "schema_name": "visual_asset_generation_plan",
        "status": "blocked" if generation_mode["mode"] == "unavailable" else "ready",
        "generation_mode": generation_mode,
        "slot_count": len(tasks),
        "tasks": tasks,
        "canva_parity_claimed": False,
    }


def build_generation_unavailable_results(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "visual_asset_generation_results",
        "status": "BLOCKED_IMAGE_GENERATION_UNAVAILABLE",
        "generated_asset_count": 0,
        "processed_asset_count": 0,
        "copied_to_import_count": 0,
        "generation_mode": plan["generation_mode"],
        "results": [
            {
                "slot_id": task["slot_id"],
                "slide_id": task["slide_id"],
                "archetype_id": task["archetype_id"],
                "expected_import_filename": task["expected_import_filename"],
                "status": "BLOCKED_IMAGE_GENERATION_UNAVAILABLE",
                "reason": "No explicit approved local image generation configuration was found.",
            }
            for task in plan.get("tasks") or []
        ],
        "canva_parity_claimed": False,
    }
