# Failures: best on bird_arcwise / dev

56 of 349 questions failed. Evidence on, git `9e6058ba110908fba8be69f59edf24a618ad2e41-dirty`, complete: 349 questions.

## 11 / california_schools / simple

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query joins `frpm` to `schools` on `CDSCode`, while the prediction reads only `frpm`. Omitting that join changes which rows qualify; the gold also filters out rows where `School` is NULL.

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
SELECT T1.CDSCode FROM frpm AS T1 WHERE T1.`Enrollment (K-12)` + T1.`Enrollment (Ages 5-17)` > 500
```

Result diff:

Gold 7804 rows, predicted 7806 rows. Within the previews: 0 rows only in gold, 0 only in predicted.

Gold (first 5 of 7804 rows):

| CDSCode |
|---|
| 01100170109835 |
| 01100170112607 |
| 01100170124172 |
| 01100170125567 |
| 01100176001788 |

Predicted (first 5 of 7806 rows):

| CDSCode |
|---|
| 01100170109835 |
| 01100170112607 |
| 01100170124172 |
| 01100170125567 |
| 01100176001788 |

## 23 / california_schools / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query excludes rows where `School` is NULL (`T1.School IS NOT NULL`), but the prediction omits that condition, producing additional rows.

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
SELECT T1.School, T1.Street FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.`Enrollment (K-12)` - T2.`Enrollment (Ages 5-17)` > 30
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

Label: `no_sql_produced` (rule): direct_full: no valid grammar tool call

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
(no SQL)
```

Errors:

- direct_full: no valid grammar tool call

Result diff:

Gold (first 5 of 6 rows):

| sname | FundingType |
|---|---|
| Arlington High | None |
| John W. North High | None |
| Martin Luther King Jr. High | None |
| Polytechnic High | None |
| Ramona High | None |

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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters to `t.rtype = 'S'`, but the prediction omits that condition. This changes which SAT-score rows can determine the school ranked first.

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
SELECT T2.AdmFName1, T2.AdmLName1, T2.AdmFName2, T2.AdmLName2, T2.AdmFName3, T2.AdmLName3 FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode ORDER BY T1.NumGE1500 DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AdmFName1 | AdmLName1 | AdmFName2 | AdmLName2 | AdmFName3 | AdmLName3 |
|---|---|---|---|---|---|
| Andrew | Ishibashi | None | None | None | None |

Predicted (first 1 of 1 rows):

| AdmFName1 | AdmLName1 | AdmFName2 | AdmLName2 | AdmFName3 | AdmLName3 |
|---|---|---|---|---|---|
| Michelle | King | None | None | None | None |

## 41 / california_schools / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold ranks all schools within each county and then filters to virtual schools; the prediction filters to virtual schools before selecting the top five, changing the ranking population. It also uses LIMIT 5 rather than rank logic that preserves ties.

Question:

```text
List the names of virtual schools that are among the top 5 in their respective counties based on average reading scores.
```

Evidence:

```text
Exclusively virtual refers to Virtual = 'F'; respective counties means PARTITION BY County; name refers to schools.School
```

Gold SQL:

```sql
WITH ranked AS (
  SELECT s.`School`,
         s.`Virtual`,
         sc.`cname`,
         RANK() OVER (PARTITION BY sc.`cname` ORDER BY sc.`AvgScrRead` DESC) AS rnk
  FROM `schools` s
  JOIN `satscores` sc ON s.`CDSCode` = sc.`cds`
  WHERE sc.`AvgScrRead` IS NOT NULL AND rtype = 'S'
)
SELECT DISTINCT `School`
FROM ranked
WHERE `Virtual` = 'F'
  AND rnk <= 5;
```

Predicted SQL:

```sql
SELECT T1.School FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.`Virtual` = 'F' AND T2.AvgScrRead IS NOT NULL AND T1.CDSCode IN (SELECT T3.CDSCode FROM schools AS T3 INNER JOIN satscores AS T4 ON T3.CDSCode = T4.cds WHERE T3.County = T1.County AND T3.`Virtual` = 'F' AND T4.AvgScrRead IS NOT NULL ORDER BY T4.AvgScrRead DESC LIMIT 5)
```

Result diff:

Gold 1 rows, predicted 4 rows. Within the previews: 0 rows only in gold, 3 only in predicted.

Gold (first 1 of 1 rows):

| School |
|---|
| California Connections Academy @ Ripon |

Predicted (first 4 of 4 rows):

| School |
|---|
| California Virtual Academy @ Los Angeles |
| Insight @ Los Angeles |
| Capistrano Connections Academy |
| California Connections Academy @ Ripon |

