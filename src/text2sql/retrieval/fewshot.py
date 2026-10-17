"""Stage 4 few-shot retrieval: the k pool questions whose masked skeletons are closest.

DAIL-SQL masks schema mentions and values out of questions so that similarity is about question
structure; MCS-SQL measured masked-question similarity above plain question similarity on BIRD
dev. Here every pool question is masked by `analyze_question`, the same call (prompt, model and
effort) that masks the test question, so both sides share one masking procedure. The skeletons
are embedded once at build time; a lookup embeds the test skeleton and ranks by cosine.

Pools: "bird" is the filtered BIRD train set (6,601 pairs, `load_bird_train`), "saas" is
data/saas/fewshot_pool.jsonl written by the SaaS eval set builder. Pool SQL is stored in the
grammar's canonical spelling (`normalize_sql`) when it parses, so examples look like what the
grammar lets the model write.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import structlog
from pydantic import BaseModel, ConfigDict

from text2sql.config import ReasoningEffort, get_settings
from text2sql.data.bird import load_bird_train
from text2sql.grammar import normalize_sql
from text2sql.grammar.errors import NormalizationError
from text2sql.llm import CallMeta, StructuredCallFailed
from text2sql.prompts import load_prompt
from text2sql.retrieval.analysis import PROMPT, analyze_question
from text2sql.retrieval.calls import (
    EMBEDDING_DIMENSIONS,
    EmbeddingLLM,
    Matrix,
    RetrievalLLM,
    embed,
)
from text2sql.retrieval.store import Dataset, fewshot_dir, missing
from text2sql.retrieval.types import FewShotExample

PURPOSE = "retrieval.fewshot"
log = structlog.get_logger(__name__)


def saas_pool_path() -> Path:
    return get_settings().data_dir / "saas" / "fewshot_pool.jsonl"


class PoolPair(BaseModel):
    """One question/SQL pair of a pool before masking."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    question: str
    evidence: str | None = None
    sql: str


class PoolItem(PoolPair):
    skeleton: str


class _PoolFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    format_version: Literal[1] = 1
    pool: Dataset
    model: str
    effort: ReasoningEffort
    prompt: str
    """Tag of the analysis prompt that masked the pool."""
    dimensions: int
    skipped: list[str]
    """Ids whose analysis call failed and that are therefore not in the pool."""
    items: list[PoolItem]


def load_pool_pairs(pool: Dataset) -> list[PoolPair]:
    if pool == "bird":
        return [
            PoolPair(
                id=f"train-{e.train_id}",
                question=e.question,
                evidence=e.evidence.strip() or None,
                sql=e.gold_sql,
            )
            for e in load_bird_train()
        ]
    path = saas_pool_path()
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing; it is written by the SaaS eval-set builder")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [PoolPair.model_validate_json(line) for line in lines if line.strip()]


def grammar_spelling(sql: str) -> str:
    try:
        return normalize_sql(sql)
    except NormalizationError:
        return sql


@dataclass(frozen=True)
class FewShotIndex:
    pool: Dataset
    items: tuple[PoolItem, ...]
    vectors: Matrix

    @classmethod
    async def build(
        cls,
        pool: Dataset,
        llm: RetrievalLLM,
        *,
        model: str,
        effort: ReasoningEffort,
        pairs: Sequence[PoolPair] | None = None,
    ) -> tuple[FewShotIndex, list[str]]:
        """Mask, embed and index a pool; returns the index and the ids whose analysis failed."""
        source = list(pairs) if pairs is not None else load_pool_pairs(pool)
        done = 0

        async def mask(pair: PoolPair) -> PoolItem | None:
            nonlocal done
            try:
                result = await analyze_question(
                    llm, question=pair.question, evidence=pair.evidence, model=model, effort=effort
                )
            except StructuredCallFailed as exc:
                log.warning("retrieval.fewshot.mask_failed", id=pair.id, error=str(exc))
                return None
            finally:
                done += 1
                if done % 500 == 0:
                    log.info("retrieval.fewshot.progress", pool=pool, done=done, total=len(source))
            return PoolItem(
                id=pair.id,
                question=pair.question,
                evidence=pair.evidence,
                sql=grammar_spelling(pair.sql),
                skeleton=result.value.skeleton.strip() or pair.question,
            )

        masked = await asyncio.gather(*(mask(p) for p in source))
        items = tuple(m for m in masked if m is not None)
        skipped = [p.id for p, m in zip(source, masked, strict=True) if m is None]
        if not items:
            raise ValueError(f"no question of the {pool} pool could be masked")
        vectors, _ = await embed(llm, [i.skeleton for i in items], purpose=PURPOSE)
        return cls(pool, items, vectors), skipped

    @classmethod
    def load(cls, pool: Dataset) -> FewShotIndex:
        directory = fewshot_dir(pool)
        path = directory / "pool.json"
        if not path.is_file():
            raise missing(path, pool)
        stored = _PoolFile.model_validate_json(path.read_bytes())
        vectors = np.load(directory / "skeletons.npy").astype(np.float32)
        if stored.dimensions != EMBEDDING_DIMENSIONS or vectors.shape != (
            len(stored.items),
            EMBEDDING_DIMENSIONS,
        ):
            raise ValueError(f"{path} does not match the current embedding settings; rebuild it")
        return cls(pool, tuple(stored.items), vectors)

    def save(self, *, model: str, effort: ReasoningEffort, skipped: Sequence[str]) -> Path:
        directory = fewshot_dir(self.pool)
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "skeletons.npy", self.vectors)
        stored = _PoolFile(
            pool=self.pool,
            model=model,
            effort=effort,
            prompt=load_prompt(PROMPT).tag,
            dimensions=EMBEDDING_DIMENSIONS,
            skipped=list(skipped),
            items=list(self.items),
        )
        path = directory / "pool.json"
        path.write_text(stored.model_dump_json(), encoding="utf-8")
        return path

    async def retrieve(
        self, *, skeleton: str, k: int, llm: EmbeddingLLM
    ) -> tuple[list[FewShotExample], list[CallMeta]]:
        """The `k` pool examples with the most similar skeletons, most similar first; examples
        repeating an already chosen question or SQL are skipped."""
        if k <= 0 or not self.items or not skeleton.strip():
            return [], []
        query, meta = await embed(llm, [skeleton.strip()], purpose=PURPOSE)
        scores = self.vectors @ query[0]
        chosen: list[FewShotExample] = []
        seen: set[str] = set()
        for i in np.argsort(-scores, kind="stable"):
            item = self.items[int(i)]
            keys = {" ".join(item.question.lower().split()), " ".join(item.sql.split())}
            if keys & seen:
                continue
            seen |= keys
            chosen.append(
                FewShotExample(question=item.question, evidence=item.evidence, sql=item.sql)
            )
            if len(chosen) == k:
                break
        return chosen, [meta]
