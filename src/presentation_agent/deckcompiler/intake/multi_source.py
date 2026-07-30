"""Deterministic multi-source adapter over the existing single-source ingestion layer."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..evidence.normalization import build_evidence_registry, evidence_coverage
from ..identity import content_sha256, stable_id, stable_source_id
from ..provenance import seal_artifact, verify_artifact_content_hash
from ...source_ingestion import ingest_source_file
from ...source_planning import SourceDocument, source_planning_structural_hash
from .config import Phase3Config
from .pdf_text import PdfExtraction, extract_searchable_pdf, normalize_text


RIGHTS_NOTE = "Repository-authored synthetic content; local-only; no third-party, private, or remote source."
USER_PDF_RIGHTS_NOTE = (
    "User-provided local PDF; rights, privacy, and redistribution authority remain the user's responsibility."
)


@dataclass(frozen=True, slots=True)
class IntakeArtifacts:
    input_request: dict[str, Any]
    source_corpus: dict[str, Any]
    source_locator_registry: dict[str, Any]
    evidence_unit_registry: dict[str, Any]
    source_coverage_report: dict[str, Any]


def build_intake_artifacts(config: Phase3Config, *, run_id: str | None = None) -> IntakeArtifacts:
    prompt_text = _read_prompt(config.prompt_path)
    source_language = _source_language(config)
    pdf_rights_note = USER_PDF_RIGHTS_NOTE if config.mode == "prompt_with_pdfs" else RIGHTS_NOTE
    pdf_fingerprints = [_file_sha256(path) for path in config.pdf_paths]
    if len(pdf_fingerprints) != len(set(pdf_fingerprints)):
        raise DeckCompilerError(
            "DC_SOURCE_DUPLICATE_CONFLICT",
            "source_preflight",
            "PDF entries resolve to identical binary content",
            remediation_hint="Provide distinct source documents or remove the duplicate input.",
        )

    input_request = _build_input_request(config, prompt_text, pdf_fingerprints, run_id)
    prompt_source, prompt_locator, prompt_segment = _prompt_records(prompt_text, source_language)
    pdf_records: list[tuple[dict[str, Any], PdfExtraction, str]] = []
    for path, fingerprint in zip(config.pdf_paths, pdf_fingerprints, strict=True):
        stable_identity = {"algorithm": "sha256", "value": fingerprint}
        source_id = stable_source_id("pdf", stable_identity)
        extraction = extract_searchable_pdf(path, source_id)
        legacy_document = ingest_source_file(path)
        source = {
            "source_id": source_id,
            "source_type": "pdf",
            "display_name": _pdf_title(extraction, path),
            "original_filename": path.name,
            "stable_identity": stable_identity,
            "locator_strategy": "pdf_page_text_span",
            "extraction_status": "extracted",
            "language": source_language,
            "rights_privacy_note": pdf_rights_note,
            "child_assets": [],
        }
        pdf_records.append((source, extraction, _checkout_independent_legacy_hash(legacy_document, path)))

    sources = sorted([prompt_source, *(record[0] for record in pdf_records)], key=lambda item: item["source_id"])
    segments = [prompt_segment]
    locators = [prompt_locator]
    for source, extraction, _legacy_hash in sorted(pdf_records, key=lambda item: item[0]["source_id"]):
        for block in extraction.blocks:
            locator = block.locator
            locators.append(locator)
            segment_payload = {
                "segment_id": stable_id("seg", source["source_id"], locator["chunk_id"], block.canonical_text),
                "source_id": source["source_id"],
                "source_locator": {
                    "source_id": source["source_id"],
                    "locator_type": "pdf_text_span",
                    "page_number": locator["page_number"],
                    "char_range": locator["char_range"],
                    "quote": block.canonical_text,
                },
                "canonical_text": block.canonical_text,
                "language": source_language,
                "content_sha256": content_sha256(block.canonical_text),
            }
            segments.append(segment_payload)

    source_corpus_payload = {
        "schema_name": "source_corpus",
        "schema_version": "1.1.0",
        "corpus_id": stable_id("corpus", [item["source_id"] for item in sources], [item["segment_id"] for item in segments]),
        "sources": sources,
        "normalized_segments": segments,
    }
    source_corpus = seal_artifact(
        source_corpus_payload,
        artifact_type="source_corpus",
        input_artifact_ids=(input_request["artifact"]["artifact_id"],),
    )
    locator_payload = {
        "schema_name": "source_locator_registry",
        "schema_version": "1.0.0",
        "registry_id": stable_id("locators", [item["locator_id"] for item in locators]),
        "locators": sorted(locators, key=lambda item: item["locator_id"]),
        "pdf_documents": [
            {
                "source_id": source["source_id"],
                "page_count": extraction.page_count,
                "normalized_page_text_sha256": list(extraction.page_text_sha256),
                "extraction_method": extraction.extraction_method,
                "text_searchable": True,
                "legacy_adapter": "presentation_agent.source_ingestion.ingest_source_file",
                "legacy_structural_hash": legacy_hash,
            }
            for source, extraction, legacy_hash in sorted(pdf_records, key=lambda item: item[0]["source_id"])
        ],
    }
    source_locator_registry = seal_artifact(
        locator_payload,
        artifact_type="source_locator_registry",
        input_artifact_ids=(source_corpus["artifact"]["artifact_id"],),
    )
    evidence_registry = build_evidence_registry(
        source_corpus,
        source_locator_registry,
        prompt_text=prompt_text,
    )
    coverage = evidence_coverage(evidence_registry, source_corpus)
    source_gaps = [] if pdf_records else ["documentary_evidence_absent", "quantitative_evidence_absent"]
    coverage_payload = {
        "schema_name": "source_coverage_report",
        "schema_version": "1.0.0",
        "report_id": stable_id("coverage", coverage, source_gaps),
        "source_count": len(sources),
        "documentary_source_count": len(pdf_records),
        "no_silent_omission": len(sources) == 1 + len(config.pdf_paths),
        "source_gaps": source_gaps,
        **coverage,
    }
    source_coverage_report = seal_artifact(
        coverage_payload,
        artifact_type="source_coverage_report",
        input_artifact_ids=(
            source_corpus["artifact"]["artifact_id"],
            evidence_registry["artifact"]["artifact_id"],
        ),
    )
    artifacts = IntakeArtifacts(
        input_request,
        source_corpus,
        source_locator_registry,
        evidence_registry,
        source_coverage_report,
    )
    for payload in (
        input_request,
        source_corpus,
        source_locator_registry,
        evidence_registry,
        source_coverage_report,
    ):
        verify_artifact_content_hash(payload)
    return artifacts


def _build_input_request(
    config: Phase3Config,
    prompt_text: str,
    pdf_fingerprints: list[str],
    run_id: str | None,
) -> dict[str, Any]:
    payload = {
        "schema_name": "input_request",
        "schema_version": "1.0.0",
        "run_id": run_id or stable_id("run", config.mode, prompt_text, pdf_fingerprints),
        "request_id": stable_id("request", config.mode, prompt_text, pdf_fingerprints, config.presentation),
        "mode": config.mode,
        "prompt": {
            "path": config.prompt_reference,
            "sha256": content_sha256(normalize_text(prompt_text)),
            "source_type": "user_prompt",
        },
        "pdfs": [
            {"path": reference, "sha256": fingerprint, "source_type": "pdf"}
            for reference, fingerprint in zip(config.pdf_references, pdf_fingerprints, strict=True)
        ],
        "presentation": config.presentation,
        "policies": dict(sorted(config.policies.items())),
        "stop_after": config.stop_after,
    }
    return seal_artifact(payload, artifact_type="input_request")


def _prompt_records(prompt_text: str, language: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    canonical = normalize_text(prompt_text)
    stable_identity = {"algorithm": "canonical_text_sha256", "value": content_sha256(canonical)}
    source_id = stable_source_id("user_prompt", stable_identity)
    source = {
        "source_id": source_id,
        "source_type": "user_prompt",
        "display_name": "User prompt",
        "user_brief": prompt_text.strip(),
        "stable_identity": stable_identity,
        "locator_strategy": "prompt_character_range",
        "extraction_status": "not_required",
        "language": language,
        "rights_privacy_note": "User-provided local prompt; no documentary factual authority.",
        "child_assets": [],
    }
    locator_payload = {
        "source_id": source_id,
        "locator_type": "user_prompt",
        "char_range": {"start": 0, "end": len(canonical)},
        "quote": canonical,
        "text_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "extraction_method": "user_prompt_normalization",
        "extraction_warning": None,
        "text_searchable": True,
    }
    locator_payload["locator_id"] = stable_id("loc", locator_payload)
    segment = {
        "segment_id": stable_id("seg", source_id, canonical),
        "source_id": source_id,
        "source_locator": {
            "source_id": source_id,
            "locator_type": "user_prompt",
            "char_range": {"start": 0, "end": len(canonical)},
            "quote": canonical,
        },
        "canonical_text": canonical,
        "language": language,
        "content_sha256": content_sha256(canonical),
    }
    return source, locator_payload, segment


def _read_prompt(path: Path) -> str:
    if not path.is_file():
        raise DeckCompilerError("DC_INPUT_MISSING", "source_preflight", f"prompt input is missing: {path}", path.as_posix())
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise DeckCompilerError("DC_INPUT_INVALID", "source_preflight", "prompt input is empty", path.as_posix())
    return text


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise DeckCompilerError("DC_INPUT_MISSING", "source_preflight", f"source input is missing: {path}", path.as_posix())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checkout_independent_legacy_hash(document: SourceDocument, source_path: Path) -> str:
    """Preserve the legacy document contract without hashing its absolute checkout path."""
    stable_document = document.model_copy(
        update={
            "source_path": source_path.name,
            "structural_hash": "",
        }
    )
    return source_planning_structural_hash(stable_document)


def _pdf_title(extraction: PdfExtraction, path: Path) -> str:
    title = extraction.metadata.get("title", "").strip()
    return title or path.stem.replace("_", " ").title()


def _source_language(config: Phase3Config) -> str:
    if config.mode == "prompt_plus_two_pdfs":
        return "en"
    normalized = config.language.strip().lower().replace("_", "-")
    aliases = {
        "english": "en",
        "korean": "ko",
        "한국어": "ko",
        "japanese": "ja",
        "chinese": "zh",
        "french": "fr",
        "german": "de",
        "spanish": "es",
    }
    candidate = aliases.get(normalized, normalized)
    parts = candidate.split("-")
    if len(parts) == 1 and re.fullmatch(r"[a-z]{2,3}", parts[0]):
        return parts[0]
    if (
        len(parts) == 2
        and re.fullmatch(r"[a-z]{2,3}", parts[0])
        and re.fullmatch(r"[a-z]{2}", parts[1])
    ):
        return f"{parts[0]}-{parts[1].upper()}"
    return "en"


__all__ = ["IntakeArtifacts", "build_intake_artifacts"]
