# Failures: best on bird_arcwise / test

37 of 149 questions failed. Evidence off, git `70b12ce88825feb7263dfaf0a75ccf74d10bb829`, complete: 149 questions.

## 24 / california_schools / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold conditions `NumGE1500 > 0` and `rtype = 'S'`, so it includes schools that do not meet the test-taker requirement. It also returns an extra `NumGE1500` column, but the missing filters are the first logic difference.

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
SELECT T2."School Name"
FROM satscores AS T1 INNER JOIN frpm AS T2 ON T1.cds = T2.CDSCode 
WHERE CAST(T2."Free Meal Count (K-12)" AS REAL) / T2."Enrollment (K-12)" > 0.1 AND T1.NumGE1500 > 0 AND rtype = 'S'
```

Predicted SQL:

```sql
SELECT T2.sname, T2.NumGE1500 FROM frpm AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.`Percent (%) Eligible Free (K-12)` > 0.1
```

Result diff:

Gold 1048 rows, predicted 1519 rows. Within the previews: 5 rows only in gold, 5 only in predicted.

Gold (first 5 of 1048 rows):

| School Name |
|---|
| Clovis North High |
| Clovis West High |
| Buchanan High |
| Clovis East High |
| Clovis High |

Predicted (first 5 of 1519 rows):

| sname | NumGE1500 |
|---|---|
| Crescent View West Charter | None |
| Hume Lake Charter | None |
| Big Picture High School - Fresno | None |
| Clovis North High | 193 |
| Clovis Online Charter | None |

## 37 / california_schools / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query restricts rows to `rtype = 'S'`, but the prediction omits that condition. It also uses `ORDER BY ... LIMIT 1`, which returns only one school rather than all schools tied at the minimum.

Question:

```text
What is the complete address of the school with the lowest excellence rate? Indicate the Street, City, State, and Zip.
```

Evidence:

```text
Execellence Rate = NumGE1500 / NumTstTakr; complete address has Street, City, State, Zip code
```

Gold SQL:

```sql
SELECT s.Street, s.City, s.State, s.Zip 
FROM schools s JOIN satscores sat ON s.CDSCode = sat.cds 
WHERE sat.NumTstTakr > 0 AND sat.NumGE1500 IS NOT NULL AND sat.NumTstTakr IS NOT NULL  AND rtype = 'S'
AND CAST(sat.NumGE1500 AS FLOAT) / CAST(sat.NumTstTakr AS FLOAT) =
 (SELECT MIN(CAST(NumGE1500 AS FLOAT) / CAST(NumTstTakr AS FLOAT)) 
 FROM satscores WHERE NumTstTakr > 0 AND NumGE1500 IS NOT NULL AND NumTstTakr IS NOT NULL AND rtype = 'S' )
```

Predicted SQL:

```sql
SELECT T1.Street, T1.City, T1.State, T1.Zip FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T2.NumTstTakr > 0 AND T2.NumGE1500 IS NOT NULL ORDER BY CAST(T2.NumGE1500 AS REAL) / T2.NumTstTakr ASC LIMIT 1
```

Result diff:

Gold 13 rows, predicted 1 rows. Within the previews: 4 rows only in gold, 0 only in predicted.

Gold (first 5 of 13 rows):

| Street | City | State | Zip |
|---|---|---|---|
| 222 North Virgil Avenue | Los Angeles | CA | 90004-3622 |
| 147 North Occidental Boulevard | Los Angeles | CA | 90026-4601 |
| 12714 South Avalon Boulevard | Los Angeles | CA | 90061-2730 |
| 3501 North Broadway | Los Angeles | CA | 90031-2856 |
| 825 West 60th Street | Los Angeles | CA | 90044-5512 |

Predicted (first 1 of 1 rows):

| Street | City | State | Zip |
|---|---|---|---|
| 222 North Virgil Avenue | Los Angeles | CA | 90004-3622 |

## 46 / california_schools / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query uses `frpm."Enrollment (K-12)"` and filters on `schools.DOC = 31`; the prediction instead uses `satscores.enroll12` and filters on `schools.SOC = '31'`. These different columns lead to a different result.

Question:

```text
Which state special schools have the highest number of enrollees from grades 1 through 12?
```

Evidence:

```text
State Special Schools refers to DOC = 31; Grades 1 through 12 means K-12
```

Gold SQL:

```sql
SELECT T2.School 
FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode 
WHERE T2.DOC = 31 AND T2.school is not NULL ORDER BY T1."Enrollment (K-12)" DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.School FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.SOC = '31' ORDER BY T2.enroll12 DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| School |
|---|
| California School for the Deaf-Fremont |

Predicted (first 1 of 1 rows):

| School |
|---|
| California School for the Deaf-Riverside |

## 77 / california_schools / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The prediction selects the stored `Percent (%) Eligible FRPM (Ages 5-17)` column, whose values are proportions, while the evidence specifies calculating the percentage as FRPM Count divided by Enrollment and multiplied by 100. This yields values 100 times smaller than the gold results.

Question:

```text
Which schools served a grade span of Kindergarten to 9th grade in the county of Los Angeles and what is its Percent (%) Eligible FRPM (Ages 5-17)?
```

Evidence:

```text
Percent (%) Eligible FRPM (Ages 5-17) can be acquired by "FRPM Count (Ages 5-17)" / "Enrollment (Ages 5-17)" * 100
```

Gold SQL:

```sql
SELECT T2.School, T1."FRPM Count (Ages 5-17)" * 100 / T1."Enrollment (Ages 5-17)" FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.County = 'Los Angeles' AND T2.GSserved = 'K-9'
```

Predicted SQL:

```sql
SELECT T1.School, T2.`Percent (%) Eligible FRPM (Ages 5-17)` FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.GSserved = 'K-9' AND T1.County = 'Los Angeles'
```

