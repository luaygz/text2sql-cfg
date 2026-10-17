# Failures: best on bird_minidev / test

48 of 150 questions failed. Evidence on, git `70b12ce88825feb7263dfaf0a75ccf74d10bb829`, complete: 150 questions.

## 24 / california_schools / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query requires `T1.NumGE1500 > 0`, but the prediction omits that filter, so schools without qualifying test takers are included. It also selects `NumGE1500` as an extra column, but the missing filter is the first difference to fix.

Gold label suspect: yes.

Question:

```text
Give the names of the schools with the percent eligible for free meals in K-12 is more than 0.1 and test takers whose test score is greater than or equal to 1500?
```

Evidence:

```text
Percent eligible for free meals = Free Meal Count (K-12) / Total (Enrollment (K-12)
```

Gold SQL:

```sql
SELECT T2.`School Name` FROM satscores AS T1 INNER JOIN frpm AS T2 ON T1.cds = T2.CDSCode WHERE CAST(T2.`Free Meal Count (K-12)` AS REAL) / T2.`Enrollment (K-12)` > 0.1 AND T1.NumGE1500 > 0
```

Predicted SQL:

```sql
SELECT T1.`School Name`, T2.NumGE1500 FROM frpm AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE CAST(T1.`Free Meal Count (K-12)` AS REAL) / T1.`Enrollment (K-12)` > 0.1
```

Result diff:

Gold 1165 rows, predicted 1658 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 1165 rows):

| School Name |
|---|
| FAME Public Charter |
| Envision Academy for Arts & Technology |
| Alameda Science and Technology Institute |
| Alameda High |
| Alternatives in Action |

Predicted (first 5 of 1658 rows):

| School Name | NumGE1500 |
|---|---|
| FAME Public Charter | 9 |
| Envision Academy for Arts & Technology | 5 |
| Aspire California College Preparatory A… | None |
| Alameda Science and Technology Institute | 29 |
| Nea Community Learning Center | None |

## 28 / california_schools / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Consider the average difference between K-12 enrollment and 15-17 enrollment of schools that are locally funded, list the names and DOC type of schools which has a difference above this average.
```

Evidence:

```text
Difference between K-12 enrollment and 15-17 enrollment can be computed by `Enrollment (K-12)` - `Enrollment (Ages 5-17)`
```

Gold SQL:

```sql
SELECT T2.School, T2.DOC FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.FundingType = 'Locally funded' AND (T1.`Enrollment (K-12)` - T1.`Enrollment (Ages 5-17)`) > (SELECT AVG(T3.`Enrollment (K-12)` - T3.`Enrollment (Ages 5-17)`) FROM frpm AS T3 INNER JOIN schools AS T4 ON T3.CDSCode = T4.CDSCode WHERE T4.FundingType = 'Locally funded')
```

Predicted SQL:

```sql
SELECT T1.School, T1.DOCType FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.FundingType = 'Locally funded' AND T2.`Enrollment (K-12)` - T2.`Enrollment (Ages 5-17)` > (SELECT AVG(T4.`Enrollment (K-12)` - T4.`Enrollment (Ages 5-17)`) FROM schools AS T3 INNER JOIN frpm AS T4 ON T3.CDSCode = T4.CDSCode WHERE T3.FundingType = 'Locally funded')
```

Result diff:

Gold 57 rows, predicted 57 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 57 rows):

| School | DOC |
|---|---|
| Mountain Oaks | 00 |
| Castle Rock | 00 |
| Charter Community School Home Study Aca… | 00 |
| Clovis Online Charter | 54 |
| Washington Elementary | 52 |

Predicted (first 5 of 57 rows):

| School | DOCType |
|---|---|
| Mountain Oaks | County Office of Education (COE) |
| Castle Rock | County Office of Education (COE) |
| Charter Community School Home Study Aca… | County Office of Education (COE) |
| Clovis Online Charter | Unified School District |
| Washington Elementary | Elementary School District |

## 37 / california_schools / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction excludes schools with a NULL numerator or nonpositive test-taker count, so it ranks valid excellence rates; the gold query does not and can sort an undefined rate first in SQLite. Thus the gold result may not identify the school with the lowest meaningful excellence rate.

Gold label suspect: yes.

Question:

```text
What is the complete address of the school with the lowest excellence rate? Indicate the Street, City, Zip and State.
```

Evidence:

```text
Execellence Rate = NumGE1500 / NumTstTakr; complete address has Street, City, State, Zip code
```

Gold SQL:

```sql
SELECT T2.Street, T2.City, T2.State, T2.Zip FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode ORDER BY CAST(T1.NumGE1500 AS REAL) / T1.NumTstTakr ASC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.Street, T1.City, T1.Zip, T1.State FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T2.NumGE1500 IS NOT NULL AND T2.NumTstTakr > 0 ORDER BY CAST(T2.NumGE1500 AS REAL) / T2.NumTstTakr ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| Street | City | State | Zip |
|---|---|---|---|
| 2125 Jefferson Avenue | Berkeley | CA | 94703-1414 |

Predicted (first 1 of 1 rows):

| Street | City | Zip | State |
|---|---|---|---|
| 2607 Myrtle Street | Oakland | 94607-3415 | CA |

## 115 / financial / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
For the branch which located in the south Bohemia with biggest number of inhabitants, what is the percentage of the male clients?
```

Evidence:

```text
Percentage of the male clients = DIVIDE(COUNT(male clients), COUNT(clients)) * 100; Male refers to gender = 'M', A3 is the region name. A4 contains the information about inhabitants.
```

Gold SQL:

```sql
SELECT CAST(SUM(T1.gender = 'M') AS REAL) * 100 / COUNT(T1.client_id) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T2.A3 = 'south Bohemia' GROUP BY T2.A4 ORDER BY T2.A4 DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.gender = 'M' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.client_id) FROM client AS T1 INNER JOIN (SELECT T2.district_id FROM district AS T2 WHERE T2.A3 = 'south Bohemia' ORDER BY CAST(T2.A4 AS INTEGER) DESC LIMIT 1) AS T3 ON T1.district_id = T3.district_id
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(T1.gender = 'M') AS REAL) * 10… |
|---|
| 44.26229508196721 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.gender = 'M' THEN… |
|---|
| 40.0 |

## 159 / financial / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
List all the withdrawals in cash transactions that the client with the id 3356 makes.
```

Evidence:

```text
operation = 'VYBER' refers to withdrawal in cash
```

Gold SQL:

```sql
SELECT T4.trans_id FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id INNER JOIN trans AS T4 ON T3.account_id = T4.account_id WHERE T1.client_id = 3356 AND T4.operation = 'VYBER'
```

Predicted SQL:

```sql
SELECT T1.* FROM trans AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id WHERE T2.client_id = 3356 AND T1.operation = 'VYBER'
```

Result diff:

Gold 140 rows, predicted 140 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 140 rows):

| trans_id |
|---|
| 816173 |
| 816174 |
| 816175 |
| 816181 |
| 816185 |

Predicted (first 5 of 140 rows):

| trans_id | account_id | date | type | operation | amount | balance | k_symbol | bank | account |
|---|---|---|---|---|---|---|---|---|---|
| 816173 | 2779 | 1993-12-02 | VYDAJ | VYBER | 800 | 42072 | None | None | None |
| 816174 | 2779 | 1994-12-29 | VYDAJ | VYBER | 2400 | 59207 | None | None | None |
| 816175 | 2779 | 1995-12-05 | VYDAJ | VYBER | 4320 | 45682 | None | None | None |
| 816181 | 2779 | 1993-11-20 | VYDAJ | VYBER | 600 | 42711 | None | None | None |
| 816185 | 2779 | 1994-02-24 | VYDAJ | VYBER | 3480 | 40506 | None | None | None |

## 186 / financial / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What percentage of male clients request for weekly statements to be issued?
```

Evidence:

```text
Percentage of male clients = [count(male clients who requested weekly statements / count(clients who requested weekly statements)] * 100%; Male means gender = 'M'; 'POPLATEK TYDNE' stands for weekly issuance
```

