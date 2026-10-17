---
title: CREATE SCHEMA
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `CREATE SCHEMA` statement creates a schema in the catalog. The default schema is `main`.

## Examples

Create a schema:

```sql
CREATE SCHEMA s1;
```

Create a schema if it does not exist yet:

```sql
CREATE SCHEMA IF NOT EXISTS s2;
```

Create a schema or replace a schema if it exists:

```sql
CREATE OR REPLACE SCHEMA s2;
```

Create table in the schemas:

```sql
CREATE TABLE s1.t (id INTEGER PRIMARY KEY, other_id INTEGER);

CREATE TABLE s2.t (id INTEGER PRIMARY KEY, j VARCHAR);
```

Compute a join between tables from two schemas:

```sql
query ???? rowsort
SELECT *
FROM s1.t s1t, s2.t s2t
WHERE s1t.other_id = s2t.id;
-- result:
id	other_id	id	j
1	1	1	a
2	1	1	a
3	2	2	b
```

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

