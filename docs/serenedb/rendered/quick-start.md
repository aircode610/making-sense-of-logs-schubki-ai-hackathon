---
title: Quick Start
sidebar_position: 1
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

# Quick Start

SereneDB is a search-OLAP database: one engine that runs full-text search, vector (semantic) search and analytical queries over the same data. It speaks the PostgreSQL wire protocol and SQL, so your existing clients and drivers just work. It ships as a single binary with nothing else to run.

## Install

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs>
<TabItem value="docker" label="DOCKER" default>

```sh
curl https://install.serenedb.com | sh
```

Or run the image directly:

```sh
docker run -d --name serenedb -p 7890:7890 serenedb/serenedb
```

</TabItem>
<TabItem value="linux" label="LINUX">

```sh
curl https://linux.serenedb.com | sh
```

Direct downloads are available on the [GitHub releases page](https://github.com/serenedb/serenedb/releases).

</TabItem>
</Tabs>

## Connect

SereneDB speaks the PostgreSQL wire protocol. Connect with `psql` or any PostgreSQL-compatible client:

```sh
psql -h localhost -p 7890
```

No credentials are required by default.

## AI search in 60 seconds

Everything from here runs in that one session. Load a real dataset, generate embeddings, index it for full-text and vector search, then query it — lexical, semantic and analytical — over the same data, with no second system and no data copies.

### Load data from Hugging Face

SereneDB reads Parquet, CSV and JSON directly from object storage, HTTP and the Hugging Face Hub — no import job and no schema to define up front. Point a `CREATE TABLE` at a remote dataset and it lands as an ordinary table:

```sql
CREATE TABLE movies AS
    SELECT id, title, overview,
           split_part(genres, '-', 1) AS genre,
           vote_average, vote_count
    FROM read_parquet('hf://datasets/wykonos/movies@~parquet/default/train/*.parquet')
    WHERE overview IS NOT NULL AND vote_count > 1000;
```

That is a real public dataset of films, read over the network in one statement. You can also skip loading entirely and index files **in place** on S3 or disk — see [zero-ETL search over external data](sql/indexes/inverted/external-data.md).

### Ask an analytical question

`movies` behaves like any SQL table. Aggregate it the way you would in any analytical database:

```sql
SELECT genre, COUNT(*) AS films, ROUND(AVG(vote_average), 2) AS avg_rating
FROM movies
GROUP BY genre
ORDER BY avg_rating DESC, genre;
-- result:
genre	films	avg_rating
Action	1	8.2
Science Fiction	4	8.13
Horror	1	8.1
Animation	2	8.05
Drama	2	7.85
Romance	2	7.85
```

### Generate embeddings

To search by *meaning* and not just keywords, turn each overview into an embedding vector. [`ai_embed`](sql/functions/ai.md) calls an embedding model straight from SQL and returns a vector you store in a fixed-size `FLOAT[N]` column — no pipeline, no separate vector service:

```sql
ALTER TABLE movies ADD COLUMN embedding FLOAT[4];

UPDATE movies
SET embedding = ai_embed(overview, 'text-embedding-3-small', 'openai');
```

The provider is configured once with [`CREATE SECRET`](sql/statements/create_secret/index.md); any OpenAI-compatible endpoint works, including a local [Ollama](https://ollama.com/) server.

### Index for full-text and vector search

A single [inverted index](sql/indexes/inverted/index.md) covers both worlds: a [text analyzer](sql/indexes/inverted/text-analysis.md) over the text columns and an `ivf` index over the embedding. Lexical and semantic search share one index, beside the columnar data:

```sql
CREATE TEXT SEARCH DICTIONARY english AS
    split_text(case := 'lower')
    WITH (frequency, position, offset);

CREATE INDEX movies_idx ON movies
    USING inverted(id, title english, overview english, embedding ivf (metric = 'cosine'));

VACUUM (REFRESH_TABLE) movies;
```

### Full-text search

Query the index by name, match text with the [`@@` operator](sql/indexes/inverted/full-text-search.md) and a query constructor like `ts_phrase`, then [rank by `BM25`](sql/indexes/inverted/ranking.md):

```sql
SELECT title, genre, ROUND(BM25(movies_idx.tableoid)::NUMERIC, 3) AS score
FROM movies_idx
WHERE overview @@ ts_phrase('falls in love')
ORDER BY score DESC, title;
-- result:
title	genre	score
The Notebook	Romance	3.076
Titanic	Romance	3.076
```

### Hybrid search: lexical and semantic

This is where SereneDB pulls ahead. A full-text predicate narrows to the rows that *mention* a term; the `<=>` distance to a query embedding ranks them by what they actually *mean* — both in one statement, against one index. Embed the query text at search time with the same `ai_embed`:

```sql
SELECT title, genre
FROM   movies_idx
WHERE  overview @@ 'space'                                   -- lexical recall
ORDER  BY embedding <=> ai_embed('space exploration',
                                 'text-embedding-3-small', 'openai')
LIMIT  3;                                                    -- semantic ranking
```

Of the four films whose overview mentions "space", semantic ranking surfaces the three that are really *about* space exploration — and drops *WALL-E*, which is set in space but is, at heart, a kids' animation.

### Search and analytics, one query

The same index feeds aggregation directly. The search predicate selects a candidate set; the `GROUP BY` runs over it — in a single statement, on one engine:

```sql
SELECT genre, COUNT(*) AS matches, ROUND(AVG(vote_average), 2) AS avg_rating
FROM movies_idx
WHERE overview @@ 'space'
GROUP BY genre
ORDER BY matches DESC, genre;
-- result:
genre	matches	avg_rating
Science Fiction	2	8.05
Animation	1	8.1
Drama	1	8.1
```

<DocCallout type="bestPractice" title="One engine, one query">
Full-text recall, semantic ranking and a `GROUP BY` over the same data — no search cluster to sync, no vector store to feed, no warehouse to copy into, no glue code between them.
</DocCallout>

## Next steps

Start with the concepts, then dive into the search type you need:

- [Inverted Index](sql/indexes/inverted/index.md) — how it works, the query model, mixing field types in one index
- [Text Analysis](sql/indexes/inverted/text-analysis.md) — dictionaries, tokenizers and the index-time = query-time rule
- [What to Index](sql/indexes/inverted/modeling.md) — columns, expressions, generated columns, JSON and `VARIANT`

Query types:

- [Full-Text Search](sql/indexes/inverted/full-text-search.md) — the `@@` operator, phrases, fuzzy, boolean queries
- [Ranking](sql/indexes/inverted/ranking.md) — BM25 and other scorers, boosting, top-K / WAND
- [Vector Search](sql/indexes/inverted/vector-search.md) — IVF indexing, kNN and range search
- [Hybrid Search](sql/indexes/inverted/hybrid-search.md) — combine full-text filters with vector ranking
- [Geospatial Search](sql/indexes/inverted/geospatial-search.md) — `ST_*` predicates over GeoJSON / `GEOMETRY`

Going further:

- [Indexing External Data](sql/indexes/inverted/external-data.md) — zero-ETL search over a Parquet / CSV / JSON / Iceberg data lake
- [Maintenance & Introspection](sql/indexes/inverted/maintenance.md) — refresh, compaction and inspecting indexes
- [Migrating from Elasticsearch](sql/indexes/inverted/migrating-from-elasticsearch.md) — feature mapping, including aggregations
- [AI Functions](sql/functions/ai.md) — generate embeddings with `ai_embed`