Gold SQL:

```sql
SELECT CAST(SUM(T1.gender = 'M') AS REAL) * 100 / COUNT(T1.client_id) FROM client AS T1 INNER JOIN district AS T3 ON T1.district_id = T3.district_id INNER JOIN account AS T2 ON T2.district_id = T3.district_id INNER JOIN disp as T4 on T1.client_id = T4.client_id AND T2.account_id = T4.account_id WHERE T2.frequency = 'POPLATEK TYDNE'
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T1.gender = 'M' THEN T1.client_id END) AS REAL) * 100 / COUNT(DISTINCT T1.client_id) FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id WHERE T3.frequency = 'POPLATEK TYDNE'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(T1.gender = 'M') AS REAL) * 10… |
|---|
| 52.63157894736842 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T1.gender… |
|---|
| 52.12765957446808 |

## 198 / toxicology / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The evidence defines the requested average as the total number of single bonds divided by the atom count. The prediction computes that ratio, while the gold query instead averages per-molecule single-bond counts, so the gold SQL does not match the stated calculation.

Gold label suspect: yes.

Question:

```text
On average how many carcinogenic molecules are single bonded?
```

Evidence:

```text
carcinogenic molecules refers to label = '+'; single-bonded refers to bond_type = '-'; average = DIVIDE(SUM(bond_type = '-'), COUNT(atom_id))
```

Gold SQL:

```sql
SELECT AVG(single_bond_count) FROM (SELECT T3.molecule_id, COUNT(T1.bond_type) AS single_bond_count FROM bond AS T1  INNER JOIN atom AS T2 ON T1.molecule_id = T2.molecule_id INNER JOIN molecule AS T3 ON T3.molecule_id = T2.molecule_id WHERE T1.bond_type = '-' AND T3.label = '+' GROUP BY T3.molecule_id) AS subquery
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T4.bond_type = '-' THEN 1 ELSE 0 END) AS REAL) / COUNT(T2.atom_id) FROM molecule AS T1 INNER JOIN atom AS T2 ON T1.molecule_id = T2.molecule_id INNER JOIN connected AS T3 ON T2.atom_id = T3.atom_id INNER JOIN bond AS T4 ON T3.bond_id = T4.bond_id WHERE T1.label = '+'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(single_bond_count) |
|---|
| 732.125 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T4.bond_type = '-' T… |
|---|
| 0.8285329744279946 |

## 215 / toxicology / challenging

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query links atoms to bonds through `connected` on `atom_id` and `bond_id`, while the prediction joins `atom` to `bond` by `molecule_id`, counting atoms in molecules with a single bond rather than atoms incident to one. This incorrect join path is the first issue to fix.

Gold label suspect: yes.

Question:

```text
How many atoms with iodine and with sulfur type elements are there in single bond molecules?
```

Evidence:

```text
with iodine element refer to element = 'i'; with sulfur element refers to element = 's'; single type bond refers to bond_type = '-'; Should consider the distinct atoms when counting;
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT CASE WHEN T1.element = 'i' THEN T1.atom_id ELSE NULL END) AS iodine_nums , COUNT(DISTINCT CASE WHEN T1.element = 's' THEN T1.atom_id ELSE NULL END) AS sulfur_nums FROM atom AS T1 INNER JOIN connected AS T2 ON T1.atom_id = T2.atom_id INNER JOIN bond AS T3 ON T2.bond_id = T3.bond_id WHERE T3.bond_type = '-'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.atom_id) FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id WHERE T1.element IN ('i', 's') AND T2.bond_type = '-'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| iodine_nums | sulfur_nums |
|---|---|
| 3 | 77 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.atom_id) |
|---|
| 97 |

## 219 / toxicology / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The evidence defines the requested percentage as triple-bond counts divided by all bond counts among carcinogenic molecules, which is what the prediction calculates. The gold query instead computes the percentage of molecules with a triple bond that are carcinogenic, reversing the denominator and counting molecules rather than bonds.

Question:

```text
What is the percentage of carcinogenic molecules in triple type bonds?
```

Evidence:

```text
label = '+' mean molecules are carcinogenic; triple bond refers to bond_type = '#'; percentage = DIVIDE(SUM(bond_type = '#') * 100, COUNT(bond_id)) as percent where label = '+'
```

Gold SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T2.label = '+' THEN T2.molecule_id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT T2.molecule_id) FROM atom AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id INNER JOIN bond AS T3 ON T2.molecule_id = T3.molecule_id WHERE T3.bond_type = '#'
```

Predicted SQL:

```sql
SELECT CAST(SUM(T1.bond_type = '#') AS REAL) * 100 / COUNT(T1.bond_id) FROM bond AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.label = '+'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.label … |
|---|
| 66.66666666666667 |

Predicted (first 1 of 1 rows):

| CAST(SUM(T1.bond_type = '#') AS REAL) *… |
|---|
| 0.08075370121130551 |

## 281 / toxicology / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): “Tally” calls for counts by element, which the prediction provides with `COUNT(*)` and `GROUP BY`. The gold query only returns distinct elements and omits the tally.

Gold label suspect: yes.

Question:

```text
Tally the toxicology element of the 4th atom of each molecule that was carcinogenic.
```

Evidence:

```text
label = '+' means molecules are carcinogenic; 4th atom of each molecule refers to substr(atom_id, 7, 1) = '4'; 
```

Gold SQL:

```sql
SELECT DISTINCT T1.element FROM atom AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.label = '+' AND SUBSTR(T1.atom_id, -1) = '4' AND LENGTH(T1.atom_id) = 7
```

Predicted SQL:

```sql
SELECT T1.element, COUNT(*) FROM atom AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.label = '+' AND SUBSTR(T1.atom_id, 7, 1) = '4' GROUP BY T1.element
```

Result diff:

Gold 8 rows, predicted 9 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 8 rows):

| element |
|---|
| cl |
| c |
| br |
| n |
| o |

Predicted (first 5 of 9 rows):

| element | COUNT(*) |
|---|---|
| br | 6 |
| c | 145 |
| cl | 9 |
| f | 1 |
| h | 59 |

## 402 / card_games / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks to list the qualifying cards by ID as well as give the percentage. The prediction returns the percentage and IDs, while the gold query returns only the percentage and omits the requested IDs.

Gold label suspect: yes.

Question:

```text
What is the percentage of Story Spotlight cards that do not have a text box? List them by their ID.
```

Evidence:

```text
Story Spotlight cards that do not have a text box refers to isStorylight = 1 and isTextless = 0; Percentage = DIVIDE(SUM(count(id) where isStorylight = 1 AND isTextless = 0 ), SUM(count(id))) * 100
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN isTextless = 0 AND  isStorySpotlight = 1 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(id) FROM cards
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT CAST(SUM(CASE WHEN T1.isStorySpotlight = 1 AND T1.isTextless = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) AS c1 FROM cards AS T1) SELECT T2.c1, T1.id FROM cards AS T1 CROSS JOIN cte1 AS T2 WHERE T1.isStorySpotlight = 1 AND T1.isTextless = 0 ORDER BY T1.id
```

Result diff:

Gold 1 rows, predicted 104 rows. Within the previews: 1 rows only in gold, 5 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN isTextless = 0 AND i… |
|---|
| 0.18302770053852382 |

Predicted (first 5 of 104 rows):

| c1 | id |
|---|---|
| 0.18302770053852382 | 4569 |
| 0.18302770053852382 | 4590 |
| 0.18302770053852382 | 4612 |
| 0.18302770053852382 | 4650 |
| 0.18302770053852382 | 4687 |

## 405 / card_games / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The evidence identifies Brazilian Portuguese as `language = 'Portuguese (Brasil)'`, which the prediction uses; the gold query instead filters for `'Portuguese (Brazil)'`. Thus the gold literal contradicts the stated evidence.

Question:

```text
How many Brazilian Portuguese translated sets are inside the Commander block?
```

Evidence:

```text
Commander block refer to block = 'Commander'; sets refer to code = setCode; Portuguese refer to language = 'Portuguese (Brasil)'
```

Gold SQL:

```sql
SELECT COUNT(T1.id) FROM sets AS T1 INNER JOIN set_translations AS T2 ON T1.code = T2.setCode WHERE T2.language = 'Portuguese (Brazil)' AND T1.block = 'Commander'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.code) FROM sets AS T1 INNER JOIN set_translations AS T2 ON T1.code = T2.setCode WHERE T1.block = 'Commander' AND T2.language = 'Portuguese (Brasil)'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.id) |
|---|
| 7 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.code) |
|---|
| 0 |

