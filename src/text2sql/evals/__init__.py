"""Evaluation harness: records, metrics with confidence intervals, reports and RESULTS.md.

Modules: `records` (the JSON shapes), `stats` (bootstrap, Wilson, exact McNemar), `metrics`
(aggregate metrics and gold-column extraction), `report` (report directories and RESULTS.md),
`taxonomy` (LLM-assisted failure labels) and `bird_metric` (BIRD's official EX and R-VES).
Methodology: docs/adr/009-evaluation-methodology.md.
"""
