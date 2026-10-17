# Failures: best on bird_minidev / dev

90 of 350 questions failed. Evidence on, git `41a88a836fa385225e7737edd13ac9197637fa02`, complete: 350 questions.

## 17 / california_schools / simple

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The join and score filter match, but the prediction returns School and CharterNum instead of the gold query’s CharterNum, AvgScrWrite, and WritingScoreRank columns.

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
SELECT T2.School, T2.CharterNum FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T1.AvgScrWrite > 499 AND T2.CharterNum IS NOT NULL ORDER BY T1.AvgScrWrite DESC
```

Result diff:

Gold 58 rows, predicted 58 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 58 rows):

| CharterNum | AvgScrWrite | WritingScoreRank |
|---|---|---|
| 0210 | 630 | 1 |
| 0890 | 593 | 2 |
| 0290 | 582 | 3 |
| 0352 | 581 | 4 |
| 0930 | 579 | 5 |

Predicted (first 5 of 58 rows):

| School | CharterNum |
|---|---|
| Pacific Collegiate Charter | 0210 |
| University High | 0890 |
| OCSA | 0290 |
| Alameda Community Learning Center | 0352 |
| Northcoast Preparatory and Performing A… | 0930 |

## 25 / california_schools / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query gets the school name, Riverside district, and funding type from `satscores` and `frpm`, while the prediction uses `schools` for those fields. It also filters individual math scores instead of applying the gold average threshold, but the source-table mismatch is the first issue to fix.

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
SELECT T1.School, T1.FundingType FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.County = 'Riverside' AND T2.AvgScrMath > 400
```

Result diff:

Gold 6 rows, predicted 80 rows. Within the previews: 5 rows only in gold, 4 only in predicted.

Gold (first 5 of 6 rows):

| sname | Charter Funding Type |
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
SELECT T1.School, T1.Street, T1.City, T1.State, T1.Zip FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.County = 'Monterey' AND T1.EILName = 'High School' AND T2.`FRPM Count (Ages 5-17)` > 800
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