## 465 / card_games / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query counts a Korean translation only when `T2.translation IS NOT NULL`, but the prediction checks only whether a Korean set-translation row exists. The returned string casing also differs (`YES` versus `Yes`).

Gold label suspect: yes.

Question:

```text
For the set of cards with "Ancestor's Chosen" in it, is there a Korean version of it?
```

Evidence:

```text
set of cards with "Ancestor''s Chosen" in it refers to name = 'Ancestor''s Chosen'; Korean version refers to language = 'Korean'
```

Gold SQL:

```sql
SELECT IIF(SUM(CASE WHEN T2.language = 'Korean' AND T2.translation IS NOT NULL THEN 1 ELSE 0 END) > 0, 'YES', 'NO') FROM cards AS T1 INNER JOIN set_translations AS T2 ON T2.setCode = T1.setCode WHERE T1.name = 'Ancestor''s Chosen'
```

Predicted SQL:

```sql
SELECT CASE WHEN EXISTS(SELECT 1 FROM cards AS T1 INNER JOIN set_translations AS T2 ON T1.setCode = T2.setCode WHERE T1.name = 'Ancestor''s Chosen' AND T2.language = 'Korean') THEN 'Yes' ELSE 'No' END
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| IIF(SUM(CASE WHEN T2.language = 'Korean… |
|---|
| YES |

Predicted (first 1 of 1 rows):

| CASE WHEN EXISTS(SELECT 1 FROM cards AS… |
|---|
| Yes |

## 474 / card_games / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The evidence explicitly defines “base set number of under 100” as `baseSetSize < 10`, which the prediction uses; the gold query instead uses `< 100` and contradicts that definition.

Question:

```text
Among the sets of cards that have an Italian translation, how many of them have a base set number of under 100?
```

Evidence:

```text
Italian translation refers to language = 'Italian'; have a translation means translation is not null; base set number of under 100 refers to baseSetSize < 10
```

Gold SQL:

```sql
SELECT COUNT(T1.id) FROM sets AS T1 INNER JOIN set_translations AS T2 ON T2.setCode = T1.code WHERE T2.translation IS NOT NULL AND T1.baseSetSize < 100 AND T2.language = 'Italian'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.id) FROM sets AS T1 INNER JOIN set_translations AS T2 ON T1.code = T2.setCode WHERE T2.language = 'Italian' AND T2.translation IS NOT NULL AND T1.baseSetSize < 10
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.id) |
|---|
| 30 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.id) |
|---|
| 0 |

## 518 / card_games / moderate

Label: `other` (classifier, gpt-6-luna): The queries are equivalent for the requested rows: both select the format with the most records having status = 'Banned' and return its banned card names. COUNT(status) equals COUNT(*) under that filter, and DISTINCT does not change set-valued results.

Gold label suspect: yes.

Question:

```text
Which of the play format has the highest number of banned status? Indicate the play format and the names of all the card meet the condition.
```

Evidence:

```text
play format refers to format; banned status refers to status = 'Banned'; the highest number of banned status refers to MAX(COUNT(status = 'Banned'))
```

Gold SQL:

```sql
WITH MaxBanned AS (SELECT format, COUNT(*) AS count_banned FROM legalities WHERE status = 'Banned' GROUP BY format ORDER BY COUNT(*) DESC LIMIT 1) SELECT T2.format, T1.name FROM cards AS T1 INNER JOIN legalities AS T2 ON T2.uuid = T1.uuid INNER JOIN MaxBanned MB ON MB.format = T2.format WHERE T2.status = 'Banned'
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.format FROM legalities AS T1 WHERE T1.status = 'Banned' GROUP BY T1.format ORDER BY COUNT(T1.status) DESC LIMIT 1) SELECT DISTINCT T1.format, T3.name FROM cte1 AS T1 INNER JOIN legalities AS T2 ON T1.format = T2.format INNER JOIN cards AS T3 ON T2.uuid = T3.uuid WHERE T2.status = 'Banned'
```

Result diff:

Predicted (first 5 of 102 rows):

| format | name |
|---|---|
| legacy | Balance |
| legacy | Crusade |
| legacy | Ancestral Recall |
| legacy | Time Walk |
| legacy | Timetwister |

## 529 / card_games / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction checks that each set has a Korean translation and no Japanese translation for that set, matching the question. The gold query applies `language NOT LIKE '%Japanese%'` only to the same row already constrained to `language = 'Korean'`, so it does not rule out sets that also have Japanese translations.

Gold label suspect: yes.

Question:

```text
Find and list the names of sets which doesn't have Japanese translation but have Korean translation.
```

Evidence:

```text
names of sets refers to name; doesn't have Japanese translation refers to language not like '%Japanese%'; have Korean translation refers to language = 'Korean'
```

Gold SQL:

```sql
SELECT name FROM sets WHERE code IN ( SELECT setCode FROM set_translations WHERE language = 'Korean' AND language NOT LIKE '%Japanese%' )
```

Predicted SQL:

```sql
SELECT DISTINCT T1.name FROM sets AS T1 INNER JOIN set_translations AS T2 ON T1.code = T2.setCode WHERE T2.language = 'Korean' AND NOT EXISTS(SELECT T3.id FROM set_translations AS T3 WHERE T3.setCode = T1.code AND T3.language LIKE '%Japanese%')
```

Result diff:

Gold 121 rows, predicted 0 rows. Within the previews: 5 rows only in gold, 0 only in predicted.

Gold (first 5 of 121 rows):

| name |
|---|
| Tenth Edition |
| Fourth Edition |
| Fifth Dawn |
| Fifth Edition |
| Classic Sixth Edition |

Predicted (first 0 of 0 rows):

| name |
|---|

## 533 / codebase_community / simple

Label: `date_handling` (classifier, gpt-6-luna): The gold query compares `date(LastAccessDate)` to the cutoff, while the prediction compares the raw `LastAccessDate` value. That difference in date handling produces a different count (4941 vs. 5146).

Question:

```text
How many users last accessed the website after 2014/9/1?
```

Evidence:

```text
last accessed after 2014/9/1 refers to LastAccessDate > '2014-09-01'
```

Gold SQL:

```sql
SELECT COUNT(Id) FROM users WHERE date(LastAccessDate) > '2014-09-01'
```

Predicted SQL:

```sql
SELECT COUNT(*) FROM users AS T1 WHERE T1.LastAccessDate > '2014-09-01'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(Id) |
|---|
| 4941 |

Predicted (first 1 of 1 rows):

| COUNT(*) |
|---|
| 5146 |

## 581 / codebase_community / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The predicted SQL omits the question mark from the title literal, so its exact-match WHERE condition returns no rows instead of the gold query's owner.

Question:

```text
Who is the owner of the post titled 'Open source tools for visualizing multi-dimensional data?'
```

Evidence:

```text
'Open source tools for visualizing multi-dimensional data' is the Title of Post; owner refers to DisplayName;
```

Gold SQL:

```sql
SELECT T2.DisplayName FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Title = 'Open source tools for visualizing multi-dimensional data?'
```

Predicted SQL:

```sql
SELECT T2.DisplayName FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Title = 'Open source tools for visualizing multi-dimensional data'
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| DisplayName |
|---|
| Paul |

Predicted (first 0 of 0 rows):

| DisplayName |
|---|

