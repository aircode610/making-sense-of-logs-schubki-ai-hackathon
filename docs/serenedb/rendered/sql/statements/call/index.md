---
title: CALL
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

The `CALL` statement invokes the given [table function](../../query_syntax/from_and_join/index.md#table-functions) and returns the results.

## Examples

Invoke the 'sdb_functions' table function:

```sql
CALL sdb_functions();
```


Invoke the 'pragma_table_info' table function:

```sql
CALL pragma_table_info('pg_am');
-- result:
cid	name	type	notnull	dflt_value	pk
0	oid	oid	f	NULL	f
1	amname	name	f	NULL	f
2	amhandler	regproc	f	NULL	f
3	amtype	char	f	NULL	f
```


Select only the functions where the name starts with `ST_`:

```sql
SELECT function_name, parameters, parameter_types, return_type
FROM sdb_functions()
WHERE function_name LIKE 'ST_%';
```


## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram1" />