Result diff:

Gold 2 rows, predicted 2 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 2 of 2 rows):

| School | T1."FRPM Count (Ages 5-17)" * 100 / T1.… |
|---|---|
| White Oak Elementary | 3.755868544600939 |
| The Accelerated | 97.63888888888889 |

Predicted (first 2 of 2 rows):

| School | Percent (%) Eligible FRPM (Ages 5-17) |
|---|---|
| White Oak Elementary | 0.0375586854460094 |
| The Accelerated | 0.976388888888889 |

## 186 / financial / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters the denominator to clients with weekly statements (`WHERE frequency = 'POPLATEK TYDNE'`) and counts male clients within that group. The prediction instead filters all rows to male clients and applies the weekly condition only to the numerator, reversing the intended denominator.

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
SELECT CAST(SUM(T1.gender = 'M') AS REAL) * 100 / COUNT(T1.client_id) FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id WHERE T3.frequency = 'POPLATEK TYDNE'
```

Predicted SQL:

```sql
SELECT CAST(COUNT(DISTINCT CASE WHEN T3.frequency = 'POPLATEK TYDNE' THEN T1.client_id END) AS REAL) * 100 / COUNT(DISTINCT T1.client_id) FROM client AS T1 INNER JOIN disp AS T2 ON T1.client_id = T2.client_id INNER JOIN account AS T3 ON T2.account_id = T3.account_id WHERE T1.gender = 'M'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(T1.gender = 'M') AS REAL) * 10… |
|---|
| 52.12765957446808 |

Predicted (first 1 of 1 rows):

