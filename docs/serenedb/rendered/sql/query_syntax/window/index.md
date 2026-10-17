---
title: WINDOW
sidebar_position: 12
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';
import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `WINDOW` clause allows you to specify named windows that can be used within [window functions](../../functions/window_functions/index.md). These are useful when you have multiple window functions, as they allow you to avoid repeating the same window clause.

## Examples

The `WINDOW` clause defines a named window (`w`) once and reuses it across several window functions — here both `rank()` and `dense_rank()` share the same partitioning and ordering instead of repeating the `OVER (...)` clause:

```sql
SELECT
    name,
    department,
    rank() OVER w       AS rank,
    dense_rank() OVER w AS dense_rank
FROM employees
WINDOW w AS (PARTITION BY department ORDER BY salary DESC)
ORDER BY department, salary DESC, name;
-- result:
name	department	rank	dense_rank
Alice	Engineering	1	1
Bob	Engineering	1	1
Carol	Engineering	3	2
Dave	Sales	1	1
Eve	Sales	2	2
```

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

