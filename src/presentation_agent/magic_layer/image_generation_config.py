"""Opt-in image generation route configuration for Magic Layer visual assets."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ACTIVE_CONFIG_ENV_VAR = "PPTXLOCAL_IMAGE_GENERATION_CONFIG"


ACTIVE_CONFIG_CANDIDATES = [
    "config/image_generation.openai.local.json",
    "config/image_generation.openai.json",
    "config/image_generation.json",
    "configs/image_generation.json",
    "design_runs/run_002/config/image_generation.json",
]


REQUIRED_SCOPE = "d07_2_visual_field_assets_only"


def load_image_generation_route_config(
    repo_root: Path,
    *,
    env: dict[str, str] | None = None,
    active_only: bool = False,
    missing_decision: str = "D07_2_4_BLOCKED_GENERATION_CONFIG_MISSING",
) -> dict[str, Any]:
    env = env if env is not None else os.environ
    configs_found: list[str] = []
    config_payload: dict[str, Any] | None = None
    selected_path: Path | None = None
    for path in _candidate_paths(repo_root, env=env, active_only=active_only):
        if not path.exists():
            continue
        configs_found.append(path.as_posix())
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return _report(
                status="blocked",
                decision=missing_decision,
                configs_found=configs_found,
                selected_path=path,
                payload={},
                missing=[f"valid_json:{exc}"],
                env=env,
            )
        if payload.get("provider") == "openai":
            config_payload = payload
            selected_path = path
            break
    if config_payload is None:
        return _report(
            status="blocked",
            decision=missing_decision,
            configs_found=configs_found,
            selected_path=None,
            payload={},
            missing=["active_openai_config_file"],
            env=env,
        )
    missing = validate_image_generation_config(config_payload, env=env)
    return _report(
        status="ready" if not missing else "blocked",
        decision="GENERATION_ROUTE_READY" if not missing else missing_decision,
        configs_found=configs_found,
        selected_path=selected_path,
        payload=config_payload,
        missing=missing,
        env=env,
    )


def _candidate_paths(repo_root: Path, *, env: dict[str, str], active_only: bool) -> list[Path]:
    configured = env.get(ACTIVE_CONFIG_ENV_VAR)
    if configured:
        path = Path(configured)
        return [path if path.is_absolute() else repo_root / path]
    if active_only:
        return [repo_root / "config/image_generation.openai.local.json"]
    return [repo_root / relative for relative in ACTIVE_CONFIG_CANDIDATES]


def validate_image_generation_config(config: dict[str, Any], *, env: dict[str, str] | None = None) -> list[str]:
    env = env if env is not None else os.environ
    missing: list[str] = []
    if config.get("image_generation_enabled") is not True:
        missing.append("image_generation_enabled_true")
    if config.get("allow_network_calls") is not True:
        missing.append("allow_network_calls_true")
    if config.get("provider") != "openai":
        missing.append("provider_openai")
    if config.get("model") != "gpt-image-2":
        missing.append("model_gpt_image_2")
    if config.get("api") != "image_api":
        missing.append("api_image_api")
    if config.get("output_format") != "png":
        missing.append("output_format_png")
    if config.get("require_env_api_key") is not True:
        missing.append("require_env_api_key_true")
    if config.get("do_not_store_secrets") is not True:
        missing.append("do_not_store_secrets_true")
    if config.get("approved_use_scope") != REQUIRED_SCOPE:
        missing.append(f"approved_use_scope_{REQUIRED_SCOPE}")
    env_name = str(config.get("env_api_key_name") or "OPENAI_API_KEY")
    if not env.get(env_name):
        missing.append(f"env_api_key_present:{env_name}")
    return missing


def sanitized_generation_config(config_report: dict[str, Any]) -> dict[str, Any]:
    payload = dict(config_report.get("config") or {})
    env_name = payload.get("env_api_key_name")
    if env_name:
        payload["env_api_key_present"] = config_report.get("env_api_key_present")
    payload.pop("api_key", None)
    return payload


def _report(
    *,
    status: str,
    decision: str,
    configs_found: list[str],
    selected_path: Path | None,
    payload: dict[str, Any],
    missing: list[str],
    env: dict[str, str],
) -> dict[str, Any]:
    env_name = str(payload.get("env_api_key_name") or "OPENAI_API_KEY")
    return {
        "schema_name": "image_generation_route_config_report",
        "status": status,
        "decision": decision,
        "configs_found": configs_found,
        "selected_config_path": selected_path.as_posix() if selected_path else None,
        "config": {
            key: value
            for key, value in payload.items()
            if key not in {"api_key", "OPENAI_API_KEY"} and "secret" not in key.lower()
        },
        "missing_requirements": missing,
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "allow_network_calls": payload.get("allow_network_calls") is True,
        "image_generation_enabled": payload.get("image_generation_enabled") is True,
        "env_api_key_name": env_name,
        "env_api_key_present": bool(env.get(env_name)),
        "secrets_stored": False,
        "canva_parity_claimed": False,
    }
