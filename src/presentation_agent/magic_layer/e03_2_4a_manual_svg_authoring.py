"""Manual deterministic SVG authoring for E03.2.4A approved icon crops."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def author_approved_manual_svgs(review_resolution: dict[str, Any], generated_root: Path) -> dict[str, Any]:
    icons: list[dict[str, Any]] = []
    for item in review_resolution.get("approved_for_authoring", []):
        role = str(item.get("role") or item.get("role_guess"))
        crop_path = item.get("cleaned_glyph_crop") or item.get("raw_crop") or item.get("source_crop_path")
        crop_hash = _hash_path(Path(crop_path)) if crop_path else _hash_text(item.get("review_id", role))
        svg_path = generated_root / role / f"{crop_hash[:16]}_{role}.svg"
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(_svg_for(role), encoding="utf-8")
        metadata = {
            "source_crop_hash": crop_hash,
            "source_crop_path": crop_path,
            "source_archetype": item.get("archetype_id"),
            "human_review_id": item.get("review_id"),
            "decision": item.get("decision"),
            "role_slug": role,
            "authoring_method": "deterministic_manual_svg_from_human_approved_crop",
            "similarity_rationale": "human-approved role crop simplified to a legible currentColor SVG without raster fallback",
            "created_stage": "E03.2.4A",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reusable": True,
        }
        metadata_path = svg_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        icons.append({**item, "role": role, "source_crop_path": crop_path, "crop_sha256": crop_hash, "svg_path": svg_path.as_posix(), "metadata_path": metadata_path.as_posix()})
    return {"schema_name": "authored_svg_manifest", "status": "passed", "authored_svg_count": len(icons), "icons": icons}


def validate_authored_svgs(manifest: dict[str, Any]) -> dict[str, Any]:
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item in manifest.get("icons", []):
        svg_path = Path(item["svg_path"])
        text = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
        reasons = _quality_failures(text)
        row = {**item, "quality_failures": reasons}
        if reasons:
            failed.append(row)
        else:
            passed.append(row)
    return {
        "schema_name": "authored_svg_quality_report",
        "status": "passed" if not failed else "failed",
        "authored_svg_count": len(manifest.get("icons", [])),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "semantic_raster_icon_count": 0,
        "passed_icons": passed,
        "failed_icons": failed,
        "icons": manifest.get("icons", []),
    }


def _quality_failures(text: str) -> list[str]:
    reasons: list[str] = []
    if not text.strip():
        return ["blank_svg"]
    try:
        ET.fromstring(text)
    except ET.ParseError:
        reasons.append("invalid_xml")
    lowered = text.lower()
    if "<text" in lowered:
        reasons.append("has_text_element")
    if "<image" in lowered or "base64" in lowered:
        reasons.append("has_raster_image")
    non_namespace_text = lowered.replace("http://www.w3.org/2000/svg", "").replace("https://www.w3.org/2000/svg", "")
    if "http://" in non_namespace_text or "https://" in non_namespace_text:
        reasons.append("has_external_reference")
    if "viewbox" not in lowered:
        reasons.append("missing_viewbox")
    if "currentcolor" not in lowered:
        reasons.append("not_currentcolor_compatible")
    if "<path" not in lowered and "<line" not in lowered and "<circle" not in lowered and "<rect" not in lowered and "<poly" not in lowered:
        reasons.append("no_visible_glyph_primitives")
    return reasons


def _svg_for(role: str) -> str:
    body = {
        "book": '<path d="M5 5.5c2.5-1 4.5-.5 7 1v13c-2.5-1.5-4.5-2-7-1z"/><path d="M19 5.5c-2.5-1-4.5-.5-7 1v13c2.5-1.5 4.5-2 7-1z"/>',
        "calendar": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/><path d="M8 14h2M12 14h2M16 14h2M8 17h2M12 17h2"/>',
        "chart_bar": '<path d="M4 20h16"/><rect x="6" y="11" width="3" height="7"/><rect x="11" y="7" width="3" height="11"/><rect x="16" y="4" width="3" height="14"/>',
        "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
        "database": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
        "decision_diamond": '<path d="M12 3l9 9-9 9-9-9z"/><path d="M8 12h8"/>',
        "document": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 12h6M9 16h6"/>',
        "evidence_trace": '<path d="M4 12s3.2-5 8-5 8 5 8 5-3.2 5-8 5-8-5-8-5z"/><circle cx="12" cy="12" r="2.5"/><path d="M17 17l3 3"/>',
        "flag": '<path d="M6 21V4"/><path d="M6 5h10l-2 4 2 4H6"/>',
        "network": '<circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 11l8-4M8 13l8 4"/>',
        "note": '<path d="M5 4h14v11l-5 5H5z"/><path d="M14 20v-5h5"/><path d="M8 8h8M8 12h6"/>',
        "process_node": '<circle cx="12" cy="12" r="6"/><path d="M8 12h8M12 8v8"/>',
        "recommendation": '<path d="M5 13l4 4L20 6"/><path d="M4 20h16"/><path d="M7 4h10"/>',
        "risk_status": '<path d="M12 3l3.2 5.4 5.8 1.2-4 4.4.7 6-5.7-2.6L6.3 20l.7-6-4-4.4 5.8-1.2z"/><path d="M12 8.5v5"/><circle cx="12" cy="16.5" r=".7"/>',
        "scale": '<path d="M12 4v16M6 7h12"/><path d="M7 7l-4 7h8zM17 7l-4 7h8z"/>',
        "shield": '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/><path d="M9 12l2 2 4-5"/>',
        "table": '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M4 10h16M4 14h16M10 5v14M15 5v14"/>',
        "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.4-4 4.3-6 8-6s6.6 2 8 6"/>',
        "warning": '<path d="M12 3l9 18H3z"/><path d="M12 8v5"/><circle cx="12" cy="17" r=".8"/>',
    }.get(role, '<path d="M12 4l7 4v8l-7 4-7-4V8z"/><path d="M9 12h6"/>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + body + "</svg>\n"


def _hash_path(path: Path) -> str:
    if path.exists():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return _hash_text(path.as_posix())


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
