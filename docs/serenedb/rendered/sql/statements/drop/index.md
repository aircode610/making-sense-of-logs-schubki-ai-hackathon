---
title: DROP
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `DROP` statement removes a catalog entry added previously with the `CREATE` command.

## Examples

Delete the table with the name `tbl`:

```sql
DROP TABLE tbl;
```

Drop the view with the name `view1`; do not throw an error if the view does not exist:

```sql
DROP VIEW IF EXISTS view1;
```

Drop function `fn`:

```sql
DROP FUNCTION fn;
```

Drop index `idx`:

```sql
DROP INDEX idx;
```

Drop schema `sch`:

```sql
DROP SCHEMA sch;
```

Drop sequence `seq`:

```sql
DROP SEQUENCE seq;
```

Drop macro `mcr`:

```sql
DROP MACRO mcr;
```

Drop macro table `mt`:

```sql
DROP MACRO TABLE mt;
```

Drop type `typ`:

```sql
DROP TYPE typ;
```

Drop text search dictionary `dict`:

```sql
DROP TEXT SEARCH DICTIONARY dict;
```

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

## Dependencies of Dropped Objects

SereneDB performs limited dependency tracking for some object types.
By default or if the `RESTRICT` clause is provided, the entry will not be dropped if there are any other objects that depend on it.
If the `CASCADE` clause is provided then all the objects that are dependent on the object will be dropped as well.

```sql
CREATE SCHEMA myschema;

CREATE TABLE myschema.t1 (i INTEGER);

DROP SCHEMA myschema;
```

The `CASCADE` modifier drops both myschema and `myschema.t1`:

```sql
CREATE SCHEMA myschema;

CREATE TABLE myschema.t1 (i INTEGER);

DROP SCHEMA myschema CASCADE;
```

The following dependencies are tracked and thus will raise an error if the user tries to drop the depending object without the `CASCADE` modifier.

| Depending object type | Dependent object type |
| --------------------- | --------------------- |
| `SCHEMA`              | `FUNCTION`            |
| `SCHEMA`              | `MACRO TABLE`         |
| `SCHEMA`              | `MACRO`               |
| `SCHEMA`              | `SCHEMA`              |
| `SCHEMA`              | `SEQUENCE`            |
| `SCHEMA`              | `TABLE`               |
| `SCHEMA`              | `TYPE`                |
| `SCHEMA`              | `VIEW`                |
| `TABLE`               | `VIEW`                |
| `TEXT SEARCH DICTIONARY` | `INDEX`            |

### Dependencies on Views

Views that reference a table are tracked as dependents of that table. If a view references a table and the table is dropped with `RESTRICT` (the default), then the drop is rejected and the view stays valid:

```sql
CREATE TABLE tbl (i INTEGER);

CREATE VIEW view1 AS
    SELECT i FROM tbl;

DROP TABLE tbl RESTRICT;
-- result:
db error: ERROR: Cannot drop entry "tbl" because there are entries that depend on it.
view "view1" depends on table "tbl".
Use DROP...CASCADE to drop all dependents.


SELECT * FROM view1;
-- result:
i
```

## Limitations on Reclaiming Disk Space

Running `DROP TABLE` should free the memory used by the table, but not always disk space.
Even if disk space does not decrease, the free blocks will be marked as `free`.
For example, if we have a 2 GB file and we drop a 1 GB table, the file might still be 2 GB, but it should have 1 GB of free blocks in it.
To check this, use the following `PRAGMA` and check the number of `free_blocks` in the output:

```sql
PRAGMA database_size;
```

To reclaim space after dropping a table, use the `CHECKPOINT` statement or compact the database by creating a fresh copy with the [`COPY FROM DATABASE` statement](../copy/index.md#copy-from-database--to).

