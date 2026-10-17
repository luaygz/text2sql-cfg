# Failures: best on bird_arcwise / dev

79 of 349 questions failed. Evidence off, git `9e6058ba110908fba8be69f59edf24a618ad2e41-dirty`, complete: 349 questions.

## 11 / california_schools / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query uses FRPM enrollment columns, summing “Enrollment (K-12)” and “Enrollment (Ages 5-17),” while the prediction reads `enroll12` from `satscores`. This uses a different table and enrollment measure.

Question:

```text
Please list the codes of the schools with a total enrollment of over 500.
```

Evidence:

```text
Total enrollment can be represented by "Enrollment (K-12)" + "Enrollment (Ages 5-17)"
```

Gold SQL:

```sql
SELECT T2.CDSCode
FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode 
WHERE T2."Enrollment (K-12)" + T2."Enrollment (Ages 5-17)" > 500
AND School is  not NULL
```

Predicted SQL:

```sql
SELECT T1.cds FROM satscores AS T1 WHERE T1.enroll12 > 500
```

Result diff:

Gold 7804 rows, predicted 534 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 7804 rows):

| CDSCode |
|---|
| 01100170109835 |
| 01100170112607 |
| 01100170124172 |
| 01100170125567 |
| 01100176001788 |

Predicted (first 5 of 534 rows):

| cds |
|---|
| 1611190000000 |
| 1611430000000 |
| 1611430131177 |
| 1611500000000 |
| 1611500132225 |

## 17 / california_schools / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s conditions `CharterNum is not null` and `rtype = 'S'`, producing 430 rows instead of 50. Its rank subquery also ranks across scores without those filters, but the missing row-filter conditions are the first difference to fix.

Question:

```text
Rank schools by their average score in Writing where the score is greater than 499, showing their charter numbers, average score, and rank.
```

Evidence:

```text
Valid charter number means the number is not null
```

Gold SQL:

```sql
SELECT CharterNum, AvgScrWrite, 
RANK() OVER (ORDER BY AvgScrWrite DESC) AS WritingScoreRank 
FROM schools AS T1  INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds 
WHERE T2.AvgScrWrite > 499 AND CharterNum is not null AND rtype = 'S'
```

Predicted SQL:

```sql
SELECT T1.CharterNum, T2.AvgScrWrite, (SELECT COUNT(*) + 1 FROM satscores AS T3 INNER JOIN schools AS T4 ON T3.cds = T4.CDSCode WHERE T3.AvgScrWrite > T2.AvgScrWrite) AS c1 FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T2.AvgScrWrite > 499 ORDER BY T2.AvgScrWrite DESC
```

Result diff:

Gold 50 rows, predicted 430 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 50 rows):

| CharterNum | AvgScrWrite | WritingScoreRank |
|---|---|---|
| 0210 | 630 | 1 |
| 0890 | 593 | 2 |
| 0290 | 582 | 3 |
| 0930 | 579 | 4 |
| 1169 | 576 | 5 |

Predicted (first 5 of 430 rows):

| CharterNum | AvgScrWrite | c1 |
|---|---|---|
| None | 664 | 1 |
| None | 661 | 2 |
| None | 657 | 3 |
| None | 650 | 4 |
| None | 646 | 5 |

## 23 / california_schools / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction uses ABS on the enrollment difference, so it includes schools whose K-12 enrollment is more than 30 lower than ages 5–17; the gold query requires the signed difference (K-12 minus ages 5–17) to exceed 30. It also omits the gold query’s non-NULL school-name condition.

Question:

```text
List the names of schools with more than 30 difference in enrollements between K-12 and ages 5-17? Please also give the full street adress of the schools.
```

Evidence:

```text
Diffrence in enrollement = "Enrollment (K-12)" - "Enrollment (Ages 5-17)", school name = "School"
```

Gold SQL:

```sql
SELECT T1.School, T1.Street FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2."Enrollment (K-12)" - T2."Enrollment (Ages 5-17)" > 30 AND T1.School is not NULL
```

Predicted SQL:

```sql
SELECT T1.School, T1.Street FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE ABS(T2.`Enrollment (K-12)` - T2.`Enrollment (Ages 5-17)`) > 30
```

Result diff:

Gold 1236 rows, predicted 1239 rows. Within the previews: 0 rows only in gold, 0 only in predicted.

Gold (first 5 of 1236 rows):

| School | Street |
|---|---|
| Alameda County Community | 313 West Winton Avenue |
| California School for the Deaf-Fremont | 39350 Gallaudet Drive |
| Alameda High | 2201 Encinal Avenue |
| Encinal High | 210 Central Avenue |
| Island High (Continuation) | 1900 Third Street |

Predicted (first 5 of 1239 rows):

| School | Street |
|---|---|
| Alameda County Community | 313 West Winton Avenue |
| California School for the Deaf-Fremont | 39350 Gallaudet Drive |
| Alameda High | 2201 Encinal Avenue |
| Encinal High | 210 Central Avenue |
| Island High (Continuation) | 1900 Third Street |

## 25 / california_schools / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The prediction filters on `schools.County`, while the gold query uses `schools.District` for Riverside. It also omits the gold `rtype = 'S'` condition, but the wrong filter column is the first difference to fix.

Question:

```text
Name schools in Riverside which the average of average math score for SAT is greater than 400, along with the funding type of these schools?
```

Evidence:

```text
Average of average math = sum(average math scores) / count(schools), in Riverside refers to "District Name" LIKE 'Riverside%'
```

Gold SQL:

```sql
SELECT s.`sname`,
       sc.`FundingType`
FROM satscores AS s
JOIN schools  AS sc
  ON s.`cds` = sc.`CDSCode`
WHERE sc.`District` LIKE 'Riverside%'   AND s.rtype = 'S'
GROUP BY s.`sname`, sc.`FundingType`
HAVING AVG(s.`AvgScrMath`) > 400;
```

Predicted SQL:

```sql
SELECT T1.School, T1.FundingType FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.County = 'Riverside' GROUP BY T1.CDSCode, T1.School, T1.FundingType HAVING AVG(T2.AvgScrMath) > 400
```

Result diff:

Gold 6 rows, predicted 80 rows. Within the previews: 5 rows only in gold, 4 only in predicted.

Gold (first 5 of 6 rows):

| sname | FundingType |
|---|---|
| Arlington High | None |
| John W. North High | None |
| Martin Luther King Jr. High | None |
| Polytechnic High | None |
| Ramona High | None |

Predicted (first 5 of 80 rows):

| School | FundingType |
|---|---|
| None | None |
| River Springs Charter | Directly funded |
| None | None |
| La Sierra High | None |
| Norte Vista High | None |

## 26 / california_schools / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The prediction uses `schools.School`, `MailStreet`, `MailCity`, `MailState`, and `MailZip`, whereas the gold query selects the school name from `frpm` and the address fields `Street`, `City`, `State`, and `Zip` from `schools`. These different columns account for the mismatch.

Question:

```text
State the names and full communication address of high schools in Monterey which has more than 800 free or reduced price meals for ages 15-17?
```

Evidence:

```text
Full communication address should include Street, City, State and zip code if any.
```

Gold SQL:

```sql
SELECT T1."School Name", T2.Street, T2.City, T2.State, T2.Zip
FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode 
WHERE T2.County = 'Monterey' AND T1."FRPM Count (Ages 5-17)" > 800 AND T1."School Type" = 'High Schools (Public)' AND T2.School is not NULL
```

Predicted SQL:

```sql
SELECT T1.School, T1.MailStreet, T1.MailCity, T1.MailState, T1.MailZip FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.`County Name` = 'Monterey' AND T2.`School Type` = 'High Schools (Public)' AND T2.`FRPM Count (Ages 5-17)` > 800 / IIF(1, 1, 1) = 1 ORDER BY T1.School LIMIT 1000 OFFSET 04387
```

Result diff:

Gold 6 rows, predicted 0 rows. Within the previews: 5 rows only in gold, 0 only in predicted.

Gold (first 5 of 6 rows):

| School Name | Street | City | State | Zip |
|---|---|---|---|---|
| Alisal High | 777 Williams Road | Salinas | CA | 93905-1907 |
| Everett Alvarez High | 1900 Independence Boulevard | Salinas | CA | 93906-5300 |
| North Salinas High | 55 Kip Drive | Salinas | CA | 93906-2908 |
| Salinas High | 726 South Main Street | Salinas | CA | 93901-3243 |
| North Monterey County High | 13990 Castroville Boulevard | Castroville | CA | 95012-9749 |

Predicted (first 0 of 0 rows):

| School | MailStreet | MailCity | MailState | MailZip |
|---|---|---|---|---|

## 27 / california_schools / moderate

Label: `wrong_join_path` (classifier, gpt-6-luna): The predicted query uses an INNER JOIN, while the gold query uses a LEFT JOIN from schools to SAT scores. The INNER JOIN excludes qualifying schools without a matching SAT-score row.

Question:

```text
Give the names and average scores in writing for the schools that were opened after 1991 or closed before 2000? Also, list the communication number of the schools if there is any.
```

Evidence:

```text
Communication number refers to phone number.
```

Gold SQL:

```sql
SELECT T2.School, T1.AvgScrWrite, T2.Phone FROM schools AS T2 LEFT JOIN satscores AS T1 ON T2.CDSCode = T1.cds WHERE strftime('%Y', T2.OpenDate) > '1991' OR strftime('%Y', T2.ClosedDate) < '2000'
```

Predicted SQL:

```sql
SELECT T1.School, T2.AvgScrWrite, T1.Phone FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE STRFTIME('%Y', T1.OpenDate) > '1991' OR STRFTIME('%Y', T1.ClosedDate) < '2000'
```

Result diff:

Gold 8574 rows, predicted 749 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 8574 rows):

| School | AvgScrWrite | Phone |
|---|---|---|
| FAME Public Charter | None | None |
| Envision Academy for Arts & Technology | None | (510) 596-8901 |
| Aspire California College Preparatory A… | None | None |
| Community School for Creative Education | None | (510) 686-4131 |
| Yu Ming Charter | None | (510) 452-2063 |

Predicted (first 5 of 749 rows):

| School | AvgScrWrite | Phone |
|---|---|---|
| Crescent View West Charter | None | (559) 222-8439 |
| Hume Lake Charter | None | (559) 305-7565 |
| Big Picture Educational Academy | None | (559) 420-1234 |
| Clovis North High | 519 | (559) 327-5000 |
| Clovis Online Charter | None | (559) 327-4400 |

## 36 / california_schools / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query restricts SAT records to `t.rtype = 'S'`, but the prediction omits that filter, changing which school ranks first. The prediction also returns only the first administrator’s name rather than all three administrator name pairs.

Question:

```text
Under whose administration is the school with the highest number of students scoring 1500 or more on the SAT? Indicate their full names.
```

Evidence:

```text
full name means first name, last name; There are at most 3 administrators for each school; SAT Scores are greater or equal to 1500 refers to NumGE1500
```

Gold SQL:

```sql
SELECT s.AdmFName1,
       s.AdmLName1,
       s.AdmFName2,
       s.AdmLName2,
       s.AdmFName3,
       s.AdmLName3
FROM satscores t
JOIN schools  s ON t.cds = s.CDSCode
WHERE t.rtype = 'S'    
ORDER BY t.NumGE1500 DESC
LIMIT 1;
```

Predicted SQL:

```sql
SELECT T1.AdmFName1, T1.AdmLName1 FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds ORDER BY T2.NumGE1500 DESC LIMIT 1 OFFSET 0
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AdmFName1 | AdmLName1 | AdmFName2 | AdmLName2 | AdmFName3 | AdmLName3 |
|---|---|---|---|---|---|
| Andrew | Ishibashi | None | None | None | None |

Predicted (first 1 of 1 rows):

| AdmFName1 | AdmLName1 |
|---|---|
| Michelle | King |

## 48 / california_schools / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction applies `County = 'Orange'` to both sides of the ratio, while the gold query restricts Orange County only for the Unified numerator and counts merged Elementary schools across all counties in the denominator.

Question:

```text
What is the ratio of merged Unified School District schools in Orange County to merged Elementary School District schools?
```

Evidence:

```text
Elementary School District refers to DOC = 52; Unified School District refers to DOC = 54.
```

Gold SQL:

```sql
SELECT CAST((
SELECT COUNT(*) FROM schools 
WHERE County = 'Orange' AND DOC = '54' AND StatusType = 'Merged' AND school is not null) AS REAL) 
/ (SELECT COUNT(*) FROM schools WHERE DOC = '52' AND StatusType = 'Merged' AND school is not null) AS ratio;
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.DOCType = 'Unified School District' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN T1.DOCType = 'Elementary School District' THEN 1 ELSE 0 END) FROM schools AS T1 WHERE T1.StatusType = 'Merged' AND T1.County = 'Orange' AND T1.DOCType IN ('Unified School District', 'Elementary School District')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| ratio |
|---|
| 0.010958904109589041 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.DOCType = 'Unifie… |
|---|
| 0.5714285714285714 |

