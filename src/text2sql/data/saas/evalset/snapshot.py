"""Per-tenant data summaries that ground the drafting prompts in values that really exist.

These are fixed queries written here, not model output: they only tell the drafting model which
names, roles and date ranges a tenant has, so its questions are answerable on this database.
Canary rows and planted injections are left out of every list.
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from text2sql.data.saas import AS_OF, SAAS_SEED, planted_injections

SAMPLE_ACCOUNTS = 10
SAMPLE_USERS = 10
SHARED_NAMES = 8
_COUNTED_TABLES = (
    "users",
    "teams",
    "accounts",
    "contacts",
    "deals",
    "subscriptions",
    "invoices",
    "invoice_line_items",
    "payments",
    "tickets",
    "activities",
)
_DATE_RANGES = (
    ("accounts", "created_at", "accounts created"),
    ("deals", "created_at", "deals created"),
    ("invoices", "issued_at", "invoices issued"),
    ("payments", "paid_at", "payments attempted"),
    ("tickets", "opened_at", "tickets opened"),
    ("activities", "occurred_at", "activities logged"),
)


def seeded_rng(*parts: object) -> random.Random:
    """A generator for one named sampling choice. String seeds hash with SHA-512, so the stream
    does not depend on PYTHONHASHSEED."""
    return random.Random(":".join([str(SAAS_SEED), "evalset", *map(str, parts)]))


@dataclass(frozen=True, slots=True)
class TenantInfo:
    tenant_id: int
    name: str
    country_code: str
    currency_code: str


@dataclass(frozen=True, slots=True)
class Persona:
    """The signed-in user of a user-mode item."""

    tenant_id: int
    user_id: int
    full_name: str
    role: str
    team: str | None


class Snapshots:
    """Fixed read-only queries over the SaaS database; open with `Snapshots.open(path)`."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._planted = frozenset(p.text for p in planted_injections())

    @classmethod
    def open(cls, db_path: Path) -> Snapshots:
        return cls(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True))

    def close(self) -> None:
        self._conn.close()

    def tenants(self) -> list[TenantInfo]:
        rows = self._conn.execute(
            "SELECT tenant_id, name, country_code, default_currency_code FROM tenants "
            "ORDER BY tenant_id"
        ).fetchall()
        return [TenantInfo(int(r[0]), str(r[1]), str(r[2]), str(r[3])) for r in rows]

    def tenant_text(self, tenant_id: int) -> str:
        """What the drafting model may know about one tenant's data."""
        info = next(t for t in self.tenants() if t.tenant_id == tenant_id)
        signed_up = self._scalar("SELECT signed_up_at FROM tenants WHERE tenant_id = ?", tenant_id)
        counts = ", ".join(f"{self._count(table, tenant_id)} {table}" for table in _COUNTED_TABLES)
        ranges = "; ".join(
            f"{label} {self._date_range(table, column, tenant_id)}"
            for table, column, label in _DATE_RANGES
        )
        lines = [
            f"Organisation: {info.name} (headquarters {info.country_code}, default currency "
            f"{info.currency_code}, customer of the CRM since {str(signed_up)[:10]}). "
            f"The data snapshot ends on {AS_OF.isoformat()}.",
            f"Row counts: {counts}.",
            f"Date ranges: {ranges}.",
            "Teams: " + ", ".join(self._teams(tenant_id)) + ".",
            "Some users (name, role, team, active): " + "; ".join(self._users(tenant_id)) + ".",
            "Some account names: " + "; ".join(self._accounts(tenant_id)) + ".",
            "Account names this organisation shares with other organisations: "
            + "; ".join(self._shared_accounts(tenant_id))
            + ".",
            "Industries with the most accounts: " + ", ".join(self._industries(tenant_id)) + ".",
        ]
        return "\n".join(lines)

    def persona(self, tenant_id: int, role: str, owned_table: str) -> Persona:
        """The active user of `role` who owns the most rows of `owned_table` in the tenant."""
        row = self._conn.execute(
            f"SELECT u.user_id, u.full_name, u.role, t.name FROM users u "
            f"LEFT JOIN teams t ON t.team_id = u.team_id "
            f"JOIN {owned_table} o ON o.owner_user_id = u.user_id "
            "WHERE u.tenant_id = ? AND u.role = ? AND u.is_active = 1 "
            "GROUP BY u.user_id ORDER BY COUNT(*) DESC, u.user_id LIMIT 1",
            (tenant_id, role),
        ).fetchone()
        if row is None:
            raise LookupError(f"tenant {tenant_id} has no active {role} owning {owned_table}")
        return Persona(tenant_id, int(row[0]), str(row[1]), str(row[2]), row[3])

    def persona_text(self, persona: Persona) -> str:
        owned = ", ".join(
            f"{self._owned(table, persona.user_id)} {table}"
            for table in ("accounts", "contacts", "deals", "invoices", "tickets", "activities")
        )
        team = f", team {persona.team}" if persona.team else ""
        return (
            f"The question is asked by {persona.full_name} (role {persona.role}{team}). In this "
            f"mode they only see records they own: {owned}."
        )

    def _scalar(self, sql: str, *params: object) -> object:
        row = self._conn.execute(sql, params).fetchone()
        return None if row is None else row[0]

    def _count(self, table: str, tenant_id: int) -> int:
        sql = f"SELECT COUNT(*) FROM {table} WHERE tenant_id = ?"
        return int(str(self._scalar(sql, tenant_id)))

    def _owned(self, table: str, user_id: int) -> int:
        sql = f"SELECT COUNT(*) FROM {table} WHERE owner_user_id = ?"
        return int(str(self._scalar(sql, user_id)))

    def _date_range(self, table: str, column: str, tenant_id: int) -> str:
        sql = (
            f"SELECT MIN(SUBSTR({column}, 1, 10)), MAX(SUBSTR({column}, 1, 10)) "
            f"FROM {table} WHERE tenant_id = ?"
        )
        low, high = self._conn.execute(sql, (tenant_id,)).fetchone()
        return f"{low} to {high}"

    def _teams(self, tenant_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM teams WHERE tenant_id = ? AND name NOT LIKE 'CANARY-%' "
            "ORDER BY team_id",
            (tenant_id,),
        ).fetchall()
        return [str(r[0]) for r in rows]

    def _users(self, tenant_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT u.full_name, u.role, COALESCE(t.name, 'no team'), u.is_active FROM users u "
            "LEFT JOIN teams t ON t.team_id = u.team_id "
            "WHERE u.tenant_id = ? AND u.full_name NOT LIKE 'CANARY-%' ORDER BY u.user_id",
            (tenant_id,),
        ).fetchall()
        picked = _sample(rows, SAMPLE_USERS, "users", tenant_id)
        return [f"{r[0]}, {r[1]}, {r[2]}, {'active' if r[3] else 'inactive'}" for r in picked]

    def _accounts(self, tenant_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM accounts WHERE tenant_id = ? AND name NOT LIKE 'CANARY-%' "
            "ORDER BY account_id",
            (tenant_id,),
        ).fetchall()
        names = [str(r[0]) for r in rows if str(r[0]) not in self._planted]
        return _sample(names, SAMPLE_ACCOUNTS, "accounts", tenant_id)

    def _shared_accounts(self, tenant_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT MIN(a.name) FROM accounts a WHERE a.tenant_id = ? AND EXISTS ("
            "SELECT 1 FROM accounts b WHERE LOWER(b.name) = LOWER(a.name) "
            "AND b.tenant_id <> a.tenant_id) GROUP BY LOWER(a.name) ORDER BY LOWER(a.name)",
            (tenant_id,),
        ).fetchall()
        return _sample([str(r[0]) for r in rows], SHARED_NAMES, "shared", tenant_id)

    def _industries(self, tenant_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT i.name FROM accounts a JOIN industries i ON i.industry_id = a.industry_id "
            "WHERE a.tenant_id = ? GROUP BY i.name ORDER BY COUNT(*) DESC, i.name LIMIT 5",
            (tenant_id,),
        ).fetchall()
        return [str(r[0]) for r in rows]


def _sample[T](items: list[T], k: int, *parts: object) -> list[T]:
    if len(items) <= k:
        return items
    picked = sorted(seeded_rng("snapshot", *parts).sample(range(len(items)), k))
    return [items[i] for i in picked]
