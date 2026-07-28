"""Bounded style-prior providers for non-structural look-and-feel hints."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from .compat.presentation_contracts import (
    CanonicalGenerationProfile,
    ContractModel,
    DeckMode,
    DesignSystem,
    SlideRole,
    VisualType,
)
from .slide_ir import (
    SlideIRBackgroundLayer,
    SlideIRDocument,
    SlideIRHeroVisualSuggestion,
    SlideIRMotifAssetSuggestion,
    SlideIRPaletteSeed,
    SlideIRSafeAreaMask,
    SlideIRStylePrior,
    SlideIRVisualPlacementHint,
)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        value = item.strip()
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    normalized = value.strip().lstrip("#")
    if len(normalized) == 3:
        normalized = "".join(char * 2 for char in normalized)
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def _rgb_to_hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02X}{green:02X}{blue:02X}"


def _blend_hex(base: str, accent: str, ratio: float) -> str:
    ratio = max(0.0, min(ratio, 1.0))
    base_rgb = _hex_to_rgb(base)
    accent_rgb = _hex_to_rgb(accent)
    blended = tuple(round((base_channel * (1.0 - ratio)) + (accent_channel * ratio)) for base_channel, accent_channel in zip(base_rgb, accent_rgb))
    return _rgb_to_hex(*blended)


class StylePriorSlideContext(ContractModel):
    """Compact structural context for one slide."""

    slide_number: int
    slide_id: str
    slide_role: SlideRole
    visual_type: VisualType
    deck_mode: DeckMode
    layout_family: str
    section: str = ""


class StylePriorContext(ContractModel):
    """Deterministic context shared with style-prior providers."""

    deck_title: str
    slide_ratio: str
    theme_name: str | None = None
    brand_name: str | None = None
    reference_source_family: str | None = None
    generation_mode: str = "unspecified"
    color_tokens: dict[str, str] = Field(default_factory=dict)
    safe_area: dict[str, Any] | None = None
    style_tokens: list[str] = Field(default_factory=list)
    reusable_visual_motifs: list[str] = Field(default_factory=list)
    brand_token_set: list[str] = Field(default_factory=list)
    slides: list[StylePriorSlideContext] = Field(default_factory=list)


@runtime_checkable
class StylePriorProvider(Protocol):
    """Provider interface for bounded style priors."""

    def build(self, context: StylePriorContext) -> SlideIRStylePrior:
        ...


def build_style_prior_context(
    *,
    slide_ir: SlideIRDocument,
    design_system: DesignSystem | None,
    canonical_generation_profile: CanonicalGenerationProfile | None,
) -> StylePriorContext:
    color_tokens = {token.token: token.hex for token in design_system.color_tokens} if design_system is not None else {}
    safe_area_model = canonical_generation_profile.safe_area if canonical_generation_profile is not None else None
    safe_area = (
        safe_area_model.model_dump(mode="json", exclude_none=True)
        if safe_area_model is not None
        else None
    )
    return StylePriorContext(
        deck_title=slide_ir.deck_title,
        slide_ratio=slide_ir.slide_ratio,
        theme_name=design_system.theme_name if design_system is not None else None,
        brand_name=design_system.brand_name if design_system is not None else None,
        reference_source_family=(
            getattr(canonical_generation_profile, "reference_source_family", None)
            if canonical_generation_profile is not None
            else None
        ),
        generation_mode=(
            canonical_generation_profile.mode.value if canonical_generation_profile is not None else "unspecified"
        ),
        color_tokens=color_tokens,
        safe_area=safe_area,
        style_tokens=list(canonical_generation_profile.style_tokens) if canonical_generation_profile is not None else [],
        reusable_visual_motifs=(
            list(canonical_generation_profile.reusable_visual_motifs) if canonical_generation_profile is not None else []
        ),
        brand_token_set=list(canonical_generation_profile.brand_token_set) if canonical_generation_profile is not None else [],
        slides=[
            StylePriorSlideContext(
                slide_number=slide.slide_number,
                slide_id=slide.slide_id,
                slide_role=slide.slide_role,
                visual_type=slide.visual_type,
                deck_mode=slide.deck_mode,
                layout_family=slide.layout_family,
                section=slide.section,
            )
            for slide in slide_ir.slides
        ],
    )


def _safe_area_value(safe_area: dict[str, Any] | None, key: str, fallback: float) -> float:
    if safe_area is None:
        return fallback
    value = safe_area.get(key, fallback)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(numeric, 0.1)


def _context_color(context: StylePriorContext, token: str, fallback: str) -> str:
    return context.color_tokens.get(token, fallback).upper()


class StubStylePriorProvider:
    """Deterministic provider that emits decorative cues only."""

    provider_name = "stub-style-prior"

    def build(self, context: StylePriorContext) -> SlideIRStylePrior:
        canvas = _context_color(context, "canvas", "#F8FAFC")
        signal = _context_color(context, "signal", "#C2410C")
        ink = _context_color(context, "ink", "#1F2937")

        palette_seeds = [
            SlideIRPaletteSeed(
                token="style-prior-background-accent",
                hex=_blend_hex(canvas, signal, 0.16),
                usage="Low-contrast background wash.",
            ),
            SlideIRPaletteSeed(
                token="style-prior-motif",
                hex=_blend_hex(ink, signal, 0.42),
                usage="Motif ribbon or corner accent.",
            ),
            SlideIRPaletteSeed(
                token="style-prior-hero-overlay",
                hex=_blend_hex(canvas, ink, 0.18),
                usage="Hero-image overlay or appendix band.",
            ),
        ]

        safe_area_masks = [
            SlideIRSafeAreaMask(
                mask_id="style-prior-background-mask",
                applies_to="background",
                top_in=_safe_area_value(context.safe_area, "top_in", 0.5),
                right_in=_safe_area_value(context.safe_area, "right_in", 0.5),
                bottom_in=_safe_area_value(context.safe_area, "bottom_in", 0.45),
                left_in=_safe_area_value(context.safe_area, "left_in", 0.5),
                notes=["Background layers stay in a broad decorative lane only."],
            ),
            SlideIRSafeAreaMask(
                mask_id="style-prior-motif-mask",
                applies_to="motif",
                top_in=_safe_area_value(context.safe_area, "top_in", 0.5),
                right_in=max(_safe_area_value(context.safe_area, "right_in", 0.5), 0.75),
                bottom_in=_safe_area_value(context.safe_area, "bottom_in", 0.45),
                left_in=_safe_area_value(context.safe_area, "left_in", 0.5),
                notes=["Motifs avoid the main reading column."],
            ),
            SlideIRSafeAreaMask(
                mask_id="style-prior-hero-mask",
                applies_to="hero-visual",
                top_in=max(_safe_area_value(context.safe_area, "top_in", 0.5), 0.55),
                right_in=max(_safe_area_value(context.safe_area, "right_in", 0.5), 0.65),
                bottom_in=max(_safe_area_value(context.safe_area, "bottom_in", 0.45), 0.5),
                left_in=max(_safe_area_value(context.safe_area, "left_in", 0.5), 0.55),
                notes=["Hero visuals can expand, but only under the existing layout-safe mask."],
            ),
        ]

        motif_cues = context.reusable_visual_motifs[:2] or ["Geometric ribbon cue derived from the deck signal color."]
        motif_assets = [
            SlideIRMotifAssetSuggestion(
                motif_id=f"style-prior-motif-{index + 1}",
                cue=cue,
                source_kind="stub",
                placement_hint_id="style-prior-primary-visual",
            )
            for index, cue in enumerate(motif_cues)
        ]

        hero_slide = next(
            (
                slide
                for slide in context.slides
                if slide.deck_mode != DeckMode.APPENDIX and slide.visual_type not in {VisualType.TEXT, VisualType.QUOTE}
            ),
            context.slides[0] if context.slides else None,
        )
        hero_visual_suggestions = []
        if hero_slide is not None:
            hero_visual_suggestions.append(
                SlideIRHeroVisualSuggestion(
                    slide_number=hero_slide.slide_number,
                    slide_id=hero_slide.slide_id,
                    cue=motif_assets[0].cue if motif_assets else "Editorial hero visual cue with soft overlay.",
                    placement_hint_id="style-prior-primary-visual",
                    notes=["Advisory only; existing SlideIR geometry remains authoritative."],
                )
            )

        texture_cues = [
            token.split(":", 1)[1]
            for token in context.style_tokens
            if ":" in token and token.split(":", 1)[0] in {"texture", "illustration"}
        ]
        if not texture_cues:
            texture_cues = ["Restrained texture or illustration cue limited to background-safe zones."]

        return SlideIRStylePrior(
            provider_name=self.provider_name,
            provider_mode="stub",
            palette_seeds=palette_seeds,
            safe_area_masks=safe_area_masks,
            background_layers=[
                SlideIRBackgroundLayer(
                    layer_id="style-prior-background-wash",
                    scope="deck",
                    layer_type="solid-fill",
                    shape_hint="full-bleed",
                    color_token="style-prior-background-accent",
                    opacity=0.12,
                    safe_area_mask_id="style-prior-background-mask",
                    cue="Soft deck-wide background wash.",
                ),
                SlideIRBackgroundLayer(
                    layer_id="style-prior-right-motif",
                    scope="deck",
                    layer_type="motif",
                    shape_hint="right-edge",
                    color_token="style-prior-motif",
                    opacity=0.08,
                    safe_area_mask_id="style-prior-motif-mask",
                    cue=motif_assets[0].cue if motif_assets else "Right-edge motif accent.",
                ),
                SlideIRBackgroundLayer(
                    layer_id="style-prior-appendix-band",
                    scope="appendix",
                    layer_type="band",
                    shape_hint="bottom-band",
                    color_token="style-prior-hero-overlay",
                    opacity=0.10,
                    safe_area_mask_id="style-prior-background-mask",
                    cue="Appendix continuity band.",
                ),
            ],
            motif_assets=motif_assets,
            hero_visual_suggestions=hero_visual_suggestions,
            visual_placement_hints=[
                SlideIRVisualPlacementHint(
                    hint_id="style-prior-primary-visual",
                    target_slot="primary_visual",
                    anchor_preference="right-band",
                    chrome_treatment="soft-frame",
                    safe_area_mask_id="style-prior-hero-mask",
                    cue="Favor a right-edge emphasis without changing the slot geometry.",
                    notes=["Placement hints annotate the visual slot; they do not change bounds or reading order."],
                )
            ],
            texture_cues=_dedupe(texture_cues),
            notes=[
                "Stub provider emits style suggestions only; no image-generation backend is active yet.",
                "Allowed influence is limited to tokens, masks, decorative background layers, and visual placement hints.",
                "Disallowed influence remains text box geometry, chart geometry, reading order, and content hierarchy.",
            ],
        )


class NullStylePriorProvider:
    """Provider used by regression tests to disable style-prior output."""

    def build(self, context: StylePriorContext) -> SlideIRStylePrior:
        return SlideIRStylePrior(
            provider_name="null-style-prior",
            provider_mode="stub",
            notes=["Style-prior output disabled for structural regression coverage."],
        )


DEFAULT_STYLE_PRIOR_PROVIDER: StylePriorProvider = StubStylePriorProvider()