## 639 / codebase_community / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction uses posts authored by Community and checks their Tags field for <r>, matching the question. The gold query instead joins postHistory.PostId to tags.ExcerptPostId, which identifies a tag’s excerpt post rather than posts that use that tag.

Question:

```text
Based on posts posted by Community, calculate the percentage of posts that use the R language.
```

Evidence:

```text
DIVIDE(COUNT(PostId WHERE TagName = 'r')), (COUNT(PostId WHERE DisplayName = 'Community')) as percentage; R language refers to tagname = 'r'
```

Gold SQL:

```sql
SELECT CAST(SUM(IIF(T3.TagName = 'r', 1, 0)) AS REAL) * 100 / COUNT(T1.Id) FROM users AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.UserId INNER JOIN tags AS T3 ON T3.ExcerptPostId = T2.PostId WHERE T1.DisplayName = 'Community'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.Tags LIKE '%<r>%' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.Id) FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T2.DisplayName = 'Community'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(T3.TagName = 'r', 1, 0)) A… |
|---|
| 0.19569471624266144 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.Tags LIKE '%<r>%'… |
|---|
| 0.0 |

## 682 / codebase_community / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Which is the most valuable post in 2010? Please give its id and the owner's display name.
```

Evidence:

```text
the most valuable post in 2010 refers to MAX(FavoriteCount) where year(CreationDate) = 2010;
```

Gold SQL:

