"""What the generated grammar accepts and rejects, checked with both lark and llguidance."""

from __future__ import annotations

import pytest
from grammar_corpus import INVALID, VALID
from lark import Lark, Tree

from text2sql.catalog.schema import Column, DatabaseSchema, Table
from text2sql.config import QueryMode
from text2sql.grammar import (
    GrammarInvalid,
    GrammarOptions,
    GrammarOutput,
    GrammarRejection,
    GuidanceMatcher,
    SqlGrammar,
    build_grammar,
    validate_grammar_offline,
)


@pytest.mark.parametrize("sql", VALID)
def test_valid_queries_parse(benchmark_grammar: SqlGrammar, sql: str) -> None:
    assert benchmark_grammar.parse(sql) == GrammarOutput(kind="sql", text=sql)


@pytest.mark.parametrize("sql", INVALID)
def test_unsafe_or_off_schema_queries_are_rejected(benchmark_grammar: SqlGrammar, sql: str) -> None:
    with pytest.raises(GrammarRejection):
        benchmark_grammar.parse(sql)
    assert not benchmark_grammar.accepts(sql)


@pytest.mark.parametrize(
    ("sql", "summary"),
    [
        ("SELECT COUNT(*) FROM ", "Unexpected end-of-input."),
        (
            "SELECT COUNT(*) FROM orders; DROP TABLE orders",
            "No terminal matches ';' in the current parser context, at line 1 col 28\n\n"
            "SELECT COUNT(*) FROM orders; DROP TABLE orders\n" + " " * 27 + "^",
        ),
    ],
)
def test_rejection_summary_keeps_the_position_and_drops_terminal_names(
    benchmark_grammar: SqlGrammar, sql: str, summary: str
) -> None:
    with pytest.raises(GrammarRejection) as caught:
        benchmark_grammar.parse(sql)
    assert "Expected one of" in str(caught.value)
    assert caught.value.summary == summary


def test_lark_and_llguidance_agree_on_every_corpus_string(
    benchmark_grammar: SqlGrammar, production_grammar: SqlGrammar, tenant_grammar: SqlGrammar
) -> None:
    extra = [f"{sql} LIMIT 5" for sql in VALID if " LIMIT " not in sql]
    newline = [f"{sql}\n" for sql in [*VALID, *extra]] + [f"{sql}\n\n" for sql in VALID[:3]]
    for grammar in (benchmark_grammar, production_grammar, tenant_grammar):
        matcher = GuidanceMatcher(grammar.definition)
        disagreements = [
            sql
            for sql in [*VALID, *INVALID, *extra, *newline]
            if grammar.accepts(sql) != matcher.accepts(sql)
        ]
        assert disagreements == [], grammar.options


class TestTrailingNewline:
    # ADR-005: the model ends its tool input with a newline when the grammar lets it; without
    # that, queries ending in a punctuation literal came out garbled.
    def test_one_trailing_newline_is_accepted_and_dropped(
        self, benchmark_grammar: SqlGrammar
    ) -> None:
        sql = "SELECT name FROM customers WHERE city = '#'"
        assert benchmark_grammar.parse(sql + "\n") == GrammarOutput(kind="sql", text=sql)

    def test_abstention_may_end_with_a_newline(self, tenant_grammar: SqlGrammar) -> None:
        output = tenant_grammar.parse("ABSTAIN: No salary data.\n")
        assert output == GrammarOutput(kind="abstain", text="No salary data.")

    @pytest.mark.parametrize(
        "text",
        [
            "SELECT name FROM customers\n\n",
            "SELECT name FROM customers \n",
            "SELECT name\nFROM customers",
            "\nSELECT name FROM customers",
            "SELECT name FROM customers\r\n",
            "SELECT name FROM customers\n; DROP TABLE customers",
        ],
    )
    def test_no_other_line_breaks(self, benchmark_grammar: SqlGrammar, text: str) -> None:
        assert not benchmark_grammar.accepts(text)

    def test_production_limit_still_required(self, production_grammar: SqlGrammar) -> None:
        assert not production_grammar.accepts("SELECT name FROM customers\n")
        assert production_grammar.accepts("SELECT name FROM customers LIMIT 5\n")


def test_generated_grammars_validate_offline(
    benchmark_grammar: SqlGrammar, production_grammar: SqlGrammar, tenant_grammar: SqlGrammar
) -> None:
    for grammar in (benchmark_grammar, production_grammar, tenant_grammar):
        validate_grammar_offline(grammar.definition)


@pytest.mark.parametrize(
    ("definition", "engine"),
    [
        ('start: e\ne: e "+" e | "1"', "lark"),  # ambiguous: shift/reduce conflict
        ('start: "a" missing_rule', "lark"),
        ("start: X\nX: /a(?=b)/", "llguidance"),  # lookaround: Python re accepts, Rust does not
    ],
)
def test_offline_validation_rejects_broken_grammars(definition: str, engine: str) -> None:
    with pytest.raises(GrammarInvalid, match=engine):
        validate_grammar_offline(definition)


def test_valid_corpus_is_unambiguous_under_earley(benchmark_grammar: SqlGrammar) -> None:
    earley = Lark(benchmark_grammar.definition, parser="earley", ambiguity="explicit")
    for sql in VALID:
        tree = earley.parse(sql)
        assert not any(
            isinstance(node, Tree) and node.data == "_ambig" for node in tree.iter_subtrees()
        ), sql


