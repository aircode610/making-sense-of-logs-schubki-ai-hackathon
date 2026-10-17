---
title: SET / RESET
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `SET` statement modifies the provided SereneDB [configuration option](../../../configuration/overview.md) at the specified scope.

## Examples

Update the `memory_limit` configuration value:

[example sql/statements/set/index/example_001 not found]

Run the queries of the current session on `1` thread:

[example sql/statements/set/index/example_002 not found]

Or use the `TO` keyword:

[example sql/statements/set/index/example_003 not found]

Change configuration option to default value:

[example sql/statements/set/index/example_004 not found]

Retrieve configuration value:

[example sql/statements/set/index/example_005 not found]

Set the default collation for the session:

[example sql/statements/set/index/example_006 not found]

### Set a Global Variable

Set the default sort order globally:

[example sql/statements/set/index/example_007 not found]

Size the thread pool of the whole instance to `4` threads:

[example sql/statements/set/index/example_008 not found]

`GLOBAL` settings persist across the whole instance and outlive the session that set them, so reset them with `RESET GLOBAL` once the override is no longer needed:

[example sql/statements/set/index/example_009 not found]

[example sql/statements/set/index/example_010 not found]

### Threads

What `threads` changes depends on the scope it is set in. `SET GLOBAL threads` sizes the pool of worker threads the whole instance runs queries on. A session value (`SET threads`, `SET SESSION threads`) or a transaction value (`SET LOCAL threads`) leaves the pool alone and caps how many of its threads each query of that session or transaction runs on; a cap larger than the pool has no effect until the pool grows. `SHOW threads` returns the cap when one is set and the pool size otherwise. `RESET threads` drops the session's cap, `RESET GLOBAL threads` sizes the pool back to its default.

Run the queries of one transaction on at most `2` threads:

[example sql/statements/set/index/example_011 not found]

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram1" />

`SET` updates a SereneDB configuration option to the provided value.

## `RESET`

<RailroadDiagram source={RailroadSource} production="rrdiagram2" />

The `RESET` statement changes the given SereneDB configuration option to the default value.

## Scopes

Configuration options can have different scopes:

-   `GLOBAL`: Configuration value is used (or reset) across the entire SereneDB instance.
-   `SESSION`: Configuration value is used (or reset) only for the current session attached to a SereneDB instance.
-   `LOCAL`: Configuration value is used only until the current transaction ends, then the session value returns. `SET LOCAL` outside a transaction block is an error.

When not specified, the default scope for the configuration option is used. The `sdb_` search settings and `integer_division` default to the session. Engine options such as `default_null_order`, `preserve_insertion_order` and `enable_progress_bar` default to `GLOBAL`, so a plain `SET` changes them for every session on the server; write `SET SESSION` to keep the change to your own. A few options, such as `memory_limit`, exist only globally: `SET SESSION` and `SET LOCAL` refuse them with `option "<name>" cannot be set locally`. `threads` takes all three scopes, see [Threads](#threads).

## Configuration

See the [Configuration](../../../configuration/overview.md) page for the full list of configuration options.

