---
title: Faceted Search
sidebar_position: 18
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Faceted Search

Faceted navigation puts a count next to every filter so a shopper sees how many products sit behind each category or brand before they click. Every count comes out of the [inverted index](../../sql/indexes/inverted/index.md) term dictionary without opening a document, so there is no separate rollup table to keep in sync. This recipe faces a product catalog, counts facets over a search result, buckets a price range, keeps a drill-down honest and lists distinct values without touching the base table.

A `products` catalog backs every query here: `category`, `brand` and `price_band` are keyword columns the dictionary faces directly and `title` is tokenized for search.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY tx AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    category VARCHAR NOT NULL,
    brand VARCHAR NOT NULL,
    price_band VARCHAR NOT NULL,
    title VARCHAR
);

INSERT INTO products VALUES
(1, 'footwear',    'acme',    'mid',     'Trail running shoe'),
(2, 'footwear',    'globex',  'mid',     'Road running shoe'),
(3, 'footwear',    'acme',    'premium', 'Hiking boot'),
(4, 'apparel',     'acme',    'mid',     'Running jacket'),
(5, 'apparel',     'globex',  'mid',     'Rain jacket'),
(6, 'electronics', 'initech', 'premium', 'Running watch'),
(7, 'electronics', 'globex',  'mid',     'Wireless earbuds'),
(8, 'electronics', 'initech', 'budget',  'Fitness tracker');

CREATE INDEX products_idx ON products
    USING inverted (category, brand, price_band, title tx);

VACUUM (REFRESH_TABLE) products;
```

</details>

## Count every category

The bread and butter of a facet sidebar: how many products in each category. On a keyword column the optimizer resolves a plain `GROUP BY` inside the dictionary itself, so it never opens a document. `EXPLAIN` shows `TsDict:` on the `IRESEARCH_SCAN` when the rewrite fires.

```sql
SELECT category, count(*) AS n
FROM products_idx
GROUP BY category
ORDER BY n DESC, category;
-- result:
category	n
electronics	3
footwear	3
apparel	2
```

## Facet a search result

Real faceting reacts to what the user typed. Someone searches "running", you show the category breakdown of the matches so they can narrow down. A `@@` matcher filters documents and [`ts_dict_agg`](../../sql/functions/search/term-dictionary.md) with its aligned [`ts_dict_count`](../../sql/functions/search/term-dictionary.md) returns every category that survives, with a live count over that result set.

```sql
SELECT unnest(ts_dict_agg(category)) AS category,
       unnest(ts_dict_count(category)) AS n
FROM products_idx
WHERE title @@ 'running'
ORDER BY n DESC, category;
-- result:
category	n
footwear	2
apparel	1
electronics	1
```

## Add another dimension

Each facet is its own `ts_dict_agg` over the same filter, so a second dimension is one more pair of lists. Here is the brand breakdown of the same "running" search.

```sql
SELECT unnest(ts_dict_agg(brand)) AS brand,
       unnest(ts_dict_count(brand)) AS n
FROM products_idx
WHERE title @@ 'running'
ORDER BY n DESC, brand;
-- result:
brand	n
acme	2
globex	1
initech	1
```

## Count every dimension in one query

One query per dimension works, but a sidebar usually wants them all. `GROUP BY GROUPING SETS` counts several columns in a single pass: each set is one facet, so `((category), (brand), (price_band))` returns a `(facet, value, count)` row for every value across all three. `EXPLAIN` shows one `TsDict: category, brand, price_band` on the scan with no document lookup.

```sql
SELECT
    CASE WHEN category IS NOT NULL THEN 'category'
         WHEN brand IS NOT NULL THEN 'brand'
         ELSE 'price_band' END AS facet,
    coalesce(category, brand, price_band) AS value,
    count(*) AS n
FROM products_idx
GROUP BY GROUPING SETS ((category), (brand), (price_band))
ORDER BY facet, n DESC, value;
-- result:
facet	value	n
brand	acme	3
brand	globex	3
brand	initech	2
category	electronics	3
category	footwear	3
category	apparel	2
price_band	mid	5
price_band	premium	2
price_band	budget	1
```

Every grouped column has to be `NOT NULL` for the rewrite to fire — a nullable facet drops the query to a document scan and collapses the `NULL` groups. Fill missing values with a sentinel such as `''` at write time and skip that row when you render.

This counts each dimension on its own, the marginal totals a sidebar shows. It is not `GROUP BY category, brand`, which asks for every category-and-brand *combination*: that needs the per-document pairing the separate dictionaries do not hold, so it always scans documents. When you do need the combination, precompute the pair as one keyword column (`category || '\x1f' || brand`, the same trick as the [price band](#bucket-a-numeric-field-into-range-facets) below) and group that.

## Bucket a numeric field into range facets

The dictionary faces terms, so a price or date range is just a keyword column you fill with the band a row lands in (`budget`, `mid`, `premium`) at write time. Facet it like any other dimension and you get a price ladder for free, no scan and no `CASE` over raw prices at query time.

```sql
SELECT price_band, count(*) AS n
FROM products_idx
GROUP BY price_band
ORDER BY price_band;
-- result:
price_band	n
budget	1
mid	5
premium	2
```

Precompute the band on insert or in a generated column. The index never sees the raw number, only the bucket, so the facet stays a dictionary walk.

## Keep the active facet clickable

Once a shopper picks a category the brand list should narrow to that category, but the category list has to stay whole so they can switch. So each dimension counts with the *other* filters applied and its own left off. Here the brand facet is scoped to the "footwear" selection while the category facet above keeps showing every category.

```sql
SELECT unnest(ts_dict_agg(brand)) AS brand,
       unnest(ts_dict_count(brand)) AS n
FROM products_idx
WHERE category @@ 'footwear'
ORDER BY n DESC, brand;
-- result:
brand	n
acme	2
globex	1
```

## Every dimension from one index scan

You do not pay per facet. A single pass over the dictionary can emit every dimension at once, so the whole sidebar is one read of the index.

```sql
SELECT list_sort(ts_dict_agg(category))   AS categories,
       list_sort(ts_dict_agg(brand))      AS brands,
       list_sort(ts_dict_agg(price_band)) AS bands
FROM products_idx;
-- result:
categories	brands	bands
{apparel,electronics,footwear}	{acme,globex,initech}	{budget,mid,premium}
```

## List distinct values without a scan

Populating a filter dropdown, a "3 brands" badge or a validation check all want the distinct values of a column. `count(DISTINCT col)` and `array_agg`/`ts_dict_agg` over a keyword column come from the dictionary, so the cost is walking the terms rather than scanning rows.

```sql
SELECT count(DISTINCT brand) AS brands FROM products_idx;
-- result:
brands
3
```

```sql
SELECT unnest(ts_dict_agg(brand)) AS brand FROM products_idx ORDER BY brand;
-- result:
brand
acme
globex
initech
```

## See also

- [Term Dictionary](../../sql/functions/search/term-dictionary.md): the full `ts_dict_*` reference, `min`/`max`, per-term frequency and the standard-SQL rewrites
- [Autocomplete](./autocomplete.md): prefix suggestions ranked by popularity from the same dictionary
- [Exact Value Matching](./exact-value-matching.md): filter the catalog down before or after faceting

