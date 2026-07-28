"""PyMuPDF page/block extraction that fails closed for invalid or scanned PDFs."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

from ..errors import DeckCompilerError
from ..identity import stable_id


@dataclass(frozen=True, slots=True)
class PdfBlock:
    locator: dict[str, Any]
    canonical_text: str
    heading_candidate: str


@dataclass(frozen=True, slots=True)
class PdfExtraction:
    page_count: int
    page_text_sha256: tuple[str, ...]
    blocks: tuple[PdfBlock, ...]
    metadata: dict[str, str]
    extraction_method: str = "pymupdf_text_blocks"


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_searchable_pdf(path: str | Path, source_id: str) -> PdfExtraction:
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise DeckCompilerError(
            "DC_INPUT_MISSING",
            "source_preflight",
            f"PDF input is missing: {pdf_path}",
            pdf_path.as_posix(),
        )
    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        raise DeckCompilerError(
            "DC_PDF_INVALID",
            "source_preflight",
            f"PDF parser rejected {pdf_path.name}",
            pdf_path.as_posix(),
            remediation_hint="Replace the file with a valid local text-searchable PDF.",
        ) from exc
    try:
        if document.page_count < 1:
            raise DeckCompilerError("DC_PDF_INVALID", "source_preflight", f"PDF has no pages: {pdf_path.name}")
        blocks: list[PdfBlock] = []
        page_hashes: list[str] = []
        for page_index, page in enumerate(document):
            page_text = normalize_text(page.get_text("text"))
            page_hashes.append(hashlib.sha256(page_text.encode("utf-8")).hexdigest())
            dictionary = page.get_text("dict")
            text_blocks = [block for block in dictionary.get("blocks", []) if block.get("type") == 0]
            heading = _heading_candidate(text_blocks)
            page_width = max(float(page.rect.width), 1.0)
            page_height = max(float(page.rect.height), 1.0)
            char_cursor = 0
            for block_index, block in enumerate(text_blocks):
                raw_text = " ".join(
                    str(span.get("text") or "")
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                )
                text = normalize_text(raw_text)
                if not text:
                    continue
                start = page_text.find(text, char_cursor)
                if start < 0:
                    start = max(0, char_cursor)
                end = start + len(text)
                char_cursor = end
                x0, y0, x1, y1 = [float(value) for value in block.get("bbox", (0, 0, 0, 0))]
                chunk_id = stable_id("chunk", source_id, page_index, block_index, text)
                locator_payload = {
                    "source_id": source_id,
                    "locator_type": "pdf_text_block",
                    "page_number": page_index + 1,
                    "page_index": page_index,
                    "block_index": block_index,
                    "chunk_id": chunk_id,
                    "char_range": {"start": start, "end": end},
                    "bbox": {
                        "x": round(max(0.0, x0 / page_width), 6),
                        "y": round(max(0.0, y0 / page_height), 6),
                        "width": round(min(1.0, max(0.000001, (x1 - x0) / page_width)), 6),
                        "height": round(min(1.0, max(0.000001, (y1 - y0) / page_height)), 6),
                        "unit": "normalized",
                    },
                    "quote": text,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "extraction_method": "pymupdf_text_blocks",
                    "extraction_warning": None,
                    "text_searchable": True,
                }
                locator_payload["locator_id"] = stable_id("loc", locator_payload)
                blocks.append(PdfBlock(locator_payload, text, heading))
        if not any(block.canonical_text for block in blocks):
            raise DeckCompilerError(
                "DC_PDF_SCANNED_UNSUPPORTED",
                "source_preflight",
                f"PDF has no extractable text layer and OCR is unsupported in Phase 3: {pdf_path.name}",
                pdf_path.as_posix(),
                remediation_hint="Provide a text-searchable PDF; do not rely on OCR in this phase.",
            )
        metadata = {str(key): str(value or "") for key, value in (document.metadata or {}).items()}
        return PdfExtraction(document.page_count, tuple(page_hashes), tuple(blocks), metadata)
    finally:
        document.close()


def _heading_candidate(blocks: list[dict[str, Any]]) -> str:
    candidates: list[tuple[float, str]] = []
    for block in blocks:
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = normalize_text(" ".join(str(span.get("text") or "") for span in spans))
            size = max((float(span.get("size") or 0) for span in spans), default=0.0)
            if text:
                candidates.append((size, text))
    return max(candidates, default=(0.0, ""), key=lambda item: item[0])[1]


__all__ = ["PdfBlock", "PdfExtraction", "extract_searchable_pdf", "normalize_text"]
