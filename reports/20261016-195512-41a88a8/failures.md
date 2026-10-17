# Failures: best on bird_minidev / dev

121 of 350 questions failed. Evidence off, git `41a88a836fa385225e7737edd13ac9197637fa02`, complete: 350 questions.

## 11 / california_schools / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction filters only on `Enrollment (K-12) > 500`, while the gold query tests the sum of `Enrollment (K-12)` and `Enrollment (Ages 5-17)` against 500. It also omits the join to `schools`, but the enrollment condition is the key mismatch.

Gold label suspect: yes.

Question:

```text
Please list the codes of the schools with a total enrollment of over 500.
```

Evidence:

```text
Total enrollment can be represented by `Enrollment (K-12)` + `Enrollment (Ages 5-17)`
```

Gold SQL:

```sql
SELECT T2.CDSCode FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.`Enrollment (K-12)` + T2.`Enrollment (Ages 5-17)` > 500
```

Predicted SQL:

```sql
SELECT T1.CDSCode FROM frpm AS T1 WHERE T1.`Enrollment (K-12)` > 500
```

Result diff:

Gold 7806 rows, predicted 5362 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 5 of 7806 rows):

| CDSCode |
|---|
| 01100170109835 |
| 01100170112607 |
| 01100170124172 |
| 01100170125567 |
| 01100176001788 |

Predicted (first 5 of 5362 rows):

| CDSCode |
|---|
| 01100170109835 |
| 01100176001788 |
| 01611190111765 |
| 01611190122085 |
| 01611190130229 |

## 17 / california_schools / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters out rows where `CharterNum` is null, but the prediction omits that condition, producing many extra rows. The prediction also selects different output columns, but the missing filter is the first substantive difference.

Question:

```text
Rank schools by their average score in Writing where the score is greater than 499, showing their charter numbers.
```

Evidence:

```text
Valid charter number means the number is not null
```

Gold SQL:

```sql
SELECT CharterNum, AvgScrWrite, RANK() OVER (ORDER BY AvgScrWrite DESC) AS WritingScoreRank FROM schools AS T1  INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T2.AvgScrWrite > 499 AND CharterNum is not null
```

Predicted SQL:

```sql
SELECT T1.sname, T2.CharterNum FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T1.AvgScrWrite > 499 ORDER BY T1.AvgScrWrite DESC
```

Result diff:

Gold 58 rows, predicted 500 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 58 rows):

| CharterNum | AvgScrWrite | WritingScoreRank |
|---|---|---|
| 0210 | 630 | 1 |
| 0890 | 593 | 2 |
| 0290 | 582 | 3 |
| 0352 | 581 | 4 |
| 0930 | 579 | 5 |

Predicted (first 5 of 500 rows):

| sname | CharterNum |
|---|---|
| Mission San Jose High | None |
| Lynbrook High | None |
| Whitney (Gretchen) High | None |
| Monta Vista High | None |
| Saratoga High | None |

## 25 / california_schools / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query gets the school name and funding type from `satscores` and `frpm`, while the prediction selects `School` and `FundingType` from `schools`. The prediction therefore reads different columns and a different source for funding type.

Question:

```text
Name schools in Riverside which the average of average math score for SAT is grater than 400, what is the funding type of these schools?
```

Evidence:

```text
Average of average math = sum(average math scores) / count(schools).
```

Gold SQL:

```sql
SELECT T1.sname, T2.`Charter Funding Type` FROM satscores AS T1 INNER JOIN frpm AS T2 ON T1.cds = T2.CDSCode WHERE T2.`District Name` LIKE 'Riverside%' GROUP BY T1.sname, T2.`Charter Funding Type` HAVING CAST(SUM(T1.AvgScrMath) AS REAL) / COUNT(T1.cds) > 400
```

Predicted SQL:

```sql
SELECT T1.School, T1.FundingType FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.County = 'Riverside' GROUP BY T1.School, T1.FundingType HAVING AVG(T2.AvgScrMath) > 400
```

Result diff:

Gold 6 rows, predicted 60 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 5 of 6 rows):

| sname | Charter Funding Type |
|---|---|
| Arlington High | None |
| John W. North High | None |
| Martin Luther King Jr. High | None |
| Polytechnic High | None |
| Ramona High | None |

Predicted (first 5 of 60 rows):

| School | FundingType |
|---|---|
| None | None |
| Arlington High | None |
| Banning High | None |
| Beaumont Senior High | None |
| California Military Institute | Locally funded |

## 26 / california_schools / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

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
SELECT T1.`School Name`, T2.Street, T2.City, T2.State, T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.County = 'Monterey' AND T1.`Free Meal Count (Ages 5-17)` > 800 AND T1.`School Type` = 'High Schools (Public)'
```

Predicted SQL:

```sql
SELECT T1.School, T1.MailStreet, T1.MailCity, T1.MailState, T1.MailZip FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.`County Name` = 'Monterey' AND T2.`School Type` = 'High Schools (Public)' AND T2.`FRPM Count (Ages 5-17)` > 800
```

Result diff:

Gold 5 rows, predicted 6 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 5 rows):

| School Name | Street | City | State | Zip |
|---|---|---|---|---|
| Alisal High | 777 Williams Road | Salinas | CA | 93905-1907 |
| Everett Alvarez High | 1900 Independence Boulevard | Salinas | CA | 93906-5300 |
| North Salinas High | 55 Kip Drive | Salinas | CA | 93906-2908 |
| Salinas High | 726 South Main Street | Salinas | CA | 93901-3243 |
| Soledad High | 425 Gabilan Drive | Soledad | CA | 93960-3207 |

Predicted (first 5 of 6 rows):

| School | MailStreet | MailCity | MailState | MailZip |
|---|---|---|---|---|
| Alisal High | 777 Williams Road | Salinas | CA | 93905-1907 |
| Everett Alvarez High | 1900 Independence Boulevard | Salinas | CA | 93906-5300 |
| North Salinas High | 55 Kip Drive | Salinas | CA | 93906-2908 |
| Salinas High | 726 South Main Street | Salinas | CA | 93901-3243 |
| North Monterey County High | 13990 Castroville Boulevard | Castroville | CA | 95012-9749 |

## 27 / california_schools / moderate

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction uses an INNER JOIN, while the gold query uses a LEFT JOIN from schools to satscores. This excludes schools without a matching SAT score and changes the result rows.

Question:

```text
What is the average score in writing for the schools that were opened after 1991 or closed before 2000? List the school names along with the score. Also, list the communication number of the schools if there is any.
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

Gold 8574 rows, predicted 813 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 5 of 8574 rows):

| School | AvgScrWrite | Phone |
|---|---|---|
| FAME Public Charter | 505 | None |
| Envision Academy for Arts & Technology | 395 | (510) 596-8901 |
| Aspire California College Preparatory A… | None | None |
| Community School for Creative Education | None | (510) 686-4131 |
| Yu Ming Charter | None | (510) 452-2063 |

Predicted (first 5 of 813 rows):

| School | AvgScrWrite | Phone |
|---|---|---|
| FAME Public Charter | 505 | None |
| Envision Academy for Arts & Technology | 395 | (510) 596-8901 |
| Aspire California College Preparatory A… | None | None |
| Alameda Science and Technology Institute | 555 | (510) 748-4021 |
| Nea Community Learning Center | None | (510) 748-4008 |

## 41 / california_schools / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
List the names of virtual schools that are among the top 5 in their respective counties based on average reading scores.
```

Evidence:

```text
Exclusively virtual refers to Virtual = 'F'; respective counties means PARTITION BY County
```

Gold SQL:

```sql
SELECT School FROM (SELECT T2.School,T1.AvgScrRead, RANK() OVER (PARTITION BY T2.County ORDER BY T1.AvgScrRead DESC) AS rnk FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T2.Virtual = 'F' ) ranked_schools WHERE rnk <= 5
```

Predicted SQL:

```sql
SELECT T1.School FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.`Virtual` = 'F' AND T2.rtype = 'S' AND T2.AvgScrRead IS NOT NULL AND (SELECT COUNT(*) FROM satscores AS T3 WHERE T3.cname = T2.cname AND T3.rtype = 'S' AND T3.AvgScrRead > T2.AvgScrRead) < 5
```

Result diff:

Gold 34 rows, predicted 1 rows. Within the previews: 5 rows only in gold, 1 only in predicted.

Gold (first 5 of 34 rows):

| School |
|---|
| Dunlap Leadership Academy |
| Academy of Arts and Sciences: Fresno |
| Insight School of California |
| California Virtual Academy @ Kings |
| National University Academy, Armona |

Predicted (first 1 of 1 rows):

| School |
|---|
| California Connections Academy @ Ripon |

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

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query calculates `Free Meal Count (K-12) * 100 / Enrollment (K-12)`, while the prediction selects the stored `Percent (%) Eligible Free (K-12)` column, yielding 0.7015 instead of 70.1511. The prediction also broadens the administrator filter to names 2 and 3, but the SELECT mismatch is the first difference to fix.

Question:

```text
What is the Percent (%) Eligible Free (K-12) in the school administered by an administrator whose first name is Alusine. List the district code of the school.
```

Evidence:

```text
Percent (%) Eligible Free (K-12) = `Free Meal Count (K-12)` / `Enrollment (K-12)` * 100%
```

Gold SQL:

```sql
SELECT T1.`Free Meal Count (K-12)` * 100 / T1.`Enrollment (K-12)`, T1.`District Code` FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.AdmFName1 = 'Alusine'
```

Predicted SQL:

```sql
SELECT T1.`Percent (%) Eligible Free (K-12)`, T1.`District Code` FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.AdmFName1 = 'Alusine' OR T2.AdmFName2 = 'Alusine' OR T2.AdmFName3 = 'Alusine'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| T1.`Free Meal Count (K-12)` * 100 / T1.… | District Code |
|---|---|
| 70.15113350125945 | 64857 |

Predicted (first 1 of 1 rows):

| Percent (%) Eligible Free (K-12) | District Code |
|---|---|
| 0.701511335012594 | 64857 |

## 87 / california_schools / challenging

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The prediction filters on District, SOCType, and DOCType instead of the gold query’s City, SOC, and DOC columns. It also omits AdmEmail2, but the differing filter columns are the first issue to fix.

Question:

```text
What are the valid e-mail addresses of the administrator of the school located in the San Bernardino county, City of San Bernardino City Unified that opened between 1/1/2009 to 12/31/2010 whose school types are public Intermediate/Middle Schools and Unified Schools?
```

Evidence:

```text
Intermediate/Middle Schools refers to SOC = 62; Unified School refers to DOC = 54; years between 2009 and 2010 can refer to 'between 1/1/2009 to 12/31/2010'
```

Gold SQL:

```sql
SELECT T2.AdmEmail1, T2.AdmEmail2 FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.County = 'San Bernardino' AND T2.City = 'San Bernardino' AND T2.DOC = 54 AND strftime('%Y', T2.OpenDate) BETWEEN '2009' AND '2010' AND T2.SOC = 62
```

Predicted SQL:

```sql
SELECT T1.AdmEmail1 FROM schools AS T1 WHERE T1.County = 'San Bernardino' AND T1.District = 'San Bernardino City Unified' AND T1.OpenDate BETWEEN '2009-01-01' AND '2010-12-31' AND T1.SOCType = 'Intermediate/Middle Schools (Public)' AND T1.DOCType = 'Unified School District' AND T1.AdmEmail1 IS NOT NULL
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AdmEmail1 | AdmEmail2 |
|---|---|
| a.lucero@realjourney.org | j.hernandez@realjourney.org |

Predicted (first 1 of 1 rows):

| AdmEmail1 |
|---|
| a.lucero@realjourney.org |

## 94 / financial / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The gold query selects accounts in the district of the oldest female client and then orders by the district’s A11 descending; it does not identify the oldest female client with the lowest average salary as the question asks. The prediction instead filters female clients and ranks by birth date and A11, so the gold query appears to encode a different task.

Gold label suspect: yes.

Question:

```text
List out the account numbers of female clients who are oldest and has lowest average salary, calculate the gap between this lowest average salary with the highest average salary?
```

Evidence:

```text
Female means gender = 'F'; A11 refers to average salary; Gap = highest average salary - lowest average salary; If the person A's birthdate > B's birthdate, it means that person B is order than person A.
```

Gold SQL:

```sql
SELECT T1.account_id , ( SELECT MAX(A11) - MIN(A11) FROM district ) FROM account AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id INNER JOIN disp AS T3 ON T1.account_id = T3.account_id INNER JOIN client AS T4 ON T3.client_id = T4.client_id WHERE T2.district_id = ( SELECT district_id FROM client WHERE gender = 'F' ORDER BY birth_date ASC LIMIT 1 ) ORDER BY T2.A11 DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.account_id, (SELECT MAX(T4.A11) FROM district AS T4) - T3.A11 AS c1 FROM disp AS T1 INNER JOIN client AS T2 ON T1.client_id = T2.client_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T2.gender = 'F' AND T2.birth_date IS NOT NULL AND T3.A11 IS NOT NULL ORDER BY T2.birth_date ASC, T3.A11 ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| account_id | ( SELECT MAX(A11) - MIN(A11) FROM distr… |
|---|---|
| 6 | 4431 |

Predicted (first 1 of 1 rows):

| account_id | c1 |
|---|---|
| 1743 | 4000 |

## 125 / financial / challenging

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction adds district name (`T3.A2`) to the SELECT list, while the gold query returns only the unemployment-rate increment. The added column also changes the DISTINCT result set.

Gold label suspect: yes.

Question:

```text
For loans contracts which are still running where client are in debt, list the district of the and the state the percentage unemployment rate increment from year 1995 to 1996.
```

Evidence:

```text
Unemployment increment rate in percentage = [(unemployment rate 2016 - unemployment rate 2015) / unemployment rate 2015] * 100; unemployment rate 2015 appears in the A12; unemployment rate 2016 appears in the A13; Loan contracts which are still running where client are in debt can be presented as status = 'D'
```

Gold SQL:

```sql
SELECT CAST((T3.A13 - T3.A12) AS REAL) * 100 / T3.A12 FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.status = 'D'
```

Predicted SQL:

```sql
SELECT DISTINCT T3.A2, CAST(T3.A13 - T3.A12 AS REAL) * 100 / T3.A12 FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.status = 'D'
```

Result diff:

Gold 45 rows, predicted 30 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 45 rows):

| CAST((T3.A13 - T3.A12) AS REAL) * 100 /… |
|---|
| 40.0 |
| 39.25925925925924 |
| 115.0 |
| 22.49999999999999 |
| 20.0 |

Predicted (first 5 of 30 rows):

| A2 | CAST(T3.A13 - T3.A12 AS REAL) * 100 / T… |
|---|---|
| Strakonice | 40.0 |
| Chrudim | 39.25925925925924 |
| Hl.m. Praha | 115.0 |
| Brno - mesto | 22.49999999999999 |
| Mlada Boleslav | 20.0 |

## 129 / financial / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The gold query returns distinct district names alphabetically, so it does not identify the top ten withdrawals. The prediction ranks transactions by amount, though it also does not aggregate withdrawals by district.

Gold label suspect: yes.

Question:

```text
Which are the top ten withdrawals (non-credit card) by district names for the month of January 1996?
```

Evidence:

```text
Non-credit card withdraws refers to type = 'VYDAJ'; January 1996 can be found by date LIKE '1996-01%' in the database; A2 means district names
```

Gold SQL:

```sql
SELECT DISTINCT T1.A2 FROM district AS T1 INNER JOIN account AS T2 ON T1.district_id = T2.district_id INNER JOIN trans AS T3 ON T2.account_id = T3.account_id WHERE T3.type = 'VYDAJ' AND T3.date LIKE '1996-01%' ORDER BY A2 ASC LIMIT 10
```

Predicted SQL:

