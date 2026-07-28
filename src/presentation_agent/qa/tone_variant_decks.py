"""Generate tone-variant decks and report effective token differences."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pptx import Presentation

from ..compiler.deck_compiler import _DeckStyle, compile_final_deck
from ..compiler.design_template_layout_planner import plan_design_template_layouts
from ..design_pipeline.build_design_brief import build_design_brief
from ..generator_contracts import validateDeckAssemblyPlan, validateEditableTemplateSpec, validatePresentationPlan, validateSlideBlueprint
from .final_deck_image_policy import build_final_deck_image_policy_report
from .render_pptx_preview import render_pptx_preview


TONES = ("academic", "professional", "creative")
DEFAULT_TEMPLATE_SPEC = Path("outputs/editable_template_spec.final.json")
DEFAULT_REPORT_JSON = Path("outputs/tone_variant_report.json")
DEFAULT_REPORT_MD = Path("outputs/tone_variant_report.md")


def generate_tone_variant_decks(
    *,
    template_spec_path: str | Path = DEFAULT_TEMPLATE_SPEC,
    output_dir: str | Path = "outputs",
    render: bool = True,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    template_spec_file = Path(template_spec_path)
    spec = _load_json(template_spec_file)
    validateEditableTemplateSpec(spec)

    presentation_plan = _presentation_plan()
    validatePresentationPlan(presentation_plan)
    slide_blueprints = _slide_blueprints()
    for slide in slide_blueprints["slides"]:
        validateSlideBlueprint(slide)
    design_brief = build_design_brief(presentation_plan, slide_blueprints)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "presentation_plan_tone_variant.json").write_text(
        json.dumps(presentation_plan, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "slide_blueprint_tone_variant.json").write_text(
        json.dumps(slide_blueprints, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "design_brief_tone_variant.json").write_text(
        json.dumps(design_brief, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    decks: list[dict[str, Any]] = []
    signatures: dict[str, str] = {}
    for tone in TONES:
        assembly_plan = plan_design_template_layouts(
            slide_blueprints=slide_blueprints,
            presentation_plan={**presentation_plan, "tone": tone},
            editable_template_spec=spec,
            design_brief={**design_brief, "tone": tone},
            template_spec_path=template_spec_file.as_posix(),
        )
        _force_tone(assembly_plan, tone)
        validateDeckAssemblyPlan(assembly_plan)
        assembly_path = output_root / f"deck_assembly_plan_{tone}.json"
        assembly_path.write_text(json.dumps(assembly_plan, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")

        output_pptx = output_root / f"final_deck_{tone}.pptx"
        manifest = compile_final_deck(slide_blueprints, spec, assembly_plan, output_pptx)
        manifest_path = output_root / f"final_deck_{tone}_manifest.json"
        manifest["source_blueprint_path"] = "outputs/slide_blueprint_tone_variant.json"
        manifest["source_assembly_plan_path"] = assembly_path.as_posix()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")

        image_policy = build_final_deck_image_policy_report(
            pptx_path=output_pptx,
            template_spec_path=template_spec_file,
            deck_assembly_plan_path=assembly_path,
        )
        image_report_path = output_root / f"final_deck_{tone}_image_policy_report.json"
        image_report_path.write_text(json.dumps(image_policy, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")

        render_manifest: dict[str, Any] | None = None
        if render:
            render_manifest = render_pptx_preview(
                pptx_path=output_pptx,
                output_dir=output_root / f"final_deck_{tone}_preview_png",
                manifest_path=output_root / f"render_preview_{tone}_manifest.json",
            )

        token_report = _tone_token_report(spec, tone, manifest, assembly_plan)
        signature = json.dumps(token_report["signature"], sort_keys=True)
        signatures[tone] = signature
        decks.append(
            {
                "selected_tone": tone,
                "pptx_path": output_pptx.as_posix(),
                "assembly_plan_path": assembly_path.as_posix(),
                "manifest_path": manifest_path.as_posix(),
                "image_policy_report_path": image_report_path.as_posix(),
                "image_policy_status": image_policy.get("status"),
                "slide_count": len(Presentation(output_pptx).slides),
                "palette_tokens_used": token_report["palette_tokens_used"],
                "typography_tokens_used": token_report["typography_tokens_used"],
                "component_variants_used": token_report["component_variants_used"],
                "footer_style": token_report["footer_style"],
                "card_style": token_report["card_style"],
                "chart_table_style": token_report["chart_table_style"],
                "section_style": token_report["section_style"],
                "background_ornament_intensity": token_report["background_ornament_intensity"],
                "image_frame_style": token_report["image_frame_style"],
                "render_status": (render_manifest or {}).get("render_status"),
                "render_backend": (render_manifest or {}).get("backend"),
                "rendered_preview_paths": (render_manifest or {}).get("output_paths", []),
            }
        )

    unique_signature_count = len(set(signatures.values()))
    all_identical = unique_signature_count <= 1
    image_policy_failed = [deck["selected_tone"] for deck in decks if deck["image_policy_status"] != "passed"]
    report = {
        "schema_name": "tone_variant_report",
        "schema_version": "1.0",
        "status": "failed" if all_identical or image_policy_failed else "passed",
        "template_spec_path": template_spec_file.as_posix(),
        "tone_variants_declared": sorted((((spec.get("tokens") or {}).get("typography") or {}).get("tone_variants") or {}).keys()),
        "same_content_source": {
            "presentation_plan_path": "outputs/presentation_plan_tone_variant.json",
            "slide_blueprint_path": "outputs/slide_blueprint_tone_variant.json",
            "slide_count": len(slide_blueprints["slides"]),
        },
        "unique_token_signature_count": unique_signature_count,
        "all_three_decks_effectively_identical": all_identical,
        "image_policy_failed_tones": image_policy_failed,
        "decks": decks,
    }
    DEFAULT_REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    DEFAULT_REPORT_MD.write_text(_markdown_report(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate three same-content tone decks and report effective token differences.")
    parser.add_argument("--template-spec", type=Path, default=DEFAULT_TEMPLATE_SPEC)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--no-render", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = generate_tone_variant_decks(
            template_spec_path=args.template_spec,
            output_dir=args.output_dir,
            render=not args.no_render,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"TONE_VARIANT_DECKS_FAILED {exc}")
        return 1
    print(f"WROTE {DEFAULT_REPORT_JSON}")
    print(f"WROTE {DEFAULT_REPORT_MD}")
    if report.get("status") != "passed":
        print("TONE_VARIANT_QA failed")
        return 1
    print("TONE_VARIANT_QA passed")
    return 0


def _presentation_plan() -> dict[str, Any]:
    return {
        "schema_name": "presentation_plan",
        "schema_version": "1.0",
        "deck_title": "Evidence-Centered AI Governance Tone Calibration",
        "audience": "AI governance and product leadership reviewers",
        "objective": "Compare how academic, professional, and creative tone variants affect the same editable content.",
        "tone": "Academic + Professional + Creative",
        "source_summary": "A compact calibration source explains evidence-centered AI governance, decision traceability, operating model structure, option comparison, and readiness metrics.",
        "narrative_structure": [
            {"step_id": "n1", "label": "Frame", "purpose": "Introduce the decision-memory theme."},
            {"step_id": "n2", "label": "Structure", "purpose": "Show reusable governance artifacts."},
            {"step_id": "n3", "label": "Measure", "purpose": "Compare choices and readiness metrics."},
        ],
        "sections": [
            {"section_id": "tone-sec-01", "title": "Tone Calibration", "purpose": "Render identical content across tone variants.", "slide_count": 5}
        ],
        "slide_count_target": 5,
        "slide_archetypes_needed": ["creative_cover", "section_divider", "research_overview", "comparison_matrix", "kpi_donut_chart"],
        "constraints": [
            "Use identical slide content across tone variants.",
            "Keep text, tables, charts, cards, labels, and titles editable.",
            "Do not use generated design board images as final slide backgrounds.",
        ],
    }


def _slide_blueprints() -> dict[str, Any]:
    slides = [
        _slide(
            "tone-001",
            "cover",
            "Evidence-Centered AI Governance",
            "Same content rendered through three tone variants",
            "low",
            ["title", "subtitle", "footer"],
            [],
        ),
        _slide(
            "tone-002",
            "section_divider",
            "Decision Memory",
            "Why traceable evidence changes AI adoption quality",
            "low",
            ["title", "section_number", "footer"],
            [_block("tone-002", 1, "section_number", "01")],
        ),
        _slide(
            "tone-003",
            "research_overview",
            "Governance Works Best As Reusable Decision Infrastructure",
            "Artifacts keep assumptions, criteria, and recommendations connected",
            "medium",
            ["title", "cards", "source_summary", "footer"],
            [
                _block("tone-003", 1, "cards", "Evidence anchors preserve source traceability.", "card"),
                _block("tone-003", 2, "cards", "Review criteria keep teams comparable across use cases.", "card"),
                _block("tone-003", 3, "cards", "Reusable artifacts reduce repeated governance effort.", "card"),
                _block("tone-003", 4, "source_summary", "Tone variants should change visual expression without changing slide copy.", "summary"),
            ],
        ),
        _slide(
            "tone-004",
            "comparison_matrix",
            "Hybrid Governance Balances Speed And Judgment",
            "The same matrix should inherit each tone's table style",
            "high",
            ["title", "matrix", "criteria_notes", "footer"],
            [_block("tone-004", 1, "criteria_notes", "Use shared criteria to keep options comparable.", "note")],
            table_data={
                "headers": ["Criterion", "Manual Review", "Structured Pipeline", "Hybrid Governance"],
                "rows": [
                    ["Traceability", "Variable", "High", "High"],
                    ["Speed", "Low", "High", "Medium-High"],
                    ["Expert judgment", "High", "Medium", "High"],
                    ["Portfolio reuse", "Low", "High", "High"],
                ],
            },
        ),
        _slide(
            "tone-005",
            "data_dashboard",
            "Readiness Metrics Direct Reviewer Attention",
            "Chart and KPI modules should inherit tone-specific emphasis",
            "high",
            ["title", "primary_chart", "metric_panels", "footer"],
            [
                _block("tone-005", 1, "metric_panels", "Trace coverage 88%", "metric"),
                _block("tone-005", 2, "metric_panels", "Method consistency 81%", "metric"),
                _block("tone-005", 3, "metric_panels", "Reviewer closure 76%", "metric"),
            ],
            chart_data={
                "categories": ["Trace", "Method", "Closure", "Reuse"],
                "series": [
                    {"name": "Current", "values": [88, 81, 76, 79]},
                    {"name": "Target", "values": [92, 86, 84, 88]},
                ],
            },
        ),
    ]
    return {"schema_name": "slide_blueprint_collection", "schema_version": "1.0", "source_schema_name": "tone_variant_calibration", "slides": slides}


def _slide(
    slide_id: str,
    slide_type: str,
    title: str,
    subtitle: str,
    density: str,
    required_slots: list[str],
    blocks: list[dict[str, Any]],
    *,
    chart_data: dict[str, Any] | None = None,
    table_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": "slide_blueprint",
        "schema_version": "1.0",
        "slide_id": slide_id,
        "section_id": "tone-sec-01",
        "slide_type": slide_type,
        "title": title,
        "subtitle": subtitle,
        "content_density": density,
        "required_slots": required_slots,
        "content_blocks": blocks,
        "chart_data": chart_data,
        "table_data": table_data,
        "image_needs": [],
        "speaker_notes": "Tone calibration slide with identical content across variants.",
        "citations": [{"citation_id": f"{slide_id}-src", "label": "Tone calibration source", "source": "generated-local-tone-calibration"}],
        "design_intent": "Render the same content through the selected academic, professional, or creative tone variant.",
    }


def _block(slide_id: str, index: int, slot: str, content: str, block_type: str = "text") -> dict[str, Any]:
    return {"block_id": f"{slide_id}-b{index:02d}", "slot": slot, "type": block_type, "content": content}


def _force_tone(assembly_plan: dict[str, Any], tone: str) -> None:
    assembly_plan["selected_tone_variant"] = tone
    assembly_plan["deck_id"] = f"{assembly_plan.get('deck_id', 'tone-deck')}-{tone}"
    for binding in assembly_plan.get("slide_layout_bindings") or []:
        if isinstance(binding, dict):
            binding["selected_tone_variant"] = tone


def _tone_token_report(spec: dict[str, Any], tone: str, manifest: dict[str, Any], assembly_plan: dict[str, Any]) -> dict[str, Any]:
    style = _DeckStyle(spec).for_tone(tone)
    tokens = style.report_tokens()
    component_counts = Counter()
    for binding in assembly_plan.get("slide_layout_bindings") or []:
        if not isinstance(binding, dict):
            continue
        for component_id in (binding.get("component_bindings") or {}).values():
            if component_id:
                component_counts[str(component_id)] += 1
    if not component_counts:
        for compiled in manifest.get("compiled_slides") or []:
            component_counts[str(compiled.get("layout_id"))] += 1
    return {
        "palette_tokens_used": tokens["palette"],
        "typography_tokens_used": tokens["typography"],
        "component_variants_used": dict(sorted(component_counts.items())),
        "footer_style": tokens["footer_style"],
        "card_style": tokens["card_style"],
        "chart_table_style": tokens["chart_table_style"],
        "section_style": tokens["section_style"],
        "background_ornament_intensity": tokens["background_ornament_intensity"],
        "image_frame_style": tokens["image_frame_style"],
        "signature": tokens,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Tone Variant Report",
        "",
        f"Status: `{report['status']}`",
        f"Unique token signatures: `{report['unique_token_signature_count']}`",
        f"All decks effectively identical: `{report['all_three_decks_effectively_identical']}`",
        f"Template spec: `{report['template_spec_path']}`",
        "",
        "## Decks",
        "",
    ]
    for deck in report["decks"]:
        lines.extend(
            [
                f"### {deck['selected_tone'].title()}",
                "",
                f"- PPTX: `{deck['pptx_path']}`",
                f"- Image policy: `{deck['image_policy_status']}`",
                f"- Footer style: `{deck['footer_style']}`",
                f"- Card style: `{deck['card_style']}`",
                f"- Chart/table style: `{deck['chart_table_style']}`",
                f"- Section style: `{deck['section_style']}`",
                f"- Background ornament intensity: `{deck['background_ornament_intensity']}`",
                f"- Render: `{deck['render_status']}` via `{deck['render_backend']}`",
                f"- Rendered previews: `{len(deck['rendered_preview_paths'])}`",
                f"- Palette: `{json.dumps(deck['palette_tokens_used'], sort_keys=True)}`",
                f"- Typography: `{json.dumps(deck['typography_tokens_used'], sort_keys=True)}`",
                "",
            ]
        )
    if report["image_policy_failed_tones"]:
        lines.extend(["## Image Policy Failures", "", ", ".join(report["image_policy_failed_tones"])])
    return "\n".join(lines) + "\n"


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
