"""Request and response bodies of the demo API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from text2sql.config import QueryMode

DB_ID_PATTERN = r"^[A-Za-z0-9_]{1,64}$"


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AskBody(_Body):
    question: str = Field(min_length=1, max_length=2000)
    evidence: str | None = Field(default=None, max_length=4000)
    db_id: str = Field(pattern=DB_ID_PATTERN)
    tenant_id: StrictInt | None = None
    """Optional assertion of the signed-in tenant; never used as the scope (see ADR-019)."""
    user_id: StrictInt | None = None
    """Optional assertion of the signed-in user; never used as the scope."""
    preset: str | None = Field(default=None, max_length=64)


class LoginBody(_Body):
    tenant_id: StrictInt
    user_id: StrictInt | None = None


class GrammarCheckBody(_Body):
    text: str = Field(min_length=1, max_length=8000)


class ExampleQuestion(_Body):
    question: str
    evidence: str | None = None
    label: str


class DatabaseInfo(_Body):
    db_id: str
    dataset: Literal["bird", "saas"]
    mode: QueryMode
    tables: int
    requires_login: bool
    """Tenant-mode databases take the caller's identity from the session."""
    examples: tuple[ExampleQuestion, ...]
    attack: ExampleQuestion
    """A canned injection question for this database."""
    attack_sql: str
    """A hand-written malicious query the page feeds to the grammar check."""


class DatabasesResponse(_Body):
    databases: tuple[DatabaseInfo, ...]
    presets: tuple[str, ...]
    default_preset: str


class GrammarInfo(_Body):
    db_id: str
    mode: QueryMode
    fingerprint: str
    definition: str
    chars: int
    rules: int
    api_load: float
    fits_api_budget: bool


class GrammarCheckResult(_Body):
    accepted: bool
    kind: Literal["sql", "abstain"] | None = None
    error: str | None = None
    """The local lark parser's message when the text is rejected."""


class UserInfo(_Body):
    user_id: int
    name: str
    role: str


class TenantInfo(_Body):
    tenant_id: int
    name: str
    users: tuple[UserInfo, ...]


class Identity(_Body):
    tenant_id: int
    tenant_name: str
    user_id: int | None
    user_name: str | None


class SessionResponse(_Body):
    identity: Identity | None
