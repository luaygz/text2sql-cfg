# Security policy

This project turns untrusted natural language into SQL that runs against a database, so security reports are welcome and taken seriously.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Email the maintainer at luaygharzeddine@gmail.com with:

- what you did (question text, configuration, preset, database),
- what happened (the generated SQL, rows returned, any safety events logged in `runs/safety_events.jsonl`),
- what you expected to happen.

You should get an acknowledgement within a week. Fixes for confirmed issues come with a regression case in the adversarial suite (`tests/safety/`, `evals/safety/`).

## Scope

In scope: anything that gets a query past the four safety layers described in `docs/THREAT_MODEL.md`. That includes writes or DDL reaching the database, reads of another tenant's rows, reads of hidden columns, reads of SQLite internals, escaping the executor's time or row limits, and prompt-injection paths that change which data is returned.

Out of scope: the residual risks the threat model already lists (inference through aggregates, timing side channels), cost exhaustion of your own OpenAI account, and vulnerabilities in upstream dependencies that do not affect this project's use of them (report those upstream).

## Handling secrets

The OpenAI key is read from `.env`, which is gitignored; only `.env.example` is committed. The response cache stores request bodies and model responses, never headers or keys. If you find a secret committed anywhere in the history, report it as above.
