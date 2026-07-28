"""Contract surfaces for PPTXlocal.

The package keeps the legacy root ``presentation_agent.contracts`` imports
available while adding executable Template Contract V2 gates under submodules.
"""

from __future__ import annotations

from ..legacy_non_pptx_modules.contracts import *  # noqa: F403
from .contract_gate import (
    GateFinding,
    GateResult,
    compile_route_gate,
    contract_preflight_gate,
    post_compile_structural_gate,
    protected_zone_gate,
    source_bound_deck_gate,
)
from .template_contract_v2 import (
    TEMPLATE_CONTRACT_V2_SCHEMA_PATH,
    ContractValidationError,
    load_template_contract,
    validate_template_contract_payload,
)
from .warning_policy import (
    DEFAULT_FATAL_WARNING_CODES,
    DEFAULT_WARNING_TAXONOMY,
    WarningPolicyFinding,
    WarningPolicyResult,
    evaluate_warning_records,
)

__all__ = [
    "ContractValidationError",
    "DEFAULT_FATAL_WARNING_CODES",
    "DEFAULT_WARNING_TAXONOMY",
    "GateFinding",
    "GateResult",
    "TEMPLATE_CONTRACT_V2_SCHEMA_PATH",
    "WarningPolicyFinding",
    "WarningPolicyResult",
    "compile_route_gate",
    "contract_preflight_gate",
    "evaluate_warning_records",
    "load_template_contract",
    "post_compile_structural_gate",
    "protected_zone_gate",
    "source_bound_deck_gate",
    "validate_template_contract_payload",
]
