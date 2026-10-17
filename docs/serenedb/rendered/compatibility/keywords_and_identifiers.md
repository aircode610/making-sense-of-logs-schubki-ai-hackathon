---
title: Keywords and Identifiers
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

## Identifiers

Similarly to other SQL dialects and programming languages, identifiers in SereneDB's SQL are subject to several rules.

-   Unquoted identifiers need to conform to a number of rules:
    -   They must not be a reserved keyword (see [`sdb_keywords()`](../sql/functions/metadata.md#sdb_keywords)), e.g., `SELECT 123 AS SELECT` will fail.
    -   They must not start with a number or special character, e.g., `SELECT 123 AS 1col` is invalid.
    -   They cannot contain whitespaces (including tabs and newline characters).
-   Identifiers can be quoted using double-quote characters (`"`). Quoted identifiers can use any keyword, whitespace or special character, e.g., `"SELECT"` and `" § 🌊 ¶ "` are valid identifiers.
-   Double quotes can be escaped by repeating the quote character, e.g., to create an identifier named `IDENTIFIER "X"`, use `"IDENTIFIER ""X"""`.

### Duplicate Identifiers

In some cases, duplicate identifiers can occur, e.g., column names may conflict when unnesting a nested data structure.
Following PostgreSQL, SereneDB allows duplicate column names in a result and preserves them as-is — they are not renamed or deduplicated.

For example, recursively unnesting a struct whose nested fields repeat a name yields a result with repeated column names:

```sql
SELECT *
FROM (SELECT unnest({'a': 42, 'b': {'a': 88, 'b': 99}}, recursive := true));
-- result:
a	a	b
42	88	99
```

## Database Names

Database names are subject to the rules for [identifiers](#identifiers).

Additionally, it is best practice to avoid SereneDB's two internal [database schema names](../sql/functions/metadata.md#sdb_databases), `system` and `temp`.
By default, persistent databases are named after their filename without the extension.
Therefore, the filenames `system.db` and `temp.db` (as well as `system.duckdb` and `temp.duckdb`) result in the database names `system` and `temp`, respectively.
If you need to attach to a database that has one of these names, use an alias, e.g.:

```sql
ATTACH 'temp.db' AS temp2;

USE temp2;
```

## Rules for Case-Sensitivity

### Keywords and Function Names

SQL keywords and function names are case-insensitive in SereneDB.

For example, the following two queries are equivalent:

```sql
select COS(Pi()) as CosineOfPi;
-- result:
cosineofpi
-1

SELECT cos(pi()) AS CosineOfPi;
-- result:
cosineofpi
-1
```

### Case-Sensitivity of Identifiers

A SereneDB server follows PostgreSQL's rules for the names of tables, columns and other catalog objects:

- An unquoted identifier folds to lowercase: `CREATE TABLE MyTable` creates `mytable`, which `FROM MYTABLE` also finds.
- A quoted identifier keeps its case and matches only that spelling: after `CREATE TABLE "MyTable"`, only `FROM "MyTable"` finds the table, and after `CREATE TABLE MyTable`, `FROM "MyTable"` fails.

Aliases inside one query, such as the output columns of a subquery, match regardless of case.

**Comparison of identifiers:**
Case folding is ASCII-based:
`col_A` and `col_a` are equal but `col_á` is not equal to them.

```sql
SELECT col_A FROM (SELECT 'x' AS col_a);
-- result:
col_a
x

SELECT col_á FROM (SELECT 'x' AS col_a);
-- result:
db error: ERROR: Referenced column "col_á" not found in FROM clause!
Candidate bindings: "col_a"
```

**Stored names:**
Because unquoted names fold, the column below is stored as `cosineofpi`:

```sql
CREATE TABLE tbl AS SELECT cos(pi()) AS CosineOfPi;

SELECT cosineofpi FROM tbl;
-- result:
cosineofpi
-1
```

`serened shell` keeps DuckDB's behavior instead: identifiers are case-insensitive even when quoted, and they keep the case they were created with. A server session gets the same by setting the `preserve_identifier_case` [configuration option](../configuration/overview.md#configuration-reference) to `true`.

### Case-Sensitivity of Keys in Nested Data Structures

The keys of `MAP`s are case-sensitive (looking up `A` when the key is `a` finds nothing):

```sql
SELECT (MAP {'a': 1})['A'] IS NOT NULL AS found;
-- result:
found
f
```

The keys of `UNION`s and `STRUCT`s are case-insensitive:

```sql
SELECT union_extract(union_value(a := 1), 'A') IS NOT NULL AS found;
-- result:
found
t
```

```sql
SELECT ({'a': 1}).A IS NOT NULL AS found;
-- result:
found
t
```

#### Handling Conflicts

When the same identifier is spelt with different cases within a nested structure, SereneDB raises an error rather than silently picking one. For example:

```sql
query error
SELECT {'a': 1, 'A': 2};
-- result:
db error: ERROR: Duplicate named argument "A" in function call to "struct_pack"


USE $__DATABASE__;

DETACH IF EXISTS db91;
```

#### Disabling Preserving Cases

With the `preserve_identifier_case` [configuration option](../configuration/overview.md#configuration-reference) set to `false`, the server's default, unquoted identifiers are turned into lowercase:

```sql
SET preserve_identifier_case = false;

CREATE TABLE tbl AS SELECT cos(pi()) AS CosineOfPi;

SELECT CosineOfPi FROM tbl;
-- result:
cosineofpi
-1
```

