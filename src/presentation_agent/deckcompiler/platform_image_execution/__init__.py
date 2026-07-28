"""Platform-managed image execution contracts kept separate from Phase 4A transport."""

from .contracts import build_capability_attestation, hash_bound_payload, verify_hash_bound_payload
from .ingestion import (
    FinalizedImageAttempt,
    RecordedAttemptAudit,
    finalize_platform_image_attempt,
    normalize_generated_image,
    verify_recorded_image_attempt,
)

__all__ = [
    "FinalizedImageAttempt",
    "RecordedAttemptAudit",
    "build_capability_attestation",
    "finalize_platform_image_attempt",
    "hash_bound_payload",
    "normalize_generated_image",
    "verify_hash_bound_payload",
    "verify_recorded_image_attempt",
]
