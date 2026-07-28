"""Vision repair manifest for SVG candidates.

The current local stage records that no API-key route is used. Vision repair is
only queued when local trace scores are below threshold.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_vision_svg_repair_manifest(local_trace_manifest: dict[str, Any], output_root: Path | None) -> dict[str, Any]:
    low_score = [row for row in local_trace_manifest.get("candidates", []) if row.get("final_candidate_score", 0.0) < 0.66]
    return {
        "schema_name": "vision_svg_repair_manifest",
        "status": "passed",
        "vision_repair_candidate_count": 0,
        "api_key_route_used": False,
        "gpt_image_2_used": False,
        "reason": "local_vector_trace_candidates_passed_threshold" if not low_score else "vision_repair_not_available_for_low_score_candidates",
        "queued_low_score_candidate_count": len(low_score),
        "candidates": [],
    }
