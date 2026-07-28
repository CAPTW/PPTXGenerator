"""Local-first reference pack scanner that emits reference_dna artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator

from ..compat.legacy_non_pptx import (
    BriefMaterialType,
    ContractModel,
    PresentationType,
    ProjectMaterial,
    ReferenceConfidenceBand,
    ReferenceDNA,
    ReferenceProfile,
    ReferenceScanMode,
    ScaleMode,
    SourceMaterialRef,
    WorkflowPlan,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
METADATA_FILENAMES = {
    "metadata.yaml",
    "metadata.yml",
    "metadata.json",
    "reference-pack.yaml",
    "reference-pack.yml",
    "reference-pack.json",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
DOCUMENT_EXTENSIONS = {".pdf"}
DECK_EXTENSIONS = {".pptx", ".potx", ".odp"}
NOTES_EXTENSIONS = {".md"}
DATA_EXTENSIONS = {".csv", ".tsv"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls"}
MARKDOWN_SECTION_MAP = {
    "positioning": "positioning",
    "source family": "source_family",
    "patterns worth borrowing": "patterns_worth_borrowing",
    "patterns to avoid": "patterns_to_avoid",
    "layout logic": "layout_logic",
    "hierarchy behavior": "hierarchy_behavior",
    "whitespace behavior": "whitespace_behavior",
    "section divider style": "section_divider_style",
    "chart table treatment": "chart_table_treatment",
    "icon illustration treatment": "icon_illustration_treatment",
    "pacing and title behavior": "pacing_and_title_behavior",
    "fit assessment": "fit_assessment",
    "terminology guardrails": "terminology_guardrails",
    "section guardrails": "section_guardrails",
}
LIST_FIELDS = {
    "tags",
    "tone_keywords",
    "patterns_worth_borrowing",
    "patterns_to_avoid",
    "layout_logic",
    "hierarchy_behavior",
    "whitespace_behavior",
    "chart_table_treatment",
    "icon_illustration_treatment",
    "pacing_and_title_behavior",
    "terminology_guardrails",
    "section_guardrails",
}
REFERENCE_CUE_KEYWORDS = {
    "report": ("report", "readout", "performance", "results", "update"),
    "decision": ("decision", "approve", "recommend", "tradeoff", "budget"),
    "persuasion": ("persuasion", "persuade", "buy in", "support", "convince"),
    "training": ("training", "enablement", "teach", "onboard", "curriculum"),
    "demo": ("demo", "walkthrough", "sandbox", "product tour"),
    "pitch": ("pitch", "investor", "sales", "prospect", "fundraise"),
    "keynote": ("keynote", "vision", "future", "north star", "transformation"),
    "workshop": ("workshop", "facilitation", "working session", "co-design", "exercise"),
    "executive": ("executive", "board", "leadership", "gm", "vp"),
    "evidence": ("evidence", "proof", "analysis", "analytical", "evidence-led"),
    "screenshot": ("screenshot", "screen", "ui", "interface"),
    "divider": ("divider", "section break", "section divider", "divider band"),
    "table": ("table", "tabular", "lookup"),
    "chart": ("chart", "graph", "series", "trend"),
}
PRESENTATION_TYPE_TO_CUES = {
    PresentationType.EXPLAINER: {"executive", "evidence"},
    PresentationType.PERSUASION: {"persuasion", "decision", "executive"},
    PresentationType.REPORT: {"report", "evidence", "chart", "table", "executive"},
    PresentationType.DECISION: {"decision", "evidence", "executive"},
    PresentationType.TRAINING: {"training", "screenshot", "divider"},
    PresentationType.DEMO: {"demo", "screenshot", "divider"},
    PresentationType.PITCH: {"pitch", "persuasion", "executive"},
    PresentationType.KEYNOTE: {"keynote", "executive", "divider"},
    PresentationType.WORKSHOP: {"workshop", "divider", "training"},
}
STRUCTURED_CONTEXT_KEYS = {
    "topic",
    "purpose",
    "audience",
    "notes",
    "constraints",
    "facts",
    "recommendations",
}


class ReferencePackMetadata(ContractModel):
    deck_title: str | None = None
    positioning: str | None = None
    source_family: str | None = None
    tags: list[str] = Field(default_factory=list)
    tone_keywords: list[str] = Field(default_factory=list)
    patterns_worth_borrowing: list[str] = Field(default_factory=list)
    patterns_to_avoid: list[str] = Field(default_factory=list)
    layout_logic: list[str] = Field(default_factory=list)
    hierarchy_behavior: list[str] = Field(default_factory=list)
    whitespace_behavior: list[str] = Field(default_factory=list)
    section_divider_style: str | None = None
    chart_table_treatment: list[str] = Field(default_factory=list)
    icon_illustration_treatment: list[str] = Field(default_factory=list)
    pacing_and_title_behavior: list[str] = Field(default_factory=list)
    fit_assessment: str | None = None
    terminology_guardrails: list[str] = Field(default_factory=list)
    section_guardrails: list[str] = Field(default_factory=list)

    @field_validator(*LIST_FIELDS, mode="before")
    @classmethod
    def _coerce_list_fields(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value


class ReferenceBriefContext(ContractModel):
    topic: str | None = None
    purpose: str | None = None
    audience: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @field_validator("audience", "notes", "constraints", "facts", "recommendations", mode="before")
    @classmethod
    def _coerce_list_fields(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value


class ReferencePackSummary(ContractModel):
    total_sources: int
    source_type_counts: dict[str, int] = Field(default_factory=dict)
    cue_tags: list[str] = Field(default_factory=list)
    tone_keywords: list[str] = Field(default_factory=list)
    has_screenshots: bool = False
    has_documents: bool = False
    has_notes: bool = False
    has_decks: bool = False
    has_data: bool = False
    has_divider_examples: bool = False


@dataclass(frozen=True)
class ReferenceSourceCandidate:
    file_path: Path
    material: ProjectMaterial


@dataclass(frozen=True)
class ReferenceMaterialAudit:
    score_total: int
    score_components: dict[str, int]
    selection_reason_codes: list[str]
    confidence_band: ReferenceConfidenceBand
    uncertain: bool


PRIMARY_FILENAME_HINTS = {
    BriefMaterialType.IMAGE: ("screenshot", "screen", "ui", "interface", "divider"),
    BriefMaterialType.DOCUMENT: ("report", "readout", "analysis", "evidence", "appendix"),
    BriefMaterialType.DECK: ("deck", "slides", "template", "keynote"),
    BriefMaterialType.NOTES: ("notes", "brief", "guide", "playbook"),
    BriefMaterialType.DATA: ("table", "chart", "data", "metrics", "tracker"),
    BriefMaterialType.SPREADSHEET: ("table", "chart", "model", "metrics", "tracker"),
}
CAPTION_HINT_KEYWORDS = ("caption", "callout", "annotated", "annotation", "figure", "legend")
LAYOUT_HINT_KEYWORDS = ("layout", "template", "screenshot", "divider", "slide", "deck", "title", "annotation")
TABLE_OR_DIAGRAM_HINT_KEYWORDS = ("report", "chart", "graph", "table", "diagram", "framework", "timeline", "matrix")
ANNOTATION_HINT_KEYWORDS = ("annotation", "annotated", "caption", "callout")
SELECTION_REASON_CODE_ORDER = (
    "filename_signal",
    "metadata_signal",
    "caption_signal",
    "layout_signal",
    "table_or_diagram_signal",
    "position_signal",
)
HIGH_CONFIDENCE_SCORE = 10
MEDIUM_CONFIDENCE_SCORE = 6
MAX_REFERENCE_PROFILE_SOURCES = 5


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _match_cue_tags(text: str) -> set[str]:
    matched: set[str] = set()
    for tag, keywords in REFERENCE_CUE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            matched.add(tag)
    return matched


def _metadata_signal_text(metadata: ReferencePackMetadata) -> str:
    parts: list[str] = [
        metadata.positioning or "",
        metadata.source_family or "",
        metadata.section_divider_style or "",
        metadata.fit_assessment or "",
    ]
    for key in LIST_FIELDS:
        parts.extend(getattr(metadata, key))
    return " ".join(part for part in parts if part).lower()


def _material_text(file_path: Path, material: ProjectMaterial) -> str:
    parts = [
        file_path.stem.replace("-", " ").replace("_", " ").lower(),
        " ".join(part.lower() for part in file_path.parts),
        material.label.lower(),
        (material.notes or "").lower(),
    ]
    return " ".join(part for part in parts if part)


def _confidence_band_for_score(score_total: int) -> ReferenceConfidenceBand:
    if score_total >= HIGH_CONFIDENCE_SCORE:
        return ReferenceConfidenceBand.HIGH
    if score_total >= MEDIUM_CONFIDENCE_SCORE:
        return ReferenceConfidenceBand.MEDIUM
    return ReferenceConfidenceBand.LOW


def _score_reference_material(
    pack_path: Path,
    file_path: Path,
    material: ProjectMaterial,
    metadata: ReferencePackMetadata,
    desired_cues: set[str],
) -> ReferenceMaterialAudit:
    material_text = _material_text(file_path, material)
    metadata_text = _metadata_signal_text(metadata)
    metadata_tags = {tag.lower() for tag in metadata.tags}
    material_cues = _match_cue_tags(material_text)

    filename_signal = min(len(material_cues), 2)
    if _contains_any(material_text, PRIMARY_FILENAME_HINTS.get(material.material_type, ())):
        filename_signal += 1
    if desired_cues and material_cues & desired_cues:
        filename_signal += 1
    elif metadata_tags and material_cues & metadata_tags:
        filename_signal += 1
    filename_signal = min(filename_signal, 4)

    metadata_signal = 0
    if material.material_type == BriefMaterialType.NOTES and metadata_text:
        metadata_signal += 3
    elif material.material_type == BriefMaterialType.DOCUMENT and metadata_tags & {"report", "decision", "evidence", "chart", "table"}:
        metadata_signal += 3
    elif material.material_type == BriefMaterialType.IMAGE and metadata_tags & {"executive", "divider", "evidence", "screenshot"}:
        metadata_signal += 2
    elif material.material_type == BriefMaterialType.DECK and metadata_tags & {"executive", "divider", "pitch", "persuasion"}:
        metadata_signal += 2
    elif material.material_type in {BriefMaterialType.DATA, BriefMaterialType.SPREADSHEET} and (
        metadata.chart_table_treatment or metadata_tags & {"chart", "table", "evidence"}
    ):
        metadata_signal += 2
    if desired_cues and metadata_tags & desired_cues:
        metadata_signal += 1
    metadata_signal = min(metadata_signal, 4)

    caption_signal = 0
    if _contains_any(material_text, CAPTION_HINT_KEYWORDS):
        caption_signal += 1
    if material.material_type == BriefMaterialType.IMAGE and _contains_any(metadata_text, ANNOTATION_HINT_KEYWORDS):
        caption_signal += 1
    caption_signal = min(caption_signal, 2)

    layout_signal = 0
    if material.material_type == BriefMaterialType.NOTES:
        layout_signal += 2
    elif _contains_any(material_text, LAYOUT_HINT_KEYWORDS):
        layout_signal += 2
    if metadata.layout_logic or metadata.hierarchy_behavior or metadata.whitespace_behavior:
        layout_signal += 1
    layout_signal = min(layout_signal, 3)

    table_or_diagram_signal = 0
    if material.material_type in {BriefMaterialType.DOCUMENT, BriefMaterialType.DATA, BriefMaterialType.SPREADSHEET}:
        table_or_diagram_signal += 1
    if _contains_any(material_text, TABLE_OR_DIAGRAM_HINT_KEYWORDS):
        table_or_diagram_signal += 2
    if material.material_type in {BriefMaterialType.DOCUMENT, BriefMaterialType.DATA, BriefMaterialType.SPREADSHEET} and metadata.chart_table_treatment:
        table_or_diagram_signal += 1
    table_or_diagram_signal = min(table_or_diagram_signal, 3)

    relative_path = file_path.relative_to(pack_path)
    if len(relative_path.parts) == 1:
        position_signal = 2
    elif len(relative_path.parts) == 2:
        position_signal = 1
    else:
        position_signal = 0
    if material.material_type == BriefMaterialType.NOTES:
        position_signal += 1
    position_signal = min(position_signal, 3)

    score_components = {
        "filename_signal": filename_signal,
        "metadata_signal": metadata_signal,
        "caption_signal": caption_signal,
        "layout_signal": layout_signal,
        "table_or_diagram_signal": table_or_diagram_signal,
        "position_signal": position_signal,
    }
    score_total = sum(score_components.values())
    confidence_band = _confidence_band_for_score(score_total)
    uncertain = score_total < MEDIUM_CONFIDENCE_SCORE

    selection_reason_codes = [code for code in SELECTION_REASON_CODE_ORDER if score_components[code] > 0]
    if uncertain and sum(1 for code in SELECTION_REASON_CODE_ORDER if score_components[code] > 0) >= 2:
        selection_reason_codes.append("weak_signal_mix")
    if uncertain:
        selection_reason_codes.append("uncertain_low_confidence")

    return ReferenceMaterialAudit(
        score_total=score_total,
        score_components=score_components,
        selection_reason_codes=selection_reason_codes,
        confidence_band=confidence_band,
        uncertain=uncertain,
    )


def _apply_material_audit(material: ProjectMaterial, audit: ReferenceMaterialAudit) -> ProjectMaterial:
    return material.model_copy(
        update={
            "score_total": audit.score_total,
            "score_components": audit.score_components,
            "selection_reason_codes": audit.selection_reason_codes,
            "confidence_band": audit.confidence_band,
            "uncertain": audit.uncertain,
        }
    )


def _audit_source_files(
    pack_path: Path,
    metadata: ReferencePackMetadata,
    source_candidates: list[ReferenceSourceCandidate],
    workflow_plan: WorkflowPlan | None,
    brief_context: ReferenceBriefContext | None,
) -> list[ProjectMaterial]:
    desired_cues = _desired_cue_tags(workflow_plan, brief_context)
    audited_materials: list[ProjectMaterial] = []
    for candidate in source_candidates:
        audit = _score_reference_material(pack_path, candidate.file_path, candidate.material, metadata, desired_cues)
        audited_materials.append(_apply_material_audit(candidate.material, audit))
    return audited_materials


def _read_structured_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"metadata file must contain a top-level object: {path}")
    return data


def load_reference_brief_context(path: str | Path) -> ReferenceBriefContext:
    context_path = Path(path)
    text = context_path.read_text(encoding="utf-8")
    if context_path.suffix.lower() in {".yaml", ".yml", ".json"}:
        payload = _read_structured_file(context_path)
        scoped = {key: value for key, value in payload.items() if key in STRUCTURED_CONTEXT_KEYS}
        return ReferenceBriefContext.model_validate(scoped)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ReferenceBriefContext(notes=lines)


def _merge_metadata(base: ReferencePackMetadata, updates: dict[str, Any]) -> ReferencePackMetadata:
    current = base.model_dump()
    for key, value in updates.items():
        if key not in current:
            continue
        if key in LIST_FIELDS:
            merged = list(current[key])
            incoming = value if isinstance(value, list) else [value]
            merged.extend(str(item) for item in incoming if item)
            current[key] = _dedupe(merged)
        elif value not in (None, "", []):
            current[key] = value
    return ReferencePackMetadata.model_validate(current)


def _parse_markdown_sections(path: Path) -> dict[str, Any]:
    sections: dict[str, list[str]] = {}
    current_key: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_key, buffer
        if current_key is None:
            buffer = []
            return
        sections.setdefault(current_key, []).extend(buffer)
        buffer = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        heading_match = re.match(r"^\s*#{1,6}\s+(.*)$", raw_line)
        if heading_match:
            flush()
            heading = _normalize_heading(heading_match.group(1))
            current_key = MARKDOWN_SECTION_MAP.get(heading)
            continue
        if current_key is not None:
            stripped = raw_line.strip()
            if stripped:
                buffer.append(stripped)
    flush()

    parsed: dict[str, Any] = {}
    for key, lines in sections.items():
        if key in LIST_FIELDS:
            items: list[str] = []
            for line in lines:
                if line.startswith(("-", "*")):
                    items.append(line[1:].strip())
                else:
                    items.append(line)
            parsed[key] = _dedupe(items)
        else:
            parsed[key] = " ".join(line.lstrip("-* ").strip() for line in lines).strip()
    return parsed


def _classify_material(path: Path) -> BriefMaterialType | None:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return BriefMaterialType.IMAGE
    if suffix in DOCUMENT_EXTENSIONS:
        return BriefMaterialType.DOCUMENT
    if suffix in DECK_EXTENSIONS:
        return BriefMaterialType.DECK
    if suffix in NOTES_EXTENSIONS:
        return BriefMaterialType.NOTES
    if suffix in DATA_EXTENSIONS:
        return BriefMaterialType.DATA
    if suffix in SPREADSHEET_EXTENSIONS:
        return BriefMaterialType.SPREADSHEET
    return None


def _collect_source_candidates(pack_path: Path) -> list[ReferenceSourceCandidate]:
    materials: list[ReferenceSourceCandidate] = []
    for file_path in sorted(candidate for candidate in pack_path.rglob("*") if candidate.is_file()):
        if file_path.name.lower() in METADATA_FILENAMES:
            continue
        material_type = _classify_material(file_path)
        if material_type is None:
            continue
        notes = None
        lower_name = file_path.name.lower()
        if "screenshot" in lower_name:
            notes = "PPTX or layout screenshot reference"
        elif "divider" in lower_name:
            notes = "Section-divider example"
        materials.append(
            ReferenceSourceCandidate(
                file_path=file_path,
                material=ProjectMaterial(
                    label=file_path.stem.replace("-", " ").replace("_", " ").strip().title(),
                    material_type=material_type,
                    path=_display_path(file_path),
                    notes=notes,
                ),
            )
        )
    return materials


def _load_pack_metadata(pack_path: Path) -> ReferencePackMetadata:
    metadata = ReferencePackMetadata()
    for file_path in sorted(candidate for candidate in pack_path.rglob("*") if candidate.is_file()):
        lower_name = file_path.name.lower()
        if lower_name in METADATA_FILENAMES:
            metadata = _merge_metadata(metadata, _read_structured_file(file_path))
        elif file_path.suffix.lower() in NOTES_EXTENSIONS:
            metadata = _merge_metadata(metadata, _parse_markdown_sections(file_path))
    return metadata


def _collect_pack_text(pack_path: Path, metadata: ReferencePackMetadata, source_files: list[ProjectMaterial]) -> str:
    parts = [pack_path.name]
    metadata_payload = metadata.model_dump(mode="json", exclude_none=True)
    for value in metadata_payload.values():
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    for file_path in sorted(candidate for candidate in pack_path.rglob("*") if candidate.is_file()):
        parts.append(file_path.stem.replace("-", " ").replace("_", " "))
        if file_path.suffix.lower() in NOTES_EXTENSIONS:
            parts.append(file_path.read_text(encoding="utf-8"))
    for material in source_files:
        parts.append(material.label)
        if material.notes:
            parts.append(material.notes)
    return " ".join(parts).lower()


def _extract_cue_tags(text: str, metadata: ReferencePackMetadata, source_files: list[ProjectMaterial]) -> list[str]:
    tags = [tag.lower() for tag in metadata.tags]
    for tag, keywords in REFERENCE_CUE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    if any(material.notes and "screenshot" in material.notes.lower() for material in source_files):
        tags.append("screenshot")
    if any(material.notes and "divider" in material.notes.lower() for material in source_files):
        tags.append("divider")
    return _dedupe(tags)


def _summarize_pack(pack_path: Path, metadata: ReferencePackMetadata, source_files: list[ProjectMaterial]) -> ReferencePackSummary:
    counts: dict[str, int] = {}
    for material in source_files:
        counts[material.material_type.value] = counts.get(material.material_type.value, 0) + 1
    pack_text = _collect_pack_text(pack_path, metadata, source_files)
    cue_tags = _extract_cue_tags(pack_text, metadata, source_files)
    return ReferencePackSummary(
        total_sources=len(source_files),
        source_type_counts=counts,
        cue_tags=cue_tags,
        tone_keywords=_dedupe(metadata.tone_keywords),
        has_screenshots="image" in counts,
        has_documents="document" in counts,
        has_notes="notes" in counts,
        has_decks="deck" in counts,
        has_data=any(key in counts for key in {"data", "spreadsheet"}),
        has_divider_examples="divider" in cue_tags,
    )


def _infer_source_family(
    pack_path: Path,
    metadata: ReferencePackMetadata,
    source_files: list[ProjectMaterial],
    summary: ReferencePackSummary,
) -> str:
    if metadata.source_family:
        return metadata.source_family
    kinds = {material.material_type for material in source_files}
    if summary.has_documents and summary.has_screenshots:
        return f"{pack_path.name} report-and-screenshot family"
    if summary.has_screenshots:
        return f"{pack_path.name} screenshot-led family"
    if BriefMaterialType.DECK in kinds:
        return f"{pack_path.name} prior-deck family"
    return f"{pack_path.name} local reference family"


def _default_positioning(source_family: str, summary: ReferencePackSummary) -> str:
    if summary.has_documents and summary.has_screenshots:
        return f"Borrow evidence-led structure and screenshot framing from the {source_family} without copying literal templates."
    if summary.has_screenshots:
        return f"Borrow screenshot hierarchy and divider pacing from the {source_family} without copying literal templates."
    return f"Borrow reusable compositional behavior from the {source_family} without copying literal templates."


def _file_kind_summary(source_files: list[ProjectMaterial]) -> set[BriefMaterialType]:
    return {material.material_type for material in source_files}


def _default_patterns_worth_borrowing(source_files: list[ProjectMaterial], summary: ReferencePackSummary) -> list[str]:
    kinds = _file_kind_summary(source_files)
    patterns = ["Borrow modular layout logic and calm visual restraint rather than one-off ornament."]
    if BriefMaterialType.DOCUMENT in kinds:
        patterns.append("Borrow evidence-panel framing from local PDF references without reproducing report pages directly.")
    if BriefMaterialType.IMAGE in kinds:
        patterns.append("Borrow screenshot framing and divider pacing when it improves clarity.")
    if BriefMaterialType.NOTES in kinds:
        patterns.append("Borrow the editorial logic described in local notes before borrowing any surface styling.")
    if "executive" in summary.cue_tags:
        patterns.append("Borrow the executive editing discipline from the pack rather than any single layout.")
    return _dedupe(patterns)


def _default_patterns_to_avoid(source_files: list[ProjectMaterial]) -> list[str]:
    patterns = [
        "Do not copy branded ornament, decorative geometry, or template-specific flourishes verbatim.",
        "Do not reproduce dense report pages or screenshot clutter as slide compositions.",
    ]
    if any(material.notes and "divider" in material.notes.lower() for material in source_files):
        patterns.append("Do not overuse section-divider treatments inside the main story.")
    return _dedupe(patterns)


def _default_layout_logic(summary: ReferencePackSummary) -> list[str]:
    logic = [
        "Use a reusable two-zone layout: one dominant thesis or visual zone and one supporting evidence zone.",
        "Prefer export-safe alignment, stable gutters, and repeatable patterns over custom per-slide compositions.",
    ]
    if summary.has_screenshots:
        logic.append("Treat screenshots as one anchored visual zone with a single clear annotation region.")
    return _dedupe(logic)


def _default_hierarchy_behavior() -> list[str]:
    return [
        "Keep titles short and message-led, with supporting text clearly subordinate.",
        "Use one primary hierarchy break per slide rather than several competing emphasis styles.",
    ]


def _default_whitespace_behavior() -> list[str]:
    return [
        "Maintain generous margins and visible gutters so dense evidence does not collapse into a report page.",
        "Use whitespace to separate thesis, evidence, and backup detail rather than extra decoration.",
    ]


def _default_chart_table_treatment(source_files: list[ProjectMaterial], summary: ReferencePackSummary) -> list[str]:
    treatments = [
        "Prefer rebuilding dense charts or tables as slide-native visuals instead of embedding them raw.",
        "Keep tables narrow in scope and demote long-form evidence to appendix candidates when possible.",
    ]
    if any(material.material_type == BriefMaterialType.DOCUMENT for material in source_files):
        treatments.append("Use PDF references to borrow analytical framing, not chart styling line for line.")
    if summary.has_data:
        treatments.append("Borrow the signal-selection behavior from data-heavy references, but simplify category count aggressively.")
    return _dedupe(treatments)


def _default_icon_treatment(summary: ReferencePackSummary) -> list[str]:
    treatments = [
        "Use simple, consistent icons or illustrations only when they clarify structure.",
        "Avoid mascot-like illustration styles or mixed icon families across sections.",
    ]
    if summary.has_screenshots:
        treatments.append("Let screenshots and evidence objects do most of the visual work before introducing icons.")
    return _dedupe(treatments)


def _default_pacing_behavior(summary: ReferencePackSummary) -> list[str]:
    behaviors = [
        "Use thesis-first titles and reserve pacing resets for true section changes.",
        "Keep divider slides short and let the main story carry the argument, not decorative pacing devices.",
    ]
    if summary.has_divider_examples:
        behaviors.append("Use divider moments sparingly and keep them visually quieter than analytical slides.")
    return _dedupe(behaviors)


def _default_section_divider_style(source_files: list[ProjectMaterial], summary: ReferencePackSummary) -> str:
    if summary.has_divider_examples or any(material.notes and "divider" in material.notes.lower() for material in source_files):
        return "Muted divider visuals with short labels and clear separation from evidence slides."
    return "Simple divider titles with restrained visual interruption and no heavy ornament."


def _brief_context_text(brief_context: ReferenceBriefContext | None) -> str:
    if brief_context is None:
        return ""
    return " ".join(
        [
            brief_context.topic or "",
            brief_context.purpose or "",
            " ".join(brief_context.audience),
            " ".join(brief_context.notes),
            " ".join(brief_context.constraints),
            " ".join(brief_context.facts),
            " ".join(brief_context.recommendations),
        ]
    ).lower()


def _desired_cue_tags(workflow_plan: WorkflowPlan | None, brief_context: ReferenceBriefContext | None) -> set[str]:
    desired: set[str] = set()
    if workflow_plan is not None:
        types = {workflow_plan.presentation_type_diagnosis.primary_type, *workflow_plan.presentation_type_diagnosis.secondary_types}
        for presentation_type in types:
            desired.update(PRESENTATION_TYPE_TO_CUES[presentation_type])
        if workflow_plan.scale_mode in {ScaleMode.LARGE_DECK, ScaleMode.MEGA_DECK}:
            desired.add("divider")
        if workflow_plan.deck_mode.value != "main-story":
            desired.add("evidence")
    context_text = _brief_context_text(brief_context)
    for tag, keywords in REFERENCE_CUE_KEYWORDS.items():
        if any(keyword in context_text for keyword in keywords):
            desired.add(tag)
    return desired


def _alignment_strength(
    workflow_plan: WorkflowPlan | None,
    brief_context: ReferenceBriefContext | None,
    summary: ReferencePackSummary,
) -> tuple[str, list[str]]:
    if workflow_plan is None and brief_context is None:
        return (
            "Partially aligned",
            ["No workflow context was supplied, so the pack is only partially aligned until Gate 1 context exists."],
        )

    desired = _desired_cue_tags(workflow_plan, brief_context)
    pack_tags = set(summary.cue_tags)
    score = len(desired & pack_tags)
    reasons: list[str] = []

    if workflow_plan is not None:
        types = {workflow_plan.presentation_type_diagnosis.primary_type, *workflow_plan.presentation_type_diagnosis.secondary_types}
        if (PresentationType.REPORT in types or PresentationType.DECISION in types) and summary.has_documents:
            score += 2
            reasons.append("the pack includes document-based evidence references")
        if (PresentationType.TRAINING in types or PresentationType.DEMO in types) and summary.has_screenshots:
            score += 2
            reasons.append("the pack includes screenshot-led references")
        if PresentationType.WORKSHOP in types and summary.has_divider_examples:
            score += 2
            reasons.append("the pack includes divider examples that support facilitation pacing")
        if (PresentationType.PITCH in types or PresentationType.KEYNOTE in types) and ("executive" in pack_tags or summary.has_decks):
            score += 1
            reasons.append("the pack reads as executive-facing rather than document-heavy only")

    if summary.has_notes:
        reasons.append("local notes add reusable editorial guidance")
    if summary.has_data:
        reasons.append("data-bearing sources can inform chart and table treatment")

    if score >= 5:
        return "Strongly aligned", _dedupe(reasons)
    if score >= 2:
        return "Partially aligned", _dedupe(reasons)
    return "Weakly aligned", _dedupe(reasons or ["the pack cues do not strongly match the current workflow context"])


def _default_fit_assessment(
    source_family: str,
    workflow_plan: WorkflowPlan | None,
    brief_context: ReferenceBriefContext | None,
    summary: ReferencePackSummary,
) -> str:
    strength, reasons = _alignment_strength(workflow_plan, brief_context, summary)
    if workflow_plan is not None:
        diagnosis = workflow_plan.presentation_type_diagnosis.diagnosis_label
        scale_mode = workflow_plan.scale_mode.value
        reason_text = "; ".join(reasons[:2]) if reasons else "the pack offers reusable structural behavior"
        return f"{strength} for {diagnosis} decks: {reason_text} for a {scale_mode} deck."
    if brief_context is not None:
        reason_text = "; ".join(reasons[:2]) if reasons else "the pack offers reusable structural behavior"
        return f"{strength} for the supplied brief context: {reason_text}."
    return f"{strength} for future Gate 2 work. The {source_family} should be treated as a local-first reference pack until a workflow_plan exists."


def _fit_assessment(
    metadata_fit_assessment: str | None,
    source_family: str,
    workflow_plan: WorkflowPlan | None,
    brief_context: ReferenceBriefContext | None,
    summary: ReferencePackSummary,
) -> str:
    contextual_fit = _default_fit_assessment(source_family, workflow_plan, brief_context, summary)
    if not metadata_fit_assessment:
        return contextual_fit
    if workflow_plan is None and brief_context is None:
        return f"{contextual_fit} Reference pack note: {metadata_fit_assessment}"
    return f"{contextual_fit} Reference pack note: {metadata_fit_assessment}"


def _reference_material_sort_key(material: ProjectMaterial) -> tuple[int, int, str, str]:
    return (1 if material.uncertain else 0, -(material.score_total or 0), material.path or "", material.label)


def _make_reference_profiles(source_family: str, source_files: list[ProjectMaterial]) -> list[ReferenceProfile]:
    selected_materials = [
        material for material in sorted(source_files, key=_reference_material_sort_key) if not material.uncertain and material.path
    ][:MAX_REFERENCE_PROFILE_SOURCES]
    source_material_refs = [
        SourceMaterialRef(
            source_id=f"ref-{index+1}",
            label=material.label,
            path=material.path,
            notes=material.notes,
            score_total=material.score_total,
            score_components=dict(material.score_components),
            selection_reason_codes=list(material.selection_reason_codes),
            confidence_band=material.confidence_band,
            uncertain=material.uncertain,
        )
        for index, material in enumerate(selected_materials)
    ]
    rationale = "Use this pack for compositional behavior, hierarchy, and pacing rather than template copying."
    if not source_material_refs:
        rationale = "No source files crossed the confidence threshold automatically; inspect uncertain source_files before borrowing patterns from this pack."
    return [
        ReferenceProfile(
            name=source_family,
            rationale=rationale,
            source_material_refs=source_material_refs,
        )
    ]


def scan_reference_pack(
    pack_path: str | Path,
    workflow_plan: WorkflowPlan | None = None,
    deck_title: str | None = None,
    brief_context: ReferenceBriefContext | None = None,
) -> ReferenceDNA:
    resolved_pack = Path(pack_path)
    if not resolved_pack.is_dir():
        raise FileNotFoundError(f"reference pack directory not found: {resolved_pack}")

    metadata = _load_pack_metadata(resolved_pack)
    source_candidates = _collect_source_candidates(resolved_pack)
    if not source_candidates:
        raise ValueError(f"reference pack contains no supported local source files: {resolved_pack}")

    source_files = [candidate.material for candidate in source_candidates]
    audited_source_files = _audit_source_files(resolved_pack, metadata, source_candidates, workflow_plan, brief_context)
    trusted_source_files = [material for material in audited_source_files if not material.uncertain]
    design_source_files = trusted_source_files or audited_source_files
    design_summary = _summarize_pack(resolved_pack, metadata, design_source_files)
    source_family = _infer_source_family(resolved_pack, metadata, design_source_files, design_summary)
    positioning = metadata.positioning or _default_positioning(source_family, design_summary)
    patterns_worth_borrowing = metadata.patterns_worth_borrowing or _default_patterns_worth_borrowing(design_source_files, design_summary)
    patterns_to_avoid = metadata.patterns_to_avoid or _default_patterns_to_avoid(design_source_files)
    layout_logic = metadata.layout_logic or _default_layout_logic(design_summary)
    hierarchy_behavior = metadata.hierarchy_behavior or _default_hierarchy_behavior()
    whitespace_behavior = metadata.whitespace_behavior or _default_whitespace_behavior()
    section_divider_style = metadata.section_divider_style or _default_section_divider_style(design_source_files, design_summary)
    chart_table_treatment = metadata.chart_table_treatment or _default_chart_table_treatment(design_source_files, design_summary)
    icon_treatment = metadata.icon_illustration_treatment or _default_icon_treatment(design_summary)
    pacing_behavior = metadata.pacing_and_title_behavior or _default_pacing_behavior(design_summary)
    fit_assessment = _fit_assessment(metadata.fit_assessment, source_family, workflow_plan, brief_context, design_summary)

    resolved_deck_title = deck_title or metadata.deck_title or (workflow_plan.deck_title if workflow_plan else resolved_pack.name.replace("-", " ").title())

    return ReferenceDNA(
        deck_title=resolved_deck_title,
        positioning=positioning,
        scan_mode=ReferenceScanMode.LOCAL_FIRST,
        source_family=source_family,
        source_files=audited_source_files,
        patterns_worth_borrowing=patterns_worth_borrowing,
        patterns_to_avoid=patterns_to_avoid,
        layout_logic=layout_logic,
        hierarchy_behavior=hierarchy_behavior,
        whitespace_behavior=whitespace_behavior,
        section_divider_style=section_divider_style,
        chart_table_treatment=chart_table_treatment,
        icon_illustration_treatment=icon_treatment,
        pacing_and_title_behavior=pacing_behavior,
        fit_assessment=fit_assessment,
        reference_profiles=_make_reference_profiles(source_family, audited_source_files),
        terminology_guardrails=_dedupe(metadata.terminology_guardrails),
        section_guardrails=_dedupe(metadata.section_guardrails),
    )


