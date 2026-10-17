---
title: SQL Quirks
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

Like all programming languages and libraries, SereneDB has its share of idiosyncrasies and inconsistencies.  
Some are vestiges of our feathered friend's evolution; others are inevitable because we strive to adhere to the [SQL Standard](https://blog.ansi.org/sql-standard-iso-iec-9075-2023-ansi-x3-135/) and specifically to PostgreSQL's dialect (see the [“PostgreSQL Compatibility”](./core-sql-compatibility.md#behavioral-differences-from-postgresql) page for exceptions).
The rest may simply come down to different preferences, or we may even agree on what _should_ be done but just haven’t gotten around to it yet.

Acknowledging these quirks is the best we can do, which is why we have compiled below a list of examples.

## Aggregating Empty Groups

On empty groups, the aggregate functions `sum`, `list`, and `string_agg` all return `NULL` instead of `0`, `[]` and `''`, respectively. This is dictated by the SQL Standard and obeyed by all SQL implementations we know. This behavior is inherited by the list aggregate [`list_sum`](../sql/functions/list.md#list_-rewrite-functions), but not by the SereneDB original [`list_dot_product`](../sql/functions/list.md#list_inner_productlist1-list2) which returns `0` on empty lists.

## 0 vs. 1-Based Indexing

To comply with standard SQL, one-based indexing is used almost everywhere, e.g., array and string indexing and slicing, and window functions (`row_number`, `rank`, `dense_rank`). However, similarly to PostgreSQL, [JSON features use a zero-based indexing](../data_import_and_export/json/overview.md#indexing).

The index origin is 1 for strings, lists and similar types:

```sql
SELECT list[1] AS element
FROM (SELECT ['first', 'second', 'third'] AS list);
-- result:
element
first
```

The index origin is 0 for JSON objects:

```sql
SELECT (json ->> 0) AS element
FROM (SELECT '["first", "second", "third"]'::JSON AS json);
-- result:
element
first
```

## Types

### `UINT8` vs. `INT8`

`UINT8` and `INT8` are aliases to integer types of different widths:

-   `UINT8` corresponds to `UTINYINT` because it's an _8-bit_ unsigned integer
-   `INT8` corresponds to `BIGINT` because it's an _8-byte_ signed integer

Explanation: the `n` in the numeric type `INTn` and `UINTn` denote the width of the number in either bytes or bits.
`INT1`, `INT2`, `INT4` correspond to the number of bytes, while `INT16`, `INT32` and `INT64` correspond to the number of bits.
The same applies to `UINT` values.
However, the value `n = 8` is a valid choice for both the number of bits and bytes.
For unsigned values, `UINT8` corresponds to `UTINYINT` (8 bits).
For signed values, `INT8` corresponds to `BIGINT` (8 bytes).

## Expressions

### Results That May Surprise You

Each expression below is evaluated on both engines — the PostgreSQL column runs it on an attached PostgreSQL, the SereneDB column locally. Where the columns match, SereneDB is PostgreSQL-compatible; where they differ — `1 = true` and `1 = '1.1'`, which PostgreSQL rejects but SereneDB coerces to `true` — it is not:

```sql
ATTACH 'host=localhost port=5432 dbname=mydb user=postgres' AS pg (TYPE postgres);

SELECT '-2^2' AS "Expression", (SELECT r FROM postgres_query('pg', 'SELECT (-2^2)::text r')) AS "PostgreSQL", (-2^2)::VARCHAR AS "SereneDB"
UNION ALL SELECT '''t'' = true',  (SELECT r FROM postgres_query('pg', 'SELECT (''t'' = true)::text r')),  ('t' = true)::VARCHAR
UNION ALL SELECT '1 = ''1''',     (SELECT r FROM postgres_query('pg', 'SELECT (1 = ''1'')::text r')),     (1 = '1')::VARCHAR
UNION ALL SELECT '1 = '' 1''',    (SELECT r FROM postgres_query('pg', 'SELECT (1 = '' 1'')::text r')),    (1 = ' 1')::VARCHAR
UNION ALL SELECT '1 = ''01''',    (SELECT r FROM postgres_query('pg', 'SELECT (1 = ''01'')::text r')),    (1 = '01')::VARCHAR
UNION ALL SELECT '1 = '' 01 ''',  (SELECT r FROM postgres_query('pg', 'SELECT (1 = '' 01 '')::text r')),  (1 = ' 01 ')::VARCHAR
UNION ALL SELECT '1 = true',      'error',                                                                (1 = true)::VARCHAR
UNION ALL SELECT '1 = ''1.1''',   'error',                                                                (1 = '1.1')::VARCHAR
UNION ALL SELECT '1 IN (0, NULL)',(SELECT r FROM postgres_query('pg', 'SELECT (1 IN (0, NULL))::text r')),(1 IN (0, NULL))::VARCHAR
UNION ALL SELECT 'concat(''abc'', NULL)', (SELECT r FROM postgres_query('pg', 'SELECT concat(''abc'', NULL) r')), concat('abc', NULL)::VARCHAR
UNION ALL SELECT '''abc'' || NULL',(SELECT r FROM postgres_query('pg', 'SELECT (''abc'' || NULL)::text r')),('abc' || NULL)::VARCHAR;
```

A couple of notes:

- `-2^2` returns `4` because unary minus binds tighter than `^` (the same as PostgreSQL); use `-(2^2)` or [`-pow(2, 2)`](../sql/functions/numeric.md#powx-y) to get `-4`.
- `1 IN (0, NULL)` is `NULL` (think of the `NULL` as `UNKNOWN`), but SereneDB's list form `1 IN [0, NULL]` returns `false`:

```sql
SELECT 1 IN (0, NULL) AS "IN (set)", 1 IN [0, NULL] AS "IN [list]";
-- result:
IN (set)	IN [list]
NULL	f
```

### `NaN` Values

`'NaN'::FLOAT = 'NaN'::FLOAT` and `'NaN'::FLOAT > 3` violate IEEE-754 but mean floating point data types have a total order, like all other data types (beware the consequences for `greatest` / `least`).

### `age` Function

`age(x)` is `current_date - x` instead of `current_timestamp - x`. Another quirk inherited from PostgreSQL.

### Extract Functions

`list_extract` / `map_extract` return `NULL` on non-existing keys. `struct_extract` throws an error because keys of structs are like columns.

## Clauses

### Automatic Column Deduplication in `SELECT`

Column names are deduplicated with the first occurrence shadowing the others:

```sql
CREATE TABLE tbl AS SELECT 1 AS a;

SELECT a FROM (SELECT *, 2 AS a FROM tbl);
-- result:
a
1
```

### Case Insensitivity for `SELECT`ing Columns

Due to case-insensitivity, it's not possible to use `SELECT a FROM 'file.parquet'` when a column called `A` appears before the desired column `a` in `file.parquet`.

### `USING SAMPLE`

The `USING SAMPLE` clause is syntactically placed after the `WHERE` and `GROUP BY` clauses (same as the `LIMIT` clause) but is semantically applied before both (unlike the `LIMIT` clause).

