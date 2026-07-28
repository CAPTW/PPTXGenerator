"""Typed runtime models kept separate from the JSON Schema wire contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProductIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_name: str = "PPTX Generator"
    product_slug: str = "pptx-generator"
    system_name: str = "DeckCompiler"
    system_id: str = "deckcompiler"
    reconstruction_engine: str = "PNGtoPPTX"


class ProducerIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str
    tool_version: str
    runtime: str


class ArtifactProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    created_at: str
    producer: ProducerIdentity
    build_baseline: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    input_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)


class ArtifactEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(pattern=r"^art_[0-9a-f]{20}$")
    artifact_type: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    artifact_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    product: ProductIdentity
    provenance: ArtifactProvenance
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    schema_name: str
    artifact_path: str | None = None
    json_path: str = "$"


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str
    artifact_path: str | None = None
    issues: tuple[ValidationIssue, ...] = Field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_human(self) -> str:
        status = "VALID" if self.valid else "INVALID"
        location = f" path={self.artifact_path}" if self.artifact_path else ""
        lines = [f"{status} {self.schema_name}{location}"]
        for issue in self.issues:
            issue_location = f" path={issue.artifact_path}" if issue.artifact_path else ""
            lines.append(f"- {issue.code} {issue.json_path}{issue_location}: {issue.message}")
        return "\n".join(lines)


__all__ = [
    "ArtifactEnvelope",
    "ArtifactProvenance",
    "ProducerIdentity",
    "ProductIdentity",
    "ValidationIssue",
    "ValidationReport",
]
