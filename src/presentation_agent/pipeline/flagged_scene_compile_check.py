"""CI-friendly check wrapper for the explicit SceneDeck compile flag."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..pipeline.experimental_scene_compile import (
    ExperimentalSceneCompileOutputs,
    compile_experimental_scene_renderer_from_manifest,
    experimental_scene_compile_failed,
)


FLAGGED_SCENE_COMPILE_CHECK_VERSION = "0.1"
FLAGGED_SCENE_COMPILE_CHECK_SUMMARY_NAME = "flagged-scene-compile-check-summary.json"
FlaggedSceneCompileCheckStatus = Literal["passed", "failed"]


class FlaggedSceneCompileCheckModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class FlaggedSceneCompileCheckSummary(FlaggedSceneCompileCheckModel):
    report_version: str = FLAGGED_SCENE_COMPILE_CHECK_VERSION
    check_name: str = "flagged-scene-compile-check"
    fixture_id: str | None = None
    status: FlaggedSceneCompileCheckStatus
    default_compile_status: str = "not_run"
    scene_compile_status: str
    renderer_path: str
    experimental_scene_renderer: bool
    scene_profile: str
    scene_validation_mode: str
    object_validation_status: str
    curated_strict_status: str | None = None
    style_status: str | None = None
    adapter_status: str | None = None
    warnings_count: int
    findings_count: int
    enforceable_count: int
    output_paths: dict[str, str] = Field(default_factory=dict)
    structural_hash: str = ""

    def to_stable_payload(self, *, include_paths: bool = True) -> dict[str, Any]:
        return flagged_scene_compile_check_summary_to_stable_payload(self, include_paths=include_paths)

    def to_stable_json(self) -> str:
        return flagged_scene_compile_check_summary_to_stable_json(self)


class FlaggedSceneCompileCheckOutputs(FlaggedSceneCompileCheckModel):
    summary: FlaggedSceneCompileCheckSummary
    compile_outputs: ExperimentalSceneCompileOutputs
    summary_path: str


def run_flagged_scene_compile_check(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    fixture_id: str | None = None,
    style_policy_path: str | Path | None = None,
    adapter_policy_path: str | Path | None = None,
) -> FlaggedSceneCompileCheckOutputs:
    """Run the curated flagged SceneDeck compile smoke check.

    The check intentionally does not run screenshots, visual diff, or visual
    baselines. It writes scene artifacts under ``<output-dir>/scene`` and a
    compact CI summary at ``<output-dir>/flagged-scene-compile-check-summary.json``.
    """

    output_root = Path(output_dir).resolve()
    scene_output_dir = output_root / "scene"
    compile_outputs = compile_experimental_scene_renderer_from_manifest(
        manifest_path=manifest_path,
        output_dir=scene_output_dir,
        fixture_id=fixture_id,
        style_policy_path=style_policy_path,
        adapter_policy_path=adapter_policy_path,
        scene_validate=True,
        scene_profile="curated-strict",
        scene_validation_mode="enforce",
    )
    summary = build_flagged_scene_compile_check_summary(
        compile_outputs,
        output_dir=output_root,
        scene_output_dir=scene_output_dir,
    )
    summary_path = write_flagged_scene_compile_check_summary(
        summary,
        output_root / FLAGGED_SCENE_COMPILE_CHECK_SUMMARY_NAME,
    )
    return FlaggedSceneCompileCheckOutputs(
        summary=summary,
        compile_outputs=compile_outputs,
        summary_path=str(summary_path.resolve()),
    )


def build_flagged_scene_compile_check_summary(
    compile_outputs: ExperimentalSceneCompileOutputs,
    *,
    output_dir: str | Path,
    scene_output_dir: str | Path,
) -> FlaggedSceneCompileCheckSummary:
    report = compile_outputs.report
    scene_compile_status = "passed" if Path(report.output_pptx_path).is_file() else "failed"
    failed = experimental_scene_compile_failed(report) or scene_compile_status == "failed"
    output_paths = {
        "output_dir": str(Path(output_dir).resolve()),
        "scene_output_dir": str(Path(scene_output_dir).resolve()),
        "deck_pptx": report.output_pptx_path,
        "scene_deck": report.scene_deck_path,
        "scene_compile_report": report.scene_compile_report_path,
        "experimental_scene_compile_report": str(Path(compile_outputs.report_path).resolve()),
    }
    if report.object_validation_report_path is not None:
        output_paths["pptx_object_report"] = report.object_validation_report_path
    summary = FlaggedSceneCompileCheckSummary(
        fixture_id=report.fixture_or_state_id,
        status="failed" if failed else "passed",
        scene_compile_status=scene_compile_status,
        renderer_path=report.renderer_path,
        experimental_scene_renderer=report.experimental_scene_renderer,
        scene_profile=report.scene_profile,
        scene_validation_mode=report.scene_validation_mode,
        object_validation_status=report.object_validation_status,
        curated_strict_status=report.curated_strict_status,
        style_status=report.style_status,
        adapter_status=report.adapter_status,
        warnings_count=report.warnings_count,
        findings_count=report.findings_count,
        enforceable_count=report.enforceable_count,
        output_paths=output_paths,
        structural_hash="",
    )
    return summary.model_copy(update={"structural_hash": flagged_scene_compile_check_summary_structural_hash(summary)})


def write_flagged_scene_compile_check_summary(
    summary: FlaggedSceneCompileCheckSummary,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(flagged_scene_compile_check_summary_to_stable_json(summary) + "\n", encoding="utf-8")
    return output


def flagged_scene_compile_check_summary_to_stable_payload(
    summary: FlaggedSceneCompileCheckSummary,
    *,
    include_paths: bool = True,
) -> dict[str, Any]:
    payload = summary.model_dump(mode="json", exclude_none=True, by_alias=True)
    if not include_paths:
        payload.pop("output_paths", None)
    return _normalize_for_stable_json(payload)


def flagged_scene_compile_check_summary_to_stable_json(summary: FlaggedSceneCompileCheckSummary) -> str:
    return json.dumps(
        flagged_scene_compile_check_summary_to_stable_payload(summary),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def flagged_scene_compile_check_summary_structural_hash(summary: FlaggedSceneCompileCheckSummary) -> str:
    payload = flagged_scene_compile_check_summary_to_stable_payload(summary, include_paths=False)
    payload.pop("structural_hash", None)
    stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def summarize_flagged_scene_compile_check(outputs: FlaggedSceneCompileCheckOutputs) -> list[str]:
    summary = outputs.summary
    return [
        (
            "FLAGGED_SCENE_COMPILE_CHECK "
            f"status={summary.status} "
            f"fixture_id={summary.fixture_id or 'unknown'} "
            f"renderer_path={summary.renderer_path} "
            f"experimental_scene_renderer={str(summary.experimental_scene_renderer).lower()} "
            f"scene_profile={summary.scene_profile} "
            f"scene_validation_mode={summary.scene_validation_mode} "
            f"object_validation_status={summary.object_validation_status} "
            f"curated_strict_status={summary.curated_strict_status or 'disabled'} "
            f"style_status={summary.style_status or 'disabled'} "
            f"adapter_status={summary.adapter_status or 'disabled'} "
            f"warnings={summary.warnings_count} "
            f"findings={summary.findings_count} "
            f"enforceable={summary.enforceable_count}"
        )
    ]


def flagged_scene_compile_check_failed(summary: FlaggedSceneCompileCheckSummary) -> bool:
    return summary.status == "failed"


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
