---
title: FROM / JOIN
sidebar_position: 2
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

The `FROM` clause specifies the _source_ of the data on which the remainder of the query should operate. Logically, the `FROM` clause is where the query starts execution. The `FROM` clause can contain a single table, a combination of multiple tables that are joined together using `JOIN` clauses, or another `SELECT` query inside a subquery node. SereneDB also has an optional `FROM`-first syntax which enables you to also query without a `SELECT` statement.

## Examples

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

Select all columns from the table using the `FROM`-first syntax:

```sql
FROM tbl
SELECT *;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

Select all columns using the `FROM`-first syntax and omitting the `SELECT` clause:

```sql
FROM tbl;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

Select all columns from the table called `tbl` through an alias `tn`:

```sql
SELECT tn.*
FROM tbl tn;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

Use a prefix alias:

```sql
SELECT tn.*
FROM tn: tbl;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

Select all columns from the table `tbl` in the schema `schema_name`:

```sql
SELECT *
FROM schema_name.tbl;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

Select the column `i` from the table function `range`, where the first column of the range function is renamed to `i`:

```sql
SELECT t.i
FROM range(100) AS t(i);
-- result:
i
0
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60
61
62
63
64
65
66
67
68
69
70
71
72
73
74
75
76
77
78
79
80
81
82
83
84
85
86
87
88
89
90
91
92
93
94
95
96
97
98
99
```

Select all columns from the CSV file called `test.csv`:

```sql
SELECT *
FROM 'test.csv';
```

Select all columns from a subquery:

```sql
SELECT *
FROM (SELECT * FROM tbl);
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

Select the entire row of the table as a struct:

```sql
SELECT t
FROM t;
-- result:
t
(1,10)
(2,20)
```

Select the entire row of the subquery as a struct (i.e., a single column):

```sql
SELECT t
FROM (SELECT unnest(generate_series(41, 43)) AS x, 'hello' AS y) t;
-- result:
t
(41,hello)
(42,hello)
(43,hello)
```

Join two tables together:

```sql
query ???? rowsort
SELECT *
FROM tbl
JOIN other_table
  ON tbl.key = other_table.key;
-- result:
key	value	key	description
1	left one	1	right one
2	left two	2	right two
```

Select a 10% sample from a table:

```sql
SELECT *
FROM tbl
TABLESAMPLE 10%;
```

Select a sample of 10 rows from a table:

```sql
query ???????????? rowsort
SELECT *
FROM tbl
TABLESAMPLE 10 ROWS;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

Use the `FROM`-first syntax with `WHERE` clause and aggregation:

```sql
FROM range(100) AS t(i)
SELECT sum(t.i)
WHERE i % 2 = 0;
-- result:
sum
2450
```

### Table Functions

Some functions in SereneDB return entire tables rather than individual values. These functions are accordingly called _table functions_ and can be used with a `FROM` clause like regular table references.
Examples include [`read_csv`](../../../data_import_and_export/csv/overview.md#csv-functions), [`read_parquet`](../../../data_import_and_export/parquet/overview.md#read_parquet-function), [`range`](../../functions/list.md#rangestart-stop-step), [`generate_series`](../../functions/list.md#generate_seriesstart-stop-step), [`repeat`](../../functions/utility.md#repeat_rowvarargs-num_rows), [`unnest`](../../query_syntax/unnest.md), and [`glob`](../../functions/utility.md#globsearch_path) (note that some of the examples here can be used as both scalar and table functions).

For example,

```sql
SELECT *
FROM 'test.csv';
```

is implicitly translated to a call of the `read_csv` table function:

```sql
SELECT *
FROM read_csv('test.csv');
```

All table functions support a `WITH ORDINALITY` suffix, which extends the returned table by an integer column `ordinality` that enumerates the generated rows starting at `1`.

```sql
SELECT *
FROM read_csv('test.csv') WITH ORDINALITY;
```

Note that the same result could be achieved using the [`row_number` window function](../../functions/window_functions/index.md#row_numberorder-by-ordering).
In the presence of [joins](#joins), however, `WITH ORDINALITY` allows enumerating one side of the join instead of the final result set, without having to resort to sub-queries.

## Joins

Joins are a fundamental relational operation used to connect two tables or relations horizontally.
The relations are referred to as the _left_ and _right_ sides of the join
based on how they are written in the join clause.
Each result row has the columns from both relations.

A join uses a rule to match pairs of rows from each relation.
Often this is a predicate, but there are other implied rules that may be specified.

### Outer Joins

Rows that do not have any matches can still be returned if an `OUTER` join is specified.
Outer joins can be one of:

-   `LEFT` (All rows from the left relation appear at least once)
-   `RIGHT` (All rows from the right relation appear at least once)
-   `FULL` (All rows from both relations appear at least once)

A join that is not `OUTER` is `INNER` (only rows that get paired are returned).

When an unpaired row is returned, the attributes from the other table are set to `NULL`.

### Cross Product Joins (Cartesian Product)

The simplest type of join is a `CROSS JOIN`.
There are no conditions for this type of join,
and it just returns all the possible pairs.

Return all pairs of rows:

```sql
SELECT a.*, b.*
FROM a
CROSS JOIN b;
-- result:
id	x	id	x
1	100	1	10
2	200	1	10
1	100	2	20
2	200	2	20
```

This is equivalent to omitting the `JOIN` clause:

```sql
SELECT a.*, b.*
FROM a, b;
-- result:
id	x	id	x
1	100	1	10
2	200	1	10
1	100	2	20
2	200	2	20
```

### Conditional Joins

Most joins are specified by a predicate that connects
attributes from one side to attributes from the other side.
The conditions can be explicitly specified using an `ON` clause
with the join (clearer) or implied by the `WHERE` clause (old-fashioned).

We use the `l_regions` and the `l_nations` tables from the TPC-H schema:

```sql
CREATE TABLE l_regions (
    r_regionkey INTEGER NOT NULL PRIMARY KEY,
    r_name      CHAR(25) NOT NULL,
    r_comment   VARCHAR(152)
);

CREATE TABLE l_nations (
    n_nationkey INTEGER NOT NULL PRIMARY KEY,
    n_name      CHAR(25) NOT NULL,
    n_regionkey INTEGER NOT NULL,
    n_comment   VARCHAR(152),
    FOREIGN KEY (n_regionkey) REFERENCES l_regions(r_regionkey)
);
```

Return the regions for the nations:

```sql
query ??????? rowsort
SELECT n.*, r.*
FROM l_nations n
JOIN l_regions r ON (n_regionkey = r_regionkey);
-- result:
n_nationkey	n_name	n_regionkey	n_comment	r_regionkey	r_name	r_comment
0	ALGERIA	0	 haggle. carefully final deposits detect slyly agai	0	AFRICA	lar deposits. blithely final packages cajole. regular waters are final requests. regular accounts are according to
1	ARGENTINA	1	al foxes promise slyly according to the regular accounts. bold requests alon	1	AMERICA	hs use ironic, even requests. s
2	BRAZIL	1	y alongside of the pending deposits. carefully special packages are about the ironic forges. slyly special 	1	AMERICA	hs use ironic, even requests. s
3	CHINA	2	even packages wake furiously alongside of the regular courts. final requests haggle carefully.	2	ASIA	ges. thinly even pinto beans ca
```

If the column names are the same and are required to be equal,
then the simpler `USING` syntax can be used:

```sql
CREATE TABLE l_regions (regionkey INTEGER NOT NULL PRIMARY KEY,
                        name      CHAR(25) NOT NULL,
                        comment   VARCHAR(152));

CREATE TABLE l_nations (nationkey INTEGER NOT NULL PRIMARY KEY,
                        name      CHAR(25) NOT NULL,
                        regionkey INTEGER NOT NULL,
                        comment   VARCHAR(152),
                        FOREIGN KEY (regionkey) REFERENCES l_regions(regionkey));
