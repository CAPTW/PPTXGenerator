"""Deterministic SlideIR to SceneDeck adapter for renderer-facing inspection.

This adapter is pure data transformation. It does not import python-pptx and it
does not alter the existing Blueprint -> SlideIR -> PPTX compiler path.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .slide_ir import (
    IRRect,
    SlideIRBackgroundLayer,
    SlideIRDocument,
    SlideIRObject,
    SlideIRSafeAreaMask,
    SlideIRSlide,
)
from .slide_scene import (
    BackgroundLayer,
    BulletItem,
    Callout,
    ChartSeries,
    DividerLine,
    FitPolicy,
    ImageCrop,
    ImageObject,
    NativeChart,
    NativeTable,
    Rect,
    SceneDeck,
    SceneObject,
    SceneSlide,
    Shape,
    TableCell,
    TextBox,
    TextRun,
    ThemeRef,
)


SUPPORTED_LAYOUT_FAMILIES: tuple[str, ...] = (
    "cover",
    "summary",
    "worked-example",
    "comparison",
    "process-flow",
    "appendix-reference",
)
_DEFAULT_THEME_TOKENS = {"canvas": "#FFFFFF", "ink": "#111827", "signal": "#C2410C", "muted": "#94A3B8"}
_MESSAGE_PANEL_BOUNDS = {
    "worked-example:case-insight": Rect(x=6.4, y=1.65, width=2.95, height=1.4),
    "worked-example:why-it-matters": Rect(x=0.55, y=6.35, width=4.35, height=0.7),
    "comparison:comparison-takeaway": Rect(x=7.0, y=1.72, width=2.3, height=1.3),
    "process-flow:takeaway": Rect(x=0.55, y=5.45, width=12.233333, height=0.8),
    "process-flow:timeline-point": Rect(x=0.55, y=4.95, width=12.233333, height=0.75),
    "process-flow:roadmap": Rect(x=0.55, y=1.6, width=3.5, height=1.25),
}


def adapt_slide_ir_document_to_scene_deck(slide_ir: SlideIRDocument) -> SceneDeck:
    """Convert a SlideIR document into deterministic renderer-facing SceneDeck JSON."""

    theme_tokens = _theme_tokens(slide_ir)
    typography_sizes = _typography_sizes(slide_ir)
    deck_warnings: list[str] = []
    slides: list[SceneSlide] = []
    for slide in sorted(slide_ir.slides, key=lambda item: item.slide_number):
        scene_slide = _adapt_slide(slide, slide_ir, theme_tokens, typography_sizes)
        if scene_slide.layout_family not in SUPPORTED_LAYOUT_FAMILIES:
            deck_warnings.append(
                _adapter_warning(
                    "unsupported_layout_family",
                    slide_number=slide.slide_number,
                    layout_family=slide.layout_family,
                )
            )
        slides.append(scene_slide)

    return SceneDeck(
        deck_id=_stable_deck_id(slide_ir.deck_title),
        deck_title=slide_ir.deck_title,
        slide_width=round(slide_ir.slide_width_in, 6),
        slide_height=round(slide_ir.slide_height_in, 6),
        theme_tokens=theme_tokens,
        slides=slides,
        warnings=deck_warnings,
    )


def scene_deck_adapter_summary(scene_deck: SceneDeck) -> dict[str, Any]:
    """Return deterministic adapter counts for inspection and tests."""

    object_kind_counts: Counter[str] = Counter()
    motif_kind_counts: Counter[str] = Counter()
    warning_code_counts: Counter[str] = Counter()
    slides: list[dict[str, Any]] = []

    for warning in scene_deck.warnings:
        code = _adapter_warning_code(warning)
        if code is not None:
            warning_code_counts[code] += 1

    for slide in scene_deck.slides:
        for scene_object in slide.objects:
            object_kind_counts[scene_object.kind] += 1
        for motif in slide.background.motifs:
            motif_kind_counts[motif.kind] += 1
        slide_warning_codes = [code for code in (_adapter_warning_code(warning) for warning in slide.warnings) if code is not None]
        warning_code_counts.update(slide_warning_codes)
        slides.append(
            {
                "slide_number": slide.slide_number,
                "slide_id": slide.slide_id,
                "layout_family": slide.layout_family,
                "object_kind_counts": dict(sorted(Counter(item.kind for item in slide.objects).items())),
                "background_motif_kind_counts": dict(sorted(Counter(item.kind for item in slide.background.motifs).items())),
                "warning_codes": slide_warning_codes,
            }
        )

    return {
        "slide_count": len(scene_deck.slides),
        "object_kind_counts": dict(sorted(object_kind_counts.items())),
        "background_motif_kind_counts": dict(sorted(motif_kind_counts.items())),
        "warning_code_counts": dict(sorted(warning_code_counts.items())),
        "slides": slides,
    }


def summarize_scene_deck_adapter(scene_deck: SceneDeck) -> list[str]:
    summary = scene_deck_adapter_summary(scene_deck)
    object_count = sum(summary["object_kind_counts"].values())
    motif_count = sum(summary["background_motif_kind_counts"].values())
    placeholder_count = int(summary["warning_code_counts"].get("placeholder_shape_emitted", 0))
    warning_count = sum(summary["warning_code_counts"].values())
    return [
        "SCENE_ADAPTER "
        f"slides={summary['slide_count']} "
        f"objects={object_count} "
        f"motifs={motif_count} "
        f"warnings={warning_count} "
        f"placeholders={placeholder_count}"
    ]


def _adapt_slide(
    slide: SlideIRSlide,
    slide_ir: SlideIRDocument,
    theme_tokens: dict[str, str],
    typography_sizes: dict[str, float],
) -> SceneSlide:
    warnings: list[str] = list(slide.layout_warnings)
    if slide.layout_family not in SUPPORTED_LAYOUT_FAMILIES:
        warnings.append(_adapter_warning("unsupported_layout_family", layout_family=slide.layout_family))

    seen_ids: set[str] = set()
    objects = _inferred_support_objects_for_slide(
        slide,
        slide_ir=slide_ir,
        theme_tokens=theme_tokens,
        warnings=warnings,
        seen_ids=seen_ids,
    )
    background = _adapt_background(slide, slide_ir, theme_tokens, warnings)

    reading_order = 1
    for index, ir_object in enumerate(slide.objects, start=len(objects) + 1):
        object_id = _unique_object_id(ir_object.object_id, seen_ids, warnings)
        mapped = _adapt_object(
            ir_object,
            object_id=object_id,
            slide=slide,
            slide_ir=slide_ir,
            z_order=index,
            reading_order=reading_order,
            theme_tokens=theme_tokens,
            typography_sizes=typography_sizes,
            warnings=warnings,
        )
        if isinstance(mapped, (TextBox, Callout)):
            reading_order += 1
        objects.append(mapped)

    return SceneSlide(
        slide_id=slide.slide_id,
        slide_number=slide.slide_number,
        layout_family=slide.layout_family,
        slide_role=_enum_value(slide.slide_role),
        visual_type=_enum_value(slide.visual_type),
        deck_mode=_enum_value(slide.deck_mode),
        layout_pattern_id=slide.layout_pattern_id,
        background=background,
        objects=objects,
        notes=list(slide.notes),
        warnings=warnings,
    )


def _adapt_object(
    ir_object: SlideIRObject,
    *,
    object_id: str,
    slide: SlideIRSlide,
    slide_ir: SlideIRDocument,
    z_order: int,
    reading_order: int,
    theme_tokens: dict[str, str],
    typography_sizes: dict[str, float],
    warnings: list[str],
) -> SceneObject:
    if ir_object.kind in {"text", "annotation", "evidence"} and ir_object.text:
        callout = _adapt_callout_object(
            ir_object,
            object_id=object_id,
            slide=slide,
            z_order=z_order,
            reading_order=reading_order,
            theme_tokens=theme_tokens,
            typography_sizes=typography_sizes,
            warnings=warnings,
        )
        if callout is not None:
            return callout
        return _adapt_text_object(
            ir_object,
            object_id=object_id,
            z_order=z_order,
            reading_order=reading_order,
            theme_tokens=theme_tokens,
            typography_sizes=typography_sizes,
            warnings=warnings,
        )
    if ir_object.kind == "visual":
        visual_type = _enum_value(slide.visual_type)
        if visual_type == "table":
            table = _adapt_native_table(ir_object, object_id, slide, slide_ir, z_order, theme_tokens)
            if table is not None:
                return table
        if visual_type == "chart":
            chart = _adapt_native_chart(ir_object, object_id, slide, slide_ir, z_order, theme_tokens)
            if chart is not None:
                return chart
        if visual_type in {"document-crop", "photo", "image"}:
            image = _adapt_image_object(ir_object, object_id, slide, slide_ir, z_order)
            if image is not None:
                return image
        warnings.append(
            _adapter_warning(
                "placeholder_shape_emitted",
                object_id=ir_object.object_id,
                role=f"{visual_type}-placeholder",
                source_kind=ir_object.kind,
                visual_type=visual_type,
            )
        )
        return _placeholder_shape(ir_object, object_id, z_order, theme_tokens, role=f"{visual_type}-placeholder")

    warnings.append(
        _adapter_warning(
            "placeholder_shape_emitted",
            object_id=ir_object.object_id,
            role="unsupported",
            source_kind=ir_object.kind,
            slot=ir_object.slot,
        )
    )
    return _placeholder_shape(ir_object, object_id, z_order, theme_tokens, role="unsupported")


def _adapt_text_object(
    ir_object: SlideIRObject,
    *,
    object_id: str,
    z_order: int,
    reading_order: int,
    theme_tokens: dict[str, str],
    typography_sizes: dict[str, float],
    warnings: list[str],
) -> TextBox:
    bullet_payload = ir_object.payload.get("bullet_items")
    if isinstance(bullet_payload, list) and bullet_payload:
        bullets = _bullet_items_from_payload(bullet_payload, ir_object.object_id, theme_tokens, typography_sizes, warnings)
        if bullets:
            return TextBox(
                object_id=object_id,
                role=_text_role(ir_object),
                bounds=_rect(ir_object.bounds),
                z_order=z_order,
                reading_order=reading_order,
                bullet_list=bullets,
                fit=FitPolicy(mode="fail"),
            )
    if bullet_payload is not None:
        warnings.append(_adapter_warning("ambiguous_bullet_mapping", object_id=ir_object.object_id))

    return TextBox(
        object_id=object_id,
        role=_text_role(ir_object),
        bounds=_rect(ir_object.bounds),
        z_order=z_order,
        reading_order=reading_order,
        runs=[
            TextRun(
                text=ir_object.text or "",
                font_token=_font_token_for_slot(ir_object.slot),
                size_pt=typography_sizes.get(_font_token_for_slot(ir_object.slot)),
                color=_theme_ref("ink", theme_tokens, "#111827"),
            )
        ],
        fit=FitPolicy(mode="fail"),
    )


def _adapt_callout_object(
    ir_object: SlideIRObject,
    *,
    object_id: str,
    slide: SlideIRSlide,
    z_order: int,
    reading_order: int,
    theme_tokens: dict[str, str],
    typography_sizes: dict[str, float],
    warnings: list[str],
) -> Callout | None:
    if ir_object.slot != "main-message" or not ir_object.text:
        return None
    spec = _callout_spec_for_slide(slide)
    if spec is None:
        if slide.layout_family in {"comparison", "process-flow"}:
            warnings.append(
                _adapter_warning(
                    "ambiguous_callout_mapping",
                    object_id=ir_object.object_id,
                    layout_family=slide.layout_family,
                    visual_type=_enum_value(slide.visual_type),
                    slide_role=_enum_value(slide.slide_role),
                )
            )
        return None
    return Callout(
        object_id=object_id,
        bounds=spec["bounds"],
        z_order=z_order,
        reading_order=reading_order,
        title=TextRun(
            text=spec["title"],
            font_token="title",
            size_pt=typography_sizes.get("caption", max(typography_sizes.get("body", 11.0), 11.0)),
            bold=True,
            color=_theme_ref("ink", theme_tokens, "#111827"),
        ),
        body=[
            TextRun(
                text=ir_object.text,
                font_token="body",
                size_pt=typography_sizes.get("body"),
                color=_theme_ref("ink", theme_tokens, "#111827"),
            )
        ],
        accent=_theme_ref("signal", theme_tokens, "#C2410C"),
        fit=FitPolicy(mode="wrap"),
    )


def _adapt_native_table(
    ir_object: SlideIRObject,
    object_id: str,
    slide: SlideIRSlide,
    slide_ir: SlideIRDocument,
    z_order: int,
    theme_tokens: dict[str, str],
) -> NativeTable | None:
    record = _first_visual_record(slide, slide_ir)
    table_data = getattr(getattr(record, "spec", None), "table", None) if record is not None else None
    columns = list(getattr(table_data, "columns", []) or [])
    rows = list(getattr(table_data, "rows", []) or [])
    if not columns:
        return None
    headers = [
        TableCell(
            runs=[TextRun(text=str(column.label), font_token="body", color=_theme_ref("ink", theme_tokens, "#111827"))],
            align=_alignment_value(getattr(column, "alignment", None)),
        )
        for column in columns
    ]
    body_rows: list[list[TableCell]] = []
    for row in rows:
        values = getattr(row, "values", {}) or {}
        body_rows.append(
            [
                TableCell(
                    runs=[
                        TextRun(
                            text=str(values.get(column.key, "")),
                            font_token="body",
                            color=_theme_ref("ink", theme_tokens, "#111827"),
                        )
                    ],
                    align=_alignment_value(getattr(column, "alignment", None)),
                )
                for column in columns
            ]
        )
    return NativeTable(
        object_id=object_id,
        bounds=_rect(ir_object.bounds),
        z_order=z_order,
        headers=headers,
        rows=body_rows,
        fit=FitPolicy(mode="fail"),
    )


def _adapt_native_chart(
    ir_object: SlideIRObject,
    object_id: str,
    slide: SlideIRSlide,
    slide_ir: SlideIRDocument,
    z_order: int,
    theme_tokens: dict[str, str],
) -> NativeChart | None:
    record = _first_visual_record(slide, slide_ir)
    chart_data = getattr(getattr(record, "spec", None), "chart", None) if record is not None else None
    if chart_data is None:
        return None
    categories = [str(item) for item in getattr(chart_data, "categories", []) or []]
    source_series = list(getattr(chart_data, "series", []) or [])
    if not categories or not source_series:
        return None
    series: list[ChartSeries] = []
    for item in source_series:
        color_token = getattr(item, "color_token", None)
        series.append(
            ChartSeries(
                series_id=str(getattr(item, "series_id", "")),
                label=str(getattr(item, "label", "")),
                values=[float(value) for value in getattr(item, "values", [])],
                color=_theme_ref(str(color_token), theme_tokens, "#111827") if color_token else None,
            )
        )
    chart_type = _enum_value(getattr(chart_data, "chart_kind", "bar"))
    if chart_type not in {"bar", "column", "line", "scatter"}:
        return None
    return NativeChart(
        object_id=object_id,
        chart_type=chart_type,  # type: ignore[arg-type]
        bounds=_rect(ir_object.bounds),
        z_order=z_order,
        categories=categories,
        series=series,
        theme="scene-adapter",
    )


def _adapt_image_object(
    ir_object: SlideIRObject,
    object_id: str,
    slide: SlideIRSlide,
    slide_ir: SlideIRDocument,
    z_order: int,
) -> ImageObject | None:
    asset = _first_asset_record(slide, slide_ir)
    asset_id = getattr(asset, "asset_id", None)
    if not asset_id:
        return None
    return ImageObject(
        object_id=object_id,
        asset_id=str(asset_id),
        source_path=getattr(asset, "local_path", None),
        bounds=_rect(ir_object.bounds),
        z_order=z_order,
        crop=ImageCrop(mode="contain"),
        alt_text=getattr(asset, "crop_subject_hint", None) or slide.title,
    )


def _bullet_items_from_payload(
    payload: list[object],
    source_object_id: str,
    theme_tokens: dict[str, str],
    typography_sizes: dict[str, float],
    warnings: list[str],
) -> list[BulletItem]:
    bullets: list[BulletItem] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict) or "text" not in item:
            warnings.append(
                _adapter_warning(
                    "ambiguous_bullet_mapping",
                    object_id=source_object_id,
                    item_index=index,
                    reason="unstructured-item",
                )
            )
            return []
        level = item.get("level", 0)
        if not isinstance(level, int) or level < 0:
            warnings.append(
                _adapter_warning(
                    "ambiguous_bullet_mapping",
                    object_id=source_object_id,
                    item_index=index,
                    reason="invalid-level",
                )
            )
            return []
        bullets.append(
            BulletItem(
                runs=[
                    TextRun(
                        text=str(item["text"]),
                        font_token="body",
                        size_pt=typography_sizes.get("body"),
                        color=_theme_ref("ink", theme_tokens, "#111827"),
                    )
                ],
                level=level,
                bullet_style=str(item.get("bullet_style", "bullet")),  # type: ignore[arg-type]
            )
        )
    return bullets


def _adapt_background(
    slide: SlideIRSlide,
    slide_ir: SlideIRDocument,
    theme_tokens: dict[str, str],
    warnings: list[str],
) -> BackgroundLayer:
    motifs: list[Shape | DividerLine] = []
    style_prior = slide_ir.style_prior
    if style_prior is None:
        return BackgroundLayer(fill=_theme_ref("canvas", theme_tokens, "#FFFFFF"))
    for layer in style_prior.background_layers:
        if layer.scope == "appendix" and _enum_value(slide.deck_mode) != "appendix":
            continue
        motif = _background_motif_for_layer(slide, slide_ir, theme_tokens, layer, style_prior.safe_area_masks, warnings)
        if motif is not None:
            motifs.append(motif)
    return BackgroundLayer(fill=_theme_ref("canvas", theme_tokens, "#FFFFFF"), motifs=motifs)


def _background_motif_for_layer(
    slide: SlideIRSlide,
    slide_ir: SlideIRDocument,
    theme_tokens: dict[str, str],
    layer: SlideIRBackgroundLayer,
    masks: list[SlideIRSafeAreaMask],
    warnings: list[str],
) -> Shape | DividerLine | None:
    mask = _style_prior_mask(
        masks,
        layer.safe_area_mask_id,
        applies_to="background" if layer.layer_type != "motif" else "motif",
    )
    top_in = mask.top_in if mask is not None else 0.5
    right_in = mask.right_in if mask is not None else 0.5
    bottom_in = mask.bottom_in if mask is not None else 0.45
    left_in = mask.left_in if mask is not None else 0.5

    slide_width = round(slide_ir.slide_width_in, 6)
    slide_height = round(slide_ir.slide_height_in, 6)
    object_id = f"{slide.slide_id}:bg:{layer.layer_id}"
    color = _theme_ref(layer.color_token, theme_tokens, theme_tokens.get(layer.color_token, "#C2410C"))

    if layer.shape_hint == "full-bleed":
        warnings.append(_adapter_warning("inferred_background_shape", slide_id=slide.slide_id, layer_id=layer.layer_id))
        return Shape(
            object_id=object_id,
            role="background-motif",
            shape_type="rect",
            bounds=Rect(x=0.0, y=0.0, width=slide_width, height=slide_height),
            z_order=0,
            fill=color,
        )
    if layer.shape_hint == "right-edge":
        width = round(min(max(right_in * 0.9, 0.22), slide_width * 0.18), 6)
        left = round(slide_width - width, 6)
        warnings.append(_adapter_warning("inferred_background_shape", slide_id=slide.slide_id, layer_id=layer.layer_id))
        return Shape(
            object_id=object_id,
            role="background-motif",
            shape_type="rect",
            bounds=Rect(x=left, y=0.0, width=width, height=slide_height),
            z_order=0,
            fill=color,
        )
    if layer.shape_hint == "corner-accent":
        width = round(min(max((left_in + right_in) * 0.42, 0.8), slide_width * 0.22), 6)
        height = round(min(max((top_in + bottom_in) * 0.38, 0.62), slide_height * 0.2), 6)
        left = round(slide_width - width - (right_in * 0.16), 6)
        top = round(slide_height - height - (bottom_in * 0.18), 6)
        warnings.append(_adapter_warning("inferred_background_shape", slide_id=slide.slide_id, layer_id=layer.layer_id))
        return Shape(
            object_id=object_id,
            role="background-motif",
            shape_type="ellipse",
            bounds=Rect(x=left, y=top, width=width, height=height),
            z_order=0,
            fill=color,
        )
    if layer.shape_hint in {"top-band", "bottom-band"}:
        extent = top_in if layer.shape_hint == "top-band" else bottom_in
        height = round(min(max(extent * 0.72, 0.16), slide_height * 0.26), 6)
        top = 0.0 if layer.shape_hint == "top-band" else round(slide_height - height, 6)
        if height <= 0.36:
            center_y = round(top + (height / 2.0), 6)
            return DividerLine(
                object_id=object_id,
                x1=0.0,
                y1=center_y,
                x2=slide_width,
                y2=center_y,
                z_order=0,
                stroke=color,
                width_pt=max(round(height * 72.0, 6), 1.0),
            )
        warnings.append(
            _adapter_warning(
                "ambiguous_divider_mapping",
                slide_id=slide.slide_id,
                layer_id=layer.layer_id,
                shape_hint=layer.shape_hint,
                inferred_as="shape",
            )
        )
        warnings.append(_adapter_warning("inferred_background_shape", slide_id=slide.slide_id, layer_id=layer.layer_id))
        return Shape(
            object_id=object_id,
            role="background-motif",
            shape_type="rect",
            bounds=Rect(x=0.0, y=top, width=slide_width, height=height),
            z_order=0,
            fill=color,
        )
    warnings.append(
        _adapter_warning(
            "unsupported_motif_pattern",
            slide_id=slide.slide_id,
            layer_id=layer.layer_id,
            layer_type=layer.layer_type,
            shape_hint=layer.shape_hint,
        )
    )
    return None


def _inferred_support_objects_for_slide(
    slide: SlideIRSlide,
    *,
    slide_ir: SlideIRDocument,
    theme_tokens: dict[str, str],
    warnings: list[str],
    seen_ids: set[str],
) -> list[SceneObject]:
    objects: list[SceneObject] = []
    if slide.layout_family == "cover":
        object_id = _unique_object_id(f"{slide.slide_id}:cover-band", seen_ids, warnings)
        objects.append(
            Shape(
                object_id=object_id,
                role="cover-band",
                shape_type="rounded_rect",
                bounds=Rect(x=0.55, y=1.05, width=round(slide_ir.slide_width_in - 1.1, 6), height=0.28),
                z_order=1,
                fill=_theme_ref("signal", theme_tokens, "#C2410C"),
            )
        )
    if slide.layout_family == "summary":
        object_id = _unique_object_id(f"{slide.slide_id}:summary-card", seen_ids, warnings)
        objects.append(
            Shape(
                object_id=object_id,
                role="summary-card",
                shape_type="rounded_rect",
                bounds=Rect(x=0.55, y=1.65, width=round(slide_ir.slide_width_in - 1.1, 6), height=1.5),
                z_order=1,
                fill=_theme_ref("signal", theme_tokens, "#C2410C"),
            )
        )
    return objects


def _placeholder_shape(
    ir_object: SlideIRObject,
    object_id: str,
    z_order: int,
    theme_tokens: dict[str, str],
    *,
    role: str,
) -> Shape:
    return Shape(
        object_id=object_id,
        role=role,
        shape_type="rect",
        bounds=_rect(ir_object.bounds),
        z_order=z_order,
        fill=_theme_ref("canvas", theme_tokens, "#FFFFFF"),
        stroke=_theme_ref("muted", theme_tokens, "#94A3B8"),
    )


def _theme_tokens(slide_ir: SlideIRDocument) -> dict[str, str]:
    tokens: dict[str, str] = dict(_DEFAULT_THEME_TOKENS)
    design_system = slide_ir.compile_context.design_system if slide_ir.compile_context is not None else None
    for item in getattr(design_system, "color_tokens", []) or []:
        token = str(getattr(item, "token", "")).strip()
        color = getattr(item, "hex", None)
        if token and isinstance(color, str) and color.startswith("#"):
            tokens[token] = color
    style_prior = slide_ir.style_prior
    for seed in getattr(style_prior, "palette_seeds", []) or []:
        token = str(getattr(seed, "token", "")).strip()
        color = getattr(seed, "hex", None)
        if token and isinstance(color, str) and color.startswith("#"):
            tokens[token] = color
    return {key: tokens[key] for key in sorted(tokens)}


def _typography_sizes(slide_ir: SlideIRDocument) -> dict[str, float]:
    sizes: dict[str, float] = {}
    design_system = slide_ir.compile_context.design_system if slide_ir.compile_context is not None else None
    for item in getattr(design_system, "typography_tokens", []) or []:
        token = str(getattr(item, "token", "")).strip()
        size = getattr(item, "size_pt", None)
        if token and isinstance(size, (int, float)) and size > 0:
            sizes[token] = float(size)
    return sizes


def _first_visual_record(slide: SlideIRSlide, slide_ir: SlideIRDocument) -> Any | None:
    visuals = slide_ir.compile_context.visuals if slide_ir.compile_context is not None else []
    matches = [
        record
        for record in visuals
        if getattr(record.spec, "slide_id", None) == slide.slide_id or getattr(record.spec, "slide_number", None) == slide.slide_number
    ]
    return sorted(matches, key=lambda item: str(getattr(item.spec, "spec_id", "")))[0] if matches else None


def _first_asset_record(slide: SlideIRSlide, slide_ir: SlideIRDocument) -> Any | None:
    assets = slide_ir.compile_context.assets if slide_ir.compile_context is not None else []
    matches = [
        asset
        for asset in assets
        if getattr(asset, "slide_id", None) == slide.slide_id or getattr(asset, "slide_number", None) == slide.slide_number
    ]
    return sorted(matches, key=lambda item: str(getattr(item, "asset_id", "")))[0] if matches else None


def _unique_object_id(object_id: str, seen_ids: set[str], warnings: list[str]) -> str:
    if object_id not in seen_ids:
        seen_ids.add(object_id)
        return object_id
    suffix = 2
    while f"{object_id}-{suffix}" in seen_ids:
        suffix += 1
    deduped = f"{object_id}-{suffix}"
    seen_ids.add(deduped)
    warnings.append(_adapter_warning("duplicate_object_id_resolved", original_object_id=object_id, emitted_object_id=deduped))
    return deduped


def _rect(bounds: IRRect) -> Rect:
    return Rect(x=round(bounds.left, 6), y=round(bounds.top, 6), width=round(bounds.width, 6), height=round(bounds.height, 6))


def _theme_ref(token: str, theme_tokens: dict[str, str], fallback_hex: str) -> ThemeRef:
    return ThemeRef(token=token, fallback_hex=theme_tokens.get(token, fallback_hex))


def _text_role(ir_object: SlideIRObject) -> str:
    if ir_object.slot == "main-message":
        return "body"
    if ir_object.kind == "annotation":
        return "annotation"
    if ir_object.kind == "evidence":
        return "evidence"
    return ir_object.slot


def _font_token_for_slot(slot: str) -> str:
    if slot == "title":
        return "title"
    if slot in {"footer", "caption"}:
        return "caption"
    return "body"


def _alignment_value(value: object) -> str:
    text = _enum_value(value)
    return "center" if text == "center" else "left"


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _stable_deck_id(deck_title: str) -> str:
    slug = "-".join("".join(char.lower() if char.isalnum() else " " for char in deck_title).split())
    return slug or "scene-deck"


def supported_layout_families() -> tuple[str, ...]:
    return SUPPORTED_LAYOUT_FAMILIES


def _adapter_warning(code: str, **details: object) -> str:
    return json.dumps({"code": code, "details": {key: details[key] for key in sorted(details)}}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _adapter_warning_code(warning: str) -> str | None:
    try:
        payload = json.loads(warning)
    except Exception:
        return None
    code = payload.get("code")
    return code if isinstance(code, str) and code else None


def _style_prior_mask(
    masks: list[SlideIRSafeAreaMask],
    mask_id: str | None,
    *,
    applies_to: str,
) -> SlideIRSafeAreaMask | None:
    if mask_id is not None:
        for mask in masks:
            if mask.mask_id == mask_id:
                return mask
    return next((mask for mask in masks if mask.applies_to == applies_to), None)


def _callout_spec_for_slide(slide: SlideIRSlide) -> dict[str, Any] | None:
    layout_family = slide.layout_family
    visual_type = _enum_value(slide.visual_type)
    slide_role = _enum_value(slide.slide_role)
    if layout_family == "worked-example":
        if visual_type == "photo":
            return {"title": "Case insight", "bounds": _MESSAGE_PANEL_BOUNDS["worked-example:case-insight"]}
        return {"title": "Why it matters", "bounds": _MESSAGE_PANEL_BOUNDS["worked-example:why-it-matters"]}
    if layout_family == "appendix-reference":
        if visual_type in {"document-crop", "photo", "chart"}:
            return {"title": "Why it matters", "bounds": _MESSAGE_PANEL_BOUNDS["worked-example:why-it-matters"]}
        return {"title": "Comparison takeaway", "bounds": _MESSAGE_PANEL_BOUNDS["comparison:comparison-takeaway"]}
    if layout_family == "comparison":
        return {"title": "Comparison takeaway", "bounds": _MESSAGE_PANEL_BOUNDS["comparison:comparison-takeaway"]}
    if layout_family == "process-flow":
        if visual_type == "timeline":
            return {"title": "Timeline point", "bounds": _MESSAGE_PANEL_BOUNDS["process-flow:timeline-point"]}
        if slide_role == "process" and visual_type in {"process", "decision-path"}:
            return {"title": "Roadmap", "bounds": _MESSAGE_PANEL_BOUNDS["process-flow:roadmap"]}
        return {"title": "Takeaway", "bounds": _MESSAGE_PANEL_BOUNDS["process-flow:takeaway"]}
    return None
