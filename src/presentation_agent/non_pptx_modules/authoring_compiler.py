"""Deterministic slide authoring compiler for lecture decks."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .state_schemas import (
    AuthoringPreview,
    AuthoringPreviewSlide,
    ConceptGraph,
    ConceptNode,
    ContentTier,
    DeckMode,
    LectureFamily,
    SlideArchetype,
    SlideIntent,
    SlideRole,
    SourceMaterialRef,
    TeachingPlan,
    TeachingPlanSlide,
    VisualType,
)


TITLE_LIMIT = 60
MESSAGE_LIMIT = 118
BODY_LIMIT = 92
APPENDIX_GROUP_TOPICS = [
    {
        "topics": ("genetic algorithm", "one generation cycle"),
        "title": "Algorithm loop evidence cluster",
        "kind": "themed",
    },
    {
        "topics": ("fitness", "phenotype to fitness bridge"),
        "title": "Fitness evaluation source-location matrix",
        "kind": "source-location",
    },
    {
        "topics": ("selection operator", "natural selection"),
        "title": "Selection analogy evidence comparison",
        "kind": "comparison",
    },
]
APPENDIX_SINGLE_TOPICS = {
    "biology to ga correspondence": {
        "title": "Correspondence source-location matrix",
        "kind": "source-location",
    },
    "crossover": {
        "title": "Crossover excerpt cluster",
        "kind": "annotated-excerpt",
    },
    "mutation operator": {
        "title": "Mutation excerpt cluster",
        "kind": "annotated-excerpt",
    },
    "representation and encoding": {
        "title": "Encoding/representation source-location matrix",
        "kind": "source-location",
    },
    "genotype": {
        "title": "Representation state evidence cluster",
        "kind": "themed",
    },
    "phenotype": {
        "title": "Decoded behavior excerpt cluster",
        "kind": "annotated-excerpt",
    },
    "exploration and exploitation tradeoff": {
        "title": "Exploration/exploitation source matrix",
        "kind": "source-location",
    },
    "genes": {
        "title": "Genes as building blocks evidence cluster",
        "kind": "themed",
    },
    "limitations": {
        "title": "Limitations evidence cluster",
        "kind": "themed",
    },
    "schema or building-block intuition": {
        "title": "Building-block intuition excerpt cluster",
        "kind": "annotated-excerpt",
    },
    "applications": {
        "title": "Applications fit evidence cluster",
        "kind": "themed",
    },
    "variation": {
        "title": "Variation cross-reference map",
        "kind": "source-map",
    },
}
APPENDIX_TOPIC_MESSAGES = {
    "genetic algorithm": "Anchor the full population-search loop rather than one isolated optimization step.",
    "one generation cycle": "Trace the ordered encode, evaluate, select, vary, and repeat loop through the cited pages.",
    "fitness": "Anchor evaluation in explicit scoring after the candidate is decoded into behavior.",
    "biology to ga correspondence": "Anchor each biology term to one concrete GA role instead of using the analogy loosely.",
    "crossover": "Anchor the passages about recombination preserving some partial structure while breaking other parts.",
    "mutation operator": "Anchor the passages about diversity-restoring local variation when the pool narrows too quickly.",
    "representation and encoding": "Anchor how the chromosome encoding decides what operators can actually change.",
    "selection operator": "Anchor the passages about biased parent choice before variation creates the next pool.",
    "natural selection": "Anchor the biological analogy that the algorithm deliberately simplifies into selection pressure.",
    "genotype": "Anchor stored search state rather than observed task performance.",
    "phenotype": "Anchor decoded behavior in the task setting before any score is assigned.",
    "exploration and exploitation tradeoff": "Anchor the tension between broad search and preserving useful inherited structure.",
    "genes": "Anchor how one decision unit becomes a reusable building block inside the encoding.",
    "limitations": "Anchor where the biology story stops helping unless it points back to design choices.",
    "schema or building-block intuition": "Anchor why building-block intuition helps only when the encoding preserves useful segments.",
    "phenotype to fitness bridge": "Anchor the scoring step that connects decoded behavior back to parent selection.",
    "applications": "Anchor the conditions under which GA search is worth its computational cost.",
    "variation": "Anchor why crossover and mutation stay separate inside the search loop.",
}
SKIP_REPEAT_KEYS = {
    "genetic algorithm in the cycle",
    "one generation cycle in the cycle",
    "crossover in the cycle",
    "mutation operator in the cycle",
    "selection operator in the cycle",
}
BRIDGE_ARCHETYPE_VALUES = {
    SlideArchetype.TWO_COLUMN_MAPPING_TABLE.value,
    SlideArchetype.CORRESPONDENCE_MATRIX.value,
}
MAIN_STORY_CHOREOGRAPHY_ORDER = [
    "From genetics concepts to genetic algorithms",
    "Biology to GA teaching arc",
    "Why the analogy helps",
    "Genes as an algorithm design choice",
    "Alleles as an algorithm design choice",
    "Genotype",
    "Phenotype as an algorithm design choice",
    "Variation changes the population in two ways",
    "Selection is the population filter",
    "Biology to GA map",
    "Genes and alleles become an encoding",
    "A GA searches with populations",
    "Phenotype shows why fitness is external",
    "Natural selection becomes a selection operator",
    "Operators in one generation",
    "One generation cycle",
    "Worked example with a toy population",
    "Why building blocks matter",
    "How one toy population changes",
    "Population search repeats across generations",
    "Selection pressure changes the candidate pool",
    "Crossover recombines partial building blocks",
    "One loop is useful only if the next loop can improve it",
    "Mutation protects exploration",
    "Fitness is scored after decoding",
    "The analogy maps roles, not literal biology",
    "Crossover preserves some patterns and breaks others",
    "Mutation operator restores diversity",
    "Selection trades speed for diversity",
    "Exploration and exploitation must stay in tension",
    "A GA is useful when the search space is awkward",
    "Variation helps until it destroys inherited structure",
    "Encoding choices shape what operators can do",
    "Genotype stores search state",
    "Engineering use cases share one pattern",
    "Keep the metaphor subordinate to design criteria",
    "Selection pressure is tuned, not natural",
    "Decoding links representation to selection",
    "Synthesis: the full correspondence chain",
    "Phenotype shows whether a candidate actually works",
    "Gene boundaries control reusable building blocks",
    "The analogy helps until it hides design choices",
    "Alleles define the search alphabet",
    "Encoding boundaries decide crossover quality",
    "Pressure settings move the convergence dial",
    "The chromosome is memory, not merit",
    "Building blocks survive only under aligned encoding",
    "Evaluation makes phenotype visible to selection",
    "Building blocks depend on linkage",
    "Schema intuition is really an encoding claim",
    "Search pressure changes over the run",
    "Scores connect behavior back to reproduction",
    "Decoded behavior is where feasibility appears",
    "Variation rate sets the repair-versus-noise tradeoff",
    "Allowed allele values define the move set",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _shorten(text: str, limit: int) -> str:
    cleaned = _norm(text)
    if len(cleaned) <= limit:
        return cleaned
    trimmed = cleaned[: max(limit - 3, 1)].rstrip(" ,;:/-")
    return f"{trimmed}..."


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = _norm(item)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _title_key(title: str) -> str:
    return _norm(title).lower()


def _title_stem(title: str) -> str:
    stem = _title_key(title)
    stem = re.sub(r"\s+as a bridge$", "", stem)
    stem = re.sub(r"\s+in the cycle$", "", stem)
    stem = re.sub(r"\s+tradeoffs$", "", stem)
    stem = re.sub(r"\s+pitfalls$", "", stem)
    return stem


def _message_opening(text: str | None, words: int = 3) -> str:
    cleaned = _norm(text or "").lower()
    if not cleaned:
        return ""
    tokens = cleaned.split()
    return " ".join(tokens[:words])


def _cluster_overflow(indices: list[int], *, allowed: int, max_gap: int = 1) -> tuple[int, list[int]]:
    if not indices:
        return 0, []
    overflow = 0
    overflow_positions: list[int] = []
    cluster: list[int] = [indices[0]]
    for index in indices[1:]:
        if index - cluster[-1] <= max_gap + 1:
            cluster.append(index)
            continue
        if len(cluster) > allowed:
            overflow += len(cluster) - allowed
            overflow_positions.extend(cluster[allowed:])
        cluster = [index]
    if len(cluster) > allowed:
        overflow += len(cluster) - allowed
        overflow_positions.extend(cluster[allowed:])
    return overflow, overflow_positions


def _is_bridge_shell_spec(spec: dict[str, Any]) -> bool:
    slide_intent = spec.get("slide_intent")
    archetype = spec.get("slide_archetype")
    archetype_value = archetype.value if isinstance(archetype, SlideArchetype) else str(archetype or "")
    return slide_intent == SlideIntent.MAPPING_BRIDGE or archetype_value in BRIDGE_ARCHETYPE_VALUES


def _is_cycle_shell_spec(spec: dict[str, Any]) -> bool:
    title = _title_key(str(spec.get("title", "")))
    slide_intent = spec.get("slide_intent")
    archetype = spec.get("slide_archetype")
    archetype_value = archetype.value if isinstance(archetype, SlideArchetype) else str(archetype or "")
    cycle_keywords = (
        "selection",
        "crossover",
        "mutation",
        "operator",
        "cycle",
        "pressure",
        "variation",
        "linkage",
        "building blocks",
    )
    if any(keyword in title for keyword in cycle_keywords):
        return archetype_value in {
            SlideArchetype.PROCESS_FLOW.value,
            SlideArchetype.STEP_BY_STEP_MECHANISM.value,
            SlideArchetype.WORKED_EXAMPLE_STATE_TABLE.value,
            SlideArchetype.COMPARISON_MATRIX.value,
            SlideArchetype.LIMITATION_PITFALL_CALLOUT.value,
        } or slide_intent in {
            SlideIntent.MECHANISM_WALKTHROUGH,
            SlideIntent.COMPARISON_TRADEOFF,
            SlideIntent.MISCONCEPTION_PITFALL,
        }
    return False


def _concept_label(concept_id: str | None, nodes_by_id: dict[str, ConceptNode]) -> str:
    if concept_id is None:
        return "This concept"
    node = nodes_by_id.get(concept_id)
    return node.label if node is not None else concept_id.replace("-", " ")


def _source_lane(refs: list[SourceMaterialRef], limit: int = 3) -> list[str]:
    labels: list[str] = []
    for ref in refs[:limit]:
        location = f"{ref.label} p.{ref.page}" if ref.page is not None else ref.label
        labels.append(location)
    return labels


def _budget(title: str, core_content: list[str], chrome_blocks: list[str], primary_visual_structure: str) -> dict[str, Any]:
    return {
        "title_chars": len(title),
        "body_slot_count": len(core_content),
        "bullet_count": len(core_content),
        "chrome_block_count": len(chrome_blocks),
        "visual_center": primary_visual_structure,
    }


def _duplicate_flags(title: str, takeaway: str, core_content: list[str]) -> list[str]:
    norm_title = _title_stem(title)
    norm_takeaway = _norm(takeaway).lower()
    flags: list[str] = []
    for item in core_content:
        norm_item = _norm(item).lower()
        if not norm_item:
            continue
        if norm_title and norm_title in norm_item:
            flags.append("title-repeated-in-body")
        if norm_takeaway and norm_item == norm_takeaway:
            flags.append("takeaway-repeated-in-body")
    return _dedupe(flags)


def _support_lines(lines: list[str]) -> list[str]:
    return [_shorten(line, BODY_LIMIT) for line in _dedupe(lines)[:3]]


def _spec(
    *,
    slide: TeachingPlanSlide,
    title: str,
    message: str,
    slide_role: SlideRole,
    visual_type: VisualType,
    layout_pattern_id: str,
    slide_archetype: SlideArchetype,
    primary_visual_structure: str,
    core_content: list[str],
    authoring_payload: dict[str, Any],
    slide_intent: SlideIntent | None = None,
    concept_ids: list[str] | None = None,
    evidence: list[SourceMaterialRef] | None = None,
) -> dict[str, Any]:
    clean_title = _shorten(title.rstrip(" .?!:;"), TITLE_LIMIT)
    clean_message = _shorten(message, MESSAGE_LIMIT)
    cleaned_content = _support_lines(core_content)
    chrome_blocks_used: list[str] = []
    return {
        "slide_key": slide.slide_key,
        "section": slide.section,
        "deck_mode": slide.deck_mode,
        "role": slide_role,
        "slide_intent": slide_intent or slide.intent,
        "title": clean_title,
        "takeaway": clean_message,
        "message": clean_message,
        "pedagogical_goal": slide.pedagogical_goal,
        "concept_ids": concept_ids if concept_ids is not None else list(slide.concept_ids),
        "visual": visual_type,
        "layout_pattern_id": layout_pattern_id,
        "chosen_layout_family": layout_pattern_id,
        "slide_archetype": slide_archetype,
        "primary_visual_structure": primary_visual_structure,
        "chrome_blocks_used": chrome_blocks_used,
        "content_budget_summary": _budget(clean_title, cleaned_content, chrome_blocks_used, primary_visual_structure),
        "duplicate_text_flags": _duplicate_flags(clean_title, clean_message, cleaned_content),
        "authoring_payload": authoring_payload,
        "core_content": cleaned_content,
        "required_assets": authoring_payload.get("required_assets", []),
        "source_material_refs": evidence if evidence is not None else list(slide.evidence),
        "content_tier": (
            ContentTier.APPENDIX_ONLY
            if slide.deck_mode == DeckMode.APPENDIX
            else ContentTier.SUPPORTING_EXAMPLE
            if slide.intent in {SlideIntent.WORKED_EXAMPLE, SlideIntent.APPLICATION_VIGNETTE}
            else ContentTier.LECTURE_CORE
        ),
        "presenter_notes": slide.pedagogical_goal,
    }


def _matrix_spec(
    slide: TeachingPlanSlide,
    *,
    title: str,
    message: str,
    slide_archetype: SlideArchetype,
    columns: list[str],
    rows: list[list[str]],
    core_content: list[str],
    primary_visual_structure: str = "matrix",
    appendix: bool = False,
    slide_intent: SlideIntent | None = None,
    concept_ids: list[str] | None = None,
    evidence: list[SourceMaterialRef] | None = None,
) -> dict[str, Any]:
    authoring_payload = {
        "columns": columns,
        "rows": rows,
        "required_assets": [row[0] for row in rows[:3]],
    }
    return _spec(
        slide=slide,
        title=title,
        message=message,
        slide_role=SlideRole.APPENDIX_EVIDENCE if appendix else SlideRole.COMPARISON,
        visual_type=VisualType.COMPARISON,
        layout_pattern_id="appendix-reference" if appendix else "comparison",
        slide_archetype=slide_archetype,
        primary_visual_structure=primary_visual_structure,
        core_content=core_content,
        authoring_payload=authoring_payload,
        slide_intent=slide_intent,
        concept_ids=concept_ids,
        evidence=evidence,
    )


def _flow_spec(
    slide: TeachingPlanSlide,
    *,
    title: str,
    message: str,
    slide_archetype: SlideArchetype,
    steps: list[dict[str, str]],
    core_content: list[str],
    slide_intent: SlideIntent | None = None,
    concept_ids: list[str] | None = None,
) -> dict[str, Any]:
    authoring_payload = {
        "steps": steps,
        "required_assets": [step["label"] for step in steps[:3]],
    }
    return _spec(
        slide=slide,
        title=title,
        message=message,
        slide_role=SlideRole.PROCESS,
        visual_type=VisualType.PROCESS,
        layout_pattern_id="process-flow",
        slide_archetype=slide_archetype,
        primary_visual_structure="flow",
        core_content=core_content,
        authoring_payload=authoring_payload,
        slide_intent=slide_intent,
        concept_ids=concept_ids,
    )


def _card_spec(
    slide: TeachingPlanSlide,
    *,
    title: str,
    message: str,
    slide_archetype: SlideArchetype,
    cards: list[dict[str, str]],
    core_content: list[str],
    slide_role: SlideRole = SlideRole.ANALYSIS,
    slide_intent: SlideIntent | None = None,
    concept_ids: list[str] | None = None,
) -> dict[str, Any]:
    authoring_payload = {
        "cards": cards,
        "required_assets": [card["label"] for card in cards[:3]],
    }
    visual_type = VisualType.FRAMEWORK
    layout_pattern_id = "concept-explainer"
    if slide_role == SlideRole.COMPARISON:
        visual_type = VisualType.COMPARISON
        layout_pattern_id = "comparison"
    elif slide_role == SlideRole.RECOMMENDATION:
        visual_type = VisualType.TEXT
        layout_pattern_id = "summary"
    return _spec(
        slide=slide,
        title=title,
        message=message,
        slide_role=slide_role,
        visual_type=visual_type,
        layout_pattern_id=layout_pattern_id,
        slide_archetype=slide_archetype,
        primary_visual_structure="callout-cluster",
        core_content=core_content,
        authoring_payload=authoring_payload,
        slide_intent=slide_intent,
        concept_ids=concept_ids,
    )


def _correspondence_rows() -> list[list[str]]:
    return [
        ["Gene / allele", "Encoded decision variable", "Defines what the search can change"],
        ["Genotype", "Candidate string", "Stores the internal search state"],
        ["Phenotype", "Decoded behavior", "Shows what the candidate does in context"],
        ["Natural selection", "Selection operator", "Rewards better candidates without guaranteeing the best one"],
    ]


def _encoding_rows() -> list[list[str]]:
    return [
        ["Gene", "Bit position", "A location in the chromosome carries one design choice"],
        ["Allele", "0 or 1 value", "A value selects one option at that position"],
        ["Chromosome", "10110", "The full string represents one candidate solution"],
        ["Operator effect", "Flip or swap bits", "Variation only works through the chosen encoding"],
    ]


def _operator_rows() -> list[list[str]]:
    return [
        ["Selection", "Before reproduction", "Chooses which candidates get copied forward", "Can collapse diversity too early"],
        ["Crossover", "Parent pairing", "Recombines partial structures from two parents", "Breaks useful blocks if boundaries are misaligned"],
        ["Mutation", "After recombination", "Injects local novelty into the population", "Turns into noise if the rate is too high"],
    ]


def _worked_example_rows() -> list[list[str]]:
    return [
        ["Start population", "A=10110, B=01110, C=11100, D=00101", "Four candidate strings compete"],
        ["Fitness check", "A=7, B=6, C=8, D=3", "Evaluation ranks candidates after decoding"],
        ["Selection + crossover", "Choose C and A, then cross after bit 3", "Parents create 11110 and 10100"],
        ["Mutation + next state", "10100 mutates to 10101", "One generation changes both composition and best score"],
    ]


def _cycle_steps() -> list[dict[str, str]]:
    return [
        {"label": "Encode", "body": "Write each candidate as a chromosome."},
        {"label": "Evaluate", "body": "Decode candidates and score fitness."},
        {"label": "Select", "body": "Bias reproduction toward better candidates."},
        {"label": "Vary", "body": "Crossover and mutation create the next population."},
        {"label": "Repeat", "body": "Stop when improvement or budget runs out."},
    ]


def _mechanism_steps() -> list[dict[str, str]]:
    return [
        {"label": "Pick parents", "body": "Selection keeps higher-fitness candidates in play."},
        {"label": "Recombine", "body": "Crossover mixes compatible parts from the chosen parents."},
        {"label": "Perturb", "body": "Mutation flips one small choice to reopen local alternatives."},
        {"label": "Update state", "body": "The next population is compared against the previous one."},
    ]


def _appendix_cluster_rows(title: str, slides: list[TeachingPlanSlide]) -> list[list[str]]:
    rows: list[list[str]] = []
    for support in slides:
        refs = _appendix_refs_text(support.evidence, limit=2)
        rows.append([_appendix_topic_label(support.title), _appendix_anchor_text(support), refs])
    return rows[:4]


def _appendix_topic_key(title: str) -> str:
    normalized = _title_key(title)
    for prefix in ("source map for ", "evidence summary for ", "evidence cluster: "):
        if normalized.startswith(prefix):
            return normalized.removeprefix(prefix).strip()
    return normalized


def _appendix_topic_label(title: str) -> str:
    label = _norm(title)
    for prefix in ("Source map for ", "Evidence summary for ", "Evidence cluster: "):
        if label.startswith(prefix):
            return label.removeprefix(prefix).strip()
    return label


def _appendix_refs_text(refs: list[SourceMaterialRef], *, limit: int = 2) -> str:
    refs_text = ", ".join(_source_lane(refs, limit=limit))
    return refs_text or "Local source evidence"


def _appendix_anchor_text(slide: TeachingPlanSlide) -> str:
    anchor = slide.main_message or getattr(slide, "one_line_takeaway", "") or _appendix_topic_label(slide.title)
    normalized = _title_key(anchor)
    if normalized.startswith(("this appendix maps where ", "appendix source support for ")):
        anchor = APPENDIX_TOPIC_MESSAGES.get(_appendix_topic_key(slide.title), anchor)
    return _shorten(anchor, BODY_LIMIT)


def _appendix_group_message(grouped_slides: list[TeachingPlanSlide], *, kind: str) -> str:
    labels = [_appendix_topic_label(slide.title) for slide in grouped_slides]
    topic_keys = [_appendix_topic_key(slide.title) for slide in grouped_slides]
    if len(labels) > 2:
        label_clause = f"{', '.join(labels[:-1])}, and {labels[-1]}"
    elif len(labels) == 2:
        label_clause = f"{labels[0]} and {labels[1]}"
    else:
        label_clause = labels[0]
    if len(grouped_slides) == 1 and kind == "themed":
        return _shorten(
            f"Use this cluster to connect {labels[0].lower()} back to the main story with explicit page anchors.",
            MESSAGE_LIMIT,
        )
    if len(grouped_slides) == 1 and kind == "source-location":
        return _shorten(
            f"Use the matrix to connect {labels[0].lower()} back to exact pages and the claim each page supports.",
            MESSAGE_LIMIT,
        )
    if len(grouped_slides) == 1 and kind == "source-map":
        return _shorten(
            f"Use this cross-reference map to link {labels[0].lower()} back to the main-story claim and its cited pages.",
            MESSAGE_LIMIT,
        )
    if len(grouped_slides) == 1:
        return _shorten(APPENDIX_TOPIC_MESSAGES.get(topic_keys[0], _appendix_anchor_text(grouped_slides[0])), MESSAGE_LIMIT)
    if kind == "comparison" and len(grouped_slides) >= 2:
        return _shorten(
            f"Read {labels[0]} against {labels[1]} to see where the analogy stays useful and where the roles diverge.",
            MESSAGE_LIMIT,
        )
    if kind == "source-location":
        return _shorten(
            f"Use the cited pages to trace how {label_clause} anchor one linked teaching claim.",
            MESSAGE_LIMIT,
        )
    if kind == "source-map":
        return _shorten(
            f"Cross-reference the cited pages to connect {label_clause} back to the main story.",
            MESSAGE_LIMIT,
        )
    return _shorten(
        f"Use the cited pages together to track {label_clause} as one source-backed theme.",
        MESSAGE_LIMIT,
    )


def _appendix_cards(slides: list[TeachingPlanSlide], *, excerpt_style: bool = False) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for support in slides[:3]:
        label = _appendix_topic_label(support.title)
        refs = _appendix_refs_text(support.evidence, limit=1)
        body_prefix = refs if excerpt_style else label
        if excerpt_style:
            body = _shorten(f"{_appendix_anchor_text(support)} Source anchor: {refs}.", BODY_LIMIT)
            cards.append({"label": body_prefix, "body": body})
        else:
            body = _shorten(f"{_appendix_anchor_text(support)} Sources: {refs}.", BODY_LIMIT)
            cards.append({"label": body_prefix, "body": body})
    return cards


def _appendix_source_location_rows(slides: list[TeachingPlanSlide]) -> list[list[str]]:
    rows: list[list[str]] = []
    for support in slides[:4]:
        rows.append(
            [
                _appendix_topic_label(support.title),
                _appendix_refs_text(support.evidence, limit=2),
                _appendix_anchor_text(support),
            ]
        )
    return rows


def _appendix_comparison_rows(slides: list[TeachingPlanSlide]) -> list[list[str]]:
    left = slides[0]
    right = slides[1] if len(slides) > 1 else slides[0]
    return [
        ["Focus", _appendix_anchor_text(left), _appendix_anchor_text(right)],
        ["Source pointer", _appendix_refs_text(left.evidence, limit=2), _appendix_refs_text(right.evidence, limit=2)],
        [
            "Teaching use",
            _shorten(f"Use when the lecture needs the {_appendix_topic_label(left.title).lower()} anchor.", BODY_LIMIT),
            _shorten(f"Use when the lecture needs the {_appendix_topic_label(right.title).lower()} anchor.", BODY_LIMIT),
        ],
    ]


def _appendix_source_map_rows(slides: list[TeachingPlanSlide]) -> list[list[str]]:
    rows: list[list[str]] = []
    for support in slides[:4]:
        rows.append(
            [
                _appendix_topic_label(support.title),
                _appendix_refs_text(support.evidence, limit=3),
                _appendix_anchor_text(support),
            ]
        )
    return rows


def _appendix_card_spec(
    slide: TeachingPlanSlide,
    *,
    title: str,
    message: str,
    slide_archetype: SlideArchetype,
    cards: list[dict[str, str]],
    core_content: list[str],
    primary_visual_structure: str,
    concept_ids: list[str] | None = None,
    evidence: list[SourceMaterialRef] | None = None,
) -> dict[str, Any]:
    return _spec(
        slide=slide,
        title=title,
        message=message,
        slide_role=SlideRole.APPENDIX_EVIDENCE,
        visual_type=VisualType.COMPARISON,
        layout_pattern_id="appendix-reference",
        slide_archetype=slide_archetype,
        primary_visual_structure=primary_visual_structure,
        core_content=core_content,
        authoring_payload={
            "cards": cards,
            "required_assets": [card["label"] for card in cards[:3]],
        },
        slide_intent=SlideIntent.APPENDIX_EVIDENCE_SUPPORT,
        concept_ids=concept_ids,
        evidence=evidence,
    )


def _appendix_authored_spec(
    slide: TeachingPlanSlide,
    grouped_slides: list[TeachingPlanSlide],
    *,
    title: str,
    kind: str,
) -> dict[str, Any]:
    concept_ids = [concept_id for item in grouped_slides for concept_id in item.concept_ids]
    evidence = [ref for item in grouped_slides for ref in item.evidence]
    message = _appendix_group_message(grouped_slides, kind=kind)
    if kind == "themed":
        return _appendix_card_spec(
            slide,
            title=title,
            message=message,
            slide_archetype=SlideArchetype.APPENDIX_THEMED_EVIDENCE_CLUSTER,
            cards=_appendix_cards(grouped_slides),
            core_content=["Keep appendix support theme-led so page-level traceability survives without clone cards."],
            primary_visual_structure="themed-evidence-cluster",
            concept_ids=concept_ids,
            evidence=evidence,
        )
    if kind == "annotated-excerpt":
        return _appendix_card_spec(
            slide,
            title=title,
            message=message,
            slide_archetype=SlideArchetype.APPENDIX_ANNOTATED_EXCERPT_CLUSTER,
            cards=_appendix_cards(grouped_slides, excerpt_style=True),
            core_content=["Use page-labeled excerpt cards only when the wording itself helps the support case."],
            primary_visual_structure="annotated-excerpt-cluster",
            concept_ids=concept_ids,
            evidence=evidence,
        )
    if kind == "comparison":
        left_title = _appendix_topic_label(grouped_slides[0].title)
        right_title = _appendix_topic_label(grouped_slides[1].title) if len(grouped_slides) > 1 else "Related source"
        return _matrix_spec(
            slide,
            title=title,
            message=message,
            slide_archetype=SlideArchetype.APPENDIX_COMPARISON_EVIDENCE_CLUSTER,
            columns=["Axis", left_title, right_title],
            rows=_appendix_comparison_rows(grouped_slides),
            core_content=["Comparison evidence slides should make the contrast explicit instead of restating one noun slot."],
            primary_visual_structure="comparison-evidence-matrix",
            appendix=True,
            slide_intent=SlideIntent.APPENDIX_EVIDENCE_SUPPORT,
            concept_ids=concept_ids,
            evidence=evidence,
        )
    if kind == "source-map":
        return _matrix_spec(
            slide,
            title=title,
            message=message,
            slide_archetype=SlideArchetype.APPENDIX_SOURCE_MAP,
            columns=["Cross-reference", "Where in source", "What it anchors"],
            rows=_appendix_source_map_rows(grouped_slides),
            core_content=["Reserve source-map layouts for cross-reference work, not for every appendix topic."],
            primary_visual_structure="source-map",
            appendix=True,
            slide_intent=SlideIntent.APPENDIX_EVIDENCE_SUPPORT,
            concept_ids=concept_ids,
            evidence=evidence,
        )
    return _matrix_spec(
        slide,
        title=title,
        message=message,
        slide_archetype=SlideArchetype.APPENDIX_SOURCE_LOCATION_MATRIX,
        columns=["Theme anchor", "Where in source", "What to inspect"],
        rows=_appendix_source_location_rows(grouped_slides),
        core_content=["Make source pointers explicit so appendix evidence is traceable without repetitive chrome."],
        primary_visual_structure="source-location-matrix",
        appendix=True,
        slide_intent=SlideIntent.APPENDIX_EVIDENCE_SUPPORT,
        concept_ids=concept_ids,
        evidence=evidence,
    )


def _concept_mapping_rows(concept_label: str, message: str) -> list[list[str]]:
    return [
        [concept_label, "Algorithmic reading", _shorten(message, BODY_LIMIT)],
        ["Encoding choice", "What can vary", "The representation decides which local moves are available"],
        ["Teaching consequence", "What to emphasize", "Explain what changes when the GA manipulates the concept"],
    ]


def _repeat_variant_spec(
    slide: TeachingPlanSlide,
    *,
    title_key: str,
    concept_label: str,
    occurrence: int,
) -> dict[str, Any] | None:
    if occurrence > 1 and title_key == "biology to ga correspondence as a bridge":
        return _card_spec(
            slide,
            title="Synthesis: the full correspondence chain",
            message="The analogy is most useful when the full chain from encoding to evaluation to selection is visible at once.",
            slide_archetype=SlideArchetype.SYNTHESIS_INTEGRATION,
            slide_intent=SlideIntent.SUMMARY_INTEGRATION,
            cards=[
                {"label": "Representation", "body": "Genes, alleles, and genotype explain how a candidate is stored."},
                {"label": "Evaluation", "body": "Phenotype and fitness explain how the stored state becomes a score."},
                {"label": "Selection", "body": "Selection pressure closes the loop by deciding which scores reproduce."},
            ],
            core_content=["Use the second pass to integrate the chain instead of repeating the same bridge card."],
            slide_role=SlideRole.RECOMMENDATION,
        )
    if occurrence > 1 and title_key == "fitness as a bridge":
        return _flow_spec(
            slide,
            title="Decoding links representation to selection",
            message="A chromosome matters only after decoding, evaluation, and ranking connect it back to reproduction.",
            slide_archetype=SlideArchetype.STEP_BY_STEP_MECHANISM,
            slide_intent=SlideIntent.MECHANISM_WALKTHROUGH,
            steps=[
                {"label": "Decode", "body": "Turn the stored chromosome into behavior in the task setting."},
                {"label": "Score", "body": "Measure performance against the fitness criterion."},
                {"label": "Compare", "body": "Rank the current candidates against each other."},
                {"label": "Select", "body": "Bias reproduction using the scores, not the raw strings."},
            ],
            core_content=["The second pass should connect evaluation to selection explicitly."],
        )
    if occurrence > 1 and title_key == "representation and encoding as a bridge":
        return _matrix_spec(
            slide,
            title="Encoding boundaries decide crossover quality",
            message="Crossover and mutation help only when the encoding partitions decisions in a way the operators can preserve.",
            slide_archetype=SlideArchetype.COMPARISON_MATRIX,
            slide_intent=SlideIntent.COMPARISON_TRADEOFF,
            columns=["Encoding choice", "Operator effect", "Failure mode"],
            rows=[
                ["Meaningful segments", "Crossover can preserve partial structure", "Useful blocks survive recombination"],
                ["Arbitrary bit order", "Crossover cuts across unrelated decisions", "Building blocks are destroyed"],
                ["Sparse local moves", "Mutation explores carefully", "The search stalls if the alphabet is too narrow"],
            ],
            core_content=["Use the repeated slot to compare good and bad operator geometry."],
            primary_visual_structure="operator-matrix",
        )
    if occurrence > 1 and title_key == "natural selection as a bridge":
        return _card_spec(
            slide,
            title="Pressure settings move the convergence dial",
            message="Selection pressure is a tuning choice that trades faster convergence against the risk of losing diversity too soon.",
            slide_archetype=SlideArchetype.LIMITATION_PITFALL_CALLOUT,
            slide_intent=SlideIntent.COMPARISON_TRADEOFF,
            cards=[
                {"label": "More pressure", "body": "Improves short-run progress when the population is still diverse."},
                {"label": "Less pressure", "body": "Keeps alternatives alive when premature convergence is a risk."},
                {"label": "Teaching point", "body": "The analogy helps only if students still see the pressure as a design knob."},
            ],
            core_content=["The repeated slot should expose the tuning lever, not restate the analogy."],
            slide_role=SlideRole.COMPARISON,
        )
    if occurrence > 1 and title_key == "genotype as a bridge":
        return _card_spec(
            slide,
            title="The chromosome is memory, not merit",
            message="The genotype stores the current search state, but it does not become meaningful until the task environment reveals what it does.",
            slide_archetype=SlideArchetype.SYNTHESIS_INTEGRATION,
            slide_intent=SlideIntent.SUMMARY_INTEGRATION,
            cards=[
                {"label": "Storage", "body": "The chromosome records the current candidate in internal form."},
                {"label": "Expression", "body": "Decoding turns that internal form into task behavior."},
                {"label": "Consequence", "body": "Operators act on the stored state even though selection responds to external performance."},
            ],
            core_content=["Keep the distinction between stored state and external merit explicit."],
            slide_role=SlideRole.ANALYSIS,
        )
    if occurrence > 1 and title_key == "exploration and exploitation tradeoff tradeoffs":
        return _matrix_spec(
            slide,
            title="Search pressure changes over the run",
            message="The right exploration-exploitation balance changes as the population narrows, so one fixed setting rarely stays ideal.",
            slide_archetype=SlideArchetype.COMPARISON_MATRIX,
            slide_intent=SlideIntent.COMPARISON_TRADEOFF,
            columns=["Run phase", "What the search needs", "What to watch"],
            rows=[
                ["Early run", "Broad exploration", "Avoid wiping out diversity too quickly"],
                ["Middle run", "Selective pressure with repair", "Preserve promising structure while still opening alternatives"],
                ["Late run", "Careful exploitation", "Do not add so much variation that the search becomes noise again"],
            ],
            core_content=["Use the second pass to show how the tradeoff shifts over time."],
            primary_visual_structure="comparison-matrix",
        )
    if occurrence > 1 and title_key == "phenotype as a bridge":
        return _matrix_spec(
            slide,
            title="Decoded behavior is where feasibility appears",
            message="Phenotype matters because feasibility and performance appear only after the internal representation is expressed in context.",
            slide_archetype=SlideArchetype.TWO_COLUMN_MAPPING_TABLE,
            slide_intent=SlideIntent.MAPPING_BRIDGE,
            columns=["State", "What it reveals", "Design consequence"],
            rows=[
                ["Genotype", "Internal encoding", "Operators change this state directly"],
                ["Phenotype", "Observed behavior", "Feasibility and constraints show up here"],
                ["Fitness", "Scored performance", "Selection acts on the score that follows the behavior"],
            ],
            core_content=["Use the repeated slot to separate phenotype from both genotype and fitness."],
            primary_visual_structure="mapping-table",
        )
    if occurrence > 1 and title_key == "genes as a bridge":
        return _matrix_spec(
            slide,
            title="Building blocks depend on linkage",
            message="Useful partial structures survive only when related decisions sit close enough together for crossover to preserve them.",
            slide_archetype=SlideArchetype.COMPARISON_MATRIX,
            slide_intent=SlideIntent.COMPARISON_TRADEOFF,
            columns=["Representation", "What crossover sees", "Result"],
            rows=[
                ["Aligned linkage", "Related decisions stay together", "Reusable blocks can survive"],
                ["Broken linkage", "Related decisions are scattered", "Crossover breaks structure more often than it helps"],
                ["Teaching response", "Show the boundaries", "Explain operator success in terms of representation geometry"],
            ],
            core_content=["The repeated slot should show linkage as geometry, not as folklore."],
            primary_visual_structure="comparison-matrix",
        )
    if occurrence > 1 and title_key == "limitations pitfalls":
        return _card_spec(
            slide,
            title="Keep the metaphor subordinate to design criteria",
            message="The analogy is useful only when it still points back to representation, evaluation, and operator settings that the designer can control.",
            slide_archetype=SlideArchetype.LIMITATION_PITFALL_CALLOUT,
            slide_intent=SlideIntent.MISCONCEPTION_PITFALL,
            cards=[
                {"label": "Keep", "body": "Retain the analogy when it clarifies a role or a mechanism."},
                {"label": "Drop", "body": "Drop it when it starts replacing concrete operator or encoding choices."},
                {"label": "Use", "body": "End the slide with the actual tuning or representation implication."},
            ],
            core_content=["Use the repeated slot to discipline the metaphor rather than repeat the warning."],
            slide_role=SlideRole.COMPARISON,
        )
    if occurrence > 1 and title_key == "schema or building-block intuition as a bridge":
        return _card_spec(
            slide,
            title="Schema intuition is really an encoding claim",
            message="The schema story helps only if the encoding makes partial solutions coherent enough for crossover to preserve.",
            slide_archetype=SlideArchetype.SYNTHESIS_INTEGRATION,
            slide_intent=SlideIntent.SUMMARY_INTEGRATION,
            cards=[
                {"label": "Assumption", "body": "Useful substructures must correspond to coherent chromosome segments."},
                {"label": "Breakdown", "body": "Poor linkage destroys the very structure the schema story assumes."},
                {"label": "Design move", "body": "Choose an encoding that makes useful blocks visible to the operator."},
            ],
            core_content=["Treat schema intuition as a representation claim with operator consequences."],
            slide_role=SlideRole.ANALYSIS,
        )
    if occurrence > 1 and title_key == "phenotype to fitness bridge as a bridge":
        return _flow_spec(
            slide,
            title="Scores connect behavior back to reproduction",
            message="Evaluation closes the loop by turning observed behavior into a score that the selection operator can use.",
            slide_archetype=SlideArchetype.PROCESS_FLOW,
            slide_intent=SlideIntent.MECHANISM_WALKTHROUGH,
            steps=[
                {"label": "Express", "body": "Decode the chromosome into task behavior."},
                {"label": "Measure", "body": "Compare that behavior against the fitness rule."},
                {"label": "Rank", "body": "Translate the score into relative reproductive advantage."},
                {"label": "Reproduce", "body": "Selection biases which structures survive into the next generation."},
            ],
            core_content=["Use the repeated slot to show the closed loop from behavior to reproduction."],
        )
    if occurrence > 1 and title_key == "applications in practice":
        return _card_spec(
            slide,
            title="Engineering use cases share one pattern",
            message="Good GA applications tend to combine hard-to-parameterize search spaces with cheap candidate-by-candidate evaluation.",
            slide_archetype=SlideArchetype.APPLICATION_VIGNETTE,
            slide_intent=SlideIntent.APPLICATION_VIGNETTE,
            cards=[
                {"label": "Search shape", "body": "Discrete, mixed, or irregular decision spaces."},
                {"label": "Evaluation shape", "body": "Candidates can still be decoded and scored one by one."},
                {"label": "Decision rule", "body": "Use a GA when awkward search geometry matters more than perfect local gradients."},
            ],
            core_content=["Use the repeated slot to explain the shared pattern behind the examples."],
            slide_role=SlideRole.ANALYSIS,
        )
    if occurrence > 1 and title_key == "variation tradeoffs":
        return _card_spec(
            slide,
            title="Variation rate sets the repair-versus-noise tradeoff",
            message="Variation is useful when it repairs stagnation, but it becomes noise when the rate is too high for structure to persist.",
            slide_archetype=SlideArchetype.LIMITATION_PITFALL_CALLOUT,
            slide_intent=SlideIntent.COMPARISON_TRADEOFF,
            cards=[
                {"label": "Too little", "body": "The search cannot escape local stagnation."},
                {"label": "Too much", "body": "Inherited structure is erased faster than it can accumulate."},
                {"label": "Practical use", "body": "Treat variation rate as a control knob that depends on population state."},
            ],
            core_content=["Use the repeated slot to show variation as a rate choice, not a slogan."],
            slide_role=SlideRole.COMPARISON,
        )
    if occurrence > 1 and title_key == "alleles as a bridge":
        return _matrix_spec(
            slide,
            title="Allowed allele values define the move set",
            message="The search alphabet matters because it determines which local changes the GA can propose at all.",
            slide_archetype=SlideArchetype.TWO_COLUMN_MAPPING_TABLE,
            slide_intent=SlideIntent.MAPPING_BRIDGE,
            columns=["Allele design", "Local move", "Implication"],
            rows=[
                ["Binary allele", "Flip between two states", "Fast, simple local variation"],
                ["Ordinal allele", "Step between ordered values", "Supports graded local moves"],
                ["Symbolic allele", "Jump between categories", "Needs careful operator design to remain meaningful"],
            ],
            core_content=["Use the repeated slot to turn allele choice into a concrete move-set decision."],
            primary_visual_structure="mapping-table",
        )
    if occurrence == 1 and title_key in {"genes", "alleles", "phenotype"}:
        return _matrix_spec(
            slide,
            title=f"{concept_label} as an algorithm design choice",
            message=slide.main_message,
            slide_archetype=SlideArchetype.TWO_COLUMN_MAPPING_TABLE,
            slide_intent=SlideIntent.MAPPING_BRIDGE,
            columns=["Concept", "GA reading", "Design consequence"],
            rows=_concept_mapping_rows(concept_label, slide.main_message),
            core_content=["Use the concept pass to expose a concrete design implication instead of repeating a text card."],
            primary_visual_structure="mapping-table",
        )
    if occurrence == 1 and title_key == "variation":
        return _flow_spec(
            slide,
            title="Variation changes the population in two ways",
            message="Variation creates both recombination and mutation moves, so it is better taught as a small mechanism than as a generic card.",
            slide_archetype=SlideArchetype.PROCESS_FLOW,
            slide_intent=SlideIntent.MECHANISM_WALKTHROUGH,
            steps=[
                {"label": "Recombine", "body": "Crossover mixes partial structure from selected parents."},
                {"label": "Perturb", "body": "Mutation reopens local alternatives when the pool narrows."},
                {"label": "Compare", "body": "The population is judged again after those changes land."},
            ],
            core_content=["Use the concept pass to show how variation actually changes state."],
        )
    if occurrence == 1 and title_key == "natural selection":
        return _card_spec(
            slide,
            title="Selection is the population filter",
            message="Natural selection maps into a designed filtering rule that decides which candidates get copied forward.",
            slide_archetype=SlideArchetype.LIMITATION_PITFALL_CALLOUT,
            slide_intent=SlideIntent.COMPARISON_TRADEOFF,
            cards=[
                {"label": "What it keeps", "body": "Higher-scoring candidates are more likely to reproduce."},
                {"label": "What it risks", "body": "Excess pressure collapses diversity before useful alternatives can combine."},
                {"label": "What the designer controls", "body": "The selection rule, pressure, and replacement policy."},
            ],
            core_content=["Use the concept pass to show selection as a controllable filter."],
            slide_role=SlideRole.COMPARISON,
        )
    return None


def _rewrite_bank(title: str) -> dict[str, str] | None:
    key = _title_key(title)
    bank = {
        "genetic algorithm in the cycle": {
            "title": "Population search repeats across generations",
            "message": "A GA makes progress by comparing one population against the next, not by taking one perfect step.",
        },
        "one generation cycle in the cycle": {
            "title": "One loop is useful only if the next loop can improve it",
            "message": "The generation cycle matters because each round changes what the next round can inherit or repair.",
        },
        "fitness as a bridge": {
            "title": "Fitness is scored after decoding",
            "message": "The chromosome stores a candidate, but fitness appears only after that candidate is tested in context.",
        },
        "biology to ga correspondence as a bridge": {
            "title": "The analogy maps roles, not literal biology",
            "message": "The biology to GA bridge works because each biological role has a matching algorithmic job.",
        },
        "representation and encoding as a bridge": {
            "title": "Encoding choices shape what operators can do",
            "message": "A good encoding makes crossover and mutation act on meaningful parts instead of random fragments.",
        },
        "natural selection as a bridge": {
            "title": "Selection pressure is tuned, not natural",
            "message": "A GA designer chooses how much pressure to apply, so selection is a controllable operator rather than a literal natural process.",
        },
        "genotype as a bridge": {
            "title": "Genotype stores search state",
            "message": "The genotype matters because it carries the structure that operators will preserve, swap, or mutate.",
        },
        "phenotype as a bridge": {
            "title": "Phenotype shows whether a candidate actually works",
            "message": "Decoding exposes feasibility and performance, which is why phenotype sits between representation and fitness.",
        },
        "genes as a bridge": {
            "title": "Gene boundaries control reusable building blocks",
            "message": "If the representation groups decisions poorly, crossover will destroy the pieces you hoped to reuse.",
        },
        "schema or building-block intuition as a bridge": {
            "title": "Building blocks survive only under aligned encoding",
            "message": "Schema intuition helps only when the encoding lets crossover preserve useful partial structure.",
        },
        "phenotype to fitness bridge as a bridge": {
            "title": "Evaluation makes phenotype visible to selection",
            "message": "Selection never sees the raw chromosome directly; it sees the score produced after decoding and evaluation.",
        },
        "alleles as a bridge": {
            "title": "Alleles define the search alphabet",
            "message": "The set of allowed allele values decides which local moves the GA can even attempt.",
        },
        "exploration and exploitation tradeoff tradeoffs": {
            "title": "Exploration and exploitation must stay in tension",
            "message": "A GA stagnates when it exploits too early and drifts when it explores without keeping useful structure.",
        },
        "variation tradeoffs": {
            "title": "Variation helps until it destroys inherited structure",
            "message": "Variation is essential, but too much variation erases the partial solutions you were trying to preserve.",
        },
        "applications in practice": {
            "title": "A GA is useful when the search space is awkward",
            "message": "GAs earn their cost when the design space is combinatorial, noisy, or resistant to clean gradients.",
        },
        "limitations pitfalls": {
            "title": "The analogy helps until it hides design choices",
            "message": "The biology story is useful only if it still points back to encoding, selection pressure, and operator tuning choices.",
        },
        "crossover in the cycle": {
            "title": "Crossover preserves some patterns and breaks others",
            "message": "Crossover is valuable only when the encoding lines up with reusable substructures in the candidate.",
        },
        "mutation operator in the cycle": {
            "title": "Mutation operator restores diversity",
            "message": "Mutation matters most when the population is converging too quickly to one narrow region.",
        },
        "selection operator in the cycle": {
            "title": "Selection trades speed for diversity",
            "message": "Stronger selection accelerates progress early but can wipe out the diversity needed later.",
        },
    }
    return bank.get(key)


def _author_main_slide(
    slide: TeachingPlanSlide,
    nodes_by_id: dict[str, ConceptNode],
    *,
    occurrence: int,
) -> dict[str, Any] | None:
    title_key = _title_key(slide.title)
    primary_concept = slide.concept_ids[0] if slide.concept_ids else None
    concept_label = _concept_label(primary_concept, nodes_by_id)

    if occurrence > 1 and title_key in SKIP_REPEAT_KEYS:
        return None

    variant = _repeat_variant_spec(
        slide,
        title_key=title_key,
        concept_label=concept_label,
        occurrence=occurrence,
    )
    if variant is not None:
        return variant

    if slide.intent == SlideIntent.ORIENTATION and slide.slide_key == "orientation-title":
        return _spec(
            slide=slide,
            title=slide.title,
            message=slide.main_message,
            slide_role=SlideRole.TITLE,
            visual_type=VisualType.TEXT,
            layout_pattern_id="cover",
            slide_archetype=SlideArchetype.TITLE_ORIENTATION,
            primary_visual_structure="title-block",
            core_content=["Start from biological intuition before algorithm detail."],
            authoring_payload={"required_assets": []},
        )

    if slide.title == "Biology to GA teaching arc":
        return _flow_spec(
            slide,
            title=slide.title,
            message="The lecture moves from biology, to mapping, to operators, to examples, and then to limits.",
            slide_archetype=SlideArchetype.PROCESS_FLOW,
            slide_intent=SlideIntent.ORIENTATION,
            steps=[
                {"label": "Biology", "body": "Genes, alleles, genotype, phenotype, and natural selection"},
                {"label": "Map", "body": "Translate those roles into representation, fitness, and operators"},
                {"label": "Operate", "body": "Follow selection, crossover, and mutation through one loop"},
                {"label": "Test", "body": "Use a toy population to see one generation change state"},
                {"label": "Bound", "body": "End with limitations, tradeoffs, and practical use cases"},
            ],
            core_content=["Use the arc as structure, not as visible chrome."],
        )

    if slide.title == "Why the analogy helps":
        return _card_spec(
            slide,
            title=slide.title,
            message="The analogy helps because it connects representation, evaluation, and variation inside one teaching frame.",
            slide_archetype=SlideArchetype.ANCHOR_CONCEPT_CARD,
            slide_intent=SlideIntent.ANCHOR_CONCEPT,
            cards=[
                {"label": "Representation", "body": "Genes and alleles explain why a candidate must be written in some encoding."},
                {"label": "Evaluation", "body": "Phenotype explains why fitness appears only after decoding and testing."},
                {"label": "Variation", "body": "Selection, crossover, and mutation each get a distinct algorithmic role."},
            ],
            core_content=["Use the analogy to clarify design choices, not to decorate the lecture."],
        )

    if slide.title == "Biology to GA map":
        return _matrix_spec(
            slide,
            title=slide.title,
            message="The biology to GA correspondence maps genes, genotype, phenotype, and selection into GA optimization roles.",
            slide_archetype=SlideArchetype.CORRESPONDENCE_MATRIX,
            slide_intent=SlideIntent.MAPPING_BRIDGE,
            columns=["Biology term", "GA role", "What the mapping clarifies"],
            rows=_correspondence_rows(),
            core_content=["This is a role map, not a vague optimization metaphor."],
            primary_visual_structure="correspondence-matrix",
        )

    if slide.title == "Genes and alleles become an encoding":
        return _matrix_spec(
            slide,
            title=slide.title,
            message="Encoding answers how genes and alleles are written into a candidate string that operators can manipulate.",
            slide_archetype=SlideArchetype.TWO_COLUMN_MAPPING_TABLE,
            slide_intent=SlideIntent.MAPPING_BRIDGE,
            columns=["Biology unit", "Encoding view", "Why the choice matters"],
            rows=_encoding_rows(),
            core_content=["The encoding decides what a small mutation or crossover actually changes."],
            primary_visual_structure="mapping-table",
        )

    if slide.title == "Worked example with a toy population":
        return _matrix_spec(
            slide,
            title=slide.title,
            message="A toy population makes the state change from one generation explicit instead of abstract.",
            slide_archetype=SlideArchetype.WORKED_EXAMPLE_STATE_TABLE,
            slide_intent=SlideIntent.WORKED_EXAMPLE,
            columns=["Stage", "Population state", "Teaching point"],
            rows=_worked_example_rows(),
            core_content=["Keep the example small enough that every state change can be read in one pass."],
            primary_visual_structure="state-table",
        )

    if slide.title == "Run one generation on the toy example":
        return _flow_spec(
            slide,
            title="How one toy population changes",
            message="Selection, crossover, and mutation change the toy population in a fixed order that students can trace.",
            slide_archetype=SlideArchetype.STEP_BY_STEP_MECHANISM,
            slide_intent=SlideIntent.MECHANISM_WALKTHROUGH,
            steps=_mechanism_steps(),
            core_content=["Use the flow to connect the operator roles back to the worked example state table."],
        )

    if slide.title == "One generation cycle":
        return _flow_spec(
            slide,
            title=slide.title,
            message="A GA loop writes candidates, scores them, selects parents, varies them, and repeats on the next population.",
            slide_archetype=SlideArchetype.PROCESS_FLOW,
            slide_intent=SlideIntent.MECHANISM_WALKTHROUGH,
            steps=_cycle_steps(),
            core_content=["One slide should carry the whole loop before operator detail is split out."],
        )

    if slide.title == "Operators play different roles":
        return _matrix_spec(
            slide,
            title="Operators in one generation",
            message="Selection, crossover, and mutation matter for different reasons, so they should not be taught as one blended action.",
            slide_archetype=SlideArchetype.COMPARISON_MATRIX,
            slide_intent=SlideIntent.COMPARISON_TRADEOFF,
            columns=["Operator", "Where it acts", "What it changes", "Main risk"],
            rows=_operator_rows(),
            core_content=["The cycle is clearer when each operator gets one distinct job."],
            primary_visual_structure="operator-matrix",
        )

    rewrite = _rewrite_bank(slide.title)
    if rewrite is not None:
        if title_key in {"exploration and exploitation tradeoff tradeoffs", "variation tradeoffs", "limitations pitfalls", "selection operator in the cycle"}:
            return _card_spec(
                slide,
                title=rewrite["title"],
                message=rewrite["message"],
                slide_archetype=SlideArchetype.LIMITATION_PITFALL_CALLOUT,
                cards=[
                    {"label": "Benefit", "body": "The operator or concept helps one part of the search process."},
                    {"label": "Failure mode", "body": "The same move can erase useful structure or collapse diversity when overused."},
                    {"label": "Design response", "body": "Tune pressure, rates, and representation together rather than in isolation."},
                ],
                core_content=["Keep the limitation anchored in a design choice the audience can control."],
                slide_role=SlideRole.COMPARISON,
                slide_intent=SlideIntent.COMPARISON_TRADEOFF,
                concept_ids=list(slide.concept_ids),
            )
        if title_key == "applications in practice":
            return _card_spec(
                slide,
                title=rewrite["title"],
                message=rewrite["message"],
                slide_archetype=SlideArchetype.APPLICATION_VIGNETTE,
                cards=[
                    {"label": "Good fit", "body": "Discrete design spaces, mixed constraints, and awkward objective surfaces."},
                    {"label": "Poor fit", "body": "Problems with clean gradients and trustworthy local methods."},
                    {"label": "Teaching point", "body": "Tie the analogy back to method fit, not to folklore."},
                ],
                core_content=["Applications should explain fit criteria instead of listing domains."],
                slide_role=SlideRole.ANALYSIS,
                slide_intent=SlideIntent.APPLICATION_VIGNETTE,
                concept_ids=list(slide.concept_ids),
            )
        if title_key in {
            "fitness as a bridge",
            "biology to ga correspondence as a bridge",
            "representation and encoding as a bridge",
            "natural selection as a bridge",
            "genotype as a bridge",
            "phenotype as a bridge",
            "genes as a bridge",
            "schema or building-block intuition as a bridge",
            "phenotype to fitness bridge as a bridge",
            "alleles as a bridge",
        }:
            return _matrix_spec(
                slide,
                title=rewrite["title"],
                message=rewrite["message"],
                slide_archetype=SlideArchetype.CORRESPONDENCE_MATRIX,
                slide_intent=SlideIntent.MAPPING_BRIDGE,
                columns=["Concept", "Clarifies", "What to watch"],
                rows=[
                    [concept_label, "Representation or operator role", "Keep the analogy at the role level"],
                    ["Encoding", "What can change", "Misaligned boundaries break useful structure"],
                    ["Evaluation", "What counts as better", "Fitness still depends on the external task"],
                ],
                core_content=["Use the bridge to expose a design decision rather than to repeat the analogy."],
                primary_visual_structure="matrix",
            )
        return _card_spec(
            slide,
            title=rewrite["title"],
            message=rewrite["message"],
            slide_archetype=SlideArchetype.ANCHOR_CONCEPT_CARD,
                cards=[
                    {"label": concept_label, "body": _shorten(slide.main_message, BODY_LIMIT)},
                    {"label": "Design consequence", "body": rewrite["message"]},
                    {"label": "Keep in view", "body": "Connect the concept back to representation, evaluation, or operator behavior."},
                ],
                core_content=["The authored slide should deepen the idea instead of repeating the title shell."],
                slide_intent=SlideIntent.ANCHOR_CONCEPT,
                concept_ids=list(slide.concept_ids),
            )

    if slide.intent == SlideIntent.MISCONCEPTION_PITFALL:
        return _card_spec(
            slide,
            title="Where the analogy stops helping",
            message="The biology story can guide intuition, but the real design work still happens in encoding and operator tuning choices.",
            slide_archetype=SlideArchetype.LIMITATION_PITFALL_CALLOUT,
            cards=[
                {"label": "Useful shortcut", "body": "The analogy names the roles of representation, selection, and variation."},
                {"label": "Where it breaks", "body": "A GA does not inherit literal genes, phenotypes, or natural environments."},
                {"label": "Design response", "body": "Bring every abstract analogy back to a controllable algorithmic choice."},
            ],
            core_content=["Limits should be shown as design consequences, not as a generic warning card."],
            slide_role=SlideRole.COMPARISON,
        )

    if slide.intent == SlideIntent.APPLICATION_VIGNETTE:
        return _card_spec(
            slide,
            title="When a GA is a useful fit",
            message="Use a GA when the search space is hard to parameterize cleanly but still easy to evaluate candidate by candidate.",
            slide_archetype=SlideArchetype.APPLICATION_VIGNETTE,
            cards=[
                {"label": "Typical fit", "body": "Discrete design variables, mixed constraints, and noisy objectives."},
                {"label": "Typical miss", "body": "Smooth problems with trustworthy gradients and fast local methods."},
                {"label": "Decision rule", "body": "Connect the analogy to method selection, not to a generic popularity claim."},
            ],
            core_content=["Applications should explain fit criteria instead of listing domains."],
            slide_intent=SlideIntent.APPLICATION_VIGNETTE,
        )

    if slide.intent == SlideIntent.COMPARISON_TRADEOFF:
        return _card_spec(
            slide,
            title=slide.title,
            message=slide.main_message,
            slide_archetype=SlideArchetype.COMPARISON_MATRIX,
            cards=[
                {"label": "Gain", "body": "The tuning choice helps one part of the search process."},
                {"label": "Cost", "body": "The same choice weakens another part of the search process."},
                {"label": "Use it when", "body": "Tie the tradeoff to one concrete search condition rather than to slogans."},
            ],
            core_content=["Tradeoffs should expose one lever, one upside, and one downside."],
            slide_role=SlideRole.COMPARISON,
            slide_intent=SlideIntent.COMPARISON_TRADEOFF,
        )

    if slide.intent == SlideIntent.MAPPING_BRIDGE:
        return _matrix_spec(
            slide,
            title=slide.title,
            message=slide.main_message,
            slide_archetype=SlideArchetype.TWO_COLUMN_MAPPING_TABLE,
            slide_intent=SlideIntent.MAPPING_BRIDGE,
            columns=["Source concept", "GA reading", "Design implication"],
            rows=[
                [concept_label, "Algorithmic counterpart", "Make the correspondence explicit before using the operator"],
                ["Encoding", "What is written into the chromosome", "Choose boundaries the operators can respect"],
                ["Evaluation", "What fitness will score", "Do not confuse stored representation with tested behavior"],
            ],
            core_content=["Mapping slides should expose a correspondence structure, not a text card."],
            primary_visual_structure="mapping-table",
        )

    if slide.intent == SlideIntent.MECHANISM_WALKTHROUGH:
        return _flow_spec(
            slide,
            title=slide.title,
            message=slide.main_message,
            slide_archetype=SlideArchetype.STEP_BY_STEP_MECHANISM,
            slide_intent=SlideIntent.MECHANISM_WALKTHROUGH,
            steps=_mechanism_steps(),
            core_content=["Mechanism slides should show ordered change, not generic chrome."],
        )

    if slide.intent in {SlideIntent.CONCEPT_UNPACKING, SlideIntent.ANCHOR_CONCEPT}:
        return _card_spec(
            slide,
            title=slide.title,
            message=slide.main_message,
            slide_archetype=SlideArchetype.ANCHOR_CONCEPT_CARD,
            slide_intent=slide.intent,
            cards=[
                {"label": concept_label, "body": _shorten(slide.main_message, BODY_LIMIT)},
                {"label": "Bridge to GA", "body": "Explain what the concept changes once it becomes an algorithmic design choice."},
            ],
            core_content=["Use one compact concept card when the slide is fundamentally definitional."],
            concept_ids=list(slide.concept_ids),
        )

    return _card_spec(
        slide,
        title=slide.title,
        message=slide.main_message,
        slide_archetype=SlideArchetype.ANCHOR_CONCEPT_CARD,
        slide_intent=SlideIntent.ANCHOR_CONCEPT,
        cards=[
            {"label": concept_label, "body": _shorten(slide.main_message, BODY_LIMIT)},
            {"label": "Teaching move", "body": _shorten(slide.pedagogical_goal, BODY_LIMIT)},
        ],
        core_content=["Keep one visual center of gravity per slide."],
        concept_ids=list(slide.concept_ids),
    )


def _author_appendix(
    appendix_slides: list[TeachingPlanSlide],
) -> tuple[list[dict[str, Any]], list[str]]:
    authored: list[dict[str, Any]] = []
    notes: list[str] = []
    consumed_indexes: set[int] = set()
    index = 0
    while index < len(appendix_slides):
        if index in consumed_indexes:
            index += 1
            continue
        slide = appendix_slides[index]
        title_key = _appendix_topic_key(slide.title)
        grouped_cluster: tuple[list[int], dict[str, Any]] | None = None
        for group_config in APPENDIX_GROUP_TOPICS:
            topics = tuple(group_config["topics"])
            if title_key != topics[0]:
                continue
            group_indexes: list[int] = [index]
            search_start = index + 1
            matched = True
            for topic in topics[1:]:
                partner_index = next(
                    (
                        candidate
                        for candidate in range(search_start, len(appendix_slides))
                        if candidate not in consumed_indexes and _appendix_topic_key(appendix_slides[candidate].title) == topic
                    ),
                    None,
                )
                if partner_index is None:
                    matched = False
                    break
                group_indexes.append(partner_index)
                search_start = partner_index + 1
            if matched:
                grouped_cluster = (group_indexes, group_config)
                break
        if grouped_cluster is not None:
            group_indexes, group_config = grouped_cluster
            cluster_slides = [appendix_slides[candidate] for candidate in group_indexes]
            authored.append(
                _appendix_authored_spec(
                    slide,
                    cluster_slides,
                    title=str(group_config["title"]),
                    kind=str(group_config["kind"]),
                )
            )
            notes.append(
                f"Merged appendix slides `{', '.join(appendix_slides[candidate].title for candidate in group_indexes)}` into `{group_config['title']}`."
            )
            consumed_indexes.update(group_indexes[1:])
            index += 1
            continue

        single_config = APPENDIX_SINGLE_TOPICS.get(
            title_key,
            {
                "title": f"{_appendix_topic_label(slide.title)} evidence cluster",
                "kind": "themed",
            },
        )
        authored.append(
            _appendix_authored_spec(
                slide,
                [slide],
                title=single_config["title"],
                kind=single_config["kind"],
            )
        )
        index += 1
    return authored, notes


def _fallback_archetype(spec: dict[str, Any]) -> tuple[SlideArchetype, str, str]:
    title = str(spec.get("title", "Slide"))
    intent = spec.get("slide_intent")
    visual = spec.get("visual", VisualType.TEXT)
    if spec.get("deck_mode") == DeckMode.APPENDIX or spec.get("section") == "Appendix":
        return (SlideArchetype.APPENDIX_EVIDENCE_CLUSTER, "appendix-reference", "evidence-cluster")
    if intent == SlideIntent.ORIENTATION:
        return (SlideArchetype.TITLE_ORIENTATION, "cover" if spec.get("role") == SlideRole.TITLE else "process-flow", "title-block")
    if visual in {VisualType.PROCESS, VisualType.TIMELINE, VisualType.DECISION_PATH}:
        return (SlideArchetype.PROCESS_FLOW, "process-flow", "flow")
    if "example" in title.lower():
        return (SlideArchetype.WORKED_EXAMPLE_STATE_TABLE, "comparison", "state-table")
    if visual in {VisualType.COMPARISON, VisualType.TABLE}:
        return (SlideArchetype.COMPARISON_MATRIX, "comparison", "matrix")
    return (SlideArchetype.ANCHOR_CONCEPT_CARD, "concept-explainer", "callout-cluster")


def _preview_from_specs(
    *,
    deck_title: str,
    lecture_family: LectureFamily,
    specs: list[dict[str, Any]],
    choreography_notes: list[str],
) -> AuthoringPreview:
    slides: list[AuthoringPreviewSlide] = []
    archetypes: list[str] = []
    main_story_archetypes: list[str] = []
    chrome_count = 0
    title_stems: Counter[str] = Counter()
    main_story_title_stems: Counter[str] = Counter()
    main_story_openings: Counter[str] = Counter()
    main_story_bridge_indices: list[int] = []
    main_story_cycle_indices: list[int] = []
    appendix_titles: list[str] = []
    for index, spec in enumerate(specs, start=1):
        archetype = spec.get("slide_archetype")
        layout_family = str(spec.get("chosen_layout_family") or spec.get("layout_pattern_id") or "concept-explainer")
        primary_visual_structure = str(spec.get("primary_visual_structure") or "content-block")
        if archetype is None:
            fallback_archetype, layout_family, primary_visual_structure = _fallback_archetype(spec)
            archetype = fallback_archetype
        deck_mode = spec.get("deck_mode", DeckMode.MAIN_STORY)
        slides.append(
            AuthoringPreviewSlide(
                slide_number=index,
                slide_key=str(spec.get("slide_key", f"slide-{index:03d}")),
                section=str(spec.get("section", "Main Story")),
                deck_mode=deck_mode,
                title=str(spec.get("title", f"Slide {index}")),
                slide_intent=spec.get("slide_intent", SlideIntent.CONCEPT_UNPACKING),
                slide_archetype=archetype,
                chosen_layout_family=layout_family,
                primary_visual_structure=primary_visual_structure,
                chrome_blocks_used=list(spec.get("chrome_blocks_used", [])),
                content_budget_summary=dict(spec.get("content_budget_summary", {})),
                duplicate_text_flags=list(spec.get("duplicate_text_flags", [])),
            )
        )
        archetypes.append(archetype.value)
        if deck_mode == DeckMode.MAIN_STORY:
            main_story_archetypes.append(archetype.value)
            main_story_title_stems[_title_stem(str(spec.get("title", f"Slide {index}")))] += 1
            opening = _message_opening(str(spec.get("message") or spec.get("takeaway") or ""))
            if opening:
                main_story_openings[opening] += 1
            if _is_bridge_shell_spec(spec):
                main_story_bridge_indices.append(index)
            if _is_cycle_shell_spec(spec):
                main_story_cycle_indices.append(index)
        else:
            appendix_titles.append(str(spec.get("title", f"Slide {index}")))
        chrome_count += len(spec.get("chrome_blocks_used", []))
        title_stems[_title_stem(str(spec.get("title", f"Slide {index}")))] += 1

    def _max_run(values: list[str]) -> int:
        max_run = 0
        current_run = 0
        previous = None
        for value in values:
            if value == previous:
                current_run += 1
            else:
                current_run = 1
                previous = value
            max_run = max(max_run, current_run)
        return max_run

    repeated_stems = sum(1 for count in title_stems.values() if count > 1)
    main_story_repeated_stems = sum(1 for count in main_story_title_stems.values() if count > 1)
    appendix_cluster_titles = sum(1 for title in appendix_titles if "evidence" in title.lower())
    repeated_opening_count = sum(count - 2 for count in main_story_openings.values() if count > 2)
    repeated_bridge_shell_count, _ = _cluster_overflow(main_story_bridge_indices, allowed=4)
    repeated_cycle_shell_count, _ = _cluster_overflow(main_story_cycle_indices, allowed=4)

    return AuthoringPreview(
        deck_title=deck_title,
        lecture_family=lecture_family,
        choreography_notes=_dedupe(choreography_notes),
        repetition_metrics={
            "slide_count": len(slides),
            "chrome_block_count": chrome_count,
            "max_consecutive_same_archetype": _max_run(archetypes),
            "main_story_max_consecutive_same_archetype": _max_run(main_story_archetypes),
            "repeated_title_stem_count": repeated_stems,
            "main_story_repeated_title_stem_count": main_story_repeated_stems,
            "main_story_repeated_rhetorical_opening_count": repeated_opening_count,
            "main_story_bridge_shell_count": repeated_bridge_shell_count,
            "main_story_cycle_cluster_count": repeated_cycle_shell_count,
            "appendix_evidence_cluster_count": appendix_cluster_titles,
        },
        slides=slides,
    )


def _move_title_before(
    specs: list[dict[str, Any]],
    *,
    title: str,
    before_title: str,
) -> list[dict[str, Any]]:
    current_index = next((index for index, spec in enumerate(specs) if spec.get("title") == title), None)
    before_index = next((index for index, spec in enumerate(specs) if spec.get("title") == before_title), None)
    if current_index is None or before_index is None or current_index < before_index:
        return specs
    reordered = list(specs)
    target = reordered.pop(current_index)
    before_index = next((index for index, spec in enumerate(reordered) if spec.get("title") == before_title), len(reordered))
    reordered.insert(before_index, target)
    return reordered


def _move_title_after(
    specs: list[dict[str, Any]],
    *,
    title: str,
    after_title: str,
) -> list[dict[str, Any]]:
    current_index = next((index for index, spec in enumerate(specs) if spec.get("title") == title), None)
    after_index = next((index for index, spec in enumerate(specs) if spec.get("title") == after_title), None)
    if current_index is None or after_index is None or current_index == after_index + 1:
        return specs
    reordered = list(specs)
    target = reordered.pop(current_index)
    after_index = next((index for index, spec in enumerate(reordered) if spec.get("title") == after_title), len(reordered) - 1)
    reordered.insert(after_index + 1, target)
    return reordered


def _reorder_titles(
    specs: list[dict[str, Any]],
    *,
    ordered_titles: list[str],
) -> list[dict[str, Any]]:
    if not specs:
        return specs
    title_rank = {title: index for index, title in enumerate(ordered_titles)}
    indexed_specs = list(enumerate(specs))
    return [
        spec
        for _, spec in sorted(
            indexed_specs,
            key=lambda item: (title_rank.get(str(item[1].get("title", "")), len(ordered_titles) + item[0]), item[0]),
        )
    ]


def _apply_mapping_family_choreography(specs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    if not specs:
        return specs, []
    notes: list[str] = []
    main_story_specs = [spec for spec in specs if spec.get("deck_mode", DeckMode.MAIN_STORY) == DeckMode.MAIN_STORY]
    appendix_specs = [spec for spec in specs if spec.get("deck_mode", DeckMode.MAIN_STORY) != DeckMode.MAIN_STORY]
    reordered_main_story = _reorder_titles(main_story_specs, ordered_titles=MAIN_STORY_CHOREOGRAPHY_ORDER)
    if reordered_main_story != main_story_specs:
        notes.append(
            "Re-sequenced the genetics main story into concept -> mapping -> mechanism -> example -> tradeoff -> synthesis arcs instead of leaving bridge and operator shells in long alternating runs."
        )
    loop_first_main_story = _move_title_before(
        reordered_main_story,
        title="One generation cycle",
        before_title="Worked example with a toy population",
    )
    if loop_first_main_story != reordered_main_story:
        notes.append(
            "Kept `One generation cycle` ahead of the toy example so the loop appears before the state-table walkthrough."
        )
    late_arc_balanced = loop_first_main_story
    for title, before_title in [
        ("The analogy helps until it hides design choices", "Phenotype shows whether a candidate actually works"),
    ]:
        updated = _move_title_before(late_arc_balanced, title=title, before_title=before_title)
        if updated != late_arc_balanced:
            late_arc_balanced = updated
    for title, after_title in [
        ("The chromosome is memory, not merit", "Phenotype shows whether a candidate actually works"),
        ("Allowed allele values define the move set", "Alleles define the search alphabet"),
        ("Scores connect behavior back to reproduction", "Evaluation makes phenotype visible to selection"),
        ("Synthesis: the full correspondence chain", "Variation rate sets the repair-versus-noise tradeoff"),
    ]:
        updated = _move_title_after(late_arc_balanced, title=title, after_title=after_title)
        if updated != late_arc_balanced:
            late_arc_balanced = updated
    if late_arc_balanced != loop_first_main_story:
        notes.append(
            "Rebalanced the late genetics sequence so limitation, evaluation, representation, and synthesis beats land in smaller arcs instead of leaving one long bridge-heavy tail."
        )
    return late_arc_balanced + appendix_specs, notes


def compile_authoring_layer(
    *,
    concept_graph: ConceptGraph,
    teaching_plan: TeachingPlan,
    fallback_specs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], AuthoringPreview, list[str]]:
    if concept_graph.lecture_family != LectureFamily.CONCEPT_TO_ALGORITHM_MAPPING:
        preview = _preview_from_specs(
            deck_title=teaching_plan.deck_title,
            lecture_family=concept_graph.lecture_family,
            specs=fallback_specs,
            choreography_notes=["No mapping-family authoring rewrite was applied for this lecture family."],
        )
        return fallback_specs, preview, preview.choreography_notes

    nodes_by_id = {node.concept_id: node for node in concept_graph.nodes}
    notes: list[str] = [
        "Mapped each main-story teaching move to an explicit slide archetype before PPTX composition.",
        "Rewrote repeated bridge and cycle shells into authored mapping, mechanism, limitation, and application slides.",
        "Grouped appendix source maps into clustered evidence slides where nearby topics shared the same support lane.",
    ]
    main_story = [slide for slide in teaching_plan.slides if slide.deck_mode == DeckMode.MAIN_STORY]
    appendix = [slide for slide in teaching_plan.slides if slide.deck_mode == DeckMode.APPENDIX]

    authored_specs: list[dict[str, Any]] = []
    title_counts: Counter[str] = Counter()
    for slide in main_story:
        key = _title_key(slide.title)
        title_counts[key] += 1
        authored = _author_main_slide(slide, nodes_by_id, occurrence=title_counts[key])
        if authored is not None:
            authored_specs.append(authored)
        else:
            notes.append(f"Removed repeated cycle shell `{slide.title}` and kept the stronger authored cycle slides instead.")

    authored_specs, choreography_cuts = _apply_mapping_family_choreography(authored_specs)
    notes.extend(choreography_cuts)

    appendix_specs, appendix_notes = _author_appendix(appendix)
    authored_specs.extend(appendix_specs)
    notes.extend(appendix_notes)

    preview = _preview_from_specs(
        deck_title=teaching_plan.deck_title,
        lecture_family=concept_graph.lecture_family,
        specs=authored_specs,
        choreography_notes=notes,
    )
    return authored_specs, preview, preview.choreography_notes
