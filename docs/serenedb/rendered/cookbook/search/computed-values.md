---
title: Computed Values
sidebar_position: 30
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Computed Values

You do not have to store a value to search it. Index an [expression over a column](../../sql/indexes/inverted/modeling.md) (a functional index) or a generated column the table computes for you, then query that computed value from the [inverted index](../../sql/indexes/inverted/index.md) like any other field. Reach for this when you want a case-folded key for exact lookups, a derived amount you filter by or a normalized form of messy input.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TABLE products (id INTEGER PRIMARY KEY, name VARCHAR, price INTEGER, price_with_tax INTEGER GENERATED ALWAYS AS (price * 110 / 100) STORED);

CREATE INDEX products_idx ON products USING inverted (id, (lower(name)), price_with_tax);

INSERT INTO products (id, name, price) VALUES (1, 'Widget', 100), (2, 'WIDGET', 200), (3, 'Gadget', 50);

VACUUM (REFRESH_TABLE) products;
```

</details>

## Index an expression

Wrap the expression in parentheses in the index definition and SereneDB indexes its result. Here `(lower(name))` folds case at index time, so one lowercase query matches every casing of the stored value. Query the same expression you indexed.

```sql
SELECT id, name FROM products_idx WHERE lower(name) @@ 'widget' ORDER BY id;
-- result:
id	name
1	Widget
2	WIDGET
```

## Index a generated column

A column declared `GENERATED ALWAYS AS (...) STORED` is computed by the table and kept in sync on every write. Index it by name like any stored column, then range over it. Here `price_with_tax` derives from `price` and you bound it with `ts_le` and `ts_ge`.

```sql
SELECT id, name, price_with_tax FROM products_idx WHERE price_with_tax @@ ts_le(120) ORDER BY id;
-- result:
id	name	price_with_tax
1	Widget	110
3	Gadget	55
```

```sql
SELECT id, name, price_with_tax FROM products_idx WHERE price_with_tax @@ ts_ge(200) ORDER BY id;
-- result:
id	name	price_with_tax
2	WIDGET	220
```

## Mix computed and stored

Put both in one `WHERE` and they filter together: the case-folded key narrows to a product and the generated amount bounds the price. The expression in the query must match the indexed expression exactly, so query `lower(name)`, not `name`.

```sql
SELECT id, name FROM products_idx WHERE lower(name) @@ 'widget' AND price_with_tax @@ ts_le(120) ORDER BY id;
-- result:
id	name
1	Widget
```

## Concatenate columns into a key

An expression can span several columns, so you can search a value the table never stores. Here `(first || ' ' || last)` builds a full-name key and one exact lookup finds the person, no `full_name` column required.

```sql
SELECT id FROM people_idx WHERE (first || ' ' || last) @@ 'Jane Doe' ORDER BY id;
-- result:
id
1
```

## Bucket with CASE

A `CASE` expression labels a raw value at index time, so you can filter or facet on the bucket without a lookup table. Here orders index as `big` or `small` by amount and you query the label.

```sql
SELECT id, amount FROM orders_idx WHERE (CASE WHEN amount >= 100 THEN 'big' ELSE 'small' END) = 'big' ORDER BY id;
-- result:
id	amount
1	150
3	200
```

## See also

- [What to Index](../../sql/indexes/inverted/modeling.md): choosing what to index and where expressions and generated columns fit
- [Range Queries](./range-queries.md): filtering indexed values by order with `ts_le`, `ts_ge` and friends
- [JSON Search](./json-search.md): indexing and querying values pulled out of JSON documents