```sql
SELECT T2.OwnerUserId, T1.DisplayName FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId WHERE STRFTIME('%Y', T1.CreationDate) = '2010' ORDER BY T2.FavoriteCount DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.Id, T2.DisplayName FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE STRFTIME('%Y', T1.CreaionDate) = '2010' ORDER BY T1.FavoriteCount DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| OwnerUserId | DisplayName |
|---|---|
| 890 | Fabian Fagerholm |

Predicted (first 1 of 1 rows):

| Id | DisplayName |
|---|---|
| 1595 | Fabian Fagerholm |

## 683 / codebase_community / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query filters on `posts.CreaionDate`, while the prediction filters on `posts.CreationDate`. That column difference changes which posts qualify for 2011.

Gold label suspect: yes.

Question:

```text
What is the percentage of posts whose owners had a reputation of over 1000 in 2011?
```

Evidence:

```text
percentage = DIVIDE(COUNT(Id where YEAR(CreationDate) = 2011 and Reputation > 1000), COUNT(Id) ) * 100;
```

Gold SQL:

```sql
SELECT CAST(SUM(IIF(STRFTIME('%Y', T2.CreaionDate) = '2011' AND T1.Reputation > 1000, 1, 0)) AS REAL) * 100 / COUNT(T1.Id) FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId
```

Predicted SQL:

```sql
SELECT CAST(COUNT(CASE WHEN STRFTIME('%Y', T2.CreationDate) = '2011' AND T2.Reputation > 1000 THEN T1.Id END) AS REAL) * 100 / COUNT(T1.Id) FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(STRFTIME('%Y', T2.CreaionD… |
|---|
| 7.24159250999183 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN STRFTIME('%Y', T2.… |
|---|
| 11.324441892816923 |

## 710 / codebase_community / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
In posts with 1 comment, how many of the comments have 0 score?
```

Evidence:

```text
in posts with 1 comment refers to CommentCount = 1;
```

Gold SQL:

```sql
SELECT COUNT(T1.id) FROM comments AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id WHERE T2.CommentCount = 1 AND T2.Score = 0
```

Predicted SQL:

```sql
SELECT COUNT(T1.Id) FROM comments AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id WHERE T2.CommentCount = 1 AND T1.Score = 0
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.id) |
|---|
| 2888 |

Predicted (first 1 of 1 rows):

| COUNT(T1.Id) |
|---|
| 10997 |

## 728 / superhero / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction returns the eye color and count but omits the gold query’s PopularityRank column. Its filtering, grouping, and count ordering otherwise match.

Question:

```text
Rank superheroes from Marvel Comics by their eye color popularity, starting with the most common color.
```

Evidence:

```text
the superheroes from Marvel Comics refers to publisher_name = 'Marvel Comics'; most common color refers to COUNT(superhero.id) DESC;
```

Gold SQL:

```sql
SELECT colour.colour AS EyeColor, COUNT(superhero.id) AS Count, RANK() OVER (ORDER BY COUNT(superhero.id) DESC) AS PopularityRank FROM superhero INNER JOIN colour ON superhero.eye_colour_id = colour.id INNER JOIN publisher ON superhero.publisher_id = publisher.id WHERE publisher.publisher_name = 'Marvel Comics' GROUP BY colour.colour
```

Predicted SQL:

```sql
SELECT T3.colour, COUNT(T1.id) AS c1 FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id INNER JOIN colour AS T3 ON T1.eye_colour_id = T3.id WHERE T2.publisher_name = 'Marvel Comics' GROUP BY T3.colour ORDER BY c1 DESC
```

Result diff:

Gold 19 rows, predicted 19 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 19 rows):

| EyeColor | Count | PopularityRank |
|---|---|---|
| Blue | 126 | 1 |
| Brown | 89 | 2 |
| No Colour | 47 | 3 |
| Green | 40 | 4 |
| Red | 31 | 5 |

Predicted (first 5 of 19 rows):

| colour | c1 |
|---|---|
| Blue | 126 |
| Brown | 89 |
| No Colour | 47 |
| Green | 40 |
| Red | 31 |

## 744 / superhero / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Between DC and Marvel Comics, which publisher has published more superheroes? Find the difference in the number of superheroes they have published.
```

Evidence:

```text
DC refers to publisher_name = 'DC Comics'; Marvel Comics refers to publisher_name = 'Marvel Comics'; calculation = SUBTRACT(SUM(publisher_name = 'Marvel Comics'), SUM(publisher_name = 'DC Comics'))
```

Gold SQL:

```sql
SELECT SUM(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) - SUM(CASE WHEN T2.publisher_name = 'DC Comics' THEN 1 ELSE 0 END) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id
```

Predicted SQL:

```sql
SELECT CASE WHEN SUM(T2.publisher_name = 'Marvel Comics') > SUM(T2.publisher_name = 'DC Comics') THEN 'Marvel Comics' ELSE 'DC Comics' END, SUM(T2.publisher_name = 'Marvel Comics') - SUM(T2.publisher_name = 'DC Comics') FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T2.publisher_name IN ('Marvel Comics', 'DC Comics')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(CASE WHEN T2.publisher_name = 'Marv… |
|---|
| 163 |

Predicted (first 1 of 1 rows):

| CASE WHEN SUM(T2.publisher_name = 'Marv… | SUM(T2.publisher_name = 'Marvel Comics'… |
|---|---|
| Marvel Comics | 163 |

## 847 / formula_1 / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What is the surname of the driver with the best lap time in race number 19 in the second qualifying period?
```

Evidence:

```text
race number refers to raceId; second qualifying period refers to q2; best lap time refers to MIN(q2);
```

Gold SQL:

```sql
SELECT T2.surname FROM qualifying AS T1 INNER JOIN drivers AS T2 ON T2.driverId = T1.driverId WHERE T1.raceId = 19 ORDER BY T1.q2 ASC LIMIT 1
```

Predicted SQL:

```sql
SELECT T2.surname FROM qualifying AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId WHERE T1.raceId = 19 AND T1.q2 IS NOT NULL ORDER BY T1.q2 ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| surname |
|---|
| Fisichella |

Predicted (first 1 of 1 rows):

| surname |
|---|
| Räikkönen |

## 866 / formula_1 / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The filters, join, and DISTINCT logic match, but the gold query returns forename and surname along with the URL. The prediction returns only the URL, so it is missing two output columns.

Question:

```text
Who was the player that got the lap time of 0:01:27 in the race No. 161? Show his introduction website.
```

Evidence:

```text
player and driver are synonyms; the lap time of 0:0M:SS refers to lapTime.time LIKE 'M:SS%';race number refers to raceId; introduction website of the drivers refers to url;
```

Gold SQL:

```sql
SELECT DISTINCT T2.forename, T2.surname, T2.url FROM lapTimes AS T1 INNER JOIN drivers AS T2 ON T2.driverId = T1.driverId WHERE T1.raceId = 161 AND T1.time LIKE '1:27%'
```

Predicted SQL:

```sql
SELECT DISTINCT T2.url FROM lapTimes AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId WHERE T1.time LIKE '1:27%' AND T1.raceId = 161
```

Result diff:

Gold 9 rows, predicted 9 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 9 rows):

| forename | surname | url |
|---|---|---|
| David | Coulthard | http://en.wikipedia.org/wiki/David_Coul… |
| Jarno | Trulli | http://en.wikipedia.org/wiki/Jarno_Trul… |
| Jenson | Button | http://en.wikipedia.org/wiki/Jenson_But… |
| Rubens | Barrichello | http://en.wikipedia.org/wiki/Rubens_Bar… |
| Ralf | Schumacher | http://en.wikipedia.org/wiki/Ralf_Schum… |

Predicted (first 5 of 9 rows):

| url |
|---|
| http://en.wikipedia.org/wiki/David_Coul… |
| http://en.wikipedia.org/wiki/Jarno_Trul… |
| http://en.wikipedia.org/wiki/Jenson_But… |
| http://en.wikipedia.org/wiki/Rubens_Bar… |
| http://en.wikipedia.org/wiki/Ralf_Schum… |

## 928 / formula_1 / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The joins and filters select the same ranked driver, but the prediction returns only driverRef, while the gold query also returns forename and surname.

Gold label suspect: yes.

Question:

```text
Which driver ranked the first in the Canadian Grand Prix in 2007? Please give his reference name.
```

Evidence:

```text
reference name refers to driverRef; Canadian Grand Prix refers to races.name = 'Canadian Grand Prix';
```

Gold SQL:

```sql
SELECT T3.forename, T3.surname, T3.driverRef FROM races AS T1 INNER JOIN results AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId WHERE T1.name = 'Canadian Grand Prix' AND T2.rank = 1 AND T1.year = 2007
```

Predicted SQL:

```sql
SELECT T1.driverRef FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T2.raceId = T3.raceId WHERE T3.name = 'Canadian Grand Prix' AND T3.year = 2007 AND T2.rank = 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| forename | surname | driverRef |
|---|---|---|
| Fernando | Alonso | alonso |

Predicted (first 1 of 1 rows):

| driverRef |
|---|
| alonso |

## 937 / formula_1 / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What's the finish time for the driver who ranked second in 2008's AustChineseralian Grand Prix?
```

Evidence:

```text
finish time refers to time; Chinese Grand Prix refers to races.name = 'Chinese Grand Prix';
```

Gold SQL:

```sql
SELECT T1.time FROM results AS T1 INNER JOIN races AS T2 on T1.raceId = T2.raceId WHERE T1.rank = 2 AND T2.name = 'Chinese Grand Prix' AND T2.year = 2008
```

Predicted SQL:

```sql
SELECT T1.time FROM results AS T1 INNER JOIN races AS T2 ON T1.raceId = T2.raceId WHERE T1.position = 2 AND T2.year = 2008 AND T2.name = 'Chinese Grand Prix'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| time |
|---|
| +16.445 |

Predicted (first 1 of 1 rows):

| time |
|---|
| +14.925 |

## 950 / formula_1 / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query reads points from `constructorStandings`, while the prediction reads them from `constructorResults`. That table difference produces a different set of constructor names.

Question:

```text
Please list the constructor names with 0 points at race 291.
```

Evidence:

```text
race at 291 refers to raceID = 291;
```

Gold SQL:

```sql
SELECT T2.name FROM constructorStandings AS T1 INNER JOIN constructors AS T2 on T1.constructorId = T2.constructorId WHERE T1.points = 0 AND T1.raceId = 291
```

Predicted SQL:

```sql
SELECT T1.name FROM constructors AS T1 INNER JOIN constructorResults AS T2 ON T1.constructorId = T2.constructorId WHERE T2.raceId = 291 AND T2.points = 0
```

Result diff:

Gold 6 rows, predicted 11 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 5 of 6 rows):

| name |
|---|
| Ligier |
| Jordan |
| Larrousse |
| Brabham |
| Dallara |

Predicted (first 5 of 11 rows):

| name |
|---|
| Minardi |
| Dallara |
| Larrousse |
| Team Lotus |
| Fondmetal |

## 955 / formula_1 / challenging

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query converts the champion’s `results.time` value from `HH:MM:SS.mmm` to seconds, while the prediction averages `results.milliseconds` instead. The evidence specifies the finished time representation, so the prediction uses the wrong column for the requested calculation.

Gold label suspect: yes.

Question:

```text
What is the average time in seconds of champion for each year, before year 1975?
```

Evidence:

```text
only champion's finished time is represented by 'HH:MM:SS.mmm'; finished the game refers to time is not null; before year 1975 refers to year < 1975;
```

Gold SQL:

```sql
WITH time_in_seconds AS ( SELECT T2.year, T2.raceId, T1.positionOrder, CASE WHEN T1.positionOrder = 1 THEN (CAST(SUBSTR(T1.time, 1, 1) AS REAL) * 3600) + (CAST(SUBSTR(T1.time, 3, 2) AS REAL) * 60) + CAST(SUBSTR(T1.time, 6,2) AS REAL )   + CAST(SUBSTR(T1.time, 9) AS REAL)/1000 ELSE 0 END AS time_seconds FROM results AS T1 INNER JOIN races AS T2 ON T1.raceId = T2.raceId WHERE T1.time IS NOT NULL ), champion_time AS ( SELECT year, raceId, time_seconds FROM time_in_seconds WHERE positionOrder = 1 ) SELECT year, AVG(time_seconds) FROM champion_time WHERE year < 1975 GROUP BY year HAVING AVG(time_seconds) IS NOT NULL
```

Predicted SQL:

```sql
SELECT T1.year, AVG(T2.milliseconds) / 1000.0 FROM races AS T1 INNER JOIN results AS T2 ON T1.raceId = T2.raceId WHERE T1.year < 1975 AND T2.position = 1 AND T2.time IS NOT NULL GROUP BY T1.year
```

Result diff:

Gold 25 rows, predicted 25 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 25 rows):

| year | AVG(time_seconds) |
|---|---|
| 1950 | 9712.01842857143 |
| 1951 | 10870.343222222224 |
| 1952 | 11061.26325 |
| 1953 | 10828.015666666666 |
| 1954 | 11212.563444444444 |

Predicted (first 5 of 25 rows):

| year | AVG(T2.milliseconds) / 1000.0 |
|---|---|
| 1950 | 9712.595714285715 |
| 1951 | 10870.532222222222 |
| 1952 | 11061.585 |
| 1953 | 10828.476666666666 |
| 1954 | 11213.074444444444 |

## 967 / formula_1 / simple

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks for the code numbers of the three youngest drivers as well as the number who are Dutch. The gold query returns only the Dutch count, while the prediction includes the driver codes.

Question:

```text
State code numbers of top 3 yougest drivers. How many Netherlandic drivers among them?
```

Evidence:

```text
youngest driver refers to Max (year(dob)); Netherlandic and Dutch refer to the same country
```

Gold SQL:

```sql
SELECT COUNT(*) FROM ( SELECT T1.nationality FROM drivers AS T1 ORDER BY JULIANDAY(T1.dob) DESC LIMIT 3) AS T3 WHERE T3.nationality = 'Dutch'
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.code, T1.nationality FROM drivers AS T1 WHERE T1.dob IS NOT NULL ORDER BY STRFTIME('%Y', T1.dob) DESC LIMIT 3) SELECT T1.code, (SELECT COUNT(*) FROM cte1 AS T2 WHERE T2.nationality = 'Dutch') AS c1 FROM cte1 AS T1
```

Result diff:

Gold 1 rows, predicted 3 rows. Within the previews: 1 rows only in gold, 3 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 1 |

Predicted (first 3 of 3 rows):

| code | c1 |
|---|---|
| STR | 1 |
| VER | 1 |
| OCO | 1 |

## 1014 / formula_1 / challenging

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query uses `results.FastestLapTime` to identify lap records, while the prediction reads individual `lapTimes.time` values. That changes the source and meaning of the time being reported.

Question:

```text
Please list the lap records for the circuits in Italy.
```

Evidence:

```text
lap record means the fastest time recorded which refers to time
```

Gold SQL:

```sql
WITH fastest_lap_times AS (SELECT T1.raceId, T1.FastestLapTime, (CAST(SUBSTR(T1.FastestLapTime, 1, INSTR(T1.FastestLapTime, ':') - 1) AS REAL) * 60) + (CAST(SUBSTR(T1.FastestLapTime, INSTR(T1.FastestLapTime, ':') + 1, INSTR(T1.FastestLapTime, '.') - INSTR(T1.FastestLapTime, ':') - 1) AS REAL)) + (CAST(SUBSTR(T1.FastestLapTime, INSTR(T1.FastestLapTime, '.') + 1) AS REAL) / 1000) as time_in_seconds FROM results AS T1 WHERE T1.FastestLapTime IS NOT NULL ) SELECT T1.FastestLapTime as lap_record FROM results AS T1 INNER JOIN races AS T2 on T1.raceId = T2.raceId INNER JOIN circuits AS T3 on T2.circuitId = T3.circuitId INNER JOIN (SELECT MIN(fastest_lap_times.time_in_seconds) as min_time_in_seconds FROM fastest_lap_times INNER JOIN races AS T2 on fastest_lap_times.raceId = T2.raceId INNER JOIN circuits AS T3 on T2.circuitId = T3.circuitId WHERE T3.country = 'Italy' ) AS T4 ON (CAST(SUBSTR(T1.FastestLapTime, 1, INSTR(T1.FastestLapTime, ':') - 1) AS REAL) * 60) + (CAST(SUBSTR(T1.FastestLapTime, INSTR(T1.FastestLapTime, ':') + 1, INSTR(T1.FastestLapTime, '.') - INSTR(T1.FastestLapTime, ':') - 1) AS REAL)) + (CAST(SUBSTR(T1.FastestLapTime, INSTR(T1.FastestLapTime, '.') + 1) AS REAL) / 1000) = T4.min_time_in_seconds LIMIT 1
```

Predicted SQL:

```sql
SELECT MIN(T3.time) FROM circuits AS T1 INNER JOIN races AS T2 ON T1.circuitId = T2.circuitId INNER JOIN lapTimes AS T3 ON T2.raceId = T3.raceId WHERE T1.country = 'Italy' AND T3.time IS NOT NULL GROUP BY T1.circuitId
```

Result diff:

Gold 1 rows, predicted 2 rows. Within the previews: 1 rows only in gold, 2 only in predicted.

Gold (first 1 of 1 rows):

| lap_record |
|---|
| 1:20.411 |

Predicted (first 2 of 2 rows):

| MIN(T3.time) |
|---|
| 15:14.219 |
| 13:29.130 |

## 1028 / european_football_2 / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query groups only by `away_team_api_id`, while the prediction additionally groups by `team_long_name`. That can split one away team’s wins across groups and change which team ranks first.

Gold label suspect: yes.

Question:

```text
In Scotland Premier League, which away team won the most during the 2010 season?
```

Evidence:

```text
Final result should return the Team.team_long_name; Scotland Premier League refers to League.name = 'Scotland Premier League'; away team refers to away_team_api_id; away team that won the most refers to MAX(SUBTRACT(away_team_goal, home_team_goal) > 0); 2010 season refers to season = '2009/2010'; won the most refers to MAX(COUNT(*));
```

Gold SQL:

```sql
SELECT teamInfo.team_long_name FROM League AS leagueData INNER JOIN Match AS matchData ON leagueData.id = matchData.league_id INNER JOIN Team AS teamInfo ON matchData.away_team_api_id = teamInfo.team_api_id WHERE leagueData.name = 'Scotland Premier League' AND matchData.season = '2009/2010' AND matchData.away_team_goal - matchData.home_team_goal > 0 GROUP BY matchData.away_team_api_id ORDER BY COUNT(*) DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.team_long_name FROM Team AS T1 INNER JOIN `Match` AS T2 ON T1.team_api_id = T2.away_team_api_id INNER JOIN League AS T3 ON T2.league_id = T3.id WHERE T3.name = 'Scotland Premier League' AND T2.season = '2009/2010' AND T2.away_team_goal > T2.home_team_goal GROUP BY T1.team_api_id, T1.team_long_name ORDER BY COUNT(*) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| team_long_name |
|---|
| Celtic |

Predicted (first 1 of 1 rows):

| team_long_name |
|---|
| Rangers |

## 1031 / european_football_2 / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
At present, calculate for the player's age who have a sprint speed of no less than 97 between 2013 to 2015.
```

Evidence:

```text
players age at present = SUBTRACT((DATETIME(), birthday)); sprint speed of no less than 97 refers to sprint_speed > = 97; between 2013 to 2015 refers to YEAR(date) > = '2013' AND YEAR(date) < = '2015'; 
```

Gold SQL:

```sql
SELECT DISTINCT DATETIME() - T2.birthday age FROM Player_Attributes AS t1 INNER JOIN Player AS t2 ON t1.player_api_id = t2.player_api_id WHERE STRFTIME('%Y',t1.`date`) >= '2013' AND STRFTIME('%Y',t1.`date`) <= '2015' AND t1.sprint_speed >= 97
```

Predicted SQL:

```sql
SELECT DISTINCT CAST(STRFTIME('%Y', 'now') AS INTEGER) - CAST(STRFTIME('%Y', T1.birthday) AS INTEGER) - CASE WHEN STRFTIME('%m-%d', 'now') < STRFTIME('%m-%d', T1.birthday) THEN 1 ELSE 0 END AS c1 FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T2.sprint_speed >= 97 AND STRFTIME('%Y', T2.date) >= '2013' AND STRFTIME('%Y', T2.date) <= '2015'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| age |
|---|
| 36 |

Predicted (first 1 of 1 rows):

| c1 |
|---|
| 35 |

## 1068 / european_football_2 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query casts the summed rating to REAL before division, producing a fractional average. The prediction performs integer division in SQLite and returns 68 instead of 68.854….

Gold label suspect: yes.

Question:

```text
From 2010 to 2015, what was the average overall rating of players who are higher than 170?
```

Evidence:

```text
from 2010 to 2015 refers to strftime('%Y', date) >= '2010' AND <= '2015'; average overall rating = SUM(t2.overall_rating)/ COUNT(t2.id); higher than 170 refers to Player.height > 170;
```

Gold SQL:

```sql
SELECT CAST(SUM(t2.overall_rating) AS REAL) / COUNT(t2.id) FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id WHERE t1.height > 170 AND STRFTIME('%Y',t2.`date`) >= '2010' AND STRFTIME('%Y',t2.`date`) <= '2015'
```

Predicted SQL:

```sql
SELECT SUM(T2.overall_rating) / COUNT(T2.id) FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.height > 170 AND STRFTIME('%Y', T2.date) >= '2010' AND STRFTIME('%Y', T2.date) <= '2015'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(t2.overall_rating) AS REAL) / … |
|---|
| 68.85402657670379 |

Predicted (first 1 of 1 rows):

| SUM(T2.overall_rating) / COUNT(T2.id) |
|---|
| 68 |

## 1107 / european_football_2 / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
When was the first time did Kevin Constant have his highest crossing score? Give the date.
```

Evidence:

```text
Kevin Constant refers to player_name = 'Kevin Constant'; highest crossing score refers to MAX(crossing)
```

Gold SQL:

```sql
SELECT `date` FROM ( SELECT t2.crossing, t2.`date` FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_fifa_api_id = t2.player_fifa_api_id WHERE t1.player_name = 'Kevin Constant' ORDER BY t2.crossing DESC) ORDER BY date DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.date FROM Player_Attributes AS T1 INNER JOIN Player AS T2 ON T1.player_api_id = T2.player_api_id WHERE T2.player_name = 'Kevin Constant' AND T1.date IS NOT NULL AND T1.crossing = (SELECT MAX(T3.crossing) FROM Player_Attributes AS T3 INNER JOIN Player AS T4 ON T3.player_api_id = T4.player_api_id WHERE T4.player_name = 'Kevin Constant') ORDER BY T1.date ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| date |
|---|
| 2016-04-21 00:00:00 |

Predicted (first 1 of 1 rows):

| date |
|---|
| 2013-02-15 00:00:00 |

## 1144 / european_football_2 / simple

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction returns only finishing and curve, while the gold query also selects id. Its heaviest-player lookup and attribute values otherwise match the gold result.

Gold label suspect: yes.

Question:

```text
Please state the finishing rate and curve score of the player who has the heaviest weight.
```

Evidence:

```text
finishing rate refer to finishing; curve score refer to curve; heaviest weight refers to MAX(weight)
```

Gold SQL:

```sql
SELECT id, finishing, curve FROM Player_Attributes WHERE player_api_id = ( SELECT player_api_id FROM Player ORDER BY weight DESC LIMIT 1 ) LIMIT 1
```

Predicted SQL:

```sql
SELECT T2.finishing, T2.curve FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.weight IS NOT NULL ORDER BY T1.weight DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| id | finishing | curve |
|---|---|---|
| 98022 | 13 | 13 |

Predicted (first 1 of 1 rows):

| finishing | curve |
|---|---|
| 13 | 13 |

## 1168 / thrombosis_prediction / challenging

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The joins, filters, ordering, and calculated age match the gold query, but the prediction omits `T2.Birthday` from the SELECT list; the gold output includes that third column.

Gold label suspect: yes.

Question:

```text
The oldest SJS patient's medical laboratory work was completed on what date, and what age was the patient when they initially arrived at the hospital?
```

Evidence:

```text
The larger the birthday value, the younger the person is, and vice versa; 'SJS' refers to diagnosis; (SUBTRACT(year(`First Date`)), year(Birthday)); age of the patients when they initially arrived at the hospital refers to year(Birthday)
```

Gold SQL:

```sql
SELECT T1.Date, STRFTIME('%Y', T2.`First Date`) - STRFTIME('%Y', T2.Birthday),T2.Birthday FROM Laboratory AS T1 INNER JOIN Patient AS T2 ON T1.ID = T2.ID WHERE T2.Diagnosis = 'SJS' AND T2.Birthday IS NOT NULL ORDER BY T2.Birthday ASC LIMIT 1
```

Predicted SQL:

```sql
SELECT T2.Date, CAST(STRFTIME('%Y', T1.`First Date`) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.Diagnosis = 'SJS' AND T1.Birthday IS NOT NULL ORDER BY T1.Birthday ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| Date | STRFTIME('%Y', T2.`First Date`) - STRFT… | Birthday |
|---|---|---|
| 1981-07-31 | 69 | 1917-04-18 |

Predicted (first 1 of 1 rows):

| Date | CAST(STRFTIME('%Y', T1.`First Date`) AS… |
|---|---|
| 1981-07-31 | 69 |

## 1171 / thrombosis_prediction / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction tests whether the birth year itself is before 18, whereas the gold query tests whether the examination year minus the birth year is under 18. That changes the underage condition and produces a different count.

Question:

```text
How many underage patients were examined during the course of the three-year period from 1990 to 1993?
```

Evidence:

```text
underage patients refers to year(Birthday) < 18; three-year period from 1990 to 1993 refers to year(`Examination Date`) between '1990' and '1993'
```

Gold SQL:

```sql
SELECT COUNT(T1.ID) FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE STRFTIME('%Y', T2.`Examination Date`) BETWEEN '1990' AND '1993' AND STRFTIME('%Y', T2.`Examination Date`) - STRFTIME('%Y', T1.Birthday) < 18
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER) < 18 AND STRFTIME('%Y', T2.`Examination Date`) BETWEEN '1990' AND '1993'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.ID) |
|---|
| 1 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 0 |

