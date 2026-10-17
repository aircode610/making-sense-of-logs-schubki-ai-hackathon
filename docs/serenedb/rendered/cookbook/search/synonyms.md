---
title: Synonyms
sidebar_position: 7
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Synonyms

Shoppers and your catalog rarely use the same word. Someone types "telly", the product says "television" and nothing matches. A synonym dictionary closes that gap: you declare the words that mean the same thing and SereneDB expands them at analysis time, on both the indexed text and the query, so either side finds the other.

Synonyms are a step in a [text search dictionary](../../sql/statements/create_text_search_dictionary/index.md). You wrap a tokenizer and a synonym filter in a [`pipeline`](../../sql/statements/create_text_search_dictionary/pipeline/index.md): the tokenizer lowercases and splits the text, then the synonym step rewrites the tokens. There are two filters. [`expand_solr_synonyms`](../../sql/functions/search/tokenizers/expand_solr_synonyms.md) takes a map you write by hand and keeps the surface words, and [`expand_wordnet_synonyms`](../../sql/functions/search/tokenizers/expand_wordnet_synonyms.md) normalizes words to a shared sense from the WordNet database. Most of this recipe uses solr; the last section shows WordNet.

Four products sit in a catalog indexed on `name`, behind a dictionary that treats `tv`, `television` and `telly` as one word and files every `laptop` under `notebook`.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY syn AS
    split_text(case := 'lower')
    | expand_solr_synonyms('tv, television, telly
laptop => notebook')
    WITH (frequency, position);

CREATE TABLE catalog (id INTEGER PRIMARY KEY, name VARCHAR);

CREATE INDEX catalog_idx ON catalog USING inverted (id, name syn);

INSERT INTO catalog VALUES
(1, 'wall mounted tv'),
(2, 'smart television screen'),
(3, 'gaming laptop'),
(4, 'wireless headphones');

VACUUM (REFRESH_TABLE) catalog;
```

</details>

## Find the word the shopper did not type

The catalog never says "telly", but the query does. Expansion runs on the indexed text too, so the tv and television rows both carry "telly" and the search lands.

```sql
SELECT id, name FROM catalog_idx WHERE name @@ 'telly' ORDER BY id;
-- result:
id	name
1	wall mounted tv
2	smart television screen
```

## It works both ways

A comma group is symmetric, so it does not matter which member is in the document and which is in the query. Searching "tv" finds the row that says "television" just as well.

```sql
SELECT id, name FROM catalog_idx WHERE name @@ 'tv' ORDER BY id;
-- result:
id	name
1	wall mounted tv
2	smart television screen
```

## Rewrite one word onto another

Use `laptop => notebook` when you want a one-way rewrite rather than a group. Every "laptop" is filed as "notebook" so a search for "notebook" finds it, without dragging unrelated notebook senses back onto laptops.

```sql
SELECT id, name FROM catalog_idx WHERE name @@ 'notebook' ORDER BY id;
-- result:
id	name
3	gaming laptop
```

## See what a word expands to

`ts_lexize` runs a single value through the dictionary so you can see the expansion the index and the query both get. A two-way group returns every member, a one-way rule returns the target.

```sql
SELECT ts_lexize('syn', 'telly') AS telly, ts_lexize('syn', 'laptop') AS laptop;
-- result:
telly	laptop
{television,telly,tv}	{notebook}
```

## Normalize to a shared sense with WordNet

The [`expand_wordnet_synonyms`](../../sql/functions/search/tokenizers/expand_wordnet_synonyms.md) filter takes a different tack. Instead of adding synonyms to the surface word it replaces each word with the numeric id of its WordNet sense, so words that mean the same thing collapse to one term and match each other. Here "couch", "sofa" and "divan" share a sense, so any of them finds all three.

```sql
SELECT id, name FROM furniture_idx WHERE name @@ 'sofa' ORDER BY id;
-- result:
id	name
1	leather couch
2	fabric sofa
3	velvet divan
```

WordNet only knows the words in its map. A word with no sense passes through unchanged, so `ts_lexize` returns the word itself and it stays searchable as written; only the words the map knows meet their synonyms. Load the full WordNet database when you want broad coverage, or reach for solr when you would rather hand-write a few groups.

```sql
SELECT ts_lexize('wn', 'sofa')  AS sofa,
       ts_lexize('wn', 'couch') AS couch,
       ts_lexize('wn', 'table') AS unknown;
-- result:
sofa	couch	unknown
{100000001}	{100000001}	{table}
```

## See also

- [solr_synonyms](../../sql/functions/search/tokenizers/expand_solr_synonyms.md): the full synonym map syntax, groups and one-way rules
- [wordnet_synonyms](../../sql/functions/search/tokenizers/expand_wordnet_synonyms.md): the WordNet record format and sense normalization
- [pipeline](../../sql/statements/create_text_search_dictionary/pipeline/index.md): chaining a tokenizer with the synonym filter
- [Case-Sensitivity and Diacritics](./case-sensitivity-and-diacritics.md): the tokenizer step that normalizes text before synonyms apply

