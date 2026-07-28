"""Small provider adapter layer for schema-critical runtime intake steps."""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .provider_profiles import (
    DEFAULT_LOCAL_PROFILE,
    EXPERIMENTAL_ALLOW_OFFLOAD_ENV_VAR,
    EXPERIMENTAL_ALLOW_TEMPLATELESS_ENV_VAR,
    EXPERIMENTAL_Q4_ALLOW_BORDERLINE_ENV_VAR,
    EXPERIMENTAL_Q4_LOCAL_PROFILE,
    REMOTE_GEMMA4_PROFILE,
    STAGE_GATE1_STRUCTURED,
    ResolvedProviderSettings,
    StagePreset,
    build_stage_packet,
    model_path_warning,
    resolve_provider_settings,
)
from .runtime_config import ProviderSettings


class ProviderRuntimeContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


class BriefIntakeSummary(ProviderRuntimeContract):
    topic: str
    deck_title: str | None = None
    audience: list[str] = Field(default_factory=list)
    purpose: str
    delivery_mode: str
    expected_duration_minutes: int | None = None
    material_labels: list[str] = Field(default_factory=list)
    material_count: int = 0
    appendix_expected: bool = False
    lecture_signal: bool = False
    key_terms: list[str] = Field(default_factory=list)


class LLMRequestTrace(ProviderRuntimeContract):
    target: str
    provider: str
    transport: str
    model: str | None = None
    endpoint: str | None = None
    request_path: str | None = None
    request_url: str | None = None
    strict_structured_output: bool = True
    response_status: int | None = None
    profile: str | None = None
    stage_preset: str | None = None
    packet_kind: str | None = None
    packet_keys: list[str] = Field(default_factory=list)
    temperature: float | None = None
    repair_attempt: int = 0


class LLMBackendProof(ProviderRuntimeContract):
    artifact_id: str = "llm-backend-proof"
    provider_requested: str
    provider_used: str
    model_requested: str | None = None
    model_used: str | None = None
    endpoint_requested: str | None = None
    endpoint_used: str | None = None
    profile_requested: str | None = None
    profile_used: str | None = None
    transport_used: str
    strict_structured_output: bool = True
    fallback_occurred: bool = False
    llm_request_count: int = 0
    llm_request_targets: list[str] = Field(default_factory=list)
    request_traces: list[LLMRequestTrace] = Field(default_factory=list)
    stage_preset: str | None = None
    packet_kind: str | None = None
    packet_keys: list[str] = Field(default_factory=list)
    repair_attempt_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    brief_intake: BriefIntakeSummary


class GPUDeviceSummary(ProviderRuntimeContract):
    index: int
    name: str
    total_vram_gib: float | None = None
    free_vram_gib: float | None = None


class TransformersLocalInspection(ProviderRuntimeContract):
    profile: str | None = None
    model_path: str | None = None
    runtime_posture: str
    cuda_available: bool = False
    gpu_count: int = 0
    aggregate_total_vram_gib: float | None = None
    aggregate_free_vram_gib: float | None = None
    gpu_devices: list[GPUDeviceSummary] = Field(default_factory=list)
    bitsandbytes_available: bool = False
    experimental_borderline_enabled: bool = False
    experimental_offload_allowed: bool = False
    experimental_templateless_enabled: bool = False
    chat_template_present: bool = False
    serialization_path: str | None = None
    selected_load_mode: str | None = None
    preflight_passed: bool = False
    preflight_error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ProviderRuntimeError(RuntimeError):
    """Raised when provider configuration or execution fails."""


class StructuredOutputError(ProviderRuntimeError):
    """Raised when a strict structured-output request returns malformed content."""


_TRANSFORMERS_RUNTIME_CACHE: dict[tuple[str, str, str], tuple[Any, Any, Any]] = {}
_TRANSFORMERS_PROCESSOR_CACHE: dict[tuple[str, bool], Any] = {}


def _normalize_provider_settings(settings: ProviderSettings | None) -> ProviderSettings:
    return settings if settings is not None else ProviderSettings()


def _material_labels(brief_payload: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for material in brief_payload.get("current_materials") or []:
        if not isinstance(material, dict):
            continue
        label = str(material.get("label") or material.get("path") or "").strip()
        if label:
            labels.append(label)
    return labels


def _appendix_expected(brief_payload: dict[str, Any]) -> bool:
    text = " ".join(
        str(item)
        for item in [
            *(brief_payload.get("constraints") or []),
            *(brief_payload.get("notes") or []),
            *(brief_payload.get("recommendations") or []),
            *(brief_payload.get("facts") or []),
            brief_payload.get("purpose") or "",
        ]
        if item
    ).lower()
    return any(keyword in text for keyword in ("appendix", "backup", "methods", "reference", "deep dive", "부록"))


def _lecture_signal(brief_payload: dict[str, Any]) -> bool:
    duration = brief_payload.get("expected_duration_minutes")
    if not isinstance(duration, int):
        duration = 0
    text = " ".join(
        str(item)
        for item in [
            brief_payload.get("topic") or "",
            brief_payload.get("purpose") or "",
            *brief_payload.get("audience", []),
            *(brief_payload.get("constraints") or []),
            *(brief_payload.get("notes") or []),
        ]
        if item
    ).lower()
    lecture_keywords = ("lecture", "curriculum", "course", "graduate", "students", "강의", "교재", "대학원", "대학원생")
    material_types = {
        str(material.get("material_type") or "").lower()
        for material in brief_payload.get("current_materials") or []
        if isinstance(material, dict)
    }
    return duration >= 90 and "document" in material_types and any(keyword in text for keyword in lecture_keywords)


def _key_terms(brief_payload: dict[str, Any]) -> list[str]:
    source = " ".join(
        str(item)
        for item in [
            brief_payload.get("topic") or "",
            *(brief_payload.get("audience") or []),
            *(_material_labels(brief_payload)),
        ]
        if item
    )
    tokens = re.findall(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣\\-]{1,30}", source)
    unique: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered not in {item.lower() for item in unique}:
            unique.append(token)
        if len(unique) >= 6:
            break
    return unique


def build_local_brief_intake(brief_payload: dict[str, Any]) -> BriefIntakeSummary:
    material_labels = _material_labels(brief_payload)
    return BriefIntakeSummary(
        topic=str(brief_payload.get("topic") or "").strip(),
        deck_title=str(brief_payload.get("deck_title")).strip() if brief_payload.get("deck_title") is not None else None,
        audience=[str(item).strip() for item in brief_payload.get("audience") or [] if str(item).strip()],
        purpose=str(brief_payload.get("purpose") or "").strip(),
        delivery_mode=str(brief_payload.get("delivery_mode") or "").strip(),
        expected_duration_minutes=brief_payload.get("expected_duration_minutes")
        if isinstance(brief_payload.get("expected_duration_minutes"), int)
        else None,
        material_labels=material_labels,
        material_count=len(material_labels),
        appendix_expected=_appendix_expected(brief_payload),
        lecture_signal=_lecture_signal(brief_payload),
        key_terms=_key_terms(brief_payload),
    )


def _strict_json_content(raw_content: Any, *, provider: str, transport: str, target: str) -> dict[str, Any]:
    if not isinstance(raw_content, str):
        raise StructuredOutputError(
            f"{provider} transport `{transport}` returned non-string structured content for target `{target}`."
        )
    stripped = raw_content.strip()
    if stripped.startswith("```"):
        raise StructuredOutputError(
            f"{provider} transport `{transport}` returned code-fenced pseudo-JSON for target `{target}`."
        )
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            f"{provider} transport `{transport}` returned malformed JSON for target `{target}`: {exc.msg}."
        ) from exc
    if not isinstance(payload, dict):
        raise StructuredOutputError(
            f"{provider} transport `{transport}` returned a non-object JSON payload for target `{target}`."
        )
    return payload


