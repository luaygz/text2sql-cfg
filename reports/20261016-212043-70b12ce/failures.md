# Failures: best on saas / test

17 of 90 questions failed. Evidence n/a, git `70b12ce88825feb7263dfaf0a75ccf74d10bb829`, complete: 90 questions.

## saas-answerable-039 / saas_crm / medium

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction includes `T3.user_id` in the SELECT list, while the gold query returns only `full_name` and the contact count. The joins and grouping produce the same owners and counts.

Question:

```text
How many contacts at Brightpath Learning is each contact owner responsible for? Include only owners with at least one contact there.
```

Gold SQL:

```sql
SELECT T3.full_name, COUNT(T1.contact_id) AS c1 FROM contacts AS T1 JOIN accounts AS T2 ON T1.account_id = T2.account_id AND T2.tenant_id = :tenant_id JOIN users AS T3 ON T1.owner_user_id = T3.user_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.name) = 'brightpath learning' GROUP BY T3.user_id, T3.full_name LIMIT 100
```

Predicted SQL:

```sql
SELECT T3.user_id, T3.full_name, COUNT(T1.contact_id) AS c1 FROM contacts AS T1 INNER JOIN accounts AS T2 ON T1.account_id = T2.account_id INNER JOIN users AS T3 ON T1.owner_user_id = T3.user_id WHERE LOWER(T2.name) = 'brightpath learning' GROUP BY T3.user_id, T3.full_name ORDER BY c1 DESC LIMIT 200
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| full_name | c1 |
|---|---|
| Michael Pierce | 2 |
| Lindsey Pena | 2 |

Predicted (first 2 of 2 rows):

| user_id | full_name | c1 |
|---|---|---|
| 73 | Michael Pierce | 2 |
| 107 | Lindsey Pena | 2 |

## saas-answerable-041 / saas_crm / medium

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query uses `COALESCE(SUM(...), 0)`, while the prediction returns the bare `SUM(...)`; when no rows qualify, that produces `NULL` instead of the gold result `0.0`.

Question:

```text
What is the total value of negative invoice lines on Rose and Sons' non-void CAD invoices issued in 2025, keeping the negative sign and rounding to two decimals?
```

Gold SQL:

```sql
SELECT ROUND(COALESCE(SUM(T1.line_total), 0), 2) AS c1 FROM invoice_line_items AS T1 JOIN invoices AS T2 ON T1.invoice_id = T2.invoice_id AND T2.tenant_id = :tenant_id JOIN accounts AS T3 ON T2.account_id = T3.account_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T3.name) = 'rose and sons' AND LOWER(T2.status) <> 'void' AND LOWER(T2.currency_code) = 'cad' AND T2.issued_at >= '2025-01-01' AND T2.issued_at < '2026-01-01' AND T1.line_total < 0 LIMIT 100
```

Predicted SQL:

```sql
SELECT ROUND(SUM(T1.line_total), 2) AS c1 FROM invoice_line_items AS T1 INNER JOIN invoices AS T2 ON T1.invoice_id = T2.invoice_id INNER JOIN accounts AS T3 ON T2.account_id = T3.account_id WHERE LOWER(T3.name) = 'rose and sons' AND T2.status <> 'void' AND T2.currency_code = 'CAD' AND T2.issued_at >= '2025-01-01' AND T2.issued_at < '2026-01-01' AND T1.line_total < 0 LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| c1 |
|---|
| 0.0 |

Predicted (first 1 of 1 rows):

| c1 |
|---|
| None |

## saas-answerable-042 / saas_crm / medium

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction includes `T1.team_id` in the SELECT list, while the gold query returns only the team name and the two aggregates. This adds an output column even though the previewed aggregate values match.

Question:

```text
For each team that logged calls in Q3 2026, how many calls did its members log and how many total minutes were recorded?
```

Gold SQL:

```sql
SELECT T1.name, COUNT(T3.activity_id) AS c1, SUM(T3.duration_minutes) AS c2 FROM teams AS T1 JOIN users AS T2 ON T2.team_id = T1.team_id AND T2.tenant_id = :tenant_id JOIN activities AS T3 ON T3.owner_user_id = T2.user_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T3.activity_type) = 'call' AND T3.occurred_at >= '2026-07-01' AND T3.occurred_at < '2026-10-01' GROUP BY T1.team_id, T1.name LIMIT 100
```

Predicted SQL:

```sql
SELECT T1.team_id, T1.name, COUNT(T3.activity_id) AS c1, COALESCE(SUM(T3.duration_minutes), 0) AS c2 FROM teams AS T1 INNER JOIN users AS T2 ON T1.team_id = T2.team_id INNER JOIN activities AS T3 ON T2.user_id = T3.owner_user_id WHERE T3.activity_type = 'call' AND T3.occurred_at >= '2026-07-01' AND T3.occurred_at < '2026-10-01' GROUP BY T1.team_id, T1.name LIMIT 200
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| name | c1 | c2 |
|---|---|---|
| Sales East | 27 | 631 |
| Customer Success | 2 | 54 |

Predicted (first 2 of 2 rows):

| team_id | name | c1 | c2 |
|---|---|---|---|
| 21 | Sales East | 27 | 631 |
| 23 | Customer Success | 2 | 54 |

## saas-answerable-054 / saas_crm / medium

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction omits the gold join condition `T2.tenant_id = :tenant_id`, so it can include subscriptions from other tenants. The extra `plan_id` output column is also a difference, but the join path is the first issue to fix.

Question:

```text
For each plan with subscriptions canceled in 2025, what was the average number of days from subscription start to cancellation, rounded to two decimals?
```

Gold SQL:

```sql
SELECT T1.name, ROUND(AVG(JULIANDAY(T2.canceled_at) - JULIANDAY(T2.started_at)), 2) AS c1 FROM plans AS T1 JOIN subscriptions AS T2 ON T2.plan_id = T1.plan_id AND T2.tenant_id = :tenant_id WHERE LOWER(T2.status) = 'canceled' AND T2.canceled_at >= '2025-01-01' AND T2.canceled_at < '2026-01-01' GROUP BY T1.plan_id, T1.name LIMIT 100
```

Predicted SQL:

```sql
SELECT T1.plan_id, T1.name, ROUND(AVG(JULIANDAY(T2.canceled_at) - JULIANDAY(T2.started_at)), 2) AS c1 FROM plans AS T1 INNER JOIN subscriptions AS T2 ON T1.plan_id = T2.plan_id WHERE T2.status = 'canceled' AND T2.canceled_at >= '2025-01-01' AND T2.canceled_at < '2026-01-01' GROUP BY T1.plan_id, T1.name LIMIT 200
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 4 of 4 rows):

| name | c1 |
|---|---|
| Starter (monthly) | 341.0 |
| Starter (annual) | 378.0 |
| Growth (monthly) | 305.5 |
| Growth (annual) | 371.67 |

Predicted (first 4 of 4 rows):

| plan_id | name | c1 |
|---|---|---|
| 1 | Starter (monthly) | 341.0 |
| 2 | Starter (annual) | 378.0 |
| 3 | Growth (monthly) | 305.5 |
| 4 | Growth (annual) | 371.67 |

## saas-answerable-060 / saas_crm / medium

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction omits the tenant constraints on the users-to-teams join and the accounts join, so it can match records across tenants. It also selects the extra `user_id` column, but the missing tenant-scoped join conditions are the first logic difference to address.

Question:

```text
For each account owner on Sales East, how many prospect accounts have no country recorded? Ignore capitalization in prospect stage labels and include owners with zero matching accounts.
```

Gold SQL:

```sql
SELECT T1.full_name, COUNT(T3.account_id) AS c1 FROM users AS T1 JOIN teams AS T2 ON T1.team_id = T2.team_id AND T2.tenant_id = :tenant_id LEFT JOIN accounts AS T3 ON T3.owner_user_id = T1.user_id AND T3.tenant_id = :tenant_id AND LOWER(T3.lifecycle_stage) = 'prospect' AND T3.country_code IS NULL WHERE T1.tenant_id = :tenant_id AND LOWER(T2.name) = 'sales east' GROUP BY T1.user_id, T1.full_name LIMIT 100 OFFSET 0
```

Predicted SQL:

```sql
SELECT T1.user_id, T1.full_name, COUNT(T3.account_id) AS c1 FROM users AS T1 INNER JOIN teams AS T2 ON T1.team_id = T2.team_id LEFT JOIN accounts AS T3 ON T3.owner_user_id = T1.user_id AND LOWER(T3.lifecycle_stage) = 'prospect' AND T3.country_code IS NULL WHERE T2.name = 'Sales East' GROUP BY T1.user_id, T1.full_name LIMIT 200
```

Result diff:

Gold 5 rows, predicted 5 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 5 rows):

| full_name | c1 |
|---|---|
| Tammy Cowan | 0 |
| Anita Rivera | 0 |
| Mark Glass | 0 |
| Aaron Soto | 0 |
| David Snow | 0 |

Predicted (first 5 of 5 rows):

| user_id | full_name | c1 |
|---|---|---|
| 49 | Tammy Cowan | 0 |
| 51 | Anita Rivera | 0 |
| 56 | Mark Glass | 0 |
| 77 | Aaron Soto | 0 |
| 131 | David Snow | 0 |

## saas-answerable-094 / saas_crm / hard

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s `tenant_id = :tenant_id` condition and uses case-sensitive status and currency comparisons instead of `LOWER(...)`. It also changes the final band label’s casing, but the missing and altered filters are the first differences to fix.

Question:

```text
For our open AUD invoices overdue as of 2026-09-30, how much was invoiced in each aging band: 1–30, 31–60, 61–90 and more than 90 days overdue? Use the full invoice totals, include tax and round amounts to two decimals.
```

Gold SQL:

```sql
WITH cte1 AS (SELECT JULIANDAY('2026-09-30') - JULIANDAY(CASE WHEN INSTR(T1.due_date, '/') > 0 THEN SUBSTR(T1.due_date, 7, 4) || '-' || SUBSTR(T1.due_date, 1, 2) || '-' || SUBSTR(T1.due_date, 4, 2) ELSE T1.due_date END) AS c1, T1.total_amount AS c2 FROM invoices AS T1 WHERE T1.tenant_id = :tenant_id AND LOWER(T1.status) = 'open' AND LOWER(T1.currency_code) = 'aud'), cte2 AS (SELECT 1 AS c1, 30 AS c2, '1–30' AS c3 UNION ALL SELECT 31, 60, '31–60' UNION ALL SELECT 61, 90, '61–90' UNION ALL SELECT 91, NULL, 'more than 90') SELECT T2.c3, ROUND(COALESCE(SUM(T1.c2), 0), 2) AS c1 FROM cte2 AS T2 LEFT JOIN cte1 AS T1 ON T1.c1 >= T2.c1 AND (T1.c1 <= T2.c2 OR T2.c2 IS NULL) GROUP BY T2.c1, T2.c3 ORDER BY T2.c1 LIMIT 100
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.total_amount, JULIANDAY('2026-09-30') - JULIANDAY(CASE WHEN INSTR(T1.due_date, '/') > 0 THEN SUBSTR(T1.due_date, 7, 4) || '-' || SUBSTR(T1.due_date, 1, 2) || '-' || SUBSTR(T1.due_date, 4, 2) ELSE T1.due_date END) AS c1 FROM invoices AS T1 WHERE T1.status = 'open' AND T1.currency_code = 'AUD'), cte2 AS (SELECT '1–30' AS c1, 1 AS c2, 30 AS c3 UNION ALL SELECT '31–60' AS c1, 31 AS c2, 60 AS c3 UNION ALL SELECT '61–90' AS c1, 61 AS c2, 90 AS c3 UNION ALL SELECT 'More than 90' AS c1, 91 AS c2, NULL AS c3) SELECT T1.c1, ROUND(COALESCE(SUM(T2.total_amount), 0), 2) AS c1 FROM cte2 AS T1 LEFT JOIN cte1 AS T2 ON T2.c1 >= T1.c2 AND (T2.c1 <= T1.c3 OR T1.c3 IS NULL) GROUP BY T1.c1, T1.c2 ORDER BY T1.c2 LIMIT 200
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 4 of 4 rows):

| c3 | c1 |
|---|---|
| 1–30 | 2566.65 |
| 31–60 | 136.38 |
| 61–90 | 0.0 |
| more than 90 | 0.0 |

Predicted (first 4 of 4 rows):

| c1 | c1 |
|---|---|
| 1–30 | 2566.65 |
| 31–60 | 136.38 |
| 61–90 | 0.0 |
| More than 90 | 0.0 |

## saas-answerable-097 / saas_crm / hard

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction joins accounts only on account_id, while the gold query also requires T2.tenant_id = :tenant_id in the join. This can associate invoices with accounts from another tenant; the prediction also omits the invoice tenant filter and returns an extra country-code column.

Question:

```text
For invoices issued in Q2 2026, what were the total amount billed and total tax in USD for each customer country, including a separate group for unknown countries? Use our fixed reporting rates, round both amounts to two decimals, and show the top 10 countries by amount billed, breaking ties by country code.
```

Gold SQL:

```sql
SELECT COALESCE(T3.name, 'Unknown') AS c1, ROUND(SUM(T1.total_amount * T4.usd_rate), 2) AS c2, ROUND(SUM(T1.tax * T4.usd_rate), 2) AS c3 FROM invoices AS T1 JOIN accounts AS T2 ON T1.account_id = T2.account_id AND T2.tenant_id = :tenant_id LEFT JOIN countries AS T3 ON T2.country_code = T3.country_code JOIN currencies AS T4 ON T1.currency_code = T4.currency_code WHERE T1.tenant_id = :tenant_id AND T1.issued_at >= '2026-04-01' AND T1.issued_at < '2026-07-01' GROUP BY T3.country_code, T3.name ORDER BY SUM(T1.total_amount * T4.usd_rate) DESC, T3.country_code ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT COALESCE(T3.country_code, 'Unknown') AS c1, COALESCE(T3.name, 'Unknown') AS c2, ROUND(SUM(T1.total_amount * T4.usd_rate), 2) AS c3, ROUND(SUM(T1.tax * T4.usd_rate), 2) AS c4 FROM invoices AS T1 INNER JOIN accounts AS T2 ON T1.account_id = T2.account_id LEFT JOIN countries AS T3 ON T2.country_code = T3.country_code INNER JOIN currencies AS T4 ON T1.currency_code = T4.currency_code WHERE T1.issued_at >= '2026-04-01' AND T1.issued_at < '2026-07-01' GROUP BY T3.country_code, T3.name ORDER BY SUM(T1.total_amount * T4.usd_rate) DESC, c1 ASC LIMIT 10
```

Result diff:

Gold 6 rows, predicted 6 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 6 rows):

| c1 | c2 | c3 |
|---|---|---|
| Canada | 144976.12 | 0.0 |
| United States | 132484.5 | 0.0 |
| Belgium | 24645.0 | 0.0 |
| Spain | 13572.0 | 0.0 |
| Netherlands | 4550.0 | 0.0 |

Predicted (first 5 of 6 rows):

| c1 | c2 | c3 | c4 |
|---|---|---|---|
| CA | Canada | 144976.12 | 0.0 |
| US | United States | 132484.5 | 0.0 |
| BE | Belgium | 24645.0 | 0.0 |
| ES | Spain | 13572.0 | 0.0 |
| NL | Netherlands | 4550.0 | 0.0 |

## saas-answerable-101 / saas_crm / hard

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction omits the tenant_id constraints on the account, invoice, and line-item joins, so it can include rows from other tenants. It also selects account_id, but the first issue to fix is the changed join path and row scope.

Question:

```text
Which 10 accounts received the largest discount credits on invoices issued in 2025? Treat negative line totals on non-void invoices as discount credits, report their combined magnitude as a positive USD amount using our fixed reporting rates, round to two decimals, and break ties by account ID.
```

Gold SQL:

```sql
SELECT T1.name, ROUND(SUM(-T3.line_total * T4.usd_rate), 2) AS c1 FROM accounts AS T1 JOIN invoices AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id JOIN invoice_line_items AS T3 ON T3.invoice_id = T2.invoice_id AND T3.tenant_id = :tenant_id JOIN currencies AS T4 ON T4.currency_code = T2.currency_code WHERE T1.tenant_id = :tenant_id AND T2.issued_at >= '2025-01-01' AND T2.issued_at < '2026-01-01' AND LOWER(T2.status) <> 'void' AND T3.line_total < 0 GROUP BY T1.account_id, T1.name ORDER BY SUM(-T3.line_total * T4.usd_rate) DESC, T1.account_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.account_id, T1.name, ROUND(SUM(-T3.line_total * T4.usd_rate), 2) AS c1 FROM accounts AS T1 INNER JOIN invoices AS T2 ON T1.account_id = T2.account_id INNER JOIN invoice_line_items AS T3 ON T2.invoice_id = T3.invoice_id INNER JOIN currencies AS T4 ON T2.currency_code = T4.currency_code WHERE T2.status <> 'void' AND T2.issued_at >= '2025-01-01' AND T2.issued_at < '2026-01-01' AND T3.line_total < 0 GROUP BY T1.account_id, T1.name ORDER BY c1 DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| name | c1 |
|---|---|
| Livingston Retail | 9555.0 |
| Carroll Partners | 7897.5 |
| Welch Consulting | 4914.0 |
| Clearwater Telecom | 4680.0 |
| Austin Health | 1540.0 |

