from __future__ import annotations

"""Narrow contract slice for the active presentation compile/preview/runtime path."""

from ..non_pptx_modules import contracts as _contracts
from ..non_pptx_modules import state_schemas as _state_schemas


WorkflowGate = _contracts.WorkflowGate
SKILL_NAMES = _contracts.SKILL_NAMES
STATE_SCHEMA_NAMES = _contracts.STATE_SCHEMA_NAMES
COMPAT_STATE_SCHEMA_NAMES = _contracts.COMPAT_STATE_SCHEMA_NAMES

AssetKind = _state_schemas.AssetKind
AssetManifest = _state_schemas.AssetManifest
AssetRecord = _state_schemas.AssetRecord
AssetStatus = _state_schemas.AssetStatus
BatchManifest = _state_schemas.BatchManifest
Blueprint = _state_schemas.Blueprint
BlueprintSlide = _state_schemas.BlueprintSlide
CanonicalGenerationProfile = _state_schemas.CanonicalGenerationProfile
ContractModel = _state_schemas.ContractModel
DeckConstitution = _state_schemas.DeckConstitution
DeckMode = _state_schemas.DeckMode
DesignSystem = _state_schemas.DesignSystem
LayoutLibrary = _state_schemas.LayoutLibrary
LayoutPattern = _state_schemas.LayoutPattern
ProductionBridge = _state_schemas.ProductionBridge
ProductionMode = _state_schemas.ProductionMode
QAStatus = _state_schemas.QAStatus
SchemaModel = _state_schemas.SchemaModel
SlideArchetype = _state_schemas.SlideArchetype
SlideDensityBudget = _state_schemas.SlideDensityBudget
SlideEvidenceClass = _state_schemas.SlideEvidenceClass
SlideLedger = _state_schemas.SlideLedger
SlideLedgerEntry = _state_schemas.SlideLedgerEntry
SlideRole = _state_schemas.SlideRole
StageStatus = _state_schemas.StageStatus
StateCapsule = _state_schemas.StateCapsule
VisualSourcePreference = _state_schemas.VisualSourcePreference
VisualType = _state_schemas.VisualType
VizManifest = _state_schemas.VizManifest
VizRecord = _state_schemas.VizRecord


__all__ = [
    "AssetKind",
    "AssetManifest",
    "AssetRecord",
    "AssetStatus",
    "BatchManifest",
    "Blueprint",
    "BlueprintSlide",
    "COMPAT_STATE_SCHEMA_NAMES",
    "CanonicalGenerationProfile",
    "ContractModel",
    "DeckConstitution",
    "DeckMode",
    "DesignSystem",
    "LayoutLibrary",
    "LayoutPattern",
    "ProductionBridge",
    "ProductionMode",
    "QAStatus",
    "SKILL_NAMES",
    "STATE_SCHEMA_NAMES",
    "SchemaModel",
    "SlideArchetype",
    "SlideDensityBudget",
    "SlideEvidenceClass",
    "SlideLedger",
    "SlideLedgerEntry",
    "SlideRole",
    "StageStatus",
    "StateCapsule",
    "VisualSourcePreference",
    "VisualType",
    "VizManifest",
    "VizRecord",
    "WorkflowGate",
]
