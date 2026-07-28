"""Centralized provider profiles, stage presets, and prompt-packet shaping."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runtime_config import ProviderSettings


DEFAULT_LOCAL_PROFILE = "gemma4_local_26b"
CPU_SAFE_LOCAL_PROFILE = "gemma_local_cpu_safe"
EXPERIMENTAL_Q4_LOCAL_PROFILE = "gemma4_local_26b_q4_experimental"
REMOTE_GEMMA4_PROFILE = "gemma4_remote_26b"
LOCAL_MODEL_PATH_ENV_VAR = "PRESENTATION_AGENT_LOCAL_MODEL_PATH"
LOCAL_MODEL_PATH_26B_IT_ENV_VAR = "PRESENTATION_AGENT_LOCAL_MODEL_PATH_26B_IT"
LOCAL_MODEL_PATH_CPU_SAFE_ENV_VAR = "PRESENTATION_AGENT_LOCAL_MODEL_PATH_CPU_SAFE"
REMOTE_BASE_URL_ENV_VAR = "PRESENTATION_AGENT_REMOTE_BASE_URL"
REMOTE_API_KEY_ENV_VAR = "PRESENTATION_AGENT_REMOTE_API_KEY"
REMOTE_MODEL_ENV_VAR = "PRESENTATION_AGENT_REMOTE_MODEL"
EXPERIMENTAL_Q4_ALLOW_BORDERLINE_ENV_VAR = "PRESENTATION_AGENT_EXPERIMENTAL_Q4_ALLOW_BORDERLINE"
EXPERIMENTAL_ALLOW_OFFLOAD_ENV_VAR = "PRESENTATION_AGENT_EXPERIMENTAL_ALLOW_OFFLOAD"
EXPERIMENTAL_ALLOW_TEMPLATELESS_ENV_VAR = "PRESENTATION_AGENT_EXPERIMENTAL_ALLOW_TEMPLATELESS"
DEFAULT_GEMMA4_LOCAL_MODEL_ID = "google/gemma-4-26B-A4B-it"

STAGE_GATE1_STRUCTURED = "gate1-structured-planning"
STAGE_GATE2_STRUCTURED = "gate2-structured-planning"
STAGE_SLIDE_COPY = "slide-copy-small-batch"
STAGE_QA_REPAIR = "qa-repair"


@dataclass(frozen=True)
class PromptPolicy:
    structured_output_only: bool = True
    json_first: bool = True
    concise_output: bool = True
    allow_markdown_fences: bool = False
    forbid_unknown_fields: bool = True
    preserve_unchanged_keys_on_repair: bool = True
    allow_schema_nulls_only: bool = True
    forbid_raw_ooxml: bool = True
    forbid_invented_assets: bool = True
    forbid_stage_switching: bool = True
    enable_thinking: bool = False


@dataclass(frozen=True)
class StagePreset:
    stage_name: str
    packet_kind: str
    temperature: float
    prompt_budget_target_tokens: int
    max_repair_rounds: int
    max_new_tokens: int
    max_slides_per_call: int | None = None
    policy: PromptPolicy = field(default_factory=PromptPolicy)
    extra_instructions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderProfile:
    profile_name: str
    provider: str
    default_model: str
    model_env_var: str
    fallback_model_env_vars: tuple[str, ...] = ()
    default_options: dict[str, str] = field(default_factory=dict)
    stage_presets: dict[str, StagePreset] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    prompt_serialization_mode: str = "auto"
    missing_chat_template_policy: str = "error"
    chat_template_required_by_default: bool = True
    chat_template_required_for_multimodal: bool = True
    missing_model_error: str | None = None
    missing_endpoint_error: str | None = None
    endpoint_env_var: str | None = None
    api_key_env_var: str | None = None
    api_key_optional: bool = False
    experimental: bool = False
    expected_runtime: str | None = None
    quantization_mode: str | None = None

    def resolve_model(self, requested_model: str | None) -> str:
        if requested_model:
            return requested_model
        override = os.environ.get(self.model_env_var)
        if override:
            return override
        for env_var in self.fallback_model_env_vars:
            fallback = os.environ.get(env_var)
            if fallback:
                return fallback
        return self.default_model


@dataclass(frozen=True)
class ResolvedProviderSettings:
    provider_requested: str
    provider_used: str
    model_requested: str | None
    model_used: str | None
    endpoint_requested: str | None
    endpoint_used: str | None
    profile_requested: str | None
    profile_used: str | None
    options: dict[str, str]
    stage_presets: dict[str, StagePreset]
    warnings: tuple[str, ...]
    prompt_serialization_mode: str
    missing_chat_template_policy: str
    chat_template_required_by_default: bool
    chat_template_required_for_multimodal: bool
    api_key_optional: bool
    experimental: bool
    expected_runtime: str | None
    quantization_mode: str | None


def _gemma_prompt_policy() -> PromptPolicy:
    return PromptPolicy(
        structured_output_only=True,
        json_first=True,
        concise_output=True,
        allow_markdown_fences=False,
        forbid_unknown_fields=True,
        preserve_unchanged_keys_on_repair=True,
        allow_schema_nulls_only=True,
        forbid_raw_ooxml=True,
        forbid_invented_assets=True,
        forbid_stage_switching=True,
        enable_thinking=False,
    )


def _gemma_stage_presets() -> dict[str, StagePreset]:
    policy = _gemma_prompt_policy()
    return {
        STAGE_GATE1_STRUCTURED: StagePreset(
            stage_name=STAGE_GATE1_STRUCTURED,
            packet_kind="gate1-packet",
            temperature=0.0,
            prompt_budget_target_tokens=8192,
            max_repair_rounds=2,
            max_new_tokens=1024,
            policy=policy,
            extra_instructions=(
                "Use English JSON keys exactly as defined by the schema.",
                "Preserve Korean natural-language values when the packet already uses Korean.",
                "Do not emit markdown fences, bullets, or chain-of-thought text.",
            ),
        ),
        STAGE_GATE2_STRUCTURED: StagePreset(
            stage_name=STAGE_GATE2_STRUCTURED,
            packet_kind="gate2-packet",
            temperature=0.05,
            prompt_budget_target_tokens=12288,
            max_repair_rounds=2,
            max_new_tokens=1536,
            policy=policy,
            extra_instructions=(
                "Return only schema-valid planning artifacts for Gate 2.",
                "Do not invent layouts, assets, or slide counts outside the supplied packet constraints.",
            ),
        ),
        STAGE_SLIDE_COPY: StagePreset(
            stage_name=STAGE_SLIDE_COPY,
            packet_kind="slide-generation-packet",
            temperature=0.25,
            prompt_budget_target_tokens=12288,
            max_repair_rounds=1,
            max_new_tokens=1536,
            max_slides_per_call=2,
            policy=policy,
            extra_instructions=(
                "Generate copy for at most two slides per call.",
                "Preserve supplied layout ids, slot ids, and asset paths exactly.",
                "Never invent unsupported layout ids, filenames, or local paths.",
            ),
        ),
        STAGE_QA_REPAIR: StagePreset(
            stage_name=STAGE_QA_REPAIR,
            packet_kind="qa-repair-packet",
            temperature=0.0,
            prompt_budget_target_tokens=8192,
            max_repair_rounds=2,
            max_new_tokens=768,
            policy=policy,
            extra_instructions=(
                "Use only the previous artifact, the validation error, and the smallest needed surrounding context.",
                "Return the smallest corrective rewrite and preserve unchanged keys.",
            ),
        ),
    }


def _host_prefers_cpu_safe_local_profile() -> bool:
    try:
        import torch
    except ImportError:
        return True
    try:
        return not bool(torch.cuda.is_available())
    except Exception:
        return True


def default_transformers_local_profile_name() -> str:
    return CPU_SAFE_LOCAL_PROFILE if _host_prefers_cpu_safe_local_profile() else DEFAULT_LOCAL_PROFILE


PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    DEFAULT_LOCAL_PROFILE: ProviderProfile(
        profile_name=DEFAULT_LOCAL_PROFILE,
        provider="transformers-local",
        default_model=DEFAULT_GEMMA4_LOCAL_MODEL_ID,
        model_env_var=LOCAL_MODEL_PATH_26B_IT_ENV_VAR,
        fallback_model_env_vars=(LOCAL_MODEL_PATH_ENV_VAR,),
        default_options={
            "dtype": "bfloat16",
            "device_map": "auto",
            "max_input_chars": "24000",
            "enable_thinking": "false",
            "trust_remote_code": "false",
            "preferred_load_mode": "auto",
            "minimum_free_vram_gib_bf16": "52",
            "minimum_free_vram_gib_int8": "28",
        },
        stage_presets=_gemma_stage_presets(),
        warnings=(
            "Profile `gemma4_local_26b` expects the instruction-tuned Gemma 4 26B A4B checkpoint. "
            "Prefer a local mirror of `google/gemma-4-26B-A4B-it` via PRESENTATION_AGENT_LOCAL_MODEL_PATH_26B_IT.",
        ),
        prompt_serialization_mode="auto",
        missing_chat_template_policy="require_chat_template",
        chat_template_required_by_default=True,
        chat_template_required_for_multimodal=True,
        experimental=False,
        expected_runtime="gpu",
        quantization_mode="bf16_or_int8",
    ),
    CPU_SAFE_LOCAL_PROFILE: ProviderProfile(
        profile_name=CPU_SAFE_LOCAL_PROFILE,
        provider="transformers-local",
        default_model="",
        model_env_var=LOCAL_MODEL_PATH_CPU_SAFE_ENV_VAR,
        default_options={
            "dtype": "float32",
            "device_map": "cpu",
            "max_input_chars": "20000",
            "enable_thinking": "false",
            "trust_remote_code": "false",
        },
        stage_presets=_gemma_stage_presets(),
        warnings=(
            "CPU-safe local mode expects a smaller or quantized instruction-tuned checkpoint configured explicitly for this host.",
        ),
        prompt_serialization_mode="auto",
        missing_chat_template_policy="gemma_gate1_text_fallback",
        chat_template_required_by_default=False,
        chat_template_required_for_multimodal=True,
        missing_model_error=(
            "CPU-safe local profile `gemma_local_cpu_safe` requires a smaller or quantized instruction-tuned checkpoint. "
            "Set PRESENTATION_AGENT_LOCAL_MODEL_PATH_CPU_SAFE or pass an explicit --model path."
        ),
        experimental=False,
        expected_runtime="cpu",
        quantization_mode="cpu_safe",
    ),
    EXPERIMENTAL_Q4_LOCAL_PROFILE: ProviderProfile(
        profile_name=EXPERIMENTAL_Q4_LOCAL_PROFILE,
        provider="transformers-local",
        default_model=DEFAULT_GEMMA4_LOCAL_MODEL_ID,
        model_env_var=LOCAL_MODEL_PATH_26B_IT_ENV_VAR,
        fallback_model_env_vars=(LOCAL_MODEL_PATH_ENV_VAR,),
        default_options={
            "dtype": "bfloat16",
            "device_map": "auto",
            "max_input_chars": "24000",
            "enable_thinking": "false",
            "trust_remote_code": "false",
            "preferred_load_mode": "4bit",
            "do_sample": "false",
            "max_new_tokens": "768",
            "repair_max_new_tokens": "512",
            "minimum_free_vram_gib_q4_comfortable": "18",
            "minimum_free_vram_gib_q4_borderline": "14.5",
        },
        stage_presets=_gemma_stage_presets(),
        warnings=(
            "Profile `gemma4_local_26b_q4_experimental` is an explicit experimental 4-bit Gate 1 path for Gemma 4 26B A4B on borderline GPU hosts. "
            "It is opt-in only, may fail or stall, and does not relax the safe `gemma4_local_26b` profile.",
        ),
        prompt_serialization_mode="auto",
        missing_chat_template_policy="prefer_chat_template_then_optional_gate1_fallback",
        chat_template_required_by_default=True,
        chat_template_required_for_multimodal=True,
        experimental=True,
        expected_runtime="gpu",
        quantization_mode="4bit",
    ),
    REMOTE_GEMMA4_PROFILE: ProviderProfile(
        profile_name=REMOTE_GEMMA4_PROFILE,
        provider="openai",
        default_model="",
        model_env_var=REMOTE_MODEL_ENV_VAR,
        default_options={
            "timeout_seconds": "120",
            "transport": "openai-compatible",
            "max_input_chars": "24000",
            "enable_thinking": "false",
        },
        stage_presets=_gemma_stage_presets(),
        warnings=(
            "Profile `gemma4_remote_26b` expects a remote OpenAI-compatible Gemma 4 26B IT endpoint such as vLLM "
            "or an Ollama `/v1` endpoint.",
        ),
        prompt_serialization_mode="remote_messages",
        missing_chat_template_policy="error",
        chat_template_required_by_default=True,
        chat_template_required_for_multimodal=False,
        missing_model_error=(
            "Remote profile `gemma4_remote_26b` requires PRESENTATION_AGENT_REMOTE_MODEL or an explicit --model value."
        ),
        missing_endpoint_error=(
            "Remote profile `gemma4_remote_26b` requires PRESENTATION_AGENT_REMOTE_BASE_URL or an explicit --endpoint "
            "value such as `http://host:8000/v1` or `http://host:11434/v1`."
        ),
        endpoint_env_var=REMOTE_BASE_URL_ENV_VAR,
        api_key_env_var=REMOTE_API_KEY_ENV_VAR,
        api_key_optional=True,
        experimental=False,
        expected_runtime="remote",
        quantization_mode=None,
    ),
}


def get_provider_profile(profile_name: str | None) -> ProviderProfile | None:
    if profile_name is None:
        return None
    return PROVIDER_PROFILES.get(profile_name)


def resolve_provider_settings(settings: ProviderSettings | None) -> ResolvedProviderSettings:
    normalized = settings if settings is not None else ProviderSettings()
    requested_provider = (normalized.provider or "local-none").strip().lower() or "local-none"
    requested_profile = normalized.profile.strip() if normalized.profile else None
    if requested_provider == "transformers-local" and requested_profile is None:
        requested_profile = default_transformers_local_profile_name()
    profile = get_provider_profile(requested_profile)
    if requested_profile is not None and profile is None:
        raise ValueError(f"unknown provider profile {requested_profile!r}")
    if profile is not None and requested_provider not in {"", "local-none", profile.provider}:
        raise ValueError(
            f"provider {requested_provider!r} conflicts with profile {requested_profile!r} "
            f"(expected provider {profile.provider!r})"
        )
    provider_used = profile.provider if profile is not None and requested_provider in {"", "local-none"} else requested_provider
    model_used = normalized.model or (profile.resolve_model(normalized.model) if profile is not None else None)
    if profile is not None and not model_used and profile.missing_model_error:
        raise ValueError(profile.missing_model_error)
    endpoint_used = normalized.endpoint
    if endpoint_used is None and profile is not None and profile.endpoint_env_var:
        endpoint_override = os.environ.get(profile.endpoint_env_var)
        if endpoint_override:
            endpoint_used = endpoint_override
    if profile is not None and not endpoint_used and profile.missing_endpoint_error:
        raise ValueError(profile.missing_endpoint_error)
    options = dict(profile.default_options) if profile is not None else {}
    options.update(normalized.options)
    if profile is not None and profile.api_key_env_var and "api_key" not in options:
        api_key_override = os.environ.get(profile.api_key_env_var)
        if api_key_override:
            options["api_key"] = api_key_override
    warnings = profile.warnings if profile is not None else ()
    return ResolvedProviderSettings(
        provider_requested=requested_provider,
        provider_used=provider_used,
        model_requested=normalized.model,
        model_used=model_used,
        endpoint_requested=normalized.endpoint,
        endpoint_used=endpoint_used,
        profile_requested=normalized.profile,
        profile_used=profile.profile_name if profile is not None else None,
        options=options,
        stage_presets=dict(profile.stage_presets) if profile is not None else _gemma_stage_presets(),
        warnings=warnings,
        prompt_serialization_mode=profile.prompt_serialization_mode if profile is not None else "auto",
        missing_chat_template_policy=profile.missing_chat_template_policy if profile is not None else "error",
        chat_template_required_by_default=profile.chat_template_required_by_default if profile is not None else True,
        chat_template_required_for_multimodal=profile.chat_template_required_for_multimodal if profile is not None else True,
        api_key_optional=profile.api_key_optional if profile is not None else False,
        experimental=profile.experimental if profile is not None else False,
        expected_runtime=profile.expected_runtime if profile is not None else None,
        quantization_mode=profile.quantization_mode if profile is not None else None,
    )


def stage_preset_for(settings: ProviderSettings | None, stage_name: str) -> StagePreset | None:
    resolved = resolve_provider_settings(settings)
    return resolved.stage_presets.get(stage_name)


def build_gate1_packet(brief_payload: dict[str, Any]) -> dict[str, Any]:
    materials: list[dict[str, Any]] = []
    for material in (brief_payload.get("current_materials") or [])[:8]:
        if not isinstance(material, dict):
            continue
        materials.append(
            {
                "label": material.get("label"),
                "material_type": material.get("material_type"),
                "path": material.get("path"),
            }
        )
    packet = {
        "topic": brief_payload.get("topic"),
        "deck_title": brief_payload.get("deck_title"),
        "audience": list(brief_payload.get("audience") or [])[:6],
        "purpose": brief_payload.get("purpose"),
        "delivery_mode": brief_payload.get("delivery_mode"),
        "expected_duration_minutes": brief_payload.get("expected_duration_minutes"),
        "current_materials": materials,
        "constraints": list(brief_payload.get("constraints") or [])[:8],
        "notes": list(brief_payload.get("notes") or [])[:6],
        "facts": list(brief_payload.get("facts") or [])[:6],
        "recommendations": list(brief_payload.get("recommendations") or [])[:6],
        "assumptions": list(brief_payload.get("assumptions") or [])[:6],
        "initial_assumptions": list(brief_payload.get("initial_assumptions") or [])[:6],
    }
    return {key: value for key, value in packet.items() if value not in (None, [], "")}


def build_gate2_packet(
    workflow_plan_payload: dict[str, Any],
    *,
    brief_payload: dict[str, Any] | None = None,
    reference_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet = {
        "workflow_option": workflow_plan_payload.get("workflow_option"),
        "deck_title": workflow_plan_payload.get("deck_title"),
        "objective": workflow_plan_payload.get("objective"),
        "audience": list(workflow_plan_payload.get("audience") or [])[:6],
        "deck_mode": workflow_plan_payload.get("deck_mode"),
        "slide_ratio": workflow_plan_payload.get("slide_ratio"),
        "main_story_slide_count_range": workflow_plan_payload.get("main_story_slide_count_range"),
        "appendix_candidate_slide_count_range": workflow_plan_payload.get("appendix_candidate_slide_count_range"),
        "brief": build_gate1_packet(brief_payload or {}) if brief_payload else None,
        "reference_summary": reference_summary,
    }
    return {key: value for key, value in packet.items() if value not in (None, [], "")}


def build_slide_generation_packet(
    slides: list[dict[str, Any]],
    *,
    layout_ids: list[str],
    asset_paths: list[str],
    design_tokens: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if len(slides) < 1 or len(slides) > 2:
        raise ValueError("slide-generation packet requires one or two slides only")
    packet = {
        "slides": slides,
        "allowed_layout_ids": layout_ids,
        "allowed_asset_paths": asset_paths,
        "design_tokens": design_tokens or {},
    }
    return packet


def build_qa_repair_packet(
    previous_artifact: dict[str, Any] | list[Any] | str,
    validation_error: str,
    *,
    surrounding_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet = {
        "previous_artifact": previous_artifact,
        "validation_error": validation_error,
    }
    if surrounding_context:
        packet["surrounding_context"] = surrounding_context
    return packet


def build_stage_packet(stage_name: str, **kwargs: Any) -> dict[str, Any]:
    if stage_name == STAGE_GATE1_STRUCTURED:
        return build_gate1_packet(kwargs["brief_payload"])
    if stage_name == STAGE_GATE2_STRUCTURED:
        return build_gate2_packet(
            kwargs["workflow_plan_payload"],
            brief_payload=kwargs.get("brief_payload"),
            reference_summary=kwargs.get("reference_summary"),
        )
    if stage_name == STAGE_SLIDE_COPY:
        return build_slide_generation_packet(
            kwargs["slides"],
            layout_ids=kwargs["layout_ids"],
            asset_paths=kwargs["asset_paths"],
            design_tokens=kwargs.get("design_tokens"),
        )
    if stage_name == STAGE_QA_REPAIR:
        return build_qa_repair_packet(
            kwargs["previous_artifact"],
            kwargs["validation_error"],
            surrounding_context=kwargs.get("surrounding_context"),
        )
    raise KeyError(f"unknown stage packet {stage_name!r}")


def model_path_warning(model_path: str | None) -> str | None:
    if not model_path:
        return None
    name = Path(model_path).name.lower()
    if "-it" in name or "instruction" in name:
        return None
    return (
        "Configured local model path does not clearly indicate an instruction-tuned Gemma checkpoint. "
        "Structured planning quality may degrade if the directory points to a base model."
    )
