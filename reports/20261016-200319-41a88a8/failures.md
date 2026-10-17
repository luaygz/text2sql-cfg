# Failures: best on saas / dev

27 of 209 questions failed. Evidence n/a, git `41a88a836fa385225e7737edd13ac9197637fa02`, complete: 209 questions.

## saas-answerable-034 / saas_crm / medium

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction omits the tenant_id constraints on the team, user, and activity joins, so it can include cross-tenant rows. It also returns an extra team_id column, but the join-path difference is the first issue to fix.

Question:

```text
For each team, how many activities did its members log in Q2 2026? Include only teams with at least five activities.
```

Gold SQL:

```sql
SELECT T1.name, COUNT(T3.activity_id) AS c1 FROM teams AS T1 JOIN users AS T2 ON T2.team_id = T1.team_id AND T2.tenant_id = :tenant_id JOIN activities AS T3 ON T3.owner_user_id = T2.user_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND T3.occurred_at >= '2026-04-01' AND T3.occurred_at < '2026-07-01' GROUP BY T1.team_id, T1.name HAVING COUNT(T3.activity_id) >= 5 LIMIT 1000
```

Predicted SQL:

```sql
SELECT T1.team_id, T1.name, COUNT(T3.activity_id) AS c1 FROM teams AS T1 INNER JOIN users AS T2 ON T1.team_id = T2.team_id INNER JOIN activities AS T3 ON T2.user_id = T3.owner_user_id WHERE T3.occurred_at >= '2026-04-01' AND T3.occurred_at < '2026-07-01' GROUP BY T1.team_id, T1.name HAVING COUNT(T3.activity_id) >= 5 ORDER BY c1 DESC LIMIT 200
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| name | c1 |
|---|---|
| Sales East | 33 |

Predicted (first 1 of 1 rows):

| team_id | name | c1 |
|---|---|---|
| 34 | Sales East | 33 |

## saas-answerable-037 / saas_crm / medium

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query restricts both users and accounts to the requested tenant, but the prediction omits both tenant conditions. That can include cross-tenant accounts or owners and change the results.

Question:

```text
For each account owner, how many customer accounts do they manage? Include former employees, but show only owners with at least three customer accounts, ordered by count descending and then user ID, limited to 10 owners.
```

Gold SQL:

```sql
SELECT T1.full_name, COUNT(T2.account_id) AS c1 FROM users AS T1 JOIN accounts AS T2 ON T2.owner_user_id = T1.user_id AND T2.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.lifecycle_stage) = 'customer' GROUP BY T1.user_id, T1.full_name HAVING COUNT(T2.account_id) >= 3 ORDER BY c1 DESC, T1.user_id LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.user_id, T1.full_name, COUNT(T2.account_id) AS c1 FROM users AS T1 INNER JOIN accounts AS T2 ON T1.user_id = T2.owner_user_id WHERE LOWER(T2.lifecycle_stage) = 'customer' GROUP BY T1.user_id, T1.full_name HAVING COUNT(T2.account_id) >= 3 ORDER BY c1 DESC, T1.user_id ASC LIMIT 10
```

Result diff:

Gold 3 rows, predicted 3 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 3 of 3 rows):

| full_name | c1 |
|---|---|
| Edward Davis | 8 |
| Janice Smith | 7 |
| Brian Nicholson | 4 |

Predicted (first 3 of 3 rows):

| user_id | full_name | c1 |
|---|---|---|
| 123 | Edward Davis | 8 |
| 129 | Janice Smith | 7 |
| 122 | Brian Nicholson | 4 |

## saas-answerable-038 / saas_crm / medium

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction returns `user_id` in addition to `full_name`, `c1`, and `c2`, while the gold query selects only those three columns. The extra output column makes the result rows differ.

Question:

```text
For each Sales East rep with deals actually closed in 2025, how many deals were won and how many were lost?
```

Gold SQL:

```sql
SELECT T1.full_name, SUM(CASE WHEN LOWER(T3.stage) = 'closed_won' THEN 1 ELSE 0 END) AS c1, SUM(CASE WHEN LOWER(T3.stage) = 'closed_lost' THEN 1 ELSE 0 END) AS c2 FROM users AS T1 JOIN teams AS T2 ON T1.team_id = T2.team_id AND T2.tenant_id = :tenant_id JOIN deals AS T3 ON T3.owner_user_id = T1.user_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.name) = 'sales east' AND LOWER(T1.role) = 'sales_rep' AND T3.closed_at >= '2025-01-01' AND T3.closed_at < '2026-01-01' AND LOWER(T3.stage) IN ('closed_won', 'closed_lost') GROUP BY T1.user_id, T1.full_name ORDER BY T1.full_name LIMIT 100 OFFSET 0
```

Predicted SQL:

```sql
SELECT T1.user_id, T1.full_name, SUM(CASE WHEN T3.stage = 'closed_won' THEN 1 ELSE 0 END) AS c1, SUM(CASE WHEN T3.stage = 'closed_lost' THEN 1 ELSE 0 END) AS c2 FROM users AS T1 INNER JOIN teams AS T2 ON T1.team_id = T2.team_id INNER JOIN deals AS T3 ON T3.owner_user_id = T1.user_id WHERE T2.name = 'Sales East' AND T1.role = 'sales_rep' AND T3.stage IN ('closed_won', 'closed_lost') AND T3.closed_at >= '2025-01-01' AND T3.closed_at < '2026-01-01' GROUP BY T1.user_id, T1.full_name ORDER BY T1.full_name LIMIT 200
```

Result diff:

Gold 5 rows, predicted 5 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 5 rows):

| full_name | c1 | c2 |
|---|---|---|
| Ashley Peterson | 1 | 3 |
| Jake Martinez | 1 | 1 |
| James Franco | 2 | 1 |
| Lindsey Pena | 2 | 4 |
| Michael Pierce | 0 | 2 |

Predicted (first 5 of 5 rows):

| user_id | full_name | c1 | c2 |
|---|---|---|---|
| 74 | Ashley Peterson | 1 | 3 |
| 76 | Jake Martinez | 1 | 1 |
| 70 | James Franco | 2 | 1 |
| 107 | Lindsey Pena | 2 | 4 |
| 73 | Michael Pierce | 0 | 2 |

## saas-answerable-043 / saas_crm / medium

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The predicted query returns `user_id` in addition to `full_name` and the account count, while the gold query selects only `full_name` and the count. The previews show the same five users and counts, so the extra output column is the first difference to fix.

Question:

```text
For each active Sales East user who owns at least one account, how many accounts do they own?
```

Gold SQL:

```sql
SELECT T1.full_name, COUNT(T3.account_id) AS c1 FROM users AS T1 JOIN teams AS T2 ON T1.team_id = T2.team_id AND T2.tenant_id = :tenant_id JOIN accounts AS T3 ON T3.owner_user_id = T1.user_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND T1.is_active = 1 AND LOWER(T2.name) = 'sales east' GROUP BY T1.user_id, T1.full_name LIMIT 100 OFFSET 0
```

Predicted SQL:

```sql
SELECT T1.user_id, T1.full_name, COUNT(T3.account_id) AS c1 FROM users AS T1 INNER JOIN teams AS T2 ON T1.team_id = T2.team_id INNER JOIN accounts AS T3 ON T3.owner_user_id = T1.user_id WHERE T1.is_active = 1 AND T2.name = 'Sales East' GROUP BY T1.user_id, T1.full_name LIMIT 200
```

Result diff:

Gold 5 rows, predicted 5 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 5 rows):

| full_name | c1 |
|---|---|
| James Franco | 16 |
| Michael Pierce | 10 |
| Ashley Peterson | 13 |
| Jake Martinez | 6 |
| Lindsey Pena | 25 |

Predicted (first 5 of 5 rows):

| user_id | full_name | c1 |
|---|---|---|
| 70 | James Franco | 16 |
| 73 | Michael Pierce | 10 |
| 74 | Ashley Peterson | 13 |
| 76 | Jake Martinez | 6 |
| 107 | Lindsey Pena | 25 |

## saas-answerable-056 / saas_crm / medium

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The aggregation and quarter grouping identify the same accounts, but the gold returns quarter labels like `2025-Q4` while the prediction returns the integer `4`. The predicted query also omits the tenant filter, but the output-label difference is the first clear mismatch shown by the results.

Question:

```text
For each quarter of 2025, how many accounts did we create in the Hospitality industry? Include only quarters with matching accounts.
```

Gold SQL:

```sql
SELECT '2025-Q' || CAST((CAST(STRFTIME('%m', T1.created_at) AS INTEGER) + 2) / 3 AS INTEGER) AS c1, COUNT(*) AS c2 FROM accounts AS T1 JOIN industries AS T2 ON T1.industry_id = T2.industry_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.name) = 'hospitality' AND T1.created_at >= '2025-01-01' AND T1.created_at < '2026-01-01' GROUP BY '2025-Q' || CAST((CAST(STRFTIME('%m', T1.created_at) AS INTEGER) + 2) / 3 AS INTEGER) ORDER BY c1 LIMIT 100 OFFSET 0
```

Predicted SQL:

```sql
SELECT CAST((CAST(STRFTIME('%m', T1.created_at) AS INTEGER) - 1) / 3 AS INTEGER) + 1 AS c1, COUNT(T1.account_id) AS c2 FROM accounts AS T1 INNER JOIN industries AS T2 ON T1.industry_id = T2.industry_id WHERE T2.name = 'Hospitality' AND T1.created_at >= '2025-01-01' AND T1.created_at < '2026-01-01' GROUP BY CAST((CAST(STRFTIME('%m', T1.created_at) AS INTEGER) - 1) / 3 AS INTEGER) + 1 ORDER BY c1 LIMIT 200
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| c1 | c2 |
|---|---|
| 2025-Q4 | 2 |

