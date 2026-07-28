"""Detect internal/debug label leakage in E01H-V2 candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e01h_v2_qa_report import extract_pptx_text


FORBIDDEN_LABELS = [
    "Editable semantic layer",
    "Bounded visual backplate",
    "PDF/PPT-like conversion benchmark",
    "Local E01H-V2 validation case",
    "semantic layer",
    "visual backplate",
    "strategy",
    "benchmark",
    "fixture",
    "layer truth",
    "conversion engine",
    "validation case",
]


def detect_internal_label_leakage(input_path: str | Path, extra_visible_text: list[str] | None = None) -> dict[str, Any]:
    path = Path(input_path)
    visible_text = extract_pptx_text(path) if path.suffix.lower() == ".pptx" else path.read_text(encoding="utf-8").splitlines()
    if extra_visible_text:
        visible_text = visible_text + extra_visible_text
    joined = "\n".join(visible_text).lower()
    detected = []
    for label in sorted(FORBIDDEN_LABELS, key=len, reverse=True):
        if label.lower() in joined:
            detected.append(label)
    filtered = []
    for label in detected:
        if not any(label.lower() in existing.lower() for existing in filtered):
            filtered.append(label)
    return {
        "schema_name": "visible_internal_label_leakage_report",
        "status": "passed" if not filtered else "failed",
        "internal_label_leakage_count": len(filtered),
        "detected_labels": filtered,
        "visible_text_sample": visible_text[:12],
        "benchmark_labels_treated_as_slide_content": bool(filtered),
        "canva_parity_claimed": False,
    }
