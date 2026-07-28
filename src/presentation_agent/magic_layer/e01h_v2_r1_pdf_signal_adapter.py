"""Extract R1 production hints from PDFs without consuming truth labels."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from src.presentation_agent.magic_layer.e01h_v2_r1_internal_label_filter import sanitize_slide_text


def adapt_r1_pdf_signals(case_dir: str | Path) -> dict[str, Any]:
    folder = Path(case_dir)
    pdf_path = folder / "reference.pdf"
    if not pdf_path.exists():
        return _fallback(folder.name)
    text_spans = []
    vector_shapes = []
    image_objects = []
    with fitz.open(pdf_path) as doc:
        page = doc[0]
        width = float(page.rect.width)
        height = float(page.rect.height)
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        bbox = _norm_bbox(span.get("bbox", [0, 0, 0, 0]), width, height)
                        text_spans.append({"object_id": f"pdf_text_{len(text_spans)+1}", "text": text, "bbox_norm": bbox})
            elif block.get("type") == 1:
                bbox = _norm_bbox(block.get("bbox", [0, 0, 0, 0]), width, height)
                image_objects.append({"object_id": f"pdf_image_{len(image_objects)+1}", "bbox_norm": bbox})
        for idx, drawing in enumerate(page.get_drawings()[:12]):
            rect = drawing.get("rect")
            if rect:
                vector_shapes.append({"object_id": f"pdf_vector_{idx+1}", "bbox_norm": _norm_bbox([rect.x0, rect.y0, rect.x1, rect.y1], width, height)})
    clean_text = sanitize_slide_text([span["text"] for span in text_spans])
    return {
        "schema_name": "pdf_object_signal_report",
        "status": "passed" if text_spans or vector_shapes or image_objects else "partial",
        "case_id": folder.name,
        "text_spans": text_spans,
        "sanitized_visible_text": clean_text,
        "vector_shapes": vector_shapes,
        "image_objects": image_objects,
        "truth_used_for_scoring_only": True,
        "canva_parity_claimed": False,
    }


def _fallback(case_id: str) -> dict[str, Any]:
    return {
        "schema_name": "pdf_object_signal_report",
        "status": "not_available",
        "case_id": case_id,
        "text_spans": [],
        "sanitized_visible_text": [case_id.replace("e01hp_", "").replace("_", " ").title(), "Reference image analysis fallback"],
        "vector_shapes": [],
        "image_objects": [],
        "truth_used_for_scoring_only": True,
        "canva_parity_claimed": False,
    }


def _norm_bbox(bbox: list[float], width: float, height: float) -> list[float]:
    return [round(bbox[0] / width, 4), round(bbox[1] / height, 4), round(bbox[2] / width, 4), round(bbox[3] / height, 4)]
