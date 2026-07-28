"""Deterministic production-handoff preparation from approved Gate 2 artifacts."""

from __future__ import annotations

from pathlib import Path

from .gate2_planner import derive_asset_requests_from_blueprint
from ..compat.legacy_non_pptx import (
    AssetKind,
    AssetPriority,
    AssetRequest,
    AssetRequests,
    Blueprint,
    BlueprintSlide,
    ContractModel,
    DeckConstitution,
    DesignSystem,
    EvidencePlanItem,
    InfographicPlanItem,
    LayoutLibrary,
    LayoutPattern,
    SlideLedger,
    SlideLedgerEntry,
    StageStatus,
    VisualSourcePreference,
    VisualType,
    VizSpec,
    VizSpecSet,
    load_state_file,
    save_state_file,
)
from .structured_visuals import build_viz_spec


STRUCTURED_VISUAL_TYPES = {
    VisualType.CHART,
    VisualType.TABLE,
    VisualType.PROCESS,
    VisualType.TIMELINE,
    VisualType.HIERARCHY,
    VisualType.COMPARISON,
    VisualType.FRAMEWORK,
    VisualType.INFOGRAPHIC,
    VisualType.METRIC_SUMMARY,
    VisualType.DECISION_PATH,
}

PRIORITY_RANK = {
    AssetPriority.LOW: 0,
    AssetPriority.NORMAL: 1,
    AssetPriority.HIGH: 2,
    AssetPriority.CRITICAL: 3,
}


class AssetDerivationOutputs(ContractModel):
    asset_requests: AssetRequests
    viz_spec: VizSpecSet
    slide_ledger: SlideLedger


def _request_index(requests: list[AssetRequest]) -> dict[int, AssetRequest]:
    indexed: dict[int, AssetRequest] = {}
    for request in requests:
        if request.slide_number in indexed:
            raise ValueError("Phase 5 handoff prep expects at most one asset request per slide")
        indexed[request.slide_number] = request
    return indexed


def _layout_index(layout_library: LayoutLibrary) -> dict[str, LayoutPattern]:
    return {pattern.pattern_id: pattern for pattern in layout_library.patterns}


def _evidence_plan_index(blueprint: Blueprint) -> dict[int, EvidencePlanItem]:
    return {item.slide_number: item for item in blueprint.evidence_asset_plan}


def _infographic_plan_index(blueprint: Blueprint) -> dict[int, InfographicPlanItem]:
    return {item.slide_number: item for item in blueprint.infographic_plan}


