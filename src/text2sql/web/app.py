"""The demo's FastAPI app: one HTML page and a small JSON API around `Pipeline.run`."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib.resources import files
from typing import Annotated

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from text2sql.config import QueryMode
from text2sql.grammar import GrammarRejection
from text2sql.pipeline import Request as PipelineRequest
from text2sql.safety.policy import ScopeContext
from text2sql.web.databases import DatabaseRegistry, DemoDatabase
from text2sql.web.gate import RunGate
from text2sql.web.models import (
    AskBody,
    DatabasesResponse,
    GrammarCheckBody,
    GrammarCheckResult,
    GrammarInfo,
    Identity,
    LoginBody,
    SessionResponse,
    TenantInfo,
)
from text2sql.web.sessions import SESSION_COOKIE, SessionStore, TenantDirectory, scope_of
from text2sql.web.stream import NDJSON, PipelineRunner, start_run

LOOPBACK_HOSTS = ("127.0.0.1", "localhost")

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_INLINE = re.compile(r"<(script|style)>(.*?)</\1>", re.DOTALL)

SessionToken = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


@dataclass(frozen=True)
class DemoServices:
    databases: DatabaseRegistry
    tenants: TenantDirectory
    pipeline_for: Callable[[str], PipelineRunner]
    """Preset name -> the pipeline that runs it (built lazily, reused across requests)."""
    presets: tuple[str, ...]
    default_preset: str
    close: Callable[[], None] = lambda: None
    """Releases what the pipelines loaded (guard worker processes); called at shutdown."""

    def database(self, db_id: str) -> DemoDatabase:
        db = self.databases.get(db_id)
        if db is None:
            raise HTTPException(404, f"unknown database {db_id!r}")
        return db


def load_page() -> str:
    return (files("text2sql.web") / "index.html").read_text(encoding="utf-8")


def content_security_policy(page: str) -> str:
    """Allow exactly the page's inline script and style blocks, by hash, and nothing remote."""
    sources: dict[str, list[str]] = {"script": [], "style": []}
    for tag, body in _INLINE.findall(page):
        digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
        sources[tag].append(f"'sha256-{digest}'")
    return "; ".join(
        [
            "default-src 'none'",
            f"script-src {' '.join(sources['script']) or "'none'"}",
            f"style-src {' '.join(sources['style']) or "'none'"}",
            "connect-src 'self'",
            "img-src 'self' data:",
            "base-uri 'none'",
            "form-action 'none'",
            "frame-ancestors 'none'",
        ]
    )


def resolve_scope(
    db: DemoDatabase, body: AskBody, identity: Identity | None
) -> ScopeContext | None:
    """The identity rule (ADR-019): the scope comes from the session, never from the request.

    For a tenant-mode database the caller must be signed in. `tenant_id` / `user_id` in the body
    are only an assertion of who the client thinks it is: a mismatch with the session is refused
    instead of silently answered for someone else. Benchmark databases have no tenants, so
    identity fields there are an error too.
    """
    if db.mode is not QueryMode.TENANT:
        if body.tenant_id is not None or body.user_id is not None:
            raise HTTPException(400, f"{db.db_id} is not a tenant database; drop tenant_id/user_id")
        return None
    if identity is None:
        raise HTTPException(401, "sign in as a tenant first (POST /api/session)")
    if body.tenant_id is not None and body.tenant_id != identity.tenant_id:
        raise HTTPException(
            403,
            f"the session is signed in as tenant {identity.tenant_id}; "
            f"tenant_id={body.tenant_id} in the request is not used to choose whose data you see",
        )
    if body.user_id is not None and body.user_id != identity.user_id:
        raise HTTPException(
            403, f"the session is signed in as user {identity.user_id}, not {body.user_id}"
        )
    return scope_of(identity)


