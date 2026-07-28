from __future__ import annotations

from typing import Any

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from ..slide_scene import NativeChart
from .common import append_warning, stable_scene_shape_name
from .style import SceneStyleContext, resolve_fill_style


_SUPPORTED_CHART_TYPES: dict[str, XL_CHART_TYPE] = {
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
}


def render_native_chart(
    slide: Any,
    native_chart: NativeChart,
    *,
    style_context: SceneStyleContext,
    used_shape_names: set[str],
    slide_number: int,
    slide_id: str,
    warnings: list[Any],
) -> str | None:
    pptx_chart_type = _SUPPORTED_CHART_TYPES.get(native_chart.chart_type)
    if pptx_chart_type is None:
        append_warning(
            warnings,
            code="unsupported_chart_type",
            severity="warning",
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=native_chart.object_id,
            message=f"NativeChart type {native_chart.chart_type!r} is not supported by the scene compile path yet.",
            details={"chart_type": native_chart.chart_type, "supported_chart_types": sorted(_SUPPORTED_CHART_TYPES)},
        )
        return None

    chart_data = CategoryChartData()
    chart_data.categories = list(native_chart.categories)
    for series in native_chart.series:
        chart_data.add_series(series.label, tuple(series.values))

    shape = slide.shapes.add_chart(
        pptx_chart_type,
        Inches(native_chart.bounds.x),
        Inches(native_chart.bounds.y),
        Inches(native_chart.bounds.width),
        Inches(native_chart.bounds.height),
        chart_data,
    )
    shape.name = stable_scene_shape_name("native_chart", native_chart.object_id, used_shape_names)
    chart = shape.chart
    chart.has_legend = len(native_chart.series) > 1
    if chart.has_legend:
        chart.legend.include_in_layout = False

    for index, scene_series in enumerate(native_chart.series):
        if scene_series.color is None:
            continue
        series = chart.series[index]
        fill = series.format.fill
        fill.solid()
        fill.fore_color.rgb = resolve_fill_style(
            style_context,
            scene_series.color,
            "#C2410C",
            slide_number=slide_number,
            slide_id=slide_id,
            object_id=native_chart.object_id,
        ).color_rgb
    return shape.name
