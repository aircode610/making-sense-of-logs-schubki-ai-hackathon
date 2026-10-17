---
title: SELECT
sidebar_position: 1
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

The `SELECT` clause specifies the list of columns that will be returned by the query. While it appears first in the clause, _logically_ the expressions here are executed only at the end. The `SELECT` clause can contain arbitrary expressions that transform the output, as well as aggregates and window functions.

## Examples

Select all columns from the table called `tbl`:

```sql
SELECT * FROM tbl;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```


Perform arithmetic on the columns in a table, and provide an alias:

```sql
SELECT col1 + col2 AS res, sqrt(col1) AS root FROM tbl;
-- result:
res	root
3	1
9	2
25	3
```


Use prefix aliases:

```sql
SELECT
    res: col1 + col2,
    root: sqrt(col1)
FROM tbl;
-- result:
res	root
3	1
9	2
25	3
```


Select all unique cities from the `addresses` table:

```sql
query ? rowsort
SELECT DISTINCT city FROM addresses;
-- result:
city
Lakeside
Linden
Mallard
```


Return the total number of rows in the `addresses` table:

```sql
SELECT count(*) FROM addresses;
-- result:
count
6
```


Select all columns except the city column from the `addresses` table:

```sql
SELECT * EXCLUDE (city) FROM addresses;
-- result:
address	street_name	income	zip	country	population	number1	number2
123 Spruce Blvd	Spruce Blvd	50000	11111	NL	100	1	10
111 Birch Ln	Birch Ln	60000	11111	NL	100	2	20
111 Birch Ln	Birch Ln	70000	11111	US	50	3	30
111 Birch Ln	Birch Ln	80000	11111-0001	US	50	4	40
5 Pond Road	Pond Road	90000	22222	UK	25	5	50
9 Lake View	Lake View	40000	33333	UK	25	6	60
```


Select all columns from the `addresses` table, but replace `city` with `lower(city)`:

```sql
SELECT * REPLACE (lower(city) AS city) FROM addresses;
-- result:
address	city	street_name	income	zip	country	population	number1	number2
123 Spruce Blvd	linden	Spruce Blvd	50000	11111	NL	100	1	10
111 Birch Ln	linden	Birch Ln	60000	11111	NL	100	2	20
111 Birch Ln	lakeside	Birch Ln	70000	11111	US	50	3	30
111 Birch Ln	lakeside	Birch Ln	80000	11111-0001	US	50	4	40
5 Pond Road	mallard	Pond Road	90000	22222	UK	25	5	50
9 Lake View	mallard	Lake View	40000	33333	UK	25	6	60
```


Select all columns matching the given regular expression from the table:

```sql
query ?? rowsort
SELECT COLUMNS('number[0-9]+') FROM addresses;
-- result:
number1	number2
1	10
2	20
3	30
4	40
5	50
6	60
```


Compute a function on all given columns of a table:

```sql
SELECT min(COLUMNS(*)) FROM addresses;
-- result:
address	city	street_name	income	zip	country	population	number1	number2
111 Birch Ln	Lakeside	Birch Ln	40000	11111	NL	25	1	10
```


To select columns with spaces or special characters, use double quotes (`"`):

```sql
SELECT "Some Column Name" FROM tbl;
-- result:
Some Column Name
alpha
beta
gamma
```


## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

## `SELECT` List

The `SELECT` clause contains a list of expressions that specify the result of a query. The select list can refer to any columns in the `FROM` clause, and combine them using expressions. As the output of a SQL query is a table – every expression in the `SELECT` clause also has a name. The expressions can be explicitly named using the `AS` clause (e.g., `expr AS name`). If a name is not provided by the user the expressions are named automatically by the system.

