"""Deterministic Architect-to-ImageGen request preparation and validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..errors import DeckCompilerError
from ..identity import content_sha256, stable_id
from ..manifest_io import read_json, write_json


WORKFLOW_MANIFEST_NAME = "generate_workflow_manifest.json"
REQUEST_MANIFEST_NAME = "image_request_manifest.json"
REQUEST_MANIFEST_SCHEMA = "codex_image_request_manifest"
REQUEST_SCHEMA = "codex_image_request"
SIDECAR_SCHEMA = "codex_semantic_sidecar"
REQUEST_MANIFEST_VERSION = "1.1.0"
REQUEST_VERSION = "1.1.0"
SIDECAR_VERSION = "1.1.0"
DEFAULT_DESIGN_DIRECTION = (
    "Academic",
    "Informative",
    "Professional",
    "Creative",
)
REFERENCE_MODE = "content_complete_slide_reference"
DESIGN_CONTEXT_MODE = (
    "compact_architect_context_plus_selected_route_and_layout"
)


@dataclass(frozen=True, slots=True)
class ImageRequestPreparationResult:
    workflow_id: str
    runtime_root: Path
    request_manifest_path: Path
    prompt_paths: tuple[Path, ...]
    sidecar_paths: tuple[Path, ...]
    slide_count: int


def prepare_image_requests(runtime_root: Path) -> ImageRequestPreparationResult:
    """Build every per-slide prompt and sidecar once from approved Architect JSON."""

    root = runtime_root.resolve()
    workflow, workflow_design, blueprint, design_system, approval = _load_inputs(root)
    workflow_id = _required_text(workflow.get("workflow_id"), "workflow_id")
    prepared = _build_payloads(
        runtime_root=root,
        workflow_id=workflow_id,
        presentation=_presentation(workflow),
        workflow_design=workflow_design,
        blueprint=blueprint,
        design_system=design_system,
        approval=approval,
        source_hashes=_source_hashes(root),
    )

    prompt_dir = root / "image_requests"
    sidecar_dir = root / "semantic_sidecars"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    sidecar_dir.mkdir(parents=True, exist_ok=True)

    expected_prompt_names: set[str] = set()
    expected_sidecar_names: set[str] = set()
    manifest_rows: list[dict[str, Any]] = []
    prompt_paths: list[Path] = []
    sidecar_paths: list[Path] = []
    for row in prepared:
        slide_number = row["slide_number"]
        prompt_path = prompt_dir / f"slide-{slide_number:03d}.prompt.json"
        sidecar_path = sidecar_dir / f"slide-{slide_number:03d}.semantic.json"
        write_json(prompt_path, row["prompt"])
        write_json(sidecar_path, row["sidecar"])
        expected_prompt_names.add(prompt_path.name)
        expected_sidecar_names.add(sidecar_path.name)
        prompt_paths.append(prompt_path)
        sidecar_paths.append(sidecar_path)
        manifest_rows.append(
            {
                **row["lineage"],
                "prompt": _artifact(root, prompt_path),
                "semantic_sidecar": _artifact(root, sidecar_path),
            }
        )

    _remove_stale_json(prompt_dir, "slide-*.prompt.json", expected_prompt_names)
    _remove_stale_json(sidecar_dir, "slide-*.semantic.json", expected_sidecar_names)

    manifest = {
        "schema_name": REQUEST_MANIFEST_SCHEMA,
        "schema_version": REQUEST_MANIFEST_VERSION,
        "workflow_id": workflow_id,
        "profile_name": "fast-quality-20",
        "generation_strategy": "single_deterministic_preparation_pass",
        "additional_model_calls": 0,
        "design_context_mode": DESIGN_CONTEXT_MODE,
        "reference_mode": REFERENCE_MODE,
        "source_artifacts": {
            name: _artifact(root, root / "architect" / filename)
            for name, filename in _architect_filenames().items()
        },
        "slide_count": len(manifest_rows),
        "prompt_character_count_total": sum(
            len(row["prompt"]["prompt_text"]) for row in prepared
        ),
        "default_design_direction": list(DEFAULT_DESIGN_DIRECTION),
        "slides": manifest_rows,
    }
    manifest["content_hash"] = content_sha256(manifest)
    manifest_path = write_json(prompt_dir / REQUEST_MANIFEST_NAME, manifest)

    report = validate_image_request_bundle(root, manifest_path)
    if not report["valid"]:
        raise _error(
            "DC_IMAGE_REQUEST_PREPARATION_INVALID",
            "; ".join(report["issues"][:8]),
            manifest_path,
        )
    return ImageRequestPreparationResult(
        workflow_id=workflow_id,
        runtime_root=root,
        request_manifest_path=manifest_path,
        prompt_paths=tuple(prompt_paths),
        sidecar_paths=tuple(sidecar_paths),
        slide_count=len(manifest_rows),
    )


def validate_image_request_bundle(
    runtime_root: Path,
    request_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Rebuild the expected request payloads and reject any semantic drift."""

    root = runtime_root.resolve()
    manifest_path = (
        request_manifest_path.resolve()
        if request_manifest_path is not None
        else root / "image_requests" / REQUEST_MANIFEST_NAME
    )
    issues: list[str] = []
    try:
        workflow, workflow_design, blueprint, design_system, approval = _load_inputs(root)
        manifest = read_json(manifest_path)
        workflow_id = _required_text(workflow.get("workflow_id"), "workflow_id")
        source_hashes = _source_hashes(root)
        expected = _build_payloads(
            runtime_root=root,
            workflow_id=workflow_id,
            presentation=_presentation(workflow),
            workflow_design=workflow_design,
            blueprint=blueprint,
            design_system=design_system,
            approval=approval,
            source_hashes=source_hashes,
        )
    except (DeckCompilerError, OSError, ValueError, TypeError) as exc:
        message = exc.message if isinstance(exc, DeckCompilerError) else str(exc)
        return {
            "valid": False,
            "workflow_id": None,
            "slide_count": 0,
            "issues": [message],
        }

    expected_header = {
        "schema_name": REQUEST_MANIFEST_SCHEMA,
        "schema_version": REQUEST_MANIFEST_VERSION,
        "workflow_id": workflow_id,
        "profile_name": "fast-quality-20",
        "generation_strategy": "single_deterministic_preparation_pass",
        "additional_model_calls": 0,
        "design_context_mode": DESIGN_CONTEXT_MODE,
        "reference_mode": REFERENCE_MODE,
        "slide_count": len(expected),
        "prompt_character_count_total": sum(
            len(row["prompt"]["prompt_text"]) for row in expected
        ),
        "default_design_direction": list(DEFAULT_DESIGN_DIRECTION),
    }
    for key, value in expected_header.items():
        if manifest.get(key) != value:
            issues.append(f"image request manifest {key} must be {value!r}")

    expected_sources = {
        name: _artifact(root, root / "architect" / filename)
        for name, filename in _architect_filenames().items()
    }
    if manifest.get("source_artifacts") != expected_sources:
        issues.append("image request manifest source_artifacts do not match Architect files")

    rows = manifest.get("slides")
    if not isinstance(rows, list) or len(rows) != len(expected):
        issues.append(
            f"image request manifest slides must contain exactly {len(expected)} rows"
        )
        rows = []

    for index, expected_row in enumerate(expected):
        if index >= len(rows):
            break
        actual_row = rows[index]
        label = f"image request manifest slides[{index}]"
        if not isinstance(actual_row, dict):
            issues.append(f"{label} must be an object")
            continue
        for key, value in expected_row["lineage"].items():
            if actual_row.get(key) != value:
                issues.append(f"{label}.{key} does not match approved Architect content")

        for artifact_key, expected_payload in (
            ("prompt", expected_row["prompt"]),
            ("semantic_sidecar", expected_row["sidecar"]),
        ):
            artifact = actual_row.get(artifact_key)
            if not isinstance(artifact, dict):
                issues.append(f"{label}.{artifact_key} must be an artifact reference")
                continue
            path = _resolve_inside(root, artifact.get("path"), f"{label}.{artifact_key}")
            if path is None:
                issues.append(f"{label}.{artifact_key} path is invalid")
                continue
            if not path.is_file():
                issues.append(f"{label}.{artifact_key} is missing: {path}")
                continue
            actual_sha = _sha256_file(path)
            if artifact.get("sha256") != actual_sha:
                issues.append(f"{label}.{artifact_key} sha256 mismatch")
            try:
                actual_payload = read_json(path)
            except (OSError, ValueError) as exc:
                issues.append(f"{label}.{artifact_key} is invalid JSON: {exc}")
                continue
            if actual_payload != expected_payload:
                issues.append(
                    f"{label}.{artifact_key} was not deterministically derived from "
                    "the approved Blueprint and Design System"
                )

    expected_content_hash = content_sha256(
        {key: value for key, value in manifest.items() if key != "content_hash"}
    )
    if manifest.get("content_hash") != expected_content_hash:
        issues.append("image request manifest content_hash mismatch")

    return {
        "valid": not issues,
        "workflow_id": workflow_id,
        "slide_count": len(expected),
        "issues": issues,
    }


