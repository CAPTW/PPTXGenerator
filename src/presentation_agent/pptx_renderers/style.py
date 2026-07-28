"""Deterministic style token resolution for the opt-in SceneDeck renderer.

This module is intentionally small. It centralizes the scene compiler's current
fallback behavior for colors, fonts, spacing, fills, strokes, and role-based
text defaults without introducing a full PowerPoint theme/master system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pptx.dml.color import RGBColor

from ..slide_scene import SceneDeck, TextRun, ThemeRef
from .common import SceneCompileWarning, append_warning, hex_to_rgb


_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
STYLE_WARNING_CODES = {
    "theme_token_missing",
    "theme_token_invalid",
    "font_token_missing",
    "font_token_unavailable",
    "spacing_token_missing",
    "color_fallback_used",
    "stroke_style_fallback_used",
    "fill_style_fallback_used",
    "text_style_fallback_used",
    "unsupported_opacity",
    "unsupported_font_feature",
    "style_token_alias_used",
    "style_token_alias_ambiguous",
    "style_token_alias_deprecated",
    "style_token_context_required",
    "style_token_normalized",
    "style_token_not_in_canonical_vocabulary",
}
UNRESOLVED_THEME_WARNING_CODES = {"theme_token_missing", "theme_token_invalid"}
UNRESOLVED_FONT_WARNING_CODES = {"font_token_missing", "font_token_unavailable"}
UNRESOLVED_SPACING_WARNING_CODES = {"spacing_token_missing"}
FALLBACK_STYLE_WARNING_CODES = {
    "color_fallback_used",
    "stroke_style_fallback_used",
    "fill_style_fallback_used",
    "text_style_fallback_used",
}
STYLE_ALIAS_WARNING_CODES = {
    "style_token_alias_used",
    "style_token_alias_deprecated",
    "style_token_normalized",
}
AMBIGUOUS_STYLE_ALIAS_WARNING_CODES = {
    "style_token_alias_ambiguous",
    "style_token_context_required",
}
CANONICAL_COLOR_TOKENS = {
    "background",
    "surface",
    "surface-muted",
    "panel",
    "border",
    "text",
    "text-muted",
    "accent",
    "accent-muted",
    "signal",
    "signal-muted",
    "success",
    "warning",
    "danger",
}
CANONICAL_FONT_TOKENS = {"title", "heading", "body", "caption", "mono"}
CANONICAL_SPACING_TOKENS = {"xs", "sm", "md", "lg", "xl"}
_COLOR_TOKEN_ALIASES: dict[str, dict[str, str]] = {
    "text": {
        "foreground": "text",
        "ink": "text",
        "muted": "text-muted",
        "secondary": "text-muted",
    },
    "fill": {
        "bg": "background",
        "canvas": "background",
        "card": "surface",
        "headline-card": "surface",
        "muted": "surface-muted",
        "panel-bg": "panel",
        "primary": "accent",
        "secondary": "accent-muted",
        "signal-band": "signal",
    },
    "stroke": {
        "foreground": "text",
        "ink": "text",
        "muted": "border",
        "primary": "accent",
        "secondary": "border",
        "signal-band": "signal",
    },
    "accent": {
        "primary": "accent",
        "secondary": "accent-muted",
        "signal-band": "signal",
    },
    "background": {
        "bg": "background",
        "canvas": "background",
        "card": "surface",
        "headline-card": "surface",
        "muted": "surface-muted",
        "panel-bg": "panel",
    },
}
_THEME_TOKEN_MAP_ALIASES: dict[str, tuple[str, ...]] = {
    "accent": ("signal",),
    "bg": ("background",),
    "canvas": ("background", "surface", "panel"),
    "card": ("surface",),
    "foreground": ("text",),
    "headline-card": ("surface",),
    "ink": ("text",),
    "muted": ("text-muted", "surface-muted", "border", "accent-muted"),
    "panel-bg": ("panel",),
    "primary": ("accent",),
    "secondary": ("text-muted", "accent-muted"),
    "signal": ("accent",),
    "signal-band": ("signal",),
}
_FONT_TOKEN_ALIASES = {
    "headline": "title",
    "heading-1": "heading",
    "heading1": "heading",
    "subtitle": "heading",
    "small": "caption",
    "label": "caption",
    "monospace": "mono",
}
_SPACING_TOKEN_ALIASES = {
    "small": "sm",
    "medium": "md",
    "large": "lg",
    "extra-small": "xs",
    "extra-large": "xl",
}


@dataclass(frozen=True)
class NormalizedTokenResult:
    original_token: str
    normalized_token: str
    alias_used: bool = False
    warning_code: str | None = None
    context: str | None = None


@dataclass(frozen=True)
class RoleTextStyle:
    font_token: str
    size_pt: float
    bold: bool = False
    color_token: str = "text"
    fallback_hex: str = "#111827"


@dataclass(frozen=True)
class ResolvedTextStyle:
    font_name: str
    size_pt: float
    bold: bool
    italic: bool
    color_rgb: RGBColor


@dataclass(frozen=True)
class ResolvedFillStyle:
    color_rgb: RGBColor


@dataclass(frozen=True)
class ResolvedStrokeStyle:
    color_rgb: RGBColor
    width_pt: float


@dataclass
class SceneStyleContext:
    theme_tokens: dict[str, str]
    font_tokens: dict[str, str]
    spacing_tokens: dict[str, float]
    default_text_styles: dict[str, RoleTextStyle]
    default_fill_hex: str = "#FFFFFF"
    default_stroke_hex: str = "#94A3B8"
    default_text_hex: str = "#111827"
    warnings: list[SceneCompileWarning] = field(default_factory=list)
    deck_id: str | None = None
    deck_title: str | None = None


def normalize_color_token(
    token: str,
    usage: Literal["text", "fill", "stroke", "accent", "background"],
) -> NormalizedTokenResult:
    """Normalize common scene color aliases without treating them as fallbacks."""

    cleaned = token.strip()
    if cleaned in CANONICAL_COLOR_TOKENS:
        return NormalizedTokenResult(original_token=cleaned, normalized_token=cleaned, context=usage)
    normalized = _COLOR_TOKEN_ALIASES.get(usage, {}).get(cleaned)
    if normalized is None and usage == "fill":
        normalized = _COLOR_TOKEN_ALIASES["background"].get(cleaned)
    if normalized is None:
        return NormalizedTokenResult(original_token=cleaned, normalized_token=cleaned, context=usage)
    return NormalizedTokenResult(
        original_token=cleaned,
        normalized_token=normalized,
        alias_used=True,
        warning_code="style_token_alias_used",
        context=usage,
    )


def normalize_font_token(token: str, role: str | None = None) -> NormalizedTokenResult:
    cleaned = token.strip()
    if cleaned in CANONICAL_FONT_TOKENS:
        return NormalizedTokenResult(original_token=cleaned, normalized_token=cleaned, context=role)
    normalized = _FONT_TOKEN_ALIASES.get(cleaned)
    if normalized is None:
        return NormalizedTokenResult(original_token=cleaned, normalized_token=cleaned, context=role)
    return NormalizedTokenResult(
        original_token=cleaned,
        normalized_token=normalized,
        alias_used=True,
        warning_code="style_token_alias_used",
        context=role,
    )


def normalize_spacing_token(token: str, usage: str | None = None) -> NormalizedTokenResult:
    cleaned = token.strip()
    if cleaned in CANONICAL_SPACING_TOKENS:
        return NormalizedTokenResult(original_token=cleaned, normalized_token=cleaned, context=usage)
    normalized = _SPACING_TOKEN_ALIASES.get(cleaned)
    if normalized is None:
        return NormalizedTokenResult(original_token=cleaned, normalized_token=cleaned, context=usage)
    return NormalizedTokenResult(
        original_token=cleaned,
        normalized_token=normalized,
        alias_used=True,
        warning_code="style_token_alias_used",
        context=usage,
    )


def build_scene_style_context(scene_deck: SceneDeck, warnings: list[SceneCompileWarning]) -> SceneStyleContext:
    return SceneStyleContext(
        theme_tokens=_theme_tokens_with_canonical_aliases(scene_deck.theme_tokens),
        font_tokens={
            "title": "Aptos Display",
            "heading": "Aptos Display",
            "body": "Aptos",
            "caption": "Aptos",
            "mono": "Aptos Mono",
        },
        spacing_tokens={
            "xxs": 0.04,
            "xs": 0.08,
            "sm": 0.12,
            "md": 0.22,
            "lg": 0.32,
            "xl": 0.48,
        },
        default_text_styles={
            "title": RoleTextStyle(font_token="title", size_pt=24.0, bold=True),
            "claim": RoleTextStyle(font_token="body", size_pt=16.0, bold=True),
            "main-message": RoleTextStyle(font_token="body", size_pt=14.0),
            "caption": RoleTextStyle(font_token="caption", size_pt=9.0),
            "footer": RoleTextStyle(font_token="caption", size_pt=9.0),
            "annotation": RoleTextStyle(font_token="caption", size_pt=9.0),
            "body": RoleTextStyle(font_token="body", size_pt=11.0),
        },
        warnings=warnings,
        deck_id=scene_deck.deck_id,
        deck_title=scene_deck.deck_title,
    )


def resolve_theme_color(
    style_context: SceneStyleContext,
    ref: ThemeRef | None,
    default_hex: str,
    *,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
    usage: str,
) -> RGBColor:
    hex_color = resolve_theme_hex(
        style_context,
        ref,
        default_hex,
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        usage=usage,
    )
    return hex_to_rgb(hex_color)


def resolve_theme_hex(
    style_context: SceneStyleContext,
    ref: ThemeRef | None,
    default_hex: str,
    *,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
    usage: str,
) -> str:
    normalized_default = _normalize_hex(
        default_hex,
        style_context.default_text_hex,
        style_context=style_context,
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        usage=usage,
        warning_code="theme_token_invalid",
    )
    if ref is None:
        return normalized_default
    token = ref.token
    token_value = style_context.theme_tokens.get(token)
    if token_value is None:
        token_result = normalize_color_token(ref.token, _color_usage_for_normalization(usage))
        token = token_result.normalized_token
        if token_result.alias_used:
            _append_token_alias_warning(
                style_context,
                token_result=token_result,
                slide_number=slide_number,
                slide_id=slide_id,
                object_id=object_id,
                token_kind="color",
            )
        token_value = style_context.theme_tokens.get(token)
    fallback_hex = ref.fallback_hex or normalized_default
    if token_value is None:
        fallback = _normalize_hex(
            fallback_hex,
            normalized_default,
            style_context=style_context,
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            usage=usage,
            warning_code="theme_token_invalid",
        )
        append_warning(
            style_context.warnings,
            code="theme_token_missing",
            severity="warning",
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            message=f"Theme token {ref.token!r} was not found for {usage}; fallback color was used.",
            details={
                "token": ref.token,
                "normalized_token": token,
                "fallback_hex": fallback,
                "usage": usage,
            },
        )
        _append_style_fallback(
            style_context,
            usage=usage,
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            code=_fallback_code_for_usage(usage),
            message=f"Fallback color was used for {usage}.",
            details={"token": ref.token, "normalized_token": token, "fallback_hex": fallback},
        )
        return fallback
    return _normalize_hex(
        token_value,
        fallback_hex,
        style_context=style_context,
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        usage=usage,
        warning_code="theme_token_invalid",
        token=token,
    )


def resolve_font(
    style_context: SceneStyleContext,
    font_token: str | None,
    fallback_token: str,
    *,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
) -> str:
    token = font_token or fallback_token
    token_result = normalize_font_token(token, role=fallback_token)
    if token_result.alias_used:
        _append_token_alias_warning(
            style_context,
            token_result=token_result,
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            token_kind="font",
        )
    token = token_result.normalized_token
    font_name = style_context.font_tokens.get(token)
    if font_name:
        return font_name
    fallback_name = style_context.font_tokens.get(fallback_token) or style_context.font_tokens["body"]
    append_warning(
        style_context.warnings,
        code="font_token_missing",
        severity="warning",
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        message=f"Font token {token!r} was not found; fallback font was used.",
        details={"font_token": token, "fallback_token": fallback_token, "fallback_font": fallback_name},
    )
    _append_style_fallback(
        style_context,
        usage="text",
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        code="text_style_fallback_used",
        message="Fallback text style was used because a font token was unresolved.",
        details={"font_token": token, "fallback_font": fallback_name},
    )
    return fallback_name


def resolve_spacing(
    style_context: SceneStyleContext,
    spacing_token: str | None,
    default_inches: float,
    *,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
) -> float:
    if spacing_token is None:
        return default_inches
    token_result = normalize_spacing_token(spacing_token)
    if token_result.alias_used:
        _append_token_alias_warning(
            style_context,
            token_result=token_result,
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            token_kind="spacing",
        )
    spacing_token = token_result.normalized_token
    value = style_context.spacing_tokens.get(spacing_token)
    if value is not None:
        return value
    append_warning(
        style_context.warnings,
        code="spacing_token_missing",
        severity="warning",
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        message=f"Spacing token {spacing_token!r} was not found; fallback spacing was used.",
        details={"spacing_token": spacing_token, "fallback_inches": round(default_inches, 6)},
    )
    return default_inches


def resolve_text_style(
    style_context: SceneStyleContext,
    source_run: TextRun,
    role: str,
    *,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
) -> ResolvedTextStyle:
    default_style = style_context.default_text_styles.get(role)
    if default_style is None:
        default_style = style_context.default_text_styles["body"]
        append_warning(
            style_context.warnings,
            code="text_style_fallback_used",
            severity="warning",
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            message=f"Text role {role!r} has no style default; body style was used.",
            details={"role": role, "fallback_role": "body"},
        )
    font_name = resolve_font(
        style_context,
        source_run.font_token,
        default_style.font_token,
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
    )
    color_ref = source_run.color or ThemeRef(token=default_style.color_token, fallback_hex=default_style.fallback_hex)
    color = resolve_theme_color(
        style_context,
        color_ref,
        default_style.fallback_hex,
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        usage="text",
    )
    return ResolvedTextStyle(
        font_name=font_name,
        size_pt=source_run.size_pt or default_style.size_pt,
        bold=source_run.bold or default_style.bold,
        italic=source_run.italic,
        color_rgb=color,
    )


def resolve_fill_style(
    style_context: SceneStyleContext,
    ref: ThemeRef | None,
    default_hex: str | None = None,
    *,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
) -> ResolvedFillStyle:
    return ResolvedFillStyle(
        color_rgb=resolve_theme_color(
            style_context,
            ref,
            default_hex or style_context.default_fill_hex,
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            usage="fill",
        )
    )


def resolve_stroke_style(
    style_context: SceneStyleContext,
    ref: ThemeRef | None,
    *,
    width_pt: float = 1.0,
    default_hex: str | None = None,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
) -> ResolvedStrokeStyle:
    return ResolvedStrokeStyle(
        color_rgb=resolve_theme_color(
            style_context,
            ref,
            default_hex or style_context.default_stroke_hex,
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=object_id,
            usage="stroke",
        ),
        width_pt=width_pt,
    )


def scene_style_warning_counts(warnings: list[SceneCompileWarning]) -> dict[str, int]:
    style_warnings = [warning for warning in warnings if warning.code in STYLE_WARNING_CODES]
    return {
        "style_warning_count": len(style_warnings),
        "unresolved_theme_token_count": sum(1 for warning in style_warnings if warning.code in UNRESOLVED_THEME_WARNING_CODES),
        "unresolved_font_token_count": sum(1 for warning in style_warnings if warning.code in UNRESOLVED_FONT_WARNING_CODES),
        "unresolved_spacing_token_count": sum(1 for warning in style_warnings if warning.code in UNRESOLVED_SPACING_WARNING_CODES),
        "fallback_style_count": sum(1 for warning in style_warnings if warning.code in FALLBACK_STYLE_WARNING_CODES),
        "style_alias_count": sum(1 for warning in style_warnings if warning.code in STYLE_ALIAS_WARNING_CODES),
        "deprecated_style_alias_count": sum(1 for warning in style_warnings if warning.code == "style_token_alias_deprecated"),
        "ambiguous_style_alias_count": sum(
            1 for warning in style_warnings if warning.code in AMBIGUOUS_STYLE_ALIAS_WARNING_CODES
        ),
    }


def _normalize_hex(
    value: str,
    fallback_hex: str,
    *,
    style_context: SceneStyleContext,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
    usage: str,
    warning_code: str,
    token: str | None = None,
) -> str:
    candidate = value.upper()
    if _HEX_COLOR_RE.match(candidate):
        return candidate
    fallback = fallback_hex.upper() if _HEX_COLOR_RE.match(fallback_hex.upper()) else "#111827"
    append_warning(
        style_context.warnings,
        code=warning_code,  # type: ignore[arg-type]
        severity="warning",
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        message=f"Invalid hex color {value!r} for {usage}; fallback color was used.",
        details={"token": token, "invalid_hex": value, "fallback_hex": fallback, "usage": usage},
    )
    _append_style_fallback(
        style_context,
        usage=usage,
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        code=_fallback_code_for_usage(usage),
        message=f"Fallback color was used for {usage}.",
        details={"token": token, "fallback_hex": fallback},
    )
    return fallback


def _fallback_code_for_usage(usage: str) -> str:
    if usage == "stroke":
        return "stroke_style_fallback_used"
    if usage == "fill":
        return "fill_style_fallback_used"
    if usage == "text":
        return "text_style_fallback_used"
    return "color_fallback_used"


def _theme_tokens_with_canonical_aliases(theme_tokens: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for token, color in sorted(theme_tokens.items()):
        cleaned = token.strip()
        if not cleaned:
            continue
        normalized[cleaned] = color.upper()
        for alias in _THEME_TOKEN_MAP_ALIASES.get(cleaned, ()):
            normalized.setdefault(alias, color.upper())
    return {key: normalized[key] for key in sorted(normalized)}


def _color_usage_for_normalization(usage: str) -> Literal["text", "fill", "stroke", "accent", "background"]:
    if usage in {"text", "fill", "stroke", "accent", "background"}:
        return usage  # type: ignore[return-value]
    return "fill"


def _append_token_alias_warning(
    style_context: SceneStyleContext,
    *,
    token_result: NormalizedTokenResult,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
    token_kind: str,
) -> None:
    append_warning(
        style_context.warnings,
        code=token_result.warning_code or "style_token_alias_used",  # type: ignore[arg-type]
        severity="warning",
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        message=(
            f"{token_kind.title()} style token {token_result.original_token!r} "
            f"was normalized to {token_result.normalized_token!r}."
        ),
        details={
            "token_kind": token_kind,
            "token": token_result.original_token,
            "normalized_token": token_result.normalized_token,
            "context": token_result.context,
        },
    )


def _append_style_fallback(
    style_context: SceneStyleContext,
    *,
    usage: str,
    slide_number: int,
    slide_id: str,
    object_id: str | None,
    code: str,
    message: str,
    details: dict[str, Any],
) -> None:
    append_warning(
        style_context.warnings,
        code=code,  # type: ignore[arg-type]
        severity="warning",
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=object_id,
        message=message,
        details={"usage": usage, **details},
    )