```

Return the regions for the nations:

```sql
query ??????? rowsort
SELECT n.*, r.*
FROM l_nations n
JOIN l_regions r USING (regionkey);
-- result:
nationkey	name	regionkey	comment	regionkey	name	comment
0	ALGERIA	0	 haggle. carefully final deposits detect slyly agai	0	AFRICA	lar deposits. blithely final packages cajole. regular waters are final requests. regular accounts are according to
1	ARGENTINA	1	al foxes promise slyly according to the regular accounts. bold requests alon	1	AMERICA	hs use ironic, even requests. s
2	BRAZIL	1	y alongside of the pending deposits. carefully special packages are about the ironic forges. slyly special 	1	AMERICA	hs use ironic, even requests. s
3	CHINA	2	even packages wake furiously alongside of the regular courts. final requests haggle carefully.	2	ASIA	ges. thinly even pinto beans ca
```

The expressions do not have to be equalities – any predicate can be used:

Return the pairs of jobs where one ran longer but cost less:

```sql
query ?? rowsort
SELECT s1.t_id, s2.t_id
FROM west s1, west s2
WHERE s1.time > s2.time
  AND s1.cost < s2.cost;
-- result:
t_id	t_id
2	1
4	1
4	2
4	3
```

### Natural Joins

Natural joins join two tables based on attributes that share the same name.

For example, take the following example with cities, airport codes and airport names. Note that both tables are intentionally incomplete, i.e., they do not have a matching pair in the other table.

```sql
CREATE TABLE city_airport (city_name VARCHAR, iata VARCHAR);

CREATE TABLE airport_names (iata VARCHAR, airport_name VARCHAR);

INSERT INTO city_airport VALUES
    ('Amsterdam', 'AMS'),
    ('Rotterdam', 'RTM'),
    ('Eindhoven', 'EIN'),
    ('Groningen', 'GRQ');

INSERT INTO airport_names VALUES
    ('AMS', 'Amsterdam Airport Schiphol'),
    ('RTM', 'Rotterdam The Hague Airport'),
    ('MST', 'Maastricht Aachen Airport');
```

To join the tables on their shared [`IATA`](https://en.wikipedia.org/wiki/IATA_airport_code) attributes, run:

```sql
SELECT *
FROM city_airport
NATURAL JOIN airport_names;
-- result:
iata	city_name	airport_name
AMS	Amsterdam	Amsterdam Airport Schiphol
RTM	Rotterdam	Rotterdam The Hague Airport
```

Note that only rows where the same `iata` attribute was present in both tables were included in the result.

We can also express this query using the vanilla `JOIN` clause with the `USING` keyword:

```sql
SELECT *
FROM city_airport
JOIN airport_names
USING (iata);
-- result:
iata	city_name	airport_name
AMS	Amsterdam	Amsterdam Airport Schiphol
RTM	Rotterdam	Rotterdam The Hague Airport
```

### Semi and Anti Joins

Semi joins return rows from the left table that have at least one match in the right table.
Anti joins return rows from the left table that have _no_ matches in the right table.
When using a semi or anti join the result will never have more rows than the left hand side table.
Semi joins provide the same logic as the [`IN` operator](../../expressions/in/index.md) statement.
Anti joins provide the same logic as the `NOT IN` operator, except anti joins ignore `NULL` values from the right table.

#### Semi Join Example

Return a list of city–airport code pairs from the `city_airport` table where the airport name **is available** in the `airport_names` table:

```sql
SELECT *
FROM city_airport
SEMI JOIN airport_names
    USING (iata);
-- result:
iata	city_name
AMS	Amsterdam
RTM	Rotterdam
```

This query is equivalent to:

```sql
SELECT *
FROM city_airport
WHERE iata IN (SELECT iata FROM airport_names);
-- result:
city_name	iata
Amsterdam	AMS
Rotterdam	RTM
```

#### Anti Join Example

Return a list of city–airport code pairs from the `city_airport` table where the airport name **is not available** in the `airport_names` table:

```sql
SELECT *
FROM city_airport
ANTI JOIN airport_names
    USING (iata);