def _build_payloads(
    *,
    runtime_root: Path,
    workflow_id: str,
    presentation: dict[str, Any],
    workflow_design: dict[str, Any],
    blueprint: dict[str, Any],
    design_system: dict[str, Any],
    approval: dict[str, Any],
    source_hashes: dict[str, str],
) -> list[dict[str, Any]]:
    _validate_approval(approval)
    slides = blueprint.get("slides")
    if not isinstance(slides, list) or not slides or len(slides) > 400:
        raise _error(
            "DC_ARCHITECT_BLUEPRINT_INVALID",
            "blueprint.slides must contain 1..400 slide objects",
        )
    route_id = _required_text(
        blueprint.get("approved_visual_route_id"),
        "blueprint.approved_visual_route_id",
    )
    route = _select_named(design_system.get("visual_routes"), "route_id", route_id)
    route_cues = _string_list(route.get("prompt_cues"), "visual route prompt_cues")
    global_cues = _string_list(
        design_system.get("global_prompt_cues"),
        "design_system.global_prompt_cues",
    )

    layout_rows = design_system.get("layouts")
    if not isinstance(layout_rows, list) or not layout_rows:
        raise _error(
            "DC_ARCHITECT_DESIGN_SYSTEM_INVALID",
            "design_system.layouts must contain at least one layout",
        )

    output: list[dict[str, Any]] = []
    expected_numbers = list(range(1, len(slides) + 1))
    actual_numbers = [row.get("slide_number") if isinstance(row, dict) else None for row in slides]
    if actual_numbers != expected_numbers:
        raise _error(
            "DC_ARCHITECT_BLUEPRINT_INVALID",
            f"blueprint slide_number values must be contiguous {expected_numbers}",
        )
    seen_ids: set[str] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            raise _error("DC_ARCHITECT_BLUEPRINT_INVALID", "each blueprint slide must be an object")
        slide_number = int(slide["slide_number"])
        slide_id = _required_text(slide.get("slide_id"), f"slide {slide_number} slide_id")
        if slide_id in seen_ids:
            raise _error("DC_ARCHITECT_BLUEPRINT_INVALID", f"duplicate slide_id: {slide_id}")
        seen_ids.add(slide_id)
        _required_text(slide.get("purpose"), f"slide {slide_number} purpose")
        title = _required_text(slide.get("title"), f"slide {slide_number} title")
        copy = slide.get("on_slide_copy")
        copy_text = _flatten_copy(copy)
        if not copy_text:
            raise _error(
                "DC_ARCHITECT_BLUEPRINT_INVALID",
                f"slide {slide_number} on_slide_copy must contain exact editable content",
            )
        layout_id = _required_text(slide.get("layout_id"), f"slide {slide_number} layout_id")
        layout = _select_named(layout_rows, "layout_id", layout_id)
        layout_cues = _string_list(layout.get("prompt_cues"), f"layout {layout_id} prompt_cues")
        visual_direction = _required_text(
            slide.get("visual_direction"), f"slide {slide_number} visual_direction"
        )
        evidence_refs = _string_list(
            slide.get("evidence_refs", []), f"slide {slide_number} evidence_refs", allow_empty=True
        )
        presenter_notes = _required_text(
            slide.get("presenter_notes"), f"slide {slide_number} presenter_notes"
        )
        workflow_context = _compact_workflow_context(
            workflow_design,
            slide_number=slide_number,
            slide_id=slide_id,
        )
        reference_assets, referenced_image_paths = _reference_inputs(
            runtime_root,
            slide,
        )
        blueprint_entry_sha = content_sha256(slide)
        route_sha = content_sha256(route)
        layout_sha = content_sha256(layout)
        request_id = stable_id(
            "imagerequest",
            workflow_id,
            slide_id,
            blueprint_entry_sha,
            source_hashes["design_system"],
        )
        lineage = {
            "slide_number": slide_number,
            "slide_id": slide_id,
            "request_id": request_id,
            "blueprint_entry_sha256": blueprint_entry_sha,
            "visual_route_id": route_id,
            "visual_route_sha256": route_sha,
            "layout_id": layout_id,
            "layout_sha256": layout_sha,
            "evidence_refs": evidence_refs,
        }
        prompt = {
            "schema_name": REQUEST_SCHEMA,
            "schema_version": REQUEST_VERSION,
            "workflow_id": workflow_id,
            **lineage,
            "architect_lineage": source_hashes,
            "reference_mode": REFERENCE_MODE,
            "architect_context": workflow_context,
            "reference_assets": reference_assets,
            "prompt_text": _prompt_text(
                presentation=presentation,
                blueprint=blueprint,
                slide=slide,
                structured_copy=_structured_copy_lines(copy),
                workflow_context=workflow_context,
                reference_assets=reference_assets,
                route=route,
                route_cues=route_cues,
                layout=layout,
                layout_cues=layout_cues,
                global_cues=global_cues,
            ),
            "tool_input": {
                "tool": "image_gen.imagegen",
                "prompt_field": "prompt_text",
                "referenced_image_paths": referenced_image_paths,
            },
        }
        prompt["prompt_hash"] = content_sha256(prompt)
        sidecar = {
            "schema_name": SIDECAR_SCHEMA,
            "schema_version": SIDECAR_VERSION,
            "workflow_id": workflow_id,
            **lineage,
            "architect_lineage": source_hashes,
            "reference_mode": REFERENCE_MODE,
            "architect_context": workflow_context,
            "reference_assets": reference_assets,
            "exact_title": title,
            "exact_on_slide_copy": copy,
            "presenter_notes": presenter_notes,
            "visual_direction": visual_direction,
        }
        sidecar["content_hash"] = content_sha256(sidecar)
        output.append(
            {
                "slide_number": slide_number,
                "lineage": lineage,
                "prompt": prompt,
                "sidecar": sidecar,
            }
        )
    return output