def _validate_brief_output(raw_content: Any, *, provider: str, transport: str, target: str) -> BriefIntakeSummary:
    payload = _strict_json_content(raw_content, provider=provider, transport=transport, target=target)
    try:
        return BriefIntakeSummary.model_validate(payload)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"{provider} transport `{transport}` returned schema-invalid JSON for target `{target}`: {exc}"
        ) from exc


def _json_post(
    *,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int,
) -> tuple[int, dict[str, Any]]:
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=encoded, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            status = getattr(response, "status", None) or response.getcode()
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise ProviderRuntimeError(f"HTTP {exc.code} calling `{url}`: {body_text}") from exc
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise ProviderRuntimeError(f"Could not reach `{url}`: {reason}") from exc
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeError(f"Endpoint `{url}` returned malformed JSON: {exc.msg}.") from exc
    if not isinstance(payload, dict):
        raise ProviderRuntimeError(f"Endpoint `{url}` returned a non-object JSON response.")
    return status, payload


def _timeout_seconds_from_options(options: dict[str, str]) -> int:
    raw = options.get("timeout_seconds")
    if raw is None:
        return 60
    try:
        value = int(raw)
    except ValueError as exc:
        raise ProviderRuntimeError(f"provider option `timeout_seconds` must be an integer, found {raw!r}.") from exc
    if value < 1:
        raise ProviderRuntimeError("provider option `timeout_seconds` must be positive.")
    return value


def _resolve_ollama_model(resolved: ResolvedProviderSettings) -> str:
    model = resolved.model_used or os.environ.get("OLLAMA_MODEL")
    if model:
        return model
    raise ProviderRuntimeError("provider `ollama` requires `model`, a profile default model, or OLLAMA_MODEL.")


def _resolve_openai_model(resolved: ResolvedProviderSettings) -> str:
    model = resolved.model_used or os.environ.get("OPENAI_MODEL")
    if model:
        return model
    raise ProviderRuntimeError("provider `openai` requires `model`, a profile default model, or OPENAI_MODEL.")


