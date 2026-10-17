---
title: VACUUM
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

`VACUUM` serves two roles in SereneDB. On standard tables it is a PostgreSQL-compatible no-op, accepted so that existing tooling keeps working. It is also extended with options that maintain SereneDB's [inverted indexes](../create_index/index.md).

## Standard `VACUUM` and `ANALYZE`

On a standard table `VACUUM` does no work — it is accepted purely for PostgreSQL compatibility.

The bare form:

```sql
VACUUM;
```

`ANALYZE` is accepted as well:

```sql
VACUUM ANALYZE;
```

Targeting a specific table, optionally with a column list, is also accepted and is likewise a no-op:

```sql
VACUUM my_table(name);
```

```sql
VACUUM ANALYZE my_table(name);
```

`VACUUM FULL` is not supported:

```sql
VACUUM FULL;
```

## Inverted Index Maintenance

SereneDB extends `VACUUM` with options that maintain [inverted indexes](../create_index/index.md). A statement takes **at most one** of these options, and an extension option cannot be combined with standard options such as `ANALYZE`. The options fall into three families.

### Refreshing — `REFRESH_*`

Inverted indexes are eventually consistent: rows you `INSERT`, `UPDATE` or `DELETE` may not be visible to queries until the index is refreshed. `REFRESH_*` publishes pending writes to readers. After writing to an indexed table, refresh it so the new rows become searchable:

```sql
INSERT INTO articles VALUES (1, 'the quick brown fox');

VACUUM (REFRESH_TABLE) articles;

SELECT count(*) FROM articles_idx WHERE body @@ ts_phrase('fox');
-- result:
count
1
```

### Compacting — `COMPACT_*`

`COMPACT_*` merges index segments to reclaim space and keep queries fast. It does not change query results:

```sql
VACUUM (COMPACT_TABLE) articles;
```

Inverted indexes and search tables also compact in the background by default (see [Background compaction](../../indexes/inverted/maintenance.md#background-compaction)); `COMPACT_*` merges on demand, including when background compaction is disabled. A search table is merged into a single segment. Set `sdb_compact_target_segments` to `N` to stop at `N` segments instead: the segments are split into `N` disjoint groups and each group is merged into one segment, so no single merge holds the whole table.

```sql
SET sdb_compact_target_segments = 4;

VACUUM (COMPACT_TABLE) docs_store;

RESET sdb_compact_target_segments;
```

### Recomputing statistics — `RECOMPUTE_STATS_*`

`RECOMPUTE_STATS_*` recomputes the index statistics used for relevance scoring and planning:

```sql
VACUUM (RECOMPUTE_STATS_TABLE) articles;
```

### Scopes

Each option applies at the scope named by its suffix and takes the matching object name as its argument:

| Scope | `REFRESH` | `COMPACT` | `RECOMPUTE_STATS` | Argument |
|---|---|---|---|---|
| Index | `REFRESH_INDEX` | `COMPACT_INDEX` | — | index name |
| Table | `REFRESH_TABLE` | `COMPACT_TABLE` | `RECOMPUTE_STATS_TABLE` | table name |
| Schema | `REFRESH_SCHEMA` | `COMPACT_SCHEMA` | `RECOMPUTE_STATS_SCHEMA` | `[database.]schema` |
| Database | `REFRESH_DATABASE` | `COMPACT_DATABASE` | `RECOMPUTE_STATS_DATABASE` | database name |
| Everything | `REFRESH_ALL` | `COMPACT_ALL` | `RECOMPUTE_STATS_ALL` | *(none)* |

`RECOMPUTE_STATS` additionally accepts a column scope, `RECOMPUTE_STATS_COLUMN`, whose argument is `[schema.]table.column`.

Object names may be qualified, for example `VACUUM (REFRESH_TABLE) mydb.public.articles`. The `*_ALL` scopes are instance-wide and take no argument.

### Combining options

A statement accepts at most one maintenance option, and a maintenance option cannot be mixed with standard `VACUUM` options such as `ANALYZE`:

```sql
VACUUM (REFRESH_TABLE, ANALYZE) my_table;
-- result:
db error: ERROR: VACUUM SereneDB option 'refresh_table' cannot be combined with standard VACUUM options
```

The `vacuum_rebuild_indexes` setting that governs index rebuilds is fixed at startup and cannot be changed while the database is running:

```sql
SET vacuum_rebuild_indexes = 1000000;
```

## Reclaiming Space

The `VACUUM` statement does not reclaim space.
To reclaim space, use the `CHECKPOINT` statement or compact the database by creating a fresh copy with the [`COPY FROM DATABASE` statement](../copy/index.md#copy-from-database--to).

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram1" />

See the [scope table](#scopes) for the valid `( … )` maintenance options and their arguments.

