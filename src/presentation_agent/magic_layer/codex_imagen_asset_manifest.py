"""Manifest helpers for Codex Imagen generated visual assets."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from .image_generation_provider import sha256_file


def collect_codex_imagen_generated_assets(plan: dict[str, Any]) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for task in plan.get("tasks") or []:
        path = Path(task["expected_original_path"])
        if not path.exists():
            missing.append(
                {
                    "slot_id": task["slot_id"],
                    "slide_id": task["slide_id"],
                    "archetype_id": task["archetype_id"],
                    "expected_filename": task["expected_filename"],
                    "expected_original_path": path.as_posix(),
                    "status": "missing_skill_output",
                }
            )
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
                mode = image.mode
        except Exception as exc:  # noqa: BLE001 - concrete validation evidence.
            missing.append(
                {
                    "slot_id": task["slot_id"],
                    "slide_id": task["slide_id"],
                    "archetype_id": task["archetype_id"],
                    "expected_filename": task["expected_filename"],
                    "expected_original_path": path.as_posix(),
                    "status": f"unreadable_skill_output:{exc}",
                }
            )
            continue
        assets.append(
            {
                "slot_id": task["slot_id"],
                "slide_id": task["slide_id"],
                "archetype_id": task["archetype_id"],
                "role": task["role"],
                "expected_filename": task["expected_filename"],
                "original_generated_file_path": path.as_posix(),
                "image_width": width,
                "image_height": height,
                "image_mode": mode,
                "file_size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "generation_route": "codex_desktop_imagen_skill",
                "prompt_hash": task["prompt_hash"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "api_key_stored": False,
                "repo_api_call_used": False,
            }
        )
    return {
        "schema_name": "codex_imagen_asset_manifest",
        "status": "passed" if assets and not missing and len(assets) == len(plan.get("tasks") or []) else "blocked",
        "generated_asset_count": len(assets),
        "missing_asset_count": len(missing),
        "assets": assets,
        "missing_assets": missing,
        "api_key_stored": False,
        "repo_api_call_used": False,
        "canva_parity_claimed": False,
    }


def manifest_as_generation_results(asset_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "codex_imagen_generation_results",
        "status": "passed" if asset_manifest.get("status") == "passed" else "blocked",
        "generation_route": "codex_desktop_imagen_skill",
        "api_key_required": False,
        "repo_api_call_used": False,
        "generated_asset_count": asset_manifest.get("generated_asset_count", 0),
        "missing_asset_count": asset_manifest.get("missing_asset_count", 0),
        "results": [
            {
                "slot_id": asset["slot_id"],
                "slide_id": asset["slide_id"],
                "archetype_id": asset["archetype_id"],
                "expected_filename": asset["expected_filename"],
                "status": "generated",
                "output_path": asset["original_generated_file_path"],
                "dimensions": [asset["image_width"], asset["image_height"]],
                "file_size_bytes": asset["file_size_bytes"],
                "sha256": asset["sha256"],
                "generation_route": asset["generation_route"],
                "prompt_hash": asset["prompt_hash"],
                "timestamp": asset["timestamp"],
            }
            for asset in asset_manifest.get("assets") or []
        ],
        "missing_outputs": asset_manifest.get("missing_assets") or [],
        "canva_parity_claimed": False,
    }


def generated_results_for_validator(generation_results: dict[str, Any]) -> dict[str, Any]:
    return {
        "results": [
            {
                "slot_id": item["slot_id"],
                "output_path": item.get("output_path"),
            }
            for item in generation_results.get("results") or []
            if item.get("status") == "generated"
        ]
    }
