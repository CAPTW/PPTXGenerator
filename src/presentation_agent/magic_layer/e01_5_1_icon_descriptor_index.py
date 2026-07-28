"""Descriptor index for the E01.5.1 curated icon library."""

from __future__ import annotations

from typing import Any


def build_curated_icon_descriptor_index(taxonomy: dict[str, Any], render_index: dict[str, Any]) -> dict[str, Any]:
    role_specs = {role["role"]: role for role in taxonomy["roles"]}
    records = []
    for render in render_index.get("records", []):
        role = render["role"]
        spec = role_specs.get(role, {"aliases": [], "search_keywords": []})
        records.append(
            {
                "role": role,
                "semantic_aliases": spec.get("aliases", []),
                "filename_aliases": [role, role.replace("_", "-")],
                "search_keywords": spec.get("search_keywords", []),
                "shape_descriptors": {
                    "edge_descriptor": render["edge_descriptor"],
                    "mask_descriptor": render["mask_descriptor"],
                    "bbox_descriptor": render["bbox_descriptor"],
                    "stroke_density": render["stroke_density"],
                    "aspect_balance": render["aspect_balance"],
                },
                "nearest_neighbors": _neighbors(role, render_index),
            }
        )
    return {
        "schema_name": "curated_icon_descriptor_index",
        "status": "passed" if records else "failed",
        "descriptor_count": len(records),
        "records": records,
        "crop_hash_only_matching_allowed": False,
        "canva_parity_claimed": False,
    }


def _neighbors(role: str, render_index: dict[str, Any]) -> list[str]:
    family_token = role.split("_")[0]
    candidates = [record["role"] for record in render_index.get("records", []) if record["role"] != role and record["role"].startswith(family_token)]
    return candidates[:5]