```sql
SELECT T3.A2, T1.amount FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.type = 'VYDAJ' AND T1.operation <> 'VYBER KARTOU' AND STRFTIME('%Y-%m', T1.date) = '1996-01' ORDER BY T1.amount DESC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| A2 |
|---|
| Benesov |
| Beroun |
| Blansko |
| Breclav |
| Brno - mesto |

Predicted (first 5 of 10 rows):

| A2 | amount |
|---|---|
| Trutnov | 63700 |
| Pelhrimov | 59600 |
| Zlin | 59400 |
| Olomouc | 57900 |
| Frydek - Mistek | 56700 |

## 145 / financial / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The predicted query computes the comparison average over all transactions, while the gold query restricts that average to transactions in 1998. This changes which account IDs qualify.

Question:

```text
Who are the account holder identification numbers whose who have transactions on the credit card with the amount is less than the average, in 1998?
```

Evidence:

```text
Operation = 'VYBER KARTOU' refers to credit card withdrawal
```

Gold SQL:

```sql
SELECT T1.account_id FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id WHERE STRFTIME('%Y', T1.date) = '1998' AND T1.operation = 'VYBER KARTOU' AND T1.amount < (SELECT AVG(amount) FROM trans WHERE STRFTIME('%Y', date) = '1998')
```

Predicted SQL:

```sql
SELECT DISTINCT T1.account_id FROM trans AS T1 WHERE T1.operation = 'VYBER KARTOU' AND T1.amount < (SELECT AVG(T2.amount) FROM trans AS T2) AND STRFTIME('%Y', T1.date) = '1998'
```

Result diff:

Gold 4484 rows, predicted 800 rows. Within the previews: 0 rows only in gold, 4 only in predicted.

Gold (first 5 of 4484 rows):

| account_id |
|---|
| 14 |
| 14 |
| 14 |
| 14 |
| 14 |

Predicted (first 5 of 800 rows):

| account_id |
|---|
| 7 |
| 14 |
| 33 |
| 34 |
| 43 |

## 168 / financial / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction filters the district associated with each account through `disp` and `account`, matching the question’s reference to where clients opened their accounts. The gold query instead filters on `client.district_id`, which identifies the client’s district rather than the account’s district.

Question:

```text
What percentage of clients who opened their accounts in the district with an average salary of over 10000 are women?
```

Evidence:

```text
Female refers to gender = 'F'; Woman and female are closed; Average salary can be found in A11
```

Gold SQL:

```sql
SELECT CAST(SUM(T2.gender = 'F') AS REAL) * 100 / COUNT(T2.client_id) FROM district AS T1 INNER JOIN client AS T2 ON T1.district_id = T2.district_id WHERE T1.A11 > 10000
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T1.gender = 'F' THEN T1.client_id END) AS REAL) * 100 / COUNT(DISTINCT T1.client_id) FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id INNER JOIN district AS T4 ON T3.district_id = T4.district_id WHERE T4.A11 > 10000
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(T2.gender = 'F') AS REAL) * 10… |
|---|
| 49.609984399375975 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T1.gender… |
|---|
| 50.38819875776397 |

## 169 / financial / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query restricts dispositions to `T3.type = 'OWNER'`, but the prediction omits that condition, so it also counts loans associated with non-owner dispositions.

Question:

```text
What was the growth rate of the total amount of loans across all accounts for a male client between 1996 and 1997?
```

Evidence:

```text
Growth rate = (sum of amount_1997 - sum of amount_1996) / (sum of amount_1996) * 100%; Male refers to gender = 'M'
```

Gold SQL:

```sql
SELECT CAST((SUM(CASE WHEN STRFTIME('%Y', T1.date) = '1997' THEN T1.amount ELSE 0 END) - SUM(CASE WHEN STRFTIME('%Y', T1.date) = '1996' THEN T1.amount ELSE 0 END)) AS REAL) * 100 / SUM(CASE WHEN STRFTIME('%Y', T1.date) = '1996' THEN T1.amount ELSE 0 END) FROM loan AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN disp AS T3 ON T3.account_id = T2.account_id INNER JOIN client AS T4 ON T4.client_id = T3.client_id WHERE T4.gender = 'M' AND T3.type = 'OWNER'
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT SUM(CASE WHEN STRFTIME('%Y', T1.date) = '1996' THEN T1.amount ELSE 0 END) AS c1, SUM(CASE WHEN STRFTIME('%Y', T1.date) = '1997' THEN T1.amount ELSE 0 END) AS c2 FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE T3.gender = 'M') SELECT CAST(T1.c2 - T1.c1 AS REAL) * 100 / T1.c1 FROM cte1 AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST((SUM(CASE WHEN STRFTIME('%Y', T1.d… |
|---|
| 25.300191222790616 |

Predicted (first 1 of 1 rows):

| CAST(T1.c2 - T1.c1 AS REAL) * 100 / T1.… |
|---|
| 25.36203967738821 |

## 197 / toxicology / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Calculate the average number of oxygen atoms in single-bonded molecules.
```

Evidence:

```text
single-bonded molecules refers to bond_type = '-' ; average number of oxygen atom = AVG(element = 'o')
```

Gold SQL:

```sql
SELECT AVG(oxygen_count) FROM (SELECT T1.molecule_id, COUNT(T1.element) AS oxygen_count FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id  WHERE T2.bond_type = '-' AND T1.element = 'o'  GROUP BY T1.molecule_id) AS oxygen_counts
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT DISTINCT T1.molecule_id FROM bond AS T1 WHERE T1.bond_type = '-'), cte2 AS (SELECT COUNT(T2.atom_id) AS c1 FROM cte1 AS T1 LEFT JOIN atom AS T2 ON T1.molecule_id = T2.molecule_id AND T2.element = 'o' GROUP BY T1.molecule_id) SELECT AVG(T1.c1) FROM cte2 AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(oxygen_count) |
|---|
| 99.68354430379746 |

Predicted (first 1 of 1 rows):

| AVG(T1.c1) |
|---|
| 2.161290322580645 |

## 207 / toxicology / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What elements are in a double type bond?
```

Evidence:

```text
double type bond refers to bond_type = '=';
```

Gold SQL:

```sql
SELECT DISTINCT T1.element FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id INNER JOIN connected AS T3 ON T1.atom_id = T3.atom_id WHERE T2.bond_type = '='
```

Predicted SQL:

```sql
SELECT DISTINCT T1.element FROM atom AS T1 INNER JOIN connected AS T2 ON T1.atom_id = T2.atom_id OR T1.atom_id = T2.atom_id2 INNER JOIN bond AS T3 ON T2.bond_id = T3.bond_id WHERE T3.bond_type = '='
```

Result diff:

Gold 13 rows, predicted 5 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 5 of 13 rows):

| element |
|---|
| c |
| o |
| cl |
| h |
| s |

Predicted (first 5 of 5 rows):

| element |
|---|
| c |
| o |
| n |
| s |
| ca |

## 218 / toxicology / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

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
SELECT CAST(COUNT(DISTINCT CASE WHEN T1.element <> 'f' THEN T2.molecule_id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT T2.molecule_id) FROM atom AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.label = '+'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN NOT EXISTS(SELECT T2.atom_id FROM atom AS T2 WHERE T2.molecule_id = T1.molecule_id AND T2.element = 'f') THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM molecule AS T1 WHERE T1.label = '+'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T1.elemen… |
|---|
| 100.0 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN NOT EXISTS(SELECT T2… |
|---|
| 99.34210526315789 |

## 231 / toxicology / challenging

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction returns both `bond_type` and `label`, while the gold query returns only `bond_type`. The added label is needed to address the carcinogenicity part of the question, which the gold query omits, so the gold label is also suspect.

Question:

```text
Which bond type accounted for the majority of the bonds found in molecule TR010 and state whether or not this molecule is carcinogenic?
```

Evidence:

```text
TR010 is the molecule id; majority of the bond found refers to MAX(COUNT(bond_type)); 
```

Gold SQL:

```sql
SELECT T.bond_type FROM ( SELECT T1.bond_type, COUNT(T1.molecule_id) FROM bond AS T1  WHERE T1.molecule_id = 'TR010' GROUP BY T1.bond_type ORDER BY COUNT(T1.molecule_id) DESC LIMIT 1 ) AS T
```

Predicted SQL:

```sql
SELECT T1.bond_type, T2.label FROM bond AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T1.molecule_id = 'TR010' GROUP BY T1.bond_type, T2.label ORDER BY COUNT(T1.bond_id) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| bond_type |
|---|
| - |

Predicted (first 1 of 1 rows):

| bond_type | label |
|---|---|
| - | - |

## 234 / toxicology / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many bonds which involved atom 12 does molecule TR009 have?
```

Evidence:

```text
TR009 is the molecule id;  involved atom 12 refers to atom_id = 'TR009_12' or atom_id2 = 'TR009_12'
```

Gold SQL:

```sql
SELECT COUNT(T2.bond_id) FROM bond AS T1 INNER JOIN connected AS T2 ON T1.bond_id = T2.bond_id WHERE T1.molecule_id = 'TR009' AND T2.atom_id = T1.molecule_id || '_1' OR T2.atom_id2 = T1.molecule_id || '_2'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.bond_id) FROM bond AS T1 INNER JOIN connected AS T2 ON T1.bond_id = T2.bond_id WHERE T1.molecule_id = 'TR009' AND (T2.atom_id = 'TR009_12' OR T2.atom_id2 = 'TR009_12')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T2.bond_id) |
|---|
| 1041 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.bond_id) |
|---|
| 3 |

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

## 247 / toxicology / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
List all the elements of atoms that can not bond with any other atoms.
```

Evidence:

```text
 atoms cannot bond with other atoms means atom_id NOT in connected table;
```

Gold SQL:

```sql
SELECT DISTINCT T.element FROM atom AS T WHERE T.element NOT IN ( SELECT DISTINCT T1.element FROM atom AS T1 INNER JOIN connected AS T2 ON T1.atom_id = T2.atom_id )
```

Predicted SQL:

```sql
SELECT DISTINCT T1.element FROM atom AS T1 WHERE NOT EXISTS(SELECT T2.bond_id FROM connected AS T2 WHERE T2.atom_id = T1.atom_id OR T2.atom_id2 = T1.atom_id)
```

Result diff:

Gold 3 rows, predicted 5 rows. Within the previews: 0 rows only in gold, 2 only in predicted.

Gold (first 3 of 3 rows):

| element |
|---|
| na |
| zn |
| k |

Predicted (first 5 of 5 rows):

| element |
|---|
| na |
| cl |
| h |
| zn |
| k |

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

## 340 / card_games / simple

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): Both queries use the same table and filters, but the gold query returns `id` while the prediction returns `name`.

Question:

```text
Which are the cards that have incredibly powerful foils.
```

Evidence:

```text
incredibly poweful foils refers to cardKingdomFoilId is not null AND cardKingdomId is not null
```

Gold SQL:

```sql
SELECT id FROM cards WHERE cardKingdomFoilId IS NOT NULL AND cardKingdomId IS NOT NULL
```

Predicted SQL:

```sql
SELECT T1.name FROM cards AS T1 WHERE T1.cardKingdomFoilId IS NOT NULL AND T1.cardKingdomId IS NOT NULL
```

Result diff:

Gold 25061 rows, predicted 25061 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 25061 rows):

| id |
|---|
| 4 |
| 5 |
| 6 |
| 9 |
| 10 |

Predicted (first 5 of 25061 rows):

| name |
|---|
| Ballista Squad |
| Bandage |
| Beacon of Immortality |
| Cho-Manno, Revolutionary |
| Condemn |

## 341 / card_games / simple

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction filters for cards with a cardKingdomId but no cardKingdomFoilId, matching the evidence for cards available without powerful foils. The gold query instead requires cardKingdomId to be NULL and does not check cardKingdomFoilId.

Gold label suspect: yes.

Question:

```text
What are the borderless cards available without powerful foils?
```

Evidence:

```text
borderless' refers to borderColor; poweful foils refers to cardKingdomFoilId paired with cardKingdomId AND cardKingdomId is not null
```

Gold SQL:

```sql
SELECT id FROM cards WHERE borderColor = 'borderless' AND (cardKingdomId IS NULL OR cardKingdomId IS NULL)
```

Predicted SQL:

```sql
SELECT T1.name FROM cards AS T1 WHERE T1.borderColor = 'borderless' AND T1.cardKingdomId IS NOT NULL AND T1.cardKingdomFoilId IS NULL
```

Result diff:

Gold 67 rows, predicted 5 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 67 rows):

| id |
|---|
| 23004 |
| 25350 |
| 25355 |
| 25357 |
| 25359 |

Predicted (first 5 of 5 rows):

| name |
|---|
| Necrotic Ooze |
| Acidic Slime |
| Scavenging Ooze |
| The Mimeoplasm |
| Voidslime |

## 344 / card_games / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction adds `T1.availability LIKE '%paper%'`, a restriction not required by the question and absent from the gold query, which excludes matching banned mythic cards. It also selects `name` instead of `id`, but the extra filter is the first logic difference to fix.

Question:

```text
List all the mythic rarity print cards banned in gladiator format.
```

Evidence:

```text
mythic rarity printing refers to rarity = 'mythic'; card banned refers to status = 'Banned'; in gladiator format refers to format = 'gladiator';
```

Gold SQL:

```sql
SELECT DISTINCT T1.id FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T2.format = 'gladiator' AND T2.status = 'Banned' AND T1.rarity = 'mythic'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.name FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T1.rarity = 'mythic' AND T1.availability LIKE '%paper%' AND T2.format = 'gladiator' AND T2.status = 'Banned'
```

Result diff:

Gold 5 rows, predicted 2 rows. Within the previews: 5 rows only in gold, 2 only in predicted.

Gold (first 5 of 5 rows):

| id |
|---|
| 17983 |
| 18058 |
| 29523 |
| 38736 |
| 38737 |

Predicted (first 2 of 2 rows):

| name |
|---|
| Oko, Thief of Crowns |
| Nexus of Fate |

## 347 / card_games / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction filters on artist = 'Stephen Daniel', while the gold query uses 'Stephen Daniele'. This literal mismatch returns no rows instead of the matching cards.

Gold label suspect: yes.

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
SELECT T1.id, T2.text, T1.hasContentWarning FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE T1.artist = 'Stephen Daniele'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.name, T2.text, T1.hasContentWarning FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE T1.artist = 'Stephen Daniel'
```

Result diff:

Gold 23 rows, predicted 0 rows. Within the previews: 5 rows only in gold, 0 only in predicted.

Gold (first 5 of 23 rows):

| id | text | hasContentWarning |
|---|---|---|
| 29 | You can’t put an Aura card from your ha… | 0 |
| 3872 | This card now has Enchant Swamp, which … | 0 |
| 6651 | Cycling is an activated ability. Effect… | 0 |
| 6652 | Cycling is an activated ability. Effect… | 0 |
| 7950 | Cycling is an activated ability. Effect… | 0 |

Predicted (first 0 of 0 rows):

| name | text | hasContentWarning |
|---|---|---|

## 349 / card_games / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The gold SQL selects based on which artist has the most distinct promotional card UUIDs, not which card has the most rulings, so it does not answer the question. The prediction also omits the promotional-card filter, but that does not make the gold query valid.

Gold label suspect: yes.

Question:

```text
Name the card and artist with the most ruling information. Also state if the card is a promotional printing.
```

Evidence:

```text
with the most ruling information refers to Max(count(rulings.uuid)); the card is the promotional printing refers to isPromo = 1;
```

Gold SQL:

```sql
SELECT T1.name, T1.artist, T1.isPromo FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE T1.isPromo = 1 AND T1.artist = (SELECT artist FROM cards WHERE isPromo = 1 GROUP BY artist HAVING COUNT(DISTINCT uuid) = (SELECT MAX(count_uuid) FROM ( SELECT COUNT(DISTINCT uuid) AS count_uuid FROM cards WHERE isPromo = 1 GROUP BY artist ))) LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.name, T1.artist, T1.isPromo FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid GROUP BY T1.id, T1.name, T1.artist, T1.isPromo ORDER BY COUNT(T2.id) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| name | artist | isPromo |
|---|---|---|
| Serrated Arrows | John Avon | 1 |

