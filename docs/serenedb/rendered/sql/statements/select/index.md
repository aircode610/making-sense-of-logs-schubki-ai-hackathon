---
title: SELECT
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

The `SELECT` statement retrieves rows from the database.

## Examples

Select all columns from the table `tbl`:

```sql
SELECT * FROM tbl;
-- result:
id	name	col1	col2	Some Column Name	i	j	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	20	11	21	31	20	200	2000
7	other	9	16	gamma	3	30	12	22	32	NULL	300	3000
```

Select the rows from `tbl`:

```sql
SELECT j FROM tbl WHERE i = 3;
-- result:
j
30
```

Perform an aggregate grouped by the column `i`:

```sql
query ?? rowsort
SELECT i, sum(j) FROM tbl GROUP BY i;
-- result:
i	sum
1	10
2	20
3	30
```

Select only the top 3 rows from the `tbl`:

```sql
SELECT * FROM tbl ORDER BY i DESC LIMIT 3;
-- result:
id	name	col1	col2	Some Column Name	i	j	a	b	c	number	number1	number2
7	other	9	16	gamma	3	30	12	22	32	NULL	300	3000
3	bookmark	4	5	beta	2	20	11	21	31	20	200	2000
1	mark	1	2	alpha	1	10	10	20	30	10	100	1000
```

Join two tables together using the `USING` clause:

```sql
query ??????????????????????????????????????????????????????????????????? rowsort
SELECT * FROM t1 JOIN t2 USING (a, b);
-- result:
a	b	id	i	j	k	x	y	z	c	article_id	comment_id	author_id	customer_id	order_id	product_id	employee_id	title	body	content	description	name	tag	category	genre	region	country	city	product	customer	status	symbol	amount	quantity	price	views	runtime	year	revenue	salary	grade	balance	count	value	published_at	created_at	updated_at	date	sale_date	ts	time	l_orderkey	l_partkey	l_suppkey	l_linenumber	l_quantity	l_extendedprice	l_discount	l_tax	l_returnflag	l_linestatus	l_shipdate	l_commitdate	l_receiptdate	l_shipinstruct	l_shipmode	l_comment
1	2	1	1	10	100	1	2	3	3	1	1	1	1	1	1	1	Intro to Search	search analytics body	search content	alien galaxy film	alpha	search	engineering	sci-fi	north	US	Berlin	widget	Alice	open	AAPL	100	10	9.5	4200	120	2024	1000	70000	1	500	1	42	2025-01-15	2025-01-15 10:00:00	2025-01-16 10:00:00	2025-01-15	2025-01-15	2025-01-15 10:00:00	2025-01-15 10:00:00	1	1	1	1	10	100	0.05	0.01	N	O	1998-09-01	1998-08-15	1998-09-05	DELIVER IN PERSON	AIR	first lineitem
2	3	2	2	20	200	2	3	4	4	2	2	2	2	2	2	2	Scaling Analytics	another text body	analytics content	biggest blockbuster story	beta	analytics	product	drama	south	DE	Paris	gadget	Bob	closed	MSFT	200	20	19.5	5100	95	2025	2500	80000	2	700	2	84	2025-03-01	2025-03-01 11:00:00	2025-03-02 11:00:00	2025-03-01	2025-03-01	2025-03-01 11:00:00	2025-03-01 11:00:00	2	2	2	2	20	200	0.1	0.02	R	F	1998-09-02	1998-08-16	1998-09-06	TAKE BACK RETURN	MAIL	second lineitem
```

Use column indexes to select the first and third column from the table `tbl`:

```sql
SELECT #1, #3 FROM tbl;
-- result:
id	col1
1	1
3	4
7	9
```

Select all unique cities from the addresses table:

```sql
query ? rowsort
SELECT DISTINCT city FROM addresses;
-- result:
city
Lakeside
Riverton
Springfield
```

Return a `STRUCT` by using a row variable:

```sql
SELECT d
FROM (SELECT 1 AS a, 2 AS b) d;
-- result:
d
(1,2)
```

## Syntax

The `SELECT` statement retrieves rows from the database. The canonical order of a `SELECT` statement is as follows, with less common clauses being indented:

```sql
SELECT ⟨select_list⟩
FROM ⟨tables⟩
    USING SAMPLE ⟨sample_expression⟩
WHERE ⟨condition⟩
GROUP BY ⟨groups⟩
HAVING ⟨group_filter⟩
    WINDOW ⟨window_expression⟩
    QUALIFY ⟨qualify_filter⟩
ORDER BY ⟨order_expression⟩
LIMIT ⟨n⟩;
```

Optionally, the `SELECT` statement can be prefixed with a [`WITH` clause](../../query_syntax/with/index.md).

As the `SELECT` statement is so complex, we have split up the syntax diagrams into several parts. The full syntax diagram can be found at the bottom of the page.

### `SELECT` Clause

<RailroadDiagram source={RailroadSource} production="rrdiagram3" />

