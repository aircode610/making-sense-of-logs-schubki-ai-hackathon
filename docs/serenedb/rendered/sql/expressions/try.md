---
title: TRY
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

The `TRY` expression ensures that errors caused by the input rows in the child (scalar) expression result in `NULL` for those rows, instead of causing the query to throw an error.

<DocCallout type="tip">
The `TRY` expression was inspired by the [`TRY_CAST` expression](../../sql/expressions/cast/index.md#try_cast).
</DocCallout>

## Examples

The following calls return errors when invoked without the `TRY` expression.
When they are wrapped into a `TRY` expression, they return `NULL`:

### Casting

#### Without `TRY`

```sql
query error
SELECT 'abc'::INTEGER;
-- result:
db error: ERROR: Could not convert string 'abc' to INT32
```

#### With `TRY`

```sql
SELECT TRY('abc'::INTEGER);
-- result:
?column?
NULL
```

### Integer Overflow

#### Without `TRY`

```sql
query error
SELECT 127::TINYINT + 1::TINYINT;
-- result:
db error: ERROR: Overflow in addition of INT8 (127 + 1)!
```

#### With `TRY`

```sql
SELECT TRY(127::TINYINT + 1::TINYINT);
-- result:
?column?
NULL
```

### Casting Multiple Rows

#### Without `TRY`

```sql
query error
WITH cte AS (FROM (VALUES ('123'), ('test'), ('235')) t(a))
SELECT a::INTEGER AS x FROM cte;
-- result:
db error: ERROR: Could not convert string 'test' to INT32 when casting from source column a
```

#### With `TRY`

<div className="docs-table-centered">

```sql
WITH cte AS (FROM (VALUES ('123'), ('test'), ('235')) t(a))
SELECT TRY(a::INTEGER) AS x FROM cte;
-- result:
x
123
NULL
235
```

</div>

## Limitations

`TRY` cannot be used in combination with a volatile function, an aggregate function, or a [scalar subquery](../../sql/expressions/subqueries/index.md#scalar-subquery).
For example:

```sql
query error
SELECT TRY(random())
-- result:
db error: ERROR: TRY can not be used in combination with a volatile function
```

