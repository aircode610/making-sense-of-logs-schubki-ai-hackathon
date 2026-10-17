---
title: Pragmas
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

<!-- markdownlint-disable MD001 -->

The `PRAGMA` statement is a SQL extension adopted by SereneDB from SQLite. `PRAGMA` statements can be issued in a similar manner to regular SQL statements. `PRAGMA` commands may alter the internal state of the database engine, and can influence the subsequent execution or behavior of the engine.

`PRAGMA` statements that assign a value to an option can also be issued using the [`SET` statement](../sql/statements/set/index.md) and the value of an option can be retrieved using `SELECT current_setting(option_name)`.

For SereneDB's built in configuration options, see the [Configuration Reference](../configuration/overview.md#configuration-reference).

This page contains the supported `PRAGMA` settings.

## Metadata

#### Schema Information

List all databases:

[example configuration/pragmas/example_001 not found]

List all tables:

[example configuration/pragmas/example_002 not found]

List all tables, with extra information, similarly to [`DESCRIBE`](../cookbook/meta/describe.md):

[example configuration/pragmas/example_003 not found]

To list all functions:

[example configuration/pragmas/example_004 not found]

For queries targeting non-existing schemas, SereneDB generates “did you mean...” style error messages.
When there are thousands of attached databases, these errors can take a long time to generate.
To limit the number of schemas SereneDB looks through, use the `catalog_error_max_schemas` option:

[example configuration/pragmas/example_005 not found]

#### Table Information

Get info for a specific table:

[example configuration/pragmas/example_006 not found]

`table_info` returns information about the columns of the table with name `table_name`. The exact format of the table returned is given below:

[example configuration/pragmas/example_007 not found]

#### Database Size

Get the file and memory size of each database:

[example configuration/pragmas/example_008 not found]

`database_size` returns information about the file and memory size of each database. A database whose size cannot be read, such as an attached PostgreSQL database whose server is unreachable, is left out, and the other databases are still listed. The column types of the returned results are given below:

[example configuration/pragmas/example_009 not found]

#### Storage Information

To get storage information:

[example configuration/pragmas/example_010 not found]

This call returns the following information for the given table:

| Name           | Type      | Description                                                                                                                                        |
| -------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `row_group_id` | `BIGINT`  |                                                                                                                                                    |
| `column_name`  | `VARCHAR` |                                                                                                                                                    |
| `column_id`    | `BIGINT`  |                                                                                                                                                    |
| `column_path`  | `VARCHAR` |                                                                                                                                                    |
| `segment_id`   | `BIGINT`  |                                                                                                                                                    |
| `segment_type` | `VARCHAR` |                                                                                                                                                    |
| `start`        | `BIGINT`  | The start row id of this chunk                                                                                                                     |
| `count`        | `BIGINT`  | The amount of entries in this storage chunk                                                                                                        |
| `compression`  | `VARCHAR` | Compression type used for this column                                                                                                              |
| `stats`        | `VARCHAR` |                                                                                                                                                    |
| `has_updates`  | `BOOLEAN` |                                                                                                                                                    |
| `persistent`   | `BOOLEAN` | `false` if temporary table                                                                                                                         |
| `block_id`     | `BIGINT`  | Empty unless persistent                                                                                                                            |
| `block_offset` | `BIGINT`  | Empty unless persistent                                                                                                                            |

#### Show Databases

The following statement is equivalent to the [`SHOW DATABASES` statement](../sql/statements/attach/index.md):

[example configuration/pragmas/example_011 not found]

## Resource Management

#### Memory Limit

Set the memory limit for the buffer manager:

[example configuration/pragmas/example_012 not found]

<DocCallout type="attention">
    The specified memory limit is only applied to the buffer manager. For most queries, the buffer manager handles the majority of the data processed. However, certain in-memory data structures such as vectors and query results are allocated outside of the buffer manager. Additionally, [aggregate functions](../sql/functions/aggregates/index.md) with complex state (e.g., `list`, `mode`, `quantile`, `string_agg`, and `approx` functions) use memory outside of the buffer manager. Therefore, the actual memory consumption can be higher than the specified memory limit.
</DocCallout>

#### Threads

Set the amount of threads for parallel query execution:

[example configuration/pragmas/example_013 not found]

