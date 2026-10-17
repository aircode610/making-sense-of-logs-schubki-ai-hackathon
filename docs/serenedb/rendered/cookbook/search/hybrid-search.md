---
title: Semantic and Hybrid Search
sidebar_position: 16
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Semantic and Hybrid Search

Keyword search matches the words a shopper typed. Vector search matches what they meant. SereneDB stores both a text field and its embedding in one [inverted index](../../sql/indexes/inverted/index.md), so you can rank by meaning, filter by keyword and fuse the two without leaving the query. This recipe walks from a plain nearest-neighbor search up to a hybrid that catches results keyword search alone would miss.

Five products sit in an `items` table, each with a `name` and a three-dimensional `emb` vector. In production you fill `emb` by running the text through an embedding model and storing the vector it returns, usually hundreds of dimensions wide. The three numbers here are written by hand so the distances stay easy to read: the first axis is roughly "made for running". `emb` is indexed with `ivf` on the `l2` metric, so `<->` gives Euclidean distance and smaller means closer.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY en AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE items (id INTEGER PRIMARY KEY, name VARCHAR, emb FLOAT[3]);

CREATE INDEX items_idx ON items
    USING inverted (id, name en, emb ivf (metric = 'l2'));

INSERT INTO items VALUES
(1, 'trail running shoe', [1.0, 0.0, 0.0]::FLOAT[3]),
(2, 'road running shoe',  [0.9, 0.1, 0.0]::FLOAT[3]),
(3, 'leather dress shoe', [0.0, 1.0, 0.0]::FLOAT[3]),
(4, 'wireless earbuds',   [0.0, 0.0, 1.0]::FLOAT[3]),
(5, 'marathon racer',     [0.95, 0.05, 0.0]::FLOAT[3]);

VACUUM (REFRESH_TABLE) items;
```

</details>

## Rank by meaning

`emb <-> query` is the distance from each row to your query vector. Order by it, take the top k and you have semantic search. Notice "marathon racer" ranks second even though it shares no words with a running query, because its embedding sits right next to the running shoes.

```sql
SELECT id, name,
       round((emb <-> [1.0, 0.0, 0.0]::FLOAT[3])::numeric, 3) AS distance
FROM items_idx
ORDER BY distance, id
LIMIT 3;
-- result:
id	name	distance
1	trail running shoe	0.000
5	marathon racer	0.071
2	road running shoe	0.141
```

## Where keyword search falls short

Search the word "running" and you only get the rows that literally contain it. "Marathon racer" is exactly what the shopper wants and it is nowhere to be found.

```sql
SELECT id, name FROM items_idx WHERE name @@ 'running' ORDER BY id;
-- result:
id	name
1	trail running shoe
2	road running shoe
```

## Filter by keyword, rank by vector

The simplest hybrid uses the keyword match as a hard filter and the vector as the sort. Great when the keyword is a firm requirement and you just want the closest matches ordered by meaning.

```sql
SELECT id, name
FROM items_idx
WHERE name @@ 'shoe'
ORDER BY emb <-> [1.0, 0.0, 0.0]::FLOAT[3], id
LIMIT 2;
-- result:
id	name
1	trail running shoe
2	road running shoe
```

## Fuse both with reciprocal rank fusion

When neither signal should be a gate, run both and blend the rankings with [reciprocal rank fusion](./reciprocal-rank-fusion.md). The one thing that changes when a branch ranks by vector distance is the sort direction: BM25 scores are better when *higher* (`ORDER BY s DESC`), but distance is better when *smaller*, so the vector branch ranks ascending (`ORDER BY dist`). Flip either one and the fusion rewards the worst matches of that branch.

Fused, "marathon racer" finally surfaces: the keyword branch never sees it, but the vector branch ranks it high enough to make the cut.

```sql
WITH fused AS (
    SELECT id, RANK() OVER (ORDER BY s DESC) AS rank FROM (
        SELECT id, BM25(items_idx.tableoid) AS s
        FROM items_idx
        WHERE name @@ 'running'
        ORDER BY s DESC LIMIT 100
    ) lex
    UNION ALL
    SELECT id, RANK() OVER (ORDER BY dist) AS rank FROM (
        SELECT id, emb <-> [1.0, 0.0, 0.0]::FLOAT[3] AS dist
        FROM items_idx
        ORDER BY dist LIMIT 100
    ) vec
)
SELECT id
FROM fused
GROUP BY id
ORDER BY SUM(1.0 / (60 + rank)) DESC, id
LIMIT 4;
-- result:
id
1
2
5
3
```

## See also

- [Vector Search guide](../../sql/indexes/inverted/vector-search.md): building `ivf` indexes, choosing a metric and tuning recall
- [Hybrid Search guide](../../sql/indexes/inverted/hybrid-search.md): the filtered-ANN and fusion strategies in depth
- [Reciprocal Rank Fusion](./reciprocal-rank-fusion.md): the fusion pattern on its own, for blending any two ranked queries
- [Vector functions reference](../../sql/functions/vector.md): `l2_distance`, `cosine_distance` and the distance operators

