---
title: Significant Terms
sidebar_position: 20
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Significant Terms

Find the words that make a subset of your corpus distinctive: terms that show up far more often inside one category than they do across the whole index. It runs on [term dictionary](../../sql/functions/search/term-dictionary.md) aggregates over an [inverted index](../../sql/indexes/inverted/index.md), and if you come from Elastic it covers what `significant_terms` gives you.

Nine articles fall into three categories (`science`, `sports` and `business`), each row carrying a tokenized `body`.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY tx AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    category VARCHAR NOT NULL,
    body VARCHAR
);

INSERT INTO articles VALUES
(1, 'science',  'quantum computing breakthrough data analysis'),
(2, 'science',  'quantum entanglement experiment data'),
(3, 'science',  'genome data sequencing quantum sensors'),
(4, 'sports',   'team wins championship data driven'),
(5, 'sports',   'team training data analytics'),
(6, 'sports',   'league data broadcast'),
(7, 'business', 'market data quarterly earnings'),
(8, 'business', 'market data stock analysis'),
(9, 'business', 'data revenue growth report');

CREATE INDEX articles_idx ON articles USING inverted (id, category, body tx);

VACUUM (REFRESH_TABLE) articles;
```

</details>

## Background frequency across the whole corpus

`ts_dict_agg(body)` returns every indexed term and `ts_dict_count(body)` returns how many documents contain each one. Run them over the full index to get the background rate. Common words like `data` sit at the top and tell you nothing about any one category.

```sql
SELECT unnest(ts_dict_agg(body))   AS term,
       unnest(ts_dict_count(body)) AS corpus_docs
FROM articles_idx
ORDER BY corpus_docs DESC, term
LIMIT 5;
-- result:
term	corpus_docs
data	9
quantum	3
analysis	2
market	2
team	2
```

## Foreground counts for one category

Filter the same aggregate to a single category and you get the per-term document counts inside that subset. On their own these counts are misleading: `data` and `quantum` both appear in all three science articles, so raw frequency cannot tell you which one is actually characteristic of science.

```sql
SELECT unnest(ts_dict_agg(body))   AS term,
       unnest(ts_dict_count(body)) AS science_docs
FROM articles_idx
WHERE category @@ 'science'
ORDER BY science_docs DESC, term;
-- result:
term	science_docs
data	3
quantum	3
analysis	1
breakthrough	1
computing	1
entanglement	1
experiment	1
genome	1
sensors	1
sequencing	1
```

## Rank by lift

Join the foreground counts to the background counts on the term and score each by how far its foreground count beats what the background rate predicts: `fg_docs - bg_docs * fg_total / bg_total`. `quantum` tops the list because it fills every science article yet stays rare across the rest of the corpus. Right behind it sits a cluster of terms that each appear in a single science article and nowhere else.

```sql
WITH bg AS (
  SELECT unnest(ts_dict_agg(body))   AS term,
         unnest(ts_dict_count(body)) AS bg_docs
  FROM articles_idx
),
fg AS (
  SELECT unnest(ts_dict_agg(body))   AS term,
         unnest(ts_dict_count(body)) AS fg_docs
  FROM articles_idx
  WHERE category @@ 'science'
),
totals AS (
  SELECT (SELECT count(*) FROM articles_idx WHERE category @@ 'science') AS fg_total,
         (SELECT count(*) FROM articles_idx)                             AS bg_total
)
SELECT fg.term,
       fg.fg_docs,
       bg.bg_docs,
       round(fg.fg_docs - bg.bg_docs * t.fg_total::DOUBLE / t.bg_total, 2) AS lift
FROM fg
JOIN bg USING (term)
CROSS JOIN totals t
ORDER BY lift DESC, fg.term
LIMIT 5;
-- result:
term	fg_docs	bg_docs	lift
quantum	3	3	2
breakthrough	1	1	0.67
computing	1	1	0.67
entanglement	1	1	0.67
experiment	1	1	0.67
```

## Require a minimum foreground count

The crude lift score rewards rarity, so a term that lands in one foreground document and no others (`breakthrough`, `computing`, `entanglement` and `experiment`) scores as high as anything with real support. A single stray document is enough to reach the top. Put a floor on `fg_docs` to make a term earn its place across several documents before it counts. At `fg_docs >= 2` only `quantum` stands out for science and the single-document noise is gone.

```sql
WITH bg AS (
  SELECT unnest(ts_dict_agg(body))   AS term,
         unnest(ts_dict_count(body)) AS bg_docs
  FROM articles_idx
),
fg AS (
  SELECT unnest(ts_dict_agg(body))   AS term,
         unnest(ts_dict_count(body)) AS fg_docs
  FROM articles_idx
  WHERE category @@ 'science'
),
totals AS (
  SELECT (SELECT count(*) FROM articles_idx WHERE category @@ 'science') AS fg_total,
         (SELECT count(*) FROM articles_idx)                             AS bg_total
)
SELECT fg.term,
       fg.fg_docs,
       bg.bg_docs,
       round(fg.fg_docs - bg.bg_docs * t.fg_total::DOUBLE / t.bg_total, 2) AS lift
FROM fg
JOIN bg USING (term)
CROSS JOIN totals t
WHERE fg.fg_docs >= 2
ORDER BY lift DESC, fg.term
LIMIT 5;
-- result:
term	fg_docs	bg_docs	lift
quantum	3	3	2
data	3	9	0
```

## The same query for another subset

Nothing in the query is tuned to science. Point the foreground filter at `business` and `market` comes out on top, concentrated in business articles and absent everywhere else. The same floor keeps the single-document terms out of the result.

```sql
WITH bg AS (
  SELECT unnest(ts_dict_agg(body))   AS term,
         unnest(ts_dict_count(body)) AS bg_docs
  FROM articles_idx
),
fg AS (
  SELECT unnest(ts_dict_agg(body))   AS term,
         unnest(ts_dict_count(body)) AS fg_docs
  FROM articles_idx
  WHERE category @@ 'business'
),
totals AS (
  SELECT (SELECT count(*) FROM articles_idx WHERE category @@ 'business') AS fg_total,
         (SELECT count(*) FROM articles_idx)                              AS bg_total
)
SELECT fg.term,
       fg.fg_docs,
       bg.bg_docs,
       round(fg.fg_docs - bg.bg_docs * t.fg_total::DOUBLE / t.bg_total, 2) AS lift
FROM fg
JOIN bg USING (term)
CROSS JOIN totals t
WHERE fg.fg_docs >= 2
ORDER BY lift DESC, fg.term
LIMIT 5;
-- result:
term	fg_docs	bg_docs	lift
market	2	2	1.33
data	3	9	0
```

## See also

- [Term Dictionary](../../sql/functions/search/term-dictionary.md): the `ts_dict_agg`, `ts_dict_count` and `ts_dict_freq` aggregates used here
- [Faceted Search](./faceted-search.md): count documents per label with the same aggregates
- [Trending Terms / Tag Cloud](./tag-cloud.md): rank terms by raw mentions instead of over-representation

