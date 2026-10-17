---
title: Map Functions
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

<!-- markdownlint-disable MD001 -->

| Name                                                                      | Description                                                                                                                                                                                                                  |
| :------------------------------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`cardinality(map)`](#cardinalitymap)                                     | Return the size of the map (or the number of entries in the map).                                                                                                                                                            |
| [`element_at(map, key)`](#element_atmap-key)                              | Return the value for a given `key` as a list, or an empty list if the key is not contained in the map. The type of the key provided in the second parameter must match the type of the map's keys; else, an error is thrown. |
| [`map_concat(maps...)`](#map_concatmaps)                                  | Returns a map created from merging the input `maps`. On key collision the value is taken from the last map with that key.                                                                                                    |
| [`map_contains(map, key)`](#map_containsmap-key)                          | Checks if a map contains a given key.                                                                                                                                                                                        |
| [`map_contains_entry(map, key, value)`](#map_contains_entrymap-key-value) | Check if a map contains a given key-value pair.                                                                                                                                                                              |
| [`map_contains_value(map, value)`](#map_contains_valuemap-value)          | Checks if a map contains a given value.                                                                                                                                                                                      |
| [`map_entries(map)`](#map_entriesmap)                                     | Return a list of struct(k, v) for each key-value pair in the map.                                                                                                                                                            |
| [`map_extract(map, key)`](#map_extractmap-key)                            | Return the value for a given `key` as a list, or an empty list if the key is not contained in the map. The type of the key provided in the second parameter must match the type of the map's keys; else, an error is thrown. |
| [`map_extract_value(map, key)`](#map_extract_valuemap-key)                | Returns the value for a given `key` or `NULL` if the `key` is not contained in the map. The type of the key provided in the second parameter must match the type of the map's keys; else, an error is thrown.                |
| [`map_from_entries(STRUCT(k, v)[])`](#map_from_entriesstructk-v)          | Returns a map created from the entries of the array.                                                                                                                                                                         |
| [`map_keys(map)`](#map_keysmap)                                           | Return a list of all keys in the map.                                                                                                                                                                                        |
| [`map_values(map)`](#map_valuesmap)                                       | Return a list of all values in the map.                                                                                                                                                                                      |
| [`map()`](#map)                                                           | Returns an empty map.                                                                                                                                                                                                        |
| [`map[entry]`](#mapentry)                                                 | Returns the value for a given `key` or `NULL` if the `key` is not contained in the map. The type of the key provided in the second parameter must match the type of the map's keys; else, an error is thrown.                |

#### `cardinality(map)`

Return the size of the map (or the number of entries in the map).

```sql
SELECT cardinality(map([4, 2], ['a', 'b'])) AS cardinality;
-- result:
cardinality
2
```

#### `element_at(map, key)`

Return the value for a given `key` as a list, or an empty list if the key is not contained in the map. The type of the key provided in the second parameter must match the type of the map's keys else an error is thrown. Alias: `map_extract(map, key)`.

```sql
SELECT element_at(map([100, 5], [42, 43]), 100) AS element_at;
-- result:
element_at
{42}
```

#### `map_concat(maps...)`

Returns a map created from merging the input `maps`. On key collision the value is taken from the last map with that key.

```sql
SELECT map_concat(MAP {'key1': 10, 'key2': 20}, MAP {'key3': 30}, MAP {'key2': 5}) AS map_concat;
-- result:
map_concat
{"(key1,10)","(key2,5)","(key3,30)"}
```

#### `map_contains(map, key)`

Checks if a map contains a given key.

```sql
SELECT map_contains(MAP {'key1': 10, 'key2': 20, 'key3': 30}, 'key2') AS map_contains;
-- result:
map_contains
t
```

#### `map_contains_entry(map, key, value)`

Check if a map contains a given key-value pair.

```sql
SELECT map_contains_entry(MAP {'key1': 10, 'key2': 20, 'key3': 30}, 'key2', 20) AS map_contains_entry;
-- result:
map_contains_entry
t
```

#### `map_contains_value(map, value)`

Checks if a map contains a given value.

```sql
SELECT map_contains_value(MAP {'key1': 10, 'key2': 20, 'key3': 30}, 20) AS map_contains_value;
-- result:
map_contains_value
t
```

#### `map_entries(map)`

Return a list of struct(k, v) for each key-value pair in the map.

```sql
SELECT map_entries(map([100, 5], [42, 43])) AS map_entries;
-- result:
map_entries
{"(100,42)","(5,43)"}
```

#### `map_extract(map, key)`

Return the value for a given `key` as a list, or an empty list if the key is not contained in the map. The type of the key provided in the second parameter must match the type of the map's keys else an error is thrown. Alias: `element_at(map, key)`.

```sql
SELECT map_extract(map([100, 5], [42, 43]), 100) AS map_extract;
-- result:
map_extract
{42}
```

#### `map_extract_value(map, key)`

Returns the value for a given `key` or `NULL` if the `key` is not contained in the map. The type of the key provided in the second parameter must match the type of the map's keys else an error is thrown. Alias: `map[key]`.

```sql
SELECT map_extract_value(map([100, 5], [42, 43]), 100) AS map_extract_value;
-- result:
map_extract_value
42
```

#### `map_from_entries(STRUCT(k, v)[])`

Returns a map created from the entries of the array.

```sql
SELECT map_from_entries([{k: 5, v: 'val1'}, {k: 3, v: 'val2'}]) AS map_from_entries;
-- result:
map_from_entries
{"(5,val1)","(3,val2)"}
```

#### `map_keys(map)`

Return a list of all keys in the map.

```sql
SELECT map_keys(map([100, 5], [42, 43])) AS map_keys;
-- result:
map_keys
{100,5}
```

#### `map_values(map)`

Return a list of all values in the map.

```sql
SELECT map_values(map([100, 5], [42, 43])) AS map_values;
-- result:
map_values
{42,43}
```

#### `map()`

Returns an empty map.

```sql
SELECT map() AS map;
-- result:
map
{}
```

#### `map[entry]`

Returns the value for a given `key` or `NULL` if the `key` is not contained in the map. The type of the key provided in the second parameter must match the type of the map's keys else an error is thrown. Alias: `map_extract_value(map, key)`.

```sql
SELECT map([100, 5], ['a', 'b'])[100] AS map_entry;
-- result:
map_entry
a
```