def _resolve_endpoint(resolved: ResolvedProviderSettings, *, provider: str) -> str:
    configured = resolved.endpoint_used or resolved.options.get("endpoint")
    if configured:
        return configured.rstrip("/")
    if provider == "ollama":
        return (
            os.environ.get("OLLAMA_ENDPOINT")
            or os.environ.get("OLLAMA_BASE_URL")
            or os.environ.get("OLLAMA_HOST")
            or "http://127.0.0.1:11434"
        ).rstrip("/")
    if provider == "openai":
        return (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    return ""


def _openai_chat_completions_url(endpoint: str) -> tuple[str, str]:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/chat/completions"):
        request_path = urlsplit(normalized).path or "/chat/completions"
        return normalized, request_path
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions", "/v1/chat/completions"
    return f"{normalized}/v1/chat/completions", "/v1/chat/completions"


def _transport_options(resolved: ResolvedProviderSettings) -> dict[str, Any]:
    return {
        key: value
        for key, value in resolved.options.items()
        if key
        not in {
            "api_key",
            "timeout_seconds",
            "transport",
            "endpoint",
            "model",
            "dtype",
            "device_map",
            "top_p",
            "do_sample",
            "max_input_chars",
            "enable_thinking",
            "trust_remote_code",
            "temperature",
            "repair_max_new_tokens",
            "max_new_tokens",
        }
    }


def _option_as_bool(options: dict[str, str], key: str, default: bool) -> bool:
    raw = options.get(key)
    if raw is None:
        return default
    lowered = str(raw).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ProviderRuntimeError(f"provider option `{key}` must be a boolean-like value, found {raw!r}.")


def _option_as_int(options: dict[str, str], key: str, default: int) -> int:
    raw = options.get(key)
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise ProviderRuntimeError(f"provider option `{key}` must be an integer, found {raw!r}.") from exc
    if value < 1:
        raise ProviderRuntimeError(f"provider option `{key}` must be positive.")
    return value


def _option_as_float(options: dict[str, str], key: str, default: float) -> float:
    raw = options.get(key)
    if raw is None:
        return default
    try:
        value = float(str(raw).strip())
    except ValueError as exc:
        raise ProviderRuntimeError(f"provider option `{key}` must be numeric, found {raw!r}.") from exc
    if value < 0:
        raise ProviderRuntimeError(f"provider option `{key}` must not be negative.")
    return value


def _env_flag_enabled(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _schema_text() -> str:
    return json.dumps(BriefIntakeSummary.model_json_schema(), ensure_ascii=False, indent=2)


def _build_system_prompt(preset: StagePreset) -> str:
    policy = preset.policy
    instructions = [
        "You are a local planning model for a deterministic PPTX pipeline.",
        f"Stage preset: {preset.stage_name}. Packet kind: {preset.packet_kind}.",
        "Return exactly one JSON object and nothing else.",
        "Use English schema keys exactly as given.",
        "Keep prose concise and operational.",
    ]
    if policy.structured_output_only:
        instructions.append("Structured output only.")
    if policy.json_first:
        instructions.append("JSON-first output; do not emit prose before or after the object.")
    if not policy.allow_markdown_fences:
        instructions.append("Never use markdown fences.")
    if policy.forbid_unknown_fields:
        instructions.append("Never add fields outside the schema.")
    if policy.allow_schema_nulls_only:
        instructions.append("Emit null or [] only when the schema allows them.")
    if policy.forbid_raw_ooxml:
        instructions.append("Do not emit OOXML, raw PPTX XML, or code snippets.")
    if policy.forbid_invented_assets:
        instructions.append("Do not invent asset ids, file names, local paths, or missing source files.")
    if policy.forbid_stage_switching:
        instructions.append("Do not switch stages or include work from other stages.")
    if not policy.enable_thinking:
        instructions.append("Do not emit thinking-mode text, scratchpads, or hidden reasoning.")
    instructions.extend(preset.extra_instructions)
    instructions.append("Target schema:")
    instructions.append(_schema_text())
    return "\n".join(instructions)


def _build_initial_user_prompt(packet: dict[str, Any]) -> str:
    return "Normalize this stage packet into the target schema.\n\n" + json.dumps(packet, ensure_ascii=False, indent=2)


def _build_repair_user_prompt(last_artifact: str, validation_error: str) -> str:
    return "\n".join(
        [
            "Repair the last artifact with the smallest corrective rewrite.",
            "Keep unchanged keys identical unless the validation error forces a change.",
            "Return one JSON object only.",
            "",
            "Validation error:",
            validation_error,
            "",
            "Last artifact:",
            last_artifact,
        ]
    )


def _has_usable_chat_template(processor: Any) -> bool:
    for candidate in (processor, getattr(processor, "tokenizer", None)):
        template = getattr(candidate, "chat_template", None)
        if isinstance(template, str) and template.strip():
            return True
    return False


def _messages_are_text_only(messages: list[dict[str, str]]) -> bool:
    return all(isinstance(message.get("content"), str) for message in messages)


def _gemma_gate1_text_fallback_eligible(
    messages: list[dict[str, str]],
    *,
    resolved: ResolvedProviderSettings,
    preset: StagePreset,
) -> bool:
    return (
        preset.stage_name == STAGE_GATE1_STRUCTURED
        and _messages_are_text_only(messages)
        and all((message.get("role") or "").strip().lower() in {"system", "user"} for message in messages)
    )


def _gemma_gate1_text_fallback_prompt(messages: list[dict[str, str]]) -> str:
    merged_content = "\n\n".join(
        content.strip()
        for content in (message.get("content") or "" for message in messages)
        if isinstance(content, str) and content.strip()
    )
    return "\n".join(
        [
            "<start_of_turn>user",
            merged_content,
            "<end_of_turn>",
            "<start_of_turn>model",
        ]
    )


def _missing_chat_template_error(
    *,
    resolved: ResolvedProviderSettings,
    preset: StagePreset,
    model_path: str,
    multimodal_required: bool,
) -> ProviderRuntimeError:
    if resolved.missing_chat_template_policy == "require_chat_template":
        guidance = (
            "Selected checkpoint for profile `gemma4_local_26b` is expected to be instruction-tuned and include "
            "chat-template metadata, but no usable chat template was found in the tokenizer/processor assets. "
            "Use `google/gemma-4-26B-A4B-it` or a local mirror of that exact IT checkpoint, or restore "
            "chat_template.jinja and matching tokenizer metadata."
        )
    elif resolved.missing_chat_template_policy == "prefer_chat_template_then_optional_gate1_fallback":
        guidance = (
            "Experimental profile `gemma4_local_26b_q4_experimental` expects Gemma IT chat-template metadata by "
            "default, but no usable chat template was found in the tokenizer/processor assets. This profile fails "
            "closed by default. To attempt the existing Gate 1 text-only fallback anyway, set "
            f"{EXPERIMENTAL_ALLOW_TEMPLATELESS_ENV_VAR}=1. Non-Gate-1 and multimodal requests still require a real "
            "chat template."
        )
    else:
        guidance = (
            "Local checkpoint lacks chat-template metadata for transformers-local prompt serialization. "
            "This usually means a non-IT Gemma checkpoint or incomplete tokenizer/processor assets. "
            "Use a proper Gemma instruction-tuned checkpoint or restore chat_template.jinja."
        )
    if multimodal_required:
        guidance += " Multimodal requests require a valid chat template."
    guidance += f" Profile={resolved.profile_used or 'none'} stage={preset.stage_name} model_path={model_path}."
    return ProviderRuntimeError(guidance)


def _serialize_transformers_chat_prompt(
    *,
    processor: Any,
    messages: list[dict[str, str]],
    resolved: ResolvedProviderSettings,
    preset: StagePreset,
) -> str:
    enable_thinking = _option_as_bool(resolved.options, "enable_thinking", preset.policy.enable_thinking)
    if _has_usable_chat_template(processor):
        return processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )
    if (
        resolved.prompt_serialization_mode == "auto"
        and resolved.missing_chat_template_policy == "gemma_gate1_text_fallback"
        and _gemma_gate1_text_fallback_eligible(messages, resolved=resolved, preset=preset)
    ):
        return _gemma_gate1_text_fallback_prompt(messages)
    if (
        resolved.prompt_serialization_mode == "auto"
        and resolved.missing_chat_template_policy == "prefer_chat_template_then_optional_gate1_fallback"
        and _env_flag_enabled(EXPERIMENTAL_ALLOW_TEMPLATELESS_ENV_VAR)
        and _gemma_gate1_text_fallback_eligible(messages, resolved=resolved, preset=preset)
    ):
        return _gemma_gate1_text_fallback_prompt(messages)
    raise _missing_chat_template_error(
        resolved=resolved,
        preset=preset,
        model_path=resolved.model_used or "",
        multimodal_required=resolved.chat_template_required_for_multimodal and not _messages_are_text_only(messages),
    )


def _torch_cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _bytes_to_gib(value: int | float | None) -> float | None:
    if value is None:
        return None
    return round(float(value) / (1024**3), 2)


def _transformers_supports_4bit() -> bool:
    try:
        import bitsandbytes  # noqa: F401
        from transformers import BitsAndBytesConfig  # noqa: F401
    except ImportError:
        return False
    return True


def _transformers_supports_int8() -> bool:
    return _transformers_supports_4bit()


def _torch_cuda_supports_bfloat16(torch_mod: Any) -> bool:
    try:
        probe = getattr(torch_mod.cuda, "is_bf16_supported", None)
        if callable(probe):
            return bool(probe())
    except Exception:
        return False
    return False


def _bnb_4bit_compute_dtype(torch_mod: Any) -> Any:
    return torch_mod.bfloat16 if _torch_cuda_supports_bfloat16(torch_mod) else torch_mod.float16


def _device_target_is_cuda(target: Any) -> bool:
    if isinstance(target, int):
        return True
    lowered = str(target).strip().lower()
    return lowered.startswith("cuda")


def _non_cuda_device_targets(model: Any) -> set[str]:
    hf_device_map = getattr(model, "hf_device_map", None)
    if isinstance(hf_device_map, dict):
        return {
            str(target).lower()
            for target in hf_device_map.values()
            if not _device_target_is_cuda(target)
        }
    device = getattr(model, "device", None)
    device_type = getattr(device, "type", None)
    if isinstance(device_type, str) and device_type.lower() == "cuda":
        return set()
    if device is None:
        return set()
    lowered = str(device).strip().lower()
    if lowered.startswith("cuda"):
        return set()
    return {lowered or "unknown"}


def _inspect_cuda_devices() -> tuple[bool, list[GPUDeviceSummary], float | None, float | None]:
    try:
        import torch
    except ImportError:
        return False, [], None, None
    try:
        cuda_available = bool(torch.cuda.is_available())
    except Exception:
        return False, [], None, None
    if not cuda_available:
        return False, [], None, None
    devices: list[GPUDeviceSummary] = []
    total_sum = 0.0
    free_sum = 0.0
    for index in range(int(torch.cuda.device_count())):
        props = torch.cuda.get_device_properties(index)
        total_bytes = int(getattr(props, "total_memory", 0) or 0)
        free_bytes: int | None = None
        try:
            free_bytes, _ = torch.cuda.mem_get_info(index)
        except Exception:
            free_bytes = None
        devices.append(
            GPUDeviceSummary(
                index=index,
                name=str(getattr(props, "name", f"cuda:{index}")),
                total_vram_gib=_bytes_to_gib(total_bytes),
                free_vram_gib=_bytes_to_gib(free_bytes),
            )
        )
        total_sum += total_bytes
        if free_bytes is not None:
            free_sum += float(free_bytes)
    aggregate_total = _bytes_to_gib(total_sum) if devices else None
    aggregate_free = _bytes_to_gib(free_sum) if devices and free_sum else None
    return True, devices, aggregate_total, aggregate_free


def _transformers_runtime_posture(resolved: ResolvedProviderSettings) -> str:
    device_map = str(resolved.options.get("device_map", "auto") or "auto").strip().lower()
    if device_map in {"cpu", "disk"}:
        return "cpu-or-disk-offload"
    if not _torch_cuda_available():
        return "cpu-only"
    return "gpu-capable"


def _load_transformers_processor(model_path: str, options: dict[str, str]) -> Any:
    cache_key = (model_path, _option_as_bool(options, "trust_remote_code", False))
    cached = _TRANSFORMERS_PROCESSOR_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        from transformers import AutoProcessor
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise ProviderRuntimeError(
            "provider `transformers-local` requires `transformers`. "
            "Install the local inference dependencies before using a local transformers profile."
        ) from exc
    try:
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=_option_as_bool(options, "trust_remote_code", False),
        )
    except Exception as exc:
        raise ProviderRuntimeError(
            f"Could not load tokenizer/processor assets for `transformers-local` model `{model_path}`: {exc}"
        ) from exc
    _TRANSFORMERS_PROCESSOR_CACHE[cache_key] = processor
    return processor


