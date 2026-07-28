from __future__ import annotations

from pathlib import Path
from typing import Any

from .powerpoint_com_renderer import _render_backend


def render_with_libreoffice(pptx_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    return _render_backend(pptx_path, out_dir, "libreoffice")
