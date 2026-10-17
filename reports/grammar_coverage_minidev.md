# Grammar coverage: bird minidev

Generated 2026-10-16T13:24:21+00:00 by `python -m text2sql.grammar.coverage`. Grammar options: mode=benchmark, max_rows=1000, full schema.

| Gold SQL | Queries | Covered | Coverage | lark/llguidance agree | Result unchanged |
| --- | --- | --- | --- | --- | --- |
| arcwise | 498 | 492 | 98.8% | 498/498 | 496/496 |
| bird | 500 | 494 | 98.8% | 500/500 | 498/498 |

## Per database

| Database | Tables | Columns | Grammar chars | Regex atoms | Rule symbols | Est. API load | arcwise | bird |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| california_schools | 3 | 88 | 2928 | 1049 | 86 | 0.55 | 93.3% | 93.3% |
| card_games | 6 | 96 | 3008 | 1126 | 86 | 0.57 | 100.0% | 100.0% |
| codebase_community | 8 | 51 | 2546 | 787 | 86 | 0.49 | 100.0% | 100.0% |
| debit_card_specializing | 5 | 15 | 2135 | 490 | 86 | 0.43 | 100.0% | 100.0% |
| european_football_2 | 7 | 185 | 3344 | 1275 | 86 | 0.64 | 98.0% | 96.1% |
| financial | 8 | 40 | 2228 | 541 | 86 | 0.45 | 100.0% | 100.0% |
| formula_1 | 13 | 49 | 2423 | 674 | 86 | 0.48 | 98.5% | 100.0% |
| student_club | 8 | 42 | 2366 | 654 | 86 | 0.47 | 100.0% | 100.0% |
| superhero | 10 | 23 | 2247 | 571 | 86 | 0.45 | 98.1% | 96.2% |
| thrombosis_prediction | 3 | 61 | 2321 | 582 | 86 | 0.47 | 98.0% | 100.0% |
| toxicology | 4 | 7 | 2003 | 396 | 86 | 0.41 | 100.0% | 100.0% |

## Failures by category

- window function: 9
- function not in allowlist: DATETIME: 1
- NULLS FIRST/LAST: 1
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

### bird 728 (superhero): window function

```sql
SELECT T2.colour AS c1, COUNT(T1.id) AS c2, RANK() OVER (ORDER BY COUNT(T1.id) DESC) AS c3 FROM superhero AS T1 INNER JOIN colour AS T2 ON T1.eye_colour_id = T2.id INNER JOIN publisher AS T3 ON T1.publisher_id = T3.id WHERE T3.publisher_name = 'Marvel Comics' GROUP BY T2.colour
```

Detail: `SELECT T2.colour AS c1, COUNT(T1.id) AS c2, RANK() OVER (ORDER BY COUNT(T1.id) DESC) AS c3 FRO |                                             ^ | `

### bird 1031 (european_football_2): function not in allowlist: DATETIME

```sql
SELECT DISTINCT DATETIME() - T2.birthday AS c1 FROM Player_Attributes AS T1 INNER JOIN Player AS T2 ON T1.player_api_id = T2.player_api_id WHERE STRFTIME('%Y', T1.date) >= '2013' AND STRFTIME('%Y', T1.date) <= '2015' AND T1.sprint_speed >= 97
```

Detail: `SELECT DISTINCT DATETIME() - T2.birthday AS c1 FROM Player_Attribu |                 ^ | `

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

### arcwise 728 (superhero): window function

```sql
SELECT T2.colour AS c1, COUNT(T1.id) AS c2, RANK() OVER (ORDER BY COUNT(T1.id) DESC) AS c3 FROM superhero AS T1 INNER JOIN colour AS T2 ON T1.eye_colour_id = T2.id INNER JOIN publisher AS T3 ON T1.publisher_id = T3.id WHERE T3.publisher_name = 'Marvel Comics' GROUP BY T2.colour
```

Detail: `SELECT T2.colour AS c1, COUNT(T1.id) AS c2, RANK() OVER (ORDER BY COUNT(T1.id) DESC) AS c3 FRO |                                             ^ | `

### arcwise 847 (formula_1): NULLS FIRST/LAST

```sql
SELECT T2.surname FROM qualifying AS T1 INNER JOIN drivers AS T2 ON T2.driverId = T1.driverId WHERE T1.raceId = 19 ORDER BY T1.q2 ASC NULLS LAST LIMIT 1
```

Detail: `1.driverId WHERE T1.raceId = 19 ORDER BY T1.q2 ASC NULLS LAST LIMIT 1 |                                                   ^ | `

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
