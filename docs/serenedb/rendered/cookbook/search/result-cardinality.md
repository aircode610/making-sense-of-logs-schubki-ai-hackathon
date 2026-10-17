---
title: Counting Unique Results
sidebar_position: 21
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Counting Unique Results

`approx_count_distinct` tells you how many distinct values a search matched without counting them one at a time. It reads the [inverted index](../../sql/indexes/inverted/index.md) over a [full-text](../../sql/functions/search/full-text.md) filter and returns a HyperLogLog estimate on a fixed memory budget, so the cost holds steady whether the query matches ten documents or ten million. If you come from Elastic this is the cardinality aggregation.

A `products` table pairs a keyword `brand` with a tokenized `title`.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY tx AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    brand VARCHAR NOT NULL,
    title VARCHAR
);

INSERT INTO products VALUES
(1,  'acme',     'Trail running shoe'),
(2,  'globex',   'Road running shoe'),
(3,  'acme',     'Running jacket'),
(4,  'initech',  'Running watch'),
(5,  'umbrella', 'Trail running vest'),
(6,  'globex',   'Waterproof running cap'),
(7,  'acme',     'Hiking boot'),
(8,  'initech',  'Wireless earbuds'),
(9,  'umbrella', 'Rain jacket'),
(10, 'wonka',    'Running belt');

CREATE INDEX products_idx ON products USING inverted (id, brand, title tx);

VACUUM (REFRESH_TABLE) products;
```

</details>

## Hits and distinct values in one pass

The number you put next to a result set is usually two things at once: how many documents matched and how many distinct brands sit behind them. `count(*)` gives the first and `approx_count_distinct(brand)` gives the second, both riding the same `WHERE`.

```sql
SELECT count(*) AS hits, approx_count_distinct(brand) AS brands
FROM products_idx
WHERE title @@ 'running';
-- result:
hits	brands
7	5
```

Seven titles mention "running" across five distinct brands.

## Check the estimate against the exact count

While the result set is small you can afford the exact `count(DISTINCT brand)` and hold the estimate up against it. At this size they land on the same number.

```sql
SELECT count(DISTINCT brand) AS exact_brands,
       approx_count_distinct(brand) AS approx_brands
FROM products_idx
WHERE title @@ 'running';
-- result:
exact_brands	approx_brands
5	5
```

The estimate trades a small margin of error for memory that does not grow with cardinality, so it is the one to reach for once you count distinct values across millions of hits. When you want a count per value rather than one total, [Faceted Search](./faceted-search.md) breaks the same result set down into a count for every brand.

## See also

- [Faceted Search](./faceted-search.md): exact per-value counts and distinct-value lists, counted in the term dictionary without opening a document
- [Search with joins and analytics](./search-with-joins.md): run these aggregates alongside joins and grouping
- [Full-text functions](../../sql/functions/search/full-text.md): the `@@` match operator used in the filter