def create_app(
    services: DemoServices,
    *,
    allowed_hosts: Sequence[str] = LOOPBACK_HOSTS,
    gate: RunGate | None = None,
    sessions: SessionStore | None = None,
) -> FastAPI:
    page = load_page()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        services.close()

    app = FastAPI(
        title="text2sql demo", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    _install_security(app, csp=content_security_policy(page), allowed_hosts=allowed_hosts)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(page)

    _info_routes(app, services)
    sessions = sessions or SessionStore()
    _session_routes(app, services, sessions)
    _ask_route(app, services, sessions, gate or RunGate())
    return app


def _install_security(app: FastAPI, *, csp: str, allowed_hosts: Sequence[str]) -> None:
    # Host allow-list against DNS rebinding: a page on another domain that resolves to
    # 127.0.0.1 would otherwise count as same-origin and could spend API money.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))

    @app.middleware("http")
    async def same_origin_and_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Browsers send Origin on cross-site POSTs, including "simple" text/plain ones that
        # skip the CORS preflight; refusing a foreign Origin stops other sites driving the API.
        origin = request.headers.get("origin")
        own_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if request.method not in _SAFE_METHODS and origin is not None and origin != own_origin:
            response: Response = JSONResponse(
                {"detail": "cross-origin requests are refused"}, status_code=403
            )
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response


def _info_routes(app: FastAPI, services: DemoServices) -> None:
    @app.get("/api/databases")
    async def databases() -> DatabasesResponse:
        return DatabasesResponse(
            databases=tuple(db.info() for db in services.databases.all()),
            presets=services.presets,
            default_preset=services.default_preset,
        )

    @app.get("/api/grammar/{db_id}")
    async def grammar(db_id: str) -> GrammarInfo:
        db = services.database(db_id)
        built = services.databases.grammar(db)
        return GrammarInfo(
            db_id=db.db_id,
            mode=db.mode,
            fingerprint=built.fingerprint,
            definition=built.definition,
            chars=built.size.chars,
            rules=built.size.rules,
            api_load=built.size.api_load,
            fits_api_budget=built.size.fits_api_budget,
        )

    @app.post("/api/grammar/{db_id}/check")
    async def check(db_id: str, body: GrammarCheckBody) -> GrammarCheckResult:
        built = services.databases.grammar(services.database(db_id))
        try:
            output = built.parse(body.text)
        except GrammarRejection as exc:
            return GrammarCheckResult(accepted=False, error=exc.summary)
        return GrammarCheckResult(accepted=True, kind=output.kind)


def _session_routes(app: FastAPI, services: DemoServices, sessions: SessionStore) -> None:
    @app.get("/api/tenants")
    async def tenants() -> tuple[TenantInfo, ...]:
        return services.tenants.tenants()

    @app.get("/api/session")
    async def current(token: SessionToken = None) -> SessionResponse:
        return SessionResponse(identity=sessions.get(token))

    @app.post("/api/session")
    async def login(
        body: LoginBody, response: Response, token: SessionToken = None
    ) -> SessionResponse:
        try:
            identity = services.tenants.identity(body.tenant_id, body.user_id)
        except LookupError as exc:
            raise HTTPException(422, str(exc)) from exc
        sessions.delete(token)
        response.set_cookie(
            SESSION_COOKIE, sessions.create(identity), httponly=True, samesite="strict"
        )
        return SessionResponse(identity=identity)

    @app.delete("/api/session")
    async def logout(response: Response, token: SessionToken = None) -> SessionResponse:
        sessions.delete(token)
        response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="strict")
        return SessionResponse(identity=None)


def _ask_route(app: FastAPI, services: DemoServices, sessions: SessionStore, gate: RunGate) -> None:
    running: set[asyncio.Task[None]] = set()

    @app.post("/api/ask", response_model=None)
    async def ask(body: AskBody, token: SessionToken = None) -> StreamingResponse | JSONResponse:
        db = services.database(body.db_id)
        identity = sessions.get(token)
        scope = resolve_scope(db, body, identity)
        preset = body.preset or services.default_preset
        if preset not in services.presets:
            raise HTTPException(422, f"unknown preset {preset!r}; choose one of {services.presets}")
        refusal = gate.try_acquire()
        if refusal is not None:
            return JSONResponse(
                {"detail": refusal.reason},
                status_code=429,
                headers={"Retry-After": str(refusal.retry_after_s)},
            )
        try:
            runner = services.pipeline_for(preset)
        except BaseException:
            gate.release()
            raise
        request = PipelineRequest(
            question=body.question,
            evidence=body.evidence,
            db_id=db.db_id,
            mode=db.mode,
            scope=scope,
        )
        header = {
            "type": "run",
            "db_id": db.db_id,
            "mode": db.mode.value,
            "preset": preset,
            "identity": None if scope is None or identity is None else identity.model_dump(),
        }
        lines = start_run(runner, request, header=header, on_finish=gate.release, tasks=running)
        return StreamingResponse(lines, media_type=NDJSON)
