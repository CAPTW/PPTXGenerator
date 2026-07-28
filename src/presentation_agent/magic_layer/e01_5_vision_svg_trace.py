"""Vision trace manifest creation for E01.5."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_e01_5_vision_svg_trace_manifest(exact_match_report: dict[str, Any], crop_manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    crops = {crop["crop_id"]: crop for crop in crop_manifest["crops"]}
    traces = []
    for match in exact_match_report["matches"]:
        if match["classification"] != "NO_LIBRARY_MATCH_TRACE_REQUIRED":
            continue
        crop = crops[match["crop_id"]]
        traces.append(
            {
                "crop_id": crop["crop_id"],
                "source_crop_path": crop["crop_path"],
                "source_crop_sha256": crop["crop_sha256"],
                "intended_role": crop["role_hint"],
                "generation_route": "codex_desktop_vision_trace",
                "no_api_key_route": True,
                "status": "pending_not_needed_for_current_library_first_run",
            }
        )
    return {
        "schema_name": "vision_svg_trace_manifest",
        "status": "not_required_existing_library_matches" if not traces else "pending",
        "trace_required_count": len(traces),
        "generated_trace_count": 0,
        "traces": traces,
        "api_key_route_used": False,
        "image_api_used": False,
        "canva_parity_claimed": False,
    }
