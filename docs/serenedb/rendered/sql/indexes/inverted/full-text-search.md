---
title: Full-Text Search
sidebar_position: 5
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

Once a column is covered by an [inverted index](./index.md), you search it with the `@@` **match operator**. The left side is the indexed column; the right side is a query expression of type [`TSQUERY`](../../data_types/tsquery.md). Queries select **from the index by name**:

```sql
SELECT ... FROM index_name WHERE column @@ query;
```

Every query family below produces a `TSQUERY`. The simplest is a bare string literal, which is analyzed by the column's [text search dictionary](../../statements/create_text_search_dictionary/index.md) into one or more tokens; multi-token input matches any token (`OR` semantics):

```sql
SELECT a, b FROM sentences_idx WHERE b @@ 'fox' ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
2	quick red fox jumps over lazy dog
```

<DocCallout type="tip">

All examples on this page use a `sentences` table whose `b` column is indexed with a lower-casing, non-stemming dictionary. For a full reference of every function and operator, see [Full-Text Search Functions](../../functions/search/full-text.md).

</DocCallout>

## Term and phrase search {#phrase-search}

[`ts_phrase`](../../functions/search/full-text.md#ts_phrase) matches a run of tokens in order. It requires `position` to be enabled on the column ([feature flags](./text-analysis.md#token-positions-and-feature-flags)):

```sql
SELECT a, b FROM sentences_idx WHERE b @@ ts_phrase('over lazy dog') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
2	quick red fox jumps over lazy dog
```

The `##` operator builds a **proximity phrase** by chaining parts left to right:

- `a ## b` — `a` and `b` must be **strictly adjacent**, in order;
- `a ## N ## b` — exactly `N` tokens may sit between them;
- `a ## [min, max] ## b` — the gap may be anywhere in that range;
- the chain extends to any length — `a ## b ## c` — and each pair can carry its own gap, e.g. `a ## 1 ## b ## c`.

```sql
SELECT a, b FROM sentences_idx WHERE b @@ ('quick' ## 'brown') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
```

```sql
SELECT a, b FROM sentences_idx WHERE b @@ ('quick' ## 1 ## 'fox') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
2	quick red fox jumps over lazy dog
```

```sql
SELECT a, b FROM sentences_idx WHERE b @@ ('quick' ## [0, 2] ## 'fox') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
2	quick red fox jumps over lazy dog
```

**How phrase matching works.** A phrase matches only when its tokens occur **adjacent and in order**; proximity (`##`) relaxes "adjacent" to "within a gap". Tested against the document `quick brown fox jumps over lazy dog`:

| Query | Matches? | Why |
|---|:---:|---|
| `ts_phrase('quick brown')` | ✅ | `quick`, `brown` are adjacent, in order |
| `ts_phrase('brown quick')` | ❌ | both tokens present, but not in that order |
| `ts_phrase('quick fox')` | ❌ | `brown` sits between them — not contiguous |
| `'quick' ## 1 ## 'fox'` | ✅ | proximity allows exactly one token (`brown`) between |

### What can be chained with `##` {#phrase-parts}

Each side of a `##` is a single **phrase part**. A part may be:

- a **bare word** — but only a *single* token (a multi-word string is not a phrase part; use `ts_phrase` for that), or
- one of [`ts_phrase`](../../functions/search/full-text.md#ts_phrase), [`ts_starts_with`](../../functions/search/full-text.md#ts_starts_with), [`ts_like`](../../functions/search/full-text.md#ts_like), [`ts_regexp`](../../functions/search/full-text.md#ts_regexp), [`ts_levenshtein`](../../functions/search/full-text.md#ts_levenshtein), [`ts_any`](../../functions/search/full-text.md#ts_any) or [`ts_between`](../../functions/search/full-text.md#ts_between).

These part types **mix freely**: any of them can occupy any position in a single chain, in any combination, with an independent gap between any pair — for example `ts_starts_with('qu') ## 1 ## ts_any(['fox', 'dog'])` chains a prefix part, a gap and an alternatives part.

The boolean operators `&&`, `||` and `!!` are **not** phrase parts — they combine *whole* queries, not positions within a phrase. So they cannot appear directly inside a `##` chain:

| Goal | ✅ Do this | ❌ Not this |
|---|---|---|
| Alternatives at one position | `'quick' ## ts_any(['brown', 'grey'])` | `'quick' ## ('brown' \|\| 'grey')` |
| Prefix / fuzzy at a position | `'quick' ## ts_starts_with('bro')` | — |
| AND / OR / NOT *around* a phrase | `('quick' ## 'brown') && 'dog'` | `'quick' ## ('brown' && 'dog')` |

In short: build the phrase with `##` and the allowed parts, then combine the finished phrase with other queries using `&&` / `||` / `!!` on the **outside**.

## Prefix, wildcard and regex

[`ts_starts_with`](../../functions/search/full-text.md#ts_starts_with) matches any token with the given prefix:

```sql
SELECT a, b FROM sentences_idx WHERE b @@ ts_starts_with('turt') ORDER BY a;
-- result:
a	b
3	slow grey turtle sleeps
```

[`ts_like`](../../functions/search/full-text.md#ts_like) matches tokens against a SQL `LIKE` pattern (`%` = any run of characters, `_` = a single character):

```sql
SELECT a, b FROM sentences_idx WHERE b @@ ts_like('quic%') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
2	quick red fox jumps over lazy dog
```

[`ts_regexp`](../../functions/search/full-text.md#ts_regexp) matches tokens against a regular expression. The default syntax is Perl-compatible (RE2); pass `'posix'` for POSIX ERE:

```sql
SELECT a, b FROM sentences_idx WHERE b @@ ts_regexp('qu.*ck') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
2	quick red fox jumps over lazy dog
```

**How pattern matching works.** Each pattern is tested against the indexed **tokens**, not the raw field. Against the tokens of `quick brown fox jumps over lazy dog`:

| Query | Matching token | Note |
|---|---|---|
| `ts_starts_with('qu')` | `quick` | any token with that prefix |
| `ts_like('%zy')` | `lazy` | `%` = any run of chars, `_` = one char |
| `ts_regexp('f.x')` | `fox` | RE2 by default; `'posix'` for POSIX ERE |

## Fuzzy and similarity search

[`ts_levenshtein`](../../functions/search/full-text.md#ts_levenshtein) matches tokens within a given edit distance — typo-tolerant search:

```sql
SELECT id, name FROM products_idx WHERE name @@ ts_levenshtein('cat', 1) ORDER BY id;
-- result:
id	name
1	cat
2	bat
3	car
5	cats
6	act
```

[`ts_ngram`](../../functions/search/full-text.md#ts_ngram) matches by n-gram similarity against an [n-gram-tokenized](../../functions/search/tokenizers/generate_ngrams.md) column; the optional threshold (0–1) trades precision for recall:

```sql
SELECT id, title FROM titles_idx WHERE title @@ ts_ngram('hello', 0.3) ORDER BY id;
-- result:
id	title
1	hello
2	help
4	held
```

**How fuzzy matching works.** Each query term matches any indexed token within the given [edit distance](https://en.wikipedia.org/wiki/Levenshtein_distance) (insertions, deletions, substitutions):

| Query | Closest token | Edit distance | `ts_levenshtein(…, 1)` |
|---|---|:---:|:---:|
| `jumxs` | `jumps` | 1 | ✅ |
| `cats` | _none within 1_ | ≥ 2 | ❌ |

See the [Fuzzy Search](../../../cookbook/search/fuzzy-search.md) recipe for a deeper walkthrough.

## Boolean composition

Build compound queries from `TSQUERY` expressions with `||` (OR), `&&` (AND) and the unary `!!` (NOT):

```sql
SELECT a, b FROM sentences_idx
WHERE b @@ (ts_phrase('quick brown') || ts_phrase('grey turtle'))
ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
3	slow grey turtle sleeps
```

```sql
SELECT a, b FROM sentences_idx
WHERE b @@ (ts_phrase('quick') && ts_phrase('brown fox'))
ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
```

```sql
SELECT a, b FROM sentences_idx
WHERE b @@ (ts_phrase('quick') && !!ts_phrase('brown fox'))
ORDER BY a;
-- result:
a	b
2	quick red fox jumps over lazy dog
```

When the alternatives are a list, [`ts_any`](../../functions/search/full-text.md#ts_any) (OR) and [`ts_all`](../../functions/search/full-text.md#ts_all) (AND) are more convenient. `ts_any` takes an optional minimum number of alternatives that must match:

```sql
SELECT a, b FROM sentences_idx
WHERE b @@ ts_any([ts_phrase('red fox'), ts_phrase('grey turtle')])
ORDER BY a;
-- result:
a	b
2	quick red fox jumps over lazy dog
3	slow grey turtle sleeps
```

```sql
SELECT a, b FROM sentences_idx
WHERE b @@ ts_all([ts_phrase('quick'), ts_phrase('brown fox')])
ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
```

```sql
SELECT a, b FROM sentences_idx
WHERE b @@ ts_any(['quick', 'brown', 'turtle'], 2)
ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
```

[`ts_compound`](../../functions/search/full-text.md#ts_compound) builds an Elasticsearch-style boolean query from `must`, `must_not` and `should` buckets:

```sql
SELECT a, b FROM sentences_idx
WHERE b @@ ts_compound(
    ts_phrase('quick'),
    ts_phrase('grey'),
    [ts_phrase('lazy'), ts_phrase('big')]
)
ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
2	quick red fox jumps over lazy dog
```

## Range queries {#range-queries}

Numeric, temporal and verbatim text columns support range matching. [`ts_between`](../../functions/search/full-text.md#ts_between) takes lower and upper bounds (either may be `NULL` for unbounded) and inclusivity flags; [`ts_lt`](../../functions/search/full-text.md#ts_lt), `ts_le`, `ts_gt` and `ts_ge` are single-bound shortcuts:

```sql
SELECT a FROM sentences_idx WHERE a @@ ts_between(2, 3, true, true) ORDER BY a;
-- result:
a
2
3
```

```sql
SELECT a FROM sentences_idx WHERE a @@ ts_le(2) ORDER BY a;
-- result:
a
1
2
```

See the [Range Queries](../../../cookbook/search/range-queries.md) recipe for lexicographic ordering details.

## PostgreSQL-compatible query parsers

For compatibility with PostgreSQL full-text search, SereneDB accepts the familiar parser functions. They produce a `TSQUERY` from a single string. Note these are SereneDB inverted-index queries, not PG `tsvector`/`tsquery`.

- [`plainto_tsquery`](../../functions/search/full-text.md#postgresql-compatible-parsers) — tokenize and `AND` the terms:

  ```sql
SELECT a, b FROM sentences_idx WHERE b @@ plainto_tsquery('Quick Brown') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
```

- [`phraseto_tsquery`](../../functions/search/full-text.md#postgresql-compatible-parsers) — treat the input as a phrase:

  ```sql
SELECT a, b FROM sentences_idx WHERE b @@ phraseto_tsquery('over lazy dog') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
2	quick red fox jumps over lazy dog
```

- [`to_tsquery`](../../functions/search/full-text.md#to_tsquery) — parse a Lucene-style query string (`AND`/`OR`, `+`required / `-`excluded, `*` prefix, `~` fuzzy, `"phrase"`, grouping, `^` boost):

  ```sql
SELECT a, b FROM sentences_idx WHERE b @@ to_tsquery('quick AND brown') ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
```

- [`websearch_to_tsquery`](../../functions/search/full-text.md#postgresql-compatible-parsers) — web-search syntax, where quoted substrings are phrases and `OR` separates alternatives:

  ```sql
SELECT a, b FROM sentences_idx
WHERE b @@ websearch_to_tsquery('"quick brown" OR "grey turtle"')
ORDER BY a;
-- result:
a	b
1	quick brown fox jumps over lazy dog
3	slow grey turtle sleeps
```

## Highlighting {#highlighting}

[`ts_highlight`](../../functions/search/highlighting.md) wraps matched terms in markup. Its standalone form takes a text and an array of start/end byte offsets (such as those produced by `ts_offsets`); the default markup is `<b>...</b>`, and `StartSel`/`StopSel` options override it:

```sql
SELECT ts_highlight('the quick brown fox jumps over the lazy dog', [4, 9]) AS snippet;
-- result:
snippet
the <b>quick</b> brown fox jumps over the lazy dog
```

[`ts_offsets`](../../functions/search/highlighting.md) returns the byte offsets of the matched tokens as interleaved `start, end` pairs — the building block for custom highlighting in the client. Enabling `offset` on the column stores those offsets in the index; without it they are recomputed for each matching row:

```sql
SELECT id, ts_offsets(docs_idx.body) AS offsets
FROM docs_idx
WHERE body @@ ts_phrase('fox')
ORDER BY id;
-- result:
id	offsets
1	{6,9}
2	{0,3}
```

## Convenience predicates

Several wrapper functions read more naturally than `col @@ ts_*(...)` and expand to exactly that — [`phrase_matches`](../../functions/search/full-text.md#phrase_matches), [`has_all_tokens`](../../functions/search/full-text.md#has_all_tokens), [`has_any_tokens`](../../functions/search/full-text.md#has_any_tokens), [`ngram_matches`](../../functions/search/full-text.md#ngram_matches) and [`levenshtein_matches`](../../functions/search/full-text.md#levenshtein_matches). Plain SQL [`IS NULL` / `IS NOT NULL`](../../functions/search/full-text.md#is-null) on an indexed column is claimed by the index as well. See the [function reference](../../functions/search/full-text.md) for the full list.

## Inspecting the query plan

A full-text search is a first-class part of the SQL query plan, not a black box bolted on the side. The `@@` predicate compiles to an **`IRESEARCH_SCAN`** over the inverted index, with the matched terms pushed into the scan as its `Index Filter`. `EXPLAIN` shows it:

```sql
EXPLAIN SELECT a FROM sentences_idx WHERE b @@ 'fox';
-- result:
QUERY PLAN
╭─ IRESEARCH_SCAN ─────╮
│ Index: sentences_idx │
│ Lookup: table        │
│ Index Filter:        │
│ ╭─ Term ───────────╮ │
│ │ Field: b(string) │ │
│ │ Value: fox       │ │
│ ╰──────────────────╯ │
│ Projections: a       │
│ ~1 row               │
╰──────────────────────╯
```

A predicate the index cannot serve shows up as a `Column Filter` instead, checked row by row after the scan.

Because the search executes inside the scan, it composes with the rest of SQL: a `JOIN`, a `GROUP BY`, or an `ORDER BY <scorer>` over the same query is planned and run as one statement. See [Profiling](../../../cookbook/performance/profiling.md) for reading plans, and [Ranking](./ranking.md#top-k-queries-and-wand-pruning) for the WAND-optimized `Top: k, optimized` plan.

## Relevance ranking {#relevance-ranking}

Matching is a yes/no filter. To score and order matches by relevance — `BM25` and other scorers, boosting, and WAND-accelerated top-K queries — see the dedicated [Ranking](./ranking.md) page.

## See also

- [Inverted Index](./index.md) — creating the index
- [Full-Text Search Functions](../../functions/search/full-text.md) — complete function reference
- [`tsquery` data type](../../data_types/tsquery.md)
- [Vector Search](./vector-search.md) · [Hybrid Search](./hybrid-search.md) · [Geospatial Search](./geospatial-search.md)
- [Search cookbook](../../../cookbook/search/index.md)