## 50 / california_schools / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters to school-level records (`rtype = 'S'`) and non-NULL Math averages, but the prediction omits both conditions. That changes which rows are ranked, yielding a different school.

Question:

```text
What is the postal street address for the school with the 7th highest Math average? Indicate the school's name.
```

Evidence:

```text
Postal street and mailing street are synonyms.
```

Gold SQL:

```sql
SELECT s.`MailStreet`   AS postal_street_address,
       s.`School`
FROM   `satscores` AS ss
JOIN   `schools`   AS s
       ON ss.`cds` = s.`CDSCode`
WHERE  ss.`rtype` = 'S'
  AND  ss.`AvgScrMath` IS NOT NULL
ORDER BY ss.`AvgScrMath` DESC
LIMIT 6, 1;
```

Predicted SQL:

```sql
SELECT T1.MailStreet, T1.School FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds ORDER BY T2.AvgScrMath DESC LIMIT 1 OFFSET 6
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| postal_street_address | School |
|---|---|
| 4771 Campus Drive | University High |

Predicted (first 1 of 1 rows):

| MailStreet | School |
|---|---|
| 5172 Orange Avenue | Oxford Academy |

## 82 / california_schools / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query ranks schools by ABS(longitude), while the prediction ranks by raw longitude. The evidence specifies maximum absolute longitude, so the ordering logic differs.

Question:

```text
What is the grade span offered in the school with the highest longitude?
```

Evidence:

```text
the highest longitude refers to the school with the maximum absolute longitude value.
```

Gold SQL:

```sql
SELECT GSoffered FROM schools ORDER BY ABS(longitude) DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.GSoffered FROM schools AS T1 ORDER BY T1.Longitude DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| GSoffered |
|---|
| K-8 |

Predicted (first 1 of 1 rows):

| GSoffered |
|---|
| Adult |

## 85 / california_schools / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query calculates the percentage from Free Meal Count and Enrollment, while the prediction selects the existing Percent (%) Eligible Free (K-12) column, yielding 0.7015 instead of 70.1511. The prediction also broadens the administrator-name filter, but the percentage-column difference is the first issue to fix.

Question:

```text
What is the Percent (%) Eligible Free (K-12) in the school administered by an administrator whose first name is Alusine. List the district code of the school.
```

Evidence:

```text
Percent (%) Eligible Free (K-12) = "Free Meal Count (K-12)" / "Enrollment (K-12)" * 100%
```

Gold SQL:

```sql
SELECT T1."Free Meal Count (K-12)" * 100 / T1."Enrollment (K-12)", T1."District Code" FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.AdmFName1 = 'Alusine'
```

Predicted SQL:

```sql
SELECT T1.`Percent (%) Eligible Free (K-12)`, T1.`District Code` FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.AdmFName1 = 'Alusine' OR T2.AdmFName2 = 'Alusine' OR T2.AdmFName3 = 'Alusine'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| T1."Free Meal Count (K-12)" * 100 / T1.… | District Code |
|---|---|
| 70.15113350125945 | 64857 |

Predicted (first 1 of 1 rows):

| Percent (%) Eligible Free (K-12) | District Code |
|---|---|
| 0.701511335012594 | 64857 |

## 125 / financial / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s filters requiring A12 and A13 to be non-NULL and A12 to be greater than zero, so it can return extra rows.

Question:

```text
For loans contracts which are still running where client are in debt, state their district percentage unemployment rate increment from year 1995 to 1996.
```

Evidence:

```text
Unemployment increment rate in percentage = [(unemployment rate 1996 - unemployment rate 1995) / unemployment rate 1995] * 100; unemployment rate 1995 appears in the A12; unemployment rate 1996 appears in the A13; Loan contracts which are still running where client are in debt can be presented as status = 'D'
```

Gold SQL:

```sql
SELECT (d.A13 - d.A12) / d.A12 * 100 FROM loan AS l JOIN account AS a ON l.account_id = a.account_id JOIN district AS d ON a.district_id = d.district_id WHERE l.status = 'D' AND NOT d.A12 IS NULL AND NOT d.A13 IS NULL AND d.A12 > 0
```

Predicted SQL:

```sql
SELECT CAST(T3.A13 - T3.A12 AS REAL) * 100 / T3.A12 FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.status = 'D'
```

Result diff:

Gold 43 rows, predicted 45 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 5 of 43 rows):

| (d.A13 - d.A12) / d.A12 * 100 |
|---|
| 40.0 |
| 39.259259259259245 |
| 114.99999999999999 |
| 22.499999999999993 |
| 20.0 |

Predicted (first 5 of 45 rows):

| CAST(T3.A13 - T3.A12 AS REAL) * 100 / T… |
|---|
| 40.0 |
| 39.25925925925924 |
| 115.0 |
| 22.49999999999999 |
| 20.0 |

## 128 / financial / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The ranking logic and female-client filtering match, but the gold query returns only district A2 while the prediction also selects the client count c1.

Question:

```text
List the top nine districts by number of female clients, in descending order.
```

Evidence:

```text
districts refers to A2; Female refers to gender = 'F'
```

Gold SQL:

```sql
SELECT T2.A2 FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.gender = 'F' GROUP BY T2.district_id, T2.A2 ORDER BY COUNT(T1.client_id) DESC LIMIT 9
```

Predicted SQL:

```sql
SELECT T1.A2, COUNT(T2.client_id) AS c1 FROM district AS T1 INNER JOIN client AS T2 ON T1.district_id = T2.district_id WHERE T2.gender = 'F' GROUP BY T1.district_id, T1.A2 ORDER BY c1 DESC LIMIT 9
```

Result diff:

Gold 9 rows, predicted 9 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 9 rows):

| A2 |
|---|
| Hl.m. Praha |
| Karvina |
| Ostrava - mesto |
| Brno - mesto |
| Zlin |

Predicted (first 5 of 9 rows):

| A2 | c1 |
|---|---|
| Hl.m. Praha | 324 |
| Karvina | 88 |
| Ostrava - mesto | 84 |
| Brno - mesto | 75 |
| Zlin | 57 |

## 145 / financial / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query returns `trans.account_id`, while the prediction returns `disp.client_id` for owner records. The prediction also omits the 1998 filter from the average subquery, but the identifier-column mismatch is the first difference to fix.

Question:

```text
Who are the account holder identification numbers whose who have transactions on the credit card with the amount is less than the overall average, in 1998?
```

Evidence:

```text
Operation = 'VYBER KARTOU' refers to credit card withdrawal; the average refers to AVG(amount) WHERE STRFTIME('%Y', date) = '1998'
```

Gold SQL:

```sql
SELECT T1.account_id FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE STRFTIME('%Y', T1.date) = '1998' AND T1.operation = 'VYBER KARTOU' AND T1.amount < (SELECT AVG(amount) FROM trans WHERE STRFTIME('%Y', date) = '1998')
```

Predicted SQL:

```sql
SELECT DISTINCT T1.client_id FROM disp AS T1 INNER JOIN trans AS T2 ON T1.account_id = T2.account_id WHERE T1.type = 'OWNER' AND T2.operation = 'VYBER KARTOU' AND T2.amount < (SELECT AVG(T3.amount) FROM trans AS T3) AND STRFTIME('%Y', T2.date) = '1998'
```

Result diff:

Gold 4484 rows, predicted 800 rows. Within the previews: 1 rows only in gold, 5 only in predicted.

Gold (first 5 of 4484 rows):

| account_id |
|---|
| 14 |
| 14 |
| 14 |
| 14 |
| 14 |

Predicted (first 5 of 800 rows):

| client_id |
|---|
| 9 |
| 19 |
| 41 |
| 42 |
| 51 |

## 197 / toxicology / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query sums the oxygen-indicator value for every atom row, while the prediction counts distinct `atom_id` values. Deduplicating atom IDs can change the per-molecule oxygen count and therefore the average.

Question:

```text
Calculate the average number of oxygen atoms in single-bonded molecules.
```

Evidence:

```text
single-bonded molecules refers to bond_type = '-' ; average number of oxygen atom = AVG(SUM(element = 'o'))
```

Gold SQL:

```sql
WITH oxygen_atoms_per_molecule AS (SELECT atom.molecule_id, SUM(atom.element = 'o') AS oxygen_count FROM atom GROUP BY atom.molecule_id), single_bond_molecules AS (SELECT DISTINCT bond.molecule_id FROM bond WHERE bond.bond_type = '-') SELECT AVG(oxygen_atoms_per_molecule.oxygen_count) AS average_oxygen_atoms FROM single_bond_molecules JOIN oxygen_atoms_per_molecule ON single_bond_molecules.molecule_id = oxygen_atoms_per_molecule.molecule_id
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.molecule_id, COUNT(DISTINCT T3.atom_id) AS c1 FROM molecule AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id LEFT JOIN atom AS T3 ON T1.molecule_id = T3.molecule_id AND T3.element = 'o' WHERE T2.bond_type = '-' GROUP BY T1.molecule_id) SELECT AVG(T1.c1) FROM cte1 AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| average_oxygen_atoms |
|---|
| 2.3597285067873304 |

Predicted (first 1 of 1 rows):

| AVG(T1.c1) |
|---|
| 2.161290322580645 |

## 212 / toxicology / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every element tied for the minimum count, while the prediction orders by count and uses `LIMIT 1`, returning only one element.

Question:

```text
Which element is the least numerous in non-carcinogenic molecules?
```

Evidence:

```text
label = '-' means molecules are non-carcinogenic; least numerous refers to MIN(COUNT(element));
```

Gold SQL:

```sql
SELECT `a`.`element`
FROM `atom` AS `a`
JOIN `molecule` AS `m`  ON `a`.`molecule_id` = `m`.`molecule_id`
WHERE `m`.`label` = '-'
GROUP BY `a`.`element`
HAVING COUNT(*) = (
    SELECT MIN(cnt)
    FROM (
        SELECT COUNT(*) AS cnt
        FROM `atom` AS `a2`
        JOIN `molecule` AS `m2` ON `a2`.`molecule_id` = `m2`.`molecule_id`
        WHERE `m2`.`label` = '-'
        GROUP BY `a2`.`element`
    )
);
```

Predicted SQL:

```sql
SELECT T1.element FROM atom AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.label = '-' AND T1.element IS NOT NULL GROUP BY T1.element ORDER BY COUNT(T1.atom_id) ASC LIMIT 1
```

Result diff:

Gold 3 rows, predicted 1 rows. Within the previews: 2 rows only in gold, 0 only in predicted.

Gold (first 3 of 3 rows):

| element |
|---|
| ca |
| k |
| pb |

Predicted (first 1 of 1 rows):

| element |
|---|
| ca |

## 218 / toxicology / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction filters for `T1.label = '+281?Wrong?Oops?'` instead of the carcinogenic label `+` used by the gold query. This prevents it from selecting the intended molecules and yields `NULL`.

Question:

```text
What percentage of carcinogenic-type molecules does not contain fluorine?
```

Evidence:

```text
label = '+' mean molecules are carcinogenic; contain fluorine refers to element = 'f'; percentage = DIVIDE(SUM(element = 'f') * 100, COUNT(molecule_id)) where label = '+'; Should consider the distinct atoms when counting;
```

Gold SQL:

```sql
SELECT 100 - CAST(COUNT(DISTINCT CASE WHEN T1.element = 'f' THEN T2.molecule_id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT T2.molecule_id) FROM atom AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.label = '+'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN NOT EXISTS(SELECT T2.atom_id FROM atom AS T2 WHERE T2.molecule_id = T1.molecule_id AND T2.element = 'f') THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM molecule AS T1 WHERE T1.label = '+281?Wrong?Oops?'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| 100 - CAST(COUNT(DISTINCT CASE WHEN T1.… |
|---|
| 99.34210526315789 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN NOT EXISTS(SELECT T2… |
|---|
| None |

## 242 / toxicology / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query selects molecules with at least one atom whose ID suffix is between '21' and '25', then uses DISTINCT. The prediction instead groups by molecule and requires the total atom count to be between 21 and 25.

Question:

```text
Among all the atoms from 21 to 25, list all the molecules that are carcinogenic.
```

Evidence:

```text
atoms from 21 to 25 refers to SUBSTR(atom_id, 7, 2) between '21' and '25'; label = '+' mean molecules are carcinogenic
```

Gold SQL:

```sql
SELECT DISTINCT T2.molecule_id FROM atom AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE SUBSTR(T1.atom_id, -2) BETWEEN '21' AND '25' AND T2.label = '+'
```

Predicted SQL:

```sql
SELECT T1.molecule_id FROM molecule AS T1 INNER JOIN atom AS T2 ON T1.molecule_id = T2.molecule_id WHERE T1.label = '+' GROUP BY T1.molecule_id HAVING COUNT(T2.atom_id) BETWEEN 21 AND 25
```

Result diff:

Gold 75 rows, predicted 22 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 5 of 75 rows):

| molecule_id |
|---|
| TR001 |
| TR006 |
| TR019 |
| TR020 |
| TR029 |

Predicted (first 5 of 22 rows):

| molecule_id |
|---|
| TR001 |
| TR058 |
| TR105 |
| TR118 |
| TR142 |

## 248 / toxicology / simple

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction selects both `atom_id` and `atom_id2`, while the gold query returns only distinct `atom_id` values. The bond and molecule filters match.

Question:

```text
List all the atom IDs of the triple bonds in molecule "TR041"?
```

Evidence:

```text
TR041 is the molecule id; triple bond refers to bond_type = '#';
```

Gold SQL:

```sql
SELECT DISTINCT T2.atom_id FROM atom AS T1 INNER JOIN connected AS T2 ON T1.atom_id = T2.atom_id INNER JOIN bond AS T3 ON T2.bond_id = T3.bond_id WHERE T3.bond_type = '#' AND T3.molecule_id = 'TR041'
```

Predicted SQL:

```sql
SELECT T2.atom_id, T2.atom_id2 FROM bond AS T1 INNER JOIN connected AS T2 ON T1.bond_id = T2.bond_id WHERE T1.bond_type = '#' AND T1.molecule_id = 'TR041'
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 4 of 4 rows):

| atom_id |
|---|
| TR041_10 |
| TR041_7 |
| TR041_8 |
| TR041_9 |

Predicted (first 4 of 4 rows):

| atom_id | atom_id2 |
|---|---|
| TR041_10 | TR041_7 |
| TR041_7 | TR041_10 |
| TR041_8 | TR041_9 |
| TR041_9 | TR041_8 |

## 260 / toxicology / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query counts every atom in molecules that contain a phosphorus or bromine atom, while the prediction filters the counted atoms themselves to element 'p' or 'br'. Thus it excludes other atoms in qualifying molecules.

Question:

```text
Calculate the total atoms with triple-bond molecules containing the element phosphorus or bromine.
```

Evidence:

```text
triple bond refers to bond_type = '#'; phosphorus refers to element = 'p'; bromine refers to element = 'br'
```

Gold SQL:

```sql
SELECT COUNT(*) FROM atom WHERE molecule_id IN ( SELECT DISTINCT molecule_id FROM bond WHERE bond_type = '#' ) AND molecule_id IN ( SELECT DISTINCT molecule_id FROM atom WHERE element IN ('p', 'br') )
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.atom_id) FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.bond_type = '#' AND T1.element IN ('p', 'br')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 4 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.atom_id) |
|---|
| 1 |

## 263 / toxicology / challenging

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction joins each atom directly to every matching bond, potentially duplicating atoms for molecules with multiple single bonds. The gold query uses the bond table only to select distinct molecule IDs, so each atom is counted once.

Question:

```text
What is the composition of element chlorine in percentage among the single bond molecules?
```

Evidence:

```text
element chlorine refers to element = 'cl'; single bond refers to bond_type = '-'; percentage = DIVIDE(SUM(element = 'cl'), COUNT(atom_id)) as percent where bond_type = '-'
```

Gold SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T.element = 'cl' THEN T.atom_id ELSE NULL END) AS REAL) * 100 / COUNT(T.atom_id) FROM atom AS T WHERE molecule_id IN (SELECT DISTINCT molecule.molecule_id FROM molecule JOIN bond ON molecule.molecule_id = bond.molecule_id AND bond.bond_type = '-')
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.element = 'cl' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.bond_type = '-'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T.element = 'cl' T… |
|---|
| 3.4823684499615513 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.element = 'cl' TH… |
|---|
| 2.319276287704702 |

## 268 / toxicology / challenging

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The gold query returns one element column for each connected atom, while the prediction adds a second element column from the other bond endpoint. The predicted rows therefore have two columns instead of the gold query’s one.

Question:

```text
What are the elements for bond id TR001_10_11?
```

Evidence:

```text
TR001_10_11 is the bond id;
```

Gold SQL:

```sql
SELECT T2.element FROM connected AS T1 INNER JOIN atom AS T2 ON T1.atom_id = T2.atom_id WHERE T1.bond_id = 'TR001_10_11'
```

Predicted SQL:

```sql
SELECT T2.element, T3.element FROM connected AS T1 INNER JOIN atom AS T2 ON T1.atom_id = T2.atom_id INNER JOIN atom AS T3 ON T1.atom_id2 = T3.atom_id WHERE T1.bond_id = 'TR001_10_11'
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| element |
|---|
| c |
| o |

Predicted (first 2 of 2 rows):

| element | element |
|---|---|
| c | o |
| o | c |

## 341 / card_games / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query includes cards where either foil ID or regular card ID is NULL. The prediction instead requires foil ID to be NULL and regular card ID to be non-NULL, excluding cases where both are NULL.

Question:

```text
What are the borderless card ids available without powerful foils?
```

Evidence:

```text
borderless' refers to borderColor; powerful foils refers to cardKingdomFoilId paired with cardKingdomId are not null
```

Gold SQL:

```sql
SELECT id FROM cards WHERE borderColor = 'borderless' AND (cardKingdomFoilId IS NULL OR cardKingdomId IS NULL)
```

Predicted SQL:

```sql
SELECT T1.id FROM cards AS T1 WHERE T1.borderColor = 'borderless' AND T1.cardKingdomFoilId IS NULL AND T1.cardKingdomId IS NOT NULL
```

Result diff:

Gold 72 rows, predicted 5 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 72 rows):

| id |
|---|
| 23004 |
| 25350 |
| 25355 |
| 25357 |
| 25359 |

Predicted (first 5 of 5 rows):

| id |
|---|
| 48333 |
| 48334 |
| 48335 |
| 48336 |
| 48337 |

## 347 / card_games / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The predicted query filters for artist = 'Stephen Daniel', but the evidence and gold query use 'Stephen Daniele'. This incorrect literal causes the prediction to return no rows.

Question:

```text
Find all cards illustrated by Stephen Daniel and describe the text of the ruling of these cards. State if these cards have missing or degraded properties and values.
```

Evidence:

```text
cards have missing or degraded properties and value refers to hasContentWarning = 1; 'Stephen Daniele' is artist; Find all cards refers to return card id
```

Gold SQL:

```sql
SELECT T1.id, T2.text, T1.hasContentWarning FROM cards AS T1 LEFT JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE T1.artist = 'Stephen Daniele'
```

Predicted SQL:

```sql
SELECT T1.name, T2.text, T1.hasContentWarning FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE T1.artist = 'Stephen Daniel'
```

Result diff:

Gold 76 rows, predicted 0 rows. Within the previews: 5 rows only in gold, 0 only in predicted.

Gold (first 5 of 76 rows):

| id | text | hasContentWarning |
|---|---|---|
| 29 | You can’t put an Aura card from your ha… | 0 |
| 211 | None | 0 |
| 274 | None | 0 |
| 275 | None | 0 |
| 3872 | This card now has Enchant Swamp, which … | 0 |

Predicted (first 0 of 0 rows):

| name | text | hasContentWarning |
|---|---|---|

## 349 / card_games / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every card printing tied for the maximum ruling count, while the prediction groups by UUID and uses `LIMIT 1`, so it returns only one arbitrary printing and omits the non-promotional row.

Question:

```text
Name the card with the most ruling information and its artist. Also state if the card is a promotional printing.
```

Evidence:

```text
with the most ruling information refers to Max(count(rulings.uuid)); the card is the promotional printing refers to isPromo = 1;
```

Gold SQL:

```sql
SELECT DISTINCT c.name, c.artist, c.isPromo FROM cards c INNER JOIN (SELECT uuid FROM rulings GROUP BY uuid HAVING COUNT(id) = ( SELECT MAX(ruling_count) FROM ( SELECT COUNT(id) as ruling_count FROM rulings GROUP BY uuid ) ) ) AS max_rulings ON c.uuid = max_rulings.uuid;
```

Predicted SQL:

```sql
SELECT T1.name, T1.artist, T1.isPromo FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid GROUP BY T1.uuid ORDER BY COUNT(T2.id) DESC LIMIT 1
```

Result diff:

Gold 2 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 2 of 2 rows):

| name | artist | isPromo |
|---|---|---|
| Teferi's Protection | Chase Stone | 0 |
| Teferi's Protection | Chase Stone | 1 |

Predicted (first 1 of 1 rows):

| name | artist | isPromo |
|---|---|---|
| Teferi's Protection | Chase Stone | 1 |

## 371 / card_games / challenging

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query uses a LEFT JOIN, while the prediction uses an INNER JOIN, which can exclude Story Spotlight cards without a matching foreign_data row. The prediction also counts joined rows with SUM/COUNT(*) instead of distinct card IDs, but the join-type difference comes first.

Question:

```text
What is the percentage of cards whose language is French among the Story Spotlight cards?
```

Evidence:

```text
Story Spotlight card refers to isStorySpotlight = 1; French is the language; Percentage = Divide(Count(distinct id) where language = 'French' and isStorySpotlight = 1, Count(distinct id) where isStorySpotlight = 1)*100
```

Gold SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T2.language = 'French' THEN T1.id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT T1.id) FROM cards AS T1 LEFT JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.isStorySpotlight = 1
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.language = 'French' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.isStorySpotlight = 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.langua… |
|---|
| 83.65384615384616 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.language = 'Frenc… |
|---|
| 10.0 |

## 391 / card_games / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The evidence defines Artifact cards by `originalType = 'Artifact'`, but the prediction filters `types LIKE '%Artifact%'`. It also adds language conditions absent from the gold query, but the Artifact-column mismatch is the first difference to fix.

Question:

```text
Among the Artifact cards, which are black color and comes with foreign languague translation?
```

Evidence:

```text
Artifact card refers to originalType = 'Artifact'; black color refers to colors = 'B'; foreign language refers to language in foreign_data
```

Gold SQL:

```sql
SELECT DISTINCT T1.name FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.originalType = 'Artifact' AND T1.colors = 'B'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.name FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.types LIKE '%Artifact%' AND T1.colors = 'B' AND T2.language IS NOT NULL AND T2.language <> 'English'
```

Result diff:

Gold 8 rows, predicted 23 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 5 of 8 rows):

| name |
|---|
| Executioner's Capsule |
| Immortal Coil |
| Onyx Goblet |
| Netherborn Altar |
| Scepter of Fugue |

Predicted (first 5 of 23 rows):

| name |
|---|
| Executioner's Capsule |
| Glaze Fiend |
| Salvage Titan |
| Immortal Coil |
| Onyx Goblet |

## 407 / card_games / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query returns the `subtypes` and `supertypes` columns from `cards`, while the prediction returns `type` from `foreign_data`. It also omits the required non-null subtype and supertype conditions.

Question:

```text
Lists all types of cards in German.
```

Evidence:

```text
German refer to language; all types refer to the subtypes, supertypes; subtypes is not null AND supertypes is not null
```

Gold SQL:

```sql
SELECT T1.subtypes, T1.supertypes FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T2.language = 'German' AND T1.subtypes IS NOT NULL AND T1.supertypes IS NOT NULL
```

Predicted SQL:

```sql
SELECT DISTINCT T1.type FROM foreign_data AS T1 WHERE T1.language = 'German'
```

Result diff:

Gold 1693 rows, predicted 2150 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 1693 rows):

| subtypes | supertypes |
|---|---|
| Human,Rebel | Legendary |
| Angel | Legendary |
| Merfolk,Wizard | Legendary |
| Vampire,Noble | Legendary |
| Avatar,Minion | Legendary |

Predicted (first 5 of 2150 rows):

| type |
|---|
| Kreatur — Mensch, Kleriker |
| Kreatur — Engel |
| Kreatur — Vogel, Soldat |
| Kreatur — Mensch, Rebell |
| Spontanzauber |

## 408 / card_games / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query finds matching text in `rulings.text`, joined to cards by `uuid`. The prediction instead searches `cards.text` and omits the rulings table.

Question:

```text
How many unknown power cards contain info about the triggered ability
```

Evidence:

```text
unknown power cards refers to power is null or power = '*'; contain info about the triggered ability refers to ruling contains 'triggered ability'
```

