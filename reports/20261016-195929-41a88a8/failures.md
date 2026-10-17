# Failures: best on bird_arcwise / dev

52 of 349 questions failed. Evidence on, git `41a88a836fa385225e7737edd13ac9197637fa02`, complete: 349 questions.

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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query excludes rows where `School` is NULL, but the prediction omits that condition, yielding three additional rows.

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
SELECT T2.School, T2.Street FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`Enrollment (K-12)` - T1.`Enrollment (Ages 5-17)` > 30
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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters `satscores` to `rtype = 'S'`, while the prediction omits that condition, changing which school ranks highest.

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
SELECT T1.AdmFName1, T1.AdmLName1, T1.AdmFName2, T1.AdmLName2, T1.AdmFName3, T1.AdmLName3 FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds ORDER BY T2.NumGE1500 DESC LIMIT 1
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The prediction counts only virtual schools with higher scores when determining the top five, while the gold ranks all qualifying schools within each county and applies the virtual-school filter afterward. It also omits the gold query’s `rtype = 'S'` condition.

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
SELECT T1.School FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.`Virtual` = 'F' AND T2.AvgScrRead IS NOT NULL AND (SELECT COUNT(*) FROM schools AS T3 INNER JOIN satscores AS T4 ON T3.CDSCode = T4.cds WHERE T3.County = T1.County AND T3.`Virtual` = 'F' AND T4.AvgScrRead > T2.AvgScrRead) < 5
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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction applies `County = 'Orange'` to both sides, but the gold denominator counts merged DOC 52 schools across all counties. It also omits the gold `school IS NOT NULL` condition.

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
SELECT CAST(SUM(CASE WHEN T1.DOC = '54' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN T1.DOC = '52' THEN 1 ELSE 0 END) FROM schools AS T1 WHERE T1.StatusType = 'Merged' AND T1.County = 'Orange'
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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s filters `rtype = 'S'` and `AvgScrMath IS NOT NULL`, so it ranks a different set of score rows and returns a different school.

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
SELECT T2.MailStreet, T2.School FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode ORDER BY T1.AvgScrMath DESC LIMIT 1 OFFSET 6
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

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The predicted query selects both `atom_id` and `atom_id2`, while the gold query returns only the distinct `atom_id` column. The bond and molecule filters match.

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
SELECT T1.atom_id, T1.atom_id2 FROM connected AS T1 INNER JOIN bond AS T2 ON T1.bond_id = T2.bond_id WHERE T2.molecule_id = 'TR041' AND T2.bond_type = '#'
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

Label: `wrong_join_path` (classifier, gpt-6-luna): The prediction joins each atom directly to every matching bond, duplicating atoms in molecules with multiple single bonds. The gold query uses an `IN` subquery over distinct molecule IDs, so each atom is counted only once.

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
SELECT CAST(SUM(T1.element = 'cl') AS REAL) * 100 / COUNT(T1.atom_id) FROM atom AS T1 INNER JOIN bond AS T2 ON T1.molecule_id = T2.molecule_id WHERE T2.bond_type = '-'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(CASE WHEN T.element = 'cl' T… |
|---|
| 3.4823684499615513 |

Predicted (first 1 of 1 rows):

| CAST(SUM(T1.element = 'cl') AS REAL) * … |
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every card UUID tied for the maximum ruling count, while the prediction orders grouped cards and uses `LIMIT 1`, selecting only one tied result.

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
SELECT T1.name, T1.artist, T1.isPromo FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid GROUP BY T1.uuid, T1.name, T1.artist, T1.isPromo ORDER BY COUNT(T2.uuid) DESC LIMIT 1
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

Label: `wrong_join_path` (classifier, gpt-6-luna): The gold query uses a LEFT JOIN, while the prediction uses an INNER JOIN, which excludes cards without a matching foreign_data row. The prediction also counts joined rows rather than distinct cards, but the join-type difference is the first issue.

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
SELECT CAST(SUM(CASE WHEN T2.language = 'French' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*'
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
| 12.975290140452374 |

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

## 640 / codebase_community / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction compares DisplayName to lowercase 'mornington', while the gold query uses 'Mornington'. This mismatched literal excludes Mornington’s posts and changes the result.

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
SELECT SUM(CASE WHEN u.DisplayName = 'Mornington' THEN p.ViewCount ELSE 0 END) - SUM(CASE WHEN u.DisplayName = 'Amos' THEN p.ViewCount ELSE 0 END) FROM posts p JOIN users u ON p.OwnerUserId = u.Id WHERE u.DisplayName IN ('Mornington', 'Amos') AND p.ViewCount IS NOT NULL;
```

Predicted SQL:

```sql
SELECT SUM(CASE WHEN T2.DisplayName = 'mornington' THEN T1.ViewCount END) - SUM(CASE WHEN T2.DisplayName = 'Amos' THEN T1.ViewCount END) FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T2.DisplayName IN ('mornington', 'Amos')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(CASE WHEN u.DisplayName = 'Morningt… |
|---|
| -497 |

Predicted (first 1 of 1 rows):

| SUM(CASE WHEN T2.DisplayName = 'morning… |
|---|
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

## 685 / codebase_community / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question asks for the user who posted it last time, but the gold query returns the post’s LastEditorUserId and does not identify the latest history entry. The prediction uses the UserId on the most recent matching postHistory row, which better matches the wording.

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
SELECT T1.ViewCount, T3.DisplayName FROM posts AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.PostId INNER JOIN users AS T3 ON T2.UserId = T3.Id WHERE T2.Text = 'Computer Game Datasets' AND T2.CreationDate IS NOT NULL ORDER BY T2.CreationDate DESC LIMIT 1
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query includes posts from every user tied at the maximum reputation, while the prediction ranks users and limits to a single user. The ranking logic can exclude posts by other tied top users.

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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query excludes rows where `height_cm` is NULL or 0, but the prediction omits both conditions, yielding more heroes.

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
SELECT T1.superhero_name FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id WHERE T2.publisher_name = 'Marvel Comics' ORDER BY T1.height_cm DESC
```

Result diff:

Gold 327 rows, predicted 387 rows. Within the previews: 0 rows only in gold, 0 only in predicted.

Gold (first 5 of 327 rows):

| superhero_name |
|---|
| Surtur |
| Ymir |
| Bloodwraith |
| Utgard-Loki |
| Fin Fang Foom |

Predicted (first 5 of 387 rows):

| superhero_name |
|---|
| Surtur |
| Ymir |
| Bloodwraith |
| Utgard-Loki |
| Fin Fang Foom |

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

## 829 / superhero / challenging

Label: `extra_or_missing_output_columns` (classifier, gpt-6-luna): The predicted query computes the same difference (-163), but returns only that value. The gold query also returns the publisher with more superheroes, so the prediction is missing that output column.

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
SELECT SUM(T2.publisher_name = 'DC Comics') - SUM(T2.publisher_name = 'Marvel Comics') FROM superhero AS T1 INNER JOIN publisher AS T2 ON T1.publisher_id = T2.id
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

## 880 / formula_1 / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The evidence defines the percentage with fastest-lap speed in race 853 as the denominator, which the prediction uses. The gold SQL instead divides by the speed in race 854, so it contradicts the supplied formula.

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
SELECT CAST((T2.fastestLapSpeed - T3.fastestLapSpeed) AS REAL) * 100 / T2.fastestLapSpeed FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN results AS T3 ON T1.driverId = T3.driverId WHERE T1.forename = 'Paul' AND T1.surname = 'di Resta' AND T2.raceId = 853 AND T3.raceId = 854
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| percent_faster |
|---|
| 48.15155382074764 |

Predicted (first 1 of 1 rows):

| CAST((T2.fastestLapSpeed - T3.fastestLa… |
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

## 930 / formula_1 / simple

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query selects Hamilton’s results with rank = 1, while the prediction compares ranks to a single MIN(rank) aggregated across all of his results. That global aggregation does not identify the races where he ranked highest as the gold query does.

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
SELECT DISTINCT T1.name FROM races AS T1 INNER JOIN results AS T2 ON T1.raceId = T2.raceId INNER JOIN drivers AS T3 ON T2.driverId = T3.driverId WHERE T3.forename = 'Lewis' AND T3.surname = 'Hamilton' AND T2.rank = (SELECT MIN(T4.rank) FROM results AS T4 INNER JOIN drivers AS T5 ON T4.driverId = T5.driverId WHERE T5.forename = 'Lewis' AND T5.surname = 'Hamilton')
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts distinct patient IDs in each sex/UA category, while the prediction sums one per matching joined row, so patients with multiple laboratory records are counted repeatedly.

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
SELECT CAST(SUM(CASE WHEN T1.UA <= 8.0 AND T2.SEX = 'M' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN T1.UA <= 6.5 AND T2.SEX = 'F' THEN 1 ELSE 0 END) FROM Laboratory AS T1 INNER JOIN Patient AS T2 ON T1.ID = T2.ID
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T2.UA <= … |
|---|
| 0.184 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.UA <= 8.0 AND T2.… |
|---|
| 0.20566810835419985 |

## 1225 / thrombosis_prediction / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query groups patients by sex and aggregates their distinct IDs with GROUP_CONCAT. The prediction instead returns distinct sex-ID rows without grouping or aggregation, producing multiple rows per sex.

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
SELECT DISTINCT T1.SEX, T1.ID FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.`T-BIL` >= 2.0 ORDER BY T1.SEX
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query deduplicates patients by ID before averaging age, while the prediction aggregates directly over joined laboratory rows, so patients with multiple qualifying lab records are counted multiple times.

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
SELECT CAST(SUM(CAST(STRFTIME('%Y', CURRENT_DATE) AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER)) AS REAL) / COUNT(T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.SEX = 'M' AND T2.`T-CHO` >= 250
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(age) |
|---|
| 71.95 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CAST(STRFTIME('%Y', CURRENT_DA… |
|---|
| 74.68535825545172 |

## 1241 / thrombosis_prediction / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query counts distinct patient IDs for each range, while the prediction sums per-row Boolean tests, producing row counts instead. It also returns low minus high in `c2` rather than the high-range patient count.

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
SELECT SUM(T1.PLT < 100) AS c1, SUM(T1.PLT < 100) - SUM(T1.PLT > 400) AS c2 FROM Laboratory AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| low_count | high_count |
|---|---|
| 36 | 82 |

Predicted (first 1 of 1 rows):

| c1 | c2 |
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

## 1255 / thrombosis_prediction / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query deduplicates patient ID–Diagnosis pairs before counting diagnoses, while the prediction counts joined rows directly. Multiple abnormal-IgM laboratory rows for a patient can therefore inflate a diagnosis count and change the most common result.

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
SELECT Diagnosis FROM (SELECT DISTINCT T1.ID, T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGM <= 40 OR T2.IGM >= 400) GROUP BY Diagnosis ORDER BY COUNT(*) DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.IGM <= 40 OR T2.IGM >= 400 GROUP BY T1.Diagnosis ORDER BY COUNT(T1.Diagnosis) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| Diagnosis |
|---|
| SLE |

Predicted (first 1 of 1 rows):

| Diagnosis |
|---|
| RA |

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

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query identifies the customer using `T1.Price = 634.8`, while the prediction instead requires `T1.Amount * T1.Price = 634.8`. That changes the customer filter and can leave no matching customer, as in the predicted result.

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
WITH cte1 AS (SELECT DISTINCT T1.CustomerID FROM transactions_1k AS T1 WHERE T1.Date = '2012-08-25' AND T1.Amount * T1.Price = 634.8), cte2 AS (SELECT T1.CustomerID, SUM(CASE WHEN T1.Date BETWEEN '201201' AND '201212' THEN T1.Consumption ELSE 0 END) AS c1, SUM(CASE WHEN T1.Date BETWEEN '201301' AND '201312' THEN T1.Consumption ELSE 0 END) AS c2 FROM yearmonth AS T1 INNER JOIN cte1 AS T2 ON T1.CustomerID = T2.CustomerID GROUP BY T1.CustomerID) SELECT CAST(T1.c1 - T1.c2 AS REAL) / T1.c1 FROM cte2 AS T1
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(SUBSTRING(Date, 1, 4) = '2… |
|---|
| -5.815242674672346 |

Predicted (first 0 of 0 rows):

| CAST(T1.c1 - T1.c2 AS REAL) / T1.c1 |
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The predicted query divides SUM(Price) by SUM(Amount), but the evidence and gold query require SUM(Price * Amount) divided by SUM(Amount). It identifies the top-spending customer correctly, but therefore computes the wrong average item price.

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
SELECT T1.CustomerID, CAST(SUM(T1.Price) AS REAL) / SUM(T1.Amount) AS c1, T2.Currency FROM transactions_1k AS T1 INNER JOIN customers AS T2 ON T1.CustomerID = T2.CustomerID GROUP BY T1.CustomerID, T2.Currency ORDER BY SUM(T1.Amount * T1.Price) DESC LIMIT 1
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
| 13665 | 21.827613636363637 | CZK |
