"""Remove internal/debug labels from visible E01H-V2-R1 output."""

from __future__ import annotations


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


def contains_internal_labels(texts: list[str]) -> bool:
    joined = "\n".join(texts).lower()
    return any(label.lower() in joined for label in FORBIDDEN_LABELS)


def sanitize_slide_text(texts: list[str]) -> list[str]:
    sanitized = []
    for text in texts:
        clean = _sanitize_one(text)
        if clean and not contains_internal_labels([clean]) and clean not in sanitized:
            sanitized.append(clean)
    return sanitized


def _sanitize_one(text: str) -> str:
    replacements = {
        "PDF/PPT-like conversion benchmark": "",
        "Local E01H-V2 validation case": "",
        "Editable semantic layer": "",
        "Bounded visual backplate": "",
        "Controlled PDF fixture with primitives, images, vectors, and semantic text.": "Primitives, images, vectors, and editable text",
        "Source: PDFB02 controlled local fixture": "Source: local controlled PDF",
        "Local PDFB02 benchmark fixture": "Source: local controlled PDF",
        "Controlled fixture with known object truth": "Controlled local reference",
    }
    cleaned = text.strip()
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    for token in ["benchmark", "fixture", "layer truth", "conversion engine", "validation case"]:
        cleaned = cleaned.replace(token, "").replace(token.title(), "")
    return " ".join(cleaned.split())
