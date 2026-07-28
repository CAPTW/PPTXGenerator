"""Quarantine weak or placeholder generated SVGs from prior stages."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .e03_2_4_placeholder_detector import detect_placeholder_svg


def quarantine_bad_svgs(approved_svg_manifest: dict[str, Any], quarantine_root: Path) -> dict[str, Any]:
    quarantine_root.mkdir(parents=True, exist_ok=True)
    rows = []
    placeholder_count = 0
    for icon in approved_svg_manifest.get("approved_svgs", []):
        svg_path = Path(icon.get("svg_path") or icon.get("generated_svg_path", ""))
        role = icon.get("likely_role") or icon.get("role") or svg_path.stem
        if not svg_path.exists():
            continue
        detection = detect_placeholder_svg(svg_path, role=role)
        weak_score = float(icon.get("final_candidate_score", 1.0)) < 0.9
        low_similarity = float(icon.get("crop_similarity", 1.0)) < 0.9
        quarantine = detection["is_placeholder"] or weak_score or low_similarity
        if not quarantine:
            continue
        reasons = list(detection["reasons"])
        if weak_score:
            reasons.append("weak_auto_score")
        if low_similarity:
            reasons.append("crop_similarity_not_proven")
        dest = quarantine_root / role / svg_path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(svg_path, dest)
        if detection["is_placeholder"]:
            placeholder_count += 1
        rows.append(
            {
                **icon,
                "role": role,
                "status": "quarantined_do_not_use_for_semantic_icon",
                "quarantine_path": dest.as_posix(),
                "quarantine_reasons": reasons,
                "placeholder_detection": detection,
            }
        )
    return {
        "schema_name": "bad_svg_quarantine_report",
        "status": "passed",
        "scanned_svg_count": len(approved_svg_manifest.get("approved_svgs", [])),
        "quarantined_bad_svg_count": len(rows),
        "generic_placeholder_svg_count": placeholder_count,
        "quarantined_roles": sorted({row["role"] for row in rows}),
        "quarantined_svg_paths": [row.get("svg_path") or row.get("generated_svg_path") for row in rows],
        "quarantined_svgs": rows,
    }


def build_generic_placeholder_svg_report(quarantine_report: dict[str, Any]) -> dict[str, Any]:
    placeholders = [row for row in quarantine_report.get("quarantined_svgs", []) if row.get("placeholder_detection", {}).get("is_placeholder")]
    return {
        "schema_name": "generic_placeholder_svg_report",
        "status": "passed",
        "generic_placeholder_svg_count": len(placeholders),
        "placeholders": placeholders,
    }
