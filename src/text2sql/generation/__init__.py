"""Candidate generation: strategies, prompt layout, repair turns (ADR-008 stages 6-7, ADR-012)."""

from text2sql.generation.candidates import (
    GenerationLLM,
    SqlAnswer,
    generate_candidate,
    generate_json_candidate,
    repair_candidate,
)
from text2sql.generation.prompting import (
    GenerationContext,
    RepairKind,
    build_messages,
    prompt_tags,
    repair_feedback,
)
from text2sql.generation.strategies import (
    DEFAULT_SCHEDULE,
    STRATEGIES,
    ModelTier,
    ScheduledCandidate,
    SchemaView,
    StrategySpec,
    model_for,
    schedule,
)

__all__ = [
    "DEFAULT_SCHEDULE",
    "STRATEGIES",
    "GenerationContext",
    "GenerationLLM",
    "ModelTier",
    "RepairKind",
    "ScheduledCandidate",
    "SchemaView",
    "SqlAnswer",
    "StrategySpec",
    "build_messages",
    "generate_candidate",
    "generate_json_candidate",
    "model_for",
    "prompt_tags",
    "repair_candidate",
    "repair_feedback",
    "schedule",
]
