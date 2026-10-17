---
title: Star Expression
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

The `*` expression can be used in a `SELECT` statement to select all columns that are projected in the `FROM` clause.

```sql
SELECT *
FROM tbl;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

### `TABLE.*` and `STRUCT.*`

The `*` expression can be prepended by a table name to select only columns from that table.

```sql
SELECT tbl.*
FROM tbl
JOIN other_tbl USING (id);
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
```

Similarly, the `*` expression can also be used to retrieve all keys from a struct as separate columns.
This is particularly useful when a prior operation creates a struct of unknown shape, or if a query must handle any potential struct keys.
See the [`STRUCT` data type](../../../sql/data_types/struct.md) and [`STRUCT` functions](../../../sql/functions/struct.md) pages for more details on working with structs.

For example:

```sql
SELECT st.* FROM (SELECT {'x': 1, 'y': 2, 'z': 3} AS st);
-- result:
x	y	z
1	2	3
```

### `EXCLUDE` Clause

`EXCLUDE` allows you to exclude specific columns from the `*` expression.

```sql
SELECT * EXCLUDE (col)
FROM tbl;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

### `REPLACE` Clause

`REPLACE` allows you to replace specific columns by alternative expressions.

```sql
SELECT * REPLACE (col1 / 1_000 AS col1, col2 / 1_000 AS col2)
FROM tbl;
-- result:
id	name	col1	col2	Some Column Name	i	a	b	c	number	number1	number2
1	mark	0.001	0.002	alpha	1	10	20	30	10	100	1000
3	bookmark	0.004	0.005	beta	2	11	21	31	20	200	2000
7	other	0.009	0.016	gamma	3	12	22	32	NULL	300	3000
```

### `RENAME` Clause

`RENAME` allows you to replace specific columns.

```sql
SELECT * RENAME (col1 AS height, col2 AS width)
FROM tbl;
-- result:
id	name	height	width	Some Column Name	i	a	b	c	number	number1	number2
1	mark	1	2	alpha	1	10	20	30	10	100	1000
3	bookmark	4	5	beta	2	11	21	31	20	200	2000
7	other	9	16	gamma	3	12	22	32	NULL	300	3000
```

### Column Filtering via Pattern Matching Operators

The [pattern matching operators](../../../sql/functions/pattern_matching/index.md) `LIKE` and `GLOB` allow you to select columns by matching their names to patterns.

```sql
SELECT * LIKE 'col%'
FROM tbl;
-- result:
col1	col2
1	2
4	5
9	16
```

```sql
SELECT * GLOB 'col*'
FROM tbl;
-- result:
col1	col2
1	2
4	5
9	16
```

The pattern applied to a star expression must be a constant, and only `LIKE` and `GLOB` are supported. The `SIMILAR TO` operator is not supported on a star expression and raises an error:

```sql
SELECT * SIMILAR TO 'col.'
FROM tbl;
-- result:
col1	col2
1	2
4	5
9	16
```

The `NOT` variant behaves the same way and also raises an error:

```sql
SELECT * NOT SIMILAR TO 'col.'
FROM tbl;
-- result:
id	name	Some Column Name	i	a	b	c	number	number1	number2
1	mark	alpha	1	10	20	30	10	100	1000
3	bookmark	beta	2	11	21	31	20	200	2000
7	other	gamma	3	12	22	32	NULL	300	3000
```

## `COLUMNS` Expression

The `COLUMNS` expression is similar to the regular star expression, but additionally allows you to execute the same expression on the resulting columns.

```sql
CREATE TABLE numbers (id INTEGER, number INTEGER);

INSERT INTO numbers VALUES (1, 10), (2, 20), (3, NULL);

SELECT min(COLUMNS(*)), count(COLUMNS(*)) FROM numbers;
-- result:
id	number	id	number
1	10	3	2
```

```sql
SELECT
    min(COLUMNS(* REPLACE (number + id AS number))),
    count(COLUMNS(* EXCLUDE (number)))
FROM numbers;
-- result:
id	min	id
1	11	3
```

`COLUMNS` expressions can also be combined, as long as they contain the same star expression:

```sql
SELECT COLUMNS(*) + COLUMNS(*) FROM numbers;
-- result:
id	number
2	20
4	40
6	NULL
```

### `COLUMNS` Expression in a `WHERE` Clause

`COLUMNS` expressions can also be used in `WHERE` clauses. The conditions are applied to all columns and are combined using the logical `AND` operator.

```sql
query ?? rowsort
SELECT *
FROM (
    SELECT 'a', 'a'
    UNION ALL
    SELECT 'a', 'b'
    UNION ALL
    SELECT 'b', 'b'
) _(x, y)
WHERE COLUMNS(*) = 'a';
-- result:
x	y
a	a
```

