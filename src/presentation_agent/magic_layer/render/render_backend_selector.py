from __future__ import annotations

from typing import Any

from src.presentation_agent.qa.render_pptx_preview import _backend_availability


def select_render_backend(*, force_unavailable: bool = False) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    if force_unavailable:
        for name in ("existing_repo_render_backend", "powerpoint_com", "libreoffice"):
            candidates.append({"backend": name, "available": False, "path": None, "reason": "Forced unavailable for controlled test."})
        return _blocked(candidates)

    existing = {
        "backend": "existing_repo_render_backend",
        "available": True,
        "path": "src.presentation_agent.qa.render_pptx_preview.render_pptx_preview",
        "reason": None,
    }
    candidates.append(existing)
    for backend in ("powerpoint_com", "libreoffice"):
        candidates.append(_backend_availability(backend))

    selected = next((item for item in candidates if item["backend"] in {"powerpoint_com", "libreoffice"} and item.get("available")), None)
    if not selected:
        return _blocked(candidates)
    return {
        "schema": "render_backend_selection_report.v1",
        "decision": "RENDER_BACKEND_SELECTED",
        "selected_backend": selected["backend"],
        "candidates_checked": candidates,
        "availability_evidence": selected,
        "reason": "Selected first available local renderer supported by the existing repo render preview module.",
        "command_or_method": "src.presentation_agent.qa.render_pptx_preview.render_pptx_preview",
        "limitations": ["controlled_single_pptx_only", "local_renderer_environment_dependent"],
        "writes_only_c03_output_folder": True,
        "renderer_modifies_source": False,
        "dependency_install_attempted": False,
    }


def _blocked(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "render_backend_selection_report.v1",
        "decision": "C03_BLOCKED_RENDER_BACKEND_UNAVAILABLE",
        "selected_backend": None,
        "candidates_checked": candidates,
        "availability_evidence": None,
        "reason": "No safe local renderer backend is available.",
        "command_or_method": None,
        "limitations": ["render_not_performed"],
        "writes_only_c03_output_folder": True,
        "renderer_modifies_source": False,
        "dependency_install_attempted": False,
    }


def select_render_backend_v2(
    *,
    powerpoint_attempts: list[dict[str, Any]],
    libreoffice_attempts: list[dict[str, Any]],
    existing_repo_attempts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Select only a backend that already produced a valid controlled PNG."""

    existing_repo_attempts = existing_repo_attempts or []
    candidate_groups = [
        ("powerpoint_com", powerpoint_attempts),
        ("libreoffice", libreoffice_attempts),
        ("existing_repo_render_backend", existing_repo_attempts),
    ]
    for backend_name, attempts in candidate_groups:
        success = next((item for item in attempts if item.get("status") == "SUCCESS" and item.get("output_path") is not None), None)
        if success:
            return {
                "schema": "render_backend_selection_v2_report.v1",
                "decision": "RENDER_BACKEND_SELECTED",
                "selected_backend": backend_name,
                "selected_strategy": success.get("method") or success.get("attempt_id"),
                "reason": "Selected first backend with a successful controlled render attempt.",
                "output_path": success.get("output_path"),
                "limitations": success.get("limitations", ["controlled_single_pptx_only"]),
                "backend_status": "SUCCESS",
                "source_hash_unchanged": success.get("source_hash_unchanged", True),
                "renderer_modifies_source": False,
                "render_ready": True,
                "attempts_considered": {
                    "powerpoint_com": powerpoint_attempts,
                    "libreoffice": libreoffice_attempts,
                    "existing_repo_render_backend": existing_repo_attempts,
                },
            }
    return {
        "schema": "render_backend_selection_v2_report.v1",
        "decision": "C03A_BLOCKED_RENDER_BACKEND_UNAVAILABLE",
        "selected_backend": None,
        "selected_strategy": None,
        "reason": "No backend produced a valid controlled render PNG. Detection alone is not enough.",
        "output_path": None,
        "limitations": ["render_not_performed", "no_fake_render_evidence"],
        "backend_status": "NO_SUCCESSFUL_RENDER_ATTEMPT",
        "source_hash_unchanged": all(item.get("source_hash_unchanged", True) for item in [*powerpoint_attempts, *libreoffice_attempts, *existing_repo_attempts]),
        "renderer_modifies_source": False,
        "render_ready": False,
        "attempts_considered": {
            "powerpoint_com": powerpoint_attempts,
            "libreoffice": libreoffice_attempts,
            "existing_repo_render_backend": existing_repo_attempts,
        },
    }
