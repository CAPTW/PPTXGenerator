from __future__ import annotations

from typing import Any


def evaluate_asset_policy(asset: dict[str, Any]) -> dict[str, Any]:
    role = str(asset.get("role", "")).lower()
    path = str(asset.get("path", "")).lower()
    if asset.get("semantic") is True and role in {"reference_image", "nonsemantic_image_frame_asset", "image", "picture"}:
        decision = "ASSET_BLOCKED_SEMANTIC_RASTER"
    elif asset.get("bounded") is False or asset.get("full_slide") is True:
        decision = "ASSET_BLOCKED_FULL_SLIDE"
    elif "quarantine" in path:
        decision = "ASSET_BLOCKED_QUARANTINE"
    elif "manual" in path:
        decision = "ASSET_BLOCKED_MANUAL_REVIEW"
    elif role in {"render", "contact_sheet", "overlay_png"} or "contact_sheet" in path or "render" in path:
        decision = "ASSET_BLOCKED_RENDER_OR_CONTACT_SHEET"
    elif role in {"svg_icon_asset", "nonsemantic_image_frame_asset", "none"}:
        decision = "ASSET_ALLOWED"
    else:
        decision = "ASSET_ALLOWED_WITH_WARNING" if asset.get("bounded", True) else "ASSET_BLOCKED_UNKNOWN_PROVENANCE"
    return {"schema": "compiler_asset_policy_result.v1", "decision": decision, "pass": decision.startswith("ASSET_ALLOWED"), "asset": asset}
