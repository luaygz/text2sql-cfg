"""Worksheet for the human spot check described in the dataset card (data/saas/README.md).

Draws a seeded sample stratified by bucket, executes each gold query read-only for every tenant
the item runs under, and writes a Markdown worksheet with the question, the gold SQL and the
first rows of each result, so a reviewer can judge items without running anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final

from text2sql.config import REPO_ROOT
from text2sql.data.saas import DEFAULT_DB_PATH, load_saas_schema, saas_scope_policy
from text2sql.data.saas.evalset.gold import MAX_GOLD_ROWS, authoring_schema, readable_columns
from text2sql.data.saas.evalset.models import SaasEvalItem
from text2sql.data.saas.evalset.snapshot import seeded_rng
from text2sql.execution import AccessPolicy, ExecutionLimits, QueryResult, SandboxedExecutor

PREVIEW_ROWS: Final = 5
WORKSHEET_PATH: Final = REPO_ROOT / "runs" / "scratch" / "saas_spotcheck.md"
"""Default output: runs/scratch is gitignored; the results go to data/saas/spot_checks.jsonl."""
BUCKETS: Final = ("answerable", "tenant", "unanswerable", "adversarial")


def sample_items(items: Sequence[SaasEvalItem], n: int, seed: int) -> list[SaasEvalItem]:
    """About `n` items, each bucket represented in proportion to its size (at least one)."""
    picked: list[SaasEvalItem] = []
    for bucket in BUCKETS:
        members = sorted((i for i in items if i.bucket == bucket), key=lambda i: i.id)
        if not members:
            continue
        k = min(len(members), max(1, round(n * len(members) / len(items))))
        picked += seeded_rng("spotcheck", seed, bucket).sample(members, k)
    return sorted(picked, key=lambda i: (BUCKETS.index(i.bucket), i.id))


def write_worksheet(
    items: Sequence[SaasEvalItem], out: Path, *, db_path: Path = DEFAULT_DB_PATH
) -> None:
    schema = authoring_schema(load_saas_schema(db_path), saas_scope_policy())
    with SandboxedExecutor(
        db_path,
        limits=ExecutionLimits(timeout_s=10.0, max_rows=MAX_GOLD_ROWS),
        access=AccessPolicy(readable=readable_columns(schema)),
    ) as executor:
        sections = [_section(item, executor) for item in items]
    header = [
        "# SaaS eval set: spot-check worksheet",
        "",
        f"{len(items)} items. For each, check the points in the dataset card (data/saas/README.md,"
        ' "Human spot check") and append one line per item to data/saas/spot_checks.jsonl.',
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(header + sections) + "\n", encoding="utf-8")


def _section(item: SaasEvalItem, executor: SandboxedExecutor) -> str:
    scope = f"tenant {item.tenant_id}" + (f", user {item.user_id}" if item.user_id else "")
    lines = [
        f"## {item.id} ({item.bucket}, {item.difficulty}, {item.split}, {scope})",
        "",
        f"Question: {item.question!r}",
        "",
        f"Expected behaviour: {item.expected}",
    ]
    if item.explanation:
        lines += ["", f"Why it is unanswerable: {item.explanation}"]
    if item.attack is not None:
        a = item.attack
        target = f", names tenant {a.target_tenant_id}" if a.target_tenant_id else ""
        lines += ["", f"Attack: {a.category} / {a.technique}{target}. {a.notes}"]
    if item.gold_sql is not None:
        lines += ["", "```sql", item.gold_sql, "```"]
        for tenant in item.eval_tenants or [item.tenant_id]:
            result = executor.execute(item.gold_sql, item.params(tenant))
            lines += ["", f"Result for tenant {tenant}:", "", *_table(result)]
    if item.provenance.review_notes:
        lines += ["", f"Reviewer notes: {item.provenance.review_notes}"]
    return "\n".join(lines) + "\n"


def _table(result: QueryResult) -> list[str]:
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    rows = [
        "| " + " | ".join(result.columns) + " |",
        "|" + "---|" * len(result.columns),
        *("| " + " | ".join(cell(v) for v in row) + " |" for row in result.rows[:PREVIEW_ROWS]),
    ]
    if len(result.rows) > PREVIEW_ROWS:
        rows.append(f"({len(result.rows)} rows in total)")
    return rows