def _prompt_text(
    *,
    presentation: dict[str, Any],
    blueprint: dict[str, Any],
    slide: dict[str, Any],
    structured_copy: list[str],
    workflow_context: dict[str, Any],
    reference_assets: list[dict[str, Any]],
    route: dict[str, Any],
    route_cues: list[str],
    layout: dict[str, Any],
    layout_cues: list[str],
    global_cues: list[str],
) -> str:
    audience = _display_value(blueprint.get("audience") or presentation.get("audience"))
    deck_purpose = _display_value(presentation.get("purpose"))
    language = _display_value(presentation.get("language"))
    tone = _display_value(presentation.get("tone"))
    deck_title = _display_value(blueprint.get("deck_title"))
    evidence = _display_value(slide.get("evidence_refs")) or "None declared"
    cues = _unique([*global_cues, *route_cues, *layout_cues])
    cue_text = "; ".join(cues) if cues else "Use the approved route and layout naturally."
    route_name = _display_value(route.get("name") or route.get("route_id"))
    layout_name = _display_value(layout.get("name") or layout.get("layout_id"))
    workflow_text = _display_value(workflow_context) or "Use the approved Architect plan."
    reference_text = (
        _display_value(reference_assets)
        if reference_assets
        else "None declared"
    )
    return "\n".join(
        (
            "Create a 16:9 presentation-slide design reference.",
            f"Deck: {deck_title}",
            f"Audience: {audience}",
            f"Deck purpose: {deck_purpose}",
            f"Language: {language}",
            f"Tone: {tone}",
            f"Approved workflow context: {workflow_text}",
            f"Slide purpose: {_display_value(slide.get('purpose'))}",
            f"Exact title: {_display_value(slide.get('title'))}",
            "Exact on-slide content (preserve structure):",
            *structured_copy,
            f"Visual direction: {_display_value(slide.get('visual_direction'))}",
            f"Approved visual route: {route_name}",
            f"Approved layout: {layout_name}",
            f"Relevant design cues: {cue_text}",
            f"Evidence references: {evidence}",
            f"Reference assets: {reference_text}",
            "Design posture: Academic, Informative, Professional and Creative.",
            "Represent supplied facts faithfully and choose a natural composition, hierarchy, density and visual language for this slide. Keep it coherent with the deck; do not invent facts or add watermarks.",
        )
    )


