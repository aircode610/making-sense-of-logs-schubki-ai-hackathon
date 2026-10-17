---
title: Collapsing and Grouping Results
sidebar_position: 22
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Collapsing and Grouping Results

Rank matches inside a partition with a window function then keep the rows you want: you get one best hit per group or the top N per group from a single ranked search, with no second round trip and no per bucket sub search. Field collapsing and `top_hits` per bucket, if you come from Elasticsearch, are both this one pattern.

Eight products spread across three categories fill the catalog below. Each row pairs a plain keyword `category` with a tokenized `title` so [BM25](../../sql/functions/search/scoring.md) can score every match.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY tx AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    category VARCHAR NOT NULL,
    title VARCHAR
);

INSERT INTO products VALUES
(1, 'footwear',    'Trail running shoe for serious running'),
(2, 'footwear',    'Road running shoe'),
(3, 'footwear',    'Waterproof hiking boot'),
(4, 'apparel',     'Lightweight running jacket for running'),
(5, 'apparel',     'Rain running jacket'),
(6, 'electronics', 'GPS running watch with running metrics'),
(7, 'electronics', 'Wireless running earbuds'),
(8, 'electronics', 'Fitness tracker');

CREATE INDEX products_idx ON products
    USING inverted (id, category, title tx);

VACUUM (REFRESH_TABLE) products;
```

</details>

## Collapse to the best hit per category

Rank every match inside its `category` with `ROW_NUMBER()`, ordering by `BM25` so the strongest hit lands at row 1, then keep only `rn = 1`. The `id` tiebreaker holds the ranking steady when two rows tie on score. `BM25` runs directly inside the window over the index scan, so the whole collapse is one query.

```sql
SELECT id, category, title
FROM (
    SELECT id, category, title,
           ROW_NUMBER() OVER (PARTITION BY category ORDER BY BM25(products_idx.tableoid) DESC, id) AS rn
    FROM products_idx
    WHERE title @@ 'running'
) s
WHERE rn = 1
ORDER BY category;
-- result:
id	category	title
4	apparel	Lightweight running jacket for running
6	electronics	GPS running watch with running metrics
1	footwear	Trail running shoe for serious running
```

## Top N hits per category

Change the filter to `rn <= 2` and you get `top_hits` per bucket: the two best matches in every category, still ranked by relevance. Raise the bound for more hits per group.

```sql
SELECT category, id, title, rn
FROM (
    SELECT id, category, title,
           ROW_NUMBER() OVER (PARTITION BY category ORDER BY BM25(products_idx.tableoid) DESC, id) AS rn
    FROM products_idx
    WHERE title @@ 'running'
) s
WHERE rn <= 2
ORDER BY category, rn;
-- result:
category	id	title	rn
apparel	4	Lightweight running jacket for running	1
apparel	5	Rain running jacket	2
electronics	6	GPS running watch with running metrics	1
electronics	7	Wireless running earbuds	2
footwear	1	Trail running shoe for serious running	1
footwear	2	Road running shoe	2
```

## See also

- [Ranking and Relevance](./ranking.md): tune the BM25 scores these examples rank on
- [Pagination](./pagination.md): page through ranked results with stable ordering
- [Faceted Search](./faceted-search.md): count matches per category instead of collapsing to one
- [Scoring functions](../../sql/functions/search/scoring.md): BM25 and the other relevance scorers

