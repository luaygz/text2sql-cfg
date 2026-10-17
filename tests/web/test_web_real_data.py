"""The demo's canned attacks against the real grammars (needs BIRD data and built catalogs)."""

from __future__ import annotations

import pytest

from text2sql.data.bird import bird_dir
from text2sql.data.saas import DEFAULT_DB_PATH, canary_values
from text2sql.pipeline import full_grammar
from text2sql.web.databases import discover_databases
from text2sql.web.sessions import TenantDirectory


@pytest.mark.bird
@pytest.mark.skipif(not (bird_dir() / "mini_dev_sqlite.json").is_file(), reason="BIRD data absent")
def test_real_databases_offer_examples_and_an_attack_the_grammar_rejects() -> None:
    databases = discover_databases()
    if not databases:
        pytest.skip("no catalogs built; run `make catalog`")
    for db in databases:
        grammar = full_grammar(db.db_id, dataset=db.dataset, mode=db.mode)
        assert not grammar.accepts(db.attack_sql), db.db_id
        if db.dataset == "bird":
            # The SELECT before the `;` is valid, so the rejection is the injected statement.
            prefix = db.attack_sql.split(";", 1)[0]
            assert grammar.accepts(prefix), db.db_id
            # One dev question per difficulty, easiest first (every Mini-Dev db has all three).
            assert [e.label.rsplit("(", 1)[1] for e in db.examples] == [
                "simple)",
                "moderate)",
                "challenging)",
            ], db.db_id


@pytest.mark.skipif(not DEFAULT_DB_PATH.is_file(), reason="data/saas/crm.sqlite not generated")
def test_login_directory_has_eight_tenants_and_no_canary_users() -> None:
    canaries = set(canary_values().values())
    directory = TenantDirectory.from_database(DEFAULT_DB_PATH, exclude_names=canaries)
    tenants = directory.tenants()
    assert [t.tenant_id for t in tenants] == list(range(1, 9))
    assert all(t.users for t in tenants)
    assert not any(u.name in canaries for t in tenants for u in t.users)