def inspect_transformers_local_runtime(settings: ProviderSettings | None) -> TransformersLocalInspection:
    resolved = resolve_provider_settings(settings)
    if resolved.provider_used != "transformers-local":
        raise ProviderRuntimeError("transformers-local runtime inspection requires a transformers-local profile.")
    model_path = resolved.model_used
    if not model_path:
        raise ProviderRuntimeError("provider `transformers-local` requires a model path or a selected local profile.")

    warnings = list(resolved.warnings)
    path_warning = model_path_warning(model_path)
    if path_warning is not None and path_warning not in warnings:
        warnings.append(path_warning)

    runtime_posture = _transformers_runtime_posture(resolved)
    cuda_available, gpu_devices, aggregate_total_vram_gib, aggregate_free_vram_gib = _inspect_cuda_devices()
    bitsandbytes_available = _transformers_supports_4bit()
    experimental_borderline_enabled = _env_flag_enabled(EXPERIMENTAL_Q4_ALLOW_BORDERLINE_ENV_VAR)
    experimental_offload_allowed = _env_flag_enabled(EXPERIMENTAL_ALLOW_OFFLOAD_ENV_VAR)
    experimental_templateless_enabled = _env_flag_enabled(EXPERIMENTAL_ALLOW_TEMPLATELESS_ENV_VAR)
    chat_template_present = False
    serialization_path = "unknown"

    selected_load_mode: str | None = None
    preflight_error: str | None = None

    if resolved.profile_used == DEFAULT_LOCAL_PROFILE:
        if runtime_posture != "gpu-capable":
            preflight_error = (
                "Local runtime preflight failed: profile `gemma4_local_26b` is GPU-only in practice and this host/runtime "
                f"resolved to `{runtime_posture}`. Gemma 4 26B A4B memory is approximately BF16 ~48 GB, 8-bit ~25 GB, "
                "Q4_0 ~15.6 GB, and extra headroom is required for KV cache and context. Use a proper GPU-capable host "
                "or a smaller profile."
            )
        else:
            min_free_bf16 = _option_as_float(resolved.options, "minimum_free_vram_gib_bf16", 52.0)
            min_free_int8 = _option_as_float(resolved.options, "minimum_free_vram_gib_int8", 28.0)
            free_vram = aggregate_free_vram_gib or 0.0
            if free_vram >= min_free_bf16:
                selected_load_mode = "bf16"
            elif free_vram >= min_free_int8 and _transformers_supports_int8():
                selected_load_mode = "int8"
            else:
                support_note = "8-bit backend support is not available in the current environment." if not _transformers_supports_int8() else ""
                preflight_error = (
                    "Local runtime preflight failed: profile `gemma4_local_26b` is GPU-only in practice and available "
                    f"VRAM is insufficient for a safe load (aggregate free VRAM ~{free_vram:.2f} GiB). Published Gemma 4 "
                    "26B A4B memory is approximately BF16 ~48 GB, 8-bit ~25 GB, Q4_0 ~15.6 GB, plus extra headroom for "
                    "KV cache and context. Use a larger GPU host, free more VRAM, or switch to a smaller profile. "
                    + support_note
                ).strip()
            if preflight_error is None and not chat_template_present:
                pass
    elif resolved.profile_used == EXPERIMENTAL_Q4_LOCAL_PROFILE:
        selected_load_mode = "4bit"
        if runtime_posture != "gpu-capable" or not cuda_available:
            preflight_error = (
                "Local runtime preflight failed: profile `gemma4_local_26b_q4_experimental` requires CUDA and does "
                f"not permit CPU-only execution. Runtime posture resolved to `{runtime_posture}`."
            )
        elif not gpu_devices:
            preflight_error = (
                "Local runtime preflight failed: profile `gemma4_local_26b_q4_experimental` did not find any visible "
                "CUDA devices."
            )
        elif not bitsandbytes_available:
            preflight_error = (
                "Local runtime preflight failed: profile `gemma4_local_26b_q4_experimental` requires bitsandbytes "
                "and transformers BitsAndBytesConfig support for experimental 4-bit loading."
            )
        else:
            comfortable_free_vram = _option_as_float(resolved.options, "minimum_free_vram_gib_q4_comfortable", 18.0)
            borderline_free_vram = _option_as_float(resolved.options, "minimum_free_vram_gib_q4_borderline", 14.5)
            free_vram = aggregate_free_vram_gib or 0.0
            warnings.append(
                "Experimental 4-bit Gemma 4 26B path is enabled for Gate 1 only. It may still fail, offload, or stall "
                "on borderline 16 GB-class GPU hosts."
            )
            if free_vram >= comfortable_free_vram:
                warnings.append(
                    f"Experimental 4-bit preflight sees aggregate free VRAM ~{free_vram:.2f} GiB, which meets the "
                    f"comfortable threshold of ~{comfortable_free_vram:.2f} GiB."
                )
            elif free_vram >= borderline_free_vram:
                if not experimental_borderline_enabled:
                    preflight_error = (
                        "Local runtime preflight failed: profile `gemma4_local_26b_q4_experimental` sees only "
                        f"borderline aggregate free VRAM (~{free_vram:.2f} GiB). Set "
                        f"{EXPERIMENTAL_Q4_ALLOW_BORDERLINE_ENV_VAR}=1 to explicitly allow this experimental 4-bit "
                        "attempt on a borderline GPU host."
                    )
                else:
                    warnings.append(
                        f"Experimental borderline Q4 mode is enabled via {EXPERIMENTAL_Q4_ALLOW_BORDERLINE_ENV_VAR}=1 "
                        f"with aggregate free VRAM ~{free_vram:.2f} GiB. The load may still fail or stall."
                    )
            else:
                preflight_error = (
                    "Local runtime preflight failed: profile `gemma4_local_26b_q4_experimental` sees aggregate free "
                    f"VRAM ~{free_vram:.2f} GiB, below the borderline experimental threshold of "
                    f"~{borderline_free_vram:.2f} GiB."
                )
            if preflight_error is None:
                if experimental_offload_allowed:
                    warnings.append(
                        f"Experimental offload is enabled via {EXPERIMENTAL_ALLOW_OFFLOAD_ENV_VAR}=1. Transformers may "
                        "still place weights on CPU or disk, which is slow and unstable."
                    )
                else:
                    warnings.append(
                        f"Experimental offload is disabled by default. If transformers places any weights on CPU or "
                        f"disk, runtime load will fail unless {EXPERIMENTAL_ALLOW_OFFLOAD_ENV_VAR}=1 is set."
                    )
    else:
        device_map = str(resolved.options.get("device_map", "cpu") or "cpu").strip().lower()
        selected_load_mode = f"{resolved.options.get('dtype', 'float32')}-{device_map}"

    if preflight_error is None:
        processor = _load_transformers_processor(model_path, resolved.options)
        chat_template_present = _has_usable_chat_template(processor)
        if chat_template_present:
            serialization_path = "processor_chat_template"
        elif resolved.missing_chat_template_policy == "gemma_gate1_text_fallback":
            serialization_path = "gemma_gate1_text_fallback"
        elif (
            resolved.profile_used == EXPERIMENTAL_Q4_LOCAL_PROFILE
            and experimental_templateless_enabled
        ):
            serialization_path = "experimental_gate1_text_fallback"
        else:
            serialization_path = "chat_template_required"
        if (
            resolved.profile_used in {DEFAULT_LOCAL_PROFILE, EXPERIMENTAL_Q4_LOCAL_PROFILE}
            and not chat_template_present
            and not (
                resolved.profile_used == EXPERIMENTAL_Q4_LOCAL_PROFILE
                and experimental_templateless_enabled
            )
        ):
            preflight_error = str(
                _missing_chat_template_error(
                    resolved=resolved,
                    preset=resolved.stage_presets[STAGE_GATE1_STRUCTURED],
                    model_path=model_path,
                    multimodal_required=False,
                )
            )
        elif resolved.profile_used == EXPERIMENTAL_Q4_LOCAL_PROFILE and not chat_template_present:
            warnings.append(
                f"Experimental template-less Gate 1 fallback is enabled via "
                f"{EXPERIMENTAL_ALLOW_TEMPLATELESS_ENV_VAR}=1. Non-Gate-1 and multimodal requests still fail closed."
            )
    else:
        serialization_path = "not-checked-preflight-failed"

    return TransformersLocalInspection(
        profile=resolved.profile_used,
        model_path=model_path,
        runtime_posture=runtime_posture,
        cuda_available=cuda_available,
        gpu_count=len(gpu_devices),
        aggregate_total_vram_gib=aggregate_total_vram_gib,
        aggregate_free_vram_gib=aggregate_free_vram_gib,
        gpu_devices=gpu_devices,
        bitsandbytes_available=bitsandbytes_available,
        experimental_borderline_enabled=experimental_borderline_enabled,
        experimental_offload_allowed=experimental_offload_allowed,
        experimental_templateless_enabled=experimental_templateless_enabled,
        chat_template_present=chat_template_present,
        serialization_path=serialization_path,
        selected_load_mode=selected_load_mode,
        preflight_passed=preflight_error is None,
        preflight_error=preflight_error,
        warnings=warnings,
    )


