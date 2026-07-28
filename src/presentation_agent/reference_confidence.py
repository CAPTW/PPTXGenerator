from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .non_pptx_modules.state_schemas import ReferenceDNA


class ReferenceScanConfidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    confidence_tier: str
    confidence_score: float
    source_count: int = 0
    accepted_source_count: int = 0
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0
    uncertain_count: int = 0
    accepted_for_design_guidance: bool = False
    policy_action: str
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    accepted_source_paths: list[str] = Field(default_factory=list)
    rejected_source_paths: list[str] = Field(default_factory=list)


_TIER_TO_SCORE = {
    "none": 0.0,
    "low": 0.25,
    "medium": 0.75,
    "high": 1.0,
}


def _dedupe_strings(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _band_name(value: object) -> str:
    if value is None:
        return "low"
    band = getattr(value, "value", value)
    if isinstance(band, str):
        normalized = band.strip().lower()
        if normalized in {"high", "medium", "low"}:
            return normalized
    return "low"


def _normalized_path(value: str | None) -> str:
    return (value or "").replace("\\", "/").strip()


def summarize_reference_scan_confidence(reference_dna: ReferenceDNA | None) -> ReferenceScanConfidenceSummary:
    if reference_dna is None:
        return ReferenceScanConfidenceSummary(
            confidence_tier="none",
            confidence_score=_TIER_TO_SCORE["none"],
            policy_action="fallback-defaults",
            reason_codes=["reference-pack-missing", "deterministic-local-default"],
        )

    band_counts = {"high": 0, "medium": 0, "low": 0}
    uncertain_count = 0
    rejected_source_paths: list[str] = []
    for material in reference_dna.source_files:
        band = _band_name(material.confidence_band)
        band_counts[band] += 1
        if material.uncertain:
            uncertain_count += 1
            normalized_path = _normalized_path(material.path)
            if normalized_path:
                rejected_source_paths.append(normalized_path)

    accepted_source_paths: list[str] = []
    accepted_bands: list[str] = []
    for profile in reference_dna.reference_profiles:
        for source_ref in profile.source_material_refs:
            normalized_path = _normalized_path(source_ref.path)
            if normalized_path:
                accepted_source_paths.append(normalized_path)
            accepted_bands.append(_band_name(source_ref.confidence_band))

    accepted_source_paths = _dedupe_strings(accepted_source_paths)
    rejected_source_paths = _dedupe_strings(rejected_source_paths)
    accepted_for_design_guidance = bool(accepted_source_paths)
    if "high" in accepted_bands:
        confidence_tier = "high"
    elif "medium" in accepted_bands:
        confidence_tier = "medium"
    elif reference_dna.source_files:
        confidence_tier = "low"
    else:
        confidence_tier = "none"

    reason_codes: list[str] = []
    warnings: list[str] = []
    if accepted_for_design_guidance:
        reason_codes.append("promoted-reference-sources-present")
        if confidence_tier == "high":
            reason_codes.append("high-confidence-reference-source-present")
        elif confidence_tier == "medium":
            reason_codes.append("medium-confidence-reference-source-present")
        if rejected_source_paths:
            reason_codes.append("low-confidence-reference-sources-excluded")
            warnings.append(
                "Low-confidence reference sources were retained for audit only and excluded from design-driving guidance."
            )
        policy_action = "trusted-reference-guidance"
    else:
        reason_codes.extend(
            [
                "no-promoted-reference-sources",
                "deterministic-local-default",
            ]
        )
        if uncertain_count:
            reason_codes.append("uncertain-reference-sources-present")
        if reference_dna.source_files and band_counts["low"] == len(reference_dna.source_files):
            reason_codes.append("all-reference-sources-low-confidence")
        warnings.append(
            "Reference scan confidence is too weak to drive Gate 2 or template decisions; local defaults remain primary."
        )
        policy_action = "fallback-defaults"

    return ReferenceScanConfidenceSummary(
        confidence_tier=confidence_tier,
        confidence_score=_TIER_TO_SCORE[confidence_tier],
        source_count=len(reference_dna.source_files),
        accepted_source_count=len(accepted_source_paths),
        high_confidence_count=band_counts["high"],
        medium_confidence_count=band_counts["medium"],
        low_confidence_count=band_counts["low"],
        uncertain_count=uncertain_count,
        accepted_for_design_guidance=accepted_for_design_guidance,
        policy_action=policy_action,
        reason_codes=_dedupe_strings(reason_codes),
        warnings=_dedupe_strings(warnings),
        accepted_source_paths=accepted_source_paths,
        rejected_source_paths=rejected_source_paths,
    )


def reference_dna_for_design_guidance(
    reference_dna: ReferenceDNA | None,
    summary: ReferenceScanConfidenceSummary | None = None,
) -> ReferenceDNA | None:
    if reference_dna is None:
        return None
    evaluated = summary or summarize_reference_scan_confidence(reference_dna)
    if not evaluated.accepted_for_design_guidance:
        return None
    return reference_dna


def build_reference_artifact_entry(
    reference_dna: ReferenceDNA | None,
    summary: ReferenceScanConfidenceSummary | None = None,
) -> dict[str, object]:
    evaluated = summary or summarize_reference_scan_confidence(reference_dna)
    payload: dict[str, object] = {
        "asset_id": "reference_pack",
        "role": "design_reference",
        "confidence": evaluated.confidence_score,
        "confidence_tier": evaluated.confidence_tier,
        "accepted_for_design_guidance": evaluated.accepted_for_design_guidance,
        "policy_action": evaluated.policy_action,
        "confidence_reason_codes": list(evaluated.reason_codes),
    }
    if reference_dna is not None:
        payload["source_family"] = reference_dna.source_family
    return payload


def build_reference_design_tokens(
    reference_dna: ReferenceDNA | None,
    summary: ReferenceScanConfidenceSummary | None = None,
) -> dict[str, object]:
    evaluated = summary or summarize_reference_scan_confidence(reference_dna)
    payload: dict[str, object] = {
        "reference_scan_confidence": evaluated.model_dump(mode="json"),
        "reference_scan_policy_action": evaluated.policy_action,
    }
    trusted_reference = reference_dna_for_design_guidance(reference_dna, evaluated)
    if trusted_reference is None:
        return payload
    payload.update(
        {
            "source_family": trusted_reference.source_family,
            "section_divider_style": trusted_reference.section_divider_style,
            "patterns_worth_borrowing": list(trusted_reference.patterns_worth_borrowing[:3]),
        }
    )
    return payload


def build_reference_style_tokens(
    reference_dna: ReferenceDNA | None,
    summary: ReferenceScanConfidenceSummary | None = None,
) -> list[str]:
    trusted_reference = reference_dna_for_design_guidance(reference_dna, summary)
    if trusted_reference is None:
        return []
    return [
        f"reference-source-family:{trusted_reference.source_family}",
        f"section-divider-style:{trusted_reference.section_divider_style}",
        *(f"pattern:{item}" for item in list(trusted_reference.patterns_worth_borrowing[:3])),
    ]


def build_reference_approval_basis(
    reference_dna: ReferenceDNA | None,
    summary: ReferenceScanConfidenceSummary | None = None,
) -> list[str]:
    evaluated = summary or summarize_reference_scan_confidence(reference_dna)
    trusted_reference = reference_dna_for_design_guidance(reference_dna, evaluated)
    if trusted_reference is None:
        if reference_dna is None:
            return []
        return [
            f"Reference scan confidence `{evaluated.confidence_tier}` did not meet the design-guidance threshold.",
            *list(evaluated.warnings[:1]),
        ]
    return [
        trusted_reference.fit_assessment,
        *list(trusted_reference.layout_logic[:2]),
        *list(trusted_reference.hierarchy_behavior[:2]),
    ]


def build_reference_guidance_payload(
    reference_dna: ReferenceDNA | None,
    summary: ReferenceScanConfidenceSummary | None = None,
) -> dict[str, object]:
    evaluated = summary or summarize_reference_scan_confidence(reference_dna)
    payload: dict[str, object] = {
        "available": evaluated.accepted_for_design_guidance,
        "confidence_tier": evaluated.confidence_tier,
        "accepted_for_design_guidance": evaluated.accepted_for_design_guidance,
        "policy_action": evaluated.policy_action,
        "confidence_reason_codes": list(evaluated.reason_codes),
        "warnings": list(evaluated.warnings),
    }
    trusted_reference = reference_dna_for_design_guidance(reference_dna, evaluated)
    if trusted_reference is None:
        return payload
    payload.update(
        {
            "source_family": trusted_reference.source_family,
            "patterns_worth_borrowing": trusted_reference.patterns_worth_borrowing,
            "patterns_to_avoid": trusted_reference.patterns_to_avoid,
            "layout_logic": trusted_reference.layout_logic,
            "hierarchy_behavior": trusted_reference.hierarchy_behavior,
            "whitespace_behavior": trusted_reference.whitespace_behavior,
            "section_divider_style": trusted_reference.section_divider_style,
            "fit_assessment": trusted_reference.fit_assessment,
        }
    )
    return payload


__all__ = [
    "ReferenceScanConfidenceSummary",
    "build_reference_approval_basis",
    "build_reference_artifact_entry",
    "build_reference_design_tokens",
    "build_reference_guidance_payload",
    "build_reference_style_tokens",
    "reference_dna_for_design_guidance",
    "summarize_reference_scan_confidence",
]