## Collations

List all available collations:

[example configuration/pragmas/example_014 not found]

Set the default collation to one of the available ones:

[example configuration/pragmas/example_015 not found]

## Default Ordering for NULLs

Set the default ordering for NULLs to be either `NULLS_FIRST`, `NULLS_LAST`, `NULLS_FIRST_ON_ASC_LAST_ON_DESC` or `NULLS_LAST_ON_ASC_FIRST_ON_DESC`:

[example configuration/pragmas/example_016 not found]

Set the default result set ordering direction to `ASCENDING` or `DESCENDING`:

[example configuration/pragmas/example_017 not found]

## Ordering by Non-Integer Literals

By default, ordering by non-integer literals is not allowed:

[example configuration/pragmas/example_018 not found]

To allow this behavior, use the `order_by_non_integer_literal` option:

[example configuration/pragmas/example_019 not found]

## Information on SereneDB

#### Version

Show SereneDB version:

[example configuration/pragmas/example_020 not found]

#### Platform

`platform` returns an identifier for the platform the current SereneDB executable has been compiled for, e.g., `osx_arm64`.
The format of this identifier matches the platform name:

[example configuration/pragmas/example_021 not found]

#### User Agent

The following statement returns the user agent information, e.g., `duckdb/v0.0.1(linux_arm64) cpp`:

[example configuration/pragmas/example_022 not found]

#### Metadata Information

The following statement returns information on the metadata store (`block_id`, `total_blocks`, `free_blocks`, and `free_list`):

[example configuration/pragmas/example_023 not found]

## Progress Bar

Show progress bar when running queries:

[example configuration/pragmas/example_024 not found]

Or:

[example configuration/pragmas/example_025 not found]

Don't show a progress bar for running queries:

[example configuration/pragmas/example_026 not found]

Or:

[example configuration/pragmas/example_027 not found]

## EXPLAIN Output

The output of [`EXPLAIN`](../sql/statements/profiling.md) can be configured to show only the physical plan.

The default configuration of `EXPLAIN`:

[example configuration/pragmas/example_028 not found]

To only show the optimized query plan:

[example configuration/pragmas/example_029 not found]

To show all query plans:

[example configuration/pragmas/example_030 not found]

## Profiling

### Enable Profiling

The following query enables profiling with the default format, `query_tree`.
Independent of the format, `enable_profiling` is **mandatory** to enable profiling.

[example configuration/pragmas/example_031 not found]

### Profiling Coverage

By default, the profiling coverage is set to `SELECT`.
`SELECT` runs the profiler for each operator in the physical plan of a `SELECT` statement.

[example configuration/pragmas/example_032 not found]

By default, the profiler **does not** emit profiling information for other statement types (`INSERT INTO`, `ATTACH`, etc.).
To run the profiler for all statement types, change this setting to `ALL`.

[example configuration/pragmas/example_033 not found]

### Profiling Format

The format of `enable_profiling` can be specified as `query_tree`, `json`, `query_tree_optimizer`, or `no_output`.
Each format prints its output to the configured output, except `no_output`.

The default format is `query_tree`.
It prints the physical query plan and the metrics of each operator in the tree.

[example configuration/pragmas/example_034 not found]

Alternatively, `json` returns the physical query plan as JSON:

[example configuration/pragmas/example_035 not found]

To return the physical query plan, including optimizer and planner metrics:

[example configuration/pragmas/example_036 not found]

Database drivers and other applications can also access profiling information through API calls, in which case users can disable any other output.
Even though the parameter reads `no_output`, it is essential to note that this **only** affects printing to the configurable output.
When accessing profiling information through API calls, it is still crucial to enable profiling:

[example configuration/pragmas/example_037 not found]

### Profiling Output

By default, SereneDB prints profiling information to the standard output.
However, if you prefer to write the profiling information to a file, you can use `PRAGMA` `profiling_output` to specify a filepath.

<DocCallout type="attention">
    The file contents will be overwritten for every newly issued query. Hence, the file will only contain the profiling information of the last run query:
</DocCallout>

[example configuration/pragmas/example_038 not found]

### Disable Profiling

To disable profiling:

[example configuration/pragmas/example_043 not found]

## Query Optimization

#### Optimizer