## 1175 / thrombosis_prediction / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query gets the examination year from `Laboratory.Date` and the diagnosis from `Patient.Diagnosis`; the prediction instead uses `Examination`.`Examination Date` and `Examination.Diagnosis`. These different source columns produce a different age and diagnosis.

Question:

```text
How old was the patient who had the highest hemoglobin count at the time of the examination, and what is the doctor's diagnosis?
```

Evidence:

```text
How old the patient refers to SUBTRACT(year(`Examination Date`), year(Birthday)); the highest hemoglobin count refers to MAX(HGB)
```

Gold SQL:

```sql
SELECT STRFTIME('%Y', T2.Date) - STRFTIME('%Y', T1.Birthday), T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID ORDER BY T2.HGB DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT CAST(STRFTIME('%Y', T3.`Examination Date`) AS INTEGER) - CAST(STRFTIME('%Y', T2.Birthday) AS INTEGER), T3.Diagnosis FROM Laboratory AS T1 INNER JOIN Patient AS T2 ON T1.ID = T2.ID INNER JOIN Examination AS T3 ON T2.ID = T3.ID ORDER BY T1.HGB DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| STRFTIME('%Y', T2.Date) - STRFTIME('%Y'… | Diagnosis |
|---|---|
| 28 | SLE |

Predicted (first 1 of 1 rows):

| CAST(STRFTIME('%Y', T3.`Examination Dat… | Diagnosis |
|---|---|
| 23 | SjS |

