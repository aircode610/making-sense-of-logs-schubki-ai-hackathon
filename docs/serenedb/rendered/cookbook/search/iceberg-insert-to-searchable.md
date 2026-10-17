---
title: Search over Iceberg
sidebar_position: 33
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Search over Iceberg: insert → searchable

An Iceberg table in your own object storage is the source of truth; SereneDB keeps a derived search index over it. Any engine — Spark, BigQuery, Flink, SereneDB itself — writes rows to the table; one `REINDEX` makes everything committed before it searchable, atomically. Full-text (BM25), vector similarity and hybrid queries then run against the index in one SQL statement.

```mermaid
flowchart LR
    w["writers<br/>Spark · BigQuery · SereneDB · any engine"] -->|"INSERT / UPDATE / DELETE<br/>atomic commits"| t[("Iceberg table<br/>object storage + REST catalog")]
    t -->|"REINDEX INDEX<br/>the freshness barrier"| idx[("inverted index<br/>BM25 · IVF vectors · filters")]
    q["queries<br/>full-text · semantic · hybrid"] --> idx
    idx -.->|"non-indexed columns:<br/>fetched per matched row"| t
```

What lives where:

- **The Iceberg table** (your bucket, your catalog) holds the rows — text, metadata, embeddings — as plain Parquet. It stays fully yours: every engine can read and write it, and `REINDEX` picks up foreign commits, updates and deletes the same way.
- **SereneDB** holds only the derived index (term dictionaries, vector structures, indexed columns) on local disk. There is no second copy of the corpus — lose the node, rebuild the index from the table. Columns you did not index are still selectable: they are materialized from the source Parquet at query time, only for the rows a query matched.

## How REINDEX refreshes

