---
title: "pipeline"
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# pipeline

The `pipeline` template composes several analyzers into one dictionary, feeding the output of each step as the input to the next. This builds behavior no single template offers — for example, split a field on a delimiter and then apply full [`split_text`](../../../functions/search/tokenizers/split_text.md) analysis (case folding, stemming, stopwords) to each resulting piece.

A pipeline is a chain: each `|` feeds the tokens of the stage on its left into the stage on its right, so `split_text_csv(',') | normalize_tokens(case := 'lower')` splits on commas and lowercases each piece. Stages run strictly in order, so a tokenizer that splits text must come before filters like [`remove_stopwords`](../../../functions/search/tokenizers/remove_stopwords.md) or [`stem_words`](../../../functions/search/tokenizers/stem_words.md) that refine the tokens it produces. Where [`union`](../union.md) runs members in parallel and merges their output, `pipeline` chains them so each stage transforms the previous stage's tokens.

```sql
CREATE TEXT SEARCH DICTIONARY pipe_expr AS split_text_csv(',') | normalize_tokens(case := 'lower');

SELECT ts_lexize('pipe_expr', 'RED,Green,BLUE');
-- result:
ts_lexize
{red,green,blue}
```

A chain of one stage is that template alone, `(a | b) | c` is the same flat pipeline as `a | b | c`, and an SQL function call or a lambda joins the chain as a [`sql`](../sql.md) stage:

```sql
CREATE TEXT SEARCH DICTIONARY pipe_expr_long AS
    normalize_tokens(case := 'lower') | split_text_csv('|') | normalize_tokens(case := 'upper') | remove_stopwords(['A']);

SELECT ts_lexize('pipe_expr_long', 'a|B|c');
-- result:
ts_lexize
{B,C}
```

## Stages

A stage may be any template, a [`union`](../union.md) list, or a bare dictionary name that runs a stored dictionary's analyzer, so `pipe_dict | remove_stopwords(['bar'])` appends a stage to a stored pipeline.

With exactly one stage the pipeline is unwrapped, so the dictionary tokenizes exactly like that template used on its own. A [`keyword`](../keyword.md) stage in any position after the first is dropped, because it passes its input through unchanged.

Two shapes are rejected when the dictionary is created. Both name the offending stage with a zero-based index that counts the stages left after dropped `keyword` stages:

- `pipeline: stage <i> expects <TYPE> input, but the preceding stage produces <TYPE>` — a step's input type must match the previous step's output. Every step takes `VARCHAR` input, so a step that emits binary terms can only be the last one: [`collate_tokens`](../../../functions/search/tokenizers/collate_tokens.md), [`encode_geopoint`](../../../functions/search/tokenizers/encode_geopoint.md) and [`encode_geojson`](../../../functions/search/tokenizers/encode_geojson.md). A [`sql`](../sql.md) step is not covered by this check: its expression is bound after the chain is validated, so the check sees `VARCHAR` whatever the expression returns.
- `pipeline: stage <i> produces a per-document store blob, which a pipeline cannot deliver` — a stage whose analyzer stores a per-document blob cannot sit in a chain. This rules out [`generate_wildcard_ngrams`](../../../functions/search/tokenizers/generate_wildcard_ngrams.md) in any position and `encode_geojson` with a `coding` other than `source`.

Both checks run only for a chain of two or more stages left after dropped `keyword` stages, since a single stage is unwrapped into the bare template.