| School | Street | City | State | Zip |
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query uses `RANK() ... PARTITION BY County` and includes all schools ranked 5th or higher, including ties. The prediction uses `ORDER BY ... LIMIT 5` in each county, which returns at most five schools and excludes ties at the cutoff.

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
SELECT T1.School FROM schools AS T1 WHERE T1.`Virtual` = 'F' AND T1.CDSCode IN (SELECT T2.CDSCode FROM schools AS T2 INNER JOIN satscores AS T3 ON T2.CDSCode = T3.cds WHERE T2.County = T1.County AND T2.`Virtual` = 'F' AND T3.AvgScrRead IS NOT NULL ORDER BY T3.AvgScrRead DESC LIMIT 5)
```

Result diff:

Gold 34 rows, predicted 4 rows. Within the previews: 5 rows only in gold, 4 only in predicted.

Gold (first 5 of 34 rows):

| School |
|---|
| Dunlap Leadership Academy |
| Academy of Arts and Sciences: Fresno |
| Insight School of California |
| California Virtual Academy @ Kings |
| National University Academy, Armona |

Predicted (first 4 of 4 rows):

| School |
|---|
| California Virtual Academy @ Los Angeles |
| Insight @ Los Angeles |
| Capistrano Connections Academy |
| California Connections Academy @ Ripon |

## 87 / california_schools / challenging

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The predicted query selects AdmEmail3 in addition to AdmEmail1 and AdmEmail2, while the gold query returns only the first two email columns.

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
SELECT T1.AdmEmail1, T1.AdmEmail2, T1.AdmEmail3 FROM schools AS T1 WHERE T1.County = 'San Bernardino' AND T1.District = 'San Bernardino City Unified' AND T1.OpenDate BETWEEN '2009-01-01' AND '2010-12-31' AND T1.SOC = '62' AND T1.DOC = '54'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AdmEmail1 | AdmEmail2 |
|---|---|
| a.lucero@realjourney.org | j.hernandez@realjourney.org |

Predicted (first 1 of 1 rows):

| AdmEmail1 | AdmEmail2 | AdmEmail3 |
|---|---|---|
| a.lucero@realjourney.org | j.hernandez@realjourney.org | None |

## 94 / financial / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks for the oldest female client with the lowest average salary, but the gold query selects the account in the oldest female client’s district with the *highest* A11. The prediction’s oldest-first, lowest-A11 ordering is closer to the question’s intent.

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
SELECT T3.account_id, (SELECT MAX(T4.A11) FROM district AS T4) - T2.A11 AS c1 FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id INNER JOIN disp AS T3 ON T1.client_id = T3.client_id WHERE T1.gender = 'F' AND T1.birth_date IS NOT NULL AND T2.A11 IS NOT NULL ORDER BY T1.birth_date ASC, T2.A11 ASC LIMIT 1
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

Label: `gold_label_suspect` (classifier, gpt-6-luna): The gold query returns ten distinct district names in alphabetical order, which does not identify the top ten withdrawals. The prediction instead ranks withdrawal transactions by amount descending, a plausible reading of “top ten withdrawals.”

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
SELECT T3.A2, T1.amount FROM trans AS T1 INNER JOIN account AS T2 ON T1.account_id = T2.account_id INNER JOIN district AS T3 ON T2.district_id = T3.district_id WHERE T1.type = 'VYDAJ' AND T1.date LIKE '1996-01%' ORDER BY T1.amount DESC LIMIT 10
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

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction omits the account join and does not restrict dispositions to owners (`T3.type = 'OWNER'`). Consequently, it includes loans associated with any disposition for a male client rather than the gold query’s owner-linked accounts, producing a different growth rate.

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
SELECT CAST(SUM(CASE WHEN STRFTIME('%Y', T1.date) = '1997' THEN T1.amount ELSE 0 END) - SUM(CASE WHEN STRFTIME('%Y', T1.date) = '1996' THEN T1.amount ELSE 0 END) AS REAL) * 100 / SUM(CASE WHEN STRFTIME('%Y', T1.date) = '1996' THEN T1.amount ELSE 0 END) FROM loan AS T1 INNER JOIN disp AS T2 ON T1.account_id = T2.account_id INNER JOIN client AS T3 ON T2.client_id = T3.client_id WHERE T3.gender = 'M'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST((SUM(CASE WHEN STRFTIME('%Y', T1.d… |
|---|
| 25.300191222790616 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN STRFTIME('%Y', T1.da… |
|---|
| 25.36203967738821 |

## 194 / financial / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

Question:

```text
Provide the IDs and age of the client with high level credit card, which is eligible for loans.
```

Evidence:

```text
the credit card is high-level refers to card.type = 'gold'; eligible for loans refers to disp.type = 'OWNER'
```

Gold SQL:

```sql
SELECT T1.client_id, STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T3.birth_date) FROM disp AS T1 INNER JOIN card AS T2 ON T2.disp_id = T1.disp_id INNER JOIN client AS T3 ON T1.client_id = T3.client_id WHERE T2.type = 'gold' AND T1.type = 'OWNER'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.client_id, CAST(STRFTIME('%Y', 'now') AS INTEGER) - CAST(STRFTIME('%Y', T1.birth_date) AS INTEGER) - (STRFTIME('%m-%d', 'now') < STRFTIME('%m-%d', T1.birth_date)) AS c1 FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN card AS T3 ON T2.disp_id = T3.disp_id WHERE T3.type = 'gold' AND T2.type = 'OWNER'
```

Result diff:

Gold 88 rows, predicted 88 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 88 rows):

| client_id | STRFTIME('%Y', CURRENT_TIMESTAMP) - STR… |
|---|---|
| 9 | 91 |
| 41 | 58 |
| 79 | 57 |
| 326 | 59 |
| 548 | 89 |

Predicted (first 5 of 88 rows):

| client_id | c1 |
|---|---|
| 9 | 91 |
| 41 | 58 |
| 79 | 57 |
| 326 | 59 |
| 548 | 88 |

## 197 / toxicology / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts oxygen atoms per molecule, then averages those per-molecule counts. The prediction averages a Boolean oxygen-element test across joined atom-bond rows instead.

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
SELECT AVG(T1.element = 'o') FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.bond_type = '-'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(oxygen_count) |
|---|
| 99.68354430379746 |

Predicted (first 1 of 1 rows):

| AVG(T1.element = 'o') |
|---|
| 0.08006384774143697 |

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
SELECT CAST(SUM(CASE WHEN NOT EXISTS(SELECT T2.atom_id FROM atom AS T2 WHERE T2.molecule_id = T1.molecule_id AND T2.element = 'f') THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.molecule_id) FROM molecule AS T1 WHERE T1.label = '+'
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

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks for both the majority bond type and whether the molecule is carcinogenic, but the gold query returns only `bond_type`. The prediction also returns the molecule’s `label`, addressing the omitted part of the question.

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
SELECT T1.bond_type, T2.label FROM bond AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T1.molecule_id = 'TR010' GROUP BY T1.bond_type, T2.label ORDER BY COUNT(*) DESC LIMIT 1
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
SELECT DISTINCT T1.element FROM atom AS T1 WHERE T1.atom_id NOT IN (SELECT T2.atom_id FROM connected AS T2)
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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The filters differ: the gold requires `cardKingdomId IS NULL`, while the prediction requires `cardKingdomFoilId IS NULL` and `cardKingdomId IS NOT NULL`. This changes which cards qualify; the SELECT columns also differ (`id` versus `name`).

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
SELECT T1.name FROM cards AS T1 WHERE T1.borderColor = 'borderless' AND T1.cardKingdomFoilId IS NULL AND T1.cardKingdomId IS NOT NULL
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

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): Both queries use the same tables, join, and filters, but the gold returns distinct card IDs while the prediction returns distinct names. Selecting names also collapses printings that share a name, so the output differs.

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
SELECT DISTINCT T1.name FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T1.rarity = 'mythic' AND T2.status = 'Banned' AND T2.format = 'gladiator'
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

## 349 / card_games / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction counts rulings per card and returns the card with the highest count, along with its artist and promotional status. The gold query instead filters to promotional cards and selects based on which artist has the most distinct card UUIDs, rather than the card with the most rulings.

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
SELECT T1.name, T1.artist, T1.isPromo FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid GROUP BY T1.id, T1.name, T1.artist, T1.isPromo ORDER BY COUNT(T2.uuid) DESC LIMIT 1
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts matching cards by summing 1 for each matching language, while the prediction sums the card IDs, inflating the numerator. It also omits the cards-to-foreign_data join, but the first correction needed is the aggregation logic.

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
SELECT CAST(SUM(CASE WHEN T1.language = 'Chinese Simplified' THEN T1.id ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM foreign_data AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.language = 'Chine… |
|---|
| 8.773399659641314 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.language = 'Chine… |
|---|
| 988424.7336224726 |

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
SELECT COUNT(DISTINCT T1.id) FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T2.status = 'Banned' AND T1.borderColor = 'white'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.id) |
|---|
| 258 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.id) |
|---|
| 89 |

## 408 / card_games / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query checks `rulings.text` for “triggered ability,” while the prediction checks `cards.text`. It therefore reads the wrong text column/table for the requested information.

Question:

```text
How many unknown power cards contain info about the triggered ability
```

Evidence:

```text
unknown power cards refers to power is null or power = '*';contain info about the triggered ability refers to text contains 'triggered ability'
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

