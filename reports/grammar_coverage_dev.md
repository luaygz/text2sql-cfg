# Grammar coverage: bird dev

Generated 2026-10-16T18:54:35+00:00 by `python -m text2sql.grammar.coverage`. Grammar options: mode=benchmark, max_rows=1000, full schema.

| Gold SQL | Queries | Covered | Coverage | lark/llguidance agree | Result unchanged |
| --- | --- | --- | --- | --- | --- |
| arcwise | 349 | 345 | 98.9% | 349/349 | 348/348 |
| bird | 350 | 346 | 98.9% | 350/350 | 349/349 |

## Per database

| Database | Tables | Columns | Grammar chars | Regex atoms | Rule symbols | Est. API load | arcwise | bird |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| california_schools | 3 | 88 | 2936 | 1049 | 87 | 0.56 | 90.5% | 90.5% |
| card_games | 6 | 96 | 3016 | 1126 | 87 | 0.57 | 100.0% | 100.0% |
| codebase_community | 8 | 51 | 2554 | 787 | 87 | 0.50 | 100.0% | 100.0% |
| debit_card_specializing | 5 | 15 | 2143 | 490 | 87 | 0.43 | 100.0% | 100.0% |
| european_football_2 | 7 | 185 | 3352 | 1275 | 87 | 0.64 | 97.2% | 97.2% |
| financial | 8 | 40 | 2236 | 541 | 87 | 0.45 | 100.0% | 100.0% |
| formula_1 | 13 | 49 | 2431 | 674 | 87 | 0.48 | 100.0% | 100.0% |
| student_club | 8 | 42 | 2374 | 654 | 87 | 0.47 | 100.0% | 100.0% |
| superhero | 10 | 23 | 2255 | 571 | 87 | 0.45 | 100.0% | 97.2% |
| thrombosis_prediction | 3 | 61 | 2329 | 582 | 87 | 0.47 | 97.1% | 100.0% |
| toxicology | 4 | 7 | 2011 | 396 | 87 | 0.41 | 100.0% | 100.0% |

## Failures by category

- window function: 7
- function not in allowlist: GROUP_CONCAT: 1

## Failures

### bird 17 (california_schools): window function

```sql
SELECT CharterNum, AvgScrWrite, RANK() OVER (ORDER BY AvgScrWrite DESC) AS c1 FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T2.AvgScrWrite > 499 AND NOT CharterNum IS NULL
```

Detail: `SELECT CharterNum, AvgScrWrite, RANK() OVER (ORDER BY AvgScrWrite DESC) AS c1 FROM |                                 ^ | `

### bird 41 (california_schools): window function

```sql
SELECT School FROM (SELECT T2.School, T1.AvgScrRead, RANK() OVER (PARTITION BY T2.County ORDER BY T1.AvgScrRead DESC) AS c1 FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T2.`Virtual` = 'F') AS T3 WHERE c1 <= 5
```

Detail: `ECT School FROM (SELECT T2.School, T1.AvgScrRead, RANK() OVER (PARTITION BY T2.County ORDER BY T1.Av |                                                   ^ | `

### bird 726 (superhero): window function

```sql
SELECT superhero_name, height_cm, RANK() OVER (ORDER BY height_cm DESC) AS c1 FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T2.publisher_name = 'Marvel Comics'
```

Detail: `SELECT superhero_name, height_cm, RANK() OVER (ORDER BY height_cm DESC) AS c1 FROM s |                                   ^ | `

### bird 1116 (european_football_2): window function

```sql
SELECT player_name FROM (SELECT player_name, height, DENSE_RANK() OVER (ORDER BY height DESC) AS c1 FROM Player AS T1) WHERE c1 = 1
```

Detail: `ECT player_name FROM (SELECT player_name, height, DENSE_RANK() OVER (ORDER BY height DESC) AS c1 FRO |                                                   ^ | `

### arcwise 17 (california_schools): window function

```sql
SELECT CharterNum, AvgScrWrite, RANK() OVER (ORDER BY AvgScrWrite DESC) AS c1 FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T2.AvgScrWrite > 499 AND NOT CharterNum IS NULL AND rtype = 'S'
```

Detail: `SELECT CharterNum, AvgScrWrite, RANK() OVER (ORDER BY AvgScrWrite DESC) AS c1 FROM |                                 ^ | `

### arcwise 41 (california_schools): window function

```sql
WITH cte1 AS (SELECT T1.School, T1.`Virtual`, T2.cname, RANK() OVER (PARTITION BY T2.cname ORDER BY T2.AvgScrRead DESC) AS c1 FROM schools AS T1 JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE NOT T2.AvgScrRead IS NULL AND rtype = 'S') SELECT DISTINCT School FROM cte1 WHERE `Virtual` = 'F' AND c1 <= 5
```

Detail: `te1 AS (SELECT T1.School, T1.`Virtual`, T2.cname, RANK() OVER (PARTITION BY T2.cname ORDER BY T2.Avg |                                                   ^ | `

### arcwise 1116 (european_football_2): window function

```sql
SELECT player_name FROM (SELECT player_name, height, DENSE_RANK() OVER (ORDER BY height DESC) AS c1 FROM Player AS T1) WHERE c1 = 1
```

Detail: `ECT player_name FROM (SELECT player_name, height, DENSE_RANK() OVER (ORDER BY height DESC) AS c1 FRO |                                                   ^ | `

### arcwise 1225 (thrombosis_prediction): function not in allowlist: GROUP_CONCAT

```sql
SELECT GROUP_CONCAT(DISTINCT T1.ID), T1.SEX FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-BIL` >= 2.0 GROUP BY T1.SEX
```

Detail: `SELECT GROUP_CONCAT(DISTINCT T1.ID), T1.SEX FROM Patient  |        ^ | `
