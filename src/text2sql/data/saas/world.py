"""In-memory building blocks of the synthetic world: rows, the seeded RNG, and date helpers.

Rows reference their parents as `Record` objects; integer ids are assigned once every row
exists. All randomness goes through `World`, so the call order alone fixes the output.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from faker import Faker

from text2sql.data.saas.dictionary import TABLES
from text2sql.data.saas.profile import AS_OF

type Cell = str | int | float | Record | None

AS_OF_START = datetime.combine(AS_OF, time())
"""Midnight at the start of the snapshot day; organic rows are dated before it."""


@dataclass(eq=False, slots=True)
class Record:
    table: str
    created: datetime
    """Creation time; ids are assigned in this order."""
    values: dict[str, Cell]
    id: int = 0


@dataclass(eq=False, slots=True)
class Account:
    """An account row plus the facts its child rows are generated from."""

    record: Record
    name: str
    """Clean company name, used when reps name deals."""
    created: datetime
    owner: Record
    currency: str
    country: str | None
    seats: int
    terms: int
    lifecycle: str = "prospect"
    active_until: datetime = AS_OF_START
    contacts: list[Record] = field(default_factory=list)
    deals: list[tuple[Record, datetime, datetime | None]] = field(default_factory=list)


class World:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.fake = Faker("en_US")
        self.fake.seed_instance(seed)
        self.tables: dict[str, list[Record]] = {t.name: [] for t in TABLES if t.scope != "global"}

    def add(self, table: str, created: datetime, **values: Cell) -> Record:
        record = Record(table, created, values)
        self.tables[table].append(record)
        return record

    def chance(self, p: float) -> bool:
        return self.rng.random() < p

    def weighted[T](self, options: Sequence[tuple[T, float]]) -> T:
        return self.rng.choices([o for o, _ in options], [w for _, w in options])[0]

    def poisson(self, lam: float) -> int:
        limit, k, product = math.exp(-lam), 0, self.rng.random()
        while product > limit:
            k += 1
            product *= self.rng.random()
        return k

    def geometric(self, p: float) -> int:
        k = 0
        while self.rng.random() > p:
            k += 1
        return k

    def between(self, start: datetime, end: datetime) -> datetime:
        """Uniform time in [start, end), moved into office hours; empty ranges give `start`."""
        span = int((end - start).total_seconds())
        if span <= 1:
            return start
        moment = start + timedelta(seconds=self.rng.randrange(span))
        moment = moment.replace(hour=8 + moment.hour % 10)
        return min(max(moment, start), end - timedelta(seconds=1))

    def vary_case(self, value: str, lower: float, upper: float) -> str:
        r = self.rng.random()
        if r < lower:
            return value.lower()
        if r < lower + upper:
            return value.upper()
        return value

    def name(self) -> tuple[str, str]:
        return str(self.fake.first_name()), str(self.fake.last_name())

    def sentence(self) -> str:
        return str(self.fake.sentence(nb_words=12))

    def hex(self, bits: int) -> str:
        return f"{self.rng.getrandbits(bits):0{bits // 4}x}"


def ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def ts_z(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def on_day(day: date, hour: int = 0) -> datetime:
    return datetime.combine(day, time(hour))


def add_months(day: date, months: int) -> date:
    years, month0 = divmod(day.month - 1 + months, 12)
    return date(day.year + years, month0 + 1, min(day.day, 28))
