---
title: IN Operator
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `IN` operator checks containment of the left expression inside the _collection_ on the right hand side (RHS).
Supported collections on the RHS are tuples, lists, maps and subqueries that return a single column.

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

## `IN (val1, val2, ...)` (Tuple)

The `IN` operator on a tuple `(val1, val2, ...)` returns `true` if the expression is present in the RHS, `false` if the expression is not in the RHS and the RHS has no `NULL` values, or `NULL` if the expression is not in the RHS and the RHS has `NULL` values.

```sql
SELECT 'Math' IN ('CS', 'Math');
-- result:
?column?
t
```

```sql
SELECT 'English' IN ('CS', 'Math');
-- result:
?column?
f
```

```sql
SELECT 'Math' IN ('CS', 'Math', NULL);
-- result:
?column?
t
```

```sql
SELECT 'English' IN ('CS', 'Math', NULL);
-- result:
?column?
NULL
```

## `IN [val1, val2, ...]` (List)

The `IN` operator works on lists according to the semantics used in Python.
Unlike for the [`IN tuple` operator](#in-val1-val2--tuple), the presence of `NULL` values on the right hand side of the expression does not make a difference in the result:

```sql
SELECT 'Math' IN ['CS', 'Math', NULL];
-- result:
contains
t
```

```sql
SELECT 'English' IN ['CS', 'Math', NULL];
-- result:
contains
f
```

## `IN` Map

The `IN` operator works on [maps](../../../sql/data_types/map.md) according to the semantics used in Python, i.e., it checks for the presence of keys (not values):

```sql
SELECT 'key1' IN MAP {'key1': 50, 'key2': 75};
-- result:
contains
t
```

```sql
SELECT 'key3' IN MAP {'key1': 50, 'key2': 75};
-- result:
contains
f
```

## `IN` Subquery

The `IN` operator works with [subqueries](../../../sql/expressions/subqueries/index.md) that return a single column.
For example:

```sql
SELECT 42 IN (SELECT unnest([32, 42, 52]) AS x);
-- result:
?column?
t
```

If the subquery returns more than one column, a Binder Error is thrown:

```sql
SELECT 42 IN (SELECT unnest([32, 42, 52]) AS x, 'a' AS y);
-- result:
db error: ERROR: Subquery returns 2 columns - expected 1
```

## `IN` String

The `IN` operator can be used as a shorthand for the [`contains` string function](../../../sql/functions/text.md#containsstring-search_string).
For example:

```sql
SELECT 'Hello' IN 'Hello World';
-- result:
contains
t
```

## `NOT IN`

`NOT IN` can be used to check if an element is not present in the set.
`x NOT IN y` is equivalent to `NOT (x IN y)`.