`REINDEX INDEX <name>` runs one pass: it compares the current source state against what the index holds, applies the difference, and publishes atomically — readers see the previous complete state or the new one, never a partial index. Iceberg tables and file globs refresh **incrementally** (only the difference is indexed); other sources rebuild in full — the [per-source table in the reference](../../sql/indexes/inverted/views.md#refreshing-the-index) has the details.

The rest of this page builds both delta roads from zero — first the Iceberg pipeline, then the same lifecycle over a plain directory of files.

## Connect the object store

The warehouse data lives in object storage; give SereneDB credentials for it. A `PERSISTENT SECRET` survives restarts:

```sql
CREATE PERSISTENT SECRET chunks_store (
    TYPE S3,
    KEY_ID '⟨access key⟩',
    SECRET '⟨secret key⟩',
    REGION '⟨us-east-1⟩',
    SCOPE 's3://⟨bucket⟩/⟨warehouse prefix⟩/'
);
```

## Attach the catalog

`CREATE SERVER` attaches the Iceberg REST catalog as a database. The server row persists in the SereneDB catalog and re-attaches at boot, so everything built on it survives restarts unattended. `max_table_staleness` bounds how old a cached table version may be served between refreshes:

```sql
CREATE SERVER chunks_catalog FOREIGN DATA WRAPPER iceberg_fdw OPTIONS (
    warehouse '⟨warehouse⟩',
    endpoint '⟨https://your-rest-catalog/iceberg/v1/restcatalog⟩',
    authorization_type '⟨oauth2⟩', token '⟨...⟩',
    max_table_staleness '10 minutes'
);
```

## Create the table

Skip this if the table already exists — the point of the pattern is that any engine may own it. Created from SereneDB it is a regular Iceberg table like any other:

```sql
CREATE SCHEMA chunks_catalog.docs;

CREATE TABLE chunks_catalog.docs.chunks (
    entity_id INTEGER,
    source_name TEXT,
    page_number INTEGER,
    uri TEXT,
    body TEXT,
    emb FLOAT[]
);
```

## Index it

Expose the table through a view (casting the embedding list to a fixed-size vector) that names it by its full path, `chunks_catalog.docs.chunks`, so searches never have to look it up in the catalog ([why](../../sql/indexes/inverted/views.md#referencing-the-source)). Then index the view: filter columns as plain terms, the text column through an analyzer for BM25, the vector column with IVF for similarity search. See [Indexes over views](../../sql/indexes/inverted/views.md) for everything the index can do:

```sql
CREATE TEXT SEARCH DICTIONARY en AS
    split_text() | stem_words('en_US.UTF-8')
    WITH (frequency, position);

CREATE VIEW chunks_v AS
    SELECT entity_id, source_name, page_number, uri, body,
           emb::FLOAT[3072] AS emb
    FROM chunks_catalog.docs.chunks;

CREATE INDEX chunks_idx ON chunks_v USING inverted(
    entity_id, source_name, page_number,
    body en,
    emb ivf (metric = 'cosine'));
```

## The freshness barrier

Writers commit batches to the table; `REINDEX INDEX` runs one pass and returns only when everything committed before it is searchable. That makes freshness a one-statement barrier in any pipeline — load the data, run `REINDEX`, start the consumers:

```sql
INSERT INTO chunks_catalog.docs.chunks VALUES (...);

REINDEX INDEX chunks_idx;
-- returns only when everything committed before it is searchable
```

Everything from the batch is now in the index:

[example cookbook/search/insert_to_searchable_iceberg/example_barrier_check: empty]

## New data keeps arriving

Each commit adds Parquet files to the table; the next pass indexes **only those** — the three rows already indexed above are not re-read:

```sql
INSERT INTO chunks_catalog.docs.chunks VALUES (...);

REINDEX INDEX chunks_idx;
```

[example cookbook/search/insert_to_searchable_iceberg/example_add_check: empty]

To run the pass on a schedule instead of by hand, set the [`reindex_interval`](../../sql/indexes/inverted/views.md#automatic-refresh) index option — the loop survives server restarts.

## Query

Vector similarity, scoped to a filter — everything below answers from the index:

```sql
SELECT source_name, page_number, body
FROM chunks_idx
WHERE entity_id = ⟨tenant⟩
ORDER BY emb <=> ⟨query vector⟩ LIMIT 5;
```

Hybrid — full-text filter plus semantic ranking in one statement:

```sql
SELECT source_name, page_number, body
FROM chunks_idx
WHERE entity_id = ⟨tenant⟩ AND body @@ ts_phrase('scope 3')
ORDER BY emb <=> ⟨query vector⟩ LIMIT 5;
```

Selecting a column the index does not hold (`uri` here) still works: it is fetched from the source Parquet at query time, only for the matched rows:

```sql
SELECT source_name, uri, body
FROM chunks_idx
WHERE entity_id = ⟨tenant⟩ AND body @@ ts_phrase('carbon emissions')
LIMIT 5;
```

## Updates

Rewrite rows in the table — from SereneDB or any other engine — and the next pass reindexes just the affected files:

```sql
UPDATE chunks_catalog.docs.chunks
SET body = '⟨new text⟩'
WHERE source_name = '⟨name⟩' AND page_number = ⟨n⟩;

REINDEX INDEX chunks_idx;
```

The search sees the new text, not the old:

[example cookbook/search/insert_to_searchable_iceberg/example_update_check: empty]

## Deletes

Deletes are the same story. Drop one document:

```sql
DELETE FROM chunks_catalog.docs.chunks WHERE source_name = '⟨name⟩';

REINDEX INDEX chunks_idx;
```

Its rows are gone; everything else never left the index:

[example cookbook/search/insert_to_searchable_iceberg/example_delete_check: empty]

## The same over plain files

No catalog at all — a directory of Parquet (or CSV, JSON) files behaves the same way, locally or on S3. Index a view over a glob:

```sql
COPY (SELECT 1 AS id, 'pallets arrive at the northern dock' AS body)
    TO '⟨dir⟩/batch1.parquet' (FORMAT parquet);

CREATE VIEW events_v AS SELECT * FROM read_parquet('⟨dir⟩/*.parquet');

CREATE INDEX events_idx ON events_v USING inverted(id, body en);
```

A new file lands in the directory — the pass picks up **just that file**:

```sql
COPY (SELECT 2 AS id, 'customs cleared the second shipment' AS body)
    TO '⟨dir⟩/batch2.parquet' (FORMAT parquet);

REINDEX INDEX events_idx;
```

[example cookbook/search/insert_to_searchable_iceberg/example_glob_add_check: empty]

A file disappears — the next pass drops its rows:

```sql
rm ⟨dir⟩/batch1.parquet
```

```sql
REINDEX INDEX events_idx;
```

[example cookbook/search/insert_to_searchable_iceberg/example_glob_remove_check: empty]

