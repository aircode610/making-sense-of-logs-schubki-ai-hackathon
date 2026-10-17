---
title: Relevance Tuning
sidebar_position: 12
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Relevance Tuning

BM25 out of the box is a good default, but real ranking is rarely one size fits all. A hit in the title usually matters more than a hit in the body and a business signal like popularity often deserves a say in the final order. SereneDB gives you two levers for this: the [boost operator](../../sql/functions/search/full-text.md) `^` weights one clause above another and [BM25](../../sql/functions/search/scoring.md) is an ordinary number you can do arithmetic on.

Every query below returns just `id` and `title`, so each change reads as rows trading places instead of a column of raw scores.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY d2 AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE pages (id INTEGER PRIMARY KEY, title VARCHAR, body VARCHAR);

CREATE INDEX pages_idx ON pages USING inverted (id, title d2, body d2);

INSERT INTO pages VALUES
(1, 'shipping policy', 'our returns and shipping policy explains how a refund works for any order you place'),
(2, 'refund and returns', 'read this before you request anything at all from support today please');

VACUUM (REFRESH_TABLE) pages;
```

</details>

## Weight one field above another

Write one `@@` clause per column and combine them with `OR`, then boost the clause that matters. Search "refund" and the page that only mentions it in the body edges ahead of the page actually titled "refund and returns": the two matches score close together and a title hit does not win on its own, which is the whole reason to reach for a boost.

```sql
SELECT id, title FROM pages_idx WHERE title @@ 'refund' OR body @@ 'refund' ORDER BY BM25(pages_idx.tableoid) DESC, id;
-- result:
id	title
1	shipping policy
2	refund and returns
```

Boost the title clause five times over with `^` and the titled page moves to the top. The `^` operator changes only the score, not which rows match, so the same two pages come back in a different order. It binds tighter than `||`, so wrap the query you want to boost in parentheses when a clause carries more than a single term. The cast form says the same thing if you prefer it: `('refund'::tsquery)::boost(42)` weights a clause exactly like `^ 42` and nested boosts multiply.

```sql
SELECT id, title FROM pages_idx WHERE title @@ ('refund'::tsquery ^ 5.0) OR body @@ 'refund' ORDER BY BM25(pages_idx.tableoid) DESC, id;
-- result:
id	title
2	refund and returns
1	shipping policy
```

## Blend in a business signal

BM25 is a plain number, so you can fold other columns straight into the `ORDER BY`. Every row here mentions "fox" and relevance alone puts the short, on-topic "Fox" page first.

```sql
SELECT id, title FROM bd_idx WHERE title @@ 'fox' OR body @@ 'fox' ORDER BY BM25(bd_idx.tableoid) DESC, id;
-- result:
id	title
1	Fox
2	Morning walk
3	Field notes
```

Multiply the score by a stored `popularity` column and the ranking shifts toward what people actually engage with. The popular walk climbs to the top and the relevant but ignored "Fox" page sinks. A raw multiply lets one runaway value dominate, so cap it with a saturating curve when you need to, which the [Recency and Decay](./recency-and-decay.md) recipe covers. It is `function_score`, if you come from Elastic, expressed as ordinary SQL arithmetic.

```sql
SELECT id, title FROM bd_idx WHERE title @@ 'fox' OR body @@ 'fox' ORDER BY BM25(bd_idx.tableoid) * popularity DESC, id;
-- result:
id	title
2	Morning walk
3	Field notes
1	Fox
```

## See also

- [BM25/TFIDF Ranking](./ranking.md): scoring functions and their `k1` and `b` parameters
- [Scoring reference](../../sql/functions/search/scoring.md): the `BM25` and `TFIDF` signatures
- [Semantic and Hybrid Search](./hybrid-search.md): blending keyword and vector rankings

