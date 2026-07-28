from __future__ import annotations

from .common import NATIVE_TARGETS, RASTER_TARGETS


def is_native_target(target: str) -> bool:
    return target in NATIVE_TARGETS


def is_raster_target(target: str) -> bool:
    return target in RASTER_TARGETS
