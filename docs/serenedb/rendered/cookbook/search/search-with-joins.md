---
title: Search with Joins and Analytics
sidebar_position: 23
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Search with Joins and Analytics

A `@@` search on an [inverted index](../../sql/indexes/inverted/index.md) is just a predicate, so it composes with the rest of SQL. The rows a search matches are ordinary rows: you can join them to other tables and aggregate them in the same statement. There is no separate analytics store to feed and no export step to run. If you are coming from Elasticsearch this is the part that disappears, see [Migrating from Elasticsearch](../../sql/indexes/inverted/migrating-from-elasticsearch.md).

The queries below join two tables: `products` holds a full-text `title` and a keyword `category` while `orders` records `qty` and `amount` against each `product_id`.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY tx AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE products (id INTEGER PRIMARY KEY, title VARCHAR, category VARCHAR NOT NULL);

CREATE INDEX products_idx ON products USING inverted (id, title tx, category);

INSERT INTO products VALUES
(1, 'trail running shoe', 'footwear'),
(2, 'road running shoe',  'footwear'),
(3, 'running jacket',      'apparel'),
(4, 'wireless earbuds',    'electronics'),
(5, 'running socks',       'apparel');

VACUUM (REFRESH_TABLE) products;

CREATE TABLE orders (order_id INTEGER PRIMARY KEY, product_id INTEGER, qty INTEGER, amount INTEGER);

INSERT INTO orders VALUES
(1, 1, 2, 240),
(2, 1, 1, 120),
(3, 2, 3, 270),
(4, 3, 1, 80),
(5, 4, 5, 200);
```

</details>

## Aggregate what matched

The search narrows the rows, `GROUP BY` rolls them up and `sum()` totals revenue and units, all in one query. The `@@` filter picks the products whose title matches "running", the join pulls their orders and the aggregate reports per product. One statement, one system.

```sql
SELECT p.title, sum(o.amount) AS revenue, sum(o.qty) AS units
FROM products_idx p
JOIN orders o ON o.product_id = p.id
WHERE p.title @@ 'running'
GROUP BY p.title
ORDER BY revenue DESC, p.title;
-- result:
title	revenue	units
trail running shoe	360	3
road running shoe	270	3
running jacket	80	1
```

## Roll up by any dimension

Slice the same matched rows by `category` instead of by product and you get a revenue breakdown across the whole search result. No aggregation DSL and no second index: it is a `GROUP BY` on the column you want, the way a terms aggregation works if you come from Elastic.

```sql
SELECT p.category, sum(o.amount) AS revenue
FROM products_idx p
JOIN orders o ON o.product_id = p.id
WHERE p.title @@ 'running'
GROUP BY p.category
ORDER BY revenue DESC, p.category;
-- result:
category	revenue
footwear	630
apparel	80
```

## Keep matches that never sold

An inner join drops matched products that have no orders, which hides part of the answer when you are looking at coverage or gaps. A `LEFT JOIN` keeps every matched product and `coalesce` turns the missing total into a zero, so a product that matched the search but never sold shows up with revenue 0 next to the ones that did.

```sql
SELECT p.title, coalesce(sum(o.amount), 0) AS revenue
FROM products_idx p
LEFT JOIN orders o ON o.product_id = p.id
WHERE p.title @@ 'running'
GROUP BY p.title
ORDER BY revenue DESC, p.title;
-- result:
title	revenue
trail running shoe	360
road running shoe	270
running jacket	80
running socks	0
```

## See also

- [Faceted Search](./faceted-search.md): count and bucket the same search result without scanning the matched rows
- [Ranking](./ranking.md): order matched rows by relevance before you aggregate them
- [Migrating from Elasticsearch](../../sql/indexes/inverted/migrating-from-elasticsearch.md): how search and analytics collapse into one query engine

