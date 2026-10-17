---
title: LIMIT / OFFSET
sidebar_position: 8
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

`LIMIT` is an output modifier. Logically it is applied at the very end of the query. The `LIMIT` clause restricts the amount of rows fetched. The `OFFSET` clause indicates at which position to start reading the values, i.e., the first `OFFSET` values are ignored.

Note that while `LIMIT` can be used without an `ORDER BY` clause, the results might not be deterministic without the `ORDER BY` clause. This can still be useful, however, for example when you want to inspect a quick snapshot of the data.

## Examples

Select the first 5 rows from the addresses table:

```sql
SELECT *
FROM addresses
LIMIT 5;
-- result:
address	city	street_name	income	zip	country	population	number1	number2
123 Spruce Blvd	Linden	Spruce Blvd	50000	11111	NL	100	1	10
111 Birch Ln	Linden	Birch Ln	60000	11111	NL	100	2	20
111 Birch Ln	Lakeside	Birch Ln	70000	11111	US	50	3	30
111 Birch Ln	Lakeside	Birch Ln	80000	11111-0001	US	50	4	40
5 Pond Road	Mallard	Pond Road	90000	22222	UK	25	5	50
```


Select the 5 rows from the addresses table, starting at position 5 (i.e., ignoring the first 5 rows):

```sql
SELECT *
FROM addresses
LIMIT 5
OFFSET 5;
-- result:
address	city	street_name	income	zip	country	population	number1	number2
9 Lake View	Mallard	Lake View	40000	33333	UK	25	6	60
```


Select the top 5 cities with the highest population:

```sql
query ?? rowsort
SELECT city, count(*) AS population
FROM addresses
GROUP BY city
ORDER BY population DESC
LIMIT 5;
-- result:
city	population
Lakeside	2
Linden	2
Mallard	2
```


Select 10% of the rows from the addresses table:

```sql
SELECT *
FROM addresses
LIMIT 10%;
-- result:
address	city	street_name	income	zip	country	population	number1	number2
Address 0	Linden	Street 0	50000	ZIP0	NL	100	0	0
Address 1	Mallard	Street 1	51000	ZIP1	UK	101	1	10
```


## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

