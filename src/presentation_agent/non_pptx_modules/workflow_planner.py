"""Deterministic Gate 1 workflow planning from a brief file."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator, model_validator

from .generation_mode_router import build_canonical_generation_profile
from .provider_runtime import LLMBackendProof, run_brief_intake, write_llm_backend_proof
from .runtime_config import ProviderSettings
from .workflow_contract_matrix import resolve_requested_workflow_option
from ..compat.legacy_non_pptx import (
    BriefMaterialType,
    CountRange,
    ContractModel,
    DeckMode,
    DeliveryMode,
    GateStatus,
    PresentationType,
    PresentationTypeDiagnosis,
    PresentationArchetype,
    PresentationBrandMode,
    PresentationBrief,
    PresentationEvidenceDensity,
    PresentationVisualDensity,
    ProjectMaterial,
    ProjectSnapshot,
    ScaleMode,
    SlideContentBudget,
    SlideFunction,
    SlideFunctionOutline,
    SlideFunctionPlanItem,
    StageStatus,
    WorkflowPhase,
    WorkflowOption,
    WorkflowPlan,
)
from ..compat.legacy_non_pptx import WorkflowGate


PRESENTATION_DISPLAY_NAMES: dict[PresentationType, str] = {
    PresentationType.EXPLAINER: "Explainer",
    PresentationType.PERSUASION: "Persuasion",
    PresentationType.REPORT: "Report",
    PresentationType.DECISION: "Decision",
    PresentationType.TRAINING: "Training",
    PresentationType.DEMO: "Demo",
    PresentationType.PITCH: "Pitch",
    PresentationType.KEYNOTE: "Keynote",
    PresentationType.WORKSHOP: "Workshop",
}

PRESENTATION_KEYWORDS: dict[PresentationType, tuple[str, ...]] = {
    PresentationType.EXPLAINER: ("explain", "overview", "background", "context", "understand", "why"),
    PresentationType.PERSUASION: ("persuade", "convince", "buy-in", "support", "approve", "pitch", "recommend"),
    PresentationType.REPORT: ("report", "update", "status", "results", "performance", "review", "readout"),
    PresentationType.DECISION: ("decision", "decide", "choose", "approve", "go/no-go", "tradeoff", "prioritize"),
    PresentationType.TRAINING: ("train", "enable", "teach", "onboard", "curriculum", "exercise", "learning"),
    PresentationType.DEMO: ("demo", "walkthrough", "showcase", "tour", "simulation", "click-through"),
    PresentationType.PITCH: ("pitch", "investor", "sales", "prospect", "customer", "pipeline", "fundraise", "commercial"),
    PresentationType.KEYNOTE: ("vision", "keynote", "future", "north star", "mission", "transformation", "inspire"),
    PresentationType.WORKSHOP: ("workshop", "facilitate", "facilitation", "working session", "exercise", "breakout", "co-design"),
}

AUDIENCE_KEYWORDS: dict[PresentationType, tuple[str, ...]] = {
    PresentationType.PITCH: ("investor", "customer", "buyer", "prospect", "sales", "account", "partner"),
    PresentationType.KEYNOTE: ("all hands", "summit", "leadership", "organization", "company-wide"),
    PresentationType.WORKSHOP: ("working group", "facilitator", "cross-functional", "task force"),
}

LECTURE_KEYWORDS = (
    "lecture",
    "curriculum",
    "course",
    "class",
    "graduate",
    "students",
    "textbook",
    "syllabus",
    "seminar",
    "\uac15\uc758",
    "\ub300\ud559\uc6d0",
    "\ub300\ud559\uc6d0\uc0dd",
    "\uad50\uc7ac",
)


class WorkflowBriefInput(ContractModel):
    topic: str
    deck_title: str | None = None
    audience: list[str] = Field(default_factory=list)
    purpose: str
    delivery_mode: DeliveryMode
    expected_duration_minutes: int | None = None
    expected_scale_hint: str | None = None
    current_materials: list[ProjectMaterial] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    approval_path: list[str] = Field(default_factory=list)
    requested_workflow_option: str | None = None
    facts: list[str] = Field(default_factory=list)
    initial_assumptions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    source_prompt: str | None = None
    lightweight_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "audience",
        "constraints",
        "notes",
        "approval_path",
        "facts",
        "initial_assumptions",
        "assumptions",
        "recommendations",
        mode="before",
    )
    @classmethod
    def _coerce_string_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("expected_duration_minutes")
    @classmethod
    def _validate_duration(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("expected_duration_minutes must be positive when provided")
        return value

    @field_validator("requested_workflow_option")
    @classmethod
    def _normalize_requested_workflow_option(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("source_prompt")
    @classmethod
    def _normalize_source_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("current_materials", mode="before")
    @classmethod
    def _coerce_materials(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            items: list[object] = []
            for entry in value:
                if isinstance(entry, str):
                    items.append({"label": entry, "material_type": "other"})
                else:
                    items.append(entry)
            return items
        raise TypeError("current_materials must be a list")

    @field_validator("lightweight_context", mode="before")
    @classmethod
    def _coerce_lightweight_context(cls, value: object) -> object:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("lightweight_context must be a mapping when provided")
        return value

    @model_validator(mode="after")
    def _validate_scale_input(self) -> "WorkflowBriefInput":
        if self.expected_duration_minutes is None and not self.expected_scale_hint:
            raise ValueError("provide expected_duration_minutes or expected_scale_hint")
        return self


def load_workflow_brief(path: str | Path) -> WorkflowBriefInput:
    brief_path = Path(path)
    payload = _load_brief_payload(brief_path)
    if isinstance(payload, dict):
        if {"topic", "purpose", "delivery_mode"} <= set(payload):
            return WorkflowBriefInput.model_validate(payload)
        prompt = str(payload.get("prompt", "")).strip()
        if prompt:
            context = payload.get("context")
            if context is None:
                context = {key: value for key, value in payload.items() if key != "prompt"}
            if not isinstance(context, dict):
                raise ValueError("prompt-only workflow briefs must use a mapping for `context` when provided")
            return infer_workflow_brief_from_prompt(prompt, context)
    if isinstance(payload, str):
        prompt = payload.strip()
        if prompt:
            return infer_workflow_brief_from_prompt(prompt)
    raise ValueError(f"workflow brief must contain a structured brief object or a prompt payload: {brief_path}")


def _load_brief_payload(path: Path) -> dict[str, Any] | str:
    text = path.read_text(encoding="utf-8").strip()
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
        return text if payload is None else payload
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return text


def _context_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = re.split(r",|\band\b", value)
        return _unique([candidate.strip(" .") for candidate in candidates if candidate.strip(" .")])
    if isinstance(value, list):
        return _unique([str(item).strip() for item in value if str(item).strip()])
    return []


def _context_text(context: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in context.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            parts.extend(f"{key} {item}" for key, item in value.items())
    return " ".join(parts)


def _contains_any_token(text: str, tokens: tuple[str, ...]) -> bool:
    for token in tokens:
        if re.search(rf"\b{re.escape(token)}\b", text):
            return True
    return False


def _coerce_count_range(value: object) -> CountRange | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, int):
            return CountRange(start=value, end=value)
        if isinstance(value, str):
            return CountRange.from_value(value)
        if isinstance(value, dict):
            return CountRange.from_value(value)
    except Exception:
        return None
    return None


def _infer_prompt_audience(prompt: str, context: dict[str, Any]) -> list[str]:
    context_audience = _context_string_list(context.get("audience"))
    if context_audience:
        return context_audience
    prompt_match = re.search(r"\bfor\s+([^.;]+)", prompt, flags=re.IGNORECASE)
    if prompt_match:
        audience = _context_string_list(prompt_match.group(1))
        if audience:
            return audience
    lowered = f"{prompt} {_context_text(context)}".lower()
    inferred: list[str] = []
    if any(token in lowered for token in ("board", "leadership", "executive", "ceo", "cfo", "coo")):
        inferred.append("Leadership")
    if any(token in lowered for token in ("investor", "fundraise", "series a", "buyer", "customer", "prospect")):
        inferred.append("External stakeholders")
    if any(token in lowered for token in ("engineer", "developer", "technical", "platform", "architecture")):
        inferred.append("Technical team")
    if any(token in lowered for token in ("student", "learner", "onboarding", "training")):
        inferred.append("Learners")
    return inferred or ["General business audience"]


def _infer_prompt_archetype(prompt: str, context: dict[str, Any]) -> PresentationArchetype:
    override = str(context.get("archetype", "")).strip().lower()
    if override:
        try:
            return PresentationArchetype(override)
        except ValueError:
            pass
    lowered = f"{prompt} {_context_text(context)}".lower()
    if _contains_any_token(lowered, ("investor", "fundraise", "raise", "pitch")):
        return PresentationArchetype.PITCH
    if _contains_any_token(lowered, ("decision", "approve", "approval", "recommend")) or "go/no-go" in lowered or "go no go" in lowered:
        return PresentationArchetype.DECISION
    if _contains_any_token(lowered, ("report", "readout", "update", "status")):
        return PresentationArchetype.REPORT
    if _contains_any_token(lowered, ("train", "training", "teach", "onboard")):
        return PresentationArchetype.TRAINING
    if _contains_any_token(lowered, ("architecture", "system", "platform", "topology")):
        return PresentationArchetype.ARCHITECTURE
    if _contains_any_token(lowered, ("timeline", "roadmap", "milestone", "phases")):
        return PresentationArchetype.TIMELINE
    if _contains_any_token(lowered, ("process", "workflow", "playbook")) or "operating model" in lowered:
        return PresentationArchetype.PROCESS
    return PresentationArchetype.EXPLAINER


def _infer_prompt_deck_length(
    prompt: str,
    context: dict[str, Any],
    archetype: PresentationArchetype,
) -> CountRange:
    for key in ("target_deck_length", "deck_length", "slide_count"):
        contextual = _coerce_count_range(context.get(key))
        if contextual is not None:
            return contextual
    lowered = prompt.lower()
    range_match = re.search(r"(\d+)\s*(?:to|-)\s*(\d+)\s*slides?", lowered)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        return CountRange(start=min(start, end), end=max(start, end))
    exact_match = re.search(r"(\d+)\s*[- ]?slides?", lowered)
    if exact_match:
        count = int(exact_match.group(1))
        return CountRange(start=count, end=count)
    capped_match = re.search(r"(?:under|less than|no more than|max(?:imum)?)\s*(\d+)\s*slides?", lowered)
    if capped_match:
        count = int(capped_match.group(1))
        return CountRange(start=max(4, count - 2), end=count)
    if archetype in {PresentationArchetype.DECISION, PresentationArchetype.PITCH}:
        return CountRange(start=5, end=8)
    if archetype in {PresentationArchetype.TRAINING, PresentationArchetype.ARCHITECTURE, PresentationArchetype.PROCESS}:
        return CountRange(start=7, end=10)
    return CountRange(start=6, end=8)


def _infer_prompt_topic(prompt: str, context: dict[str, Any]) -> str:
    contextual = str(context.get("topic", "") or context.get("subject", "")).strip()
    if contextual:
        return contextual.rstrip(".")
    for pattern in (
        r"\bon\s+(.+?)(?:\s+for\s+|[.;]|$)",
        r"\babout\s+(.+?)(?:\s+for\s+|[.;]|$)",
    ):
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" .")
    cleaned = re.sub(r"^(create|build|make|prepare|draft|generate)\s+", "", prompt.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"^\d+\s*[- ]?slides?\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(an?|the)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" .") or "Presentation"


def _display_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" .")
    if not cleaned:
        return "Presentation"
    return cleaned.title() if cleaned.islower() else cleaned


def _infer_prompt_delivery_mode(
    prompt: str,
    context: dict[str, Any],
    archetype: PresentationArchetype,
) -> DeliveryMode:
    contextual = str(context.get("delivery_mode", "")).strip().lower()
    if contextual:
        try:
            return DeliveryMode(contextual)
        except ValueError:
            pass
    lowered = f"{prompt} {_context_text(context)}".lower()
    if _contains_any_token(lowered, ("workshop", "facilitate")) or "working session" in lowered:
        return DeliveryMode.WORKSHOP
    if _contains_any_token(lowered, ("demo", "walkthrough", "tour")):
        return DeliveryMode.DEMO_SESSION
    if _contains_any_token(lowered, ("train", "training", "teach", "onboard")):
        return DeliveryMode.TRAINING_SESSION
    if archetype == PresentationArchetype.DECISION:
        return DeliveryMode.DECISION_MEETING
    if archetype == PresentationArchetype.REPORT:
        return DeliveryMode.ASYNC_READOUT
    return DeliveryMode.LIVE_PRESENTATION


def _infer_prompt_goal(topic: str, archetype: PresentationArchetype) -> str:
    templates = {
        PresentationArchetype.DECISION: f"Support a clear decision on {topic} and make the required next step explicit.",
        PresentationArchetype.REPORT: f"Summarize the current status of {topic} and highlight the implication the audience should retain.",
        PresentationArchetype.PITCH: f"Make the case for {topic} and close on the primary ask.",
        PresentationArchetype.TRAINING: f"Teach {topic} in a way the audience can apply immediately.",
        PresentationArchetype.ARCHITECTURE: f"Explain how {topic} is structured and why the design matters.",
        PresentationArchetype.PROCESS: f"Show how {topic} works step by step and what the audience should do next.",
        PresentationArchetype.TIMELINE: f"Explain the sequencing and milestones for {topic}.",
    }
    return templates.get(archetype, f"Explain {topic} clearly and land the main takeaway.")


def _infer_prompt_scale_hint(target_deck_length: CountRange) -> str:
    if target_deck_length.end <= 8:
        return "compact"
    if target_deck_length.end <= 14:
        return "standard"
    if target_deck_length.end <= 20:
        return "extended"
    if target_deck_length.end <= 40:
        return "large"
    return "mega"


def infer_workflow_brief_from_prompt(prompt: str, context: dict[str, Any] | None = None) -> WorkflowBriefInput:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise ValueError("prompt-only workflow briefs must include non-empty prompt text")
    prompt_context = dict(context or {})
    archetype = _infer_prompt_archetype(cleaned_prompt, prompt_context)
    target_deck_length = _infer_prompt_deck_length(cleaned_prompt, prompt_context, archetype)
    topic = _infer_prompt_topic(cleaned_prompt, prompt_context)
    deck_title = str(prompt_context.get("deck_title", "")).strip() or _display_title(topic)
    audience = _infer_prompt_audience(cleaned_prompt, prompt_context)
    delivery_mode = _infer_prompt_delivery_mode(cleaned_prompt, prompt_context, archetype)
    expected_duration_minutes = int(prompt_context.get("expected_duration_minutes") or max(8, target_deck_length.end * 2))
    current_materials = prompt_context.get("current_materials") or prompt_context.get("materials") or []
    brand_mode = str(prompt_context.get("brand_mode", "")).strip()
    prompt_notes = [
        "Prompt-only workflow brief inferred before layout planning.",
    ]
    if brand_mode:
        prompt_notes.append(f"Brand mode hint: {brand_mode}.")
    return WorkflowBriefInput.model_validate(
        {
            "topic": topic,
            "deck_title": deck_title,
            "audience": audience,
            "purpose": _infer_prompt_goal(topic, archetype),
            "delivery_mode": delivery_mode,
            "expected_duration_minutes": expected_duration_minutes,
            "expected_scale_hint": _infer_prompt_scale_hint(target_deck_length),
            "current_materials": current_materials,
            "constraints": _context_string_list(prompt_context.get("constraints"))
            or [f"Keep the main story within {target_deck_length.start}-{target_deck_length.end} slides."],
            "notes": _context_string_list(prompt_context.get("notes")) + prompt_notes,
            "approval_path": _context_string_list(prompt_context.get("approval_path")),
            "requested_workflow_option": prompt_context.get("requested_workflow_option"),
            "facts": _context_string_list(prompt_context.get("facts")),
            "assumptions": _context_string_list(prompt_context.get("assumptions")),
            "recommendations": _context_string_list(prompt_context.get("recommendations")),
            "source_prompt": cleaned_prompt,
            "lightweight_context": prompt_context,
        }
    )


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "workflow-plan"


def _title_case(value: str) -> str:
    return value.replace("-", " ").title()


def _presentation_label(presentation_type: PresentationType) -> str:
    return PRESENTATION_DISPLAY_NAMES.get(presentation_type, _title_case(presentation_type.value))


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _is_continuity_scale(scale_mode: ScaleMode) -> bool:
    return scale_mode in {ScaleMode.EXTENDED, ScaleMode.LARGE_DECK, ScaleMode.MEGA_DECK}


def _all_text(brief: WorkflowBriefInput) -> str:
    material_text = " ".join(
        " ".join(filter(None, [material.label, material.path or "", material.notes or "", material.material_type.value]))
        for material in brief.current_materials
    )
    audience_text = " ".join(brief.audience)
    return " ".join(
        [
            brief.topic,
            brief.purpose,
            audience_text,
            " ".join(brief.constraints),
            " ".join(brief.notes),
            material_text,
            " ".join(brief.approval_path),
            " ".join(brief.facts),
            " ".join(brief.initial_assumptions),
            " ".join(brief.assumptions),
            " ".join(brief.recommendations),
        ]
    ).lower()


def _has_document_materials(brief: WorkflowBriefInput) -> bool:
    return any(material.material_type == BriefMaterialType.DOCUMENT for material in brief.current_materials)


def _is_graduate_lecture_brief(brief: WorkflowBriefInput) -> bool:
    text = _all_text(brief)
    audience_text = " ".join(brief.audience).lower()
    duration = brief.expected_duration_minutes or 0
    lecture_signal = any(keyword in text for keyword in LECTURE_KEYWORDS) or any(
        keyword in audience_text for keyword in LECTURE_KEYWORDS
    )
    return lecture_signal and _has_document_materials(brief) and duration >= 90


def _supports_evidence_backed_core(
    brief: WorkflowBriefInput,
    diagnosis: PresentationTypeDiagnosis,
    scale_mode: ScaleMode,
    evidence_density: str,
) -> bool:
    types = {diagnosis.primary_type, *diagnosis.secondary_types}
    if PresentationType.REPORT not in types:
        return False
    if any(
        blocked_type in types
        for blocked_type in {
            PresentationType.TRAINING,
            PresentationType.DEMO,
            PresentationType.WORKSHOP,
            PresentationType.KEYNOTE,
        }
    ):
        return False
    if _is_graduate_lecture_brief(brief):
        return False
    if _is_continuity_scale(scale_mode):
        return False
    if evidence_density == "light":
        return False
    source_ready_types = {
        BriefMaterialType.DOCUMENT,
        BriefMaterialType.DATA,
        BriefMaterialType.SPREADSHEET,
        BriefMaterialType.DECK,
        BriefMaterialType.IMAGE,
    }
    return any(material.material_type in source_ready_types for material in brief.current_materials)


def infer_evidence_density(brief: WorkflowBriefInput) -> str:
    text = _all_text(brief)
    score = len(brief.current_materials)
    score += sum(1 for material in brief.current_materials if material.material_type.value in {"spreadsheet", "data", "demo-environment"})
    if any(material.material_type.value in {"document", "deck"} for material in brief.current_materials):
        score += 1
    if any(keyword in text for keyword in ("appendix", "deep dive", "methods", "evidence", "proof", "backup")):
        score += 1
    if len(brief.facts) >= 3:
        score += 1
    if score <= 2:
        return "light"
    if score <= 6:
        return "medium"
    return "heavy"


def infer_presentation_type_diagnosis(brief: WorkflowBriefInput) -> PresentationTypeDiagnosis:
    text = _all_text(brief)
    audience_text = " ".join(brief.audience).lower()
    evidence_density = infer_evidence_density(brief)
    scores: dict[PresentationType, int] = {presentation_type: 0 for presentation_type in PresentationType}
    graduate_lecture_mode = _is_graduate_lecture_brief(brief)

    for presentation_type, keywords in PRESENTATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[presentation_type] += 1
    for presentation_type, keywords in AUDIENCE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in audience_text:
                scores[presentation_type] += 2

    if brief.delivery_mode == DeliveryMode.DECISION_MEETING:
        scores[PresentationType.DECISION] += 2
        scores[PresentationType.PERSUASION] += 1
    elif brief.delivery_mode == DeliveryMode.ASYNC_READOUT:
        scores[PresentationType.REPORT] += 1
        scores[PresentationType.EXPLAINER] += 1
    elif brief.delivery_mode == DeliveryMode.TRAINING_SESSION:
        scores[PresentationType.TRAINING] += 2
    elif brief.delivery_mode == DeliveryMode.DEMO_SESSION:
        scores[PresentationType.DEMO] += 2
    elif brief.delivery_mode == DeliveryMode.WORKSHOP:
        scores[PresentationType.WORKSHOP] += 3
        scores[PresentationType.DECISION] += 1
        scores[PresentationType.EXPLAINER] += 1

    for material in brief.current_materials:
        if material.material_type in {"spreadsheet", "data"}:
            scores[PresentationType.REPORT] += 1
        if material.material_type == "demo-environment":
            scores[PresentationType.DEMO] += 2
        if material.material_type == "deck":
            scores[PresentationType.EXPLAINER] += 1
        if material.material_type == "brief":
            scores[PresentationType.PERSUASION] += 1
        if material.material_type == "image":
            scores[PresentationType.KEYNOTE] += 1
        if material.material_type == "notes" and brief.delivery_mode == DeliveryMode.WORKSHOP:
            scores[PresentationType.WORKSHOP] += 1

    if any(keyword in text for keyword in ("investor", "prospect", "sales", "pipeline", "buyer")):
        scores[PresentationType.PITCH] += 1
    if any(keyword in text for keyword in ("vision", "future", "north star", "transformation", "inspire")):
        scores[PresentationType.KEYNOTE] += 1
    if any(keyword in text for keyword in ("facilitate", "facilitation", "working session", "co-design", "alignment session")):
        scores[PresentationType.WORKSHOP] += 1
    if graduate_lecture_mode:
        scores[PresentationType.TRAINING] += 5
        scores[PresentationType.EXPLAINER] += 4
        scores[PresentationType.PITCH] = max(0, scores[PresentationType.PITCH] - 2)
        scores[PresentationType.PERSUASION] = max(0, scores[PresentationType.PERSUASION] - 1)

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0].value))
    positive = [presentation_type for presentation_type, score in ranked if score > 0]
    if not positive:
        positive = [PresentationType.EXPLAINER]

    primary = positive[0]
    secondary = positive[1:2]

    label_parts = [primary, *secondary]
    reasoning = [
        f"Purpose, audience, and delivery mode suggest a {_presentation_label(primary)} deck.",
    ]
    if secondary:
        reasoning.append(
            "Secondary behavior is also present: "
            + ", ".join(_presentation_label(presentation_type) for presentation_type in secondary)
            + "."
        )
    if brief.current_materials:
        reasoning.append(f"Current materials already include {len(brief.current_materials)} source inputs.")
    reasoning.append(f"Evidence density appears {evidence_density} based on the current brief inputs.")
    if brief.notes:
        reasoning.append("Brief notes were supplied and folded into the Gate 1 diagnosis.")
    if graduate_lecture_mode:
        reasoning.append("Graduate lecture signals override commercial heuristics so Gate 2 starts from a teaching-first posture.")

    return PresentationTypeDiagnosis(
        primary_type=primary,
        secondary_types=secondary,
        diagnosis_label=" + ".join(_presentation_label(presentation_type) for presentation_type in label_parts),
        reasoning=reasoning,
    )


def infer_scale_mode(brief: WorkflowBriefInput, diagnosis: PresentationTypeDiagnosis, evidence_density: str) -> ScaleMode:
    hint = (brief.expected_scale_hint or "").lower()
    if "compact" in hint or "small" in hint or "short" in hint:
        return ScaleMode.COMPACT
    if "mega" in hint:
        return ScaleMode.MEGA_DECK
    if "large-deck" in hint or "large" in hint or "deep" in hint:
        return ScaleMode.LARGE_DECK
    if "extended" in hint or "expanded" in hint or "medium" in hint:
        return ScaleMode.EXTENDED
    if "standard" in hint:
        return ScaleMode.STANDARD

    duration = brief.expected_duration_minutes or 0
    text = _all_text(brief)
    types = {diagnosis.primary_type, *diagnosis.secondary_types}

    if _is_graduate_lecture_brief(brief):
        if duration >= 150:
            return ScaleMode.LARGE_DECK
        return ScaleMode.EXTENDED

    if duration and duration <= 10:
        return ScaleMode.COMPACT
    if duration and duration >= 65:
        return ScaleMode.MEGA_DECK
    if duration and duration >= 40:
        return ScaleMode.LARGE_DECK
    if duration and duration >= 25:
        return ScaleMode.EXTENDED
    if PresentationType.WORKSHOP in types and duration >= 20:
        return ScaleMode.EXTENDED
    if PresentationType.KEYNOTE in types and duration >= 25:
        return ScaleMode.EXTENDED
    if PresentationType.PITCH in types and duration and duration <= 12 and len(brief.current_materials) <= 3:
        return ScaleMode.COMPACT
    if "mega" in text or len(brief.current_materials) >= 8:
        return ScaleMode.MEGA_DECK
    if evidence_density == "heavy" and (duration >= 18 or len(brief.current_materials) >= 5):
        return ScaleMode.LARGE_DECK
    if "appendix" in text or "deep dive" in text or len(brief.current_materials) >= 5:
        return ScaleMode.LARGE_DECK
    if diagnosis.primary_type in {PresentationType.TRAINING, PresentationType.DEMO, PresentationType.WORKSHOP} and duration >= 30:
        return ScaleMode.LARGE_DECK
    if evidence_density in {"medium", "heavy"} and (duration >= 18 or len(brief.current_materials) >= 4):
        return ScaleMode.EXTENDED
    if "brief" in text or "pilot approval" in text or "five minute" in text:
        return ScaleMode.COMPACT
    return ScaleMode.STANDARD


def _tuned_range(start: int, end: int, delta_start: int = 0, delta_end: int = 0, *, minimum: int = 1) -> CountRange:
    tuned_start = max(minimum, start + delta_start)
    tuned_end = max(tuned_start, end + delta_end)
    return CountRange(start=tuned_start, end=tuned_end)


def infer_slide_count_guidance(
    brief: WorkflowBriefInput,
    scale_mode: ScaleMode,
    diagnosis: PresentationTypeDiagnosis,
    evidence_density: str,
) -> tuple[CountRange, CountRange, CountRange, int]:
    if _is_graduate_lecture_brief(brief):
        return (
            CountRange(start=72, end=95),
            CountRange(start=55, end=70),
            CountRange(start=15, end=25),
            72,
        )

    if scale_mode == ScaleMode.COMPACT:
        optimal = CountRange(start=5, end=8)
        main_story = CountRange(start=4, end=6)
        appendix = CountRange(start=0, end=2)
        smallest = 5
    elif scale_mode == ScaleMode.EXTENDED:
        optimal = CountRange(start=12, end=20)
        main_story = CountRange(start=8, end=13)
        appendix = CountRange(start=3, end=6)
        smallest = 12
    elif scale_mode == ScaleMode.MEGA_DECK:
        optimal = CountRange(start=28, end=60)
        main_story = CountRange(start=16, end=28)
        appendix = CountRange(start=8, end=24)
        smallest = 28
    elif scale_mode == ScaleMode.LARGE_DECK:
        optimal = CountRange(start=16, end=26)
        main_story = CountRange(start=10, end=16)
        appendix = CountRange(start=4, end=10)
        smallest = 16
    else:
        optimal = CountRange(start=8, end=14)
        main_story = CountRange(start=6, end=10)
        appendix = CountRange(start=2, end=4)
        smallest = 8

    types = {diagnosis.primary_type, *diagnosis.secondary_types}
    if PresentationType.DECISION in types or PresentationType.PERSUASION in types or PresentationType.PITCH in types:
        optimal = _tuned_range(optimal.start, optimal.end, 0, -1)
        main_story = _tuned_range(main_story.start, main_story.end, 0, -1)
        smallest = max(optimal.start, smallest - 1)
    if PresentationType.REPORT in types or PresentationType.TRAINING in types or PresentationType.DEMO in types or PresentationType.WORKSHOP in types:
        optimal = _tuned_range(optimal.start, optimal.end, 0, 2)
        appendix = _tuned_range(appendix.start, appendix.end, 0, 2, minimum=0)
    if PresentationType.KEYNOTE in types:
        main_story = _tuned_range(main_story.start, main_story.end, 0, 1)
        appendix = _tuned_range(appendix.start, appendix.end, 0, -1, minimum=0)
    if brief.delivery_mode == DeliveryMode.ASYNC_READOUT:
        optimal = _tuned_range(optimal.start, optimal.end, 0, 2)
        appendix = _tuned_range(appendix.start, appendix.end, 0, 1, minimum=0)
    if evidence_density == "heavy" and not (
        PresentationType.REPORT in types
        or PresentationType.TRAINING in types
        or PresentationType.DEMO in types
        or PresentationType.WORKSHOP in types
    ):
        optimal = _tuned_range(optimal.start, optimal.end, 0, 2)
        appendix = _tuned_range(appendix.start, appendix.end, 0, 2, minimum=0)
    elif evidence_density == "light":
        appendix = _tuned_range(appendix.start, appendix.end, 0, -1, minimum=0)
        if scale_mode == ScaleMode.COMPACT:
            appendix = CountRange(start=0, end=0)
    smallest = max(optimal.start, min(smallest, optimal.end))
    return optimal, main_story, appendix, smallest


def _material_strength_label(brief: WorkflowBriefInput) -> str:
    if not brief.current_materials:
        return "materials-thin"
    if len(brief.current_materials) >= 4:
        return "materials-rich"
    return "materials-ready"


def _phase(phase_id: str, label: str, objective: str, expected_outputs: list[str]) -> WorkflowPhase:
    return WorkflowPhase(
        phase_id=phase_id,
        label=label,
        objective=objective,
        expected_outputs=expected_outputs,
    )


def _option(
    *,
    option_id: str,
    label: str,
    summary: str,
    main_story_slide_count_range: CountRange,
    appendix_candidate_slide_count_range: CountRange,
    when_it_fits_best: list[str],
    phases: list[WorkflowPhase],
    expected_outputs: list[str],
    benefits: list[str],
    risks: list[str],
    tradeoffs: list[str],
) -> WorkflowOption:
    return WorkflowOption(
        option_id=option_id,
        label=label,
        summary=summary,
        main_story_slide_count_range=main_story_slide_count_range,
        appendix_candidate_slide_count_range=appendix_candidate_slide_count_range,
        when_it_fits_best=when_it_fits_best,
        phases=phases,
        expected_outputs=expected_outputs,
        benefits=benefits,
        risks=risks,
        fit_rationale=when_it_fits_best,
        tradeoffs=tradeoffs,
    )


def build_workflow_options(
    brief: WorkflowBriefInput,
    diagnosis: PresentationTypeDiagnosis,
    scale_mode: ScaleMode,
    main_story_range: CountRange,
    appendix_range: CountRange,
    evidence_density: str,
) -> list[WorkflowOption]:
    compact_main = CountRange(start=main_story_range.start, end=min(main_story_range.end, main_story_range.start + 1))
    compact_appendix = CountRange(start=appendix_range.start, end=min(appendix_range.end, max(appendix_range.start, 2)))
    is_graduate_lecture = _is_graduate_lecture_brief(brief)
    evidence_specific_benefit = (
        "Adds explicit appendix planning early because the brief already points to heavy evidence density."
        if evidence_density == "heavy"
        else "Keeps proof accessible without committing to unnecessary appendix volume."
    )
    options: list[WorkflowOption] = [
        _option(
            option_id="tight-main-story",
            label="Tight main story first",
            summary="Start with the smallest effective story, then defer backup evidence to appendix candidates only if it changes the decision.",
            main_story_slide_count_range=compact_main,
            appendix_candidate_slide_count_range=compact_appendix,
            when_it_fits_best=[
                "Best when decision time is limited.",
                "Reinforces one-slide-one-message discipline before blueprinting.",
            ],
            phases=[
                _phase("freeze-ask", "Freeze the ask", "Define the single audience outcome and approval path.", ["Audience outcome", "Approval path"]),
                _phase(
                    "trim-story",
                    "Trim the core story",
                    "Lock the smallest main-story range and push backup material into appendix candidates.",
                    ["Main-story range", "Appendix candidate boundary"],
                ),
                _phase("gate-ready", "Prepare Gate 2 handoff", "Document assumptions, risks, and the workflow recommendation.", ["Validated workflow_plan"]),
            ],
            expected_outputs=["Approved main-story range", "Appendix candidate list", "Validated Gate 1 workflow_plan"],
            benefits=["Minimizes unnecessary slide growth.", "Keeps the deck aligned to one clear ask."],
            risks=["Lower-priority proof may need follow-up work before Gate 2."],
            tradeoffs=["May delay lower-priority evidence until after the core story is stable."],
        ),
    ]
    if _supports_evidence_backed_core(brief, diagnosis, scale_mode, evidence_density):
        options.append(
            _option(
                option_id="evidence-backed-core",
                label="Evidence-backed core",
                summary="Keep a concise main story but plan a modest appendix from the current materials so facts and methods remain accessible.",
                main_story_slide_count_range=main_story_range,
                appendix_candidate_slide_count_range=appendix_range,
                when_it_fits_best=[
                    "Useful when source materials already exist locally.",
                    "Balances executive clarity with supporting proof.",
                ],
                phases=[
                    _phase("sort-evidence", "Sort the evidence", "Separate proof that belongs in the main story from evidence that belongs in appendix candidates.", ["Evidence map", "Appendix candidate list"]),
                    _phase("shape-core", "Shape the core narrative", "Connect the decision or update narrative to the strongest available proof objects.", ["Core narrative outline", "Proof priorities"]),
                    _phase("confirm-bounds", "Confirm planning bounds", "Record slide-count guidance and Gate 2 prerequisites before blueprinting.", ["Validated workflow_plan"]),
                ],
                expected_outputs=["Main-story evidence priorities", "Appendix candidate list", "Gate 2 planning bounds"],
                benefits=["Preserves access to proof without overloading the main story.", evidence_specific_benefit],
                risks=["Requires early discipline about what stays in the appendix."],
                tradeoffs=["Can inflate the deck if appendix discipline slips."],
            )
        )

    if is_graduate_lecture:
        options.insert(
            0,
            _option(
                option_id="graduate-lecture-clustered",
                label="Graduate lecture clustered",
                summary="Cluster source subsections into concept-led lecture modules, cap the main-story budget, and route derivations or backup material into appendix-only support.",
                main_story_slide_count_range=main_story_range,
                appendix_candidate_slide_count_range=appendix_range,
                when_it_fits_best=[
                    "Best for long-form lectures built from textbooks, notes, or source documents.",
                    "Useful when the audience needs a teachable arc rather than document-faithful section mirroring.",
                ],
                phases=[
                    _phase(
                        "cluster-concepts",
                        "Cluster the concepts",
                        "Merge granular source subsections into teachable concept groups instead of mirroring every subsection.",
                        ["Concept clusters", "Cluster pacing map"],
                    ),
                    _phase(
                        "trim-teaching-copy",
                        "Trim teaching copy",
                        "Compress on-slide language to short teaching copy and push overflow into notes or appendix.",
                        ["Slide copy budget", "Appendix overflow list"],
                    ),
                    _phase(
                        "lock-lecture-bounds",
                        "Lock lecture bounds",
                        "Hold the lecture inside the approved main-story and appendix budgets before blueprinting.",
                        ["Lecture slide budget", "Appendix boundary"],
                    ),
                ],
                expected_outputs=["Concept-cluster map", "Lecture slide budget", "Appendix-only backlog"],
                benefits=[
                    "Produces a lecture narrative instead of a section-by-section document expansion.",
                    "Makes long teaching decks more predictable in pacing and density.",
                ],
                risks=["Needs stronger up-front pruning when the source document is highly granular."],
                tradeoffs=["Some lower-priority derivations move out of the main lecture and into appendix support."],
            ),
        )

    types = {diagnosis.primary_type, *diagnosis.secondary_types}
    if PresentationType.WORKSHOP in types and (brief.delivery_mode == DeliveryMode.WORKSHOP or diagnosis.primary_type == PresentationType.WORKSHOP):
        options.append(
            _option(
                option_id="facilitated-workshop-flow",
                label="Facilitated workshop flow",
                summary="Plan the deck as a facilitated working session with clear alignment, exercise, and decision modules plus bounded backup material.",
                main_story_slide_count_range=CountRange(start=max(6, main_story_range.start), end=main_story_range.end + 1),
                appendix_candidate_slide_count_range=CountRange(start=max(appendix_range.start, 2), end=appendix_range.end + 2),
                when_it_fits_best=[
                    "Best for facilitation-heavy sessions that need structured discussion moves.",
                    "Useful when the audience must align or decide together during the session.",
                ],
                phases=[
                    _phase("align-room", "Align the room", "Set the objective, agenda, and starting facts for the working session.", ["Workshop agenda", "Alignment frame"]),
                    _phase("work-through", "Work through the material", "Sequence the core modules or exercises so each part has a clear outcome.", ["Module sequence", "Exercise plan"]),
                    _phase("capture-decisions", "Capture decisions", "Define the intended outputs, decisions, and follow-up appendix needs.", ["Decision list", "Follow-up items"]),
                ],
                expected_outputs=["Facilitated flow", "Module sequence", "Decision and follow-up list"],
                benefits=["Protects facilitation structure.", "Prevents workshop decks from collapsing into unfocused status slides."],
                risks=["Can sprawl if each exercise becomes its own mini-deck."],
                tradeoffs=["Needs tighter timekeeping and explicit module boundaries."],
            )
        )
    elif PresentationType.TRAINING in types or PresentationType.DEMO in types:
        options.append(
            _option(
                option_id="training-demo-sequence",
                label="Training then demo sequence",
                summary="Teach the operating model first, then stage the demo as proof, with detailed steps pushed to appendix or backup sections.",
                main_story_slide_count_range=CountRange(start=max(5, main_story_range.start), end=main_story_range.end + 1),
                appendix_candidate_slide_count_range=CountRange(start=max(appendix_range.start, 2), end=appendix_range.end + 2),
                when_it_fits_best=[
                    "Matches decks that need understanding before system walkthroughs.",
                    "Supports training and enablement flows without overcrowding the core story.",
                ],
                phases=[
                    _phase("teach-core", "Teach the core workflow", "Define the smallest teaching spine the audience needs before the demo.", ["Training spine", "Critical concepts"]),
                    _phase("prove-in-demo", "Prove the flow in demo", "Sequence the live or recorded demo moments that validate the training story.", ["Demo checkpoints", "Fallback plan"]),
                    _phase("park-detail", "Park detail in appendix", "Move step-by-step detail, FAQs, and backup screenshots out of the core deck.", ["Appendix candidate list", "Leave-behind notes"]),
                ],
                expected_outputs=["Training spine", "Demo checkpoints", "Appendix candidate list"],
                benefits=["Matches enablement flows cleanly.", "Keeps training and demo logic distinct."],
                risks=["Can grow too long if demo detail leaks into the main story."],
                tradeoffs=["Requires clear separation between teaching slides and system proof."],
            )
        )
    elif PresentationType.REPORT in types and PresentationType.DECISION in types:
        options.append(
            _option(
                option_id="report-with-decision-cut",
                label="Report with decision cut",
                summary="Lead with the decision needed, then organize the body as a report-backed narrative with explicit appendix candidates for methods and detailed evidence.",
                main_story_slide_count_range=main_story_range,
                appendix_candidate_slide_count_range=CountRange(start=max(appendix_range.start, 2), end=appendix_range.end + 1),
                when_it_fits_best=[
                    "Fits update decks that still need a clear executive ask.",
                    "Keeps reporting detail available without turning the main story into a data dump.",
                ],
                phases=[
                    _phase("frame-decision", "Frame the decision", "Define the executive ask before reporting detail expands the story.", ["Decision framing", "Executive question list"]),
                    _phase("report-the-proof", "Report the proof", "Sequence the few reporting sections that justify the recommendation.", ["Core evidence list", "Methods boundary"]),
                    _phase("split-methods", "Split methods and backup", "Move supporting data, methods, and detailed tables into appendix candidates.", ["Appendix candidate list", "Method backlog"]),
                ],
                expected_outputs=["Decision framing", "Proof-led update structure", "Method and appendix split"],
                benefits=["Maintains executive clarity.", "Supports evidence-heavy update decks."],
                risks=["Needs tight section discipline to avoid sliding into a pure report deck."],
                tradeoffs=["Detailed reporting can still crowd the core story if not pruned early."],
            )
        )
    elif PresentationType.PITCH in types and diagnosis.primary_type == PresentationType.PITCH:
        options.append(
            _option(
                option_id="thesis-proof-close",
                label="Thesis proof close",
                summary="Lead with the commercial thesis, prove it with the few strongest signals, and end on a crisp ask or next step.",
                main_story_slide_count_range=compact_main,
                appendix_candidate_slide_count_range=compact_appendix,
                when_it_fits_best=[
                    "Best for pitch, sales, or investor-facing decks.",
                    "Useful when the audience needs conviction fast.",
                ],
                phases=[
                    _phase("state-thesis", "State the thesis", "Freeze the one-line pitch or commercial claim.", ["Pitch thesis", "Audience ask"]),
                    _phase("prove-traction", "Prove traction", "Select the smallest credible set of proof points.", ["Proof shortlist", "Supporting evidence backlog"]),
                    _phase("close-ask", "Close with the ask", "Define the decision, next step, or commercial close.", ["Close sequence", "Follow-up asks"]),
                ],
                expected_outputs=["Pitch thesis", "Proof shortlist", "Close sequence"],
                benefits=["Optimized for commercial clarity.", "Naturally keeps decks compact."],
                risks=["Thin proof can undermine the close if evidence is weak."],
                tradeoffs=["Requires aggressive pruning of context and backstory."],
            )
        )
    elif PresentationType.KEYNOTE in types and diagnosis.primary_type == PresentationType.KEYNOTE:
        options.append(
            _option(
                option_id="vision-arc",
                label="Vision arc",
                summary="Shape the deck as a keynote-style arc: why now, where the organization is headed, and what proof makes the vision credible.",
                main_story_slide_count_range=CountRange(start=max(6, main_story_range.start), end=main_story_range.end + 1),
                appendix_candidate_slide_count_range=CountRange(start=max(0, appendix_range.start - 1), end=max(1, appendix_range.end)),
                when_it_fits_best=[
                    "Best for keynote or vision-led presentations.",
                    "Useful when inspiration and strategic alignment matter as much as detail.",
                ],
                phases=[
                    _phase("frame-moment", "Frame the moment", "Establish why the audience should care now.", ["Opening narrative", "Urgency frame"]),
                    _phase("show-future", "Show the future state", "Define the vision, destination, or strategy shift.", ["Vision arc", "Core proof points"]),
                    _phase("land-proof", "Land the proof path", "Select the few signals that make the vision credible and bounded.", ["Proof shortlist", "Appendix backlog"]),
                ],
                expected_outputs=["Opening narrative", "Vision arc", "Proof shortlist"],
                benefits=["Supports strategic alignment without overloading detail.", "Creates a clear story spine for later Gate 2 work."],
                risks=["Can become vague if the proof path is not explicit enough."],
                tradeoffs=["Requires disciplined separation between inspiration and operational detail."],
            )
        )
    elif PresentationType.EXPLAINER in types and PresentationType.PERSUASION in types:
        options.append(
            _option(
                option_id="explainer-then-persuade",
                label="Explainer then persuade",
                summary="Spend early slides aligning the audience on the problem and mechanism, then convert to a focused recommendation sequence.",
                main_story_slide_count_range=main_story_range,
                appendix_candidate_slide_count_range=compact_appendix,
                when_it_fits_best=[
                    "Useful when the audience first needs to understand the context.",
                    "Supports mixed explainer and persuasion briefs cleanly.",
                ],
                phases=[
                    _phase("build-context", "Build context", "Define the few context points the audience must understand first.", ["Context list", "Proof shortlist"]),
                    _phase("turn-to-ask", "Turn to the ask", "Convert context into a focused recommendation or approval path.", ["Recommendation frame", "Main-story transition"]),
                    _phase("trim-overflow", "Trim overflow", "Move lower-priority detail into appendix candidates before Gate 2.", ["Appendix candidate list", "Open questions"]),
                ],
                expected_outputs=["Context list", "Recommendation frame", "Appendix candidate list"],
                benefits=["Handles mixed explain-and-persuade briefs cleanly.", "Prevents context from dominating the ask."],
                risks=["Needs strict pruning so context slides do not overwhelm the ask."],
                tradeoffs=["Context can still overgrow if proof points are not bounded."],
            )
        )
    else:
        options.append(
            _option(
                option_id="modular-briefing",
                label="Modular briefing",
                summary="Build a modular narrative that can flex between live delivery and appendix-heavy follow-up, while preserving a tight core story.",
                main_story_slide_count_range=main_story_range,
                appendix_candidate_slide_count_range=appendix_range,
                when_it_fits_best=[
                    "Works when the brief is still evolving.",
                    "Keeps later Gate 2 blueprinting flexible without losing discipline.",
                ],
                phases=[
                    _phase("freeze-core", "Freeze the core", "Define the minimum viable main story and audience outcome.", ["Main-story range", "Audience outcome"]),
                    _phase("modularize-proof", "Modularize proof", "Sort proof, methods, and follow-up material into reusable modules.", ["Proof modules", "Appendix candidates"]),
                    _phase("hold-optional", "Hold optional paths", "Document optional expansions without treating them as committed slide count.", ["Option backlog", "Planning notes"]),
                ],
                expected_outputs=["Main-story range", "Proof modules", "Option backlog"],
                benefits=["Flexible when the brief is still changing.", "Supports live and async adaptation."],
                risks=["Less opinionated than the more specialized workflow paths."],
                tradeoffs=["Can feel underspecified if the team avoids making workflow choices."],
            )
        )

    if scale_mode in {ScaleMode.LARGE_DECK, ScaleMode.MEGA_DECK}:
        options.append(
            _option(
                option_id="batched-core-and-appendix",
                label="Batched core and appendix",
                summary="Treat the main story and appendix as separate planning batches so long-deck continuity, numbering, and QA remain bounded.",
                main_story_slide_count_range=main_story_range,
                appendix_candidate_slide_count_range=CountRange(start=max(appendix_range.start, 4), end=appendix_range.end + 2),
                when_it_fits_best=[
                    "Best for large or continuity-sensitive decks.",
                    "Creates a safer path to Gate 2 and later production batching.",
                ],
                phases=[
                    _phase("batch-core", "Batch the core story", "Define the main-story batch and its continuity constraints.", ["Core batch plan", "Continuity rules"]),
                    _phase("batch-appendix", "Batch appendix candidates", "Separate backup evidence, methods, and references into explicit follow-on batches.", ["Appendix batch plan", "Boundary rules"]),
                    _phase("lock-handoffs", "Lock handoffs", "Record the decisions that later stages must preserve across batches.", ["Handoff notes", "Continuity warnings"]),
                ],
                expected_outputs=["Core batch plan", "Appendix batch plan", "Continuity notes"],
                benefits=["Protects continuity for large decks.", "Supports bounded later-stage execution."],
                risks=["Adds explicit coordination overhead early in planning."],
                tradeoffs=["Requires more planning discipline up front."],
            )
        )

    unique_options: list[WorkflowOption] = []
    seen_ids: set[str] = set()
    for option in options:
        if option.option_id not in seen_ids:
            seen_ids.add(option.option_id)
            unique_options.append(option)
    return unique_options[:4]


def choose_recommended_option(
    diagnosis: PresentationTypeDiagnosis, scale_mode: ScaleMode, options: list[WorkflowOption]
) -> str:
    option_ids = {option.option_id for option in options}
    types = {diagnosis.primary_type, *diagnosis.secondary_types}
    if "graduate-lecture-clustered" in option_ids:
        return "graduate-lecture-clustered"
    if "facilitated-workshop-flow" in option_ids and diagnosis.primary_type == PresentationType.WORKSHOP:
        return "facilitated-workshop-flow"
    if "training-demo-sequence" in option_ids and (PresentationType.TRAINING in types or PresentationType.DEMO in types):
        return "training-demo-sequence"
    if "report-with-decision-cut" in option_ids and PresentationType.REPORT in types and PresentationType.DECISION in types:
        return "report-with-decision-cut"
    if "thesis-proof-close" in option_ids and diagnosis.primary_type == PresentationType.PITCH:
        return "thesis-proof-close"
    if "vision-arc" in option_ids and diagnosis.primary_type == PresentationType.KEYNOTE:
        return "vision-arc"
    if scale_mode in {ScaleMode.LARGE_DECK, ScaleMode.MEGA_DECK} and "batched-core-and-appendix" in option_ids:
        return "batched-core-and-appendix"
    if "explainer-then-persuade" in option_ids and PresentationType.EXPLAINER in types and PresentationType.PERSUASION in types:
        return "explainer-then-persuade"
    if PresentationType.DECISION in types or PresentationType.PERSUASION in types or PresentationType.PITCH in types:
        return "tight-main-story"
    if "evidence-backed-core" in option_ids:
        return "evidence-backed-core"
    return options[0].option_id


def _derive_facts(brief: WorkflowBriefInput) -> list[str]:
    facts = list(brief.facts)
    facts.append(f"Delivery mode is {brief.delivery_mode.value}.")
    if brief.expected_duration_minutes is not None:
        facts.append(f"Target delivery window is {brief.expected_duration_minutes} minutes.")
    if brief.current_materials:
        material_labels = ", ".join(material.label for material in brief.current_materials)
        facts.append(f"Current materials include: {material_labels}.")
    return _unique(facts)


def _derive_assumptions(
    brief: WorkflowBriefInput, scale_mode: ScaleMode, appendix_range: CountRange
) -> list[str]:
    assumptions = [*brief.initial_assumptions, *brief.assumptions]
    if not brief.approval_path:
        assumptions.append("Assume the primary audience also acts as the first workflow approver.")
    if not brief.current_materials:
        assumptions.append("Assume new source material collection will be required before blueprint approval.")
    if appendix_range.end > 0:
        assumptions.append("Assume methods, backup evidence, and references can move into appendix candidates.")
    if _is_graduate_lecture_brief(brief):
        assumptions.append("Assume the lecture should cluster adjacent subsections into concept-led teaching modules.")
    if brief.delivery_mode == DeliveryMode.ASYNC_READOUT:
        assumptions.append("Assume slides must carry more self-contained context than a live talk track.")
    if _is_continuity_scale(scale_mode):
        assumptions.append("Assume the deck will require batching to protect continuity and QA bounds.")
    return _unique(assumptions)


def _derive_recommendations(
    brief: WorkflowBriefInput,
    smallest_effective_slide_count: int,
    main_story_range: CountRange,
    appendix_range: CountRange,
    recommended_option_id: str,
    evidence_density: str,
) -> list[str]:
    recommendations = list(brief.recommendations)
    recommendations.append("Choose the smallest workflow option that still answers the audience need.")
    recommendations.append(f"Keep the initial main story near {smallest_effective_slide_count} slides before expanding.")
    recommendations.append(f"Adopt `{recommended_option_id}` as the starting Gate 1 recommendation.")
    if appendix_range.end > 0:
        recommendations.append("Move methods, references, and backup evidence into appendix candidates rather than the main story.")
    recommendations.append("Do not start slide production until the workflow option is approved and Gate 2 is defined.")
    if main_story_range.end > 0:
        recommendations.append(f"Hold the main story inside roughly {main_story_range.label()} slides.")
    if evidence_density == "heavy":
        recommendations.append("Plan appendix candidates early so heavy evidence does not inflate the core narrative.")
    if _is_graduate_lecture_brief(brief):
        recommendations.append("Cluster source subsections into lecture modules instead of expanding one subsection into one slide.")
        recommendations.append("Cap the main lecture near 55-70 slides and hold derivations or backup examples for appendix support.")
    return _unique(recommendations)


def _derive_risks(
    brief: WorkflowBriefInput,
    diagnosis: PresentationTypeDiagnosis,
    scale_mode: ScaleMode,
    evidence_density: str,
) -> list[str]:
    risks: list[str] = []
    types = {diagnosis.primary_type, *diagnosis.secondary_types}
    if not brief.current_materials:
        risks.append("Thin source materials could force assumptions to dominate the workflow choice.")
    if len(types) > 1:
        risks.append("Mixed presentation modes can blur the story unless the main ask is explicit.")
    if _is_continuity_scale(scale_mode):
        risks.append("Large-deck continuity drift is likely without batching, ledger discipline, and appendix control.")
    if brief.delivery_mode == DeliveryMode.ASYNC_READOUT:
        risks.append("Async delivery raises the burden on slide clarity and may inflate deck size if not constrained.")
    if PresentationType.DEMO in types and not any(material.material_type == "demo-environment" for material in brief.current_materials):
        risks.append("Demo intent exists but no demo environment is listed in the current materials.")
    if PresentationType.REPORT in types and not any(material.material_type in {"spreadsheet", "data"} for material in brief.current_materials):
        risks.append("Report behavior is expected, but no explicit data source is listed in the current materials.")
    if PresentationType.PITCH in types and evidence_density == "light":
        risks.append("Pitch intent is present, but the current proof set may be too thin for a credible close.")
    if PresentationType.KEYNOTE in types and evidence_density == "light":
        risks.append("Vision-heavy storytelling may become vague unless a few grounding proof points are selected.")
    if PresentationType.WORKSHOP in types:
        risks.append("Workshop decks can sprawl unless each module has a bounded objective and output.")
    if _is_graduate_lecture_brief(brief):
        risks.append("Lecture decks can become chapter-faithful expansions unless concept clustering and copy compression are enforced early.")
    return _unique(risks)


def _decision_prompt_labels(
    brief: WorkflowBriefInput,
    diagnosis: PresentationTypeDiagnosis,
    scale_mode: ScaleMode,
    appendix_range: CountRange,
) -> list[str]:
    labels = [
        scale_mode.value,
        diagnosis.primary_type.value,
        *[presentation_type.value for presentation_type in diagnosis.secondary_types],
        brief.delivery_mode.value,
        _material_strength_label(brief),
        "smallest-effective-deck",
        "appendix-disciplined" if appendix_range.end > 0 else "main-story-only",
    ]
    if _is_graduate_lecture_brief(brief):
        labels.extend(["graduate-lecture", "document-clustered"])
    return _unique(labels)


def _deck_mode(scale_mode: ScaleMode, appendix_range: CountRange) -> DeckMode:
    if scale_mode == ScaleMode.COMPACT and appendix_range.end == 0:
        return DeckMode.MAIN_STORY
    return DeckMode.MIXED if appendix_range.end > 0 else DeckMode.MAIN_STORY


def _brief_source_prompt(brief: WorkflowBriefInput) -> str:
    return brief.source_prompt or f"{brief.deck_title or brief.topic}. {brief.purpose}"


def _infer_visual_density(
    brief: WorkflowBriefInput,
    diagnosis: PresentationTypeDiagnosis,
) -> PresentationVisualDensity:
    contextual = str(brief.lightweight_context.get("visual_density", "")).strip().lower()
    if contextual:
        try:
            return PresentationVisualDensity(contextual)
        except ValueError:
            pass
    text = _all_text(brief)
    if any(token in text for token in ("architecture", "diagram", "timeline", "roadmap", "workflow", "process", "kpi", "chart", "dashboard")):
        return PresentationVisualDensity.HIGH
    if diagnosis.primary_type in {
        PresentationType.REPORT,
        PresentationType.TRAINING,
        PresentationType.DEMO,
        PresentationType.WORKSHOP,
    }:
        return PresentationVisualDensity.MEDIUM
    return PresentationVisualDensity.LIGHT


def _infer_brand_mode(brief: WorkflowBriefInput) -> PresentationBrandMode:
    contextual = str(brief.lightweight_context.get("brand_mode", "")).strip().lower()
    if contextual:
        try:
            return PresentationBrandMode(contextual)
        except ValueError:
            pass
    text = _all_text(brief)
    if "reference" in text:
        return PresentationBrandMode.REFERENCE_ALIGNED
    if "brand" in text or "template" in text:
        return PresentationBrandMode.BRAND_CONSTRAINED
    if any(token in text for token in ("internal", "leadership", "executive", "board")):
        return PresentationBrandMode.INTERNAL_DEFAULT
    return PresentationBrandMode.GENERIC_PROFESSIONAL


def _infer_tone(
    brief: WorkflowBriefInput,
    diagnosis: PresentationTypeDiagnosis,
) -> str:
    contextual_tone = brief.lightweight_context.get("tone")
    if isinstance(contextual_tone, str) and contextual_tone.strip():
        return contextual_tone.strip()
    if isinstance(contextual_tone, list):
        joined = ", ".join(str(item).strip() for item in contextual_tone if str(item).strip())
        if joined:
            return joined
    if diagnosis.primary_type == PresentationType.PITCH:
        return "confident and persuasive"
    if diagnosis.primary_type in {PresentationType.DECISION, PresentationType.REPORT}:
        return "executive and concise"
    if diagnosis.primary_type in {PresentationType.TRAINING, PresentationType.DEMO, PresentationType.WORKSHOP}:
        return "clear and instructional"
    if any(token in _all_text(brief) for token in ("architecture", "platform", "system", "technical")):
        return "technical and structured"
    return "clear and professional"


def _evidence_density_enum(value: str) -> PresentationEvidenceDensity:
    mapping = {
        "light": PresentationEvidenceDensity.LIGHT,
        "medium": PresentationEvidenceDensity.MEDIUM,
        "heavy": PresentationEvidenceDensity.HEAVY,
    }
    return mapping.get(value, PresentationEvidenceDensity.MEDIUM)


def _infer_presentation_brief(
    brief: WorkflowBriefInput,
    diagnosis: PresentationTypeDiagnosis,
    optimal_range: CountRange,
    evidence_density: str,
) -> PresentationBrief:
    archetype = _infer_prompt_archetype(_brief_source_prompt(brief), brief.lightweight_context)
    source_prompt = _brief_source_prompt(brief)
    target_deck_length = optimal_range
    for key in ("target_deck_length", "deck_length", "slide_count"):
        contextual_range = _coerce_count_range(brief.lightweight_context.get(key))
        if contextual_range is not None:
            target_deck_length = contextual_range
            break
    if brief.source_prompt is not None:
        target_deck_length = _infer_prompt_deck_length(brief.source_prompt, brief.lightweight_context, archetype)
    inference_notes = [
        "Prompt-only inference seeded the planning contract." if brief.source_prompt else "Structured brief normalized into an explicit planning contract.",
        f"Primary diagnosis: {diagnosis.primary_type.value}.",
        f"Workflow planner target deck length: {target_deck_length.start}-{target_deck_length.end} slides.",
    ]
    return PresentationBrief(
        deck_title=brief.deck_title or brief.topic,
        source_prompt=source_prompt,
        audience=brief.audience,
        presentation_goal=brief.purpose,
        target_deck_length=target_deck_length,
        tone=_infer_tone(brief, diagnosis),
        evidence_density=_evidence_density_enum(evidence_density),
        visual_density=_infer_visual_density(brief, diagnosis),
        archetype=archetype,
        brand_mode=_infer_brand_mode(brief),
        lightweight_context=dict(brief.lightweight_context),
        assumptions=_unique([*brief.initial_assumptions, *brief.assumptions]),
        inference_notes=inference_notes,
    )


def _outline_function_pattern(archetype: PresentationArchetype) -> list[SlideFunction]:
    patterns = {
        PresentationArchetype.DECISION: [SlideFunction.KPI, SlideFunction.COMPARE, SlideFunction.PROCESS, SlideFunction.TIMELINE],
        PresentationArchetype.REPORT: [SlideFunction.KPI, SlideFunction.COMPARE, SlideFunction.TIMELINE, SlideFunction.PROCESS],
        PresentationArchetype.PITCH: [SlideFunction.COMPARE, SlideFunction.KPI, SlideFunction.TIMELINE, SlideFunction.PROCESS],
        PresentationArchetype.TRAINING: [SlideFunction.PROCESS, SlideFunction.ARCHITECTURE, SlideFunction.PROCESS, SlideFunction.TIMELINE],
        PresentationArchetype.ARCHITECTURE: [SlideFunction.ARCHITECTURE, SlideFunction.PROCESS, SlideFunction.COMPARE, SlideFunction.KPI],
        PresentationArchetype.PROCESS: [SlideFunction.PROCESS, SlideFunction.TIMELINE, SlideFunction.ARCHITECTURE, SlideFunction.COMPARE],
        PresentationArchetype.TIMELINE: [SlideFunction.TIMELINE, SlideFunction.PROCESS, SlideFunction.KPI, SlideFunction.COMPARE],
    }
    return patterns.get(archetype, [SlideFunction.ARCHITECTURE, SlideFunction.PROCESS, SlideFunction.COMPARE, SlideFunction.KPI])


def _slide_function_budget(
    slide_function: SlideFunction,
    presentation_brief: PresentationBrief,
) -> SlideContentBudget:
    if slide_function == SlideFunction.TITLE:
        return SlideContentBudget(
            max_title_chars=84,
            max_body_bullets=0,
            max_body_chars=0,
            max_evidence_items=0,
            visual_density=PresentationVisualDensity.MEDIUM,
            evidence_density=PresentationEvidenceDensity.LIGHT,
        )
    if slide_function == SlideFunction.AGENDA:
        return SlideContentBudget(
            max_title_chars=64,
            max_body_bullets=5,
            max_body_chars=180,
            max_evidence_items=0,
            visual_density=PresentationVisualDensity.LIGHT,
            evidence_density=PresentationEvidenceDensity.LIGHT,
        )
    if slide_function == SlideFunction.SECTION_DIVIDER:
        return SlideContentBudget(
            max_title_chars=56,
            max_body_bullets=0,
            max_body_chars=0,
            max_evidence_items=0,
            visual_density=PresentationVisualDensity.LIGHT,
            evidence_density=PresentationEvidenceDensity.LIGHT,
        )
    if slide_function in {SlideFunction.KPI, SlideFunction.COMPARE}:
        return SlideContentBudget(
            max_title_chars=72,
            max_body_bullets=4,
            max_body_chars=220,
            max_evidence_items=3,
            visual_density=PresentationVisualDensity.HIGH,
            evidence_density=presentation_brief.evidence_density,
        )
    if slide_function in {SlideFunction.TIMELINE, SlideFunction.PROCESS, SlideFunction.ARCHITECTURE}:
        return SlideContentBudget(
            max_title_chars=72,
            max_body_bullets=4,
            max_body_chars=210,
            max_evidence_items=2,
            visual_density=(
                PresentationVisualDensity.HIGH
                if presentation_brief.visual_density == PresentationVisualDensity.HIGH
                else PresentationVisualDensity.MEDIUM
            ),
            evidence_density=presentation_brief.evidence_density,
        )
    return SlideContentBudget(
        max_title_chars=72,
        max_body_bullets=3,
        max_body_chars=180,
        max_evidence_items=1,
        visual_density=PresentationVisualDensity.MEDIUM,
        evidence_density=presentation_brief.evidence_density,
    )


def _slide_function_title_hint(slide_function: SlideFunction, deck_title: str) -> str:
    mapping = {
        SlideFunction.TITLE: deck_title,
        SlideFunction.AGENDA: "Agenda",
        SlideFunction.SECTION_DIVIDER: "Core Story",
        SlideFunction.COMPARE: "Option comparison",
        SlideFunction.KPI: "Key metrics",
        SlideFunction.TIMELINE: "Timing and milestones",
        SlideFunction.ARCHITECTURE: "System structure",
        SlideFunction.PROCESS: "Process flow",
        SlideFunction.SUMMARY: "Key takeaways",
    }
    return mapping[slide_function]


def _slide_function_rationale(slide_function: SlideFunction) -> str:
    mapping = {
        SlideFunction.TITLE: "Open with the deck promise before detail appears.",
        SlideFunction.AGENDA: "Expose the story path so the compact deck still feels navigable.",
        SlideFunction.SECTION_DIVIDER: "Reset pacing without changing the underlying workflow contract.",
        SlideFunction.COMPARE: "Use a bounded comparison to help the audience choose between paths.",
        SlideFunction.KPI: "Lead with the strongest measurable signal when evidence is part of the argument.",
        SlideFunction.TIMELINE: "Translate the recommendation into concrete sequencing and timing.",
        SlideFunction.ARCHITECTURE: "Give the audience one stable structural frame for the material.",
        SlideFunction.PROCESS: "Explain the operating sequence before the close.",
        SlideFunction.SUMMARY: "Close on the retained message and the next step.",
    }
    return mapping[slide_function]


def _outline_section_name(slide_function: SlideFunction) -> str:
    if slide_function in {SlideFunction.TITLE, SlideFunction.AGENDA}:
        return "Open"
    if slide_function == SlideFunction.SECTION_DIVIDER:
        return "Transition"
    if slide_function == SlideFunction.SUMMARY:
        return "Close"
    return "Core Story"


def _build_slide_function_outline(
    presentation_brief: PresentationBrief,
    workflow_plan: WorkflowPlan,
) -> SlideFunctionOutline:
    target_slide_count = min(
        max(workflow_plan.smallest_effective_slide_count, presentation_brief.target_deck_length.start),
        presentation_brief.target_deck_length.end,
    )
    include_agenda = target_slide_count >= 6
    include_divider = target_slide_count >= 8
    reserved_slots = 2 + (1 if include_agenda else 0) + (1 if include_divider else 0)
    body_slots = max(1, target_slide_count - reserved_slots)
    outline_functions: list[SlideFunction] = [SlideFunction.TITLE]
    if include_agenda:
        outline_functions.append(SlideFunction.AGENDA)
    pattern = _outline_function_pattern(presentation_brief.archetype)
    divider_index = max(1, body_slots // 2)
    for index in range(body_slots):
        if include_divider and index == divider_index:
            outline_functions.append(SlideFunction.SECTION_DIVIDER)
        outline_functions.append(pattern[index % len(pattern)])
    outline_functions.append(SlideFunction.SUMMARY)
    slides = [
        SlideFunctionPlanItem(
            slide_number=slide_number,
            section=_outline_section_name(slide_function),
            deck_mode=DeckMode.MAIN_STORY,
            slide_function=slide_function,
            title_hint=_slide_function_title_hint(slide_function, presentation_brief.deck_title),
            content_budget=_slide_function_budget(slide_function, presentation_brief),
            rationale=_slide_function_rationale(slide_function),
        )
        for slide_number, slide_function in enumerate(outline_functions, start=1)
    ]
    return SlideFunctionOutline(
        deck_title=presentation_brief.deck_title,
        source_prompt=presentation_brief.source_prompt,
        workflow_option=workflow_plan.workflow_option,
        target_slide_count=target_slide_count,
        slides=slides,
        planning_notes=[
            "Generated before Gate 2 layout selection.",
            f"Archetype={presentation_brief.archetype.value}, workflow_option={workflow_plan.workflow_option}.",
            f"Evidence density={presentation_brief.evidence_density.value}, visual density={presentation_brief.visual_density.value}.",
        ],
    )


def plan_workflow(brief: WorkflowBriefInput) -> WorkflowPlan:
    diagnosis = infer_presentation_type_diagnosis(brief)
    evidence_density = infer_evidence_density(brief)
    scale_mode = infer_scale_mode(brief, diagnosis, evidence_density)
    optimal_range, main_story_range, appendix_range, smallest_effective = infer_slide_count_guidance(
        brief,
        scale_mode,
        diagnosis,
        evidence_density,
    )
    workflow_options = build_workflow_options(brief, diagnosis, scale_mode, main_story_range, appendix_range, evidence_density)
    recommended_option_id = choose_recommended_option(diagnosis, scale_mode, workflow_options)
    selected_option_id, workflow_option_provenance = resolve_requested_workflow_option(
        brief.requested_workflow_option,
        workflow_options,
        recommended_option_id,
    )
    deck_title = brief.deck_title or brief.topic

    project_snapshot = ProjectSnapshot(
        topic=brief.topic,
        audience=brief.audience,
        purpose=brief.purpose,
        delivery_mode=brief.delivery_mode,
        expected_duration_minutes=brief.expected_duration_minutes,
        expected_scale_hint=brief.expected_scale_hint,
        current_materials=brief.current_materials,
        constraints=brief.constraints,
        notes=brief.notes,
    )
    presentation_brief = _infer_presentation_brief(brief, diagnosis, optimal_range, evidence_density)
    draft_plan = WorkflowPlan(
        request_id=f"workflow-plan-{_slugify(deck_title)}",
        deck_title=deck_title,
        objective=brief.purpose,
        project_snapshot=project_snapshot,
        presentation_type_diagnosis=diagnosis,
        audience=brief.audience,
        deck_mode=_deck_mode(scale_mode, appendix_range),
        scale_mode=scale_mode,
        workflow_option=selected_option_id,
        workflow_options=workflow_options,
        workflow_option_provenance=workflow_option_provenance,
        decision_prompt_labels=_decision_prompt_labels(brief, diagnosis, scale_mode, appendix_range),
        facts=_derive_facts(brief),
        assumptions=_derive_assumptions(brief, scale_mode, appendix_range),
        recommendations=_derive_recommendations(
            brief,
            smallest_effective,
            main_story_range,
            appendix_range,
            selected_option_id,
            evidence_density,
        ),
        risks=_derive_risks(brief, diagnosis, scale_mode, evidence_density),
        optimal_slide_count_range=optimal_range,
        smallest_effective_slide_count=smallest_effective,
        main_story_slide_count_range=main_story_range,
        appendix_candidate_slide_count_range=appendix_range,
        presentation_brief=presentation_brief,
        approval_path=brief.approval_path or brief.audience[:2] or ["TBD approver"],
        gates=[
            GateStatus(gate=WorkflowGate.WORKFLOW_DESIGN, status=StageStatus.READY),
            GateStatus(gate=WorkflowGate.BLUEPRINT_AND_VISUAL_APPROVAL, status=StageStatus.DRAFT),
            GateStatus(gate=WorkflowGate.PRODUCTION_AND_QA, status=StageStatus.DRAFT),
        ],
        bounded_qa_rounds=2,
        constraints=brief.constraints,
        notes=(
            f"Gate 1 diagnosis is {diagnosis.diagnosis_label}. "
            f"Evidence density is {evidence_density}. "
            f"Selected workflow option is {selected_option_id} with a {scale_mode.value} deck profile. "
            f"{workflow_option_provenance.reason}"
        ),
    )
    slide_function_outline = _build_slide_function_outline(presentation_brief, draft_plan)
    canonical_generation_profile = build_canonical_generation_profile(
        deck_title=draft_plan.deck_title,
        materials=brief.current_materials,
        presentation_brief=presentation_brief,
        slide_function_outline=slide_function_outline,
        brand_context=brief.lightweight_context,
    )

    return draft_plan.model_copy(
        update={
            "canonical_generation_profile": canonical_generation_profile,
            "slide_function_outline": slide_function_outline,
        }
    )


def plan_workflow_with_provider(
    brief: WorkflowBriefInput,
    *,
    provider_settings: ProviderSettings | None = None,
    llm_backend_proof_path: str | Path | None = None,
) -> tuple[WorkflowPlan, LLMBackendProof]:
    proof = run_brief_intake(brief.model_dump(mode="json", exclude_none=True), provider_settings)
    if llm_backend_proof_path is not None:
        write_llm_backend_proof(proof, llm_backend_proof_path)
    return plan_workflow(brief), proof


def plan_workflow_from_file(path: str | Path) -> WorkflowPlan:
    return plan_workflow(load_workflow_brief(path))


def plan_workflow_from_file_with_provider(
    path: str | Path,
    *,
    provider_settings: ProviderSettings | None = None,
    llm_backend_proof_path: str | Path | None = None,
) -> tuple[WorkflowPlan, LLMBackendProof]:
    brief = load_workflow_brief(path)
    return plan_workflow_with_provider(
        brief,
        provider_settings=provider_settings,
        llm_backend_proof_path=llm_backend_proof_path,
    )

