"""Which correct BIRD predictions in reports/ need more than BIRD's 30 s of wall time?

Re-scores every distinct (prediction, gold) pair one at a time and times it; ADR-009 ("Time
limits in scoring") reports the output. Run on an idle machine:

    uv run --frozen python scripts/time_scoring.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from text2sql.data.bird import bird_db_path
from text2sql.evals.bird_metric import execution_match

Key = tuple[str, str, str, str]


def main() -> None:
    timed: dict[Key, tuple[bool, float]] = {}
    records: list[tuple[bool, float, bool]] = []
    for results in sorted(Path("reports").glob("*/results.json")):
        run = json.loads(results.read_text())["run"]
        if run["dataset"] not in ("bird_minidev", "bird_arcwise"):
            continue
        release = "minidev" if run["dataset"] == "bird_minidev" else "dev"
        for line in (results.parent / "per_question.jsonl").read_text().splitlines():
            q = json.loads(line)
            if not q.get("final_sql") or not q.get("gold_sql"):
                continue
            key = (release, q["db_id"], q["final_sql"], q["gold_sql"])
            if key not in timed:
                db = bird_db_path(q["db_id"], release=release)
                start = time.monotonic()
                ok = execution_match(q["final_sql"], q["gold_sql"], db)
                timed[key] = (ok, time.monotonic() - start)
            ok, wall = timed[key]
            records.append((ok, wall, q["correct"]))

    slow = sorted((k[1], k[0], round(wall, 1), ok) for k, (ok, wall) in timed.items() if wall > 30)
    slowest_correct = max((wall for ok, wall in timed.values() if ok), default=0.0)
    print("distinct (prediction, gold) pairs timed:", len(timed))
    print("pairs over 30 s of wall time (db, release, seconds, correct):", slow)
    late = sum(ok and wall > 30 for ok, wall, _ in records)
    print("records scored correct after more than 30 s:", late)
    print("records whose stored score differs:", sum(ok != stored for ok, _, stored in records))
    print(f"slowest correct pair: {slowest_correct:.1f} s")


if __name__ == "__main__":
    main()
