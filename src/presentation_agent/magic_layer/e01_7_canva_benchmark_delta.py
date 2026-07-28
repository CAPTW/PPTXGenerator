"""Canva benchmark delta helpers for the E01.7 single-slide final gate."""

from __future__ import annotations

from typing import Any


CANVA_BENCHMARK_FACTS = {
    "slide_count": 1,
    "shape_count": 53,
    "editable_text_count": 26,
    "raster_image_fill_or_freeform_count": 27,
    "embedded_media_count": 27,
    "native_chart_table_count": 0,
    "classification": "hybrid_visual_layer_segmentation_benchmark",
}


def build_canva_benchmark_delta(
    *,
    ooxml_ledger: dict[str, Any],
    media_ledger: dict[str, Any],
    e01_6_patch_report: dict[str, Any],
    canva_object_ledger: dict[str, Any] | None = None,
    canva_media_ledger: dict[str, Any] | None = None,
    canva_text_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare E01.6 with the real Canva benchmark boundary.

    Canva is treated as a minimum segmentation benchmark. The E01.7 target is
    not simply more objects; it is comparable visual decomposition with stronger
    native editability for semantic text, icons, panels, and footer objects.
    """

    canva = _facts_from_ledgers(canva_object_ledger, canva_media_ledger, canva_text_ledger)
    e01_shape_count = int(ooxml_ledger.get("total_shapes", 0))
    e01_editable_text_count = int(ooxml_ledger.get("text_boxes", e01_6_patch_report.get("editable_text_count", 0)))
    e01_vector_icon_count = int(e01_6_patch_report.get("semantic_icon_vector_count", 0))
    e01_raster_semantic_count = int(media_ledger.get("semantic_raster_media_count", 0))
    e01_full_slide_raster = int(ooxml_ledger.get("full_slide_raster_count", 0))
    e01_native_panel_count = sum(
        1
        for row in ooxml_ledger.get("shapes", [])
        if row.get("likely_semantic_role")
        in {"checklist_panel", "bottom_action_bar", "source_footer_strip", "semantic_text"}
        and row.get("editability_class") != "bounded_nonsemantic_raster"
    )
    passes = (
        ooxml_ledger.get("slide_count") == 1
        and e01_shape_count >= canva["shape_count"]
        and e01_editable_text_count >= canva["editable_text_count"]
        and e01_vector_icon_count >= 16
        and e01_raster_semantic_count == 0
        and e01_full_slide_raster == 0
    )
    return {
        "schema_name": "e01_7_canva_benchmark_delta_report",
        "status": "passed" if passes else "failed",
        "canva_benchmark": canva,
        "e01_6": {
            "slide_count": ooxml_ledger.get("slide_count"),
            "shape_count": e01_shape_count,
            "editable_text_count": e01_editable_text_count,
            "semantic_vector_icon_count": e01_vector_icon_count,
            "semantic_native_or_shape_panel_count": e01_native_panel_count,
            "raster_semantic_count": e01_raster_semantic_count,
            "full_slide_raster_count": e01_full_slide_raster,
            "png_jpeg_media_count": media_ledger.get("png_jpeg_media_count", 0),
            "svg_media_count": media_ledger.get("svg_media_count", 0),
        },
        "interpretation": {
            "canva_is_minimum_visual_segmentation_benchmark": True,
            "canva_is_not_native_editability_ceiling": True,
            "e01_6_exceeds_canva_semantic_native_editability": e01_editable_text_count > canva["editable_text_count"]
            and e01_vector_icon_count >= 16
            and e01_raster_semantic_count == 0,
            "fewer_raster_layers_is_positive_only_with_region_fidelity": True,
            "single_slide_scope_only": True,
        },
        "decision": "PASS" if passes else "PATCH_REQUIRED",
        "canva_parity_claimed": bool(passes),
        "canva_parity_scope": "single_reference_single_slide_only" if passes else "not_claimed",
    }


def _facts_from_ledgers(
    object_ledger: dict[str, Any] | None,
    media_ledger: dict[str, Any] | None,
    text_ledger: dict[str, Any] | None,
) -> dict[str, Any]:
    facts = dict(CANVA_BENCHMARK_FACTS)
    if object_ledger:
        summary = object_ledger.get("summary", {})
        facts["slide_count"] = int(object_ledger.get("slide_count", summary.get("slide_count", facts["slide_count"])))
        facts["shape_count"] = int(
            object_ledger.get("shape_count", object_ledger.get("total_shape_count", summary.get("shape_count", facts["shape_count"])))
        )
        facts["editable_text_count"] = int(
            object_ledger.get("editable_text_count", summary.get("editable_text_count", facts["editable_text_count"]))
        )
        facts["raster_image_fill_or_freeform_count"] = int(
            object_ledger.get(
                "raster_image_fill_or_freeform_count",
                summary.get("raster_image_fill_or_freeform_count", facts["raster_image_fill_or_freeform_count"]),
            )
        )
        facts["native_chart_table_count"] = int(
            object_ledger.get("native_chart_table_count", summary.get("native_chart_table_count", facts["native_chart_table_count"]))
        )
    if media_ledger:
        summary = media_ledger.get("summary", {})
        facts["embedded_media_count"] = int(
            media_ledger.get("embedded_media_count", media_ledger.get("media_count", summary.get("embedded_media_count", facts["embedded_media_count"])))
        )
    if text_ledger:
        facts["editable_text_count"] = int(
            text_ledger.get("editable_text_count", text_ledger.get("text_box_count", facts["editable_text_count"]))
        )
    return facts