-- result:
iata	city_name
EIN	Eindhoven
GRQ	Groningen
```

This query is equivalent to:

```sql
SELECT *
FROM city_airport
WHERE iata NOT IN (SELECT iata FROM airport_names WHERE iata IS NOT NULL);
-- result:
city_name	iata
Eindhoven	EIN
Groningen	GRQ
```

### Lateral Joins

The `LATERAL` keyword allows subqueries in the `FROM` clause to refer to previous subqueries. This feature is also known as a _lateral join_.

<div className="docs-table-centered">

```sql
SELECT *
FROM range(3) t(i), LATERAL (SELECT i + 1) t2(j);
-- result:
i	j
0	1
1	2
2	3
```

</div>

Lateral joins are a generalization of correlated subqueries, as they can return multiple values per input value rather than only a single value.

<div className="docs-table-centered">

```sql
query ?? rowsort
SELECT *
FROM
    generate_series(0, 1) t(i),
    LATERAL (SELECT i + 10 UNION ALL SELECT i + 100) t2(j);
-- result:
i	j
0	10
0	100
1	101
1	11
```

</div>

It may be helpful to think about `LATERAL` as a loop where we iterate through the rows of the first subquery and use it as input to the second (`LATERAL`) subquery.
In the examples above, we iterate through table `t` and refer to its column `i` from the definition of table `t2`. The rows of `t2` form column `j` in the result.

It is possible to refer to multiple attributes from the `LATERAL` subquery. Using the table from the first example:

<div className="docs-table-centered">

```sql
CREATE TABLE t1 AS
    SELECT *
    FROM range(3) t(i), LATERAL (SELECT i + 1) t2(j);

SELECT *
    FROM t1, LATERAL (SELECT i + j) t2(k)
    ORDER BY ALL;
-- result:
i	j	k
0	1	1
1	2	3
2	3	5
```

</div>

<DocCallout type="tip">
SereneDB detects when `LATERAL` joins should be used, making the use of the `LATERAL` keyword optional.
</DocCallout>

### Positional Joins

When working with data frames or other embedded tables of the same size,
the rows may have a natural correspondence based on their physical order.
In scripting languages, this is easily expressed using a loop:

```cpp
for (i = 0; i < n; i++) {
    f(t1.a[i], t2.b[i]);
}
```

It is difficult to express this in standard SQL because
relational tables are not ordered, but imported tables such as data frames
or disk files (like [CSVs](../../../data_import_and_export/csv/overview.md) or [Parquet files](../../../data_import_and_export/parquet/overview.md)) do have a natural ordering.

Connecting them using this ordering is called a _positional join:_

<div className="docs-table-centered">

```sql
CREATE TABLE t1 (x INTEGER);

CREATE TABLE t2 (s VARCHAR);

INSERT INTO t1 VALUES (1), (2), (3);

INSERT INTO t2 VALUES ('a'), ('b');

SELECT *
FROM t1
POSITIONAL JOIN t2;
-- result:
x	s
1	a
2	b
3	NULL
```

</div>

Positional joins are always `FULL OUTER` joins, i.e., the resulting table has the length of the longer input table and the missing entries are filled with `NULL` values.

### As-Of Joins

A common operation when working with temporal or similarly-ordered data
is to find the nearest (first) event in a reference table (such as prices).
This is called an _as-of join:_

Attach prices to stock trades:

```sql
query ???? rowsort
SELECT t.*, p.price
FROM trades t
ASOF JOIN prices p
       ON t.symbol = p.symbol AND t.when >= p.when;
-- result:
symbol	when	quantity	price
AAPL	2025-01-01 10:00:00	5	100
MSFT	2025-01-01 10:15:00	2	200
```

The `ASOF` join requires at least one inequality condition on the ordering field.
The inequality can be any inequality condition (`>=`, `>`, `<=`, `<`)
on any data type, but the most common form is `>=` on a temporal type.
Any other conditions must be equalities (or `NOT DISTINCT`).
This means that the left/right order of the tables is significant.

`ASOF` joins each left side row with at most one right side row.
It can be specified as an `OUTER` join to find unpaired rows
(e.g., trades without prices or prices which have no trades.)

Attach prices or NULLs to stock trades:

```sql
query ??????? rowsort
SELECT *
FROM trades t
ASOF LEFT JOIN prices p
            ON t.symbol = p.symbol
           AND t.when >= p.when;
