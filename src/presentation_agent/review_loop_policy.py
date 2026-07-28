"""Policy helpers for crop/visual approval-loop state and active-path reporting."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .non_pptx_modules.state_schemas import AssetKind, AssetManifest, AssetStatus, VizManifest, VizStatus

COMPILE_READY_ASSET_STATUSES = (AssetStatus.APPROVED, AssetStatus.READY)
COMPILE_READY_VIZ_STATUSES = (VizStatus.RENDERED, VizStatus.APPROVED)


class CropVisualReviewTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    action: str
    pending_document_crop_count: int = 0
    ready_document_crop_count: int = 0
    rejected_document_crop_count: int = 0
    reason_codes: list[str] = Field(default_factory=list)

    @property
    def can_skip_crop_review(self) -> bool:
        return self.action == "skip-review"


class CropVisualReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    approval_outcome: str
    raw_review_artifacts: dict[str, int] = Field(default_factory=dict)
    compile_warning_codes: list[str] = Field(default_factory=list)
    compile_blocking: bool = False
    compile_ready_asset_count: int = 0
    pending_review_asset_count: int = 0
    rejected_asset_count: int = 0
    asset_status_counts: dict[str, int] = Field(default_factory=dict)
    asset_kind_counts: dict[str, int] = Field(default_factory=dict)
    viz_status_counts: dict[str, int] = Field(default_factory=dict)
    document_crop_ready_count: int = 0
    document_crop_pending_review_count: int = 0
    document_crop_rejected_count: int = 0
    structured_visual_ready_count: int = 0
    rendered_visual_count: int = 0
    approved_visual_count: int = 0
    rejected_visual_count: int = 0
    compatibility_fields: dict[str, Any] = Field(default_factory=dict)


def determine_crop_review_transition(asset_manifest: AssetManifest) -> CropVisualReviewTransition:
    document_crops = [asset for asset in asset_manifest.assets if asset.asset_kind == AssetKind.DOCUMENT_CROP]
    pending_count = sum(1 for asset in document_crops if asset.status == AssetStatus.PENDING_REVIEW)
    ready_count = sum(1 for asset in document_crops if asset.status in COMPILE_READY_ASSET_STATUSES)
    rejected_count = sum(1 for asset in document_crops if asset.status == AssetStatus.REJECTED)
    reason_codes: list[str] = []
    if pending_count:
        reason_codes.append("pending-document-crop-review")
        if ready_count:
            reason_codes.append("mixed-document-crop-review-state")
        if rejected_count:
            reason_codes.append("rejected-document-crops-retained")
        action = "review-required"
    else:
        action = "skip-review"
        if ready_count:
            reason_codes.append("document-crop-review-complete")
        else:
            reason_codes.append("no-document-crop-review-needed")
        if rejected_count:
            reason_codes.append("rejected-document-crops-retained")
    return CropVisualReviewTransition(
        action=action,
        pending_document_crop_count=pending_count,
        ready_document_crop_count=ready_count,
        rejected_document_crop_count=rejected_count,
        reason_codes=reason_codes,
    )


def summarize_crop_visual_review(
    *,
    asset_manifest: AssetManifest,
    viz_manifest: VizManifest,
    crop_review_inputs: Any | None = None,
    crop_review_decisions: Any | None = None,
    selected_crops: Any | None = None,
) -> CropVisualReviewReport:
    asset_status_counts = _enum_counts((asset.status for asset in asset_manifest.assets), AssetStatus)
    asset_kind_counts = _enum_counts((asset.asset_kind for asset in asset_manifest.assets), AssetKind)
    viz_status_counts = _enum_counts((record.status for record in viz_manifest.visuals), VizStatus)
    document_crop_assets = [asset for asset in asset_manifest.assets if asset.asset_kind == AssetKind.DOCUMENT_CROP]
    structured_visual_assets = [
        asset for asset in asset_manifest.assets if asset.asset_kind == AssetKind.STRUCTURED_VISUAL
    ]
    raw_review_artifacts = {
        "crop_review_input_count": _collection_count(crop_review_inputs, "inputs"),
        "crop_review_decision_count": _collection_count(crop_review_decisions, "decisions"),
        "selected_crop_count": _collection_count(selected_crops, "selections"),
        "visual_record_count": len(viz_manifest.visuals),
    }

    compile_ready_asset_count = sum(1 for asset in asset_manifest.assets if asset.status in COMPILE_READY_ASSET_STATUSES)
    pending_review_asset_count = sum(1 for asset in asset_manifest.assets if asset.status == AssetStatus.PENDING_REVIEW)
    rejected_asset_count = sum(1 for asset in asset_manifest.assets if asset.status == AssetStatus.REJECTED)
    document_crop_ready_count = sum(1 for asset in document_crop_assets if asset.status in COMPILE_READY_ASSET_STATUSES)
    document_crop_pending_review_count = sum(
        1 for asset in document_crops(asset_manifest) if asset.status == AssetStatus.PENDING_REVIEW
    )
    document_crop_rejected_count = sum(1 for asset in document_crops(asset_manifest) if asset.status == AssetStatus.REJECTED)
    structured_visual_ready_count = sum(
        1 for asset in structured_visual_assets if asset.status in COMPILE_READY_ASSET_STATUSES
    )
    rendered_visual_count = sum(1 for record in viz_manifest.visuals if record.status == VizStatus.RENDERED)
    approved_visual_count = sum(1 for record in viz_manifest.visuals if record.status == VizStatus.APPROVED)
    rejected_visual_count = sum(1 for record in viz_manifest.visuals if record.status == VizStatus.REJECTED)

    compile_warning_codes = _compile_warning_codes(
        document_crop_pending_review_count=document_crop_pending_review_count,
        document_crop_rejected_count=document_crop_rejected_count,
        rejected_visual_count=rejected_visual_count,
        structured_visual_ready_count=structured_visual_ready_count,
        rendered_visual_count=rendered_visual_count,
        approved_visual_count=approved_visual_count,
        raw_review_artifacts=raw_review_artifacts,
    )
    approval_outcome = _approval_outcome(
        pending_review_asset_count=document_crop_pending_review_count,
        rejected_asset_count=document_crop_rejected_count + rejected_visual_count,
        compile_ready_asset_count=compile_ready_asset_count,
        rendered_visual_count=rendered_visual_count,
        approved_visual_count=approved_visual_count,
    )
    compatibility_fields = {
        "compile_ready_asset_statuses": [status.value for status in COMPILE_READY_ASSET_STATUSES],
        "compile_ready_visual_statuses": [status.value for status in COMPILE_READY_VIZ_STATUSES],
        "legacy_review_required": document_crop_pending_review_count > 0,
        "legacy_pending_document_crop_count": document_crop_pending_review_count,
    }
    return CropVisualReviewReport(
        approval_outcome=approval_outcome,
        raw_review_artifacts=raw_review_artifacts,
        compile_warning_codes=compile_warning_codes,
        compile_blocking=False,
        compile_ready_asset_count=compile_ready_asset_count,
        pending_review_asset_count=pending_review_asset_count,
        rejected_asset_count=rejected_asset_count,
        asset_status_counts=asset_status_counts,
        asset_kind_counts=asset_kind_counts,
        viz_status_counts=viz_status_counts,
        document_crop_ready_count=document_crop_ready_count,
        document_crop_pending_review_count=document_crop_pending_review_count,
        document_crop_rejected_count=document_crop_rejected_count,
        structured_visual_ready_count=structured_visual_ready_count,
        rendered_visual_count=rendered_visual_count,
        approved_visual_count=approved_visual_count,
        rejected_visual_count=rejected_visual_count,
        compatibility_fields=compatibility_fields,
    )


def document_crops(asset_manifest: AssetManifest):
    return [asset for asset in asset_manifest.assets if asset.asset_kind == AssetKind.DOCUMENT_CROP]


def _enum_counts(values, enum_cls) -> dict[str, int]:
    counter = Counter()
    for value in values:
        key = getattr(value, "value", str(value))
        counter[key] += 1
    return {member.value: counter.get(member.value, 0) for member in enum_cls}


def _collection_count(model: Any | None, attribute: str) -> int:
    if model is None:
        return 0
    value = getattr(model, attribute, None)
    if not isinstance(value, list):
        return 0
    return len(value)


def _compile_warning_codes(
    *,
    document_crop_pending_review_count: int,
    document_crop_rejected_count: int,
    rejected_visual_count: int,
    structured_visual_ready_count: int,
    rendered_visual_count: int,
    approved_visual_count: int,
    raw_review_artifacts: dict[str, int],
) -> list[str]:
    warnings: list[str] = []
    if document_crop_pending_review_count:
        warnings.append("crop-review-pending")
        if raw_review_artifacts["crop_review_input_count"] == 0:
            warnings.append("crop-review-inputs-missing")
        if raw_review_artifacts["crop_review_decision_count"] == 0:
            warnings.append("crop-review-decisions-missing")
        if raw_review_artifacts["selected_crop_count"] == 0:
            warnings.append("crop-selection-missing")
    if document_crop_rejected_count:
        warnings.append("crop-review-rejected")
    if rejected_visual_count:
        warnings.append("visual-review-rejected")
    if structured_visual_ready_count and not (rendered_visual_count or approved_visual_count):
        warnings.append("visual-review-artifacts-missing")
    return list(dict.fromkeys(warnings))


def _approval_outcome(
    *,
    pending_review_asset_count: int,
    rejected_asset_count: int,
    compile_ready_asset_count: int,
    rendered_visual_count: int,
    approved_visual_count: int,
) -> str:
    has_ready_outputs = bool(compile_ready_asset_count or rendered_visual_count or approved_visual_count)
    if pending_review_asset_count and (rejected_asset_count or has_ready_outputs):
        return "mixed"
    if pending_review_asset_count:
        return "pending-review"
    if rejected_asset_count:
        return "repairable"
    if has_ready_outputs:
        return "approved"
    return "no-review-required"
