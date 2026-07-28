from __future__ import annotations

from typing import Any

from pptx.enum.shapes import MSO_CONNECTOR_TYPE
from pptx.util import Inches, Pt

from ..slide_scene import DividerLine
from .common import stable_scene_shape_name
from .style import SceneStyleContext, resolve_stroke_style


def render_divider_line(
    slide: Any,
    divider: DividerLine,
    *,
    style_context: SceneStyleContext,
    used_shape_names: set[str],
    slide_number: int,
    slide_id: str,
    trace_prefix: str = "divider",
) -> str:
    shape = slide.shapes.add_connector(
        MSO_CONNECTOR_TYPE.STRAIGHT,
        Inches(divider.x1),
        Inches(divider.y1),
        Inches(divider.x2),
        Inches(divider.y2),
    )
    shape.name = stable_scene_shape_name(trace_prefix, divider.object_id, used_shape_names)
    line = shape.line
    line.fill.solid()
    stroke_style = resolve_stroke_style(
        style_context,
        divider.stroke,
        width_pt=divider.width_pt,
        default_hex="#94A3B8",
        slide_number=slide_number,
        slide_id=slide_id,
        object_id=divider.object_id,
    )
    line.fill.fore_color.rgb = stroke_style.color_rgb
    line.width = Pt(stroke_style.width_pt)
    return shape.name