-- result:
symbol	when	quantity	symbol	when	price	ticker
AAPL	2025-01-01 10:00:00	5	AAPL	2025-01-01 09:30:00	100	AAPL
MSFT	2025-01-01 10:15:00	2	MSFT	2025-01-01 09:45:00	200	MSFT
```

`ASOF` joins can also specify join conditions on matching column names with the `USING` syntax,
but the _last_ attribute in the list must be the inequality,
which will be greater than or equal to (`>=`):

```sql
query ????? rowsort
SELECT *
FROM trades t
ASOF JOIN prices p USING (symbol, "when");
-- result:
symbol	when	quantity	price	ticker
AAPL	2025-01-01 10:00:00	5	100	AAPL
MSFT	2025-01-01 10:15:00	2	200	MSFT
```

Returns symbol, trades.when, price (but NOT prices.when):

If you combine `USING` with a `SELECT *` like this,
the query will return the left side (probe) column values for the matches,
not the right side (build) column values.
To get the `prices` times in the example, you will need to list the columns explicitly:

```sql
query ???? rowsort
SELECT t.symbol, t.when AS trade_when, p.when AS price_when, price
FROM trades t
ASOF LEFT JOIN prices p USING (symbol, "when");
-- result:
symbol	trade_when	price_when	price
AAPL	2025-01-01 10:00:00	2025-01-01 09:30:00	100
MSFT	2025-01-01 10:15:00	2025-01-01 09:45:00	200
```

### Self-Joins

SereneDB allows self-joins for all types of joins.
Note that tables need to be aliased, using the same table name without aliases will result in an error:

```sql
CREATE TABLE t (x INTEGER);

query error
SELECT * FROM t JOIN t USING(x);
-- result:
db error: ERROR: Ambiguous reference to table "<slt:ignore>.public.t" (duplicate alias "<slt:ignore>.public.t", explicitly alias one of the tables using "AS my_alias")
```

Adding the aliases allows the query to parse successfully:

```sql
SELECT * FROM t AS t1 JOIN t AS t2 USING(x);
-- result:
x
```

### Shorthands in the `JOIN` Clause

You can specify column names in the `JOIN` clause:

```sql
CREATE TABLE t1 (x INTEGER);

CREATE TABLE t2 (y INTEGER);

INSERT INTO t1 VALUES (1), (2), (4);

INSERT INTO t2 VALUES (2), (3);

SELECT * FROM t1 NATURAL JOIN t2 t2(x);
-- result:
x
2
```

You can also use the `VALUES` clause in the `JOIN` clause:

```sql
SELECT * FROM t1 NATURAL JOIN (VALUES (2), (4)) _(x);
-- result:
x
2
4
```

## `FROM`-First Syntax

SereneDB's SQL supports the `FROM`-first syntax, i.e., it allows putting the `FROM` clause before the `SELECT` clause or completely omitting the `SELECT` clause. We use the following example to demonstrate it:

```sql
CREATE TABLE tbl AS
    SELECT *
    FROM (VALUES ('a'), ('b')) t1(s), range(1, 3) t2(i);
```

### `FROM`-First Syntax with a `SELECT` Clause

The following statement demonstrates the use of the `FROM`-first syntax:

```sql
FROM tbl
SELECT i, s;
-- result:
i	s
1	a
1	b
2	a
2	b
```

This is equivalent to:

<div className="docs-table-centered">

```sql
SELECT i, s
FROM tbl;
-- result:
i	s
1	a
1	b
2	a
2	b
```

</div>

### `FROM`-First Syntax without a `SELECT` Clause

The following statement demonstrates the use of the optional `SELECT` clause:

```sql
FROM tbl;
-- result:
s	i
a	1
b	1
a	2
b	2
```

This is equivalent to:

<div className="docs-table-centered">

```sql
SELECT *
FROM tbl;
-- result:
s	i
a	1
b	1
a	2
b	2
```

</div>

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

