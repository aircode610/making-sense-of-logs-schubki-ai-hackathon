---
layout: docu
redirect_from:
- /docs/guides/file_formats/json_export
- /docs/guides/import/json_export
- /docs/preview/guides/file_formats/json_export
- /docs/stable/guides/file_formats/json_export
title: JSON Export
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

To export the data from a table to a JSON file, use the `COPY` statement:

```sql
COPY tbl TO 'output.json';
```

The result of queries can also be directly exported to a JSON file. Reading the file back shows its contents:

```sql
COPY (SELECT * FROM range(3) tbl(n)) TO 'output.json';
```

```sql
SELECT unnest(string_split(rtrim(content, chr(10)), chr(10))) AS line
FROM read_text('output.json');
-- result:
line
{"n":0}
{"n":1}
{"n":2}
```

The JSON export writes JSON lines by default, standardized as [Newline-delimited JSON](https://en.wikipedia.org/wiki/JSON_streaming#NDJSON).
The `ARRAY` option can be used to write a single JSON array object instead; reading it back yields the same rows:

```sql
COPY (SELECT * FROM range(3) tbl(n)) TO 'output.json' (ARRAY);
```

```sql
SELECT n FROM read_json('output.json') ORDER BY n;
-- result:
n
0
1
2
```

For additional options, see the [`COPY` statement documentation](../../sql/statements/copy/index.md).

