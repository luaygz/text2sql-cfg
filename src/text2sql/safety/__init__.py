"""Safety layers 2 and 4 (AST validation, tenant scoping), the guard composing all four layers,
and the safety event log.

Layer 1 (the grammar) lives in `text2sql.grammar`, layer 3 (the sandboxed executor) in
`text2sql.execution`; `QueryGuard` runs a query through all four. docs/THREAT_MODEL.md describes
what each layer defends against.
"""

from text2sql.safety.errors import Layer, SafetyError, ScopeViolation, ValidationError
from text2sql.safety.events import SafetyEvent, SafetyEventLog
from text2sql.safety.guard import GuardRejection, GuardResult, QueryGuard, access_policy
from text2sql.safety.policy import ScopeContext, ScopePolicy
from text2sql.safety.scoping import (
    TENANT_PARAM,
    USER_PARAM,
    ScopedQuery,
    ScopeRule,
    apply_scope,
    verify_scope,
)
from text2sql.safety.validator import ALLOWED_FUNCTIONS, Rule, ValidationConfig, validate_sql

__all__ = [
    "ALLOWED_FUNCTIONS",
    "TENANT_PARAM",
    "USER_PARAM",
    "GuardRejection",
    "GuardResult",
    "Layer",
    "QueryGuard",
    "Rule",
    "SafetyError",
    "SafetyEvent",
    "SafetyEventLog",
    "ScopeContext",
    "ScopePolicy",
    "ScopeRule",
    "ScopeViolation",
    "ScopedQuery",
    "ValidationConfig",
    "ValidationError",
    "access_policy",
    "apply_scope",
    "validate_sql",
    "verify_scope",
]
