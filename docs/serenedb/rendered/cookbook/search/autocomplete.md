---
title: Autocomplete
sidebar_position: 10
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Autocomplete

A type-ahead box wants the handful of terms that start with what the user typed so far, ranked by how popular they are. SereneDB walks the matching terms inside the [inverted index](../../sql/indexes/inverted/index.md) dictionary and [`ts_dict_count`](../../sql/functions/search/term-dictionary.md) supplies the popularity to rank them, so a keystroke costs a dictionary seek instead of a scan over the whole log.

Each row in the `searches` log below is one logged query stored as a keyword, so the whole string stays a single term and its document count is how many times that query was searched.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TABLE searches (id INTEGER PRIMARY KEY, query VARCHAR NOT NULL);

INSERT INTO searches VALUES
(1,  'running shoes'),
(2,  'running shoes'),
(3,  'running shoes'),
(4,  'running jacket'),
(5,  'running jacket'),
(6,  'running watch'),
(7,  'rain jacket'),
(8,  'rain jacket'),
(9,  'road bike'),
(10, 'road running'),
(11, 'hiking boots'),
(12, 'hiking boots');

CREATE INDEX searches_idx ON searches USING inverted (query);

VACUUM (REFRESH_TABLE) searches;
```

</details>

## Prefix suggestions

A `LIKE 'run%'` prefix on a keyword column is a term match, so the optimizer prunes the dictionary to the `run` branch and [`ts_dict_agg`](../../sql/functions/search/term-dictionary.md) returns only those terms. No document is read.

```sql
SELECT unnest(ts_dict_agg(query)) AS suggestion
FROM searches_idx
WHERE query LIKE 'run%'
ORDER BY suggestion;
-- result:
suggestion
running jacket
running shoes
running watch
```

## Rank by popularity

Suggestions are only useful in the right order. Pair the terms with their aligned `ts_dict_count` and sort on it so the most searched queries surface first.

```sql
SELECT unnest(ts_dict_agg(query))   AS suggestion,
       unnest(ts_dict_count(query)) AS searches
FROM searches_idx
WHERE query LIKE 'run%'
ORDER BY searches DESC, suggestion;
-- result:
suggestion	searches
running shoes	3
running jacket	2
running watch	1
```

## Return the top few

A dropdown shows a few rows, not the whole branch. Order by popularity and `LIMIT` to the top suggestions.

```sql
SELECT unnest(ts_dict_agg(query))   AS suggestion,
       unnest(ts_dict_count(query)) AS searches
FROM searches_idx
WHERE query LIKE 'r%'
ORDER BY searches DESC, suggestion
LIMIT 2;
-- result:
suggestion	searches
running shoes	3
rain jacket	2
```

## Prefix with a matcher

[`ts_starts_with`](../../sql/functions/search/full-text.md#tsquery-constructors) is the matcher form of the same prefix and reads the same way inside a larger `@@` query.

```sql
SELECT unnest(ts_dict_agg(query)) AS suggestion
FROM searches_idx
WHERE query @@ ts_starts_with('road')
ORDER BY suggestion;
-- result:
suggestion
road bike
road running
```

## See also

- [Faceted Search](./faceted-search.md): count how many results sit behind each filter from the same dictionary
- [Term Dictionary](../../sql/functions/search/term-dictionary.md): the full `ts_dict_*` reference and the term-vs-document filtering rules
- [Wildcard Search](./wildcard-search.md): `_` and `%` patterns beyond a leading prefix

