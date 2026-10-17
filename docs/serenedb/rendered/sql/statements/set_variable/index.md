---
title: SET / RESET VARIABLE
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

SereneDB supports the definition of SQL-level variables using the `SET VARIABLE` and `RESET VARIABLE` statements.

## Variable Scopes

SereneDB supports two levels of variable scopes:

| Scope     | Description                                                                                                                                                                                                                                                                                              |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSION` | Variables with a `SESSION` scope are local to you and only affect the current session.                                                                                                                                                                                                                   |
| `GLOBAL`  | Variables with a `GLOBAL` scope are specific [configuration option variables](../../../configuration/overview.md#global-configuration-options) that affect the entire SereneDB instance and all sessions. For example, see [Set a Global Variable](../../statements/set/index.md#set-a-global-variable). |

## `SET VARIABLE`

The `SET VARIABLE` statement assigns a value to a variable, which can be accessed using the `getvariable` call:

```sql
SET VARIABLE my_var = 30;

SELECT 20 + getvariable('my_var') AS total;
-- result:
total
50
```

If `SET VARIABLE` is invoked on an existing variable, it will overwrite its value:

```sql
SET VARIABLE my_var = 30;

SET VARIABLE my_var = 100;

SELECT 20 + getvariable('my_var') AS total;
-- result:
total
120
```

Variables can have different types:

```sql
SET VARIABLE my_date = DATE '2018-07-13';

SET VARIABLE my_string = 'Hello world';

SET VARIABLE my_map = MAP {'k1': 10, 'k2': 20};
```

Variables can also be assigned to results of queries:

```sql
-- write some CSV files
COPY (SELECT 42 AS a) TO 'test1.csv' (HEADER);

COPY (SELECT 84 AS a) TO 'test2.csv' (HEADER);

-- add a list of CSV files to a table
CREATE TABLE csv_files (file VARCHAR);

INSERT INTO csv_files VALUES ('test1.csv'), ('test2.csv');

-- initialize a variable with the list of csv files
SET VARIABLE list_of_files = (SELECT list(file) FROM csv_files);

-- read the CSV files
SELECT * FROM read_csv(getvariable('list_of_files'), filename := True);
```

If a variable is not set, the `getvariable` function returns `NULL`:

```sql
SELECT getvariable('undefined_var') AS result;
-- result:
result
NULL
```

The `getvariable` function can also be used in a [`COLUMNS` expression](../../expressions/star/index.md#columns-expression):

```sql
SET VARIABLE column_to_exclude = 'col1';

CREATE TABLE tbl AS SELECT 12 AS col0, 34 AS col1, 56 AS col2;

SELECT COLUMNS(c -> c != getvariable('column_to_exclude')) FROM tbl;
-- result:
col0	col2
12	56
```

### Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram1" />

## `RESET VARIABLE`

The `RESET VARIABLE` statement unsets a variable.

```sql
SET VARIABLE my_var = 30;

RESET VARIABLE my_var;

SELECT getvariable('my_var') AS my_var;
-- result:
my_var
NULL
```

### Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram2" />