def _dedupe_text(*groups: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        if not group:
            continue
        for item in group:
            text = item.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def _prefer_priority(canonical: AssetPriority, existing: AssetPriority | None) -> AssetPriority:
    if existing is None:
        return canonical
    return existing if PRIORITY_RANK[existing] >= PRIORITY_RANK[canonical] else canonical


def _requires_handoff_request(slide_visual_type: VisualType, source_preference: VisualSourcePreference) -> bool:
    if source_preference in {VisualSourcePreference.DOCUMENT_CROP, VisualSourcePreference.EXISTING_ASSET}:
        return True
    if slide_visual_type in {VisualType.DOCUMENT_CROP, VisualType.PHOTO}:
        return True
    return slide_visual_type in STRUCTURED_VISUAL_TYPES


def _ensure_gate2_alignment(
    blueprint: Blueprint,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution,
    layout_library: LayoutLibrary,
    slide_ledger: SlideLedger,
    asset_requests: AssetRequests | None,
) -> None:
    deck_titles = {
        blueprint.deck_title,
        design_system.deck_title,
        deck_constitution.deck_title,
        layout_library.deck_title,
        slide_ledger.deck_title,
    }
    if asset_requests is not None:
        deck_titles.add(asset_requests.deck_title)
    if len(deck_titles) != 1:
        raise ValueError("Gate 2 artifacts must share the same deck_title before Phase 5 handoff prep")

    blueprint_numbers = [slide.slide_number for slide in blueprint.slides]
    ledger_numbers = [entry.slide_number for entry in slide_ledger.entries]
    if blueprint_numbers != ledger_numbers:
        raise ValueError("Phase 5 handoff prep requires blueprint and slide_ledger to cover the same slide numbers")

    layout_by_id = _layout_index(layout_library)
    missing_layouts = sorted({slide.layout_pattern_id for slide in blueprint.slides if slide.layout_pattern_id not in layout_by_id})
    if missing_layouts:
        raise ValueError(f"layout_library is missing approved layout pattern ids: {', '.join(missing_layouts)}")

    missing_constitution_layouts = sorted(set(deck_constitution.layout_pattern_ids) - set(layout_by_id))
    if missing_constitution_layouts:
        raise ValueError(
            "deck_constitution references layout patterns that are missing from layout_library: "
            + ", ".join(missing_constitution_layouts)
        )

    if design_system.visual_route_id != blueprint.recommended_route:
        raise ValueError("design_system.visual_route_id must match blueprint.recommended_route")
    if deck_constitution.approved_visual_route not in {None, blueprint.recommended_route, design_system.visual_route_id}:
        raise ValueError("deck_constitution.approved_visual_route must match the approved Gate 2 route")

    if asset_requests is not None:
        request_numbers = [request.slide_number for request in asset_requests.requests]
        unknown_numbers = sorted(set(request_numbers) - set(blueprint_numbers))
        if unknown_numbers:
            raise ValueError(
                "asset_requests contain slide numbers that are not present in the approved blueprint: "
                + ", ".join(str(number) for number in unknown_numbers)
            )
        _request_index(asset_requests.requests)


def _canonical_request_for_slide(
    slide_number: int,
    derived_requests: dict[int, AssetRequest],
    existing_requests: dict[int, AssetRequest],
) -> AssetRequest | None:
    return existing_requests.get(slide_number) or derived_requests.get(slide_number)


def _normalized_quality_requirements(
    canonical: AssetRequest,
    existing: AssetRequest | None,
    layout_pattern: LayoutPattern,
    deck_constitution: DeckConstitution,
    evidence_plan: EvidencePlanItem | None,
    infographic_plan: InfographicPlanItem | None,
) -> list[str]:
    layout_requirement = (
        f"Honor layout pattern `{layout_pattern.pattern_id}` density guidance: {layout_pattern.density_guidance}"
        if layout_pattern.density_guidance
        else f"Honor layout pattern `{layout_pattern.pattern_id}` safe-area rules: {layout_pattern.safe_area_notes}"
    )
    route_requirement = (
        f"Keep the approved `{deck_constitution.approved_visual_route}` visual route consistent across this handoff."
        if deck_constitution.approved_visual_route
        else None
    )
    source_rule = deck_constitution.source_handling_rules[:1]
    verification_needs = evidence_plan.verification_needs[:2] if evidence_plan is not None else []
    frame_fit = infographic_plan.frame_fit_considerations[:1] if infographic_plan is not None else []
    return _dedupe_text(
        canonical.asset_quality_requirements,
        existing.asset_quality_requirements if existing is not None else None,
        [layout_requirement],
        [route_requirement] if route_requirement is not None else None,
        source_rule,
        verification_needs,
        frame_fit,
    )
def _build_normalized_request(
    slide: BlueprintSlide,
    canonical: AssetRequest,
    existing: AssetRequest | None,
    layout_pattern: LayoutPattern,
    deck_constitution: DeckConstitution,
    evidence_plan: EvidencePlanItem | None,
    infographic_plan: InfographicPlanItem | None,
) -> AssetRequest:
    source_refs = slide.production_bridge.source_material_refs or canonical.source_material_refs
    first_source = source_refs[0] if source_refs else None
    fallback_ladder = list(existing.fallback_ladder) if existing is not None and existing.fallback_ladder else list(canonical.fallback_ladder)
    fallback_visual = (
        existing.fallback_visual
        if existing is not None and existing.fallback_visual in fallback_ladder[1:]
        else slide.production_bridge.fallback_visual
    )
    if fallback_visual not in fallback_ladder[1:]:
        fallback_visual = canonical.fallback_visual if canonical.fallback_visual in fallback_ladder[1:] else None
    if fallback_visual not in fallback_ladder[1:] and len(fallback_ladder) > 1:
        fallback_visual = fallback_ladder[1]

    preferred_source_doc = None
    if source_refs:
        preferred_source_doc = (
            existing.preferred_source_doc
            if existing is not None and existing.preferred_source_doc
            else canonical.preferred_source_doc or first_source.path or first_source.label
        )
    page_hint = (
        existing.page_hint
        if existing is not None and existing.page_hint is not None
        else canonical.page_hint if canonical.page_hint is not None else first_source.page if first_source is not None else None
    )
    crop_subject_hint = slide.production_bridge.crop_subject_hint or (existing.crop_subject_hint if existing is not None else None)

    return AssetRequest(
        request_id=canonical.request_id,
        slide_number=slide.slide_number,
        slide_id=canonical.slide_id,
        slide_message=slide.main_message,
        asset_kind=canonical.asset_kind,
        priority=_prefer_priority(canonical.priority, existing.priority if existing is not None else None),
        brief=existing.brief if existing is not None and existing.brief else canonical.brief,
        required_visual_type=slide.visual_type,
        visual_type=slide.visual_type,
        visual_source_preference=canonical.visual_source_preference,
        source_material_refs=source_refs,
        preferred_source_doc=preferred_source_doc,
        page_hint=page_hint,
        crop_subject_hint=crop_subject_hint,
        fallback_visual=fallback_visual,
        fallback_ladder=fallback_ladder,
        approval_status=existing.approval_status if existing is not None and existing.approval_status == StageStatus.APPROVED else StageStatus.READY,
        production_mode=canonical.production_mode,
        asset_quality_requirements=_normalized_quality_requirements(
            canonical=canonical,
            existing=existing,
            layout_pattern=layout_pattern,
            deck_constitution=deck_constitution,
            evidence_plan=evidence_plan,
            infographic_plan=infographic_plan,
        ),
        allowed_crop_review_actions=(
            list(existing.allowed_crop_review_actions)
            if existing is not None and existing.allowed_crop_review_actions
            else list(canonical.allowed_crop_review_actions)
        ),
    )


def _slide_blockers(
    slide: BlueprintSlide,
    request: AssetRequest | None,
    layout_pattern: LayoutPattern,
    evidence_plan: EvidencePlanItem | None,
) -> list[str]:
    blockers: list[str] = []
    if not layout_pattern.export_safe:
        blockers.append(f"Layout pattern `{layout_pattern.pattern_id}` is not marked export-safe.")
    if request is None:
        return blockers
    if request.asset_kind in {AssetKind.DOCUMENT_CROP, AssetKind.IMAGE} and not request.source_material_refs:
        blockers.append("Source-reuse path is missing local source_material_refs.")
    if request.asset_kind == AssetKind.DOCUMENT_CROP and not request.crop_subject_hint:
        blockers.append("Document-crop path is missing a crop_subject_hint.")
    if request.asset_kind == AssetKind.STRUCTURED_VISUAL and slide.visual_type in STRUCTURED_VISUAL_TYPES:
        has_support = bool(slide.required_evidence_assets) or bool(request.source_material_refs)
        if evidence_plan is not None:
            has_support = has_support or bool(evidence_plan.required_data) or bool(evidence_plan.critical_assets)
        if not has_support:
            blockers.append("Structured visual path needs required evidence assets or source references before rendering.")
    return blockers


def _default_simple_variant(request: AssetRequest) -> str:
    if request.fallback_visual is not None:
        fallback_label = request.fallback_visual.value.replace("-", " ")
        return f"Fallback to a simpler {fallback_label} if the primary visual becomes too dense or the source is unavailable."
    return "Fallback to a simpler comparison or text-led layout if the primary visual path is not viable."


def _prepared_viz_spec(
    slide: BlueprintSlide,
    request: AssetRequest,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution,
    evidence_plan: EvidencePlanItem | None,
    infographic_plan: InfographicPlanItem | None,
) -> VizSpec:
    spec = build_viz_spec(slide, request, design_system)
    data_contract = _dedupe_text(
        spec.data_contract,
        [f"visual_route={design_system.visual_route_id}", f"theme={design_system.theme_name}"],
        [f"preferred_source={request.preferred_source_doc}"] if request.preferred_source_doc else None,
        [f"required_data={item}" for item in evidence_plan.required_data[:3]] if evidence_plan is not None else None,
        [f"critical_asset={item}" for item in evidence_plan.critical_assets[:2]] if evidence_plan is not None else None,
        [f"frame_fit={item}" for item in infographic_plan.frame_fit_considerations[:2]] if infographic_plan is not None else None,
    )
    style_profile = spec.style_profile.model_copy(
        update={
            "chart_rules": _dedupe_text(spec.style_profile.chart_rules, deck_constitution.chart_rules),
            "table_rules": _dedupe_text(spec.style_profile.table_rules, deck_constitution.table_rules),
            "highlight_rules": _dedupe_text(
                spec.style_profile.highlight_rules,
                design_system.highlight_rules,
                deck_constitution.visual_consistency_rules[:2],
            ),
        }
    )
    style_tokens = _dedupe_text(spec.style_tokens, deck_constitution.design_token_refs)
    simpler_variant = spec.simpler_variant or (
        infographic_plan.fallback_simple_version if infographic_plan is not None else None
    )
    return spec.model_copy(
        update={
            "style_tokens": style_tokens,
            "style_profile": style_profile,
            "data_contract": data_contract,
            "simpler_variant": simpler_variant or _default_simple_variant(request),
        }
    )


def derive_assets_from_blueprint(
    blueprint: Blueprint,
    design_system: DesignSystem,
    deck_constitution: DeckConstitution,
    layout_library: LayoutLibrary,
    slide_ledger: SlideLedger,
    asset_requests: AssetRequests | None = None,
) -> AssetDerivationOutputs:
    _ensure_gate2_alignment(
        blueprint=blueprint,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        slide_ledger=slide_ledger,
        asset_requests=asset_requests,
    )

    derived_requests = _request_index(derive_asset_requests_from_blueprint(blueprint.slides))
    existing_requests = _request_index(asset_requests.requests) if asset_requests is not None else {}
    layout_by_id = _layout_index(layout_library)
    evidence_plan_by_slide = _evidence_plan_index(blueprint)
    infographic_plan_by_slide = _infographic_plan_index(blueprint)
    slides_by_number = {slide.slide_number: slide for slide in blueprint.slides}

    normalized_requests: list[AssetRequest] = []
    request_by_slide: dict[int, AssetRequest] = {}
    viz_specs: list[VizSpec] = []
    viz_spec_by_slide: dict[int, VizSpec] = {}
    blockers_by_slide: dict[int, list[str]] = {}

    for slide in blueprint.slides:
        canonical = _canonical_request_for_slide(slide.slide_number, derived_requests, existing_requests)
        if canonical is None:
            blockers_by_slide[slide.slide_number] = []
            continue
        if not _requires_handoff_request(slide.visual_type, slide.production_bridge.visual_source_preference):
            blockers_by_slide[slide.slide_number] = []
            continue

        evidence_plan = evidence_plan_by_slide.get(slide.slide_number)
        infographic_plan = infographic_plan_by_slide.get(slide.slide_number)
        layout_pattern = layout_by_id[slide.layout_pattern_id]
        existing = existing_requests.get(slide.slide_number)

        normalized = _build_normalized_request(
            slide=slide,
            canonical=canonical,
            existing=existing,
            layout_pattern=layout_pattern,
            deck_constitution=deck_constitution,
            evidence_plan=evidence_plan,
            infographic_plan=infographic_plan,
        )
        blockers = _slide_blockers(
            slide=slide,
            request=normalized,
            layout_pattern=layout_pattern,
            evidence_plan=evidence_plan,
        )
        blockers_by_slide[slide.slide_number] = blockers
        normalized_requests.append(normalized)
        request_by_slide[slide.slide_number] = normalized

        if normalized.asset_kind == AssetKind.STRUCTURED_VISUAL and normalized.required_visual_type in STRUCTURED_VISUAL_TYPES:
            spec = _prepared_viz_spec(
                slide=slide,
                request=normalized,
                design_system=design_system,
                deck_constitution=deck_constitution,
                evidence_plan=evidence_plan,
                infographic_plan=infographic_plan,
            )
            viz_specs.append(spec)
            viz_spec_by_slide[slide.slide_number] = spec

    updated_entries: list[SlideLedgerEntry] = []
    for entry in slide_ledger.entries:
        slide = slides_by_number[entry.slide_number]
        request = request_by_slide.get(entry.slide_number)
        spec = viz_spec_by_slide.get(entry.slide_number)
        blockers = blockers_by_slide.get(entry.slide_number, [])

        if blockers:
            production_readiness = StageStatus.BLOCKED
        else:
            production_readiness = StageStatus.READY

        if request is None:
            asset_status = StageStatus.COMPLETE
            visual_status = StageStatus.COMPLETE
            change_note = "No external asset or structured-visual handoff is required; keep this slide native to the approved layout."
        elif request.asset_kind == AssetKind.STRUCTURED_VISUAL:
            asset_status = StageStatus.BLOCKED if blockers else StageStatus.READY
            visual_status = StageStatus.BLOCKED if blockers else StageStatus.READY
            change_note = "Prepared normalized structured-visual handoff state from the approved Gate 2 package."
        else:
            asset_status = StageStatus.BLOCKED if blockers else StageStatus.READY
            visual_status = StageStatus.COMPLETE
            change_note = "Prepared normalized source-reuse handoff state from the approved Gate 2 package."

        updated_entries.append(
            entry.model_copy(
                update={
                    "title": slide.title,
                    "one_line_takeaway": slide.one_line_takeaway,
                    "main_message": slide.main_message,
                    "section": slide.section,
                    "deck_mode": slide.deck_mode,
                    "visual_type": slide.visual_type,
                    "visual_source_preference": slide.production_bridge.visual_source_preference,
                    "production_mode": slide.production_bridge.production_mode,
                    "layout_pattern_id": slide.layout_pattern_id,
                    "required_evidence_assets": slide.required_evidence_assets,
                    "asset_request_ids": [request.request_id] if request is not None else [],
                    "asset_dependency_kinds": [request.asset_kind] if request is not None else [],
                    "viz_spec_id": spec.spec_id if spec is not None else None,
                    "production_readiness": production_readiness,
                    "unresolved_blockers": blockers or None,
                    "blueprint_status": StageStatus.READY,
                    "asset_status": asset_status,
                    "visual_status": visual_status,
                    "change_note": change_note,
                }
            )
        )

    continuity_notes = list(slide_ledger.continuity_notes)
    additions = [
        "Treat asset_request_ids as the source-reuse handoff index and viz_spec_id as the structured-visual handoff index.",
        "Slides without asset_request_ids or viz_spec_id should compile directly from the approved blueprint and layout library.",
        "Re-run production handoff prep whenever blueprint slide roles, visual types, source refs, or layout assignments change.",
    ]
    if any(blockers_by_slide.values()):
        additions.append("Resolve any unresolved_blockers in the slide ledger before running crop or structured-visual workers.")
    for note in additions:
        if note not in continuity_notes:
            continuity_notes.append(note)

    return AssetDerivationOutputs(
        asset_requests=AssetRequests(deck_title=blueprint.deck_title, requests=normalized_requests),
        viz_spec=VizSpecSet(deck_title=blueprint.deck_title, specs=viz_specs),
        slide_ledger=SlideLedger(
            deck_title=slide_ledger.deck_title,
            entries=updated_entries,
            continuity_notes=continuity_notes,
        ),
    )


def derive_assets_from_files(
    blueprint_path: str | Path,
    design_system_path: str | Path,
    deck_constitution_path: str | Path,
    layout_library_path: str | Path,
    slide_ledger_path: str | Path,
    asset_requests_path: str | Path | None = None,
) -> AssetDerivationOutputs:
    blueprint = load_state_file(blueprint_path)
    design_system = load_state_file(design_system_path)
    deck_constitution = load_state_file(deck_constitution_path)
    layout_library = load_state_file(layout_library_path)
    slide_ledger = load_state_file(slide_ledger_path)

    if blueprint.schema_name != "blueprint":
        raise TypeError(f"expected blueprint, found {blueprint.schema_name}")
    if design_system.schema_name != "design_system":
        raise TypeError(f"expected design_system, found {design_system.schema_name}")
    if deck_constitution.schema_name != "deck_constitution":
        raise TypeError(f"expected deck_constitution, found {deck_constitution.schema_name}")
    if layout_library.schema_name != "layout_library":
        raise TypeError(f"expected layout_library, found {layout_library.schema_name}")
    if slide_ledger.schema_name != "slide_ledger":
        raise TypeError(f"expected slide_ledger, found {slide_ledger.schema_name}")

    loaded_requests = None
    if asset_requests_path is not None:
        loaded_requests = load_state_file(asset_requests_path)
        if loaded_requests.schema_name != "asset_requests":
            raise TypeError(f"expected asset_requests, found {loaded_requests.schema_name}")

    return derive_assets_from_blueprint(
        blueprint=blueprint,
        design_system=design_system,
        deck_constitution=deck_constitution,
        layout_library=layout_library,
        slide_ledger=slide_ledger,
        asset_requests=loaded_requests,
    )


def write_asset_derivation_outputs(outputs: AssetDerivationOutputs, output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    return {
        "asset_requests": save_state_file(outputs.asset_requests, root / "asset-requests.json"),
        "viz_spec": save_state_file(outputs.viz_spec, root / "viz-spec.json"),
        "slide_ledger": save_state_file(outputs.slide_ledger, root / "slide-ledger.json"),
    }

