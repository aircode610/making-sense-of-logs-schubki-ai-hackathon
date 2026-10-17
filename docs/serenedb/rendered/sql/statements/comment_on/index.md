---
title: COMMENT ON
draft: true
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `COMMENT ON` statement allows adding metadata to catalog entries (tables, columns, etc.).
It follows the [PostgreSQL syntax](https://www.postgresql.org/docs/16/sql-comment.html).

## Examples

Create a comment on a `TABLE`:

```sql
COMMENT ON TABLE test_table IS 'very nice table';
```


Create a comment on a `COLUMN`:

```sql
COMMENT ON COLUMN test_table.title IS 'very nice column';
```


To unset a comment, set it to `NULL`, e.g.:

```sql
COMMENT ON TABLE test_table IS NULL;
```


Commenting on other catalog objects — views, indexes, sequences, types and macros — is not yet supported and currently returns an error.

Commenting on a `VIEW`:

```sql
COMMENT ON VIEW test_view IS 'very nice view';
```


Commenting on an `INDEX`:

```sql
COMMENT ON INDEX test_index IS 'very nice index';
```


Commenting on a `SEQUENCE`:

```sql
COMMENT ON SEQUENCE test_sequence IS 'very nice sequence';
```


Commenting on a `TYPE`:

```sql
COMMENT ON TYPE test_type IS 'very nice type';
```


Commenting on a `MACRO`:

```sql
COMMENT ON MACRO test_macro IS 'very nice macro';
```


Commenting on a `MACRO TABLE`:

```sql
COMMENT ON MACRO TABLE test_table_macro IS 'very nice table macro';
```


## Reading Comments

Comments can be read by querying the `comment` column of the respective [metadata functions](../../functions/metadata.md):

List comments on `TABLE`s:

```sql
SELECT comment FROM sdb_tables();
```


List comments on `COLUMN`s:

```sql
SELECT comment FROM sdb_columns();
```


List comments on `VIEW`s:

```sql
SELECT comment FROM sdb_views();
```


List comments on `INDEX`s:

```sql
SELECT comment FROM sdb_indexes();
```


List comments on `SEQUENCE`s:

```sql
SELECT comment FROM sdb_sequences();
```


List comments on `TYPE`s:

```sql
SELECT comment FROM sdb_types();
```


List comments on `MACRO`s:

```sql
SELECT comment FROM sdb_functions();
```


List comments on `MACRO TABLE`s:

```sql
SELECT comment FROM sdb_functions();
```


## Limitations

The `COMMENT ON` statement currently has the following limitations:

-   Comments are only supported on tables and columns. Comments on views, indexes, sequences, types and macros are not yet supported.
-   It is not possible to comment on schemas or databases.
-   It is not possible to comment on things that have a dependency (e.g., a table with an index).

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram1" />

