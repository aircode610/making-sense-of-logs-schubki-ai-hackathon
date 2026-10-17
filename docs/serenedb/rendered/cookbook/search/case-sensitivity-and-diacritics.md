---
title: Case-Sensitivity and Diacritics
sidebar_position: 3
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Case-Sensitivity and Diacritics

Control how text is normalized before indexing and searching. Dictionary configuration determines whether searches are case-sensitive and whether accented characters match their base forms.

See [Setup](./index.md#setup) for the shared dataset used in all examples.

## How it works

When text is indexed, the dictionary's `CASE` and `ACCENT` options normalize tokens:

| Option | Value | Effect |
|---|---|---|
| `CASE` | `'lower'` | Convert all tokens to lowercase |
| `CASE` | `'upper'` | Convert all tokens to uppercase |
| `CASE` | `'none'` | Preserve original case |
| `ACCENT` | `false` | Strip diacritics (é → e, ü → u) |
| `ACCENT` | `true` | Preserve diacritics |

Use `ts_lexize` to see exactly how a dictionary transforms text:

```sql
SELECT ts_lexize('basic_dict', 'Café Résumé');
-- result:
ts_lexize
{cafe,resume}

-- {cafe,resume}
SELECT ts_lexize('exact_dict', 'Café Résumé');
-- result:
ts_lexize
{Café,Résumé}
```

## Case-insensitive search

The `basic_dict` uses `CASE = 'lower'`, so searches are case-insensitive:

```sql
-- All of these match "The Matrix"
SELECT id, title FROM movies_idx WHERE title @@ ts_phrase('the matrix');
-- result:
id	title
1	The Matrix
2	The Matrix Reloaded
3	The Matrix Revolutions

SELECT id, title FROM movies_idx WHERE title @@ ts_phrase('THE MATRIX');
-- result:
id	title
1	The Matrix
2	The Matrix Reloaded
3	The Matrix Revolutions

SELECT id, title FROM movies_idx WHERE title @@ ts_phrase('The Matrix');
-- result:
id	title
1	The Matrix
2	The Matrix Reloaded
3	The Matrix Revolutions
```

## Case-sensitive search

The `exact_dict` uses `CASE = 'none'`, preserving original case:

```sql
-- Only matches the exact capitalization
SELECT id, title FROM movies_exact_idx WHERE title @@ ts_phrase('The Matrix');
-- result:
id	title
1	The Matrix
2	The Matrix Reloaded
3	The Matrix Revolutions
```

```sql
-- No results — wrong case
SELECT id, title FROM movies_exact_idx WHERE title @@ ts_phrase('the matrix');
-- result:
id	title
```

## Accent-insensitive search

The `basic_dict` uses `ACCENT = false`, stripping diacritics:

```sql
SELECT id, title FROM movies_idx WHERE title @@ ts_phrase('cafe society');
-- result:
id	title
9	Café Society
```

```sql
-- Also works with the accented form
SELECT id, title FROM movies_idx WHERE title @@ ts_phrase('café society');
-- result:
id	title
9	Café Society
```

## Accent-sensitive search

The `exact_dict` uses `ACCENT = true`, preserving diacritics:

```sql
-- Must use the exact accent to match
SELECT id, title FROM movies_exact_idx WHERE title @@ ts_phrase('Café');
-- result:
id	title
9	Café Society
```

```sql
-- No match — accent is missing
SELECT id, title FROM movies_exact_idx WHERE title @@ ts_phrase('Cafe');
-- result:
id	title
```

## Creating custom dictionaries

Different use cases call for different normalization. Here are common patterns:

### Search-friendly (case + accent insensitive)

```sql
CREATE TEXT SEARCH DICTIONARY search_friendly AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false) | stem_words('en_US.UTF-8')
    WITH (frequency, position);
```

### Identifier matching (case + accent sensitive)

```sql
CREATE TEXT SEARCH DICTIONARY identifier_dict AS
    split_text();
```

### Uppercase normalization

```sql
CREATE TEXT SEARCH DICTIONARY upper_dict AS
    split_text(case := 'upper') | normalize_tokens('en_US.UTF-8', accent := false);

SELECT ts_lexize('upper_dict', 'Café Résumé');
-- result:
ts_lexize
{CAFE,RESUME}
```

## See also

- [CREATE TEXT SEARCH DICTIONARY](../../sql/statements/create_text_search_dictionary/index.md) — all dictionary templates and options
- [Phrase and Proximity Search](./phrase-and-proximity-search.md) — using phrase search with dictionaries

