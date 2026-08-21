"""Build and validate the executable Codex-to-PNGtoPPTX SkillSet plan."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from ..errors import DeckCompilerError
from ..identity import content_sha256
from ..manifest_io import read_json, write_json
from ..schemas import REPO_ROOT, validator_for
from .quality_acceptance import CANARY_METRIC_LIMITS
from .execution_profiles import execution_profile_payload


PLAN_NAME = "skillset_execution_plan.json"
PLAN_SCHEMA = "codex_skillset_execution_plan"
PROJECT_DIRECTORY = "pngtopptx-project"
REPOSITORY_ARCHITECT_RELATIVE_ROOT = Path(".agents/skills/pptx-workflow-architect")

_REPOSITORY_SKILL_FILES = (
    ("skill", "SKILL.md"),
    ("design_system", "references/design-system.md"),
    ("large_deck", "references/large-deck.md"),
    ("production_qa", "references/production-qa.md"),
)

_SKILLS = (
    (1, "pptx-workflow-architect", "SKILL.md", "required_first", "repository"),
    (2, "imagegen", ".system/imagegen/SKILL.md", "required", "external"),
    (
        3,
        "slide-editable-deck-orchestrator",
        "slide-editable-deck-orchestrator/SKILL.md",
        "required_coordinator",
        "external",
    ),
    (
        4,
        "slide-text-layer-inpaint",
        "slide-text-layer-inpaint/SKILL.md",
        "conditional_preprocessor",
        "external",
    ),
    (
        5,
        "slide-image-dual-render",
        "slide-image-dual-render/SKILL.md",
        "required_renderer",
        "external",
    ),
    (
        6,
        "slide-visual-polish-qa",
        "slide-visual-polish-qa/SKILL.md",
        "required_visual_qa",
        "external",
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
    "validate_agent_work": (
        "slide-image-dual-render",
        "slide-image-dual-render/scripts/validate_agent_work.js",
    ),
    "integrate_subagent_work": (
        "slide-image-dual-render",
        "slide-image-dual-render/scripts/integrate_subagent_work.js",
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
    """Return external installation files required beside the Repo Architect."""

    values = [
        relative
        for _, _, relative, _, distribution in _SKILLS
        if distribution == "external"
    ]
    values.extend(relative for _, relative in _ENTRYPOINTS.values())
    return tuple(values)


def required_repository_skillset_paths() -> tuple[str, ...]:
    """Return Repo-relative files that form the Architect Skill package."""

    return tuple(
        (REPOSITORY_ARCHITECT_RELATIVE_ROOT / relative).as_posix()
        for _, relative in _REPOSITORY_SKILL_FILES
    )


def resolve_skill_root(explicit: Path | None = None) -> Path:
    """Resolve the external ImageGen and PNGtoPPTX installation root."""

    if explicit is not None:
        return explicit.expanduser().resolve()
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    if codex_home:
        candidate = Path(codex_home).expanduser().resolve()
        return candidate if candidate.name.lower() == "skills" else candidate / "skills"
    user_profile = os.environ.get("USERPROFILE", "").strip()
    if user_profile:
        return Path(user_profile).expanduser().resolve() / ".codex" / "skills"
    return Path.home().resolve() / ".codex" / "skills"


def resolve_repository_architect_root(repo_root: Path | None = None) -> Path:
    """Resolve the tracked, repository-owned Architect Skill directory."""

    root = REPO_ROOT if repo_root is None else repo_root
    return (root.resolve() / REPOSITORY_ARCHITECT_RELATIVE_ROOT).resolve()


def inspect_skillset(
    skill_root: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Fail closed unless the Repo Architect and external companions are complete."""

    external_root = resolve_skill_root(skill_root)
    repository_root = resolve_repository_architect_root(repo_root)
    skills: list[dict[str, Any]] = []
    missing: list[str] = []
    repository_files: dict[str, dict[str, str]] = {}
    for label, relative in _REPOSITORY_SKILL_FILES:
        path = (repository_root / relative).resolve()
        if not path.is_file():
            missing.append(path.as_posix())
            continue
        repository_files[label] = {
            "path": path.as_posix(),
            "sha256": _sha256_file(path),
        }

    for order, name, relative, policy, distribution in _SKILLS:
        base = repository_root if distribution == "repository" else external_root
        path = (base / relative).resolve()
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
        path = (external_root / relative).resolve()
        if not path.is_file():
            missing.append(path.as_posix())
            continue
        entrypoints[name] = {
            "skill_name": skill_name,
            "path": path.as_posix(),
            "sha256": _sha256_file(path),
        }

    if missing:
        artifact_root = (
            repository_root
            if any(Path(item).is_relative_to(repository_root) for item in missing)
            else external_root
        )
        raise DeckCompilerError(
            "DC_GENERATE_SKILLSET_MISSING",
            "general_generate_workflow",
            "The repository Architect or installed ImageGen/PNGtoPPTX SkillSet "
            "is incomplete: " + "; ".join(sorted(missing)),
            artifact_root.as_posix(),
            remediation_hint=(
                "Restore .agents/skills/pptx-workflow-architect from the Git "
                "checkout, and install ImageGen/PNGtoPPTX companions under "
                "CODEX_HOME/skills or pass --skill-root with their verified root."
            ),
        )

    return {
        "status": "PASS",
        "skill_root": external_root.as_posix(),
        "repository_skill_root": repository_root.as_posix(),
        "repository_skill_files": repository_files,
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
        "image_batches",
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
    execution_profile_name: str = "sol-medium",
) -> dict[str, Any]:
    """Build the exact command and artifact contract used by live Codex production."""

    project = (runtime_root / PROJECT_DIRECTORY).resolve()
    runtime_profile = execution_profile_payload(execution_profile_name)
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
    preview_pptx = (project / "out" / "deck-shared-preview.pptx").as_posix()
    preview_html = (project / "out" / "deck-shared-preview.html").as_posix()
    preview_summary = (project / "out" / "visual_qa_summary_preview.json").as_posix()
    preview_summary_md = (project / "out" / "visual_qa_summary_preview.md").as_posix()
    final_summary = (project / "out" / "visual_qa_summary_final.json").as_posix()
    final_summary_md = (project / "out" / "visual_qa_summary_final.md").as_posix()
    reconstruction_jobs = (project / "work" / "reconstruction_job_manifest.json").as_posix()
    integration_report = (project / "work" / "integration_report.md").as_posix()

    commands = {
        "install_node_dependencies": [
            "npm",
            "install",
            "--prefix",
            project_value,
            "--prefer-offline",
            "--no-audit",
            "--no-fund",
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
            "2",
        ],
        "prepare_streaming_execution": [
            "deckcompiler",
            "prepare-streaming-execution",
            "--runtime",
            runtime_root.resolve().as_posix(),
        ],
        "accept_streaming_image": [
            "deckcompiler",
            "accept-streaming-image",
            "--runtime",
            runtime_root.resolve().as_posix(),
            "--slide",
            "<completed-slide>",
            "--tool-call-id",
            "<imagegen-tool-call-id>",
            "--queued-at",
            "<queued-at>",
            "--started-at",
            "<started-at>",
            "--completed-at",
            "<completed-at>",
        ],
        "record_reconstruction_started": [
            "deckcompiler",
            "record-streaming-reconstruction",
            "--runtime",
            runtime_root.resolve().as_posix(),
            "--slide",
            "<ready-slide>",
            "--status",
            "STARTED",
            "--timestamp",
            "<started-at>",
        ],
        "record_authoring_completed": [
            "deckcompiler",
            "record-streaming-reconstruction",
            "--runtime",
            runtime_root.resolve().as_posix(),
            "--slide",
            "<completed-slide>",
            "--status",
            "AUTHORING_COMPLETED",
            "--timestamp",
            "<completed-at>",
        ],
        "finalize_streaming_images": [
            "deckcompiler",
            "finalize-streaming-images",
            "--runtime",
            runtime_root.resolve().as_posix(),
        ],
        "validate_streaming_execution": [
            "deckcompiler",
            "validate-streaming-execution",
            "--runtime",
            runtime_root.resolve().as_posix(),
            "--require-complete",
            "--require-authoring-complete",
            "--require-overlap",
        ],
        "prepare_reconstruction_jobs": [
            "deckcompiler",
            "prepare-reconstruction-jobs",
            "--runtime",
            runtime_root.resolve().as_posix(),
        ],
        "codex_execute_reconstruction_jobs": [
            "CODEX_AGENT_ACTION",
            "execute-ready-reconstruction-jobs",
            "--state",
            (runtime_root / "streaming_execution.json").resolve().as_posix(),
            "--fresh-context-per-slide",
            "--max-parallel-workers",
            str(runtime_profile["max_reconstruction_workers"]),
        ],
        "validate_reconstruction_jobs": [
            "deckcompiler",
            "validate-reconstruction-jobs",
            "--runtime",
            runtime_root.resolve().as_posix(),
            "--require-authoring-outputs",
        ],
        "validate_agent_work": [
            "node",
            ep("validate_agent_work"),
            "--work",
            work,
            "--slides",
            "<slides>",
        ],
        "integrate_agent_work": [
            "node",
            ep("integrate_subagent_work"),
        ],
        "prepare_crops": ["python", ep("crop_generator")],
        "compile_shared_preview": [
            "node",
            ep("slide_pipeline"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--quality",
            "canary",
            "--allow-large-batch",
            "--crop-plan",
            crop_plan,
            "--node-path",
            node_modules,
            "--target",
            "both",
            "--pptx-out",
            preview_pptx,
            "--html-out",
            preview_html,
        ],
        "rasterize_shared_preview": [
            "python",
            ep("rasterize_pptx"),
            "--project",
            project_value,
            "--pptx",
            preview_pptx,
            "--source-slides",
            "<slides>",
            "--out-dir",
            work,
        ],
        "capture_shared_preview_html": [
            "python",
            ep("capture_html_screenshot"),
            "--project",
            project_value,
            "--html",
            preview_html,
            "--source-slides",
            "<slides>",
            "--out-dir",
            work,
            "--width",
            "<source-width>",
            "--height",
            "<source-height>",
        ],
        "compare_shared_preview": [
            "python",
            ep("compare_slide_images"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--mode",
            "qa-polish",
            "--source-dir",
            (project / "src").as_posix(),
            "--qa-dir",
            work,
            "--out-summary",
            preview_summary,
        ],
        "summarize_shared_preview": [
            "node",
            ep("generate_visual_qa_summary"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--out-json",
            preview_summary,
            "--out-md",
            preview_summary_md,
        ],
        "enforce_shared_preview_qa": [
            "node",
            ep("enforce_visual_qa"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--mode",
            "qa-polish",
            "--summary",
            preview_summary,
            "--require-pptx",
            "--require-html",
        ],
        "enforce_shared_preview_quality_acceptance": [
            "deckcompiler",
            "validate-visual-quality",
            "--project",
            project_value,
            "--summary",
            preview_summary,
            "--slides",
            "<slides>",
        ],
        "finalize_source_mapped_qa": [
            "deckcompiler",
            "finalize-shared-render-qa",
            "--runtime",
            runtime_root.resolve().as_posix(),
            "--summary",
            preview_summary,
        ],
        "validate_reconstruction_qa": [
            "deckcompiler",
            "validate-reconstruction-jobs",
            "--runtime",
            runtime_root.resolve().as_posix(),
            "--require-worker-outputs",
        ],
        "compile_full_deck": [
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
        "gate_full_deck": [
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
        "rasterize_full_deck": [
            "python",
            ep("rasterize_pptx"),
            "--project",
            project_value,
            "--pptx",
            final_pptx,
            "--source-slides",
            "<slides>",
            "--out-dir",
            work,
        ],
        "capture_full_html": [
            "python",
            ep("capture_html_screenshot"),
            "--project",
            project_value,
            "--html",
            final_html,
            "--source-slides",
            "<slides>",
            "--out-dir",
            work,
            "--width",
            "<source-width>",
            "--height",
            "<source-height>",
        ],
        "compare_full_deck": [
            "python",
            ep("compare_slide_images"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--mode",
            "qa-polish",
            "--source-dir",
            (project / "src").as_posix(),
            "--qa-dir",
            work,
            "--out-summary",
            final_summary,
        ],
        "summarize_full_deck": [
            "node",
            ep("generate_visual_qa_summary"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--out-json",
            final_summary,
            "--out-md",
            final_summary_md,
        ],
        "enforce_full_deck_qa": [
            "node",
            ep("enforce_visual_qa"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--mode",
            "qa-polish",
            "--summary",
            final_summary,
            "--require-pptx",
            "--require-html",
        ],
        "enforce_full_deck_quality_acceptance": [
            "deckcompiler",
            "validate-visual-quality",
            "--project",
            project_value,
            "--summary",
            final_summary,
            "--slides",
            "<slides>",
        ],
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
        "enforce_wave_quality_acceptance": [
            "deckcompiler",
            "validate-visual-quality",
            "--project",
            project_value,
            "--summary",
            f"{out}/visual_qa_summary_wave-<wave>.json",
            "--slides",
            "<wave-slides-max-5>",
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
        "enforce_orchestration_state": [
            "node",
            ep("enforce_orchestration_state"),
            "--state",
            (project / "work" / "orchestration_state.json").as_posix(),
            "--summary",
            final_summary,
            "--quality-level",
            "polish",
            "--require-artifacts",
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
        "schema_version": "1.5.0",
        "workflow_id": workflow_id,
        "status": "READY",
        "skill_root": inspection["skill_root"],
        "repository_skill_root": inspection["repository_skill_root"],
        "repository_skill_files": inspection["repository_skill_files"],
        "ordered_skills": inspection["skills"],
        "official_entrypoints": entrypoints,
        "project_layout": {
            "project_root": project_value,
            "source_png_pattern": (project / "src" / "slideN.png").as_posix(),
            "image_batch_manifest_path": (
                runtime_root / "image_batches" / "image_generation_batch_manifest.json"
            )
            .resolve()
            .as_posix(),
            "image_request_manifest_path": (
                runtime_root / "image_requests" / "image_request_manifest.json"
            )
            .resolve()
            .as_posix(),
            "streaming_execution_path": (runtime_root / "streaming_execution.json")
            .resolve()
            .as_posix(),
            "timing_report_path": (runtime_root / "execution_timing.json")
            .resolve()
            .as_posix(),
            "semantic_sidecar_pattern": (
                runtime_root / "semantic_sidecars" / "slide-NNN.semantic.json"
            )
            .resolve()
            .as_posix(),
            "per_slide_work_pattern": (project / "work" / "slideXX").as_posix(),
            "reconstruction_job_manifest_path": reconstruction_jobs,
            "integration_report_path": integration_report,
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
            "WORK_DIR": work,
            "SLIDES_OUT": (project / "lib" / "slides.js").as_posix(),
            "CROP_PLAN_OUT": crop_plan,
            "INTEGRATION_REPORT_OUT": integration_report,
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
        "execution_profile": {
            **runtime_profile,
            "default_design_direction": [
                "Academic",
                "Informative",
                "Professional",
                "Creative",
            ],
            "prompt_policy": {
                "mode": "concise_content_adaptive",
                "preserve_user_direction": True,
                "blanket_layout_bans_forbidden": True,
                "hard_numeric_density_caps_forbidden": True,
                "preparation_mode": "single_deterministic_pass",
                "preparation_command": (
                    "deckcompiler prepare-image-requests --runtime <runtime>"
                ),
                "additional_model_call_required": False,
                "architect_lineage_required": True,
            },
            "image_generation": {
                "batch_size": 20,
                "dispatch_mode": "concurrent_wave",
                "acceptance_mode": "streaming_ready_queue",
                "call_strategy": "one_independent_builtin_call_per_slide",
                "initial_variants_per_slide": 1,
                "max_regenerations_per_slide": 1,
                "automatic_canary": False,
                "compile_after_all_images": True,
                "reconstruction_starts_before_all_images_complete": True,
            },
            "reconstruction_authoring": {
                "context_unit": "one_source_slide_per_fresh_context",
                "dispatch_mode": "streaming_ready_queue_bounded_workers",
                "max_parallel_workers": runtime_profile[
                    "max_reconstruction_workers"
                ],
                "shared_file_writer": "integrator_only",
                "worker_scope": "one_slide_work_directory_only",
                "worker_model": runtime_profile["target_model"],
                "worker_reasoning_effort": runtime_profile[
                    "target_reasoning_effort"
                ],
                "token_policy": (
                    "compact_job_plus_one_source_slide_no_full_deck_duplication"
                ),
                "isolated_dual_render_qa_required": False,
                "shared_render_source_mapped_qa_required": True,
            },
            "compilation": {
                "per_slide_isolated_builds": 0,
                "shared_preview_full_deck_invocation": True,
                "final_reconstruction_full_deck_invocation": True,
                "full_deck_render_count_without_repair": 2,
                "post_repair_recompile_only": True,
            },
            "performance_target": {
                "baseline_minutes_20_slides": 120,
                "target_minutes_20_slides": 30,
                "target_speedup": 4.0,
                "measurement_required": True,
                "quality_gates_take_precedence": True,
            },
        },
        "quality_contract": {
            "orchestrator_quality_level": "polish",
            "renderer_quality": "reconstruction",
            "visual_qa_mode": "qa-polish",
            "max_repair_wave_size": 5,
            "route_hardlock_required": True,
            "reconstruction_hardlock_required": True,
            "pptx_openability_required": True,
            "zero_fail_required": True,
            "zero_blocking_required": True,
            "per_slide_isolated_render_forbidden": True,
            "shared_preview_render_required": True,
            "final_reconstruction_render_required": True,
            "final_full_deck_qa_required": True,
            "source_slide_mapping_required": True,
            "full_slide_source_raster_forbidden": True,
            "high_fidelity_acceptance_required": True,
            "allowed_needs_polish_issue_types": [
                "palette_drift",
                "pptx_html_edge_mismatch",
            ],
            "quality_reference_baseline": "accepted_one_slide_canary_20260808",
            "allowed_needs_polish_metric_limits": CANARY_METRIC_LIMITS,
        },
        "crop_contract": {
            "explicit_crop_plan_required": True,
            "empty_plan_is_valid": True,
            "skip_crops_flag_forbidden_for_final_delivery": True,
            "initial_plan": {"schema_version": "1.0.0", "crops": []},
        },
        "command_templates": commands,
        "execution_contract": {
            "setup": [
                "install_node_dependencies",
                "install_hardlock",
                "plan_orchestration",
            ],
            "streaming_image_generation": [
                "prepare_streaming_execution",
                "accept_streaming_image",
                "record_reconstruction_started",
                "record_authoring_completed",
            ],
            "reconstruction_authoring": [
                "codex_execute_reconstruction_jobs",
                "finalize_streaming_images",
                "validate_streaming_execution",
                "validate_reconstruction_jobs",
                "validate_agent_work",
                "integrate_agent_work",
                "prepare_crops",
            ],
            "shared_preview_qa": [
                "compile_shared_preview",
                "rasterize_shared_preview",
                "capture_shared_preview_html",
                "compare_shared_preview",
                "summarize_shared_preview",
                "enforce_shared_preview_qa",
                "enforce_shared_preview_quality_acceptance",
                "finalize_source_mapped_qa",
                "validate_reconstruction_qa",
            ],
            "final_compile_fast_path": [
                "compile_full_deck",
                "gate_full_deck",
                "rasterize_full_deck",
                "capture_full_html",
                "compare_full_deck",
                "summarize_full_deck",
                "enforce_full_deck_qa",
                "enforce_full_deck_quality_acceptance",
            ],
            "fast_path_acceptance": ["enforce_orchestration_state"],
            "repair_wave_loop": [
                "make_repair_wave_plan",
                "generate_repair_prompt",
                "reconstruct_wave",
                "gate_wave",
                "rasterize_wave",
                "capture_wave_html",
                "compare_wave",
                "summarize_wave",
                "enforce_wave_qa",
                "enforce_wave_quality_acceptance",
                "summarize_backlog",
            ],
            "post_repair_recompile": [
                "compile_full_deck",
                "gate_full_deck",
                "rasterize_full_deck",
                "capture_full_html",
                "compare_full_deck",
                "summarize_full_deck",
                "enforce_full_deck_qa",
                "enforce_full_deck_quality_acceptance",
                "enforce_orchestration_state",
            ],
            "completion": ["seal_codex_run", "register_completion"],
            "repair_exit_codes": {
                "enforce_shared_preview_qa": [0, 1],
                "enforce_full_deck_qa_fast_path": [0, 1],
                "enforce_wave_qa": [0, 1],
                "enforce_full_deck_qa_post_repair": [0],
            },
            "max_repair_iterations": 2,
            "full_deck_render_count_without_repair": 2,
        },
        "required_artifacts": [
            "../streaming_execution.json",
            "../image_requests/image_request_manifest.json",
            "../image_batches/image_generation_batch_manifest.json",
            "../execution_timing.json",
            "work/reconstruction_job_manifest.json",
            "work/integration_report.md",
            "work/orchestration_state.json",
            "work/crop_plan.json",
            "assets/manifest.json",
            "out/render_trace.json",
            "out/native_object_manifest.json",
            "out/crop_coverage_summary.json",
            "out/qa_evidence_summary.json",
            "out/pptx_openability_debug/pptx_package_validation.json",
            "out/visual_qa_summary_final.json",
            "out/visual_qa_summary_final.md",
            "out/qa/contact_sheet.png",
            "out/deck-final-editable.pptx",
            "out/deck-final-editable.html",
        ],
        "stop_conditions": {
            "complete": (
                "single fast-path or conditional post-repair full-deck gate PASS, "
                "PPTX openable, route and reconstruction hardlocks PASS, "
                "high-fidelity issue policy accepted, and visual QA fail/blocking "
                "counts both zero"
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
    """Validate schema, content hash, Repo Skill, and installed companions."""

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
    if (
        expected_workflow_id is not None
        and payload["workflow_id"] != expected_workflow_id
    ):
        issues.append("skillset execution plan workflow_id mismatch")
    if payload["content_hash"] != _plan_content_hash(payload):
        issues.append("skillset execution plan content_hash mismatch")

    expected_repository_root = resolve_repository_architect_root()
    if Path(payload["repository_skill_root"]).resolve() != expected_repository_root:
        issues.append("skillset execution plan repository_skill_root mismatch")
    for label, relative in _REPOSITORY_SKILL_FILES:
        row = payload["repository_skill_files"][label]
        expected_path = (expected_repository_root / relative).resolve()
        if Path(row["path"]).resolve() != expected_path:
            issues.append(f"repository Architect {label} path mismatch")
        _validate_bound_file(
            row["path"],
            row["sha256"],
            f"repository Architect {label}",
            issues,
        )
    architect = payload["ordered_skills"][0]
    architect_file = payload["repository_skill_files"]["skill"]
    if (
        Path(architect["skill_path"]).resolve()
        != Path(architect_file["path"]).resolve()
        or architect["sha256"] != architect_file["sha256"]
    ):
        issues.append(
            "ordered Architect Skill must match the repository-owned Skill file"
        )

    for row in payload["ordered_skills"]:
        _validate_bound_file(
            row["skill_path"], row["sha256"], row["skill_name"], issues
        )
    for name, row in payload["official_entrypoints"].items():
        _validate_bound_file(row["path"], row["sha256"], f"entrypoint {name}", issues)

    commands = payload["command_templates"]
    _require_flags(
        commands["install_node_dependencies"],
        ("--prefer-offline", "--no-audit", "--no-fund"),
        "install_node_dependencies",
        issues,
    )
    _require_flags(
        commands["plan_orchestration"],
        ("--quality-level", "polish", "--max-iterations", "2"),
        "plan_orchestration",
        issues,
    )
    _require_flags(
        commands["prepare_streaming_execution"],
        ("prepare-streaming-execution", "--runtime"),
        "prepare_streaming_execution",
        issues,
    )
    _require_flags(
        commands["accept_streaming_image"],
        (
            "accept-streaming-image",
            "--runtime",
            "--slide",
            "--tool-call-id",
            "--queued-at",
            "--started-at",
            "--completed-at",
        ),
        "accept_streaming_image",
        issues,
    )
    _require_flags(
        commands["finalize_streaming_images"],
        ("finalize-streaming-images", "--runtime"),
        "finalize_streaming_images",
        issues,
    )
    _require_flags(
        commands["validate_streaming_execution"],
        (
            "validate-streaming-execution",
            "--runtime",
            "--require-complete",
            "--require-authoring-complete",
            "--require-overlap",
        ),
        "validate_streaming_execution",
        issues,
    )
    _require_flags(
        commands["prepare_reconstruction_jobs"],
        ("prepare-reconstruction-jobs", "--runtime"),
        "prepare_reconstruction_jobs",
        issues,
    )
    _require_flags(
        commands["codex_execute_reconstruction_jobs"],
        ("--state", "--fresh-context-per-slide", "--max-parallel-workers", "6"),
        "codex_execute_reconstruction_jobs",
        issues,
    )
    _require_flags(
        commands["validate_reconstruction_jobs"],
        ("validate-reconstruction-jobs", "--runtime", "--require-authoring-outputs"),
        "validate_reconstruction_jobs",
        issues,
    )
    _require_flags(
        commands["compile_shared_preview"],
        (
            "--quality",
            "canary",
            "--allow-large-batch",
            "--crop-plan",
            "--node-path",
            "--target",
            "both",
        ),
        "compile_shared_preview",
        issues,
    )
    _require_flags(
        commands["finalize_source_mapped_qa"],
        ("finalize-shared-render-qa", "--runtime", "--summary"),
        "finalize_source_mapped_qa",
        issues,
    )
    _require_flags(
        commands["validate_reconstruction_qa"],
        ("validate-reconstruction-jobs", "--runtime", "--require-worker-outputs"),
        "validate_reconstruction_qa",
        issues,
    )
    _require_flags(
        commands["validate_agent_work"],
        ("--work", "--slides"),
        "validate_agent_work",
        issues,
    )
    _require_flags(
        commands["compile_full_deck"],
        (
            "--quality",
            "reconstruction",
            "--require-qa",
            "--require-reconstruction",
            "--allow-large-batch",
            "--crop-plan",
            "--node-path",
            "--target",
            "both",
        ),
        "compile_full_deck",
        issues,
    )
    _require_flags(
        commands["gate_full_deck"],
        (
            "--require-pptx-openable",
            "--require-qa",
            "--require-reconstruction",
        ),
        "gate_full_deck",
        issues,
    )
    _require_flags(
        commands["rasterize_full_deck"],
        ("--source-slides",),
        "rasterize_full_deck",
        issues,
    )
    _require_flags(
        commands["capture_full_html"],
        ("--source-slides", "--width", "--height"),
        "capture_full_html",
        issues,
    )
    _require_path_suffixes(
        commands["compile_full_deck"],
        ("deck-final-editable.pptx", "deck-final-editable.html"),
        "compile_full_deck",
        issues,
    )
    _require_path_suffixes(
        commands["gate_full_deck"],
        ("deck-final-editable.pptx", "deck-final-editable.html"),
        "gate_full_deck",
        issues,
    )
    _require_path_suffixes(
        commands["rasterize_full_deck"],
        ("deck-final-editable.pptx",),
        "rasterize_full_deck",
        issues,
    )
    _require_path_suffixes(
        commands["capture_full_html"],
        ("deck-final-editable.html",),
        "capture_full_html",
        issues,
    )
    _require_flags(
        commands["compare_full_deck"],
        ("--mode", "qa-polish", "--out-summary"),
        "compare_full_deck",
        issues,
    )
    _require_flags(
        commands["summarize_full_deck"],
        ("--out-json", "--out-md"),
        "summarize_full_deck",
        issues,
    )
    _require_flags(
        commands["enforce_full_deck_qa"],
        (
            "--mode",
            "qa-polish",
            "--summary",
            "--require-pptx",
            "--require-html",
        ),
        "enforce_full_deck_qa",
        issues,
    )
    _require_flags(
        commands["enforce_full_deck_quality_acceptance"],
        ("validate-visual-quality", "--project", "--summary", "--slides"),
        "enforce_full_deck_quality_acceptance",
        issues,
    )
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
    _require_flags(
        commands["enforce_wave_quality_acceptance"],
        ("validate-visual-quality", "--project", "--summary", "--slides"),
        "enforce_wave_quality_acceptance",
        issues,
    )
    _require_flags(
        commands["enforce_orchestration_state"],
        ("--summary", "--quality-level", "polish", "--require-artifacts"),
        "enforce_orchestration_state",
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


def _require_path_suffixes(
    command: list[str],
    suffixes: tuple[str, ...],
    label: str,
    issues: list[str],
) -> None:
    missing = [
        suffix
        for suffix in suffixes
        if not any(value.replace("\\", "/").endswith(suffix) for value in command)
    ]
    if missing:
        issues.append(f"skillset plan command {label} is missing output {missing}")


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
    "REPOSITORY_ARCHITECT_RELATIVE_ROOT",
    "build_skillset_execution_plan",
    "inspect_skillset",
    "required_repository_skillset_paths",
    "resolve_skill_root",
    "resolve_repository_architect_root",
    "required_skillset_paths",
    "scaffold_runtime_project",
    "validate_skillset_execution_plan",
]
