"""Hypothesis strategies: grammar-shaped SELECTs over the fixture schema.

Every generated query names only visible columns, qualifies every column, aliases every select
item (`c1`, `c2`, ...), joins along foreign keys, and ends with `LIMIT 1000`, which is larger than
any result on the fixture, so scoped and oracle results compare as complete multisets.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import strategies as st

MAX_ROWS = 1000

COLUMNS: dict[str, dict[str, str]] = {
    "plans": {"id": "int", "name": "text", "monthly_price": "int"},
    "users": {"id": "int", "name": "text", "email": "text"},
    "accounts": {
        "id": "int", "owner_user_id": "int", "name": "text", "plan_id": "int", "country": "text"
    },
    "deals": {
        "id": "int", "owner_user_id": "int", "account_id": "int", "title": "text",
        "amount": "int", "stage": "text", "created_at": "text",
    },
}  # fmt: skip

JOINS: dict[str, list[tuple[str, str]]] = {
    "plans": [("accounts", "{r}.plan_id = {l}.id")],
    "users": [("accounts", "{r}.owner_user_id = {l}.id"), ("deals", "{r}.owner_user_id = {l}.id")],
    "accounts": [
        ("deals", "{r}.account_id = {l}.id"),
        ("plans", "{r}.id = {l}.plan_id"),
        ("users", "{r}.id = {l}.owner_user_id"),
        ("accounts", "{r}.name = {l}.name"),
    ],
    "deals": [
        ("accounts", "{r}.id = {l}.account_id"),
        ("users", "{r}.id = {l}.owner_user_id"),
        ("deals", "{r}.title = {l}.title"),
    ],
}

SUBQUERY_FILTERS: dict[str, list[str]] = {
    "accounts": [
        "T1.id IN (SELECT T3.account_id FROM deals AS T3 WHERE T3.amount > {n})",
        "EXISTS (SELECT 1 FROM deals AS T3 WHERE T3.account_id = T1.id AND T3.stage = 'won')",
        "T1.name IN (SELECT T3.name FROM accounts AS T3 WHERE T3.country = 'US')",
    ],
    "deals": [
        "T1.account_id IN (SELECT T3.id FROM accounts AS T3 WHERE T3.name = 'Acme')",
        "T1.amount > (SELECT AVG(T3.amount) FROM deals AS T3)",
        "T1.amount >= (SELECT MAX(T3.amount) FROM deals AS T3 WHERE T3.account_id = T1.account_id)",
    ],
    "users": ["EXISTS (SELECT 1 FROM accounts AS T3 WHERE T3.owner_user_id = T1.id)"],
    "plans": ["T1.id IN (SELECT T3.plan_id FROM accounts AS T3 UNION SELECT 3)"],
}

TEXT_VALUES = ("Acme", "Globex", "won", "open", "US", "CANARY-T2", "Alice 1")


@dataclass(frozen=True)
class Query:
    sql: str
    base: str
    """Table of alias T1 in the innermost SELECT; `FROM {base} AS T1` occurs in `sql`."""


@st.composite
def _predicate(draw: st.DrawFn, alias: str, table: str) -> str:
    column, kind = draw(st.sampled_from(sorted(COLUMNS[table].items())))
    ref = f"{alias}.{column}"
    if kind == "int":
        n = draw(st.integers(0, 400))
        return draw(
            st.sampled_from(
                [f"{ref} > {n}", f"{ref} = {n}", f"{ref} BETWEEN {n} AND {n + 150}",
                 f"{ref} IS NOT NULL"]
            )
        )  # fmt: skip
    value = draw(st.sampled_from(TEXT_VALUES))
    return draw(
        st.sampled_from(
            [f"{ref} = '{value}'", f"{ref} LIKE '{value[0]}%'", f"{ref} IS NULL",
             f"UPPER({ref}) <> '{value.upper()}'"]
        )
    )  # fmt: skip


@st.composite
def _core(draw: st.DrawFn, *, single_column: bool = False) -> Query:
    """One SELECT without LIMIT whose items are aliased c1..cN."""
    base = draw(st.sampled_from(sorted(COLUMNS)))
    sources = [("T1", base)]
    joins = ""
    if draw(st.booleans()):
        other, condition = draw(st.sampled_from(JOINS[base]))
        kind = draw(st.sampled_from(["JOIN", "LEFT JOIN", "INNER JOIN"]))
        joins = f" {kind} {other} AS T2 ON {condition.format(l='T1', r='T2')}"
        sources.append(("T2", other))

    filters = [
        draw(_predicate(*draw(st.sampled_from(sources)))) for _ in range(draw(st.integers(0, 2)))
    ]
    if draw(st.booleans()):
        template = draw(st.sampled_from(SUBQUERY_FILTERS[base]))
        filters.append(template.format(n=draw(st.integers(0, 400))))
    connective = draw(st.sampled_from([" AND ", " OR "]))
    where = f" WHERE {connective.join(filters)}" if filters else ""

    alias, table = draw(st.sampled_from(sources))
    column = draw(st.sampled_from(sorted(COLUMNS[table])))
    if not single_column and draw(st.booleans()):
        int_alias, int_table = draw(st.sampled_from(sources))
        ints = sorted(c for c, k in COLUMNS[int_table].items() if k == "int")
        int_ref = f"{int_alias}.{draw(st.sampled_from(ints))}"
        aggregate = draw(st.sampled_from(
            ["COUNT(*)", f"SUM({int_ref})", f"MAX({int_ref})", f"COUNT(DISTINCT {int_ref})"]
        ))  # fmt: skip
        select = f"{alias}.{column} AS c1, {aggregate} AS c2"
        tail = f" GROUP BY {alias}.{column}"
        if draw(st.booleans()):
            tail += f" HAVING {aggregate} > {draw(st.integers(0, 3))}"
    elif single_column:
        select, tail = f"{alias}.{column} AS c1", ""
    else:
        items = draw(st.lists(st.sampled_from([(a, c) for a, t in sources for c in COLUMNS[t]]),
                              min_size=1, max_size=3, unique=True))  # fmt: skip
        select = ", ".join(f"{a}.{c} AS c{i}" for i, (a, c) in enumerate(items, 1))
        tail = ""
    distinct = "DISTINCT " if draw(st.booleans()) else ""
    return Query(f"SELECT {distinct}{select} FROM {base} AS T1{joins}{where}{tail}", base)


@st.composite
def tenant_queries(draw: st.DrawFn) -> Query:
    """A complete query in one of the shapes the grammar produces."""
    shape = draw(st.sampled_from(["plain", "cte", "derived", "union"]))
    limit = f" LIMIT {MAX_ROWS}"
    if shape == "union":
        left = draw(_core(single_column=True))
        right = draw(_core(single_column=True))
        op = draw(st.sampled_from(["UNION", "UNION ALL", "INTERSECT", "EXCEPT"]))
        return Query(f"{left.sql} {op} {right.sql} ORDER BY c1{limit}", left.base)
    inner = draw(_core())
    if shape == "cte":
        return Query(f"WITH cte1 AS ({inner.sql}) SELECT T5.c1 FROM cte1 AS T5{limit}", inner.base)
    if shape == "derived":
        return Query(f"SELECT T5.c1 FROM ({inner.sql}) AS T5{limit}", inner.base)
    order = " ORDER BY c1" if draw(st.booleans()) else ""
    return Query(f"{inner.sql}{order}{limit}", inner.base)