| CAST(COUNT(DISTINCT CASE WHEN T3.freque… |
|---|
| 5.39647577092511 |

## 239 / toxicology / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The evidence defines atom 19 by `atom_id`, but the prediction also searches `atom_id2`, counting rows where the atom appears in that different column and producing 994 instead of 498.

Question:

```text
How many connections does the atom 19 have?
```

Evidence:

```text
connections refers to bond_id; atom 19 refers to atom_id like 'TR%_19';
```

Gold SQL:

```sql
SELECT COUNT(T.bond_id) FROM connected AS T WHERE SUBSTR(T.atom_id, -2) = '19'
```

Predicted SQL:

```sql
SELECT COUNT(*) FROM connected AS T1 WHERE SUBSTR(T1.atom_id, -3) = '_19' OR SUBSTR(T1.atom_id2, -3) = '_19'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(T.bond_id) |
|---|
| 498 |

Predicted (first 1 of 1 rows):

| COUNT(*) |
|---|
| 994 |

## 356 / card_games / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The evidence defines infinite power as `power = '*'`, but the prediction filters for `power = '∞'`, yielding a different count.

Question:

```text
How many cards have infinite power?
```

Evidence:

```text
infinite power refers to power = '*';
```

Gold SQL:

```sql
SELECT COUNT(*) FROM cards WHERE power = '*'
```

Predicted SQL:

```sql
SELECT COUNT(*) FROM cards AS T1 WHERE T1.power = '∞'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 429 |

Predicted (first 1 of 1 rows):

| COUNT(*) |
|---|
| 2 |

## 366 / card_games / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query gets the card’s playable formats from `legalities.format`, while the prediction reads `rulings.text`, which is a different table and column.

Question:

```text
What is the rule of playing card "Benalish Knight"?
```

Evidence:

```text
Benalish Knight' is the name of card; rule of playing card refers to format;
```

Gold SQL:

```sql
SELECT T2.format FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T1.name = 'Benalish Knight'
```

Predicted SQL:

```sql
SELECT DISTINCT T2.text FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE T1.name = 'Benalish Knight'
```

Result diff:

Gold 32 rows, predicted 0 rows. Within the previews: 5 rows only in gold, 0 only in predicted.

Gold (first 5 of 32 rows):

| format |
|---|
| commander |
| duel |
| legacy |
| modern |
| pauper |

Predicted (first 0 of 0 rows):

| text |
|---|

## 424 / card_games / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query computes the proportion over all cards, counting only cards that are both textless and have normal layout. The prediction filters the denominator to normal-layout cards and omits the required ×100, changing the proportion's basis and scale.

Question:

```text
What proportion of cards do not have a text box with a normal layout?
```

Evidence:

```text
do not have a text box refers to isTextless = 1; proportion refers to DIVIDE(COUNT(Textless = 1 and layout = 'normal'),COUNT(*))*100
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN isTextless = 1 AND layout = 'normal' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM cards
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.isTextless = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) FROM cards AS T1 WHERE T1.layout = 'normal'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN isTextless = 1 AND l… |
|---|
| 0.20238639963394459 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.isTextless = 1 TH… |
|---|
| 0.0020944887626124647 |

## 518 / card_games / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The queries select the same top banned format and its banned cards, with the same output columns. The only difference is `DISTINCT` in the prediction, which does not change rows when results are compared as a set.

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
WITH cte1 AS (SELECT T1.format FROM legalities AS T1 WHERE T1.status = 'Banned' GROUP BY T1.format ORDER BY COUNT(*) DESC LIMIT 1) SELECT DISTINCT T1.format, T2.name FROM legalities AS T1 INNER JOIN cards AS T2 ON T1.uuid = T2.uuid INNER JOIN cte1 AS T3 ON T1.format = T3.format WHERE T1.status = 'Banned'
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

## 533 / codebase_community / simple

Label: `date_handling` (classifier, gpt-6-luna): The gold query applies `date(LastAccessDate)` before comparing with `'2014-09-01'`, while the prediction compares the raw `LastAccessDate`; this changes which users qualify (4941 versus 5146).

Question:

```text
How many users last accessed the website after 2014/9/1?
```

Evidence:

```text
last accessed after 2014/9/1 refers to date(LastAccessDate) > '2014-09-01'
```

Gold SQL:

```sql
SELECT COUNT(Id) FROM users WHERE date(LastAccessDate) > '2014-09-01'
```

Predicted SQL:

```sql
SELECT COUNT(T1.Id) FROM users AS T1 WHERE T1.LastAccessDate > '2014-09-01'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(Id) |
|---|
| 4941 |

Predicted (first 1 of 1 rows):

| COUNT(T1.Id) |
|---|
| 5146 |

## 587 / codebase_community / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters with `Tags = '<humor>'`, while the prediction uses `Tags LIKE '%<humor>%'`, which can include posts whose tags merely contain that text. The prediction also groups by post ID, but the filter is the first difference to fix.

Question:

```text
Calculate the average view count of each post tagged as 'humor' and list the title and the comment of each post.
```

Evidence:

```text
tagged as  'humor' refers to tag = '<humor>'; comment of the post refers to Text; average view count = AVG(ViewCount)
```

Gold SQL:

```sql
SELECT AVG(T2.ViewCount), T2.Title, T1.Text FROM comments AS T1 INNER JOIN posts AS T2 ON T2.Id = T1.PostId  WHERE T2.Tags = '<humor>' GROUP BY T2.Title, T1.Text
```

Predicted SQL:

```sql
SELECT AVG(T1.ViewCount), T1.Title, T2.Text FROM posts AS T1 INNER JOIN comments AS T2 ON T1.Id = T2.PostId WHERE T1.Tags LIKE '%<humor>%' GROUP BY T1.Id, T1.Title, T2.Text
```

Result diff:

Gold 9 rows, predicted 19 rows. Within the previews: 0 rows only in gold, 0 only in predicted.

Gold (first 5 of 9 rows):

| AVG(T2.ViewCount) | Title | Text |
|---|---|---|
| 288.0 | So how many staticians *does* it take t… | @Jason Punyon in particular gets a humo… |
| 288.0 | So how many staticians *does* it take t… | Probably better asked on meta. People f… |
| 64481.0 | What is your favorite "data analysis" c… | @Sharpie, feel free to close or reopen … |
| 64481.0 | What is your favorite "data analysis" c… | @sharpie: are jokes out? We obviously d… |
| 64481.0 | What is your favorite "data analysis" c… | Also my question on the source of a sta… |

Predicted (first 5 of 19 rows):

| AVG(T1.ViewCount) | Title | Text |
|---|---|---|
| 288.0 | So how many staticians *does* it take t… | @Jason Punyon in particular gets a humo… |
| 288.0 | So how many staticians *does* it take t… | Probably better asked on meta. People f… |
| 64481.0 | What is your favorite "data analysis" c… | @Sharpie, feel free to close or reopen … |
| 64481.0 | What is your favorite "data analysis" c… | @sharpie: are jokes out? We obviously d… |
| 64481.0 | What is your favorite "data analysis" c… | Also my question on the source of a sta… |

## 598 / codebase_community / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query subtracts the 2011 share of all Student badges from the 2010 share, while the prediction computes a relative change using the 2010 count as its denominator. Its aggregation formula therefore differs from the requested calculation.

Question:

```text
What is the percentage difference of student badges given during 2010 and 2011?
```

Evidence:

```text
student badges refers to badge's name = 'Student'; during 2010 refers to Year(Date) = 2010; during 2011 refers to Year(Date) = 2011; percentage difference = Subtract (Divide(Count(Name where Year(Date) = 2010), Count (Name)) *100, Divide(Count(Name where Year(Date) = 2011), Count(Name)) * 100)
```

Gold SQL:

```sql
SELECT CAST(SUM(IIF(STRFTIME('%Y', Date) = '2010', 1, 0)) AS REAL) * 100 / COUNT(Id) - CAST(SUM(IIF(STRFTIME('%Y', Date) = '2011', 1, 0)) AS REAL) * 100 / COUNT(Id) FROM badges WHERE Name = 'Student'
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN STRFTIME('%Y', T1.Date) = '2011' THEN 1 ELSE 0 END) - SUM(CASE WHEN STRFTIME('%Y', T1.Date) = '2010' THEN 1 ELSE 0 END) AS REAL) * 100 / SUM(CASE WHEN STRFTIME('%Y', T1.Date) = '2010' THEN 1 ELSE 0 END) FROM badges AS T1 WHERE T1.Name = 'Student' AND STRFTIME('%Y', T1.Date) IN ('2010', '2011')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(IIF(STRFTIME('%Y', Date) = '20… |
|---|
| -9.544015626052403 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN STRFTIME('%Y', T1.Da… |
|---|
| 261.4391143911439 |

## 639 / codebase_community / challenging

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The prediction checks the `posts.Tags` column for `<r>`, while the gold query identifies R posts through `tags.TagName = 'r'` (via `postHistory`).

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
SELECT CAST(SUM(CASE WHEN T1.Tags LIKE '%<r>%' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM posts AS T1 INNER JOIN users AS T2 ON T1.OwnerUserId = T2.Id WHERE T2.DisplayName = 'Community'
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

## 791 / superhero / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters out rows where `height_cm` is not positive, but the prediction has no such condition. That changes which heights are averaged.

Question:

```text
Calculate the average height for all superhero.
```

Evidence:

```text
average = DIVIDE(SUM(height_cm), COUNT(all heros));
```

Gold SQL:

```sql
SELECT AVG(height_cm) FROM superhero WHERE height_cm > 0;
```

Predicted SQL:

```sql
SELECT AVG(T1.height_cm) FROM superhero AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(height_cm) |
|---|
| 345.03538175046555 |

Predicted (first 1 of 1 rows):

| AVG(T1.height_cm) |
|---|
| 267.7514450867052 |

## 794 / superhero / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every hero whose Speed equals the maximum, including ties; the prediction orders by Speed and limits the result to one hero.

Question:

```text
Which hero was the fastest?
```

Evidence:

```text
which hero refers to superhero_name; fastest refers to MAX(attribute_value) WHERE attribute_name = 'Speed';
```

Gold SQL:

```sql
SELECT s.superhero_name FROM superhero AS s JOIN hero_attribute AS ha ON s.id = ha.hero_id JOIN attribute AS a ON ha.attribute_id = a.id WHERE a.attribute_name = 'Speed' AND ha.attribute_value = ( SELECT MAX(ha2.attribute_value) FROM hero_attribute AS ha2 JOIN attribute AS a2 ON ha2.attribute_id = a2.id WHERE a2.attribute_name = 'Speed' )
```

Predicted SQL:

```sql
SELECT T1.superhero_name FROM superhero AS T1 INNER JOIN hero_attribute AS T2 ON T1.id = T2.hero_id INNER JOIN attribute AS T3 ON T2.attribute_id = T3.id WHERE T3.attribute_name = 'Speed' ORDER BY T2.attribute_value DESC LIMIT 1
```

Result diff:

Gold 40 rows, predicted 1 rows. Within the previews: 4 rows only in gold, 0 only in predicted.

Gold (first 5 of 40 rows):

| superhero_name |
|---|
| Air-Walker |
| Angela |
| Ardina |
| Aurora |
| Ben 10 |

Predicted (first 1 of 1 rows):

| superhero_name |
|---|
| Air-Walker |

## 937 / formula_1 / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction filters for `Australian Grand Prix`, while the evidence and gold query specify `Chinese Grand Prix`. It also uses `rank` rather than the gold query’s `position` column, but the race-name filter is the first difference to fix.

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
SELECT r.time FROM results r JOIN races ra ON r.raceId = ra.raceId WHERE ra.year = 2008 AND ra.name = 'Chinese Grand Prix' AND r.position = 2
```

Predicted SQL:

```sql
SELECT T1.time FROM results AS T1 INNER JOIN races AS T2 ON T1.raceId = T2.raceId WHERE T2.year = 2008 AND T2.name = 'Australian Grand Prix' AND T1.rank = 2
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| time |
|---|
| +14.925 |

Predicted (first 1 of 1 rows):

| time |
|---|
| 1:34:50.616 |

## 950 / formula_1 / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The evidence identifies constructor standings as the source, and the gold query filters `constructorStandings`. The prediction instead filters `constructorResults`, which changes which constructors qualify.

Question:

```text
Please list the constructor names with 0 points at race 291.
```

Evidence:

```text
race at 291 refers to raceID = 291; constructor refers to constructorStandings
```

Gold SQL:

```sql
SELECT T2.name FROM constructorStandings AS T1 INNER JOIN constructors AS T2 on T1.constructorId = T2.constructorId WHERE T1.points = 0 AND T1.raceId = 291
```

Predicted SQL:

```sql
SELECT T1.name FROM constructors AS T1 INNER JOIN constructorResults AS T2 ON T1.constructorId = T2.constructorId WHERE T2.points = 0 AND T2.raceId = 291
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

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction computes the average champion time in seconds per year; `AVG` ignores NULL values, so omitting `milliseconds IS NOT NULL` does not change the rows. Dividing the average by 1000 instead of averaging values already divided by 1000 is mathematically equivalent, with only minor floating-point differences.

Question:

```text
For each year before year 1975, what was the average time in seconds of the champion?
```

Evidence:

```text
only champion's finished time is represented by 'HH:MM:SS.mmm'; finished the game refers to time is not null; before year 1975 refers to year < 1975;
```

Gold SQL:

```sql
SELECT r.year, AVG(res.milliseconds / 1000.0) AS avg_time_seconds FROM results res JOIN races r ON res.raceId = r.raceId WHERE r.year < 1975 AND res.position = 1 AND res.milliseconds IS NOT NULL GROUP BY r.year
```

Predicted SQL:

```sql
SELECT T1.year, AVG(T2.milliseconds) / 1000.0 FROM races AS T1 INNER JOIN results AS T2 ON T1.raceId = T2.raceId WHERE T1.year < 1975 AND T2.position = 1 GROUP BY T1.year
```

Result diff:

Gold 25 rows, predicted 25 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 25 rows):

| year | avg_time_seconds |
|---|---|
| 1950 | 9712.595714285713 |
| 1951 | 10870.532222222222 |
| 1952 | 11061.585 |
| 1953 | 10828.476666666666 |
| 1954 | 11213.074444444444 |

Predicted (first 5 of 25 rows):

| year | AVG(T2.milliseconds) / 1000.0 |
|---|---|
| 1950 | 9712.595714285715 |
| 1951 | 10870.532222222222 |
| 1952 | 11061.585 |
| 1953 | 10828.476666666666 |
| 1954 | 11213.074444444444 |

## 1028 / european_football_2 / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold filters for season = '2009/2010', while the prediction uses '2010/2011'. This season literal difference must be fixed first.

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
SELECT DISTINCT t.team_long_name FROM Team t JOIN Match m ON t.team_api_id = m.away_team_api_id JOIN League l ON m.league_id = l.id WHERE l.name = 'Scotland Premier League' AND m.season = '2009/2010' AND m.away_team_goal > m.home_team_goal GROUP BY t.team_api_id, t.team_long_name HAVING COUNT(*) = ( SELECT MAX(win_count) FROM ( SELECT COUNT(*) AS win_count FROM Match m2 JOIN League l2 ON m2.league_id = l2.id WHERE l2.name = 'Scotland Premier League' AND m2.season = '2009/2010' AND m2.away_team_goal > m2.home_team_goal GROUP BY m2.away_team_api_id ) );
```

Predicted SQL:

```sql
SELECT T3.team_long_name FROM `Match` AS T1 INNER JOIN League AS T2 ON T1.league_id = T2.id INNER JOIN Team AS T3 ON T1.away_team_api_id = T3.team_api_id WHERE T2.name = 'Scotland Premier League' AND T1.season = '2010/2011' AND T1.away_team_goal > T1.home_team_goal GROUP BY T3.team_api_id, T3.team_long_name ORDER BY COUNT(T1.id) DESC LIMIT 1
```

Result diff:

Gold 2 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 2 of 2 rows):

| team_long_name |
|---|
| Rangers |
| Celtic |

Predicted (first 1 of 1 rows):

| team_long_name |
|---|
| Rangers |

## 1030 / european_football_2 / moderate

Label: `date_handling` (classifier, gpt-6-luna): The gold query identifies the 2016 season with `season = '2015/2016'`, while the prediction filters the match date’s year to `2016`. These select different season sets, producing different league results.

Question:

```text
Give the name of the league had the most matches end as draw in the 2016 season?
```

Evidence:

```text
most matches end as draw refers to MAX(SUM(home_team_goal = away_team_goal)); 2016 season refers to season = '2015/2016';
```

Gold SQL:

```sql
SELECT t2.name FROM Match AS t1 INNER JOIN League AS t2 ON t1.league_id = t2.id WHERE t1.season = '2015/2016' AND t1.home_team_goal = t1.away_team_goal GROUP BY t2.name ORDER BY COUNT(t1.id) DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T2.name FROM `Match` AS T1 INNER JOIN League AS T2 ON T1.league_id = T2.id WHERE T1.home_team_goal = T1.away_team_goal AND STRFTIME('%Y', T1.date) = '2016' GROUP BY T2.id, T2.name ORDER BY COUNT(T1.id) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| name |
|---|
| France Ligue 1 |

Predicted (first 1 of 1 rows):

| name |
|---|
| Italy Serie A |

## 1032 / european_football_2 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every league tied for the maximum match count, while the prediction orders by count and LIMITs to one league, dropping the other tied leagues.

Question:

```text
Give the name of the league with the highest matches of all time and how many matches were played in the said league.
```

Evidence:

```text
 league with highest matches of all time refers to MAX(COUNT(league_id));
```

Gold SQL:

```sql
SELECT l.name, COUNT(m.id) AS match_count FROM League AS l JOIN Match AS m ON l.id = m.league_id GROUP BY l.id, l.name HAVING COUNT(m.id) = (SELECT MAX(match_count) FROM (SELECT COUNT(id) AS match_count FROM Match GROUP BY league_id ) )
```

Predicted SQL:

```sql
SELECT T1.name, COUNT(T2.id) AS c1 FROM League AS T1 INNER JOIN `Match` AS T2 ON T1.id = T2.league_id GROUP BY T1.id, T1.name ORDER BY c1 DESC LIMIT 1
```

Result diff:

Gold 3 rows, predicted 1 rows. Within the previews: 2 rows only in gold, 0 only in predicted.

Gold (first 3 of 3 rows):

| name | match_count |
|---|---|
| England Premier League | 3040 |
| France Ligue 1 | 3040 |
| Spain LIGA BBVA | 3040 |

Predicted (first 1 of 1 rows):

| name | c1 |
|---|---|
| England Premier League | 3040 |

## 1122 / european_football_2 / simple

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The evidence defines strongest by MAX(overall_rating), but the prediction orders by T2.strength instead. It therefore reads the wrong attribute to identify the strongest player.

Question:

```text
State the name of the most strongest player.
```

Evidence:

```text
strongest players refers to player has MAX(overall_rating)
```

Gold SQL:

```sql
SELECT DISTINCT t1.player_name FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id WHERE t2.overall_rating = (SELECT MAX(overall_rating) FROM Player_Attributes)
```

Predicted SQL:

```sql
SELECT T1.player_name FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id ORDER BY T2.strength DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| player_name |
|---|
| Lionel Messi |

Predicted (first 1 of 1 rows):

| player_name |
|---|
| Christopher Samba |

## 1124 / european_football_2 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query filters on `Player_Attributes.attacking_work_rate`, matching the evidence, while the prediction instead uses `defensive_work_rate`.

Question:

```text
Who are the players that tend to be attacking when their mates were doing attack moves? List down their name.
```

Evidence:

```text
tend to be attacking when their mates were doing attack moves refers to attacking_work_rate = 'high';
```

Gold SQL:

```sql
SELECT DISTINCT t1.player_name FROM Player AS t1 INNER JOIN Player_Attributes AS t2 ON t1.player_api_id = t2.player_api_id WHERE t2.attacking_work_rate = 'high'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.player_name FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T2.defensive_work_rate = 'low'
```

Result diff:

Gold 3339 rows, predicted 1608 rows. Within the previews: 3 rows only in gold, 3 only in predicted.

Gold (first 5 of 3339 rows):

| player_name |
|---|
| Aaron Cresswell |
| Aaron Lennon |
| Aaron Meijers |
| Aaron Niguez |
| Aaron Ramsey |

Predicted (first 5 of 1608 rows):

| player_name |
|---|
| Aaron Mooy |
| Aaron Niguez |
| Aaron Ramsey |
| Abdelkader Ghezzal |
| Abdoulwahid Sissoko |

## 1156 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query selects patients with RVVT = '+', while the prediction also includes patients whose KCT or LAC equals '+'. This broadens the filter and adds rows.

Question:

```text
State the ID and age of patient with positive degree of coagulation.
```

Evidence:

```text
age refers to SUBTRACT(year(current_timestamp), year(Birthday)); positive degree of coagulation refers to RVVT = '+';
```

Gold SQL:

```sql
SELECT DISTINCT T1.ID, STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T1.Birthday) FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T2.RVVT = '+'
```

Predicted SQL:

```sql
SELECT DISTINCT T1.ID, CAST((JULIANDAY('now') - JULIANDAY(T1.Birthday)) / 365.25 AS INTEGER) AS c1 FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T2.KCT = '+' OR T2.RVVT = '+' OR T2.LAC = '+'
```

Result diff:

Gold 7 rows, predicted 8 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 5 of 7 rows):