Predicted (first 1 of 1 rows):

| name | artist | isPromo |
|---|---|---|
| Teferi's Protection | Chase Stone | 0 |

## 352 / card_games / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Calculate the percentage of the cards availabe in Chinese Simplified.
```

Evidence:

```text
Chinese Simplified' is the language; percentage = Divide(Sum(id where language = 'Chinese Simplified'), Count(id)) *100
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.language = 'Chinese Simplified' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT T2.uuid) AS REAL) * 100 / COUNT(DISTINCT T1.uuid) FROM cards AS T1 LEFT JOIN foreign_data AS T2 ON T1.uuid = T2.uuid AND T2.language = 'Chinese Simplified'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.language = 'Chine… |
|---|
| 8.773399659641314 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT T2.uuid) AS REAL) *… |
|---|
| 35.384182182957304 |

## 383 / card_games / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many of the banned cards are white border?
```

Evidence:

```text
banned card refers to status = 'Banned'; white border refers to borderColor = 'white';
```

Gold SQL:

```sql
SELECT COUNT(T1.id) FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T2.status = 'Banned' AND T1.borderColor = 'white'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.uuid) FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T2.status = 'Banned' AND T1.borderColor = 'white'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.id) |
|---|
| 258 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.uuid) |
|---|
| 89 |

## 391 / card_games / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query identifies Artifact cards with `originalType = 'Artifact'`, while the prediction filters `types LIKE '%Artifact%'`. That reads a different column and yields extra results.

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
SELECT DISTINCT T1.name FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.types LIKE '%Artifact%' AND T1.colors = 'B'
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

## 416 / card_games / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction filters only `T1.power IS NULL`, omitting the gold query’s `OR T1.power = '*'` condition. This changes which cards are included in the percentage.

Gold label suspect: yes.

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
SELECT CAST(SUM(CASE WHEN T2.language = 'French' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*'
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT T2.uuid) AS REAL) * 100 / COUNT(DISTINCT T1.uuid) FROM cards AS T1 LEFT JOIN foreign_data AS T2 ON T1.uuid = T2.uuid AND T2.language = 'French' WHERE T1.power IS NULL
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.language = 'Frenc… |
|---|
| 12.975290140452374 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT T2.uuid) AS REAL) *… |
|---|
| 47.85788923719958 |

## 469 / card_games / moderate

Label: `other` (classifier, gpt-6-luna): The join and name filter match, but the prediction changes the output logic: it also treats an empty `mtgoCode` as absent and returns `Yes`/`No` instead of the gold query’s `YES`/`NO`. These differences can make the result values unequal.

Gold label suspect: yes.

Question:

```text
Did the set of cards with "Angel of Mercy" appear on Magic: The Gathering Online?
```

Evidence:

```text
card set "Angel of Mercy" refers to name = 'Angel of Mercy'; appear on Magic: The Gathering Online refers to mtgoCode is NOT NULL and vice versa
```

Gold SQL:

```sql
SELECT IIF(T2.mtgoCode IS NOT NULL, 'YES', 'NO') FROM cards AS T1 INNER JOIN sets AS T2 ON T2.code = T1.setCode WHERE T1.name = 'Angel of Mercy'
```

Predicted SQL:

```sql
SELECT CASE WHEN T2.mtgoCode IS NOT NULL AND T2.mtgoCode != '' THEN 'Yes' ELSE 'No' END FROM cards AS T1 INNER JOIN sets AS T2 ON T1.setCode = T2.code WHERE T1.name = 'Angel of Mercy'
```

Result diff:

Gold 15 rows, predicted 15 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 15 rows):

| IIF(T2.mtgoCode IS NOT NULL, 'YES', 'NO… |
|---|
| YES |
| YES |
| YES |
| YES |
| YES |

Predicted (first 5 of 15 rows):

| CASE WHEN T2.mtgoCode IS NOT NULL AND T… |
|---|
| Yes |
| Yes |
| Yes |
| Yes |
| Yes |

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

## 473 / card_games / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction selects the raw `isForeignOnly` value (`0`), while the gold query converts it to the requested `YES`/`NO` answer. The join and card-name filter match.

Question:

```text
Is the set of cards with Adarkar Valkyrie only available outside the United States?
```

Evidence:

```text
card set Adarkar Valkyrie refers to name = 'Adarkar Valkyrie'; isForeignOnly = 1 means only available outside the United States;
```

Gold SQL:

```sql
SELECT IIF(isForeignOnly = 1, 'YES', 'NO') FROM cards AS T1 INNER JOIN sets AS T2 ON T2.code = T1.setCode WHERE T1.name = 'Adarkar Valkyrie'
```

Predicted SQL:

```sql
SELECT DISTINCT T2.isForeignOnly FROM cards AS T1 INNER JOIN sets AS T2 ON T1.setCode = T2.code WHERE T1.name = 'Adarkar Valkyrie'
```

Result diff:

Gold 5 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 5 rows):

| IIF(isForeignOnly = 1, 'YES', 'NO') |
|---|
| NO |
| NO |
| NO |
| NO |
| NO |

Predicted (first 1 of 1 rows):

| isForeignOnly |
|---|
| 0 |

## 484 / card_games / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Please list the Italian names of the cards in the set Coldsnap with the highest converted mana cost.
```

Evidence:

```text
card set Coldsnap refers to name = 'Coldsnap'; Italian refers to language = 'Italian'; highest converted mana cost refers to MAX(convertedManaCost)
```

Gold SQL:

```sql
SELECT T2.name FROM foreign_data AS T1 INNER JOIN cards AS T2 ON T2.uuid = T1.uuid INNER JOIN sets AS T3 ON T3.code = T2.setCode WHERE T3.name = 'Coldsnap' AND T1.language = 'Italian' ORDER BY T2.convertedManaCost DESC
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.uuid, T1.convertedManaCost FROM cards AS T1 INNER JOIN sets AS T2 ON T1.setCode = T2.code WHERE T2.name = 'Coldsnap') SELECT DISTINCT T2.name FROM cte1 AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T2.language = 'Italian' AND T1.convertedManaCost = (SELECT MAX(T3.convertedManaCost) FROM cte1 AS T3)
```

Result diff:

Gold 155 rows, predicted 12 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 5 of 155 rows):

| name |
|---|
| Sunscour |
| Commandeer |
| Jokulmorder |
| Rimefeather Owl |
| Herald of Leshrac |

Predicted (first 5 of 12 rows):

| name |
|---|
| Devastazione Solare |
| Requisire |
| Jokulmorder |
| Gufo Gelopiuma |
| Araldo di Leshrac |

## 530 / card_games / moderate

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query inner-joins all legalities, while the prediction left-joins only rows with status = 'Banned'. This changes which legality records contribute to the results; the prediction also returns raw status instead of the gold query’s conditional card-name-or-'NO' value.

Question:

```text
List all the frame styles and cards Allen Williams worked on and find any banned cards if there are any.
```

Evidence:

```text
frame styles refers to frameVersion; cards Allen Williams worked on refers to artist = 'Allen Williams'; banned cards refers to status = 'Banned'
```

Gold SQL:

```sql
SELECT DISTINCT T1.frameVersion, T1.name , IIF(T2.status = 'Banned', T1.name, 'NO') FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T1.artist = 'Allen Williams'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.frameVersion, T1.name, T2.status FROM cards AS T1 LEFT JOIN legalities AS T2 ON T1.uuid = T2.uuid AND T2.status = 'Banned' WHERE T1.artist = 'Allen Williams'
```

Result diff:

Gold 83 rows, predicted 83 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 83 rows):

| frameVersion | name | IIF(T2.status = 'Banned', T1.name, 'NO') |
|---|---|---|
| 1997 | Blinking Spirit | NO |
| 1997 | Kjeldoran Royal Guard | NO |
| 1997 | Enervate | NO |
| 1997 | Diminishing Returns | NO |
| 2003 | Blinking Spirit | NO |

Predicted (first 5 of 83 rows):

| frameVersion | name | status |
|---|---|---|
| 1997 | Blinking Spirit | None |
| 1997 | Kjeldoran Royal Guard | None |
| 1997 | Enervate | None |
| 1997 | Diminishing Returns | None |
| 2003 | Blinking Spirit | None |

## 557 / codebase_community / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Among the posts with a score of over 5, what is the percentage of them being owned by an elder user?
```

Evidence:

```text
score of over 5 refers to Score > 5; elder user refers to Age > 65; percentage = Divide (Count(Id where Age>65), Count(Id)) * 100
```

Gold SQL:

```sql
SELECT CAST(SUM(IIF(T2.Age > 65, 1, 0)) AS REAL) * 100 / COUNT(T1.Id) FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Score > 5
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.Age > 65 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.Id) FROM posts AS T1 LEFT JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Score > 5
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(T2.Age > 65, 1, 0)) AS REA… |
|---|
| 0.16899404073645824 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.Age > 65 THEN 1 E… |
|---|
| 0.16572176188399476 |

## 565 / codebase_community / moderate

Label: `other` (classifier, gpt-6-luna): Both queries use the same comment-to-post join and filters, and their conditions encode the same well-finished status. The SELECT expressions use different output labels: the gold returns “well-finished”/“NOT well-finished,” while the prediction returns “Yes”/“No.”

Gold label suspect: yes.

Question:

```text
User No.23853 gave a comment to a post at 9:08:18 on 2013/7/12, was that post well-finished?
```

Evidence:

```text
user no. 23853 refers to UserId = '23853'; at 9:08:18 on 2013/7/12 refers to CreationDate = '2013-07-12 09:08:18.0'; not well-finished refers to ClosedDate IS NULL and vice versa
```

Gold SQL:

```sql
SELECT IIF(T2.ClosedDate IS NULL, 'NOT well-finished', 'well-finished') AS resylt FROM comments AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id WHERE T1.UserId = 23853 AND T1.CreationDate = '2013-07-12 09:08:18.0'
```

Predicted SQL:

```sql
SELECT CASE WHEN T2.ClosedDate IS NOT NULL AND T2.ClosedDate != '' THEN 'Yes' ELSE 'No' END FROM comments AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id WHERE T1.UserId = 23853 AND T1.CreationDate = '2013-07-12 09:08:18.0'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| resylt |
|---|
| well-finished |

Predicted (first 1 of 1 rows):

| CASE WHEN T2.ClosedDate IS NOT NULL AND… |
|---|
| Yes |

## 584 / codebase_community / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query retrieves `postHistory.Comment`, the comments left during edits, while the prediction retrieves `comments.Text`. The prediction also joins through the post’s last editor rather than the post’s history, but the first difference is the source table and column.

Question:

```text
Write all the comments left by users who edited the post titled 'Why square the difference instead of taking the absolute value in standard deviation?'
```

Evidence:

```text
"Why square the difference instead of taking the absolute value in standard deviation?" is the Title of post;
```

Gold SQL:

```sql
SELECT T2.Comment FROM posts AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.PostId WHERE T1.Title = 'Why square the difference instead of taking the absolute value in standard deviation?'
```

Predicted SQL:

```sql
SELECT T2.Text FROM posts AS T1 INNER JOIN comments AS T2 ON T1.LastEditorUserId = T2.UserId WHERE T1.Title = 'Why square the difference instead of taking the absolute value in standard deviation?'
```

Result diff:

Gold 8 rows, predicted 1033 rows. Within the previews: 3 rows only in gold, 5 only in predicted.

Gold (first 5 of 8 rows):

| Comment |
|---|
|  |
|  |
|  |
| edited title |
| TeXified the formulas. |

Predicted (first 5 of 1033 rows):

| Text |
|---|
| "Classifying documents with Bayes" soun… |
| $\\\\sqrt{2}-1$ is 0.4142, so it is in ag… |
| $k$-means is NP-hard, so there is a lot… |
| (Migration-related comments deleted) |
| (a)Aaron @StéphaneLaurent (a)Joris The … |

## 586 / codebase_community / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Which user added a bounty amount of 50 to the post title mentioning variance?
```

Evidence:

```text
bounty amount of 50 refers to BountyAmount = 50; user refers to DisplayName; title mentioning variance refers to Title include 'variance'
```

Gold SQL:

```sql
SELECT T3.DisplayName, T1.Title FROM posts AS T1 INNER JOIN votes AS T2 ON T1.Id = T2.PostId INNER JOIN users AS T3 ON T3.Id = T2.UserId WHERE T2.BountyAmount = 50 AND T1.Title LIKE '%variance%'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.DisplayName FROM users AS T1 INNER JOIN votes AS T2 ON T1.Id = T2.UserId INNER JOIN posts AS T3 ON T2.PostId = T3.Id WHERE T2.BountyAmount = 50 AND T3.Title LIKE '%variance%'
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| DisplayName | Title |
|---|---|
| chl | How to combine confidence intervals for… |
| shabbychef | Unbiased estimation of covariance matri… |

Predicted (first 2 of 2 rows):

| DisplayName |
|---|
| chl |
| shabbychef |

## 595 / codebase_community / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query filters on `posts.ViewCount` and selects `postHistory.UserId`, while the prediction uses `users.Views` and selects `DisplayName`. It also omits the `posts` join needed to apply the view-count condition.

Gold label suspect: yes.

Question:

```text
Which user have only one post history per post and having at least 1000 views?
```

Evidence:

```text
having at least 1000 view refers to Views > = 1000; user refers to UserId
```

Gold SQL:

```sql
SELECT T2.UserId FROM users AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.UserId INNER JOIN posts AS T3 ON T2.PostId = T3.Id WHERE T3.ViewCount >= 1000 GROUP BY T2.UserId HAVING COUNT(DISTINCT T2.PostHistoryTypeId) = 1
```

Predicted SQL:

```sql
SELECT DISTINCT T1.DisplayName FROM users AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.UserId WHERE T1.Views >= 1000 GROUP BY T1.Id, T2.PostId HAVING COUNT(T2.Id) = 1
```

Result diff:

Gold 94 rows, predicted 46 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 94 rows):

| UserId |
|---|
| 57 |
| 61 |
| 80 |
| 124 |
| 139 |

Predicted (first 5 of 46 rows):

| DisplayName |
|---|
| Shane |
| csgillespie |
| Neil McGuigan |
| mbq |
| Rob Hyndman |

## 634 / codebase_community / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query sums view counts grouped by DisplayName to compare the two users, while the prediction ranks individual posts by ViewCount without grouping or aggregation. It also selects a post title rather than the winning user's name.

Gold label suspect: yes.

Question:

```text
Among posts by Harvey Motulsky and Noah Snyder, which one has higher popularity?
```

Evidence:

```text
Has higher popularity means the post has higher view count ; calculation = MAX(SUM(ViewCount)) where DisplayName = 'Harvey Motulsky' OR DisplayName = 'Noah Snyder';
```

Gold SQL:

```sql
SELECT T1.DisplayName FROM users AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.UserId INNER JOIN posts AS T3 ON T2.PostId = T3.Id WHERE T1.DisplayName = 'Harvey Motulsky' OR T1.DisplayName = 'Noah Snyder' GROUP BY T1.DisplayName ORDER BY SUM(T3.ViewCount) DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.Title FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T2.DisplayName IN ('Harvey Motulsky', 'Noah Snyder') ORDER BY T1.ViewCount DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| DisplayName |
|---|
| Harvey Motulsky |

Predicted (first 1 of 1 rows):

| Title |
|---|
| Power of Holm's multiple comparison tes… |

## 640 / codebase_community / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Calculate the difference in view count from post posted by Mornington and view count from posts posted by Amos.
```

Evidence:

```text
calculation = SUBTRACT(SUM(ViewCount where DisplayName = 'Mornington'), SUM(ViewCount where DisplayName = 'Amos'));
```

Gold SQL:

```sql
SELECT SUM(IIF(T1.DisplayName = 'Mornington', T3.ViewCount, 0)) - SUM(IIF(T1.DisplayName = 'Amos', T3.ViewCount, 0)) AS diff FROM users AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.UserId INNER JOIN posts AS T3 ON T3.Id = T2.PostId
```

