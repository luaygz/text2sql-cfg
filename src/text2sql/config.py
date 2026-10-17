"""Runtime configuration, read from environment variables and `.env`, and pipeline presets.

Model names are configuration, not code: see docs/adr/001-openai-cfg.md for why these defaults
were chosen and when they were verified. `PipelineConfig` switches the pipeline's stages for
ablations; `PRESETS` holds the named configurations (docs/adr/014-pipeline.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType, NoneType
from typing import Literal, Self, get_args, get_origin

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
ServiceTier = Literal["auto", "default", "flex"]

REPO_ROOT = Path(__file__).resolve().parents[2]


class QueryMode(StrEnum):
    """How strict the grammar, validator and executor are for a request."""

    BENCHMARK = "benchmark"
    """BIRD: LIMIT optional, no scoping, generous row cap so EX compares full results."""
    PRODUCTION = "production"
    """Single-tenant app: LIMIT required and capped."""
    TENANT = "tenant"
    """Multi-tenant SaaS: production rules plus tenant (and optionally user) scoping."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: SecretStr | None = None

    generator_model: str = "gpt-6.1-sol"
    """Frontier reasoning model for SQL generation, repair and candidate selection."""
    small_model: str = "gpt-6-luna"
    """Cheap model for schema linking, keyword extraction and judging."""
    embedding_model: str = "text-embedding-3-small"
    generator_effort: ReasoningEffort = "low"
    small_effort: ReasoningEffort = "low"
    service_tier: ServiceTier = "flex"
    """Flex is billed at Batch rates (50% off); 429 resource-unavailable is retried."""

    max_spend_usd: float = 30.0
    """Per-run budget. A run aborts once its estimated spend exceeds this."""
    total_spend_cap_usd: float = 50.0
    """Lifetime cap across every run recorded in the spend ledger."""

    cache_dir: Path = REPO_ROOT / "cache" / "llm"
    ledger_path: Path = REPO_ROOT / "runs" / "spend_ledger.jsonl"
    runs_dir: Path = REPO_ROOT / "runs"
    data_dir: Path = REPO_ROOT / "data"
    offline: bool = False
    """Replay from the response cache only; a cache miss raises instead of calling the API."""

    request_timeout_s: float = 900.0
    max_concurrency: int = 8
    max_retries: int = 6
    """Retries after the first attempt on 429, 5xx, timeouts and connection errors."""
    max_output_tokens: int = 4_096
    """Default cap (reasoning plus visible output) for every Responses call, overridable per
    call; also the output allowance in the budget pre-check. Kept low because runaway outputs
    that fill the cap have been observed (docs/adr/006-llm-client.md)."""
    embedding_batch_size: int = 256

    pricing_path: Path = REPO_ROOT / "config" / "pricing.yaml"
    phase: str = Field(default="dev", validation_alias=AliasChoices("T2SQL_PHASE", "phase"))
    """Label on every spend-ledger row (env `T2SQL_PHASE`), e.g. `dev`, `eval-dev`, `eval-test`."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


Selector = Literal["first", "vote", "judge", "unit_test"]


class PipelineConfig(BaseModel):
    """Which pipeline stages run and how. Every stage can be switched off for an ablation.

    Strategy names refer to `text2sql.generation.STRATEGIES`; the pipeline checks them, since
    this module cannot import the generation package. `strategies` is a schedule that cycles:
    candidate i uses `strategies[i % len(strategies)]`, and a repeated name gets the next sample
    index.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    use_evidence: bool = True
    question_analysis: bool
    value_retrieval: bool
    schema_linking: bool
    fewshot_k: int = Field(ge=0)
    strategies: tuple[str, ...] = Field(min_length=1)
    n_candidates: int = Field(ge=1)
    repair: bool
    max_repairs: int = Field(default=2, ge=0)
    literal_check: bool = False
    """After a candidate executes, check each string it compares a TEXT column with against the
    database; a value that is not stored but has a case/spacing variant (or retrieved values) in
    that column triggers a `value` repair, counted against `max_repairs`. Needs `repair`; skipped
    in tenant mode (ADR-014)."""
    selector: Selector
    judge_threshold: float = Field(default=1.0, gt=0.0, le=1.0)
    """The judge (or unit tests) runs only when the top vote share is below this."""
    cheap_path: bool
    grammar: bool = True
    """False is the "grammar off" ablation: JSON output, then the same guard layers 2-4."""
    generator_effort: ReasoningEffort | None = None
    """Overrides the reasoning effort of generator-tier strategies; None keeps each strategy's."""
    explain: bool = False
    """Ask the small model for a one-paragraph explanation of the chosen SQL."""
    bird_conventions: bool = True
    """Benchmark mode only: include the BIRD annotation-style conventions in generation prompts.
    Off is the ablation that measures how much of the score is matching BIRD's gold style."""

    @model_validator(mode="after")
    def _stages_have_inputs(self) -> Self:
        needs_analysis = {
            "value_retrieval": self.value_retrieval,
            "schema_linking": self.schema_linking,
            "fewshot_k > 0": self.fewshot_k > 0,
            "cheap_path": self.cheap_path,
        }
        missing = [name for name, on in needs_analysis.items() if on]
        if missing and not self.question_analysis:
            raise ValueError(f"{', '.join(missing)} need question_analysis (keywords, skeleton)")
        if self.cheap_path and self.n_candidates < 2:
            raise ValueError("cheap_path needs n_candidates >= 2 (it starts with two candidates)")
        if not self.grammar and self.repair:
            # A JSON candidate has no tool-call conversation to continue; comparing grammar on
            # and off is only fair with repair off in both arms.
            raise ValueError(
                "grammar=false needs repair=false (JSON candidates cannot be repaired)"
            )
        if self.literal_check and not self.repair:
            raise ValueError("literal_check needs repair=true (it triggers repair turns)")
        return self


