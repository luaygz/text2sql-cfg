"""Repair feedback wording and the generation prompt files."""

from __future__ import annotations

import string

import pytest

from text2sql.generation import repair_feedback
from text2sql.prompts import PROMPTS_DIR, load_prompt

GENERATION_PROMPTS = sorted(
    p.stem
    for p in PROMPTS_DIR.glob("*.yaml")
    if p.stem.startswith("generate_") or p.stem == "repair"
)


def test_error_feedback_states_the_error_and_asks_for_a_fix() -> None:
    text = repair_feedback(kind="error", detail="no such column: T1.totl\n")
    assert text.startswith("Running the query failed. SQLite reported: no such column: T1.totl\n")
    assert text.endswith(load_prompt("repair").render("fix"))


def test_validator_feedback_names_the_rule() -> None:
    text = repair_feedback(kind="validator", detail="unknown_column: T1.x does not resolve")
    problem, request = text.split("\n\n")
    assert "rejected before it ran" in problem
    assert problem.endswith(": unknown_column: T1.x does not resolve")
    assert request == load_prompt("repair").render("fix")


def test_empty_result_feedback_is_gentle() -> None:
    text = repair_feedback(kind="empty", detail="")
    assert "returned 0 rows" in text
    assert "failed" not in text
    assert "can be the right answer" in text
    assert "unchanged" in text


def test_value_hints_are_listed_between_problem_and_request() -> None:
    hints = ["T1.city = 'paris': stored values are 'Paris'", "  ", "T2.status = 'open': exists"]
    text = repair_feedback(kind="empty", detail="question expects rows", value_hints=hints)
    blocks = text.split("\n\n")
    assert blocks[0].endswith("returned 0 rows.")
    assert blocks[1] == "question expects rows"
    assert blocks[2].splitlines()[1:] == [
        "- T1.city = 'paris': stored values are 'Paris'",
        "- T2.status = 'open': exists",
    ]
    assert "unchanged" in blocks[3]


@pytest.mark.parametrize("kind", ["error", "validator", "value"])
def test_a_failure_without_its_detail_is_a_caller_bug(kind: str) -> None:
    with pytest.raises(ValueError, match="observed problem"):
        repair_feedback(kind=kind, detail="  ")  # type: ignore[arg-type]


def test_generation_prompt_files_are_present() -> None:
    assert GENERATION_PROMPTS == [
        "generate_common",
        "generate_direct",
        "generate_divide_conquer",
        "generate_query_plan",
        "repair",
    ]


@pytest.mark.parametrize("name", GENERATION_PROMPTS)
def test_every_section_renders_with_its_placeholders(name: str) -> None:
    prompt = load_prompt(name)
    for section, text in prompt.sections.items():
        template = string.Template(text)
        assert template.is_valid(), f"{name}.{section} has a stray $"
        values = {key: f"<{key}>" for key in template.get_identifiers()}
        rendered = prompt.render(section, **values)
        assert rendered
        assert all(v in rendered for v in values.values())