def _preflight_transformers_local_runtime(resolved: ResolvedProviderSettings) -> TransformersLocalInspection:
    inspection = inspect_transformers_local_runtime(
        ProviderSettings(
            provider=resolved.provider_used,
            model=resolved.model_used,
            endpoint=resolved.endpoint_used,
            profile=resolved.profile_used,
            options=dict(resolved.options),
        )
    )
    if not inspection.preflight_passed:
        raise ProviderRuntimeError(str(inspection.preflight_error))
    return inspection


def _extract_packet_keys(messages: list[dict[str, str]]) -> list[str]:
    for message in reversed(messages):
        content = message.get("content") or ""
        brace_index = content.find("{")
        if brace_index < 0:
            continue
        payload_text = content[brace_index:]
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return sorted(str(key) for key in payload.keys())
    return []


class ProviderAdapter:
    provider_name = "local-none"
    transport_name = "deterministic-local"

    def run_brief_intake(self, brief_payload: dict[str, Any], settings: ProviderSettings) -> LLMBackendProof:
        resolved = resolve_provider_settings(settings)
        preset = resolved.stage_presets.get(STAGE_GATE1_STRUCTURED)
        if preset is None:
            raise ProviderRuntimeError(
                f"provider {self.provider_name!r} requires a stage preset for {STAGE_GATE1_STRUCTURED!r}."
            )
        packet = build_stage_packet(STAGE_GATE1_STRUCTURED, brief_payload=brief_payload)
        traces: list[LLMRequestTrace] = []
        warnings = list(resolved.warnings)
        if resolved.provider_used == "transformers-local":
            path_warning = model_path_warning(resolved.model_used)
            if path_warning is not None and path_warning not in warnings:
                warnings.append(path_warning)

        messages = [
            {"role": "system", "content": _build_system_prompt(preset)},
            {"role": "user", "content": _build_initial_user_prompt(packet)},
        ]
        intake: BriefIntakeSummary | None = None
        for attempt in range(preset.max_repair_rounds + 1):
            raw_content, trace = self._request_stage(
                target="brief-intake",
                messages=messages,
                resolved=resolved,
                preset=preset,
                repair_attempt=attempt,
            )
            traces.append(trace)
            try:
                intake = _validate_brief_output(
                    raw_content,
                    provider=self.provider_name,
                    transport=trace.transport,
                    target="brief-intake",
                )
                break
            except StructuredOutputError as exc:
                if attempt >= preset.max_repair_rounds:
                    raise
                last_raw = raw_content if isinstance(raw_content, str) else json.dumps(raw_content, ensure_ascii=False)
                messages = [
                    {"role": "system", "content": _build_system_prompt(preset)},
                    {"role": "user", "content": _build_repair_user_prompt(last_raw, str(exc))},
                ]
        if intake is None:  # pragma: no cover - defensive
            raise ProviderRuntimeError("brief intake completed without a validated artifact.")
        return LLMBackendProof(
            provider_requested=resolved.provider_requested,
            provider_used=self.provider_name,
            model_requested=resolved.model_requested,
            model_used=resolved.model_used,
            endpoint_requested=resolved.endpoint_requested,
            endpoint_used=resolved.endpoint_used,
            profile_requested=resolved.profile_requested,
            profile_used=resolved.profile_used,
            transport_used=traces[-1].transport,
            strict_structured_output=True,
            fallback_occurred=len(traces) > 1,
            llm_request_count=len(traces),
            llm_request_targets=["brief-intake"],
            request_traces=traces,
            stage_preset=preset.stage_name,
            packet_kind=preset.packet_kind,
            packet_keys=sorted(packet.keys()),
            repair_attempt_count=max(0, len(traces) - 1),
            warnings=warnings,
            brief_intake=intake,
        )

    def _request_stage(
        self,
        *,
        target: str,
        messages: list[dict[str, str]],
        resolved: ResolvedProviderSettings,
        preset: StagePreset,
        repair_attempt: int,
    ) -> tuple[str, LLMRequestTrace]:
        raise NotImplementedError