Gold SQL:

```sql
SELECT Count(DISTINCT T1.id) FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE (T1.power IS NULL OR T1.power = '*') AND T2.text LIKE '%triggered ability%'
```

Predicted SQL:

```sql
SELECT COUNT(*) FROM cards AS T1 WHERE (T1.power IS NULL OR T1.power = '*') AND T1.text LIKE '%triggered ability%'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| Count(DISTINCT T1.id) |
|---|
| 1382 |

Predicted (first 1 of 1 rows):

| COUNT(*) |
|---|
| 35 |

## 416 / card_games / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction filters only `T1.power IS NULL`, while the gold query also includes cards where `T1.power = '*'`. Thus it omits part of the requested set of cards without power.

Question:

```text
What percentage of cards without power are in French?
```

Evidence:

```text
in French refers to language = 'French'; cards without power refers to power IS NULL OR power = '*'; percentage = DIVIDE(COUNT(language = 'French' and power is NULL or power = '*'), COUNT( power is NULL or power = '*'))*100
```

Gold SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T2.language = 'French' THEN T1.id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT T1.id) FROM cards AS T1 LEFT JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.language = 'French' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.langua… |
|---|
| 47.95671915756932 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.language = 'Frenc… |
|---|
| 12.965436707684958 |

## 472 / card_games / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query requires `T2.translation IS NOT NULL`, but the prediction omits this filter, counting Italian translation records even when the translation is null.

Question:

```text
Among the sets in the block "Ice Age", how many of them have an Italian translation?
```

Evidence:

```text
sets in the block "Ice Age" refers to block = 'Ice Age'; Italian translation refers to language = 'Italian' and translation is not null
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.id) FROM sets AS T1 INNER JOIN set_translations AS T2 ON T2.setCode = T1.code WHERE T1.block = 'Ice Age' AND T2.language = 'Italian' AND T2.translation IS NOT NULL
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.id) FROM sets AS T1 INNER JOIN set_translations AS T2 ON T1.code = T2.setCode WHERE T1.block = 'Ice Age' AND T2.language = 'Italian'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.id) |
|---|
| 1 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.id) |
|---|
| 2 |

## 578 / codebase_community / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The predicted query compares the title to a string with a trailing space, while the gold query uses the exact title without that space, so it returns no rows.

Question:

```text
Which user made a post titled 'Understanding what Dassault iSight is doing?' and how much is the reputation of the user?
```

Evidence:

```text
"Understanding what Dassault iSight is doing?" is the Title of post; user refers to DisplayName;
```

Gold SQL:

```sql
SELECT T1.DisplayName, T1.Reputation FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId WHERE T2.Title = 'Understanding what Dassault iSight is doing?'
```

Predicted SQL:

```sql
SELECT T2.DisplayName, T2.Reputation FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Title = 'Understanding what Dassault iSight is doing? ' OR T1.Title = 'Understanding what Dassault iSight is doing? ' LIMIT 1
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| DisplayName | Reputation |
|---|---|
| Hendy | 146 |

Predicted (first 0 of 0 rows):

| DisplayName | Reputation |
|---|---|

## 584 / codebase_community / moderate

Label: `no_sql_produced` (rule): direct_full: no valid grammar tool call

Question:

```text
Write all the edit comments left by users who edited the post titled 'Why square the difference instead of taking the absolute value in standard deviation?'
```

Evidence:

```text
Why square the difference instead of taking the absolute value in standard deviation? is the Title of post; include blank comments
```

Gold SQL:

```sql
SELECT T2.Comment FROM posts AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.PostId WHERE T1.Title = 'Why square the difference instead of taking the absolute value in standard deviation?'
```

Predicted SQL:

```sql
(no SQL)
```

Errors:

- direct_full: no valid grammar tool call

Result diff:

Gold (first 5 of 8 rows):

| Comment |
|---|
|  |
|  |
|  |
| edited title |
| TeXified the formulas. |

## 595 / codebase_community / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The gold query returns `T2.UserId`, while the prediction returns `T1.DisplayName`. The user filter and distinct post-history-type condition otherwise match; the prediction also omits the `posts` join present in the gold query.

Question:

```text
Which users have only one post history type and have at least 100 views?
```

Evidence:

```text
having at least 100 view refers to Views >= 100; user refers to UserId
```

Gold SQL:

```sql
SELECT T2.UserId FROM users AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.UserId INNER JOIN posts AS T3 ON T2.PostId = T3.Id WHERE T1.Views >= 100 GROUP BY T2.UserId HAVING COUNT(DISTINCT T2.PostHistoryTypeId) = 1
```

Predicted SQL:

```sql
SELECT T1.DisplayName FROM users AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.UserId WHERE T1.Views >= 100 GROUP BY T1.Id, T1.DisplayName HAVING COUNT(DISTINCT T2.PostHistoryTypeId) = 1
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| UserId |
|---|
| 5792 |
| 14546 |

Predicted (first 2 of 2 rows):

| DisplayName |
|---|
| Mike Anderson |
| Chris Sims |

## 637 / codebase_community / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s `p.Tags IS NOT NULL` condition, so it includes a null tag in addition to `<books>`. Add that filter to match the requested tags and the gold result.

Question:

```text
State all the tags used by Mark Meckes in his posts that doesn't have comments.
```

Evidence:

```text
used by Mark Meckes refers to DisplayName = 'Mark Meckes'; Doen't have comments refers to CommentCount = 0; exclude null tags
```

Gold SQL:

```sql
SELECT DISTINCT p.`Tags`
FROM `posts` p
JOIN `users` u ON u.`Id` = p.`OwnerUserId`
WHERE u.`DisplayName` = 'Mark Meckes'
  AND p.`CommentCount` = 0
  AND p.`Tags` IS NOT NULL;
```

Predicted SQL:

```sql
SELECT DISTINCT T1.Tags FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T2.DisplayName = 'Mark Meckes' AND T1.CommentCount = 0
```

Result diff:

Gold 1 rows, predicted 2 rows. Within the previews: 0 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| Tags |
|---|
| <books> |

Predicted (first 2 of 2 rows):

| Tags |
|---|
| <books> |
| None |

## 671 / codebase_community / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every user tied for the minimum badge date, while the prediction orders by date and uses LIMIT 1, returning only one user.

Question:

```text
What is the display name of the user who acquired the first Autobiographer badge?
```

Evidence:

```text
Autobiographer is the name of the badge; acquired the first refers to MIN(Date);
```

Gold SQL:

```sql
SELECT DISTINCT u.DisplayName FROM users AS u JOIN badges AS b ON u.Id = b.UserId WHERE b.Name = 'Autobiographer' AND b.Date = ( SELECT MIN(Date) FROM badges WHERE Name = 'Autobiographer')
```

Predicted SQL:

```sql
SELECT T2.DisplayName FROM badges AS T1 INNER JOIN users AS T2 ON T1.UserId = T2.Id WHERE T1.Name = 'Autobiographer' AND T1.Date IS NOT NULL ORDER BY T1.Date ASC LIMIT 1
```

Result diff:

Gold 12 rows, predicted 1 rows. Within the previews: 4 rows only in gold, 0 only in predicted.

Gold (first 5 of 12 rows):

| DisplayName |
|---|
| Geoff Dalgas |
| Jarrod Dixon |
| Vince |
| csgillespie |
| Pierre |

Predicted (first 1 of 1 rows):

| DisplayName |
|---|
| Geoff Dalgas |

## 672 / codebase_community / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query requires an exact location match (`Location = 'United Kingdom'`), while the prediction uses `LIKE '%United Kingdom%'`, also matching locations that merely contain that phrase. This changes the count from 14 to 38.

Question:

```text
Among the users located in United Kingdom, how many users have at least one post with a favorite amount of 4 or more?
```

Evidence:

```text
favorite amount of 4 or more refers to FavoriteCount > = 4; Location = 'United Kingdom';
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.Id) FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId WHERE T1.Location = 'United Kingdom' AND T2.FavoriteCount >= 4
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.Id) FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId WHERE T1.Location LIKE '%United Kingdom%' AND T2.FavoriteCount >= 4
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.Id) |
|---|
| 14 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.Id) |
|---|
| 38 |

## 701 / codebase_community / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query includes every user tied for maximum reputation, while the prediction uses ORDER BY Reputation DESC LIMIT 1 and selects only one user. This ranking difference can change which posts are counted.

Question:

```text
Among all the posts posted by the most influential user, identify the percentage with a score above 50.
```

Evidence:

```text
The higher reputation the user has the more influence; percentage = DIVIDE(COUNT(stats_posts.Id where Score > 50 and MAX(Reputation))), COUNT(stats_posts.Id where MAX(Reputation));
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.Score > 50 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.Id) FROM users T1 INNER JOIN posts T2 ON T1.Id = T2.OwnerUserId INNER JOIN ( SELECT MAX(Reputation) AS max_reputation FROM users ) T3 ON T1.Reputation = T3.max_reputation
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.Score > 50 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM posts AS T1 INNER JOIN (SELECT T3.Id FROM users AS T3 ORDER BY T3.Reputation DESC LIMIT 1) AS T2 ON T1.OwnerUserId = T2.Id
```

Result diff:

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.Score > 50 THEN 1… |
|---|
| 0.6644518272425249 |

## 716 / codebase_community / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts distinct users with zero upvotes over distinct users in the score range. The prediction instead counts matching comment rows and divides by all comment rows, so it calculates a comment-level percentage rather than a user-level percentage.

Question:

```text
Among the comments with scores between 5 to 10, what is the percentage of the users with 0 up votes?
```

Evidence:

```text
percentage = DIVIDE(COUNT(DISTINCT UserId where UpVotes = 0 and Score BETWEEN 5 and 10))*100, (COUNT(DISTINCT UserId where Score BETWEEN 5 and 10));
```

Gold SQL:

```sql
SELECT CAST(COUNT(DISTINCT IIF(T1.UpVotes = 0, T1.Id, NULL)) AS REAL) * 100/ COUNT(DISTINCT T1.Id) AS per FROM users AS T1 INNER JOIN comments AS T2 ON T1.Id = T2.UserId WHERE T2.Score BETWEEN 5 AND 10
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.UpVotes = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.Id) FROM comments AS T1 INNER JOIN users AS T2 ON T1.UserId = T2.Id WHERE T1.Score BETWEEN 5 AND 10
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| per |
|---|
| 4.87012987012987 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.UpVotes = 0 THEN … |
|---|
| 1.3254786450662739 |

## 726 / superhero / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s filters excluding NULL and zero heights, producing 387 rows instead of 327. It also returns `height_cm` as an extra column, but the missing filters are the first difference to address.

Question:

```text
Rank heroes published by Marvel Comics by their height in descending order.
```

Evidence:

```text
name refers to superhero_name; the tallest hero refers to MAX(height_cm); published by Marvel Comics refers to publisher_name = 'Marvel Comics'
```

Gold SQL:

```sql
SELECT superhero_name FROM superhero AS s JOIN publisher AS p ON s.publisher_id = p.id WHERE p.publisher_name = 'Marvel Comics' AND s.height_cm IS NOT NULL AND s.height_cm != 0 ORDER BY s.height_cm DESC
```

Predicted SQL:

```sql
SELECT T1.superhero_name, T1.height_cm FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T2.publisher_name = 'Marvel Comics' ORDER BY T1.height_cm DESC
```

Result diff:

Gold 327 rows, predicted 387 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 327 rows):

| superhero_name |
|---|
| Surtur |
| Ymir |
| Bloodwraith |
| Utgard-Loki |
| Fin Fang Foom |

Predicted (first 5 of 387 rows):

| superhero_name | height_cm |
|---|---|
| Surtur | 30480 |
| Ymir | 30480 |
| Bloodwraith | 3050 |
| Utgard-Loki | 1520 |
| Fin Fang Foom | 975 |

## 736 / superhero / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every superhero whose Intelligence equals the minimum value, including ties. The prediction orders by Intelligence and limits the result to one row, so it omits tied superheroes.

Question:

```text
Who is the dumbest superhero?
```

Evidence:

```text
the dumbest superhero refers to MIN(attribute_value) where attribute_name = 'Intelligence'
```

Gold SQL:

```sql
SELECT s.superhero_name FROM superhero AS s JOIN hero_attribute AS ha ON s.id = ha.hero_id JOIN attribute AS a ON ha.attribute_id = a.id WHERE a.attribute_name = 'Intelligence' AND ha.attribute_value = ( SELECT MIN(attribute_value) FROM hero_attribute WHERE attribute_id = ( SELECT id FROM attribute WHERE attribute_name = 'Intelligence' ) )
```

Predicted SQL:

```sql
SELECT T1.superhero_name FROM superhero AS T1 INNER JOIN hero_attribute AS T2 ON T1.id = T2.hero_id INNER JOIN attribute AS T3 ON T2.attribute_id = T3.id WHERE T3.attribute_name = 'Intelligence' AND T2.attribute_value IS NOT NULL ORDER BY T2.attribute_value ASC LIMIT 1
```

Result diff:

Gold 3 rows, predicted 1 rows. Within the previews: 2 rows only in gold, 0 only in predicted.

Gold (first 3 of 3 rows):

| superhero_name |
|---|
| Ammo |
| Ando Masahashi |
| Jack-Jack |

Predicted (first 1 of 1 rows):

| superhero_name |
|---|
| Ammo |

## 743 / superhero / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The evidence and gold query select superheroes with alignment = 'Bad', but the prediction calculates both values for alignment = 'Neutral'. This wrong alignment value changes the result.

Question:

```text
What is the percentage of superheroes who act in their own self-interest or make decisions based on their own moral code? Indicate how many of the said superheroes were published by Marvel Comics.
```

Evidence:

```text
published by Marvel Comics refers to publisher_name = 'Marvel Comics'; superheroes who act in their own self-interest or make decisions based on their own moral code refers to alignment = 'Bad'; calculation = MULTIPLY(DIVIDE(SUM(alignment = 'Bad); count(id)), 100)
```

Gold SQL:

```sql
SELECT (CAST(COUNT(*) AS REAL) * 100 / (SELECT COUNT(*) FROM superhero)), SUM(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id INNER JOIN alignment AS T3 ON T3.id = T1.alignment_id WHERE T3.alignment = 'Bad'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.alignment = 'Neutral' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id), SUM(CASE WHEN T2.alignment = 'Neutral' AND T3.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) FROM superhero AS T1 LEFT JOIN alignment AS T2 ON T1.alignment_id = T2.id LEFT JOIN publisher AS T3 ON T1.publisher_id = T3.id
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| (CAST(COUNT(*) AS REAL) * 100 / (SELECT… | SUM(CASE WHEN T2.publisher_name = 'Marv… |
|---|---|
| 28.266666666666666 | 118 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.alignment = 'Neut… | SUM(CASE WHEN T2.alignment = 'Neutral' … |
|---|---|
| 3.7333333333333334 | 10 |

## 747 / superhero / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters for `full_name IS NULL`, while the prediction checks whether `full_name = '-'`. The prediction therefore uses the wrong filter condition for superheroes without a full name.

Question:

```text
What is the total number of superheroes without full name?
```

Evidence:

```text
superheroes without full name refers to full_name IS NULL
```

Gold SQL:

```sql
SELECT COUNT(id) FROM superhero WHERE full_name IS NULL
```

Predicted SQL:

```sql
SELECT COUNT(T1.id) FROM superhero AS T1 WHERE T1.full_name = '-'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(id) |
|---|
| 122 |

Predicted (first 1 of 1 rows):

| COUNT(T1.id) |
|---|
| 125 |

## 772 / superhero / challenging

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query returns the eye, hair, and skin colour ID columns, while the prediction joins the colour table and returns its `colour` names instead. The gender and publisher filters match.

Question:

```text
List the eyes, hair and skin colour of all female superheroes published by Dark Horse Comics.
```

Evidence:

```text
eyes refers to eye_colour_id; hair refers to hair_colour_id; skin colour refers to skin_colour_id; female superheroes refers to gender = 'Female'; published by Dark Horse Comics refers to publisher_name = 'Dark Horse Comics';
```

Gold SQL:

```sql
SELECT T1.eye_colour_id, T1.hair_colour_id, T1.skin_colour_id FROM superhero AS T1 INNER JOIN publisher AS T2 ON T2.id = T1.publisher_id INNER JOIN gender AS T3 ON T3.id = T1.gender_id WHERE T2.publisher_name = 'Dark Horse Comics' AND T3.gender = 'Female'
```

Predicted SQL:

```sql
SELECT T2.colour, T3.colour, T4.colour FROM superhero AS T1 INNER JOIN colour AS T2 ON T1.eye_colour_id = T2.id INNER JOIN colour AS T3 ON T1.hair_colour_id = T3.id INNER JOIN colour AS T4 ON T1.skin_colour_id = T4.id INNER JOIN gender AS T5 ON T1.gender_id = T5.id INNER JOIN publisher AS T6 ON T1.publisher_id = T6.id WHERE T5.gender = 'Female' AND T6.publisher_name = 'Dark Horse Comics'
```

Result diff:

Gold 5 rows, predicted 5 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 5 rows):

| eye_colour_id | hair_colour_id | skin_colour_id |
|---|---|---|
| 14 | 6 | 1 |
| 9 | 9 | 1 |
| 1 | 1 | 1 |
| 1 | 1 | 28 |
| 30 | 4 | 1 |

Predicted (first 5 of 5 rows):

| colour | colour | colour |
|---|---|---|
| Green | Blond | No Colour |
| Brown | Brown | No Colour |
| No Colour | No Colour | No Colour |
| No Colour | No Colour | Silver |
| Violet | Black | No Colour |

## 773 / superhero / challenging

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query uses a LEFT JOIN to retain matching superheroes even if they lack a publisher, while the prediction uses an INNER JOIN and excludes those rows.

Question:

```text
Which superhero has the same eyes, hair and skin colour? Indicate the publisher of the superhero.
```

Evidence:

```text
which superhero refers to superhero_name; the same eyes, hair and skin colour refers to hair_colour_id = skin_colour_id AND hair_colour_id = eye_colour_id; publisher refers to publisher_name;
```

Gold SQL:

```sql
SELECT T1.superhero_name, T2.publisher_name FROM superhero AS T1 LEFT JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T1.eye_colour_id = T1.hair_colour_id AND T1.eye_colour_id = T1.skin_colour_id
```

Predicted SQL:

```sql
SELECT T1.superhero_name, T2.publisher_name FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T1.eye_colour_id = T1.hair_colour_id AND T1.hair_colour_id = T1.skin_colour_id LIMIT 1000 OFFSET 0
```

Result diff:

Gold 159 rows, predicted 157 rows. Within the previews: 0 rows only in gold, 0 only in predicted.

Gold (first 5 of 159 rows):

| superhero_name | publisher_name |
|---|---|
| Agent Zero | Marvel Comics |
| Alex Mercer | Wildstorm |
| Alex Woolsly | NBC - Heroes |
| Allan Quatermain | Wildstorm |
| Ando Masahashi | NBC - Heroes |

Predicted (first 5 of 157 rows):

| superhero_name | publisher_name |
|---|---|
| Agent Zero | Marvel Comics |
| Alex Mercer | Wildstorm |
| Alex Woolsly | NBC - Heroes |
| Allan Quatermain | Wildstorm |
| Ando Masahashi | NBC - Heroes |

## 829 / superhero / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query computes `dc_cnt - marvel_cnt`, yielding -163, while the prediction subtracts the smaller count from the larger count, yielding 163. The winner is correctly identified, but the difference calculation has the opposite sign.

Question:

```text
Which publisher created more superheroes: DC or Marvel Comics? Find the difference in the number of superheroes.
```

Evidence:

```text
DC refers to publisher_name = 'DC Comics'; Marvel Comics refers to publisher_name = 'Marvel Comics'; difference = SUBTRACT(SUM(publisher_name = 'DC Comics'), SUM(publisher_name = 'Marvel Comics'));
```

Gold SQL:

```sql
SELECT CASE WHEN marvel_cnt > dc_cnt THEN 'Marvel Comics' ELSE 'DC Comics' END AS publisher_with_more_superheroes,
        dc_cnt - marvel_cnt AS difference
FROM (
    SELECT SUM(CASE WHEN p.`publisher_name`='Marvel Comics' THEN 1 END) AS marvel_cnt,
           SUM(CASE WHEN p.`publisher_name`='DC Comics' THEN 1 END)    AS dc_cnt
    FROM `superhero` s
    JOIN `publisher` p ON s.`publisher_id` = p.`id`
) t;
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.publisher_name, COUNT(T2.id) AS c1 FROM publisher AS T1 INNER JOIN superhero AS T2 ON T1.id = T2.publisher_id WHERE T1.publisher_name IN ('DC Comics', 'Marvel Comics') GROUP BY T1.publisher_name) SELECT T1.publisher_name, T1.c1 - T2.c1 FROM cte1 AS T1 INNER JOIN cte1 AS T2 ON T1.c1 > T2.c1 ORDER BY T1.c1 DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| publisher_with_more_superheroes | difference |
|---|---|
| Marvel Comics | -163 |

Predicted (first 1 of 1 rows):

| publisher_name | T1.c1 - T2.c1 |
|---|---|
| Marvel Comics | 163 |

## 846 / formula_1 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query selects the five drivers with the highest q1 values using ORDER BY q1 DESC LIMIT 5. The prediction instead filters on q2 IS NULL, returning six drivers and not applying the q1 ranking.

Question:

```text
Please list the reference names of the drivers who are eliminated in the first period in race number 20.
```

Evidence:

```text
driver reference name refers to driverRef; first qualifying period refers to q1; drivers who are eliminated in the first qualifying period refers to 5 drivers with MAX(q1); race number refers to raceId;
```

Gold SQL:

```sql
SELECT T2.driverRef FROM qualifying AS T1 INNER JOIN drivers AS T2 ON T2.driverId = T1.driverId WHERE T1.raceId = 20 ORDER BY T1.q1 DESC LIMIT 5
```

Predicted SQL:

```sql
SELECT T1.driverRef FROM drivers AS T1 INNER JOIN qualifying AS T2 ON T1.driverId = T2.driverId WHERE T2.raceId = 20 AND T2.q2 IS NULL
```

Result diff:

Gold 5 rows, predicted 6 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 5 rows):

| driverRef |
|---|
| sato |
| davidson |
| vettel |
| sutil |
| fisichella |

Predicted (first 5 of 6 rows):

| driverRef |
|---|
| coulthard |
| fisichella |
| vettel |
| sutil |
| davidson |

## 861 / formula_1 / simple

Label: `date_handling` (classifier, gpt-6-luna): The gold query matches the Q3 time using `LIKE '1:54%'`, while the prediction compares it to the exact string `'0:01:54'`. The time-format interpretation and comparison differ, causing the prediction to return no rows.

Question:

```text
What is his number of the driver who finished 0:01:54 in the Q3 of qualifying race No.903?
```

Evidence:

```text
race number refers to raceId; finished 0:0M:SS in the Q3 refers to q3 LIKE 'M:SS%'
```

Gold SQL:

```sql
SELECT T2.number FROM qualifying AS T1 INNER JOIN drivers AS T2 ON T2.driverId = T1.driverId WHERE T1.raceId = 903 AND T1.q3 LIKE '1:54%'
```

Predicted SQL:

```sql
SELECT T1.number FROM drivers AS T1 INNER JOIN qualifying AS T2 ON T1.driverId = T2.driverId WHERE T2.raceId = 903 AND T2.q3 = '0:01:54'
```

Result diff:

Gold 2 rows, predicted 0 rows. Within the previews: 2 rows only in gold, 0 only in predicted.

Gold (first 2 of 2 rows):

| number |
|---|
| 3 |
| 5 |

Predicted (first 0 of 0 rows):

| number |
|---|

## 872 / formula_1 / simple

Label: `date_handling` (classifier, gpt-6-luna): The prediction compares q3 to the exact string '0:01:33', while the evidence specifies the time format should be matched with LIKE '1:33%'. The formatting and comparison of the time value cause the prediction to return no rows.

Question:

```text
In the race No. 45, for the driver who had the Q3 time as 0:01:33, what is his abbreviated code?
```

Evidence:

```text
race number refers to raceId; had the Q3 time as 0:0M:SS refers to q3 LIKE 'M:SS%'
```

Gold SQL:

```sql
SELECT T2.code FROM qualifying AS T1 INNER JOIN drivers AS T2 ON T2.driverId = T1.driverId WHERE T1.raceId = 45 AND T1.q3 LIKE '1:33%'
```

Predicted SQL:

```sql
SELECT T2.code FROM qualifying AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId WHERE T1.raceId = 45 AND T1.q3 = '0:01:33'
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| code |
|---|
| HAM |

Predicted (first 0 of 0 rows):

| code |
|---|

## 894 / formula_1 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query returns `lapTimes.milliseconds`, the numeric value defining the best lap time. The prediction selects `lapTimes.time` instead, so the recorded lap-time output differs.

Question:

```text
What is the best lap time recorded? List the recorded lap time, driver, and race.
```

Evidence:

```text
the best lap time refers to min(milliseconds); List the driver refers to drivers.forename and drivers.surname; List the race refers to races.name
```