| ID | STRFTIME('%Y', CURRENT_TIMESTAMP) - STR… |
|---|---|
| 163109 | 76 |
| 174116 | 53 |
| 355009 | 42 |
| 1567380 | 67 |
| 2803470 | 41 |

Predicted (first 5 of 8 rows):

| ID | c1 |
|---|---|
| 163109 | 76 |
| 174116 | 53 |
| 355009 | 42 |
| 821298 | 59 |
| 1567380 | 67 |

## 1175 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction uses the examination record’s date and diagnosis, which better match the question’s examination date and doctor’s diagnosis. The gold query instead takes the date from Laboratory and the diagnosis from Patient, so it appears to return different information than requested.

Question:

```text
How old was the patient who had the highest hemoglobin count at the time of the examination, and what is the doctor's diagnosis?
```

Evidence:

```text
How old the patient refers to SUBTRACT(year("Examination Date"), year(Birthday)); the highest hemoglobin count refers to MAX(HGB)
```

Gold SQL:

```sql
SELECT STRFTIME('%Y', T2.Date) - STRFTIME('%Y', T1.Birthday), T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID ORDER BY T2.HGB DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT CAST(STRFTIME('%Y', T3.`Examination Date`) AS INTEGER) - CAST(STRFTIME('%Y', T2.Birthday) AS INTEGER) - (STRFTIME('%m-%d', T3.`Examination Date`) < STRFTIME('%m-%d', T2.Birthday)) AS c1, T3.Diagnosis FROM Laboratory AS T1 INNER JOIN Patient AS T2 ON T1.ID = T2.ID INNER JOIN Examination AS T3 ON T2.ID = T3.ID ORDER BY T1.HGB DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| STRFTIME('%Y', T2.Date) - STRFTIME('%Y'… | Diagnosis |
|---|---|
| 28 | SLE |

Predicted (first 1 of 1 rows):

| c1 | Diagnosis |
|---|---|
| 23 | SjS |

## 1179 / thrombosis_prediction / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query identifies the patient using `Patient.Diagnosis` and `Patient.Description`; the prediction instead reads `Diagnosis` and the 1994 date from `Examination`, so it does not select the patient described in the question.

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
SELECT "aCL IgM" FROM Examination WHERE ID IN (SELECT ID FROM Patient WHERE Diagnosis = 'SLE' AND Description = '1994-02-19') AND "Examination Date" = '1993-11-12'
```

