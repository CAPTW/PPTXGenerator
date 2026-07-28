"""Deterministic source-document crop worker for PDFs, raster images, and DOCX media."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

import fitz
from PIL import Image
from pydantic import Field, field_validator

from ..compat.legacy_non_pptx import (
    AssetKind,
    AssetManifest,
    AssetPriority,
    AssetProvenance,
    AssetRecord,
    AssetRenderSettings,
    AssetRequest,
    AssetRequests,
    AssetStatus,
    ContractModel,
    CropBounds,
    CropReviewAction,
    ProductionMode,
    RenderAdapter,
    SchemaModel,
    SlideLedger,
    SlideLedgerEntry,
    SourceMaterialRef,
    StageStatus,
    VisualSourcePreference,
    VisualType,
    save_state_file,
)


class SourcePreview(ContractModel):
    preview_id: str
    request_id: str
    slide_id: str
    source_file: str
    adapter: RenderAdapter
    page_number: int | None = None
    source_index: int | None = None
    preview_path: str
    render_settings: AssetRenderSettings
    limitations: list[str] = Field(default_factory=list)


class CropCandidate(ContractModel):
    candidate_id: str
    request_id: str
    slide_id: str
    slide_number: int
    source_file: str
    adapter: RenderAdapter
    page_number: int | None = None
    source_index: int | None = None
    preview_path: str
    candidate_path: str
    crop_box: CropBounds
    score: float
    selection_rank: int
    rationale: list[str] = Field(default_factory=list)
    render_settings: AssetRenderSettings
    provenance: AssetProvenance
    limitations: list[str] = Field(default_factory=list)


class SelectedCrop(ContractModel):
    selection_id: str
    candidate_id: str
    request_id: str
    slide_id: str
    slide_number: int
    asset_id: str
    output_path: str
    status: AssetStatus
    review_action: CropReviewAction
    selection_method: str
    provenance: AssetProvenance
    limitations: list[str] = Field(default_factory=list)


class CropCandidates(SchemaModel):
    SCHEMA_NAME = "crop_candidates"
    SUMMARY = "Deterministic crop candidates generated from local source documents before any review."

    deck_title: str
    previews: list[SourcePreview] = Field(default_factory=list)
    candidates: list[CropCandidate] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SelectedCrops(SchemaModel):
    SCHEMA_NAME = "selected_crops"
    SUMMARY = "Best-effort selected crops and their provenance for downstream asset assembly."

    deck_title: str
    selections: list[SelectedCrop] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


ALLOWED_REVIEW_ACTIONS = {
    "accept",
    "reject",
    "expand_top",
    "expand_bottom",
    "expand_left",
    "expand_right",
    "tighten",
    "exclude_caption_band",
    "fallback_to_generated_visual",
}


class CropReviewReasonCode(str, Enum):
    MISSING_REQUEST_ID = "missing_request_id"
    MISSING_SLIDE_ID = "missing_slide_id"
    CANDIDATE_NOT_FOUND_FOR_REQUEST = "candidate_not_found_for_request"
    MANIFEST_ASSET_MISSING = "manifest_asset_missing"
    ARTIFACT_FILE_MISSING = "artifact_file_missing"
    MANIFEST_LINEAGE_MISMATCH = "manifest_lineage_mismatch"
    SELECTED_CROP_NOT_COMPILE_READY = "selected_crop_not_compile_ready"
    REVIEW_ROUND_LIMIT_REACHED = "review_round_limit_reached"
    CANDIDATE_LINEAGE_MISMATCH = "candidate_lineage_mismatch"


MAX_REVIEW_ROUNDS_LOWER_BOUND = 0
MAX_REVIEW_ROUNDS_UPPER_BOUND = 2


def _parse_review_action(action: str) -> tuple[str, str | None]:
    if action.startswith("choose_candidate_"):
        candidate_id = action.removeprefix("choose_candidate_")
        if not candidate_id:
            raise ValueError("choose_candidate actions must include a candidate id")
        return "choose_candidate", candidate_id
    if action not in ALLOWED_REVIEW_ACTIONS:
        raise ValueError(f"unsupported crop review action {action!r}")
    return action, None


class BoundedCropReviewDirective(ContractModel):
    action: str
    rationale: str
    failure_reason: str | None = None
    fallback_reason: str | None = None

    @field_validator("action")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        _parse_review_action(value)
        return value

    @property
    def action_kind(self) -> str:
        return _parse_review_action(self.action)[0]

    @property
    def target_candidate_id(self) -> str | None:
        return _parse_review_action(self.action)[1]


class CropReviewInput(ContractModel):
    input_id: str
    request_id: str
    slide_id: str
    slide_number: int
    iteration: int
    page_preview_path: str
    source_file: str
    current_candidate_id: str
    slide_intent: str
    crop_subject_hint: str | None = None
    visual_type_expectation: VisualType
    request_priority: AssetPriority
    asset_quality_requirements: list[str] = Field(default_factory=list)
    fallback_ladder: list[VisualType] = Field(default_factory=list)
    source_material_refs: list[SourceMaterialRef] = Field(default_factory=list)
    configured_max_review_rounds: int = 2
    review_rounds_used: int = 0
    termination_reason: str | None = None
    manifest_asset_id: str | None = None
    candidates: list[CropCandidate] = Field(default_factory=list)


class CropReviewInputs(SchemaModel):
    SCHEMA_NAME = "crop_review_inputs"
    SUMMARY = "Persisted bounded crop-review inputs for each request and iteration."

    deck_title: str
    inputs: list[CropReviewInput] = Field(default_factory=list)


class CropReviewDecision(ContractModel):
    decision_id: str
    input_id: str
    request_id: str
    slide_id: str
    slide_number: int | None = None
    iteration: int
    reviewer_name: str
    action: str
    current_candidate_id: str
    applied_candidate_id: str | None = None
    rationale: str
    terminal: bool = False
    configured_max_review_rounds: int = 2
    review_rounds_used: int = 0
    termination_reason: str | None = None
    fallback_applied: bool = False
    stopped_without_fallback: bool = False
    selection_reason_codes: list[str] = Field(default_factory=list)
    manifest_asset_id: str | None = None
    manifest_asset_path: str | None = None
    selected_candidate_path: str | None = None
    failure_reason: str | None = None
    fallback_reason: str | None = None

    @field_validator("action")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        _parse_review_action(value)
        return value


class CropReviewDecisions(SchemaModel):
    SCHEMA_NAME = "crop_review_decisions"
    SUMMARY = "Persisted bounded crop-review decisions and final outcomes."

    deck_title: str
    decisions: list[CropReviewDecision] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DocumentCropOutputs(ContractModel):
    crop_candidates: CropCandidates
    crop_review_inputs: CropReviewInputs
    crop_review_decisions: CropReviewDecisions
    selected_crops: SelectedCrops
    asset_manifest: AssetManifest
    slide_ledger: SlideLedger


class CropReviewer(Protocol):
    name: str

    def review(self, review_input: CropReviewInput) -> BoundedCropReviewDirective:
        ...


class HeuristicCropReviewer:
    name = "heuristic-crop-reviewer"

    def review(self, review_input: CropReviewInput) -> BoundedCropReviewDirective:
        current = next(
            (candidate for candidate in review_input.candidates if candidate.candidate_id == review_input.current_candidate_id),
            None,
        )
        if current is None:
            return BoundedCropReviewDirective(
                action="fallback_to_generated_visual",
                rationale="No current candidate could be resolved for bounded crop review.",
                fallback_reason="Candidate state was incomplete at review time.",
            )
        if current.score < 0.16:
            return BoundedCropReviewDirective(
                action="fallback_to_generated_visual",
                rationale="The strongest deterministic candidate still scores too weakly for reuse.",
                fallback_reason="Candidate quality stayed below the bounded review threshold.",
            )
        quality_text = " ".join(item.lower() for item in review_input.asset_quality_requirements)
        if "exclude captions" in quality_text or "exclude caption" in quality_text:
            try:
                preview_height = Image.open(review_input.page_preview_path).height
            except Exception:
                preview_height = 0
            bottom = current.crop_box.top + current.crop_box.height
            if preview_height and bottom / float(preview_height) >= 0.84:
                return BoundedCropReviewDirective(
                    action="exclude_caption_band",
                    rationale="The candidate extends deep into the lower page band where caption furniture often lives.",
                )
        return BoundedCropReviewDirective(
            action="accept",
            rationale="Accept the current highest-ranked candidate under the bounded heuristic reviewer.",
        )


@dataclass(slots=True)
class RenderedSurface:
    request: AssetRequest
    source_path: Path
    adapter: RenderAdapter
    image: Image.Image
    preview_path: Path
    preview_label: str
    render_settings: AssetRenderSettings
    page_number: int | None = None
    source_index: int | None = None
    page_size_points: tuple[float, float] | None = None
    limitations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RequestExecutionResult:
    request: AssetRequest
    candidates: list[CropCandidate]
    asset_record: AssetRecord
    selected_crop: SelectedCrop | None
    review_inputs: list[CropReviewInput] = field(default_factory=list)
    review_decisions: list[CropReviewDecision] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    ledger_status: StageStatus = StageStatus.DRAFT
    production_readiness: StageStatus = StageStatus.DRAFT
    blockers: list[str] = field(default_factory=list)
    change_note: str | None = None


@dataclass(slots=True)
class CropLineageValidationIssue:
    reason_code: CropReviewReasonCode
    message: str
    request_id: str
    slide_id: str
    slide_number: int
    candidate_id: str | None = None
    manifest_asset_id: str | None = None
    manifest_asset_path: str | None = None


def _slugify(text: str) -> str:
    letters = []
    previous_dash = False
    for char in text.lower():
        if char.isalnum():
            letters.append(char)
            previous_dash = False
        elif not previous_dash:
            letters.append("-")
            previous_dash = True
    slug = "".join(letters).strip("-")
    return slug or "asset"


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _fallback_ladder_note(request: AssetRequest) -> str:
    ladder = " -> ".join(item.value for item in request.fallback_ladder)
    return f"Fallback ladder preserved: {ladder}."


def _merge_change_note(existing: str | None, addition: str | None) -> str | None:
    if not addition:
        return existing
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} {addition}"


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _candidate_box_to_tuple(bounds: CropBounds) -> tuple[int, int, int, int]:
    left = int(round(bounds.left))
    top = int(round(bounds.top))
    right = int(round(bounds.left + bounds.width))
    bottom = int(round(bounds.top + bounds.height))
    return left, top, right, bottom


def _tuple_to_crop_bounds(left: int, top: int, right: int, bottom: int) -> CropBounds:
    return CropBounds(left=float(left), top=float(top), width=float(right - left), height=float(bottom - top))


def _candidate_selection_reason(code: CropReviewReasonCode | str) -> str:
    return code.value if isinstance(code, CropReviewReasonCode) else str(code)


def _reason_codes(*codes: CropReviewReasonCode | str | None) -> list[str]:
    normalized: list[str] = []
    for code in codes:
        if code is None:
            continue
        value = code.value if isinstance(code, CropReviewReasonCode) else str(code)
        if value not in normalized:
            normalized.append(value)
    return normalized


def _lineage_issue(
    reason_code: CropReviewReasonCode,
    *,
    request: AssetRequest,
    message: str,
    candidate: CropCandidate | None = None,
    manifest_asset: AssetRecord | None = None,
    manifest_asset_path: str | None = None,
) -> CropLineageValidationIssue:
    return CropLineageValidationIssue(
        reason_code=reason_code,
        message=message,
        request_id=request.request_id,
        slide_id=request.slide_id,
        slide_number=request.slide_number,
        candidate_id=(
            candidate.candidate_id
            if candidate is not None
            else manifest_asset.candidate_id if manifest_asset is not None else None
        ),
        manifest_asset_id=manifest_asset.asset_id if manifest_asset is not None else None,
        manifest_asset_path=manifest_asset_path if manifest_asset_path is not None else manifest_asset.local_path if manifest_asset is not None else None,
    )


def _lineage_issue_codes(issues: list[CropLineageValidationIssue]) -> list[str]:
    return _reason_codes(*(issue.reason_code for issue in issues))


def _lineage_issue_summary(issue: CropLineageValidationIssue) -> str:
    parts = [
        f"request_id={issue.request_id or '<missing>'}",
        f"slide_id={issue.slide_id or '<missing>'}",
        f"slide_number={issue.slide_number}",
    ]
    if issue.candidate_id:
        parts.append(f"candidate_id={issue.candidate_id}")
    if issue.manifest_asset_id:
        parts.append(f"manifest_asset_id={issue.manifest_asset_id}")
    if issue.manifest_asset_path:
        parts.append(f"manifest_asset_path={issue.manifest_asset_path}")
    return f"{issue.reason_code.value}: {issue.message} ({', '.join(parts)})"


def _lineage_failure_summary(issues: list[CropLineageValidationIssue]) -> str:
    return "; ".join(_lineage_issue_summary(issue) for issue in issues)


def _artifact_file_exists(path_text: str, root: Path) -> bool:
    return _resolve_source_path(path_text, root).is_file()


def _resolve_source_path(path_text: str, base_dir: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _ensure_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    return image.convert("RGB")


def _pdf_page_numbers(request: AssetRequest, source_ref: SourceMaterialRef, pdf_path: Path) -> list[int]:
    if source_ref.page is not None:
        return [source_ref.page]
    if request.page_hint is not None:
        return [request.page_hint]
    with fitz.open(pdf_path) as document:
        return list(range(1, document.page_count + 1))


def _render_pdf_surfaces(
    request: AssetRequest,
    source_ref: SourceMaterialRef,
    pdf_path: Path,
    previews_dir: Path,
    dpi: int,
    root: Path,
) -> list[RenderedSurface]:
    surfaces: list[RenderedSurface] = []
    zoom = dpi / 72.0
    with fitz.open(pdf_path) as document:
        for page_number in _pdf_page_numbers(request, source_ref, pdf_path):
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            image = _ensure_rgb(image)
            preview_path = previews_dir / f"{_slugify(request.slide_id)}-{_slugify(pdf_path.stem)}-p{page_number:03d}.png"
            image.save(preview_path)
            surfaces.append(
                RenderedSurface(
                    request=request,
                    source_path=pdf_path,
                    adapter=RenderAdapter.PDF,
                    image=image,
                    preview_path=preview_path,
                    preview_label=_display_path(preview_path, root),
                    page_number=page_number,
                    render_settings=AssetRenderSettings(
                        adapter=RenderAdapter.PDF,
                        dpi=dpi,
                        image_format="png",
                        preview_path=_display_path(preview_path, root),
                    ),
                    page_size_points=(float(page.rect.width), float(page.rect.height)),
                )
            )
    return surfaces


def _render_image_surface(
    request: AssetRequest,
    image_path: Path,
    previews_dir: Path,
    root: Path,
) -> RenderedSurface:
    image = _ensure_rgb(Image.open(image_path))
    preview_path = previews_dir / f"{_slugify(request.slide_id)}-{_slugify(image_path.stem)}-preview.png"
    image.save(preview_path)
    return RenderedSurface(
        request=request,
        source_path=image_path,
        adapter=RenderAdapter.RASTER_IMAGE,
        image=image,
        preview_path=preview_path,
        preview_label=_display_path(preview_path, root),
        source_index=1,
        render_settings=AssetRenderSettings(
            adapter=RenderAdapter.RASTER_IMAGE,
            image_format="png",
            preview_path=_display_path(preview_path, root),
        ),
    )


def _render_docx_surfaces(
    request: AssetRequest,
    docx_path: Path,
    previews_dir: Path,
    root: Path,
) -> list[RenderedSurface]:
    limitations = ["DOCX layout is not rendered; the worker extracts embedded media only."]
    surfaces: list[RenderedSurface] = []
    with zipfile.ZipFile(docx_path) as archive:
        media_names = sorted(name for name in archive.namelist() if name.startswith("word/media/"))
        for source_index, media_name in enumerate(media_names, start=1):
            try:
                image = Image.open(io.BytesIO(archive.read(media_name)))
            except Exception:
                continue
            image = _ensure_rgb(image)
            preview_path = previews_dir / f"{_slugify(request.slide_id)}-{_slugify(docx_path.stem)}-m{source_index:03d}.png"
            image.save(preview_path)
            surfaces.append(
                RenderedSurface(
                    request=request,
                    source_path=docx_path,
                    adapter=RenderAdapter.DOCX,
                    image=image,
                    preview_path=preview_path,
                    preview_label=_display_path(preview_path, root),
                    source_index=source_index,
                    render_settings=AssetRenderSettings(
                        adapter=RenderAdapter.DOCX,
                        image_format="png",
                        preview_path=_display_path(preview_path, root),
                    ),
                    limitations=list(limitations),
                )
            )
    return surfaces


def _render_surfaces_for_ref(
    request: AssetRequest,
    source_ref: SourceMaterialRef,
    previews_dir: Path,
    dpi: int,
    root: Path,
) -> tuple[list[RenderedSurface], list[str]]:
    source_path_text = source_ref.path or request.preferred_source_doc
    if not source_path_text:
        return [], [f"{request.request_id}: source reference {source_ref.source_id} has no usable file path."]
    source_path = _resolve_source_path(source_path_text, root)
    if not source_path.is_file():
        return [], [f"{request.request_id}: source file not found at {source_path}."]
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return _render_pdf_surfaces(request, source_ref, source_path, previews_dir, dpi, root), []
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return [_render_image_surface(request, source_path, previews_dir, root)], []
    if suffix == ".docx":
        surfaces = _render_docx_surfaces(request, source_path, previews_dir, root)
        if surfaces:
            return surfaces, []
        return [], [f"{request.request_id}: DOCX file {source_path} had no embedded images to extract."]
    return [], [f"{request.request_id}: unsupported source type {suffix or '<none>'} for {source_path.name}."]


def _analysis_image(image: Image.Image) -> tuple[Image.Image, float, float]:
    analysis = image.copy()
    analysis.thumbnail((384, 384))
    scale_x = image.width / analysis.width
    scale_y = image.height / analysis.height
    return analysis, scale_x, scale_y


def _projection_segments(counts: list[int], threshold: int, min_span: int) -> list[tuple[int, int, int]]:
    segments: list[tuple[int, int, int]] = []
    start: int | None = None
    for index, value in enumerate(counts):
        if value >= threshold:
            if start is None:
                start = index
        elif start is not None:
            if index - start >= min_span:
                segments.append((start, index, sum(counts[start:index])))
            start = None
    if start is not None and len(counts) - start >= min_span:
        segments.append((start, len(counts), sum(counts[start:])))
    segments.sort(key=lambda row: row[2], reverse=True)
    return segments


def _pad_box(left: int, top: int, right: int, bottom: int, width: int, height: int) -> tuple[int, int, int, int]:
    pad_x = max(4, int((right - left) * 0.03))
    pad_y = max(4, int((bottom - top) * 0.03))
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(width, right + pad_x),
        min(height, bottom + pad_y),
    )


def _iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    left = max(box_a[0], box_b[0])
    top = max(box_a[1], box_b[1])
    right = min(box_a[2], box_b[2])
    bottom = min(box_a[3], box_b[3])
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    return intersection / float(area_a + area_b - intersection)


def _score_box(gray: Image.Image, box: tuple[int, int, int, int]) -> float:
    pixels = gray.load()
    width, height = gray.size
    left, top, right, bottom = box
    area = max(1, (right - left) * (bottom - top))
    foreground = 0
    for y in range(top, bottom):
        for x in range(left, right):
            if pixels[x, y] < 245:
                foreground += 1
    density = foreground / area
    coverage = area / float(width * height)
    density_score = min(1.0, density / 0.35)
    coverage_score = max(0.0, 1.0 - min(abs(coverage - 0.28) / 0.28, 1.0))
    aspect = (right - left) / max(1.0, float(bottom - top))
    aspect_score = max(0.0, 1.0 - min(abs(aspect - 1.4) / 1.4, 1.0))
    border_penalty = 0.08 if left == 0 or top == 0 or right == width or bottom == height else 0.0
    return round(max(0.0, 0.5 * density_score + 0.35 * coverage_score + 0.15 * aspect_score - border_penalty), 4)


def _candidate_rationale(box: tuple[int, int, int, int], gray: Image.Image) -> list[str]:
    score = _score_box(gray, box)
    rationale = [f"Foreground-density score {score:.2f} from deterministic page analysis."]
    if box[0] == 0 or box[1] == 0 or box[2] == gray.width or box[3] == gray.height:
        rationale.append("Touches a page edge and may include surrounding page furniture.")
    else:
        rationale.append("Keeps away from the outer page edge to reduce page furniture.")
    return rationale


def _generate_candidate_boxes(image: Image.Image, max_candidates: int) -> list[tuple[CropBounds, float, list[str]]]:
    analysis, scale_x, scale_y = _analysis_image(image)
    gray = analysis.convert("L")
    pixels = gray.load()
    width, height = gray.size
    row_counts = [0] * height
    col_counts = [0] * width
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    for y in range(height):
        for x in range(width):
            if pixels[x, y] < 245:
                row_counts[y] += 1
                col_counts[x] += 1
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if max_x < 0 or max_y < 0:
        return [(_tuple_to_crop_bounds(0, 0, image.width, image.height), 0.1, ["No foreground detected; falling back to the full image."])]

    content_box = _pad_box(min_x, min_y, max_x + 1, max_y + 1, width, height)
    candidate_boxes: list[tuple[int, int, int, int]] = [content_box]
    row_segments = _projection_segments(row_counts, max(3, int(width * 0.03)), max(8, height // 24))
    col_segments = _projection_segments(col_counts, max(3, int(height * 0.03)), max(8, width // 24))

    for start, end, _mass in row_segments[:3]:
        candidate_boxes.append(_pad_box(content_box[0], start, content_box[2], end, width, height))
    for start, end, _mass in col_segments[:3]:
        candidate_boxes.append(_pad_box(start, content_box[1], end, content_box[3], width, height))
    for row_start, row_end, _row_mass in row_segments[:3]:
        for col_start, col_end, _col_mass in col_segments[:3]:
            candidate_boxes.append(_pad_box(col_start, row_start, col_end, row_end, width, height))

    if len(candidate_boxes) < 4:
        mid_x = (content_box[0] + content_box[2]) // 2
        mid_y = (content_box[1] + content_box[3]) // 2
        candidate_boxes.extend(
            [
                _pad_box(content_box[0], content_box[1], mid_x, content_box[3], width, height),
                _pad_box(mid_x, content_box[1], content_box[2], content_box[3], width, height),
                _pad_box(content_box[0], content_box[1], content_box[2], mid_y, width, height),
                _pad_box(content_box[0], mid_y, content_box[2], content_box[3], width, height),
            ]
        )

    unique_boxes: list[tuple[int, int, int, int]] = []
    for candidate in candidate_boxes:
        left, top, right, bottom = candidate
        if right - left < 12 or bottom - top < 12:
            continue
        if any(_iou(candidate, existing) > 0.9 for existing in unique_boxes):
            continue
        unique_boxes.append(candidate)

    scored: list[tuple[CropBounds, float, list[str]]] = []
    for box in unique_boxes:
        scaled_box = _tuple_to_crop_bounds(
            left=int(round(box[0] * scale_x)),
            top=int(round(box[1] * scale_y)),
            right=int(round(box[2] * scale_x)),
            bottom=int(round(box[3] * scale_y)),
        )
        scored.append((scaled_box, _score_box(gray, box), _candidate_rationale(box, gray)))
    scored.sort(key=lambda row: row[1], reverse=True)
    return scored[:max_candidates]


def _score_crop_bounds(image: Image.Image, crop_box: CropBounds) -> float:
    analysis, scale_x, scale_y = _analysis_image(image)
    scaled_box = (
        int(round(crop_box.left / scale_x)),
        int(round(crop_box.top / scale_y)),
        int(round((crop_box.left + crop_box.width) / scale_x)),
        int(round((crop_box.top + crop_box.height) / scale_y)),
    )
    return _score_box(analysis.convert("L"), scaled_box)


def _save_candidate_crop(surface: RenderedSurface, candidate_id: str, crop_box: CropBounds, candidates_dir: Path) -> Path:
    left, top, right, bottom = _candidate_box_to_tuple(crop_box)
    candidate_path = candidates_dir / f"{candidate_id}.png"
    surface.image.crop((left, top, right, bottom)).save(candidate_path)
    return candidate_path


def _render_pdf_clip(surface: RenderedSurface, crop_box: CropBounds, output_path: Path) -> None:
    if surface.page_number is None or surface.page_size_points is None or surface.render_settings.dpi is None:
        raise ValueError("pdf clip rendering requires a page_number, page_size_points, and dpi")
    page_width_points, page_height_points = surface.page_size_points
    scale_x = surface.image.width / page_width_points
    scale_y = surface.image.height / page_height_points
    with fitz.open(surface.source_path) as document:
        page = document.load_page(surface.page_number - 1)
        clip = fitz.Rect(
            crop_box.left / scale_x,
            crop_box.top / scale_y,
            (crop_box.left + crop_box.width) / scale_x,
            (crop_box.top + crop_box.height) / scale_y,
        )
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(surface.render_settings.dpi / 72.0, surface.render_settings.dpi / 72.0),
            clip=clip,
            alpha=False,
        )
        output_path.write_bytes(pixmap.tobytes("png"))


def _save_selected_asset(surface: RenderedSurface, crop_box: CropBounds, asset_path: Path) -> None:
    if surface.adapter == RenderAdapter.PDF:
        _render_pdf_clip(surface, crop_box, asset_path)
        return
    left, top, right, bottom = _candidate_box_to_tuple(crop_box)
    surface.image.crop((left, top, right, bottom)).save(asset_path)


def _source_preview(surface: RenderedSurface) -> SourcePreview:
    return SourcePreview(
        preview_id=f"preview-{surface.request.slide_id}-{_slugify(surface.source_path.stem)}-{surface.page_number or surface.source_index or 1:03d}",
        request_id=surface.request.request_id,
        slide_id=surface.request.slide_id,
        source_file=str(surface.source_path),
        adapter=surface.adapter,
        page_number=surface.page_number,
        source_index=surface.source_index,
        preview_path=surface.preview_label,
        render_settings=surface.render_settings,
        limitations=list(surface.limitations),
    )


def _candidate_provenance(surface: RenderedSurface, candidate_id: str, crop_box: CropBounds) -> AssetProvenance:
    return AssetProvenance(
        source_file=str(surface.source_path),
        slide_id=surface.request.slide_id,
        page_number=surface.page_number,
        source_index=surface.source_index,
        candidate_id=candidate_id,
        render_settings=surface.render_settings,
        crop_box=crop_box,
        limitations=list(surface.limitations),
    )


def _candidate_surface_key(candidate: CropCandidate) -> tuple[str, int | None, int | None]:
    try:
        return (str(Path(candidate.source_file).resolve()), candidate.page_number, candidate.source_index)
    except Exception:
        return (candidate.source_file, candidate.page_number, candidate.source_index)


def _candidate_surface_lookup_key(candidate: CropCandidate, root: Path) -> tuple[str, int | None, int | None]:
    return str(_resolve_source_path(candidate.source_file, root)), candidate.page_number, candidate.source_index


def _normalize_max_review_rounds(max_review_rounds: int) -> int:
    if max_review_rounds < MAX_REVIEW_ROUNDS_LOWER_BOUND or max_review_rounds > MAX_REVIEW_ROUNDS_UPPER_BOUND:
        raise ValueError(
            f"max_review_rounds must stay within the bounded range of {MAX_REVIEW_ROUNDS_LOWER_BOUND} to "
            f"{MAX_REVIEW_ROUNDS_UPPER_BOUND}"
        )
    return max_review_rounds


def _is_crop_request(request: AssetRequest) -> bool:
    return request.asset_kind in {AssetKind.DOCUMENT_CROP, AssetKind.IMAGE} or request.production_mode == ProductionMode.SOURCE_REUSE


def _validate_crop_review_lineage(
    request: AssetRequest,
    request_candidates: list[CropCandidate],
    manifest_asset: AssetRecord | None,
    slide_entry: SlideLedgerEntry | None,
    root: Path,
) -> list[CropLineageValidationIssue]:
    issues: list[CropLineageValidationIssue] = []

    if not request.request_id:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.MISSING_REQUEST_ID,
                request=request,
                message="The asset request is missing request_id.",
                manifest_asset=manifest_asset,
            )
        )
    if not request.slide_id:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.MISSING_SLIDE_ID,
                request=request,
                message="The asset request is missing slide_id.",
                manifest_asset=manifest_asset,
            )
        )

    if slide_entry is None:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.MISSING_SLIDE_ID,
                request=request,
                message="The slide ledger does not contain the request slide_id and slide_number.",
                manifest_asset=manifest_asset,
            )
        )
    else:
        if slide_entry.slide_id != request.slide_id or slide_entry.slide_number != request.slide_number:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                    request=request,
                    message="The slide ledger entry does not match the request slide linkage.",
                    manifest_asset=manifest_asset,
                )
            )
        if request.request_id and slide_entry.asset_request_ids and request.request_id not in slide_entry.asset_request_ids:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                    request=request,
                    message="The authoritative slide ledger entry does not list the request_id for this slide.",
                    manifest_asset=manifest_asset,
                )
            )

    candidate_ids: set[str] = set()
    candidates_by_id: dict[str, CropCandidate] = {}
    for candidate in request_candidates:
        candidate_ids.add(candidate.candidate_id)
        candidates_by_id[candidate.candidate_id] = candidate

        if candidate.request_id != request.request_id:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                    request=request,
                    message="The candidate request_id does not match the asset request.",
                    candidate=candidate,
                    manifest_asset=manifest_asset,
                )
            )
        if candidate.slide_id != request.slide_id:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                    request=request,
                    message="The candidate slide_id does not match the asset request.",
                    candidate=candidate,
                    manifest_asset=manifest_asset,
                )
            )
        if candidate.slide_number != request.slide_number:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                    request=request,
                    message="The candidate slide_number does not match the authoritative request slide number.",
                    candidate=candidate,
                    manifest_asset=manifest_asset,
                )
            )

        if not _artifact_file_exists(candidate.candidate_path, root):
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.ARTIFACT_FILE_MISSING,
                    request=request,
                    message="The candidate crop artifact is missing from disk.",
                    candidate=candidate,
                    manifest_asset=manifest_asset,
                    manifest_asset_path=candidate.candidate_path,
                )
            )
        if not _artifact_file_exists(candidate.source_file, root):
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.ARTIFACT_FILE_MISSING,
                    request=request,
                    message="The candidate source artifact is missing from disk.",
                    candidate=candidate,
                    manifest_asset=manifest_asset,
                    manifest_asset_path=candidate.source_file,
                )
            )

        if candidate.provenance is not None:
            if candidate.provenance.candidate_id is not None and candidate.provenance.candidate_id != candidate.candidate_id:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                        request=request,
                        message="The candidate provenance candidate_id does not match the candidate record.",
                        candidate=candidate,
                        manifest_asset=manifest_asset,
                    )
                )
            if candidate.provenance.source_file != candidate.source_file:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                        request=request,
                        message="The candidate provenance source_file does not match the candidate record.",
                        candidate=candidate,
                        manifest_asset=manifest_asset,
                    )
                )
            if candidate.provenance.slide_id != request.slide_id:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                        request=request,
                        message="The candidate provenance slide_id does not match the authoritative request slide_id.",
                        candidate=candidate,
                        manifest_asset=manifest_asset,
                    )
                )
            if candidate.provenance.page_number != candidate.page_number:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                        request=request,
                        message="The candidate provenance page_number does not match the candidate record.",
                        candidate=candidate,
                        manifest_asset=manifest_asset,
                    )
                )
            if candidate.provenance.source_index != candidate.source_index:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                        request=request,
                        message="The candidate provenance source_index does not match the candidate record.",
                        candidate=candidate,
                        manifest_asset=manifest_asset,
                    )
                )
            if candidate.provenance.render_settings != candidate.render_settings:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                        request=request,
                        message="The candidate provenance render settings do not match the candidate record.",
                        candidate=candidate,
                        manifest_asset=manifest_asset,
                    )
                )
            if candidate.provenance.crop_box != candidate.crop_box:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                        request=request,
                        message="The candidate provenance crop box does not match the candidate record.",
                        candidate=candidate,
                        manifest_asset=manifest_asset,
                    )
                )

    if not request_candidates:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.CANDIDATE_NOT_FOUND_FOR_REQUEST,
                request=request,
                message="No candidate pool exists for the request_id under review.",
                manifest_asset=manifest_asset,
            )
        )

    if manifest_asset is None:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.MANIFEST_ASSET_MISSING,
                request=request,
                message="The asset manifest is missing the request asset expected for crop review.",
            )
        )
        return issues

    if manifest_asset.request_id != request.request_id or manifest_asset.slide_id != request.slide_id or manifest_asset.slide_number != request.slide_number:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                request=request,
                message="The manifest asset does not match the request request_id, slide_id, and slide_number linkage.",
                manifest_asset=manifest_asset,
            )
        )
    if manifest_asset.asset_kind != request.asset_kind:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                request=request,
                message="The manifest asset_kind does not match the request asset_kind.",
                manifest_asset=manifest_asset,
            )
        )

    if manifest_asset.status == AssetStatus.PENDING_REVIEW:
        if not manifest_asset.candidate_id:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                    request=request,
                    message="The pending-review manifest asset is missing candidate_id.",
                    manifest_asset=manifest_asset,
                )
            )
        elif manifest_asset.candidate_id not in candidate_ids:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.CANDIDATE_NOT_FOUND_FOR_REQUEST,
                    request=request,
                    message="The manifest asset candidate_id does not resolve inside the request candidate pool.",
                    manifest_asset=manifest_asset,
                )
            )
        else:
            selected_candidate = candidates_by_id[manifest_asset.candidate_id]
            if manifest_asset.local_path != selected_candidate.candidate_path:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                        request=request,
                        message="The pending-review manifest asset local_path does not match the candidate artifact path.",
                        candidate=selected_candidate,
                        manifest_asset=manifest_asset,
                    )
                )
        if manifest_asset.local_path and not _artifact_file_exists(manifest_asset.local_path, root):
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.ARTIFACT_FILE_MISSING,
                    request=request,
                    message="The manifest asset local_path points to a missing artifact file.",
                    manifest_asset=manifest_asset,
                )
            )

    elif manifest_asset.status in {AssetStatus.READY, AssetStatus.REJECTED, AssetStatus.APPROVED}:
        if not manifest_asset.candidate_id:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                    request=request,
                    message="The manifest asset is missing candidate_id for a finalized crop record.",
                    manifest_asset=manifest_asset,
                )
            )
        elif manifest_asset.candidate_id not in candidate_ids:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.CANDIDATE_NOT_FOUND_FOR_REQUEST,
                    request=request,
                    message="The finalized manifest asset candidate_id does not resolve inside the request candidate pool.",
                    manifest_asset=manifest_asset,
                )
            )
        else:
            selected_candidate = candidates_by_id[manifest_asset.candidate_id]
            if manifest_asset.provenance is not None:
                if manifest_asset.provenance.slide_id != request.slide_id:
                    issues.append(
                        _lineage_issue(
                            CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                            request=request,
                            message="The manifest provenance slide_id does not match the authoritative request slide_id.",
                            candidate=selected_candidate,
                            manifest_asset=manifest_asset,
                        )
                    )
                if manifest_asset.provenance.candidate_id is not None and manifest_asset.provenance.candidate_id != manifest_asset.candidate_id:
                    issues.append(
                        _lineage_issue(
                            CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                            request=request,
                            message="The manifest provenance candidate_id does not match the manifest record.",
                            candidate=selected_candidate,
                            manifest_asset=manifest_asset,
                        )
                    )
                if manifest_asset.provenance.source_file != selected_candidate.source_file:
                    issues.append(
                        _lineage_issue(
                            CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                            request=request,
                            message="The manifest provenance source_file does not match the selected candidate lineage.",
                            candidate=selected_candidate,
                            manifest_asset=manifest_asset,
                        )
                    )
                if manifest_asset.provenance.candidate_id and manifest_asset.provenance.candidate_id != selected_candidate.candidate_id:
                    issues.append(
                        _lineage_issue(
                            CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                            request=request,
                            message="The manifest provenance candidate_id does not match the selected candidate lineage.",
                            candidate=selected_candidate,
                            manifest_asset=manifest_asset,
                        )
                    )
            if manifest_asset.status in {AssetStatus.READY, AssetStatus.APPROVED} and request.asset_kind == AssetKind.DOCUMENT_CROP and manifest_asset.review_action != CropReviewAction.ACCEPT:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                        request=request,
                        message="The finalized document-crop manifest asset is not marked as an accepted crop.",
                        candidate=selected_candidate,
                        manifest_asset=manifest_asset,
                    )
                )
            if not manifest_asset.local_path:
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                        request=request,
                        message="The finalized manifest asset is missing local_path for compile-ready promotion.",
                        candidate=selected_candidate,
                        manifest_asset=manifest_asset,
                    )
                )
            elif not _artifact_file_exists(manifest_asset.local_path, root):
                issues.append(
                    _lineage_issue(
                        CropReviewReasonCode.ARTIFACT_FILE_MISSING,
                        request=request,
                        message="The finalized manifest asset local_path points to a missing artifact file.",
                        candidate=selected_candidate,
                        manifest_asset=manifest_asset,
                    )
                )

    else:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The manifest asset status is not valid for pending review or compile-ready crop promotion.",
                manifest_asset=manifest_asset,
            )
        )

    return issues


def _review_input_for_candidate(
    request: AssetRequest,
    current_candidate: CropCandidate,
    candidates: list[CropCandidate],
    iteration: int,
    configured_max_review_rounds: int,
    manifest_asset_id: str | None,
) -> CropReviewInput:
    return CropReviewInput(
        input_id=f"review-input-{request.slide_id}-{iteration:02d}",
        request_id=request.request_id,
        slide_id=request.slide_id,
        slide_number=request.slide_number,
        iteration=iteration,
        page_preview_path=current_candidate.preview_path,
        source_file=current_candidate.source_file,
        current_candidate_id=current_candidate.candidate_id,
        slide_intent=request.slide_message,
        crop_subject_hint=request.crop_subject_hint,
        visual_type_expectation=request.required_visual_type,
        request_priority=request.priority,
        asset_quality_requirements=list(request.asset_quality_requirements),
        fallback_ladder=list(request.fallback_ladder),
        source_material_refs=list(request.source_material_refs),
        configured_max_review_rounds=configured_max_review_rounds,
        review_rounds_used=iteration,
        manifest_asset_id=manifest_asset_id,
        candidates=candidates,
    )


def _build_review_validation_failure(
    request: AssetRequest,
    asset_record: AssetRecord,
    request_candidates: list[CropCandidate],
    note: str,
    *,
    issues: list[CropLineageValidationIssue] | None = None,
    configured_max_review_rounds: int = 2,
    review_rounds_used: int = 0,
) -> RequestExecutionResult:
    normalized_reason_codes = _lineage_issue_codes(issues or [])
    reason = normalized_reason_codes[0] if normalized_reason_codes else note
    decision = CropReviewDecision(
        decision_id=f"review-decision-{request.slide_id}-validation",
        input_id=f"review-input-{request.slide_id}-00",
        request_id=request.request_id,
        slide_id=request.slide_id,
        slide_number=request.slide_number,
        iteration=0,
        reviewer_name="crop-review-validator",
        action="reject",
        current_candidate_id=request_candidates[0].candidate_id if request_candidates else asset_record.candidate_id or "",
        applied_candidate_id=None,
        rationale=note,
        terminal=True,
        configured_max_review_rounds=configured_max_review_rounds,
        review_rounds_used=review_rounds_used,
        failure_reason=reason,
        selection_reason_codes=normalized_reason_codes,
        stopped_without_fallback=True,
        fallback_applied=False,
        termination_reason=reason,
        manifest_asset_id=asset_record.asset_id if asset_record.asset_id else None,
        manifest_asset_path=asset_record.local_path,
    )
    return RequestExecutionResult(
        request=request,
        candidates=request_candidates,
        asset_record=asset_record,
        selected_crop=None,
        review_inputs=[],
        review_decisions=[decision],
        limitations=_dedupe_text(asset_record.limitations or [note]),
        ledger_status=StageStatus.BLOCKED,
        production_readiness=StageStatus.BLOCKED,
        blockers=[note],
        change_note=note,
    )


def _refine_crop_box(action_kind: str, crop_box: CropBounds, surface: RenderedSurface) -> CropBounds:
    width = surface.image.width
    height = surface.image.height
    left = crop_box.left
    top = crop_box.top
    right = crop_box.left + crop_box.width
    bottom = crop_box.top + crop_box.height
    step_x = max(12.0, crop_box.width * 0.08)
    step_y = max(12.0, crop_box.height * 0.08)
    if action_kind == "expand_top":
        top = max(0.0, top - step_y)
    elif action_kind == "expand_bottom":
        bottom = min(float(height), bottom + step_y)
    elif action_kind == "expand_left":
        left = max(0.0, left - step_x)
    elif action_kind == "expand_right":
        right = min(float(width), right + step_x)
    elif action_kind == "tighten":
        left = min(right - 24.0, left + step_x * 0.6)
        right = max(left + 24.0, right - step_x * 0.6)
        top = min(bottom - 24.0, top + step_y * 0.6)
        bottom = max(top + 24.0, bottom - step_y * 0.6)
    elif action_kind == "exclude_caption_band":
        bottom = max(top + 24.0, bottom - max(18.0, crop_box.height * 0.14))
    else:
        raise ValueError(f"unsupported refinement action {action_kind!r}")
    return CropBounds(left=left, top=top, width=max(24.0, right - left), height=max(24.0, bottom - top))


def _create_refined_candidate(
    base_candidate: CropCandidate,
    action_kind: str,
    surface: RenderedSurface,
    candidates_dir: Path,
    root: Path,
) -> CropCandidate:
    refined_box = _refine_crop_box(action_kind, base_candidate.crop_box, surface)
    candidate_id = f"{base_candidate.candidate_id}-{action_kind}"
    candidate_path = _save_candidate_crop(surface, candidate_id, refined_box, candidates_dir)
    rationale = list(base_candidate.rationale)
    rationale.append(f"Applied bounded refinement action {action_kind}.")
    return CropCandidate(
        candidate_id=candidate_id,
        request_id=base_candidate.request_id,
        slide_id=base_candidate.slide_id,
        slide_number=base_candidate.slide_number,
        source_file=base_candidate.source_file,
        adapter=base_candidate.adapter,
        page_number=base_candidate.page_number,
        source_index=base_candidate.source_index,
        preview_path=base_candidate.preview_path,
        candidate_path=_display_path(candidate_path, root),
        crop_box=refined_box,
        score=_score_crop_bounds(surface.image, refined_box),
        selection_rank=base_candidate.selection_rank,
        rationale=rationale,
        render_settings=base_candidate.render_settings,
        provenance=_candidate_provenance(surface, candidate_id, refined_box),
        limitations=list(base_candidate.limitations),
    )


def _failure_asset_record(
    request: AssetRequest,
    local_path: str,
    source_file: str,
    limitations: list[str],
    review_action: CropReviewAction | None = None,
    *,
    failure_reason_codes: list[str] | None = None,
    notes: str | None = None,
    candidate_id: str | None = None,
    provenance: AssetProvenance | None = None,
) -> AssetRecord:
    normalized_reason_codes = _reason_codes(*(failure_reason_codes or []))
    record_slide_id = request.slide_id or (provenance.slide_id if provenance is not None else None)
    record_provenance = None
    if request.asset_kind == AssetKind.DOCUMENT_CROP and record_slide_id is not None:
        if provenance is not None:
            record_provenance = provenance.model_copy(
                update={
                    "slide_id": record_slide_id,
                    "candidate_id": candidate_id if candidate_id is not None else provenance.candidate_id,
                    "limitations": limitations,
                }
            )
        else:
            record_provenance = AssetProvenance(
                source_file=source_file,
                slide_id=record_slide_id,
                page_number=request.page_hint,
                candidate_id=candidate_id,
                limitations=limitations,
            )
    return AssetRecord(
        asset_id=f"asset-{request.slide_id}-rejected",
        request_id=request.request_id,
        slide_number=request.slide_number,
        slide_id=record_slide_id,
        asset_kind=request.asset_kind,
        status=AssetStatus.REJECTED,
        local_path=local_path,
        visual_source_preference=request.visual_source_preference,
        source_material_refs=request.source_material_refs,
        crop_subject_hint=request.crop_subject_hint,
        fallback_visual=request.fallback_visual,
        production_mode=request.production_mode,
        review_action=review_action,
        candidate_id=candidate_id,
        provenance=record_provenance,
        failure_reason_codes=normalized_reason_codes or None,
        limitations=limitations,
        notes=notes or "; ".join(limitations) if limitations else None,
    )


def _full_surface_bounds(surface: RenderedSurface) -> CropBounds:
    return CropBounds(left=0.0, top=0.0, width=float(surface.image.width), height=float(surface.image.height))


def _build_direct_candidate(
    request: AssetRequest,
    surface: RenderedSurface,
    candidates_dir: Path,
    root: Path,
) -> CropCandidate:
    crop_box = _full_surface_bounds(surface)
    candidate_id = (
        f"cand-{request.slide_id}-"
        f"{_slugify(surface.source_path.stem)}-"
        f"{surface.page_number or surface.source_index or 1:03d}-direct"
    )
    candidate_path = _save_candidate_crop(surface, candidate_id, crop_box, candidates_dir)
    limitations = list(surface.limitations)
    rationale = ["Direct normalization retained the full local source asset without a review loop."]
    return CropCandidate(
        candidate_id=candidate_id,
        request_id=request.request_id,
        slide_id=request.slide_id,
        slide_number=request.slide_number,
        source_file=str(surface.source_path),
        adapter=surface.adapter,
        page_number=surface.page_number,
        source_index=surface.source_index,
        preview_path=surface.preview_label,
        candidate_path=_display_path(candidate_path, root),
        crop_box=crop_box,
        score=1.0,
        selection_rank=1,
        rationale=rationale,
        render_settings=surface.render_settings,
        provenance=_candidate_provenance(surface, candidate_id, crop_box),
        limitations=limitations,
    )


def _generate_request_candidates(
    request: AssetRequest,
    surfaces: list[RenderedSurface],
    candidates_dir: Path,
    max_candidates_per_source: int,
    root: Path,
) -> list[CropCandidate]:
    candidate_records: list[CropCandidate] = []
    for surface in surfaces:
        for selection_rank, (crop_box, score, rationale) in enumerate(_generate_candidate_boxes(surface.image, max_candidates_per_source), start=1):
            candidate_id = (
                f"cand-{request.slide_id}-"
                f"{_slugify(surface.source_path.stem)}-"
                f"{surface.page_number or surface.source_index or 1:03d}-"
                f"{selection_rank:02d}"
            )
            candidate_path = _save_candidate_crop(surface, candidate_id, crop_box, candidates_dir)
            candidate_records.append(
                CropCandidate(
                    candidate_id=candidate_id,
                    request_id=request.request_id,
                    slide_id=request.slide_id,
                    slide_number=request.slide_number,
                    source_file=str(surface.source_path),
                    adapter=surface.adapter,
                    page_number=surface.page_number,
                    source_index=surface.source_index,
                    preview_path=surface.preview_label,
                    candidate_path=_display_path(candidate_path, root),
                    crop_box=crop_box,
                    score=score,
                    selection_rank=selection_rank,
                    rationale=rationale,
                    render_settings=surface.render_settings,
                    provenance=_candidate_provenance(surface, candidate_id, crop_box),
                    limitations=list(surface.limitations),
                )
            )
    candidate_records.sort(key=lambda row: row.score, reverse=True)
    for rank, candidate in enumerate(candidate_records, start=1):
        candidate.selection_rank = rank
    return candidate_records


def _finalize_selected_candidate(
    request: AssetRequest,
    chosen: CropCandidate,
    chosen_surface: RenderedSurface,
    assets_dir: Path,
    root: Path,
    selection_method: str,
    notes: str,
) -> tuple[SelectedCrop, AssetRecord]:
    asset_path = assets_dir / f"asset-{request.slide_id}.png"
    _save_selected_asset(chosen_surface, chosen.crop_box, asset_path)
    selected = SelectedCrop(
        selection_id=f"selected-{request.slide_id}",
        candidate_id=chosen.candidate_id,
        request_id=request.request_id,
        slide_id=request.slide_id,
        slide_number=request.slide_number,
        asset_id=f"asset-{request.slide_id}-v1",
        output_path=_display_path(asset_path, root),
        status=AssetStatus.READY,
        review_action=CropReviewAction.ACCEPT,
        selection_method=selection_method,
        provenance=chosen.provenance,
        limitations=list(chosen.limitations),
    )
    asset_record = AssetRecord(
        asset_id=selected.asset_id,
        request_id=request.request_id,
        slide_number=request.slide_number,
        slide_id=request.slide_id,
        asset_kind=request.asset_kind,
        status=AssetStatus.READY,
        local_path=selected.output_path,
        visual_source_preference=request.visual_source_preference,
        source_material_refs=request.source_material_refs,
        crop_subject_hint=request.crop_subject_hint,
        fallback_visual=request.fallback_visual,
        production_mode=request.production_mode,
        review_action=selected.review_action if request.asset_kind == AssetKind.DOCUMENT_CROP else None,
        crop_bounds=chosen.crop_box,
        candidate_id=chosen.candidate_id,
        render_settings=chosen.render_settings,
        provenance=chosen.provenance,
        limitations=list(chosen.limitations),
        notes=notes,
    )
    return selected, asset_record


def _candidate_ready_asset_record(
    request: AssetRequest,
    candidate: CropCandidate,
    *,
    notes: str,
    limitations: list[str],
) -> AssetRecord:
    return AssetRecord(
        asset_id=f"asset-{request.slide_id}-candidate",
        request_id=request.request_id,
        slide_number=request.slide_number,
        slide_id=request.slide_id,
        asset_kind=request.asset_kind,
        status=AssetStatus.PENDING_REVIEW,
        local_path=candidate.candidate_path,
        visual_source_preference=request.visual_source_preference,
        source_material_refs=request.source_material_refs,
        crop_subject_hint=request.crop_subject_hint,
        fallback_visual=request.fallback_visual,
        production_mode=request.production_mode,
        review_action=CropReviewAction.REVISE if request.asset_kind == AssetKind.DOCUMENT_CROP else None,
        crop_bounds=candidate.crop_box,
        candidate_id=candidate.candidate_id,
        render_settings=candidate.render_settings,
        provenance=candidate.provenance,
        limitations=limitations,
        notes=notes,
    )


def _validate_selected_crop_promotion(
    request: AssetRequest,
    candidate: CropCandidate,
    selected: SelectedCrop,
    asset_record: AssetRecord,
    root: Path,
) -> list[CropLineageValidationIssue]:
    issues: list[CropLineageValidationIssue] = []

    if selected.request_id != request.request_id or selected.slide_id != request.slide_id or selected.slide_number != request.slide_number:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The selected crop record does not match the authoritative request slide linkage.",
                candidate=candidate,
                manifest_asset=asset_record,
                manifest_asset_path=selected.output_path,
            )
        )
    if selected.candidate_id != candidate.candidate_id:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                request=request,
                message="The selected crop candidate_id does not match the promoted candidate.",
                candidate=candidate,
                manifest_asset=asset_record,
                manifest_asset_path=selected.output_path,
            )
        )
    if selected.provenance.slide_id != request.slide_id or selected.provenance.candidate_id != candidate.candidate_id or selected.provenance.source_file != candidate.source_file:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                request=request,
                message="The selected crop provenance does not match the promoted candidate lineage.",
                candidate=candidate,
                manifest_asset=asset_record,
                manifest_asset_path=selected.output_path,
            )
        )
    if selected.status != AssetStatus.READY or selected.review_action != CropReviewAction.ACCEPT:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The selected crop is not marked compile-ready with an accepted review action.",
                candidate=candidate,
                manifest_asset=asset_record,
                manifest_asset_path=selected.output_path,
            )
        )
    if not selected.output_path:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The selected crop is missing output_path for compile-ready promotion.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    elif not _artifact_file_exists(selected.output_path, root):
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.ARTIFACT_FILE_MISSING,
                request=request,
                message="The selected crop output_path points to a missing artifact file.",
                candidate=candidate,
                manifest_asset=asset_record,
                manifest_asset_path=selected.output_path,
            )
        )

    if asset_record.status != AssetStatus.READY:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The manifest asset is not marked READY after crop promotion.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    if request.asset_kind == AssetKind.DOCUMENT_CROP and asset_record.review_action != CropReviewAction.ACCEPT:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The promoted document-crop manifest asset is not marked with ACCEPT review_action.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    if asset_record.request_id != request.request_id or asset_record.slide_id != request.slide_id or asset_record.slide_number != request.slide_number:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                request=request,
                message="The promoted manifest asset does not match the request linkage.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    if asset_record.candidate_id != candidate.candidate_id:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.CANDIDATE_LINEAGE_MISMATCH,
                request=request,
                message="The promoted manifest asset candidate_id does not match the selected candidate lineage.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    if not asset_record.local_path:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The promoted manifest asset is missing local_path for compile-ready promotion.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    elif asset_record.local_path != selected.output_path:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The promoted manifest asset local_path does not match the selected crop output_path.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    elif not _artifact_file_exists(asset_record.local_path, root):
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.ARTIFACT_FILE_MISSING,
                request=request,
                message="The promoted manifest asset local_path points to a missing artifact file.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    if asset_record.provenance is None:
        issues.append(
            _lineage_issue(
                CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY,
                request=request,
                message="The promoted manifest asset is missing provenance for compile-ready promotion.",
                candidate=candidate,
                manifest_asset=asset_record,
            )
        )
    else:
        if asset_record.provenance.slide_id != request.slide_id or asset_record.provenance.source_file != candidate.source_file:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                    request=request,
                    message="The promoted manifest provenance does not match the selected candidate source lineage.",
                    candidate=candidate,
                    manifest_asset=asset_record,
                )
            )
        if asset_record.provenance.candidate_id != candidate.candidate_id:
            issues.append(
                _lineage_issue(
                    CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                    request=request,
                    message="The promoted manifest provenance candidate_id does not match the selected candidate.",
                    candidate=candidate,
                    manifest_asset=asset_record,
                )
            )

    return issues


def _should_directly_normalize(request: AssetRequest, surfaces: list[RenderedSurface]) -> bool:
    if len(surfaces) != 1:
        return False
    if request.visual_source_preference == VisualSourcePreference.EXISTING_ASSET:
        return True
    return request.asset_kind == AssetKind.IMAGE and surfaces[0].adapter != RenderAdapter.PDF


def _normalize_direct_asset(
    request: AssetRequest,
    surface: RenderedSurface,
    candidates_dir: Path,
    assets_dir: Path,
    root: Path,
) -> tuple[CropCandidate, SelectedCrop, AssetRecord]:
    direct_candidate = _build_direct_candidate(request, surface, candidates_dir, root)
    selected, asset_record = _finalize_selected_candidate(
        request,
        direct_candidate,
        surface,
        assets_dir,
        root,
        selection_method="direct-normalization",
        notes="Normalized an existing local source asset without a crop review loop.",
    )
    return direct_candidate, selected, asset_record


def _review_request_candidates(
    request: AssetRequest,
    candidates: list[CropCandidate],
    surfaces: list[RenderedSurface],
    candidates_dir: Path,
    assets_dir: Path,
    root: Path,
    reviewer: CropReviewer,
    manifest_asset_id: str | None,
    max_review_rounds: int,
) -> tuple[list[CropCandidate], list[CropReviewInput], list[CropReviewDecision], SelectedCrop | None, AssetRecord | None]:
    max_review_rounds = _normalize_max_review_rounds(max_review_rounds)
    review_inputs: list[CropReviewInput] = []
    review_decisions: list[CropReviewDecision] = []
    if not candidates:
        return [], review_inputs, review_decisions, None, None

    surfaces_by_key = {
        (str(surface.source_path.resolve()), surface.page_number, surface.source_index): surface
        for surface in surfaces
    }

    current_candidate = candidates[0]
    review_rounds_used = 0

    def _current_surface() -> RenderedSurface:
        key = _candidate_surface_lookup_key(current_candidate, root)
        surface = surfaces_by_key.get(key)
        if surface is None:
            surface = _rehydrate_surface_for_candidate(request, current_candidate, root)
            surfaces_by_key[key] = surface
        return surface

    def _current_input_id() -> str:
        if review_inputs:
            return review_inputs[-1].input_id
        return f"review-input-{request.slide_id}-00"

    def _mark_last_input(termination_reason: str | None) -> None:
        if review_inputs:
            review_inputs[-1].termination_reason = termination_reason

    def _append_failure(
        *,
        reason_code: CropReviewReasonCode,
        rationale: str,
        fallback_action: CropReviewAction,
        decision: CropReviewDecision | None = None,
        failure_reason: str | None = None,
        fallback_reason: str | None = None,
        selection_reason_codes: list[str] | None = None,
        local_path: str | None = None,
        source_file: str | None = None,
        candidate_id: str | None = None,
        provenance: AssetProvenance | None = None,
        notes: str | None = None,
    ) -> tuple[list[CropCandidate], list[CropReviewInput], list[CropReviewDecision], SelectedCrop | None, AssetRecord]:
        terminal_reason = fallback_reason or failure_reason or reason_code.value
        _mark_last_input(terminal_reason)
        limitation_note = fallback_reason or failure_reason or rationale
        if fallback_action == CropReviewAction.FALLBACK_TO_VISUAL and "fallback" not in limitation_note.lower():
            limitation_note = f"Fallback applied: {limitation_note}"
        reason_codes = _reason_codes(*(selection_reason_codes or [reason_code.value]))
        failure = _failure_asset_record(
            request=request,
            local_path=local_path or request.preferred_source_doc or current_candidate.candidate_path,
            source_file=source_file or current_candidate.source_file,
            limitations=[limitation_note],
            review_action=fallback_action if request.asset_kind == AssetKind.DOCUMENT_CROP else CropReviewAction.REJECT,
            failure_reason_codes=reason_codes,
            notes=notes,
            candidate_id=candidate_id if candidate_id is not None else current_candidate.candidate_id,
            provenance=provenance if provenance is not None else current_candidate.provenance,
        )
        terminal_decision = decision or CropReviewDecision(
            decision_id=f"review-decision-{request.slide_id}-terminal",
            input_id=_current_input_id(),
            request_id=request.request_id,
            slide_id=request.slide_id,
            slide_number=request.slide_number,
            iteration=review_rounds_used,
            reviewer_name=reviewer.name,
            action="reject" if fallback_action == CropReviewAction.REJECT else "fallback_to_generated_visual",
            current_candidate_id=current_candidate.candidate_id,
            rationale=rationale,
            terminal=True,
            configured_max_review_rounds=max_review_rounds,
            review_rounds_used=review_rounds_used,
        )
        terminal_decision.terminal = True
        terminal_decision.review_rounds_used = review_rounds_used
        terminal_decision.applied_candidate_id = terminal_decision.applied_candidate_id or current_candidate.candidate_id
        terminal_decision.termination_reason = terminal_reason
        terminal_decision.failure_reason = failure_reason or reason_code.value
        terminal_decision.fallback_reason = fallback_reason
        terminal_decision.selection_reason_codes = reason_codes
        terminal_decision.fallback_applied = fallback_action == CropReviewAction.FALLBACK_TO_VISUAL
        terminal_decision.stopped_without_fallback = fallback_action != CropReviewAction.FALLBACK_TO_VISUAL
        terminal_decision.manifest_asset_id = failure.asset_id if failure.asset_id else terminal_decision.manifest_asset_id
        terminal_decision.manifest_asset_path = failure.local_path
        review_decisions.append(terminal_decision)
        return candidates, review_inputs, review_decisions, None, failure

    def _append_success(
        *,
        rationale: str,
        notes: str,
        decision: CropReviewDecision | None = None,
        termination_reason: str | None = None,
        selection_reason_codes: list[str] | None = None,
    ) -> tuple[list[CropCandidate], list[CropReviewInput], list[CropReviewDecision], SelectedCrop, AssetRecord]:
        _mark_last_input(termination_reason)
        chosen_surface = _current_surface()
        selected, asset_record = _finalize_selected_candidate(
            request,
            current_candidate,
            chosen_surface,
            assets_dir,
            root,
            selection_method=f"bounded-review:{reviewer.name}",
            notes=notes,
        )
        terminal_decision = decision or CropReviewDecision(
            decision_id=f"review-decision-{request.slide_id}-final",
            input_id=_current_input_id(),
            request_id=request.request_id,
            slide_id=request.slide_id,
            slide_number=request.slide_number,
            iteration=review_rounds_used,
            reviewer_name=reviewer.name,
            action="accept",
            current_candidate_id=current_candidate.candidate_id,
            rationale=rationale,
            terminal=True,
            configured_max_review_rounds=max_review_rounds,
            review_rounds_used=review_rounds_used,
        )
        terminal_decision.terminal = True
        terminal_decision.review_rounds_used = review_rounds_used
        terminal_decision.applied_candidate_id = current_candidate.candidate_id
        terminal_decision.selected_candidate_path = selected.output_path
        terminal_decision.termination_reason = termination_reason
        terminal_decision.fallback_applied = False
        terminal_decision.stopped_without_fallback = True
        terminal_decision.failure_reason = None
        terminal_decision.fallback_reason = None
        terminal_decision.selection_reason_codes = _reason_codes(*(selection_reason_codes or ([] if termination_reason is None else [termination_reason])))
        terminal_decision.manifest_asset_id = asset_record.asset_id if asset_record.asset_id is not None else terminal_decision.manifest_asset_id
        terminal_decision.manifest_asset_path = asset_record.local_path

        promotion_issues = _validate_selected_crop_promotion(request, current_candidate, selected, asset_record, root)
        if promotion_issues:
            return _append_failure(
                reason_code=promotion_issues[0].reason_code,
                rationale=_lineage_failure_summary(promotion_issues),
                fallback_action=CropReviewAction.FALLBACK_TO_VISUAL,
                decision=terminal_decision,
                failure_reason=promotion_issues[0].reason_code.value,
                selection_reason_codes=_lineage_issue_codes(promotion_issues),
                local_path=selected.output_path,
                source_file=current_candidate.source_file,
                candidate_id=current_candidate.candidate_id,
                provenance=current_candidate.provenance,
                notes=_lineage_failure_summary(promotion_issues),
            )
        review_decisions.append(terminal_decision)
        return candidates, review_inputs, review_decisions, selected, asset_record

    if max_review_rounds == 0:
        review_inputs.append(
            _review_input_for_candidate(
                request=request,
                current_candidate=current_candidate,
                candidates=list(candidates),
                iteration=0,
                configured_max_review_rounds=max_review_rounds,
                manifest_asset_id=manifest_asset_id,
            )
        )
        if not _artifact_file_exists(current_candidate.candidate_path, root) or not _artifact_file_exists(current_candidate.source_file, root):
            return _append_failure(
                reason_code=CropReviewReasonCode.ARTIFACT_FILE_MISSING,
                rationale="The strongest candidate could not be promoted because a required artifact file is missing.",
                fallback_action=CropReviewAction.FALLBACK_TO_VISUAL,
                failure_reason=CropReviewReasonCode.ARTIFACT_FILE_MISSING.value,
                selection_reason_codes=[CropReviewReasonCode.ARTIFACT_FILE_MISSING.value],
            )
        return _append_success(
            rationale="Accepted the strongest candidate because review rounds were configured as zero.",
            notes="Accepted with a bounded review limit of zero rounds.",
            termination_reason=CropReviewReasonCode.REVIEW_ROUND_LIMIT_REACHED.value,
            selection_reason_codes=[CropReviewReasonCode.REVIEW_ROUND_LIMIT_REACHED.value],
        )

    for iteration in range(1, max_review_rounds + 1):
        review_rounds_used = iteration
        review_input = _review_input_for_candidate(
            request=request,
            current_candidate=current_candidate,
            candidates=list(candidates),
            iteration=iteration,
            configured_max_review_rounds=max_review_rounds,
            manifest_asset_id=manifest_asset_id,
        )
        review_inputs.append(review_input)
        directive = reviewer.review(review_input)
        action_kind, target_candidate_id = _parse_review_action(directive.action)
        decision = CropReviewDecision(
            decision_id=f"review-decision-{request.slide_id}-{iteration:02d}",
            input_id=review_input.input_id,
            request_id=request.request_id,
            slide_id=request.slide_id,
            slide_number=request.slide_number,
            iteration=iteration,
            reviewer_name=reviewer.name,
            action=directive.action,
            current_candidate_id=current_candidate.candidate_id,
            applied_candidate_id=None,
            rationale=directive.rationale,
            terminal=action_kind in {"accept", "reject", "fallback_to_generated_visual"},
            configured_max_review_rounds=max_review_rounds,
            review_rounds_used=review_rounds_used,
            manifest_asset_id=manifest_asset_id,
            manifest_asset_path=current_candidate.candidate_path,
            failure_reason=directive.failure_reason,
            fallback_reason=directive.fallback_reason,
        )

        if action_kind == "accept":
            decision.applied_candidate_id = current_candidate.candidate_id
            if not _artifact_file_exists(current_candidate.candidate_path, root) or not _artifact_file_exists(current_candidate.source_file, root):
                return _append_failure(
                    reason_code=CropReviewReasonCode.ARTIFACT_FILE_MISSING,
                    rationale=directive.rationale,
                    fallback_action=CropReviewAction.FALLBACK_TO_VISUAL,
                    decision=decision,
                    failure_reason=CropReviewReasonCode.ARTIFACT_FILE_MISSING.value,
                    selection_reason_codes=[CropReviewReasonCode.ARTIFACT_FILE_MISSING.value],
                )
            return _append_success(
                rationale=directive.rationale,
                notes="Accepted after bounded crop review.",
                decision=decision,
                termination_reason="accepted",
                selection_reason_codes=["accepted"],
            )

        if action_kind == "reject":
            rejection_reason = directive.failure_reason or "reviewer_rejected"
            return _append_failure(
                reason_code=CropReviewReasonCode.MANIFEST_LINEAGE_MISMATCH,
                rationale=directive.rationale,
                fallback_action=CropReviewAction.REJECT,
                decision=decision,
                failure_reason=rejection_reason,
                selection_reason_codes=[rejection_reason],
            )

        if action_kind == "fallback_to_generated_visual":
            fallback_reason = directive.fallback_reason or CropReviewReasonCode.REVIEW_ROUND_LIMIT_REACHED.value
            return _append_failure(
                reason_code=CropReviewReasonCode.REVIEW_ROUND_LIMIT_REACHED,
                rationale=directive.rationale,
                fallback_action=CropReviewAction.FALLBACK_TO_VISUAL,
                decision=decision,
                fallback_reason=fallback_reason,
                selection_reason_codes=[fallback_reason],
            )

        if action_kind == "choose_candidate":
            chosen_candidate = next((candidate for candidate in candidates if candidate.candidate_id == target_candidate_id), None)
            if chosen_candidate is None:
                return _append_failure(
                    reason_code=CropReviewReasonCode.CANDIDATE_NOT_FOUND_FOR_REQUEST,
                    rationale=directive.rationale,
                    fallback_action=CropReviewAction.FALLBACK_TO_VISUAL,
                    decision=decision,
                    failure_reason=CropReviewReasonCode.CANDIDATE_NOT_FOUND_FOR_REQUEST.value,
                    selection_reason_codes=[CropReviewReasonCode.CANDIDATE_NOT_FOUND_FOR_REQUEST.value],
                )
            current_candidate = chosen_candidate
            decision.applied_candidate_id = current_candidate.candidate_id
            review_decisions.append(decision)
            continue

        refined_surface = _current_surface()
        refined_candidate = _create_refined_candidate(
            current_candidate,
            action_kind,
            refined_surface,
            candidates_dir,
            root,
        )
        candidates = [candidate for candidate in candidates if candidate.candidate_id != current_candidate.candidate_id]
        candidates.append(refined_candidate)
        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        for rank, candidate in enumerate(candidates, start=1):
            candidate.selection_rank = rank
        current_candidate = refined_candidate
        decision.applied_candidate_id = refined_candidate.candidate_id
        decision.selected_candidate_path = refined_candidate.candidate_path
        review_decisions.append(decision)

    if not _artifact_file_exists(current_candidate.candidate_path, root) or not _artifact_file_exists(current_candidate.source_file, root):
        return _append_failure(
            reason_code=CropReviewReasonCode.ARTIFACT_FILE_MISSING,
            rationale="The final bounded review result could not be promoted into a compile-ready crop.",
            fallback_action=CropReviewAction.FALLBACK_TO_VISUAL,
            failure_reason=CropReviewReasonCode.ARTIFACT_FILE_MISSING.value,
            selection_reason_codes=[CropReviewReasonCode.ARTIFACT_FILE_MISSING.value],
        )

    return _append_success(
        rationale="Accepted the latest bounded review result because the review budget was exhausted.",
        notes="Accepted after bounded crop review exhausted its retry budget.",
        termination_reason=CropReviewReasonCode.REVIEW_ROUND_LIMIT_REACHED.value,
        selection_reason_codes=[CropReviewReasonCode.REVIEW_ROUND_LIMIT_REACHED.value],
    )


def _execute_request(
    request: AssetRequest,
    *,
    previews_dir: Path,
    candidates_dir: Path,
    assets_dir: Path,
    dpi: int,
    max_candidates_per_source: int,
    root: Path,
) -> tuple[list[SourcePreview], RequestExecutionResult]:
    request_surfaces: list[RenderedSurface] = []
    request_limitations: list[str] = []
    for source_ref in request.source_material_refs:
        surfaces, surface_limitations = _render_surfaces_for_ref(request, source_ref, previews_dir, dpi, root)
        request_surfaces.extend(surfaces)
        request_limitations.extend(surface_limitations)

    previews = [_source_preview(surface) for surface in request_surfaces]
    fallback_note = _fallback_ladder_note(request)
    if not request_surfaces:
        failure_notes = _dedupe_text(request_limitations + [fallback_note])
        fallback_source = request.preferred_source_doc or (
            request.source_material_refs[0].path if request.source_material_refs else request.slide_id
        )
        failure_record = _failure_asset_record(
            request=request,
            local_path=fallback_source,
            source_file=fallback_source,
            limitations=failure_notes,
            review_action=CropReviewAction.FALLBACK_TO_VISUAL if request.asset_kind == AssetKind.DOCUMENT_CROP else None,
            failure_reason_codes=[CropReviewReasonCode.ARTIFACT_FILE_MISSING.value],
        )
        return previews, RequestExecutionResult(
            request=request,
            candidates=[],
            asset_record=failure_record,
            selected_crop=None,
            limitations=failure_notes,
            ledger_status=StageStatus.BLOCKED,
            production_readiness=StageStatus.BLOCKED,
            blockers=failure_notes,
            change_note="Crop execution could not resolve a local source file; preserve the fallback route.",
        )

    candidate_records = _generate_request_candidates(
        request,
        request_surfaces,
        candidates_dir,
        max_candidates_per_source,
        root,
    )
    if not candidate_records:
        failure_notes = _dedupe_text(
            request_limitations
            + [f"{request.request_id}: no deterministic crop candidates could be generated."]
            + [fallback_note]
        )
        fallback_source = request.preferred_source_doc or str(request_surfaces[0].source_path)
        failure_record = _failure_asset_record(
            request=request,
            local_path=fallback_source,
            source_file=str(request_surfaces[0].source_path),
            limitations=failure_notes,
            review_action=CropReviewAction.FALLBACK_TO_VISUAL if request.asset_kind == AssetKind.DOCUMENT_CROP else None,
            failure_reason_codes=[CropReviewReasonCode.CANDIDATE_NOT_FOUND_FOR_REQUEST.value],
        )
        return previews, RequestExecutionResult(
            request=request,
            candidates=[],
            asset_record=failure_record,
            selected_crop=None,
            limitations=failure_notes,
            ledger_status=StageStatus.BLOCKED,
            production_readiness=StageStatus.BLOCKED,
            blockers=failure_notes,
            change_note="Crop execution produced no usable candidate; preserve the fallback route.",
        )

    if _should_directly_normalize(request, request_surfaces):
        direct_candidate, selected_crop, asset_record = _normalize_direct_asset(
            request,
            request_surfaces[0],
            candidates_dir,
            assets_dir,
            root,
        )
        candidate_records = [direct_candidate] + [candidate for candidate in candidate_records if candidate.candidate_id != direct_candidate.candidate_id]
        for rank, candidate in enumerate(candidate_records, start=1):
            candidate.selection_rank = rank
        direct_limitations = _dedupe_text(list(direct_candidate.limitations) + request_limitations)
        asset_record.limitations = direct_limitations
        selected_crop.limitations = direct_limitations
        selected_crop.provenance.limitations = direct_limitations
        asset_record.provenance.limitations = direct_limitations
        promotion_issues = _validate_selected_crop_promotion(request, direct_candidate, selected_crop, asset_record, root)
        if promotion_issues:
            failure_notes = _dedupe_text(
                direct_limitations
                + [issue.reason_code.value for issue in promotion_issues]
                + [_lineage_failure_summary(promotion_issues)]
                + [fallback_note]
            )
            failure_record = _failure_asset_record(
                request=request,
                local_path=selected_crop.output_path,
                source_file=direct_candidate.source_file,
                limitations=failure_notes,
                review_action=CropReviewAction.FALLBACK_TO_VISUAL if request.asset_kind == AssetKind.DOCUMENT_CROP else None,
                failure_reason_codes=_lineage_issue_codes(promotion_issues),
                notes=_lineage_failure_summary(promotion_issues),
                candidate_id=direct_candidate.candidate_id,
                provenance=direct_candidate.provenance,
            )
            return previews, RequestExecutionResult(
                request=request,
                candidates=candidate_records,
                asset_record=failure_record,
                selected_crop=None,
                limitations=failure_notes,
                ledger_status=StageStatus.BLOCKED,
                production_readiness=StageStatus.BLOCKED,
                blockers=failure_notes,
                change_note="Crop execution stopped before finalizing a compile-ready direct-normalized asset.",
            )
        return previews, RequestExecutionResult(
            request=request,
            candidates=candidate_records,
            asset_record=asset_record,
            selected_crop=selected_crop,
            limitations=direct_limitations,
            ledger_status=StageStatus.COMPLETE,
            production_readiness=StageStatus.COMPLETE,
            blockers=[],
            change_note="Crop execution normalized an existing local asset and recorded full provenance.",
        )

    chosen_candidate = candidate_records[0]
    pending_notes = _dedupe_text(
        list(chosen_candidate.limitations)
        + request_limitations
        + [f"Crop review required for slide {request.slide_number} before final compilation."]
        + [fallback_note]
    )
    notes = "Deterministic crop candidates are ready for Phase 7 review before approval."
    asset_record = _candidate_ready_asset_record(
        request,
        chosen_candidate,
        notes=f"{notes} {fallback_note}",
        limitations=pending_notes,
    )
    return previews, RequestExecutionResult(
        request=request,
        candidates=candidate_records,
        asset_record=asset_record,
        selected_crop=None,
        limitations=pending_notes,
        ledger_status=StageStatus.IN_PROGRESS,
        production_readiness=StageStatus.IN_PROGRESS,
        blockers=[f"Crop review required for slide {request.slide_number} before final compilation."],
        change_note="Crop execution generated candidate assets and preserved the fallback ladder for later review.",
    )


def _candidate_sort_key(candidate: CropCandidate) -> tuple[int, int, int, str]:
    return (candidate.slide_number, candidate.page_number or 0, candidate.selection_rank, candidate.candidate_id)


def _rehydrate_surface_for_candidate(request: AssetRequest, candidate: CropCandidate, root: Path) -> RenderedSurface:
    source_path = _resolve_source_path(candidate.source_file, root)
    preview_path = _resolve_source_path(candidate.preview_path, root)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    if candidate.adapter == RenderAdapter.PDF:
        if candidate.page_number is None:
            raise ValueError(f"pdf candidate {candidate.candidate_id} is missing page_number")
        dpi = candidate.render_settings.dpi or 144
        zoom = dpi / 72.0
        with fitz.open(source_path) as document:
            page = document.load_page(candidate.page_number - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            image = _ensure_rgb(image)
            if not preview_path.is_file():
                image.save(preview_path)
            return RenderedSurface(
                request=request,
                source_path=source_path,
                adapter=RenderAdapter.PDF,
                image=image,
                preview_path=preview_path,
                preview_label=candidate.preview_path,
                render_settings=candidate.render_settings,
                page_number=candidate.page_number,
                source_index=candidate.source_index,
                page_size_points=(float(page.rect.width), float(page.rect.height)),
                limitations=list(candidate.limitations),
            )
    if candidate.adapter == RenderAdapter.RASTER_IMAGE:
        image = _ensure_rgb(Image.open(source_path))
        if not preview_path.is_file():
            image.save(preview_path)
        return RenderedSurface(
            request=request,
            source_path=source_path,
            adapter=RenderAdapter.RASTER_IMAGE,
            image=image,
            preview_path=preview_path,
            preview_label=candidate.preview_path,
            render_settings=candidate.render_settings,
            page_number=candidate.page_number,
            source_index=candidate.source_index or 1,
            limitations=list(candidate.limitations),
        )
    if candidate.adapter == RenderAdapter.DOCX:
        with zipfile.ZipFile(source_path) as archive:
            media_names = sorted(name for name in archive.namelist() if name.startswith("word/media/"))
            source_index = candidate.source_index or 1
            if source_index < 1 or source_index > len(media_names):
                raise ValueError(f"docx candidate {candidate.candidate_id} references unknown source_index {source_index}")
            image = Image.open(io.BytesIO(archive.read(media_names[source_index - 1])))
            image = _ensure_rgb(image)
        if not preview_path.is_file():
            image.save(preview_path)
        limitations = list(candidate.limitations)
        note = "DOCX layout is not rendered; the worker extracts embedded media only."
        if note not in limitations:
            limitations.append(note)
        return RenderedSurface(
            request=request,
            source_path=source_path,
            adapter=RenderAdapter.DOCX,
            image=image,
            preview_path=preview_path,
            preview_label=candidate.preview_path,
            render_settings=candidate.render_settings,
            page_number=candidate.page_number,
            source_index=source_index,
            limitations=limitations,
        )
    raise ValueError(f"unsupported review adapter {candidate.adapter!r}")


def _surfaces_for_review(request: AssetRequest, candidates: list[CropCandidate], root: Path) -> list[RenderedSurface]:
    surfaces: dict[tuple[str, int | None, int | None], RenderedSurface] = {}
    for candidate in candidates:
        key = _candidate_surface_lookup_key(candidate, root)
        if key in surfaces:
            continue
        surfaces[key] = _rehydrate_surface_for_candidate(request, candidate, root)
    return list(surfaces.values())


def _merge_crop_candidates(
    existing: CropCandidates,
    review_results: list[RequestExecutionResult],
) -> CropCandidates:
    reviewed_ids = {result.request.request_id for result in review_results}
    merged = [candidate for candidate in existing.candidates if candidate.request_id not in reviewed_ids]
    for result in review_results:
        merged.extend(result.candidates)
    merged.sort(key=_candidate_sort_key)
    limitations = _dedupe_text(existing.limitations + [item for result in review_results for item in result.limitations])
    return CropCandidates(deck_title=existing.deck_title, previews=existing.previews, candidates=merged, limitations=limitations)


def _merge_crop_review_inputs(
    deck_title: str,
    existing: CropReviewInputs | None,
    review_results: list[RequestExecutionResult],
) -> CropReviewInputs:
    reviewed_ids = {result.request.request_id for result in review_results}
    merged = [] if existing is None else [item for item in existing.inputs if item.request_id not in reviewed_ids]
    for result in review_results:
        merged.extend(result.review_inputs)
    return CropReviewInputs(deck_title=deck_title, inputs=merged)


def _merge_crop_review_decisions(
    deck_title: str,
    existing: CropReviewDecisions | None,
    review_results: list[RequestExecutionResult],
) -> CropReviewDecisions:
    reviewed_ids = {result.request.request_id for result in review_results}
    merged = [] if existing is None else [item for item in existing.decisions if item.request_id not in reviewed_ids]
    for result in review_results:
        merged.extend(result.review_decisions)
    limitations = _dedupe_text(
        ([] if existing is None else existing.limitations) + [item for result in review_results for item in result.limitations]
    )
    return CropReviewDecisions(deck_title=deck_title, decisions=merged, limitations=limitations)


def _merge_selected_crops(
    deck_title: str,
    existing: SelectedCrops | None,
    review_results: list[RequestExecutionResult],
) -> SelectedCrops:
    reviewed_ids = {result.request.request_id for result in review_results}
    merged = [] if existing is None else [item for item in existing.selections if item.request_id not in reviewed_ids]
    for result in review_results:
        if result.selected_crop is not None:
            merged.append(result.selected_crop)
    merged.sort(key=lambda selection: (selection.slide_number, selection.selection_id))
    limitations = _dedupe_text(
        ([] if existing is None else existing.limitations) + [item for result in review_results for item in result.limitations]
    )
    return SelectedCrops(deck_title=deck_title, selections=merged, limitations=limitations)


def _review_failure_result(
    request: AssetRequest,
    asset_record: AssetRecord,
    request_candidates: list[CropCandidate],
    *,
    note: str,
) -> RequestExecutionResult:
    limitations = _dedupe_text(asset_record.limitations or [note])
    return RequestExecutionResult(
        request=request,
        candidates=request_candidates,
        asset_record=asset_record,
        selected_crop=None,
        review_inputs=[],
        review_decisions=[],
        limitations=limitations,
        ledger_status=StageStatus.BLOCKED,
        production_readiness=StageStatus.BLOCKED,
        blockers=limitations,
        change_note=note,
    )


def _review_request(
    request: AssetRequest,
    request_candidates: list[CropCandidate],
    *,
    manifest_asset: AssetRecord | None,
    slide_entry: SlideLedgerEntry | None,
    candidates_dir: Path,
    assets_dir: Path,
    reviewer: CropReviewer,
    max_review_rounds: int,
    root: Path,
) -> RequestExecutionResult:
    issues = _validate_crop_review_lineage(
        request=request,
        request_candidates=request_candidates,
        manifest_asset=manifest_asset,
        slide_entry=slide_entry,
        root=root,
    )
    if issues:
        candidate_id = request_candidates[0].candidate_id if request_candidates else manifest_asset.candidate_id if manifest_asset is not None else None
        provenance = request_candidates[0].provenance if request_candidates else manifest_asset.provenance if manifest_asset is not None else None
        fallback_local_path = request.preferred_source_doc
        source_path = request.preferred_source_doc
        if not fallback_local_path and request_candidates:
            fallback_local_path = request_candidates[0].candidate_path
            source_path = request_candidates[0].source_file
        elif not fallback_local_path and manifest_asset is not None:
            fallback_local_path = manifest_asset.local_path
            source_path = manifest_asset.provenance.source_file if manifest_asset.provenance is not None else source_path

        failure_record = _failure_asset_record(
            request=request,
            local_path=fallback_local_path or request.slide_id,
            source_file=source_path or request.preferred_source_doc or request.slide_id,
            limitations=_dedupe_text([issues[0].reason_code.value, _fallback_ladder_note(request)]),
            review_action=CropReviewAction.FALLBACK_TO_VISUAL if request.asset_kind == AssetKind.DOCUMENT_CROP else None,
            failure_reason_codes=_lineage_issue_codes(issues),
            notes=_lineage_failure_summary(issues),
            candidate_id=candidate_id,
            provenance=provenance,
        )
        return _build_review_validation_failure(
            request=request,
            asset_record=failure_record,
            request_candidates=request_candidates,
            note=f"Crop review validation failed: {_lineage_failure_summary(issues)}",
            issues=issues,
            configured_max_review_rounds=max_review_rounds,
            review_rounds_used=0,
        )

    surfaces = _surfaces_for_review(request, request_candidates, root)
    manifest_asset_id = manifest_asset.asset_id if manifest_asset is not None else None
    reviewed_candidates, review_inputs, review_decisions, selected_crop, asset_record = _review_request_candidates(
        request,
        list(request_candidates),
        surfaces,
        candidates_dir,
        assets_dir,
        root,
        reviewer=reviewer,
        manifest_asset_id=manifest_asset_id,
        max_review_rounds=max_review_rounds,
    )
    if selected_crop is not None and asset_record is not None:
        limitations = _dedupe_text(asset_record.limitations)
        return RequestExecutionResult(
            request=request,
            candidates=reviewed_candidates,
            asset_record=asset_record,
            selected_crop=selected_crop,
            review_inputs=review_inputs,
            review_decisions=review_decisions,
            limitations=limitations,
            ledger_status=StageStatus.COMPLETE,
            production_readiness=StageStatus.COMPLETE,
            blockers=[],
            change_note="Bounded crop review accepted a compile-ready source crop.",
        )

    if asset_record is None:
        asset_record = _failure_asset_record(
            request=request,
            local_path=request.preferred_source_doc or reviewed_candidates[0].candidate_path,
            source_file=reviewed_candidates[0].source_file,
            limitations=[
                f"{request.request_id}: the bounded crop review ended without a compile-ready crop.",
                _fallback_ladder_note(request),
            ],
            review_action=CropReviewAction.FALLBACK_TO_VISUAL if request.asset_kind == AssetKind.DOCUMENT_CROP else None,
            failure_reason_codes=[CropReviewReasonCode.SELECTED_CROP_NOT_COMPILE_READY.value],
        )
    limitations = _dedupe_text(asset_record.limitations)
    return RequestExecutionResult(
        request=request,
        candidates=reviewed_candidates,
        asset_record=asset_record,
        selected_crop=None,
        review_inputs=review_inputs,
        review_decisions=review_decisions,
        limitations=limitations,
        ledger_status=StageStatus.BLOCKED,
        production_readiness=StageStatus.BLOCKED,
        blockers=limitations,
        change_note="Bounded crop review rejected the source crop and preserved the fallback path.",
    )


def _merge_asset_manifest(existing: AssetManifest | None, deck_title: str, asset_records: list[AssetRecord]) -> AssetManifest:
    prior_assets = [] if existing is None else [asset for asset in existing.assets if asset.request_id not in {record.request_id for record in asset_records}]
    merged_assets = prior_assets + asset_records
    merged_assets.sort(key=lambda asset: (asset.slide_number, asset.asset_id))
    return AssetManifest(deck_title=deck_title, assets=merged_assets)


def _update_slide_ledger(
    slide_ledger: SlideLedger,
    request_results: list[RequestExecutionResult],
) -> SlideLedger:
    results_by_slide: dict[str, list[RequestExecutionResult]] = {}
    for result in request_results:
        results_by_slide.setdefault(result.request.slide_id, []).append(result)
    updated_entries: list[SlideLedgerEntry] = []
    for entry in slide_ledger.entries:
        results = results_by_slide.get(entry.slide_id)
        if not results:
            updated_entries.append(entry)
            continue
        if any(result.ledger_status == StageStatus.BLOCKED for result in results):
            asset_status = StageStatus.BLOCKED
            production_readiness = StageStatus.BLOCKED
            blockers = _dedupe_text([item for result in results for item in result.blockers])
        elif all(result.ledger_status == StageStatus.COMPLETE for result in results):
            asset_status = StageStatus.COMPLETE
            production_readiness = StageStatus.COMPLETE
            blockers = []
        else:
            asset_status = StageStatus.IN_PROGRESS
            production_readiness = StageStatus.IN_PROGRESS
            blockers = _dedupe_text([item for result in results for item in result.blockers])
        change_note = entry.change_note
        for result in results:
            change_note = _merge_change_note(change_note, result.change_note)
        payload = entry.model_dump(mode="json")
        payload["asset_status"] = asset_status
        payload["production_readiness"] = production_readiness
        payload["unresolved_blockers"] = blockers or None
        payload["change_note"] = change_note
        updated_entries.append(SlideLedgerEntry.model_validate(payload))
    return SlideLedger(deck_title=slide_ledger.deck_title, entries=updated_entries, continuity_notes=slide_ledger.continuity_notes)


def run_document_asset_crop(
    asset_requests: AssetRequests,
    slide_ledger: SlideLedger,
    output_dir: str | Path,
    asset_manifest: AssetManifest | None = None,
    dpi: int = 144,
    max_candidates_per_source: int = 6,
    reviewer: CropReviewer | None = None,
    max_review_rounds: int = 2,
    root: str | Path | None = None,
) -> DocumentCropOutputs:
    del reviewer, max_review_rounds
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    previews_dir = output_root / "previews"
    candidates_dir = output_root / "candidates"
    assets_dir = output_root / "assets"
    previews_dir.mkdir(parents=True, exist_ok=True)
    candidates_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    root_path = Path(root).resolve() if root is not None else Path.cwd().resolve()
    handled_requests = [request for request in asset_requests.requests if _is_crop_request(request)]

    previews: list[SourcePreview] = []
    candidate_records: list[CropCandidate] = []
    review_inputs: list[CropReviewInput] = []
    review_decisions: list[CropReviewDecision] = []
    selected_records: list[SelectedCrop] = []
    asset_records: list[AssetRecord] = []
    limitations: list[str] = []
    request_results: list[RequestExecutionResult] = []

    for request in handled_requests:
        request_previews, result = _execute_request(
            request,
            previews_dir=previews_dir,
            candidates_dir=candidates_dir,
            assets_dir=assets_dir,
            dpi=dpi,
            max_candidates_per_source=max_candidates_per_source,
            root=root_path,
        )
        previews.extend(request_previews)
        candidate_records.extend(result.candidates)
        if result.selected_crop is not None:
            selected_records.append(result.selected_crop)
        asset_records.append(result.asset_record)
        limitations.extend(result.limitations)
        request_results.append(result)

    manifest = _merge_asset_manifest(asset_manifest, asset_requests.deck_title, asset_records)
    updated_ledger = _update_slide_ledger(slide_ledger, request_results)
    return DocumentCropOutputs(
        crop_candidates=CropCandidates(
            deck_title=asset_requests.deck_title,
            previews=previews,
            candidates=candidate_records,
            limitations=_dedupe_text(limitations),
        ),
        crop_review_inputs=CropReviewInputs(
            deck_title=asset_requests.deck_title,
            inputs=review_inputs,
        ),
        crop_review_decisions=CropReviewDecisions(
            deck_title=asset_requests.deck_title,
            decisions=review_decisions,
            limitations=_dedupe_text(limitations),
        ),
        selected_crops=SelectedCrops(
            deck_title=asset_requests.deck_title,
            selections=selected_records,
            limitations=_dedupe_text(limitations),
        ),
        asset_manifest=manifest,
        slide_ledger=updated_ledger,
    )


def run_document_crop_review(
    asset_requests: AssetRequests,
    crop_candidates: CropCandidates,
    asset_manifest: AssetManifest,
    slide_ledger: SlideLedger,
    output_dir: str | Path,
    *,
    crop_review_inputs: CropReviewInputs | None = None,
    crop_review_decisions: CropReviewDecisions | None = None,
    selected_crops: SelectedCrops | None = None,
    reviewer: CropReviewer | None = None,
    max_review_rounds: int = 2,
    root: str | Path | None = None,
) -> DocumentCropOutputs:
    max_review_rounds = _normalize_max_review_rounds(max_review_rounds)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    candidates_dir = output_root / "candidates"
    assets_dir = output_root / "assets"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    root_path = Path(root).resolve() if root is not None else Path.cwd().resolve()
    handled_requests = [request for request in asset_requests.requests if _is_crop_request(request)]
    manifest_by_request = {asset.request_id: asset for asset in asset_manifest.assets}
    slide_entries_by_slide = {(entry.slide_id, entry.slide_number): entry for entry in slide_ledger.entries}
    reviewable_requests = [
        request
        for request in handled_requests
        if manifest_by_request.get(request.request_id) is None
        or manifest_by_request[request.request_id].status == AssetStatus.PENDING_REVIEW
    ]

    if not reviewable_requests:
        return DocumentCropOutputs(
            crop_candidates=crop_candidates,
            crop_review_inputs=crop_review_inputs or CropReviewInputs(deck_title=asset_requests.deck_title, inputs=[]),
            crop_review_decisions=crop_review_decisions or CropReviewDecisions(deck_title=asset_requests.deck_title, decisions=[]),
            selected_crops=selected_crops or SelectedCrops(deck_title=asset_requests.deck_title, selections=[]),
            asset_manifest=asset_manifest,
            slide_ledger=slide_ledger,
        )

    candidates_by_request: dict[str, list[CropCandidate]] = {}
    for candidate in crop_candidates.candidates:
        candidates_by_request.setdefault(candidate.request_id, []).append(candidate)
    for bucket in candidates_by_request.values():
        bucket.sort(key=lambda candidate: (candidate.selection_rank, -candidate.score, candidate.candidate_id))

    review_results: list[RequestExecutionResult] = []
    active_reviewer = reviewer or HeuristicCropReviewer()
    for request in reviewable_requests:
        result = _review_request(
            request,
            candidates_by_request.get(request.request_id, []),
            manifest_asset=manifest_by_request.get(request.request_id),
            slide_entry=slide_entries_by_slide.get((request.slide_id, request.slide_number)),
            candidates_dir=candidates_dir,
            assets_dir=assets_dir,
            reviewer=active_reviewer,
            max_review_rounds=max_review_rounds,
            root=root_path,
        )
        review_results.append(result)

    manifest = _merge_asset_manifest(asset_manifest, asset_requests.deck_title, [result.asset_record for result in review_results])
    merged_candidates = _merge_crop_candidates(crop_candidates, review_results)
    merged_inputs = _merge_crop_review_inputs(asset_requests.deck_title, crop_review_inputs, review_results)
    merged_decisions = _merge_crop_review_decisions(asset_requests.deck_title, crop_review_decisions, review_results)
    merged_selected = _merge_selected_crops(asset_requests.deck_title, selected_crops, review_results)
    updated_ledger = _update_slide_ledger(slide_ledger, review_results)
    return DocumentCropOutputs(
        crop_candidates=merged_candidates,
        crop_review_inputs=merged_inputs,
        crop_review_decisions=merged_decisions,
        selected_crops=merged_selected,
        asset_manifest=manifest,
        slide_ledger=updated_ledger,
    )


def load_document_crop_file(path: str | Path) -> CropCandidates | CropReviewInputs | CropReviewDecisions | SelectedCrops:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    schema_name = payload.get("schema_name")
    if schema_name == CropCandidates.SCHEMA_NAME:
        return CropCandidates.model_validate(payload)
    if schema_name == CropReviewInputs.SCHEMA_NAME:
        return CropReviewInputs.model_validate(payload)
    if schema_name == CropReviewDecisions.SCHEMA_NAME:
        return CropReviewDecisions.model_validate(payload)
    if schema_name == SelectedCrops.SCHEMA_NAME:
        return SelectedCrops.model_validate(payload)
    raise ValueError(f"unsupported document-crop schema {schema_name!r}")


def run_document_asset_crop_from_files(
    asset_requests_path: str | Path,
    slide_ledger_path: str | Path,
    output_dir: str | Path,
    asset_manifest_path: str | Path | None = None,
    dpi: int = 144,
    max_candidates_per_source: int = 6,
    max_review_rounds: int = 2,
    root: str | Path | None = None,
) -> DocumentCropOutputs:
    from ..compat.legacy_non_pptx import load_state_file

    loaded_requests = load_state_file(asset_requests_path)
    if loaded_requests.schema_name != "asset_requests":
        raise TypeError(f"expected asset_requests, found {loaded_requests.schema_name}")
    loaded_ledger = load_state_file(slide_ledger_path)
    if loaded_ledger.schema_name != "slide_ledger":
        raise TypeError(f"expected slide_ledger, found {loaded_ledger.schema_name}")
    loaded_manifest = None
    if asset_manifest_path is not None:
        loaded_manifest = load_state_file(asset_manifest_path)
        if loaded_manifest.schema_name != "asset_manifest":
            raise TypeError(f"expected asset_manifest, found {loaded_manifest.schema_name}")
    return run_document_asset_crop(
        asset_requests=loaded_requests,
        slide_ledger=loaded_ledger,
        asset_manifest=loaded_manifest,
        output_dir=output_dir,
        dpi=dpi,
        max_candidates_per_source=max_candidates_per_source,
        max_review_rounds=max_review_rounds,
        root=root,
    )


def run_document_crop_review_from_files(
    asset_requests_path: str | Path,
    slide_ledger_path: str | Path,
    crop_candidates_path: str | Path,
    asset_manifest_path: str | Path,
    output_dir: str | Path,
    *,
    crop_review_inputs_path: str | Path | None = None,
    crop_review_decisions_path: str | Path | None = None,
    selected_crops_path: str | Path | None = None,
    max_review_rounds: int = 2,
    root: str | Path | None = None,
) -> DocumentCropOutputs:
    from ..compat.legacy_non_pptx import load_state_file

    loaded_requests = load_state_file(asset_requests_path)
    if loaded_requests.schema_name != "asset_requests":
        raise TypeError(f"expected asset_requests, found {loaded_requests.schema_name}")
    loaded_ledger = load_state_file(slide_ledger_path)
    if loaded_ledger.schema_name != "slide_ledger":
        raise TypeError(f"expected slide_ledger, found {loaded_ledger.schema_name}")
    loaded_manifest = load_state_file(asset_manifest_path)
    if loaded_manifest.schema_name != "asset_manifest":
        raise TypeError(f"expected asset_manifest, found {loaded_manifest.schema_name}")

    loaded_candidates = load_document_crop_file(crop_candidates_path)
    if loaded_candidates.schema_name != "crop_candidates":
        raise TypeError(f"expected crop_candidates, found {loaded_candidates.schema_name}")

    loaded_inputs = None
    if crop_review_inputs_path is not None and Path(crop_review_inputs_path).is_file():
        loaded_inputs = load_document_crop_file(crop_review_inputs_path)
        if loaded_inputs.schema_name != "crop_review_inputs":
            raise TypeError(f"expected crop_review_inputs, found {loaded_inputs.schema_name}")

    loaded_decisions = None
    if crop_review_decisions_path is not None and Path(crop_review_decisions_path).is_file():
        loaded_decisions = load_document_crop_file(crop_review_decisions_path)
        if loaded_decisions.schema_name != "crop_review_decisions":
            raise TypeError(f"expected crop_review_decisions, found {loaded_decisions.schema_name}")

    loaded_selected = None
    if selected_crops_path is not None and Path(selected_crops_path).is_file():
        loaded_selected = load_document_crop_file(selected_crops_path)
        if loaded_selected.schema_name != "selected_crops":
            raise TypeError(f"expected selected_crops, found {loaded_selected.schema_name}")

    return run_document_crop_review(
        asset_requests=loaded_requests,
        crop_candidates=loaded_candidates,
        crop_review_inputs=loaded_inputs,
        crop_review_decisions=loaded_decisions,
        selected_crops=loaded_selected,
        asset_manifest=loaded_manifest,
        slide_ledger=loaded_ledger,
        output_dir=output_dir,
        max_review_rounds=max_review_rounds,
        root=root,
    )


def write_document_crop_outputs(outputs: DocumentCropOutputs, output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    written = {
        "crop_candidates": save_state_file(outputs.crop_candidates, root / "crop-candidates.json"),
        "crop_review_inputs": save_state_file(outputs.crop_review_inputs, root / "crop-review-inputs.json"),
        "crop_review_decisions": save_state_file(outputs.crop_review_decisions, root / "crop-review-decisions.json"),
        "selected_crops": save_state_file(outputs.selected_crops, root / "selected-crops.json"),
        "asset_manifest": save_state_file(outputs.asset_manifest, root / "asset-manifest.json"),
        "slide_ledger": save_state_file(outputs.slide_ledger, root / "slide-ledger.json"),
    }
    return written



