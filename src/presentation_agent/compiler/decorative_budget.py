"""Resolve decorative budgets for editable PPTX rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DENSITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}
TEXT_SLOT_TYPES = {"text", "content"}
STRUCTURED_SLOT_TYPES = {"table", "chart"}


@dataclass
class DecorativeBudgetPlan:
    max_shape_count_target: int
    max_ornament_density: str
    max_background_coverage: float
    protected_text_zones: list[dict[str, Any]]
    protected_table_chart_zones: list[dict[str, Any]]
    footer_max_footprint: float
    card_chrome_budget: float
    text_pressure: str
    component_density: str
    allowed_ornament_density: str
    high_density_allowed: bool
    decisions: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_shape_count_target": self.max_shape_count_target,
            "max_ornament_density": self.max_ornament_density,
            "max_background_coverage": self.max_background_coverage,
            "protected_text_zones": self.protected_text_zones,
            "protected_table_chart_zones": self.protected_table_chart_zones,
            "footer_max_footprint": self.footer_max_footprint,
            "card_chrome_budget": self.card_chrome_budget,
            "text_pressure": self.text_pressure,
            "component_density": self.component_density,
            "allowed_ornament_density": self.allowed_ornament_density,
            "high_density_allowed": self.high_density_allowed,
            "decisions": self.decisions,
        }


def resolve_decorative_budget(
    layout: dict[str, Any],
    contract: dict[str, Any] | None,
    *,
    binding: dict[str, Any] | None = None,
    slot_capacity_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or {}
    budget = contract.get("decorative_budget") if isinstance(contract.get("decorative_budget"), dict) else {}
    layout_family = str(layout.get("layout_family_id") or (binding or {}).get("layout_family_id") or "")
    archetype = str(layout.get("archetype_id") or (binding or {}).get("slide_type") or "")
    component_density = str((binding or {}).get("component_density") or layout.get("density") or "medium")
    text_pressure = _text_pressure(slot_capacity_status or (binding or {}).get("slot_capacity_status") or {})
    contract_density = _normalize_density(budget.get("max_ornament_density"), "medium")
    max_shape_count = int(budget.get("max_shape_count_target") or _default_shape_budget(layout_family, archetype))
    max_background = float(budget.get("max_background_coverage") or _default_background_coverage(layout_family, archetype))
    high_density_allowed = _high_density_allowed(layout_family, archetype, text_pressure)
    allowed_density = contract_density
    if text_pressure in {"high", "severe"} and archetype not in {"creative_cover", "section_divider", "visual_table_of_contents"}:
        allowed_density = _min_density(allowed_density, "low")
    elif not high_density_allowed:
        allowed_density = _min_density(allowed_density, "medium")
    if archetype == "data_table_appendix":
        allowed_density = "low"

    plan = DecorativeBudgetPlan(
        max_shape_count_target=max_shape_count,
        max_ornament_density=contract_density,
        max_background_coverage=max_background,
        protected_text_zones=_protected_zones(layout, TEXT_SLOT_TYPES),
        protected_table_chart_zones=_protected_zones(layout, STRUCTURED_SLOT_TYPES),
        footer_max_footprint=0.12 if archetype in {"creative_cover", "section_divider"} else 0.10,
        card_chrome_budget=0.75 if text_pressure in {"high", "severe"} else 0.95,
        text_pressure=text_pressure,
        component_density=component_density,
        allowed_ornament_density=allowed_density,
        high_density_allowed=high_density_allowed,
        decisions={
            "ornaments_removed": 0,
            "ornaments_relocated": 0,
            "background_density_reduced": False,
            "card_chrome_simplified": text_pressure in {"medium", "high", "severe"},
            "footer_chrome_simplified": True,
            "shape_budget_status": "planned",
            "protected_zone_intrusion_status": "protected",
            "required_visual_motifs_preserved_at_lower_density": True,
        },
    )
    return plan.as_dict()


def update_budget_decisions_after_render(
    plan: dict[str, Any],
    *,
    shape_count: int,
    previous_shape_count: int | None = None,
    intrusion_count: int | None = None,
) -> dict[str, Any]:
    updated = dict(plan)
    decisions = dict(updated.get("decisions") or {})
    target = int(updated.get("max_shape_count_target") or 0)
    decisions["shape_budget_status"] = "ok" if not target or shape_count <= target else "over_budget"
    decisions["protected_zone_intrusion_status"] = "ok" if not intrusion_count else "needs_followup"
    if previous_shape_count is not None:
        decisions["ornaments_removed"] = max(0, previous_shape_count - shape_count)
    updated["decisions"] = decisions
    updated["rendered_shape_count"] = shape_count
    return updated


def _text_pressure(slot_capacity_status: dict[str, Any]) -> str:
    if not isinstance(slot_capacity_status, dict) or not slot_capacity_status:
        return "medium"
    statuses: list[str] = []
    for payload in slot_capacity_status.values():
        if isinstance(payload, dict):
            statuses.append(str(payload.get("status") or "ok"))
            if payload.get("content_trimmed") or payload.get("trimmed"):
                statuses.append("adjusted")
            if int(payload.get("body_bullet_count") or 0) > int(payload.get("body_bullet_limit") or 999):
                statuses.append("failed")
    if any(status in {"failed", "overflow"} for status in statuses):
        return "severe"
    if any(status == "adjusted" for status in statuses):
        return "high"
    return "medium" if statuses else "low"


def _protected_zones(layout: dict[str, Any], slot_types: set[str]) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for slot in layout.get("slots") or []:
        if not isinstance(slot, dict) or slot.get("slot_type") not in slot_types:
            continue
        bounds = slot.get("bounds")
        if not isinstance(bounds, dict):
            continue
        zones.append(
            {
                "slot_id": slot.get("slot_id"),
                "slot_type": slot.get("slot_type"),
                "component_id": slot.get("component_id"),
                "bounds": {key: float(bounds.get(key) or 0) for key in ("x", "y", "w", "h")},
            }
        )
    return zones


def _high_density_allowed(layout_family: str, archetype: str, text_pressure: str) -> bool:
    if text_pressure in {"high", "severe"} and archetype not in {"creative_cover", "section_divider"}:
        return False
    return layout_family in {"expressive_cover_divider", "visual_toc_navigation"} or archetype in {
        "creative_cover",
        "section_divider",
        "visual_table_of_contents",
    }


def _default_shape_budget(layout_family: str, archetype: str) -> int:
    if archetype in {"creative_cover", "section_divider"} or layout_family == "expressive_cover_divider":
        return 180
    if archetype == "visual_table_of_contents":
        return 150
    if layout_family in {"table_appendix", "kpi_dashboard"}:
        return 120
    return 130


def _default_background_coverage(layout_family: str, archetype: str) -> float:
    if archetype == "creative_cover":
        return 0.82
    if archetype == "section_divider":
        return 0.62
    if layout_family == "table_appendix":
        return 0.34
    return 0.42


def _normalize_density(value: Any, default: str) -> str:
    text = str(value or default).strip().lower().replace("_", "-")
    return text if text in DENSITY_ORDER else default


def _min_density(left: str, right: str) -> str:
    return left if DENSITY_ORDER[_normalize_density(left, "medium")] <= DENSITY_ORDER[_normalize_density(right, "medium")] else right
