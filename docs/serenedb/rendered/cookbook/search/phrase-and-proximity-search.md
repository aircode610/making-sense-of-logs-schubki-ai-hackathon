---
title: Phrase and Proximity Search
sidebar_position: 5
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Phrase and Proximity Search

Search for tokens appearing in a specific order. This allows matching partial or full sentences within indexed text, and — with [slop](#proximity-search-with-slop) — sentences whose wording drifts from the query. Requires `POSITION = true` in the dictionary.

See [Setup](./index.md#setup) for the shared dataset used in all examples.

## Basic phrase search

Use the `@@` operator with `ts_phrase` to find documents containing tokens in sequence:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('biggest blockbuster')
ORDER BY id;
-- result:
id	title
4	Jurassic Park
6	Scary Movie
```

Both documents contain the phrase "biggest blockbuster" in their descriptions.

## Multi-word phrases

Search for longer sequences:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('the war against its controllers');
-- result:
id	title
1	The Matrix
```

## Combining phrase conditions with AND

Find documents matching multiple phrases:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('alien') AND description @@ ts_phrase('galaxy')
ORDER BY id;
-- result:
id	title
7	Star Trek: The Motion Picture
```

## Combining phrase conditions with OR

Find documents matching any of several phrases:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('computer hacker') OR description @@ ts_phrase('serial killer')
ORDER BY id;
-- result:
id	title
1	The Matrix
6	Scary Movie
```

## Phrase search across columns

Search different columns in the same query:

```sql
SELECT id, title
FROM movies_idx
WHERE title @@ ts_phrase('the matrix') AND description @@ ts_phrase('machine')
ORDER BY id;
-- result:
id	title
2	The Matrix Reloaded
3	The Matrix Revolutions
```

## Combine with exact matching

Use phrase search together with term operations:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ 'sci-fi' AND description @@ ts_phrase('galaxy')
ORDER BY id;
-- result:
id	title	genre
7	Star Trek: The Motion Picture	sci-fi
8	Alien	sci-fi
```

## Proximity search with slop

An exact phrase is brittle: it fails on the words a writer put *between* the ones a searcher typed. Nobody searching for "group children" wants to miss "a group **of** children". Pass `slop := N` to buy the phrase a budget of `N` position moves:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('group children')
ORDER BY id;
-- result:
id	title
```

Nothing — the tokens are not adjacent. With one unit of slop, the intervening `of` is affordable:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('group children', slop := 1)
ORDER BY id;
-- result:
id	title
4	Jurassic Park
```

`slop` is an edit budget for phrases, playing the role [Levenshtein distance](./fuzzy-search.md#levenshtein-matching-with-ts_levenshtein) plays for a single word — except the only edit it can buy is *moving* a term, never substituting or dropping one. Line the query up with the document and note how far each token had to move: slop is the difference between the largest and the smallest of those moves, one figure for the whole phrase rather than a sum per token. When the tokens stay in order that is simply the number of words wedged between them, and `slop := 0` is an exact phrase, identical to omitting it. Every token you type must still appear in the document, so no amount of slop rescues a misspelled word — that is [`ts_levenshtein`](./fuzzy-search.md)'s job, and the two compose.

### Widening the window

Raise the budget and more distant co-occurrences come into range. "Zion falls to the machine army" needs three units:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('zion machine', slop := 3)
ORDER BY id;
-- result:
id	title
2	The Matrix Reloaded
```

At five, "Zion defends itself against the massive machine invasion" joins it:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('zion machine', slop := 5)
ORDER BY id;
-- result:
id	title
2	The Matrix Reloaded
3	The Matrix Revolutions
```

That is the whole tuning trade-off. A low budget keeps the phrase tight and precise; a high one drifts toward "these words appear near each other", and eventually toward a plain AND of the terms.

### Matching words out of order

A budget of 2 also pays for one swap of an adjacent pair, so a phrase can match text that reverses it. Searching "spacecraft alien" finds the film that says "alien spacecraft":

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('spacecraft alien', slop := 2)
ORDER BY id;
-- result:
id	title
7	Star Trek: The Motion Picture
```

Reordering is strictly more expensive than insertion: one intervening word costs 1, one transposition costs 2, whether the swapped pair stands alone or sits inside a longer phrase. If word order matters to you, keep `slop` at `0` or `1`.

### Other spellings

`::slop(N)` applies the same budget as a modifier on an existing phrase — useful when the phrase comes from somewhere you would rather not edit, such as [`phraseto_tsquery`](../../sql/functions/search/full-text.md#phraseto_tsquery) or a stored query string:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('group children')::slop(1)
ORDER BY id;
-- result:
id	title
4	Jurassic Park
```

Lucene's `"..."~N` proximity syntax also carries through [`to_tsquery`](../../sql/functions/search/full-text.md#to_tsquery), which matters when you are porting queries from Elasticsearch:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ to_tsquery('"group children"~1')
ORDER BY id;
-- result:
id	title
4	Jurassic Park
```

The two spellings are mutually exclusive — combining `slop := N` with `::slop(N)` on one phrase is an error rather than a silently chosen winner.

### Slop and explicit gaps

`slop` composes with the gap arguments, and this is the one case where its meaning needs care: the budget counts deviation from the gap you *declared*, not from adjacency. Here `group`, gap `1`, `children` declares "exactly one token between", which "a group of children" satisfies outright, so a zero budget suffices:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_phrase('group', 1, 'children', slop := 0)
ORDER BY id;
-- result:
id	title
4	Jurassic Park
```

Raising the budget to `1` would then admit anything one step off that declaration — adjacent tokens, or two tokens apart. Interval gaps are the exception: `[min, max]` already expresses a range, so pairing it with `slop` is rejected rather than compounded.

## Combine with analytics

The power of SereneDB: search and aggregate in a single query:

```sql
SELECT genre, COUNT(*) AS matches, AVG(runtime) AS avg_runtime
FROM movies_idx
WHERE description @@ ts_phrase('film')
GROUP BY genre
ORDER BY matches DESC, genre;
-- result:
genre	matches	avg_runtime
drama	1	96
```

```sql
SELECT genre,
       COUNT(*) AS count,
       MIN(year) AS earliest,
       MAX(year) AS latest
FROM movies_idx
WHERE description @@ ts_phrase('biggest blockbuster')
GROUP BY genre
ORDER BY genre;
-- result:
genre	count	earliest	latest
adventure	1	1993	1993
comedy	1	2000	2000
```

## How phrase search works

1. The query text goes through the **same dictionary** as the indexed data
2. The resulting tokens must appear in the **same order** and at **consecutive positions** in the document -- unless a gap or [slop](#proximity-search-with-slop) budget loosens one or both of those requirements
3. Because both sides use the same normalization (case, stemming, accents), matching is consistent

For example, with `basic_dict` (`CASE = 'lower'`, `ACCENT = false`):

```sql
-- The query "Biggest Blockbuster" becomes tokens: {biggest, blockbuster}
SELECT ts_lexize('basic_dict', 'Biggest Blockbuster');
-- result:
ts_lexize
{biggest,blockbuster}
```

## See also

- [Case-Sensitivity and Diacritics](./case-sensitivity-and-diacritics.md) — how normalization affects phrase matching
- [Exact Value Matching](./exact-value-matching.md) — single-token matching
- [BM25/TFIDF Ranking](./ranking.md) — ordering results by relevance

