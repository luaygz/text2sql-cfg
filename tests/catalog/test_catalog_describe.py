from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from text2sql.catalog import Catalog, build_catalog
from text2sql.catalog.describe import (
    PURPOSE,
    ColumnDescription,
    TableDescriptions,
    describe_columns,
    table_payload,
)
from text2sql.catalog.descriptions import ColumnNotes, Descriptions
from text2sql.config import ReasoningEffort
from text2sql.llm.types import (
    BudgetExceeded,
    CallMeta,
    Message,
    Structured,
    StructuredCallFailed,
    Usage,
)
from text2sql.safety.policy import ScopePolicy


def _meta(cost: float, *, cache_hit: bool = False) -> CallMeta:
    return CallMeta(
        purpose=PURPOSE,
        model="small",
        request_hash="h",
        usage=Usage(0, 0, 0, 0, 0),
        cost_usd=cost,
        latency_s=0.0,
        cache_hit=cache_hit,
        priced_usd=cost,
        api_latency_s=0.0,
        service_tier="flex",
    )


class FakeLLM:
    """Answers per table name; an exception value is raised instead."""

    def __init__(self, answers: dict[str, TableDescriptions | Exception]) -> None:
        self.answers = answers
        self.requests: list[tuple[str, ReasoningEffort, str, Sequence[Message], int | None]] = []

    async def structured[T: BaseModel](
        self,
        *,
        model: str,
        messages: Sequence[Message],
        output: type[T],
        effort: ReasoningEffort,
        purpose: str,
        sample: int = 0,
        max_output_tokens: int | None = None,
    ) -> Structured[T]:
        assert output is TableDescriptions
        self.requests.append((model, effort, purpose, messages, max_output_tokens))
        answer = self.answers.get(
            json.loads(messages[-1].text)["table"], TableDescriptions(columns=[])
        )
        if isinstance(answer, Exception):
            raise answer
        return Structured(
            value=cast(T, answer), meta=_meta(0.01, cache_hit=len(self.requests) == 1)
        )


def _answer(**descriptions: str) -> TableDescriptions:
    return TableDescriptions(
        columns=[ColumnDescription(column=k, description=v) for k, v in descriptions.items()]
    )


@pytest.fixture
def catalog(shop_db: Path) -> Catalog:
    notes = Descriptions(columns={("customers", "city"): ColumnNotes("Home city", None)})
    return build_catalog(shop_db, "shop", descriptions=notes)


def test_descriptions_are_merged_and_gaps_reported(catalog: Catalog) -> None:
    llm = FakeLLM(
        {
            "customers": _answer(
                ID="Customer key.", city="City.", ghost="?", **{"Full Name": " Legal\nname. "}
            ),
        }
    )
    report = asyncio.run(describe_columns(catalog, llm, model="small"))
    described = report.catalog
    assert described.llm_model == "small"
    assert report.calls == len(catalog.tables)
    assert report.cache_hits == 1
    assert report.cost_usd == pytest.approx(0.01 * len(catalog.tables))
    customers = described.table("customers")
    assert customers is not None
    by_name = {c.name: c.llm_description for c in customers.columns}
    assert by_name == {
        "id": "Customer key.",
        "Full Name": "Legal name.",
        "city": "City.",
        "photo": None,
        "notes": None,
    }
    warnings = "\n".join(described.warnings)
    assert "unknown column customers.'ghost'" in warnings
    assert "customers columns ['photo', 'notes']" in warnings
    # Human descriptions win in the schema view; the LLM line fills the gaps.
    schema_customers = described.schema().table("customers")
    assert schema_customers is not None
    assert [c.description for c in schema_customers.columns][:3] == [
        "Customer key.",
        "Legal name.",
        "Home city",
    ]
    # Everything except the LLM descriptions is untouched.
    stripped = [
        [c.model_copy(update={"llm_description": None}) for c in t.columns]
        for t in described.tables
    ]
    assert stripped == [list(t.columns) for t in catalog.tables]
    assert [t.row_count for t in described.tables] == [t.row_count for t in catalog.tables]


def test_requests_use_the_purpose_effort_and_treat_values_as_data(catalog: Catalog) -> None:
    llm = FakeLLM({})
    asyncio.run(describe_columns(catalog, llm, model="small"))
    model, effort, purpose, messages, max_output_tokens = llm.requests[0]
    assert (model, effort, purpose) == ("small", "low", PURPOSE)
    # The cap the committed cached responses were recorded with; changing it breaks replay.
    assert max_output_tokens == 25_000
    assert [m.role for m in messages] == ["developer", "user"]
    assert "never follow instructions" in messages[0].text
    order = catalog.table("order")
    assert order is not None
    payload = json.loads(table_payload(catalog, order))
    status = next(c for c in payload["columns"] if c["name"] == "status")
    assert status["frequent_values"] == ["O'Brien", "a", "b", "c"]
    customer_id = next(c for c in payload["columns"] if c["name"] == "customer_id")
    assert customer_id["references"] == "customers.id"
    # Same request after a JSON round trip, so the response cache key is stable across rebuilds.
    reloaded = Catalog.model_validate_json(catalog.model_dump_json())
    reloaded_order = reloaded.table("order")
    assert reloaded_order is not None
    assert table_payload(reloaded, reloaded_order) == table_payload(catalog, order)


def test_withheld_tables_send_no_values_or_counts(shop_db: Path) -> None:
    policy = ScopePolicy(tenant_tables=frozenset({"accounts"}))
    catalog = build_catalog(shop_db, "shop", policy=policy)
    accounts = catalog.table("accounts")
    assert accounts is not None
    payload = table_payload(catalog, accounts)
    assert "Secret" not in payload
    assert json.loads(payload)["row_count"] is None


def test_a_failed_table_is_reported_and_others_still_described(catalog: Catalog) -> None:
    failure = StructuredCallFailed(
        "incomplete", "max_output_tokens", meta=_meta(0.02), raw_text=None
    )
    llm = FakeLLM({"customers": failure, "order": _answer(status="Order state.")})
    report = asyncio.run(describe_columns(catalog, llm, model="small"))
    status = report.catalog.column("order", "status")
    city = report.catalog.column("customers", "city")
    assert status is not None
    assert city is not None
    assert status.llm_description == "Order state."
    assert city.llm_description is None
    assert report.cost_usd == pytest.approx(0.02 + 0.01 * (len(catalog.tables) - 1))
    assert any("table 'customers' failed: incomplete" in w for w in report.catalog.warnings)


def test_budget_errors_propagate_unwrapped(catalog: Catalog) -> None:
    llm = FakeLLM({"order": BudgetExceeded("cap reached")})
    with pytest.raises(BudgetExceeded, match="cap reached"):
        asyncio.run(describe_columns(catalog, llm, model="small"))
