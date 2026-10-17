---
title: Pinned Results
sidebar_position: 14
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Pinned Results

Relevance order is not always the order you want to ship. A promo deal, a sponsored listing or a freshly launched SKU has to lead the page whatever its score says, and in SereneDB that merchandising pin is one `CASE` expression in the `ORDER BY`: the pinned query, if you come from Elastic.

The catalog below holds eight coffee products with "coffee" in every title, so a pin only moves rows around instead of changing which ones match.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY en AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position, norm);

CREATE TABLE products (id INTEGER PRIMARY KEY, title VARCHAR);

CREATE INDEX products_idx ON products USING inverted (id, title en);

INSERT INTO products VALUES
(1, 'Coffee Beans'),
(2, 'Organic Fair Trade Coffee Beans Dark Roast Whole Bean One Kilogram Bag'),
(3, 'Espresso Coffee'),
(4, 'Single Origin Ethiopian Coffee'),
(5, 'Stainless Steel Pour Over Coffee Maker With Reusable Mesh Filter Set'),
(6, 'Cold Brew Coffee'),
(7, 'Ground Coffee'),
(8, 'Decaf Coffee Pods Variety Pack Assortment Box Forty Count');

VACUUM (REFRESH_TABLE) products;
```

</details>

## Organic ranking

Start with the plain relevance order. [BM25](../../sql/functions/search/scoring.md) rewards the short on-topic titles and pushes the long ones with a single mention of "coffee" to the bottom.

```sql
SELECT id, title
FROM products_idx
WHERE title @@ 'coffee'
ORDER BY BM25(products_idx.tableoid) DESC, id;
-- result:
id	title
1	Coffee Beans
3	Espresso Coffee
7	Ground Coffee
6	Cold Brew Coffee
4	Single Origin Ethiopian Coffee
8	Decaf Coffee Pods Variety Pack Assortment Box Forty Count
5	Stainless Steel Pour Over Coffee Maker With Reusable Mesh Filter Set
2	Organic Fair Trade Coffee Beans Dark Roast Whole Bean One Kilogram Bag
```

## Pin ids to the top

Add a leading sort key that is `0` for the pinned ids and `1` for everything else. The pinned rows sort ahead of the rest, then `BM25 DESC, id` orders both groups so the result stays deterministic. Products 2 and 5 sat at the very bottom on relevance alone and now lead the page.

```sql
SELECT id, title
FROM products_idx
WHERE title @@ 'coffee'
ORDER BY CASE WHEN id IN (2, 5) THEN 0 ELSE 1 END,
         BM25(products_idx.tableoid) DESC, id;
-- result:
id	title
5	Stainless Steel Pour Over Coffee Maker With Reusable Mesh Filter Set
2	Organic Fair Trade Coffee Beans Dark Roast Whole Bean One Kilogram Bag
1	Coffee Beans
3	Espresso Coffee
7	Ground Coffee
6	Cold Brew Coffee
4	Single Origin Ethiopian Coffee
8	Decaf Coffee Pods Variety Pack Assortment Box Forty Count
```

Inside the pinned group that `CASE` still falls back to `BM25 DESC`, so it keeps a stable order but cannot honor a hand-picked sequence.

## Order the pins by hand

When merchandising hands you an exact running order, swap the leading key for `array_position(ARRAY[5, 2, 7], id)`. Each pin now sorts by where it sits in that array. Rows that are not pinned get `NULL` back from `array_position`, `NULLS LAST` parks them below the pins and `BM25 DESC, id` takes over from there. Ground Coffee (id 7) would outscore both 5 and 2, yet it lands third because that is the slot you gave it.

```sql
SELECT id, title
FROM products_idx
WHERE title @@ 'coffee'
ORDER BY array_position(ARRAY[5, 2, 7], id) NULLS LAST,
         BM25(products_idx.tableoid) DESC, id;
-- result:
id	title
5	Stainless Steel Pour Over Coffee Maker With Reusable Mesh Filter Set
2	Organic Fair Trade Coffee Beans Dark Roast Whole Bean One Kilogram Bag
7	Ground Coffee
1	Coffee Beans
3	Espresso Coffee
6	Cold Brew Coffee
4	Single Origin Ethiopian Coffee
8	Decaf Coffee Pods Variety Pack Assortment Box Forty Count
```

You can spell the same thing as a `UNION ALL`: the pinned rows on top concatenated with the organic query minus those ids via `NOT IN`. The `CASE` and `array_position` forms stay in a single pass and read shorter, so save `UNION ALL` for when the two halves are genuinely different queries.

## See also

- [BM25/TFIDF Ranking](./ranking.md): the relevance scoring the organic order is built on
- [Relevance Tuning](./boosting.md): boost fields and blend business signals into the score
- [Scoring reference](../../sql/functions/search/scoring.md): the `BM25` and `TFIDF` signatures

