"""Exceptions raised by the grammar package."""

from __future__ import annotations


class GrammarRejection(Exception):  # noqa: N818 - name fixed by the shared interface contract
    """The text does not parse under the grammar."""

    @property
    def summary(self) -> str:
        """The parser's message without the terminals it expected, for showing to a person.

        Lark ends both of its messages, "No terminal matches ..." (with the line and a caret)
        and the one-line "Unexpected end-of-input.", with "Expected one of:" and a list of
        internal terminal names such as `__ANON_3`, which mean nothing to a reader.
        """
        return str(self).split("Expected one of", 1)[0].rstrip()


class GrammarInvalid(Exception):  # noqa: N818 - name fixed by the shared interface contract
    """The grammar definition itself fails offline validation."""


class NormalizationError(ValueError):
    """Gold SQL cannot be rewritten into the grammar's canonical spelling."""
