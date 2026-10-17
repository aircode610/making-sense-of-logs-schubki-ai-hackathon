---
title: Fuzzy Search
sidebar_position: 8
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Fuzzy Search

Fuzzy search finds approximate matches despite typos, spelling variations or alternative forms. SereneDB supports two approaches, each suited to different use cases.

## Similarity measures

### Levenshtein distance

Measures the minimum number of single-character edits (insertions, deletions, substitutions) to transform one string into another.

| From | To | Distance | Edits |
|---|---|---|---|
| `galaxy` | `galxy` | 1 | 1 deletion |
| `search` | `serach` | 2 | 2 substitutions |

### Damerau-Levenshtein distance

Extends Levenshtein by also counting **transpositions** (adjacent character swaps) as a single edit. This is more forgiving for common typos:

| From | To | Levenshtein | Damerau-Levenshtein |
|---|---|---|---|
| `galaxy` | `glaaxy` | 2 | 1 (transposition) |
| `search` | `saerch` | 2 | 1 (transposition) |

### N-gram similarity

Breaks strings into substrings of fixed length (bigrams, trigrams, etc.) and measures how many substrings are shared. Works better for longer strings and partial matches.

Example with bigrams (n=2):

| String | Bigrams |
|---|---|
| `hello` | `he`, `el`, `ll`, `lo` |
| `help` | `he`, `el`, `lp` |

Searching for `hello` finds `help` with similarity 2/4 = 0.5: two of the query's four bigrams, `he` and `el`, appear in `help` in the same order.

## When to use which

| Approach | Best for | Typical use case |
|---|---|---|
| **Levenshtein** | Short strings, exact typo correction | User name search, product codes, tags |
| **N-gram** | Longer strings, partial matching | Autocomplete, "did you mean?", document titles |

## Levenshtein matching with `ts_levenshtein`

Finds terms within a given edit distance. Uses Damerau-Levenshtein by default (transpositions count as one edit).

### Setup

Any text dictionary works — stemming should typically be disabled for fuzzy matching:

```sql
CREATE TEXT SEARCH DICTIONARY fuzzy_dict AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name VARCHAR
);

CREATE INDEX idx_products ON products
    USING inverted (id, name fuzzy_dict);

INSERT INTO products VALUES
    (1, 'cat'), (2, 'bat'), (3, 'car'),
    (4, 'dog'), (5, 'cats'), (6, 'act');

VACUUM (REFRESH_TABLE) products;
```

### Basic usage

```sql
-- Exact match only (distance 0)
SELECT id, name FROM idx_products
WHERE name @@ ts_levenshtein('cat', 0)
ORDER BY id;
-- result:
id	name
1	cat

-- Distance 1: one edit away
SELECT id, name FROM idx_products
WHERE name @@ ts_levenshtein('cat', 1)
ORDER BY id;
-- result:
id	name
1	cat
2	bat
3	car
5	cats
6	act

-- Distance 2: two edits away
SELECT id, name FROM idx_products
WHERE name @@ ts_levenshtein('cat', 2)
ORDER BY id;
-- result:
id	name
1	cat
2	bat
3	car
5	cats
6	act
```

### Disable transpositions

Use strict Levenshtein (no transposition counting):

```sql
-- Disable transpositions: 'act' no longer matches 'cat'
SELECT id, name FROM idx_products
WHERE name @@ ts_levenshtein('cat', 1, false)
ORDER BY id;
-- result:
id	name
1	cat
2	bat
3	car
5	cats
```

### Prefix matching

Require a prefix before applying fuzzy matching — useful for autocomplete:

```sql
-- Must start with 'ca', then fuzzy match the rest
SELECT id, name FROM idx_products
WHERE name @@ ts_levenshtein('t', 1, true, 'ca')
ORDER BY id;
-- result:
id	name
1	cat
3	car
5	cats
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| *column* | column | | Indexed text column |
| *term* | string | | Search term |
| *distance* | integer | | Max edit distance (0–4) |
| *transpositions* | boolean | `true` | Count transpositions as single edit |
| *prefix* | string | `''` | Required prefix before fuzzy matching |

The number of dictionary terms the predicate expands to is capped by the [`sdb_levenshtein_max_terms`](../../sql/indexes/inverted/maintenance.md#session-settings) session setting (default `50`, per index segment), keeping the terms closest to the query. `SET sdb_levenshtein_max_terms = 0` matches every term within the edit distance.

## N-gram matching with `ts_ngram`

Finds terms by n-gram similarity. Requires an index built with a `generate_ngrams` dictionary of one gram size, `min_gram` equal to `max_gram`.

### Setup

```sql
CREATE TEXT SEARCH DICTIONARY bigram_dict AS
    generate_ngrams(2, 2)
    WITH (frequency, position);

CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    title VARCHAR
);

CREATE INDEX idx_articles_ngram ON articles
    USING inverted (id, title bigram_dict);

INSERT INTO articles VALUES
    (1, 'hello'), (2, 'help'), (3, 'world'),
    (4, 'held'), (5, 'hero');

VACUUM (REFRESH_TABLE) articles;
```

### Basic usage

```sql
-- Default threshold — strict matching
SELECT id, title FROM idx_articles_ngram
WHERE title @@ ts_ngram('hello')
ORDER BY id;
-- result:
id	title
1	hello

-- Lower threshold (0.3) — matches more loosely
SELECT id, title FROM idx_articles_ngram
WHERE title @@ ts_ngram('hello', 0.3)
ORDER BY id;
-- result:
id	title
1	hello
2	help
4	held

-- Threshold 0.0 — matches anything with at least one shared n-gram
SELECT id, title FROM idx_articles_ngram
WHERE title @@ ts_ngram('hello', 0.0)
ORDER BY id;
-- result:
id	title
1	hello
2	help
4	held
5	hero
```

### Tuning n-gram size

- **Bigrams** (min_gram=2, max_gram=2): More matches, less precision. Good for short terms.
- **Trigrams** (min_gram=3, max_gram=3): Fewer matches, more precision. Better for longer terms.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| *column* | column | | Indexed text column (must use `generate_ngrams` dictionary) |
| *term* | string | | Search term |
| *threshold* | float | `0.7` | Minimum n-gram similarity (0.0–1.0) |

## Combining with other filters

Both fuzzy functions work with `AND`, `OR` and other search predicates:

```sql
-- Fuzzy match + exact filter
SELECT id, name FROM idx_products
WHERE name @@ ts_levenshtein('cat', 1) AND id < 4
ORDER BY id;
-- result:
id	name
1	cat
2	bat
3	car
```

## See also

- [CREATE INDEX](../../sql/statements/create_index/index.md)
- [CREATE TEXT SEARCH DICTIONARY](../../sql/statements/create_text_search_dictionary/index.md)
- [Phrase and Proximity Search](./phrase-and-proximity-search.md)
- [Spell Correction](./spell-correction.md): correct the input before you query instead of matching fuzzily at query time
- [Synonyms](./synonyms.md): match different words for the same thing rather than typos of one word

