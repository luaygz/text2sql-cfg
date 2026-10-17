"""Simulated login: a server-side session holds the caller's tenant and user.

The page's tenant picker stands in for authentication. Choosing a tenant creates a session
whose opaque token travels in an HttpOnly cookie; the identity itself stays on the server, so
neither the question text nor the request body can change whose rows a query sees.
"""

from __future__ import annotations

import secrets
import sqlite3
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path

from text2sql.safety.policy import ScopeContext
from text2sql.web.models import Identity, TenantInfo, UserInfo

SESSION_COOKIE = "t2sql_session"


class TenantDirectory:
    """Tenants and their users that the login picker offers."""

    def __init__(self, tenants: Iterable[TenantInfo]) -> None:
        self._tenants = {t.tenant_id: t for t in tenants}

    @classmethod
    def from_database(cls, db_path: Path, *, exclude_names: Iterable[str] = ()) -> TenantDirectory:
        """Read tenants and active users from the SaaS database, opened read-only.

        `exclude_names` drops planted canary users, which exist to detect leaks and would only
        confuse someone picking a user to sign in as.
        """
        excluded = set(exclude_names)
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            tenants = conn.execute(
                "SELECT tenant_id, name FROM tenants ORDER BY tenant_id"
            ).fetchall()
            users = conn.execute(
                "SELECT tenant_id, user_id, full_name, role FROM users "
                "WHERE is_active = 1 ORDER BY tenant_id, user_id"
            ).fetchall()
        finally:
            conn.close()
        by_tenant: dict[int, list[UserInfo]] = {}
        for tenant_id, user_id, name, role in users:
            if name not in excluded:
                by_tenant.setdefault(tenant_id, []).append(
                    UserInfo(user_id=user_id, name=name, role=role)
                )
        return cls(
            TenantInfo(tenant_id=tid, name=name, users=tuple(by_tenant.get(tid, ())))
            for tid, name in tenants
        )

    def tenants(self) -> tuple[TenantInfo, ...]:
        return tuple(self._tenants.values())

    def identity(self, tenant_id: int, user_id: int | None) -> Identity:
        """The identity for a login choice; raises LookupError if it does not exist."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise LookupError(f"no tenant {tenant_id}")
        if user_id is None:
            return Identity(
                tenant_id=tenant_id, tenant_name=tenant.name, user_id=None, user_name=None
            )
        user = next((u for u in tenant.users if u.user_id == user_id), None)
        if user is None:
            raise LookupError(f"tenant {tenant_id} has no active user {user_id}")
        return Identity(
            tenant_id=tenant_id, tenant_name=tenant.name, user_id=user_id, user_name=user.name
        )


class SessionStore:
    """In-memory sessions, oldest evicted first once `capacity` is reached."""

    def __init__(self, capacity: int = 256) -> None:
        self._capacity = capacity
        self._sessions: OrderedDict[str, Identity] = OrderedDict()

    def create(self, identity: Identity) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = identity
        while len(self._sessions) > self._capacity:
            self._sessions.popitem(last=False)
        return token

    def get(self, token: str | None) -> Identity | None:
        return None if token is None else self._sessions.get(token)

    def delete(self, token: str | None) -> None:
        if token is not None:
            self._sessions.pop(token, None)


def scope_of(identity: Identity) -> ScopeContext:
    return ScopeContext(tenant_id=identity.tenant_id, user_id=identity.user_id)
