---
title: Finding Similar Documents
sidebar_position: 17
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Finding Similar Documents

Point at one row and get back the rows most like it. That is more-like-this: the related-articles rail under a support page, the "you might also want" list, the pass that flags an article someone published twice. It runs on embeddings, so two documents count as similar when their vectors sit close together even when they share no words. This is a different job from typing a query into a search box and ranking by it. For that reach for the [Semantic and Hybrid Search](./hybrid-search.md) recipe. Here the probe is always an existing row.

Eight help-center articles carry a `title` and a three-dimensional `emb`. The three numbers are written by hand so the distances read cleanly: the axes stand in for account, billing and connectivity topics. `emb` is indexed with `ivf` on the `l2` metric, so `<->` gives Euclidean distance and smaller means closer. Two pairs of articles hold the same content under a reworded title, which is exactly what the near-duplicate pass exists to catch.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TABLE articles (id INTEGER PRIMARY KEY, title VARCHAR, emb FLOAT[3]);

CREATE INDEX articles_idx ON articles
    USING inverted (id, title, emb ivf (metric = 'l2'));

INSERT INTO articles VALUES
(1, 'Reset your password',               [1.0, 0.0, 0.0]::FLOAT[3]),
(2, 'How to reset your password',        [1.0, 0.0, 0.0]::FLOAT[3]),
(3, 'Recover a locked account',          [0.9, 0.1, 0.0]::FLOAT[3]),
(4, 'Set up two-factor authentication',  [0.8, 0.2, 0.0]::FLOAT[3]),
(5, 'Change your payment method',        [0.0, 1.0, 0.0]::FLOAT[3]),
(6, 'Update your billing address',       [0.1, 0.9, 0.0]::FLOAT[3]),
(7, 'Fix a dropped connection',          [0.0, 0.0, 1.0]::FLOAT[3]),
(8, 'How do I change my payment method', [0.0, 1.0, 0.0]::FLOAT[3]);

VACUUM (REFRESH_TABLE) articles;
```

</details>

## More like this

Name the row by id and use its own embedding as the probe. The subquery reads the vector for article 1, then `emb <-> ...` scores every other row by distance to it and the closest rows are the ones most like it. The nearest result here is a reworded copy of the same article sitting at distance 0, with the genuinely related account articles just behind it. This form scores every other row inline, which is fine at this size. On a large collection split it into two steps: fetch the row's embedding first, then issue the nearest-neighbor query with that vector as the probe so the planner can drive the IVF index instead of scoring the whole table.

```sql
SELECT id, title,
       round((emb <-> (SELECT emb FROM articles WHERE id = 1))::numeric, 3) AS distance
FROM articles_idx
WHERE id <> 1
ORDER BY distance, id
LIMIT 3;
-- result:
id	title	distance
2	How to reset your password	0.000
3	Recover a locked account	0.141
4	Set up two-factor authentication	0.283
```

## Catching near-duplicates

To find the copies you compare every pair and keep the ones inside a tiny radius. A self-join does exactly that: join the table to itself on `a.id < b.id` so each pair appears once, then filter on distance. Anything under a small threshold is effectively the same document. Here it surfaces both reworded copies at distance 0. A self-join scores every pair so it is fine for small tables. On a big collection you would cluster on the MinHash signatures below instead.

```sql
SELECT a.id AS id_a, a.title AS title_a,
       b.id AS id_b, b.title AS title_b,
       round((a.emb <-> b.emb)::numeric, 3) AS distance
FROM articles a JOIN articles b ON a.id < b.id
WHERE (a.emb <-> b.emb) < 0.05
ORDER BY distance, a.id, b.id;
-- result:
id_a	title_a	id_b	title_b	distance
1	Reset your password	2	How to reset your password	0.000
5	Change your payment method	8	How do I change my payment method	0.000
```

## MinHash for near-duplicate text

Distances work once you have vectors. To catch near-duplicate text from the words alone, with no embedding model in the loop, SereneDB has the [`minhash`](../../sql/functions/search/tokenizers/minhash.md) scalar function. It takes a list of tokens and a signature width, hashes every token and keeps the smallest hashes; that set is the document's signature. Two documents that share most of their words share most of their signature, so the fraction of matching components estimates the Jaccard similarity of their word sets. That estimate is the standard signal for approximate deduplication across a large collection.

There is no `minhash` dictionary template. The signature is built by calling the function, either inside an indexed expression or inside the `expression` of a [`sql`](../../sql/statements/create_text_search_dictionary/sql.md) dictionary. Index the signature, then match its components as keyword terms:

```sql
CREATE TABLE mh_docs(id INTEGER, body TEXT);

CREATE INDEX mh_idx ON mh_docs USING inverted(
    id,
    (minhash(regexp_split_to_array(lower(body), '\W+'), 64))
);

SELECT id FROM mh_idx
WHERE minhash(regexp_split_to_array(lower(body), '\W+'), 64)
      @@ ts_any(ts_tokenize(minhash(regexp_split_to_array(lower('the quick brown fox'), '\W+'), 64), 'keyword'), 8);
```

The `min_match` argument of `ts_any` is how many components must match, so it is the similarity threshold. Both sides have to build the token list the same way, or the signatures never line up. The second argument of `minhash` sets how many hashes form the signature, trading index size for a sharper similarity estimate. The components are opaque 8-byte hash values, not readable words, so compare whole signatures between documents and never match on an individual value. That is why this stays an overview rather than a worked query with fixed expected output.

## See also

- [Semantic and Hybrid Search](./hybrid-search.md): ranking by a search-box query vector and fusing it with keyword matches
- [Vector Search guide](../../sql/indexes/inverted/vector-search.md): building `ivf` indexes, choosing a metric and tuning recall
- [Vector functions reference](../../sql/functions/vector.md): `l2_distance`, `cosine_distance` and the distance operators
- [`minhash` function](../../sql/functions/search/tokenizers/minhash.md): the signature arguments and how overlap estimates Jaccard similarity

