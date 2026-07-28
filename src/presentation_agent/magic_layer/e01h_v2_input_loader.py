"""Load E01H-V2 validation case inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e01h_v2_report import read_json


def load_pdfb02_validation_case(fixture: dict[str, Any], case_id: str | None = None) -> dict[str, Any]:
    folder = Path(fixture["fixture_dir"])
    truth = read_json(folder / "source_layer_truth.json")
    return {
        "schema_name": "e01h_v2_validation_case_input",
        "case_id": case_id or fixture["fixture_id"],
        "source_fixture_id": fixture["fixture_id"],
        "source": "pdfb02_fixture",
        "reference_pdf": fixture.get("reference_pdf") or str(folder / "reference.pdf"),
        "reference_image": fixture["reference_image"],
        "source_layer_truth": truth,
        "expected_semantic_slots": read_json(folder / "expected_semantic_slots.json"),
        "expected_visual_backplates": read_json(folder / "expected_visual_backplates.json"),
        "expected_native_components": read_json(folder / "expected_native_components.json"),
        "expected_raster_policy": read_json(folder / "expected_raster_policy.json"),
        "style_family": fixture.get("style_family", truth.get("style_family")),
        "background_mode": fixture.get("background_mode", truth.get("background_mode")),
        "requires_chart": fixture.get("requires_chart", any(obj.get("semantic_role") == "chart" for obj in truth.get("table_chart_objects", []))),
        "requires_table": fixture.get("requires_table", any(obj.get("semantic_role") == "table" for obj in truth.get("table_chart_objects", []))),
        "canva_parity_claimed": False,
    }


def load_image_validation_case(case_id: str, reference_image: str | Path, *, source: str = "image_reference") -> dict[str, Any]:
    image_path = Path(reference_image)
    truth = _fallback_truth(case_id)
    return {
        "schema_name": "e01h_v2_validation_case_input",
        "case_id": case_id,
        "source_fixture_id": case_id,
        "source": source,
        "reference_pdf": None,
        "reference_image": image_path.as_posix(),
        "source_layer_truth": truth,
        "expected_semantic_slots": {"slots": truth["semantic_text_objects"] + truth["semantic_icon_objects"]},
        "expected_visual_backplates": {"allowed_backplates": truth["nonsemantic_visual_backplates"] + truth["raster_image_fields"]},
        "expected_native_components": {"requires_chart": False, "requires_table": False, "components": truth["card_panel_objects"]},
        "expected_raster_policy": truth["allowed_raster_policy"],
        "style_family": "maritime_hybrid",
        "background_mode": "dark",
        "requires_chart": False,
        "requires_table": False,
        "canva_parity_claimed": False,
    }


def _fallback_truth(case_id: str) -> dict[str, Any]:
    text = [
        {"object_id": "text_title", "zone_id": "text_title", "semantic_role": "semantic_text", "bbox_norm": [0.06, 0.06, 0.62, 0.13], "text": "Editable maritime checklist", "z_order": 10},
        {"object_id": "footer_source", "zone_id": "footer_source", "semantic_role": "footer_source", "bbox_norm": [0.06, 0.88, 0.92, 0.94], "text": "Local E01H-P regression fixture", "z_order": 90},
    ]
    icons = [{"object_id": "icon_marker_1", "zone_id": "icon_marker_1", "semantic_role": "semantic_icon", "bbox_norm": [0.74, 0.18, 0.80, 0.26], "z_order": 30}]
    backplates = [{"object_id": "background_substrate", "zone_id": "background_substrate", "semantic_role": "nonsemantic_visual_backplate", "bbox_norm": [0.00, 0.00, 1.00, 1.00], "z_order": 1}]
    raster_fields = [{"object_id": "hero_visual_field", "zone_id": "hero_visual_field", "semantic_role": "nonsemantic_visual_backplate", "bbox_norm": [0.05, 0.16, 0.58, 0.78], "z_order": 4}]
    panels = [{"object_id": "checklist_panel", "zone_id": "checklist_panel", "semantic_role": "card_panel", "bbox_norm": [0.62, 0.18, 0.92, 0.78], "z_order": 20}]
    objects = backplates + raster_fields + panels + icons + text
    return {
        "schema_name": "source_layer_truth",
        "fixture_id": case_id,
        "status": "passed",
        "style_family": "maritime_hybrid",
        "background_mode": "dark",
        "semantic_text_objects": text,
        "semantic_icon_objects": icons,
        "table_chart_objects": [],
        "card_panel_objects": panels,
        "connector_vector_objects": [],
        "footer_source_objects": [text[-1]],
        "nonsemantic_visual_backplates": backplates,
        "raster_image_fields": raster_fields,
        "vector_objects": icons,
        "z_order": [obj["object_id"] for obj in sorted(objects, key=lambda row: row["z_order"])],
        "all_objects": objects,
        "allowed_raster_policy": {
            "full_slide_reference_background_allowed": False,
            "allowed_raster_object_ids": ["background_substrate", "hero_visual_field"],
            "forbidden_raster_roles": ["semantic_text", "semantic_icon", "footer_source", "card_panel"],
        },
        "canva_parity_claimed": False,
    }
