---
title: QUALIFY
sidebar_position: 12
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `QUALIFY` clause is used to filter the results of [`WINDOW` functions](../../functions/window_functions/index.md). This filtering of results is similar to how a [`HAVING` clause](../../query_syntax/having/index.md) filters the results of aggregate functions applied based on the [`GROUP BY` clause](../../query_syntax/groupby/index.md).

The `QUALIFY` clause avoids the need for a subquery or [`WITH` clause](../../query_syntax/with/index.md) to perform this filtering (much like `HAVING` avoids a subquery). An example using a `WITH` clause instead of `QUALIFY` is included below the `QUALIFY` examples.

Note that this is filtering based on [`WINDOW` functions](../../functions/window_functions/index.md), not necessarily based on the [`WINDOW` clause](../../query_syntax/window/index.md). The `WINDOW` clause is optional and can be used to simplify the creation of multiple `WINDOW` function expressions.

The position of where to specify a `QUALIFY` clause is following the [`WINDOW` clause](../../query_syntax/window/index.md) in a `SELECT` statement (`WINDOW` does not need to be specified), and before the [`ORDER BY`](../../query_syntax/orderby/index.md).

## Examples

Each of the following examples produces the same output.

Filter based on a window function defined in the `QUALIFY` clause:

```sql
query ??? rowsort
SELECT
    team,
    player,
    -- In this example the player_rank column in the select clause is for reference
    row_number() OVER (PARTITION BY team ORDER BY points DESC) AS player_rank
FROM scores
QUALIFY
    row_number() OVER (PARTITION BY team ORDER BY points DESC) < 3;
-- result:
team	player	player_rank
Hawks	Ann	1
Hawks	Bob	2
Owls	Dan	1
Owls	Eve	2
```


Filter based on a window function defined in the `SELECT` clause:

```sql
query ??? rowsort
SELECT
    team,
    player,
    row_number() OVER (PARTITION BY team ORDER BY points DESC) AS player_rank
FROM scores
QUALIFY
    player_rank < 3;
-- result:
team	player	player_rank
Hawks	Ann	1
Hawks	Bob	2
Owls	Dan	1
Owls	Eve	2
```


Filter based on a window function defined in the `QUALIFY` clause, but using the `WINDOW` clause:

```sql
query ??? rowsort
SELECT
    team,
    player,
    -- In this example the player_rank column in the select clause is for reference
    row_number() OVER my_window AS player_rank
FROM scores
WINDOW
    my_window AS (PARTITION BY team ORDER BY points DESC)
QUALIFY
    row_number() OVER my_window < 3;
-- result:
team	player	player_rank
Hawks	Ann	1
Hawks	Bob	2
Owls	Dan	1
Owls	Eve	2
```


Filter based on a window function defined in the `SELECT` clause, but using the `WINDOW` clause:

```sql
query ??? rowsort
SELECT
    team,
    player,
    row_number() OVER my_window AS player_rank
FROM scores
WINDOW
    my_window AS (PARTITION BY team ORDER BY points DESC)
QUALIFY
    player_rank < 3;
-- result:
team	player	player_rank
Hawks	Ann	1
Hawks	Bob	2
Owls	Dan	1
Owls	Eve	2
```


Equivalent query based on a `WITH` clause (without a `QUALIFY` clause):

```sql
query ??? rowsort
WITH ranked_players AS (
    SELECT
        team,
        player,
        row_number() OVER (PARTITION BY team ORDER BY points DESC) AS player_rank
    FROM scores
)
SELECT
    *
FROM ranked_players
WHERE
    player_rank < 3;
-- result:
team	player	player_rank
Hawks	Ann	1
Hawks	Bob	2
Owls	Dan	1
Owls	Eve	2
```

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