Predicted (first 1 of 1 rows):

| c1 | c2 |
|---|---|
| 4 | 2 |

## saas-answerable-066 / saas_crm / easy

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the tenant_id restrictions on both deals and accounts and compares stage/currency directly instead of using LOWER(), so it may include or exclude different rows. It also lacks COALESCE, causing NULL rather than 0 when no rows match.

Question:

```text
What was the total value in USD of USD-denominated deals won with Martin Software in 2025, rounded to two decimals? Match the account name without regard to capitalization and use the actual closing date.
```

Gold SQL:

```sql
SELECT ROUND(COALESCE(SUM(T1.amount), 0), 2) AS c1 FROM deals AS T1 JOIN accounts AS T2 ON T1.account_id = T2.account_id AND T2.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.name) = 'martin software' AND LOWER(T1.stage) = 'closed_won' AND LOWER(T1.currency_code) = 'usd' AND T1.closed_at >= '2025-01-01' AND T1.closed_at < '2026-01-01' LIMIT 100
```

Predicted SQL:

```sql
SELECT ROUND(SUM(T1.amount), 2) AS c1 FROM deals AS T1 INNER JOIN accounts AS T2 ON T1.account_id = T2.account_id WHERE LOWER(T2.name) = 'martin software' AND T1.stage = 'closed_won' AND T1.currency_code = 'USD' AND T1.closed_at >= '2025-01-01' AND T1.closed_at < '2026-01-01' LIMIT 1
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

## saas-answerable-092 / saas_crm / hard

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query creates every quarter/agent combination and LEFT JOINs tickets, while the prediction uses an INNER JOIN, which can omit combinations with no matching tickets. It also omits the tenant constraints on users and tickets used by the gold query.

Question:

```text
For each quarter from Q1 through Q3 2026, what was the average resolution time in hours for tickets assigned to Travis Baird or Brandon Kirby and resolved during that quarter? Show each agent separately, include partial hours and round averages to two decimals.
```

Gold SQL:

```sql
WITH cte1 AS (SELECT 'Q1 2026' AS c1, '2026-01-01' AS c2, '2026-04-01' AS c3 UNION ALL SELECT 'Q2 2026' AS c1, '2026-04-01' AS c2, '2026-07-01' AS c3 UNION ALL SELECT 'Q3 2026' AS c1, '2026-07-01' AS c2, '2026-10-01' AS c3) SELECT T1.c1, T2.full_name, ROUND(AVG((JULIANDAY(T3.resolved_at) - JULIANDAY(T3.opened_at)) * 24.0), 2) AS c4 FROM cte1 AS T1 CROSS JOIN users AS T2 LEFT JOIN tickets AS T3 ON T3.owner_user_id = T2.user_id AND T3.tenant_id = :tenant_id AND JULIANDAY(T3.resolved_at) >= JULIANDAY(T1.c2) AND JULIANDAY(T3.resolved_at) < JULIANDAY(T1.c3) WHERE T2.tenant_id = :tenant_id AND LOWER(T2.full_name) IN ('travis baird', 'brandon kirby') GROUP BY T1.c1, T2.user_id, T2.full_name ORDER BY T1.c1, T2.full_name LIMIT 100
```

Predicted SQL:

```sql
SELECT T2.full_name, CASE WHEN STRFTIME('%m', T1.resolved_at) <= '03' THEN 'Q1 2026' WHEN STRFTIME('%m', T1.resolved_at) <= '06' THEN 'Q2 2026' ELSE 'Q3 2026' END AS c1, ROUND(AVG((JULIANDAY(T1.resolved_at) - JULIANDAY(T1.opened_at)) * 24.0), 2) AS c2 FROM tickets AS T1 INNER JOIN users AS T2 ON T1.owner_user_id = T2.user_id WHERE T2.full_name IN ('Travis Baird', 'Brandon Kirby') AND JULIANDAY(T1.resolved_at) >= JULIANDAY('2026-01-01') AND JULIANDAY(T1.resolved_at) < JULIANDAY('2026-10-01') GROUP BY T2.user_id, T2.full_name, c1 ORDER BY c1, T2.full_name LIMIT 200
```

Result diff:

Gold 6 rows, predicted 6 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 6 rows):

| c1 | full_name | c4 |
|---|---|---|
| Q1 2026 | Brandon Kirby | 19.2 |
| Q1 2026 | Travis Baird | 16.09 |
| Q2 2026 | Brandon Kirby | 23.38 |
| Q2 2026 | Travis Baird | 108.7 |
| Q3 2026 | Brandon Kirby | 37.7 |

Predicted (first 5 of 6 rows):

| full_name | c1 | c2 |
|---|---|---|
| Brandon Kirby | Q1 2026 | 19.2 |
| Travis Baird | Q1 2026 | 16.09 |
| Brandon Kirby | Q2 2026 | 23.38 |
| Travis Baird | Q2 2026 | 108.7 |
| Brandon Kirby | Q3 2026 | 37.7 |

## saas-answerable-100 / saas_crm / hard

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction joins `tenants` only on country, rather than also restricting it to `:tenant_id` as the gold query does; it also omits tenant-scoped join conditions for accounts and invoices. This can include or multiply rows from other tenants. It additionally returns `account_id`, which the gold output omits.

Question:

```text
Which 10 accounts had the most tax billed on non-void invoices issued in 2025 while based in the same country as us? Show each account's tax total in USD using our fixed reporting rates, rounded to two decimals, and break ties by account ID.
```

Gold SQL:

```sql
SELECT T1.name, ROUND(SUM(T2.tax * T4.usd_rate), 2) AS c1 FROM accounts AS T1 JOIN invoices AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id JOIN tenants AS T3 ON T3.country_code = T1.country_code AND T3.tenant_id = :tenant_id JOIN currencies AS T4 ON T4.currency_code = T2.currency_code WHERE T1.tenant_id = :tenant_id AND LOWER(T2.status) <> 'void' AND T2.issued_at >= '2025-01-01' AND T2.issued_at < '2026-01-01' GROUP BY T1.account_id, T1.name ORDER BY SUM(T2.tax * T4.usd_rate) DESC, T1.account_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.account_id, T1.name, ROUND(SUM(T2.tax * T3.usd_rate), 2) AS c1 FROM accounts AS T1 INNER JOIN invoices AS T2 ON T1.account_id = T2.account_id INNER JOIN currencies AS T3 ON T2.currency_code = T3.currency_code INNER JOIN tenants AS T4 ON T1.country_code = T4.country_code WHERE T2.status <> 'void' AND T2.issued_at >= '2025-01-01' AND T2.issued_at < '2026-01-01' GROUP BY T1.account_id, T1.name ORDER BY SUM(T2.tax * T3.usd_rate) DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| name | c1 |
|---|---|
| Austin Health | 0.0 |
| Jones Foods | 0.0 |
| Beck Energy | 0.0 |
| Welch Consulting | 0.0 |
| Ramirez Holdings | 0.0 |