## 469 / card_games / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The predicted query returns 'Yes'/'No', while the gold query returns 'YES'/'NO'. Since result values are case-sensitive, the output differs.

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
SELECT CASE WHEN T2.mtgoCode IS NOT NULL THEN 'Yes' ELSE 'No' END FROM cards AS T1 INNER JOIN sets AS T2 ON T1.setCode = T2.code WHERE T1.name = 'Angel of Mercy'
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

| CASE WHEN T2.mtgoCode IS NOT NULL THEN … |
|---|
| Yes |
| Yes |
| Yes |
| Yes |
| Yes |

## 473 / card_games / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): Both queries use the same tables, join, and filter, but the gold returns a YES/NO expression while the prediction returns the raw isForeignOnly value. The result columns therefore differ in value representation.

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
SELECT T2.isForeignOnly FROM cards AS T1 INNER JOIN sets AS T2 ON T1.setCode = T2.code WHERE T1.name = 'Adarkar Valkyrie'
```

Result diff:

Gold 5 rows, predicted 5 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 5 rows):

| IIF(isForeignOnly = 1, 'YES', 'NO') |
|---|
| NO |
| NO |
| NO |
| NO |
| NO |

Predicted (first 5 of 5 rows):

| isForeignOnly |
|---|
| 0 |
| 0 |
| 0 |
| 0 |
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
WITH cte1 AS (SELECT T3.name, T2.convertedManaCost FROM sets AS T1 INNER JOIN cards AS T2 ON T1.code = T2.setCode INNER JOIN foreign_data AS T3 ON T2.uuid = T3.uuid WHERE T1.name = 'Coldsnap' AND T3.language = 'Italian') SELECT DISTINCT T1.name FROM cte1 AS T1 WHERE T1.convertedManaCost = (SELECT MAX(T2.convertedManaCost) FROM cte1 AS T2)
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

## 486 / card_games / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold computes the percentage of cards costing 7 as the count of matching cards divided by COUNT(id). The prediction instead divides that count by the sum of all converted mana costs, producing a different denominator.

Question:

```text
What is the percentage of the cards with a converted mana cost of 7 in the set Coldsnap?
```

Evidence:

```text
converted mana cost of 7 refers to convertedManaCost = 7; card set Coldsnap refers to name = 'Coldsnap'; percentage = DIVIDE(SUM(convertedManaCost = 7), SUM(convertedManaCost))*100
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.convertedManaCost = 7 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN sets AS T2 ON T2.code = T1.setCode WHERE T2.name = 'Coldsnap'
```

Predicted SQL:

```sql
SELECT CAST(SUM(T1.convertedManaCost = 7) AS REAL) * 100 / SUM(T1.convertedManaCost) FROM cards AS T1 INNER JOIN sets AS T2 ON T1.setCode = T2.code WHERE T2.name = 'Coldsnap'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.convertedManaCost… |
|---|
| 7.741935483870968 |

Predicted (first 1 of 1 rows):

| CAST(SUM(T1.convertedManaCost = 7) AS R… |
|---|
| 2.42914979757085 |

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
SELECT CAST(COUNT(CASE WHEN T2.Age > 65 THEN T1.Id END) AS REAL) * 100 / COUNT(T1.Id) FROM posts AS T1 LEFT JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Score > 5
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(T2.Age > 65, 1, 0)) AS REA… |
|---|
| 0.16899404073645824 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T2.Age > 65 THEN T… |
|---|
| 0.16572176188399476 |

## 565 / codebase_community / moderate

Label: `other` (classifier, gpt-6-luna): The join and filters match, and the CASE uses the same ClosedDate logic as the gold query. The output values differ only because the prediction returns “Yes”/“No” instead of “well-finished”/“NOT well-finished.”

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
SELECT CASE WHEN T2.ClosedDate IS NULL THEN 'No' ELSE 'Yes' END FROM comments AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id WHERE T1.UserId = 23853 AND T1.CreationDate = '2013-07-12 09:08:18.0'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| resylt |
|---|
| well-finished |

Predicted (first 1 of 1 rows):

| CASE WHEN T2.ClosedDate IS NULL THEN 'N… |
|---|
| Yes |

## 584 / codebase_community / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query retrieves `postHistory.Comment` for the titled post, while the prediction retrieves `comments.Text`. It also joins through `LastEditorUserId`, which does not identify comments left by users who edited that post.

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
SELECT T1.Text FROM comments AS T1 INNER JOIN posts AS T2 ON T1.UserId = T2.LastEditorUserId WHERE T2.Title = 'Why square the difference instead of taking the absolute value in standard deviation?'
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

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query filters on `posts.ViewCount`, while the prediction uses `users.Views`. It also omits the `posts` join and changes the grouping, but the first issue is reading the wrong column/table for views.

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
SELECT DISTINCT T1.UserId FROM postHistory AS T1 INNER JOIN users AS T2 ON T1.UserId = T2.Id WHERE T2.Views >= 1000 GROUP BY T1.PostId HAVING COUNT(T1.Id) = 1
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

