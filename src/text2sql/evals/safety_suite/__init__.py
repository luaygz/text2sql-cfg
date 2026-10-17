"""The SQL-level adversarial suite for the safety layers, and its report; see docs/adr/015.

`run_safety_suite()` is what `text2sql safety` and `make safety` run. It needs no API key.
"""

from text2sql.evals.safety_suite.cases import CASES_PATH, SafetyCase, load_cases
from text2sql.evals.safety_suite.render import REPORT_DIR, write_safety_report
from text2sql.evals.safety_suite.results import CaseResult, SafetySuiteReport
from text2sql.evals.safety_suite.runner import run_safety_suite

__all__ = [
    "CASES_PATH",
    "REPORT_DIR",
    "CaseResult",
    "SafetyCase",
    "SafetySuiteReport",
    "load_cases",
    "run_safety_suite",
    "write_safety_report",
]
