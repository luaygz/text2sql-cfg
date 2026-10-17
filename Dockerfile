# syntax=docker/dockerfile:1
#
# Runtime image for the `text2sql` CLI. Data is mounted, never baked in. Build with the commit
# so eval reports can record the code version (the image has no git):
#
#   docker build -t text2sql-cfg \
#       --build-arg GIT_SHA="$(git rev-parse HEAD)$(git diff --quiet HEAD || echo -dirty)" .
#   docker run --rm text2sql-cfg safety
#
# The demo server binds 127.0.0.1 inside the container, so publishing a port alone exposes
# nothing. To reach it from the host, bind all interfaces inside the container and publish the
# port on the host's loopback only:
#
#   docker run --rm -p 127.0.0.1:8000:8000 -v "$PWD/data:/app/data" --env-file .env \
#       text2sql-cfg demo --host 0.0.0.0
#
# CONTRIBUTING.md ("Docker") lists the mounts for eval runs; docs/adr/018-ci-and-docker.md
# explains the choices below.

ARG DEBIAN_IMAGE=debian:trixie-slim

FROM ${DEBIAN_IMAGE} AS builder
COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /bin/uv
# The uv-managed CPython that local runs and CI use, so the bundled SQLite version (which
# decides query semantics and therefore eval results) is the same everywhere.
ENV UV_PYTHON_INSTALL_DIR=/python \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
RUN --mount=type=bind,source=.python-version,target=.python-version \
    uv python install

# Dependencies first: this layer only changes when the lockfile does.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

COPY . /app
# Editable on purpose: REPO_ROOT is derived from the source path, and prompts/, config/ and the
# committed response cache are read relative to it.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM ${DEBIAN_IMAGE}
RUN useradd --create-home --uid 10001 --user-group --shell /usr/sbin/nologin text2sql
COPY --from=builder /python /python
COPY --from=builder /app /app
WORKDIR /app
# Code, prompts, pricing and the interpreter stay root-owned; the app user can write only the
# paths the CLI writes to: data, run logs, the response cache and eval reports.
RUN mkdir -p data runs reports \
    && touch RESULTS.md \
    && chown -R text2sql:text2sql data runs cache reports RESULTS.md
# Read by text2sql.evals.report.current_git_sha when there is no git checkout; an eval whose
# image was built without it stops with GitShaError instead of writing an untraceable report.
ARG GIT_SHA=""
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    T2SQL_GIT_SHA=${GIT_SHA}
# Numeric so runtimes that enforce non-root (e.g. Kubernetes runAsNonRoot) can verify it.
USER 10001:10001
VOLUME ["/app/data", "/app/runs"]
ENTRYPOINT ["text2sql"]
CMD ["--help"]