Predicted (first 5 of 10 rows):

| account_id | name | c1 |
|---|---|---|
| 351 | Austin Health | 0.0 |
| 359 | Jones Foods | 0.0 |
| 372 | Beck Energy | 0.0 |
| 375 | Welch Consulting | 0.0 |
| 377 | Ramirez Holdings | 0.0 |

## saas-answerable-104 / saas_crm / medium

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction selects `T2.user_id` in addition to `full_name` and the average, while the gold query returns only `full_name` and the average. This extra column makes the result rows differ.

Question:

```text
For each Support team agent who resolved at least five tickets opened in Q1 2026, what was the average time from opening to resolution in hours? Use tickets with a recorded resolution time, attribute them to their assigned agent, and round averages to two decimals.
```

Gold SQL:

```sql
SELECT T1.full_name, ROUND(AVG((JULIANDAY(T3.resolved_at) - JULIANDAY(T3.opened_at)) * 24.0), 2) AS c1 FROM users AS T1 JOIN teams AS T2 ON T1.team_id = T2.team_id AND T2.tenant_id = :tenant_id JOIN tickets AS T3 ON T3.owner_user_id = T1.user_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.department) = 'support' AND LOWER(T1.role) = 'support_agent' AND T3.resolved_at IS NOT NULL AND JULIANDAY(T3.opened_at) >= JULIANDAY('2026-01-01') AND JULIANDAY(T3.opened_at) < JULIANDAY('2026-04-01') GROUP BY T1.user_id, T1.full_name HAVING COUNT(*) >= 5 LIMIT 100
```

Predicted SQL:

```sql
SELECT T2.user_id, T2.full_name, ROUND(AVG((JULIANDAY(T1.resolved_at) - JULIANDAY(T1.opened_at)) * 24), 2) AS c1 FROM tickets AS T1 INNER JOIN users AS T2 ON T1.owner_user_id = T2.user_id INNER JOIN teams AS T3 ON T2.team_id = T3.team_id WHERE T3.department = 'support' AND T2.role = 'support_agent' AND T1.resolved_at IS NOT NULL AND DATE(T1.opened_at) >= '2026-01-01' AND DATE(T1.opened_at) < '2026-04-01' GROUP BY T2.user_id, T2.full_name HAVING COUNT(T1.ticket_id) >= 5 ORDER BY T2.full_name LIMIT 200
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| full_name | c1 |
|---|---|
| Sara Nelson | 40.46 |
| Stephen Cortez | 14.62 |

Predicted (first 2 of 2 rows):

| user_id | full_name | c1 |
|---|---|---|
| 8 | Sara Nelson | 40.46 |
| 12 | Stephen Cortez | 14.62 |

## saas-answerable-116 / saas_crm / hard

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction omits the tenant_id conditions from the account-to-invoice and invoice-to-payment joins, and also omits the account tenant filter, so it can include cross-tenant rows. It additionally returns account_id, but the first issue to fix is the join path.

Question:

```text
Which 10 accounts had the most successful payment receipts in USD during 2025? Show each account's total converted using the fixed reporting rates, rounded to two decimals, and break ties by account ID.
```

Gold SQL:

```sql
SELECT T1.name, ROUND(SUM(T3.amount / 100.0 * T4.usd_rate), 2) AS c1 FROM accounts AS T1 JOIN invoices AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id JOIN payments AS T3 ON T3.invoice_id = T2.invoice_id AND T3.tenant_id = :tenant_id JOIN currencies AS T4 ON T4.currency_code = T3.currency_code WHERE T1.tenant_id = :tenant_id AND LOWER(T3.status) = 'succeeded' AND T3.paid_at >= '2025-01-01' AND T3.paid_at < '2026-01-01' GROUP BY T1.account_id, T1.name ORDER BY SUM(T3.amount / 100.0 * T4.usd_rate) DESC, T1.account_id ASC LIMIT 10 OFFSET 0
```

Predicted SQL:

```sql
SELECT T1.account_id, T1.name, ROUND(SUM(T3.amount / 100.0 * T4.usd_rate), 2) AS c1 FROM accounts AS T1 INNER JOIN invoices AS T2 ON T1.account_id = T2.account_id INNER JOIN payments AS T3 ON T2.invoice_id = T3.invoice_id INNER JOIN currencies AS T4 ON T3.currency_code = T4.currency_code WHERE T3.status = 'succeeded' AND T3.paid_at >= '2025-01-01' AND T3.paid_at < '2026-01-01' GROUP BY T1.account_id, T1.name ORDER BY SUM(T3.amount / 100.0 * T4.usd_rate) DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| name | c1 |
|---|---|
| Bishop Consulting | 161452.05 |
| Neal Software | 82675.93 |
| adams media | 44200.17 |
| Lewis Energy | 19403.92 |
| Pioneer Dental Group | 17786.93 |