def _compact_workflow_context(
    workflow_design: dict[str, Any],
    *,
    slide_number: int,
    slide_id: str,
) -> dict[str, Any]:
    """Keep the planning signal that affects art direction without prompt bloat."""

    preferred_keys = (
        "selected_workflow",
        "chosen_workflow",
        "workflow_option",
        "workflow_delta",
        "reason",
        "objective",
        "message_spine",
        "narrative_promise",
        "communication_core",
        "story_architecture",
        "continuity_rules",
        "approved_visual_route",
        "visual_route_rationale",
        "evidence_asset_plan",
    )
    context = {
        key: _compact_context_value(workflow_design[key])
        for key in preferred_keys
        if key in workflow_design and _has_content(workflow_design[key])
    }
    slide_contexts = workflow_design.get("slide_contexts")
    if isinstance(slide_contexts, list):
        matches = [
            row
            for row in slide_contexts
            if isinstance(row, dict)
            and (
                row.get("slide_number") == slide_number
                or row.get("slide_id") == slide_id
            )
        ]
        if len(matches) == 1:
            context["slide_context"] = _compact_context_value(matches[0])
    elif isinstance(slide_contexts, dict):
        selected = slide_contexts.get(slide_id) or slide_contexts.get(
            str(slide_number)
        )
        if _has_content(selected):
            context["slide_context"] = _compact_context_value(selected)
    return context


