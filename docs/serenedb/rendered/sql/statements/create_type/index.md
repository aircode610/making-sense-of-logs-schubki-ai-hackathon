---
title: CREATE TYPE
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `CREATE TYPE` statement defines a new type in the catalog.

## Examples

Create a simple `ENUM` type:

```sql
CREATE TYPE mood AS ENUM ('happy', 'sad', 'curious');
```

Create a simple `STRUCT` type:

```sql
CREATE TYPE many_things AS STRUCT(k INTEGER, l VARCHAR);
```

Create a simple `UNION` type:

```sql
CREATE TYPE one_thing AS UNION(number INTEGER, string VARCHAR);
```

Create a type alias:

```sql
CREATE TYPE x_index AS INTEGER;
```

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

The `CREATE TYPE` clause defines a new data type available to this SereneDB instance.
These new types can then be inspected in the [`sdb_types` table](../../functions/metadata.md#sdb_types).

## Limitations

-   Extending types to support custom operators (such as the PostgreSQL `&&` operator) is not possible via plain SQL.

-   The `CREATE TYPE` clause does not support the `OR REPLACE` modifier.

