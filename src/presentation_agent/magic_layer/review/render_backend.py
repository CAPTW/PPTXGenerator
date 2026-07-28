from __future__ import annotations

from typing import Any


def render_if_missing(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {
        "schema": "render_backend_report.v1",
        "status": "RENDER_BACKEND_UNAVAILABLE",
        "pass": False,
        "default_render_performed": False,
        "message": "B01 rendering is optional and disabled unless a future local backend is explicitly configured.",
    }