class LocalNoneAdapter(ProviderAdapter):
    provider_name = "local-none"
    transport_name = "deterministic-local"

    def run_brief_intake(self, brief_payload: dict[str, Any], settings: ProviderSettings) -> LLMBackendProof:
        resolved = resolve_provider_settings(settings)
        intake = build_local_brief_intake(brief_payload)
        return LLMBackendProof(
            provider_requested=resolved.provider_requested,
            provider_used=self.provider_name,
            model_requested=resolved.model_requested,
            model_used=resolved.model_used,
            endpoint_requested=resolved.endpoint_requested,
            endpoint_used=resolved.endpoint_used,
            profile_requested=resolved.profile_requested,
            profile_used=resolved.profile_used,
            transport_used=self.transport_name,
            strict_structured_output=True,
            fallback_occurred=False,
            llm_request_count=0,
            llm_request_targets=[],
            request_traces=[],
            warnings=list(resolved.warnings),
            brief_intake=intake,
        )


class OllamaAdapter(ProviderAdapter):
    provider_name = "ollama"
    transport_name = "native-ollama-chat"

    def _request_stage(
        self,
        *,
        target: str,
        messages: list[dict[str, str]],
        resolved: ResolvedProviderSettings,
        preset: StagePreset,
        repair_attempt: int,
    ) -> tuple[str, LLMRequestTrace]:
        transport = (resolved.options.get("transport") or "native").strip().lower()
        if transport in {"native", "native-ollama-chat"}:
            return self._request_native(
                target=target,
                messages=messages,
                resolved=resolved,
                preset=preset,
                repair_attempt=repair_attempt,
            )
        if transport in {"openai-compat", "openai-compatible"}:
            return self._request_openai_compat(
                target=target,
                messages=messages,
                resolved=resolved,
                preset=preset,
                repair_attempt=repair_attempt,
            )
        raise ProviderRuntimeError(f"provider `ollama` does not support transport {transport!r}.")

    def _request_native(
        self,
        *,
        target: str,
        messages: list[dict[str, str]],
        resolved: ResolvedProviderSettings,
        preset: StagePreset,
        repair_attempt: int,
    ) -> tuple[str, LLMRequestTrace]:
        model = _resolve_ollama_model(resolved)
        endpoint = _resolve_endpoint(resolved, provider="ollama")
        temperature = _option_as_float(resolved.options, "temperature", preset.temperature)
        options = _transport_options(resolved) | {"temperature": temperature}
        status, response_payload = _json_post(
            url=f"{endpoint}/api/chat",
            body={
                "model": model,
                "messages": messages,
                "stream": False,
                "format": BriefIntakeSummary.model_json_schema(),
                "options": options,
            },
            headers={"Content-Type": "application/json"},
            timeout_seconds=_timeout_seconds_from_options(resolved.options),
        )
        raw_content = ((response_payload.get("message") or {}).get("content")) if isinstance(response_payload.get("message"), dict) else None
        trace = LLMRequestTrace(
            target=target,
            provider=self.provider_name,
            transport=self.transport_name,
            model=model,
            endpoint=endpoint,
            request_path="/api/chat",
            request_url=f"{endpoint}/api/chat",
            strict_structured_output=True,
            response_status=status,
            profile=resolved.profile_used,
            stage_preset=preset.stage_name,
            packet_kind=preset.packet_kind,
            packet_keys=_extract_packet_keys(messages),
            temperature=temperature,
            repair_attempt=repair_attempt,
        )
        return str(raw_content or ""), trace

    def _request_openai_compat(
        self,
        *,
        target: str,
        messages: list[dict[str, str]],
        resolved: ResolvedProviderSettings,
        preset: StagePreset,
        repair_attempt: int,
    ) -> tuple[str, LLMRequestTrace]:
        model = _resolve_ollama_model(resolved)
        endpoint = _resolve_endpoint(resolved, provider="ollama")
        temperature = _option_as_float(resolved.options, "temperature", preset.temperature)
        request_url, request_path = _openai_chat_completions_url(endpoint)
        status, response_payload = _json_post(
            url=request_url,
            body={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "brief_intake_summary",
                        "strict": True,
                        "schema": BriefIntakeSummary.model_json_schema(),
                    },
                },
            },
            headers={"Content-Type": "application/json"},
            timeout_seconds=_timeout_seconds_from_options(resolved.options),
        )
        choices = response_payload.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices else None
        raw_content = message.get("content") if isinstance(message, dict) else None
        trace = LLMRequestTrace(
            target=target,
            provider=self.provider_name,
            transport="openai-compatible-chat",
            model=model,
            endpoint=endpoint,
            request_path=request_path,
            request_url=request_url,
            strict_structured_output=True,
            response_status=status,
            profile=resolved.profile_used,
            stage_preset=preset.stage_name,
            packet_kind=preset.packet_kind,
            packet_keys=_extract_packet_keys(messages),
            temperature=temperature,
            repair_attempt=repair_attempt,
        )
        return str(raw_content or ""), trace


