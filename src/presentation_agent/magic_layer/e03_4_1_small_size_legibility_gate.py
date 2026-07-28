"""Small-size legibility gate for v7.1 rendered icon cells."""

from __future__ import annotations

from typing import Any


def build_small_size_legibility_report_v7_1(cell_rows: list[dict[str, Any]]) -> dict[str, Any]:
    roles = sorted({row["role_id"] for row in cell_rows})
    p0_roles = sorted({row["role_id"] for row in cell_rows if row.get("priority") == "P0_REQUIRED_SEMANTIC"})
    p1_roles = sorted({row["role_id"] for row in cell_rows if row.get("priority") == "P1_HIGH_REUSE"})
    p0_visible_16 = _role_count(cell_rows, "P0_REQUIRED_SEMANTIC", 16)
    p0_visible_24 = _role_count(cell_rows, "P0_REQUIRED_SEMANTIC", 24)
    p0_visible_32 = _role_count(cell_rows, "P0_REQUIRED_SEMANTIC", 32)
    p1_visible_16 = _role_count(cell_rows, "P1_HIGH_REUSE", 16)
    p1_visible_24 = _role_count(cell_rows, "P1_HIGH_REUSE", 24)
    p1_visible_32 = _role_count(cell_rows, "P1_HIGH_REUSE", 32)
    p0_failures = [
        role
        for role in p0_roles
        if not all(_role_visible(cell_rows, role, size) for size in (16, 24, 32))
    ]
    p1_failures = [
        role
        for role in p1_roles
        if not _role_visible(cell_rows, role, 24) or not _role_visible(cell_rows, role, 32) or not _role_visible(cell_rows, role, 16)
    ]
    return {
        "schema_name": "icon_fixture_small_size_legibility_report",
        "status": "passed" if not p0_failures and not p1_failures else "failed",
        "role_count": len(roles),
        "p0_role_count": len(p0_roles),
        "p1_role_count": len(p1_roles),
        "p0_visible_at_16px_count": p0_visible_16,
        "p0_visible_at_24px_count": p0_visible_24,
        "p0_visible_at_32px_count": p0_visible_32,
        "p1_visible_at_16px_count": p1_visible_16,
        "p1_visible_at_24px_count": p1_visible_24,
        "p1_visible_at_32px_count": p1_visible_32,
        "p0_legibility_failures": p0_failures,
        "p1_legibility_failures": p1_failures,
    }


def _role_visible(rows: list[dict[str, Any]], role_id: str, size: int) -> bool:
    matches = [row for row in rows if row.get("role_id") == role_id and row.get("size_px") == size]
    return bool(matches) and all(row.get("visible") for row in matches)


def _role_count(rows: list[dict[str, Any]], priority: str, size: int) -> int:
    return len({row["role_id"] for row in rows if row.get("priority") == priority and row.get("size_px") == size and row.get("visible")})