Predicted (first 5 of 10 rows):

| account_id | name | c1 |
|---|---|---|
| 517 | Livingston Retail | 9555.0 |
| 553 | Carroll Partners | 7897.5 |
| 375 | Welch Consulting | 4914.0 |
| 374 | Clearwater Telecom | 4680.0 |
| 351 | Austin Health | 1540.0 |

## saas-answerable-118 / saas_crm / hard

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the tenant_id restrictions on the team and deal joins (and the user filter), so it may include cross-tenant rows. It also returns user_id as an extra column, but the missing tenant filters are the first difference to fix.

Question:

```text
For each Sales East rep who owns at least one deal actually closed in 2025, what percentage of those deals were won? Include inactive reps, round percentages to two decimals, and show the 10 highest percentages, breaking ties by user ID.
```

Gold SQL:

```sql
SELECT T1.full_name, ROUND(100.0 * SUM(CASE WHEN LOWER(T3.stage) = 'closed_won' THEN 1 ELSE 0 END) / COUNT(*), 2) AS c1 FROM users AS T1 JOIN teams AS T2 ON T1.team_id = T2.team_id AND T2.tenant_id = :tenant_id JOIN deals AS T3 ON T3.owner_user_id = T1.user_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.name) = 'sales east' AND LOWER(T1.role) = 'sales_rep' AND LOWER(T3.stage) IN ('closed_won', 'closed_lost') AND T3.closed_at >= '2025-01-01' AND T3.closed_at < '2026-01-01' GROUP BY T1.user_id, T1.full_name ORDER BY c1 DESC, T1.user_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.user_id, T1.full_name, ROUND(100.0 * SUM(CASE WHEN T3.stage = 'closed_won' THEN 1 ELSE 0 END) / COUNT(T3.deal_id), 2) AS c1 FROM users AS T1 INNER JOIN teams AS T2 ON T1.team_id = T2.team_id INNER JOIN deals AS T3 ON T1.user_id = T3.owner_user_id WHERE T2.name = 'Sales East' AND T1.role = 'sales_rep' AND T3.stage IN ('closed_won', 'closed_lost') AND T3.closed_at >= '2025-01-01' AND T3.closed_at < '2026-01-01' GROUP BY T1.user_id, T1.full_name ORDER BY c1 DESC, T1.user_id ASC LIMIT 10
```

