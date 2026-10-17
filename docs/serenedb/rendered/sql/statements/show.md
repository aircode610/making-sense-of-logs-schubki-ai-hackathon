---
title: SHOW
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `SHOW` statement inspects the database — it lists tables, databases and schemas, shows the schema of a relation and displays the values of session variables.

## `SHOW`

`SHOW TABLE <name>` returns the columns of a table and their types, the same as [`DESCRIBE TABLE <name>`](describe.md). Without the `TABLE` keyword, a name after `SHOW` is read as a setting, even if a table of that name exists: a server sets [`show_behavior`](../../configuration/overview.md) to `SETTING`, so `SHOW <name>` shows the setting `<name>` (see [Session variables](#session-variables)).

## `SHOW TABLES`

`SHOW TABLES` lists the tables in the current database and schema:

```sql
SHOW TABLES;
-- result:
name
products
```

Use `SHOW TABLES FROM <database>` to list the tables of another attached database.

## `SHOW DATABASES`

`SHOW DATABASES` lists every attached database. This includes SereneDB's internal catalogs — the transactional store (`__sdb_store`) and the default in-memory database (`memory`) — alongside your own databases:

```sql
SHOW DATABASES;
```

## `SHOW SCHEMAS`

`SHOW SCHEMAS` lists the schemas of every attached database, internal catalogs included:

```sql
SHOW SCHEMAS;
```

Each row pairs a database with one of its schemas; the `current` column marks the default schema, set via the [`USE`](use/index.md) statement.

## Session variables

`SHOW <variable>` displays the current value of a session variable:

```sql
SHOW search_path;
-- result:
search_path
"$user", public
```

`SHOW ALL` displays every variable with its value and description:

```sql
SHOW ALL;

DETACH IF EXISTS db81;
```

## See also

- [DESCRIBE](describe.md) — the columns of a table or query; `SHOW TABLE <name>` is the same as `DESCRIBE TABLE <name>`
- [SET](set/index.md) — change a session variable

