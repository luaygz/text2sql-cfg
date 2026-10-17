"""Adversarial case file (evals/safety/cases.yaml): one SQL attack per case, grouped by category.

A category states what every one of its cases expects and which layers are responsible for it;
a case may override both. Expectations:

- `reject`: the guard must stop the query before layer 3 sees it, and every responsible layer
  must stop it on its own.
- `contain`: ordinary-looking SQL the guard may run (cross-tenant probes); no result may leak, and
  each responsible layer alone must stop it or run it without a leak.
- `bounded`: valid SQL that tries to exhaust resources; it may reach layer 3, which must stop it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from text2sql.config import REPO_ROOT
from text2sql.safety import Layer

CASES_PATH: Final = REPO_ROOT / "evals" / "safety" / "cases.yaml"

Expectation = Literal["reject", "contain", "bounded"]
Cell = int | float | str | None

_EXECUTING_LAYERS: Final[frozenset[Layer]] = frozenset({"scoping", "executor"})


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CaseCategory(_Frozen):
    description: str
    expect: Expectation
    layers: tuple[Layer, ...] = Field(min_length=1)


class Repeat(_Frozen):
    """Text repeated `times` times, for attacks whose size is the point (long literals, SQL)."""

    text: str = Field(min_length=1)
    times: int = Field(ge=1, le=100_000)


class _CaseSpec(_Frozen):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    category: str
    sql: str = Field(min_length=1)
    expand: dict[str, Repeat] = {}
    """`{NAME}` in `sql` is replaced by the repeated text."""
    tenant: int | None = None
    user: int | None = None
    expect: Expectation | None = None
    layers: tuple[Layer, ...] | None = None
    expect_rows: list[list[Cell]] | None = None
    note: str = ""


class SafetyCase(_Frozen):
    id: str
    category: str
    sql: str
    tenant: int
    user: int | None
    """Set for user mode: owner-scoped tables are also filtered to this user's rows."""
    expect: Expectation
    layers: tuple[Layer, ...]
    """Layers that must each stop the case (or, for `contain`, never leak) when run alone."""
    expect_rows: list[list[Cell]] | None
    """For `contain` cases: the exact result the caller's own data gives; anything else leaked."""
    note: str

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.expect == "contain" and not set(self.layers) <= _EXECUTING_LAYERS:
            raise ValueError(f"{self.id}: only scoping and executor can contain a query")
        if self.expect_rows is not None and self.expect != "contain":
            raise ValueError(f"{self.id}: expect_rows only applies to contain cases")
        return self


class CaseFile(_Frozen):
    version: int
    default_tenant: int
    categories: dict[str, CaseCategory]
    cases: list[_CaseSpec] = Field(min_length=1)


def load_cases(path: Path = CASES_PATH) -> list[SafetyCase]:
    """Every case with category defaults applied; ids are unique, categories must exist."""
    spec = CaseFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    cases: list[SafetyCase] = []
    seen: set[str] = set()
    for raw in spec.cases:
        category = spec.categories.get(raw.category)
        if category is None:
            raise ValueError(f"{raw.id}: unknown category {raw.category!r}")
        if raw.id in seen:
            raise ValueError(f"duplicate case id {raw.id!r}")
        seen.add(raw.id)
        sql = raw.sql
        for name, repeat in raw.expand.items():
            if "{" + name + "}" not in sql:
                raise ValueError(f"{raw.id}: expand key {name!r} does not occur in sql")
            sql = sql.replace("{" + name + "}", repeat.text * repeat.times)
        cases.append(
            SafetyCase(
                id=raw.id,
                category=raw.category,
                sql=sql,
                tenant=spec.default_tenant if raw.tenant is None else raw.tenant,
                user=raw.user,
                expect=raw.expect or category.expect,
                layers=raw.layers or category.layers,
                expect_rows=raw.expect_rows,
                note=raw.note,
            )
        )
    return cases