Predicted (first 5 of 10 rows):

| account_id | name | c1 |
|---|---|---|
| 331 | Bishop Consulting | 161452.05 |
| 312 | Neal Software | 82675.93 |
| 418 | adams media | 44200.17 |
| 483 | Lewis Energy | 19403.92 |
| 302 | Pioneer Dental Group | 17786.93 |

## saas-answerable-117 / saas_crm / hard

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the `tenant_id = :tenant_id` restrictions on both accounts and contacts, so it can count or include rows from other tenants. It also selects `account_id` as an extra output column, but the missing tenant filters are the first difference to fix.

Question:

```text
Which 10 accounts have more contacts than the average across all our accounts, including accounts with no contacts? Show the contact count, highest first, breaking ties by account ID.
```

Gold SQL:

```sql
WITH cte1 AS (SELECT T1.account_id, T1.name, COUNT(T2.contact_id) AS c1 FROM accounts AS T1 LEFT JOIN contacts AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id GROUP BY T1.account_id, T1.name) SELECT T1.name, T1.c1 FROM cte1 AS T1 WHERE T1.c1 > (SELECT AVG(T2.c1) FROM cte1 AS T2) ORDER BY T1.c1 DESC, T1.account_id ASC LIMIT 10 OFFSET 0
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.account_id, T1.name, COUNT(T2.contact_id) AS c1 FROM accounts AS T1 LEFT JOIN contacts AS T2 ON T1.account_id = T2.account_id GROUP BY T1.account_id, T1.name) SELECT T1.account_id, T1.name, T1.c1 FROM cte1 AS T1 WHERE T1.c1 > (SELECT AVG(T2.c1) FROM cte1 AS T2) ORDER BY T1.c1 DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| name | c1 |
|---|---|
| Jones Capital | 7 |
| Silverline Media | 6 |
| Simmons Labs | 6 |
| adams media | 6 |
| Granite Peak Energy | 6 |

Predicted (first 5 of 10 rows):

| account_id | name | c1 |
|---|---|---|
| 671 | Jones Capital | 7 |
| 301 | Silverline Media | 6 |
| 305 | Simmons Labs | 6 |
| 418 | adams media | 6 |
| 488 | Granite Peak Energy | 6 |

## saas-answerable-120 / saas_crm / hard

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The predicted query returns account_id in addition to name and call count, while the gold output contains only name and call count. Its filtering, grouping, and ordering otherwise match the gold query.

Question:

```text
Which 10 accounts had the most calls logged in 2025 but no meetings logged in 2025? Show the call count, highest first, breaking ties by account ID.
```

Gold SQL:

```sql
SELECT T1.name, COUNT(*) AS c1 FROM accounts AS T1 JOIN activities AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.activity_type) = 'call' AND T2.occurred_at >= '2025-01-01' AND T2.occurred_at < '2026-01-01' AND NOT EXISTS(SELECT 1 FROM activities AS T3 WHERE T3.tenant_id = :tenant_id AND T3.account_id = T1.account_id AND LOWER(T3.activity_type) = 'meeting' AND T3.occurred_at >= '2025-01-01' AND T3.occurred_at < '2026-01-01') GROUP BY T1.account_id, T1.name ORDER BY c1 DESC, T1.account_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.account_id, T1.name, COUNT(T2.activity_id) AS c1 FROM accounts AS T1 INNER JOIN activities AS T2 ON T1.account_id = T2.account_id WHERE T2.activity_type = 'call' AND T2.occurred_at >= '2025-01-01' AND T2.occurred_at < '2026-01-01' AND NOT EXISTS(SELECT T3.activity_id FROM activities AS T3 WHERE T3.account_id = T1.account_id AND T3.activity_type = 'meeting' AND T3.occurred_at >= '2025-01-01' AND T3.occurred_at < '2026-01-01') GROUP BY T1.account_id, T1.name ORDER BY c1 DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| name | c1 |
|---|---|
| Lewis Energy | 4 |
| Morales Capital | 3 |
| Carroll Partners | 3 |
| Pioneer Dental Group | 2 |
| Garcia, Gilmore and Goodman | 2 |

Predicted (first 5 of 10 rows):

| account_id | name | c1 |
|---|---|---|
| 483 | Lewis Energy | 4 |
| 303 | Morales Capital | 3 |
| 384 | Carroll Partners | 3 |
| 302 | Pioneer Dental Group | 2 |
| 308 | Garcia, Gilmore and Goodman | 2 |

## saas-answerable-121 / saas_crm / hard

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s tenant filters and uses `T2.stage = 'closed_won'` instead of the case-insensitive `LOWER(T2.stage) = 'closed_won'`, which can change the qualifying deals. It also returns an extra `account_id` column, but the filter differences need addressing first.

Question:

```text
Which 10 accounts had a total value of deals won in 2025 above the average among accounts with at least one deal won that year? Use actual close dates, convert deal values to USD using the fixed reporting rates, and show totals rounded to two decimals, highest first, breaking ties by account ID.
```

Gold SQL:

```sql
WITH cte1 AS (SELECT T1.account_id, T1.name, SUM(T2.amount * T3.usd_rate) AS c1 FROM accounts AS T1 JOIN deals AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id JOIN currencies AS T3 ON T3.currency_code = T2.currency_code WHERE T1.tenant_id = :tenant_id AND LOWER(T2.stage) = 'closed_won' AND T2.closed_at >= '2025-01-01' AND T2.closed_at < '2026-01-01' GROUP BY T1.account_id, T1.name) SELECT T1.name, ROUND(T1.c1, 2) AS c1 FROM cte1 AS T1 WHERE T1.c1 > (SELECT AVG(T2.c1) AS c1 FROM cte1 AS T2) ORDER BY T1.c1 DESC, T1.account_id ASC LIMIT 10 OFFSET 0
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.account_id, T1.name, SUM(T2.amount * T3.usd_rate) AS c1 FROM accounts AS T1 INNER JOIN deals AS T2 ON T1.account_id = T2.account_id INNER JOIN currencies AS T3 ON T2.currency_code = T3.currency_code WHERE T2.stage = 'closed_won' AND T2.closed_at >= '2025-01-01' AND T2.closed_at < '2026-01-01' GROUP BY T1.account_id, T1.name) SELECT T1.account_id, T1.name, ROUND(T1.c1, 2) AS c2 FROM cte1 AS T1 WHERE T1.c1 > (SELECT AVG(T2.c1) FROM cte1 AS T2) ORDER BY T1.c1 DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 3 rows, predicted 3 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 3 of 3 rows):

| name | c1 |
|---|---|
| Lewis Energy | 17641.8 |
| Acme Logistics | 14698.2 |
| MORENO MEDIA | 10078.2 |

Predicted (first 3 of 3 rows):

| account_id | name | c2 |
|---|---|---|
| 483 | Lewis Energy | 17641.8 |
| 602 | Acme Logistics | 14698.2 |
| 534 | MORENO MEDIA | 10078.2 |

## saas-answerable-128 / saas_crm / hard

Label: `abstention_error` (rule): abstained on a question it should have answered

Question:

```text
How many of my accounts had more activities logged by me in 2026 than the average across all my accounts, including accounts where I logged no activities?
```

Gold SQL:

```sql
WITH cte1 AS (SELECT COUNT(T2.activity_id) AS c1 FROM accounts AS T1 LEFT JOIN activities AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id AND T2.owner_user_id = :user_id AND T2.occurred_at >= '2026-01-01' AND T2.occurred_at < '2027-01-01' WHERE T1.tenant_id = :tenant_id AND T1.owner_user_id = :user_id GROUP BY T1.account_id) SELECT COUNT(*) FROM cte1 AS T1 WHERE T1.c1 > (SELECT AVG(T2.c1) FROM cte1 AS T2) LIMIT 100
```

Predicted SQL:

```sql
(abstained)
```

Errors:

- direct_full: abstained: The schema does not identify the signed-in user, so I cannot determine which accounts are yours or which activities were logged by you.

Result diff:

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 20 |

## saas-answerable-146 / saas_crm / medium

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction includes `T1.user_id` in the SELECT list, while the gold query returns only `full_name`, `currency_code`, and the rounded total. This extra column makes the result rows differ.

Question:

```text
For each Sales East rep who won at least one deal in 2025, what was the total value of their deals actually won that year, broken down by currency and rounded to two decimals? Include reps who have since left.
```

Gold SQL:

```sql
SELECT T1.full_name, T3.currency_code, ROUND(SUM(T3.amount), 2) AS c1 FROM users AS T1 JOIN teams AS T2 ON T1.team_id = T2.team_id AND T2.tenant_id = :tenant_id JOIN deals AS T3 ON T3.owner_user_id = T1.user_id AND T3.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.name) = 'sales east' AND LOWER(T1.role) = 'sales_rep' AND LOWER(T3.stage) = 'closed_won' AND T3.closed_at >= '2025-01-01' AND T3.closed_at < '2026-01-01' GROUP BY T1.user_id, T1.full_name, T3.currency_code LIMIT 100
```

Predicted SQL:

```sql
SELECT T1.user_id, T1.full_name, T3.currency_code, ROUND(SUM(T3.amount), 2) AS c1 FROM users AS T1 INNER JOIN teams AS T2 ON T1.team_id = T2.team_id INNER JOIN deals AS T3 ON T1.user_id = T3.owner_user_id WHERE T2.name = 'Sales East' AND T1.role = 'sales_rep' AND T3.stage = 'closed_won' AND T3.closed_at >= '2025-01-01' AND T3.closed_at < '2026-01-01' GROUP BY T1.user_id, T1.full_name, T3.currency_code ORDER BY T1.full_name, T3.currency_code LIMIT 200
```

Result diff:

Gold 3 rows, predicted 3 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 3 of 3 rows):

| full_name | currency_code | c1 |
|---|---|---|
| Donald Benitez | AUD | 22270.0 |
| Justin Williams | AUD | 43090.0 |
| Justin Williams | SGD | 5600.0 |

Predicted (first 3 of 3 rows):

| user_id | full_name | currency_code | c1 |
|---|---|---|---|
| 81 | Donald Benitez | AUD | 22270.0 |
| 133 | Justin Williams | AUD | 43090.0 |
| 133 | Justin Williams | SGD | 5600.0 |

## saas-answerable-150 / saas_crm / medium

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s `T2.tenant_id = :tenant_id` restriction, so it may aggregate subscriptions for other tenants. It also selects an extra `plan_id` column, but the missing tenant condition changes which rows contribute to the results.

Question:

```text
For each plan with active subscriptions, what is the total list-price charge per billing period before discounts, and how much do subscription discounts reduce that charge? Use the plan's USD price and licensed seats, keep monthly and annual plans separate, and round both amounts to two decimals.
```

Gold SQL:

```sql
SELECT T1.name, T1.billing_period, ROUND(SUM(T1.price_per_seat * T2.seats), 2) AS c1, ROUND(SUM(T1.price_per_seat * T2.seats * COALESCE(T2.discount_pct, 0) / 100.0), 2) AS c2 FROM plans AS T1 JOIN subscriptions AS T2 ON T2.plan_id = T1.plan_id AND T2.tenant_id = :tenant_id WHERE LOWER(T2.status) = 'active' GROUP BY T1.plan_id, T1.name, T1.billing_period LIMIT 100 OFFSET 0
```

Predicted SQL:

```sql
SELECT T1.plan_id, T1.name, T1.billing_period, ROUND(SUM(T1.price_per_seat * T2.seats), 2) AS c1, ROUND(SUM(T1.price_per_seat * T2.seats * T2.discount_pct / 100.0), 2) AS c2 FROM plans AS T1 INNER JOIN subscriptions AS T2 ON T1.plan_id = T2.plan_id WHERE T2.status = 'active' GROUP BY T1.plan_id, T1.name, T1.billing_period LIMIT 200
```

Result diff:

Gold 6 rows, predicted 6 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 6 rows):

| name | billing_period | c1 | c2 |
|---|---|---|---|
| Starter (monthly) | monthly | 135.0 | 0.0 |
| Starter (annual) | annual | 3600.0 | 180.0 |
| Growth (monthly) | monthly | 5705.0 | 70.0 |
| Growth (annual) | annual | 19950.0 | 2730.0 |
| Business (monthly) | monthly | 20345.0 | 0.0 |

Predicted (first 5 of 6 rows):

| plan_id | name | billing_period | c1 | c2 |
|---|---|---|---|---|
| 1 | Starter (monthly) | monthly | 135.0 | 0.0 |
| 2 | Starter (annual) | annual | 3600.0 | 180.0 |
| 3 | Growth (monthly) | monthly | 5705.0 | 70.0 |
| 4 | Growth (annual) | annual | 19950.0 | 2730.0 |
| 5 | Business (monthly) | monthly | 20345.0 | 0.0 |

## saas-tenant-016 / saas_crm / hard

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The predicted query adds `T1.account_id` to the SELECT list, while the gold query returns only the account name, ticket count, and average hours. The extra output column makes the result rows differ.

Question:

```text
Which 10 accounts had the longest average support resolution time for tickets opened in 2025 and resolved by 2026-09-30? Include only accounts with at least five such tickets, show their ticket counts and average hours rounded to two decimals, and break ties by account ID.
```

Gold SQL:

```sql
SELECT T1.name, COUNT(T2.ticket_id) AS c1, ROUND(AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24.0), 2) AS c2 FROM accounts AS T1 JOIN tickets AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND JULIANDAY(T2.opened_at) >= JULIANDAY('2025-01-01') AND JULIANDAY(T2.opened_at) < JULIANDAY('2026-01-01') AND JULIANDAY(T2.resolved_at) < JULIANDAY('2026-10-01') GROUP BY T1.account_id, T1.name HAVING COUNT(T2.ticket_id) >= 5 ORDER BY AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24.0) DESC, T1.account_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.account_id, T1.name, COUNT(T2.ticket_id) AS c1, ROUND(AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24), 2) AS c2 FROM accounts AS T1 INNER JOIN tickets AS T2 ON T1.account_id = T2.account_id WHERE JULIANDAY(T2.opened_at) >= JULIANDAY('2025-01-01') AND JULIANDAY(T2.opened_at) < JULIANDAY('2026-01-01') AND JULIANDAY(T2.resolved_at) < JULIANDAY('2026-10-01') GROUP BY T1.account_id, T1.name HAVING COUNT(T2.ticket_id) >= 5 ORDER BY AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24) DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| name | c1 | c2 |
|---|---|---|
| Haas Energy | 6 | 18.39 |
| LITTLE HEALTH | 5 | 15.85 |

