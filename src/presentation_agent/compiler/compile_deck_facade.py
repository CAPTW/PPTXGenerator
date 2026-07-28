"""Unified facade for deterministic PPTX deck compilation routes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal

from jsonschema.exceptions import ValidationError

from ..pptx_compiler import compile_pptx_from_files, write_pptx_compile_outputs
from .blueprint_adapter import (
    DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH,
    DEFAULT_SLIDE_BLUEPRINT_PATH,
    load_valid_slide_blueprints,
)
from .deck_compiler import (
    DEFAULT_ASSEMBLY_PLAN_PATH,
    DEFAULT_FINAL_TEMPLATE_SPEC_PATH,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_TEMPLATE_SPEC_PATH,
    compile_final_deck_from_files,
)
from .template_spec_selector import (
    TemplateSpecSelection,
    load_explicit_template_spec,
    select_template_spec,
)


CompileMode = Literal["auto", "legacy", "editable_template"]

DEFAULT_PRESENTATION_PLAN_PATH = Path("outputs/presentation_plan.json")
DEFAULT_LEGACY_BLUEPRINT_PATH = Path("state/blueprint.json")
DEFAULT_ROUTE_REPORT_JSON_PATH = Path("outputs/compile_deck_route_report.json")
DEFAULT_ROUTE_REPORT_MD_PATH = Path("outputs/compile_deck_route_report.md")


def compile_deck(
    presentation_plan_path: str | Path | None = None,
    blueprint_path: str | Path | None = None,
    slide_blueprint_path: str | Path | None = None,
    editable_template_spec_path: str | Path | None = None,
    deck_assembly_plan_path: str | Path | None = None,
    output_pptx_path: str | Path | None = None,
    mode: CompileMode = "auto",
) -> Path:
    """Compile a PPTX deck through the selected route and write a route report."""

    if mode not in {"auto", "legacy", "editable_template"}:
        raise ValueError("mode must be one of: auto, legacy, editable_template")

    report = _base_report(
        mode=mode,
        presentation_plan_path=presentation_plan_path,
        blueprint_path=blueprint_path,
        slide_blueprint_path=slide_blueprint_path,
        editable_template_spec_path=editable_template_spec_path,
        deck_assembly_plan_path=deck_assembly_plan_path,
        output_pptx_path=output_pptx_path,
    )
    try:
        output = _compile_deck_inner(
            presentation_plan_path=presentation_plan_path,
            blueprint_path=blueprint_path,
            slide_blueprint_path=slide_blueprint_path,
            editable_template_spec_path=editable_template_spec_path,
            deck_assembly_plan_path=deck_assembly_plan_path,
            output_pptx_path=output_pptx_path,
            mode=mode,
            report=report,
        )
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        _write_route_report(report)
        raise
    report["status"] = "passed"
    report["output_path"] = _display_path(output)
    _write_route_report(report)
    return output


def _compile_deck_inner(
    *,
    presentation_plan_path: str | Path | None,
    blueprint_path: str | Path | None,
    slide_blueprint_path: str | Path | None,
    editable_template_spec_path: str | Path | None,
    deck_assembly_plan_path: str | Path | None,
    output_pptx_path: str | Path | None,
    mode: CompileMode,
    report: dict[str, Any],
) -> Path:
    output = Path(output_pptx_path) if output_pptx_path is not None else DEFAULT_OUTPUT_PATH

    if mode == "editable_template":
        selection = _require_editable_template_selection(editable_template_spec_path)
        return _run_editable_template_route(
            slide_blueprint_path=slide_blueprint_path,
            selection=selection,
            deck_assembly_plan_path=deck_assembly_plan_path,
            output_pptx_path=output,
            report=report,
        )

    if mode == "legacy":
        return _run_legacy_route(
            blueprint_path=blueprint_path,
            output_pptx_path=output,
            report=report,
        )

    selection, selection_warning = _optional_editable_template_selection(editable_template_spec_path)
    if selection is not None:
        if selection_warning is not None:
            report["warnings"].append(selection_warning)
        try:
            return _run_editable_template_route(
                slide_blueprint_path=slide_blueprint_path,
                selection=selection,
                deck_assembly_plan_path=deck_assembly_plan_path,
                output_pptx_path=output,
                report=report,
            )
        except (FileNotFoundError, OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            report["fallback_reasons"].append(
                {
                    "from": "editable_template",
                    "to": "legacy",
                    "reason": f"editable template route unavailable: {exc}",
                }
            )
            report["warnings"].append(
                {
                    "code": "EDITABLE_TEMPLATE_ROUTE_UNAVAILABLE_AUTO_FALLBACK",
                    "severity": "warning",
                    "message": str(exc),
                }
            )
    else:
        report["fallback_reasons"].append(
            {
                "from": "editable_template",
                "to": "legacy",
                "reason": "no valid editable_template_spec.final.json or editable_template_spec.json was available",
            }
        )
        if selection_warning is not None:
            report["warnings"].append(selection_warning)

    return _run_legacy_route(
        blueprint_path=blueprint_path,
        output_pptx_path=output,
        report=report,
    )


def _run_editable_template_route(
    *,
    slide_blueprint_path: str | Path | None,
    selection: TemplateSpecSelection,
    deck_assembly_plan_path: str | Path | None,
    output_pptx_path: Path,
    report: dict[str, Any],
) -> Path:
    requested_slide_blueprint = Path(slide_blueprint_path) if slide_blueprint_path is not None else DEFAULT_SLIDE_BLUEPRINT_PATH
    _slide_blueprints, selected_slide_blueprint = load_valid_slide_blueprints(
        requested_slide_blueprint,
        DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH,
    )
    assembly_plan = Path(deck_assembly_plan_path) if deck_assembly_plan_path is not None else DEFAULT_ASSEMBLY_PLAN_PATH
    output = compile_final_deck_from_files(
        slide_blueprint_path=selected_slide_blueprint,
        template_spec_path=selection.path,
        prefer_final_template_spec=selection.source.get("selection") == "final",
        assembly_plan_path=assembly_plan,
        output_path=output_pptx_path,
        manifest_path=DEFAULT_MANIFEST_PATH,
    )
    report["selected_route"] = "editable_template"
    report["editable_template_final_spec_used"] = selection.source.get("selection") == "final"
    report["slide_blueprint_source"] = "adapted" if selected_slide_blueprint.name == DEFAULT_ADAPTED_SLIDE_BLUEPRINT_PATH.name else "direct"
    report["input_artifacts_used"].update(
        {
            "slide_blueprint": _display_path(selected_slide_blueprint),
            "editable_template_spec": _display_path(selection.path),
            "deck_assembly_plan": _display_path(assembly_plan),
        }
    )
    report["schema_sample_used"] = _schema_sample_used(report["input_artifacts_used"])
    report["warnings"].extend(selection.source.get("warnings") or [])
    return output


def _run_legacy_route(
    *,
    blueprint_path: str | Path | None,
    output_pptx_path: Path,
    report: dict[str, Any],
) -> Path:
    bundle = _legacy_bundle(blueprint_path)
    output_pptx_path.parent.mkdir(parents=True, exist_ok=True)
    outputs = compile_pptx_from_files(
        blueprint_path=bundle["blueprint"],
        design_system_path=bundle["design_system"],
        deck_constitution_path=bundle["deck_constitution"],
        layout_library_path=bundle["layout_library"],
        slide_ledger_path=bundle["slide_ledger"],
        asset_manifest_path=bundle["asset_manifest"],
        viz_manifest_path=bundle["viz_manifest"],
        output_dir=output_pptx_path.parent,
        batch_manifest_path=bundle.get("batch_manifest"),
        state_capsule_path=bundle.get("state_capsule"),
        pptx_name=output_pptx_path.name,
        root=Path.cwd(),
    )
    write_pptx_compile_outputs(outputs, output_pptx_path.parent)
    report["selected_route"] = "legacy"
    report["editable_template_final_spec_used"] = False
    report["slide_blueprint_source"] = None
    report["input_artifacts_used"].update({key: _display_path(path) for key, path in bundle.items() if path is not None})
    report["schema_sample_used"] = _schema_sample_used(report["input_artifacts_used"])
    return output_pptx_path


def _optional_editable_template_selection(
    editable_template_spec_path: str | Path | None,
) -> tuple[TemplateSpecSelection | None, dict[str, Any] | None]:
    try:
        return _require_editable_template_selection(editable_template_spec_path), None
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return None, {
            "code": "NO_VALID_EDITABLE_TEMPLATE_SPEC",
            "severity": "warning",
            "message": str(exc),
        }


def _require_editable_template_selection(editable_template_spec_path: str | Path | None) -> TemplateSpecSelection:
    if editable_template_spec_path is not None:
        return load_explicit_template_spec(editable_template_spec_path)
    return select_template_spec(
        base_template_spec_path=DEFAULT_TEMPLATE_SPEC_PATH,
        final_template_spec_path=DEFAULT_FINAL_TEMPLATE_SPEC_PATH,
        prefer_final=True,
    )


def _legacy_bundle(blueprint_path: str | Path | None) -> dict[str, Path | None]:
    blueprint = Path(blueprint_path) if blueprint_path is not None else DEFAULT_LEGACY_BLUEPRINT_PATH
    if not blueprint.exists():
        raise FileNotFoundError(
            f"legacy blueprint not found at {blueprint.as_posix()}; pass --blueprint pointing to a Gate 2 state blueprint"
        )
    state_dir = blueprint.parent
    required = {
        "blueprint": blueprint,
        "design_system": state_dir / "design-system.json",
        "deck_constitution": state_dir / "deck-constitution.json",
        "layout_library": state_dir / "layout-library.json",
        "slide_ledger": state_dir / "slide-ledger.json",
        "asset_manifest": state_dir / "asset-manifest.json",
        "viz_manifest": state_dir / "viz-manifest.json",
    }
    missing = [path.as_posix() for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"legacy compile state bundle is incomplete: {', '.join(missing)}")
    optional = {
        "batch_manifest": state_dir / "batch-manifest.json",
        "state_capsule": state_dir / "state-capsule.json",
    }
    return {**required, **{key: path if path.exists() else None for key, path in optional.items()}}


def _base_report(
    *,
    mode: CompileMode,
    presentation_plan_path: str | Path | None,
    blueprint_path: str | Path | None,
    slide_blueprint_path: str | Path | None,
    editable_template_spec_path: str | Path | None,
    deck_assembly_plan_path: str | Path | None,
    output_pptx_path: str | Path | None,
) -> dict[str, Any]:
    inputs = {
        "presentation_plan": _optional_display_path(presentation_plan_path or DEFAULT_PRESENTATION_PLAN_PATH),
        "blueprint": _optional_display_path(blueprint_path),
        "slide_blueprint_requested": _optional_display_path(slide_blueprint_path or DEFAULT_SLIDE_BLUEPRINT_PATH),
        "editable_template_spec_requested": _optional_display_path(editable_template_spec_path),
        "deck_assembly_plan_requested": _optional_display_path(deck_assembly_plan_path or DEFAULT_ASSEMBLY_PLAN_PATH),
    }
    return {
        "schema_name": "compile_deck_route_report",
        "schema_version": "1.0",
        "status": "pending",
        "mode": mode,
        "selected_route": None,
        "input_artifacts_requested": inputs,
        "input_artifacts_used": {},
        "fallback_reasons": [],
        "warnings": [],
        "output_path": _optional_display_path(output_pptx_path or DEFAULT_OUTPUT_PATH),
        "editable_template_final_spec_used": False,
        "slide_blueprint_source": None,
        "schema_sample_used": False,
    }


def _write_route_report(report: dict[str, Any]) -> None:
    DEFAULT_ROUTE_REPORT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_ROUTE_REPORT_JSON_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    DEFAULT_ROUTE_REPORT_MD_PATH.write_text(_markdown_report(report), encoding="utf-8")


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Compile Deck Route Report",
        "",
        f"Status: `{report['status']}`",
        f"Mode: `{report['mode']}`",
        f"Selected route: `{report.get('selected_route')}`",
        f"Output: `{report.get('output_path')}`",
        f"Final editable template spec used: `{report.get('editable_template_final_spec_used')}`",
        f"Slide blueprint source: `{report.get('slide_blueprint_source')}`",
        "",
        "## Input Artifacts Used",
        "",
    ]
    if report.get("input_artifacts_used"):
        for key, value in sorted(report["input_artifacts_used"].items()):
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- None")
    if report.get("fallback_reasons"):
        lines.extend(["", "## Fallback Reasons", ""])
        for reason in report["fallback_reasons"]:
            lines.append(f"- `{reason.get('from')}` -> `{reason.get('to')}`: {reason.get('reason')}")
    if report.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- `{warning.get('severity', 'warning')}` `{warning.get('code', 'WARNING')}`: {warning.get('message')}")
    if report.get("error"):
        lines.extend(["", "## Error", "", str(report["error"])])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile a PPTX deck through the canonical route facade.")
    parser.add_argument("--mode", choices=["auto", "legacy", "editable_template"], default="auto")
    parser.add_argument("--presentation-plan", type=Path, default=None)
    parser.add_argument("--blueprint", type=Path, default=None)
    parser.add_argument("--slide-blueprint", type=Path, default=None)
    parser.add_argument("--editable-template-spec", type=Path, default=None)
    parser.add_argument("--deck-assembly-plan", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = compile_deck(
            presentation_plan_path=args.presentation_plan,
            blueprint_path=args.blueprint,
            slide_blueprint_path=args.slide_blueprint,
            editable_template_spec_path=args.editable_template_spec,
            deck_assembly_plan_path=args.deck_assembly_plan,
            output_pptx_path=args.output,
            mode=args.mode,
        )
    except Exception as exc:
        print(f"COMPILE_DECK_FAILED {exc}")
        return 1
    print(f"WROTE {output}")
    return 0


def _display_path(path: Path) -> str:
    return str(path.as_posix())


def _optional_display_path(path: str | Path | None) -> str | None:
    return _display_path(Path(path)) if path is not None else None


def _schema_sample_used(paths: dict[str, Any]) -> bool:
    return any("schema_samples" in str(value).replace("\\", "/") for value in paths.values() if value is not None)


if __name__ == "__main__":
    raise SystemExit(main())
