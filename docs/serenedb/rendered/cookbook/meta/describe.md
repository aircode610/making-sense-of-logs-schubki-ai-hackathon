---
layout: docu
redirect_from:
    - /docs/guides/meta/describe
    - /docs/preview/guides/meta/describe
    - /docs/stable/guides/meta/describe
title: Describe
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

## Describing a Table

To view the schema of a table, use `DESCRIBE TABLE` or `SHOW TABLE` followed by the table name. Without the `TABLE` keyword, a name after `SHOW` is read as a setting, not as a table (see [`SHOW`](../../sql/statements/show.md)).

```sql
CREATE TABLE tbl (i INTEGER PRIMARY KEY, j VARCHAR);

DESCRIBE TABLE tbl;
-- result:
column_name	column_type	null	key	default	extra
i	INTEGER	NO	PRI	NULL	NULL
j	VARCHAR	YES	NULL	NULL	NULL

SHOW TABLE tbl;
-- result:
column_name	column_type	null	key	default	extra
i	INTEGER	NO	PRI	NULL	NULL
j	VARCHAR	YES	NULL	NULL	NULL
```

## Describing a Query

To view the schema of the result of a query, prepend `DESCRIBE` to a query.

```sql
DESCRIBE SELECT * FROM tbl;
-- result:
column_name	column_type	null	key	default	extra
i	INTEGER	NO	PRI	NULL	NULL
j	VARCHAR	YES	NULL	NULL	NULL
```

## Using `DESCRIBE` in a Subquery

`DESCRIBE` can be used as a subquery. This allows creating a table from the description, for example:

```sql
CREATE TABLE tbl_description AS SELECT * FROM (DESCRIBE TABLE tbl);
```

## Describing Remote Tables

It is possible to describe remote tables over HTTP(S) and S3 using the `DESCRIBE TABLE` statement. For example:

```sql
DESCRIBE TABLE 'https://example.com/data.csv';
```