The template supports the `FREQUENCY`, `POSITION` and `NORM` [feature flags](../index.md#feature-flags). `OFFSET` requires every stage to report offsets, because the pipeline folds that trait across the chain: one stage without offsets — [`sql`](../sql.md), [`generate_sparse_ngrams`](../../../functions/search/tokenizers/generate_sparse_ngrams.md), [`union`](../union.md), [`encode_geopoint`](../../../functions/search/tokenizers/encode_geopoint.md) or [`encode_geojson`](../../../functions/search/tokenizers/encode_geojson.md) — makes `WITH (offset)` fail when the dictionary is created, with `Unsupported index features are specified: offset`.

## Tokenization

Step 1 consumes the raw value; every later step is called once per token the step before it produced, and what it emits replaces that token. A first step of [`split_text_csv`](../../../functions/search/tokenizers/split_text_csv.md) on `,` splits `RED,Green,BLUE` into three tokens, then a [`normalize_tokens`](../../../functions/search/tokenizers/normalize_tokens.md) second step lowercases each, giving `{red,green,blue}`. Swap the second step for [`split_text`](../../../functions/search/tokenizers/split_text.md) with stemming and the same split feeds a stemmer, so `Cats,RUNNING` becomes `{cat,run}` — a split-then-analyze behavior no single template provides.

| Input | Steps | Tokens |
|---|---|---|
| `RED,Green,BLUE` | `split_text_csv(',') \| normalize_tokens(case := 'lower')` | `{red,green,blue}` |
| `Cats,RUNNING` | `split_text_csv(',') \| split_text(case := 'lower') \| stem_words('en_US.UTF-8')` | `{cat,run}` |

Split on commas, then lowercase each piece:

```sql
-- step 1 splits on commas, step 2 lowercases each piece
CREATE TEXT SEARCH DICTIONARY pipe_delim_norm AS
    split_text_csv(',')
    | normalize_tokens('en_US.UTF-8', case := 'lower');

SELECT ts_lexize('pipe_delim_norm', 'RED,Green,BLUE');
-- result:
ts_lexize
{red,green,blue}
```

Replace the second step with `split_text` analysis so each piece is also stemmed:

```sql
-- step 1 splits on commas, step 2 lowercases and stems each piece
CREATE TEXT SEARCH DICTIONARY pipe_delim_stem AS
    split_text_csv(',')
    | split_text(case := 'lower') | stem_words('en_US.UTF-8');

SELECT ts_lexize('pipe_delim_stem', 'Cats,RUNNING');
-- result:
ts_lexize
{cat,run}
```

Positions are consecutive and a dropped token leaves no hole: when a later step removes a token — a stop word, or a token it cannot handle such as an over-long collation key — a position whose tokens are all removed disappears and the later positions close up, while tokens that shared a position with a removed one keep it. A step that fans out, like [`generate_ngrams`](../../../functions/search/tokenizers/generate_ngrams.md) or a synonym step, has its own positions rebased onto the parent stream. Only steps that assign positions themselves — [`classify_text`](../../../functions/search/tokenizers/classify_text.md), [`find_nearest_words`](../../../functions/search/tokenizers/find_nearest_words.md), [`expand_solr_synonyms`](../../../functions/search/tokenizers/expand_solr_synonyms.md) and [`union`](../union.md) — keep their stacked numbering. If the first step rejects a value outright, that value yields no tokens at all and the following values are unaffected.

When offsets are available they always index the original input: each step's offsets are rebased into the span of the parent token they came from, and a token that reaches the end of its parent's text inherits the parent's end offset. The pipeline itself never transforms bytes: case folding, accent handling and Unicode normalization are each step's own business.

## Examples

### Delimiter then text analysis

```sql
CREATE TEXT SEARCH DICTIONARY pipe_dict AS
    split_text_csv(',')
    | split_text(case := 'lower') | stem_words('en_US.UTF-8');
```

### Three-step pipeline with stopwords

```sql
CREATE TEXT SEARCH DICTIONARY advanced_pipe AS
    split_text_csv('A')
    | split_text(case := 'lower')
    | normalize_tokens('en_US.UTF-8', accent := false)
    | remove_stopwords(['fox'])
    | stem_words('en_US.UTF-8')
    | normalize_tokens('en_US.UTF-8', case := 'upper');
```

### N-grams then normalization

```sql
CREATE TEXT SEARCH DICTIONARY ngram_norm AS
    generate_ngrams(2, 3) | normalize_tokens('en_US.UTF-8', case := 'lower');
```

### Longer chain

Grouping with parentheses changes nothing: `(a | b) | c` is the flat chain `a | b | c`:

```sql
CREATE TEXT SEARCH DICTIONARY nested_pipe AS
    normalize_tokens('en_US.UTF-8', case := 'lower')
    | split_text_csv('|')
    | normalize_tokens('en_US.UTF-8', case := 'upper')
    | remove_stopwords(['A']);
```

## See also

- [`union`](../union.md) — run analyzers in parallel and merge their tokens
- [CREATE TEXT SEARCH DICTIONARY](../index.md)

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