To combine conditions using the logical `OR` operator, you can `UNPACK` the `COLUMNS` expression into the variadic `greatest` function.

```sql
query ?? rowsort
SELECT *
FROM (
    SELECT 'a', 'a'
    UNION ALL
    SELECT 'a', 'b'
    UNION ALL
    SELECT 'b', 'b'
) _(x, y)
WHERE greatest(UNPACK(COLUMNS(*) = 'a'));
-- result:
x	y
a	a
a	b
```

### `COLUMNS` Expression in `DISTINCT ON`

`COLUMNS` expressions can be used in [`DISTINCT ON`](../../../sql/query_syntax/select/index.md#distinct-on-clause) clauses to specify distinct columns by pattern:

```sql
query ??? rowsort
SELECT DISTINCT ON (COLUMNS('x|y')) *
FROM (VALUES (1, 2, 'a'), (1, 2, 'b'), (3, 4, 'c')) t(x, y, z);
-- result:
x	y	z
1	2	<slt:ignore>
3	4	c
```

### Regular Expressions in a `COLUMNS` Expression

`COLUMNS` expressions don't currently support the pattern matching operators, but they do support regular expression matching by simply passing a string constant in place of the star:

```sql
SELECT COLUMNS('(id|numbers?)') FROM numbers;
-- result:
id	number
1	10
2	20
3	NULL
```

### Renaming Columns with Regular Expressions in a `COLUMNS` Expression

The matches of capture groups in regular expressions can be used to rename matching columns.
The capture groups are one-indexed; `\0` is the original column name.

For example, to select the first three letters of column names, run:

```sql
SELECT COLUMNS('(\w{3}).*') AS '\1' FROM numbers;
-- result:
num
10
20
NULL
```

To remove a colon (`:`) character in the middle of a column name, run:

```sql
CREATE TABLE tbl ("Foo:Bar" INTEGER, "Foo:Baz" INTEGER, "Foo:Qux" INTEGER);

SELECT COLUMNS('(\w*):(\w*)') AS '\1\2' FROM tbl;
-- result:
FooBar	FooBaz	FooQux
```

To add the original column name to the expression alias, run:

```sql
SELECT min(COLUMNS(*)) AS "min_\0" FROM numbers;
-- result:
min_id	min_number
1	10
```

### `COLUMNS` Lambda Function

`COLUMNS` also supports passing in a lambda function. The lambda function will be evaluated for all columns present in the `FROM` clause, and only columns that match the lambda function will be returned. This allows the execution of arbitrary expressions in order to select and rename columns.

```sql
SELECT COLUMNS(lambda c: c LIKE '%num%') FROM numbers;
-- result:
number
10
20
NULL
```

### `COLUMNS` List

`COLUMNS` also supports passing in a list of column names.

```sql
SELECT COLUMNS(['id', 'num']) FROM numbers;
-- result:
id	num
1	10
2	20
3	NULL
```

## Unpacking a `COLUMNS` Expression

By wrapping a `COLUMNS` expression in `UNPACK`, the columns expand into a parent expression, much like the [iterable unpacking behavior in Python](https://peps.python.org/pep-3132/).

Without `UNPACK`, operations on the `COLUMNS` expression are applied to each column separately:

```sql
SELECT coalesce(COLUMNS(['a', 'b', 'c'])) AS result
FROM (SELECT NULL a, 42 b, true c);
-- result:
result	result	result
NULL	42	t
```

With `UNPACK`, the `COLUMNS` expression is expanded into its parent expression, `coalesce` in the example above, which results in a single column:

```sql
SELECT coalesce(UNPACK(COLUMNS(['a', 'b', 'c']))) AS result
FROM (SELECT NULL AS a, 42 AS b, true AS c);
-- result:
result
42
```

The `UNPACK` keyword may be replaced by `*`, [matching Python syntax](https://peps.python.org/pep-3132/), when it is applied directly to the `COLUMNS` expression without any intermediate operations.

```sql
SELECT coalesce(*COLUMNS(*)) AS result
FROM (SELECT NULL a, 42 AS b, true AS c);
-- result:
result
42
```

<DocCallout type="attention">
In the following example, where the `COLUMNS` expression has an intermediate operation (`+ 1`), replacing `UNPACK` by `*` results in an error:

```sql
query error
SELECT greatest(*COLUMNS(*) + 1) AS result
FROM (SELECT 1 AS a, 2 AS b, 3 AS c);
-- result:
db error: ERROR: No function matches the given name and argument types '+(INTEGER, INTEGER, INTEGER, INTEGER_LITERAL)'. <slt:ignore>
```
</DocCallout>