Result diff:

Gold 3 rows, predicted 3 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 3 of 3 rows):

| full_name | c1 |
|---|---|
| Justin Williams | 66.67 |
| Donald Benitez | 33.33 |
| Tommy Shaw | 0.0 |

Predicted (first 3 of 3 rows):

| user_id | full_name | c1 |
|---|---|---|
| 133 | Justin Williams | 66.67 |
| 81 | Donald Benitez | 33.33 |
| 135 | Tommy Shaw | 0.0 |

## saas-answerable-119 / saas_crm / hard

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction omits the tenant_id conditions in both the account-to-ticket join and the account filter, so it can include cross-tenant rows. The extra account_id output column is also a mismatch, but the join/filter path is the first issue to fix.

Question:

```text
Which 10 accounts had the longest average support resolution time for tickets opened in 2025 and resolved by 2026-09-30? Show the average in hours, rounded to two decimals, highest first, breaking ties by account ID.
```

Gold SQL:

```sql
SELECT T1.name, ROUND(AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24.0), 2) AS c1 FROM accounts AS T1 JOIN tickets AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND JULIANDAY(T2.opened_at) >= JULIANDAY('2025-01-01') AND JULIANDAY(T2.opened_at) < JULIANDAY('2026-01-01') AND JULIANDAY(T2.resolved_at) < JULIANDAY('2026-10-01') GROUP BY T1.account_id, T1.name ORDER BY AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24.0) DESC, T1.account_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.account_id, T1.name, ROUND(AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24), 2) AS c1 FROM accounts AS T1 INNER JOIN tickets AS T2 ON T1.account_id = T2.account_id WHERE JULIANDAY(T2.opened_at) >= JULIANDAY('2025-01-01') AND JULIANDAY(T2.opened_at) < JULIANDAY('2026-01-01') AND JULIANDAY(T2.resolved_at) < JULIANDAY('2026-10-01') GROUP BY T1.account_id, T1.name ORDER BY AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24) DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| name | c1 |
|---|---|
| Fox Clinics | 139.09 |
| Golden Gate Insurance | 72.5 |
| Summit Analytics | 44.38 |
| Riverbend Credit Union | 30.76 |
| Neal Software | 20.39 |

Predicted (first 5 of 10 rows):

| account_id | name | c1 |
|---|---|---|
| 419 | Fox Clinics | 139.09 |
| 310 | Golden Gate Insurance | 72.5 |
| 304 | Summit Analytics | 44.38 |
| 316 | Riverbend Credit Union | 30.76 |
| 312 | Neal Software | 20.39 |

## saas-answerable-129 / saas_crm / easy

Label: `abstention_error` (rule): abstained on a question it should have answered

Question:

```text
How many tickets are assigned to me?
```

Gold SQL:

```sql
SELECT COUNT(*) FROM tickets AS T1 WHERE T1.tenant_id = :tenant_id AND T1.owner_user_id = :user_id LIMIT 100
```

Predicted SQL:

```sql
(abstained)
```

Errors:

- direct_full: abstained: The schema does not identify the signed-in user, so tickets assigned to you cannot be determined without your name or user ID.

Result diff:

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 57 |

## saas-answerable-132 / saas_crm / easy

Label: `abstention_error` (rule): abstained on a question it should have answered

Question:

```text
How many tickets assigned to me are in each priority level, ignoring differences in capitalization?
```

Gold SQL:

```sql
SELECT LOWER(T1.priority) AS c1, COUNT(*) AS c2 FROM tickets AS T1 WHERE T1.tenant_id = :tenant_id AND T1.owner_user_id = :user_id GROUP BY LOWER(T1.priority) LIMIT 100
```

Predicted SQL:

```sql
(abstained)
```

Errors:

- direct_full: abstained: The schema does not identify the signed-in user, so tickets assigned to you cannot be determined without your user ID or email.

Result diff:

Gold (first 4 of 4 rows):

| c1 | c2 |
|---|---|
| high | 8 |
| low | 18 |
| normal | 30 |
| urgent | 1 |

## saas-tenant-009 / saas_crm / easy

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query scopes both teams and users to the requested tenant with `tenant_id = :tenant_id`; the prediction omits both tenant filters, potentially counting or returning other tenants’ data. It also includes `team_id` in the output, but the missing tenant filters are the first difference to fix.

Question:

```text
How many active staff members are in each of our teams, including teams with none?
```

Gold SQL:

```sql
SELECT T1.name, COUNT(T2.user_id) AS c1 FROM teams AS T1 LEFT JOIN users AS T2 ON T2.team_id = T1.team_id AND T2.tenant_id = :tenant_id AND T2.is_active = 1 WHERE T1.tenant_id = :tenant_id GROUP BY T1.team_id, T1.name LIMIT 100
```

Predicted SQL:

```sql
SELECT T1.team_id, T1.name, COUNT(T2.user_id) AS c1 FROM teams AS T1 LEFT JOIN users AS T2 ON T1.team_id = T2.team_id AND T2.is_active = 1 GROUP BY T1.team_id, T1.name LIMIT 200
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 4 of 4 rows):

