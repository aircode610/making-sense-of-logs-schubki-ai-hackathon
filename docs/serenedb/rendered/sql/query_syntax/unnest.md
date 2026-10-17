---
title: Unnesting
sidebar_position: 10
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

## Examples

Unnest a list, generating 3 rows (1, 2, 3):

```sql
SELECT unnest([1, 2, 3]);
-- result:
unnest
1
2
3
```

Unnesting a struct, generating two columns (a, b):

```sql
SELECT unnest({'a': 42, 'b': 84});
-- result:
a	b
42	84
```

Recursive unnest of a list of structs:

```sql
SELECT unnest([{'a': 42, 'b': 84}, {'a': 100, 'b': NULL}], recursive := true);
-- result:
a	b
42	84
100	NULL
```

Limit depth of recursive unnest using `max_depth`:

```sql
SELECT unnest([[[1, 2], [3, 4]], [[5, 6], [7, 8, 9], []], [[10, 11]]], max_depth := 2);
-- result:
unnest
{1,2}
{3,4}
{5,6}
{7,8,9}
{}
{10,11}
```

The `unnest` special function is used to unnest lists or structs by one level. The function can be used as a regular scalar function, but only in the `SELECT` clause. Invoking `unnest` with the `recursive` parameter will unnest lists and structs of multiple levels. The depth of unnesting can be limited using the `max_depth` parameter (which assumes `recursive` unnesting by default).

### Unnesting Lists

Unnest a list, generating 3 rows (1, 2, 3):

```sql
SELECT unnest([1, 2, 3]);
-- result:
unnest
1
2
3
```

Unnest a list, generating 3 rows ((1, 10), (2, 10), (3, 10)):

```sql
SELECT unnest([1, 2, 3]), 10;
-- result:
unnest	?column?
1	10
2	10
3	10
```

Unnest two lists of different sizes, generating 3 rows ((1, 10), (2, 11), (3, NULL)):

```sql
SELECT unnest([1, 2, 3]), unnest([10, 11]);
-- result:
unnest	unnest
1	10
2	11
3	NULL
```

Unnest a list column from a subquery:

```sql
SELECT unnest(l) + 10 FROM (VALUES ([1, 2, 3]), ([4, 5])) tbl(l);
-- result:
?column?
11
12
13
14
15
```

Empty result:

```sql
SELECT unnest([]);
-- result:
unnest
```

Empty result:

```sql
SELECT unnest(NULL);
-- result:
unnest
```

Using `unnest` on a list emits one row per list entry. Regular scalar expressions in the same `SELECT` clause are repeated for every emitted row. When multiple lists are unnested in the same `SELECT` clause, the lists are unnested side-by-side. If one list is longer than the other, the shorter list is padded with `NULL` values.

Empty and `NULL` lists both unnest to zero rows.

### Unnesting Structs

Unnesting a struct, generating two columns (a, b):

```sql
SELECT unnest({'a': 42, 'b': 84});
-- result:
a	b
42	84
```

Unnesting a struct, generating two columns (a, b):

```sql
SELECT unnest({'a': 42, 'b': {'x': 84}});
-- result:
a	b
42	(84)
```

`unnest` on a struct will emit one column per entry in the struct.

### Recursive Unnest

Unnesting a list of lists recursively, generating 5 rows (1, 2, 3, 4, 5):

```sql
SELECT unnest([[1, 2, 3], [4, 5]], recursive := true);
-- result:
unnest
1
2
3
4
5
```

Unnesting a list of structs recursively, generating two rows of two columns (a, b):

```sql
SELECT unnest([{'a': 42, 'b': 84}, {'a': 100, 'b': NULL}], recursive := true);
-- result:
a	b
42	84
100	NULL
```

Unnesting a struct, generating two columns (a, b):

```sql
SELECT unnest({'a': [1, 2, 3], 'b': 88}, recursive := true);
-- result:
a	b
{1,2,3}	88
```

Calling `unnest` with the `recursive` setting will fully unnest lists, followed by fully unnesting structs. This can be useful to fully flatten columns that contain lists within lists, or lists of structs. Note that lists _within_ structs are not unnested.

### Setting the Maximum Depth of Unnesting

The `max_depth` parameter allows limiting the maximum depth of recursive unnesting (which is assumed by default and does not have to be specified separately).
For example, unnesting to `max_depth` of 2 yields the following:

```sql
SELECT unnest([[[1, 2], [3, 4]], [[5, 6], [7, 8, 9], []], [[10, 11]]], max_depth := 2) AS x;
-- result:
x
{1,2}
{3,4}
{5,6}
{7,8,9}
{}
{10,11}
```

Meanwhile, unnesting to `max_depth` of 3 results in:

```sql
SELECT unnest([[[1, 2], [3, 4]], [[5, 6], [7, 8, 9], []], [[10, 11]]], max_depth := 3) AS x;
-- result:
x
1
2
3
4
5
6
7
8
9
10
11
```

### Keeping Track of List Entry Positions

To keep track of each entry's position within the original list, `unnest` may be combined with [`generate_subscripts`](../functions/list.md#generate_subscriptsarr-dim):

```sql
SELECT unnest(l) AS x, generate_subscripts(l, 1) AS index
FROM (VALUES ([1, 2, 3]), ([4, 5])) tbl(l);
-- result:
x	index
1	1
2	2
3	3
4	1
5	2
```

### Keep Column Names When Recursively Unnesting

The `keep_parent_names` parameter can be used to retain the parent column names when recursively unnesting a named struct. For example, unnesting the following query with `keep_parent_names` enabled:

```sql
SELECT unnest([{'a': 0, 'b': {'bb': {'bbb': 1}}}], recursive := true, keep_parent_names := true);
-- result:
a	b.bb.bbb
0	1
```

In this case, the field names are preserved, showing the path to the innermost value. This is particularly useful when working with complex nested data structures, as it maintains the structure and naming convention of the original data. The parameter can also be used in conjunction with the `max_depth` parameter, allowing more control and enabling more precise management of nested structures.