| UserId |
|---|
| 88 |
| 253 |
| 449 |
| 919 |
| 7972 |

## 604 / codebase_community / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The predicted age calculation divides SUM(Age) by COUNT(Id), which counts users with NULL ages; the gold AVG(Age) excludes those users. The up-vote average and qualifying-user filter otherwise match.

Question:

```text
What is the average of the up votes and the average user age for users creating more than 10 posts?
```

Evidence:

```text
creating more than 10 post refers to Count (UserId) > 10; average of the up votes = Divide (Sum(UpVotes), Count (UserId)); average age = Divide (Sum(Age), Count(UserId))
```

Gold SQL:

```sql
SELECT AVG(T1.UpVotes), AVG(T1.Age) FROM users AS T1 INNER JOIN ( SELECT OwnerUserId, COUNT(*) AS post_count FROM posts GROUP BY OwnerUserId HAVING post_count > 10) AS T2 ON T1.Id = T2.OwnerUserId
```

Predicted SQL:

```sql
SELECT CAST(SUM(T1.UpVotes) AS REAL) / COUNT(T1.Id), CAST(SUM(T1.Age) AS REAL) / COUNT(T1.Id) FROM users AS T1 INNER JOIN (SELECT T2.OwnerUserId FROM posts AS T2 GROUP BY T2.OwnerUserId HAVING COUNT(T2.OwnerUserId) > 10) AS T3 ON T1.Id = T3.OwnerUserId
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(T1.UpVotes) | AVG(T1.Age) |
|---|---|
| 182.2832618025751 | 34.083333333333336 |

Predicted (first 1 of 1 rows):

| CAST(SUM(T1.UpVotes) AS REAL) / COUNT(T… | CAST(SUM(T1.Age) AS REAL) / COUNT(T1.Id) |
|---|---|
| 182.2832618025751 | 9.127896995708154 |

## 640 / codebase_community / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction compares DisplayName to lowercase `'mornington'`, while the gold query uses `'Mornington'`; SQLite string comparison is case-sensitive, so that condition matches no rows.

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
SELECT SUM(CASE WHEN T2.DisplayName = 'mornington' THEN T1.ViewCount END) - SUM(CASE WHEN T2.DisplayName = 'Amos' THEN T1.ViewCount END) FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T2.DisplayName IN ('mornington', 'Amos')
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
| None |

## 672 / codebase_community / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

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
SELECT COUNT(DISTINCT T1.Id) FROM users AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId WHERE T1.Location = 'United Kingdom' AND T2.FavoriteCount >= 4
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T1.Id) |
|---|
| 19 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.Id) |
|---|
| 14 |

## 685 / codebase_community / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction selects the user on the latest matching post-history record, which fits “posted it last time.” The gold query instead joins through `posts.LastEditorUserId` and does not identify the latest post-history user.

Question:

```text
Identify the total views on the post 'Computer Game Datasets'. Name the user who posted it last time.
```

Evidence:

```text
total views refer to ViewCount; Name the user refers to DisplayName; post 'Computer Game Datasets' refers to Text = 'Computer Game Datasets';
```

Gold SQL:

```sql
SELECT T2.ViewCount, T3.DisplayName FROM postHistory AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id INNER JOIN users AS T3 ON T2.LastEditorUserId = T3.Id WHERE T1.Text = 'Computer Game Datasets'
```

Predicted SQL:

```sql
SELECT T2.ViewCount, T3.DisplayName FROM postHistory AS T1 INNER JOIN posts AS T2 ON T1.PostId = T2.Id INNER JOIN users AS T3 ON T1.UserId = T3.Id WHERE T1.Text = 'Computer Game Datasets' ORDER BY T1.CreationDate DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| ViewCount | DisplayName |
|---|---|
| 1708 | mbq |

Predicted (first 1 of 1 rows):

