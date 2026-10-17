"""Wiring the demo to the real pipeline, and `serve`, which `text2sql demo` calls."""

from __future__ import annotations

import ipaddress

from text2sql.config import PRESETS, Settings, get_settings
from text2sql.data.saas import DEFAULT_DB_PATH, canary_values
from text2sql.grammar import SqlGrammar
from text2sql.llm import LLMClient, RunBudget
from text2sql.observability import configure_logging, new_run_id, start_run
from text2sql.pipeline import Pipeline, full_grammar
from text2sql.web.app import LOOPBACK_HOSTS, DemoServices, create_app
from text2sql.web.databases import DatabaseRegistry, DemoDatabase, discover_databases
from text2sql.web.sessions import TenantDirectory


def build_services(settings: Settings, *, preset: str) -> DemoServices:
    """Databases, login directory and one lazily built `Pipeline` per preset.

    All presets share one `LLMClient` and one `RunBudget`, so `MAX_SPEND_USD` caps what the
    whole server process may spend, and every call lands in the ledger under `T2SQL_PHASE`.
    Each preset's pipeline loads its own database resources (catalog, grammar, guard workers)
    on first use; `close` releases them when the server stops.
    """
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; choose one of {sorted(PRESETS)}")
    run_id = start_run(f"webdemo-{new_run_id()}")
    llm = LLMClient(settings, budget=RunBudget.from_settings(settings, run_id=run_id))
    pipelines: dict[str, Pipeline] = {}

    def pipeline_for(name: str) -> Pipeline:
        if name not in pipelines:
            pipelines[name] = Pipeline(llm, PRESETS[name], settings=settings)
        return pipelines[name]

    def grammar_for(db: DemoDatabase) -> SqlGrammar:
        return full_grammar(db.db_id, dataset=db.dataset, mode=db.mode)

    def close() -> None:
        for pipeline in pipelines.values():
            pipeline.close()

    tenants = (
        TenantDirectory.from_database(DEFAULT_DB_PATH, exclude_names=canary_values().values())
        if DEFAULT_DB_PATH.is_file()
        else TenantDirectory(())
    )
    return DemoServices(
        databases=DatabaseRegistry(discover_databases(), grammar_for=grammar_for),
        tenants=tenants,
        pipeline_for=pipeline_for,
        presets=tuple(PRESETS),
        default_preset=preset,
        close=close,
    )


def allowed_hosts_for(host: str) -> list[str]:
    """Host headers the server answers to: loopback names, plus the address it was bound to.

    Binding to a wildcard address means "reachable under any name", so the check is dropped;
    that only happens when someone passes `--host 0.0.0.0` on purpose.
    """
    try:
        if ipaddress.ip_address(host).is_unspecified:
            return ["*"]
    except ValueError:
        pass
    return sorted({host, *LOOPBACK_HOSTS})


def serve(host: str = "127.0.0.1", port: int = 8000, preset: str = "baseline") -> None:
    """Run the demo with uvicorn until interrupted. Loopback only unless `host` says otherwise."""
    import uvicorn

    configure_logging()
    services = build_services(get_settings(), preset=preset)
    app = create_app(services, allowed_hosts=allowed_hosts_for(host))
    uvicorn.run(app, host=host, port=port)
