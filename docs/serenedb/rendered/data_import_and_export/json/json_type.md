---
title: JSON Type
sidebar_position: 5
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

SereneDB supports `json` via the `JSON` logical type. For example:

```sql
SELECT '[1, null, {"key": "value"}]'::JSON;
-- result:
json
[1, null, {"key": "value"}]
```

Logically, the `JSON` type is similar to a `VARCHAR`, but with the restriction that it must be valid JSON.
Physically, the data is stored as a `VARCHAR`.

For example, you can't parse invalid JSON:

```sql
query error
SELECT 'unquoted'::JSON;
-- result:
db error: ERROR: Malformed JSON at byte 0 of input: unexpected character, expected a JSON value.  Input: "unquoted"
```

Instead, what you probably want here is `SELECT '"quoted"'::JSON`.

Since the data is stored physically as a `VARCHAR`, whitespace is significant:

```sql
SELECT '{ "a": 5 }'::JSON = '{"a":5}'::JSON;
-- result:
?column?
f
```

Please note that whitespaces are kept in roundtrips:

```sql
SELECT '{  "a":5 }'::JSON::VARCHAR
-- result:
text
{  "a":5 }
```

The order of keys in objects is significant:

```sql
SELECT '{"a":1,"b":2}'::JSON = '{"b":2,"a":1}'::JSON;
-- result:
?column?
f
```

Duplicate keys are allowed in JSON objects:

```sql
SELECT '{"a":1,"a":2}'::JSON;
-- result:
json
{"a":1,"a":2}
```

We allow any of SereneDB's types to be cast to JSON, and JSON to be cast back to any of SereneDB's types, for example, to cast `JSON` to SereneDB's `STRUCT` type, run:

```sql
SELECT '{"mercury": 42}'::JSON::STRUCT(mercury INTEGER);
-- result:
struct(mercury integer)
(42)
```

And back:

```sql
SELECT {mercury: 42}::JSON;
-- result:
struct_pack
{"mercury":42}
```

This works for our nested types as shown in the example, but also for non-nested types:

```sql
SELECT '2023-05-12'::DATE::JSON;
-- result:
json
"2023-05-12"
```

The only exception to this behavior is the cast from `VARCHAR` to `JSON`, which does not alter the data, but instead parses and validates the contents of the `VARCHAR` as JSON.