## 48 / california_schools / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold numerator filters to Orange County, but the denominator counts all merged DOC 52 schools without a County condition. The prediction applies County = 'Orange' to both counts, changing the denominator.

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
SELECT CAST(SUM(CASE WHEN T1.DOC = '54' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN T1.DOC = '52' THEN 1 ELSE 0 END) FROM schools AS T1 WHERE T1.StatusType = 'Merged' AND T1.County = 'Orange' AND T1.DOC IN ('54', '52')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| ratio |
|---|
| 0.010958904109589041 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.DOC = '54' THEN 1… |
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

## 212 / toxicology / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every element tied for the minimum count, while the prediction orders by count and limits the result to one element, dropping the other tied elements.

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
SELECT T1.element FROM atom AS T1 INNER JOIN molecule AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.label = '-' GROUP BY T1.element ORDER BY COUNT(T1.element) ASC LIMIT 1
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

## 248 / toxicology / simple

Label: `no_sql_produced` (rule): direct_full: no valid grammar tool call

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
(no SQL)
```

Errors:

- direct_full: no valid grammar tool call

Result diff:

Gold (first 4 of 4 rows):

| atom_id |
|---|
| TR041_10 |
| TR041_7 |
| TR041_8 |
| TR041_9 |

## 253 / toxicology / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters on bond_type = '#', matching the evidence, while the prediction uses '#159', yielding no rows. The extra ordering and limit would also affect results, but the filter value is the first difference to fix.

Question:

```text
List the elements of all the triple bonds.
```

Evidence:

```text
triple bond refers to bond_type = '#';
```

Gold SQL:

```sql
SELECT DISTINCT T3.element FROM bond AS T1 INNER JOIN connected AS T2 ON T1.bond_id = T2.bond_id INNER JOIN atom AS T3 ON T2.atom_id = T3.atom_id WHERE T1.bond_type = '#'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.element FROM atom AS T1 INNER JOIN connected AS T2 ON T1.atom_id = T2.atom_id OR T1.atom_id = T2.atom_id2 INNER JOIN bond AS T3 ON T2.bond_id = T3.bond_id WHERE T3.bond_type = '#159' ORDER BY T1.element LIMIT 4 OFFSET 1
```

Result diff:

Gold 4 rows, predicted 0 rows. Within the previews: 4 rows only in gold, 0 only in predicted.

Gold (first 4 of 4 rows):

| element |
|---|
| n |
| c |
| y |
| p |

Predicted (first 0 of 0 rows):

| element |
|---|

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

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction joins atoms directly to every matching bond, duplicating atoms in molecules with multiple single bonds. The gold query uses `IN` over distinct molecule IDs, so each atom is counted only once.

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
SELECT CAST(SUM(CASE WHEN T1.element = 'cl' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.atom_id) FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.bond_type = '-'
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

## 347 / card_games / moderate

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query uses a LEFT JOIN from cards to rulings, preserving cards without a matching ruling (with NULL text). The prediction uses an INNER JOIN, which drops those cards and returns fewer rows.

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
SELECT T1.id, T2.text, T1.hasContentWarning FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE T1.artist = 'Stephen Daniele'
```

Result diff:

Gold 76 rows, predicted 23 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 5 of 76 rows):

| id | text | hasContentWarning |
|---|---|---|
| 29 | You can’t put an Aura card from your ha… | 0 |
| 211 | None | 0 |
| 274 | None | 0 |
| 275 | None | 0 |
| 3872 | This card now has Enchant Swamp, which … | 0 |

Predicted (first 5 of 23 rows):

| id | text | hasContentWarning |
|---|---|---|
| 29 | You can’t put an Aura card from your ha… | 0 |
| 3872 | This card now has Enchant Swamp, which … | 0 |
| 6651 | Cycling is an activated ability. Effect… | 0 |
| 6652 | Cycling is an activated ability. Effect… | 0 |
| 7950 | Cycling is an activated ability. Effect… | 0 |

## 349 / card_games / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every printing whose card UUID has the maximum ruling count. The prediction groups by individual card row and uses `ORDER BY COUNT(...) DESC LIMIT 1`, so it returns only one printing and drops the tied promotional printing.

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
SELECT T1.name, T1.artist, T1.isPromo FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid GROUP BY T1.id, T1.name, T1.artist, T1.isPromo ORDER BY COUNT(T2.uuid) DESC LIMIT 1
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
| Teferi's Protection | Chase Stone | 0 |