Predicted (first 2 of 2 rows):

| account_id | name | c1 | c2 |
|---|---|---|---|
| 487 | Haas Energy | 6 | 18.39 |
| 407 | LITTLE HEALTH | 5 | 15.85 |

## saas-tenant-017 / saas_crm / easy

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s tenant filter and EUR-only currency condition, instead including deals of other currencies via conversion. These missing filter conditions are the first differences to fix.

Question:

```text
What was the total EUR value of deals we won in Q2 2026, using their actual close dates, rounded to two decimals?
```

Gold SQL:

```sql
SELECT ROUND(SUM(T1.amount), 2) AS c1 FROM deals AS T1 WHERE T1.tenant_id = :tenant_id AND LOWER(T1.stage) = 'closed_won' AND UPPER(T1.currency_code) = 'EUR' AND T1.closed_at >= '2026-04-01' AND T1.closed_at < '2026-07-01' LIMIT 100
```

Predicted SQL:

```sql
SELECT ROUND(SUM(T1.amount * T2.usd_rate / T3.usd_rate), 2) AS c1 FROM deals AS T1 INNER JOIN currencies AS T2 ON T1.currency_code = T2.currency_code INNER JOIN currencies AS T3 ON T3.currency_code = 'EUR' WHERE T1.stage = 'closed_won' AND T1.closed_at >= '2026-04-01' AND T1.closed_at < '2026-07-01' LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 0 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| c1 |
|---|
| 17250.0 |

Predicted (first 1 of 1 rows):

| c1 |
|---|
| 17250.0 |

## saas-tenant-029 / saas_crm / medium

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the tenant_id constraints on the team, user, and deal rows, and compares department and stage case-sensitively instead of using LOWER(...). It also returns an extra team_id column, but the filtering differences must be addressed first.

Question:

```text
How many deals did each sales team win in 2025? Include teams with no wins.
```

Gold SQL:

```sql
SELECT T1.name, COUNT(T3.deal_id) AS c1 FROM teams AS T1 LEFT JOIN users AS T2 ON T2.team_id = T1.team_id AND T2.tenant_id = :tenant_id LEFT JOIN deals AS T3 ON T3.owner_user_id = T2.user_id AND T3.tenant_id = :tenant_id AND LOWER(T3.stage) = 'closed_won' AND T3.closed_at >= '2025-01-01' AND T3.closed_at < '2026-01-01' WHERE T1.tenant_id = :tenant_id AND LOWER(T1.department) = 'sales' GROUP BY T1.team_id, T1.name LIMIT 100 OFFSET 0
```

Predicted SQL:

```sql
SELECT T1.team_id, T1.name, COUNT(T3.deal_id) AS c1 FROM teams AS T1 LEFT JOIN users AS T2 ON T1.team_id = T2.team_id LEFT JOIN deals AS T3 ON T2.user_id = T3.owner_user_id AND T3.stage = 'closed_won' AND T3.closed_at >= '2025-01-01' AND T3.closed_at < '2026-01-01' WHERE T1.department = 'sales' GROUP BY T1.team_id, T1.name ORDER BY c1 DESC, T1.name LIMIT 200
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 4 of 4 rows):

| name | c1 |
|---|---|
| Sales East | 1 |
| Sales West | 10 |
| Enterprise Sales | 3 |
| CANARY-T1-ff8aac37c22c | 0 |

Predicted (first 4 of 4 rows):

| team_id | name | c1 |
|---|---|---|
| 2 | Sales West | 10 |
| 3 | Enterprise Sales | 3 |
| 1 | Sales East | 1 |
| 6 | CANARY-T1-ff8aac37c22c | 0 |

## saas-tenant-038 / saas_crm / easy

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters to the specified tenant with `tenant_id = :tenant_id`, but the prediction omits that condition, so it can count subscriptions from other tenants. The different quarter formatting does not address this missing filter.

Question:

```text
How many subscriptions started in each quarter of 2025? Include only quarters with new subscriptions.
```

Gold SQL:

```sql
SELECT (CAST(STRFTIME('%m', T1.started_at) AS INTEGER) + 2) / 3 AS c1, COUNT(*) AS c2 FROM subscriptions AS T1 WHERE T1.tenant_id = :tenant_id AND T1.started_at >= '2025-01-01' AND T1.started_at < '2026-01-01' GROUP BY (CAST(STRFTIME('%m', T1.started_at) AS INTEGER) + 2) / 3 ORDER BY c1 LIMIT 100
```

Predicted SQL:

```sql
SELECT '2025-Q' || CAST((CAST(STRFTIME('%m', T1.started_at) AS INTEGER) + 2) / 3 AS INTEGER) AS c1, COUNT(T1.subscription_id) AS c2 FROM subscriptions AS T1 WHERE T1.started_at >= '2025-01-01' AND T1.started_at < '2026-01-01' GROUP BY c1 ORDER BY c1 LIMIT 200
```

Result diff:

Gold 3 rows, predicted 3 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 3 of 3 rows):

| c1 | c2 |
|---|---|
| 1 | 5 |
| 2 | 4 |
| 4 | 5 |

Predicted (first 3 of 3 rows):

| c1 | c2 |
|---|---|
| 2025-Q1 | 5 |
| 2025-Q2 | 4 |
| 2025-Q4 | 5 |

## saas-tenant-044 / saas_crm / hard

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The aggregation and included deal rows match, but the predicted query returns quarter numbers (1, 2, 4) instead of the requested labeled quarters (2025-Q1, 2025-Q2, 2025-Q4) produced by the gold query.

Question:

```text
For deals won in each quarter of 2025, what was the average elapsed time from creation to actual close in days, rounded to two decimals? Include only quarters with won deals.
```

Gold SQL:

```sql
SELECT '2025-Q' || CAST((CAST(STRFTIME('%m', T1.closed_at) AS INTEGER) + 2) / 3 AS INTEGER) AS c1, ROUND(AVG(JULIANDAY(T1.closed_at) - JULIANDAY(T1.created_at)), 2) AS c2 FROM deals AS T1 WHERE T1.tenant_id = :tenant_id AND LOWER(T1.stage) = 'closed_won' AND T1.closed_at >= '2025-01-01' AND T1.closed_at < '2026-01-01' GROUP BY 1 ORDER BY 1 LIMIT 100
```

Predicted SQL:

```sql
SELECT (CAST(STRFTIME('%m', T1.closed_at) AS INTEGER) + 2) / 3 AS c1, ROUND(AVG(JULIANDAY(T1.closed_at) - JULIANDAY(T1.created_at)), 2) AS c2 FROM deals AS T1 WHERE T1.stage = 'closed_won' AND T1.closed_at >= '2025-01-01' AND T1.closed_at < '2026-01-01' GROUP BY (CAST(STRFTIME('%m', T1.closed_at) AS INTEGER) + 2) / 3 ORDER BY c1 LIMIT 200
```

Result diff:

Gold 3 rows, predicted 3 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 3 of 3 rows):

| c1 | c2 |
|---|---|
| 2025-Q1 | 55.81 |
| 2025-Q2 | 52.96 |
| 2025-Q4 | 58.87 |

Predicted (first 3 of 3 rows):

| c1 | c2 |
|---|---|
| 1 | 55.81 |
| 2 | 52.96 |
| 4 | 58.87 |

## saas-tenant-045 / saas_crm / hard

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction returns `user_id` in addition to `full_name` and the average, while the gold query returns only `full_name` and the average. The other differences do not affect the shown rows in this case.

Question:

```text
For tickets opened in Q2 2026 that have a recorded resolution time, what was the average elapsed resolution time in hours for each support agent, rounded to two decimals? Show the 10 agents with the highest averages, breaking ties by user ID.
```

Gold SQL:

```sql
SELECT T2.full_name, ROUND(AVG((JULIANDAY(T1.resolved_at) - JULIANDAY(T1.opened_at)) * 24.0), 2) AS c1 FROM tickets AS T1 JOIN users AS T2 ON T1.owner_user_id = T2.user_id AND T2.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND LOWER(T2.role) = 'support_agent' AND JULIANDAY(T1.opened_at) >= JULIANDAY('2026-04-01') AND JULIANDAY(T1.opened_at) < JULIANDAY('2026-07-01') AND T1.resolved_at IS NOT NULL GROUP BY T2.user_id, T2.full_name ORDER BY AVG((JULIANDAY(T1.resolved_at) - JULIANDAY(T1.opened_at)) * 24.0) DESC, T2.user_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T2.user_id, T2.full_name, ROUND(AVG((JULIANDAY(T1.resolved_at) - JULIANDAY(T1.opened_at)) * 24), 2) AS c1 FROM tickets AS T1 INNER JOIN users AS T2 ON T1.owner_user_id = T2.user_id WHERE T2.role = 'support_agent' AND JULIANDAY(T1.opened_at) >= JULIANDAY('2026-04-01') AND JULIANDAY(T1.opened_at) < JULIANDAY('2026-07-01') AND T1.resolved_at IS NOT NULL GROUP BY T2.user_id, T2.full_name ORDER BY c1 DESC, T2.user_id ASC LIMIT 10
```

Result diff:

Gold 3 rows, predicted 3 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 3 of 3 rows):

| full_name | c1 |
|---|---|
| Phillip Green | 38.96 |
| Rodney Edwards | 37.76 |
| Tracy Smith | 14.24 |

Predicted (first 3 of 3 rows):

| user_id | full_name | c1 |
|---|---|---|
| 46 | Phillip Green | 38.96 |
| 53 | Rodney Edwards | 37.76 |
| 121 | Tracy Smith | 14.24 |

## saas-tenant-051 / saas_crm / hard

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the tenant constraints on users, teams, and deals, so it can include rows outside the requested tenant. It also returns `user_id` as an extra output column, but the missing tenant restrictions are the first substantive difference.

Question:

```text
Which 10 sales reps had the highest total value of deals won in Q2 2026, converted to USD using our fixed reporting rates? Show each rep's team and total rounded to two decimals; break ties by rep ID.
```

Gold SQL:

```sql
SELECT T1.full_name, T2.name, ROUND(SUM(T3.amount * T4.usd_rate), 2) AS c1 FROM users AS T1 LEFT JOIN teams AS T2 ON T1.team_id = T2.team_id AND T2.tenant_id = :tenant_id JOIN deals AS T3 ON T1.user_id = T3.owner_user_id AND T3.tenant_id = :tenant_id JOIN currencies AS T4 ON T3.currency_code = T4.currency_code WHERE T1.tenant_id = :tenant_id AND LOWER(T1.role) = 'sales_rep' AND LOWER(T3.stage) = 'closed_won' AND T3.closed_at >= '2026-04-01' AND T3.closed_at < '2026-07-01' GROUP BY T1.user_id, T1.full_name, T2.name ORDER BY SUM(T3.amount * T4.usd_rate) DESC, T1.user_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.user_id, T1.full_name, T2.name, ROUND(SUM(T3.amount * T4.usd_rate), 2) AS c1 FROM users AS T1 LEFT JOIN teams AS T2 ON T1.team_id = T2.team_id INNER JOIN deals AS T3 ON T1.user_id = T3.owner_user_id INNER JOIN currencies AS T4 ON T3.currency_code = T4.currency_code WHERE T1.role = 'sales_rep' AND T3.stage = 'closed_won' AND T3.closed_at >= '2026-04-01' AND T3.closed_at < '2026-07-01' GROUP BY T1.user_id, T1.full_name, T2.name ORDER BY SUM(T3.amount * T4.usd_rate) DESC, T1.user_id ASC LIMIT 10
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| full_name | name | c1 |
|---|---|---|
| David Jimenez | Sales East | 7975.0 |

Predicted (first 1 of 1 rows):

| user_id | full_name | name | c1 |
|---|---|---|---|
| 63 | David Jimenez | Sales East | 7975.0 |

## saas-tenant-052 / saas_crm / hard

Label: `wrong_join_path` (classifier, gpt-6-luna): The predicted joins omit the tenant_id constraints used in the gold query for tickets and users, so they can include cross-tenant rows or match users from another tenant. The extra account_id output column is also a difference, but the join path is the first issue to fix.

Question:

```text
Which 10 accounts had the highest average resolution time for tickets opened in 2025 that have a recorded resolution time? Show each account's industry, account manager, and average resolution time in hours rounded to two decimals; break ties by account ID.
```

Gold SQL:

```sql
SELECT T1.name, T3.name, T4.full_name, ROUND(AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24.0), 2) AS c1 FROM accounts AS T1 JOIN tickets AS T2 ON T2.account_id = T1.account_id AND T2.tenant_id = :tenant_id LEFT JOIN industries AS T3 ON T3.industry_id = T1.industry_id LEFT JOIN users AS T4 ON T4.user_id = T1.owner_user_id AND T4.tenant_id = :tenant_id WHERE T1.tenant_id = :tenant_id AND DATE(T2.opened_at) >= '2025-01-01' AND DATE(T2.opened_at) < '2026-01-01' AND T2.resolved_at IS NOT NULL GROUP BY T1.account_id, T1.name, T3.name, T4.full_name ORDER BY AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24.0) DESC, T1.account_id ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.account_id, T1.name, T3.name, T4.full_name, ROUND(AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24), 2) AS c1 FROM accounts AS T1 INNER JOIN tickets AS T2 ON T1.account_id = T2.account_id LEFT JOIN industries AS T3 ON T1.industry_id = T3.industry_id LEFT JOIN users AS T4 ON T1.owner_user_id = T4.user_id WHERE DATE(T2.opened_at) >= '2025-01-01' AND DATE(T2.opened_at) < '2026-01-01' AND T2.resolved_at IS NOT NULL GROUP BY T1.account_id, T1.name, T3.name, T4.full_name ORDER BY AVG((JULIANDAY(T2.resolved_at) - JULIANDAY(T2.opened_at)) * 24) DESC, T1.account_id ASC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| name | name | full_name | c1 |
|---|---|---|---|
| Morse Labs | Hospitality | Gary Harmon | 57.25 |
| Tran Group | Logistics | Zachary Reyes | 45.69 |
| BLUEWATER FOODS | None | Destiny Andrews | 44.47 |
| Ortiz and Sons | Legal Services | David Jimenez | 35.91 |
| Adkins-Riley | Retail | Gary Harmon | 34.91 |

Predicted (first 5 of 10 rows):

| account_id | name | name | full_name | c1 |
|---|---|---|---|---|
| 187 | Morse Labs | Hospitality | Gary Harmon | 57.25 |
| 449 | Tran Group | Logistics | Zachary Reyes | 45.69 |
| 212 | BLUEWATER FOODS | None | Destiny Andrews | 44.47 |
| 213 | Ortiz and Sons | Legal Services | David Jimenez | 35.91 |
| 204 | Adkins-Riley | Retail | Gary Harmon | 34.91 |

## saas-tenant-057 / saas_crm / medium

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query restricts subscriptions to `T1.tenant_id = :tenant_id` and compares status case-insensitively with `LOWER(...) = 'active'`; the prediction omits the tenant filter and uses an exact-case status comparison.

Question:

```text
For each subscription plan we currently use for active subscriptions, how many active subscriptions and licensed seats do we have?
```

Gold SQL:

```sql
SELECT T2.name, COUNT(*) AS c1, SUM(T1.seats) AS c2 FROM subscriptions AS T1 JOIN plans AS T2 ON T1.plan_id = T2.plan_id WHERE T1.tenant_id = :tenant_id AND LOWER(T1.status) = 'active' GROUP BY T2.plan_id, T2.name LIMIT 100
```

Predicted SQL:

```sql
SELECT T1.plan_id, T1.name, COUNT(T2.subscription_id) AS c1, SUM(T2.seats) AS c2 FROM plans AS T1 INNER JOIN subscriptions AS T2 ON T1.plan_id = T2.plan_id WHERE T2.status = 'active' GROUP BY T1.plan_id, T1.name ORDER BY T1.name LIMIT 200
```

Result diff:

Gold 8 rows, predicted 8 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 8 rows):

| name | c1 | c2 |
|---|---|---|
| Starter (monthly) | 12 | 68 |
| Starter (annual) | 16 | 73 |
| Growth (monthly) | 13 | 306 |
| Growth (annual) | 13 | 339 |
| Business (monthly) | 5 | 439 |

Predicted (first 5 of 8 rows):

| plan_id | name | c1 | c2 |
|---|---|---|---|
| 6 | Business (annual) | 9 | 776 |
| 5 | Business (monthly) | 5 | 439 |
| 7 | Enterprise (annual) | 1 | 325 |
| 4 | Growth (annual) | 13 | 339 |
| 3 | Growth (monthly) | 13 | 306 |

## saas-unanswerable-031 / saas_crm / hard

Label: `abstention_error` (rule): answered a question it should have abstained on

Question:

```text
How many licensed seats did Pioneer Dental Group have across its subscriptions on 2025-12-31?
```

Gold SQL:

```sql
(none: should abstain)
```

Predicted SQL:

```sql
SELECT COALESCE(SUM(T2.seats), 0) AS c1 FROM accounts AS T1 INNER JOIN subscriptions AS T2 ON T1.account_id = T2.account_id WHERE LOWER(T1.name) = 'pioneer dental group' AND T2.started_at <= '2025-12-31' AND (T2.canceled_at IS NULL OR T2.canceled_at > '2025-12-31') LIMIT 1
```

## saas-unanswerable-037 / saas_crm / hard

Label: `abstention_error` (rule): answered a question it should have abstained on

Question:

```text
How many of the deals open on 2026-09-30 will actually be won in Q4 2026?
```

Gold SQL:

```sql
(none: should abstain)
```

Predicted SQL:

```sql
SELECT COUNT(T1.deal_id) AS c1 FROM deals AS T1 WHERE T1.created_at < '2026-10-01' AND T1.stage = 'closed_won' AND T1.closed_at >= '2026-10-01' AND T1.closed_at < '2027-01-01' LIMIT 1
```
