---
layout: docu
redirect_from:
- /docs/guides/meta/list_tables
- /docs/preview/guides/meta/list_tables
- /docs/stable/guides/meta/list_tables
title: List Tables
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `SHOW TABLES` command can be used to obtain a list of all tables within the selected schema.

```sql
CREATE TABLE tbl (i INTEGER);

SHOW TABLES;
```

`SHOW` or `SHOW ALL TABLES` can be used to obtain a list of all tables within **all** attached databases and schemas.

```sql
CREATE TABLE tbl (i INTEGER);

CREATE SCHEMA s1;

CREATE TABLE s1.tbl (v VARCHAR);

SHOW ALL TABLES;
-- result:
database	schema	name	column_names	column_types	temporary
postgres	public	tbl	{i}	{INTEGER}	f
postgres	s1	tbl	{v}	{VARCHAR}	f
```

`SHOW TABLES FROM db` can be used to list all tables in a given database or schema.

```sql
ATTACH 'db.duckdb';

CREATE TABLE db.main_tbl (u VARCHAR);

CREATE SCHEMA db.s1;

CREATE TABLE db.s1.schema_tbl (v VARCHAR);

SHOW TABLES FROM db;
```

Or a specific schema.

```sql
SHOW TABLES FROM db61.s1;
-- result:
name
schema_tbl

DETACH IF EXISTS db61;
```

To view the schema of an individual table, use the [`DESCRIBE` command](./describe.md).

## See Also

The SQL-standard [`information_schema`](../../sql/information_schema.md) views are also defined. Moreover, SereneDB defines `sqlite_master` and many [PostgreSQL system catalog tables](https://www.postgresql.org/docs/18/catalogs.html) for compatibility with SQLite and PostgreSQL respectively.

