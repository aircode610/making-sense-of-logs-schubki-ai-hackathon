---
title: Logical Operators
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';
import SqlLogicTest from "@site/src/components/SqlLogicTest";

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

The following logical operators are available: `AND`, `OR` and `NOT`. SQL uses a three-valued logic system with `true`, `false` and `NULL`. Note that logical operators involving `NULL` do not always evaluate to `NULL`. For example, `NULL AND false` will evaluate to `false`, and `NULL OR true` will evaluate to `true`. Below are the complete truth tables.

## Binary Operators: `AND` and `OR`

```sql
SELECT true AS "a", true AS "b", true AND true AS "a AND b", true OR true AS "a OR b"
UNION ALL SELECT true, false, true AND false, true OR false
UNION ALL SELECT true, NULL, true AND NULL, true OR NULL
UNION ALL SELECT false, false, false AND false, false OR false
UNION ALL SELECT false, NULL, false AND NULL, false OR NULL
UNION ALL SELECT NULL, NULL, NULL AND NULL, NULL OR NULL;
-- result:
a	b	a AND b	a OR b
t	t	t	t
t	f	f	t
t	NULL	NULL	t
f	f	f	f
f	NULL	f	NULL
NULL	NULL	NULL	NULL
```

## Unary Operator: `NOT`

```sql
SELECT true AS "a", NOT true AS "NOT a"
UNION ALL SELECT false, NOT false
UNION ALL SELECT NULL, NOT NULL;
-- result:
a	NOT a
t	f
f	t
NULL	NULL
```

The operators `AND` and `OR` are commutative, that is, you can switch the left and right operand without affecting the result.

