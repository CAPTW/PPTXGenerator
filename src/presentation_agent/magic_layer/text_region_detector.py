"""Text-like region detection for Magic Layer D02.

D02 uses deterministic geometry and image heuristics plus D01 layer context.
It does not call remote vision APIs and does not treat OCR text as final copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .layer_schema_v4 import bbox_norm


TEXT_CANDIDATE_TYPES = {
    "title_text_candidate",
    "subtitle_text_candidate",
    "body_text_candidate",
    "card_label_candidate",
    "kpi_label_candidate",
    "chart_label_candidate",
    "table_cell_text_candidate",
    "source_footer_text_candidate",
    "decorative_microtext_candidate",
    "unknown_text_candidate",
}


@dataclass(frozen=True)
class TextCandidatePolicy:
    min_confidence: float = 0.35
    min_edge_density: float = 0.015
    max_decorative_area_ratio: float = 0.012


def detect_text_candidates(
    image_path: Path,
    d01_manifest: dict[str, Any],
    *,
    policy: TextCandidatePolicy | None = None,
) -> list[dict[str, Any]]:
    """Return text-like candidates derived from D01 layers and crop heuristics."""

    active_policy = policy or TextCandidatePolicy()
    metadata = d01_manifest.get("reference_metadata") or {}
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    reference_id = str(d01_manifest.get("reference_id") or "reference")
    if width <= 0 or height <= 0:
        with Image.open(image_path) as image:
            width, height = image.size

    image = Image.open(image_path).convert("RGB")
    candidates: list[dict[str, Any]] = []
    for index, layer in enumerate(d01_manifest.get("layers") or [], start=1):
        candidate_type = _candidate_type_for_layer(layer, width, height)
        if candidate_type is None:
            continue
        bbox = [int(v) for v in layer["bbox_px"]]
        edge_density = _edge_density(image.crop(_crop_box(bbox)))
        text_like_score = _text_like_score(layer, candidate_type, edge_density, width, height)
        confidence = max(float(layer.get("confidence") or 0.0), text_like_score)
        content_bearing = bool(layer.get("content_bearing")) or candidate_type not in {"decorative_microtext_candidate"}
        low_confidence = confidence < active_policy.min_confidence
        candidates.append(
            {
                "candidate_id": f"{reference_id}_text_candidate_{len(candidates) + 1:03d}",
                "reference_id": reference_id,
                "source_layer_ids": [layer["layer_id"]],
                "bbox_px": bbox,
                "bbox_norm": bbox_norm(bbox, width, height),
                "candidate_type": candidate_type,
                "detection_source": "d01_layer_context+deterministic_text_heuristic",
                "d01_layer_type": layer.get("layer_type"),
                "semantic_hint": layer.get("semantic_role"),
                "content_bearing": content_bearing,
                "edge_density": round(edge_density, 5),
                "text_like_score": round(text_like_score, 4),
                "confidence": round(confidence, 4),
                "low_confidence": low_confidence,
                "disposition": "review_low_confidence" if low_confidence and content_bearing else "accepted_candidate",
                "notes": "D02 text candidate; OCR text, if any, is slot evidence only.",
            }
        )

    if not any(c["candidate_type"] == "source_footer_text_candidate" for c in candidates):
        candidates.append(_synthetic_footer_unresolved(reference_id, width, height))

    return sorted(candidates, key=lambda item: (item["bbox_px"][1], item["bbox_px"][0], item["candidate_id"]))


def validate_text_candidate(candidate: dict[str, Any]) -> list[str]:
    required = {
        "candidate_id",
        "reference_id",
        "source_layer_ids",
        "bbox_px",
        "bbox_norm",
        "candidate_type",
        "detection_source",
        "confidence",
        "low_confidence",
        "disposition",
    }
    errors: list[str] = []
    missing = required.difference(candidate)
    if missing:
        errors.append(f"missing_fields:{','.join(sorted(missing))}")
    if candidate.get("candidate_type") not in TEXT_CANDIDATE_TYPES:
        errors.append(f"invalid_candidate_type:{candidate.get('candidate_type')}")
    if candidate.get("candidate_type") == "unknown_text_candidate" and candidate.get("disposition") in {None, "", "accepted_candidate"}:
        errors.append("unknown_text_candidate_requires_explicit_disposition")
    if candidate.get("low_confidence") and candidate.get("content_bearing") and candidate.get("disposition") == "accepted_candidate":
        errors.append("low_confidence_content_text_cannot_silently_pass")
    return errors


def _candidate_type_for_layer(layer: dict[str, Any], width: int, height: int) -> str | None:
    layer_type = str(layer.get("layer_type") or "")
    semantic_role = str(layer.get("semantic_role") or "")
    x, y, w, h = [int(v) for v in layer.get("bbox_px") or [0, 0, 0, 0]]
    ny = y / height if height else 0
    area = (w * h) / (width * height) if width and height else 0

    if layer_type == "title_text_region":
        return "title_text_candidate"
    if layer_type == "subtitle_text_region":
        return "subtitle_text_candidate"
    if layer_type == "body_text_region":
        return "body_text_candidate"
    if layer_type == "source_footer_strip" or ny > 0.83:
        return "source_footer_text_candidate"
    if layer_type == "chart_region":
        return "chart_label_candidate"
    if layer_type in {"table_region", "matrix_region"}:
        return "table_cell_text_candidate"
    if layer_type == "card_panel" and bool(layer.get("content_bearing")):
        return "card_label_candidate"
    if layer_type == "icon_region" and area < 0.004:
        return "decorative_microtext_candidate"
    if layer_type == "unknown" and bool(layer.get("content_bearing")):
        return "unknown_text_candidate"
    if "footer" in semantic_role:
        return "source_footer_text_candidate"
    return None


def _text_like_score(layer: dict[str, Any], candidate_type: str, edge_density: float, width: int, height: int) -> float:
    _x, _y, w, h = [int(v) for v in layer["bbox_px"]]
    area = (w * h) / (width * height) if width and height else 0
    base = {
        "title_text_candidate": 0.82,
        "subtitle_text_candidate": 0.72,
        "source_footer_text_candidate": 0.76,
        "body_text_candidate": 0.64,
        "card_label_candidate": 0.58,
        "chart_label_candidate": 0.52,
        "table_cell_text_candidate": 0.52,
        "kpi_label_candidate": 0.58,
        "decorative_microtext_candidate": 0.38,
        "unknown_text_candidate": 0.32,
    }.get(candidate_type, 0.35)
    edge_bonus = min(0.12, edge_density * 1.5)
    area_penalty = 0.08 if area > 0.18 else 0.0
    return max(0.0, min(0.95, base + edge_bonus - area_penalty))


def _edge_density(crop: Image.Image) -> float:
    gray = crop.convert("L")
    width, height = gray.size
    if width < 2 or height < 2:
        return 0.0
    pixels = gray.load()
    edges = 0
    total = 0
    step_x = max(1, width // 180)
    step_y = max(1, height // 120)
    for y in range(0, height - 1, step_y):
        for x in range(0, width - 1, step_x):
            total += 1
            if abs(int(pixels[x, y]) - int(pixels[x + 1, y])) > 28 or abs(int(pixels[x, y]) - int(pixels[x, y + 1])) > 28:
                edges += 1
    return edges / max(1, total)


def _crop_box(bbox: list[int]) -> tuple[int, int, int, int]:
    x, y, w, h = bbox
    return (x, y, x + w, y + h)


def _synthetic_footer_unresolved(reference_id: str, width: int, height: int) -> dict[str, Any]:
    bbox = [int(width * 0.04), int(height * 0.88), int(width * 0.92), max(12, int(height * 0.07))]
    return {
        "candidate_id": f"{reference_id}_text_candidate_unresolved_footer",
        "reference_id": reference_id,
        "source_layer_ids": [],
        "bbox_px": bbox,
        "bbox_norm": bbox_norm(bbox, width, height),
        "candidate_type": "source_footer_text_candidate",
        "detection_source": "required_footer_prior_unresolved",
        "d01_layer_type": None,
        "semantic_hint": "source_footer",
        "content_bearing": True,
        "edge_density": 0.0,
        "text_like_score": 0.0,
        "confidence": 0.2,
        "low_confidence": True,
        "disposition": "blocking_unresolved_source_footer_text",
        "notes": "No D01 footer text layer was available; D02 records the unresolved required source/footer region.",
    }
