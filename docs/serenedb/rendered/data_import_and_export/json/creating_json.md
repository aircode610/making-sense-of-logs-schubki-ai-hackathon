---
title: Creating JSON
sidebar_position: 2
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

## JSON Creation Functions

The following functions are used to create JSON.

| Function                       | Description                                                                                                                                   |
| :----------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| `to_json(any)`                 | Create `JSON` from a value of `any` type. Our `LIST` is converted to a JSON array, and our `STRUCT` and `MAP` are converted to a JSON object. |
| `json_quote(any)`              | Alias for `to_json`.                                                                                                                          |
| `array_to_json(list)`          | Alias for `to_json` that only accepts `LIST`.                                                                                                 |
| `row_to_json(list)`            | Alias for `to_json` that only accepts `STRUCT`.                                                                                               |
| `json_array(any, ...)`         | Create a JSON array from the values in the argument lists.                                                                                    |
| `json_object(key, value, ...)` | Create a JSON object from `key`, `value` pairs in the argument list. Requires an even number of arguments.                                    |
| `json_build_array(any, ...)` | Alias for `json_array`, under its PostgreSQL name. |
| `json_build_object(key, value, ...)` | Alias for `json_object`, under its PostgreSQL name. |
| `json_merge_patch(json, json)` | Merge two JSON documents together.                                                                                                            |

Examples:

```sql
SELECT to_json('mercury');
-- result:
to_json
"mercury"
```

```sql
SELECT to_json([1, 2, 3]);
-- result:
to_json
[1,2,3]
```

```sql
SELECT to_json({mercury : 42});
-- result:
to_json
{"mercury":42}
```

```sql
SELECT to_json(MAP(['mercury'], [42]));
-- result:
to_json
{"mercury":42}
```

```sql
SELECT json_array('mercury', 42, 'venus', 123);
-- result:
json_array
["mercury",42,"venus",123]
```

```sql
SELECT json_object('mercury', 42, 'venus', 123);
-- result:
json_object
{"mercury":42,"venus":123}
```

```sql
SELECT json_merge_patch('{"mercury": 42}', '{"venus": 123}');
-- result:
json_merge_patch
{"mercury":42,"venus":123}
```

