---
title: Writing JSON
sidebar_position: 3
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The contents of tables or the result of queries can be written directly to a JSON file using the `COPY` statement.
For example:

```sql
CREATE TABLE cities AS
    FROM (VALUES ('Amsterdam', 1), ('London', 2)) cities(name, id);

COPY cities TO 'cities.json';
```

This writes `cities.json` with one JSON object per line. Reading the file back shows its contents:

```sql
SELECT unnest(string_split(rtrim(content, chr(10)), chr(10))) AS line
FROM read_text('cities.json');
-- result:
line
{"name":"Amsterdam","id":1}
{"name":"London","id":2}
```

See the [`COPY` statement](../../sql/statements/copy/index.md#copy--to) for more information.

