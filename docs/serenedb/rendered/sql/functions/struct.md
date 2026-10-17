---
title: Struct Functions
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

<!-- markdownlint-disable MD001 -->

| Name                                                                         | Description                                                                                                              |
| :--------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------- |
| [`struct.entry`](#structentry)                                               | Dot notation that serves as an alias for `struct_extract` from named `STRUCT`s.                                          |
| [`struct[entry]`](#structentry-bracket)                                      | Bracket notation that serves as an alias for `struct_extract` from named `STRUCT`s.                                      |
| [`struct[idx]`](#structidx)                                                  | Bracket notation that serves as an alias for `struct_extract` from unnamed `STRUCT`s (tuples), using an index (1-based). |
| [`row(any, ...)`](#rowany-)                                                  | Create an unnamed `STRUCT` (tuple) containing the argument values.                                                       |
| [`struct_concat(structs...)`](#struct_concatstructs)                         | Merge the multiple `structs` into a single `STRUCT`.                                                                     |
| [`struct_contains(struct, entry)`](#struct_containsstruct-entry)             | Check if the `STRUCT` contains the specified entry.                                                                      |
| [`struct_extract(struct, 'entry')`](#struct_extractstruct-entry)             | Extract the named entry from the `STRUCT`.                                                                               |
| [`struct_extract(struct, idx)`](#struct_extractstruct-idx)                   | Extract the entry from an unnamed `STRUCT` (tuple) using an index (1-based).                                             |
| [`struct_extract_at(struct, idx)`](#struct_extract_atstruct-idx)             | Extract the entry from a `STRUCT` (tuple) using an index (1-based).                                                      |
| [`struct_insert(struct, name := any, ...)`](#struct_insertstruct-name--any-) | Add field(s) to an existing `STRUCT`.                                                                                    |
| [`struct_pack(name := any, ...)`](#struct_packname--any-)                    | Create a `STRUCT` containing the argument values. The entry name will be the bound variable name.                        |
| [`struct_position(struct, entry)`](#struct_positionstruct-entry)             | Return the index of the entry within the `STRUCT` (1-based), or `NULL` if not found.                                     |
| [`struct_update(struct, name := any, ...)`](#struct_updatestruct-name--any-) | Add or update field(s) of an existing `STRUCT`.                                                                          |
| [`struct_values(struct)`](#struct_valuesstruct)                              | Return the values of a `STRUCT` as an unnamed `STRUCT` (tuple).                                                          |

#### `struct.entry` {#structentry}

Dot notation that serves as an alias for `struct_extract` from named `STRUCT`s.

```sql
SELECT ({'i': 3, 's': 'string'}).i AS i;
-- result:
i
3
```

#### `struct[entry]` {#structentry-bracket}

Bracket notation that serves as an alias for `struct_extract` from named `STRUCT`s.

```sql
SELECT ({'i': 3, 's': 'string'})['i'] AS i;
-- result:
i
3
```

#### `struct[idx]`

Bracket notation that serves as an alias for `struct_extract` from unnamed `STRUCT`s (tuples), using an index (1-based).

```sql
SELECT (row(42, 84))[1] AS first;
-- result:
first
42
```

#### `row(any, ...)`

Create an unnamed `STRUCT` (tuple) containing the argument values.

```sql
SELECT row(i, i % 4, i / 4) AS r FROM (SELECT 10 AS i);
-- result:
r
(10,2,2)
```

#### `struct_concat(structs...)`

Merge the multiple `structs` into a single `STRUCT`.

```sql
SELECT struct_concat(struct_pack(i := 4), struct_pack(s := 'string')) AS s;
-- result:
s
(4,string)
```

#### `struct_contains(struct, entry)`

Check if the `STRUCT` contains the specified entry. Alias: `struct_has`.

```sql
SELECT struct_contains(row(1, 2, 3), 2) AS contains;
-- result:
contains
t
```

#### `struct_extract(struct, 'entry')`

Extract the named entry from the `STRUCT`.

```sql
SELECT struct_extract({'i': 3, 'v2': 3, 'v3': 0}, 'i') AS i;
-- result:
i
3
```

#### `struct_extract(struct, idx)`

Extract the entry from an unnamed `STRUCT` (tuple) using an index (1-based).

```sql
SELECT struct_extract(row(42, 84), 1) AS first;
-- result:
first
42
```

#### `struct_extract_at(struct, idx)`

Extract the entry from a `STRUCT` (tuple) using an index (1-based).

```sql
SELECT struct_extract_at({'v1': 10, 'v2': 20, 'v3': 3}, 2) AS v;
-- result:
v
20
```

#### `struct_insert(struct, name := any, ...)`

Add field(s) to an existing `STRUCT`.

```sql
SELECT struct_insert({'a': 1}, b := 2) AS s;
-- result:
s
(1,2)
```

#### `struct_pack(name := any, ...)`

Create a `STRUCT` containing the argument values. The entry name will be the bound variable name.

```sql
SELECT struct_pack(i := 4, s := 'string') AS s;
-- result:
s
(4,string)
```

#### `struct_position(struct, entry)`

Return the index of the entry within the `STRUCT` (1-based), or `NULL` if not found. Alias: `struct_indexof`.

```sql
SELECT struct_position(row(1, 2, 3), 2) AS pos;
-- result:
pos
2
```

#### `struct_update(struct, name := any, ...)`

Add or update field(s) of an existing `STRUCT`.

```sql
SELECT struct_update({'a': 1, 'b': 2}, b := 3, c := 4) AS s;
-- result:
s
(1,3,4)
```

#### `struct_values(struct)`

Return the values of a `STRUCT` as an unnamed `STRUCT` (tuple).

```sql
SELECT struct_values({'a': 1, 'b': 2, 'c': 3}) AS vals;
-- result:
vals
(1,2,3)
```