To disable the query optimizer:

[example configuration/pragmas/example_044 not found]

To enable the query optimizer:

[example configuration/pragmas/example_045 not found]

#### Selectively Disabling Optimizers

The `disabled_optimizers` option allows selectively disabling optimization steps.
For example, to disable `filter_pushdown` and `statistics_propagation`, run:

[example configuration/pragmas/example_046 not found]

The available optimizations can be queried using the [`sdb_optimizers()` table function](../sql/functions/metadata.md#sdb_optimizers).

To re-enable the optimizers, run:

[example configuration/pragmas/example_047 not found]

<DocCallout type="attention">
    The `disabled_optimizers` option should only be used for debugging performance issues and should be avoided in production.
</DocCallout>

## Logging

Set a path for query logging:

[example configuration/pragmas/example_048 not found]

Disable query logging:

[example configuration/pragmas/example_049 not found]

## Checkpointing

#### Compression

During checkpointing, the existing column data + any new changes get compressed.
There exist a couple of pragmas to influence which compression functions are considered.

##### Force Compression

Prefer using this compression method over any other method if possible:

[example configuration/pragmas/example_056 not found]

##### Disabled Compression Methods

Avoid using any of the listed compression methods from the comma separated list:

[example configuration/pragmas/example_057 not found]

#### Force Checkpoint

When `CHECKPOINT` is called when no changes are made, force a checkpoint regardless:

[example configuration/pragmas/example_058 not found]

#### Checkpoint on Shutdown

Run a `CHECKPOINT` on successful shutdown and delete the WAL, to leave only a single database file behind:

[example configuration/pragmas/example_059 not found]

Don't run a `CHECKPOINT` on shutdown:

[example configuration/pragmas/example_060 not found]

## Temp Directory for Spilling Data to Disk

By default, SereneDB uses a temporary directory named `⟨database_file_name⟩.tmp`{:.language-sql .highlight} to spill to disk, located in the same directory as the database file. To change this, use:

[example configuration/pragmas/example_061 not found]

## Returning Errors as JSON

The `errors_as_json` setting makes the [`serened` shell](../clients/serened-shell.md) report errors as raw JSON instead of a formatted message, which is easier to process programmatically. For certain errors it includes extra, decomposed fields:

[example configuration/pragmas/example_062 not found]

With the setting enabled, a failing query in the shell prints a JSON object such as:

```console
{"exception_type":"Catalog","exception_message":"Table with name nonexistent_tbl does not exist!","type":"Table","name":"nonexistent_tbl","error_subtype":"MISSING_ENTRY"}
```

Over the PostgreSQL wire protocol, errors are always returned as standard PostgreSQL error messages, regardless of this setting.

<DocCallout type="note">

The JSON error format applies to SereneDB's native interface. When connected over the PostgreSQL wire protocol (for example via `psql` or any PostgreSQL driver), errors are always delivered through the standard PostgreSQL error fields, so `errors_as_json` has no visible effect on the client.

</DocCallout>

## IEEE Floating-Point Operation Semantics

SereneDB follows IEEE floating-point operation semantics. If you would like to turn this off, run:

[example configuration/pragmas/example_064 not found]

In this case, floating point division by zero (e.g., `1.0 / 0.0`, `0.0 / 0.0` and `-1.0 / 0.0`) will all return `NULL`.

## Query Verification (for Development)

The following `PRAGMA`s are mostly used for development and internal testing.

Enable force parallel query processing:

[example configuration/pragmas/example_067 not found]

Disable force parallel query processing:

[example configuration/pragmas/example_068 not found]

## Block Sizes

When persisting a database to disk, SereneDB writes to a dedicated file containing a list of blocks holding the data.
In the case of a file that only holds very little data, e.g., a small table, the default block size of 256 kB might not be ideal.
Therefore, SereneDB's storage format supports different block sizes.

There are a few constraints on possible block size values.

-   Must be a power of two.
-   Must be greater or equal to 16384 (16 kB).
-   Must be lesser or equal to 262144 (256 kB).

You can set the default block size for all new SereneDB files created by an instance like so:

[example configuration/pragmas/example_069 not found]

It is also possible to set the block size on a per-file basis, see [`ATTACH`](../sql/statements/attach/index.md) for details.