def _compact_context_value(value: Any, *, depth: int = 0) -> Any:
    """Project rich Gate output into a bounded prompt signal."""

    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized if len(normalized) <= 600 else normalized[:597] + "..."
    if isinstance(value, list):
        return [
            _compact_context_value(item, depth=depth + 1)
            for item in value[:6]
            if _has_content(item)
        ]
    if isinstance(value, dict):
        if depth >= 2:
            return _display_value(value)[:600]
        useful_subkeys = (
            "name",
            "summary",
            "reason",
            "rationale",
            "objective",
            "takeaway",
            "key_question",
            "message",
            "narrative_flow",
            "audience_journey",
            "role",
        )
        selected_keys = [key for key in useful_subkeys if key in value]
        if not selected_keys:
            selected_keys = list(value)[:6]
        return {
            key: _compact_context_value(value[key], depth=depth + 1)
            for key in selected_keys
            if _has_content(value[key])
        }
    return value


def _reference_inputs(
    runtime_root: Path,
    slide: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    raw = slide.get("reference_inputs", slide.get("referenced_assets", []))
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise _error(
            "DC_IMAGE_REQUEST_INPUT_INVALID",
            "slide reference_inputs/referenced_assets must be a list",
        )

    assets: list[dict[str, Any]] = []
    image_paths: list[str] = []
    for index, value in enumerate(raw):
        if isinstance(value, str):
            item: dict[str, Any] = {"path": value, "role": "visual_reference"}
        elif isinstance(value, dict):
            item = dict(value)
        else:
            raise _error(
                "DC_IMAGE_REQUEST_INPUT_INVALID",
                f"slide reference input {index} must be a string or object",
            )
        raw_path = str(item.get("path", "")).strip()
        role = str(item.get("role", "visual_reference")).strip()
        if not raw_path:
            label = str(item.get("label", "")).strip()
            if not label:
                raise _error(
                    "DC_IMAGE_REQUEST_INPUT_INVALID",
                    f"slide reference input {index} needs path or label",
                )
            assets.append({"label": label, "role": role})
            continue
        resolved = _resolve_inside(runtime_root, raw_path, "reference input")
        if resolved is None or not resolved.is_file():
            raise _error(
                "DC_IMAGE_REQUEST_INPUT_INVALID",
                f"reference input must be an existing file inside the runtime: {raw_path}",
            )
        relative = resolved.relative_to(runtime_root).as_posix()
        asset = {
            "path": relative,
            "role": role,
            "sha256": _sha256_file(resolved),
        }
        if str(item.get("usage", "")).strip():
            asset["usage"] = str(item["usage"]).strip()
        assets.append(asset)
        if resolved.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            image_paths.append(resolved.as_posix())
    return assets, image_paths


def _structured_copy_lines(value: Any, *, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, str):
        return [f"{prefix}- {' '.join(value.split())}"]
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            lines.extend(_structured_copy_lines(item, indent=indent))
        return lines
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (list, dict)):
                lines.append(f"{prefix}- {key}:")
                lines.extend(_structured_copy_lines(item, indent=indent + 1))
            else:
                rendered = " ".join(str(item).split())
                lines.append(f"{prefix}- {key}: {rendered}")
        return lines
    if value is None:
        return []
    return [f"{prefix}- {value}"]


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _load_inputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    workflow_path = root / WORKFLOW_MANIFEST_NAME
    if not workflow_path.is_file():
        raise _error("DC_GENERATE_MANIFEST_MISSING", f"workflow manifest is missing: {workflow_path}")
    workflow = read_json(workflow_path)
    architect = root / "architect"
    paths = [architect / filename for filename in _architect_filenames().values()]
    missing = [path.as_posix() for path in paths if not path.is_file()]
    if missing:
        raise _error(
            "DC_ARCHITECT_ARTIFACT_MISSING",
            f"approved Architect artifacts are missing: {missing}",
        )
    return workflow, *(read_json(path) for path in paths)


