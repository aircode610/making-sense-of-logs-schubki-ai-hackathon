---
title: WHERE
sidebar_position: 3
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `WHERE` clause specifies any filters to apply to the data. This allows you to select only a subset of the data in which you are interested. Logically the `WHERE` clause is applied immediately after the `FROM` clause.

## Examples

Select all rows where the `id` is equal to 3:

```sql
SELECT *
FROM tbl
WHERE id = 3;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
```


Select all rows that match the given **case-sensitive** `LIKE` expression:

```sql
SELECT *
FROM tbl
WHERE name LIKE '%mark%';
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
```


Select all rows that match the given **case-insensitive** expression formulated with the `ILIKE` operator:

```sql
SELECT *
FROM tbl
WHERE name ILIKE '%mark%';
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
```


Select all rows that match the given composite expression:

```sql
SELECT *
FROM tbl
WHERE id = 3 OR id = 7;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```


## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

