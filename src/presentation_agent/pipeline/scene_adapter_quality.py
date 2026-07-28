"""Opt-in adapter diagnostic policy checks for scene readiness reports."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ADAPTER_QUALITY_POLICY_SCHEMA = "scene_adapter_policy"
ADAPTER_QUALITY_POLICY_VERSION = "0.1"
AdapterQualityStatus = Literal["disabled", "passed", "failed"]
AdapterWarningCategory = Literal[
    "informational",
    "inferred_structure",
    "ambiguity",
    "unsupported",
    "lossy_fallback",
    "identity_repair",
]
AdapterQualityFindingCode = Literal[
    "adapter_quality_warning_count_exceeded",
    "adapter_quality_placeholder_shapes",
    "adapter_quality_unsupported_layout_family",
    "adapter_quality_unsupported_motif_pattern",
    "adapter_quality_ambiguous_callout_mapping",
    "adapter_quality_ambiguous_divider_mapping",
    "adapter_quality_ambiguous_bullet_mapping",
    "adapter_quality_duplicate_object_id_resolved",
    "adapter_quality_lossy_fallback",
    "adapter_quality_inferred_background_shape",
    "adapter_quality_policy_missing",
    "adapter_quality_policy_invalid",
]

ADAPTER_WARNING_CATEGORIES: dict[str, AdapterWarningCategory] = {
    "inferred_background_shape": "inferred_structure",
    "placeholder_shape_emitted": "lossy_fallback",
    "unsupported_layout_family": "unsupported",
    "unsupported_motif_pattern": "unsupported",
    "ambiguous_callout_mapping": "ambiguity",
    "ambiguous_divider_mapping": "ambiguity",
    "ambiguous_bullet_mapping": "ambiguity",
    "duplicate_object_id_resolved": "identity_repair",
}
_CODE_TO_FINDING: dict[str, AdapterQualityFindingCode] = {
    "placeholder_shape_emitted": "adapter_quality_placeholder_shapes",
    "unsupported_layout_family": "adapter_quality_unsupported_layout_family",
    "unsupported_motif_pattern": "adapter_quality_unsupported_motif_pattern",
    "ambiguous_callout_mapping": "adapter_quality_ambiguous_callout_mapping",
    "ambiguous_divider_mapping": "adapter_quality_ambiguous_divider_mapping",
    "ambiguous_bullet_mapping": "adapter_quality_ambiguous_bullet_mapping",
    "duplicate_object_id_resolved": "adapter_quality_duplicate_object_id_resolved",
    "inferred_background_shape": "adapter_quality_inferred_background_shape",
}


class SceneAdapterQualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdapterQualitySummary(SceneAdapterQualityModel):
    adapter_warning_count: int = 0
    adapter_warning_count_by_code: dict[str, int] = Field(default_factory=dict)
    placeholder_shape_count: int = 0
    unsupported_layout_family_count: int = 0
    unsupported_motif_pattern_count: int = 0
    duplicate_object_id_resolved_count: int = 0
    ambiguous_mapping_count: int = 0
    inferred_background_shape_count: int = 0
    lossy_fallback_count: int = 0


class AdapterQualityPolicy(SceneAdapterQualityModel):
    max_adapter_warning_count: int | None = None
    max_adapter_warning_count_by_code: dict[str, int] = Field(default_factory=dict)
    max_placeholder_shape_count: int | None = None
    max_unsupported_layout_family_count: int | None = None
    max_unsupported_motif_pattern_count: int | None = None
    max_ambiguous_mapping_count: int | None = None
    max_duplicate_object_id_resolved_count: int | None = None
    allow_inferred_background_shape: bool = True
    allow_placeholder_shapes: bool = False
    allow_unsupported_layout_families: bool = False
    allow_duplicate_object_id_repairs: bool = False
    enforce_zero_lossy_fallbacks: bool = False
    enforce_zero_unsupported_families: bool = False
    enforce_zero_placeholder_shapes: bool = False
    enforce_zero_ambiguous_mappings: bool = False

    @field_validator(
        "max_adapter_warning_count",
        "max_placeholder_shape_count",
        "max_unsupported_layout_family_count",
        "max_unsupported_motif_pattern_count",
        "max_ambiguous_mapping_count",
        "max_duplicate_object_id_resolved_count",
    )
    @classmethod
    def _validate_optional_non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("adapter quality thresholds must be non-negative")
        return value

    @field_validator("max_adapter_warning_count_by_code")
    @classmethod
    def _validate_code_thresholds(cls, value: dict[str, int]) -> dict[str, int]:
        for warning_code, threshold in value.items():
            if threshold < 0:
                raise ValueError(f"adapter quality threshold for {warning_code!r} must be non-negative")
        return value


class AdapterQualityFixturePolicy(SceneAdapterQualityModel):
    profile: str


class SceneAdapterPolicyFile(SceneAdapterQualityModel):
    schema_name: Literal["scene_adapter_policy"] = ADAPTER_QUALITY_POLICY_SCHEMA
    schema_version: str = ADAPTER_QUALITY_POLICY_VERSION
    profiles: dict[str, AdapterQualityPolicy] = Field(default_factory=dict)
    fixtures: dict[str, AdapterQualityFixturePolicy] = Field(default_factory=dict)

    def policy_for_fixture(self, fixture_id: str, profile_name: str) -> tuple[str, AdapterQualityPolicy | None]:
        fixture_policy = self.fixtures.get(fixture_id)
        selected_profile = fixture_policy.profile if fixture_policy is not None else profile_name
        return selected_profile, self.profiles.get(selected_profile)


class AdapterQualityFinding(SceneAdapterQualityModel):
    code: AdapterQualityFindingCode
    severity: Literal["warning", "error"] = "error"
    enforceable: bool = True
    observed: int | bool
    allowed: int | bool | None = None
    fixture_id: str | None = None
    adapter_warning_code: str | None = None
    category: AdapterWarningCategory | None = None
    message: str


class AdapterQualityResult(SceneAdapterQualityModel):
    enabled: bool
    profile: str | None = None
    status: AdapterQualityStatus = "disabled"
    passed: bool = True
    summary: AdapterQualitySummary = Field(default_factory=AdapterQualitySummary)
    findings: list[AdapterQualityFinding] = Field(default_factory=list)
    enforceable_count: int = 0
    warning_count: int = 0


def default_adapter_quality_policy() -> AdapterQualityPolicy:
    """Return a built-in adapter-strict policy for curated real fixtures."""

    return AdapterQualityPolicy(
        max_adapter_warning_count_by_code={
            "inferred_background_shape": 8,
            "placeholder_shape_emitted": 0,
            "unsupported_layout_family": 0,
            "unsupported_motif_pattern": 0,
            "duplicate_object_id_resolved": 0,
        },
        max_placeholder_shape_count=0,
        max_unsupported_layout_family_count=0,
        max_unsupported_motif_pattern_count=0,
        max_duplicate_object_id_resolved_count=0,
        allow_inferred_background_shape=True,
        allow_placeholder_shapes=False,
        allow_unsupported_layout_families=False,
        allow_duplicate_object_id_repairs=False,
        enforce_zero_unsupported_families=True,
        enforce_zero_placeholder_shapes=True,
        enforce_zero_lossy_fallbacks=True,
    )


def load_scene_adapter_policy(policy_path: str | Path) -> SceneAdapterPolicyFile:
    return SceneAdapterPolicyFile.model_validate_json(Path(policy_path).read_text(encoding="utf-8"))


def evaluate_adapter_quality_policy(
    adapter_summary: dict[str, Any],
    *,
    policy: AdapterQualityPolicy | None,
    profile: str | None,
    fixture_id: str | None = None,
) -> AdapterQualityResult:
    summary = adapter_quality_summary_from_adapter_summary(adapter_summary)
    if policy is None:
        return AdapterQualityResult(enabled=False, profile=profile, status="disabled", passed=True, summary=summary)

    findings: list[AdapterQualityFinding] = []
    _append_threshold_finding(
        findings,
        code="adapter_quality_warning_count_exceeded",
        warning_code=None,
        category=None,
        observed=summary.adapter_warning_count,
        allowed=policy.max_adapter_warning_count,
        fixture_id=fixture_id,
        message="Adapter warning count exceeded the configured policy threshold.",
    )
    for warning_code, allowed in sorted(policy.max_adapter_warning_count_by_code.items()):
        _append_threshold_finding(
            findings,
            code=_CODE_TO_FINDING.get(warning_code, "adapter_quality_warning_count_exceeded"),
            warning_code=warning_code,
            category=ADAPTER_WARNING_CATEGORIES.get(warning_code),
            observed=summary.adapter_warning_count_by_code.get(warning_code, 0),
            allowed=allowed,
            fixture_id=fixture_id,
            message=f"Adapter warning {warning_code!r} exceeded the configured policy threshold.",
        )

    _append_threshold_finding(
        findings,
        code="adapter_quality_placeholder_shapes",
        warning_code="placeholder_shape_emitted",
        category="lossy_fallback",
        observed=summary.placeholder_shape_count,
        allowed=0 if policy.enforce_zero_placeholder_shapes or not policy.allow_placeholder_shapes else policy.max_placeholder_shape_count,
        fixture_id=fixture_id,
        message="Placeholder shapes exceeded the configured adapter policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="adapter_quality_unsupported_layout_family",
        warning_code="unsupported_layout_family",
        category="unsupported",
        observed=summary.unsupported_layout_family_count,
        allowed=0 if policy.enforce_zero_unsupported_families or not policy.allow_unsupported_layout_families else policy.max_unsupported_layout_family_count,
        fixture_id=fixture_id,
        message="Unsupported layout-family warnings exceeded the configured adapter policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="adapter_quality_unsupported_motif_pattern",
        warning_code="unsupported_motif_pattern",
        category="unsupported",
        observed=summary.unsupported_motif_pattern_count,
        allowed=policy.max_unsupported_motif_pattern_count,
        fixture_id=fixture_id,
        message="Unsupported motif-pattern warnings exceeded the configured adapter policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="adapter_quality_duplicate_object_id_resolved",
        warning_code="duplicate_object_id_resolved",
        category="identity_repair",
        observed=summary.duplicate_object_id_resolved_count,
        allowed=0 if not policy.allow_duplicate_object_id_repairs else policy.max_duplicate_object_id_resolved_count,
        fixture_id=fixture_id,
        message="Duplicate object-id repairs exceeded the configured adapter policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="adapter_quality_lossy_fallback",
        warning_code=None,
        category="lossy_fallback",
        observed=summary.lossy_fallback_count,
        allowed=0 if policy.enforce_zero_lossy_fallbacks else None,
        fixture_id=fixture_id,
        message="Lossy adapter fallbacks exceeded the configured adapter policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="adapter_quality_ambiguous_callout_mapping",
        warning_code=None,
        category="ambiguity",
        observed=summary.ambiguous_mapping_count,
        allowed=0 if policy.enforce_zero_ambiguous_mappings else policy.max_ambiguous_mapping_count,
        fixture_id=fixture_id,
        message="Ambiguous adapter mappings exceeded the configured adapter policy threshold.",
    )
    if not policy.allow_inferred_background_shape and summary.inferred_background_shape_count > 0:
        findings.append(
            AdapterQualityFinding(
                code="adapter_quality_inferred_background_shape",
                observed=summary.inferred_background_shape_count,
                allowed=0,
                fixture_id=fixture_id,
                adapter_warning_code="inferred_background_shape",
                category="inferred_structure",
                message="Inferred background shapes are not allowed by the configured adapter policy.",
            )
        )

    enforceable_count = sum(1 for finding in findings if finding.enforceable)
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    return AdapterQualityResult(
        enabled=True,
        profile=profile,
        status="passed" if enforceable_count == 0 else "failed",
        passed=enforceable_count == 0,
        summary=summary,
        findings=sorted(findings, key=lambda item: (item.fixture_id or "", item.adapter_warning_code or "", item.code)),
        enforceable_count=enforceable_count,
        warning_count=warning_count,
    )


def adapter_quality_summary_from_adapter_summary(adapter_summary: dict[str, Any]) -> AdapterQualitySummary:
    counts = Counter({str(key): int(value) for key, value in dict(adapter_summary.get("warning_code_counts", {})).items()})
    ambiguous_mapping_count = sum(
        counts[code]
        for code in ("ambiguous_callout_mapping", "ambiguous_divider_mapping", "ambiguous_bullet_mapping")
    )
    lossy_fallback_count = counts["placeholder_shape_emitted"]
    return AdapterQualitySummary(
        adapter_warning_count=sum(counts.values()),
        adapter_warning_count_by_code=dict(sorted(counts.items())),
        placeholder_shape_count=counts["placeholder_shape_emitted"],
        unsupported_layout_family_count=counts["unsupported_layout_family"],
        unsupported_motif_pattern_count=counts["unsupported_motif_pattern"],
        duplicate_object_id_resolved_count=counts["duplicate_object_id_resolved"],
        ambiguous_mapping_count=ambiguous_mapping_count,
        inferred_background_shape_count=counts["inferred_background_shape"],
        lossy_fallback_count=lossy_fallback_count,
    )


def adapter_quality_findings_to_stable_json(findings: list[AdapterQualityFinding]) -> str:
    return json.dumps(
        [finding.model_dump(mode="json", exclude_none=True) for finding in findings],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _append_threshold_finding(
    findings: list[AdapterQualityFinding],
    *,
    code: AdapterQualityFindingCode,
    warning_code: str | None,
    category: AdapterWarningCategory | None,
    observed: int,
    allowed: int | None,
    fixture_id: str | None,
    message: str,
) -> None:
    if allowed is None or observed <= allowed:
        return
    findings.append(
        AdapterQualityFinding(
            code=code,
            observed=observed,
            allowed=allowed,
            fixture_id=fixture_id,
            adapter_warning_code=warning_code,
            category=category,
            message=message,
        )
    )
