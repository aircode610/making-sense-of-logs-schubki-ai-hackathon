---
title: Indexing Views
sidebar_position: 31
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Indexing Views

An [inverted index](../../sql/indexes/inverted/index.md) in SereneDB is a named relation, and you can build it on a [view](../../sql/indexes/inverted/views.md) just as easily as on a table. That is the hook for searching anything a view can express: a projection of a table, a join, a union or a pile of [Parquet and CSV files](./indexing-external-data.md). You point the index at the view and query the index relation, and every search feature works the same as on a table.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY en AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE docs (id INTEGER PRIMARY KEY, body VARCHAR, category VARCHAR);

INSERT INTO docs VALUES
(1, 'quick brown fox',        'animal'),
(2, 'lazy dog sleeps',        'animal'),
(3, 'quick red fox',          'animal'),
(4, 'distributed sql engine', 'tech'),
(5, 'quick sql query',        'tech');

CREATE VIEW v_docs AS SELECT id, body, category FROM docs;

CREATE INDEX v_docs_idx ON v_docs USING inverted (id, body en, category);
```

</details>

## Index a view and search it

Build the index on the view with `CREATE INDEX ... ON v_docs USING inverted(...)`, then query the index relation `v_docs_idx`. Full-text `@@` and [BM25](./ranking.md) ranking work exactly as they do on a table-backed index.

```sql
SELECT id, body
FROM v_docs_idx
WHERE body @@ 'quick'
ORDER BY BM25(v_docs_idx.tableoid) DESC, id;
-- result:
id	body
1	quick brown fox
3	quick red fox
5	quick sql query
```

## Facet through it

`GROUP BY` and the [`ts_dict_*`](../../sql/functions/search/term-dictionary.md) aggregates read that same index, so faceting a search over a view is no different from faceting one over a table.

```sql
SELECT category, count(*) AS n
FROM v_docs_idx
WHERE body @@ 'quick'
GROUP BY category
ORDER BY category;
-- result:
category	n
animal	2
tech	1
```

## A reusable saved search

Wrap a search in a view and it becomes a named query you point applications at. Callers add their own predicates on top and they fuse into the same index scan, so `recent_hits` filtered by category stays a single indexed lookup, not a scan over the results. Re-point it with `CREATE OR REPLACE VIEW` when you want the name to follow a new search, which is how you stand in for an index alias.

```sql
SELECT id, body
FROM recent_hits
WHERE category = 'animal'
ORDER BY id;
-- result:
id	body
1	quick brown fox
3	quick red fox
```

## No materialized views

SereneDB has no `MATERIALIZED VIEW`. You do not need one here: an index built on a view over a base table already holds a postings snapshot that only moves when you run `REINDEX INDEX` or set `reindex_interval`, which covers the usual reason to reach for a materialized view in the first place.

## See also

- [Indexing Views](../../sql/indexes/inverted/views.md): the reference on building an index over a view, including the `pk` rule for union and join views
- [Indexing External Data](./indexing-external-data.md): the real payoff, an index over a view of Parquet, CSV or S3 files
- [Migrating from Elasticsearch](../../sql/indexes/inverted/migrating-from-elasticsearch.md): where index aliases map to views