Predicted SQL:

```sql
SELECT DISTINCT T2.`aCL IgG`, T2.`aCL IgM`, T2.`aCL IgA` FROM Examination AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID WHERE T1.Diagnosis = 'SLE' AND T1.`Examination Date` = '1994-02-19' AND T2.`Examination Date` = '1993-11-12'
```

Result diff:

Gold 1 rows, predicted 0 rows. Within the previews: 1 rows only in gold, 0 only in predicted.

Gold (first 1 of 1 rows):

| aCL IgM |
|---|
| 4.1 |

Predicted (first 0 of 0 rows):

| aCL IgG | aCL IgM | aCL IgA |
|---|---|---|

## 1187 / thrombosis_prediction / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query filters `Laboratory.Date`, while the prediction filters `Examination.`Examination Date` instead. That different date source changes which IDs qualify.

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
SELECT DISTINCT T1.ID FROM Examination AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.`Examination Date` BETWEEN '1987-07-06' AND '1996-01-31' AND T2.GPT > 30 AND T2.ALB < 4
```

Result diff:

Gold 63 rows, predicted 2 rows. Within the previews: 5 rows only in gold, 2 only in predicted.

Gold (first 5 of 63 rows):

| ID |
|---|
| 27654 |
| 71417 |
| 912147 |
| 944797 |
| 1078741 |

Predicted (first 2 of 2 rows):

| ID |
|---|
| 460574 |
| 1043570 |

## 1189 / thrombosis_prediction / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The subquery in the prediction calculates the average over all Examination rows, while the gold query averages only rows with Thrombosis = 2 and ANA Pattern = 'S'. This changes the threshold used to select patients.

Question:

```text
What number of patients with a degree of thrombosis level 2 and ANA pattern of only S, have a level of anti-Cardiolip in antibody (IgM) 20% higher than average?
```

Evidence:

```text
thrombosis level 2 refers to Thrombosis = 2; ANA pattern of only S refers to ANA = 'S'; average anti-Cardiolip in antibody (IgM) refers to AVG("aCL IgM"); calculation = MULTIPLY(AVG + AVG, 0.2)
```

Gold SQL:

```sql
SELECT COUNT(*) FROM Examination WHERE Thrombosis = 2 AND "ANA Pattern" = 'S' AND "aCL IgM" > (SELECT AVG("aCL IgM") * 1.2 FROM Examination WHERE Thrombosis = 2 AND "ANA Pattern" = 'S')
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Examination AS T1 WHERE T1.Thrombosis = 2 AND T1.`ANA Pattern` = 'S' AND T1.`aCL IgM` > (SELECT AVG(T2.`aCL IgM`) * 1.2 FROM Examination AS T2)
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(*) |
|---|
| 3 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 0 |

