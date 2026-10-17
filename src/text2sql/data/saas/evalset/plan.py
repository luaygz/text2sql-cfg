"""The drafting plan: which batches of questions to draft, and how many items each bucket keeps.

Every batch is drafted for one tenant, whose data summary grounds the questions. Tenants are
assigned by a seeded shuffle, so the plan, and with it every prompt, is identical on every run.
Each bucket is over-drafted by roughly a quarter because the execution checks and the review
drop items; `QUOTAS` says how many survivors each stratum keeps.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, Literal

from text2sql.data.saas.evalset.models import AttackCategory, Bucket
from text2sql.data.saas.evalset.snapshot import seeded_rng

DraftBucket = Bucket | Literal["fewshot"]
TENANT_IDS: Final = tuple(range(1, 9))
MIXED = "mixed: about a third each of easy, medium and hard"


@dataclass(frozen=True, slots=True)
class PersonaSpec:
    role: str
    owned_table: str
    """The persona is the active user of `role` who owns the most rows of this table."""


@dataclass(frozen=True, slots=True)
class Batch:
    key: str
    bucket: DraftBucket
    section: str
    """Bucket instructions in prompts/saas_question_drafting.yaml."""
    focus: str
    """`focus_*` or `attack_*` section of the same prompt."""
    difficulty: str
    count: int
    tenant_id: int
    persona: PersonaSpec | None = None
    category: AttackCategory | None = None


_ANSWERABLE: Final = (
    ("easy", ("counts", "lookup_join", "dirty", "reference", "dates")),
    ("medium", ("aggregation", "multi_join", "money", "dates", "dirty", "ranking", "reference")),
    ("hard", ("ranking", "dates", "money", "multi_join", "nested", "mixed")),
)
_PERSONAS: Final = (PersonaSpec("sales_rep", "deals"), PersonaSpec("support_agent", "tickets"))
_TENANT_FOCUS: Final = ("counts", "aggregation", "money", "ranking", "dates", "multi_join", "mixed")
_EXTRA_MEDIUM: Final = ("aggregation", "money")
_FEWSHOT_FOCUS: Final = ("counts", "lookup_join", "aggregation", "multi_join", "dates", "money")
_ATTACKS: Final[tuple[tuple[AttackCategory, int], ...]] = (
    ("prompt_injection", 9),
    ("cross_tenant", 9),
    ("write_ddl", 8),
    ("system_catalog", 7),
    ("sql_smuggling", 8),
    ("comment_unicode", 10),
    ("hidden_column", 5),
)

QUOTAS: Final[dict[str, dict[str, int]]] = {
    # Strata: difficulty, or "user" for user-mode answerable items.
    "answerable": {"user": 12, "easy": 42, "medium": 54, "hard": 42},
    "tenant": {"all": 60},
    "unanswerable": {"all": 40},
    # Strata: attack category, with comment and Unicode tricks counted apart so that every
    # Unicode trick (homoglyph, zero-width, fullwidth, bidi override) can be represented.
    "adversarial": {
        "prompt_injection": 6,
        "cross_tenant": 8,
        "write_ddl": 7,
        "system_catalog": 6,
        "sql_smuggling": 6,
        "comment_unicode:comment": 3,
        "comment_unicode:unicode": 5,
        "hidden_column": 3,
        "indirect_injection": 6,
    },
    "fewshot": {"all": 40},
}


def drafting_plan() -> list[Batch]:
    tenants = _tenant_cycle()
    mixed_tenant = "mixed: about 4 easy, 4 medium and 3 hard"
    batches: list[Batch] = []
    answerable = 0
    for difficulty, focuses in _ANSWERABLE:
        for focus in focuses:
            answerable += 1
            batches.append(
                Batch(
                    f"answerable-{answerable:02d}",
                    "answerable",
                    "answerable",
                    f"focus_{focus}",
                    difficulty,
                    10,
                    next(tenants),
                )
            )
    for persona in _PERSONAS:
        answerable += 1
        batches.append(
            Batch(
                f"answerable-{answerable:02d}",
                "answerable",
                "user_mode",
                "focus_user",
                MIXED,
                8,
                next(tenants),
                persona=persona,
            )
        )
    for n, focus in enumerate(_TENANT_FOCUS, start=1):
        batches.append(
            Batch(
                f"tenant-{n:02d}",
                "tenant",
                "tenant",
                f"focus_{focus}",
                mixed_tenant,
                11,
                next(tenants),
            )
        )
    for n in range(1, 5):
        batches.append(
            Batch(
                f"unanswerable-{n:02d}",
                "unanswerable",
                "unanswerable",
                "focus_unanswerable",
                MIXED,
                13,
                next(tenants),
            )
        )
    for n, (category, count) in enumerate(_ATTACKS, start=1):
        batches.append(
            Batch(
                f"adversarial-{n:02d}",
                "adversarial",
                "adversarial",
                f"attack_{category}",
                MIXED,
                count,
                next(tenants),
                category=category,
            )
        )
    # Appended after the first build showed the reviewer moving many medium items to easy or
    # hard; placed here so the tenants of every earlier batch stay the same.
    for n, focus in enumerate(_EXTRA_MEDIUM, start=answerable + 1):
        batches.append(
            Batch(
                f"answerable-{n:02d}",
                "answerable",
                "answerable",
                f"focus_{focus}",
                "medium",
                10,
                next(tenants),
            )
        )
    for n, focus in enumerate(_FEWSHOT_FOCUS, start=1):
        batches.append(
            Batch(
                f"fewshot-{n:02d}", "fewshot", "fewshot", f"focus_{focus}", MIXED, 10, next(tenants)
            )
        )
    return batches


def _tenant_cycle() -> Iterator[int]:
    """Endless tenant ids: each round of eight is a fresh seeded permutation."""
    rng = seeded_rng("plan", "tenants")
    while True:
        order = list(TENANT_IDS)
        rng.shuffle(order)
        yield from order
