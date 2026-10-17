from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI
from web_fakes import TENANTS, make_demo

from text2sql.config import get_settings
from text2sql.web import server
from text2sql.web.gate import RunGate
from text2sql.web.sessions import SessionStore, TenantDirectory


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# ---- binding ----


def test_serve_binds_to_loopback_unless_told_otherwise(monkeypatch: pytest.MonkeyPatch) -> None:
    app = make_demo().client.app
    hosts: list[list[str]] = []
    runs: list[dict[str, object]] = []

    def fake_create_app(_services: object, *, allowed_hosts: list[str]) -> object:
        hosts.append(allowed_hosts)
        return app

    def fake_run(served: FastAPI, **kwargs: object) -> None:
        assert served is app
        runs.append(kwargs)

    monkeypatch.setattr(server, "configure_logging", lambda: None)
    monkeypatch.setattr(server, "build_services", lambda _settings, *, preset: preset)
    monkeypatch.setattr(server, "create_app", fake_create_app)
    monkeypatch.setattr(uvicorn, "run", fake_run)
    server.serve()
    assert runs == [{"host": "127.0.0.1", "port": 8000}]
    assert hosts == [["127.0.0.1", "localhost"]]


def test_allowed_host_names_follow_the_bind_address() -> None:
    assert server.allowed_hosts_for("127.0.0.1") == ["127.0.0.1", "localhost"]
    assert server.allowed_hosts_for("192.168.1.20") == ["127.0.0.1", "192.168.1.20", "localhost"]
    assert server.allowed_hosts_for("0.0.0.0") == ["*"]
    assert server.allowed_hosts_for("::") == ["*"]


def test_unknown_preset_fails_at_startup() -> None:
    with pytest.raises(ValueError, match="unknown preset"):
        server.build_services(get_settings(), preset="ultra")


# ---- admission ----


def test_gate_allows_one_run_at_a_time() -> None:
    gate = RunGate(max_runs=10)
    assert gate.try_acquire() is None
    refusal = gate.try_acquire()
    assert refusal is not None
    assert "one run at a time" in refusal.reason
    gate.release()
    assert gate.try_acquire() is None


def test_gate_caps_starts_per_window_and_says_when_to_retry() -> None:
    clock = Clock()
    gate = RunGate(max_runs=2, window_s=60, clock=clock)
    for _ in range(2):
        assert gate.try_acquire() is None
        gate.release()
        clock.now += 10
    refusal = gate.try_acquire()
    assert refusal is not None
    assert refusal.retry_after_s == 40  # the first start leaves the window at t=1060
    clock.now += 40
    assert gate.try_acquire() is None


# ---- sessions and the login directory ----


def test_session_store_evicts_oldest_beyond_capacity() -> None:
    store = SessionStore(capacity=2)
    identity = TenantDirectory(TENANTS).identity(1, None)
    first = store.create(identity)
    second = store.create(identity)
    third = store.create(identity)
    assert store.get(first) is None
    assert store.get(second) == store.get(third) == identity
    assert len({first, second, third}) == 3


def test_directory_reads_tenants_and_active_non_canary_users(tmp_path: Path) -> None:
    db = tmp_path / "crm.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE tenants (tenant_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE users (user_id INTEGER PRIMARY KEY, tenant_id INTEGER, full_name TEXT,
                            role TEXT, is_active INTEGER);
        INSERT INTO tenants VALUES (1, 'Acme'), (2, 'Globex');
        INSERT INTO users VALUES (1, 1, 'CANARY-T1-x', 'sales_rep', 1),
                                 (2, 1, 'Ann', 'sales_rep', 1),
                                 (3, 1, 'Gone', 'sales_rep', 0),
                                 (4, 2, 'Bo', 'admin', 1);
        """
    )
    conn.commit()
    conn.close()
    directory = TenantDirectory.from_database(db, exclude_names=["CANARY-T1-x"])
    tenants = {t.tenant_id: [u.name for u in t.users] for t in directory.tenants()}
    assert tenants == {1: ["Ann"], 2: ["Bo"]}
    with pytest.raises(LookupError):
        directory.identity(1, 4)  # Bo works for tenant 2
    assert directory.identity(2, 4).user_name == "Bo"


def test_directory_never_creates_a_missing_database(tmp_path: Path) -> None:
    missing = tmp_path / "absent.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        TenantDirectory.from_database(missing)
    assert not missing.exists()
