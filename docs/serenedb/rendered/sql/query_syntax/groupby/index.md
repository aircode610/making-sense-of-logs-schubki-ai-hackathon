---
title: GROUP BY
sidebar_position: 4
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `GROUP BY` clause specifies which grouping columns should be used to perform any aggregations in the `SELECT` clause.
If the `GROUP BY` clause is specified, the query is always an aggregate query, even if no aggregations are present in the `SELECT` clause.

When a `GROUP BY` clause is specified, all tuples that have matching data in the grouping columns (i.e., all tuples that belong to the same group) will be combined.
The values of the grouping columns themselves are unchanged, and any other columns can be combined using an [aggregate function](../../functions/aggregates/index.md) (such as `count`, `sum`, `avg`, etc).

## `GROUP BY ALL`

Use `GROUP BY ALL` to `GROUP BY` all columns in the `SELECT` statement that are not wrapped in aggregate functions.
This simplifies the syntax by allowing the columns list to be maintained in a single location, and prevents bugs by keeping the `SELECT` granularity aligned to the `GROUP BY` granularity (e.g., it prevents duplication).
See examples below and the [SQL Extensions](../../../compatibility/sql_extensions.md) page.

## Multiple Dimensions

Normally, the `GROUP BY` clause groups along a single dimension.
Using the [`GROUPING SETS`, `CUBE` or `ROLLUP` clauses](../../query_syntax/grouping_sets/index.md) it is possible to group along multiple dimensions.
See the [`GROUPING SETS`](../../query_syntax/grouping_sets/index.md) page for more information.

## Examples

Count the number of entries in the `addresses` table that belong to each different city:

```sql
query ?? rowsort
SELECT city, count(*)
FROM addresses
GROUP BY city;
-- result:
city	count
Lakeside	2
Linden	2
Mallard	2
```


Compute the average income per city per street_name:

```sql
query ??? rowsort
SELECT city, street_name, avg(income)
FROM addresses
GROUP BY city, street_name;
-- result:
city	street_name	avg
Lakeside	Birch Ln	75000
Linden	Birch Ln	60000
Linden	Spruce Blvd	50000
Mallard	Lake View	40000
Mallard	Pond Road	90000
```


### `GROUP BY ALL` Examples

Group by city and street_name to remove any duplicate values:

```sql
query ?? rowsort
SELECT city, street_name
FROM addresses
GROUP BY ALL;
-- result:
city	street_name
Lakeside	Birch Ln
Linden	Birch Ln
Linden	Spruce Blvd
Mallard	Lake View
Mallard	Pond Road
```


Compute the average income per city per street_name. Since income is wrapped in an aggregate function, do not include it in the `GROUP BY`:

```sql
query ??? rowsort
SELECT city, street_name, avg(income)
FROM addresses
GROUP BY ALL;
-- result:
city	street_name	avg
Lakeside	Birch Ln	75000
Linden	Birch Ln	60000
Linden	Spruce Blvd	50000
Mallard	Lake View	40000
Mallard	Pond Road	90000
```


## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

