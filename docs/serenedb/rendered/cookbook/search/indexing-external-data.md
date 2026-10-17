---
title: Indexing External Data
sidebar_position: 32
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Indexing External Data

SereneDB can create inverted indexes over external files — Parquet, CSV or ORC files on local disk or S3 — enabling full-text search, phrase queries, fuzzy matching and relevance ranking without importing data into the database. You expose the files through a view over a reader function, then index the view.

## Expose the files through a view

Define a view backed by a remote file:

```sql
CREATE VIEW logs AS
    SELECT * FROM read_parquet('s3://my-bucket/logs/2025/*.parquet');
```

Local files work the same way:

```sql
CREATE VIEW logs_csv AS
    SELECT * FROM read_csv('/data/logs/*.csv');
```

## Create a text search dictionary

Define how text columns should be tokenized:

```sql
CREATE TEXT SEARCH DICTIONARY english_dict AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false) | stem_words('en_US.UTF-8')
    WITH (frequency, position, offset);
```

## Build an inverted index

Create the index over the view. Columns without a dictionary are indexed as-is (exact matching); columns with a dictionary get full-text processing:

```sql
CREATE INDEX logs_idx ON logs
    USING inverted (id, level, service, message english_dict);
```

## Query the index

Once built, query the index by name — just like any other inverted index:

```sql
-- Full-text search ranked by relevance, combined with an exact filter
SELECT id, level, message
FROM logs_idx
WHERE message @@ ts_phrase('out of memory') AND level @@ 'ERROR'
ORDER BY BM25(logs_idx.tableoid) DESC, id;
-- result:
id	level	message
3	ERROR	out of memory while indexing
```

## Refresh the index

An external-data index holds a snapshot of the files. When they change, refresh it in one pass: behind a glob, `REINDEX INDEX` re-reads only the files that appeared, changed or disappeared. Set the `reindex_interval` index option to run the same pass on a timer ([Refreshing the index](../../sql/indexes/inverted/views.md#refreshing-the-index)).

```sql
REINDEX INDEX logs_idx;
```

## Use cases

- **Log analysis** — search through terabytes of Parquet log files on S3 without loading them into the database.
- **Data lake search** — add full-text search to your existing data lake files.
- **Archival queries** — index historical data that rarely changes but needs to be searchable.
- **Hybrid pipelines** — combine external data with local tables in the same query.

## See also

- [Working with Parquet](../file_formats/parquet_import.md)
- [CREATE INDEX](../../sql/statements/create_index/index.md)
- [CREATE TEXT SEARCH DICTIONARY](../../sql/statements/create_text_search_dictionary/index.md)
- [COPY](../../sql/statements/copy/index.md)