class TestProductionMode:
    def test_limit_is_required_at_the_top_level(self, production_grammar: SqlGrammar) -> None:
        assert not production_grammar.accepts("SELECT name FROM customers")
        assert production_grammar.accepts("SELECT name FROM customers LIMIT 100")

    def test_limit_is_capped_at_max_rows(self, production_grammar: SqlGrammar) -> None:
        assert not production_grammar.accepts("SELECT name FROM customers LIMIT 101")
        assert not production_grammar.accepts("SELECT name FROM customers LIMIT 0100")

    def test_subqueries_may_omit_limit(self, production_grammar: SqlGrammar) -> None:
        sql = "SELECT name FROM customers WHERE id IN (SELECT customer_id FROM orders) LIMIT 5"
        assert production_grammar.accepts(sql)

    def test_limit_inside_a_subquery_does_not_satisfy_the_top_level(
        self, production_grammar: SqlGrammar
    ) -> None:
        sql = "SELECT T1.c1 FROM (SELECT name AS c1 FROM customers LIMIT 5) AS T1"
        assert not production_grammar.accepts(sql)


class TestTenantMode:
    def test_star_projections_are_not_expressible(self, tenant_grammar: SqlGrammar) -> None:
        assert not tenant_grammar.accepts("SELECT * FROM customers LIMIT 5")
        assert not tenant_grammar.accepts("SELECT T1.* FROM customers AS T1 LIMIT 5")

    def test_count_star_still_works(self, tenant_grammar: SqlGrammar) -> None:
        assert tenant_grammar.accepts("SELECT COUNT(*) FROM customers LIMIT 1")

    def test_hidden_columns_are_not_expressible(self, shop_schema: DatabaseSchema) -> None:
        visible = shop_schema.without_columns({"orders": ["customer_id"]})
        grammar = build_grammar(visible, GrammarOptions(mode=QueryMode.TENANT))
        assert not grammar.accepts("SELECT customer_id FROM orders LIMIT 5")
        assert grammar.accepts("SELECT amount FROM orders LIMIT 5")


class TestAbstain:
    def test_abstention_parses_as_abstain(self, tenant_grammar: SqlGrammar) -> None:
        output = tenant_grammar.parse("ABSTAIN: The database has no salary data.")
        assert output == GrammarOutput(kind="abstain", text="The database has no salary data.")

    def test_abstention_text_is_never_sql(self, tenant_grammar: SqlGrammar) -> None:
        output = tenant_grammar.parse("ABSTAIN: SELECT 1; DROP TABLE customers")
        assert output.kind == "abstain"

    @pytest.mark.parametrize(
        "text", ["ABSTAIN: ", "ABSTAIN: line\nbreak", "ABSTAIN: " + "x" * 301, "ABSTAIN:no space"]
    )
    def test_malformed_abstentions_are_rejected(
        self, tenant_grammar: SqlGrammar, text: str
    ) -> None:
        assert not tenant_grammar.accepts(text)


def test_column_aliases_only_from_the_reserved_set(benchmark_grammar: SqlGrammar) -> None:
    assert benchmark_grammar.accepts("SELECT COUNT(*) AS c9 FROM orders")
    assert not benchmark_grammar.accepts("SELECT COUNT(*) AS c10 FROM orders")
    assert not benchmark_grammar.accepts("SELECT COUNT(*) AS total FROM orders")


def test_linked_subset_drops_unlinked_identifiers(shop_schema: DatabaseSchema) -> None:
    grammar = build_grammar(shop_schema.subset({"customers": ["name"]}))
    assert grammar.accepts("SELECT name FROM customers")
    assert not grammar.accepts("SELECT city FROM customers")
    assert not grammar.accepts("SELECT amount FROM orders")


def test_names_reserved_for_aliases_are_refused() -> None:
    bad_table = DatabaseSchema(db_id="x", tables=(Table(name="t1", columns=(Column(name="a"),)),))
    bad_column = DatabaseSchema(db_id="x", tables=(Table(name="t", columns=(Column(name="T1"),)),))
    for schema in (bad_table, bad_column):
        with pytest.raises(ValueError, match="reserved"):
            build_grammar(schema)


def test_identifier_that_looks_like_a_function_is_quoted() -> None:
    schema = DatabaseSchema(db_id="x", tables=(Table(name="t", columns=(Column(name="DATE"),)),))
    grammar = build_grammar(schema)
    assert grammar.accepts("SELECT `DATE`, DATE('now') FROM t")
    assert not grammar.accepts("SELECT DATE FROM t")


def test_fingerprint_tracks_the_definition(shop_schema: DatabaseSchema) -> None:
    first = build_grammar(shop_schema)
    assert first.fingerprint == build_grammar(shop_schema).fingerprint
    other = build_grammar(shop_schema, GrammarOptions(max_rows=10))
    assert other.fingerprint != first.fingerprint
    assert len(first.fingerprint) == 64


def test_max_rows_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_rows"):
        GrammarOptions(max_rows=0)


def test_description_states_the_mode_rules(tenant_grammar: SqlGrammar) -> None:
    assert "LIMIT n (n <= 100)" in tenant_grammar.description
    assert "No SELECT *" in tenant_grammar.description
    assert "ABSTAIN: " in tenant_grammar.description