| ViewCount | DisplayName |
|---|---|
| 1708 | Menno |

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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query includes posts from every user tied at the maximum reputation, while the prediction ranks users and limits to a single user. The ranking logic can exclude posts by other tied top users.

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
SELECT CAST(COUNT(CASE WHEN T1.Score > 50 THEN T1.Id END) AS REAL) * 100 / COUNT(T1.Id) FROM posts AS T1 INNER JOIN (SELECT T2.Id FROM users AS T2 ORDER BY T2.Reputation DESC LIMIT 1) AS T3 ON T1.OwnerUserId = T3.Id
```

Result diff:

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T1.Score > 50 THEN… |
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

## 896 / formula_1 / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction uses race results to calculate Hamilton’s non-first-place finishes, matching the evidence’s raceId-based percentage. The gold instead uses driverStandings positions and driverStandingsId counts, which measure standings rather than race finishes.

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
SELECT CAST(COUNT(CASE WHEN T1.position > 1 THEN T1.raceId END) AS REAL) * 100 / COUNT(T1.raceId) FROM results AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T1.raceId = T3.raceId WHERE T2.surname = 'Hamilton' AND T3.year >= 2010
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T2.position <> 1 T… |
|---|
| 73.2394366197183 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T1.position > 1 TH… |
|---|
| 54.225352112676056 |

## 902 / formula_1 / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query checks Alex Yoong’s position in `driverStandings`, while the prediction checks `results.position`. These are different tables and yield different race sets.

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
SELECT T1.name FROM races AS T1 INNER JOIN results AS T2 ON T1.raceId = T2.raceId INNER JOIN drivers AS T3 ON T2.driverId = T3.driverId WHERE T3.forename = 'Alex' AND T3.surname = 'Yoong' AND T2.position < 20
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

## 906 / formula_1 / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction uses `results.points`, the points scored in the race event, while the gold query uses `driverStandings.points`, which records standings points and yields 14 rather than 8. For the question’s points recorded for the race, the gold query appears to use the wrong measure.

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
SELECT T2.name, T1.points FROM results AS T1 INNER JOIN races AS T2 ON T1.raceId = T2.raceId INNER JOIN drivers AS T3 ON T1.driverId = T3.driverId WHERE T3.forename = 'Lewis' AND T3.surname = 'Hamilton' AND T2.year IS NOT NULL ORDER BY T2.year ASC, T2.round ASC LIMIT 1
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
SELECT COUNT(*) FROM (SELECT T1.constructorId FROM constructors AS T1 INNER JOIN constructorResults AS T2 ON T1.constructorId = T2.constructorId WHERE T1.nationality = 'Japanese' AND T2.points = 0 GROUP BY T1.constructorId HAVING COUNT(T2.raceId) = 2) AS T3
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

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The gold query returns only the champion’s time, while the prediction also returns the driver’s forename and surname. The race and winner selection produce the same time row, but the extra output columns make the results differ.

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
SELECT T3.forename, T3.surname, T2.time FROM races AS T1 INNER JOIN results AS T2 ON T1.raceId = T2.raceId INNER JOIN drivers AS T3 ON T2.driverId = T3.driverId WHERE T1.name = 'Canadian Grand Prix' AND T1.year = 2008 AND T2.position = 1
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

Label: `date_handling` (classifier, gpt-6-luna): The gold query parses lap-time strings into seconds before finding and ranking each driver’s minimum, while the prediction applies MIN directly to the text values, producing a different ordering. The prediction also omits `driverId`, but the time-comparison difference comes first.

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
SELECT T1.forename, T1.surname FROM drivers AS T1 INNER JOIN lapTimes AS T2 ON T1.driverId = T2.driverId WHERE T2.time IS NOT NULL GROUP BY T1.driverId, T1.forename, T1.surname ORDER BY MIN(T2.time) ASC LIMIT 20
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
| Anthony | Davidson |
| Enrique | Bernoldi |
| Christian | Klien |
| Olivier | Panis |
| Yuji | Ide |

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
SELECT MAX(T1.buildUpPlaySpeed) AS c1 FROM Team_Attributes AS T1 GROUP BY T1.team_api_id ORDER BY c1 DESC LIMIT 4
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

| c1 |
|---|
| 80 |
| 78 |
| 78 |
| 77 |

## 1058 / european_football_2 / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query compares the average finishing rate for the tallest-player group against the shortest-player group. The prediction instead groups by individual player and ranks those players by their own average finishing rate.

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
SELECT T1.player_name FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.height = (SELECT MAX(T3.height) FROM Player AS T3) OR T1.height = (SELECT MIN(T4.height) FROM Player AS T4 WHERE T4.height IS NOT NULL) GROUP BY T1.id, T1.player_name ORDER BY AVG(T2.finishing) DESC LIMIT 1
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query aggregates each player's overall ratings with `SUM` and returns one percentage, while the prediction compares individual attribute rows and returns many results. Thus the prediction omits the gold query's aggregation logic.

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
SELECT CAST(T2.overall_rating - T4.overall_rating AS REAL) * 100 / T4.overall_rating FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id INNER JOIN Player AS T3 ON T3.player_name = 'Paulin Puel' INNER JOIN Player_Attributes AS T4 ON T3.player_api_id = T4.player_api_id WHERE T1.player_name = 'Ariel Borysiuk'
```

Result diff:

Gold 1 rows, predicted 288 rows. Within the previews: 1 rows only in gold, 2 only in predicted.

Gold (first 1 of 1 rows):