## 1232 / thrombosis_prediction / challenging

Label: `date_handling` (classifier, gpt-6-luna): The prediction adjusts the year difference based on whether the birthday has occurred yet this year, while the gold query simply subtracts the birth year from the current year. This produces different ages for some patients.

Question:

```text
Provide ID, sex and age of patients with a lab result having blood glucose (GLU) not within normal range but with total cholesterol(T-CHO) within normal range.
```

Evidence:

```text
age = SUBTRACT(year(current_timestamp), year(Birthday)); blood glucose (GLU) not within normal range refers to GLU > = 180; total cholesterol(T-CHO) within normal range refers to "T-CHO" < 250;
```

Gold SQL:

```sql
SELECT DISTINCT T1.ID, T1.SEX , STRFTIME('%Y', CURRENT_TIMESTAMP) - STRFTIME('%Y', T1.Birthday) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.GLU >= 180 AND T2."T-CHO" < 250
```

Predicted SQL:

```sql
SELECT DISTINCT T1.ID, T1.SEX, CAST(STRFTIME('%Y', 'now') AS INTEGER) - CAST(STRFTIME('%Y', T1.Birthday) AS INTEGER) - (STRFTIME('%m-%d', 'now') < STRFTIME('%m-%d', T1.Birthday)) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T2.GLU >= 180 AND T2.`T-CHO` < 250
```

