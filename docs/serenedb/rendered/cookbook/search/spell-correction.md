---
title: Spell Correction
sidebar_position: 9
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Spell Correction

A search box gets typos. Instead of running a query for "jaket" and returning nothing, correct the input against the terms you actually indexed and rerun with the fix. SereneDB does the correction with a fuzzy match over the [inverted index](../../sql/indexes/inverted/index.md) dictionary: [`ts_levenshtein`](../../sql/functions/search/full-text.md#tsquery-constructors) enumerates the terms within an edit distance of what the user typed and [`ts_dict_score`](../../sql/functions/search/term-dictionary.md) ranks them by similarity, so the closest term is the correction.

This is the mirror image of [Fuzzy Search](./fuzzy-search.md). Fuzzy search runs the real query with typo tolerance baked in. Spell correction fixes the input first, then runs a normal exact query with the corrected term, which keeps the hot query path fast and precise.

Each row of the query log holds one past search stored as a keyword so a term's document count is how many times that word got searched.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TABLE query_log (id INTEGER PRIMARY KEY, term VARCHAR NOT NULL);

INSERT INTO query_log VALUES
(1, 'jacket'), (2, 'jacket'), (3, 'jacket'), (4, 'jacket'), (5, 'jacket'),
(6, 'running'), (7, 'running'), (8, 'running'), (9, 'running'),
(10, 'running'), (11, 'running'), (12, 'running'), (13, 'running'),
(14, 'basket'),
(15, 'racket'),
(16, 'boot'), (17, 'boot'), (18, 'boot'), (19, 'boot'), (20, 'boot'), (21, 'boot'),
(22, 'boat'), (23, 'boat'),
(24, 'boots'), (25, 'boots'), (26, 'boots'),
(27, 'watch'), (28, 'watch'), (29, 'watch'), (30, 'watch');

CREATE INDEX query_log_idx ON query_log USING inverted (term);

VACUUM (REFRESH_TABLE) query_log;
```

</details>

## Suggest corrections

`ts_levenshtein('jaket', 2)` enumerates the indexed terms within edit distance 2 of the typo and `ts_dict_score` reports each candidate's similarity. Ordering by similarity puts the intended word on top.

```sql
SELECT unnest(ts_dict_agg(term))   AS suggestion,
       unnest(ts_dict_score(term)) AS similarity
FROM query_log_idx
WHERE term @@ ts_levenshtein('jaket', 2)
ORDER BY similarity DESC, suggestion;
-- result:
suggestion	similarity
jacket	0.8
basket	0.6
racket	0.6
```

## Pick the correction

Take the top candidate and you have the "did you mean" to feed back into the real query. `ORDER BY` similarity then `LIMIT 1`.

```sql
SELECT unnest(ts_dict_agg(term)) AS correction
FROM query_log_idx
WHERE term @@ ts_levenshtein('jaket', 2)
ORDER BY unnest(ts_dict_score(term)) DESC, unnest(ts_dict_count(term)) DESC
LIMIT 1;
-- result:
correction
jacket
```

## Break ties by popularity

When the typo sits the same distance from two real words the similarity ties, so lean on the log: prefer the word people actually search. Here "bost" is one edit from both "boot" and "boat", and the document count breaks the tie toward the popular one.

```sql
SELECT unnest(ts_dict_agg(term))   AS suggestion,
       unnest(ts_dict_score(term)) AS similarity,
       unnest(ts_dict_count(term)) AS searches
FROM query_log_idx
WHERE term @@ ts_levenshtein('bost', 2)
ORDER BY similarity DESC, searches DESC, suggestion;
-- result:
suggestion	similarity	searches
boot	0.75	6
boat	0.75	2
boots	0.5	3
```

## See also

- [Fuzzy Search](./fuzzy-search.md): match documents with the typo tolerance at query time instead of correcting first
- [Autocomplete](./autocomplete.md): complete a prefix rather than correct a whole word
- [Term Dictionary](../../sql/functions/search/term-dictionary.md): how `ts_dict_score` follows the driving fuzzy matcher

