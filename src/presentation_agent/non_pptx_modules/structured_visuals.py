"""Deterministic structured-visual worker for slide-native charts, tables, and infographics."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from ..compat.legacy_non_pptx import (
    AssetKind,
    AssetManifest,
    AssetRequest,
    AssetRequests,
    AssetRecord,
    AssetStatus,
    Blueprint,
    BlueprintSlide,
    ChartKind,
    ContractModel,
    DeckConstitution,
    DesignSystem,
    FrameFit,
    LayoutLibrary,
    LayoutPattern,
    ProductionMode,
    ReadingDirection,
    SlideLedger,
    SlideLedgerEntry,
    StageStatus,
    TableAlignment,
    TypographyToken,
    VisualSourcePreference,
    VisualType,
    VizChartData,
    VizChartSeries,
    VizDensityBand,
    VizDiagramConnector,
    VizDiagramData,
    VizDiagramNode,
    VizManifest,
    VizMetricItem,
    VizMetricSummaryData,
    VizSpecSet,
    VizReadability,
    VizRecord,
    VizSpec,
    VizStatus,
    VizStyleProfile,
    VizTableColumn,
    VizTableData,
    VizTableRow,
    save_state_file,
)


CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720
MARGIN_X = 72
MARGIN_Y = 56

CHART_SIMPLIFY_CATEGORY_LIMIT = 4
CHART_SPLIT_CATEGORY_LIMIT = 5
CHART_SIMPLIFY_SERIES_LIMIT = 2
CHART_SIMPLIFIED_SERIES_TARGET = 1
CHART_POINT_LIMIT = 8
CHART_SPLIT_POINT_LIMIT = 10
CHART_LABEL_LIMIT = 18
CHART_SPLIT_LABEL_LIMIT = 28
TABLE_SIMPLIFY_ROW_LIMIT = 4
TABLE_SPLIT_ROW_LIMIT = 5
TABLE_SIMPLIFY_COLUMN_LIMIT = 3
TABLE_SPLIT_COLUMN_LIMIT = 4
TABLE_CELL_LIMIT = 12
TABLE_SPLIT_CELL_LIMIT = 16
TABLE_LABEL_LIMIT = 24
TABLE_SPLIT_LABEL_LIMIT = 36
DIAGRAM_SIMPLIFY_NODE_LIMIT = 4
DIAGRAM_SPLIT_NODE_LIMIT = 5
DIAGRAM_SIMPLIFY_BRANCH_LIMIT = 2
DIAGRAM_SPLIT_BRANCH_LIMIT = 3
DIAGRAM_SIMPLIFY_CALLOUT_LIMIT = 1
DIAGRAM_SPLIT_CALLOUT_LIMIT = 2
DIAGRAM_LABEL_LIMIT = 24
DIAGRAM_SPLIT_LABEL_LIMIT = 36
METRIC_SIMPLIFY_ITEM_LIMIT = 3
METRIC_SPLIT_ITEM_LIMIT = 4
METRIC_LABEL_LIMIT = 28
METRIC_SPLIT_LABEL_LIMIT = 40


@dataclass(frozen=True)
class DensityDecision:
    node_count: int
    label_count: int
    frame_fit: FrameFit
    split_recommendation: str | None
    density_score: int
    density_reason_codes: list[str]
    density_band: VizDensityBand
    simplification_required: bool
    split_required: bool


class StructuredVisualOutputs(ContractModel):
    viz_manifest: VizManifest
    asset_manifest: AssetManifest
    slide_ledger: SlideLedger


def _slugify(text: str) -> str:
    letters: list[str] = []
    previous_dash = False
    for char in text.lower():
        if char.isalnum():
            letters.append(char)
            previous_dash = False
        elif not previous_dash:
            letters.append("-")
            previous_dash = True
    return "".join(letters).strip("-") or "visual"


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _token_map(design_system: DesignSystem) -> dict[str, str]:
    return {token.token: token.hex for token in design_system.color_tokens}


def _typography_map(design_system: DesignSystem) -> dict[str, TypographyToken]:
    return {token.token: token for token in design_system.typography_tokens}


def _truncate(text: str, limit: int = 28) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _stable_score(text: str, *, floor: int, ceiling: int) -> int:
    span = max(1, ceiling - floor)
    total = sum((index + 1) * ord(char) for index, char in enumerate(text))
    return floor + (total % (span + 1))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _density_band(split_required: bool, simplification_required: bool) -> VizDensityBand:
    if split_required:
        return VizDensityBand.HIGH
    if simplification_required:
        return VizDensityBand.MEDIUM
    return VizDensityBand.LOW


def _chart_label_lengths(chart: VizChartData) -> list[int]:
    labels = [*chart.categories, *(series.label for series in chart.series)]
    if chart.unit_label:
        labels.append(chart.unit_label)
    return [len(label) for label in labels if label]


def _table_label_lengths(table: VizTableData) -> list[int]:
    labels = [*(column.label for column in table.columns)]
    for row in table.rows:
        labels.extend(row.values.values())
    return [len(label) for label in labels if label]


def _diagram_label_lengths(diagram: VizDiagramData) -> list[int]:
    labels: list[str] = []
    for node in diagram.nodes:
        labels.append(node.label)
        if node.supporting_text:
            labels.append(node.supporting_text)
    for connector in diagram.connectors:
        if connector.label:
            labels.append(connector.label)
    return [len(label) for label in labels if label]


def _metric_label_lengths(metric_summary: VizMetricSummaryData) -> list[int]:
    labels: list[str] = []
    for metric in metric_summary.metrics:
        labels.extend([metric.label, metric.value])
        if metric.detail:
            labels.append(metric.detail)
    if metric_summary.footer:
        labels.append(metric_summary.footer)
    return [len(label) for label in labels if label]


def _diagram_branch_count(diagram: VizDiagramData) -> int:
    outbound: dict[str, int] = {}
    for connector in diagram.connectors:
        outbound[connector.source_id] = outbound.get(connector.source_id, 0) + 1
    return max(outbound.values(), default=0)


def _diagram_callout_count(diagram: VizDiagramData) -> int:
    return sum(1 for node in diagram.nodes if node.supporting_text) + sum(1 for connector in diagram.connectors if connector.label)


def _fallback_variant_description(spec: VizSpec) -> str:
    if spec.chart is not None:
        return "Single-series direct-label chart with reduced categories."
    if spec.table is not None:
        return "Trimmed lookup table with reduced rows and columns."
    if spec.diagram is not None:
        return "Reduced-node diagram with collapsed secondary branches."
    if spec.metric_summary is not None:
        return "Trimmed metric summary with only the primary metrics."
    return "Compile-safe structured visual fallback."


def _chart_density_decision(spec: VizSpec) -> DensityDecision:
    assert spec.chart is not None
    category_count = len(spec.chart.categories)
    series_count = len(spec.chart.series)
    point_count = category_count * series_count
    max_label_length = max(_chart_label_lengths(spec.chart), default=0)
    score = 0
    reasons: list[str] = []
    simplification_required = False
    split_required = False

    if category_count > CHART_SIMPLIFY_CATEGORY_LIMIT:
        reasons.append("too_many_categories")
        score += 2
        simplification_required = True
        if category_count > CHART_SPLIT_CATEGORY_LIMIT:
            score += 1
            split_required = True
    if series_count > CHART_SIMPLIFY_SERIES_LIMIT:
        reasons.append("too_many_series")
        score += 3
        simplification_required = True
        split_required = True
    if point_count > CHART_POINT_LIMIT:
        score += 1
        simplification_required = True
        if point_count > CHART_SPLIT_POINT_LIMIT:
            split_required = True
    if max_label_length > CHART_LABEL_LIMIT:
        reasons.append("labels_too_long")
        score += 1
        simplification_required = True
        if max_label_length > CHART_SPLIT_LABEL_LIMIT:
            score += 1
            split_required = True

    if split_required:
        reasons.extend(["requires_simplification", "requires_split"])
        frame_fit = FrameFit.SPLIT_RECOMMENDED
        split_recommendation = "Reduce chart categories or series, or route the evidence into a simpler comparison or table fallback."
    elif simplification_required:
        reasons.append("requires_simplification")
        frame_fit = FrameFit.TIGHT
        split_recommendation = None
    else:
        reasons.append("density_within_limits")
        frame_fit = FrameFit.FIT
        split_recommendation = None

    return DensityDecision(
        node_count=point_count,
        label_count=category_count + series_count,
        frame_fit=frame_fit,
        split_recommendation=split_recommendation,
        density_score=score,
        density_reason_codes=_dedupe(reasons),
        density_band=_density_band(split_required, simplification_required),
        simplification_required=simplification_required,
        split_required=split_required,
    )


def _table_density_decision(spec: VizSpec) -> DensityDecision:
    assert spec.table is not None
    row_count = len(spec.table.rows)
    column_count = len(spec.table.columns)
    cell_count = row_count * column_count
    max_label_length = max(_table_label_lengths(spec.table), default=0)
    score = 0
    reasons: list[str] = []
    simplification_required = False
    split_required = False

    if row_count > TABLE_SIMPLIFY_ROW_LIMIT:
        reasons.append("too_many_table_rows")
        score += 1
        simplification_required = True
        if row_count > TABLE_SPLIT_ROW_LIMIT:
            score += 1
            split_required = True
    if column_count > TABLE_SIMPLIFY_COLUMN_LIMIT:
        reasons.append("too_many_table_columns")
        score += 1
        simplification_required = True
        if column_count > TABLE_SPLIT_COLUMN_LIMIT:
            score += 1
            split_required = True
    if cell_count > TABLE_CELL_LIMIT:
        reasons.append("too_many_table_cells")
        score += 2
        simplification_required = True
        if cell_count > TABLE_SPLIT_CELL_LIMIT:
            score += 1
            split_required = True
    if max_label_length > TABLE_LABEL_LIMIT:
        reasons.append("labels_too_long")
        score += 1
        simplification_required = True
        if max_label_length > TABLE_SPLIT_LABEL_LIMIT:
            score += 1
            split_required = True

    if split_required:
        reasons.extend(["requires_simplification", "requires_split"])
        frame_fit = FrameFit.SPLIT_RECOMMENDED
        split_recommendation = "Reduce rows or columns, or move the overflow into appendix lookup support."
    elif simplification_required:
        reasons.append("requires_simplification")
        frame_fit = FrameFit.TIGHT
        split_recommendation = None
    else:
        reasons.append("density_within_limits")
        frame_fit = FrameFit.FIT
        split_recommendation = None

    return DensityDecision(
        node_count=cell_count,
        label_count=row_count + column_count,
        frame_fit=frame_fit,
        split_recommendation=split_recommendation,
        density_score=score,
        density_reason_codes=_dedupe(reasons),
        density_band=_density_band(split_required, simplification_required),
        simplification_required=simplification_required,
        split_required=split_required,
    )


def _diagram_density_decision(spec: VizSpec) -> DensityDecision:
    assert spec.diagram is not None
    node_count = len(spec.diagram.nodes)
    branch_count = _diagram_branch_count(spec.diagram)
    callout_count = _diagram_callout_count(spec.diagram)
    max_label_length = max(_diagram_label_lengths(spec.diagram), default=0)
    score = 0
    reasons: list[str] = []
    simplification_required = False
    split_required = False

    if node_count > DIAGRAM_SIMPLIFY_NODE_LIMIT:
        reasons.append("too_many_nodes")
        score += 2
        simplification_required = True
        if node_count > DIAGRAM_SPLIT_NODE_LIMIT:
            score += 1
            split_required = True
    if branch_count > DIAGRAM_SIMPLIFY_BRANCH_LIMIT:
        reasons.append("too_many_branches")
        score += 2
        simplification_required = True
        if branch_count > DIAGRAM_SPLIT_BRANCH_LIMIT:
            score += 1
            split_required = True
    if callout_count > DIAGRAM_SIMPLIFY_CALLOUT_LIMIT:
        reasons.append("too_many_callouts")
        score += 1
        simplification_required = True
        if callout_count > DIAGRAM_SPLIT_CALLOUT_LIMIT:
            score += 1
            split_required = True
    if max_label_length > DIAGRAM_LABEL_LIMIT:
        reasons.append("labels_too_long")
        score += 1
        simplification_required = True
        if max_label_length > DIAGRAM_SPLIT_LABEL_LIMIT:
            score += 1
            split_required = True

    if split_required:
        reasons.extend(["requires_simplification", "requires_split"])
        frame_fit = FrameFit.SPLIT_RECOMMENDED
        split_recommendation = "Reduce nodes or branches, or move the overflow into a split comparison, process, or timeline fallback."
    elif simplification_required:
        reasons.append("requires_simplification")
        frame_fit = FrameFit.TIGHT
        split_recommendation = None
    else:
        reasons.append("density_within_limits")
        frame_fit = FrameFit.FIT
        split_recommendation = None

    return DensityDecision(
        node_count=node_count,
        label_count=node_count + len(spec.diagram.connectors) + callout_count,
        frame_fit=frame_fit,
        split_recommendation=split_recommendation,
        density_score=score,
        density_reason_codes=_dedupe(reasons),
        density_band=_density_band(split_required, simplification_required),
        simplification_required=simplification_required,
        split_required=split_required,
    )


def _metric_density_decision(spec: VizSpec) -> DensityDecision:
    assert spec.metric_summary is not None
    metric_count = len(spec.metric_summary.metrics)
    max_label_length = max(_metric_label_lengths(spec.metric_summary), default=0)
    score = 0
    reasons: list[str] = []
    simplification_required = False
    split_required = False

    if metric_count > METRIC_SIMPLIFY_ITEM_LIMIT:
        reasons.append("too_many_metrics")
        score += 1
        simplification_required = True
        if metric_count > METRIC_SPLIT_ITEM_LIMIT:
            score += 1
            split_required = True
    if max_label_length > METRIC_LABEL_LIMIT:
        reasons.append("labels_too_long")
        score += 1
        simplification_required = True
        if max_label_length > METRIC_SPLIT_LABEL_LIMIT:
            score += 1
            split_required = True

    if split_required:
        reasons.extend(["requires_simplification", "requires_split"])
        frame_fit = FrameFit.SPLIT_RECOMMENDED
        split_recommendation = "Limit the summary to the few metrics that directly support the slide message."
    elif simplification_required:
        reasons.append("requires_simplification")
        frame_fit = FrameFit.TIGHT
        split_recommendation = None
    else:
        reasons.append("density_within_limits")
        frame_fit = FrameFit.FIT
        split_recommendation = None

    return DensityDecision(
        node_count=metric_count,
        label_count=metric_count + (1 if spec.metric_summary.footer else 0),
        frame_fit=frame_fit,
        split_recommendation=split_recommendation,
        density_score=score,
        density_reason_codes=_dedupe(reasons),
        density_band=_density_band(split_required, simplification_required),
        simplification_required=simplification_required,
        split_required=split_required,
    )


def _evaluate_density_policy(spec: VizSpec) -> DensityDecision:
    if spec.chart is not None:
        return _chart_density_decision(spec)
    if spec.table is not None:
        return _table_density_decision(spec)
    if spec.diagram is not None:
        return _diagram_density_decision(spec)
    if spec.metric_summary is not None:
        return _metric_density_decision(spec)
    return DensityDecision(
        node_count=0,
        label_count=0,
        frame_fit=FrameFit.FIT,
        split_recommendation=None,
        density_score=0,
        density_reason_codes=["density_within_limits"],
        density_band=VizDensityBand.LOW,
        simplification_required=False,
        split_required=False,
    )


def _readability_from_decision(
    current_decision: DensityDecision,
    *,
    audit_decision: DensityDecision | None = None,
    simplification_applied: bool = False,
    split_applied: bool = False,
    fallback_variant_generated: bool = False,
    fallback_reason_codes: list[str] | None = None,
) -> VizReadability:
    density_audit = current_decision if audit_decision is None else audit_decision
    return VizReadability(
        reading_path="left-to-right with one dominant focal point",
        node_count=current_decision.node_count,
        label_count=current_decision.label_count,
        frame_fit=current_decision.frame_fit,
        split_recommendation=density_audit.split_recommendation,
        simplified=simplification_applied,
        density_score=density_audit.density_score,
        density_reason_codes=list(density_audit.density_reason_codes),
        fallback_reason_codes=[] if fallback_reason_codes is None else list(fallback_reason_codes),
        density_band=density_audit.density_band,
        simplification_applied=simplification_applied,
        split_applied=split_applied,
        fallback_variant_generated=fallback_variant_generated,
    )


def _apply_density_policy(spec: VizSpec) -> VizSpec:
    decision = _evaluate_density_policy(spec)
    simpler_variant = spec.simpler_variant
    if decision.simplification_required or decision.split_required:
        simpler_variant = simpler_variant or _fallback_variant_description(spec)
    return spec.model_copy(
        update={
            "readability": _readability_from_decision(decision),
            "simpler_variant": simpler_variant,
        }
    )


def _needs_compile_safe_simplification(spec: VizSpec) -> bool:
    readability = spec.readability
    if readability is None:
        return False
    reason_codes = set(readability.density_reason_codes)
    return "requires_simplification" in reason_codes or "requires_split" in reason_codes


def _density_audit_summary(readability: VizReadability | None) -> str | None:
    if readability is None:
        return None
    reason_text = ", ".join(readability.density_reason_codes)
    summary = f"Density audit: band={readability.density_band.value}; score={readability.density_score}; reasons={reason_text}."
    if readability.fallback_reason_codes:
        summary += f" Fallback reasons: {', '.join(readability.fallback_reason_codes)}."
    return summary


def _content_labels(slide: BlueprintSlide, request: AssetRequest, minimum: int = 3, maximum: int = 7) -> list[str]:
    labels = _dedupe(
        [
            *slide.required_evidence_assets,
            *(ref.label for ref in request.source_material_refs),
            slide.title,
            slide.one_line_takeaway,
        ]
    )
    labels = [_truncate(label, 30) for label in labels]
    defaults_by_type = {
        VisualType.CHART: ["Current", "Transition", "Target"],
        VisualType.TABLE: ["Item", "Evidence", "Status"],
        VisualType.PROCESS: ["Input", "Decision", "Action", "Outcome"],
        VisualType.TIMELINE: ["Now", "Near term", "Transition", "Target state"],
        VisualType.HIERARCHY: ["Owner", "Workstream A", "Workstream B", "Support"],
        VisualType.COMPARISON: ["Baseline", "Recommended", "Tradeoff"],
        VisualType.FRAMEWORK: ["Axis A", "Axis B", "Axis C", "Axis D"],
        VisualType.INFOGRAPHIC: ["Problem", "Mechanism", "Proof", "Action"],
        VisualType.METRIC_SUMMARY: ["Thesis", "Sources", "Mode"],
        VisualType.DECISION_PATH: ["Trigger", "Check", "Decision", "Commit"],
        VisualType.TEXT: ["Claim", "Support", "Action"],
        VisualType.QUOTE: ["Quote", "Speaker", "Why it matters"],
    }
    while len(labels) < minimum:
        defaults = defaults_by_type.get(slide.visual_type, ["Point 1", "Point 2", "Point 3"])
        labels.append(defaults[len(labels) % len(defaults)])
    return labels[:maximum]


def _style_profile(design_system: DesignSystem) -> VizStyleProfile:
    return VizStyleProfile(
        color_tokens=[token.token for token in design_system.color_tokens],
        typography_tokens=[token.token for token in design_system.typography_tokens],
        chart_rules=design_system.chart_rules,
        table_rules=design_system.table_rules,
        highlight_rules=design_system.highlight_rules,
    )


def _chart_data(slide: BlueprintSlide, request: AssetRequest) -> VizChartData:
    categories = _content_labels(slide, request, minimum=3, maximum=6)
    primary_values = [
        float(_stable_score(f"{slide.main_message}|{label}|primary", floor=38, ceiling=92))
        for label in categories
    ]
    secondary_values = [
        max(18.0, float(value - _stable_score(f"{slide.title}|{label}|secondary", floor=6, ceiling=18)))
        for label, value in zip(categories, primary_values, strict=False)
    ]
    return VizChartData(
        chart_kind=ChartKind.BAR,
        categories=categories,
        series=[
            VizChartSeries(series_id="current", label="Current", values=secondary_values, color_token="ink"),
            VizChartSeries(series_id="target", label="Target", values=primary_values, color_token="signal"),
        ],
        unit_label="index",
        direct_labels=True,
    )


def _table_data(slide: BlueprintSlide, request: AssetRequest) -> VizTableData:
    rows = _content_labels(slide, request, minimum=3, maximum=8)
    columns = [
        VizTableColumn(key="item", label="Item", alignment=TableAlignment.LEFT),
        VizTableColumn(key="evidence", label="Evidence", alignment=TableAlignment.LEFT),
        VizTableColumn(key="status", label="Status", alignment=TableAlignment.CENTER),
    ]
    table_rows: list[VizTableRow] = []
    for index, row in enumerate(rows, start=1):
        source_label = request.source_material_refs[(index - 1) % len(request.source_material_refs)].label if request.source_material_refs else "Deck rule"
        table_rows.append(
            VizTableRow(
                values={
                    "item": row,
                    "evidence": _truncate(source_label, 24),
                    "status": "Primary" if index == 1 else "Support",
                },
                highlight=index == 1,
            )
        )
    return VizTableData(columns=columns, rows=table_rows, compact=slide.deck_mode.value == "appendix")


def _diagram_data(slide: BlueprintSlide, request: AssetRequest) -> VizDiagramData:
    if slide.visual_type == VisualType.COMPARISON:
        labels = _content_labels(slide, request, minimum=3, maximum=5)
    elif slide.visual_type in {VisualType.FRAMEWORK, VisualType.INFOGRAPHIC}:
        labels = _content_labels(slide, request, minimum=4, maximum=7)
    else:
        labels = _content_labels(slide, request, minimum=4, maximum=8)
    nodes = [
        VizDiagramNode(
            node_id=f"node-{index}",
            label=_truncate(label, 24),
            supporting_text="Key point" if index == 1 else None,
            emphasis=index == 1,
            group="primary" if index <= 2 else "secondary",
        )
        for index, label in enumerate(labels, start=1)
    ]
    connectors: list[VizDiagramConnector] = []
    if slide.visual_type in {VisualType.PROCESS, VisualType.TIMELINE, VisualType.DECISION_PATH, VisualType.INFOGRAPHIC}:
        connectors = [
            VizDiagramConnector(source_id=nodes[index].node_id, target_id=nodes[index + 1].node_id)
            for index in range(len(nodes) - 1)
        ]
    elif slide.visual_type == VisualType.HIERARCHY and len(nodes) > 1:
        connectors = [VizDiagramConnector(source_id=nodes[0].node_id, target_id=node.node_id) for node in nodes[1:]]
    reading_direction = ReadingDirection.LEFT_TO_RIGHT
    if slide.visual_type == VisualType.HIERARCHY:
        reading_direction = ReadingDirection.TOP_TO_BOTTOM
    elif slide.visual_type == VisualType.FRAMEWORK:
        reading_direction = ReadingDirection.CENTER_OUT
    return VizDiagramData(nodes=nodes, connectors=connectors, reading_direction=reading_direction)


def _metric_summary_data(slide: BlueprintSlide, request: AssetRequest) -> VizMetricSummaryData:
    return VizMetricSummaryData(
        metrics=[
            VizMetricItem(label="Message", value=_truncate(slide.main_message, 40), highlight=True),
            VizMetricItem(label="Sources", value=str(max(1, len(request.source_material_refs))), detail="local inputs"),
            VizMetricItem(label="Mode", value=request.production_mode.value),
        ],
        footer=_truncate(slide.one_line_takeaway, 60),
    )


def _readability_for_spec(spec: VizSpec) -> VizReadability:
    return _readability_from_decision(_evaluate_density_policy(spec))


def build_viz_spec(slide: BlueprintSlide, request: AssetRequest, design_system: DesignSystem) -> VizSpec:
    style_profile = _style_profile(design_system)
    visual_type = request.visual_type or request.required_visual_type
    spec = VizSpec(
        spec_id=f"viz-{request.slide_id}",
        slide_number=slide.slide_number,
        slide_id=request.slide_id,
        title=slide.title,
        message=slide.main_message,
        visual_type=visual_type,
        layout_pattern_id=slide.layout_pattern_id,
        style_tokens=style_profile.color_tokens + style_profile.typography_tokens,
        style_profile=style_profile,
        data_contract=[
            f"slide_id={request.slide_id}",
            f"layout_pattern={slide.layout_pattern_id}",
            *(f"evidence={item}" for item in slide.required_evidence_assets[:4]),
        ],
        visual_source_preference=VisualSourcePreference.STRUCTURED_VISUAL,
        source_material_refs=request.source_material_refs,
        crop_subject_hint=request.crop_subject_hint,
        fallback_visual=request.fallback_visual,
        production_mode=request.production_mode,
        chart=_chart_data(slide, request) if visual_type == VisualType.CHART else None,
        table=_table_data(slide, request) if visual_type == VisualType.TABLE else None,
        diagram=(
            _diagram_data(slide, request)
            if visual_type
            in {
                VisualType.PROCESS,
                VisualType.TIMELINE,
                VisualType.HIERARCHY,
                VisualType.COMPARISON,
                VisualType.FRAMEWORK,
                VisualType.INFOGRAPHIC,
                VisualType.DECISION_PATH,
            }
            else None
        ),
        metric_summary=(
            _metric_summary_data(slide, request)
            if visual_type in {VisualType.TEXT, VisualType.QUOTE, VisualType.METRIC_SUMMARY}
            else None
        ),
    )
    return _apply_density_policy(spec)


def _simplified_spec(spec: VizSpec) -> VizSpec | None:
    audited_spec = _apply_density_policy(spec)
    if not _needs_compile_safe_simplification(audited_spec):
        return None
    payload = audited_spec.model_dump(mode="json", exclude_none=True)
    audit_decision = _evaluate_density_policy(audited_spec)
    fallback_reason_codes = _dedupe(["fallback_due_to_density", *[code for code in audit_decision.density_reason_codes if code != "density_within_limits"]])

    if audited_spec.chart is not None:
        payload["chart"]["categories"] = [_truncate(label, CHART_LABEL_LIMIT) for label in payload["chart"]["categories"][:CHART_SIMPLIFY_CATEGORY_LIMIT]]
        payload["chart"]["series"] = payload["chart"]["series"][:CHART_SIMPLIFIED_SERIES_TARGET]
        payload["chart"]["series"][0]["values"] = payload["chart"]["series"][0]["values"][:4]
        payload["chart"]["series"][0]["label"] = _truncate(payload["chart"]["series"][0]["label"], CHART_LABEL_LIMIT)
        if payload["chart"].get("unit_label"):
            payload["chart"]["unit_label"] = _truncate(payload["chart"]["unit_label"], 12)
    elif audited_spec.table is not None:
        columns = payload["table"]["columns"][:TABLE_SIMPLIFY_COLUMN_LIMIT]
        for column in columns:
            column["label"] = _truncate(column["label"], TABLE_LABEL_LIMIT)
        allowed = {column["key"] for column in columns}
        rows = []
        for row in payload["table"]["rows"][:TABLE_SIMPLIFY_ROW_LIMIT]:
            row["values"] = {key: _truncate(value, TABLE_LABEL_LIMIT) for key, value in row["values"].items() if key in allowed}
            rows.append(row)
        payload["table"]["columns"] = columns
        payload["table"]["rows"] = rows
    elif audited_spec.diagram is not None:
        payload["diagram"]["nodes"] = payload["diagram"]["nodes"][:DIAGRAM_SIMPLIFY_NODE_LIMIT]
        for index, node in enumerate(payload["diagram"]["nodes"]):
            node["label"] = _truncate(node["label"], DIAGRAM_LABEL_LIMIT)
            if index > 0:
                node["supporting_text"] = None
            elif node.get("supporting_text"):
                node["supporting_text"] = _truncate(node["supporting_text"], DIAGRAM_LABEL_LIMIT)
        node_ids = {node["node_id"] for node in payload["diagram"]["nodes"]}
        source_counts: dict[str, int] = {}
        connectors = []
        for connector in payload["diagram"].get("connectors", []):
            if connector["source_id"] not in node_ids or connector["target_id"] not in node_ids:
                continue
            current_count = source_counts.get(connector["source_id"], 0)
            if current_count >= DIAGRAM_SIMPLIFY_BRANCH_LIMIT:
                continue
            source_counts[connector["source_id"]] = current_count + 1
            connector["label"] = None
            connectors.append(connector)
        payload["diagram"]["connectors"] = connectors
    elif audited_spec.metric_summary is not None:
        payload["metric_summary"]["metrics"] = payload["metric_summary"]["metrics"][:METRIC_SIMPLIFY_ITEM_LIMIT]
        for metric in payload["metric_summary"]["metrics"]:
            metric["label"] = _truncate(metric["label"], METRIC_LABEL_LIMIT)
            metric["value"] = _truncate(metric["value"], METRIC_LABEL_LIMIT)
            if metric.get("detail"):
                metric["detail"] = _truncate(metric["detail"], METRIC_LABEL_LIMIT)
        if payload["metric_summary"].get("footer"):
            payload["metric_summary"]["footer"] = _truncate(payload["metric_summary"]["footer"], METRIC_LABEL_LIMIT)

    simplified_spec = VizSpec.model_validate(payload)
    final_decision = _evaluate_density_policy(simplified_spec)
    if final_decision.frame_fit == FrameFit.SPLIT_RECOMMENDED:
        raise ValueError(
            "density policy could not produce a compile-safe fallback "
            f"for {audited_spec.spec_id}: {', '.join(audit_decision.density_reason_codes)}"
        )
    return simplified_spec.model_copy(
        update={
            "readability": _readability_from_decision(
                final_decision,
                audit_decision=audit_decision,
                simplification_applied=True,
                split_applied=audit_decision.split_required,
                fallback_variant_generated=True,
                fallback_reason_codes=fallback_reason_codes,
            ),
            "simpler_variant": _fallback_variant_description(audited_spec),
        }
    )


def _svg_text(x: float, y: float, text: str, *, size: float, fill: str, family: str, weight: str = "400", anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" font-family="{escape(family)}" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(text)}</text>'
    )


def _render_chart_svg(spec: VizSpec, design_system: DesignSystem) -> str:
    assert spec.chart is not None
    colors = _token_map(design_system)
    typography = _typography_map(design_system)
    body = typography["body"]
    caption = typography["caption"]
    ink = colors.get("ink", "#1F2937")
    signal = colors.get("signal", "#C2410C")
    canvas = colors.get("canvas", "#F8FAFC")
    categories = spec.chart.categories
    primary_series = spec.chart.series[0]
    max_value = max(max(series.values) for series in spec.chart.series)
    plot_width = CANVAS_WIDTH - (MARGIN_X * 2)
    plot_height = CANVAS_HEIGHT - (MARGIN_Y * 2) - 44
    bar_gap = 18
    total_bars = len(categories)
    bar_width = max(48, int((plot_width - ((total_bars - 1) * bar_gap)) / max(1, total_bars)))
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">',
        f'<rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="{canvas}" />',
        f'<line x1="{MARGIN_X}" y1="{CANVAS_HEIGHT - MARGIN_Y}" x2="{CANVAS_WIDTH - MARGIN_X}" y2="{CANVAS_HEIGHT - MARGIN_Y}" stroke="{ink}" stroke-width="4" />',
    ]
    for index, label in enumerate(categories):
        x = MARGIN_X + (index * (bar_width + bar_gap))
        value = primary_series.values[index]
        bar_height = int((value / max_value) * (plot_height - 30))
        y = CANVAS_HEIGHT - MARGIN_Y - bar_height
        fill = signal if index == len(categories) - 1 else ink
        svg.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="10" fill="{fill}" opacity="0.88" />')
        svg.append(_svg_text(x + (bar_width / 2), y - 10, str(int(value)), size=caption.size_pt, fill=ink, family=caption.font_family, weight="700", anchor="middle"))
        svg.append(_svg_text(x + (bar_width / 2), CANVAS_HEIGHT - MARGIN_Y + 28, _truncate(label, 18), size=body.size_pt, fill=ink, family=body.font_family, anchor="middle"))
    svg.append(_svg_text(MARGIN_X, MARGIN_Y - 10, spec.message, size=caption.size_pt, fill=ink, family=caption.font_family))
    svg.append("</svg>")
    return "\n".join(svg)


def _render_table_svg(spec: VizSpec, design_system: DesignSystem) -> str:
    assert spec.table is not None
    colors = _token_map(design_system)
    typography = _typography_map(design_system)
    body = typography["body"]
    caption = typography["caption"]
    ink = colors.get("ink", "#1F2937")
    signal = colors.get("signal", "#C2410C")
    canvas = colors.get("canvas", "#F8FAFC")
    columns = spec.table.columns
    rows = spec.table.rows
    table_width = CANVAS_WIDTH - (MARGIN_X * 2)
    table_height = CANVAS_HEIGHT - (MARGIN_Y * 2)
    row_height = max(54, int(table_height / (len(rows) + 1)))
    col_width = int(table_width / len(columns))
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">',
        f'<rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="{canvas}" />',
    ]
    for index, column in enumerate(columns):
        x = MARGIN_X + (index * col_width)
        svg.append(f'<rect x="{x}" y="{MARGIN_Y}" width="{col_width}" height="{row_height}" fill="{ink}" />')
        svg.append(_svg_text(x + 18, MARGIN_Y + (row_height / 2) + 6, column.label, size=body.size_pt, fill="#FFFFFF", family=body.font_family, weight="700"))
    for row_index, row in enumerate(rows, start=1):
        y = MARGIN_Y + (row_index * row_height)
        row_fill = "#FFFFFF" if not row.highlight else "#FFF1E8"
        svg.append(f'<rect x="{MARGIN_X}" y="{y}" width="{table_width}" height="{row_height}" fill="{row_fill}" stroke="{ink}" stroke-width="1" />')
        for col_index, column in enumerate(columns):
            x = MARGIN_X + (col_index * col_width)
            svg.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + row_height}" stroke="{ink}" stroke-width="1" />')
            value = _truncate(row.values[column.key], 26)
            fill = signal if row.highlight and col_index == 0 else ink
            svg.append(_svg_text(x + 18, y + (row_height / 2) + 6, value, size=body.size_pt, fill=fill, family=body.font_family))
    svg.append(_svg_text(MARGIN_X, MARGIN_Y - 12, spec.message, size=caption.size_pt, fill=ink, family=caption.font_family))
    svg.append("</svg>")
    return "\n".join(svg)


def _render_diagram_svg(spec: VizSpec, design_system: DesignSystem) -> str:
    assert spec.diagram is not None
    colors = _token_map(design_system)
    typography = _typography_map(design_system)
    body = typography["body"]
    caption = typography["caption"]
    ink = colors.get("ink", "#1F2937")
    signal = colors.get("signal", "#C2410C")
    canvas = colors.get("canvas", "#F8FAFC")
    nodes = spec.diagram.nodes
    connectors = spec.diagram.connectors
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">',
        f'<rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="{canvas}" />',
    ]

    positions: dict[str, tuple[int, int]] = {}
    if spec.diagram.reading_direction == ReadingDirection.TOP_TO_BOTTOM:
        top_y = MARGIN_Y + 70
        positions[nodes[0].node_id] = (CANVAS_WIDTH // 2, top_y)
        branch_y = top_y + 180
        step = int((CANVAS_WIDTH - (MARGIN_X * 2)) / max(1, len(nodes) - 1))
        for index, node in enumerate(nodes[1:], start=0):
            positions[node.node_id] = (MARGIN_X + (step // 2) + (index * step), branch_y)
    elif spec.diagram.reading_direction == ReadingDirection.CENTER_OUT:
        cols = 2
        for index, node in enumerate(nodes):
            row = index // cols
            col = index % cols
            positions[node.node_id] = (MARGIN_X + 250 + (col * 360), MARGIN_Y + 130 + (row * 180))
    else:
        step = int((CANVAS_WIDTH - (MARGIN_X * 2)) / max(1, len(nodes)))
        y = CANVAS_HEIGHT // 2
        for index, node in enumerate(nodes, start=0):
            positions[node.node_id] = (MARGIN_X + (step // 2) + (index * step), y)

    for connector in connectors:
        source = positions[connector.source_id]
        target = positions[connector.target_id]
        svg.append(f'<line x1="{source[0]}" y1="{source[1]}" x2="{target[0]}" y2="{target[1]}" stroke="{ink}" stroke-width="3" opacity="0.65" />')

    box_w = 210
    box_h = 96
    for node in nodes:
        x, y = positions[node.node_id]
        left = x - (box_w // 2)
        top = y - (box_h // 2)
        fill = signal if node.emphasis else "#FFFFFF"
        text_fill = "#FFFFFF" if node.emphasis else ink
        svg.append(f'<rect x="{left}" y="{top}" width="{box_w}" height="{box_h}" rx="16" fill="{fill}" stroke="{ink}" stroke-width="2" />')
        svg.append(_svg_text(x, y - 4, _truncate(node.label, 22), size=body.size_pt, fill=text_fill, family=body.font_family, weight="700", anchor="middle"))
        if node.supporting_text:
            svg.append(_svg_text(x, y + 20, _truncate(node.supporting_text, 24), size=caption.size_pt, fill=text_fill, family=caption.font_family, anchor="middle"))
    svg.append(_svg_text(MARGIN_X, MARGIN_Y - 12, spec.message, size=caption.size_pt, fill=ink, family=caption.font_family))
    svg.append("</svg>")
    return "\n".join(svg)


def _render_metric_summary_svg(spec: VizSpec, design_system: DesignSystem) -> str:
    assert spec.metric_summary is not None
    colors = _token_map(design_system)
    typography = _typography_map(design_system)
    title = typography["title"]
    body = typography["body"]
    caption = typography["caption"]
    ink = colors.get("ink", "#1F2937")
    signal = colors.get("signal", "#C2410C")
    canvas = colors.get("canvas", "#F8FAFC")
    metrics = spec.metric_summary.metrics
    card_width = int((CANVAS_WIDTH - (MARGIN_X * 2) - ((len(metrics) - 1) * 24)) / max(1, len(metrics)))
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">',
        f'<rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="{canvas}" />',
    ]
    for index, metric in enumerate(metrics):
        x = MARGIN_X + (index * (card_width + 24))
        fill = "#FFFFFF" if not metric.highlight else "#FFF1E8"
        value_fill = signal if metric.highlight else ink
        svg.append(f'<rect x="{x}" y="{MARGIN_Y + 90}" width="{card_width}" height="250" rx="18" fill="{fill}" stroke="{ink}" stroke-width="2" />')
        svg.append(_svg_text(x + 24, MARGIN_Y + 138, metric.label, size=body.size_pt, fill=ink, family=body.font_family, weight="700"))
        svg.append(_svg_text(x + 24, MARGIN_Y + 212, _truncate(metric.value, 34), size=title.size_pt, fill=value_fill, family=title.font_family, weight="700"))
        if metric.detail:
            svg.append(_svg_text(x + 24, MARGIN_Y + 248, _truncate(metric.detail, 26), size=caption.size_pt, fill=ink, family=caption.font_family))
    if spec.metric_summary.footer:
        svg.append(_svg_text(MARGIN_X, CANVAS_HEIGHT - MARGIN_Y + 8, spec.metric_summary.footer, size=caption.size_pt, fill=ink, family=caption.font_family))
    svg.append("</svg>")
    return "\n".join(svg)


def _render_svg(spec: VizSpec, design_system: DesignSystem) -> str:
    if spec.chart is not None:
        return _render_chart_svg(spec, design_system)
    if spec.table is not None:
        return _render_table_svg(spec, design_system)
    if spec.diagram is not None:
        return _render_diagram_svg(spec, design_system)
    return _render_metric_summary_svg(spec, design_system)


def _write_svg(path: Path, svg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg + "\n", encoding="utf-8")


def _write_table_data(path: Path, table: VizTableData) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "\t".join(column.label for column in table.columns)
    rows = ["\t".join(row.values[column.key] for column in table.columns) for row in table.rows]
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


def _merge_viz_manifest(existing: VizManifest | None, deck_title: str, records: list[VizRecord]) -> VizManifest:
    prior_map = {} if existing is None else {record.spec.spec_id: record for record in existing.visuals}
    merged_rows: list[VizRecord] = []
    replacement_ids = {row.spec.spec_id for row in records}
    if existing is not None:
        merged_rows.extend(record for record in existing.visuals if record.spec.spec_id not in replacement_ids)
    for record in records:
        prior = prior_map.get(record.spec.spec_id)
        revision = 1 if prior is None else prior.revision + 1
        merged_rows.append(record.model_copy(update={"revision": revision}))
    merged_rows.sort(key=lambda row: (row.spec.slide_number, row.spec.spec_id))
    return VizManifest(deck_title=deck_title, visuals=merged_rows)


def _merge_asset_manifest(existing: AssetManifest | None, deck_title: str, records: list[AssetRecord]) -> AssetManifest:
    replacement_ids = {record.asset_id for record in records}
    prior = [] if existing is None else [asset for asset in existing.assets if asset.asset_id not in replacement_ids]
    merged = prior + records
    merged.sort(key=lambda asset: (asset.slide_number, asset.asset_id))
    return AssetManifest(deck_title=deck_title, assets=merged)


def _style_profile_for_render(
    spec: VizSpec,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution | None,
) -> VizStyleProfile:
    constitution_tokens = [] if deck_constitution is None else deck_constitution.design_token_refs
    color_tokens = [token.token for token in design_system.color_tokens if token.token in constitution_tokens]
    if not color_tokens:
        color_tokens = spec.style_profile.color_tokens if spec.style_profile is not None else [token.token for token in design_system.color_tokens]
    typography_tokens = [token.token for token in design_system.typography_tokens if token.token in constitution_tokens]
    if not typography_tokens:
        typography_tokens = (
            spec.style_profile.typography_tokens if spec.style_profile is not None else [token.token for token in design_system.typography_tokens]
        )
    return VizStyleProfile(
        color_tokens=color_tokens,
        typography_tokens=typography_tokens,
        chart_rules=_dedupe([*design_system.chart_rules, *(([] if deck_constitution is None else deck_constitution.chart_rules))]),
        table_rules=_dedupe([*design_system.table_rules, *(([] if deck_constitution is None else deck_constitution.table_rules))]),
        highlight_rules=_dedupe([*design_system.highlight_rules, *(([] if deck_constitution is None else deck_constitution.infographic_rules))]),
    )


def _find_layout_pattern(layout_library: LayoutLibrary | None, pattern_id: str) -> LayoutPattern | None:
    if layout_library is None:
        return None
    for pattern in layout_library.patterns:
        if pattern.pattern_id == pattern_id:
            return pattern
    return None


def _request_rank(request: AssetRequest) -> tuple[int, int]:
    structured = 1 if request.asset_kind == AssetKind.STRUCTURED_VISUAL else 0
    primary_mode = 1 if request.production_mode in {ProductionMode.STRUCTURED_VISUAL, ProductionMode.HYBRID} else 0
    preferred_source = 1 if request.visual_source_preference in {VisualSourcePreference.STRUCTURED_VISUAL, VisualSourcePreference.EITHER} else 0
    return (structured, primary_mode, preferred_source)


def _find_routing_request(spec: VizSpec, asset_requests: AssetRequests | None) -> AssetRequest | None:
    if asset_requests is None:
        return None
    candidates = [
        request
        for request in asset_requests.requests
        if request.slide_number == spec.slide_number or request.slide_id == spec.slide_id
    ]
    if not candidates:
        return None
    candidates.sort(key=_request_rank, reverse=True)
    best = candidates[0]
    return best if _request_rank(best) > (0, 0, 0) else None


def _is_renderable_spec(spec: VizSpec) -> bool:
    if spec.visual_type in {VisualType.DOCUMENT_CROP, VisualType.PHOTO}:
        return False
    if spec.visual_source_preference == VisualSourcePreference.DOCUMENT_CROP:
        return False
    if spec.production_mode == ProductionMode.SOURCE_REUSE and spec.visual_source_preference != VisualSourcePreference.STRUCTURED_VISUAL:
        return False
    return True


def _build_spec_from_blueprint(
    blueprint: Blueprint | None,
    asset_requests: AssetRequests | None,
    design_system: DesignSystem,
) -> VizSpecSet:
    if blueprint is None or asset_requests is None:
        raise ValueError("run_structured_visuals requires viz_spec or a compatibility blueprint + asset_requests pair")
    slides_by_number = {slide.slide_number: slide for slide in blueprint.slides}
    specs: list[VizSpec] = []
    for request in asset_requests.requests:
        if request.asset_kind != AssetKind.STRUCTURED_VISUAL:
            continue
        slide = slides_by_number.get(request.slide_number)
        if slide is None:
            raise ValueError(f"structured visual request {request.request_id} has no matching blueprint slide")
        specs.append(build_viz_spec(slide, request, design_system))
    return VizSpecSet(deck_title=blueprint.deck_title, specs=specs)


def _render_note_prefix(deck_constitution: DeckConstitution | None) -> str | None:
    if deck_constitution is None or deck_constitution.approved_visual_route is None:
        return None
    return f"Rendered under visual route {deck_constitution.approved_visual_route}."


def _render_spec_assets(
    spec: VizSpec,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution | None,
    layout_pattern: LayoutPattern | None,
    visuals_dir: Path,
    data_dir: Path,
    root_path: Path,
) -> tuple[VizRecord, AssetRecord | None, list[str]]:
    styled_spec = _apply_density_policy(spec.model_copy(update={"style_profile": _style_profile_for_render(spec, design_system, deck_constitution)}))
    primary_spec = styled_spec
    alternate_output_path: str | None = None
    limitations: list[str] = []
    notes: list[str] = []

    if layout_pattern is None:
        limitations.append(f"Layout pattern {styled_spec.layout_pattern_id!r} was not found in the approved layout library.")
    else:
        if styled_spec.visual_type not in layout_pattern.supported_visual_types:
            limitations.append(
                f"Layout pattern {layout_pattern.pattern_id} is not approved for visual type {styled_spec.visual_type.value}; rendered with existing layout fallback."
            )
        if not layout_pattern.export_safe:
            limitations.append(f"Layout pattern {layout_pattern.pattern_id} is not marked export-safe.")
        if layout_pattern.density_guidance:
            notes.append(f"Layout density guidance: {layout_pattern.density_guidance}")

    route_note = _render_note_prefix(deck_constitution)
    if route_note is not None:
        notes.append(route_note)

    density_summary = _density_audit_summary(styled_spec.readability)
    if density_summary is not None:
        notes.append(density_summary)

    simplified_spec = _simplified_spec(styled_spec)
    if simplified_spec is not None:
        primary_spec = simplified_spec
        notes.append(simplified_spec.simpler_variant or "Rendered a simpler compile-safe visual variant due to density.")
        simplified_density_summary = _density_audit_summary(simplified_spec.readability)
        if simplified_density_summary is not None:
            notes.append(simplified_density_summary)
        if simplified_spec.readability is not None and simplified_spec.readability.split_applied:
            limitations.append(
                "Original requested visual exceeded split-level density thresholds; the worker promoted a compile-safe fallback variant instead of passing the dense visual through."
            )
        else:
            limitations.append(
                "Original requested visual exceeded one-slide density guidance; a compile-safe simplified variant was promoted to primary output."
            )

    slug = _slugify(primary_spec.title)
    primary_path = visuals_dir / f"slide-{primary_spec.slide_number:02d}-{slug}.svg"
    _write_svg(primary_path, _render_svg(primary_spec, design_system))

    if simplified_spec is not None:
        full_variant_path = visuals_dir / f"slide-{styled_spec.slide_number:02d}-{_slugify(styled_spec.title)}-full.svg"
        _write_svg(full_variant_path, _render_svg(styled_spec, design_system))
        alternate_output_path = _display_path(full_variant_path, root_path)

    data_output_path: str | None = None
    if primary_spec.table is not None:
        table_path = data_dir / f"slide-{primary_spec.slide_number:02d}-{slug}-table.tsv"
        _write_table_data(table_path, primary_spec.table)
        data_output_path = _display_path(table_path, root_path)
        notes.append(f"Structured table data written to {data_output_path}.")

    viz_record = VizRecord(
        spec=primary_spec,
        status=VizStatus.RENDERED,
        output_path=_display_path(primary_path, root_path),
        fallback_output_path=alternate_output_path,
        data_output_path=data_output_path,
        applied_color_tokens=primary_spec.style_profile.color_tokens,
        applied_typography_tokens=primary_spec.style_profile.typography_tokens,
        notes=" ".join(notes + limitations) if notes or limitations else None,
    )

    asset_record = AssetRecord(
        asset_id=f"asset-{primary_spec.slide_id}-structured-visual",
        request_id=f"viz-spec-{primary_spec.spec_id}",
        slide_number=primary_spec.slide_number,
        slide_id=primary_spec.slide_id,
        asset_kind=AssetKind.STRUCTURED_VISUAL,
        status=AssetStatus.READY,
        local_path=_display_path(primary_path, root_path),
        visual_source_preference=primary_spec.visual_source_preference,
        source_material_refs=primary_spec.source_material_refs,
        crop_subject_hint=primary_spec.crop_subject_hint,
        fallback_visual=primary_spec.fallback_visual,
        production_mode=primary_spec.production_mode,
        limitations=limitations,
        notes=" ".join(notes) if notes else None,
    )
    return (viz_record, asset_record, limitations)


def _update_asset_record_from_request(asset_record: AssetRecord, request: AssetRequest | None, data_output_path: str | None) -> AssetRecord:
    if request is None:
        notes = asset_record.notes or ""
        if data_output_path is not None:
            notes = (notes + " " if notes else "") + f"Data output: {data_output_path}."
        return asset_record.model_copy(update={"notes": notes or None})
    notes = asset_record.notes or ""
    if data_output_path is not None:
        notes = (notes + " " if notes else "") + f"Data output: {data_output_path}."
    return asset_record.model_copy(
        update={
            "request_id": request.request_id,
            "visual_source_preference": request.visual_source_preference,
            "source_material_refs": request.source_material_refs or asset_record.source_material_refs,
            "crop_subject_hint": request.crop_subject_hint or asset_record.crop_subject_hint,
            "fallback_visual": request.fallback_visual or asset_record.fallback_visual,
            "production_mode": request.production_mode,
            "notes": notes or None,
        }
    )


def _update_slide_ledger(
    slide_ledger: SlideLedger,
    *,
    successes: dict[str, tuple[VizSpec, AssetRecord, str]],
    failures: dict[str, str],
) -> SlideLedger:
    updated_entries: list[SlideLedgerEntry] = []
    for entry in slide_ledger.entries:
        outcome = successes.get(entry.slide_id)
        failure = failures.get(entry.slide_id)
        if outcome is None and failure is None:
            updated_entries.append(entry)
            continue

        payload = entry.model_dump(mode="json", exclude_none=True)
        blockers = list(entry.unresolved_blockers or [])
        blockers = [blocker for blocker in blockers if "structured visual" not in blocker.lower() and "viz" not in blocker.lower()]
        dependency_kinds = list(entry.asset_dependency_kinds)
        if AssetKind.STRUCTURED_VISUAL not in dependency_kinds:
            dependency_kinds.append(AssetKind.STRUCTURED_VISUAL)
        payload["asset_dependency_kinds"] = dependency_kinds

        if outcome is not None:
            spec, asset_record, note = outcome
            request_ids = list(entry.asset_request_ids)
            if asset_record.request_id not in request_ids:
                request_ids.append(asset_record.request_id)
            payload["asset_request_ids"] = request_ids
            payload["viz_spec_id"] = spec.spec_id
            payload["visual_status"] = StageStatus.COMPLETE
            if all(kind == AssetKind.STRUCTURED_VISUAL for kind in dependency_kinds):
                payload["asset_status"] = StageStatus.COMPLETE
            payload["production_readiness"] = StageStatus.READY if not blockers else StageStatus.BLOCKED
            payload["unresolved_blockers"] = blockers or None
            payload["change_note"] = note
        else:
            failure_message = failure or "Structured visual rendering did not complete."
            blockers.append(failure_message)
            payload["visual_status"] = StageStatus.BLOCKED
            if all(kind == AssetKind.STRUCTURED_VISUAL for kind in dependency_kinds):
                payload["asset_status"] = StageStatus.BLOCKED
            payload["production_readiness"] = StageStatus.BLOCKED
            payload["unresolved_blockers"] = _dedupe(blockers)
            payload["change_note"] = failure_message

        updated_entries.append(SlideLedgerEntry.model_validate(payload))
    return SlideLedger(deck_title=slide_ledger.deck_title, entries=updated_entries, continuity_notes=slide_ledger.continuity_notes)


def run_structured_visuals(
    *,
    viz_spec: VizSpecSet | None = None,
    design_system: DesignSystem,
    slide_ledger: SlideLedger,
    output_dir: str | Path,
    deck_constitution: DeckConstitution | None = None,
    layout_library: LayoutLibrary | None = None,
    asset_requests: AssetRequests | None = None,
    asset_manifest: AssetManifest | None = None,
    viz_manifest: VizManifest | None = None,
    blueprint: Blueprint | None = None,
    root: str | Path | None = None,
) -> StructuredVisualOutputs:
    viz_specs = viz_spec if viz_spec is not None else _build_spec_from_blueprint(blueprint, asset_requests, design_system)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    visuals_dir = output_root / "visuals"
    data_dir = output_root / "visuals-data"
    visuals_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    root_path = Path(root).resolve() if root is not None else Path.cwd().resolve()

    records: list[VizRecord] = []
    asset_records: list[AssetRecord] = []
    successes: dict[str, tuple[VizSpec, AssetRecord, str]] = {}
    failures: dict[str, str] = {}

    for spec in viz_specs.specs:
        if not _is_renderable_spec(spec):
            continue
        layout_pattern = _find_layout_pattern(layout_library, spec.layout_pattern_id)
        routing_request = _find_routing_request(spec, asset_requests)
        try:
            viz_record, asset_record, limitations = _render_spec_assets(
                spec=spec,
                design_system=design_system,
                deck_constitution=deck_constitution,
                layout_pattern=layout_pattern,
                visuals_dir=visuals_dir,
                data_dir=data_dir,
                root_path=root_path,
            )
        except Exception as exc:
            failure_note = f"Structured visual render failed for {spec.spec_id}: {exc}"
            records.append(
                VizRecord(
                    spec=spec,
                    status=VizStatus.REJECTED,
                    applied_color_tokens=spec.style_profile.color_tokens,
                    applied_typography_tokens=spec.style_profile.typography_tokens,
                    notes=failure_note,
                )
            )
            failures[spec.slide_id] = failure_note
            continue

        asset_record = _update_asset_record_from_request(asset_record, routing_request, viz_record.data_output_path)
        render_note = "Structured visual rendered and registered for compile."
        if viz_record.spec.readability is not None and viz_record.spec.readability.simplified:
            render_note = "Structured visual rendered with a simpler compile-safe fallback as the primary asset."
            if viz_record.spec.readability.split_applied:
                render_note = "Structured visual exceeded split-level density thresholds; a compile-safe fallback was promoted as the primary asset."
        if limitations:
            render_note += f" {' '.join(limitations)}"

        records.append(viz_record)
        asset_records.append(asset_record)
        successes[spec.slide_id] = (viz_record.spec, asset_record, render_note)

    manifest = _merge_viz_manifest(viz_manifest, slide_ledger.deck_title, records)
    merged_assets = _merge_asset_manifest(asset_manifest, slide_ledger.deck_title, asset_records)
    updated_ledger = _update_slide_ledger(slide_ledger, successes=successes, failures=failures)
    return StructuredVisualOutputs(viz_manifest=manifest, asset_manifest=merged_assets, slide_ledger=updated_ledger)


def run_structured_visuals_from_files(
    viz_spec_path: str | Path,
    design_system_path: str | Path,
    deck_constitution_path: str | Path,
    layout_library_path: str | Path,
    slide_ledger_path: str | Path,
    output_dir: str | Path,
    *,
    asset_requests_path: str | Path | None = None,
    asset_manifest_path: str | Path | None = None,
    viz_manifest_path: str | Path | None = None,
    root: str | Path | None = None,
) -> StructuredVisualOutputs:
    from ..compat.legacy_non_pptx import load_state_file

    viz_spec = load_state_file(viz_spec_path)
    if viz_spec.schema_name != "viz_spec":
        raise TypeError(f"expected viz_spec, found {viz_spec.schema_name}")
    design_system = load_state_file(design_system_path)
    if design_system.schema_name != "design_system":
        raise TypeError(f"expected design_system, found {design_system.schema_name}")
    deck_constitution = load_state_file(deck_constitution_path)
    if deck_constitution.schema_name != "deck_constitution":
        raise TypeError(f"expected deck_constitution, found {deck_constitution.schema_name}")
    layout_library = load_state_file(layout_library_path)
    if layout_library.schema_name != "layout_library":
        raise TypeError(f"expected layout_library, found {layout_library.schema_name}")
    slide_ledger = load_state_file(slide_ledger_path)
    if slide_ledger.schema_name != "slide_ledger":
        raise TypeError(f"expected slide_ledger, found {slide_ledger.schema_name}")

    asset_requests = None
    if asset_requests_path is not None:
        asset_requests = load_state_file(asset_requests_path)
        if asset_requests.schema_name != "asset_requests":
            raise TypeError(f"expected asset_requests, found {asset_requests.schema_name}")

    asset_manifest = None
    if asset_manifest_path is not None:
        asset_manifest = load_state_file(asset_manifest_path)
        if asset_manifest.schema_name != "asset_manifest":
            raise TypeError(f"expected asset_manifest, found {asset_manifest.schema_name}")

    loaded_viz_manifest = None
    if viz_manifest_path is not None:
        loaded_viz_manifest = load_state_file(viz_manifest_path)
        if loaded_viz_manifest.schema_name != "viz_manifest":
            raise TypeError(f"expected viz_manifest, found {loaded_viz_manifest.schema_name}")

    return run_structured_visuals(
        viz_spec=viz_spec,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        slide_ledger=slide_ledger,
        output_dir=output_dir,
        asset_requests=asset_requests,
        asset_manifest=asset_manifest,
        viz_manifest=loaded_viz_manifest,
        root=root,
    )


def write_structured_visual_outputs(outputs: StructuredVisualOutputs, output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    return {
        "viz_manifest": save_state_file(outputs.viz_manifest, root / "viz-manifest.json"),
        "asset_manifest": save_state_file(outputs.asset_manifest, root / "asset-manifest.json"),
        "slide_ledger": save_state_file(outputs.slide_ledger, root / "slide-ledger.json"),
    }

