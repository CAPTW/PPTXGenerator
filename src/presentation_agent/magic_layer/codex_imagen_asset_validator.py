"""Validation wrapper for Codex Imagen visual-field assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .generated_visual_asset_validator import validate_generated_visual_assets


def validate_codex_imagen_generated_assets(
    generation_results_for_validator: dict[str, Any],
    resolved_map: dict[str, Any],
    *,
    forbidden_hashes: dict[str, str] | None = None,
    rejected_dir: Path | None = None,
) -> dict[str, Any]:
    report = validate_generated_visual_assets(
        generation_results_for_validator,
        resolved_map,
        forbidden_hashes=forbidden_hashes,
    )
    report["schema_name"] = "generated_asset_validation_report"
    report["generation_route"] = "codex_desktop_imagen_skill"
    report["api_key_required"] = False
    report["repo_api_call_used"] = False
    report["text_validation_mode"] = "heuristic_no_ocr"
    report["text_risk"] = "bounded"
    report["prompt_no_text_policy_enforced"] = True
    if rejected_dir and report.get("rejected_assets"):
        rejected_dir.mkdir(parents=True, exist_ok=True)
        for rejected in report["rejected_assets"]:
            source = Path(rejected.get("asset_path") or "")
            if source.exists():
                target = rejected_dir / source.name
                target.write_bytes(source.read_bytes())
                rejected["rejected_copy_path"] = target.as_posix()
    return report