## 1179 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
For the patient who was diagnosed with SLE on 1994/2/19, what was his/her anti-Cardiolipin antibody concentration status on 1993/11/12?
```

Evidence:

```text
diagnosed with SLE refers to Diagnosis = 'SLE'; 1994/2/19 refers to Description = '1994-02-19'; anti-Cardiolipin refers to aCL IgM; 1993/11/12 refers to Examination Date = '1993/11/12'
```

Gold SQL:

```sql
SELECT `aCL IgA`, `aCL IgG`, `aCL IgM` FROM Examination WHERE ID IN ( SELECT ID FROM Patient WHERE Diagnosis = 'SLE' AND Description = '1994-02-19' ) AND `Examination Date` = '1993-11-12'
```

Predicted SQL:

```sql
SELECT T2.`aCL IgM` FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.Diagnosis = 'SLE' AND T1.Description = '1994-02-19' AND T2.`Examination Date` = '1993-11-12'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| aCL IgA | aCL IgG | aCL IgM |
|---|---|---|
| 3 | 5.1 | 4.1 |

Predicted (first 1 of 1 rows):

| aCL IgM |
|---|
| 4.1 |

## 1187 / thrombosis_prediction / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The predicted query returns an extra `COUNT(T1.ID)` column, while the gold query returns only distinct IDs. The ID rows themselves match.

Question:

```text
How many patients who were examined between 1987/7/6 and 1996/1/31 had a GPT level greater than 30 and an ALB level less than 4? List them by their ID.
```

Evidence:

```text
examined between 1987/7/6 and 1996/1/31 refers to Date BETWEEN '1987-07-06' AND '1996-01-31'; GPT level greater than 30 refers to GPT > 30; ALB level less than 4 ALB < 4
```

Gold SQL:

```sql
SELECT DISTINCT ID FROM Laboratory WHERE Date BETWEEN '1987-07-06' AND '1996-01-31' AND GPT > 30 AND ALB < 4
```

Predicted SQL:

```sql
SELECT T1.ID, COUNT(T1.ID) FROM Laboratory AS T1 WHERE T1.Date BETWEEN '1987-07-06' AND '1996-01-31' AND T1.GPT > 30 AND T1.ALB < 4 GROUP BY T1.ID
```

Result diff:

Gold 63 rows, predicted 63 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 63 rows):

| ID |
|---|
| 27654 |
| 71417 |
| 912147 |
| 944797 |
| 1078741 |