def _architect_filenames() -> dict[str, str]:
    return {
        "workflow_design": "workflow_design.json",
        "blueprint": "blueprint.json",
        "design_system": "design_system.json",
        "approval_record": "approval_record.json",
    }


def _source_hashes(root: Path) -> dict[str, str]:
    return {
        name: _sha256_file(root / "architect" / filename)
        for name, filename in _architect_filenames().items()
    }


def _presentation(workflow: dict[str, Any]) -> dict[str, Any]:
    contract = workflow.get("input_contract")
    presentation = contract.get("presentation") if isinstance(contract, dict) else None
    if not isinstance(presentation, dict):
        raise _error(
            "DC_GENERATE_MANIFEST_INVALID",
            "workflow input_contract.presentation must be an object",
        )
    return presentation


def _validate_approval(approval: dict[str, Any]) -> None:
    for gate in ("gate1", "gate2"):
        row = approval.get(gate)
        if not isinstance(row, dict) or str(row.get("status", "")).upper() != "APPROVED":
            raise _error(
                "DC_ARCHITECT_APPROVAL_REQUIRED",
                f"approval_record.{gate}.status must be APPROVED",
            )
        approved_by = str(row.get("approved_by") or row.get("approval_source") or "").strip()
        if approved_by.lower() not in {"user", "사용자"}:
            raise _error(
                "DC_ARCHITECT_APPROVAL_REQUIRED",
                f"approval_record.{gate} must record explicit user approval",
            )


