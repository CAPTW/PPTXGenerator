"""Build side-by-side artifacts comparing default PPTX and SceneDeck paths."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..pipeline.pptx_object_validation import (
    PptxObjectValidationReport,
    validate_pptx_objects,
    write_pptx_object_validation_report,
)
from ..pipeline.scene_readiness_gate import (
    SceneReadinessFixtureResult,
    SceneReadinessReport,
    load_scene_readiness_manifest,
    run_scene_readiness_gate_from_file,
    write_scene_readiness_report,
)
from ..pptx_compiler import compile_pptx_from_files, write_pptx_compile_outputs


DEFAULT_VS_SCENE_REPORT_VERSION = "0.1"

ComparisonStatus = Literal["passed", "failed", "issues_reported"]
PathStatus = Literal["passed", "failed", "skipped"]
PocRecommendation = Literal[
    "no_go",
    "not_yet",
    "ready_for_limited_flagged_poc",
    "ready_for_visual_side_by_side",
    "ready_for_default_path_switch_discussion",
]


class DefaultVsSceneModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ObjectInventorySummary(DefaultVsSceneModel):
    shape_count: int = 0
    text_shape_count: int = 0
    picture_count: int = 0
    native_table_count: int = 0
    native_chart_count: int = 0
    group_count: int = 0
    placeholder_count: int = 0
    auto_shape_count: int = 0
    other_shape_count: int = 0


class PathArtifactSummary(DefaultVsSceneModel):
    compile_status: PathStatus = "skipped"
    validation_status: str = "skipped"
    curated_strict_status: str | None = None
    slide_count: int = 0
    warnings_count: int = 0
    findings_count: int = 0
    enforceable_count: int = 0
    style_status: str | None = None
    adapter_status: str | None = None
    object_inventory: ObjectInventorySummary = Field(default_factory=ObjectInventorySummary)
    native_table_count: int = 0
    native_chart_count: int = 0
    picture_count: int = 0
    text_shape_count: int = 0
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class ObjectCoverageComparison(DefaultVsSceneModel):
    slide_count_match: bool
    default_native_chart_count: int
    scene_native_chart_count: int
    default_native_table_count: int
    scene_native_table_count: int
    default_picture_count: int
    scene_picture_count: int
    editable_object_delta: int
    native_data_object_delta: int
    warning_delta: int
    finding_delta: int
    expected_trace_gap_note: str = "Default path has no SceneDeck trace names and is compared only by inventory/basic validation."


class MigrationPocBlocker(DefaultVsSceneModel):
    fixture_id: str
    code: str
    severity: Literal["warning", "error"] = "error"
    message: str
    path: Literal["default", "scene", "comparison"]
    suggested_next_action: str | None = None


class FixtureDefaultVsSceneComparison(DefaultVsSceneModel):
    fixture_id: str
    default: PathArtifactSummary
    scene: PathArtifactSummary
    comparison: ObjectCoverageComparison
    blockers: list[MigrationPocBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifact_paths: dict[str, str] = Field(default_factory=dict)


class DefaultVsSceneComparisonReport(DefaultVsSceneModel):
    report_version: str = DEFAULT_VS_SCENE_REPORT_VERSION
    fixture_count: int
    fixture_ids: list[str]
    overall_status: ComparisonStatus
    default_path_status: ComparisonStatus
    scene_path_status: ComparisonStatus
    scene_curated_strict_status: ComparisonStatus
    comparison_status: ComparisonStatus
    recommendation: PocRecommendation
    blockers: list[MigrationPocBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    per_fixture: list[FixtureDefaultVsSceneComparison] = Field(default_factory=list)
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    structural_hash: str = ""

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return default_vs_scene_report_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return default_vs_scene_report_to_stable_json(self)


def run_default_vs_scene_poc(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    style_policy_path: str | Path | None = None,
    adapter_policy_path: str | Path | None = None,
    fixture_ids: list[str] | None = None,
    write_markdown: bool = False,
) -> DefaultVsSceneComparisonReport:
    manifest_file = Path(manifest_path).resolve()
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = load_scene_readiness_manifest(manifest_file)
    fixtures = manifest.fixtures
    if fixture_ids:
        requested = set(fixture_ids)
        fixtures = [fixture for fixture in fixtures if fixture.fixture_id in requested]
        missing = sorted(requested - {fixture.fixture_id for fixture in fixtures})
        if missing:
            raise KeyError(f"unknown side-by-side fixture ids: {', '.join(missing)}")

    fixture_reports: list[FixtureDefaultVsSceneComparison] = []
    for fixture in fixtures:
        fixture_dir = output_root / "fixtures" / fixture.fixture_id
        default_summary = _run_default_path_for_fixture(
            fixture=fixture,
            manifest_dir=manifest_file.parent,
            fixture_dir=fixture_dir / "default",
        )
        scene_summary, scene_readiness_report = _run_scene_path_for_fixture(
            manifest_path=manifest_file,
            fixture_id=fixture.fixture_id,
            fixture_dir=fixture_dir / "scene",
            style_policy_path=style_policy_path,
            adapter_policy_path=adapter_policy_path,
        )
        comparison = _coverage_comparison(default_summary, scene_summary)
        blockers = _fixture_blockers(fixture.fixture_id, default_summary, scene_summary, comparison)
        fixture_report = FixtureDefaultVsSceneComparison(
            fixture_id=fixture.fixture_id,
            default=default_summary,
            scene=scene_summary,
            comparison=comparison,
            blockers=blockers,
            artifact_paths={
                "default_dir": str((fixture_dir / "default").resolve()),
                "scene_dir": str((fixture_dir / "scene").resolve()),
                "scene_readiness_report": str((fixture_dir / "scene" / "scene-readiness-report.json").resolve()),
            },
        )
        fixture_report_path = fixture_dir / "comparison" / "fixture-comparison-report.json"
        fixture_report_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_report_path.write_text(_stable_json(fixture_report.model_dump(mode="json", exclude_none=True)) + "\n", encoding="utf-8")
        if write_markdown:
            (fixture_dir / "comparison" / "fixture-comparison-summary.md").write_text(
                default_vs_scene_fixture_to_markdown(fixture_report),
                encoding="utf-8",
            )
        fixture_reports.append(fixture_report)

    report = build_default_vs_scene_comparison_report(
        fixture_reports,
        artifact_paths={
            "manifest": str(manifest_file),
            "output_dir": str(output_root),
        },
    )
    report, _, _ = write_default_vs_scene_poc_artifacts(
        report,
        output_path=output_root / "default-vs-scene-report.json",
        markdown_path=(output_root / "default-vs-scene-summary.md") if write_markdown else None,
    )
    return report


def build_default_vs_scene_comparison_report(
    fixture_reports: list[FixtureDefaultVsSceneComparison],
    *,
    artifact_paths: dict[str, str] | None = None,
) -> DefaultVsSceneComparisonReport:
    blockers = [blocker for fixture in fixture_reports for blocker in fixture.blockers]
    warnings = [warning for fixture in fixture_reports for warning in fixture.warnings]
    default_status = _aggregate_path_status([fixture.default.compile_status for fixture in fixture_reports])
    scene_status = _aggregate_path_status([fixture.scene.compile_status for fixture in fixture_reports])
    curated_status = _aggregate_status([fixture.scene.curated_strict_status or "skipped" for fixture in fixture_reports])
    comparison_status: ComparisonStatus = "passed" if not blockers else "failed"
    overall_status: ComparisonStatus = "passed" if default_status == scene_status == curated_status == comparison_status == "passed" else "failed"
    report = DefaultVsSceneComparisonReport(
        fixture_count=len(fixture_reports),
        fixture_ids=[fixture.fixture_id for fixture in fixture_reports],
        overall_status=overall_status,
        default_path_status=default_status,
        scene_path_status=scene_status,
        scene_curated_strict_status=curated_status,
        comparison_status=comparison_status,
        recommendation=_recommendation(default_status, scene_status, curated_status, blockers),
        blockers=blockers,
        warnings=warnings,
        per_fixture=fixture_reports,
        artifact_paths=dict(sorted((artifact_paths or {}).items())),
        structural_hash="",
    )
    return report.model_copy(update={"structural_hash": default_vs_scene_report_structural_hash(report)})


def write_default_vs_scene_poc_artifacts(
    report: DefaultVsSceneComparisonReport,
    *,
    output_path: str | Path,
    markdown_path: str | Path | None = None,
) -> tuple[DefaultVsSceneComparisonReport, Path, Path | None]:
    report_to_write = report.model_copy(update={"structural_hash": default_vs_scene_report_structural_hash(report)})
    json_path = Path(output_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(default_vs_scene_report_to_stable_json(report_to_write) + "\n", encoding="utf-8")
    md_path: Path | None = None
    if markdown_path is not None:
        md_path = Path(markdown_path)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(default_vs_scene_report_to_markdown(report_to_write), encoding="utf-8")
    return report_to_write, json_path, md_path


def default_vs_scene_report_to_stable_payload(
    report: DefaultVsSceneComparisonReport,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = report.model_dump(mode="json", exclude_none=True, by_alias=True)
    if not include_paths:
        payload.pop("artifact_paths", None)
        for fixture in payload.get("per_fixture", []):
            fixture.pop("artifact_paths", None)
            fixture.get("default", {}).pop("artifact_paths", None)
            fixture.get("scene", {}).pop("artifact_paths", None)
    return _normalize_for_stable_json(payload)


def default_vs_scene_report_to_stable_json(report: DefaultVsSceneComparisonReport) -> str:
    return _stable_json(default_vs_scene_report_to_stable_payload(report))


def default_vs_scene_report_structural_hash(report: DefaultVsSceneComparisonReport) -> str:
    payload = default_vs_scene_report_to_stable_payload(report, include_paths=False)
    payload.pop("structural_hash", None)
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def default_vs_scene_report_to_markdown(report: DefaultVsSceneComparisonReport) -> str:
    lines = [
        "# Default vs SceneDeck POC",
        "",
        "## Executive Summary",
        "",
        f"- Overall status: `{report.overall_status}`",
        f"- Recommendation: `{report.recommendation}`",
        f"- Fixtures: {report.fixture_count}",
        f"- Blockers: {len(report.blockers)}",
        "",
        "## Fixture Comparison Matrix",
        "",
        "| Fixture | Default | Scene | Curated Strict | Slide Match | Native Data Delta | Blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for fixture in report.per_fixture:
        lines.append(
            "| "
            + " | ".join(
                [
                    fixture.fixture_id,
                    fixture.default.compile_status,
                    fixture.scene.compile_status,
                    fixture.scene.curated_strict_status or "skipped",
                    str(fixture.comparison.slide_count_match).lower(),
                    str(fixture.comparison.native_data_object_delta),
                    str(len(fixture.blockers)),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Object And Native Coverage", ""])
    for fixture in report.per_fixture:
        lines.append(
            f"- `{fixture.fixture_id}`: default tables/charts="
            f"{fixture.comparison.default_native_table_count}/{fixture.comparison.default_native_chart_count}; "
            f"scene tables/charts={fixture.comparison.scene_native_table_count}/{fixture.comparison.scene_native_chart_count}; "
            f"pictures default/scene={fixture.comparison.default_picture_count}/{fixture.comparison.scene_picture_count}."
        )
    lines.extend(["", "## Warnings And Findings", ""])
    for fixture in report.per_fixture:
        lines.append(
            f"- `{fixture.fixture_id}`: warning_delta={fixture.comparison.warning_delta}, "
            f"finding_delta={fixture.comparison.finding_delta}."
        )
    lines.extend(["", "## Migration POC Blockers", ""])
    if not report.blockers:
        lines.append("No side-by-side blockers were detected.")
    else:
        for blocker in report.blockers:
            lines.append(f"- `{blocker.fixture_id}` `{blocker.path}` `{blocker.code}`: {blocker.message}")
    lines.extend(
        [
            "",
            "## What This Does Not Prove",
            "",
            "This artifact does not switch the default compiler, does not evaluate the default path with scene trace rules, and does not prove visual fidelity.",
            "",
            "## Artifact Paths",
            "",
        ]
    )
    for key, path in sorted(report.artifact_paths.items()):
        lines.append(f"- `{key}`: `{path}`")
    return "\n".join(lines) + "\n"


def default_vs_scene_fixture_to_markdown(fixture: FixtureDefaultVsSceneComparison) -> str:
    return "\n".join(
        [
            f"# Default vs SceneDeck Fixture: {fixture.fixture_id}",
            "",
            f"- Default compile: `{fixture.default.compile_status}`",
            f"- Scene compile: `{fixture.scene.compile_status}`",
            f"- Curated strict: `{fixture.scene.curated_strict_status}`",
            f"- Slide count match: `{str(fixture.comparison.slide_count_match).lower()}`",
            f"- Native data object delta: {fixture.comparison.native_data_object_delta}",
            f"- Blockers: {len(fixture.blockers)}",
            "",
        ]
    )


def summarize_default_vs_scene_report(report: DefaultVsSceneComparisonReport) -> list[str]:
    return [
        (
            "DEFAULT_VS_SCENE_POC "
            f"status={report.overall_status} "
            f"recommendation={report.recommendation} "
            f"fixtures={report.fixture_count} "
            f"default_status={report.default_path_status} "
            f"scene_status={report.scene_path_status} "
            f"curated_strict={report.scene_curated_strict_status} "
            f"blockers={len(report.blockers)}"
        )
    ]


def _run_default_path_for_fixture(*, fixture: Any, manifest_dir: Path, fixture_dir: Path) -> PathArtifactSummary:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    try:
        paths = _state_fixture_paths(fixture, manifest_dir)
        outputs = compile_pptx_from_files(
            blueprint_path=paths["blueprint"],
            design_system_path=paths["design_system"],
            deck_constitution_path=paths["deck_constitution"],
            layout_library_path=paths["layout_library"],
            slide_ledger_path=paths["slide_ledger"],
            asset_manifest_path=paths["asset_manifest"],
            viz_manifest_path=paths["viz_manifest"],
            output_dir=fixture_dir,
            pptx_name="deck.pptx",
            root=paths["root"],
        )
        written = write_pptx_compile_outputs(outputs, fixture_dir)
        compile_summary_path = fixture_dir / "compile-summary.json"
        compile_summary = {
            "deck_title": outputs.build_manifest.deck_title,
            "pptx_path": str(outputs.pptx_path.resolve()),
            "slide_count": outputs.build_manifest.slide_count,
            "warnings": sorted(set([*outputs.build_manifest.warnings, *outputs.compile_report.warnings])),
            "build_manifest_path": str(written["build_manifest"].resolve()),
            "slide_build_linkage_path": str(written["slide_build_linkage"].resolve()),
        }
        compile_summary_path.write_text(_stable_json(compile_summary) + "\n", encoding="utf-8")
        validation_report = validate_pptx_objects(outputs.pptx_path, mode="inspect", profile="basic")
        validation_path = write_pptx_object_validation_report(validation_report, fixture_dir / "pptx-object-report.json")
        inventory = _inventory_from_validation_report(validation_report)
        warnings_count = len(compile_summary["warnings"])
        return _path_summary(
            compile_status="passed",
            validation_report=validation_report,
            inventory=inventory,
            warnings_count=warnings_count,
            artifact_paths={
                "deck_pptx": str(outputs.pptx_path.resolve()),
                "compile_summary": str(compile_summary_path.resolve()),
                "pptx_object_report": str(validation_path.resolve()),
            },
        )
    except Exception as exc:
        return PathArtifactSummary(compile_status="failed", validation_status="skipped", error=str(exc))


def _run_scene_path_for_fixture(
    *,
    manifest_path: Path,
    fixture_id: str,
    fixture_dir: Path,
    style_policy_path: str | Path | None,
    adapter_policy_path: str | Path | None,
) -> tuple[PathArtifactSummary, SceneReadinessReport | None]:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    try:
        report = run_scene_readiness_gate_from_file(
            manifest_path=manifest_path,
            output_dir=fixture_dir,
            fixture_ids=[fixture_id],
            mode="enforce",
            profile="curated-strict",
            style_policy_path=style_policy_path,
            adapter_policy_path=adapter_policy_path,
        )
        report_path = write_scene_readiness_report(report, fixture_dir / "scene-readiness-report.json")
        fixture_result = report.fixtures[0]
        artifact_root = fixture_dir / "fixtures" / fixture_id
        validation_report = PptxObjectValidationReport.model_validate_json(
            (artifact_root / "pptx-object-report.json").read_text(encoding="utf-8")
        )
        inventory = _inventory_from_validation_report(validation_report)
        summary = _path_summary(
            compile_status="passed" if fixture_result.execution_error is None else "failed",
            validation_report=validation_report,
            inventory=inventory,
            warnings_count=fixture_result.compile_warning_count + fixture_result.adapter_warning_count,
            artifact_paths={
                "scene_readiness_report": str(report_path.resolve()),
                "scene_deck": str((artifact_root / "scene-deck.json").resolve()),
                "deck_pptx": str((artifact_root / "deck.pptx").resolve()),
                "scene_compile_report": str((artifact_root / "scene-compile-report.json").resolve()),
                "pptx_object_report": str((artifact_root / "pptx-object-report.json").resolve()),
            },
        )
        summary = summary.model_copy(
            update={
                "curated_strict_status": report.combined_nonvisual_status,
                "style_status": report.style_policy_status,
                "adapter_status": report.adapter_policy_status,
            }
        )
        return summary, report
    except Exception as exc:
        return PathArtifactSummary(compile_status="failed", validation_status="skipped", curated_strict_status="failed", error=str(exc)), None


def _path_summary(
    *,
    compile_status: PathStatus,
    validation_report: PptxObjectValidationReport,
    inventory: ObjectInventorySummary,
    warnings_count: int,
    artifact_paths: dict[str, str],
) -> PathArtifactSummary:
    return PathArtifactSummary(
        compile_status=compile_status,
        validation_status=validation_report.mode_result,
        slide_count=validation_report.slide_count,
        warnings_count=warnings_count,
        findings_count=validation_report.findings_summary.total_findings,
        enforceable_count=validation_report.findings_summary.enforceable_count,
        object_inventory=inventory,
        native_table_count=inventory.native_table_count,
        native_chart_count=inventory.native_chart_count,
        picture_count=inventory.picture_count,
        text_shape_count=inventory.text_shape_count,
        artifact_paths=dict(sorted(artifact_paths.items())),
    )


def _coverage_comparison(default: PathArtifactSummary, scene: PathArtifactSummary) -> ObjectCoverageComparison:
    default_editable = default.text_shape_count + default.native_table_count + default.native_chart_count + default.object_inventory.auto_shape_count
    scene_editable = scene.text_shape_count + scene.native_table_count + scene.native_chart_count + scene.object_inventory.auto_shape_count
    return ObjectCoverageComparison(
        slide_count_match=default.slide_count == scene.slide_count and default.slide_count > 0,
        default_native_chart_count=default.native_chart_count,
        scene_native_chart_count=scene.native_chart_count,
        default_native_table_count=default.native_table_count,
        scene_native_table_count=scene.native_table_count,
        default_picture_count=default.picture_count,
        scene_picture_count=scene.picture_count,
        editable_object_delta=scene_editable - default_editable,
        native_data_object_delta=(scene.native_table_count + scene.native_chart_count) - (default.native_table_count + default.native_chart_count),
        warning_delta=scene.warnings_count - default.warnings_count,
        finding_delta=scene.findings_count - default.findings_count,
    )


def _fixture_blockers(
    fixture_id: str,
    default: PathArtifactSummary,
    scene: PathArtifactSummary,
    comparison: ObjectCoverageComparison,
) -> list[MigrationPocBlocker]:
    blockers: list[MigrationPocBlocker] = []
    if default.compile_status != "passed":
        blockers.append(_blocker(fixture_id, "default_compile_failed", "default", default.error or "Default path compile failed."))
    if scene.compile_status != "passed":
        blockers.append(_blocker(fixture_id, "scene_compile_failed", "scene", scene.error or "Scene path compile failed."))
    if scene.curated_strict_status not in {"passed"}:
        blockers.append(_blocker(fixture_id, "scene_curated_strict_failed", "scene", "Scene curated-strict readiness did not pass."))
    if not comparison.slide_count_match:
        blockers.append(_blocker(fixture_id, "slide_count_mismatch", "comparison", "Default and scene PPTX slide counts differ."))
    if scene.validation_status == "failed":
        blockers.append(_blocker(fixture_id, "scene_object_validation_failed", "scene", "Scene object validation failed."))
    if scene.style_status == "failed":
        blockers.append(_blocker(fixture_id, "scene_style_policy_failed", "scene", "Scene style policy failed."))
    if scene.adapter_status == "failed":
        blockers.append(_blocker(fixture_id, "scene_adapter_policy_failed", "scene", "Scene adapter policy failed."))
    if scene.native_chart_count < default.native_chart_count:
        blockers.append(_blocker(fixture_id, "scene_native_chart_regression", "comparison", "Scene path emitted fewer native charts than default path."))
    if scene.native_table_count < default.native_table_count:
        blockers.append(_blocker(fixture_id, "scene_native_table_regression", "comparison", "Scene path emitted fewer native tables than default path."))
    return sorted(blockers, key=lambda item: (item.fixture_id, item.path, item.code))


def _blocker(fixture_id: str, code: str, path: Literal["default", "scene", "comparison"], message: str) -> MigrationPocBlocker:
    return MigrationPocBlocker(
        fixture_id=fixture_id,
        code=code,
        path=path,
        message=message,
        suggested_next_action="Inspect the side-by-side fixture artifacts before any flagged migration POC.",
    )


def _inventory_from_validation_report(report: PptxObjectValidationReport) -> ObjectInventorySummary:
    counts = ObjectInventorySummary()
    for slide in report.slides:
        slide_counts = slide.inventory.counts
        counts.shape_count += slide_counts.shape_count
        counts.text_shape_count += slide_counts.text_object_count
        counts.picture_count += slide_counts.image_object_count
        counts.native_table_count += slide_counts.native_table_count
        counts.native_chart_count += slide_counts.native_chart_count
        counts.group_count += slide_counts.group_count
        counts.placeholder_count += slide_counts.placeholder_count
        counts.auto_shape_count += slide_counts.auto_shape_count
        counts.other_shape_count += slide_counts.other_shape_count
    return counts


def _state_fixture_paths(fixture: Any, manifest_dir: Path) -> dict[str, Path]:
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
        return manifest_dir.resolve()
    path = Path(root_path)
    if path.is_absolute():
        return path
    return (manifest_dir / path).resolve()


def _aggregate_path_status(statuses: list[str]) -> ComparisonStatus:
    if not statuses or any(status == "failed" for status in statuses):
        return "failed"
    if any(status != "passed" for status in statuses):
        return "issues_reported"
    return "passed"


def _aggregate_status(statuses: list[str]) -> ComparisonStatus:
    if not statuses or any(status in {"failed", "skipped", "disabled"} for status in statuses):
        return "failed"
    if any(status != "passed" for status in statuses):
        return "issues_reported"
    return "passed"


def _recommendation(
    default_status: ComparisonStatus,
    scene_status: ComparisonStatus,
    curated_status: ComparisonStatus,
    blockers: list[MigrationPocBlocker],
) -> PocRecommendation:
    if scene_status == "failed" or curated_status == "failed":
        return "no_go"
    if default_status == "failed" or blockers:
        return "not_yet"
    return "ready_for_limited_flagged_poc"


def _stable_json(payload: Any) -> str:
    return json.dumps(_normalize_for_stable_json(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


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