class OpenAIAdapter(ProviderAdapter):
    provider_name = "openai"
    transport_name = "openai-chat-completions"

    def _request_stage(
        self,
        *,
        target: str,
        messages: list[dict[str, str]],
        resolved: ResolvedProviderSettings,
        preset: StagePreset,
        repair_attempt: int,
    ) -> tuple[str, LLMRequestTrace]:
        model = _resolve_openai_model(resolved)
        endpoint = _resolve_endpoint(resolved, provider="openai")
        api_key = resolved.options.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key and not resolved.api_key_optional:
            raise ProviderRuntimeError("provider `openai` requires `api_key` or OPENAI_API_KEY.")
        request_url, request_path = _openai_chat_completions_url(endpoint)
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        temperature = _option_as_float(resolved.options, "temperature", preset.temperature)
        status, response_payload = _json_post(
            url=request_url,
            body={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "brief_intake_summary",
                        "strict": True,
                        "schema": BriefIntakeSummary.model_json_schema(),
                    },
                },
            },
            headers=headers,
            timeout_seconds=_timeout_seconds_from_options(resolved.options),
        )
        choices = response_payload.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices else None
        raw_content = message.get("content") if isinstance(message, dict) else None
        transport_name = "openai-compatible-chat" if resolved.profile_used == REMOTE_GEMMA4_PROFILE else self.transport_name
        trace = LLMRequestTrace(
            target=target,
            provider=self.provider_name,
            transport=transport_name,
            model=model,
            endpoint=endpoint,
            request_path=request_path,
            request_url=request_url,
            strict_structured_output=True,
            response_status=status,
            profile=resolved.profile_used,
            stage_preset=preset.stage_name,
            packet_kind=preset.packet_kind,
            packet_keys=_extract_packet_keys(messages),
            temperature=temperature,
            repair_attempt=repair_attempt,
        )
        return str(raw_content or ""), trace


