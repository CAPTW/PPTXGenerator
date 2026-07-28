"""Opt-in style quality policy checks for scene readiness reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..pptx_scene_compiler import ScenePptxCompileReport


STYLE_QUALITY_POLICY_SCHEMA = "scene_style_policy"
STYLE_QUALITY_POLICY_VERSION = "0.1"
StyleQualityStatus = Literal["disabled", "passed", "failed"]
StyleQualityFindingCode = Literal[
    "style_quality_warning_count_exceeded",
    "style_quality_unresolved_theme_tokens",
    "style_quality_unresolved_font_tokens",
    "style_quality_unresolved_spacing_tokens",
    "style_quality_fallbacks_used",
    "style_quality_invalid_theme_tokens",
    "style_quality_ambiguous_aliases",
    "style_quality_deprecated_aliases",
    "style_quality_aliases",
    "style_quality_noncanonical_token",
    "style_quality_policy_missing",
    "style_quality_policy_invalid",
]


class SceneStyleQualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StyleQualitySummary(SceneStyleQualityModel):
    style_warning_count: int = 0
    unresolved_theme_token_count: int = 0
    unresolved_font_token_count: int = 0
    unresolved_spacing_token_count: int = 0
    fallback_style_count: int = 0
    invalid_theme_token_count: int = 0
    style_alias_count: int = 0
    deprecated_style_alias_count: int = 0
    ambiguous_style_alias_count: int = 0
    noncanonical_token_count: int = 0


class StyleQualityPolicy(SceneStyleQualityModel):
    max_style_warning_count: int | None = None
    max_unresolved_theme_token_count: int | None = None
    max_unresolved_font_token_count: int | None = None
    max_unresolved_spacing_token_count: int | None = None
    max_fallback_style_count: int | None = None
    max_invalid_theme_token_count: int | None = None
    max_ambiguous_style_alias_count: int | None = None
    max_deprecated_style_alias_count: int | None = None
    allow_style_aliases: bool = True
    allow_deprecated_aliases: bool = False
    allow_ambiguous_aliases: bool = False
    enforce_canonical_tokens_only: bool = False
    enforce_zero_fallbacks: bool = False
    enforce_zero_unresolved_tokens: bool = False


class StyleQualityFixturePolicy(SceneStyleQualityModel):
    profile: str


class SceneStylePolicyFile(SceneStyleQualityModel):
    schema_name: Literal["scene_style_policy"] = STYLE_QUALITY_POLICY_SCHEMA
    schema_version: str = STYLE_QUALITY_POLICY_VERSION
    profiles: dict[str, StyleQualityPolicy] = Field(default_factory=dict)
    fixtures: dict[str, StyleQualityFixturePolicy] = Field(default_factory=dict)

    def policy_for_fixture(self, fixture_id: str, profile_name: str) -> tuple[str, StyleQualityPolicy | None]:
        fixture_policy = self.fixtures.get(fixture_id)
        selected_profile = fixture_policy.profile if fixture_policy is not None else profile_name
        return selected_profile, self.profiles.get(selected_profile)


class StyleQualityFinding(SceneStyleQualityModel):
    code: StyleQualityFindingCode
    severity: Literal["warning", "error"] = "error"
    enforceable: bool = True
    observed: int | bool
    allowed: int | bool | None = None
    fixture_id: str | None = None
    deck_id: str | None = None
    message: str


class StyleQualityResult(SceneStyleQualityModel):
    enabled: bool
    profile: str | None = None
    status: StyleQualityStatus = "disabled"
    passed: bool = True
    summary: StyleQualitySummary = Field(default_factory=StyleQualitySummary)
    findings: list[StyleQualityFinding] = Field(default_factory=list)
    enforceable_count: int = 0
    warning_count: int = 0


def default_style_quality_policy() -> StyleQualityPolicy:
    """Return the built-in style-strict policy used when no policy file is supplied."""

    return StyleQualityPolicy(
        max_style_warning_count=0,
        max_unresolved_theme_token_count=0,
        max_unresolved_font_token_count=0,
        max_unresolved_spacing_token_count=0,
        max_fallback_style_count=0,
        max_invalid_theme_token_count=0,
        max_ambiguous_style_alias_count=0,
        max_deprecated_style_alias_count=0,
        allow_style_aliases=True,
        allow_deprecated_aliases=False,
        allow_ambiguous_aliases=False,
        enforce_zero_fallbacks=True,
        enforce_zero_unresolved_tokens=True,
    )


def load_scene_style_policy(policy_path: str | Path) -> SceneStylePolicyFile:
    return SceneStylePolicyFile.model_validate_json(Path(policy_path).read_text(encoding="utf-8"))


def evaluate_style_quality_policy(
    compile_report: ScenePptxCompileReport,
    *,
    policy: StyleQualityPolicy | None,
    profile: str | None,
    fixture_id: str | None = None,
    deck_id: str | None = None,
) -> StyleQualityResult:
    summary = style_quality_summary_from_compile_report(compile_report)
    if policy is None:
        return StyleQualityResult(enabled=False, profile=profile, status="disabled", passed=True, summary=summary)

    findings: list[StyleQualityFinding] = []
    policy_style_warning_count = summary.style_warning_count
    if policy.allow_style_aliases:
        policy_style_warning_count = max(policy_style_warning_count - summary.style_alias_count, 0)
    _append_threshold_finding(
        findings,
        code="style_quality_warning_count_exceeded",
        observed=policy_style_warning_count,
        allowed=policy.max_style_warning_count,
        fixture_id=fixture_id,
        deck_id=deck_id,
        message="Style warning count exceeded the configured policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="style_quality_unresolved_theme_tokens",
        observed=summary.unresolved_theme_token_count,
        allowed=0 if policy.enforce_zero_unresolved_tokens else policy.max_unresolved_theme_token_count,
        fixture_id=fixture_id,
        deck_id=deck_id,
        message="Unresolved theme tokens exceeded the configured policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="style_quality_unresolved_font_tokens",
        observed=summary.unresolved_font_token_count,
        allowed=0 if policy.enforce_zero_unresolved_tokens else policy.max_unresolved_font_token_count,
        fixture_id=fixture_id,
        deck_id=deck_id,
        message="Unresolved font tokens exceeded the configured policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="style_quality_unresolved_spacing_tokens",
        observed=summary.unresolved_spacing_token_count,
        allowed=0 if policy.enforce_zero_unresolved_tokens else policy.max_unresolved_spacing_token_count,
        fixture_id=fixture_id,
        deck_id=deck_id,
        message="Unresolved spacing tokens exceeded the configured policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="style_quality_fallbacks_used",
        observed=summary.fallback_style_count,
        allowed=0 if policy.enforce_zero_fallbacks else policy.max_fallback_style_count,
        fixture_id=fixture_id,
        deck_id=deck_id,
        message="Fallback style usage exceeded the configured policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="style_quality_invalid_theme_tokens",
        observed=summary.invalid_theme_token_count,
        allowed=policy.max_invalid_theme_token_count,
        fixture_id=fixture_id,
        deck_id=deck_id,
        message="Invalid theme tokens exceeded the configured policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="style_quality_ambiguous_aliases",
        observed=summary.ambiguous_style_alias_count,
        allowed=0 if not policy.allow_ambiguous_aliases else policy.max_ambiguous_style_alias_count,
        fixture_id=fixture_id,
        deck_id=deck_id,
        message="Ambiguous style aliases exceeded the configured policy threshold.",
    )
    _append_threshold_finding(
        findings,
        code="style_quality_deprecated_aliases",
        observed=summary.deprecated_style_alias_count,
        allowed=0 if not policy.allow_deprecated_aliases else policy.max_deprecated_style_alias_count,
        fixture_id=fixture_id,
        deck_id=deck_id,
        message="Deprecated style aliases exceeded the configured policy threshold.",
    )
    if not policy.allow_style_aliases and summary.style_alias_count > 0:
        findings.append(
            StyleQualityFinding(
                code="style_quality_aliases",
                observed=summary.style_alias_count,
                allowed=0,
                fixture_id=fixture_id,
                deck_id=deck_id,
                message="Style aliases are not allowed by the configured policy.",
            )
        )
    if policy.enforce_canonical_tokens_only and summary.noncanonical_token_count > 0:
        findings.append(
            StyleQualityFinding(
                code="style_quality_noncanonical_token",
                observed=summary.noncanonical_token_count,
                allowed=0,
                fixture_id=fixture_id,
                deck_id=deck_id,
                message="Noncanonical style tokens are not allowed by the configured policy.",
            )
        )

    enforceable_count = sum(1 for finding in findings if finding.enforceable)
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    return StyleQualityResult(
        enabled=True,
        profile=profile,
        status="passed" if enforceable_count == 0 else "failed",
        passed=enforceable_count == 0,
        summary=summary,
        findings=sorted(findings, key=lambda item: (item.fixture_id or "", item.code, item.message)),
        enforceable_count=enforceable_count,
        warning_count=warning_count,
    )


def style_quality_summary_from_compile_report(compile_report: ScenePptxCompileReport) -> StyleQualitySummary:
    code_counts = {code: 0 for code in ("theme_token_invalid", "style_token_not_in_canonical_vocabulary")}
    for warning in compile_report.warnings:
        if warning.code in code_counts:
            code_counts[warning.code] += 1
    return StyleQualitySummary(
        style_warning_count=compile_report.style_warning_count,
        unresolved_theme_token_count=compile_report.unresolved_theme_token_count,
        unresolved_font_token_count=compile_report.unresolved_font_token_count,
        unresolved_spacing_token_count=compile_report.unresolved_spacing_token_count,
        fallback_style_count=compile_report.fallback_style_count,
        invalid_theme_token_count=code_counts["theme_token_invalid"],
        style_alias_count=compile_report.style_alias_count,
        deprecated_style_alias_count=compile_report.deprecated_style_alias_count,
        ambiguous_style_alias_count=compile_report.ambiguous_style_alias_count,
        noncanonical_token_count=code_counts["style_token_not_in_canonical_vocabulary"],
    )


def style_quality_findings_to_stable_json(findings: list[StyleQualityFinding]) -> str:
    return json.dumps(
        [finding.model_dump(mode="json", exclude_none=True) for finding in findings],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _append_threshold_finding(
    findings: list[StyleQualityFinding],
    *,
    code: StyleQualityFindingCode,
    observed: int,
    allowed: int | None,
    fixture_id: str | None,
    deck_id: str | None,
    message: str,
) -> None:
    if allowed is None or observed <= allowed:
        return
    findings.append(
        StyleQualityFinding(
            code=code,
            observed=observed,
            allowed=allowed,
            fixture_id=fixture_id,
            deck_id=deck_id,
            message=message,
        )
    )
