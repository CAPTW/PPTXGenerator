"""Fresh isolated Phase 6.1 reconstruction and evidence reachability runner."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from PIL import Image

from ..identity import content_sha256
from ..manifest_io import write_json
from ..pngtopptx_handoff import HandoffError, export_phase4_handoff, validate_handoff
from .composite import CompositeQAError, bind_external_visual_reconciliation, run_composite_qa
from .contracts import sha256_file
from .evidence_capsule import (
    EvidenceCapsuleError,
    bind_current_output_evidence,
    build_evidence_capsule,
    materialize_per_slide_crop_evidence,
    seal_reconstruction_scores,
)
from .external_visual_qa import (
    ExternalVisualQAError,
    build_external_visual_qa_reconciliation,
    parse_external_visual_qa,
)
from .html_capture import HtmlCaptureError, capture_official_html_screenshots


SLIDES = tuple(range(1, 7))
SOURCE_EXPECTATIONS = {
    "slides.js": "8130f47caa5decf4e1df5343f405fcc79ff18f6d7c6e1880d7e56733d45ae20b",
    "native_table.js": "91375691f036cb9ce42a0085ca84eb14ba28b621b5e468cdc4dc6248771dd22e",
}


@dataclass(frozen=True)
class ReachabilityConfig:
    repo_root: Path
    runtime_root: Path
    source_commit: str
    run_id: str
    fault_state: str
    created_at: str
    external_skill_root: Path
    profile_path: Path
    node_modules: Path
    node_executable: Path
    python_executable: Path
    baseline: bool = True
    expected_finding_ids: tuple[str, ...] = ()

    @property
    def phase4_bundle(self) -> Path:
        return self.repo_root / "examples" / "deckcompiler_demo" / "phase4"

    @property
    def phase5_bundle(self) -> Path:
        return self.repo_root / "examples" / "deckcompiler_demo" / "phase5"

    @property
    def pin_path(self) -> Path:
        return self.repo_root / "docs" / "devpost" / "evidence" / "pngtopptx_external_skillset_pin.json"

    @property
    def source_template(self) -> Path:
        return self.repo_root / "src" / "presentation_agent" / "deckcompiler" / "qa" / "reconstruction_source"


@dataclass(frozen=True)
class EvidencePipelineResult:
    runtime_root: Path
    project_root: Path
    run_id: str
    handoff_id: str
    pptx_path: Path
    html_path: Path
    capsule_path: Path
    reachability_report_path: Path
    composite_qa_dir: Path
    external_reconciliation_path: Path
    status: str
    pptx_sha256: str
    html_sha256: str


def _command_label(index: int, name: str) -> str:
    return f"{index:02d}-{name.replace(' ', '-').lower()}"


def _run_command(
    *,
    command: Sequence[str],
    cwd: Path,
    env: Mapping[str, str],
    logs_dir: Path,
    index: int,
    name: str,
    accepted_returncodes: set[int] | None = None,
    blocker: str = "BLOCKED_FAULT_HARNESS_BASELINE_UNREACHABLE",
    timeout: int = 300,
) -> dict[str, Any]:
    accepted = accepted_returncodes or {0}
    result = subprocess.run(
        [str(value) for value in command],
        cwd=cwd,
        env=dict(env),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    logs_dir.mkdir(parents=True, exist_ok=True)
    label = _command_label(index, name)
    (logs_dir / f"{label}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (logs_dir / f"{label}.stderr.log").write_text(result.stderr, encoding="utf-8")
    record = {
        "stage": name,
        "executable": Path(command[0]).name,
        "returncode": result.returncode,
        "accepted_returncodes": sorted(accepted),
        "stdout_log": f"logs/{label}.stdout.log",
        "stderr_log": f"logs/{label}.stderr.log",
        "status": "PASS" if result.returncode in accepted else "BLOCKED",
    }
    if result.returncode not in accepted:
        tail = (result.stderr or result.stdout)[-1500:]
        raise EvidenceCapsuleError(blocker, f"{name} returned {result.returncode}: {tail}")
    return record


def _query_powerpoint_version() -> str:
    try:
        import win32com.client  # type: ignore[import-not-found]

        app = win32com.client.DispatchEx("PowerPoint.Application")
        try:
            return str(app.Version)
        finally:
            app.Quit()
    except Exception as exc:  # pragma: no cover - Windows/Office gate
        raise EvidenceCapsuleError("BLOCKED_FAULT_HARNESS_BASELINE_UNREACHABLE", f"PowerPoint COM unavailable: {exc}") from exc


def _stage_reconstruction_source(config: ReachabilityConfig, project: Path) -> dict[str, Any]:
    provenance = json.loads((config.source_template / "provenance.json").read_text(encoding="utf-8"))
    for name, expected in SOURCE_EXPECTATIONS.items():
        source = config.source_template / name
        if not source.is_file() or sha256_file(source) != expected or provenance.get(f"{name.replace('.', '_')}_sha256") not in {None, expected}:
            raise EvidenceCapsuleError("BLOCKED_REPAIR_OWNER_UNPROVEN", f"reconstruction source provenance mismatch: {name}")
        shutil.copy2(source, project / "lib" / name)
    return {
        "owner": provenance["owner_classification"],
        "producer_contract": provenance["producer_contract"],
        "slides_js_sha256": sha256_file(project / "lib" / "slides.js"),
        "native_table_js_sha256": sha256_file(project / "lib" / "native_table.js"),
        "higher_geometry_source_present": provenance["higher_geometry_source_present"],
        "source_template_paths": [
            "src/presentation_agent/deckcompiler/qa/reconstruction_source/slides.js",
            "src/presentation_agent/deckcompiler/qa/reconstruction_source/native_table.js",
        ],
    }


def _materialize_reconstruction_records(
    project: Path,
    *,
    run_id: str,
    fault_state: str,
    source_commit: str,
    created_at: str,
) -> None:
    native = json.loads((project / "out" / "native_object_manifest.json").read_text(encoding="utf-8"))
    slides_js_hash = sha256_file(project / "lib" / "slides.js")
    for slide in SLIDES:
        slide_dir = project / "work" / f"slide{slide:02d}"
        source = project / "src" / f"slide{slide}.png"
        sidecar = slide_dir / "semantic_sidecar.json"
        with Image.open(source) as image:
            width, height = image.size
        native_slide = native.get("slides", {}).get(str(slide), {})
        write_json(
            slide_dir / "measurements.json",
            {
                "schema_name": "pngtopptx_slide_measurements",
                "schema_version": "observed_external_contract_v1",
                "project_run_id": run_id,
                "fault_state": fault_state,
                "slide": slide,
                "source_image": f"src/slide{slide}.png",
                "source_sha256": sha256_file(source),
                "canvas_px": {"width": width, "height": height},
                "native_object_counts": native_slide.get("counts", {}),
                "measurement_authority": "fresh source image plus official native_object_manifest",
            },
        )
        write_json(
            slide_dir / "profile_override.json",
            {
                "schema_name": "pngtopptx_slide_profile_override",
                "schema_version": "observed_external_contract_v1",
                "slide": slide,
                "project_run_id": run_id,
                "fault_state": fault_state,
                "profile": "corporate-light",
                "canvas_px": {"width": width, "height": height},
                "override_count": 0,
                "overrides": {},
            },
        )
        (slide_dir / "reconstruction_notes.md").write_text(
            "\n".join(
                (
                    f"# Slide {slide:02d} reconstruction notes",
                    "",
                    "The project-owned reconstruction source binds the fresh semantic Sidecar to native editable text, panels, rules, and the declared native table.",
                    f"Current source image SHA-256: `{sha256_file(source)}`.",
                    f"Current reconstruction source SHA-256: `{slides_js_hash}`.",
                    "No source image is used as a slide background or semantic raster surface.",
                    "",
                )
            ),
            encoding="utf-8",
        )
        (slide_dir / "editability_inventory.md").write_text(
            "\n".join(
                (
                    f"# Slide {slide:02d} editability inventory",
                    "",
                    f"- Native editable objects: {native_slide.get('editableObjectCount', 0)}",
                    f"- Native editable text length: {native_slide.get('editableTextLength', 0)}",
                    f"- Native text objects: {native_slide.get('counts', {}).get('text', 0)}",
                    f"- Native tables: {native_slide.get('counts', {}).get('tables', 0)}",
                    "- Full-slide pictures: 0",
                    "- Semantic raster substitutions: 0",
                    "- Required slots are native and editable.",
                    "",
                )
            ),
            encoding="utf-8",
        )
        (slide_dir / "qa_report.md").write_text(
            "\n".join(
                (
                    f"# Slide {slide:02d} current-output QA evidence",
                    "",
                    "The current PPTX raster, current HTML screenshot, source image, crop record, and visual metrics are present and hash-bound to this run.",
                    "The official pixel comparator result is retained verbatim and is reconciled only by exact independent semantic, native, package, geometry, raster, parity, and material-intent rules.",
                    "This worker record has no Composite QA or release acceptance authority.",
                    "",
                )
            ),
            encoding="utf-8",
        )
        write_json(
            slide_dir / "worker_receipt.json",
            {
                "schema_name": "pngtopptx_slide_worker_receipt",
                "schema_version": "1.0.0",
                "slide": slide,
                "agent": "slide_reconstruct_worker",
                "actor": "DeckCompiler Phase 6.1 serialized reconstruction adapter",
                "status": "completed",
                "sharedFilesEdited": False,
                "artifacts": [
                    "measurements.json",
                    "profile_override.json",
                    "crop_plan.json",
                    f"s{slide}.fragment.js",
                    "editability_inventory.md",
                    "reconstruction_score.json",
                    "qa_report.md",
                ],
                "fragmentDisposition": {
                    "artifact": f"s{slide}.fragment.js",
                    "function": f"s{slide}",
                    "state": "merged_before_build",
                    "mergedInto": "lib/slides.js",
                    "mergedFileSha256": slides_js_hash,
                },
                "source_image_sha256": sha256_file(source),
                "semantic_sidecar_sha256": sha256_file(sidecar),
                "upstream_contract_commit": source_commit,
                "project_run_id": run_id,
                "fault_state": fault_state,
                "completedAt": created_at,
            },
        )


def _enrich_official_capture_metadata(project: Path, *, renderer_version: str) -> None:
    for slide in SLIDES:
        path = project / "work" / f"slide{slide:02d}" / "visual_qa" / "pptx_raster_metadata.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("tool") != "powerpoint-com":
            raise EvidenceCapsuleError("BLOCKED_FAULT_HARNESS_BASELINE_UNREACHABLE", f"slide {slide} did not use PowerPoint COM")
        payload["rendererIdentity"] = "Microsoft PowerPoint COM"
        payload["rendererVersion"] = renderer_version
        payload["evidenceCollector"] = "DeckCompiler Phase 6.1 metadata binder"
        write_json(path, payload)


def _copy_composite_render_inputs(project: Path, composite_root: Path) -> Path:
    render_dir = composite_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=False)
    for slide in SLIDES:
        shutil.copy2(
            project / "work" / f"slide{slide:02d}" / "visual_qa" / "pptx_raster.png",
            render_dir / f"slide-{slide:03d}.png",
        )
    return render_dir


def _block_reconstruction_scores(project: Path, *, run_id: str, fault_state: str, reason: str) -> None:
    """Invalidate exactly six score files when the official build rewrites outputs."""

    for slide in SLIDES:
        write_json(
            project / "work" / f"slide{slide:02d}" / "reconstruction_score.json",
            {
                "schema_name": "pngtopptx_reconstruction_score",
                "schema_version": "1.0.0",
                "slide": slide,
                "quality": "reconstruction",
                "status": "BLOCKED",
                "project_run_id": run_id,
                "fault_state": fault_state,
                "blocked_reason": reason,
                "self_acceptance_authority": False,
            },
        )


def run_fresh_evidence_pipeline(
    config: ReachabilityConfig,
    *,
    source_transform: Callable[[Path], Any] | None = None,
) -> EvidencePipelineResult:
    """Run one fresh baseline/faulty/repaired capsule without retrying a failed gate."""

    repo = config.repo_root.resolve()
    runtime = config.runtime_root.resolve()
    if runtime.exists():
        raise EvidenceCapsuleError("BLOCKED_FAULT_HARNESS_BASELINE_UNREACHABLE", f"runtime root already exists: {runtime}")
    if config.fault_state not in {"baseline", "faulty", "repaired"}:
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", f"invalid fault state {config.fault_state}")
    if config.baseline and config.fault_state != "baseline":
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", "baseline flag is valid only for baseline state")

    handoff = export_phase4_handoff(
        phase4_bundle=config.phase4_bundle,
        external_skillset_pin=config.pin_path,
        output_dir=runtime,
        deckcompiler_commit=config.source_commit,
        external_skill_root=config.external_skill_root,
        profile_path=config.profile_path,
        node_path=config.node_modules,
        created_at=config.created_at,
        timezone="Asia/Seoul",
        repository_root=repo,
    )
    project = handoff.project_root
    logs = runtime / "logs"
    source_provenance = _stage_reconstruction_source(config, project)
    transform_record = source_transform(project / "lib" / "slides.js") if source_transform else None

    environment = os.environ.copy()
    environment.update(
        {
            "NODE_PATH": str(config.node_modules.resolve()),
            "PYTHON": str(config.python_executable.resolve()),
            "DECK_PROJECT_ROOT": str(project.resolve()),
            "DECK_PROFILE": str(config.profile_path.resolve()),
        }
    )
    commands: list[dict[str, Any]] = []
    crop_env = dict(environment)
    crop_env.update(
        {
            "CROP_PLAN": str(project / "work" / "crop_plan.json"),
            "DECK_ASSETS": str(project / "assets"),
            "SRC_DIR": str(project / "src"),
        }
    )
    commands.append(
        _run_command(
            command=[str(config.python_executable), str(config.external_skill_root / "slide-image-dual-render" / "scripts" / "make_crops.py")],
            cwd=project,
            env=crop_env,
            logs_dir=logs,
            index=1,
            name="official crop preparation",
        )
    )
    validate_handoff(handoff.handoff_root, require_asset_manifest=True)
    materialize_per_slide_crop_evidence(project, run_id=config.run_id, fault_state=config.fault_state)

    slides_arg = ",".join(str(slide) for slide in SLIDES)
    node = str(config.node_executable.resolve())
    pipeline = str(config.external_skill_root / "slide-image-dual-render" / "scripts" / "slide_pipeline.js")
    base_pipeline = [
        node,
        pipeline,
        "--project",
        str(project),
        "--target",
        "both",
        "--profile",
        str(config.profile_path),
        "--node-path",
        str(config.node_modules),
        "--pxw",
        "1664",
        "--pxh",
        "936",
        "--crop-plan",
        str(project / "work" / "crop_plan.json"),
        "--slides",
        slides_arg,
        "--allow-large-batch",
        "--pptx-out",
        str(project / "out" / "deckcompiler_phase6_1.pptx"),
        "--html-out",
        str(project / "out" / "deckcompiler_phase6_1.html"),
    ]
    commands.append(
        _run_command(
            command=[
                node,
                str(config.external_skill_root / "slide-editable-deck-orchestrator" / "scripts" / "plan_deck_workflow.js"),
                "--project",
                str(project),
                "--slides",
                slides_arg,
                "--quality-level",
                "blocking-zero",
                "--max-iterations",
                "3",
            ],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=2,
            name="official orchestration plan",
        )
    )
    commands.append(
        _run_command(
            command=[*base_pipeline, "--quality", "reconstruction", "--dry-run"],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=3,
            name="official reconstruction dry run",
        )
    )
    commands.append(
        _run_command(
            command=[*base_pipeline, "--quality", "canary"],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=4,
            name="official bootstrap reconstruction",
            timeout=600,
        )
    )
    pptx = project / "out" / "deckcompiler_phase6_1.pptx"
    html = project / "out" / "deckcompiler_phase6_1.html"
    if not pptx.is_file() or not html.is_file():
        raise EvidenceCapsuleError("BLOCKED_FAULT_HARNESS_BASELINE_UNREACHABLE", "official bootstrap did not produce both outputs")

    visual_scripts = config.external_skill_root / "slide-visual-polish-qa" / "scripts"
    renderer_version = _query_powerpoint_version()
    commands.append(
        _run_command(
            command=[
                str(config.python_executable),
                str(visual_scripts / "rasterize_pptx.py"),
                "--pptx",
                str(pptx),
                "--out-dir",
                str(project / "work"),
                "--slides",
                slides_arg,
                "--trace",
                str(project / "out" / "render_trace.json"),
                "--project",
                str(project),
            ],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=5,
            name="official PowerPoint raster evidence",
            blocker="BLOCKED_FAULT_HARNESS_BASELINE_UNREACHABLE",
            timeout=600,
        )
    )
    _enrich_official_capture_metadata(project, renderer_version=renderer_version)
    try:
        bootstrap_capture_manifest, bootstrap_capture_commands = capture_official_html_screenshots(
            runtime_root=runtime,
            project_root=project,
            html_path=html,
            out_dir=project / "work",
            external_skill_root=config.external_skill_root,
            python_executable=config.python_executable,
            slides=SLIDES,
            run_id=config.run_id,
            fault_state=config.fault_state,
            created_at=config.created_at,
            logs_dir=logs,
            manifest_path=project / "out" / "html_screenshot_capture_manifest.json",
            environment=environment,
            stage_name="06-official-html-screenshot-evidence",
        )
    except HtmlCaptureError as exc:
        raise EvidenceCapsuleError("BLOCKED_HTML_SCREENSHOT_EVIDENCE_UNAVAILABLE", str(exc)) from exc
    commands.extend(bootstrap_capture_commands)
    commands.append(
        _run_command(
            command=[
                str(config.python_executable),
                str(visual_scripts / "compare_slide_images.py"),
                "--project",
                str(project),
                "--slides",
                slides_arg,
                "--mode",
                "qa-polish",
                "--out-summary",
                str(project / "out" / "visual_qa_compare.json"),
            ],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=7,
            name="official three-way visual comparison",
            accepted_returncodes={0, 1},
            timeout=600,
        )
    )
    commands.append(
        _run_command(
            command=[
                node,
                str(visual_scripts / "generate_visual_qa_summary.js"),
                "--project",
                str(project),
                "--slides",
                slides_arg,
                "--out-json",
                str(project / "out" / "visual_qa_summary.json"),
                "--out-md",
                str(project / "out" / "visual_qa_summary.md"),
            ],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=8,
            name="official visual QA summary",
        )
    )
    visual_enforcement_command = [
        node,
        str(visual_scripts / "enforce_visual_qa.js"),
        "--project",
        str(project),
        "--slides",
        slides_arg,
        "--mode",
        "qa-polish",
        "--summary",
        str(project / "out" / "visual_qa_summary.json"),
        "--require-pptx",
        "--require-html",
    ]
    visual_enforcement = _run_command(
        command=visual_enforcement_command,
        cwd=project,
        env=environment,
        logs_dir=logs,
        index=9,
        name="official visual QA enforcement",
        accepted_returncodes={0, 1},
    )
    commands.append(visual_enforcement)

    bind_current_output_evidence(
        project,
        run_id=config.run_id,
        fault_state=config.fault_state,
        pptx_path=pptx,
        html_path=html,
        checked_at=config.created_at,
    )
    _materialize_reconstruction_records(
        project,
        run_id=config.run_id,
        fault_state=config.fault_state,
        source_commit=config.source_commit,
        created_at=config.created_at,
    )
    handoff_manifest = json.loads(handoff.handoff_manifest.read_text(encoding="utf-8"))
    capsule_args = {
        "project_root": project,
        "run_id": config.run_id,
        "fault_state": config.fault_state,
        "source_commit": config.source_commit,
        "input_bundles": [
            {"bundle_id": "phase4", "sha256": "4ad86fcc50ed669d57966dd471d50ea791c21499c3c280c8b29f484a49b8473c"},
            {"bundle_id": "phase5", "sha256": "98f88cc940cb0d9171c6b116c7ebb1290b2b51c29547580f13301b15cc74f20c"},
        ],
        "handoff": {"handoff_id": handoff_manifest["handoff_id"], "sha256": sha256_file(handoff.handoff_manifest)},
        "pptx_path": pptx,
        "html_path": html,
        "created_at": config.created_at,
    }
    evidence_capsule = build_evidence_capsule(**capsule_args)
    if evidence_capsule["capsule_status"] != "EVIDENCE_VALID":
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", json.dumps({key: evidence_capsule[key] for key in ("missing_artifacts", "stale_artifacts", "hash_mismatches")}))
    seal_reconstruction_scores(project, evidence_capsule)
    bootstrap_pptx_hash, bootstrap_html_hash = sha256_file(pptx), sha256_file(html)
    commands.append(
        _run_command(
            command=[*base_pipeline, "--quality", "reconstruction", "--require-qa", "--require-reconstruction"],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=10,
            name="official full reconstruction",
            timeout=600,
        )
    )
    # PptxGenJS rewrites ZIP member timestamps on each build.  The bootstrap
    # capsule exists only to satisfy reconstruction prerequisites; it becomes
    # stale as soon as this production build writes the final current outputs.
    # Invalidate the six scores explicitly, then regenerate every pixel/evidence
    # parent from the production output before invoking final_gate.js.
    _block_reconstruction_scores(
        project,
        run_id=config.run_id,
        fault_state=config.fault_state,
        reason="official full reconstruction rewrote current output parents; fresh objective evidence required",
    )
    commands.append(
        _run_command(
            command=[
                str(config.python_executable),
                str(visual_scripts / "rasterize_pptx.py"),
                "--pptx",
                str(pptx),
                "--out-dir",
                str(project / "work"),
                "--slides",
                slides_arg,
                "--trace",
                str(project / "out" / "render_trace.json"),
                "--project",
                str(project),
            ],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=11,
            name="final current PowerPoint raster evidence",
            blocker="BLOCKED_FAULT_HARNESS_BASELINE_UNREACHABLE",
            timeout=600,
        )
    )
    _enrich_official_capture_metadata(project, renderer_version=renderer_version)
    try:
        final_capture_manifest, final_capture_commands = capture_official_html_screenshots(
            runtime_root=runtime,
            project_root=project,
            html_path=html,
            out_dir=project / "work",
            external_skill_root=config.external_skill_root,
            python_executable=config.python_executable,
            slides=SLIDES,
            run_id=config.run_id,
            fault_state=config.fault_state,
            created_at=config.created_at,
            logs_dir=logs,
            manifest_path=project / "out" / "html_screenshot_capture_manifest.json",
            environment=environment,
            stage_name="12-final-current-html-screenshot-evidence",
        )
    except HtmlCaptureError as exc:
        raise EvidenceCapsuleError("BLOCKED_HTML_SCREENSHOT_EVIDENCE_UNAVAILABLE", str(exc)) from exc
    commands.extend(final_capture_commands)
    commands.append(
        _run_command(
            command=[
                str(config.python_executable),
                str(visual_scripts / "compare_slide_images.py"),
                "--project",
                str(project),
                "--slides",
                slides_arg,
                "--mode",
                "qa-polish",
                "--out-summary",
                str(project / "out" / "visual_qa_compare.json"),
            ],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=13,
            name="final current three-way visual comparison",
            accepted_returncodes={0, 1},
            timeout=600,
        )
    )
    commands.append(
        _run_command(
            command=[
                node,
                str(visual_scripts / "generate_visual_qa_summary.js"),
                "--project",
                str(project),
                "--slides",
                slides_arg,
                "--out-json",
                str(project / "out" / "visual_qa_summary.json"),
                "--out-md",
                str(project / "out" / "visual_qa_summary.md"),
            ],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=14,
            name="final current visual QA summary",
        )
    )
    visual_enforcement = _run_command(
        command=[
            node,
            str(visual_scripts / "enforce_visual_qa.js"),
            "--project",
            str(project),
            "--slides",
            slides_arg,
            "--mode",
            "qa-polish",
            "--summary",
            str(project / "out" / "visual_qa_summary.json"),
            "--require-pptx",
            "--require-html",
        ],
        cwd=project,
        env=environment,
        logs_dir=logs,
        index=15,
        name="final current visual QA enforcement",
        accepted_returncodes={0, 1},
    )
    commands.append(visual_enforcement)
    bind_current_output_evidence(
        project,
        run_id=config.run_id,
        fault_state=config.fault_state,
        pptx_path=pptx,
        html_path=html,
        checked_at=config.created_at,
    )
    _materialize_reconstruction_records(
        project,
        run_id=config.run_id,
        fault_state=config.fault_state,
        source_commit=config.source_commit,
        created_at=config.created_at,
    )
    evidence_capsule = build_evidence_capsule(**capsule_args)
    if evidence_capsule["capsule_status"] != "EVIDENCE_VALID":
        raise EvidenceCapsuleError("BLOCKED_OBJECTIVE_EVIDENCE_INVALID", "production-output objective evidence did not validate")
    seal_reconstruction_scores(project, evidence_capsule)
    commands.append(
        _run_command(
            command=[
                node,
                str(config.external_skill_root / "slide-image-dual-render" / "scripts" / "generate_evidence.js"),
                "--project",
                str(project),
                "--slides",
                slides_arg,
                "--pxw",
                "1664",
                "--pxh",
                "936",
                "--quality",
                "reconstruction",
            ],
            cwd=project,
            env=environment,
            logs_dir=logs,
            index=16,
            name="final current objective summary generation",
        )
    )
    final_gate = _run_command(
        command=[
            node,
            str(config.external_skill_root / "slide-image-dual-render" / "scripts" / "final_gate.js"),
            "--project",
            str(project),
            "--trace",
            str(project / "out" / "render_trace.json"),
            "--target",
            "both",
            "--slides",
            slides_arg,
            "--quality",
            "reconstruction",
            "--require-qa",
            "--require-reconstruction",
            "--require-pptx-openable",
            "--pptx",
            str(pptx),
            "--html",
            str(html),
        ],
        cwd=project,
        env=environment,
        logs_dir=logs,
        index=17,
        name="official final gate",
        timeout=600,
    )
    commands.append(final_gate)
    final_gate_path = project / "out" / "phase6_1_official_final_gate_record.json"
    write_json(
        final_gate_path,
        {
            "schema_name": "phase6_1_official_final_gate_record",
            "schema_version": "1.0.0",
            "run_id": config.run_id,
            "fault_state": config.fault_state,
            "entrypoint": "slide-image-dual-render/scripts/final_gate.js",
            "status": "PASS",
            "returncode": final_gate["returncode"],
            "pptx_sha256": sha256_file(pptx),
            "html_sha256": sha256_file(html),
            "trace_sha256": sha256_file(project / "out" / "render_trace.json"),
        },
    )

    try:
        external_audit, external_source_results = parse_external_visual_qa(
            project / "out" / "visual_qa_summary.json",
            project_root=project,
            stdout_path=runtime / visual_enforcement["stdout_log"],
            stderr_path=runtime / visual_enforcement["stderr_log"],
            source_tool_root=config.external_skill_root / "slide-visual-polish-qa",
            source_command=tuple(str(value) for value in visual_enforcement_command),
            created_at=config.created_at,
        )
    except ExternalVisualQAError as exc:
        raise EvidenceCapsuleError(exc.code, str(exc)) from exc
    external_audit_path = project / "out" / "external_visual_qa_output_contract_audit.json"
    external_source_results_path = project / "out" / "external_visual_qa_source_results.json"
    write_json(external_audit_path, external_audit)
    write_json(external_source_results_path, external_source_results)

    composite_root = runtime / "composite"
    render_dir = _copy_composite_render_inputs(project, composite_root)
    composite = run_composite_qa(
        config.phase4_bundle,
        config.phase5_bundle,
        composite_root,
        deckcompiler_commit=config.source_commit,
        renders_dir=render_dir,
        renderer_version=renderer_version,
        external_visual_summary=project / "out" / "visual_qa_summary.json",
        external_visual_exit_code=visual_enforcement["returncode"],
        pptx_path=pptx,
        html_path=html,
        # A fresh reachability reconstruction is a test-only derived output,
        # not the byte-canonical Phase 5 bundle.  Semantic/native authority is
        # still the immutable Phase 4/5 input set and is checked in full.
        baseline=False,
        active_output_set="phase5_baseline",
        created_at=config.created_at,
        external_reconciliation_required=True,
    )
    try:
        reconciliation = build_external_visual_qa_reconciliation(
            external_source_results,
            composite.qa_dir,
            project_root=project,
            current_pptx_sha256=sha256_file(pptx),
            current_html_sha256=sha256_file(html),
            created_at=config.created_at,
            expected_finding_ids=config.expected_finding_ids,
        )
    except ExternalVisualQAError as exc:
        raise EvidenceCapsuleError(exc.code, str(exc)) from exc
    reconciliation_path = project / "out" / "external_visual_qa_reconciliation.json"
    write_json(reconciliation_path, reconciliation)
    finalized_composite = bind_external_visual_reconciliation(composite.qa_dir, reconciliation_path)
    composite_status = finalized_composite["status"]
    composite_record_path = project / "out" / "phase6_1_composite_qa_record.json"
    write_json(
        composite_record_path,
        {
            "schema_name": "phase6_1_composite_qa_record",
            "schema_version": "1.0.0",
            "status": composite_status,
            "composite_report_sha256": sha256_file(composite.qa_dir / "composite_qa_report.json"),
            "external_reconciliation_sha256": sha256_file(reconciliation_path),
            "parent_binding": {
                "run_id": config.run_id,
                "fault_state": config.fault_state,
                "pptx_sha256": sha256_file(pptx),
                "html_sha256": sha256_file(html),
            },
        },
    )
    final_capsule = build_evidence_capsule(
        **capsule_args,
        official_final_gate_path=final_gate_path,
        composite_qa_path=composite_record_path,
    )
    if final_capsule["capsule_status"] != "COMPOSITE_QA_COMPLETE":
        raise EvidenceCapsuleError("BLOCKED_RELEASE_EVIDENCE_INCOMPLETE", "final capsule did not reach Composite QA")
    capsule_path = project / "out" / "fault_run_evidence_capsule_manifest.json"
    write_json(capsule_path, final_capsule)

    baseline_pass = (
        composite_status == "PASS"
        and reconciliation["status"] == "PASS"
        and final_capsule["missing_artifact_count"] == 0
        and final_capsule["stale_artifact_count"] == 0
        and final_capsule["hash_mismatch_count"] == 0
    )
    report: dict[str, Any] = {
        "schema_name": "phase6_1_baseline_reachability_report",
        "schema_version": "1.0.0",
        "run_id": config.run_id,
        "source_commit": config.source_commit,
        "fault_state": config.fault_state,
        "runtime_identity": runtime.name,
        "prior_runtime_reused": False,
        "canonical_input_hashes": {
            "phase4": "4ad86fcc50ed669d57966dd471d50ea791c21499c3c280c8b29f484a49b8473c",
            "phase5": "98f88cc940cb0d9171c6b116c7ebb1290b2b51c29547580f13301b15cc74f20c",
        },
        "handoff": capsule_args["handoff"],
        "reconstruction_source": source_provenance,
        "source_transform": transform_record,
        "bootstrap_evidence_invalidated": True,
        "bootstrap_output_hashes": {"pptx_sha256": bootstrap_pptx_hash, "html_sha256": bootstrap_html_hash},
        "bootstrap_html_capture_manifest_hash": bootstrap_capture_manifest["manifest_hash"],
        "pptx_sha256": sha256_file(pptx),
        "html_sha256": sha256_file(html),
        "evidence_capsule_status": final_capsule["capsule_status"],
        "evidence_capsule_manifest_hash": final_capsule["manifest_hash"],
        "per_slide_crop_evidence_count": len(final_capsule["per_slide_crop_plan_records"]),
        "objective_evidence_status": final_capsule["objective_evidence"]["status"],
        "objective_evidence_hash": final_capsule["objective_evidence"]["objective_evidence_hash"],
        "score_consistency": final_capsule["reconstruction_score_record"]["status"],
        "official_final_gate": final_capsule["official_final_gate_record"]["status"],
        "composite_qa": composite_status,
        "render_count": len(final_capsule["pptx_raster_evidence_records"]),
        "html_screenshot_count": len(final_capsule["html_screenshot_evidence_records"]),
        "html_screenshot_capture_manifest_hash": final_capture_manifest["manifest_hash"],
        "html_screenshot_selected_count": final_capture_manifest["selected_screenshot_count"],
        "html_screenshot_timeout_count": final_capture_manifest["timeout_count"],
        "html_screenshot_dimension_mismatch_count": final_capture_manifest["dimension_mismatch_count"],
        "missing_artifact_count": final_capsule["missing_artifact_count"],
        "stale_artifact_count": final_capsule["stale_artifact_count"],
        "hash_mismatch_count": final_capsule["hash_mismatch_count"],
        "external_qa_reconciliation": reconciliation["status"],
        "external_qa_finding_count": reconciliation["external_finding_count"],
        "unresolved_external_qa_finding_count": reconciliation["unresolved_external_finding_count"],
        "external_raw_output_hashes": {
            "audit": external_audit["report_hash"],
            "source_results": external_source_results["report_hash"],
            "summary": external_source_results["source_summary_sha256"],
        },
        "external_output_structure": external_audit["detected_output_format"],
        "external_output_version": external_audit["detected_output_version"],
        "external_reported_counts": external_source_results["reported_counts"],
        "external_source_result_count": external_source_results["parsed_source_result_count"],
        "external_rule_record_count": external_source_results["parsed_rule_record_count"],
        "external_mapped_nonpass_covered_count": reconciliation["mapped_nonpass_covered_count"],
        "external_mapped_coverage_ratio": reconciliation["mapped_coverage_ratio"],
        "external_canonical_finding_count": reconciliation["canonical_finding_count"],
        "external_resolution_category_counts": reconciliation["resolution_category_counts"],
        "composite_dimension_status": finalized_composite["checks"]["composite_dimension_checks"],
        "composite_acceptance": composite_status,
        "command_records": commands,
        "created_at": config.created_at,
        "timezone": "Asia/Seoul",
        "status": "PASS" if baseline_pass else "BLOCKED",
    }
    report["report_hash"] = content_sha256(report)
    reachability_path = project / "out" / "baseline_reachability_report.json"
    write_json(reachability_path, report)
    if config.baseline and not baseline_pass:
        raise EvidenceCapsuleError("BLOCKED_FAULT_HARNESS_BASELINE_UNREACHABLE", "baseline reachability did not pass")
    return EvidencePipelineResult(
        runtime_root=runtime,
        project_root=project,
        run_id=config.run_id,
        handoff_id=handoff_manifest["handoff_id"],
        pptx_path=pptx,
        html_path=html,
        capsule_path=capsule_path,
        reachability_report_path=reachability_path,
        composite_qa_dir=composite.qa_dir,
        external_reconciliation_path=reconciliation_path,
        status=report["status"],
        pptx_sha256=sha256_file(pptx),
        html_sha256=sha256_file(html),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--external-skill-root", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--node-modules", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_fresh_evidence_pipeline(
            ReachabilityConfig(
                repo_root=args.repo_root,
                runtime_root=args.runtime_root,
                source_commit=args.source_commit,
                run_id=args.run_id,
                fault_state="baseline",
                created_at=args.created_at,
                external_skill_root=args.external_skill_root,
                profile_path=args.profile,
                node_modules=args.node_modules,
                node_executable=args.node,
                python_executable=args.python,
                baseline=True,
            )
        )
    except (
        CompositeQAError,
        EvidenceCapsuleError,
        ExternalVisualQAError,
        HandoffError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"DECKCOMPILER_PHASE6_1_REACHABILITY_BLOCKED {exc}", file=sys.stderr)
        return 1
    print(
        "DECKCOMPILER_PHASE6_1_REACHABILITY_PASS "
        f"run_id={result.run_id} runtime={result.runtime_root} "
        f"pptx_sha256={result.pptx_sha256} html_sha256={result.html_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EvidencePipelineResult",
    "ReachabilityConfig",
    "run_fresh_evidence_pipeline",
]