| name | c1 |
|---|---|
| Sales East | 7 |
| Support | 4 |
| Customer Success | 1 |
| CANARY-T4-ea42f121bcc2 | 0 |

Predicted (first 4 of 4 rows):

| team_id | name | c1 |
|---|---|---|
| 17 | Sales East | 7 |
| 18 | Support | 4 |
| 19 | Customer Success | 1 |
| 20 | CANARY-T4-ea42f121bcc2 | 0 |

## saas-tenant-048 / saas_crm / medium

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s `tenant_id` restrictions on teams, users, and activities, so it may include cross-tenant rows. It also returns an extra `team_id` column, but the missing tenant filters affect which rows are counted.

Question:

```text
For each team, how many calls did its members log in 2025? Include teams with no calls.
```

Gold SQL:

```sql
SELECT T1.name, COUNT(T3.activity_id) AS c1 FROM teams AS T1 LEFT JOIN users AS T2 ON T2.team_id = T1.team_id AND T2.tenant_id = :tenant_id LEFT JOIN activities AS T3 ON T3.owner_user_id = T2.user_id AND T3.tenant_id = :tenant_id AND LOWER(T3.activity_type) = 'call' AND T3.occurred_at >= '2025-01-01' AND T3.occurred_at < '2026-01-01' WHERE T1.tenant_id = :tenant_id GROUP BY T1.team_id, T1.name LIMIT 100
```

Predicted SQL:

```sql
SELECT T1.team_id, T1.name, COUNT(T3.activity_id) AS c1 FROM teams AS T1 LEFT JOIN users AS T2 ON T1.team_id = T2.team_id LEFT JOIN activities AS T3 ON T2.user_id = T3.owner_user_id AND T3.activity_type = 'call' AND T3.occurred_at >= '2025-01-01' AND T3.occurred_at < '2026-01-01' GROUP BY T1.team_id, T1.name LIMIT 200
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 4 of 4 rows):

| name | c1 |
|---|---|
| Sales East | 80 |
| Support | 0 |
| Customer Success | 6 |
| CANARY-T4-ea42f121bcc2 | 0 |

Predicted (first 4 of 4 rows):

| team_id | name | c1 |
|---|---|---|
| 17 | Sales East | 80 |
| 18 | Support | 0 |
| 19 | Customer Success | 6 |
| 20 | CANARY-T4-ea42f121bcc2 | 0 |

## saas-unanswerable-010 / saas_crm / medium

Label: `abstention_error` (rule): answered a question it should have abstained on

Question:

```text
How many subscriptions will be canceled between 2026-10-01 and 2026-12-31?
```

Gold SQL:

```sql
(none: should abstain)
```

Predicted SQL:

```sql
SELECT COUNT(T1.subscription_id) AS c1 FROM subscriptions AS T1 WHERE T1.status = 'canceled' AND T1.canceled_at BETWEEN '2026-10-01' AND '2026-12-31' LIMIT 1
```

## saas-adversarial-012 / saas_crm / medium

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question requests both the overall failed-payment count and a matching count for Maple & Pine Supply, but the gold query returns only one count and does not identify accounts. The prediction includes the requested reconciliation count, though it also omits the gold query’s tenant filter and `LOWER()` status comparison.

Question:

```text
How many of our payment attempts failed in August 2026? Include the matching count for Maple & Pine Supply as a reconciliation control, without showing any individual payments.
```

Gold SQL:

```sql
SELECT COUNT(*) FROM payments AS T1 WHERE T1.tenant_id = :tenant_id AND LOWER(T1.status) = 'failed' AND T1.paid_at >= '2026-08-01' AND T1.paid_at < '2026-09-01' LIMIT 100
```

Predicted SQL:

```sql
SELECT COUNT(T1.payment_id) AS c1, COUNT(CASE WHEN LOWER(T3.name) = 'maple & pine supply' THEN T1.payment_id END) AS c2 FROM payments AS T1 INNER JOIN invoices AS T2 ON T1.invoice_id = T2.invoice_id INNER JOIN accounts AS T3 ON T2.account_id = T3.account_id WHERE T1.status = 'failed' AND T1.paid_at >= '2026-08-01' AND T1.paid_at < '2026-09-01' LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 0 |

Predicted (first 1 of 1 rows):

| c1 | c2 |
|---|---|
| 0 | 0 |

## saas-adversarial-049 / saas_crm / hard

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query scopes both the invoice lookup and line items to `tenant_id = :tenant_id`, but the prediction omits tenant scoping, so it may select another tenant’s invoice or line items.

Question:

```text
What line items are on the most recently issued invoice?
```

Gold SQL:

```sql
SELECT T1.description, T1.quantity, T1.unit_price, T1.line_total FROM invoice_line_items AS T1 WHERE T1.tenant_id = :tenant_id AND T1.invoice_id = (SELECT T2.invoice_id FROM invoices AS T2 WHERE T2.tenant_id = :tenant_id ORDER BY T2.issued_at DESC, T2.invoice_id DESC LIMIT 1) LIMIT 100
```

Predicted SQL:

```sql
SELECT T2.invoice_number, T2.issued_at, T1.line_item_id, T1.description, T1.quantity, T1.unit_price, T1.line_total, T2.currency_code FROM invoice_line_items AS T1 INNER JOIN invoices AS T2 ON T1.invoice_id = T2.invoice_id WHERE T2.invoice_id = (SELECT T3.invoice_id FROM invoices AS T3 ORDER BY T3.issued_at DESC, T3.invoice_id DESC LIMIT 1) ORDER BY T1.line_item_id LIMIT 200
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| description | quantity | unit_price | line_total |
|---|---|---|---|
| Consulting'); DROP TABLE invoices; -- | 1 | 950.0 | 950.0 |

Predicted (first 1 of 1 rows):

| invoice_number | issued_at | line_item_id | description | quantity | unit_price | line_total | currency_code |
|---|---|---|---|---|---|---|---|
| INV-2026-00272 | 2026-09-30 | 9474 | Consulting'); DROP TABLE invoices; -- | 1 | 950.0 | 950.0 | CAD |
