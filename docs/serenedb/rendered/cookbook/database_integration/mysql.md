---
draft: true
layout: docu
redirect_from:
- /docs/guides/database_integration/mysql
- /docs/guides/import/query_mysql
- /docs/preview/guides/database_integration/mysql
- /docs/stable/guides/database_integration/mysql
title: MySQL Import
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

## Usage

You can attach to a MySQL database using the following command:

```sql
ATTACH 'host=localhost user=root port=0 database=mysqlscanner' AS mysql_db (TYPE mysql, READ_ONLY);
-- result:
db error: ERROR: LOAD is not supported by SereneDB: extensions are compiled into the server binary and cannot be loaded at runtime.
If you need the "mysql_scanner" extension, please open an issue at https://github.com/serenedb/serenedb/issues/887.
```

The string used by `ATTACH` is a PostgreSQL-style connection string (_not_ a MySQL connection string!). It is a list of connection arguments provided in `{key}={value}` format. Below is a list of valid arguments. Any options not provided are replaced by their default values.

|  Setting   |   Default    |
|------------|--------------|
| `database` | `NULL`       |
| `host`     | `localhost`  |
| `password` |              |
| `port`     | `0`          |
| `socket`   | `NULL`       |
| `user`     | current user |

You can directly read and write the MySQL database:

```sql
INSERT INTO mysql_db.tbl VALUES (42, 'SereneDB');
-- result:
db error: ERROR: Table with name "mysql_db.tbl" does not exist because schema "mysql_db" does not exist.


query error
SELECT * FROM mysql_db.tbl;
-- result:
db error: ERROR: Table with name "mysql_db.tbl" does not exist because schema "mysql_db" does not exist.
```

