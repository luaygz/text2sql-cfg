from __future__ import annotations

import io
import json
import sys

import pytest
import structlog

from text2sql.observability import configure_logging


@pytest.fixture
def restore_structlog():
    yield
    structlog.reset_defaults()


def test_logging_follows_the_current_stderr_after_the_old_one_is_closed(
    restore_structlog, monkeypatch
):
    configure_logging()
    log = structlog.get_logger()
    first = io.StringIO()
    monkeypatch.setattr(sys, "stderr", first)
    log.info("before")
    first.close()  # what a CLI test runner does with the stream it swapped in

    second = io.StringIO()
    monkeypatch.setattr(sys, "stderr", second)
    log.warning("after", stage="x")

    line = json.loads(second.getvalue())
    assert (line["event"], line["level"], line["stage"]) == ("after", "warning", "x")