Predicted SQL:

```sql
SELECT SUM(CASE WHEN T2.DisplayName = 'mornington' THEN T1.ViewCount ELSE 0 END) - SUM(CASE WHEN T2.DisplayName = 'Amos' THEN T1.ViewCount ELSE 0 END) FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T2.DisplayName IN ('mornington', 'Amos')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| diff |
|---|
| -1491 |

Predicted (first 1 of 1 rows):

| SUM(CASE WHEN T2.DisplayName = 'morning… |
|---|
| -497 |

## 672 / codebase_community / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts qualifying user-post rows where an individual post has FavoriteCount >= 4. The prediction instead groups posts by user, sums FavoriteCount across that user’s posts, and counts users whose sum reaches 4.

Gold label suspect: yes.

Question:

```text
Among the users located in United Kingdom, how many users whose post have a total favorite amount of 4 or more?
```

Evidence:

```text
favorite amount of 4 or more refers to FavoriteCount > = 4; Location = 'United Kingdom';
```

Gold SQL:

```sql
SELECT COUNT(T1.Id) FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId WHERE T1.Location = 'United Kingdom' AND T2.FavoriteCount >= 4
```

Predicted SQL:

```sql
SELECT COUNT(*) FROM (SELECT T1.Id FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId WHERE T1.Location = 'United Kingdom' GROUP BY T1.Id HAVING SUM(T2.FavoriteCount) >= 4) AS T3
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.Id) |
|---|
| 19 |

Predicted (first 1 of 1 rows):

| COUNT(*) |
|---|
| 18 |

## 694 / codebase_community / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Provide the text of the latest 10 comments to the post with the title 'Analysing wind data with R' and the display name of the user who left it.
```

Evidence:

```text
the latest comment refers to MAX(CreationDate);
```

Gold SQL:

```sql
SELECT T3.Text, T1.DisplayName FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId INNER JOIN comments AS T3 ON T2.Id = T3.PostId WHERE T2.Title = 'Analysing wind data with R' ORDER BY T1.CreationDate DESC LIMIT 10
```

Predicted SQL:

```sql
SELECT T1.Text, T3.DisplayName FROM comments AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id INNER JOIN users AS T3 ON T1.UserId = T3.Id WHERE T2.Title = 'Analysing wind data with R' ORDER BY T1.CreationDate DESC LIMIT 10
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| Text | DisplayName |
|---|---|
| About the picture, post to some image h… | eliavs |
| +1, interesting question, you might fin… | eliavs |
| yup i have thanks to all that helped me… | eliavs |
| judging from the graph, the problem is … | eliavs |
| well yes mainly from literature and oth… | eliavs |

Predicted (first 5 of 10 rows):

| Text | DisplayName |
|---|---|
| i thought of integrating seperetly unti… | eliavs |
| well untill 4 m/s there is no wind gene… | eliavs |
| Regarding your question about energy, i… | David Heffernan |
| note that 'lag' is a term used mainly i… | Spacedman |
| i tried ploting it with out zero's but … | eliavs |

## 701 / codebase_community / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query includes every user tied for maximum reputation, while the prediction orders by reputation and limits to one user, potentially excluding other top-reputation users.

