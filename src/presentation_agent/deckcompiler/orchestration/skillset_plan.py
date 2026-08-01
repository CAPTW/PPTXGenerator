"""Build and validate the executable Codex-to-PNGtoPPTX SkillSet plan."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..identity import content_sha256
from ..manifest_io import read_json, write_json
from ..schemas import validator_for


PLAN_NAME = "skillset_execution_plan.json"
PLAN_SCHEMA = "codex_skillset_execution_plan"
PROJECT_DIRECTORY = "pngtopptx-project"

_SKILLS = (
    (1, "pptx-workflow-architect", "pptx-workflow-architect/SKILL.md", "required_first"),
    (2, "imagegen", ".system/imagegen/SKILL.md", "required"),
    (
        3,
        "slide-editable-deck-orchestrator",
        "slide-editable-deck-orchestrator/SKILL.md",
        "required_coordinator",
    ),
    (
        4,
        "slide-text-layer-inpaint",
        "slide-text-layer-inpaint/SKILL.md",
        "conditional_preprocessor",
    ),
    (
        5,
        "slide-image-dual-render",
        "slide-image-dual-render/SKILL.md",
        "required_renderer",
    ),
    (
        6,
        "slide-visual-polish-qa",
        "slide-visual-polish-qa/SKILL.md",
        "required_visual_qa",
    ),
)

_ENTRYPOINTS = {
    "orchestration_plan": (
        "slide-editable-deck-orchestrator",
        "slide-editable-deck-orchestrator/scripts/plan_deck_workflow.js",
    ),
    "summarize_visual_backlog": (
        "slide-editable-deck-orchestrator",
        "slide-editable-deck-orchestrator/scripts/summarize_visual_backlog.js",
    ),
    "make_repair_wave_plan": (
        "slide-editable-deck-orchestrator",
        "slide-editable-deck-orchestrator/scripts/make_repair_wave_plan.js",
    ),
    "generate_repair_prompt": (
        "slide-editable-deck-orchestrator",
        "slide-editable-deck-orchestrator/scripts/generate_repair_prompt.js",
    ),
    "enforce_orchestration_state": (
        "slide-editable-deck-orchestrator",
        "slide-editable-deck-orchestrator/scripts/enforce_orchestration_state.js",
    ),
    "detect_text_regions": (
        "slide-text-layer-inpaint",
        "slide-text-layer-inpaint/scripts/detect_text_regions.py",
    ),
    "make_text_masks": (
        "slide-text-layer-inpaint",
        "slide-text-layer-inpaint/scripts/make_text_masks.py",
    ),
    "classify_background_regions": (
        "slide-text-layer-inpaint",
        "slide-text-layer-inpaint/scripts/classify_background_regions.py",
    ),
    "repair_text_backgrounds": (
        "slide-text-layer-inpaint",
        "slide-text-layer-inpaint/scripts/repair_text_backgrounds.py",
    ),
    "detect_residual_text": (
        "slide-text-layer-inpaint",
        "slide-text-layer-inpaint/scripts/detect_residual_text.py",
    ),
    "enforce_text_layer": (
        "slide-text-layer-inpaint",
        "slide-text-layer-inpaint/scripts/enforce_text_layer.js",
    ),
    "install_hardlock": (
        "slide-image-dual-render",
        "slide-image-dual-render/scripts/install_hardlock.js",
    ),
    "crop_generator": (
        "slide-image-dual-render",
        "slide-image-dual-render/scripts/make_crops.py",
    ),
    "slide_pipeline": (
        "slide-image-dual-render",
        "slide-image-dual-render/scripts/slide_pipeline.js",
    ),
    "final_gate": (
        "slide-image-dual-render",
        "slide-image-dual-render/scripts/final_gate.js",
    ),
    "rasterize_pptx": (
        "slide-visual-polish-qa",
        "slide-visual-polish-qa/scripts/rasterize_pptx.py",
    ),
    "capture_html_screenshot": (
        "slide-visual-polish-qa",
        "slide-visual-polish-qa/scripts/capture_html_screenshot.py",
    ),
    "compare_slide_images": (
        "slide-visual-polish-qa",
        "slide-visual-polish-qa/scripts/compare_slide_images.py",
    ),
    "generate_visual_qa_summary": (
        "slide-visual-polish-qa",
        "slide-visual-polish-qa/scripts/generate_visual_qa_summary.js",
    ),
    "enforce_visual_qa": (
        "slide-visual-polish-qa",
        "slide-visual-polish-qa/scripts/enforce_visual_qa.js",
    ),
}

NODE_PACKAGES = ("pptxgenjs", "sharp", "react", "react-dom", "react-icons")


def required_skillset_paths() -> tuple[str, ...]:
    """Return the relative files that make an installation execution eligible."""

    values = [relative for _, _, relative, _ in _SKILLS]
    values.extend(relative for _, relative in _ENTRYPOINTS.values())
    return tuple(values)


def resolve_skill_root(explicit: Path | None = None) -> Path:
    """Resolve the directory that directly contains the installed Skill folders."""

    if explicit is not None:
        return explicit.expanduser().resolve()
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    if codex_home:
        candidate = Path(codex_home).expanduser().resolve()
        return candidate if candidate.name.lower() == "skills" else candidate / "skills"
    user_profile = os.environ.get("USERPROFILE", "").strip()
    if user_profile:
        return (Path(user_profile).expanduser().resolve() / ".codex" / "skills")
    return Path.home().resolve() / ".codex" / "skills"


def inspect_skillset(skill_root: Path | None = None) -> dict[str, Any]:
    """Fail closed unless every Skill and official entrypoint is installed."""

    root = resolve_skill_root(skill_root)
    skills: list[dict[str, Any]] = []
    missing: list[str] = []
    for order, name, relative, policy in _SKILLS:
        path = (root / relative).resolve()
        if not path.is_file():
            missing.append(path.as_posix())
            continue
        skills.append(
            {
                "invocation_order": order,
                "skill_name": name,
                "invocation_policy": policy,
                "skill_path": path.as_posix(),
                "sha256": _sha256_file(path),
            }
        )

    entrypoints: dict[str, dict[str, str]] = {}
    for name, (skill_name, relative) in _ENTRYPOINTS.items():
        path = (root / relative).resolve()
        if not path.is_file():
            missing.append(path.as_posix())
            continue
        entrypoints[name] = {
            "skill_name": skill_name,
            "path": path.as_posix(),
            "sha256": _sha256_file(path),
        }

    if missing:
        raise DeckCompilerError(
            "DC_GENERATE_SKILLSET_MISSING",
            "general_generate_workflow",
            "The installed Architect/ImageGen/PNGtoPPTX SkillSet is incomplete: "
            + "; ".join(sorted(missing)),
            root.as_posix(),
            remediation_hint=(
                "Install the required Skills under CODEX_HOME/skills or pass "
                "--skill-root with the verified SkillSet installation root."
            ),
        )

    return {
        "status": "PASS",
        "skill_root": root.as_posix(),
        "skills": skills,
        "entrypoints": entrypoints,
    }


def scaffold_runtime_project(runtime_root: Path) -> Path:
    """Create the mutable external-Skill project without copying Skill code."""

    project = runtime_root / PROJECT_DIRECTORY
    for relative in (
        "src",
        "styles",
        "lib",
        "assets",
        "work",
        "out",
        "out/qa",
    ):
        (project / relative).mkdir(parents=True, exist_ok=False)
    write_json(
        project / "work" / "crop_plan.json",
        {"schema_version": "1.0.0", "crops": []},
    )
    for relative in (
        "architect",
        "image_requests",
        "semantic_sidecars",
        "inspections",
    ):
        (runtime_root / relative).mkdir(parents=True, exist_ok=False)
    return project


def build_skillset_execution_plan(
    *,
    workflow_id: str,
    runtime_root: Path,
    inspection: dict[str, Any],
) -> dict[str, Any]:
    """Build the exact command and artifact contract used by live Codex production."""

    project = (runtime_root / PROJECT_DIRECTORY).resolve()
    entrypoints = inspection["entrypoints"]

    def ep(name: str) -> str:
        return entrypoints[name]["path"]

    project_value = project.as_posix()
    work = (project / "work").as_posix()
    out = (project / "out").as_posix()
    crop_plan = (project / "work" / "crop_plan.json").as_posix()
    node_modules = (project / "node_modules").as_posix()
    final_pptx = (project / "out" / "deck-final-editable.pptx").as_posix()
    final_html = (project / "out" / "deck-final-editable.html").as_posix()
    final_summary = (project / "out" / "visual_qa_summary_final.json").as_posix()

    commands = {
        "install_node_dependencies": [
            "npm",
            "install",
            "--prefix",
            project_value,
            *NODE_PACKAGES,
        ],
        "install_hardlock": [
            "node",
            ep("install_hardlock"),
            "--project",
            project_value,
        ],
        "plan_orchestration": [
            "node",
            ep("orchestration_plan"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--quality-level",
            "polish",
            "--max-iterations",
            "10",
        ],
        "prepare_crops": ["python", ep("crop_generator")],
        "reconstruct_wave": [
            "node",
            ep("slide_pipeline"),
            "--project",
            project_value,
            "--slides",
            "<wave-slides-max-5>",
            "--quality",
            "reconstruction",
            "--require-qa",
            "--require-reconstruction",
            "--crop-plan",
            crop_plan,
            "--node-path",
            node_modules,
            "--target",
            "both",
            "--pptx-out",
            f"{out}/deck-wave-<wave>.pptx",
            "--html-out",
            f"{out}/deck-wave-<wave>.html",
        ],
        "gate_wave": [
            "node",
            ep("final_gate"),
            "--project",
            project_value,
            "--slides",
            "<wave-slides-max-5>",
            "--quality",
            "reconstruction",
            "--require-qa",
            "--require-reconstruction",
            "--require-pptx-openable",
            "--target",
            "both",
            "--pptx",
            f"{out}/deck-wave-<wave>.pptx",
            "--html",
            f"{out}/deck-wave-<wave>.html",
        ],
        "rasterize_wave": [
            "python",
            ep("rasterize_pptx"),
            "--project",
            project_value,
            "--pptx",
            f"{out}/deck-wave-<wave>.pptx",
            "--source-slides",
            "<wave-slides-max-5>",
            "--out-dir",
            work,
        ],
        "capture_wave_html": [
            "python",
            ep("capture_html_screenshot"),
            "--project",
            project_value,
            "--html",
            f"{out}/deck-wave-<wave>.html",
            "--source-slides",
            "<wave-slides-max-5>",
            "--out-dir",
            work,
            "--width",
            "<source-width>",
            "--height",
            "<source-height>",
        ],
        "compare_wave": [
            "python",
            ep("compare_slide_images"),
            "--project",
            project_value,
            "--slides",
            "<wave-slides-max-5>",
            "--mode",
            "qa-polish",
            "--source-dir",
            (project / "src").as_posix(),
            "--qa-dir",
            work,
            "--out-summary",
            f"{out}/visual_qa_summary_wave-<wave>.json",
        ],
        "summarize_wave": [
            "node",
            ep("generate_visual_qa_summary"),
            "--project",
            project_value,
            "--slides",
            "<wave-slides-max-5>",
            "--out-json",
            f"{out}/visual_qa_summary_wave-<wave>.json",
            "--out-md",
            f"{out}/visual_qa_summary_wave-<wave>.md",
        ],
        "enforce_wave_qa": [
            "node",
            ep("enforce_visual_qa"),
            "--project",
            project_value,
            "--slides",
            "<wave-slides-max-5>",
            "--mode",
            "qa-polish",
            "--summary",
            f"{out}/visual_qa_summary_wave-<wave>.json",
            "--require-pptx",
            "--require-html",
        ],
        "summarize_backlog": [
            "node",
            ep("summarize_visual_backlog"),
            "--summary",
            "<latest-visual-qa-summary>",
        ],
        "make_repair_wave_plan": [
            "node",
            ep("make_repair_wave_plan"),
            "--summary",
            "<latest-visual-qa-summary>",
            "--quality-level",
            "polish",
            "--out",
            (project / "work" / "repair_wave_plan.json").as_posix(),
        ],
        "generate_repair_prompt": [
            "node",
            ep("generate_repair_prompt"),
            "--project",
            project_value,
            "--quality-level",
            "polish",
            "--wave-plan",
            (project / "work" / "repair_wave_plan.json").as_posix(),
            "--wave-index",
            "<wave-index>",
        ],
        "final_reconstruction": [
            "node",
            ep("slide_pipeline"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--quality",
            "reconstruction",
            "--require-qa",
            "--require-reconstruction",
            "--allow-large-batch",
            "--crop-plan",
            crop_plan,
            "--node-path",
            node_modules,
            "--target",
            "both",
            "--pptx-out",
            final_pptx,
            "--html-out",
            final_html,
        ],
        "final_gate": [
            "node",
            ep("final_gate"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--quality",
            "reconstruction",
            "--require-qa",
            "--require-reconstruction",
            "--require-pptx-openable",
            "--target",
            "both",
            "--pptx",
            final_pptx,
            "--html",
            final_html,
        ],
        "enforce_orchestration_state": [
            "node",
            ep("enforce_orchestration_state"),
            "--state",
            (project / "work" / "orchestration_state.json").as_posix(),
            "--summary",
            final_summary,
            "--quality-level",
            "polish",
        ],
        "seal_codex_run": [
            "deckcompiler",
            "seal-codex-run",
            "--draft",
            (runtime_root / "codex_run.draft.json").resolve().as_posix(),
            "--output",
            (runtime_root / "codex_run.json").resolve().as_posix(),
        ],
        "register_completion": [
            "deckcompiler",
            "generate",
            "--resume",
            runtime_root.resolve().as_posix(),
            "--codex-run-manifest",
            (runtime_root / "codex_run.json").resolve().as_posix(),
        ],
    }

    payload: dict[str, Any] = {
        "schema_name": PLAN_SCHEMA,
        "schema_version": "1.0.0",
        "workflow_id": workflow_id,
        "status": "READY",
        "skill_root": inspection["skill_root"],
        "ordered_skills": inspection["skills"],
        "official_entrypoints": entrypoints,
        "project_layout": {
            "project_root": project_value,
            "source_png_pattern": (project / "src" / "slideN.png").as_posix(),
            "semantic_sidecar_pattern": (
                runtime_root / "semantic_sidecars" / "slide-NNN.semantic.json"
            ).resolve().as_posix(),
            "per_slide_work_pattern": (project / "work" / "slideXX").as_posix(),
            "profile_path": (project / "styles" / "active.json").as_posix(),
            "slides_source_path": (project / "lib" / "slides.js").as_posix(),
            "crop_plan_path": crop_plan,
            "crop_manifest_path": (project / "assets" / "manifest.json").as_posix(),
            "output_root": out,
        },
        "environment_template": {
            "SLIDE_PIPELINE_STRICT": "1",
            "DECK_PROFILE": (project / "styles" / "active.json").as_posix(),
            "DECK_ASSETS": (project / "assets").as_posix(),
            "DECK_PXW": "<source-width>",
            "DECK_PXH": "<source-height>",
            "CROP_PLAN": crop_plan,
            "SRC_DIR": (project / "src").as_posix(),
        },
        "dependency_contract": {
            "node_packages": list(NODE_PACKAGES),
            "resolution_order": [
                "--node-path",
                "project-local node_modules",
                "installed Skill node_modules",
            ],
            "hidden_node_path_forbidden": True,
        },
        "quality_contract": {
            "orchestrator_quality_level": "polish",
            "renderer_quality": "reconstruction",
            "visual_qa_mode": "qa-polish",
            "max_wave_size": 5,
            "route_hardlock_required": True,
            "reconstruction_hardlock_required": True,
            "pptx_openability_required": True,
            "zero_fail_required": True,
            "zero_blocking_required": True,
            "full_slide_source_raster_forbidden": True,
        },
        "crop_contract": {
            "explicit_crop_plan_required": True,
            "empty_plan_is_valid": True,
            "skip_crops_flag_forbidden_for_final_delivery": True,
            "initial_plan": {"schema_version": "1.0.0", "crops": []},
        },
        "command_templates": commands,
        "required_artifacts": [
            "work/orchestration_state.json",
            "work/crop_plan.json",
            "assets/manifest.json",
            "out/render_trace.json",
            "out/native_object_manifest.json",
            "out/crop_coverage_summary.json",
            "out/qa_evidence_summary.json",
            "out/pptx_openability_debug/pptx_package_validation.json",
            "out/visual_qa_summary_final.json",
            "out/qa/contact_sheet.png",
            "out/deck-final-editable.pptx",
            "out/deck-final-editable.html",
        ],
        "stop_conditions": {
            "complete": (
                "final_gate PASS, PPTX openable, route and reconstruction hardlocks PASS, "
                "and visual QA fail/blocking counts both zero"
            ),
            "needs_repair": "any visual QA fail or blocking slide remains",
            "blocked": "missing Skill, Skill bug, hardlock failure, or PPTX openability failure",
        },
        "content_hash": "0" * 64,
    }
    payload["content_hash"] = _plan_content_hash(payload)
    return payload


def validate_skillset_execution_plan(
    path: Path,
    *,
    expected_workflow_id: str | None = None,
) -> list[str]:
    """Validate schema, content hash, and the exact installed Skill files."""

    try:
        payload = read_json(path)
    except (OSError, ValueError) as exc:
        return [f"skillset execution plan cannot be read: {exc}"]
    issues = [
        f"skillset plan schema:{'.'.join(str(part) for part in issue.path) or '$'}: {issue.message}"
        for issue in sorted(
            validator_for(PLAN_SCHEMA).iter_errors(payload),
            key=lambda item: list(item.path),
        )
    ]
    if issues:
        return issues
    if expected_workflow_id is not None and payload["workflow_id"] != expected_workflow_id:
        issues.append("skillset execution plan workflow_id mismatch")
    if payload["content_hash"] != _plan_content_hash(payload):
        issues.append("skillset execution plan content_hash mismatch")

    for row in payload["ordered_skills"]:
        _validate_bound_file(row["skill_path"], row["sha256"], row["skill_name"], issues)
    for name, row in payload["official_entrypoints"].items():
        _validate_bound_file(row["path"], row["sha256"], f"entrypoint {name}", issues)

    commands = payload["command_templates"]
    _require_flags(
        commands["reconstruct_wave"],
        (
            "--quality",
            "reconstruction",
            "--require-qa",
            "--require-reconstruction",
            "--crop-plan",
            "--node-path",
            "--target",
            "both",
        ),
        "reconstruct_wave",
        issues,
    )
    _require_flags(
        commands["gate_wave"],
        ("--require-pptx-openable", "--require-qa", "--require-reconstruction"),
        "gate_wave",
        issues,
    )
    _require_flags(
        commands["rasterize_wave"],
        ("--source-slides",),
        "rasterize_wave",
        issues,
    )
    _require_flags(
        commands["capture_wave_html"],
        ("--source-slides",),
        "capture_wave_html",
        issues,
    )
    return issues


def _require_flags(
    command: list[str],
    values: tuple[str, ...],
    label: str,
    issues: list[str],
) -> None:
    missing = [value for value in values if value not in command]
    if missing:
        issues.append(f"skillset plan command {label} is missing {missing}")


def _validate_bound_file(
    raw_path: str,
    expected_hash: str,
    label: str,
    issues: list[str],
) -> None:
    path = Path(raw_path)
    if not path.is_file():
        issues.append(f"skillset {label} is missing: {path}")
    elif _sha256_file(path) != expected_hash:
        issues.append(f"skillset {label} hash mismatch: {path}")


def _plan_content_hash(payload: dict[str, Any]) -> str:
    value = dict(payload)
    value.pop("content_hash", None)
    return content_sha256(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


__all__ = [
    "NODE_PACKAGES",
    "PLAN_NAME",
    "PLAN_SCHEMA",
    "PROJECT_DIRECTORY",
    "build_skillset_execution_plan",
    "inspect_skillset",
    "resolve_skill_root",
    "required_skillset_paths",
    "scaffold_runtime_project",
    "validate_skillset_execution_plan",
]