The [`SELECT` clause](../../query_syntax/select/index.md) specifies the list of columns that will be returned by the query. While it appears first in the clause, _logically_ the expressions here are executed only at the end. The `SELECT` clause can contain arbitrary expressions that transform the output, as well as aggregates and window functions. The `DISTINCT` keyword ensures that only unique tuples are returned.

<DocCallout type="tip">
Column names are case-insensitive. See the [Rules for Case Sensitivity](../../../compatibility/keywords_and_identifiers.md#rules-for-case-sensitivity) for more details.
</DocCallout>

### `FROM` Clause

<RailroadDiagram source={RailroadSource} production="rrdiagram4" />

The [`FROM` clause](../../query_syntax/from_and_join/index.md) specifies the _source_ of the data on which the remainder of the query should operate. Logically, the `FROM` clause is where the query starts execution. The `FROM` clause can contain a single table, a combination of multiple tables that are joined together, or another `SELECT` query inside a subquery node.

### `SAMPLE` Clause

<RailroadDiagram source={RailroadSource} production="rrdiagram10" />

The [`SAMPLE` clause](../../query_syntax/sample/index.md) allows you to run the query on a sample from the base table. This can significantly speed up processing of queries, at the expense of accuracy in the result. Samples can also be used to quickly see a snapshot of the data when exploring a dataset. The `SAMPLE` clause is applied right after anything in the `FROM` clause (i.e., after any joins, but before the where clause or any aggregates). See the [Samples](../../samples/index.md) page for more information.

### `WHERE` Clause

<RailroadDiagram source={RailroadSource} production="rrdiagram5" />

The [`WHERE` clause](../../query_syntax/where/index.md) specifies any filters to apply to the data. This allows you to select only a subset of the data in which you are interested. Logically the `WHERE` clause is applied immediately after the `FROM` clause.

### `GROUP BY` and `HAVING` Clauses

<RailroadDiagram source={RailroadSource} production="rrdiagram6" />

The [`GROUP BY` clause](../../query_syntax/groupby/index.md) specifies which grouping columns should be used to perform any aggregations in the `SELECT` clause. If the `GROUP BY` clause is specified, the query is always an aggregate query, even if no aggregations are present in the `SELECT` clause.

### `WINDOW` Clause

<RailroadDiagram source={RailroadSource} production="rrdiagram7" />

The [`WINDOW` clause](../../query_syntax/window/index.md) allows you to specify named windows that can be used within window functions. These are useful when you have multiple window functions, as they allow you to avoid repeating the same window clause.

### `QUALIFY` Clause

<RailroadDiagram source={RailroadSource} production="rrdiagram11" />

The [`QUALIFY` clause](../../query_syntax/qualify/index.md) is used to filter the result of [`WINDOW` functions](../../functions/window_functions/index.md).

### `ORDER BY`, `LIMIT` and `OFFSET` Clauses

<RailroadDiagram source={RailroadSource} production="rrdiagram8" />

[`ORDER BY`](../../query_syntax/orderby/index.md), [`LIMIT` and `OFFSET`](../../query_syntax/limit/index.md) are output modifiers.
Logically they are applied at the very end of the query.
The `ORDER BY` clause sorts the rows on the sorting criteria in either ascending or descending order.
The `LIMIT` clause restricts the amount of rows fetched, while the `OFFSET` clause indicates at which position to start reading the values.

### `VALUES` List

<RailroadDiagram source={RailroadSource} production="rrdiagram9" />

[A `VALUES` list](../../query_syntax/values/index.md) is a set of values that is supplied instead of a `SELECT` statement.

### Row IDs

For each table, the [`rowid` pseudocolumn](https://docs.oracle.com/cd/B19306_01/server.102/b14200/pseudocolumns008.htm) returns the row identifiers based on the physical storage.

```sql
CREATE TABLE t (id INTEGER, content VARCHAR);

INSERT INTO t VALUES (42, 'hello'), (43, 'world');

SELECT rowid, id, content FROM t;
-- result:
rowid	id	content
0	42	hello
1	43	world
```

In the current storage, these identifiers are contiguous unsigned integers (0, 1, ...) if no rows were deleted.
Deletions introduce gaps in the rowids which may be reclaimed later:

```sql
CREATE OR REPLACE TABLE t AS (FROM range(10) r(i));

DELETE FROM t WHERE i % 2 = 0;

SELECT rowid FROM t;
-- result:
rowid
1
3
5
7
9
```

The `rowid` values are stable within a transaction.

<DocCallout type="bestPractice">
It is strongly advised to avoid using rowids as identifiers.
</DocCallout>

<DocCallout type="note">

If there is a user-defined column named `rowid`, it shadows the `rowid` pseudocolumn.

</DocCallout>

### Common Table Expressions

<RailroadDiagram source={RailroadSource} production="rrdiagram2" />

## Full Syntax Diagram

Below is the full syntax diagram of the `SELECT` statement:

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

