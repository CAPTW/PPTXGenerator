"""Governance guards for Magic Layer stages."""

from .scaleout_lock import is_stage_allowed

__all__ = ["is_stage_allowed"]
