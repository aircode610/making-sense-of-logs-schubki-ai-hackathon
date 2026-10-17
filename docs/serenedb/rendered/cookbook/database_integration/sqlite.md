---
layout: docu
redirect_from:
- /docs/guides/database_integration/sqlite
- /docs/guides/import/query_sqlite
- /docs/preview/guides/database_integration/sqlite
- /docs/stable/guides/database_integration/sqlite
title: SQLite Import
draft: true
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

## Usage

Tables can be queried from SQLite using the `sqlite_scan` function:

```sql
-- Scan the table "tbl_name" from the SQLite file "test.db"
SELECT * FROM sqlite_scan('⟨test.db⟩', '⟨tbl_name⟩');
```

Alternatively, the entire file can be attached using the `ATTACH` command. This allows you to query all tables stored within a SQLite database file as if they were a regular database.

```sql
-- Attach the SQLite file "test.db"
ATTACH '⟨test.db⟩' AS test (TYPE sqlite);
```