PRESETS: Mapping[str, PipelineConfig] = MappingProxyType(
    {
        # R0 (EXPERIMENTS.md): one candidate, full schema, grammar on, no retrieval, no repair.
        "baseline": PipelineConfig(
            name="baseline",
            question_analysis=False,
            value_retrieval=False,
            schema_linking=False,
            fewshot_k=0,
            strategies=("direct_full",),
            n_candidates=1,
            repair=False,
            selector="first",
            cheap_path=False,
        ),
        # `best` at low reasoning effort: the lowest-latency configuration measured in R0-R13.
        "fast": PipelineConfig(
            name="fast",
            question_analysis=False,
            value_retrieval=False,
            schema_linking=False,
            fewshot_k=0,
            strategies=("direct_full", "divide_conquer", "query_plan"),
            n_candidates=1,
            repair=True,
            max_repairs=2,
            literal_check=True,
            selector="vote",
            cheap_path=False,
            generator_effort="low",
        ),
        # The final choice (EXPERIMENTS.md, R13): one direct full-schema candidate at medium
        # effort with repair turns and the literal check. Retrieval, linking as a filter,
        # few-shots, multi-candidate voting, the judge and unit tests did not earn their cost on
        # dev. The schedule names two more full-schema strategies so that an N-sweep
        # (`--set n_candidates=k`, voted) reuses the cached prompt prefix.
        "best": PipelineConfig(
            name="best",
            question_analysis=False,
            value_retrieval=False,
            schema_linking=False,
            fewshot_k=0,
            strategies=("direct_full", "divide_conquer", "query_plan"),
            n_candidates=1,
            repair=True,
            max_repairs=2,
            literal_check=True,
            selector="vote",
            cheap_path=False,
        ),
    }
)

_NULL_WORDS = frozenset({"null", "default"})


def apply_overrides(cfg: PipelineConfig, overrides: Mapping[str, str]) -> PipelineConfig:
    """`cfg` with CLI `--set key=value` overrides applied and the result re-validated.

    Values are parsed by field type: comma-separated lists for tuples, `null` or `default` for
    an optional field's None, and pydantic's lax parsing for the rest (`true`/`false`, numbers,
    literals). `name` cannot be overridden: reports pair the preset name with the overrides.
    Raises ValueError (pydantic's ValidationError included) on an unknown key or a bad value.
    """
    fields = PipelineConfig.model_fields
    data = cfg.model_dump()
    for key, raw in overrides.items():
        if key == "name" or key not in fields:
            known = ", ".join(sorted(k for k in fields if k != "name"))
            raise ValueError(f"unknown pipeline setting {key!r}; known: {known}")
        annotation = fields[key].annotation
        value = raw.strip()
        if NoneType in get_args(annotation) and value.lower() in _NULL_WORDS:
            data[key] = None
        elif get_origin(annotation) is tuple:
            data[key] = tuple(part.strip() for part in value.split(",") if part.strip())
        else:
            data[key] = value
    return PipelineConfig.model_validate(data)
