---
title: SAMPLE
sidebar_position: 9
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `SAMPLE` clause allows you to run the query on a sample from the base table. This can significantly speed up processing of queries, at the expense of accuracy in the result. Samples can also be used to quickly see a snapshot of the data when exploring a dataset. The sample clause is applied right after anything in the `FROM` clause (i.e., after any joins, but before the `WHERE` clause or any aggregates). See the [`SAMPLE`](../../samples/index.md) page for more information.

## Examples

Select a sample of 1% of the addresses table using default (system) sampling:

```sql
SELECT *
FROM addresses
USING SAMPLE 1%;
```


Select a sample of 1% of the addresses table using bernoulli sampling:

```sql
SELECT *
FROM addresses
USING SAMPLE 1% (bernoulli);
```


Select a sample of 10 rows from the subquery:

```sql
query ????????? rowsort
SELECT *
FROM (SELECT * FROM addresses)
USING SAMPLE 10 ROWS;
-- result:
address	city	street_name	income	zip	country	population	number1	number2
111 Birch Ln	Lakeside	Birch Ln	70000	11111	US	50	3	30
111 Birch Ln	Lakeside	Birch Ln	80000	11111-0001	US	50	4	40
111 Birch Ln	Linden	Birch Ln	60000	11111	NL	100	2	20
123 Spruce Blvd	Linden	Spruce Blvd	50000	11111	NL	100	1	10
5 Pond Road	Mallard	Pond Road	90000	22222	UK	25	5	50
9 Lake View	Mallard	Lake View	40000	33333	UK	25	6	60
```


## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

