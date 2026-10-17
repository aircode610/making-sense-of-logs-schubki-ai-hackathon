---
title: JSON Functions
sidebar_position: 6
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

## JSON Extraction Functions

SereneDB follows PostgreSQL semantics for extracting values from `JSON`. The `->` and `->>` operators — and their function equivalents `json_extract` and `json_extract_string` — access a member by its **name** or an array element by its **integer index** (they do not interpret `$.` JSONPath or `/` JSON Pointer syntax). To address a value by a JSON Pointer or JSONPath location instead, use `json_value`. The operators require the value to be of the `JSON` logical type.

| Function                                  | Alias                    | Operator | Description                                                                                                                                                  |
| :---------------------------------------- | :----------------------- | :------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `json_exists(json, path)`                 |                          |          | Returns `true` if the supplied path exists in the `json`, and `false` otherwise.                                                                             |
| `json_extract(json, key_or_index)`        | `json_extract_path`      | `->`     | Extracts the named member (string key) or array element (integer index) as `JSON`. If the argument is a `LIST`, the result is a `LIST` of `JSON`.            |
| `json_extract_string(json, key_or_index)` | `json_extract_path_text` | `->>`    | Same as `->`, but returns the value as `VARCHAR` instead of `JSON`.                                                                                          |
| `json_value(json, path)`                  |                          |          | Extracts the scalar at the given [JSON Pointer](https://datatracker.ietf.org/doc/html/rfc6901) or JSONPath (`$.…`) `path`. Returns `NULL` if it is not a scalar. |

Note that the arrow operator `->`, which is used for JSON extracts, has a low precedence as it is also used in [lambda functions](../../sql/functions/lambda.md). Therefore, you need to surround the `->` operator with parentheses when expressing operations such as equality comparisons (`=`).
For example:

```sql
SELECT ((JSON '{"field": 42}')->'field') = 42;
-- result:
?column?
t
```

<DocCallout type="attention">
SereneDB's JSON data type uses [0-based indexing](../../data_import_and_export/json/overview.md#indexing).
</DocCallout>

The examples below use this dataset:

```sql
CREATE TABLE example (j JSON);

INSERT INTO example VALUES
    ('{ "family": "terrestrial", "species": [ "mercury", "venus", "earth", null ] }');
```

Extract a member by name — `json_extract` and the `->` operator are equivalent and both return `JSON`:

```sql
SELECT json_extract(j, 'family') FROM example;
-- result:
json_extract
"terrestrial"
```

```sql
SELECT j->'family' FROM example;
-- result:
?column?
"terrestrial"
```

Use `->>` to return the value as text (`VARCHAR`) instead of `JSON`:

```sql
SELECT j->>'family' FROM example;
-- result:
?column?
terrestrial
```

The operators chain, so a nested array comes back as `JSON`:

```sql
SELECT j->'species' FROM example;
-- result:
?column?
[ "mercury", "venus", "earth", null ]
```

Index into an array with an integer ([0-based](../../data_import_and_export/json/overview.md#indexing)); negative indices count from the end:

```sql
SELECT j->'species'->0 FROM example;
-- result:
?column?
"mercury"
```

```sql
SELECT j->'species'->>0 FROM example;
-- result:
?column?
mercury
```

```sql
SELECT j->'species'->-1 FROM example;
-- result:
?column?
null
```

`json_extract_string` is the function form of `->>`:

```sql
SELECT json_extract_string(j, 'family') FROM example;
-- result:
json_extract_string
terrestrial
```

To address a value by a JSON Pointer or JSONPath location, use `json_value` — it accepts both the JSONPath `$.…` form and the `/…` pointer form:

```sql
SELECT json_value(j, '$.family') FROM example;
-- result:
json_value
"terrestrial"
```

```sql
SELECT json_value(j, '$.species[0]') FROM example;
-- result:
json_value
"mercury"
```

```sql
SELECT json_value(j, '/species/1') FROM example;
-- result:
json_value
"venus"
```

When the input is a plain `VARCHAR` string rather than the `JSON` type, `json_extract` accepts a JSONPath directly:

```sql
SELECT json_extract('{"a": [10, 20]}', '$.a[1]');
-- result:
json_extract
20
```

When several values are needed from the same JSON, calling `json_extract` once per value parses the document repeatedly:

```sql
SELECT
    json_extract(j, 'family') AS family,
    json_extract(j, 'species') AS species
FROM example;
-- result:
family	species
"terrestrial"	[ "mercury", "venus", "earth", null ]
```

Passing a `LIST` of keys extracts them all in a single pass, which is faster and uses less memory:

```sql
WITH extracted AS (
    SELECT json_extract(j, ['family', 'species']) AS extracted_list
    FROM example
)
SELECT
    extracted_list[1] AS family,
    extracted_list[2] AS species
FROM extracted;
-- result:
family	species
"terrestrial"	["mercury","venus","earth",null]
```

## JSON Scalar Functions

The following scalar JSON functions can be used to gain information about the stored JSON values.
With the exception of `json_valid(json)`, all JSON functions produce an error when invalid JSON is supplied.

We support two kinds of notations to describe locations within JSON: [JSON Pointer](https://datatracker.ietf.org/doc/html/rfc6901) and JSONPath.

| Function                                    | Description                                                                                                                                                                                                                                                                       |
| :------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `json_array_length(json[, path])`           | Return the number of elements in the JSON array `json`, or `0` if it is not a JSON array. If `path` is specified, return the number of elements in the JSON array at the given `path`. If `path` is a `LIST`, the result will be `LIST` of array lengths.                         |
| `json_contains(json_haystack, json_needle)` | Returns `true` if `json_needle` is contained in `json_haystack`. Both parameters are of JSON type, but `json_needle` can also be a numeric value or a string, however the string must be wrapped in double quotes.                                                                |
| `json_keys(json[, path])`                   | Returns the keys of `json` as a `LIST` of `VARCHAR`, if `json` is a JSON object. If `path` is specified, return the keys of the JSON object at the given `path`. If `path` is a `LIST`, the result will be `LIST` of `LIST` of `VARCHAR`.                                         |
| `json_structure(json)`                      | Return the structure of `json`. Defaults to `JSON` if the structure is inconsistent (e.g., incompatible types in an array).                                                                                                                                                       |
| `json_type(json[, path])`                   | Return the type of the supplied `json`, which is one of `ARRAY`, `BIGINT`, `BOOLEAN`, `DOUBLE`, `OBJECT`, `UBIGINT`, `VARCHAR` and `NULL`. If `path` is specified, return the type of the element at the given `path`. If `path` is a `LIST`, the result will be `LIST` of types. |
| `json_valid(json)`                          | Return whether `json` is valid JSON.                                                                                                                                                                                                                                              |
| `json(json)`                                | Parse and minify `json`.                                                                                                                                                                                                                                                          |

The JSONPointer syntax separates each field with a `/`.
For example, to extract the first element of the array with key `mercury`, you can do:

```sql
SELECT json_extract('{"mercury": [1, 2, 3]}', '/mercury/0');
-- result:
json_extract
1
```

The JSONPath syntax separates fields with a `.`, and accesses array elements with `[i]`, and always starts with `$`. Using the same example, we can do the following:

```sql
SELECT json_extract('{"mercury": [1, 2, 3]}', '$.mercury[0]');
-- result:
json_extract
1
```

Note that SereneDB's JSON data type uses [0-based indexing](../../data_import_and_export/json/overview.md#indexing).

JSONPath is more expressive, and can also access from the back of lists:

```sql
SELECT json_extract('{"mercury": [1, 2, 3]}', '$.mercury[#-1]');
-- result:
json_extract
3
```

JSONPath also allows escaping syntax tokens, using double quotes:

```sql
SELECT json_extract('{"mercury.venus": [1, 2, 3]}', '$."mercury.venus"[1]');
-- result:
json_extract
2
```

Examples using a solar-system dataset:

```sql
CREATE TABLE example (j JSON);

INSERT INTO example VALUES
    ('{ "family": "terrestrial", "species": [ "mercury", "venus", "earth", null ] }');
```

```sql
SELECT json(j) FROM example;
-- result:
json
{"family":"terrestrial","species":["mercury","venus","earth",null]}
```

```sql
SELECT j.family FROM example;
-- result:
family
NULL
```

```sql
SELECT j.species[0] FROM example;
-- result:
species
NULL
```

```sql
SELECT json_valid(j) FROM example;
-- result:
json_valid
t
```

```sql
SELECT json_valid('{');
-- result:
json_valid
f
```

```sql
SELECT json_array_length('["mercury", "venus", "earth", null]');
-- result:
json_array_length
4
```

```sql
SELECT json_array_length(j, 'species') FROM example;
-- result:
json_array_length
4
```

```sql
SELECT json_array_length(j, '/species') FROM example;
-- result:
json_array_length
4
```

```sql
SELECT json_array_length(j, '$.species') FROM example;
-- result:
json_array_length
4
```

```sql
SELECT json_array_length(j, ['$.species']) FROM example;
-- result:
json_array_length
{4}
```

```sql
SELECT json_type(j) FROM example;
-- result:
json_type
OBJECT
```

```sql
SELECT json_keys(j) FROM example;
-- result:
json_keys
{family,species}
```

```sql
SELECT json_structure(j) FROM example;
-- result:
json_structure
{"family":"VARCHAR","species":["VARCHAR"]}
```

```sql
SELECT json_structure('["mercury", {"family": "terrestrial"}]');
-- result:
json_structure
["JSON"]
```

```sql
SELECT json_contains('{"key": "value"}', '"value"');
-- result:
json_contains
t
```

```sql
SELECT json_contains('{"key": 1}', '1');
-- result:
json_contains
t
```

```sql
SELECT json_contains('{"top_key": {"key": "value"}}', '{"key": "value"}');
-- result:
json_contains
t
```

## JSON Aggregate Functions

There are three JSON aggregate functions.

| Function                        | Description                                                            |
| :------------------------------ | :--------------------------------------------------------------------- |
| `json_group_array(any)`         | Return a JSON array with all values of `any` in the aggregation.       |
| `json_group_object(key, value)` | Return a JSON object with all `key`, `value` pairs in the aggregation. |
| `json_group_structure(json)`    | Return the combined `json_structure` of all `json` in the aggregation. |

Examples:

```sql
CREATE TABLE example1 (k VARCHAR, v INTEGER);

INSERT INTO example1 VALUES ('mercury', 42), ('venus', 7);
```

```sql
SELECT json_group_array(v) FROM example1;
-- result:
json_group_array
[42,7]
```

```sql
SELECT json_group_object(k, v) FROM example1;
-- result:
json_group_object
{"mercury":42,"venus":7}
```

```sql
CREATE TABLE example2 (j JSON);

INSERT INTO example2 VALUES
    ('{"family": "terrestrial", "species": ["mercury", "venus"], "coolness": 42.42}'),
    ('{"family": "gas_giant", "species": ["jupiter", "saturn"], "has_rings": true}');
```

```sql
SELECT json_group_structure(j) FROM example2;
-- result:
json_group_structure
{"family":"VARCHAR","species":["VARCHAR"],"coolness":"DOUBLE","has_rings":"BOOLEAN"}
```

## Transforming JSON to Nested Types

In many cases, it is inefficient to extract values from JSON one-by-one.
Instead, we can “extract” all values at once, transforming JSON to the nested types `LIST` and `STRUCT`.

| Function                                 | Description                                                            |
| :--------------------------------------- | :--------------------------------------------------------------------- |
| `json_transform(json, structure)`        | Transform `json` according to the specified `structure`.               |
| `from_json(json, structure)`             | Alias for `json_transform`.                                            |
| `json_transform_strict(json, structure)` | Same as `json_transform`, but throws an error when type casting fails. |
| `from_json_strict(json, structure)`      | Alias for `json_transform_strict`.                                     |

The `structure` argument is JSON of the same form as returned by `json_structure`.
The `structure` argument can be modified to transform the JSON into the desired structure and types.
It is possible to extract fewer key/value pairs than are present in the JSON, and it is also possible to extract more: missing keys become `NULL`.

Examples:

```sql
CREATE TABLE example (j JSON);

INSERT INTO example VALUES
    ('{"family": "terrestrial", "species": ["mercury", "venus"], "coolness": 42.42}'),
    ('{"family": "gas_giant", "species": ["jupiter", "saturn"], "has_rings": true}');
```

```sql
SELECT json_transform(j, '{"family": "VARCHAR", "coolness": "DOUBLE"}') FROM example;
-- result:
json_transform
(terrestrial,42.42)
(gas_giant,)
```

```sql
SELECT json_transform(j, '{"family": "TINYINT", "coolness": "DECIMAL(4, 2)"}') FROM example;
-- result:
json_transform
(,42.42)
(,)
```

```sql
query error
SELECT json_transform_strict(j, '{"family": "TINYINT", "coolness": "DOUBLE"}') FROM example;
-- result:
db error: ERROR: Failed to cast value to numerical: "gas_giant"
```

## JSON Table Functions

SereneDB implements two JSON table functions that take a JSON value and produce a table from it.

| Function                 | Description                                                                                  |
| :----------------------- | :------------------------------------------------------------------------------------------- |
| `json_each(json[ ,path]` | Traverse `json` and return one row for each element in the top-level array or object.        |
| `json_tree(json[ ,path]` | Traverse `json` in depth-first fashion and return one row for each element in the structure. |

If the element is not an array or object, the element itself is returned.
If the optional `path` argument is supplied, traversal starts from the element at the given path instead of the root element.

The resulting table has the following columns:

| Field     | Type               | Description                                 |
| :-------- | :----------------- | :------------------------------------------ |
| `key`     | `VARCHAR`          | Key of element relative to its parent       |
| `value`   | `JSON`             | Value of element                            |
| `type`    | `VARCHAR`          | `json_type` (function) of this element      |
| `atom`    | `JSON`             | `json_value` (function) of this element     |
| `id`      | `UBIGINT`          | Element identifier, numbered by parse order |
| `parent`  | `UBIGINT`          | `id` of parent element                      |
| `fullkey` | `VARCHAR`          | JSON path to element                        |
| `path`    | `VARCHAR`          | JSON path to parent element                 |
| `json`    | `JSON` (Virtual)   | The `json` parameter                        |
| `root`    | `TEXT` (Virtual)   | The `path` parameter                        |
| `rowid`   | `BIGINT` (Virtual) | The row identifier                          |

These functions are analogous to [SQLite's functions with the same name](https://www.sqlite.org/json1.html#jeach).
Note that, because the `json_each` and `json_tree` functions refer to previous subqueries in the same FROM clause, they are [_lateral joins_](../../sql/query_syntax/from_and_join/index.md#lateral-joins).

Examples:

```sql
CREATE TABLE example (j JSON);

INSERT INTO example VALUES
    ('{"family": "terrestrial", "species": ["mercury", "venus"], "coolness": 42.42}'),
    ('{"family": "gas_giant", "species": ["jupiter", "saturn"], "has_rings": true}');
```

```sql
SELECT je.*, je.rowid
FROM example AS e, json_each(e.j) AS je
ORDER BY e.j::TEXT, je.id;
-- result:
key	value	type	atom	id	parent	fullkey	path	rowid
family	"gas_giant"	VARCHAR	"gas_giant"	2	NULL	$.family	$	0
species	["jupiter","saturn"]	ARRAY	NULL	4	NULL	$.species	$	1
has_rings	true	BOOLEAN	true	8	NULL	$.has_rings	$	2
family	"terrestrial"	VARCHAR	"terrestrial"	2	NULL	$.family	$	0
species	["mercury","venus"]	ARRAY	NULL	4	NULL	$.species	$	1
coolness	42.42	DOUBLE	42.42	8	NULL	$.coolness	$	2
```

```sql
SELECT je.*, je.rowid
FROM example AS e, json_each(e.j, '$.species') AS je
ORDER BY e.j::TEXT, je.id;
-- result:
key	value	type	atom	id	parent	fullkey	path	rowid
0	"jupiter"	VARCHAR	"jupiter"	5	NULL	$.species[0]	$.species	0
1	"saturn"	VARCHAR	"saturn"	6	NULL	$.species[1]	$.species	1
0	"mercury"	VARCHAR	"mercury"	5	NULL	$.species[0]	$.species	0
1	"venus"	VARCHAR	"venus"	6	NULL	$.species[1]	$.species	1
```

```sql
SELECT je.key, je.value, je.type, je.id, je.parent, je.fullkey, je.rowid
FROM example AS e, json_tree(e.j) AS je
ORDER BY e.j::TEXT, je.id;
-- result:
key	value	type	id	parent	fullkey	rowid
NULL	{"family":"gas_giant","species":["jupiter","saturn"],"has_rings":true}	OBJECT	0	NULL	$	0
family	"gas_giant"	VARCHAR	2	0	$.family	1
species	["jupiter","saturn"]	ARRAY	4	0	$.species	2
0	"jupiter"	VARCHAR	5	4	$.species[0]	3
1	"saturn"	VARCHAR	6	4	$.species[1]	4
has_rings	true	BOOLEAN	8	0	$.has_rings	5
NULL	{"family":"terrestrial","species":["mercury","venus"],"coolness":42.42}	OBJECT	0	NULL	$	0
family	"terrestrial"	VARCHAR	2	0	$.family	1
species	["mercury","venus"]	ARRAY	4	0	$.species	2
0	"mercury"	VARCHAR	5	4	$.species[0]	3
1	"venus"	VARCHAR	6	4	$.species[1]	4
coolness	42.42	DOUBLE	8	0	$.coolness	5
```

