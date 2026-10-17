---
layout: docu
redirect_from:
- /docs/guides/meta/explain
- /docs/preview/guides/meta/explain
- /docs/stable/guides/meta/explain
title: 'EXPLAIN: Inspect Query Plans'
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

```sql
EXPLAIN SELECT * FROM tbl;
-- result:
QUERY PLAN
╭─ SEQ_SCAN ─────────────────────╮
│ Table: tbl                     │
│ Type: Sequential Scan          │
│ Projections: id, name, col1,   │
│              col2,             │
│              Some Column Name, │
│              i, a, b, c,       │
│              number, number1,  │
│              number2           │
│ ~3 rows                        │
╰────────────────────────────────╯
```

The `EXPLAIN` statement displays the physical plan, i.e., the query plan that will get executed,
and is enabled by prepending the query with `EXPLAIN`.
The physical plan is a tree of operators that are executed in a specific order to produce the result of the query.
To generate an efficient physical plan, the query optimizer transforms the existing physical plan into a better physical plan.

To demonstrate, see the below example:

```sql
EXPLAIN
    SELECT name
    FROM students
    JOIN exams USING (sid)
    WHERE name LIKE 'Ma%';
-- result:
QUERY PLAN
╭─ PROJECTION ──────────╮
│ Projections: name     │
│ ~1 row                │
╰───────────┬───────────╯
╭─ HASH_JOIN ───────────╮
│ Join Type: INNER      │
│ Conditions: sid = sid │
│ ~1 row                │
╰───────────┬───────────╯
            ├─────────────────────────────╮
╭─ SEQ_SCAN ┴───────────╮  ╭─ SEQ_SCAN ───┴──────────────╮
│ Table: exams          │  │ Table: students             │
│ Type: Sequential Scan │  │ Type: Sequential Scan       │
│ Projections: sid      │  │ Projections: sid, name      │
│ ~3 rows               │  │ Column Filter: name >= 'Ma' │
╰───────────────────────╯  │ ~1 row                      │
                           ╰─────────────────────────────╯
```

Note that the query is not actually executed – therefore, we can only see the estimated cardinality (shown as the `~N rows` line) for each operator, which is calculated by using the statistics of the base tables and applying heuristics for each operator.

Table scan operators display the fully qualified table name including catalog and schema (e.g., `memory.myschema.mytable`).

## Additional Explain Settings

The `EXPLAIN` statement supports additional settings that can be used to control the output. These settings are controlled via the `explain_output` pragma. The following values are available:

`physical_only` is the default setting. It shows only the physical plan.

```sql
PRAGMA explain_output = 'physical_only';
EXPLAIN SELECT * FROM tbl;
```

`optimized_only` shows only the optimized plan.

```sql
PRAGMA explain_output = 'optimized_only';
EXPLAIN SELECT * FROM tbl;
```

`all` shows both the physical and optimized plans.

```sql
PRAGMA explain_output = 'all';
EXPLAIN SELECT * FROM tbl;
```

## See Also

For more information, see the ["Profiling" page](../performance/profiling.md).