Gold label suspect: yes.

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
WITH cte1 AS (SELECT T1.Id FROM users AS T1 ORDER BY T1.Reputation DESC LIMIT 1) SELECT CAST(SUM(CASE WHEN T2.Score > 50 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM cte1 AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId
```

Result diff:

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.Score > 50 THEN 1… |
|---|
| 0.6644518272425249 |

## 726 / superhero / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The prediction returns the hero name and height but omits the rank column (`HeightRank`) produced by the gold query. The join and Marvel filter match.

Gold label suspect: yes.

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
SELECT superhero_name, height_cm, RANK() OVER (ORDER BY height_cm DESC) AS HeightRank FROM superhero INNER JOIN publisher ON superhero.publisher_id = publisher.id WHERE publisher.publisher_name = 'Marvel Comics'
```

Predicted SQL:

```sql
SELECT T1.superhero_name, T1.height_cm FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T2.publisher_name = 'Marvel Comics' ORDER BY T1.height_cm DESC
```

Result diff:

Gold 387 rows, predicted 387 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 387 rows):

| superhero_name | height_cm | HeightRank |
|---|---|---|
| Surtur | 30480 | 1 |
| Ymir | 30480 | 1 |
| Bloodwraith | 3050 | 3 |
| Utgard-Loki | 1520 | 4 |
| Fin Fang Foom | 975 | 5 |

Predicted (first 5 of 387 rows):

| superhero_name | height_cm |
|---|---|
| Surtur | 30480 |
| Ymir | 30480 |
| Bloodwraith | 3050 |
| Utgard-Loki | 1520 |
| Fin Fang Foom | 975 |

## 743 / superhero / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters for `alignment = 'Bad'`, while the prediction counts `alignment = 'Neutral'` and does not filter to the requested superheroes. This changes both the percentage and the Marvel count.

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
SELECT (CAST(COUNT(*) AS REAL) * 100 / (SELECT COUNT(*) FROM superhero)), CAST(SUM(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) AS REAL) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id INNER JOIN alignment AS T3 ON T3.id = T1.alignment_id WHERE T3.alignment = 'Bad'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.alignment = 'Neutral' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id), SUM(CASE WHEN T2.alignment = 'Neutral' AND T3.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) FROM superhero AS T1 LEFT JOIN alignment AS T2 ON T1.alignment_id = T2.id LEFT JOIN publisher AS T3 ON T1.publisher_id = T3.id
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| (CAST(COUNT(*) AS REAL) * 100 / (SELECT… | CAST(SUM(CASE WHEN T2.publisher_name = … |
|---|---|
| 28.266666666666666 | 118.0 |

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

## 750 / superhero / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What is the average weight of all female superheroes?
```

Evidence:

```text
female refers to gender = 'Female'; average weight refers to AVG(weight_kg)
```

Gold SQL:

```sql
SELECT AVG(T1.weight_kg) FROM superhero AS T1 INNER JOIN gender AS T2 ON T1.gender_id = T2.id WHERE T2.gender = 'Female'
```

Predicted SQL:

```sql
SELECT AVG(T1.weight_kg) FROM superhero AS T1 INNER JOIN gender AS T2 ON T1.gender_id = T2.id WHERE T2.gender = 'Female' AND T1.weight_kg > 0
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(T1.weight_kg) |
|---|
| 60.77956989247312 |

Predicted (first 1 of 1 rows):

| AVG(T1.weight_kg) |
|---|
| 78.50694444444444 |

## 751 / superhero / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
List down at least five superpowers of male superheroes.
```

Evidence:

```text
male refers to gender = 'Male'; superpowers refers to power_name;
```

Gold SQL:

```sql
SELECT T3.power_name FROM superhero AS T1 INNER JOIN hero_power AS T2 ON T1.id = T2.hero_id INNER JOIN superpower AS T3 ON T3.id = T2.power_id INNER JOIN gender AS T4 ON T4.id = T1.gender_id WHERE T4.gender = 'Male' LIMIT 5
```

Predicted SQL:

```sql
SELECT DISTINCT T1.power_name FROM superpower AS T1 INNER JOIN hero_power AS T2 ON T1.id = T2.power_id INNER JOIN superhero AS T3 ON T2.hero_id = T3.id INNER JOIN gender AS T4 ON T3.gender_id = T4.id WHERE T4.gender = 'Male'
```

Result diff:

Gold 5 rows, predicted 162 rows. Within the previews: 0 rows only in gold, 0 only in predicted.

Gold (first 5 of 5 rows):

| power_name |
|---|
| Agility |
| Super Strength |
| Stamina |
| Super Speed |
| Accelerated Healing |

Predicted (first 5 of 162 rows):

| power_name |
|---|
| Agility |
| Super Strength |
| Stamina |
| Super Speed |
| Accelerated Healing |

## 772 / superhero / challenging

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query returns the eye, hair, and skin colour ID columns, while the prediction joins the colour table and returns colour names. The requested fields are explicitly identified as the *_colour_id columns in the evidence.

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
SELECT T4.colour, T5.colour, T6.colour FROM superhero AS T1 INNER JOIN gender AS T2 ON T1.gender_id = T2.id INNER JOIN publisher AS T3 ON T1.publisher_id = T3.id INNER JOIN colour AS T4 ON T1.eye_colour_id = T4.id INNER JOIN colour AS T5 ON T1.hair_colour_id = T5.id INNER JOIN colour AS T6 ON T1.skin_colour_id = T6.id WHERE T2.gender = 'Female' AND T3.publisher_name = 'Dark Horse Comics'
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

## 788 / superhero / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many percent of female heroes were published by Marvel Comics?
```

Evidence:

```text
percent = MULTIPLY(DIVIDE(SUM(gender = 'Female' WHERE publisher_name = 'Marvel Comics'), COUNT(publisher_name = 'Marvel Comics')), 100); female heroes refers to gender = 'Female'; Marvel Comics refers to publisher_name = 'Marvel Comics';
```

Gold SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T3.gender = 'Female' AND T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) / COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) * 100 FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id INNER JOIN gender AS T3 ON T1.gender_id = T3.id
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T3.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM superhero AS T1 INNER JOIN gender AS T2 ON T1.gender_id = T2.id LEFT JOIN publisher AS T3 ON T1.publisher_id = T3.id WHERE T2.gender = 'Female'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T3.gender = 'Femal… |
|---|
| 28.68217054263566 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T3.publisher_name = … |
|---|
| 54.679802955665025 |

## 829 / superhero / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction identifies Marvel Comics as the publisher with more superheroes and reports the positive difference, while the gold query returns only DC's count minus Marvel's count (−163) and does not name the publisher. The gold result therefore omits an explicit part of the question.

Gold label suspect: yes.

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
SELECT SUM(CASE WHEN T2.publisher_name = 'DC Comics' THEN 1 ELSE 0 END) - SUM(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.publisher_name, COUNT(T2.id) AS c1 FROM publisher AS T1 INNER JOIN superhero AS T2 ON T1.id = T2.publisher_id WHERE T1.publisher_name IN ('DC Comics', 'Marvel Comics') GROUP BY T1.id, T1.publisher_name) SELECT T1.publisher_name, T1.c1 - (SELECT MIN(T2.c1) FROM cte1 AS T2) AS c2 FROM cte1 AS T1 ORDER BY T1.c1 DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(CASE WHEN T2.publisher_name = 'DC C… |
|---|
| -163 |

Predicted (first 1 of 1 rows):

| publisher_name | c2 |
|---|---|
| Marvel Comics | 163 |

## 846 / formula_1 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query identifies five drivers by ranking q1 times in descending order and applying LIMIT 5. The prediction instead selects every driver with q1 present and q2 absent, returning six rows rather than applying that ranking.

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
SELECT T1.driverRef FROM drivers AS T1 INNER JOIN qualifying AS T2 ON T1.driverId = T2.driverId WHERE T2.raceId = 20 AND T2.q1 IS NOT NULL AND T2.q2 IS NULL
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

## 880 / formula_1 / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Paul di Resta was in the No. 853 race, what percent faster did he finish in the 853rd race than the next race for the fastest lap speed?
```

Evidence:

```text
Paul di Resta refers to the full name of the driver; Full name of the driver refers to drivers.forename ='Paul' and drivers.surname = 'di Resta'; race number refers to raceId; percentage = DIVIDE(SUBTRACT(fastestLapSpeed(raceId = 853), (fastestLapSpeed (raceId = 854)) * 100 , (fastestLapSpeed(raceId = 853))
```

Gold SQL:

```sql
SELECT (SUM(IIF(T2.raceId = 853, T2.fastestLapSpeed, 0)) - SUM(IIF(T2.raceId = 854, T2.fastestLapSpeed, 0))) * 100 / SUM(IIF(T2.raceId = 853, T2.fastestLapSpeed, 0)) FROM drivers AS T1 INNER JOIN results AS T2 ON T2.driverId = T1.driverId WHERE T1.forename = 'Paul' AND T1.surname = 'di Resta'
```

Predicted SQL:

```sql
SELECT CAST(T2.fastestLapSpeed - T3.fastestLapSpeed AS REAL) * 100 / T3.fastestLapSpeed FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN results AS T3 ON T1.driverId = T3.driverId WHERE T1.forename = 'Paul' AND T1.surname = 'di Resta' AND T2.raceId = 853 AND T3.raceId = 854
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| (SUM(IIF(T2.raceId = 853, T2.fastestLap… |
|---|
| 32.50155167390781 |

Predicted (first 1 of 1 rows):

| CAST(T2.fastestLapSpeed - T3.fastestLap… |
|---|
| 48.15155382074764 |

## 892 / formula_1 / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
State the driver with the most points scored. Find his full name with that points.
```

Evidence:

```text
the most points scored refers to max(points); Full name of the driver refers to drivers.forename and drivers.surname;
```

Gold SQL:

```sql
SELECT T3.forename, T3.surname, T2.points FROM races AS T1 INNER JOIN driverStandings AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId ORDER BY T2.points DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.forename, T1.surname, SUM(T2.points) AS c1 FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId GROUP BY T1.driverId, T1.forename, T1.surname ORDER BY c1 DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| forename | surname | points |
|---|---|---|
| Sebastian | Vettel | 397.0 |

Predicted (first 1 of 1 rows):

| forename | surname | c1 |
|---|---|---|
| Lewis | Hamilton | 2382.0 |

## 894 / formula_1 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query selects `lapTimes.milliseconds`, which the evidence identifies as the value to minimize. The prediction selects `lapTimes.time` instead, so it returns a differently represented column.

Question:

```text
What is the best lap time recorded? List the driver and race with such recorded lap time.
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

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks whether Hamilton finished outside first place in races, and the evidence specifies counting race entries by position. The prediction uses race results, while the gold query uses driver championship standings, which measure a different position and do not answer the question as asked.

Question:

```text
Calculate the percentage whereby Hamilton was not at the 1st track of the the f1 circuit since 2010.
```

Evidence:

```text
percentage = DIVIDE(COUNT(raceId) where surname = 'Hamilton' and position>1), (COUNT(raceId) where surname = 'Hamilton'); since 2010 refers to year >= 2010
```

Gold SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T2.position <> 1 THEN T2.position END) AS REAL) * 100 / COUNT(T2.driverStandingsId) FROM races AS T1 INNER JOIN driverStandings AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId WHERE T3.surname = 'Hamilton' AND T1.year >= 2010
```

Predicted SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T1.position != 1 THEN 1 END) AS REAL) * 100 / COUNT(*) FROM results AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T1.raceId = T3.raceId WHERE T2.surname = 'Hamilton' AND T3.year >= 2010
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T2.position <> 1 T… |
|---|
| 73.2394366197183 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T1.position != 1 T… |
|---|
| 54.225352112676056 |

## 902 / formula_1 / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query checks Alex Yoong’s `position` in `driverStandings`, while the prediction checks `position` in `results`. These are different data sources for the track-number condition and yield different races.

Question:

```text
Which race was Alex Yoong in when he was in track number less than 20?
```

Evidence:

```text
Alex Yoong refers to the full name of the driver; Full name of the driver refers to drivers.forename and drivers.surname;track number less than 10 refers to position < 20
```

Gold SQL:

```sql
SELECT T1.name FROM races AS T1 INNER JOIN driverStandings AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId WHERE T3.forename = 'Alex' AND T3.surname = 'Yoong' AND T2.position < 20
```

Predicted SQL:

```sql
SELECT DISTINCT T3.name FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T2.raceId = T3.raceId WHERE T1.forename = 'Alex' AND T1.surname = 'Yoong' AND T2.position < 20
```

Result diff:

Gold 15 rows, predicted 5 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 5 of 15 rows):

| name |
|---|
| Malaysian Grand Prix |
| Brazilian Grand Prix |
| San Marino Grand Prix |
| Spanish Grand Prix |
| Austrian Grand Prix |

Predicted (first 5 of 5 rows):

| name |
|---|
| Brazilian Grand Prix |
| Canadian Grand Prix |
| French Grand Prix |
| Italian Grand Prix |
| Japanese Grand Prix |

## 904 / formula_1 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query finds the minimum lap time from `lapTimes.milliseconds`; the prediction instead orders by `results.fastestLapTime`, a different field and source for the fastest lap. This changes the selected race.

Question:

```text
State the race and year of race in which Michael Schumacher had his fastest lap.
```

Evidence:

```text
fastest lap refers to min(milliseconds); Alex Yoong refers to the full name of the driver; Full name of the driver refers to drivers.forename and drivers.surname;
```

Gold SQL:

```sql
SELECT T1.name, T1.year FROM races AS T1 INNER JOIN lapTimes AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId WHERE T3.forename = 'Michael' AND T3.surname = 'Schumacher' ORDER BY T2.milliseconds ASC LIMIT 1
```

Predicted SQL:

```sql
SELECT T3.name, T3.year FROM results AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T1.raceId = T3.raceId WHERE T2.forename = 'Michael' AND T2.surname = 'Schumacher' AND T1.fastestLapTime IS NOT NULL ORDER BY T1.fastestLapTime ASC LIMIT 1
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

## 906 / formula_1 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query gets the event points from `driverStandings.points`, while the prediction reads `results.points`, which records a different points value for the event.

Question:

```text
Which was Lewis Hamilton first race? What was his points recorded for his first race event?
```

Evidence:

```text
first race refers to min(Year); Lewis Hamiltonrefers to the full name of the driver; Full name of the driver refers to drivers.forename and drivers.surname;
```

Gold SQL:

```sql
SELECT T1.name, T2.points FROM races AS T1 INNER JOIN driverStandings AS T2 ON T2.raceId = T1.raceId INNER JOIN drivers AS T3 ON T3.driverId = T2.driverId WHERE T3.forename = 'Lewis' AND T3.surname = 'Hamilton' ORDER BY T1.year ASC LIMIT 1
```

Predicted SQL:

```sql
SELECT T3.name, T1.points FROM results AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T1.raceId = T3.raceId WHERE T2.forename = 'Lewis' AND T2.surname = 'Hamilton' AND T3.date IS NOT NULL ORDER BY T3.date ASC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| name | points |
|---|---|
| Malaysian Grand Prix | 14.0 |

Predicted (first 1 of 1 rows):

| name | points |
|---|---|
| Malaysian Grand Prix | 8.0 |

## 930 / formula_1 / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every race where Hamilton had rank 1, while the prediction orders by rank and uses LIMIT 1, returning only one race. The difference is the ranking/tie-handling logic.

Question:

```text
In which Formula_1 race did Lewis Hamilton rank the highest?
```

Evidence:

```text
rank the highest refers to min(rank); Lewis Hamilton refers to the full name of the driver; Full name of the driver refers to drivers.forename and drivers.surname;
```

Gold SQL:

```sql
SELECT name FROM races WHERE raceId IN ( SELECT raceId FROM results WHERE rank = 1 AND driverId = ( SELECT driverId FROM drivers WHERE forename = 'Lewis' AND surname = 'Hamilton' ) )
```

Predicted SQL:

```sql
SELECT T3.name FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T2.raceId = T3.raceId WHERE T1.forename = 'Lewis' AND T1.surname = 'Hamilton' AND T2.rank IS NOT NULL ORDER BY T2.rank ASC LIMIT 1
```

Result diff:

Gold 37 rows, predicted 1 rows. Within the previews: 3 rows only in gold, 0 only in predicted.

Gold (first 5 of 37 rows):

| name |
|---|
| Chinese Grand Prix |
| Malaysian Grand Prix |
| Japanese Grand Prix |
| Chinese Grand Prix |
| Spanish Grand Prix |

Predicted (first 1 of 1 rows):

| name |
|---|
| Chinese Grand Prix |

## 931 / formula_1 / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): Both queries return the fastest lap speed for the specified race, but the gold selects `fastestLapSpeed` while the prediction returns an aggregate expression (`MAX(CAST(... AS REAL))`), producing a differently typed/value-labeled output column.

Question:

```text
What was the fastest lap speed among all drivers in the 2009 Spanish Grand Prix?
```

Evidence:

```text
the fastest lap speed among all refers to max(fastestLapSpeed); Spanish Grand Prix refers to races.name = 'Spanish Grand Prix';
```

Gold SQL:

```sql
SELECT T2.fastestLapSpeed FROM races AS T1 INNER JOIN results AS T2 ON T2.raceId = T1.raceId WHERE T1.name = 'Spanish Grand Prix' AND T1.year = 2009 AND T2.fastestLapSpeed IS NOT NULL ORDER BY T2.fastestLapSpeed DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT MAX(CAST(T1.fastestLapSpeed AS REAL)) FROM results AS T1 INNER JOIN races AS T2 ON T1.raceId = T2.raceId WHERE T2.year = 2009 AND T2.name = 'Spanish Grand Prix'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| fastestLapSpeed |
|---|
| 202.484 |

Predicted (first 1 of 1 rows):

| MAX(CAST(T1.fastestLapSpeed AS REAL)) |
|---|
| 202.484 |

## 951 / formula_1 / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many Japanese constructors have 0 points in 2 races?
```

Evidence:

```text
2 races refers to COUNT(raceID) = 2; Japanese refers to constructors.nationality = 'Japanese';
```

Gold SQL:

```sql
SELECT COUNT(T1.raceId) FROM constructorStandings AS T1 INNER JOIN constructors AS T2 on T1.constructorId = T2.constructorId WHERE T1.points = 0 AND T2.nationality = 'Japanese' GROUP BY T1.constructorId HAVING COUNT(raceId) = 2
```

Predicted SQL:

```sql
SELECT COUNT(*) FROM (SELECT T1.constructorId FROM constructors AS T1 INNER JOIN constructorResults AS T2 ON T1.constructorId = T2.constructorId WHERE T1.nationality = 'Japanese' AND T2.points = 0 GROUP BY T1.constructorId HAVING COUNT(DISTINCT T2.raceId) = 2) AS T3
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.raceId) |
|---|
| 2 |

Predicted (first 1 of 1 rows):

| COUNT(*) |
|---|
| 1 |

## 963 / formula_1 / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many French drivers who obtain the laptime less than 02:00.00?
```

Evidence:

```text
lap time less than 02:00.00 refers to seconds < 120;
```

Gold SQL:

```sql
SELECT COUNT(T1.driverId) FROM drivers AS T1 INNER JOIN lapTimes AS T2 on T1.driverId = T2.driverId WHERE T1.nationality = 'French' AND (CAST(SUBSTR(T2.time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(T2.time, 4, 2) AS INTEGER) + CAST(SUBSTR(T2.time, 7, 2) AS REAL) / 1000) < 120
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.driverId) FROM drivers AS T1 INNER JOIN lapTimes AS T2 ON T1.driverId = T2.driverId WHERE T1.nationality = 'French' AND T2.milliseconds < 120000
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.driverId) |
|---|
| 23295 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.driverId) |
|---|
| 9 |

## 972 / formula_1 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every matching race result with a non-null fastestLapTime, while the prediction orders by fastestLapTime and limits the result to one driver. The question does not ask for the minimum lap-time value or a single row.

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
SELECT T2.driverId, T2.code FROM results AS T1 INNER JOIN drivers AS T2 on T1.driverId = T2.driverId WHERE STRFTIME('%Y', T2.dob) = '1971' AND T1.fastestLapTime IS NOT NULL
```

Predicted SQL:

```sql
SELECT T1.driverId, T1.code FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId WHERE STRFTIME('%Y', T1.dob) = '1971' AND T2.fastestLapTime IS NOT NULL ORDER BY T2.fastestLapTime ASC LIMIT 1
```

Result diff:

Gold 150 rows, predicted 1 rows. Within the previews: 0 rows only in gold, 0 only in predicted.

Gold (first 5 of 150 rows):

| driverId | code |
|---|---|
| 14 | COU |
| 14 | COU |
| 14 | COU |
| 14 | COU |
| 14 | COU |

Predicted (first 1 of 1 rows):

| driverId | code |
|---|---|
| 14 | COU |

## 977 / formula_1 / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction uses inclusive `BETWEEN 50 AND 100` instead of the specified strict bounds (`raceId > 50` and `< 100`). It also counts all disqualified results rather than only those with a non-NULL time.

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
SELECT COUNT(T1.resultId) FROM results AS T1 INNER JOIN status AS T2 ON T1.statusId = T2.statusId WHERE T1.raceId BETWEEN 50 AND 100 AND T2.status = 'Disqualified'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(IIF(time IS NOT NULL, 1, 0)) |
|---|
| 2 |

Predicted (first 1 of 1 rows):

| COUNT(T1.resultId) |
|---|
| 13 |

## 978 / formula_1 / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns distinct locations and coordinates, while the prediction groups by them and adds COUNT(circuitId). That aggregation changes the output and returns counts the question does not request as a distinct-location result.

Question:

```text
How many times the circuits were held in Austria? Please give their location and coordinates.
```

Evidence:

```text
location coordinates refers to (lat,lng); Austria refers to country = 'Austria';
```

Gold SQL:

```sql
SELECT DISTINCT location, lat, lng FROM circuits WHERE country = 'Austria'
```

Predicted SQL:

```sql
SELECT COUNT(T1.circuitId), T1.location, T1.lat, T1.lng FROM circuits AS T1 WHERE T1.country = 'Austria' GROUP BY T1.location, T1.lat, T1.lng
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| location | lat | lng |
|---|---|---|
| Spielburg | 47.2197 | 14.7647 |
| Styria | 47.2039 | 14.7478 |

Predicted (first 2 of 2 rows):

| COUNT(T1.circuitId) | location | lat | lng |
|---|---|---|---|
| 2 | Spielburg | 47.2197 | 14.7647 |
| 1 | Styria | 47.2039 | 14.7478 |

## 989 / formula_1 / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks for both the champion and his finish time, but the gold query returns only the time. The prediction identifies Robert Kubica and gives the time, so its additional name columns address the question rather than being an error.

Question:

```text
Who is the champion of the Canadian Grand Prix in 2008? Indicate his finish time.
```

Evidence:

```text
Only the time of the champion shows in the format of "hour: minutes: seconds.millionsecond";
```

Gold SQL:

```sql
SELECT T1.time FROM results AS T1 INNER JOIN races AS T2 ON T1.raceId = T2.raceId WHERE T2.name = 'Canadian Grand Prix' AND T2.year = 2008 AND T1.time LIKE '_:%:__.___'
```

Predicted SQL:

```sql
SELECT T1.forename, T1.surname, T2.time FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T2.raceId = T3.raceId WHERE T3.name = 'Canadian Grand Prix' AND T3.year = 2008 AND T2.position = 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| time |
|---|
| 1:36:24.227 |

Predicted (first 1 of 1 rows):

| forename | surname | time |
|---|---|---|
| Robert | Kubica | 1:36:24.227 |

## 1011 / formula_1 / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Which top 20 driver created the shortest lap time ever record in a Formula_1 race? Please give them full names.
```

Evidence:

```text
shortest lap time refers to MIN(time); the time format for the shortest lap time is 'MM:SS.mmm' or 'M:SS.mmm'; full name of the driver refers to forename, surname
```

Gold SQL:

```sql
WITH lap_times_in_seconds AS (SELECT driverId, (CASE WHEN SUBSTR(time, 1, INSTR(time, ':') - 1) <> '' THEN CAST(SUBSTR(time, 1, INSTR(time, ':') - 1) AS REAL) * 60 ELSE 0 END + CASE WHEN SUBSTR(time, INSTR(time, ':') + 1, INSTR(time, '.') - INSTR(time, ':') - 1) <> '' THEN CAST(SUBSTR(time, INSTR(time, ':') + 1, INSTR(time, '.') - INSTR(time, ':') - 1) AS REAL) ELSE 0 END + CASE WHEN SUBSTR(time, INSTR(time, '.') + 1) <> '' THEN CAST(SUBSTR(time, INSTR(time, '.') + 1) AS REAL) / 1000 ELSE 0 END) AS time_in_seconds FROM lapTimes) SELECT T2.forename, T2.surname, T1.driverId FROM (SELECT driverId, MIN(time_in_seconds) AS min_time_in_seconds FROM lap_times_in_seconds GROUP BY driverId) AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId ORDER BY T1.min_time_in_seconds ASC LIMIT 20
```

Predicted SQL:

```sql
SELECT T1.forename, T1.surname FROM drivers AS T1 INNER JOIN lapTimes AS T2 ON T1.driverId = T2.driverId WHERE T2.milliseconds IS NOT NULL GROUP BY T1.driverId, T1.forename, T1.surname ORDER BY MIN(T2.milliseconds) ASC LIMIT 20
```

Result diff:

Gold 20 rows, predicted 20 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 20 rows):

| forename | surname | driverId |
|---|---|---|
| Nico | Hülkenberg | 807 |
| Daniel | Ricciardo | 817 |
| Adrian | Sutil | 16 |
| Kevin | Magnussen | 825 |
| Nico | Rosberg | 3 |

Predicted (first 5 of 20 rows):

| forename | surname |
|---|---|
| Lewis | Hamilton |
| Daniel | Ricciardo |
| Kimi | Räikkönen |
| Sebastian | Vettel |
| Valtteri | Bottas |

## 1029 / european_football_2 / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What are the speed in which attacks are put together of the top 4 teams with the highest build Up Play Speed?
```

Evidence:

```text
speed in which attacks are put together refers to buildUpPlaySpeed;highest build up play speed refers to MAX(buildUpPlaySpeed)
```

Gold SQL:

```sql
SELECT t1.buildUpPlaySpeed FROM Team_Attributes AS t1 INNER JOIN Team AS t2 ON t1.team_api_id = t2.team_api_id ORDER BY t1.buildUpPlaySpeed ASC LIMIT 4
```

Predicted SQL:

```sql
SELECT T1.buildUpPlaySpeed FROM Team_Attributes AS T1 ORDER BY T1.buildUpPlaySpeed DESC LIMIT 4
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 2 rows only in gold, 3 only in predicted.

Gold (first 4 of 4 rows):

| buildUpPlaySpeed |
|---|
| 20 |
| 20 |
| 20 |
| 23 |

Predicted (first 4 of 4 rows):

| buildUpPlaySpeed |
|---|
| 80 |
| 78 |
| 78 |
| 77 |

## 1037 / european_football_2 / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Calculate the percentage of players who prefer left foot, who were born between 1987 and 1992.
```

Evidence:

```text
players who prefer left foot refers to preferred_foot = 'left'; percentage of players who prefer left foot = DIVIDE(MULTIPLY((SUM(preferred_foot = 'left'), 100)), COUNT(player_fifa_api_id)); born between 1987 and 1992 refers to YEAR(birthday) BETWEEN '1987' AND '1992';
```

Gold SQL:

```sql
SELECT CAST(COUNT(CASE WHEN t2.preferred_foot = 'left' THEN t1.id ELSE NULL END) AS REAL) * 100 / COUNT(t1.id) percent FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id WHERE SUBSTR(t1.birthday, 1, 4) BETWEEN '1987' AND '1992'
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T2.preferred_foot = 'left' THEN T1.player_api_id END) AS REAL) * 100 / COUNT(DISTINCT T1.player_api_id) FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE STRFTIME('%Y', T1.birthday) BETWEEN '1987' AND '1992'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| percent |
|---|
| 24.56690504416995 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.prefer… |
|---|
| 28.868144690781797 |

## 1058 / european_football_2 / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query compares average finishing across all players at the maximum and minimum heights, while the prediction selects one player at each extreme and ranks their individual averages. It also returns a player name rather than the winning height-category label.

Gold label suspect: yes.

Question:

```text
Who has the highest average finishing rate between the highest and shortest football player?
```

Evidence:

```text
finishing rate refers to finishing; highest average finishing rate = MAX(AVG(finishing)); highest football player refers to MAX(height); shortest football player refers to MIN(height);
```

Gold SQL:

```sql
SELECT A FROM ( SELECT AVG(finishing) result, 'Max' A FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.height = ( SELECT MAX(height) FROM Player ) UNION SELECT AVG(finishing) result, 'Min' A FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.height = ( SELECT MIN(height) FROM Player ) ) ORDER BY result DESC LIMIT 1
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.player_api_id FROM Player AS T1 WHERE T1.height IS NOT NULL ORDER BY T1.height DESC LIMIT 1), cte2 AS (SELECT T1.player_api_id FROM Player AS T1 WHERE T1.height IS NOT NULL ORDER BY T1.height ASC LIMIT 1) SELECT T1.player_name FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.player_api_id IN (SELECT T3.player_api_id FROM cte1 AS T3 UNION SELECT T4.player_api_id FROM cte2 AS T4) GROUP BY T1.player_api_id, T1.player_name ORDER BY AVG(T2.finishing) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| A |
|---|
| Min |

Predicted (first 1 of 1 rows):

| player_name |
|---|
| Juan Quero |

## 1080 / european_football_2 / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Among the players whose preferred foot was the left foot when attacking, how many of them would remain in his position when the team attacked?
```

Evidence:

```text
preferred foot when attacking was the left refers to preferred_foot = 'left'; players who would remain in his position when the team attacked refers to attacking_work_rate = 'low';
```

Gold SQL:

```sql
SELECT COUNT(player_api_id) FROM Player_Attributes WHERE preferred_foot = 'left' AND attacking_work_rate = 'low'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.player_api_id) FROM Player_Attributes AS T1 WHERE T1.preferred_foot = 'left' AND T1.attacking_work_rate = 'low'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(player_api_id) |
|---|
| 1569 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.player_api_id) |
|---|
| 189 |

## 1092 / european_football_2 / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every league tied for the maximum match count, while the prediction orders by match count and uses LIMIT 1, returning only one league and dropping ties.

Question:

```text
Give the name of the league had the most matches in the 2008/2009 season?
```

Evidence:

```text
league that had the most matches in the 2008/2009 season refers to MAX(league_name WHERE season = '2008/2009');
```

Gold SQL:

```sql
SELECT t1.name FROM League AS t1 JOIN Match AS t2 ON t1.id = t2.league_id WHERE t2.season = '2008/2009' GROUP BY t1.name HAVING COUNT(t2.id) = (SELECT MAX(match_count) FROM (SELECT COUNT(t2.id) AS match_count FROM Match AS t2 WHERE t2.season = '2008/2009' GROUP BY t2.league_id))
```

Predicted SQL:

```sql
SELECT T1.name FROM League AS T1 INNER JOIN `Match` AS T2 ON T1.id = T2.league_id WHERE T2.season = '2008/2009' GROUP BY T1.id, T1.name ORDER BY COUNT(T2.id) DESC LIMIT 1
```

Result diff:

Gold 4 rows, predicted 1 rows. Within the previews: 3 rows only in gold, 0 only in predicted.

Gold (first 4 of 4 rows):

| name |
|---|
| England Premier League |
| France Ligue 1 |
| Italy Serie A |
| Spain LIGA BBVA |

Predicted (first 1 of 1 rows):

| name |
|---|
| England Premier League |

## 1094 / european_football_2 / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query sums each player’s overall ratings across attribute rows, while the prediction averages them. This changes the percentage from 133.73 to 16.86.

Question:

```text
How much higher in percentage is Ariel Borysiuk's overall rating than that of Paulin Puel?
```

Evidence:

```text
how much higher in percentage = MULTIPLY(DIVIDE(SUBTRACT(overall_rating WHERE player_name = 'Ariel Borysiuk', overall_rating WHERE player_name = 'Paulin Puel'), overall_rating WHERE player_name = 'Paulin Puel'), 100);
```

Gold SQL:

```sql
SELECT (SUM(CASE WHEN t1.player_name = 'Ariel Borysiuk' THEN t2.overall_rating ELSE 0 END) * 1.0 - SUM(CASE WHEN t1.player_name = 'Paulin Puel' THEN t2.overall_rating ELSE 0 END)) * 100 / SUM(CASE WHEN t1.player_name = 'Paulin Puel' THEN t2.overall_rating ELSE 0 END) FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id
```

Predicted SQL:

```sql
SELECT CAST(AVG(CASE WHEN T1.player_name = 'Ariel Borysiuk' THEN T2.overall_rating END) - AVG(CASE WHEN T1.player_name = 'Paulin Puel' THEN T2.overall_rating END) AS REAL) * 100 / AVG(CASE WHEN T1.player_name = 'Paulin Puel' THEN T2.overall_rating END) FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.player_name IN ('Ariel Borysiuk', 'Paulin Puel')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| (SUM(CASE WHEN t1.player_name = 'Ariel … |
|---|
| 133.7260677466863 |

Predicted (first 1 of 1 rows):

| CAST(AVG(CASE WHEN T1.player_name = 'Ar… |
|---|
| 16.863033873343145 |

## 1115 / european_football_2 / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What percentage is Landon Donovan's overall rating higher than Jordan Bowery on 2013/7/12?
```

Evidence:

```text
Landon Donovan's refers to player_name = 'Landon Donovan'; Jordan Bowery refers to player_name = 'Jordan Bowery'; percentage refers to DIVIDE(SUBTRACT(player_name = 'Landon Donovan' overall_rating; player_name = 'Jordan Bowery' overall_rating), player_name = 'Landon Donovan' overall_rating)*100
```

Gold SQL:

```sql
SELECT (SUM(CASE WHEN t1.player_name = 'Landon Donovan' THEN t2.overall_rating ELSE 0 END) * 1.0 - SUM(CASE WHEN t1.player_name = 'Jordan Bowery' THEN t2.overall_rating ELSE 0 END)) * 100 / SUM(CASE WHEN t1.player_name = 'Landon Donovan' THEN t2.overall_rating ELSE 0 END) LvsJ_percent FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_fifa_api_id = t2.player_fifa_api_id WHERE SUBSTR(t2.`date`, 1, 10) = '2013-07-12'
```

Predicted SQL:

```sql
SELECT CAST(T2.overall_rating - T4.overall_rating AS REAL) * 100 / T4.overall_rating FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id INNER JOIN Player AS T3 ON T3.player_name = 'Jordan Bowery' INNER JOIN Player_Attributes AS T4 ON T3.player_api_id = T4.player_api_id WHERE T1.player_name = 'Landon Donovan' AND DATE(T2.date) = '2013-07-12' AND DATE(T4.date) = '2013-07-12'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| LvsJ_percent |
|---|
| 25.31645569620253 |

Predicted (first 1 of 1 rows):

| CAST(T2.overall_rating - T4.overall_rat… |
|---|
| 33.898305084745765 |

## 1135 / european_football_2 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query selects `id`, while the prediction selects `player_api_id`; these are different columns and produce different IDs. The added non-NULL condition on `potential` is also a difference, but the column mismatch is the first issue to fix.

Question:

```text
Please provide top four football players' IDs who are among the lowest potential players and prefer to use the right foot when attacking.
```

Evidence:

```text
lowest potential players refers to MIN(potential); prefer to use the right foot when attacking refers to preferred_foot = 'right'
```

Gold SQL:

```sql
SELECT id FROM Player_Attributes WHERE preferred_foot = 'right' ORDER BY potential ASC LIMIT 4
```

Predicted SQL:

```sql
SELECT T1.player_api_id FROM Player_Attributes AS T1 WHERE T1.preferred_foot = 'right' AND T1.potential IS NOT NULL ORDER BY T1.potential ASC LIMIT 4
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 2 only in predicted.

Gold (first 4 of 4 rows):

| id |
|---|
| 132235 |
| 132236 |
| 66213 |
| 66214 |

Predicted (first 4 of 4 rows):

| player_api_id |
|---|
| 41496 |
| 41496 |
| 166963 |
| 166963 |

## 1136 / european_football_2 / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many players had the highest potential score for crossing that preferred to use their left foots while attacking?
```

Evidence:

```text
highest potential score for crossing refers to MAX(crossing); preferred to use their left foots while attacking refers to preferred_foot = 'left'
```

Gold SQL:

```sql
SELECT COUNT(t1.id) FROM Player_Attributes AS t1 WHERE t1.preferred_foot = 'left' AND t1.crossing = ( SELECT MAX(crossing) FROM Player_Attributes)
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.player_api_id) FROM Player_Attributes AS T1 WHERE T1.preferred_foot = 'left' AND T1.crossing = (SELECT MAX(T2.crossing) FROM Player_Attributes AS T2)
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(t1.id) |
|---|
| 3 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.player_api_id) |
|---|
| 2 |

## 1148 / european_football_2 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The prediction applies `overall_rating > 70` to the entire row set, so its denominator counts only players with a qualifying rating; the gold denominator counts all joined player IDs. It also uses `DISTINCT` player IDs rather than the gold query’s `COUNT(id)`.

Gold label suspect: yes.

Question:

```text
What is the percentage of players that are under 180 cm who have an overall strength of more than 70?
```

Evidence:

```text
percentage refers to DIVIDE(COUNT(height < 180 AND overall_rating > 70),COUNT(id)) * 100
```

Gold SQL:

```sql
SELECT CAST(COUNT(CASE WHEN t2.overall_rating > 70  AND t1.height < 180 THEN t1.id ELSE NULL END) AS REAL) * 100 / COUNT(t1.id) percent FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id 
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T1.height < 180 THEN T1.player_api_id END) AS REAL) * 100 / COUNT(DISTINCT T1.player_api_id) FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T2.overall_rating > 70
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| percent |
|---|
| 13.940797269238713 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T1.height… |
|---|
| 34.54093411472208 |

## 1149 / thrombosis_prediction / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold percentage is inpatient male count divided by outpatient male count, while the prediction calculates the absolute count difference divided by all qualifying males. The prediction also adds a category column, but its percentage aggregation is already different.

Gold label suspect: yes.

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
SELECT CAST(SUM(CASE WHEN Admission = '+' THEN 1 ELSE 0 END) AS REAL) * 100 / SUM(CASE WHEN Admission = '-' THEN 1 ELSE 0 END) FROM Patient WHERE SEX = 'M'
```

Predicted SQL:

```sql
SELECT CASE WHEN SUM(CASE WHEN T1.Admission = '+' THEN 1 ELSE 0 END) > SUM(CASE WHEN T1.Admission = '-' THEN 1 ELSE 0 END) THEN 'in-patient' WHEN SUM(CASE WHEN T1.Admission = '+' THEN 1 ELSE 0 END) < SUM(CASE WHEN T1.Admission = '-' THEN 1 ELSE 0 END) THEN 'outpatient' ELSE 'equal' END, CAST(ABS(SUM(CASE WHEN T1.Admission = '+' THEN 1 ELSE 0 END) - SUM(CASE WHEN T1.Admission = '-' THEN 1 ELSE 0 END)) AS REAL) * 100 / COUNT(*) FROM Patient AS T1 WHERE T1.SEX = 'M' AND T1.Admission IN ('+', '-')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN Admission = '+' THEN… |
|---|
| 83.17757009345794 |

Predicted (first 1 of 1 rows):

| CASE WHEN SUM(CASE WHEN T1.Admission = … | CAST(ABS(SUM(CASE WHEN T1.Admission = '… |
|---|---|
| outpatient | 9.183673469387756 |

## 1152 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The evidence defines the requested ratio as inpatient ('+') count divided by outpatient ('-') count, which the prediction computes. The gold SQL reverses that ratio, so it contradicts the stated calculation.

Question:

```text
What is the ratio of outpatient to inpatient followed up treatment among all the 'SLE' diagnosed patient?
```

Evidence:

```text
'SLE' diagnosed patient means Diagnosis = 'SLE'; inpatient refers to Admission = '+'; outpatient refers to Admission = '-'; calculation =  DIVIDE(COUNT(ID) where Diagnosis = 'SLE' and Admission = '+', COUNT(ID) where Diagnosis = 'SLE' and Admission = '-')
```

Gold SQL:

```sql
SELECT SUM(CASE WHEN Admission = '+' THEN 1.0 ELSE 0 END) / SUM(CASE WHEN Admission = '-' THEN 1 ELSE 0 END) FROM Patient WHERE Diagnosis = 'SLE'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.Admission = '-' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN T1.Admission = '+' THEN 1 ELSE 0 END) FROM Patient AS T1 WHERE T1.Diagnosis = 'SLE'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(CASE WHEN Admission = '+' THEN 1.0 … |
|---|
| 1.3095238095238095 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.Admission = '-' T… |
|---|
| 0.7636363636363637 |

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

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query filters on `Description` for the year 1997, while the prediction filters on `First Date`. The evidence specifies `Description`, so this different column changes which patients are counted.

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
SELECT COUNT(T1.ID) FROM Patient AS T1 WHERE T1.SEX = 'F' AND STRFTIME('%Y', T1.`First Date`) = '1997' AND T1.Admission = '-'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 161 |

Predicted (first 1 of 1 rows):

| COUNT(T1.ID) |
|---|
| 61 |

## 1166 / thrombosis_prediction / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query selects `Diagnosis` from `Patient` (`T1.Diagnosis`), while the prediction selects `Diagnosis` from `Examination` (`T2.Diagnosis`). The prediction also omits the non-NULL symptoms filter.

Gold label suspect: yes.

Question:

```text
What are the symptoms observed by the youngest patient to ever did a medical examination? Identify their diagnosis.
```

Evidence:

```text
The larger the birthday value, the younger the person is, and vice versa; symptoms observed refers to the symptoms is not NULL
```

Gold SQL:

```sql
SELECT T2.Symptoms, T1.Diagnosis FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T2.Symptoms IS NOT NULL ORDER BY T1.Birthday DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T2.Symptoms, T2.Diagnosis FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID ORDER BY T1.Birthday DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| Symptoms | Diagnosis |
|---|---|
| CNS susp | SLE |

Predicted (first 1 of 1 rows):

| Symptoms | Diagnosis |
|---|---|
| None | SjS |

## 1169 / thrombosis_prediction / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What is the ratio of male to female patients among all those with abnormal uric acid counts?
```

Evidence:

```text
male refers to SEX = 'M'; female refers to SEX = 'F'; abnormal uric acid refers to UA < = '8.0' where SEX = 'M', UA < = '6.5' where SEX = 'F'; calculation = DIVIDE(SUM(UA <= '8.0' and SEX = 'M'), SUM(UA <= '6.5 and SEX = 'F'))
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.UA <= 8.0 AND T1.SEX = 'M' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.UA <= 6.5 AND T1.SEX = 'F' THEN 1 ELSE 0 END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T1.SEX = 'M' THEN T1.ID END) AS REAL) / COUNT(DISTINCT CASE WHEN T1.SEX = 'F' THEN T1.ID END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE (T1.SEX = 'M' AND T2.UA <= 8.0) OR (T1.SEX = 'F' AND T2.UA <= 6.5)
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.UA <= 8.0 AND T1.… |
|---|
| 0.20566810835419985 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T1.SEX = … |
|---|
| 0.184 |

## 1185 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query compares monthly SUM totals and divides by the December total. The prediction uses MAX values instead and divides by the November maximum, changing the aggregation and rate calculation.

Gold label suspect: yes.

Question:

```text
For the patient who was born on 1959/2/18, what is the decrease rate for his/her total cholesterol from November to December in 1981?
```

Evidence:

```text
born on 1959/2/18 refers to Birthday = '1959-02-18'; calculation = DIVISION(SUBTRACT(SUM(Birthday = '1959-02-18' and Date like '1981-11-%' THEN `T-CHO`), SUM(Birthday = '1959-02-18' and Date like '1981-12-%' THEN `T-CHO`)), SUM(Birthday = '1959-02-18' and Date like '1981-12-%' THEN `T-CHO`))
```

Gold SQL:

```sql
SELECT CAST((SUM(CASE WHEN T2.Date LIKE '1981-11-%' THEN T2.`T-CHO` ELSE 0 END) - SUM(CASE WHEN T2.Date LIKE '1981-12-%' THEN T2.`T-CHO` ELSE 0 END)) AS REAL) / SUM(CASE WHEN T2.Date LIKE '1981-12-%' THEN T2.`T-CHO` ELSE 0 END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.Birthday = '1959-02-18'
```

Predicted SQL:

```sql
SELECT CAST(MAX(CASE WHEN STRFTIME('%m', T2.Date) = '11' THEN T2.`T-CHO` END) - MAX(CASE WHEN STRFTIME('%m', T2.Date) = '12' THEN T2.`T-CHO` END) AS REAL) * 100 / MAX(CASE WHEN STRFTIME('%m', T2.Date) = '11' THEN T2.`T-CHO` END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.Birthday = '1959-02-18' AND STRFTIME('%Y', T2.Date) = '1981'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST((SUM(CASE WHEN T2.Date LIKE '1981-… |
|---|
| 0.06030150753768844 |

Predicted (first 1 of 1 rows):

| CAST(MAX(CASE WHEN STRFTIME('%m', T2.Da… |
|---|
| 5.687203791469194 |

## 1198 / thrombosis_prediction / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query requires Diagnosis = 'APS', while the prediction uses LIKE '%APS%', which also counts diagnoses containing APS as a substring. This broadens the filter and produces 51 instead of 16.

Question:

```text
How many female patients were given an APS diagnosis?
```

Evidence:

```text
female refers to SEX = 'F'; APS diagnosis refers to Diagnosis='APS'
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

## 1205 / thrombosis_prediction / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The conditions and join/filter logic match, but the gold returns boolean true/false while the prediction returns the text values 'Yes'/'No'. The different output values make the result rows unequal.

Gold label suspect: yes.

Question:

```text
Was the patient with the number 57266's uric acid within a normal range?
```

Evidence:

```text
uric acid within a normal range refers to UA > 8.0 and SEX = 'M'OR UA > 6.5 and SEX = 'F'
```

Gold SQL:

```sql
SELECT CASE WHEN (T1.SEX = 'F' AND T2.UA > 6.5) OR (T1.SEX = 'M' AND T2.UA > 8.0) THEN true ELSE false END FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.ID = 57266
```

Predicted SQL:

```sql
SELECT CASE WHEN (T1.SEX = 'M' AND T2.UA > 8.0) OR (T1.SEX = 'F' AND T2.UA > 6.5) THEN 'Yes' ELSE 'No' END FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.ID = 57266
```

Result diff:

Gold 67 rows, predicted 67 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 67 rows):

| CASE WHEN (T1.SEX = 'F' AND T2.UA > 6.5… |
|---|
| 0 |
| 0 |
| 0 |
| 0 |
| 0 |

Predicted (first 5 of 67 rows):

| CASE WHEN (T1.SEX = 'M' AND T2.UA > 8.0… |
|---|
| No |
| No |
| No |
| No |
| No |

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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The evidence says to list patients using GROUP_CONCAT(DISTINCT ID), but the prediction counts distinct IDs per sex instead. It also groups only by sex, rather than returning the patient IDs as in the gold query.

Gold label suspect: yes.

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
SELECT T1.ID,T1.SEX FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-BIL` >= 2.0 GROUP BY T1.SEX,T1.ID
```

Predicted SQL:

```sql
SELECT T1.SEX, COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-BIL` >= 2.0 GROUP BY T1.SEX
```

Result diff:

Gold 10 rows, predicted 2 rows. Within the previews: 5 rows only in gold, 2 only in predicted.

Gold (first 5 of 10 rows):

| ID | SEX |
|---|---|
| 43003 | M |
| 250391 | F |
| 444499 | M |
| 1137040 | M |
| 1180510 | F |

Predicted (first 2 of 2 rows):

| SEX | COUNT(DISTINCT T1.ID) |
|---|---|
| F | 5 |
| M | 5 |

## 1227 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What is the average age of the male patient with high cholesterol?
```

Evidence:

```text
average age = DIVIDE(SUM(SUBTRACT(YEAR(NOW()), YEAR(birthday))), COUNT(ID)); male patient refers to sex = 'M'; high cholesterol refers to `T-CHO` > = 250;
```

Gold SQL:

```sql
SELECT AVG(STRFTIME('%Y', date('NOW')) - STRFTIME('%Y', T1.Birthday)) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-CHO` >= 250 AND T1.SEX = 'M'
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT DISTINCT T1.ID, T1.Birthday FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M' AND T2.`T-CHO` >= 250) SELECT AVG(CAST(STRFTIME('%Y', CURRENT_DATE) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER)) FROM cte1 AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(STRFTIME('%Y', date('NOW')) - STRFT… |
|---|
| 74.68535825545172 |

Predicted (first 1 of 1 rows):

| AVG(CAST(STRFTIME('%Y', CURRENT_DATE) A… |
|---|
| 71.95 |

## 1235 / thrombosis_prediction / moderate

Label: `date_handling` (classifier, gpt-6-luna): The predicted query calculates age from elapsed days divided by 365.25, while the gold query subtracts the calendar-year components. This produces different ages for some patients, such as 53 instead of 54.

Question:

```text
What are the patient's diagnosis for those who has lower red blood blood cell? State their ID and age.
```

Evidence:

```text
patient's diagnosis refers to Diagnosis; lower red blood cell refers to RBC < 3.5; age = SUBTRACT(year(current_timestamp), year(Birthday)); 
```

Gold SQL:

```sql
SELECT DISTINCT T1.Diagnosis, T1.ID , STRFTIME('%Y', CURRENT_TIMESTAMP) -STRFTIME('%Y', T1.Birthday) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.RBC < 3.5
```

Predicted SQL:

```sql
SELECT DISTINCT T1.Diagnosis, T1.ID, CAST((JULIANDAY(CURRENT_DATE) - JULIANDAY(T1.Birthday)) / 365.25 AS INTEGER) AS c1 FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.RBC < 3.5
```

Result diff:

Gold 73 rows, predicted 73 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 5 of 73 rows):

| Diagnosis | ID | STRFTIME('%Y', CURRENT_TIMESTAMP) -STRF… |
|---|---|---|
| RA, SLE susp | 27654 | 90 |
| SLE, MCTD | 30609 | 82 |
| SJS | 58139 | 54 |
| RA | 71417 | 97 |
| RA | 130370 | 74 |

Predicted (first 5 of 73 rows):

| Diagnosis | ID | c1 |
|---|---|---|
| RA, SLE susp | 27654 | 90 |
| SLE, MCTD | 30609 | 82 |
| SJS | 58139 | 53 |
| RA | 71417 | 96 |
| RA | 130370 | 74 |

## 1241 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns one value by subtracting the high-range count from the low-range count, while the prediction returns two separate counts. The prediction also counts distinct patient IDs rather than summing matching rows.

Gold label suspect: yes.

Question:

```text
For patients with abnormal platelet level, state the number of patients with lower than normal range. How is it compare to the number of patients with higher than normal range?
```

Evidence:

```text
abnormal platelet level refers to PLT <= 100 or PLT >= 400; platelet level lower than normal range refers to PLT < 100; calculation = SUBTRACT(SUM(PLT < 100), SUM(PLT > 400)); platelet level higher than normal range refers to PLT > 400;
```

Gold SQL:

```sql
SELECT SUM(CASE WHEN T2.PLT <= 100 THEN 1 ELSE 0 END) - SUM(CASE WHEN T2.PLT >= 400 THEN 1 ELSE 0 END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT CASE WHEN T1.PLT <= 100 THEN T1.ID END), COUNT(DISTINCT CASE WHEN T1.PLT >= 400 THEN T1.ID END) FROM Laboratory AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(CASE WHEN T2.PLT <= 100 THEN 1 ELSE… |
|---|
| -562 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT CASE WHEN T1.PLT <= 100 … | COUNT(DISTINCT CASE WHEN T1.PLT >= 400 … |
|---|---|
| 37 | 82 |

## 1243 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold denominator counts records with PT ≥ 14, while the prediction denominator counts all distinct patients. The prediction also uses distinct-patient counts where the gold counts matching laboratory rows.

Gold label suspect: yes.

Question:

```text
For all patients who are older than 55 years old, what is the percentage of female who has abnormal prothrombin time (PT)?
```

Evidence:

```text
older than 55 years old = SUBTRACT(year(current_timestamp), year(Birthday)) > 55; abnormal prothrombin time (PT) refers to PT > = 14; percentage = DIVIDE(SUM(PT > = 14 AND SEX = 'F'), SUM(PT > = 14)) * 100; female refers to sex = 'F'; 
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.PT >= 14 AND T1.SEX = 'F' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(CASE WHEN T2.PT >= 14 THEN 1 ELSE 0 END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T1.Birthday) > 55
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T1.SEX = 'F' AND T2.PT >= 14 THEN T1.ID END) AS REAL) * 100 / COUNT(DISTINCT T1.ID) FROM Patient AS T1 LEFT JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.Birthday < DATE(CURRENT_DATE, '-55 years')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.PT >= 14 AND T1.S… |
|---|
| 1.2030885257676422 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T1.SEX = … |
|---|
| 0.9316770186335404 |

## 1247 / thrombosis_prediction / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Among the male patients who have a normal level of white blood cells, how many of them have an abnormal fibrinogen level?
```

Evidence:

```text
male patients refers to Sex = 'M'; normal level of white blood cells refers to WBC > 3.5 and WBC <9.0; abnormal fibrinogen level refers to FG < = 150 or FG > = 450; Don't compute repetitive ones.
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.FG <= 150 OR T2.FG >= 450 AND T2.WBC > 3.5 AND T2.WBC < 9.0 AND T1.SEX = 'M'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M' AND T2.WBC > 3.5 AND T2.WBC < 9.0 AND (T2.FG <= 150 OR T2.FG >= 450)
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 75 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 6 |

## 1252 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Among the patients with a normal Ig G level, how many of them have symptoms?
```

Evidence:

```text
normal Ig G level refers to IGG > 900 and IGG < 2000; have symptoms refers to Symptoms IS NOT NULL;
```

Gold SQL:

```sql
SELECT COUNT(T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID INNER JOIN Examination AS T3 ON T3.ID = T2.ID WHERE T2.IGG BETWEEN 900 AND 2000 AND T3.Symptoms IS NOT NULL
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Laboratory AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.IGG > 900 AND T1.IGG < 2000 AND T2.Symptoms IS NOT NULL AND T2.Symptoms <> ''
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.ID) |
|---|
| 4 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 1 |

## 1254 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
How many patients with a normal Ig A level came to the hospital after 1990/1/1?
```

Evidence:

```text
normal Ig A level refers to IGA > 80 AND IGA < 500; came to the hospital after 1990/1/1 refers to YEAR(`First Date`) > = 1990;
```

Gold SQL:

```sql
SELECT COUNT(T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGA BETWEEN 80 AND 500 AND  strftime('%Y',  T1.`First Date`) > '1990'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGA > 80 AND T2.IGA < 500 AND T1.`First Date` > '1990-01-01'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.ID) |
|---|
| 1590 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 140 |

## 1255 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
For the patients with an abnormal Ig M level, what is the most common disease they are diagnosed with?
```

Evidence:

```text
abnormal Ig M level refers to IGM <=40 OR IGM >= 400; most common disease refers to MAX(COUNT(Diagnosis));
```

Gold SQL:

```sql
SELECT T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGM NOT BETWEEN 40 AND 400 GROUP BY T1.Diagnosis ORDER BY COUNT(T1.Diagnosis) DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE (T2.IGM <= 40 OR T2.IGM >= 400) AND T1.Diagnosis IS NOT NULL GROUP BY T1.Diagnosis ORDER BY COUNT(DISTINCT T1.ID) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| Diagnosis |
|---|
| RA |

Predicted (first 1 of 1 rows):

| Diagnosis |
|---|
| SLE |

## 1256 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold filters abnormal CRP as `T2.CRP = '+'`, while the prediction substitutes a numeric threshold and exclusion condition. It also broadens missing Description to include empty strings, but the CRP filter is the first substantive mismatch.

Gold label suspect: yes.

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
SELECT COUNT(T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE (T2.CRP = '+' ) AND T1.Description IS NULL
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE (T1.Description IS NULL OR T1.Description = '') AND T2.CRP NOT IN ('-', '+' || '-') AND CAST(T2.CRP AS REAL) >= 1.0
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.ID) |
|---|
| 208 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 38 |

## 1267 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction filters SM using `'-'` and `'+-'`, but the evidence and gold query use the stored values `'negative'` and `'0'`. This yields 0 instead of the gold count of 7.

Gold label suspect: yes.

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
SELECT COUNT(T1.ID) FROM Examination AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.SM IN ('negative','0') AND T1.Thrombosis = 0
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Laboratory AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.SM IN ('-', '+' || '-') AND T2.Thrombosis = 0
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.ID) |
|---|
| 7 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 0 |

## 1270 / thrombosis_prediction / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters SC170 to `'negative'` or `'0'`, while the prediction filters it to `'-'` (the expression `'+' \|\| '-'` also evaluates to `'-'`). This changes which patients qualify.

Question:

```text
Among the patients who has a normal anti-scl70, how many of them are female and does not have any symptom?
```

Evidence:

```text
normal anti-scl70 refers to SC170 IN('negative', '0'); female refers to Sex = 'F'; does not have any symptom refers to symptoms IS NULL; Should consider DISTINCT in the final result;
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID INNER JOIN Examination AS T3 ON T3.ID = T2.ID WHERE (T2.SC170 = 'negative' OR T2.SC170 = '0') AND T1.SEX = 'F' AND T3.Symptoms IS NULL
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID INNER JOIN Examination AS T3 ON T1.ID = T3.ID WHERE T2.SC170 IN ('-', '+' || '-') AND T1.SEX = 'F' AND T3.Symptoms IS NULL
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 2 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 0 |

## 1275 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The evidence specifies normal as CENTROMEA and SSB in ('-', '+-'), but the gold query uses ('negative', '0'). The predicted query follows the evidence, so the gold label is suspect.

Question:

```text
Among the patients who has a normal level of anti-centromere and a normal level of anti-SSB, how many of them are male?
```

Evidence:

```text
normal level of anti-centromere refers to CENTROMEA IN('-', '+-'); normal level of anti-SSB refers to SSB IN('-', '+-'); male refers to Sex = 'M'; Should consider DISTINCT in the final result;
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

## 1302 / thrombosis_prediction / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
For the patients with a normal range of creatinine phosphokinase, how many of them have a positive measure of degree of coagulation?
```

Evidence:

```text
normal range of creatinine phosphokinase refers to CPK < 250; positive measure of degree of coagulation refers to KCT = '+' or RVVT = '+' or LAC = '+' ;
```

Gold SQL:

```sql
SELECT COUNT(T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID INNER JOIN Examination AS T3 ON T1.ID = T3.ID WHERE T2.CPK < 250 AND (T3.KCT = '+' OR T3.RVVT = '+' OR T3.LAC = '+')
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Laboratory AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.CPK < 250 AND (T2.KCT = '+' OR T2.RVVT = '+' OR T2.LAC = '+')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.ID) |
|---|
| 7 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 1 |

## 1322 / student_club / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Among the events attended by more than 10 members of the Student_Club, how many of them are meetings?
```

Evidence:

```text
meetings events refers to type = 'Meeting'; attended by more than 10 members refers to COUNT(event_id) > 10
```

Gold SQL:

```sql
SELECT COUNT(DISTINCT T1.event_id) FROM event AS T1 INNER JOIN attendance AS T2 ON T1.event_id = T2.link_to_event WHERE T1.type = 'Meeting' GROUP BY T1.event_id HAVING COUNT(T2.link_to_event) > 10
```

Predicted SQL:

```sql
SELECT COUNT(*) FROM (SELECT T1.event_id FROM event AS T1 INNER JOIN attendance AS T2 ON T1.event_id = T2.link_to_event WHERE T1.type = 'Meeting' GROUP BY T1.event_id HAVING COUNT(T2.link_to_member) > 10) AS T3
```

Result diff:

Gold 4 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 4 of 4 rows):

| COUNT(DISTINCT T1.event_id) |
|---|
| 1 |
| 1 |
| 1 |
| 1 |

Predicted (first 1 of 1 rows):

| COUNT(*) |
|---|
| 4 |

## 1399 / student_club / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction filters for Maya’s attendance at 'Women's Soccer' and returns whether a match exists, which answers the question. The gold query does not filter by event and instead returns one YES or NULL per attendance record, so it does not correctly express the question.

Gold label suspect: yes.

Question:

```text
Did Maya Mclean attend the 'Women's Soccer' event?
```

Evidence:

```text
Maya Mclean is the full name; full name refers to first_name, last_name; 'Women's Soccer' is an event_name
```

Gold SQL:

```sql
SELECT CASE WHEN T3.event_name = 'Women''s Soccer' THEN 'YES' END AS result FROM member AS T1 INNER JOIN attendance AS T2 ON T1.member_id = T2.link_to_member INNER JOIN event AS T3 ON T2.link_to_event = T3.event_id WHERE T1.first_name = 'Maya' AND T1.last_name = 'Mclean'
```

Predicted SQL:

```sql
SELECT CASE WHEN COUNT(*) > 0 THEN 'Yes' ELSE 'No' END FROM attendance AS T1 INNER JOIN member AS T2 ON T1.link_to_member = T2.member_id INNER JOIN event AS T3 ON T1.link_to_event = T3.event_id WHERE T2.first_name = 'Maya' AND T2.last_name = 'Mclean' AND T3.event_name = 'Women''s Soccer'
```

Result diff:

Gold 14 rows, predicted 1 rows. Within the previews: 2 rows only in gold, 1 only in predicted.

Gold (first 5 of 14 rows):

| result |
|---|
| YES |
| None |
| None |
| None |
| None |

Predicted (first 1 of 1 rows):

| CASE WHEN COUNT(*) > 0 THEN 'Yes' ELSE … |
|---|
| Yes |

## 1422 / student_club / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
State the category of events were held at MU 215.
```

Evidence:

```text
'MU 215' is the location of event; 
```

Gold SQL:

```sql
SELECT DISTINCT T2.category FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event WHERE T1.location = 'MU 215'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.type FROM event AS T1 WHERE T1.location = 'MU 215'
```

Result diff:

Gold 4 rows, predicted 3 rows. Within the previews: 4 rows only in gold, 3 only in predicted.

Gold (first 4 of 4 rows):

| category |
|---|
| Advertisement |
| Food |
| Speaker Gifts |
| Parking |

Predicted (first 3 of 3 rows):

| type |
|---|
| Meeting |
| Election |
| Guest Speaker |

## 1427 / student_club / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What are the budget category of the events located at MU 215 and a guest speaker type with a 0 budget spent?
```

Evidence:

```text
budget category refers to category; events located at refers to location; type = 'Guest Speaker'; 0 budget spent refers to spent = 0; 
```

Gold SQL:

```sql
SELECT DISTINCT T2.category, T1.type FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event WHERE T1.location = 'MU 215' AND T2.spent = 0 AND T1.type = 'Guest Speaker'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.category FROM budget AS T1 INNER JOIN event AS T2 ON T1.link_to_event = T2.event_id WHERE T2.location = 'MU 215' AND T2.type = 'Guest Speaker' AND T1.spent = 0
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 4 of 4 rows):

| category | type |
|---|---|
| Speaker Gifts | Guest Speaker |
| Food | Guest Speaker |
| Parking | Guest Speaker |
| Advertisement | Guest Speaker |

Predicted (first 4 of 4 rows):

| category |
|---|
| Speaker Gifts |
| Food |
| Parking |
| Advertisement |

## 1482 / debit_card_specializing / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks which segments have the highest and lowest percentage increases in EUR, but the gold query returns only three percentage values and does not filter for EUR. The prediction identifies the two extreme segments and includes the EUR filter, so the gold query does not answer the question as asked.

Gold label suspect: yes.

Question:

```text
Which of the three segments—SME, LAM and KAM—has the biggest and lowest percentage increases in consumption paid in EUR between 2012 and 2013?
```

Evidence:

```text
Increase or Decrease = consumption for 2013 - consumption for 2012; Percentage of Increase = (Increase or Decrease / consumption for 2013) * 100%; The first 4 strings of the Date values in the yearmonth table can represent year
```

Gold SQL:

```sql
SELECT CAST((SUM(IIF(T1.Segment = 'SME' AND T2.Date LIKE '2013%', T2.Consumption, 0)) - SUM(IIF(T1.Segment = 'SME' AND T2.Date LIKE '2012%', T2.Consumption, 0))) AS FLOAT) * 100 / SUM(IIF(T1.Segment = 'SME' AND T2.Date LIKE '2012%', T2.Consumption, 0)), CAST(SUM(IIF(T1.Segment = 'LAM' AND T2.Date LIKE '2013%', T2.Consumption, 0)) - SUM(IIF(T1.Segment = 'LAM' AND T2.Date LIKE '2012%', T2.Consumption, 0)) AS FLOAT) * 100 / SUM(IIF(T1.Segment = 'LAM' AND T2.Date LIKE '2012%', T2.Consumption, 0)) , CAST(SUM(IIF(T1.Segment = 'KAM' AND T2.Date LIKE '2013%', T2.Consumption, 0)) - SUM(IIF(T1.Segment = 'KAM' AND T2.Date LIKE '2012%', T2.Consumption, 0)) AS FLOAT) * 100 / SUM(IIF(T1.Segment = 'KAM' AND T2.Date LIKE '2012%', T2.Consumption, 0)) FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.Segment, SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2012' THEN T2.Consumption ELSE 0 END) AS c1, SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2013' THEN T2.Consumption ELSE 0 END) AS c2 FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Currency = 'EUR' AND T1.Segment IN ('SME', 'LAM', 'KAM') AND SUBSTR(T2.Date, 1, 4) IN ('2012', '2013') GROUP BY T1.Segment), cte2 AS (SELECT T1.Segment, CAST(T1.c2 - T1.c1 AS REAL) * 100 / NULLIF(T1.c1, 0) AS c1 FROM cte1 AS T1) SELECT T1.Segment, T1.c1 FROM (SELECT T2.Segment, T2.c1 FROM cte2 AS T2 WHERE T2.c1 IS NOT NULL ORDER BY T2.c1 DESC LIMIT 1) AS T1 UNION ALL SELECT T3.Segment, T3.c1 FROM (SELECT T4.Segment, T4.c1 FROM cte2 AS T4 WHERE T4.c1 IS NOT NULL ORDER BY T4.c1 ASC LIMIT 1) AS T3
```

Result diff:

Gold 1 rows, predicted 2 rows. Within the previews: 1 rows only in gold, 2 only in predicted.

Gold (first 1 of 1 rows):

| CAST((SUM(IIF(T1.Segment = 'SME' AND T2… | CAST(SUM(IIF(T1.Segment = 'LAM' AND T2.… | CAST(SUM(IIF(T1.Segment = 'KAM' AND T2.… |
|---|---|---|
| 545.4018999790969 | 681.5824574939339 | 708.1124062978664 |

Predicted (first 2 of 2 rows):

| Segment | c1 |
|---|---|
| SME | 734.7140627123255 |
| LAM | 539.8291924960649 |

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

## 1500 / debit_card_specializing / simple

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction omits the `yearmonth` join used by the gold query and instead joins products directly to transactions. It consequently filters `transactions_1k.Date` rather than the `yearmonth.Date` value identifying September 2013.

Question:

```text
Please list the product description of the products consumed in September, 2013.
```

Evidence:

```text
September 2013 refers to 201309; The first 4 strings of the Date values in the yearmonth table can represent year; The 5th and 6th string of the date can refer to month.
```

Gold SQL:

```sql
SELECT T3.Description FROM transactions_1k AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID INNER JOIN products AS T3 ON T1.ProductID = T3.ProductID WHERE T2.Date = '201309'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.Description FROM products AS T1 INNER JOIN transactions_1k AS T2 ON T1.ProductID = T2.ProductID WHERE STRFTIME('%Y', T2.Date) = '2013' AND STRFTIME('%m', T2.Date) = '09'
```

Result diff:

Gold 976 rows, predicted 0 rows. Within the previews: 3 rows only in gold, 0 only in predicted.

Gold (first 5 of 976 rows):

| Description |
|---|
| Nafta |
| Nafta |
| Provoz.nápl. |
| Natural |
| Nafta |

Predicted (first 0 of 0 rows):

| Description |
|---|

## 1501 / debit_card_specializing / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query gets the month from `yearmonth.Date`, joined by `CustomerID`; the prediction instead filters `transactions_1k.Date` and omits `yearmonth`.

Question:

```text
Please list the countries of the gas stations with transactions taken place in June, 2013.
```

Evidence:

```text
June 2013 refers to '201306'; The first 4 strings of the Date values in the yearmonth table can represent year; The 5th and 6th string of the date can refer to month;
```

Gold SQL:

```sql
SELECT DISTINCT T2.Country FROM transactions_1k AS T1 INNER JOIN gasstations AS T2 ON T1.GasStationID = T2.GasStationID INNER JOIN yearmonth AS T3 ON T1.CustomerID = T3.CustomerID WHERE T3.Date = '201306'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.Country FROM gasstations AS T1 INNER JOIN transactions_1k AS T2 ON T1.GasStationID = T2.GasStationID WHERE STRFTIME('%Y', T2.Date) = '2013' AND STRFTIME('%m', T2.Date) = '06'
```

Result diff:

Gold 2 rows, predicted 0 rows. Within the previews: 2 rows only in gold, 0 only in predicted.

Gold (first 2 of 2 rows):

| Country |
|---|
| CZE |
| SVK |

Predicted (first 0 of 0 rows):

| Country |
|---|

## 1505 / debit_card_specializing / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Among the customers who paid in euro, how many of them have a monthly consumption of over 1000?
```

Evidence:

```text
Pays in euro = Currency = 'EUR'.
```

Gold SQL:

```sql
SELECT COUNT(*) FROM yearmonth AS T1 INNER JOIN customers AS T2 ON T1.CustomerID = T2.CustomerID WHERE T2.Currency = 'EUR' AND T1.Consumption > 1000.00
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.CustomerID) FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Currency = 'EUR' AND T2.Consumption > 1000
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 2730 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.CustomerID) |
|---|
| 391 |

## 1525 / debit_card_specializing / simple

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
What is the percentage of the customers who used EUR in 2012/8/25?
```

Evidence:

```text
'2012/8/25' can be represented by '2012-08-25'
```

Gold SQL:

```sql
SELECT CAST(SUM(IIF(T2.Currency = 'EUR', 1, 0)) AS FLOAT) * 100 / COUNT(T1.CustomerID) FROM transactions_1k AS T1 INNER JOIN customers AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Date = '2012-08-25'
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T2.Currency = 'EUR' THEN T1.CustomerID END) AS REAL) * 100 / COUNT(DISTINCT T1.CustomerID) FROM transactions_1k AS T1 INNER JOIN customers AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Date = '2012-08-25'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(T2.Currency = 'EUR', 1, 0)… |
|---|
| 1.6470588235294117 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.Curren… |
|---|
| 2.7027027027027026 |

## 1526 / debit_card_specializing / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question identifies the customer by a payment of 634.8 on 2012-08-25, but the gold query selects customers with `Price = 1513.12` on that date. The prediction’s `Amount * Price = 634.8` condition matches the stated payment amount.

Gold label suspect: yes.

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
SELECT CAST(SUM(IIF(SUBSTRING(Date, 1, 4) = '2012', Consumption, 0)) - SUM(IIF(SUBSTRING(Date, 1, 4) = '2013', Consumption, 0)) AS FLOAT) / SUM(IIF(SUBSTRING(Date, 1, 4) = '2012', Consumption, 0)) FROM yearmonth WHERE CustomerID = ( SELECT T1.CustomerID FROM transactions_1k AS T1 INNER JOIN gasstations AS T2 ON T1.GasStationID = T2.GasStationID WHERE T1.Date = '2012-08-25' AND T1.Price  = 1513.12 )
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT DISTINCT T1.CustomerID FROM transactions_1k AS T1 WHERE T1.Date = '2012-08-25' AND T1.Amount * T1.Price = 634.8) SELECT CAST(SUM(CASE WHEN T1.Date BETWEEN '201201' AND '201212' THEN T1.Consumption ELSE 0 END) - SUM(CASE WHEN T1.Date BETWEEN '201301' AND '201312' THEN T1.Consumption ELSE 0 END) AS REAL) * 100 / SUM(CASE WHEN T1.Date BETWEEN '201201' AND '201212' THEN T1.Consumption ELSE 0 END) FROM yearmonth AS T1 INNER JOIN cte1 AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Date BETWEEN '201201' AND '201312' GROUP BY T1.CustomerID
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(SUBSTRING(Date, 1, 4) = '2… |
|---|
| None |

Predicted (first 0 of 0 rows):

| CAST(SUM(CASE WHEN T1.Date BETWEEN '201… |
|---|

## 1529 / debit_card_specializing / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query sums `transactions_1k.Price` for gas-station transactions, while the prediction sums `yearmonth.Consumption` instead. It also omits the gas-station and transaction joins, but the first issue is using different source columns and table.

Gold label suspect: yes.

Question:

```text
What is the amount spent by customer "38508" at the gas stations? How much had the customer spent in January 2012?
```

Evidence:

```text
January 2012 refers to the Date value = '201201'
```

Gold SQL:

```sql
SELECT SUM(T1.Price ) , SUM(IIF(T3.Date = '201201', T1.Price, 0)) FROM transactions_1k AS T1 INNER JOIN gasstations AS T2 ON T1.GasStationID = T2.GasStationID INNER JOIN yearmonth AS T3 ON T1.CustomerID = T3.CustomerID WHERE T1.CustomerID = '38508'
```

Predicted SQL:

```sql
SELECT SUM(T1.Consumption), SUM(CASE WHEN T1.Date = '201201' THEN T1.Consumption ELSE 0 END) FROM yearmonth AS T1 WHERE T1.CustomerID = 38508
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(T1.Price ) | SUM(IIF(T3.Date = '201201', T1.Price, 0… |
|---|---|
| 68740.2 | 3437.01 |

Predicted (first 1 of 1 rows):

| SUM(T1.Consumption) | SUM(CASE WHEN T1.Date = '201201' THEN T… |
|---|---|
| 5124646.35 | 67156.94 |

## 1531 / debit_card_specializing / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Who is the top spending customer and how much is the average price per single item purchased by this customer? What currency was being used?
```

Evidence:

```text
average price per single item = Total(price) / Total(amount)
```

Gold SQL:

```sql
SELECT T2.CustomerID, SUM(T2.Price / T2.Amount), T1.Currency FROM customers AS T1 INNER JOIN transactions_1k AS T2 ON T1.CustomerID = T2.CustomerID WHERE T2.CustomerID = ( SELECT CustomerID FROM yearmonth ORDER BY Consumption DESC LIMIT 1 ) GROUP BY T2.CustomerID, T1.Currency
```

Predicted SQL:

```sql
SELECT T1.CustomerID, CAST(SUM(T2.Amount * T2.Price) AS REAL) / SUM(T2.Amount) AS c1, T1.Currency FROM customers AS T1 INNER JOIN transactions_1k AS T2 ON T1.CustomerID = T2.CustomerID GROUP BY T1.CustomerID, T1.Currency ORDER BY SUM(T2.Amount * T2.Price) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CustomerID | SUM(T2.Price / T2.Amount) | Currency |
|---|---|---|
| 12459 | 203.8560787354258 | CZK |

Predicted (first 1 of 1 rows):

| CustomerID | c1 | Currency |
|---|---|---|
| 13665 | 5762.49 | CZK |
