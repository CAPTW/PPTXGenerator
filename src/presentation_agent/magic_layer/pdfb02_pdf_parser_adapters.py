"""Detect local PDF parser capabilities for PDFB02."""

from __future__ import annotations

import importlib.util
from typing import Any


def detect_pdf_parser_capabilities() -> dict[str, Any]:
    adapters = {
        "pymupdf": {"available": importlib.util.find_spec("fitz") is not None, "signals": ["text", "drawings", "images", "render"]},
        "pdfplumber": {"available": importlib.util.find_spec("pdfplumber") is not None, "signals": ["text", "rects", "lines", "tables"]},
        "python_pptx": {"available": importlib.util.find_spec("pptx") is not None, "signals": ["pptx_candidate_inspection"]},
        "docling": {"available": importlib.util.find_spec("docling") is not None, "signals": []},
        "unstructured": {"available": importlib.util.find_spec("unstructured") is not None, "signals": []},
    }
    available_required = adapters["pymupdf"]["available"] and adapters["pdfplumber"]["available"]
    return {
        "schema_name": "pdf_parser_capability_report",
        "status": "passed" if available_required else "partial",
        "adapters": adapters,
        "external_api_used": False,
        "canva_parity_claimed": False,
    }
