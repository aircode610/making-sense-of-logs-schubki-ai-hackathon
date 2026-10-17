---
title: DESCRIBE
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `DESCRIBE` statement shows the schema of a table, view or query.

## Usage

```sql
DESCRIBE TABLE tbl;
-- result:
column_name	column_type	null	key	default	extra
id	INTEGER	YES	NULL	NULL	NULL
name	VARCHAR	YES	NULL	NULL	NULL
col1	DOUBLE	YES	NULL	NULL	NULL
col2	DOUBLE	YES	NULL	NULL	NULL
Some Column Name	VARCHAR	YES	NULL	NULL	NULL
i	INTEGER	YES	NULL	NULL	NULL
a	INTEGER	YES	NULL	NULL	NULL
b	INTEGER	YES	NULL	NULL	NULL
c	INTEGER	YES	NULL	NULL	NULL
number	INTEGER	YES	NULL	NULL	NULL
number1	INTEGER	YES	NULL	NULL	NULL
number2	INTEGER	YES	NULL	NULL	NULL
```

To describe a query, prepend `DESCRIBE` to a query.

```sql
DESCRIBE SELECT * FROM tbl;
-- result:
column_name	column_type	null	key	default	extra
id	INTEGER	YES	NULL	NULL	NULL
name	VARCHAR	YES	NULL	NULL	NULL
col1	DOUBLE	YES	NULL	NULL	NULL
col2	DOUBLE	YES	NULL	NULL	NULL
Some Column Name	VARCHAR	YES	NULL	NULL	NULL
i	INTEGER	YES	NULL	NULL	NULL
a	INTEGER	YES	NULL	NULL	NULL
b	INTEGER	YES	NULL	NULL	NULL
c	INTEGER	YES	NULL	NULL	NULL
number	INTEGER	YES	NULL	NULL	NULL
number1	INTEGER	YES	NULL	NULL	NULL
number2	INTEGER	YES	NULL	NULL	NULL
```

## Alias

`SHOW TABLE <name>` returns the same as `DESCRIBE TABLE <name>`. A name after `SHOW` without the `TABLE` keyword is read as a setting instead: see [`SHOW`](show.md).

## See Also

For more examples, see the [guide on `DESCRIBE`](../../cookbook/meta/describe.md).