Gold SQL:

```sql
SELECT T2.milliseconds, T1.forename, T1.surname, T3.name FROM drivers AS T1 INNER JOIN lapTimes AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T2.raceId = T3.raceId ORDER BY T2.milliseconds ASC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.time, T2.forename, T2.surname, T3.name FROM lapTimes AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T1.raceId = T3.raceId WHERE T1.milliseconds IS NOT NULL ORDER BY T1.milliseconds ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| milliseconds | forename | surname | name |
|---|---|---|---|
| 67411 | Lewis | Hamilton | Austrian Grand Prix |

Predicted (first 1 of 1 rows):

| time | forename | surname | name |
|---|---|---|---|
| 1:07.411 | Lewis | Hamilton | Austrian Grand Prix |

## 896 / formula_1 / challenging

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query uses `driverStandings.position` and counts `driverStandingsId`, while the prediction uses `results.position` and counts `resultId`. These are different records and produce a different percentage.

Question:

```text
Calculate the percentage whereby Hamilton was not at the 1st track of the the f1 circuit since 2010.
```

Evidence:

```text
percentage = DIVIDE(COUNT(raceId) where surname = 'Hamilton' and position>1), (COUNT(raceId) where surname = 'Hamilton'); since 2010 refers to year >= 2010. position refers to driverStandings.position
```

Gold SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T2.position <> 1 THEN T2.position END) AS REAL) * 100 / COUNT(T2.driverStandingsId) FROM races AS T1 INNER JOIN driverStandings AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId WHERE T3.surname = 'Hamilton' AND T1.year >= 2010
```

Predicted SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T1.position != 1 THEN 1 END) AS REAL) * 100 / COUNT(T1.resultId) FROM results AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T1.raceId = T3.raceId WHERE T2.surname = 'Hamilton' AND T3.year >= 2010
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T2.position <> 1 T… |
|---|
| 74.0 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T1.position != 1 T… |
|---|
| 55.333333333333336 |

## 902 / formula_1 / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query uses `driverStandings` to interpret the requested track/position, while the prediction uses `results`. That changes which race names qualify.

Question:

```text
Which race was Alex Yoong in when he was in track number less than 20?
```

Evidence:

```text
Alex Yoong refers to the full name of the driver; Full name of the driver refers to drivers.forename and drivers.surname;track number less than 10 refers to driverStandings.position < 20
```

Gold SQL:

```sql
SELECT T1.name FROM races AS T1 INNER JOIN driverStandings AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId WHERE T3.forename = 'Alex' AND T3.surname = 'Yoong' AND T2.position < 20
```

Predicted SQL:

```sql
SELECT DISTINCT T1.name FROM races AS T1 INNER JOIN results AS T2 ON T1.raceId = T2.raceId INNER JOIN drivers AS T3 ON T2.driverId = T3.driverId WHERE T3.forename = 'Alex' AND T3.surname = 'Yoong' AND T2.position < 20
```

Result diff:

Gold 16 rows, predicted 6 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 5 of 16 rows):

| name |
|---|
| Australian Grand Prix |
| Malaysian Grand Prix |
| Brazilian Grand Prix |
| San Marino Grand Prix |
| Spanish Grand Prix |

Predicted (first 5 of 6 rows):

| name |
|---|
| Australian Grand Prix |
| Brazilian Grand Prix |
| Canadian Grand Prix |
| French Grand Prix |
| Italian Grand Prix |

## 904 / formula_1 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query identifies the fastest lap using `lapTimes.milliseconds`, while the prediction uses `results.fastestLapTime` from a different table. This changes which race is selected.

Question:

```text
State the race and year of race in which Michael Schumacher had his fastest lap.
```

Evidence:

```text
fastest lap refers to min(milliseconds); Michael Schumacher refers to the full name of the driver; Full name of the driver refers to drivers.forename and drivers.surname;
```

Gold SQL:

```sql
SELECT T1.name, T1.year FROM races AS T1 INNER JOIN lapTimes AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId WHERE T3.forename = 'Michael' AND T3.surname = 'Schumacher' ORDER BY T2.milliseconds ASC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.name, T1.year FROM races AS T1 INNER JOIN results AS T2 ON T1.raceId = T2.raceId INNER JOIN drivers AS T3 ON T2.driverId = T3.driverId WHERE T3.forename = 'Michael' AND T3.surname = 'Schumacher' AND T2.fastestLapTime IS NOT NULL ORDER BY T2.fastestLapTime ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| name | year |
|---|---|
| Austrian Grand Prix | 2003 |

Predicted (first 1 of 1 rows):

| name | year |
|---|---|
| United States Grand Prix | 2004 |

## 962 / formula_1 / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query counts results with `laps > 50`, while the prediction filters for `laps = 50`. This changes the condition for qualifying drivers.

Question:

```text
In the races from 2000 to 2005, what percentage of drivers were born before 1985 and completed 50 laps?
```

Evidence:

```text
born before 1985 refers to year(dob)<1985; in 2000 to 2005 refers to year between 2000 and 2005; percentage = Divide(COUNT(driverId where year (dob) <1985 and laps >50),COUNT(DriverID where year between 2000 and 2005) *100;
```

Gold SQL:

```sql
SELECT CAST(COUNT(DISTINCT IIF(STRFTIME('%Y', T3.dob) < '1985' AND T1.laps > 50, T1.driverId, NULL)) AS REAL) * 100 / COUNT(DISTINCT T1.driverId) FROM results AS T1 INNER JOIN races AS T2 on T1.raceId = T2.raceId INNER JOIN drivers AS T3 on T1.driverId = T3.driverId WHERE T2.year BETWEEN 2000 AND 2005
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN STRFTIME('%Y', T1.dob) < '1985' AND T2.laps = 50 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T2.raceId = T3.raceId WHERE T3.year BETWEEN 2000 AND 2005
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT IIF(STRFTIME('%Y', … |
|---|
| 100.0 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN STRFTIME('%Y', T1.do… |
|---|
| 0.6004618937644342 |

## 972 / formula_1 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query checks whether `results.fastestLapTime` is non-NULL, while the prediction filters on `results.rank = 1`. It uses a different column to identify drivers with a fastest lap time.

Question:

```text
Which drivers who were born in 1971 and has the fastest lap time on the race? Give id and code of these drivers.
```

Evidence:

```text
born in 1971 refers to year(dob) = 1971; has the fastest lap time refers to fastestLapTime has values
```

Gold SQL:

```sql
SELECT DISTINCT T2.driverId, T2.code 
FROM results AS T1 INNER JOIN drivers AS T2 on T1.driverId = T2.driverId 
WHERE STRFTIME('%Y', T2.dob) = '1971' AND T1.fastestLapTime IS NOT NULL
```

Predicted SQL:

```sql
SELECT DISTINCT T1.driverId, T1.code FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId WHERE STRFTIME('%Y', T1.dob) = '1971' AND T2.rank = 1
```

Result diff:

Gold 4 rows, predicted 1 rows. Within the previews: 3 rows only in gold, 0 only in predicted.

Gold (first 4 of 4 rows):

| driverId | code |
|---|---|
| 14 | COU |
| 35 | VIL |
| 37 | DLR |
| 69 | BAD |

Predicted (first 1 of 1 rows):

| driverId | code |
|---|---|
| 37 | DLR |

## 977 / formula_1 / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction uses `BETWEEN 50 AND 100`, while the evidence and gold query require `raceId > 50 AND raceId < 100`. It also counts all matching disqualified rows instead of counting only those with a non-NULL finish time.

Question:

```text
From race no. 50 to 100, how many finishers have been disqualified?
```

Evidence:

```text
disqualified refers to statusID = 2, finisher refers to time! = null; race no. refers to raceId; raceId > 50 and raceId < 100;
```

Gold SQL:

```sql
SELECT SUM(IIF(time IS NOT NULL, 1, 0)) FROM results WHERE statusId = 2 AND raceID < 100 AND raceId > 50
```

Predicted SQL:

```sql
SELECT COUNT(*) FROM results AS T1 INNER JOIN status AS T2 ON T1.statusId = T2.statusId WHERE T1.raceId BETWEEN 50 AND 100 AND T2.status = 'Disqualified'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(IIF(time IS NOT NULL, 1, 0)) |
|---|
| 2 |

Predicted (first 1 of 1 rows):

| COUNT(*) |
|---|
| 13 |

## 1094 / european_football_2 / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query sums each player's overall ratings, while the prediction averages them. This changes the percentage result.

Question:

```text
How much higher in percentage is Ariel Borysiuk's overall rating than that of Paulin Puel?
```

Evidence:

```text
how much higher in percentage = MULTIPLY(DIVIDE(SUBTRACT(overall_rating WHERE player_name = 'Ariel Borysiuk', overall_rating WHERE player_name = 'Paulin Puel'), overall_rating WHERE player_name = 'Paulin Puel'), 100); overall_rating = SUM(overall_rating)
```

Gold SQL:

```sql
SELECT (SUM(CASE WHEN t1.player_name = 'Ariel Borysiuk' THEN t2.overall_rating ELSE 0 END) * 1.0 - SUM(CASE WHEN t1.player_name = 'Paulin Puel' THEN t2.overall_rating ELSE 0 END)) * 100 / SUM(CASE WHEN t1.player_name = 'Paulin Puel' THEN t2.overall_rating ELSE 0 END) FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT AVG(CASE WHEN T1.player_name = 'Ariel Borysiuk' THEN T2.overall_rating END) AS c1, AVG(CASE WHEN T1.player_name = 'Paulin Puel' THEN T2.overall_rating END) AS c2 FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.player_name IN ('Ariel Borysiuk', 'Paulin Puel')) SELECT CAST(T1.c1 - T1.c2 AS REAL) * 100 / T1.c2 FROM cte1 AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| (SUM(CASE WHEN t1.player_name = 'Ariel … |
|---|
| 133.7260677466863 |

Predicted (first 1 of 1 rows):

| CAST(T1.c1 - T1.c2 AS REAL) * 100 / T1.… |
|---|
| 16.863033873343145 |

## 1133 / european_football_2 / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction uses `player_name LIKE 'Aaron %'` instead of the gold `LIKE 'Aaron%'`, adding a required space after Aaron and changing which names match. Its year condition `>= '2000'` is equivalent here to the gold condition `> '1990'` for four-digit years.

Question:

```text
How many football players born after the 1990s have the first name "Aaron"?
```

Evidence:

```text
first name "Aaron" refers to player_name LIKE 'Aaron%'; born after the 1990s refers to STRFTIME('%Y', birthday) > '1990'
```

Gold SQL:

```sql
SELECT COUNT(id) FROM Player WHERE STRFTIME('%Y', birthday) > '1990' AND player_name LIKE 'Aaron%'
```

Predicted SQL:

```sql
SELECT COUNT(T1.id) FROM Player AS T1 WHERE STRFTIME('%Y', T1.birthday) >= '2000' AND T1.player_name LIKE 'Aaron %'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(id) |
|---|
| 6 |

Predicted (first 1 of 1 rows):

| COUNT(T1.id) |
|---|
| 0 |

## 1149 / thrombosis_prediction / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The prediction computes the absolute difference between in-patient and outpatient counts as a percentage of all male patients. The evidence and gold query define the percentage as in-patient male count divided by outpatient male count, times 100.

Question:

```text
Are there more in-patient or outpatient who were male? What is the deviation in percentage?
```

Evidence:

```text
male refers to SEX = 'M'; in-patient refers to Admission = '+'; outpatient refers to Admission = '-'; percentage = DIVIDE(COUNT(ID) where SEX = 'M' and Admission = '+', COUNT(ID) where SEX  = 'M' and Admission = '-')
```

Gold SQL:

```sql
WITH male_counts AS ( SELECT SUM(CASE WHEN p.SEX = 'M' AND p.Admission = '+' THEN 1 ELSE 0 END) AS in_count, SUM(CASE WHEN p.SEX = 'M' AND p.Admission = '-' THEN 1 ELSE 0 END) AS out_count FROM Patient p ) SELECT CASE WHEN in_count > out_count THEN 'in-patient' ELSE 'outpatient' END, CAST(in_count AS FLOAT) * 100 / out_count AS percentage FROM male_counts;
```

Predicted SQL:

```sql
SELECT CASE WHEN SUM(CASE WHEN T1.Admission = '+' THEN 1 ELSE 0 END) > SUM(CASE WHEN T1.Admission = '-' THEN 1 ELSE 0 END) THEN 'In-patient' WHEN SUM(CASE WHEN T1.Admission = '+' THEN 1 ELSE 0 END) < SUM(CASE WHEN T1.Admission = '-' THEN 1 ELSE 0 END) THEN 'Outpatient' ELSE 'Equal' END AS c1, CAST(ABS(SUM(CASE WHEN T1.Admission = '+' THEN 1 ELSE 0 END) - SUM(CASE WHEN T1.Admission = '-' THEN 1 ELSE 0 END)) AS REAL) * 100 / COUNT(*) AS c2 FROM Patient AS T1 WHERE T1.SEX = 'M'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CASE WHEN in_count > out_count THEN 'in… | percentage |
|---|---|
| outpatient | 83.17757009345794 |

Predicted (first 1 of 1 rows):

| c1 | c2 |
|---|---|
| Outpatient | 8.910891089108912 |

## 1150 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters the denominator to female patients (`WHERE SEX = 'F'`) and counts those born after 1930 in the numerator. The prediction instead filters all patients to those born after 1930 and counts female patients in that subset, reversing the conditions.

Question:

```text
What is the percentage of female patient were born after 1930?
```

Evidence:

```text
female refers to Sex = 'F'; patient who were born after 1930 refers to year(Birthday) > '1930'; calculation = DIVIDE(COUNT(ID) where year(Birthday) > '1930' and SEX = 'F'), (COUNT(ID) where SEX = 'F')
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN STRFTIME('%Y', Birthday) > '1930' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM Patient WHERE SEX = 'F'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.SEX = 'F' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.ID) FROM Patient AS T1 WHERE STRFTIME('%Y', T1.Birthday) > '1930'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN STRFTIME('%Y', Birth… |
|---|
| 94.03714565004887 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.SEX = 'F' THEN 1 … |
|---|
| 83.65217391304348 |

## 1155 / thrombosis_prediction / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold filters LDH > 500, while the prediction uses LDH >= 500, incorrectly including patients whose LDH is exactly 500.

Question:

```text
List the patient ID, sex and birthday of patient with LDH beyond normal range.
```

Evidence:

```text
LDH beyond normal range refers to LDH > '500';
```

Gold SQL:

```sql
SELECT DISTINCT T1.ID, T1.SEX, T1.Birthday FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.LDH > 500
```

Predicted SQL:

```sql
SELECT DISTINCT T1.ID, T1.SEX, T1.Birthday FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.LDH >= 500
```

Result diff:

Gold 103 rows, predicted 104 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 103 rows):

| ID | SEX | Birthday |
|---|---|---|
| 27654 | F | 1936-03-25 |
| 57266 | M | 1923-07-25 |
| 81043 | M | 1967-03-25 |
| 540520 | F | 1941-11-21 |
| 912147 | F | 1975-02-17 |

Predicted (first 5 of 104 rows):

| ID | SEX | Birthday |
|---|---|---|
| 27654 | F | 1936-03-25 |
| 57266 | M | 1923-07-25 |
| 81043 | M | 1967-03-25 |
| 304157 | F | 1920-08-22 |
| 540520 | F | 1941-11-21 |

## 1162 / thrombosis_prediction / moderate

Label: `no_sql_produced` (rule): direct_full: no valid grammar tool call

Question:

```text
How many female patients who came at the hospital in 1997 was immediately followed at the outpatient clinic?
```

Evidence:

```text
female refers to sex = 'F'; came at the hospital in 1997 refers to year(Description) = '1997'; immediately followed at the outpatient clinic refers to Admission = '-'
```

Gold SQL:

```sql
SELECT COUNT(*) FROM Patient WHERE STRFTIME('%Y', Description) = '1997' AND SEX = 'F' AND Admission = '-'
```

Predicted SQL:

```sql
(no SQL)
```

Errors:

- direct_full: no valid grammar tool call

Result diff:

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 161 |

## 1166 / thrombosis_prediction / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query selects patients with the maximum birthday value and handles the case where the youngest patient has no non-NULL symptoms. The prediction instead orders examination rows and takes a single row with LIMIT 1, which can select a different patient or examination, as reflected by the differing diagnosis.

Question:

```text
What are the symptoms observed by the youngest patient to ever did a medical examination? Identify the patient diagnosis.
```

Evidence:

```text
The larger the birthday value, the younger the person is, and vice versa; symptoms observed refers to the symptoms is not NULL
```

Gold SQL:

```sql
SELECT DISTINCT e.Symptoms, p.Diagnosis FROM Patient AS p INNER JOIN Examination AS e ON p.ID = e.ID WHERE p.Birthday = ( SELECT MAX(p2.Birthday) FROM Patient AS p2 INNER JOIN Examination AS e2 ON p2.ID = e2.ID ) AND NOT e.Symptoms IS NULL UNION SELECT NULL AS Symptoms, p.Diagnosis FROM Patient AS p WHERE p.ID = (SELECT p2.ID FROM Patient AS p2 INNER JOIN Examination AS e2 ON p2.ID = e2.ID WHERE p2.Birthday = (SELECT MAX(p3.Birthday) FROM Patient AS p3 INNER JOIN Examination AS e3 ON p3.ID = e3.ID ) ) AND NOT EXISTS( SELECT 1 FROM Examination AS e WHERE e.ID = p.ID AND NOT e.Symptoms IS NULL )
```

Predicted SQL:

```sql
SELECT T2.Symptoms, T2.Diagnosis FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.Birthday IS NOT NULL ORDER BY T1.Birthday DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| Symptoms | Diagnosis |
|---|---|
| None | SJS |

Predicted (first 1 of 1 rows):

| Symptoms | Diagnosis |
|---|---|
| None | SjS |

## 1185 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query calculates the decrease rate from monthly SUMs, while the prediction subtracts individual November and December measurements pairwise. It also multiplies the ratio by 100, unlike the gold query.

Question:

```text
For the patient who was born on 1959/2/18, what is the decrease rate for his/her total cholesterol from November to December in 1981?
```

Evidence:

```text
born on 1959/2/18 refers to Birthday = '1959-02-18'; calculation = DIVISION(SUBTRACT(SUM(Birthday = '1959-02-18' and Date like '1981-11-%' THEN `T-CHO`), SUM(Birthday = '1959-02-18' and Date like '1981-12-%' THEN `T-CHO`)), SUM(Birthday = '1959-02-18' and Date like '1981-11-%' THEN `T-CHO`))
```

Gold SQL:

```sql
SELECT CAST((SUM(CASE WHEN T2.Date LIKE '1981-11-%' THEN T2."T-CHO" ELSE 0 END) - SUM(CASE WHEN T2.Date LIKE '1981-12-%' THEN T2."T-CHO" ELSE 0 END)) AS REAL) / SUM(CASE WHEN T2.Date LIKE '1981-11-%' THEN T2."T-CHO" ELSE 0 END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.Birthday = '1959-02-18'
```

Predicted SQL:

```sql
SELECT CAST(T2.`T-CHO` - T3.`T-CHO` AS REAL) * 100 / T2.`T-CHO` FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID INNER JOIN Laboratory AS T3 ON T1.ID = T3.ID WHERE T1.Birthday = '1959-02-18' AND STRFTIME('%Y-%m', T2.Date) = '1981-11' AND STRFTIME('%Y-%m', T3.Date) = '1981-12'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST((SUM(CASE WHEN T2.Date LIKE '1981-… |
|---|
| 0.05687203791469194 |

Predicted (first 1 of 1 rows):

| CAST(T2.`T-CHO` - T3.`T-CHO` AS REAL) *… |
|---|
| 5.687203791469194 |

## 1198 / thrombosis_prediction / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query requires an exact match, `Diagnosis = 'APS'`, while the prediction uses `LIKE '%APS%'`, which also counts diagnoses containing APS as a substring. This changes the count from 16 to 51.

Question:

```text
How many female patients were given an APS diagnosis?
```

Evidence:

```text
female refers to SEX = 'F'; APS diagnosis refers to Patient.Diagnosis='APS'
```

Gold SQL:

```sql
SELECT COUNT(ID) FROM Patient WHERE SEX = 'F' AND Diagnosis = 'APS'
```

Predicted SQL:

```sql
SELECT COUNT(T1.ID) FROM Patient AS T1 WHERE T1.SEX = 'F' AND T1.Diagnosis LIKE '%APS%'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(ID) |
|---|
| 16 |

Predicted (first 1 of 1 rows):

| COUNT(T1.ID) |
|---|
| 51 |

## 1220 / thrombosis_prediction / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The evidence specifies that borderline-passing UN is 29, and the gold query filters on `T2.UN = 29`. The prediction instead uses `T2.UN = 30`.

Question:

```text
Provide all ID, sex and birthday of patients whose urea nitrogen (UN) just within the borderline of passing?
```

Evidence:

```text
urea nitrogen (UN) just within the borderline of passing refers to UN = 29; 
```

Gold SQL:

```sql
SELECT DISTINCT T1.ID, T1.SEX, T1.Birthday FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.UN = 29
```

Predicted SQL:

```sql
SELECT DISTINCT T1.ID, T1.SEX, T1.Birthday FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.UN = 30
```

Result diff:

Gold 20 rows, predicted 10 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 5 of 20 rows):

| ID | SEX | Birthday |
|---|---|---|
| 27654 | F | 1936-03-25 |
| 444499 | M | 1954-01-24 |
| 912147 | F | 1975-02-17 |
| 1138737 | F | 1965-11-18 |
| 1185720 | F | 1953-10-12 |

Predicted (first 5 of 10 rows):

| ID | SEX | Birthday |
|---|---|---|
| 444499 | M | 1954-01-24 |
| 912147 | F | 1975-02-17 |
| 1138737 | F | 1965-11-18 |
| 3182521 | M | 1952-10-16 |
| 3545964 | F | 1926-08-01 |

## 1225 / thrombosis_prediction / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The patient join, bilirubin filter, and grouping by sex match. The gold query lists distinct patient IDs using GROUP_CONCAT, while the prediction returns only their count, so the selected output differs.

Question:

```text
List and group all patients by sex for total bilirubin (T-BIL) level not within the normal range.
```

Evidence:

```text
List refers to GROUP_CONCAT(DISTINCT ID); total bilirubin (T-BIL) not within normal range refers to T-BIL > = 2.0
```

Gold SQL:

```sql
SELECT GROUP_CONCAT(DISTINCT T1.ID),T1.SEX FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-BIL` >= 2.0 GROUP BY T1.SEX
```

Predicted SQL:

```sql
SELECT T1.SEX, COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-BIL` >= 2.0 GROUP BY T1.SEX
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| GROUP_CONCAT(DISTINCT T1.ID) | SEX |
|---|---|
| 250391,1180510,2308236,2931207,4862013 | F |
| 43003,444499,1137040,2307640,4618443 | M |

Predicted (first 2 of 2 rows):

| SEX | COUNT(DISTINCT T1.ID) |
|---|---|
| F | 5 |
| M | 5 |

## 1227 / thrombosis_prediction / moderate

Label: `date_handling` (classifier, gpt-6-luna): The gold query calculates age as the difference between calendar years, while the prediction calculates elapsed days divided by 365.25 and truncates to an integer. This produces a different average age (71.6 versus 71.95).

Question:

```text
What is the average age of the male patient with high cholesterol?
```

Evidence:

```text
average age = DIVIDE(SUM(SUBTRACT(YEAR(NOW()), YEAR(birthday))), COUNT(ID)); male patient refers to sex = 'M'; high cholesterol refers to "T-CHO" > = 250;
```

Gold SQL:

```sql
SELECT AVG(age) FROM (SELECT DISTINCT T1.ID, STRFTIME('%Y', date('NOW')) - STRFTIME('%Y', T1.Birthday) as age FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2."T-CHO" >= 250 AND T1.SEX = 'M')
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT DISTINCT T1.ID, T1.Birthday FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M' AND T2.`T-CHO` >= 250) SELECT AVG(CAST((JULIANDAY('now') - JULIANDAY(T1.Birthday)) / 365.25 AS INTEGER)) FROM cte1 AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(age) |
|---|
| 71.95 |

Predicted (first 1 of 1 rows):

| AVG(CAST((JULIANDAY('now') - JULIANDAY(… |
|---|
| 71.6 |

## 1241 / thrombosis_prediction / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query uses strict thresholds, PLT < 100 and PLT > 400, while the prediction uses inclusive thresholds, PLT <= 100 and PLT >= 400. This adds patients exactly at the cutoff (reflected in the low-count difference).

Question:

```text
For patients with abnormal platelet level, state the number of patients with lower than normal range. How is it compare to the number of patients with higher than normal range?
```

Evidence:

```text
platelet level lower than normal range refers to PLT < 100; calculation = SUBTRACT(SUM(PLT < 100), SUM(PLT > 400)); platelet level higher than normal range refers to PLT > 400;
```

Gold SQL:

```sql
SELECT (SELECT COUNT(DISTINCT ID) FROM Laboratory WHERE PLT < 100) AS low_count, (SELECT COUNT(DISTINCT ID) FROM Laboratory WHERE PLT > 400) AS high_count;
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT CASE WHEN T1.PLT <= 100 THEN T1.ID END), COUNT(DISTINCT CASE WHEN T1.PLT >= 400 THEN T1.ID END) FROM Laboratory AS T1 WHERE T1.PLT <= 100 OR T1.PLT >= 400
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| low_count | high_count |
|---|---|
| 36 | 82 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT CASE WHEN T1.PLT <= 100 … | COUNT(DISTINCT CASE WHEN T1.PLT >= 400 … |
|---|---|
| 37 | 82 |

## 1242 / thrombosis_prediction / challenging

Label: `date_handling` (classifier, gpt-6-luna): The gold query calculates age from the current year, while the prediction compares each patient’s birthday with the examination date minus 50 years. The prediction also excludes platelet values exactly at 100 and 400, but the age-date difference appears first.

Question:

```text
For laboratory examinations take in 1984, list all patients below 50 years old with normal platelet level.
```

Evidence:

```text
laboratory examinations take in 1984 refers to YEAR(Date) = '1984'; below 50 years old = SUBTRACT(year(current_timestamp), year(Birthday)) < 50; normal platelet level refers to PLT between 100 and 400; 
```

Gold SQL:

```sql
SELECT DISTINCT T1.ID FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.PLT BETWEEN 100 AND 400 AND STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T1.Birthday) < 50 AND STRFTIME('%Y', T2.Date) = '1984'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.ID FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE STRFTIME('%Y', T2.Date) = '1984' AND T1.Birthday > DATE(T2.Date, '-50 years') AND T2.PLT > 100 AND T2.PLT < 400
```

Result diff:

Gold 5 rows, predicted 76 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 5 rows):

| ID |
|---|
| 102490 |
| 460574 |
| 1086485 |
| 2047892 |
| 3173679 |

Predicted (first 5 of 76 rows):

| ID |
|---|
| 30609 |
| 48473 |
| 52199 |
| 58139 |
| 81043 |

## 1243 / thrombosis_prediction / challenging

Label: `date_handling` (classifier, gpt-6-luna): The gold query defines age as the difference between calendar years, while the prediction computes elapsed days divided by 365.25, which can classify patients near the age cutoff differently. Both queries otherwise restrict the denominator and numerator to records with PT >= 14.

Question:

```text
For all patients who are older than 55 years old, what is the percentage of those with abnormal prothrombin time (PT) that are female?
```

Evidence:

```text
older than 55 years old = SUBTRACT(year(current_timestamp), year(Birthday)) > 55; abnormal prothrombin time (PT) refers to PT > = 14; percentage = DIVIDE(SUM(PT > = 14 AND SEX = 'F'), SUM(PT > = 14)) * 100; female refers to sex = 'F';
```

Gold SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T2.PT >= 14 AND T1.SEX = 'F' THEN T1.ID END) AS REAL) * 100 / COUNT(DISTINCT CASE WHEN T2.PT >= 14 THEN T1.ID END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T1.Birthday) > 55
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T1.SEX = 'F' THEN T1.ID END) AS REAL) * 100 / COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE (JULIANDAY(CURRENT_DATE) - JULIANDAY(T1.Birthday)) / 365.25 > 55 AND T2.PT >= 14
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.PT >= … |
|---|
| 72.72727272727273 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T1.SEX = … |
|---|
| 75.0 |

## 1256 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query matches abnormal CRP using `T2.CRP = '+'`, while the prediction uses a numeric cast and `>= 1.0`. It also broadens the missing-description condition from `IS NULL` to include empty strings.

Question:

```text
How many patients with a abnormal C-reactive protein don't have their data recorded?
```

Evidence:

```text
abnormal C-reactive protein refers to CRP ='+'; don't have data recorded refers to Description IS NULL;
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE (T2.CRP = '+') AND T1.Description IS NULL
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE CAST(T2.CRP AS REAL) >= 1.0 AND (T1.Description IS NULL OR T1.Description = '')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 25 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 38 |

## 1267 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The evidence maps normal anti-SM to `SM` values `'negative'` and `'0'`, but the prediction filters for `'-'` and `'+' \|\| '-'` (which evaluates to `'+-'`). It also tests thrombosis per examination row rather than requiring no thrombosis across a patient's examinations, but the first difference is the incorrect SM filter values.

Question:

```text
Among the patients with normal anti-SM, how many of them does not have thrombosis?
```

Evidence:

```text
normal anti-SM refers to SM IN('-', '+-'); SM = 'negative' means '-'; SM = '0' means '+-'; SM = '1' means '+'; does not have thrombosis refers to Thrombosis = 0;
```

Gold SQL:

```sql
WITH normal_sm AS (
  SELECT DISTINCT `ID`
  FROM `Laboratory`
  WHERE `SM` IN ('negative','0')
), no_thrombosis AS (
  SELECT n.`ID`
  FROM normal_sm n
  JOIN `Examination` e ON e.`ID` = n.`ID`
  GROUP BY n.`ID`
  HAVING MAX(COALESCE(e.`Thrombosis`,0)) = 0
)
SELECT COUNT(*)
FROM no_thrombosis;
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Laboratory AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.SM IN ('-', '+' || '-') AND T2.Thrombosis = 0
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 6 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 0 |

## 1275 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters CENTROMEA and SSB for ('negative', '0'), while the prediction uses ('-', '+-'), which excludes the intended normal values and produces a different count.

Question:

```text
Among the patients who has a normal level of anti-centromere and a normal level of anti-SSB, how many of them are male?
```

Evidence:

```text
normal level of anti-centromere refers to CENTROMEA IN('negative', '0'); normal level of anti-SSB refers to SSB IN('negative', '0'); male refers to Sex = 'M'; Should consider DISTINCT in the final result;
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.CENTROMEA IN ('negative', '0') AND T2.SSB IN ('negative', '0') AND T1.SEX = 'M'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M' AND T2.CENTROMEA IN ('-', '+' || '-') AND T2.SSB IN ('-', '+' || '-')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 1 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 0 |

## 1387 / student_club / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s `T4.position = 'Treasurer'` condition, so it includes an additional student who is associated with the event but is not the designated treasurer.

Question:

```text
Which student has been entrusted to manage the budget for the Yearly Kickoff?
```

Evidence:

```text
name of students means the full name; full name refers to first_name, last_name;'Yearly Kickoff' is an event name;
```

Gold SQL:

```sql
SELECT T4.first_name, T4.last_name FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event INNER JOIN expense AS T3 ON T2.budget_id = T3.link_to_budget INNER JOIN member AS T4 ON T3.link_to_member = T4.member_id WHERE T1.event_name = 'Yearly Kickoff' AND T4.position = 'Treasurer';
```

Predicted SQL:

```sql
SELECT DISTINCT T1.first_name, T1.last_name FROM member AS T1 INNER JOIN expense AS T2 ON T1.member_id = T2.link_to_member INNER JOIN budget AS T3 ON T2.link_to_budget = T3.budget_id INNER JOIN event AS T4 ON T3.link_to_event = T4.event_id WHERE T4.event_name = 'Yearly Kickoff'
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 0 rows only in gold, 1 only in predicted.

Gold (first 2 of 2 rows):

| first_name | last_name |
|---|---|
| Elijah | Allen |
| Elijah | Allen |

Predicted (first 2 of 2 rows):

| first_name | last_name |
|---|---|
| Sacha | Harrison |
| Elijah | Allen |

## 1389 / student_club / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold orders individual expense rows by `T3.cost`, while the prediction groups by event and orders by `SUM(T3.cost)`. This changes the meaning from the lowest cost to the lowest total cost per event.

Question:

```text
Which event has the lowest cost? Break ties by name in alphabetical order.
```

Evidence:

```text
event refers to event_name; lowest cost means MIN(cost)
```

Gold SQL:

```sql
SELECT T1.event_name FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event INNER JOIN expense AS T3 ON T2.budget_id = T3.link_to_budget ORDER BY T3.cost, T1.event_name LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.event_name FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event INNER JOIN expense AS T3 ON T2.budget_id = T3.link_to_budget WHERE T3.cost IS NOT NULL GROUP BY T1.event_id, T1.event_name ORDER BY SUM(T3.cost) ASC, T1.event_name ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| event_name |
|---|
| November Speaker |

Predicted (first 1 of 1 rows):

| event_name |
|---|
| Officers meeting - November |

## 1490 / debit_card_specializing / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold counts distinct LAM customers in both numerator and denominator, while the prediction counts matching yearmonth rows with SUM and COUNT(*). This computes a percentage of records rather than customers.

Question:

```text
How many percent of LAM customer consumed more than 46.73?
```

Evidence:

```text
Percentage of LAM customer consumed more than 46.73 = (Total no. of LAM customers who consumed more than 46.73 / Total no. of LAM customers) * 100.
```

Gold SQL:

```sql
SELECT CAST(COUNT(DISTINCT IIF(T2.Consumption > 46.73, T1.CustomerID, NULL)) AS REAL) * 100 / COUNT(DISTINCT T1.CustomerID) FROM customers AS T1 LEFT JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Segment = 'LAM'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.Consumption > 46.73 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Segment = 'LAM'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT IIF(T2.Consumption … |
|---|
| 98.25041006014216 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.Consumption > 46.… |
|---|
| 98.5267932135058 |

## 1498 / debit_card_specializing / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query sums consumption by month and selects the largest monthly total. The prediction instead orders individual Consumption rows and returns the largest single value, omitting the monthly GROUP BY and SUM.

Question:

```text
What is the highest monthly consumption in the year 2012?
```

Evidence:

```text
The first 4 strings of the Date values in the yearmonth table can represent year; The 5th and 6th string of the date can refer to month.
```

Gold SQL:

```sql
SELECT SUM(Consumption) FROM yearmonth WHERE SUBSTR(Date, 1, 4) = '2012' GROUP BY SUBSTR(Date, 5, 2) ORDER BY SUM(Consumption) DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.Consumption FROM yearmonth AS T1 WHERE SUBSTR(T1.Date, 1, 4) = '2012' ORDER BY T1.Consumption DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(Consumption) |
|---|
| 51787161.74 |

Predicted (first 1 of 1 rows):

| Consumption |
|---|
| 445279.69 |

## 1526 / debit_card_specializing / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query identifies the customer with `T1.Price = 634.8`, while the prediction filters on `T1.Amount * T1.Price = 634.8`. This different condition can select a different customer, so the consumption calculation may not match.

Question:

```text
For the customer who paid 634.8 in 2012/8/25, what was the consumption decrease rate from Year 2012 to 2013?
```

Evidence:

```text
'2012/8/24' can be represented by '2012-08-24'; Consumption decrease rate = (consumption_2012 - consumption_2013) / consumption_2012
```

Gold SQL:

```sql
SELECT CAST(SUM(IIF(SUBSTRING(Date, 1, 4) = '2012', Consumption, 0)) - SUM(IIF(SUBSTRING(Date, 1, 4) = '2013', Consumption, 0)) AS FLOAT) / SUM(IIF(SUBSTRING(Date, 1, 4) = '2012', Consumption, 0)) FROM yearmonth WHERE CustomerID = ( SELECT T1.CustomerID FROM transactions_1k AS T1 INNER JOIN gasstations AS T2 ON T1.GasStationID = T2.GasStationID WHERE T1.Date = '2012-08-25' AND T1.Price  = 634.8 )
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT DISTINCT T1.CustomerID FROM transactions_1k AS T1 WHERE T1.Date = '2012-08-25' AND T1.Amount * T1.Price = 634.8), cte2 AS (SELECT SUM(CASE WHEN SUBSTR(T1.Date, 1, 4) = '2012' THEN T1.Consumption ELSE 0 END) AS c1, SUM(CASE WHEN SUBSTR(T1.Date, 1, 4) = '2013' THEN T1.Consumption ELSE 0 END) AS c2 FROM yearmonth AS T1 INNER JOIN cte1 AS T2 ON T1.CustomerID = T2.CustomerID) SELECT CAST(T1.c1 - T1.c2 AS REAL) / T1.c1 FROM cte2 AS T1 INTERSECT SELECT CAST(T1.c1 - T1.c2 AS REAL) / T1.c1 FROM cte2 AS T1 LIMIT 1 OFFSET 0
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(SUBSTRING(Date, 1, 4) = '2… |
|---|
| -5.815242674672346 |

Predicted (first 1 of 1 rows):

| CAST(T1.c1 - T1.c2 AS REAL) / T1.c1 |
|---|
| None |
