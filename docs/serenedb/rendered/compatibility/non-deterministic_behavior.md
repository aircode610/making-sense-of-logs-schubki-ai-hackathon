---
layout: docu
redirect_from:
- /docs/operations_manual/non-deterministic_behavior
- /docs/preview/operations_manual/non-deterministic_behavior
- /docs/stable/operations_manual/non-deterministic_behavior
- /docs/contribution/non-deterministic_behavior
title: Non-Deterministic Behavior
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

Several operators in SereneDB exhibit non-deterministic behavior.
Most notably, SQL uses set semantics, which allows results to be returned in a different order.
SereneDB exploits this to improve performance, particularly when performing multi-threaded query execution.
Other factors, such as using different compilers, operating systems and hardware architectures, can also cause changes in ordering.
This page documents the cases where non-determinism is an _expected behavior_.
If you would like to make your queries deterministic, see the [“Working Around Non-Determinism” section](#working-around-non-determinism).

## Set Semantics

One of the most common sources of non-determinism is the set semantics used by SQL.
E.g., if you run the following query repeatedly, you may get two different results:

[example compatibility/non-deterministic_behavior/example_001 not found]

Both results `A`, `B` and `B`, `A` are correct.

## Different Results on Different Platforms: `array_distinct`

The `array_distinct` function may return results [in a different order on different platforms](https://github.com/duckdb/duckdb/issues/13746):

[example compatibility/non-deterministic_behavior/example_002 not found]

For this query, both `[A, B]` and `[B, A]` are valid results.

## Floating-Point Aggregate Operations with Multi-Threading

Floating-point inaccuracies may produce different results when run in multi-threaded configurations:
For example, [`stddev` and `corr` may produce non-deterministic results](https://github.com/duckdb/duckdb/issues/13763):

```sql
CREATE TABLE tbl AS
    SELECT 'ABCDEFG'[floor(random() * 7 + 1)::INT] AS s, random() AS x, i AS y
    FROM range(1, 1_000_000) r(i);

SELECT s, stddev(x) AS standard_deviation, corr(x, y) AS correlation
FROM tbl
GROUP BY s
ORDER BY s;
-- result:
s	standard_deviation	correlation
A	0.2892	0.0036
B	0.2887	-0.0024
C	0.2889	-0.0059
D	0.2885	0.0036
E	0.2888	0.0043
F	0.2887	0.0016
G	0.2880	0.0018
```

With `x` drawn from `random()`, the standard deviation is approximately `0.289` and the correlation is approximately `0` for every value of `s`. The exact digits, however, differ from run to run: when the aggregation is split across multiple threads, the order in which floating-point values are summed is not deterministic, so the low-order digits vary.

## Working Around Non-Determinism

For the majority of use cases, non-determinism is not causing any issues.
However, there are some cases where deterministic results are desirable.
In these cases, try the following workarounds:

1. Limit the number of threads to prevent non-determinism introduced by multi-threading.

   [example compatibility/non-deterministic_behavior/example_004 not found]

2. Enforce ordering. For example, you can use the [`ORDER BY ALL` clause](../sql/query_syntax/orderby/index.md#order-by-all):

   [example compatibility/non-deterministic_behavior/example_005 not found]

   You can also sort lists using [`list_sort`](../sql/functions/list.md#list_sortlist-col1-col2):

   [example compatibility/non-deterministic_behavior/example_006 not found]

   It's also possible to introduce a deterministic shuffling.

