"""Build style contract schemas and token manifests."""

from __future__ import annotations

from typing import Any


def build_contract_style_schema_v1() -> dict[str, Any]:
    return {
        "schema_name": "contract_style_schema_v1",
        "required_fields": [
            "style_ref",
            "theme_token",
            "fill_token",
            "line_token",
            "typography_token",
            "media_crop_token",
            "svg_variant_token",
            "table_style_token",
            "chart_style_token",
            "opacity",
            "effect_token",
        ],
        "source": "baseline candidate object XML style inventory",
    }


def build_visual_style_token_manifest(style_report: dict[str, Any]) -> dict[str, Any]:
    tokens = []
    for slide in style_report.get("slides", []):
        for obj in slide.get("objects", []):
            tokens.append(
                {
                    "slide_number": slide["slide_number"],
                    "z_order": obj["z_order"],
                    "name": obj["name"],
                    "fill_token": obj.get("fill_color"),
                    "line_token": obj.get("line_color"),
                    "line_width": obj.get("line_width"),
                    "style_ref": f"slide-{slide['slide_number']:03d}:z{obj['z_order']:04d}",
                }
            )
    return {
        "schema_name": "visual_style_token_manifest",
        "status": "passed" if tokens else "failed",
        "style_token_count": len(tokens),
        "tokens": tokens[:400],
    }


def build_media_crop_and_asset_manifest(style_report: dict[str, Any]) -> dict[str, Any]:
    media = []
    for slide in style_report.get("slides", []):
        for obj in slide.get("objects", []):
            if obj.get("has_media"):
                media.append(
                    {
                        "slide_number": slide["slide_number"],
                        "z_order": obj["z_order"],
                        "name": obj["name"],
                        "media_rid": obj.get("media_rid"),
                        "media_crop_token": f"slide-{slide['slide_number']:03d}:z{obj['z_order']:04d}:crop",
                    }
                )
    return {
        "schema_name": "media_crop_and_asset_manifest",
        "status": "passed",
        "media_object_count": len(media),
        "media": media,
    }
