---
title: Casting
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

Casting refers to the operation of converting a value in a particular data type to the corresponding value in another data type.
Casting can occur either implicitly or explicitly. The syntax described here performs an explicit cast. More information on casting can be found on the [typecasting page](../../../sql/data_types/typecasting.md).

## Explicit Casting

The standard SQL syntax for explicit casting is `CAST(expr AS TYPENAME)`, where `TYPENAME` is a name (or alias) of one of [SereneDB's data types](../../../sql/data_types/index.md). SereneDB also supports the shorthand `expr::TYPENAME`, which is also present in PostgreSQL.

```sql
SELECT CAST(i AS VARCHAR) AS i
FROM generate_series(1, 3) tbl(i);
-- result:
i
1
2
3
```

```sql
SELECT i::DOUBLE AS i
FROM generate_series(1, 3) tbl(i);
-- result:
i
1
2
3
```

### Casting Rules

Not all casts are possible. For example, it is not possible to convert an `INTEGER` to a `DATE`. Casts may also throw errors when the cast could not be successfully performed. For example, trying to cast the string `'hello'` to an `INTEGER` will result in an error being thrown.

```sql
query error db error: ERROR: Could not convert string 'hello' to INT32
SELECT CAST('hello' AS INTEGER);
```

The exact behavior of the cast depends on the source and destination types. For example, when casting from `VARCHAR` to any other type, the string will be attempted to be converted.

### `TRY_CAST`

`TRY_CAST` can be used when the preferred behavior is not to throw an error, but instead to return a `NULL` value. `TRY_CAST` will never throw an error, and will instead return `NULL` if a cast is not possible.

```sql
SELECT TRY_CAST('hello' AS INTEGER) AS i;
-- result:
i
NULL
```

## `cast_to_type` Function

The `cast_to_type` function allows generating a cast from an expression to the type of another column.
For example:

```sql
SELECT cast_to_type('42', NULL::INTEGER) AS result;
-- result:
result
42
```

This function is primarily useful in [macros](../../statements/create_macro/index.md), as it allows you to maintain types.
This helps with making generic macros that operate on different types. For example, the following macro adds to a number if the input is an `INTEGER`:

```sql
CREATE TABLE tbl (i INT, s VARCHAR);

INSERT INTO tbl VALUES (42, 'hello world');

CREATE MACRO conditional_add(col, nr) AS
    CASE
        WHEN typeof(col) == 'INTEGER' THEN cast_to_type(col::INTEGER + nr, col)
        ELSE col
    END;

SELECT conditional_add(COLUMNS(*), 100) FROM tbl;
-- result:
i	s
142	hello world
```

Note that the `CASE` statement needs to return the same type in all code paths. We can perform the addition on any input column by adding a cast to the desired type – but we need to cast the result of the addition back to the source type to make the binding work.

