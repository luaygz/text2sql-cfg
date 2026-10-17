# Failures: best on bird_arcwise / test

22 of 149 questions failed. Evidence on, git `70b12ce88825feb7263dfaf0a75ccf74d10bb829`, complete: 149 questions.

## 24 / california_schools / moderate

Label: `wrong_filter_value` (classifier, gpt-6-luna): The prediction omits the gold query’s `NumGE1500 > 0` condition and `rtype = 'S'` filter, so it includes schools without qualifying test takers and other record types. It also returns `NumGE1500` as an extra column, but the missing filters are the first difference to fix.

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
SELECT T1.`School Name`, T2.NumGE1500 FROM frpm AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE CAST(T1.`Free Meal Count (K-12)` AS REAL) / T1.`Enrollment (K-12)` > 0.1
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

| School Name | NumGE1500 |
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

## 219 / toxicology / challenging

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query filters to triple bonds (`bond_type = '#'`) and measures which molecules are carcinogenic; the prediction instead filters to carcinogenic molecules (`label = '+'`) and measures which bonds are triple. This reverses the population condition needed for the percentage.

Question:

```text
What is the percentage of molecules in triple type bonds are carcinogenic?
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

## 402 / card_games / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction follows the question’s meaning of “do not have a text box” as `isTextless = 0`. The gold instead uses `isTextless = 1`, contradicting the supplied evidence and the question wording.

Question:

```text
What is the percentage of cards which are Story Spotlight cards and do not have a text box?
```

Evidence:

```text
Story Spotlight cards and do not have a text box refers to isStorylight = 1 and isTextless = 0; Percentage = DIVIDE(SUM(count(id) where isStorylight = 1 AND isTextless = 0 ), SUM(count(id))) * 100
```

Gold SQL:

```sql
SELECT CAST(SUM(CASE WHEN isTextless = 1 AND isStorySpotlight = 1 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(id) FROM cards
```

Predicted SQL:

```sql
SELECT CAST(SUM(CASE WHEN T1.isStorySpotlight = 1 AND T1.isTextless = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| CAST(SUM(CASE WHEN isTextless = 1 AND i… |
|---|
| 0.0 |

Predicted (first 1 of 1 rows):

| CAST(SUM(CASE WHEN T1.isStorySpotlight … |
|---|
| 0.18302770053852382 |

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

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query selects `cards.name`, while the prediction selects `foreign_data.name` (`T1.name`), yielding the Korean translation “불모지” instead of the card name “Wastes.”

Question:

```text
Find and list the names of cards which doesn't have Japanese translation but have Korean translation.
```

Evidence:

```text
doesn't have Japanese translation refers to language not like '%Japanese%'; have Korean translation refers to language = 'Korean'
```

Gold SQL:

```sql
SELECT name FROM cards WHERE uuid IN (SELECT DISTINCT uuid FROM foreign_data WHERE language LIKE 'Korean' EXCEPT SELECT DISTINCT uuid FROM foreign_data WHERE language LIKE '%Japanese%')
```

Predicted SQL:

```sql
SELECT DISTINCT T1.name FROM foreign_data AS T1 INNER JOIN cards AS T2 ON T1.uuid = T2.uuid LEFT JOIN (SELECT DISTINCT T4.uuid FROM foreign_data AS T4 WHERE T4.language LIKE '%Japanese%') AS T3 ON T2.uuid = T3.uuid WHERE T1.language = 'Korean' AND T3.uuid IS NULL
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| name |
|---|
| Wastes |

Predicted (first 1 of 1 rows):

| name |
|---|
| 불모지 |

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

## 791 / superhero / simple

Label: `wrong_filter_value` (classifier, gpt-6-luna): The gold query averages only rows where `height_cm > 0`, while the prediction includes all rows in the count and sum. This missing filter changes the average.

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
SELECT CAST(SUM(T1.height_cm) AS REAL) / COUNT(*) FROM superhero AS T1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| AVG(height_cm) |
|---|
| 345.03538175046555 |

Predicted (first 1 of 1 rows):

| CAST(SUM(T1.height_cm) AS REAL) / COUNT… |
|---|
| 247.04533333333333 |

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

## 928 / formula_1 / moderate

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold query identifies first place with `results.position = 1`, while the prediction uses `results.rank = 1`, which selects a different driver.

Question:

```text
Which driver ranked the first in the Canadian Grand Prix in 2007? Please give his forename, surname, and reference name.
```

Evidence:

```text
reference name refers to driverRef; Canadian Grand Prix refers to races.name = 'Canadian Grand Prix';
```

Gold SQL:

```sql
SELECT d.forename, d.surname, d.driverRef FROM drivers AS d JOIN results AS r ON d.driverId = r.driverId JOIN races AS ra ON r.raceId = ra.raceId WHERE ra.name = 'Canadian Grand Prix' AND ra.year = 2007 AND r.position = 1
```

Predicted SQL:

```sql
SELECT T1.forename, T1.surname, T1.driverRef FROM drivers AS T1 INNER JOIN results AS T2 ON T1.driverId = T2.driverId INNER JOIN races AS T3 ON T2.raceId = T3.raceId WHERE T3.name = 'Canadian Grand Prix' AND T3.year = 2007 AND T2.rank = 1
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| forename | surname | driverRef |
|---|---|---|
| Lewis | Hamilton | hamilton |

Predicted (first 1 of 1 rows):

| forename | surname | driverRef |
|---|---|---|
| Fernando | Alonso | alonso |

## 955 / formula_1 / challenging

Label: `gold_label_suspect` (classifier, gpt-6-luna): The prediction filters finished champions with `T2.time IS NOT NULL`, matching the evidence that a finished game means time is not null. The gold instead uses `res.milliseconds IS NOT NULL`, so it may include or exclude a different set of rows.

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
SELECT T1.year, AVG(T2.milliseconds) / 1000.0 FROM races AS T1 INNER JOIN results AS T2 ON T1.raceId = T2.raceId WHERE T1.year < 1975 AND T2.position = 1 AND T2.time IS NOT NULL GROUP BY T1.year
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

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every away team tied for the maximum number of wins, while the prediction uses `ORDER BY COUNT(*) DESC LIMIT 1` and returns only one team. The prediction therefore drops Celtic, which is tied with Rangers in the gold result.

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
SELECT T1.team_long_name FROM Team AS T1 INNER JOIN `Match` AS T2 ON T1.team_api_id = T2.away_team_api_id INNER JOIN League AS T3 ON T2.league_id = T3.id WHERE T3.name = 'Scotland Premier League' AND T2.season = '2009/2010' AND T2.away_team_goal > T2.home_team_goal GROUP BY T1.team_api_id, T1.team_long_name ORDER BY COUNT(*) DESC LIMIT 1
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

## 1032 / european_football_2 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query returns every league tied for the maximum match count, while the prediction uses `ORDER BY ... LIMIT 1` and returns only one league.

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
SELECT T1.name, COUNT(T2.league_id) AS c1 FROM League AS T1 INNER JOIN `Match` AS T2 ON T1.id = T2.league_id GROUP BY T1.id, T1.name ORDER BY c1 DESC LIMIT 1
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

## 1068 / european_football_2 / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold uses AVG(overall_rating), while the prediction divides SUM by COUNT using SQLite integer division, producing 68 instead of 68.945. The date filters and join otherwise match.

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
SELECT AVG(t2.overall_rating) AS avg_rating
FROM `Player` AS t1
JOIN `Player_Attributes` AS t2 ON t1.player_api_id = t2.player_api_id
WHERE t1.height > 170
  AND strftime('%Y', t2.`date`) BETWEEN '2010' AND '2015';
```

Predicted SQL:

```sql
SELECT SUM(T2.overall_rating) / COUNT(T2.id) FROM Player AS T1 INNER JOIN Player_Attributes AS T2 ON T1.player_api_id = T2.player_api_id WHERE T1.height > 170 AND STRFTIME('%Y', T2.date) >= '2010' AND STRFTIME('%Y', T2.date) <= '2015'
```

Result diff:

Gold 1 rows, predicted 1 rows. Within the previews: 1 rows only in gold, 1 only in predicted.

Gold (first 1 of 1 rows):

| avg_rating |
|---|
| 68.94520387296329 |

Predicted (first 1 of 1 rows):

| SUM(T2.overall_rating) / COUNT(T2.id) |
|---|
| 68 |

## 1175 / thrombosis_prediction / moderate

Label: `gold_label_suspect` (classifier, gpt-6-luna): The question and evidence specify age at the examination, but the gold query calculates age from `Laboratory.Date` and takes diagnosis from `Patient`. The prediction uses `Examination Date` and `Examination.Diagnosis`, which better matches the question.

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

Label: `wrong_table_or_column` (classifier, gpt-6-luna): The gold filters on the column "ANA Pattern", while the prediction filters on `ANA`. This reads a different column and may select different patients.

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
SELECT COUNT(DISTINCT T1.ID) FROM Examination AS T1 WHERE T1.Thrombosis = 2 AND T1.ANA = 'S' AND T1.`aCL IgM` > (SELECT (AVG(T2.`aCL IgM`) + AVG(T2.`aCL IgM`)) * 0.2 FROM Examination AS T2)
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

## 1376 / student_club / moderate

Label: `wrong_aggregation_or_grouping` (classifier, gpt-6-luna): The gold query compares each event’s summed spent-to-summed budget ratio and returns all events tied for the maximum. The prediction ranks individual budget rows by their ratio and limits the result to one event.

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
SELECT T1.event_name FROM event AS T1 INNER JOIN budget AS T2 ON T1.event_id = T2.link_to_event WHERE T1.status = 'Closed' ORDER BY CAST(T2.spent AS REAL) / T2.amount DESC LIMIT 1
```

Result diff:

Gold 3 rows, predicted 1 rows. Within the previews: 3 rows only in gold, 1 only in predicted.

Gold (first 3 of 3 rows):

| event_name |
|---|
| Officers meeting - November |
| Officers meeting - September |
| Officers meeting - October |

Predicted (first 1 of 1 rows):

| event_name |
|---|
| September Speaker |

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
