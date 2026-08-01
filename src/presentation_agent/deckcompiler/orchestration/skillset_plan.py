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
    initial_pptx = (project / "out" / "deck-initial-editable.pptx").as_posix()
    initial_html = (project / "out" / "deck-initial-editable.html").as_posix()
    initial_summary = (project / "out" / "visual_qa_summary_initial.json").as_posix()
    initial_summary_md = (project / "out" / "visual_qa_summary_initial.md").as_posix()
    final_summary = (project / "out" / "visual_qa_summary_final.json").as_posix()
    final_summary_md = (project / "out" / "visual_qa_summary_final.md").as_posix()

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
        "initial_reconstruction": [
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
            initial_pptx,
            "--html-out",
            initial_html,
        ],
        "initial_gate": [
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
            initial_pptx,
            "--html",
            initial_html,
        ],
        "rasterize_initial": [
            "python",
            ep("rasterize_pptx"),
            "--project",
            project_value,
            "--pptx",
            initial_pptx,
            "--source-slides",
            "<slides>",
            "--out-dir",
            work,
        ],
        "capture_initial_html": [
            "python",
            ep("capture_html_screenshot"),
            "--project",
            project_value,
            "--html",
            initial_html,
            "--source-slides",
            "<slides>",
            "--out-dir",
            work,
            "--width",
            "<source-width>",
            "--height",
            "<source-height>",
        ],
        "compare_initial": [
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
            initial_summary,
        ],
        "summarize_initial": [
            "node",
            ep("generate_visual_qa_summary"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--out-json",
            initial_summary,
            "--out-md",
            initial_summary_md,
        ],
        "enforce_initial_qa": [
            "node",
            ep("enforce_visual_qa"),
            "--project",
            project_value,
            "--slides",
            "<slides>",
            "--mode",
            "qa-polish",
            "--summary",
            initial_summary,
            "--require-pptx",
            "--require-html",
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
        "rasterize_final": [
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
        "capture_final_html": [
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
        "compare_final": [
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
        "summarize_final": [
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
        "enforce_final_qa": [
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
        "schema_version": "1.2.0",
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
            "semantic_sidecar_pattern": (
                runtime_root / "semantic_sidecars" / "slide-NNN.semantic.json"
            )
            .resolve()
            .as_posix(),
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
            "initial_full_deck_qa_required": True,
            "final_full_deck_qa_required": True,
            "source_slide_mapping_required": True,
            "full_slide_source_raster_forbidden": True,
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
                "prepare_crops",
            ],
            "initial_full_deck": [
                "initial_reconstruction",
                "initial_gate",
                "rasterize_initial",
                "capture_initial_html",
                "compare_initial",
                "summarize_initial",
                "enforce_initial_qa",
                "summarize_backlog",
            ],
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
                "summarize_backlog",
            ],
            "final_full_deck": [
                "final_reconstruction",
                "final_gate",
                "rasterize_final",
                "capture_final_html",
                "compare_final",
                "summarize_final",
                "enforce_final_qa",
                "enforce_orchestration_state",
            ],
            "completion": ["seal_codex_run", "register_completion"],
            "repair_exit_codes": {
                "enforce_initial_qa": [0, 1],
                "enforce_wave_qa": [0, 1],
                "enforce_final_qa": [0],
            },
            "max_repair_iterations": 10,
        },
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
            "out/visual_qa_summary_final.md",
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
    for label in ("initial_reconstruction", "final_reconstruction"):
        _require_flags(
            commands[label],
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
            label,
            issues,
        )
    for label in ("initial_gate", "final_gate"):
        _require_flags(
            commands[label],
            ("--require-pptx-openable", "--require-qa", "--require-reconstruction"),
            label,
            issues,
        )
    for label in ("rasterize_initial", "rasterize_final"):
        _require_flags(
            commands[label],
            ("--source-slides",),
            label,
            issues,
        )
    for label in ("capture_initial_html", "capture_final_html"):
        _require_flags(
            commands[label],
            ("--source-slides", "--width", "--height"),
            label,
            issues,
        )
    for label in ("compare_initial", "compare_final"):
        _require_flags(
            commands[label],
            ("--mode", "qa-polish", "--out-summary"),
            label,
            issues,
        )
    for label in ("summarize_initial", "summarize_final"):
        _require_flags(
            commands[label],
            ("--out-json", "--out-md"),
            label,
            issues,
        )
    for label in ("enforce_initial_qa", "enforce_final_qa"):
        _require_flags(
            commands[label],
            (
                "--mode",
                "qa-polish",
                "--summary",
                "--require-pptx",
                "--require-html",
            ),
            label,
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
