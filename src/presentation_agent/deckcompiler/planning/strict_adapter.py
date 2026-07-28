"""Versioned deterministic adapter from Source/Evidence contracts to strict plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ...compiler.blueprint_adapter import validate_slide_blueprint_collection
from ...generator_contracts import validatePresentationPlan, validateSlideBlueprint
from ...non_pptx_modules.workflow_planner import infer_workflow_brief_from_prompt, plan_workflow
from ..errors import DeckCompilerError
from ..identity import stable_id
from ..intake.config import Phase3Config
from ..intake.multi_source import IntakeArtifacts
from ..provenance import seal_artifact, semantic_content_sha256, verify_artifact_content_hash


ADAPTER_VERSION = "deckcompiler-source-to-strict-v1"
WORKFLOW_ALIASES = {
    "decision_brief": "tight-main-story",
    "technical_explainer": "tight-main-story",
    "executive_summary": "tight-main-story",
    "academic_review": "thesis-proof-close",
    "modular_briefing": "modular-briefing",
}
FORBIDDEN_REQUEST_PATTERNS = {
    "full_slide_screenshot": ("full-slide screenshot", "full slide screenshot", "screenshots only"),
    "invented_evidence": ("invent citations", "invent statistics", "make up citations", "make up statistics"),
    "multi_deck_conflict": ("multiple decks", "multi-deck", "separate decks"),
}


@dataclass(frozen=True, slots=True)
class StrictPlanningArtifacts:
    workflow_resolution: dict[str, Any]
    source_gap_report: dict[str, Any]
    presentation_plan: dict[str, Any]
    slide_blueprint_collection: dict[str, Any]
    evidence_allocation_report: dict[str, Any]


ROLE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "role": "decision_framing",
        "title": "Decision framing and thesis",
        "objective": "Frame the decision, audience stakes, and source-backed thesis.",
        "slide_type": "decision_framing",
        "density": "low",
        "slot": "body",
        "required_slots": ["title", "body", "footer"],
        "preferred": ["recommendation", "claim", "intent"],
        "limit": 3,
    },
    {
        "role": "system_process",
        "title": "System and operating process",
        "objective": "Explain the operating system and causal process needed for the decision.",
        "slide_type": "process_explainer",
        "density": "medium",
        "slot": "process",
        "required_slots": ["title", "process", "footer"],
        "preferred": ["definition", "process", "constraint"],
        "limit": 4,
    },
    {
        "role": "risk_findings",
        "title": "Evidence-backed risk findings",
        "objective": "Prioritize the most consequential risks using traceable findings and numbers.",
        "slide_type": "risk_findings",
        "density": "high",
        "slot": "body",
        "required_slots": ["title", "body", "kpi", "footer"],
        "preferred": ["claim", "statistic", "limitation"],
        "limit": 5,
    },
    {
        "role": "options_comparison",
        "title": "Response options and trade-offs",
        "objective": "Compare viable response options against explicit decision criteria.",
        "slide_type": "option_comparison",
        "density": "high",
        "slot": "table",
        "required_slots": ["title", "table", "footer"],
        "preferred": ["comparison", "decision_criterion", "statistic"],
        "limit": 4,
    },
    {
        "role": "recommendation",
        "title": "Recommendation and rationale",
        "objective": "State the recommended decision and connect it to the strongest evidence.",
        "slide_type": "recommendation",
        "density": "medium",
        "slot": "callout",
        "required_slots": ["title", "callout", "body", "footer"],
        "preferred": ["recommendation", "decision_criterion", "claim"],
        "limit": 4,
    },
    {
        "role": "implementation_sources",
        "title": "Implementation path and source notes",
        "objective": "Close with an executable path, limitations, and visible source notes.",
        "slide_type": "implementation_roadmap",
        "density": "medium",
        "slot": "timeline",
        "required_slots": ["title", "timeline", "footer"],
        "preferred": ["process", "limitation", "constraint", "intent"],
        "limit": 4,
    },
)


def build_strict_planning(config: Phase3Config, intake: IntakeArtifacts) -> StrictPlanningArtifacts:
    prompt_text = _prompt_text(intake.source_corpus)
    workflow_resolution = _resolve_workflow(config, prompt_text)
    source_gap_report = _build_source_gap_report(config, intake)
    evidence = intake.evidence_unit_registry["evidence_units"]
    source_by_id = {item["source_id"]: item for item in intake.source_corpus["sources"]}
    topic = _topic_label(prompt_text)
    sections = _sections()
    slides: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    allocation_rows: list[dict[str, Any]] = []

    for index, role in enumerate(ROLE_SPECS, start=1):
        selected = _select_evidence(evidence, role["preferred"], role["limit"])
        if not selected:
            raise DeckCompilerError(
                "DC_PLANNING_FAILED",
                "strict_planning",
                f"no evidence or prompt intent is available for role {role['role']}",
            )
        slide_id = f"slide-{index:02d}-{role['role'].replace('_', '-')}"
        section_id = sections[(index - 1) // 2]["section_id"]
        citations = [
            {
                "citation_id": item["evidence_id"],
                "label": item["citation_metadata"]["citation_label"],
                "source": item["source_id"],
            }
            for item in selected
        ]
        content_blocks = [
            {
                "block_id": f"{slide_id}-evidence-{item_index:02d}",
                "slot": role["slot"],
                "type": "source_evidence" if item["factuality_class"] == "documentary_fact" else "prompt_or_inference",
                "content": item["canonical_content"]["text"],
            }
            for item_index, item in enumerate(selected, start=1)
        ]
        claim_origin = (
            "documentary_fact"
            if any(item["factuality_class"] == "documentary_fact" for item in selected)
            else "prompt_derived"
        )
        title = f"{role['title']}: {topic}" if index == 1 else role["title"]
        slide = {
            "schema_name": "slide_blueprint",
            "schema_version": "1.0",
            "slide_id": slide_id,
            "section_id": section_id,
            "slide_type": role["slide_type"],
            "title": title,
            "subtitle": f"Claim origin: {claim_origin.replace('_', ' ')}",
            "content_density": role["density"],
            "required_slots": role["required_slots"],
            "content_blocks": content_blocks,
            "chart_data": None,
            "table_data": None,
            "image_needs": [],
            "speaker_notes": _speaker_notes(selected, source_by_id),
            "citations": citations,
            "design_intent": role["objective"],
        }
        validateSlideBlueprint(slide)
        evidence_ids = [item["evidence_id"] for item in selected]
        slides.append(slide)
        bindings.append({"slide_id": slide_id, "evidence_ids": evidence_ids, "allocation_role": "primary"})
        allocation_rows.append(
            {
                "slide_id": slide_id,
                "role": role["role"],
                "primary_objective": role["objective"],
                "claim_origin": claim_origin,
                "evidence_ids": evidence_ids,
                "source_ids": sorted({item["source_id"] for item in selected}),
                "documentary_source_ids": sorted(
                    {item["source_id"] for item in selected if item["factuality_class"] == "documentary_fact"}
                ),
            }
        )

    presentation_plan = {
        "schema_name": "presentation_plan",
        "schema_version": "1.0",
        "deck_title": f"{topic}: Decision Brief",
        "audience": config.audience,
        "objective": f"Enable {config.audience} to make and implement a traceable decision about {topic}.",
        "tone": ", ".join(config.tone),
        "source_summary": _source_summary(config, intake),
        "narrative_structure": [
            {"step_id": section["section_id"], "label": section["title"], "purpose": section["purpose"]}
            for section in sections
        ],
        "sections": sections,
        "slide_count_target": config.slide_count,
        "slide_archetypes_needed": [role["slide_type"] for role in ROLE_SPECS],
        "constraints": [
            "Use only registered source evidence for documentary factual claims.",
            "Preserve source locators and visible citations.",
            "Keep real slide text and structured content editable.",
            "Forbid full-slide raster output and invented citations.",
            "Use one primary communication objective per slide.",
        ],
    }
    validatePresentationPlan(presentation_plan)
    collection_payload = {
        "schema_name": "slide_blueprint_collection",
        "schema_version": "1.1.0",
        "collection_id": stable_id("blueprints", [slide["slide_id"] for slide in slides], bindings),
        "slides": slides,
        "evidence_bindings": bindings,
    }
    collection = seal_artifact(
        collection_payload,
        artifact_type="slide_blueprint_collection",
        input_artifact_ids=(
            intake.evidence_unit_registry["artifact"]["artifact_id"],
            workflow_resolution["artifact"]["artifact_id"],
        ),
    )
    validate_slide_blueprint_collection(collection)
    represented_documentary = sorted(
        {source_id for row in allocation_rows for source_id in row["documentary_source_ids"]}
    )
    allocation_payload = {
        "schema_name": "evidence_allocation_report",
        "schema_version": "1.0.0",
        "report_id": stable_id("allocation", allocation_rows),
        "adapter_version": ADAPTER_VERSION,
        "ordered_slide_ids": [slide["slide_id"] for slide in slides],
        "slides": allocation_rows,
        "represented_documentary_source_ids": represented_documentary,
        "presentation_plan_content_sha256": semantic_content_sha256(presentation_plan),
        "slide_blueprint_collection_content_sha256": collection["artifact"]["content_sha256"],
        "every_factual_claim_evidence_bound": all(
            row["evidence_ids"] for row in allocation_rows if row["claim_origin"] == "documentary_fact"
        ),
        "duplicate_primary_objectives": _duplicates([row["primary_objective"] for row in allocation_rows]),
    }
    allocation_report = seal_artifact(
        allocation_payload,
        artifact_type="evidence_allocation_report",
        input_artifact_ids=(collection["artifact"]["artifact_id"],),
    )
    _validate_planning(config, intake, presentation_plan, collection, allocation_report)
    for payload in (workflow_resolution, source_gap_report, collection, allocation_report):
        verify_artifact_content_hash(payload)
    return StrictPlanningArtifacts(
        workflow_resolution,
        source_gap_report,
        presentation_plan,
        collection,
        allocation_report,
    )


def _resolve_workflow(config: Phase3Config, prompt_text: str) -> dict[str, Any]:
    lowered = prompt_text.lower()
    conflicts = [
        code for code, patterns in FORBIDDEN_REQUEST_PATTERNS.items() if any(pattern in lowered for pattern in patterns)
    ]
    if re.search(r"\b2\s+slides?\b", lowered) and re.search(r"\b30\b", lowered):
        conflicts.append("impossible_content_capacity")
    mapped = WORKFLOW_ALIASES.get(config.workflow)
    if mapped is None:
        raise DeckCompilerError(
            "DC_WORKFLOW_INCOMPATIBLE",
            "workflow_resolution",
            f"requested workflow alias is unsupported: {config.workflow}",
            related_ids=(config.workflow,),
            remediation_hint="Use a documented DeckCompiler workflow alias compatible with the six-slide P0 policy.",
        )
    if conflicts:
        raise DeckCompilerError(
            "DC_WORKFLOW_INCOMPATIBLE",
            "workflow_resolution",
            f"request conflicts with Phase 3 policy: {', '.join(sorted(conflicts))}",
            related_ids=(config.workflow, *sorted(conflicts)),
            remediation_hint="Remove screenshot-only, invented-evidence, multi-deck, or impossible-capacity constraints.",
        )
    brief = infer_workflow_brief_from_prompt(
        prompt_text,
        {
            "audience": [config.audience],
            "expected_duration_minutes": max(6, config.slide_count * 2),
            "requested_workflow_option": mapped,
            "delivery_mode": "live-presentation",
        },
    )
    workflow_plan = plan_workflow(brief)
    provenance = workflow_plan.workflow_option_provenance
    status = provenance.contract_status.value if provenance is not None else "absent"
    if status != "honored":
        raise DeckCompilerError(
            "DC_WORKFLOW_INCOMPATIBLE",
            "workflow_resolution",
            provenance.reason if provenance is not None else "workflow contract was not honored",
            related_ids=(config.workflow, mapped),
            remediation_hint="Select a contractable workflow reported by the existing workflow contract matrix.",
        )
    payload = {
        "schema_name": "workflow_resolution",
        "schema_version": "1.0.0",
        "resolution_id": stable_id("workflow", config.workflow, provenance.model_dump(mode="json")),
        "requested_workflow": config.workflow,
        "mapped_workflow_option": mapped,
        "selected_workflow_option": workflow_plan.workflow_option,
        "contract_status": status,
        "resolution_code": provenance.resolution_code.value,
        "policy_id": provenance.policy_id,
        "reason": provenance.reason,
        "existing_contract_matrix_used": True,
        "planning_adapter_version": ADAPTER_VERSION,
    }
    return seal_artifact(payload, artifact_type="workflow_resolution")


def _build_source_gap_report(config: Phase3Config, intake: IntakeArtifacts) -> dict[str, Any]:
    documentary_count = intake.source_coverage_report["documentary_source_count"]
    gaps = list(intake.source_coverage_report["source_gaps"])
    payload = {
        "schema_name": "source_gap_report",
        "schema_version": "1.0.0",
        "report_id": stable_id("gaps", config.mode, gaps),
        "documentary_evidence_status": "present" if documentary_count else "absent",
        "gaps": gaps,
        "unsupported_claim_policy": "declare_as_source_gap_or_inference",
        "invented_citations_forbidden": True,
        "invented_quantitative_evidence_forbidden": True,
    }
    return seal_artifact(
        payload,
        artifact_type="source_gap_report",
        input_artifact_ids=(intake.source_coverage_report["artifact"]["artifact_id"],),
    )


def _select_evidence(
    evidence: list[dict[str, Any]],
    preferred_types: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for evidence_type in preferred_types:
        for item in evidence:
            if item["evidence_type"] == evidence_type and item not in selected:
                selected.append(item)
                if len(selected) >= limit:
                    return selected
    if not selected:
        selected = [item for item in evidence if item["factuality_class"] != "documentary_fact"][:1]
    return selected


def _validate_planning(
    config: Phase3Config,
    intake: IntakeArtifacts,
    plan: dict[str, Any],
    collection: dict[str, Any],
    allocation: dict[str, Any],
) -> None:
    slides = collection["slides"]
    if config.slide_count != 6 or len(slides) != 6:
        raise DeckCompilerError("DC_BLUEPRINT_COUNT_MISMATCH", "strict_planning", "Phase 3 P0 requires exactly six slides")
    slide_ids = [slide["slide_id"] for slide in slides]
    if len(slide_ids) != len(set(slide_ids)):
        raise DeckCompilerError("DC_DUPLICATE_SLIDE_ID", "strict_planning", "slide IDs must be unique")
    if allocation["duplicate_primary_objectives"]:
        raise DeckCompilerError("DC_DUPLICATE_SLIDE_OBJECTIVE", "strict_planning", "primary objectives must be unique")
    known_evidence = {item["evidence_id"] for item in intake.evidence_unit_registry["evidence_units"]}
    for binding in collection["evidence_bindings"]:
        unknown = set(binding["evidence_ids"]) - known_evidence
        if unknown:
            raise DeckCompilerError(
                "DC_EVIDENCE_SOURCE_MISMATCH",
                "strict_planning",
                f"blueprint references unknown evidence: {', '.join(sorted(unknown))}",
            )
    if config.mode == "prompt_plus_two_pdfs":
        expected_sources = {
            item["source_id"] for item in intake.source_corpus["sources"] if item["source_type"] == "pdf"
        }
        if set(allocation["represented_documentary_source_ids"]) != expected_sources:
            raise DeckCompilerError(
                "DC_EVIDENCE_COVERAGE_INCOMPLETE",
                "strict_planning",
                "strict planning must represent both documentary PDF sources",
            )
    validatePresentationPlan(plan)
    validate_slide_blueprint_collection(collection)


def _topic_label(prompt_text: str) -> str:
    normalized = " ".join(prompt_text.split())
    about = re.search(r"\babout\s+(.+?)(?:\.|\bdo not\b|$)", normalized, flags=re.IGNORECASE)
    if about:
        return _title_case(about.group(1))
    explain = re.search(r"\bexplain\s+(.+?)(?:\s+operation\b|,|\.)", normalized, flags=re.IGNORECASE)
    if explain:
        return _title_case(explain.group(1))
    words = re.findall(r"[A-Za-z0-9-]+", normalized)
    return _title_case(" ".join(words[:8])) or "Source-Grounded Decision"


def _title_case(value: str) -> str:
    return " ".join(word.capitalize() if word.islower() else word for word in value.strip().split())


def _sections() -> list[dict[str, Any]]:
    return [
        {
            "section_id": "section-01-understand",
            "title": "Understand the decision",
            "purpose": "Establish the decision frame and explain the operating system.",
            "slide_count": 2,
        },
        {
            "section_id": "section-02-evaluate",
            "title": "Evaluate evidence and options",
            "purpose": "Prioritize risks and compare response options.",
            "slide_count": 2,
        },
        {
            "section_id": "section-03-act",
            "title": "Decide and implement",
            "purpose": "State the recommendation and define an implementation path.",
            "slide_count": 2,
        },
    ]


def _prompt_text(corpus: dict[str, Any]) -> str:
    return next(item["user_brief"] for item in corpus["sources"] if item["source_type"] == "user_prompt")


def _source_summary(config: Phase3Config, intake: IntakeArtifacts) -> str:
    if config.mode == "prompt_only":
        return "One user prompt; no documentary source supplied; factual and quantitative gaps remain explicit."
    count = intake.source_coverage_report["documentary_fact_count"]
    return f"One user prompt and two repository-authored synthetic PDFs normalized into {count} documentary Evidence Units."


def _speaker_notes(items: list[dict[str, Any]], source_by_id: dict[str, dict[str, Any]]) -> str:
    notes = []
    for item in items:
        source = source_by_id[item["source_id"]]
        notes.append(f"{item['citation_metadata']['display_locator']} — {source['display_name']}")
    return "Source notes: " + "; ".join(notes)


def _duplicates(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


__all__ = ["ADAPTER_VERSION", "StrictPlanningArtifacts", "build_strict_planning"]
