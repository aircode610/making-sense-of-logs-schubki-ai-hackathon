---
title: Enum Functions
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

<!-- markdownlint-disable MD001 -->

This section describes functions and operators for examining and manipulating [`ENUM` values](../../sql/data_types/enum.md).
The examples assume an enum type created as:

```sql
CREATE TYPE mood AS ENUM ('sad', 'ok', 'happy', 'anxious');
```

These functions can take `NULL` or a specific value of the type as argument(s).
With the exception of `enum_range_boundary`, the result depends only on the type of the argument and not on its value.

| Name                                                               | Description                                                      |
| :----------------------------------------------------------------- | :--------------------------------------------------------------- |
| [`enum_code(enum_value)`](#enum_codeenum_value)                    | Returns the numeric value backing the given enum value.          |
| [`enum_first(enum)`](#enum_firstenum)                              | Returns the first value of the input enum type.                  |
| [`enum_last(enum)`](#enum_lastenum)                                | Returns the last value of the input enum type.                   |
| [`enum_range(enum)`](#enum_rangeenum)                              | Returns all values of the input enum type as an array.           |
| [`enum_range_boundary(enum, enum)`](#enum_range_boundaryenum-enum) | Returns the range between the two given enum values as an array. |

#### `enum_code(enum_value)`

Returns the numeric value backing the given enum value.

```sql
SELECT enum_code('happy'::mood) AS enum_code;
-- result:
enum_code
2
```

#### `enum_first(enum)`

Returns the first value of the input enum type.

```sql
SELECT enum_first(NULL::mood) AS enum_first;
-- result:
enum_first
sad
```

#### `enum_last(enum)`

Returns the last value of the input enum type.

```sql
SELECT enum_last(NULL::mood) AS enum_last;
-- result:
enum_last
anxious
```

#### `enum_range(enum)`

Returns all values of the input enum type as an array.

```sql
SELECT enum_range(NULL::mood) AS enum_range;
-- result:
enum_range
{sad,ok,happy,anxious}
```

#### `enum_range_boundary(enum, enum)`

Returns the range between the two given enum values as an array. The values must be of the same enum type. When the first parameter is `NULL`, the result starts with the first value of the enum type. When the second parameter is `NULL`, the result ends with the last value of the enum type.

```sql
SELECT enum_range_boundary(NULL, 'happy'::mood) AS enum_range_boundary;
-- result:
enum_range_boundary
{sad,ok,happy}
```

