"""Grammar size and an estimate of how much of the OpenAI grammar budget it uses.

The Responses API rejects grammars whose compilation exceeds a fixed work budget ("regex
construction fuel exhausted"). Neither lark nor the local llguidance build reproduces the
limit, so ADR-005 measured it with acceptance probes and fitted a cost model on this package's
grammar template. Cost is counted in regex atoms (a literal character or a character class
inside a regex terminal): each atom costs 1, each `|` alternative 4.1, and each symbol written
in a rule body 24; the budget is about 6,750. The estimate decides when to fall back to a
linked-schema grammar before calling the API; `LLMClient.grammar_accepted` is the ground truth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Fitted on the probes in docs/adr/data/grammar_budget_probes.json (ADR-005).
_REF_COST = 24.0
_ALTERNATIVE_COST = 4.14
_BUDGET = 6748.0
API_LOAD_LIMIT = 0.85
"""Estimated load above which a grammar counts as too large; the margin covers model error,
which was within 15% on grammars shaped differently from ours."""

_RULE = re.compile(r"^[?!]?([a-z_][a-z0-9_]*)\s*:(.*)$")
_TERMINAL = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*:\s*(.*)$")
_BODY_SYMBOL = re.compile(r'"(?:[^"\\]|\\.)*"i?|/(?:[^/\\]|\\.)*/[imslux]*|[A-Za-z_][A-Za-z0-9_]*')


@dataclass(frozen=True)
class GrammarSize:
    chars: int
    rules: int
    symbol_refs: int
    """Symbols (terminals, literals, rule names) written in rule bodies."""
    regex_terminals: int
    regex_atoms: int
    """Literal characters and character classes inside regex terminals."""
    regex_alternatives: int
    """`|` branches inside regex terminals."""
    api_load: float
    """Estimated share of the API grammar budget; about 1.0 is where rejections start."""

    @property
    def fits_api_budget(self) -> bool:
        return self.api_load <= API_LOAD_LIMIT


def measure_grammar(definition: str) -> GrammarSize:
    rules: set[str] = set()
    refs = regex_terminals = atoms = alternatives = 0
    for line in definition.splitlines():
        if rule := _RULE.match(line):
            rules.add(rule.group(1))
            refs += len(_BODY_SYMBOL.findall(rule.group(2)))
        elif line[:1].isspace() and line.strip().startswith("|"):
            refs += len(_BODY_SYMBOL.findall(line))
        elif (terminal := _TERMINAL.match(line)) and terminal.group(2).startswith("/"):
            pattern = terminal.group(2).rstrip()
            regex_terminals += 1
            found_atoms, found_alternatives = regex_stats(pattern[1 : pattern.rindex("/")])
            atoms += found_atoms
            alternatives += found_alternatives
    load = (atoms + _ALTERNATIVE_COST * alternatives + _REF_COST * refs) / _BUDGET
    return GrammarSize(
        chars=len(definition),
        rules=len(rules),
        symbol_refs=refs,
        regex_terminals=regex_terminals,
        regex_atoms=atoms,
        regex_alternatives=alternatives,
        api_load=round(load, 4),
    )


def regex_stats(regex: str) -> tuple[int, int]:
    """(atoms, alternatives): characters, escapes and classes count as atoms; `|` as branches."""
    atoms = alternatives = i = 0
    while i < len(regex):
        ch = regex[i]
        if ch == "\\":
            atoms, i = atoms + 1, i + 2
        elif ch == "[":
            atoms, i = atoms + 1, _class_end(regex, i) + 1
        elif regex.startswith("(?:", i):
            i += 3
        elif ch == "{":
            i = regex.index("}", i) + 1
        else:
            alternatives += ch == "|"
            atoms += ch not in "()|?*+"
            i += 1
    return atoms, alternatives


def _class_end(regex: str, start: int) -> int:
    i = start + 1
    if regex[i : i + 1] == "^":
        i += 1
    if regex[i : i + 1] == "]":
        i += 1
    while regex[i] != "]":
        i += 2 if regex[i] == "\\" else 1
    return i
