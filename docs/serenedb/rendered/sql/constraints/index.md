---
title: Constraints
sidebar_position: 7
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

In SQL, constraints can be specified for tables. Constraints enforce certain properties over data that is inserted into a table. Constraints can be specified along with the schema of the table as part of the [`CREATE TABLE` statement](../../sql/statements/create_table/index.md). In certain cases, constraints can also be added to a table using the [`ALTER TABLE` statement](../../sql/statements/alter_table/index.md), but this is not currently supported for all constraints.

<DocCallout type="attention">

Constraints have a strong impact on performance: they slow down loading and updates but speed up certain queries. Please consult the [Performance Guide](../../cookbook/performance/schema.md#constraints) for details.

</DocCallout>

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

## Check Constraint

Check constraints allow you to specify an arbitrary Boolean expression. Any columns that _do not_ satisfy this expression violate the constraint. For example, we could enforce that the `name` column does not contain spaces using the following `CHECK` constraint.

```sql
CREATE TABLE students (name VARCHAR CHECK (NOT contains(name, ' ')));

INSERT INTO students VALUES ('this name contains spaces');
-- result:
db error: ERROR: CHECK constraint failed on table <slt:ignore>
```

## Not Null Constraint

A not-null constraint specifies that the column cannot contain any `NULL` values. By default, all columns in tables are nullable. Adding `NOT NULL` to a column definition enforces that a column cannot contain `NULL` values.

```sql
CREATE TABLE students (name VARCHAR NOT NULL);

INSERT INTO students VALUES (NULL);
-- result:
db error: ERROR: NOT NULL constraint failed: <slt:ignore>
```

## Primary Key and Unique Constraint

Primary key or unique constraints define a column, or set of columns, that are a unique identifier for a row in the table. The constraint enforces that the specified columns are _unique_ within a table, i.e., that at most one row contains the given values for the set of columns.

```sql
CREATE TABLE students (id INTEGER PRIMARY KEY, name VARCHAR);

INSERT INTO students VALUES (1, 'Student 1');

INSERT INTO students VALUES (1, 'Student 2');
-- result:
db error: ERROR: Duplicate key "id: 1" violates primary key constraint.
```

```sql
CREATE TABLE students (id INTEGER, name VARCHAR, PRIMARY KEY (id, name));

INSERT INTO students VALUES (1, 'Student 1');

INSERT INTO students VALUES (1, 'Student 2');

INSERT INTO students VALUES (1, 'Student 1');
-- result:
db error: ERROR: Duplicate key "id: 1, name: Student 1" violates primary key constraint.
```

To enforce this property efficiently, an [ART index is automatically created](../../sql/indexes/index.md) for every primary key or unique constraint that is defined in the table.

Primary key constraints and unique constraints are identical except for two points:

-   A table can only have one primary key constraint defined, but many unique constraints
-   A primary key constraint also enforces the keys to not be `NULL`.

```sql
CREATE TABLE students (id INTEGER PRIMARY KEY, name VARCHAR, email VARCHAR UNIQUE);

INSERT INTO students VALUES (1, 'Student 1', 'student1@uni.com');

INSERT INTO students VALUES (2, 'Student 2', 'student1@uni.com');
-- result:
db error: ERROR: Duplicate key "email: student1@uni.com" violates unique constraint.
```

```sql
INSERT INTO students (id, name) VALUES (3, 'Student 3');

INSERT INTO students (name, email) VALUES ('Student 3', 'student3@uni.com');
-- result:
db error: ERROR: NOT NULL constraint failed: <slt:ignore>
```

<DocCallout type="attention">

Indexes have certain limitations that might result in constraints being evaluated too eagerly, leading to constraint errors such as `violates primary key constraint` and `violates unique constraint`. See the [ART index limitations](../../sql/indexes/art.md#limitations) for more details.

</DocCallout>

You can also define a uniqueness constraint on multiple columns:

```sql
CREATE TABLE integers (i INTEGER, j INTEGER, k INTEGER, UNIQUE (i, j));

INSERT INTO integers VALUES (1, 2, 3);

INSERT INTO integers VALUES (1, 4, 5);

INSERT INTO integers VALUES (1, 2, 5);
-- result:
db error: ERROR: Duplicate key "i: 1, j: 2" violates unique constraint.
```

### Deferred Checking

A primary key or unique constraint is checked by every statement that changes the table. Write `DEFERRED` after `PRIMARY KEY` or `UNIQUE` to check it when the transaction commits instead: in between, the transaction may hold duplicate keys, and the commit fails if any are left. `IMMEDIATE`, the default, can be written out the same way. The PostgreSQL form `DEFERRABLE INITIALLY DEFERRED` is not supported.

```sql
CREATE TABLE accounts (id INTEGER PRIMARY KEY DEFERRED, name VARCHAR);

INSERT INTO accounts VALUES (1, 'a'), (2, 'b');

BEGIN;

INSERT INTO accounts VALUES (2, 'c');

UPDATE accounts SET id = 3 WHERE name = 'c';

COMMIT;

BEGIN;

INSERT INTO accounts VALUES (3, 'd');

COMMIT;
-- result:
db error: ERROR: Failed to commit: PRIMARY KEY or UNIQUE constraint violation: duplicate key "3"


SELECT id, name FROM accounts ORDER BY id;
-- result:
id	name
1	a
2	b
3	c
```

## Foreign Keys

Foreign keys define a column, or set of columns, that refer to a primary key or unique constraint from _another_ table. The constraint enforces that the key exists in the other table.

```sql
CREATE TABLE students (id INTEGER PRIMARY KEY, name VARCHAR);

CREATE TABLE subjects (id INTEGER PRIMARY KEY, name VARCHAR);

CREATE TABLE exams (
    exam_id INTEGER PRIMARY KEY,
    subject_id INTEGER REFERENCES subjects(id),
    student_id INTEGER REFERENCES students(id),
    grade INTEGER
);

INSERT INTO students VALUES (1, 'Student 1');

INSERT INTO subjects VALUES (1, 'CS 101');

INSERT INTO exams VALUES (1, 1, 1, 10);

INSERT INTO exams VALUES (2, 1, 2, 10);
-- result:
db error: ERROR: Violates foreign key constraint because key "id: 2" does not exist in the referenced table
```

To enforce this property efficiently, an [ART index is automatically created](../../sql/indexes/index.md) for every foreign key constraint that is defined in the table.

<DocCallout type="attention">

Indexes have certain limitations that might result in constraints being evaluated too eagerly, leading to constraint errors such as `violates primary key constraint` and `violates unique constraint`. See the [ART index limitations](../../sql/indexes/art.md#limitations) for more details.

</DocCallout>

