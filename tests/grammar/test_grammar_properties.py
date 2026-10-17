"""Property tests for the regex builders and the string-literal terminal."""

from __future__ import annotations

import re

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from text2sql.grammar import GuidanceMatcher, SqlGrammar
from text2sql.grammar.builder import int_range_regex, trie_regex
from text2sql.grammar.conventions import TRAP_PUNCTUATION

identifiers = st.text(
    alphabet=st.characters(codec="ascii", exclude_categories=("Cc",)), min_size=1, max_size=12
)


@given(st.sets(identifiers, min_size=1, max_size=30), identifiers)
def test_trie_regex_matches_exactly_its_words(words: set[str], probe: str) -> None:
    pattern = re.compile(trie_regex(words))
    assert all(pattern.fullmatch(word) for word in words)
    assert bool(pattern.fullmatch(probe)) == (probe in words)


@given(st.sets(identifiers, min_size=1, max_size=30), identifiers)
def test_trie_regex_prefers_the_longest_word(words: set[str], tail: str) -> None:
    # lark's lexer takes the first match Python's re finds; it must be the longest word that
    # prefixes the text, as llguidance's greedy lexer would pick.
    for word in words:
        text = word + tail
        expected = max((w for w in words if text.startswith(w)), key=len)
        match = re.compile(trie_regex(words)).match(text)
        assert match is not None
        assert match.group() == expected


@given(st.integers(min_value=1, max_value=100_000))
def test_int_range_regex_matches_one_to_upper(upper: int) -> None:
    pattern = re.compile(int_range_regex(upper))
    for n in {1, 9, 10, 99, 100, upper // 2, upper - 1, upper}:
        if 1 <= n <= upper:
            assert pattern.fullmatch(str(n)), n
    for bad in (str(upper + 1), "0", "0" + str(upper), str(upper * 10)):
        assert not pattern.fullmatch(bad), bad


@given(st.integers(min_value=1, max_value=12_000))
def test_int_range_regex_picks_the_whole_number(upper: int) -> None:
    pattern = re.compile(int_range_regex(upper))
    match = pattern.match(str(upper))
    assert match is not None
    assert match.group() == str(upper)


literal_text = st.text(
    alphabet=st.characters(exclude_characters="\\;", exclude_categories=("Cc", "Cs")),
    max_size=40,
)


def _quoted(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _opens_with_trap_punctuation(text: str) -> bool:
    return len(text) > 1 and text[0] in TRAP_PUNCTUATION and not text[1].isdigit()


@settings(max_examples=150, deadline=None)
@given(literal_text)
def test_any_quoted_text_is_one_string_literal(benchmark_grammar: SqlGrammar, text: str) -> None:
    assume(not _opens_with_trap_punctuation(text))
    sql = f"SELECT name FROM customers WHERE name = {_quoted(text)}"
    assert benchmark_grammar.accepts(sql)
    assert GuidanceMatcher(benchmark_grammar.definition).accepts(sql)


@settings(max_examples=60, deadline=None)
@given(literal_text, st.sampled_from(["\\", ";", "\n", "\x00"]), literal_text)
def test_backslash_semicolon_and_control_characters_never_enter_a_literal(
    benchmark_grammar: SqlGrammar, before: str, bad: str, after: str
) -> None:
    sql = f"SELECT name FROM customers WHERE name = {_quoted(before + bad + after)}"
    assert not benchmark_grammar.accepts(sql)
    assert not GuidanceMatcher(benchmark_grammar.definition).accepts(sql)


@settings(max_examples=80, deadline=None)
@given(st.sampled_from(TRAP_PUNCTUATION), literal_text)
def test_trap_punctuation_opens_only_a_lone_character_or_a_digit(
    benchmark_grammar: SqlGrammar, first: str, rest: str
) -> None:
    # ADR-005: after a leading '+', '-', '*', ... the closing quote must be the decoder's only
    # non-digit choice, or the hosted model cannot end the literal.
    sql = f"SELECT name FROM customers WHERE name = {_quoted(first + rest)}"
    expected = not _opens_with_trap_punctuation(first + rest)
    assert benchmark_grammar.accepts(sql) == expected
    assert GuidanceMatcher(benchmark_grammar.definition).accepts(sql) == expected