def _select_named(value: Any, key: str, target: str) -> dict[str, Any]:
    if not isinstance(value, list):
        raise _error("DC_ARCHITECT_DESIGN_SYSTEM_INVALID", f"design system {key} collection must be a list")
    matches = [row for row in value if isinstance(row, dict) and row.get(key) == target]
    if len(matches) != 1:
        raise _error(
            "DC_ARCHITECT_DESIGN_SYSTEM_INVALID",
            f"design system must define exactly one {key}={target!r}",
        )
    return matches[0]


def _required_text(value: Any, label: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise _error("DC_IMAGE_REQUEST_INPUT_INVALID", f"{label} must be non-empty")
    return text


def _string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if value is None and allow_empty:
        return []
    if not isinstance(value, list):
        raise _error("DC_IMAGE_REQUEST_INPUT_INVALID", f"{label} must be a list")
    items = [str(item).strip() for item in value if str(item).strip()]
    if len(items) != len(value):
        raise _error("DC_IMAGE_REQUEST_INPUT_INVALID", f"{label} cannot contain empty values")
    if not items and not allow_empty:
        raise _error("DC_IMAGE_REQUEST_INPUT_INVALID", f"{label} must not be empty")
    if len(items) != len(set(items)):
        raise _error("DC_IMAGE_REQUEST_INPUT_INVALID", f"{label} must be unique")
    return items


def _flatten_copy(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return " | ".join(filter(None, (_flatten_copy(item) for item in value)))
    if isinstance(value, dict):
        return " | ".join(
            f"{key}: {text}"
            for key, item in value.items()
            if (text := _flatten_copy(item))
        )
    if value is None:
        return ""
    return str(value).strip()


def _display_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_display_value(item)}" for key, item in value.items())
    return str(value).strip() if value is not None else ""


def _unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _artifact(root: Path, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise _error("DC_IMAGE_REQUEST_PATH_ESCAPE", f"artifact escapes runtime root: {resolved}") from exc
    return {"path": relative.as_posix(), "sha256": _sha256_file(resolved)}


def _resolve_inside(root: Path, raw: Any, label: str) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _remove_stale_json(directory: Path, pattern: str, expected: set[str]) -> None:
    for path in directory.glob(pattern):
        if path.name not in expected:
            path.unlink()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _error(code: str, message: str, path: Path | None = None) -> DeckCompilerError:
    return DeckCompilerError(
        code=code,
        stage="image_request_preparation",
        message=message,
        artifact_path=path.as_posix() if path is not None else None,
        remediation_hint=(
            "Correct the approved Architect Blueprint/Design System package, rerun "
            "prepare-image-requests once, then dispatch ImageGen."
        ),
    )


__all__ = [
    "DESIGN_CONTEXT_MODE",
    "DEFAULT_DESIGN_DIRECTION",
    "ImageRequestPreparationResult",
    "REQUEST_MANIFEST_NAME",
    "REQUEST_MANIFEST_VERSION",
    "REQUEST_VERSION",
    "REFERENCE_MODE",
    "SIDECAR_VERSION",
    "prepare_image_requests",
    "validate_image_request_bundle",
]