Result diff:

Gold 13 rows, predicted 13 rows. Within the previews: 2 rows only in gold, 2 only in predicted.

Gold (first 5 of 13 rows):

| ID | SEX | STRFTIME('%Y', CURRENT_TIMESTAMP) - STR… |
|---|---|---|
| 57266 | M | 103 |
| 2371753 | F | 94 |
| 3354706 | F | 90 |
| 4432946 | M | 66 |
| 4466420 | F | 96 |

Predicted (first 5 of 13 rows):

| ID | SEX | CAST(STRFTIME('%Y', 'now') AS INTEGER) … |
|---|---|---|
| 57266 | M | 103 |
| 2371753 | F | 93 |
| 3354706 | F | 89 |
| 4432946 | M | 66 |
| 4466420 | F | 96 |

## 1265 / thrombosis_prediction / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query matches RNP values `'negative'` or `'0'`, while the prediction matches `'-'` or `'+' \|\| '-'` (evaluating to `'+-'`). The differing literals produce different patient counts.

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
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE (T2.RNP = 'negative' OR T2.RNP = '0') AND T1.Admission = '+'
```

Predicted SQL:

```sql
SELECT COUNT(DISTINCT T1.ID) FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID WHERE T1.Admission = '+' AND T2.RNP IN ('-', '+' || '-')
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 35 |

Predicted (first 1 of 1 rows):

| COUNT(DISTINCT T1.ID) |
|---|
| 0 |

## 1376 / student_club / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every event tied for the maximum spend-to-budget ratio, while the prediction uses `ORDER BY ... LIMIT 1` and returns only one event.

Question:

```text
Among all the closed events, which event has the highest spend-to-budget ratio?
```

Evidence:

```text
closed events refers to event_name where status = 'Closed'; highest spend-to budget ratio refers to MAX(DIVIDE(spent, amount))
```

Gold SQL:

```sql
SELECT e.event_name FROM event AS e JOIN budget AS b ON e.event_id = b.link_to_event WHERE e.status = 'Closed' GROUP BY e.event_id, e.event_name HAVING SUM(b.amount) > 0 AND SUM(b.spent) / SUM(b.amount) = ( SELECT MAX(ratio) FROM ( SELECT SUM(b2.spent) * 1.0 / SUM(b2.amount) AS ratio FROM budget AS b2 JOIN event AS e2 ON b2.link_to_event = e2.event_id WHERE e2.status = 'Closed' GROUP BY e2.event_id HAVING SUM(b2.amount) > 0 ) )
```

Predicted SQL:

```sql
SELECT T1.event_name FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event WHERE T1.status = 'Closed' GROUP BY T1.event_id, T1.event_name ORDER BY CAST(SUM(T2.spent) AS REAL) / NULLIF(SUM(T2.amount), 0) DESC LIMIT 1
```

Result diff:

Gold 3 rows, predicted 1 rows. Within the previews: 2 rows only in gold, 0 only in predicted.

Gold (first 3 of 3 rows):

| event_name |
|---|
| Officers meeting - November |
| Officers meeting - September |
| Officers meeting - October |

Predicted (first 1 of 1 rows):

| event_name |
|---|
| Officers meeting - November |

## 1473 / debit_card_specializing / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query sums each customer’s 2013 consumption, averages those customer totals, then divides by 12. The prediction instead averages individual consumption rows, with no per-customer grouping or division by 12.

Question:

```text
What was the average monthly consumption of customers in SME for the year 2013?
```

Evidence:

```text
Average Monthly consumption = AVG(SUM(Consumption) by CustomerID) / 12; Year 2013 can be presented as Between 201301 And 201312; The first 4 strings of the Date values in the yearmonth table can represent year.
```

Gold SQL:

```sql
SELECT AVG(TotalConsumption) / 12 FROM (SELECT SUM(T2.Consumption) AS TotalConsumption FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE SUBSTR(T2.Date, 1, 4) = '2013' AND T1.Segment = 'SME' GROUP BY T1.CustomerID)
```

Predicted SQL:

