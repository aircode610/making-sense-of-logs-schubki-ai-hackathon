---
title: List
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

A `LIST` column encodes lists of values. Fields in the column can have values with different lengths, but they must all have the same underlying type. `LIST`s are typically used to store arrays of numbers, but can contain any uniform data type, including other `LIST`s and `STRUCT`s.

`LIST`s are similar to PostgreSQL's `ARRAY` type. SereneDB uses the `LIST` terminology, but some [`array_` functions](../../sql/functions/list.md) are provided for PostgreSQL compatibility.

See the [data types overview](../../sql/data_types/index.md) for a comparison between nested data types.

<DocCallout type="tip">
For storing fixed-length lists, SereneDB uses the [`ARRAY` type](../../sql/data_types/array.md).
</DocCallout>

## Creating Lists

Lists can be created using the [`list_value(expr, ...)`](../../sql/functions/list.md#list_valuearg-) function or the equivalent bracket notation `[expr, ...]`. The expressions can be constants or arbitrary expressions. To create a list from a table column, use the [`list`](../../sql/functions/aggregates/index.md#general-aggregate-functions) aggregate function.

List of integers:

```sql
SELECT [1, 2, 3];
-- result:
list_value
{1,2,3}
```

List of strings with a `NULL` value:

```sql
SELECT ['alpha', 'beta', NULL, 'gamma'];
-- result:
list_value
{alpha,beta,NULL,gamma}
```

List of lists with `NULL` values:

```sql
skipif pg-wire-extended
SELECT [['alpha', 'beta', 'gamma'], NULL, ['delta', 'epsilon'], []];
-- result:
list_value
{{alpha,beta,gamma},NULL,{delta,epsilon},{}}
```

Create a list with the list_value function:

```sql
SELECT list_value(1, 2, 3);
-- result:
list_value
{1,2,3}
```

Create a table with an `INTEGER` list column and a `VARCHAR` list column:

```sql
CREATE TABLE list_table (int_list INTEGER[], varchar_list VARCHAR[]);
```

## Retrieving from Lists

Retrieving one or more values from a list can be accomplished using brackets and slicing notation, or through [list functions](../../sql/functions/list.md) like `list_extract`. Multiple equivalent functions are provided as aliases for compatibility with systems that refer to lists as arrays. For example, the function `array_slice`.

```sql
SELECT $$['a', 'b', 'c'][3]$$                AS "Example", (['a', 'b', 'c'][3])::VARCHAR                AS "Result"
UNION ALL SELECT $$['a', 'b', 'c'][-1]$$,                  (['a', 'b', 'c'][-1])::VARCHAR
UNION ALL SELECT $$['a', 'b', 'c'][2 + 1]$$,               (['a', 'b', 'c'][2 + 1])::VARCHAR
UNION ALL SELECT $$list_extract(['a', 'b', 'c'], 3)$$,     (list_extract(['a', 'b', 'c'], 3))::VARCHAR
UNION ALL SELECT $$['a', 'b', 'c'][1:2]$$,                 (['a', 'b', 'c'][1:2])::VARCHAR
UNION ALL SELECT $$['a', 'b', 'c'][:2]$$,                  (['a', 'b', 'c'][:2])::VARCHAR
UNION ALL SELECT $$['a', 'b', 'c'][-2:]$$,                 (['a', 'b', 'c'][-2:])::VARCHAR
UNION ALL SELECT $$list_slice(['a', 'b', 'c'], 2, 3)$$,    (list_slice(['a', 'b', 'c'], 2, 3))::VARCHAR;
-- result:
Example	Result
['a', 'b', 'c'][3]	c
['a', 'b', 'c'][-1]	c
['a', 'b', 'c'][2 + 1]	c
list_extract(['a', 'b', 'c'], 3)	c
['a', 'b', 'c'][1:2]	[a, b]
['a', 'b', 'c'][:2]	[a, b]
['a', 'b', 'c'][-2:]	[b, c]
list_slice(['a', 'b', 'c'], 2, 3)	[b, c]
```

## Comparison and Ordering

The `LIST` type can be compared using all the [comparison operators](../../sql/expressions/comparison_operators/index.md).
These comparisons can be used in [logical expressions](../../sql/expressions/logical_operators/index.md)
such as `WHERE` and `HAVING` clauses, and return [`BOOLEAN` values](../../sql/data_types/boolean.md).

The `LIST` ordering is defined positionally using the following rules, where `min_len = min(len(l1), len(l2))`.

-   **Equality.** `l1` and `l2` are equal, if for each `i` in `[1, min_len]`: `l1[i] = l2[i]`.
-   **Less Than**. For the first index `i` in `[1, min_len]` where `l1[i] != l2[i]`:
    If `l1[i] < l2[i]`, `l1` is less than `l2`.

`NULL` values are compared following PostgreSQL's semantics.
Lower nesting levels are used for tie-breaking.

Here are some queries returning `true` for the comparison.

```sql
SELECT [1, 2] < [1, 3] AS result;
-- result:
result
t
```

```sql
SELECT [[1], [2, 4, 5]] < [[2]] AS result;
-- result:
result
t
```

```sql
SELECT [ ] < [1] AS result;
-- result:
result
t
```

```sql
SELECT [1, 2] < [1, NULL, 4] AS result;
-- result:
result
t
```

These queries return `false`.

```sql
SELECT [ ] < [ ] AS result;
-- result:
result
f
```

```sql
SELECT [1, 2] < [1] AS result;
-- result:
result
f
```

## Functions

See [List Functions](../../sql/functions/list.md).

