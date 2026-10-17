---
title: Overview
sidebar_position: 1
redirect_from:
- /docs/guides/import/overview
- /docs/guides/performance/import
- /docs/preview/guides/performance/import
- /docs/stable/guides/performance/import
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

The first step to using a database system is to insert data into that system.
SereneDB can directly connect to many popular data sources — file formats, cloud storage, and database systems — and offers several data ingestion methods that allow you to easily and efficiently fill up the database.
On this page, we provide an overview of these methods so you can select which one is best suited for your use case.

## Recommended Import Methods

When importing data from another system into SereneDB, we recommend the following order:

1. If the source system has a bulk export feature, export the data to Parquet or CSV, then load it with SereneDB's [Parquet](../data_import_and_export/parquet/overview.md) or [CSV](../data_import_and_export/csv/overview.md) reader.
2. If that is not possible, stream the rows over the PostgreSQL [`COPY ... FROM STDIN`](../sql/statements/copy/index.md) protocol. Every PostgreSQL driver exposes it — for example libpq's `PQputCopyData`, psycopg's `copy`, JDBC's `CopyManager` or Go's `pq.CopyIn` — and it is far faster than row-by-row `INSERT`s.

Avoid looping row-by-row (tuple-at-a-time): performing row-by-row inserts — even with prepared statements — is detrimental to performance and results in slow load times. Prefer bulk operations instead.

<DocCallout type="bestPractice">
Unless your data is small (`<100k rows`), avoid using inserts in loops. See the [`INSERT` statement page](../data_import_and_export/insert.md) for more detail.
</DocCallout>

## `INSERT` Statements

`INSERT` statements are the standard way of loading data into a database system. They are suitable for quick prototyping, but should be avoided for bulk loading as they have significant per-row overhead.

```sql
INSERT INTO people VALUES (1, 'Mark');
```

For a more detailed description, see the [page on the `INSERT` statement](../data_import_and_export/insert.md).

## File Loading: Relative Paths

Use the configuration option [`file_search_path`](../configuration/overview.md#local-configuration-options) to configure to which “root directories” relative paths are expanded on.
If `file_search_path` is not set, the working directory is used as the basis for relative paths.

## File Formats

### CSV Loading

Data can be efficiently loaded from CSV files using several methods. The simplest is to use the CSV file's name:

```sql
SELECT * FROM 'test.csv';
```

Alternatively, use the [`read_csv` function](../data_import_and_export/csv/overview.md) to pass along options:

```sql
SELECT * FROM read_csv('test.csv', header = false);
```

Or use the [`COPY` statement](../sql/statements/copy/index.md#copy--from):

```sql
COPY tbl FROM 'test.csv' (HEADER false);
```

It is also possible to read data directly from **compressed CSV files** (e.g., compressed with [gzip](https://www.gzip.org/)):

```sql
SELECT * FROM 'test.csv.gz';
```

SereneDB can create a table from the loaded data using the [`CREATE TABLE ... AS SELECT` statement](../sql/statements/create_table/index.md#create-table--as-select-ctas):

```sql
CREATE TABLE test AS
    SELECT * FROM 'test.csv';
```

For more details, see the [page on CSV loading](../data_import_and_export/csv/overview.md).

### Parquet Loading

Parquet files can be efficiently loaded and queried using their filename:

```sql
SELECT * FROM 'test.parquet';
```

Alternatively, use the [`read_parquet` function](../data_import_and_export/parquet/overview.md):

```sql
SELECT * FROM read_parquet('test.parquet');
```

Or use the [`COPY` statement](../sql/statements/copy/index.md#copy--from):

```sql
COPY tbl FROM 'test.parquet';
```

For more details, see the [page on Parquet loading](../data_import_and_export/parquet/overview.md).

### JSON Loading

JSON files can be efficiently loaded and queried using their filename:

```sql
SELECT * FROM 'test.json';
```

Alternatively, use the [`read_json_auto` function](../data_import_and_export/json/overview.md):

```sql
SELECT * FROM read_json_auto('test.json');
```

Or use the [`COPY` statement](../sql/statements/copy/index.md#copy--from):

```sql
COPY tbl FROM 'test.json';
```

For more details, see the [page on JSON loading](../data_import_and_export/json/overview.md).

### Returning the Filename

In SereneDB the CSV, JSON and Parquet readers support the `filename` virtual column:

```sql
COPY (FROM (VALUES (42), (43)) t(x)) TO 'test.parquet';

SELECT *, filename FROM 'test.parquet';
```