Predicted (first 5 of 63 rows):

| ID | COUNT(T1.ID) |
|---|---|
| 27654 | 5 |
| 71417 | 1 |
| 912147 | 6 |
| 944797 | 9 |
| 1078741 | 2 |

## 1189 / thrombosis_prediction / challenging

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The prediction filters on `ANA = 'S'`, while the gold query uses `ANA Pattern = 'S'`. It also omits the thrombosis and ANA conditions from the average subquery, but the column mismatch is the first difference to fix.

Question:

```text
What number of patients with a degree of thrombosis level 2 and ANA pattern of only S, have a level of anti-Cardiolip in antibody (IgM) 20% higher than average?
```

Evidence:

```text
thrombosis level 2 refers to Thrombosis = 2; ANA pattern of only S refers to ANA = 'S'; average anti-Cardiolip in antibody (IgM) refers to AVG(`aCL IgM`); calculation = MULTIPLY(AVG + AVG, 0.2)
```

Gold SQL:

```sql
SELECT COUNT(*) FROM Examination WHERE Thrombosis = 2 AND `ANA Pattern` = 'S' AND `aCL IgM` > (SELECT AVG(`aCL IgM`) * 1.2 FROM Examination WHERE Thrombosis = 2 AND `ANA Pattern` = 'S')
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Examination AS T1 WHERE T1.Thrombosis = 2 AND T1.ANA = 'S' AND T1.`aCL IgM` > (SELECT (AVG(T2.`aCL IgM`) + AVG(T2.`aCL IgM`)) * 0.2 FROM Examination AS T2)
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 1 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 0 |

## 1251 / thrombosis_prediction / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many patients with an Ig G higher than normal?
```

Evidence:

```text
Ig G higher than normal refers to IGG >= 2000; Should consider DISTINCT in the final result;
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID INNER JOIN Examination AS T3 ON T3.ID = T2.ID WHERE T2.IGG >= 2000
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Laboratory AS T1 WHERE T1.IGG >= 2000
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 9 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 136 |

## 1265 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many patients have a normal level of anti-ribonuclear protein and have been admitted to the hospital?
```

Evidence:

```text
normal level of anti-ribonuclear protein refers to RNP = '-', '+-'; And'-' means 'negative'; '+-' refers to '0'; admitted to the hospital refers to Admission = '+'; Should consider DISTINCT in the final result;
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.RNP = 'negative' OR T2.RNP = '0' AND T1.Admission = '+'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.RNP IN ('negative', '0') AND T1.Admission = '+'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 47 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 35 |

## 1404 / student_club / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Identify the type of expenses and their total value approved for 'October Meeting' event.
```

Evidence:

```text
total value refers to SUM(cost); 'October Meeting' is an event name;
```

Gold SQL:

```sql
SELECT T1.type, SUM(T3.cost) FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event INNER JOIN expense AS T3 ON T2.budget_id = T3.link_to_budget WHERE T1.event_name = 'October Meeting'
```

Predicted SQL:

```sql
SELECT T2.category, SUM(T1.cost) FROM expense AS T1 INNER JOIN budget AS T2 ON T1.link_to_budget = T2.budget_id INNER JOIN event AS T3 ON T2.link_to_event = T3.event_id WHERE T1.approved = 'true' AND T3.event_name = 'October Meeting' GROUP BY T2.category
```

Result diff:

Gold 1 rows, predicted 2 rows. Within the previews: 1 rows only in gold, 2 only in predicted.

Gold (first 1 of 1 rows):

| type | SUM(T3.cost) |
|---|---|
| Meeting | 175.39 |

Predicted (first 2 of 2 rows):

| category | SUM(T1.cost) |
|---|---|
| Advertisement | 54.25 |
| Food | 121.14 |

## 1481 / debit_card_specializing / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What is the difference in the annual average consumption of the customers with the least amount of consumption paid in CZK for 2013 between SME and LAM, LAM and KAM, and KAM and SME?
```

Evidence:

```text
annual average consumption of customer with the lowest consumption in each segment = total consumption per year / the number of customer with lowest consumption in each segment; Difference in annual average = SME's annual average - LAM's annual average; Difference in annual average = LAM's annual average - KAM's annual average; Year 2013 can be presented as Between 201301 And 201312; The first 4 strings of the Date values in the yearmonth table can represent year.
```

Gold SQL:

```sql
SELECT CAST(SUM(IIF(T1.Segment = 'SME', T2.Consumption, 0)) AS REAL) / COUNT(T1.CustomerID) - CAST(SUM(IIF(T1.Segment = 'LAM', T2.Consumption, 0)) AS REAL) / COUNT(T1.CustomerID) , CAST(SUM(IIF(T1.Segment = 'LAM', T2.Consumption, 0)) AS REAL) / COUNT(T1.CustomerID) - CAST(SUM(IIF(T1.Segment = 'KAM', T2.Consumption, 0)) AS REAL) / COUNT(T1.CustomerID) , CAST(SUM(IIF(T1.Segment = 'KAM', T2.Consumption, 0)) AS REAL) / COUNT(T1.CustomerID) - CAST(SUM(IIF(T1.Segment = 'SME', T2.Consumption, 0)) AS REAL) / COUNT(T1.CustomerID) FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Currency = 'CZK' AND T2.Consumption = ( SELECT MIN(Consumption) FROM yearmonth ) AND T2.Date BETWEEN 201301 AND 201312
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.CustomerID, T1.Segment, SUM(T2.Consumption) AS c1 FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Currency = 'CZK' AND T2.Date BETWEEN '201301' AND '201312' GROUP BY T1.CustomerID, T1.Segment), cte2 AS (SELECT T1.Segment, MIN(T1.c1) AS c2 FROM cte1 AS T1 WHERE T1.c1 IS NOT NULL GROUP BY T1.Segment), cte3 AS (SELECT T1.Segment, CAST(SUM(T1.c1) AS REAL) / COUNT(T1.CustomerID) AS c3 FROM cte1 AS T1 INNER JOIN cte2 AS T2 ON T1.Segment = T2.Segment AND T1.c1 = T2.c2 GROUP BY T1.Segment) SELECT T1.c3 - T2.c3, T2.c3 - T3.c3, T3.c3 - T1.c3 FROM cte3 AS T1 INNER JOIN cte3 AS T2 ON T2.Segment = 'LAM' INNER JOIN cte3 AS T3 ON T3.Segment = 'KAM' WHERE T1.Segment = 'SME'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(T1.Segment = 'SME', T2.Con… | CAST(SUM(IIF(T1.Segment = 'LAM', T2.Con… | CAST(SUM(IIF(T1.Segment = 'KAM', T2.Con… |
|---|---|---|
| 0.0 | 582092.86 | -582092.86 |

Predicted (first 1 of 1 rows):

| T1.c3 - T2.c3 | T2.c3 - T3.c3 | T3.c3 - T1.c3 |
|---|---|---|
| -14009.339999999998 | 6046.619999999999 | 7962.719999999999 |

## 1524 / debit_card_specializing / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query filters on `T1.Price = 548.4`, while the prediction uses `T1.Amount * T1.Price = 548.4`. The prediction therefore uses a different column expression to represent the requested spend.

Question:

```text
What's the nationality of the customer who spent 548.4 in 2012/8/24?
```

Evidence:

```text
'2012/8/24' can be represented by '2012-08-24'
```

Gold SQL:

```sql
SELECT T2.Country FROM transactions_1k AS T1 INNER JOIN gasstations AS T2 ON T1.GasStationID = T2.GasStationID WHERE T1.Date = '2012-08-24' AND T1.Price  = 548.4
```

Predicted SQL:

```sql
SELECT DISTINCT T2.Country FROM transactions_1k AS T1 INNER JOIN gasstations AS T2 ON T1.GasStationID = T2.GasStationID WHERE T1.Amount * T1.Price = 548.4 AND T1.Date = '2012-08-24'
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| Country |
|---|
| CZE |

Predicted (first 0 of 0 rows):

| Country |
|---|