| (SUM(CASE WHEN t1.player_name = 'Ariel … |
|---|
| 133.7260677466863 |

Predicted (first 5 of 288 rows):

| CAST(T2.overall_rating - T4.overall_rat… |
|---|
| 23.636363636363637 |
| 23.636363636363637 |
| 23.636363636363637 |
| 21.428571428571427 |
| 21.428571428571427 |

## 1135 / european_football_2 / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction groups by player and ranks each player's minimum potential, matching the evidence that “lowest potential” means MIN(potential). The gold query instead ranks individual attribute rows and selects `id`, rather than returning player IDs ranked by their minimum potential.

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
SELECT T1.player_api_id FROM Player_Attributes AS T1 WHERE T1.preferred_foot = 'right' AND T1.potential IS NOT NULL GROUP BY T1.player_api_id ORDER BY MIN(T1.potential) ASC LIMIT 4
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

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
| 166963 |
| 8893 |
| 168342 |

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
SELECT COUNT(DISTINCT T1.player_api_id) FROM Player_Attributes AS T1 WHERE T1.crossing = (SELECT MAX(T2.crossing) FROM Player_Attributes AS T2) AND T1.preferred_foot = 'left'
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

## 1149 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

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
SELECT CASE WHEN COUNT(CASE WHEN T1.Admission = '+' THEN T1.ID END) > COUNT(CASE WHEN T1.Admission = '-' THEN T1.ID END) THEN 'in-patient' ELSE 'outpatient' END, CAST(COUNT(CASE WHEN T1.Admission = '+' THEN T1.ID END) AS REAL) * 100 / COUNT(CASE WHEN T1.Admission = '-' THEN T1.ID END) FROM Patient AS T1 WHERE T1.SEX = 'M'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN Admission = '+' THEN… |
|---|
| 83.17757009345794 |

Predicted (first 1 of 1 rows):

| CASE WHEN COUNT(CASE WHEN T1.Admission … | CAST(COUNT(CASE WHEN T1.Admission = '+'… |
|---|---|
| outpatient | 83.17757009345794 |

## 1166 / thrombosis_prediction / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The queries use the same tables, join keys, non-NULL symptom filter, and descending birthday ranking, but return different diagnosis values for the selected row. The difference appears to come from the data or gold labeling rather than a distinct SQL logic error, so the gold result is suspect.

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
SELECT T1.Symptoms, T1.Diagnosis FROM Examination AS T1 INNER JOIN Patient AS T2 ON T1.ID = T2.ID WHERE T1.Symptoms IS NOT NULL ORDER BY T2.Birthday DESC LIMIT 1
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
| CNS susp | SLE+Psy |

## 1205 / thrombosis_prediction / moderate

Label: `other` (classifier, gpt-6-luna): The predicates use the same sex-specific UA thresholds and the same patient filter, but the prediction returns the strings 'Yes'/'No' instead of the gold query’s boolean true/false values. This changes result values, not the selected columns or query logic.

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
SELECT CASE WHEN (T1.UA > 8.0 AND T2.SEX = 'M') OR (T1.UA > 6.5 AND T2.SEX = 'F') THEN 'Yes' ELSE 'No' END FROM Laboratory AS T1 INNER JOIN Patient AS T2 ON T1.ID = T2.ID WHERE T2.ID = 57266
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

| CASE WHEN (T1.UA > 8.0 AND T2.SEX = 'M'… |
|---|
| No |
| No |
| No |
| No |
| No |

## 1225 / thrombosis_prediction / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The query returns the same patient IDs and sexes for the bilirubin filter, but selects them in the order SEX, ID instead of the gold query’s ID, SEX. Column order matters for result equality.

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
SELECT DISTINCT T1.SEX, T1.ID FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-BIL` >= 2.0 ORDER BY T1.SEX
```

Result diff:

Gold 10 rows, predicted 10 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 10 rows):

| ID | SEX |
|---|---|
| 43003 | M |
| 250391 | F |
| 444499 | M |
| 1137040 | M |
| 1180510 | F |

Predicted (first 5 of 10 rows):

| SEX | ID |
|---|---|
| F | 250391 |
| F | 1180510 |
| F | 2308236 |
| F | 2931207 |
| F | 4862013 |

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
SELECT AVG(CAST(STRFTIME('%Y', CURRENT_DATE) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER)) FROM Patient AS T1 INNER JOIN (SELECT DISTINCT T3.ID FROM Laboratory AS T3 WHERE T3.`T-CHO` >= 250) AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M'
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

## 1239 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The prediction uses `HAVING COUNT(T2.ID) > 2`, while the gold query uses `HAVING COUNT(ID) >= 2`. The question asks for two or more examinations, so the strict threshold excludes patients with exactly two.

Question:

```text
Name the ID and age of patient with two or more laboratory examinations which show their hematoclit level exceeded the normal range.
```

Evidence:

```text
age = SUBTRACT(year(current_timestamp), year(Birthday)); patient with two or more laboratory examinations refers to COUNT(ID) > 2; hematoclit level exceeded the normal range refers to HCT > = 52;
```

Gold SQL:

```sql
SELECT DISTINCT T1.ID, STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T1.Birthday) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.ID IN ( SELECT ID FROM Laboratory WHERE HCT >= 52 GROUP BY ID HAVING COUNT(ID) >= 2 )
```

Predicted SQL:

```sql
SELECT T1.ID, CAST(STRFTIME('%Y', CURRENT_TIMESTAMP) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.HCT >= 52 GROUP BY T1.ID, T1.Birthday HAVING COUNT(T2.ID) > 2
```

Result diff:

Gold 3 rows, predicted 2 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 3 of 3 rows):

| ID | STRFTIME('%Y', CURRENT_TIMESTAMP) - STR… |
|---|---|
| 2307640 | 73 |
| 3182521 | 74 |
| 4007151 | 58 |

Predicted (first 2 of 2 rows):

| ID | CAST(STRFTIME('%Y', CURRENT_TIMESTAMP) … |
|---|---|
| 2307640 | 73 |
| 4007151 | 58 |

## 1241 / thrombosis_prediction / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction’s second expression follows the evidence’s specified subtraction of counts where PLT < 100 and PLT > 400, while the gold uses inclusive thresholds (<= 100 and >= 400). The prediction also provides the lower-than-normal count requested, which the gold omits.

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
SELECT SUM(T1.PLT < 100), SUM(T1.PLT < 100) - SUM(T1.PLT > 400) FROM Laboratory AS T1 WHERE T1.PLT <= 100 OR T1.PLT >= 400
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(CASE WHEN T2.PLT <= 100 THEN 1 ELSE… |
|---|
| -562 |

Predicted (first 1 of 1 rows):

| SUM(T1.PLT < 100) | SUM(T1.PLT < 100) - SUM(T1.PLT > 400) |
|---|---|
| 320 | -555 |

## 1242 / thrombosis_prediction / challenging

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

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
SELECT DISTINCT T1.ID FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.PLT BETWEEN 100 AND 400 AND STRFTIME('%Y', T2.Date) - STRFTIME('%Y', T1.Birthday) < 50 AND STRFTIME('%Y', T2.Date) = '1984'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.ID FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE STRFTIME('%Y', T2.Date) = '1984' AND CAST(STRFTIME('%Y', CURRENT_TIMESTAMP) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER) < 50 AND T2.PLT BETWEEN 100 AND 400
```

Result diff:

Gold 76 rows, predicted 5 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 76 rows):

| ID |
|---|
| 30609 |
| 48473 |
| 52199 |
| 58139 |
| 81043 |

Predicted (first 5 of 5 rows):

| ID |
|---|
| 102490 |
| 460574 |
| 1086485 |
| 2047892 |
| 3173679 |

## 1243 / thrombosis_prediction / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The gold denominator uses `COUNT(CASE WHEN PT >= 14 THEN 1 ELSE 0 END)`, which counts every row because both 1 and 0 are non-NULL. The prediction correctly sums the abnormal-PT condition for the denominator, matching the question’s requested percentage among patients with abnormal PT.

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
SELECT CAST(SUM(T2.PT >= 14 AND T1.SEX = 'F') AS REAL) * 100 / SUM(T2.PT >= 14) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE CAST(STRFTIME('%Y', CURRENT_TIMESTAMP) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER) > 55
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.PT >= 14 AND T1.S… |
|---|
| 1.2030885257676422 |

Predicted (first 1 of 1 rows):

| CAST(SUM(T2.PT >= 14 AND T1.SEX = 'F') … |
|---|
| 78.3625730994152 |

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
SELECT COUNT(DISTINCT T1.ID) FROM Laboratory AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.IGG > 900 AND T1.IGG < 2000 AND T2.Symptoms IS NOT NULL
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
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGA > 80 AND T2.IGA < 500 AND STRFTIME('%Y', T1.`First Date`) >= '1990'
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

## 1256 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

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
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.CRP = '+' AND T1.Description IS NULL
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
| 25 |

## 1267 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

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
SELECT COUNT(DISTINCT T1.ID) FROM Laboratory AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.SM IN ('negative', '0') AND T2.Thrombosis = 0
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
| 6 |

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
SELECT COUNT(*) FROM (SELECT T1.event_id FROM event AS T1 INNER JOIN attendance AS T2 ON T1.event_id = T2.link_to_event WHERE T1.type = 'Meeting' GROUP BY T1.event_id HAVING COUNT(T1.event_id) > 10) AS T3
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

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction checks whether Maya attended the specified event and returns a single yes/no answer. The gold SQL instead returns one row per attendance record and only marks rows for that event, so it does not correctly answer the question as asked.

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
SELECT CASE WHEN COUNT(*) > 0 THEN 'Yes' ELSE 'No' END FROM member AS T1 INNER JOIN attendance AS T2 ON T1.member_id = T2.link_to_member INNER JOIN event AS T3 ON T2.link_to_event = T3.event_id WHERE T1.first_name = 'Maya' AND T1.last_name = 'Mclean' AND T3.event_name = 'Women''s Soccer'
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

## 1405 / student_club / moderate

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The joins, filtering, grouping, and ascending amount order match. The prediction selects the amount before the category, while the gold query selects category before amount, so the output columns are ordered differently.

Question:

```text
Calculate the amount budgeted for 'April Speaker' event. List all the budgeted categories for said event in an ascending order based on their amount budgeted.
```

Evidence:

```text
'April Speaker' is an event name; amount budgeted refers to SUM(amount); budget categories refers to category
```

Gold SQL:

```sql
SELECT T2.category, SUM(T2.amount) FROM event AS T1 JOIN budget AS T2 ON T1.event_id = T2.link_to_event WHERE T1.event_name = 'April Speaker' GROUP BY T2.category ORDER BY SUM(T2.amount) ASC
```

Predicted SQL:

```sql
SELECT SUM(T2.amount) AS c1, T2.category FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event WHERE T1.event_name = 'April Speaker' GROUP BY T2.category ORDER BY c1 ASC
```

Result diff:

Gold 4 rows, predicted 4 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 4 of 4 rows):

| category | SUM(T2.amount) |
|---|---|
| Parking | 10 |
| Speaker Gifts | 25 |
| Advertisement | 75 |
| Food | 150 |

Predicted (first 4 of 4 rows):

| c1 | category |
|---|---|
| 10 | Parking |
| 25 | Speaker Gifts |
| 75 | Advertisement |
| 150 | Food |

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
SELECT T1.category FROM budget AS T1 INNER JOIN event AS T2 ON T1.link_to_event = T2.event_id WHERE T2.location = 'MU 215' AND T2.type = 'Guest Speaker' AND T1.spent = 0
```

Result diff:

Gold 4 rows, predicted 16 rows. Within the previews: 4 rows only in gold, 4 only in predicted.

Gold (first 4 of 4 rows):

| category | type |
|---|---|
| Speaker Gifts | Guest Speaker |
| Food | Guest Speaker |
| Parking | Guest Speaker |
| Advertisement | Guest Speaker |

Predicted (first 5 of 16 rows):

| category |
|---|
| Speaker Gifts |
| Food |
| Parking |
| Advertisement |
| Speaker Gifts |

## 1482 / debit_card_specializing / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks for the biggest and lowest segment, and the prediction returns those two segments; the gold query instead returns percentages for all three segments. The gold also divides the increase by 2012 consumption, contrary to the supplied evidence specifying 2013 consumption.

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
WITH cte1 AS (SELECT T1.Segment, SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2012' THEN T2.Consumption ELSE 0 END) AS c1, SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2013' THEN T2.Consumption ELSE 0 END) AS c2 FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Currency = 'EUR' AND T1.Segment IN ('SME', 'LAM', 'KAM') AND SUBSTR(T2.Date, 1, 4) IN ('2012', '2013') GROUP BY T1.Segment), cte2 AS (SELECT T1.Segment, CAST(T1.c2 - T1.c1 AS REAL) * 100 / NULLIF(T1.c2, 0) AS c3 FROM cte1 AS T1) SELECT T1.Segment, T1.c3 FROM (SELECT T2.Segment, T2.c3 FROM cte2 AS T2 WHERE T2.c3 IS NOT NULL ORDER BY T2.c3 DESC LIMIT 1) AS T1 UNION ALL SELECT T3.Segment, T3.c3 FROM (SELECT T4.Segment, T4.c3 FROM cte2 AS T4 WHERE T4.c3 IS NOT NULL ORDER BY T4.c3 ASC LIMIT 1) AS T3
```

Result diff:

Gold 1 rows, predicted 2 rows. Within the previews: 1 rows only in gold, 2 only in predicted.

Gold (first 1 of 1 rows):

| CAST((SUM(IIF(T1.Segment = 'SME' AND T2… | CAST(SUM(IIF(T1.Segment = 'LAM' AND T2.… | CAST(SUM(IIF(T1.Segment = 'KAM' AND T2.… |
|---|---|---|
| 545.4018999790969 | 681.5824574939339 | 708.1124062978664 |

Predicted (first 2 of 2 rows):

| Segment | c3 |
|---|---|
| SME | 88.01984961472203 |
| LAM | 84.37082878168067 |

## 1490 / debit_card_specializing / moderate

Label: `gold_label_suspect` (rule): the prediction returns the rows of the Arcwise-Plat-SQL corrected gold

Gold label suspect: yes.

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
SELECT CAST(SUM(IIF(T2.Consumption > 46.73, 1, 0)) AS FLOAT) * 100 / COUNT(T1.CustomerID) FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Segment = 'LAM'
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT T2.CustomerID) AS REAL) * 100 / COUNT(DISTINCT T1.CustomerID) FROM customers AS T1 LEFT JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID AND T2.Consumption > 46.73 WHERE T1.Segment = 'LAM'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(T2.Consumption > 46.73, 1,… |
|---|
| 98.5267932135058 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT T2.CustomerID) AS R… |
|---|
| 98.25041006014216 |

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

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question identifies the customer by a payment of 634.8 on 2012-08-25, and the prediction filters on `Amount * Price = 634.8`. The gold query instead selects a customer using `T1.Price = 1513.12`, which does not match the stated payment criterion.

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
WITH cte1 AS (SELECT DISTINCT T1.CustomerID FROM transactions_1k AS T1 WHERE T1.Date = '2012-08-25' AND T1.Amount * T1.Price = 634.8), cte2 AS (SELECT SUM(CASE WHEN SUBSTR(T1.Date, 1, 4) = '2012' THEN T1.Consumption ELSE 0 END) AS c1, SUM(CASE WHEN SUBSTR(T1.Date, 1, 4) = '2013' THEN T1.Consumption ELSE 0 END) AS c2 FROM yearmonth AS T1 INNER JOIN cte1 AS T2 ON T1.CustomerID = T2.CustomerID GROUP BY T1.CustomerID) SELECT CAST(T1.c1 - T1.c2 AS REAL) / T1.c1 FROM cte2 AS T1
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(SUBSTRING(Date, 1, 4) = '2… |
|---|
| None |

Predicted (first 0 of 0 rows):

| CAST(T1.c1 - T1.c2 AS REAL) / T1.c1 |
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

Label: `gold_label_suspect` (classifier, gpt-6-luna): The evidence defines average price as total price divided by total amount, which the prediction computes, while the gold query sums per-transaction price/amount ratios. The prediction also ranks customers by amount × price to identify the top spender, rather than selecting the customer with the highest Consumption in yearmonth.

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
SELECT T1.CustomerID, CAST(SUM(T2.Price) AS REAL) / SUM(T2.Amount), T1.Currency FROM customers AS T1 INNER JOIN transactions_1k AS T2 ON T1.CustomerID = T2.CustomerID GROUP BY T1.CustomerID, T1.Currency ORDER BY SUM(T2.Amount * T2.Price) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CustomerID | SUM(T2.Price / T2.Amount) | Currency |
|---|---|---|
| 12459 | 203.8560787354258 | CZK |

Predicted (first 1 of 1 rows):

| CustomerID | CAST(SUM(T2.Price) AS REAL) / SUM(T2.Am… | Currency |
|---|---|---|
| 13665 | 21.827613636363637 | CZK |
