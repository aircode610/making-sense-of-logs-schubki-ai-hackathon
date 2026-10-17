---
title: Stemming and Stopwords
sidebar_position: 6
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Stemming and Stopwords

A search for "run" should find "running" and "runs". Noise words like "the" and "a" should never bloat the index. A [text dictionary](../../sql/indexes/inverted/text-analysis.md) handles both: [`stemming = true`](../../sql/functions/search/tokenizers/split_text.md) reduces words to their root with the Snowball stemmer picked by `locale`, while [`remove_stopwords`](../../sql/functions/search/tokenizers/remove_stopwords.md) drops a list of words before they ever reach the index. The same dictionary analyzes the indexed text and the query, so the inflection you store and the term you search for meet in the middle.

Three short articles share one indexed `body` column whose dictionary stems each word and strips the stopwords.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY body_dict AS
    split_text(case := 'lower') | remove_stopwords(['the', 'a', 'an', 'is', 'are', 'for']) | stem_words('en_US.UTF-8')
    WITH (frequency, position);

CREATE TABLE articles (id INTEGER PRIMARY KEY, body VARCHAR);

CREATE INDEX articles_idx ON articles USING inverted (id, body body_dict);

INSERT INTO articles VALUES
(1, 'the cats are running'),
(2, 'a dog runs fast'),
(3, 'running shoes for runners');

VACUUM (REFRESH_TABLE) articles;
```

</details>

## Match every inflection

The dictionary folds "running" and "runs" down to the stem `run` as it indexes each row, so all three rows store the same term. The query term is stemmed the exact same way, which means one query form finds every inflection without you spelling them out.

```sql
SELECT id, body FROM articles_idx WHERE body @@ 'run' ORDER BY id;
-- result:
id	body
1	the cats are running
2	a dog runs fast
3	running shoes for runners
```

## Stemming is not fuzzy matching

Stemming is precise, not fuzzy. "runners" stems to `runner`, which is a different root from `run`, so searching for `runner` matches only that row. If you want to match on misspellings or near-typos instead, reach for [Fuzzy Search](./fuzzy-search.md) or [Spell Correction](./spell-correction.md). The Snowball algorithm is rule based too, so irregular forms like "ran" are left alone rather than folded back to `run`.

```sql
SELECT id, body FROM articles_idx WHERE body @@ 'runner' ORDER BY id;
-- result:
id	body
3	running shoes for runners
```

## See the analysis

[`ts_lexize`](../../sql/functions/search/full-text.md) runs a string through the dictionary and hands back the terms it produces, which is the fastest way to see what stemming and stopword removal actually do. Regular inflections collapse to their stem, the irregular "ran" survives untouched and the stopwords disappear entirely.

```sql
SELECT ts_lexize('body_dict', 'running runners ran') AS stems, ts_lexize('body_dict', 'the cats are running') AS with_stopwords;
-- result:
stems	with_stopwords
{run,runner,ran}	{cat,run}
```

## What ends up in the index

`ts_dict_agg` lists the terms the index actually stores. The stopwords are gone and everything else is a stem, so the dictionary stays small and every query hits the same normalized form.

```sql
SELECT unnest(ts_dict_agg(body)) AS term FROM articles_idx ORDER BY term;
-- result:
term
cat
dog
fast
run
runner
shoe
```

## See also

- [Text analysis](../../sql/indexes/inverted/text-analysis.md): how a text dictionary tokenizes, stems and filters
- [Fuzzy Search](./fuzzy-search.md): match near-typos and misspellings, not inflections
- [Case Sensitivity and Diacritics](./case-sensitivity-and-diacritics.md): fold case and accents in the same dictionary

