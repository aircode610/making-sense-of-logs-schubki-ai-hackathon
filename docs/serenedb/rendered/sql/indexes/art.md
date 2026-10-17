---
title: Adaptive Radix Tree (ART)
sidebar_position: 2
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

An [Adaptive Radix Tree (ART)](https://db.in.tum.de/~leis/papers/ART.pdf) is SereneDB's default secondary index — the index type created by [`CREATE INDEX`](../statements/create_index/index.md) when no `USING` clause is given. It is mainly used to enforce primary key constraints and to speed up point and very highly selective (i.e., < 0.1%) queries. ART indexes are created automatically for columns with a `UNIQUE` or `PRIMARY KEY` constraint, and can be created manually with `CREATE INDEX`.

<DocCallout type="attention">

ART indexes must currently be able to fit in memory during index creation. Avoid creating ART indexes if the index does not fit in memory during index creation.

</DocCallout>

## Persistence

ART indexes are persisted on disk.

## Limitations

ART indexes create a secondary copy of the data in a second location. Maintaining that second copy complicates processing. Thus, certain limitations currently apply when it comes to modifying data that is also stored in secondary indexes.

### Constraint Checking in `UPDATE` Statements

`UPDATE` statements on indexed columns and columns that cannot be updated in place are transformed into a `DELETE` of the original row followed by an `INSERT` of the updated row. This rewrite has performance implications, particularly for wide tables, as entire rows are rewritten instead of only the affected columns.

Additionally, it causes the following constraint-checking limitation of `UPDATE` statements. The same limitation exists in other DBMSs, like PostgreSQL.

In the example below, note how the number of rows exceeds the standard vector size, which is 2048 by default. The `UPDATE` statement is rewritten into a `DELETE`, followed by an `INSERT`. This rewrite happens per chunk of data (2048 rows) moving through the processing pipeline. When updating `i = 2047` to `i = 2048`, we do not yet know that 2048 becomes 2049, and so forth. That is because we have not yet seen that chunk. Thus, we throw a constraint violation.

```sql
CREATE TABLE my_table (i INTEGER PRIMARY KEY);

INSERT INTO my_table SELECT range FROM range(3_000);

UPDATE my_table SET i = i + 1;
-- result:
db error: ERROR: Duplicate key "i: 2048" violates primary key constraint.
```

A workaround is to split the `UPDATE` into a `DELETE ... RETURNING ...` followed by an `INSERT`, with some additional logic to (temporarily) store the result of the `DELETE`. All statements should be run inside a transaction via `BEGIN`, and eventually `COMMIT`.

```sql
CREATE TABLE my_table (i INTEGER PRIMARY KEY);

INSERT INTO my_table SELECT range FROM range(3_000);

BEGIN;

CREATE TEMP TABLE tmp AS SELECT i FROM my_table;

DELETE FROM my_table;

INSERT INTO my_table SELECT i FROM tmp;

DROP TABLE tmp;

COMMIT;
```

In other clients, you might be able to fetch the result of `DELETE ... RETURNING ...`. Then, you can use that result in a subsequent `INSERT ...` statement.

### Over-Eager Constraint Checking in Foreign Keys

This limitation occurs if you meet the following conditions:

-   A table has a `FOREIGN KEY` constraint.
-   There is an `UPDATE` on a composite payload column (e.g., a `LIST` or a `STRUCT`) of the corresponding `PRIMARY KEY` table, which is rewritten into a `DELETE` followed by an `INSERT`.
-   The to-be-deleted row exists in the foreign key table.

If these hold, you'll encounter an unexpected constraint violation:

```sql
CREATE TABLE pk_table (id INTEGER PRIMARY KEY, payload VARCHAR[]);

INSERT INTO pk_table VALUES (1, ['hello']);

CREATE TABLE fk_table (id INTEGER REFERENCES pk_table(id));

INSERT INTO fk_table VALUES (1);

UPDATE pk_table SET payload = ['world'] WHERE id = 1;
-- result:
db error: ERROR: Violates foreign key constraint because key "id: 1" is still referenced by a foreign key in a different table. If this is an unexpected constraint violation, please refer to our foreign key limitations in the documentation
```

The reason for this is that SereneDB does not yet support “looking ahead”. During the `INSERT`, it is unaware it will reinsert the foreign key value as part of the `UPDATE` rewrite.

## See also

- [Inverted Index](./inverted/index.md) — for full-text, vector and geospatial search
- [CREATE INDEX](../statements/create_index/index.md)

