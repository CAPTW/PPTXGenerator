"""Resolve role-mapped SVG icons for editable PowerPoint template rendering."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_LIBRARY_MANIFEST = Path("assets/icons/manifests/icon_library_manifest.json")
DEFAULT_ROLE_MAP = Path("assets/icons/manifests/icon_role_map.json")
DEFAULT_STYLE_TOKENS = Path("assets/icons/manifests/icon_style_tokens.json")
SVG_CONTENT_TYPE = "image/svg+xml"


@dataclass(frozen=True)
class IconResolution:
    """Resolved normalized SVG icon metadata."""

    icon_id: str
    icon_role: str | None
    icon_family: str
    normalized_path: Path
    source_path: str | None
    color_token: str
    stroke_width: float
    size_in: float
    role_entry: dict[str, Any] | None
    manifest_record: dict[str, Any]


def empty_icon_report() -> dict[str, Any]:
    return {
        "icons_used": [],
        "missing_icons": [],
        "unresolved_icon_roles": [],
        "icon_asset_paths": [],
        "icon_family": [],
    }


def merge_icon_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    merged = empty_icon_report()
    family_seen: set[str] = set()
    path_seen: set[str] = set()
    for report in reports:
        for key in ("icons_used", "missing_icons", "unresolved_icon_roles"):
            merged[key].extend(report.get(key) or [])
        for path in report.get("icon_asset_paths") or []:
            if path not in path_seen:
                path_seen.add(str(path))
                merged["icon_asset_paths"].append(path)
        for family in report.get("icon_family") or []:
            if family not in family_seen:
                family_seen.add(str(family))
                merged["icon_family"].append(family)
    merged["icon_family"] = sorted(merged["icon_family"])
    merged["icon_asset_paths"] = sorted(merged["icon_asset_paths"])
    return merged


class IconResolver:
    """Resolve semantic icon roles to local normalized SVG files.

    The resolver intentionally fails closed. Missing assets, unresolved roles,
    raster paths, and template-disallowed records produce warnings and no icon.
    """

    def __init__(
        self,
        *,
        repo_root: str | Path | None = None,
        library_manifest_path: str | Path = DEFAULT_LIBRARY_MANIFEST,
        role_map_path: str | Path = DEFAULT_ROLE_MAP,
        style_tokens_path: str | Path = DEFAULT_STYLE_TOKENS,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
        self.library_manifest_path = self._repo_path(library_manifest_path)
        self.role_map_path = self._repo_path(role_map_path)
        self.style_tokens_path = self._repo_path(style_tokens_path)
        self.library_manifest = self._load_json(self.library_manifest_path)
        self.role_map = self._load_json(self.role_map_path)
        self.style_tokens = self._load_json(self.style_tokens_path)
        self.icons_by_id = {
            str(record.get("icon_id")): record
            for record in self.library_manifest.get("icons") or []
            if isinstance(record, dict) and record.get("icon_id")
        }
        self.roles_by_name = {
            str(record.get("role")): record
            for record in self.role_map.get("roles") or []
            if isinstance(record, dict) and record.get("role")
        }

    def empty_report(self) -> dict[str, Any]:
        return empty_icon_report()

    def merge_reports(self, reports: list[dict[str, Any]]) -> dict[str, Any]:
        return merge_icon_reports(reports)

    def resolve(
        self,
        component: dict[str, Any],
        *,
        report: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> IconResolution | None:
        icon_id = _clean(component.get("icon_id"))
        icon_role = _clean(component.get("icon_role"))
        icon_family = _clean(component.get("icon_family"))
        role_entry = self.roles_by_name.get(icon_role) if icon_role else None

        if not icon_id and not icon_role:
            return None
        if icon_role and role_entry is None:
            self._record_unresolved_role(icon_role, report, context)
            return None

        candidate_ids = self._candidate_icon_ids(icon_id, icon_family, role_entry)
        if not candidate_ids:
            self._record_missing(icon_id or None, icon_role, "NO_ICON_CANDIDATES", report, context)
            return None

        for candidate_id in candidate_ids:
            record = self.icons_by_id.get(candidate_id)
            if record is None:
                continue
            resolution = self._resolution_from_record(record, component, icon_role, role_entry, report, context)
            if resolution is not None:
                return resolution

        self._record_missing(candidate_ids[0], icon_role, "ICON_ASSET_MISSING", report, context, candidates=candidate_ids)
        return None

    def materialize_svg(self, resolution: IconResolution, *, color_hex: str | None = None, stroke_width: float | None = None) -> Path:
        """Write a temporary SVG with currentColor and stroke width applied."""

        svg = resolution.normalized_path.read_text(encoding="utf-8")
        color = _normalize_hex_color(color_hex) or "#111827"
        svg = svg.replace("currentColor", color)
        effective_stroke_width = stroke_width if stroke_width is not None else resolution.stroke_width
        if effective_stroke_width:
            svg = re.sub(
                r'stroke-width="[^"]*"',
                f'stroke-width="{_number_text(effective_stroke_width)}"',
                svg,
                count=0,
            )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".svg", delete=False) as handle:
            handle.write(svg)
            return Path(handle.name)

    def _candidate_icon_ids(
        self,
        explicit_icon_id: str | None,
        icon_family: str | None,
        role_entry: dict[str, Any] | None,
    ) -> list[str]:
        candidates: list[str] = []
        if explicit_icon_id:
            candidates.append(explicit_icon_id)
        if role_entry:
            preferred = _clean(role_entry.get("preferred_icon_id"))
            fallback_ids = [
                str(item)
                for item in role_entry.get("fallback_icon_ids") or []
                if isinstance(item, str) and item.strip()
            ]
            candidates.extend([candidate for candidate in [preferred, *fallback_ids] if candidate])
        if icon_family:
            family_first = [candidate for candidate in candidates if candidate.startswith(f"{icon_family}__")]
            family_later = [candidate for candidate in candidates if not candidate.startswith(f"{icon_family}__")]
            candidates = [*family_first, *family_later]
        return _dedupe(candidates)

    def _resolution_from_record(
        self,
        record: dict[str, Any],
        component: dict[str, Any],
        icon_role: str | None,
        role_entry: dict[str, Any] | None,
        report: dict[str, Any] | None,
        context: dict[str, Any] | None,
    ) -> IconResolution | None:
        icon_id = str(record.get("icon_id") or "")
        normalized = _clean(record.get("normalized_path"))
        if not bool(record.get("allowed_for_template")):
            self._record_missing(icon_id, icon_role, "ICON_NOT_ALLOWED_FOR_TEMPLATE", report, context)
            return None
        if not normalized:
            self._record_missing(icon_id, icon_role, "ICON_NORMALIZED_PATH_MISSING", report, context)
            return None
        path = self._repo_path(normalized)
        if path.suffix.lower() != ".svg":
            self._record_missing(icon_id, icon_role, "ICON_NON_SVG_PATH_REJECTED", report, context, normalized_path=str(path))
            return None
        if not path.exists():
            self._record_missing(icon_id, icon_role, "ICON_NORMALIZED_FILE_MISSING", report, context, normalized_path=_display_path(path))
            return None
        return IconResolution(
            icon_id=icon_id,
            icon_role=icon_role,
            icon_family=str(record.get("source_family") or "unknown"),
            normalized_path=path,
            source_path=_clean(record.get("source_path")),
            color_token=self._color_token(component, role_entry),
            stroke_width=self._stroke_width(component, role_entry),
            size_in=self._size_in(component, role_entry),
            role_entry=role_entry,
            manifest_record=record,
        )

    def _color_token(self, component: dict[str, Any], role_entry: dict[str, Any] | None) -> str:
        return (
            _clean(component.get("icon_color_token"))
            or _clean((role_entry or {}).get("default_color_token"))
            or "accent"
        )

    def _stroke_width(self, component: dict[str, Any], role_entry: dict[str, Any] | None) -> float:
        explicit = _float_or_none(component.get("icon_stroke_width"))
        if explicit is not None:
            return explicit
        stroke = self.style_tokens.get("stroke") if isinstance(self.style_tokens.get("stroke"), dict) else {}
        token_name = _clean((role_entry or {}).get("stroke_width_token")) or "default_stroke_width"
        return float(stroke.get(token_name) or stroke.get("default_stroke_width") or 2)

    def _size_in(self, component: dict[str, Any], role_entry: dict[str, Any] | None) -> float:
        explicit = _float_or_none(component.get("icon_size"))
        size_policy = self.style_tokens.get("size_policy") if isinstance(self.style_tokens.get("size_policy"), dict) else {}
        maximum = float(size_policy.get("maximum_template_icon_size_in") or 0.32)
        if explicit is not None:
            return min(max(0.05, explicit), maximum)
        token_name = _clean((role_entry or {}).get("default_size")) or "metadata_icon_size_in"
        return min(max(0.05, float(size_policy.get(token_name) or size_policy.get("metadata_icon_size_in") or 0.16)), maximum)

    def _record_unresolved_role(
        self,
        role: str,
        report: dict[str, Any] | None,
        context: dict[str, Any] | None,
    ) -> None:
        if report is None:
            return
        entry = {
            "code": "ICON_ROLE_UNRESOLVED",
            "icon_role": role,
            "message": f"Icon role `{role}` is not present in icon_role_map.json.",
            "context": context or {},
        }
        report["unresolved_icon_roles"].append(entry)

    def _record_missing(
        self,
        icon_id: str | None,
        icon_role: str | None,
        code: str,
        report: dict[str, Any] | None,
        context: dict[str, Any] | None,
        **details: Any,
    ) -> None:
        if report is None:
            return
        entry = {
            "code": code,
            "icon_id": icon_id,
            "icon_role": icon_role,
            "message": _missing_message(code, icon_id, icon_role),
            "context": context or {},
        }
        entry.update(details)
        report["missing_icons"].append(entry)

    def record_used(
        self,
        resolution: IconResolution,
        report: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        color_hex: str | None = None,
        bounds: dict[str, Any] | None = None,
        relationship_id: str | None = None,
        object_id: int | str | None = None,
        object_name: str | None = None,
        object_description: str | None = None,
        slide_part: str | None = None,
    ) -> None:
        asset_path = _display_path(resolution.normalized_path)
        report["icons_used"].append(
            {
                "icon_id": resolution.icon_id,
                "icon_role": resolution.icon_role,
                "icon_family": resolution.icon_family,
                "normalized_path": asset_path,
                "source_path": resolution.source_path,
                "color_token": resolution.color_token,
                "color_hex": color_hex,
                "stroke_width": resolution.stroke_width,
                "size_in": resolution.size_in,
                "bounds": bounds or {},
                "relationship_id": relationship_id,
                "object_id": object_id,
                "object_name": object_name,
                "object_description": object_description,
                "slide_part": slide_part,
                "context": context or {},
            }
        )
        if asset_path not in report["icon_asset_paths"]:
            report["icon_asset_paths"].append(asset_path)
        if resolution.icon_family not in report["icon_family"]:
            report["icon_family"].append(resolution.icon_family)
            report["icon_family"].sort()

    def _repo_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else self.repo_root / candidate

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


def _clean(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _normalize_hex_color(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not stripped.startswith("#"):
        stripped = f"#{stripped}"
    return stripped if re.fullmatch(r"#[0-9A-Fa-f]{6}", stripped) else None


def _number_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.3f}".rstrip("0").rstrip(".")


def _missing_message(code: str, icon_id: str | None, icon_role: str | None) -> str:
    subject = icon_id or icon_role or "icon"
    messages = {
        "NO_ICON_CANDIDATES": "No preferred or fallback icon ids are available.",
        "ICON_ASSET_MISSING": "No matching allowed normalized SVG icon record was found.",
        "ICON_NOT_ALLOWED_FOR_TEMPLATE": "Icon record exists but is not allowed for template use.",
        "ICON_NORMALIZED_PATH_MISSING": "Icon record lacks a normalized SVG path.",
        "ICON_NON_SVG_PATH_REJECTED": "Icon normalized path is not an SVG and was rejected.",
        "ICON_NORMALIZED_FILE_MISSING": "Icon normalized SVG file is missing.",
    }
    return f"{messages.get(code, 'Icon could not be resolved')} ({subject})."


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()).as_posix())
    except ValueError:
        return str(path.as_posix())