class TransformersLocalAdapter(ProviderAdapter):
    provider_name = "transformers-local"
    transport_name = "local-transformers-chat"

    def _request_stage(
        self,
        *,
        target: str,
        messages: list[dict[str, str]],
        resolved: ResolvedProviderSettings,
        preset: StagePreset,
        repair_attempt: int,
    ) -> tuple[str, LLMRequestTrace]:
        model_path = resolved.model_used
        if not model_path:
            raise ProviderRuntimeError("provider `transformers-local` requires a model path or a selected local profile.")
        temperature = _option_as_float(resolved.options, "temperature", preset.temperature)
        raw_content = self._generate_text(
            messages=messages,
            resolved=resolved,
            preset=preset,
            repair_attempt=repair_attempt,
        )
        trace = LLMRequestTrace(
            target=target,
            provider=self.provider_name,
            transport=self.transport_name,
            model=model_path,
            request_path=model_path,
            strict_structured_output=True,
            profile=resolved.profile_used,
            stage_preset=preset.stage_name,
            packet_kind=preset.packet_kind,
            packet_keys=_extract_packet_keys(messages),
            temperature=temperature,
            repair_attempt=repair_attempt,
        )
        return raw_content, trace

    def _generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        resolved: ResolvedProviderSettings,
        preset: StagePreset,
        repair_attempt: int,
    ) -> str:
        inspection = _preflight_transformers_local_runtime(resolved)
        torch_mod, processor, model = self._load_runtime(
            resolved.model_used or "",
            resolved.options,
            profile_name=resolved.profile_used,
            load_mode=inspection.selected_load_mode,
        )
        chat_prompt = _serialize_transformers_chat_prompt(
            processor=processor,
            messages=messages,
            resolved=resolved,
            preset=preset,
        )
        max_input_chars = _option_as_int(resolved.options, "max_input_chars", 24000)
        if len(chat_prompt) > max_input_chars:
            raise ProviderRuntimeError(
                f"local prompt length {len(chat_prompt)} exceeded conservative budget {max_input_chars} characters for {preset.stage_name}."
            )
        inputs = processor(text=chat_prompt, return_tensors="pt")
        if hasattr(inputs, "to"):
            inputs = inputs.to(model.device)
        input_ids = inputs["input_ids"]
        input_len = int(input_ids.shape[-1])
        do_sample = _option_as_bool(resolved.options, "do_sample", preset.temperature > 0)
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": _option_as_int(
                resolved.options,
                "repair_max_new_tokens" if repair_attempt else "max_new_tokens",
                preset.max_new_tokens,
            ),
            "do_sample": do_sample,
        }
        generation_config = copy.deepcopy(getattr(model, "generation_config", None))
        if generation_config is not None and not do_sample:
            for field_name in ("top_p", "top_k", "temperature"):
                if hasattr(generation_config, field_name):
                    setattr(generation_config, field_name, None)
            generation_kwargs["generation_config"] = generation_config
        if do_sample:
            generation_kwargs["temperature"] = _option_as_float(resolved.options, "temperature", preset.temperature)
            generation_kwargs["top_p"] = _option_as_float(resolved.options, "top_p", 0.9)
        with torch_mod.inference_mode():
            outputs = model.generate(**inputs, **generation_kwargs)
        generated = outputs[0][input_len:]
        return processor.decode(generated, skip_special_tokens=True).strip()

    def _load_runtime(
        self,
        model_path: str,
        options: dict[str, str],
        *,
        profile_name: str | None = None,
        load_mode: str | None = None,
    ) -> tuple[Any, Any, Any]:
        effective_load_mode = load_mode or options.get("preferred_load_mode", "default")
        cache_key = (
            model_path,
            effective_load_mode,
            options.get("dtype", "bfloat16"),
            options.get("device_map", "auto"),
        )
        cached = _TRANSFORMERS_RUNTIME_CACHE.get(cache_key)
        if cached is not None:
            return cached
        model_dir = Path(model_path)
        if not model_dir.exists() and not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", model_path):
            raise ProviderRuntimeError(f"local model path does not exist: {model_path}")
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - environment-specific
            raise ProviderRuntimeError("provider `transformers-local` requires `torch`.") from exc
        try:
            from transformers import AutoModelForCausalLM
        except ImportError as exc:  # pragma: no cover - environment-specific
            raise ProviderRuntimeError(
                "provider `transformers-local` requires `transformers`. "
                "Install the local inference dependencies before using a local transformers profile."
            ) from exc
        processor = _load_transformers_processor(model_path, options)
        load_kwargs: dict[str, Any] = {
            "device_map": options.get("device_map", "auto"),
            "trust_remote_code": _option_as_bool(options, "trust_remote_code", False),
        }
        if effective_load_mode == "int8":
            if not _transformers_supports_int8():
                raise ProviderRuntimeError(
                    "profile `gemma4_local_26b` selected 8-bit load mode, but the installed backend does not support it."
                )
            from transformers import BitsAndBytesConfig

            load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        elif effective_load_mode == "4bit":
            if not _transformers_supports_4bit():
                raise ProviderRuntimeError(
                    "profile `gemma4_local_26b_q4_experimental` selected 4-bit load mode, but the installed backend "
                    "does not support BitsAndBytesConfig 4-bit loading."
                )
            from transformers import BitsAndBytesConfig

            compute_dtype = _bnb_4bit_compute_dtype(torch)
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=compute_dtype,
            )
            load_kwargs["dtype"] = compute_dtype
        else:
            dtype_name = options.get("dtype", "bfloat16")
            dtype = getattr(torch, dtype_name, None)
            if dtype is None:
                raise ProviderRuntimeError(f"unsupported torch dtype {dtype_name!r} for `transformers-local`.")
            load_kwargs["dtype"] = dtype
        model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
        non_gpu_targets = _non_cuda_device_targets(model)
        if profile_name == DEFAULT_LOCAL_PROFILE and non_gpu_targets:
            raise ProviderRuntimeError(
                "Local runtime preflight expected GPU-only placement for profile `gemma4_local_26b`, "
                f"but transformers resolved weights to non-GPU targets: {sorted(non_gpu_targets)}. "
                "Free more VRAM, use a larger GPU host, or switch profiles."
            )
        if profile_name == EXPERIMENTAL_Q4_LOCAL_PROFILE and non_gpu_targets and not _env_flag_enabled(
            EXPERIMENTAL_ALLOW_OFFLOAD_ENV_VAR
        ):
            raise ProviderRuntimeError(
                "Experimental 4-bit load for profile `gemma4_local_26b_q4_experimental` resolved weights to non-GPU "
                f"targets: {sorted(non_gpu_targets)}. Explicit offload opt-in is required; set "
                f"{EXPERIMENTAL_ALLOW_OFFLOAD_ENV_VAR}=1 to allow this experimental posture."
            )
        runtime = (torch, processor, model)
        _TRANSFORMERS_RUNTIME_CACHE[cache_key] = runtime
        return runtime


def create_provider_adapter(settings: ProviderSettings | None) -> ProviderAdapter:
    try:
        resolved = resolve_provider_settings(settings)
    except ValueError as exc:
        raise ProviderRuntimeError(str(exc)) from exc
    provider = resolved.provider_used.strip().lower() or "local-none"
    if provider == "local-none":
        return LocalNoneAdapter()
    if provider == "ollama":
        return OllamaAdapter()
    if provider == "openai":
        return OpenAIAdapter()
    if provider == "transformers-local":
        return TransformersLocalAdapter()
    raise ProviderRuntimeError(f"unknown provider {provider!r}")


def run_brief_intake(brief_payload: dict[str, Any], settings: ProviderSettings | None = None) -> LLMBackendProof:
    normalized = _normalize_provider_settings(settings)
    adapter = create_provider_adapter(normalized)
    return adapter.run_brief_intake(brief_payload, normalized)


def write_llm_backend_proof(proof: LLMBackendProof, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(proof.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
