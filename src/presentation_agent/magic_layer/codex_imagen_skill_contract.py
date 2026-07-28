"""Codex Desktop Imagen skill contract for D07.2 visual-field assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_CODEX_IMAGEN_FILENAMES = [
    "d07_slide_01_cover_hero_hero_field.png",
    "d07_slide_02_section_divider_chapter_visual.png",
    "d07_slide_15_case_study_case_image.png",
    "d07_slide_15_case_image_frame.png",
]


def build_api_route_reclassification_report(*, d07_2_4_report: dict[str, Any], d07_2_5_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "api_route_reclassification_report",
        "d07_2_4_api_route_scaffold_status": "BUILT_BUT_WRONG_WORKFLOW",
        "d07_2_5_api_config_gate_status": "BLOCKED_CORRECTLY_BUT_NOT_PRODUCT_PATH",
        "d07_2_4_previous_decision": d07_2_4_report.get("decision"),
        "d07_2_5_previous_decision": d07_2_5_report.get("decision"),
        "api_key_route_required": False,
        "codex_desktop_imagen_skill_route_required": True,
        "manual_external_asset_generation": "fallback_only",
        "primary_generation_route": "codex_desktop_imagen_skill",
        "api_route_archived_for_non_primary_use": True,
        "d08_visual_asset_path_status": "LOCKED_UNTIL_IMAGEN_ASSETS_VALIDATE",
        "decision": "D07_2_6_REPLACE_API_ROUTE_WITH_CODEX_IMAGEN_SKILL_ROUTE",
        "canva_parity_claimed": False,
    }


def build_codex_imagen_skill_contract(*, target_import_folder: Path, required_filenames: list[str] | None = None) -> dict[str, Any]:
    filenames = required_filenames or REQUIRED_CODEX_IMAGEN_FILENAMES
    return {
        "schema_name": "codex_imagen_skill_contract",
        "generation_provider": "codex_desktop_imagen_skill",
        "model_or_skill_label": "GPT-Image-2 / Imagen skill",
        "api_key_required": False,
        "repo_api_call_required": False,
        "repo_secret_storage_allowed": False,
        "output_mode": "file_asset",
        "generated_asset_count_required": len(filenames),
        "exact_filenames_required": filenames,
        "target_import_folder": target_import_folder.as_posix(),
        "semantic_restrictions": [
            "bounded_visual_field_asset_only",
            "no_full_slide_background",
            "no_screenshot_slide",
            "no_readable_required_text",
            "no_letters",
            "no_numbers",
            "no_ui_labels",
            "no_charts",
            "no_tables",
            "no_semantic_icons",
            "no_logo_or_watermark",
            "no_source_citation_footer_text",
            "no_semantic_text_icon_chart_table_rasterization",
        ],
        "validation_after_generation_required": True,
        "d07_2_1_rerun_only_after_files_exist_and_validate": True,
        "manual_external_asset_generation": "fallback_only",
        "canva_parity_claimed": False,
    }


def api_route_reclassification_md(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# API Route Reclassification Report",
            "",
            f"- d07_2_4_api_route_scaffold_status: `{report['d07_2_4_api_route_scaffold_status']}`",
            f"- d07_2_5_api_config_gate_status: `{report['d07_2_5_api_config_gate_status']}`",
            f"- api_key_route_required: `{report['api_key_route_required']}`",
            f"- codex_desktop_imagen_skill_route_required: `{report['codex_desktop_imagen_skill_route_required']}`",
            f"- primary_generation_route: `{report['primary_generation_route']}`",
            f"- api_route_archived_for_non_primary_use: `{report['api_route_archived_for_non_primary_use']}`",
            f"- decision: `{report['decision']}`",
        ]
    ) + "\n"


def codex_imagen_skill_contract_md(contract: dict[str, Any]) -> str:
    lines = [
        "# Codex Imagen Skill Contract",
        "",
        f"- generation_provider: `{contract['generation_provider']}`",
        f"- model_or_skill_label: `{contract['model_or_skill_label']}`",
        f"- api_key_required: `{contract['api_key_required']}`",
        f"- repo_api_call_required: `{contract['repo_api_call_required']}`",
        f"- repo_secret_storage_allowed: `{contract['repo_secret_storage_allowed']}`",
        f"- output_mode: `{contract['output_mode']}`",
        f"- generated_asset_count_required: `{contract['generated_asset_count_required']}`",
        f"- target_import_folder: `{contract['target_import_folder']}`",
        "",
        "## Exact Filenames",
    ]
    lines.extend(f"- `{name}`" for name in contract["exact_filenames_required"])
    lines.extend(["", "## Semantic Restrictions"])
    lines.extend(f"- `{item}`" for item in contract["semantic_restrictions"])
    return "\n".join(lines) + "\n"
