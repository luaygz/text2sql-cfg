from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from text2sql.prompts import PROMPTS_DIR, load_prompt


def _write(directory: Path, name: str, body: str) -> None:
    (directory / f"{name}.yaml").write_text(body, encoding="utf-8")


GOOD = """
name: demo
version: "1.1"
description: test prompt
changelog:
  - {version: "1.0", date: 2026-10-16, note: first}
  - {version: "1.1", date: 2026-10-17, note: tightened wording}
sections:
  user: |
    Question: $question
    Example JSON: {"winner": "A"}
"""


def test_render_substitutes_and_keeps_literal_braces(tmp_path: Path) -> None:
    _write(tmp_path, "demo", GOOD)
    prompt = load_prompt("demo", tmp_path)
    assert prompt.tag == "demo@1.1"
    text = prompt.render("user", question="How many?")
    assert text == 'Question: How many?\nExample JSON: {"winner": "A"}'


def test_missing_placeholder_fails_loudly(tmp_path: Path) -> None:
    _write(tmp_path, "demo", GOOD)
    with pytest.raises(KeyError):
        load_prompt("demo", tmp_path).render("user")


def test_unknown_section_is_named(tmp_path: Path) -> None:
    _write(tmp_path, "demo", GOOD)
    with pytest.raises(KeyError, match="no section 'system'"):
        load_prompt("demo", tmp_path).render("system")


def test_version_bump_without_changelog_entry_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "demo", GOOD.replace('version: "1.1"\n', 'version: "1.2"\n', 1))
    with pytest.raises(ValidationError, match="no changelog entry"):
        load_prompt("demo", tmp_path)


def test_file_name_and_declared_name_must_agree(tmp_path: Path) -> None:
    _write(tmp_path, "other", GOOD)
    with pytest.raises(ValueError, match="must be 'other'"):
        load_prompt("other", tmp_path)


@pytest.mark.parametrize("path", sorted(PROMPTS_DIR.glob("*.yaml")), ids=lambda p: p.stem)
def test_every_committed_prompt_loads(path: Path) -> None:
    load_prompt(path.stem)
