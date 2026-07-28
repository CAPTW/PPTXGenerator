from __future__ import annotations

from .backend_selector import BackendSelection, select_backend
from .minimal_ooxml_backend import MinimalOoxmlBackend

__all__ = ["BackendSelection", "MinimalOoxmlBackend", "select_backend"]