```sql
SELECT AVG(T1.Consumption) FROM yearmonth AS T1 INNER JOIN customers AS T2 ON T1.CustomerID = T2.CustomerID WHERE T2.Segment = 'SME' AND T1.Date LIKE '2013%'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(TotalConsumption) / 12 |
|---|
| 3682.6443523465327 |

Predicted (first 1 of 1 rows):

| AVG(T1.Consumption) |
|---|
| 5519.475171445073 |

## 1480 / debit_card_specializing / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query groups consumption by the two-character month, while the prediction groups by the full YYYYMM date. This changes the aggregation to a specific year-month rather than the peak month.

Question:

```text
What was the gas consumption peak month for SME customers in 2013?
```

Evidence:

```text
Year 2013 can be presented as Between 201301 And 201312; The first 4 strings of the Date values in the yearmonth table can represent year; The 5th and 6th string of the date can refer to month.
```

Gold SQL:

```sql
SELECT SUBSTR(T2.Date, 5, 2) FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE SUBSTR(T2.Date, 1, 4) = '2013' AND T1.Segment = 'SME' GROUP BY SUBSTR(T2.Date, 5, 2) ORDER BY SUM(T2.Consumption) DESC LIMIT 1
```

Predicted SQL:

```sql
SELECT T1.Date FROM yearmonth AS T1 INNER JOIN customers AS T2 ON T1.CustomerID = T2.CustomerID WHERE T2.Segment = 'SME' AND SUBSTR(T1.Date, 1, 4) = '2013' GROUP BY T1.Date ORDER BY SUM(T1.Consumption) DESC LIMIT 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUBSTR(T2.Date, 5, 2) |
|---|
| 04 |

Predicted (first 1 of 1 rows):

| Date |
|---|
| 201304 |

## 1481 / debit_card_specializing / challenging

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query sums each customer’s 2013 consumption and selects the minimum annual total per segment, while the prediction averages monthly consumption per customer and selects the minimum of those averages. That changes the aggregation used to identify each segment’s lowest-consuming customer.

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
WITH customer_consumption AS (SELECT c.Segment, c.CustomerID, SUM(ym.Consumption) AS TotalConsumption, COUNT(DISTINCT ym.CustomerID) AS CustomerCount FROM customers AS c JOIN yearmonth AS ym ON c.CustomerID = ym.CustomerID WHERE ym.Date BETWEEN '201301' AND '201312' AND c.Currency = 'CZK' GROUP BY c.Segment, c.CustomerID), customer_average_consumption AS (SELECT Segment, TotalConsumption, CAST(TotalConsumption AS REAL) / CustomerCount AS AnnualAverageConsumption FROM customer_consumption), segment_min_consumption AS (SELECT Segment, MIN(TotalConsumption) LeastConsumptionCustomer FROM customer_average_consumption GROUP BY Segment), segment_min_consumption_avg AS (SELECT T1.Segment, T2.AnnualAverageConsumption FROM segment_min_consumption T1 JOIN customer_average_consumption T2 ON T1.Segment = T2.Segment AND T1.LeastConsumptionCustomer = T2.TotalConsumption) SELECT SUM(IIF(Segment = 'SME', AnnualAverageConsumption, 0)) - SUM(IIF(Segment = 'LAM', AnnualAverageConsumption, 0)), SUM(IIF(Segment = 'LAM', AnnualAverageConsumption, 0)) - SUM(IIF(Segment = 'KAM', AnnualAverageConsumption, 0)), SUM(IIF(Segment = 'KAM', AnnualAverageConsumption, 0)) - SUM(IIF(Segment = 'SME', AnnualAverageConsumption, 0)) FROM segment_min_consumption_avg
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT T1.CustomerID, T1.Segment, AVG(T2.Consumption) AS c1 FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Currency = 'CZK' AND SUBSTR(T2.Date, 1, 4) = '2013' AND T2.Consumption IS NOT NULL GROUP BY T1.CustomerID, T1.Segment), cte2 AS (SELECT T1.Segment, MIN(T1.c1) AS c1 FROM cte1 AS T1 GROUP BY T1.Segment) SELECT T1.c1 - T2.c1, T2.c1 - T3.c1, T3.c1 - T1.c1 FROM cte2 AS T1 CROSS JOIN cte2 AS T2 CROSS JOIN cte2 AS T3 WHERE T1.Segment = 'SME' AND T2.Segment = 'LAM' AND T3.Segment = 'KAM'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| SUM(IIF(Segment = 'SME', AnnualAverageC… | SUM(IIF(Segment = 'LAM', AnnualAverageC… | SUM(IIF(Segment = 'KAM', AnnualAverageC… |
|---|---|---|
| -14009.339999999998 | 6046.619999999999 | 7962.719999999999 |

Predicted (first 1 of 1 rows):

| T1.c1 - T2.c1 | T2.c1 - T3.c1 | T3.c1 - T1.c1 |
|---|---|---|
| -7004.669999999999 | 1401.83 | 5602.839999999999 |

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

## 1533 / debit_card_specializing / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters on `Price / Amount > 29.00`, matching the stated price-per-unit definition, while the prediction uses `Price > 29.00`. The prediction therefore selects a different set of customers.

Question:

```text
For all the people who paid more than 29.00 per unit of product id No.5. Give their consumption status in the August of 2012.
```

Evidence:

```text
August of 2012 refers to the Date value = '201208' ; Price per unit of product = Price / Amount;
```

Gold SQL:

```sql
SELECT T2.Consumption FROM transactions_1k AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Price / T1.Amount > 29.00 AND T1.ProductID = 5 AND T2.Date = '201208'
```

Predicted SQL:

```sql
WITH cte1 AS (SELECT DISTINCT T1.CustomerID FROM transactions_1k AS T1 WHERE T1.Price > 29.00 AND T1.ProductID = 5) SELECT T1.Consumption FROM yearmonth AS T1 INNER JOIN cte1 AS T2 ON T1.CustomerID = T2.CustomerID WHERE T1.Date = '201208'
```

Result diff:

Gold 10 rows, predicted 153 rows. Within the previews: 3 rows only in gold, 4 only in predicted.

Gold (first 5 of 10 rows):

| Consumption |
|---|
| 1903.2 |
| 88265.39 |
| 1129.2 |
| 126157.7 |
| 126157.7 |

Predicted (first 5 of 153 rows):

| Consumption |
|---|
| 1425.56 |
| 106067.39 |
| 138251.61 |
| 30648.57 |
| 88265.39 |