## 352 / card_games / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The prediction reads `language` from `foreign_data` as `T1.language`, but the required card IDs come from `cards` and the language is `foreign_data.language`. It also sums IDs instead of counting matching distinct cards, but the first issue is the incorrect table/column usage.

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
SELECT CAST(COUNT(DISTINCT CASE WHEN T2.language = 'Chinese Simplified' THEN T1.id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT T1.id) FROM cards AS T1 LEFT JOIN foreign_data AS T2 ON T1.uuid = T2.uuid
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.language = 'Chinese Simplified' THEN T1.id ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM foreign_data AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.langua… |
|---|
| 35.384182182957304 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.language = 'Chine… |
|---|
| 988424.7336224726 |

## 416 / card_games / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction compares power to the corrupted literal '*9641B9D8-7B04-44A8-B67D-6FF697016C53' instead of '*', so it excludes the intended cards without power.

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
SELECT CAST(COUNT(CASE WHEN T2.language = 'French' THEN 1 END) AS REAL) * 100 / COUNT(*) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*9641B9D8-7B04-44A8-B67D-6FF697016C53' LIMIT 1 OFFSET 900719
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.langua… |
|---|
| 47.95671915756932 |

Predicted (first 0 of 0 rows):

| CAST(COUNT(CASE WHEN T2.language = 'Fre… |
|---|

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

## 557 / codebase_community / moderate

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query uses a LEFT JOIN to retain posts without a matching owner, while the prediction uses an INNER JOIN and excludes them, changing the denominator and percentage.

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
SELECT CAST(SUM(IIF(T2.Age > 65, 1, 0)) AS REAL) * 100 / COUNT(T1.Id) FROM posts AS T1 LEFT JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Score > 5
```

Predicted SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T2.Age > 65 THEN T1.Id END) AS REAL) * 100 / COUNT(T1.Id) FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T1.Score > 5
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(T2.Age > 65, 1, 0)) AS REA… |
|---|
| 0.16572176188399476 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T2.Age > 65 THEN T… |
|---|
| 0.16899404073645824 |

## 578 / codebase_community / moderate

Label: `no_sql_produced` (rule): direct_full: no valid grammar tool call

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
(no SQL)
```

Errors:

- direct_full: no valid grammar tool call

Result diff:

Gold (first 1 of 1 rows):

| DisplayName | Reputation |
|---|---|
| Hendy | 146 |

## 604 / codebase_community / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The predicted age calculation divides SUM(Age) by COUNT(Id), which counts qualifying users even when Age is NULL; the gold AVG(Age) excludes NULL ages from its denominator. The up-vote averages match.

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
WITH cte1 AS (SELECT T1.OwnerUserId FROM posts AS T1 GROUP BY T1.OwnerUserId HAVING COUNT(T1.OwnerUserId) > 10) SELECT CAST(SUM(T1.UpVotes) AS REAL) / COUNT(T1.Id), CAST(SUM(T1.Age) AS REAL) / COUNT(T1.Id) FROM users AS T1 INNER JOIN cte1 AS T2 ON T1.Id = T2.OwnerUserId
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

## 701 / codebase_community / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The prediction orders users by reputation and takes only one row with `LIMIT 1`, while the gold query selects every user tied at the maximum reputation. This changes which posts contribute when the maximum is shared.

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
WITH cte1 AS (SELECT T1.Id FROM users AS T1 ORDER BY T1.Reputation DESC LIMIT 1) SELECT CAST(COUNT(CASE WHEN T2.Score > 50 THEN T2.Id END) AS REAL) * 100 / COUNT(T2.Id) FROM cte1 AS T1 INNER JOIN posts AS T2 ON T1.Id = T2.OwnerUserId
```

Result diff:

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T2.Score > 50 THEN… |
|---|
| 0.6644518272425249 |

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

## 750 / superhero / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters out nonpositive weights with `weight_kg > 0`, but the prediction omits that condition, changing the rows included in the average.

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
SELECT AVG(weight_kg) FROM superhero s JOIN gender g ON s.gender_id = g.id WHERE g.gender = 'Female' AND weight_kg > 0;
```

Predicted SQL:

```sql
SELECT AVG(T1.weight_kg) FROM superhero AS T1 INNER JOIN gender AS T2 ON T1.gender_id = T2.id WHERE T2.gender = 'Female'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(weight_kg) |
|---|
| 78.50694444444444 |

Predicted (first 1 of 1 rows):

| AVG(T1.weight_kg) |
|---|
| 60.77956989247312 |

## 760 / superhero / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The predicted query adds `LIMIT 1 OFFSET 00787`, which removes the single aggregate result row; the gold query has no limit or offset. It also adds an extra condition to the `WHERE` clause.

Question:

```text
In superheroes with height between 150 to 180, what is the percentage of heroes published by Marvel Comics?
```

Evidence:

```text
height between 150 to 180 refers to height_cm BETWEEN 150 AND 180; heroes published by Marvel Comics refers to publisher_name = 'Marvel Comics'; calculation = MULTIPLY(DIVIDE(SUM(publisher.id = 13)), COUNT(publisher.id), 100)
```

Gold SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(T1.id) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T1.height_cm BETWEEN 150 AND 180
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.publisher_name = 'Marvel Comics' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T2.id) FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T1.height_cm BETWEEN 150 AND 180 NOT IN (SELECT 1) = 0 LIMIT 1 OFFSET 00787
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T2.publisher_name … |
|---|
| 60.869565217391305 |

Predicted (first 0 of 0 rows):

| CAST(SUM(CASE WHEN T2.publisher_name = … |
|---|

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

## 773 / superhero / challenging

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query uses a LEFT JOIN to retain superheroes without a matching publisher, while the prediction uses an INNER JOIN and drops those rows.

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
SELECT T1.superhero_name, T2.publisher_name FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T1.hair_colour_id = T1.skin_colour_id AND T1.hair_colour_id = T1.eye_colour_id
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

## 788 / superhero / challenging

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query uses a LEFT JOIN to publisher, while the prediction uses an INNER JOIN, which can exclude female heroes without a publisher from the denominator. This changes the result rows.

Question:

```text
How many percent of female heroes were published by Marvel Comics?
```

Evidence:

```text
percent = MULTIPLY(DIVIDE(COUNT(gender = 'Female' AND publisher_name = 'Marvel Comics'), COUNT(gender = 'Female')), 100); female heroes refers to gender = 'Female'; Marvel Comics refers to publisher_name = 'Marvel Comics';
```

Gold SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T3.gender = 'Female' AND T2.publisher_name = 'Marvel Comics' THEN 1 ELSE NULL END) AS REAL) / COUNT(CASE WHEN T3.gender = 'Female' THEN 1 ELSE NULL END) * 100 FROM superhero AS T1 LEFT JOIN publisher AS T2 ON T1.publisher_id = T2.id INNER JOIN gender AS T3 ON T1.gender_id = T3.id
```

Predicted SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T3.publisher_name = 'Marvel Comics' THEN 1 END) AS REAL) * 100 / COUNT(*) FROM superhero AS T1 INNER JOIN gender AS T2 ON T1.gender_id = T2.id INNER JOIN publisher AS T3 ON T1.publisher_id = T3.id WHERE T2.gender = 'Female'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T3.gender = 'Femal… |
|---|
| 54.679802955665025 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T3.publisher_name … |
|---|
| 54.95049504950495 |

## 829 / superhero / challenging

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The predicted query returns only the difference, while the gold query also returns the publisher with more superheroes. The difference value itself matches, but the output columns do not.

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
SELECT SUM(T2.publisher_name = 'DC Comics') - SUM(T2.publisher_name = 'Marvel Comics') FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T2.publisher_name IN ('DC Comics', 'Marvel Comics')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| publisher_with_more_superheroes | difference |
|---|---|
| Marvel Comics | -163 |

Predicted (first 1 of 1 rows):

| SUM(T2.publisher_name = 'DC Comics') - … |
|---|
| -163 |

## 861 / formula_1 / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The predicted query adds a trailing modifier-letter apostrophe (`ʼ`) to the LIKE pattern, so it does not match the Q3 times matched by the gold pattern `1:54%`.

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
SELECT T1.number FROM drivers AS T1 INNER JOIN qualifying AS T2 ON T1.driverId = T2.driverId WHERE T2.raceId = 903 AND T2.q3 LIKE '1:54%ʼ'
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

## 880 / formula_1 / challenging

Label: `other` (classifier, gpt-6-luna): The joins and race filters match, but the percentage calculation uses the race 853 speed as the denominator. The gold query divides by the race 854 speed, producing a different percentage.

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
SELECT ((MAX(CASE WHEN r.`raceId` = 853 THEN CAST(r.`fastestLapSpeed` AS REAL) END) -
         MAX(CASE WHEN r.`raceId` = 854 THEN CAST(r.`fastestLapSpeed` AS REAL) END)) * 100.0) /
       MAX(CASE WHEN r.`raceId` = 854 THEN CAST(r.`fastestLapSpeed` AS REAL) END) AS percent_faster
FROM `drivers` d
JOIN `results`  r ON d.`driverId` = r.`driverId`
WHERE d.`forename` = 'Paul'
  AND d.`surname`  = 'di Resta';
  
```

Predicted SQL:

```sql
SELECT CAST(T2.fastestLapSpeed - T3.fastestLapSpeed AS REAL) * 100 / T2.fastestLapSpeed FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN results AS T3 ON T1.driverId = T3.driverId WHERE T1.forename = 'Paul' AND T1.surname = 'di Resta' AND T2.raceId = 853 AND T3.raceId = 854
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| percent_faster |
|---|
| 48.15155382074764 |

Predicted (first 1 of 1 rows):

| CAST(T2.fastestLapSpeed - T3.fastestLap… |
|---|
| 32.50155167390781 |

## 892 / formula_1 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query totals points from `results`, while the prediction reads `points` from `driverStandings`. This different source produces a different driver and point count.

Question:

```text
State the driver with the most points scored. Find his full name and the number of points.
```

Evidence:

```text
the most points scored refers to max(points); Full name of the driver refers to drivers.forename and drivers.surname;
```

Gold SQL:

```sql
SELECT d.`forename`, d.`surname`, SUM(r.`points`) AS total_points
FROM `results` r
JOIN `drivers` d ON d.`driverId` = r.`driverId`
GROUP BY r.`driverId`
ORDER BY total_points DESC
LIMIT 1;
```

Predicted SQL:

```sql
SELECT T1.forename, T1.surname, T2.points FROM drivers AS T1 INNER JOIN driverStandings AS T2 ON T1.driverId = T2.driverId ORDER BY T2.points DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| forename | surname | total_points |
|---|---|---|
| Lewis | Hamilton | 2510.0 |

Predicted (first 1 of 1 rows):

| forename | surname | points |
|---|---|---|
| Sebastian | Vettel | 397.0 |

## 930 / formula_1 / simple

Label: `gold_label_suspect` (classifier, gpt-6-luna): The evidence defines “rank the highest” as the minimum rank. The prediction selects Hamilton’s minimum rank across his results, while the gold SQL hard-codes `rank = 1`, which does not match the benchmark’s stated interpretation and yields different rows.

Question:

```text
In which Formula_1 races did Lewis Hamilton rank the highest?
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
SELECT T3.name FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T2.raceId = T3.raceId WHERE T1.forename = 'Lewis' AND T1.surname = 'Hamilton' AND T2.rank = (SELECT MIN(T4.rank) FROM results AS T4 INNER JOIN drivers AS T5 ON T4.driverId = T5.driverId WHERE T5.forename = 'Lewis' AND T5.surname = 'Hamilton')
```

Result diff:

Gold 38 rows, predicted 3 rows. Within the previews: 2 rows only in gold, 1 only in predicted.

Gold (first 5 of 38 rows):

| name |
|---|
| Chinese Grand Prix |
| Malaysian Grand Prix |
| Japanese Grand Prix |
| Chinese Grand Prix |
| Spanish Grand Prix |

Predicted (first 3 of 3 rows):

| name |
|---|
| Chinese Grand Prix |
| Belgian Grand Prix |
| Spanish Grand Prix |

## 962 / formula_1 / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts DISTINCT driver IDs in both numerator and denominator, while the prediction counts result rows, so drivers appearing in multiple races are counted repeatedly.

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
SELECT CAST(COUNT(CASE WHEN STRFTIME('%Y', T2.dob) < '1985' AND T1.laps > 50 THEN T1.driverId END) AS REAL) * 100 / COUNT(T1.driverId) FROM results AS T1 INNER JOIN drivers AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T1.raceId = T3.raceId WHERE T3.year BETWEEN 2000 AND 2005
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT IIF(STRFTIME('%Y', … |
|---|
| 100.0 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN STRFTIME('%Y', T2.… |
|---|
| 64.6189376443418 |

## 1011 / formula_1 / challenging

Label: `date_handling` (classifier, gpt-6-luna): The prediction orders by `MIN(T2.time)`, a formatted time string, while the gold query orders by numeric `MIN(milliseconds)`. Comparing formatted lap times as text can produce a different ranking.

Question:

```text
List the full names of the top 20 drivers, ranked by their shortest lap time ever record in a Formula_1 race.
```

Evidence:

```text
shortest lap time refers to MIN(time); the time format for the shortest lap time is 'MM:SS.mmm' or 'M:SS.mmm'; full name of the driver refers to forename, surname
```

Gold SQL:

```sql
SELECT d.forename, d.surname FROM drivers d INNER JOIN (SELECT driverId, MIN(milliseconds) as min_ms FROM lapTimes WHERE milliseconds IS NOT NULL GROUP BY driverId) lt ON d.driverId = lt.driverId ORDER BY lt.min_ms ASC LIMIT 20;
```

Predicted SQL:

```sql
SELECT T1.forename, T1.surname FROM drivers AS T1 INNER JOIN lapTimes AS T2 ON T1.driverId = T2.driverId WHERE T2.time IS NOT NULL GROUP BY T1.driverId, T1.forename, T1.surname ORDER BY MIN(T2.time) ASC LIMIT 20
```

Result diff:

Gold 20 rows, predicted 20 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 20 rows):

| forename | surname |
|---|---|
| Lewis | Hamilton |
| Daniel | Ricciardo |
| Kimi | Räikkönen |
| Sebastian | Vettel |
| Valtteri | Bottas |

Predicted (first 5 of 20 rows):

| forename | surname |
|---|---|
| Anthony | Davidson |
| Enrique | Bernoldi |
| Christian | Klien |
| Timo | Glock |
| Kevin | Magnussen |

## 1037 / european_football_2 / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The prediction aggregates Player_Attributes rows with SUM and COUNT, while the gold counts distinct players for both numerator and denominator. Repeated attribute rows therefore change the percentage.

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
SELECT CAST(COUNT(DISTINCT CASE WHEN t2.preferred_foot = 'left' THEN t1.id ELSE NULL END) AS REAL) * 100 / COUNT(DISTINCT t1.id) percent FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id WHERE SUBSTR(t1.birthday, 1, 4) BETWEEN '1987' AND '1992'
```

Predicted SQL:

```sql
SELECT CAST(SUM(T2.preferred_foot = 'left') AS REAL) * 100 / COUNT(T2.player_fifa_api_id) FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE STRFTIME('%Y', T1.birthday) BETWEEN '1987' AND '1992'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| percent |
|---|
| 28.868144690781797 |

Predicted (first 1 of 1 rows):

| CAST(SUM(T2.preferred_foot = 'left') AS… |
|---|
| 24.56690504416995 |

## 1092 / european_football_2 / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every league tied for the maximum match count. The prediction orders by count and uses LIMIT 1, returning only one league and dropping the other ties.

Question:

```text
Give the names of the leagues with the most matches in the 2008/2009 season?
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

## 1110 / european_football_2 / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction adds an altered date pattern (`'2010-02-22%け'`) and an extra `NOT LIKE 'x'` condition instead of matching the gold date filter `LIKE '2010-02-22%'`, producing extra rows.

Question:

```text
Tell the build Up play passing class for "FC Lorient" on 2010/2/22.
```

Evidence:

```text
"FC Lorient" refers to team_long_name = 'FC Lorient'; on 2010/2/22 refers to date LIKE '2010-02-22%';
```

Gold SQL:

```sql
SELECT t2.buildUpPlayPassingClass FROM Team AS t1 INNER JOIN Team_Attributes AS t2 ON t1.team_api_id = t2.team_api_id WHERE t1.team_long_name = 'FC Lorient' AND t2."date" LIKE '2010-02-22%'
```

Predicted SQL:

```sql
SELECT T2.buildUpPlayPassingClass FROM Team AS T1 INNER JOIN Team_Attributes AS T2 ON T1.team_api_id = T2.team_api_id WHERE T1.team_long_name = 'FC Lorient' AND T2.date LIKE '2010-02-22%け' NOT LIKE 'x'
```

Result diff:

Gold 1 rows, predicted 6 rows. Within the previews: 0 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| buildUpPlayPassingClass |
|---|
| Long |

Predicted (first 5 of 6 rows):

| buildUpPlayPassingClass |
|---|
| Long |
| Mixed |
| Mixed |
| Mixed |
| Mixed |

## 1115 / european_football_2 / challenging

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query joins Player to Player_Attributes on player_fifa_api_id, while the prediction uses player_api_id for both player joins. This changes which attribute records are matched.

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
SELECT (SUM(CASE WHEN t1.player_name = 'Landon Donovan' THEN t2.overall_rating ELSE 0 END) * 1.0 - 
SUM(CASE WHEN t1.player_name = 'Jordan Bowery' THEN t2.overall_rating ELSE 0 END)) * 100 / 
SUM(CASE WHEN t1.player_name = 'Jordan Bowery' THEN t2.overall_rating ELSE 0 END) LvsJ_percent 
FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_fifa_api_id = t2.player_fifa_api_id WHERE SUBSTR(t2.date, 1, 10) = '2013-07-12'
```

Predicted SQL:

```sql
SELECT CAST(T2.overall_rating - T4.overall_rating AS REAL) * 100 / T2.overall_rating FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id INNER JOIN Player AS T3 ON T3.player_name = 'Jordan Bowery' INNER JOIN Player_Attributes AS T4 ON T3.player_api_id = T4.player_api_id WHERE T1.player_name = 'Landon Donovan' AND DATE(T2.date) = '2013-07-12' AND DATE(T4.date) = '2013-07-12'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| LvsJ_percent |
|---|
| 33.898305084745765 |

Predicted (first 1 of 1 rows):

| CAST(T2.overall_rating - T4.overall_rat… |
|---|
| 25.31645569620253 |

## 1148 / european_football_2 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts distinct player IDs in both numerator and denominator, while the prediction counts joined attribute rows with COUNT(*), inflating the counts for players with multiple attribute records.

Question:

```text
What is the percentage of players that are under 180 cm who have an overall strength of more than 70?
```

Evidence:

```text
percentage refers to DIVIDE(COUNT(height < 180 AND overall_rating > 70),COUNT(height < 180)) * 100
```

Gold SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN t2.overall_rating > 70 AND t1.height < 180 THEN t1.id END) AS REAL) * 100 / COUNT(DISTINCT t1.id) percent FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id WHERE t1.height < 180
```

Predicted SQL:

```sql
SELECT CAST(COUNT(CASE WHEN T2.overall_rating > 70 THEN 1 END) AS REAL) * 100 / COUNT(*) FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.height < 180
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| percent |
|---|
| 51.1572856391373 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T2.overall_rating … |
|---|
| 40.65754640711444 |

## 1166 / thrombosis_prediction / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query first identifies the youngest patient who had an examination, then returns that patient’s non-NULL symptoms—or NULL if none exist. The prediction filters to examinations with non-NULL symptoms before ordering and limiting, so it can select an older patient instead.

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
SELECT T2.Symptoms, T1.Diagnosis FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T2.Symptoms IS NOT NULL ORDER BY T1.Birthday DESC LIMIT 1
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
| CNS susp | SLE |

## 1169 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts distinct patient IDs meeting each condition, while the prediction sums one per matching joined laboratory row. This counts patients with multiple qualifying rows more than once and changes the ratio.

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
SELECT CAST(COUNT(DISTINCT CASE WHEN T2.UA <= 8.0 AND T1.SEX = 'M' THEN T1.ID ELSE NULL END) AS REAL) / COUNT(DISTINCT CASE WHEN T2.UA <= 6.5 AND T1.SEX = 'F' THEN T1.ID ELSE NULL END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T2.UA <= 8.0 AND T1.SEX = 'M' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN T2.UA <= 6.5 AND T1.SEX = 'F' THEN 1 ELSE 0 END) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.UA <= … |
|---|
| 0.184 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T2.UA <= 8.0 AND T1.… |
|---|
| 0.20566810835419985 |

## 1225 / thrombosis_prediction / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query groups by sex and concatenates distinct patient IDs into one row per sex. The prediction instead returns individual distinct sex–ID pairs without grouping or aggregation.

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
SELECT DISTINCT T1.SEX, T1.ID FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-BIL` >= 2.0 ORDER BY T1.SEX, T1.ID
```

Result diff:

Gold 2 rows, predicted 10 rows. Within the previews: 2 rows only in gold, 5 only in predicted.

Gold (first 2 of 2 rows):

| GROUP_CONCAT(DISTINCT T1.ID) | SEX |
|---|---|
| 250391,1180510,2308236,2931207,4862013 | F |
| 43003,444499,1137040,2307640,4618443 | M |

Predicted (first 5 of 10 rows):

| SEX | ID |
|---|---|
| F | 250391 |
| F | 1180510 |
| F | 2308236 |
| F | 2931207 |
| F | 4862013 |

## 1227 / thrombosis_prediction / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query deduplicates patients by ID before averaging age, while the prediction averages joined patient-laboratory rows directly. Multiple qualifying laboratory rows per patient therefore weight that patient more than once.

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
SELECT AVG(CAST(STRFTIME('%Y', 'now') AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER)) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M' AND T2.`T-CHO` >= 250
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(age) |
|---|
| 71.95 |

Predicted (first 1 of 1 rows):

| AVG(CAST(STRFTIME('%Y', 'now') AS INTEG… |
|---|
| 74.68535825545172 |

## 1241 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts distinct patient IDs for each platelet range, while the prediction sums boolean conditions across laboratory rows, so it counts abnormal measurements rather than patients. The prediction also returns a low-minus-high difference instead of the high-range patient count.

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
SELECT SUM(T1.PLT < 100), SUM(T1.PLT < 100) - SUM(T1.PLT > 400) FROM Laboratory AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| low_count | high_count |
|---|---|
| 36 | 82 |

Predicted (first 1 of 1 rows):

| SUM(T1.PLT < 100) | SUM(T1.PLT < 100) - SUM(T1.PLT > 400) |
|---|---|
| 320 | -555 |

## 1243 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold counts distinct patient IDs for the numerator and denominator, while the prediction sums qualifying laboratory rows. Patients with multiple PT records are therefore counted repeatedly in the prediction.

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
SELECT CAST(SUM(T2.PT >= 14 AND T1.SEX = 'F') AS REAL) * 100 / SUM(T2.PT >= 14) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE CAST(STRFTIME('%Y', CURRENT_TIMESTAMP) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER) > 55
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.PT >= … |
|---|
| 72.72727272727273 |

Predicted (first 1 of 1 rows):

| CAST(SUM(T2.PT >= 14 AND T1.SEX = 'F') … |
|---|
| 78.3625730994152 |

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

## 1482 / debit_card_specializing / challenging

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The percentage calculations match, but the gold query returns three percentage columns in one row, while the prediction returns a Segment column and one percentage column across three rows. The result columns and row structure therefore differ.

Question:

```text
Provide the percentage increase or decrease in consumption paid in EUR between 2012 and 2013 for SME, LAM, and KAM respectively.
```

Evidence:

```text
Increase or Decrease = consumption for 2013 - consumption for 2012; Percentage of Increase = (Increase or Decrease / consumption for 2012) * 100%; The first 4 strings of the Date values in the yearmonth table can represent year
```

Gold SQL:

```sql
SELECT CAST((SUM(IIF(T1.Segment = 'SME' AND T2.Date LIKE '2013%', T2.Consumption, 0)) - SUM(IIF(T1.Segment = 'SME' AND T2.Date LIKE '2012%', T2.Consumption, 0))) AS FLOAT) * 100 / SUM(IIF(T1.Segment = 'SME' AND T2.Date LIKE '2012%', T2.Consumption, 0)), CAST(SUM(IIF(T1.Segment = 'LAM' AND T2.Date LIKE '2013%', T2.Consumption, 0)) - SUM(IIF(T1.Segment = 'LAM' AND T2.Date LIKE '2012%', T2.Consumption, 0)) AS FLOAT) * 100 / SUM(IIF(T1.Segment = 'LAM' AND T2.Date LIKE '2012%', T2.Consumption, 0)), CAST(SUM(IIF(T1.Segment = 'KAM' AND T2.Date LIKE '2013%', T2.Consumption, 0)) - SUM(IIF(T1.Segment = 'KAM' AND T2.Date LIKE '2012%', T2.Consumption, 0)) AS FLOAT) * 100 / SUM(IIF(T1.Segment = 'KAM' AND T2.Date LIKE '2012%', T2.Consumption, 0)) FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Currency = 'EUR'
```

Predicted SQL:

```sql
SELECT T1.Segment, CAST(SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2013' THEN T2.Consumption ELSE 0 END) - SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2012' THEN T2.Consumption ELSE 0 END) AS REAL) * 100 / SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2012' THEN T2.Consumption ELSE 0 END) AS c1 FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Currency = 'EUR' AND T1.Segment IN ('SME', 'LAM', 'KAM') AND SUBSTR(T2.Date, 1, 4) IN ('2012', '2013') GROUP BY T1.Segment ORDER BY CASE T1.Segment WHEN 'SME' THEN 1 WHEN 'LAM' THEN 2 WHEN 'KAM' THEN 3 END ASC
```

Result diff:

Gold 1 rows, predicted 3 rows. Within the previews: 1 rows only in gold, 3 only in predicted.

Gold (first 1 of 1 rows):

| CAST((SUM(IIF(T1.Segment = 'SME' AND T2… | CAST(SUM(IIF(T1.Segment = 'LAM' AND T2.… | CAST(SUM(IIF(T1.Segment = 'KAM' AND T2.… |
|---|---|---|
| 734.7140627123255 | 539.8291924960649 | 553.2053767491262 |

Predicted (first 3 of 3 rows):

| Segment | c1 |
|---|---|
| SME | 734.7140627123255 |
| LAM | 539.8291924960649 |
| KAM | 553.2053767491262 |

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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query identifies the customer with `T1.Price = 634.8`, while the prediction uses `T1.Amount * T1.Price = 634.8`. That changes the transaction filter and yields no matching customer rows.

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
WITH cte1 AS (SELECT DISTINCT T1.CustomerID FROM transactions_1k AS T1 WHERE T1.Date = '2012-08-25' AND T1.Amount * T1.Price = 634.8) SELECT CAST(SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2012' THEN T2.Consumption ELSE 0 END) - SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2013' THEN T2.Consumption ELSE 0 END) AS REAL) / SUM(CASE WHEN SUBSTR(T2.Date, 1, 4) = '2012' THEN T2.Consumption ELSE 0 END) FROM cte1 AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID GROUP BY T1.CustomerID LIMIT 1
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(SUBSTRING(Date, 1, 4) = '2… |
|---|
| -5.815242674672346 |

Predicted (first 0 of 0 rows):

| CAST(SUM(CASE WHEN SUBSTR(T2.Date, 1, 4… |
|---|

## 1529 / debit_card_specializing / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query reads `transactions_1k` and calculates spending as `Amount * Price`, while the prediction reads `yearmonth` and sums `Consumption`. This changes the source and measure used for the requested amount.

Question:

```text
What is the amount spent by customer "38508" at the gas stations? How much had the customer spent in August 2012?
```

Evidence:

```text
August 2012 refers to the Date value = '201208'
```

Gold SQL:

```sql
SELECT SUM(Amount * Price) AS total_spent, SUM(CASE WHEN Date LIKE '2012-08%' THEN Amount * Price ELSE 0 END) AS august_2012_spent FROM transactions_1k WHERE CustomerID = 38508
```

Predicted SQL:

```sql
SELECT SUM(T1.Consumption), SUM(CASE WHEN T1.Date = '201208' THEN T1.Consumption ELSE 0 END) FROM yearmonth AS T1 WHERE T1.CustomerID = 38508
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| total_spent | august_2012_spent |
|---|---|
| 88612.38 | 88612.38 |

Predicted (first 1 of 1 rows):

| SUM(T1.Consumption) | SUM(CASE WHEN T1.Date = '201208' THEN T… |
|---|---|
| 5124646.35 | 67433.08 |

## 1531 / debit_card_specializing / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query selects the customer with the greatest SUM(Amount * Price), while the prediction ranks customers by SUM(Price). It also computes the average item price as SUM(Price) / SUM(Amount) instead of the gold formula SUM(Price * Amount) / SUM(Amount).

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
SELECT c.CustomerID, SUM(t.Price * t.Amount) / SUM(t.Amount) AS average_price_per_item, c.Currency FROM transactions_1k AS t JOIN customers AS c ON t.CustomerID = c.CustomerID WHERE t.CustomerID = ( SELECT CustomerID FROM transactions_1k GROUP BY CustomerID ORDER BY SUM(Amount * Price) DESC LIMIT 1 ) GROUP BY c.CustomerID, c.Currency;
```

Predicted SQL:

```sql
SELECT T1.CustomerID, CAST(SUM(T1.Price) AS REAL) / SUM(T1.Amount) AS c1, T2.Currency FROM transactions_1k AS T1 INNER JOIN customers AS T2 ON T1.CustomerID = T2.CustomerID GROUP BY T1.CustomerID, T2.Currency ORDER BY SUM(T1.Price) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CustomerID | average_price_per_item | Currency |
|---|---|---|
| 13665 | 5762.49 | CZK |

Predicted (first 1 of 1 rows):

| CustomerID | c1 | Currency |
|---|---|---|
| 19182 | 24.277577464788735 | CZK |