<DocCallout type="tip">
Column names are case-insensitive. See the [Rules for Case Sensitivity](../../../compatibility/keywords_and_identifiers.md#rules-for-case-sensitivity) for more details.
</DocCallout>

### Star Expressions

Select all columns from the table called `tbl`:

```sql
SELECT *
FROM tbl;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```


Select all columns matching the given regular expression from the table:

```sql
query ?? rowsort
SELECT COLUMNS('number[0-9]+')
FROM addresses;
-- result:
number1	number2
1	10
2	20
3	30
4	40
5	50
6	60
```


The [star expression](../../expressions/star/index.md) is a special expression that expands to _multiple expressions_ based on the contents of the `FROM` clause. In the simplest case, `*` expands to **all** expressions in the `FROM` clause. Columns can also be selected using regular expressions or lambda functions. See the [star expression page](../../expressions/star/index.md) for more details.

### `DISTINCT` Clause

Select all unique cities from the addresses table:

```sql
query ? rowsort
SELECT DISTINCT city
FROM addresses;
-- result:
city
Lakeside
Linden
Mallard
```


The `DISTINCT` clause can be used to return **only** the unique rows in the result – so that any duplicate rows are filtered out.

<DocCallout type="tip">
Queries starting with `SELECT DISTINCT` run deduplication, which is an expensive operation. Therefore, only use `DISTINCT` if necessary.
</DocCallout>

### `DISTINCT ON` Clause

Select only the highest population city for each country:

```sql
SELECT DISTINCT ON(country) city, population
FROM cities
ORDER BY population DESC;
-- result:
city	population
New York	8804190
London	8799800
Amsterdam	921402
```


The `DISTINCT ON` clause returns only one row per unique value in the set of expressions as defined in the `ON` clause. If an `ORDER BY` clause is present, the row that is returned is the first row that is encountered as per the `ORDER BY` criteria. If an `ORDER BY` clause is not present, the first row that is encountered is not defined and can be any row in the table.

<DocCallout type="tip">
When querying large datasets, using `DISTINCT` on all columns can be expensive. Therefore, consider using `DISTINCT ON` on a column (or a set of columns) which guarantees a sufficient degree of uniqueness for your results. For example, using `DISTINCT ON` on the key column(s) of a table guarantees full uniqueness.
</DocCallout>

### Aggregates

Return the total number of rows in the addresses table:

```sql
SELECT count(*)
FROM addresses;
-- result:
count
6
```


Return the total number of rows in the addresses table grouped by city:

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


[Aggregate functions](../../functions/aggregates/index.md) are special functions that _combine_ multiple rows into a single value. When aggregate functions are present in the `SELECT` clause, the query is turned into an aggregate query. In an aggregate query, **all** expressions must either be part of an aggregate function, or part of a group (as specified by the [`GROUP BY clause`](../../query_syntax/groupby/index.md)).

### Window Functions

Generate a `row_number` column containing incremental identifiers for each row:

```sql
SELECT row_number() OVER ()
FROM sales;
-- result:
row_number
1
2
```


Compute the difference between the current amount, and the previous amount, by order of time:

```sql
SELECT amount - lag(amount) OVER (ORDER BY time)
FROM sales;
-- result:
?column?
NULL
100
```


[Window functions](../../functions/window_functions/index.md) are special functions that allow the computation of values relative to _other rows_ in a result. Window functions are marked by the `OVER` clause which contains the _window specification_. The window specification defines the frame or context in which the window function is computed. See the [window functions page](../../functions/window_functions/index.md) for more information.

### `unnest` Function

Unnest an array by one level:

```sql
SELECT unnest([1, 2, 3]);
-- result:
unnest
1
2
3
```


Unnest a struct by one level:

```sql
SELECT unnest({'a': 42, 'b': 84});
-- result:
a	b
42	84
```


The [`unnest`](../../query_syntax/unnest.md) function is a special function that can be used together with [arrays](../../data_types/array.md), [lists](../../data_types/list.md), or [structs](../../data_types/struct.md). The unnest function strips one level of nesting from the type. For example, `INTEGER[]` is transformed into `INTEGER`. `STRUCT(a INTEGER, b INTEGER)` is transformed into `a INTEGER, b INTEGER`. The unnest function can be used to transform nested types into regular scalar types, which makes them easier to operate on.

