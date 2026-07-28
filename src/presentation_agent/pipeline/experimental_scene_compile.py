"""Explicitly flagged SceneDeck compile path for migration POCs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..compat.state_io import load_state_file
from ..pipeline.pptx_object_validation import (
    PptxObjectValidationReport,
    ValidationMode,
    validate_pptx_objects,
    write_pptx_object_validation_report,
)
from ..pipeline.scene_adapter_quality import (
    AdapterQualityResult,
    default_adapter_quality_policy,
    evaluate_adapter_quality_policy,
    load_scene_adapter_policy,
)
from ..pipeline.scene_readiness_gate import load_scene_readiness_manifest
from ..pipeline.scene_style_quality import (
    StyleQualityResult,
    default_style_quality_policy,
    evaluate_style_quality_policy,
    load_scene_style_policy,
)
from ..pptx_compiler import adapt_blueprint_to_slide_ir
from ..pptx_scene_compiler import (
    ScenePptxCompileOutputs,
    compile_pptx_from_scene_deck,
    write_scene_pptx_compile_report,
)
from ..slide_scene import scene_deck_to_stable_json
from ..slide_scene_adapter import adapt_slide_ir_document_to_scene_deck, scene_deck_adapter_summary
from ..style_prior import StylePriorProvider


EXPERIMENTAL_SCENE_COMPILE_REPORT_VERSION = "0.1"
RendererPath = Literal["scene_experimental"]
SceneProfile = Literal["none", "scene-strict", "curated-strict"]


class ExperimentalSceneCompileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ExperimentalSceneCompileReport(ExperimentalSceneCompileModel):
    report_version: str = EXPERIMENTAL_SCENE_COMPILE_REPORT_VERSION
    renderer_path: RendererPath = "scene_experimental"
    experimental_scene_renderer: bool = True
    experimental_flag_used: str = "--experimental-scene-renderer"
    fixture_or_state_id: str | None = None
    output_pptx_path: str
    scene_deck_path: str
    scene_compile_report_path: str
    object_validation_report_path: str | None = None
    scene_profile: SceneProfile = "none"
    scene_validation_mode: ValidationMode = "inspect"
    object_validation_status: str = "disabled"
    curated_strict_status: str | None = None
    style_status: str | None = None
    adapter_status: str | None = None
    warnings_count: int = 0
    findings_count: int = 0
    enforceable_count: int = 0
    style_warning_count: int = 0
    adapter_warning_count: int = 0
    structural_hash: str = ""

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return experimental_scene_compile_report_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return experimental_scene_compile_report_to_stable_json(self)


class ExperimentalSceneCompileOutputs(ExperimentalSceneCompileModel):
    report: ExperimentalSceneCompileReport
    scene_outputs: ScenePptxCompileOutputs
    validation_report: PptxObjectValidationReport | None = None
    report_path: str


def compile_pptx_with_experimental_scene_renderer(
    *,
    blueprint_path: str | Path,
    design_system_path: str | Path,
    deck_constitution_path: str | Path,
    layout_library_path: str | Path,
    slide_ledger_path: str | Path,
    asset_manifest_path: str | Path,
    viz_manifest_path: str | Path,
    output_dir: str | Path,
    root: str | Path | None = None,
    pptx_name: str = "deck.pptx",
    enable_layout_critic: bool = True,
    style_prior_provider: StylePriorProvider | None = None,
    scene_validate: bool = False,
    scene_profile: SceneProfile = "none",
    scene_validation_mode: ValidationMode = "inspect",
    style_policy_path: str | Path | None = None,
    adapter_policy_path: str | Path | None = None,
    fixture_or_state_id: str | None = None,
) -> ExperimentalSceneCompileOutputs:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    blueprint = load_state_file(blueprint_path)
    design_system = load_state_file(design_system_path)
    deck_constitution = load_state_file(deck_constitution_path)
    layout_library = load_state_file(layout_library_path)
    slide_ledger = load_state_file(slide_ledger_path)
    asset_manifest = load_state_file(asset_manifest_path)
    viz_manifest = load_state_file(viz_manifest_path)

    slide_ir = adapt_blueprint_to_slide_ir(
        blueprint=blueprint,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        slide_ledger=slide_ledger,
        asset_manifest=asset_manifest,
        viz_manifest=viz_manifest,
        enable_layout_critic=enable_layout_critic,
        style_prior_provider=style_prior_provider,
    )
    scene_deck = adapt_slide_ir_document_to_scene_deck(slide_ir)
    scene_deck_path = output_root / "scene-deck.json"
    scene_deck_path.write_text(scene_deck_to_stable_json(scene_deck) + "\n", encoding="utf-8")
    scene_outputs = compile_pptx_from_scene_deck(
        scene_deck,
        output_root,
        root=root,
        pptx_name=pptx_name,
        scene_deck_path=scene_deck_path,
    )
    scene_compile_report_path = write_scene_pptx_compile_report(
        scene_outputs.report,
        output_root / "scene-compile-report.json",
    )

    validation_report: PptxObjectValidationReport | None = None
    validation_report_path: Path | None = None
    should_validate = scene_validate or scene_profile in {"scene-strict", "curated-strict"}
    object_validation_status = "disabled"
    findings_count = 0
    enforceable_count = 0
    if should_validate:
        validation_report = validate_pptx_objects(
            scene_outputs.pptx_path,
            scene_deck=scene_deck,
            scene_deck_path=scene_deck_path,
            mode=scene_validation_mode,
            profile="scene-strict",
        )
        validation_report_path = write_pptx_object_validation_report(
            validation_report,
            output_root / "pptx-object-report.json",
        )
        object_validation_status = validation_report.mode_result
        findings_count += validation_report.findings_summary.total_findings
        enforceable_count += validation_report.findings_summary.enforceable_count

    style_result = StyleQualityResult(enabled=False)
    adapter_result = AdapterQualityResult(enabled=False)
    adapter_summary = scene_deck_adapter_summary(scene_deck)
    if scene_profile == "curated-strict":
        profile_fixture_id = fixture_or_state_id or "compile-pptx"
        style_policy_file = load_scene_style_policy(style_policy_path) if style_policy_path is not None else None
        style_profile, style_policy = (
            style_policy_file.policy_for_fixture(profile_fixture_id, "style-strict")
            if style_policy_file is not None
            else ("style-strict", default_style_quality_policy())
        )
        style_result = evaluate_style_quality_policy(
            scene_outputs.report,
            policy=style_policy or default_style_quality_policy(),
            profile=style_profile,
            fixture_id=profile_fixture_id,
            deck_id=scene_deck.deck_id,
        )
        adapter_policy_file = load_scene_adapter_policy(adapter_policy_path) if adapter_policy_path is not None else None
        adapter_profile, adapter_policy = (
            adapter_policy_file.policy_for_fixture(profile_fixture_id, "adapter-strict")
            if adapter_policy_file is not None
            else ("adapter-strict", default_adapter_quality_policy())
        )
        adapter_result = evaluate_adapter_quality_policy(
            adapter_summary,
            policy=adapter_policy or default_adapter_quality_policy(),
            profile=adapter_profile,
            fixture_id=profile_fixture_id,
        )
        findings_count += len(style_result.findings) + len(adapter_result.findings)
        enforceable_count += style_result.enforceable_count + adapter_result.enforceable_count

    curated_strict_status = None
    if scene_profile == "curated-strict":
        curated_strict_status = (
            "passed"
            if object_validation_status != "failed" and style_result.passed and adapter_result.passed
            else "failed"
        )

    report = ExperimentalSceneCompileReport(
        fixture_or_state_id=fixture_or_state_id,
        output_pptx_path=str(scene_outputs.pptx_path.resolve()),
        scene_deck_path=str(scene_deck_path.resolve()),
        scene_compile_report_path=str(scene_compile_report_path.resolve()),
        object_validation_report_path=str(validation_report_path.resolve()) if validation_report_path is not None else None,
        scene_profile=scene_profile,
        scene_validation_mode=scene_validation_mode,
        object_validation_status=object_validation_status,
        curated_strict_status=curated_strict_status,
        style_status=style_result.status if scene_profile == "curated-strict" else None,
        adapter_status=adapter_result.status if scene_profile == "curated-strict" else None,
        warnings_count=len(scene_outputs.report.warnings) + adapter_result.summary.adapter_warning_count,
        findings_count=findings_count,
        enforceable_count=enforceable_count,
        style_warning_count=scene_outputs.report.style_warning_count,
        adapter_warning_count=adapter_result.summary.adapter_warning_count,
        structural_hash="",
    )
    report = report.model_copy(update={"structural_hash": experimental_scene_compile_report_structural_hash(report)})
    report_path = write_experimental_scene_compile_report(report, output_root / "experimental-scene-compile-report.json")
    return ExperimentalSceneCompileOutputs(
        report=report,
        scene_outputs=scene_outputs,
        validation_report=validation_report,
        report_path=str(report_path.resolve()),
    )


def compile_experimental_scene_renderer_from_manifest(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    fixture_id: str | None = None,
    style_policy_path: str | Path | None = None,
    adapter_policy_path: str | Path | None = None,
    scene_validate: bool = True,
    scene_profile: SceneProfile = "curated-strict",
    scene_validation_mode: ValidationMode = "enforce",
    pptx_name: str = "deck.pptx",
) -> ExperimentalSceneCompileOutputs:
    manifest_file = Path(manifest_path).resolve()
    manifest = load_scene_readiness_manifest(manifest_file)
    if not manifest.fixtures:
        raise ValueError("scene readiness manifest has no fixtures")
    fixtures = manifest.fixtures
    if fixture_id is not None:
        fixtures = [fixture for fixture in fixtures if fixture.fixture_id == fixture_id]
        if not fixtures:
            raise KeyError(f"unknown scene readiness fixture id: {fixture_id}")
    fixture = fixtures[0]
    if fixture.fixture_kind != "state":
        raise ValueError("flagged scene compile wrapper requires a state fixture")
    paths = _state_fixture_paths(manifest_file.parent, fixture)
    return compile_pptx_with_experimental_scene_renderer(
        blueprint_path=paths["blueprint"],
        design_system_path=paths["design_system"],
        deck_constitution_path=paths["deck_constitution"],
        layout_library_path=paths["layout_library"],
        slide_ledger_path=paths["slide_ledger"],
        asset_manifest_path=paths["asset_manifest"],
        viz_manifest_path=paths["viz_manifest"],
        output_dir=output_dir,
        root=paths["root"],
        pptx_name=pptx_name,
        scene_validate=scene_validate,
        scene_profile=scene_profile,
        scene_validation_mode=scene_validation_mode,
        style_policy_path=style_policy_path,
        adapter_policy_path=adapter_policy_path,
        fixture_or_state_id=fixture.fixture_id,
    )


def write_experimental_scene_compile_report(report: ExperimentalSceneCompileReport, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(experimental_scene_compile_report_to_stable_json(report) + "\n", encoding="utf-8")
    return output


def experimental_scene_compile_report_to_stable_payload(
    report: ExperimentalSceneCompileReport,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True, by_alias=True)
    if not include_paths:
        for key in (
            "output_pptx_path",
            "scene_deck_path",
            "scene_compile_report_path",
            "object_validation_report_path",
        ):
            payload.pop(key, None)
    return _normalize_for_stable_json(payload)


def experimental_scene_compile_report_to_stable_json(report: ExperimentalSceneCompileReport) -> str:
    return json.dumps(
        experimental_scene_compile_report_to_stable_payload(report),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def experimental_scene_compile_report_structural_hash(report: ExperimentalSceneCompileReport) -> str:
    payload = experimental_scene_compile_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def summarize_experimental_scene_compile(outputs: ExperimentalSceneCompileOutputs) -> list[str]:
    report = outputs.report
    return [
        (
            "COMPILE_PPTX "
            "renderer_path=scene_experimental "
            "experimental_scene_renderer=true "
            f"pptx={report.output_pptx_path} "
            f"scene_profile={report.scene_profile} "
            f"object_validation_status={report.object_validation_status} "
            f"curated_strict_status={report.curated_strict_status or 'disabled'} "
            f"style_status={report.style_status or 'disabled'} "
            f"adapter_status={report.adapter_status or 'disabled'} "
            f"warnings={report.warnings_count} "
            f"findings={report.findings_count} "
            f"enforceable={report.enforceable_count}"
        )
    ]


def experimental_scene_compile_failed(report: ExperimentalSceneCompileReport) -> bool:
    if report.scene_validation_mode == "enforce" and report.enforceable_count > 0:
        return True
    return report.curated_strict_status == "failed" or report.object_validation_status == "failed"


def _state_fixture_paths(manifest_dir: Path, fixture: Any) -> dict[str, Path]:
    root = _resolve_root(manifest_dir, fixture.root_path)

    def resolve(path_text: str | None) -> Path:
        if not path_text:
            raise ValueError("state fixture path is required")
        path = Path(path_text)
        if path.is_absolute():
            return path
        return (root / path).resolve()

    return {
        "root": root,
        "blueprint": resolve(fixture.blueprint_path),
        "design_system": resolve(fixture.design_system_path),
        "deck_constitution": resolve(fixture.deck_constitution_path),
        "layout_library": resolve(fixture.layout_library_path),
        "slide_ledger": resolve(fixture.slide_ledger_path),
        "asset_manifest": resolve(fixture.asset_manifest_path),
        "viz_manifest": resolve(fixture.viz_manifest_path),
    }


def _resolve_root(manifest_dir: Path, root_path: str | None) -> Path:
    if root_path is None:
        return manifest_dir
    path = Path(root_path)
    if path.is_absolute():
        return path
    return (manifest_dir / path).resolve()


def _normalize_for_stable_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_for_stable_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_for_stable_json(item) for item in value]
    if isinstance(value, float):
        normalized = round(value, 6)
        if normalized == 0:
            return 0
        if float(normalized).is_integer():
            return int(normalized)
        return normalized
    return value
