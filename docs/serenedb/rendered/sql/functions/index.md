---
title: Overview
redirect_from:
- /docs/sql/functions/overview
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

## Function Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

## Function Chaining via the Dot Operator

SereneDB supports the dot syntax for function chaining. This allows the function call `fn(arg1, arg2, arg3, ...)` to be rewritten as `arg1.fn(arg2, arg3, ...)`. For example, take the following use of the [`replace` function](../../sql/functions/text.md#replacestring-source-target):

```sql
SELECT replace(goose_name, 'goose', 'duck') AS duck_name
FROM unnest(['African goose', 'Faroese goose', 'Hungarian goose', 'Pomeranian goose']) breed(goose_name);
-- result:
duck_name
African duck
Faroese duck
Hungarian duck
Pomeranian duck
```

This can be rewritten as follows:

```sql
SELECT goose_name.replace('goose', 'duck') AS duck_name
FROM unnest(['African goose', 'Faroese goose', 'Hungarian goose', 'Pomeranian goose']) breed(goose_name);
-- result:
duck_name
African duck
Faroese duck
Hungarian duck
Pomeranian duck
```

### Using with Literals and Arrays

Function chaining also works on literals and on the result of array access. Wrapping the argument in parentheses is optional, but makes the intent explicit:

```sql
SELECT ('hello world').replace(' ', '_');
-- result:
replace
hello_world
```

```sql
SELECT (2).sqrt();
-- result:
sqrt
1.4142135623730951
```

```sql
SELECT (m[1]).map_entries()
FROM (VALUES ([MAP {'hello': 42}, MAP {'world': 42}])) t(m);
-- result:
map_entries
{"(hello,42)"}
```

`coalesce` and `ifnull` chain the same way:

```sql
SELECT (NULL::INTEGER).coalesce(0);
-- result:
coalesce
0


SELECT (2).ifnull(0);
-- result:
coalesce
2
```

### Limitations

Function chaining via the dot operator is limited to _scalar_ functions and is not supported for _table_ functions.
For example, the following call returns a `Parser Error`:

```sql
query error
SELECT * FROM ('my_file.parquet').read_parquet();
-- result:
db error: ERROR: syntax error at or near "."
```

## Query Functions

The `sdb_functions()` table function shows the list of functions currently built into the system.

```sql
SELECT DISTINCT ON(function_name)
    function_name,
    function_type,
    return_type,
    parameter_types
FROM sdb_functions()
WHERE function_type = 'scalar'
  AND function_name LIKE 'b%'
ORDER BY function_name;
-- result:
function_name	function_type	return_type	parameter_types
bar	scalar	VARCHAR	{DOUBLE,DOUBLE,DOUBLE,DOUBLE}
base64	scalar	VARCHAR	{BLOB}
bin	scalar	VARCHAR	{VARCHAR}
binom	scalar	HUGEINT	{INTEGER,INTEGER}
bit_count	scalar	TINYINT	{TINYINT}
bit_length	scalar	BIGINT	{VARCHAR}
bit_position	scalar	INTEGER	{BIT,BIT}
bitstring	scalar	BIT	{VARCHAR,INTEGER}
bitstring_byte_comparable	scalar	BLOB	{BIT}
bm25	scalar	FLOAT	{BIGINT}
broadcast	scalar	INET	{INET}
```

In addition to the columns shown above, `sdb_functions()` exposes the `parameters` and `description` columns, which provide the parameter names and a human-readable description (where available) for each function.

