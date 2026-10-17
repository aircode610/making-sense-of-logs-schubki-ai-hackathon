---
title: Profiling Queries
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

SereneDB supports profiling queries via the `EXPLAIN` and `EXPLAIN ANALYZE` statements.

## `EXPLAIN`

To see the query plan of a query without executing it, run:

```sql
EXPLAIN
    SELECT count(*)
    FROM generate_series(1, 100) AS t(i)
    WHERE i % 2 = 0;
```

The output of `EXPLAIN` contains the estimated cardinalities for each operator.

## `EXPLAIN ANALYZE`

To profile a query, run:

```sql
EXPLAIN ANALYZE
    SELECT count(*)
    FROM generate_series(1, 100) AS t(i)
    WHERE i % 2 = 0;
```

The `EXPLAIN ANALYZE` statement runs the query, and shows the actual cardinalities for each operator,
as well as the cumulative wall-clock time spent in each operator.

