---
title: "keyword"
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# keyword

The `keyword` template emits the entire input as a single verbatim token — it performs no splitting, normalization or stemming. It is the right choice for values that must match exactly and as a whole: tags, status codes, enum values, identifiers and other atomic strings.

Because the token is the raw input, a query matches only when it is byte-for-byte identical, including case and spacing. For an exact-match column that should still be case- or accent-insensitive, use [`normalize_tokens`](../../functions/search/tokenizers/normalize_tokens.md), which normalizes the single token; for per-word search, use [`split_text`](../../functions/search/tokenizers/split_text.md).

## Options

The `keyword` template takes no options.

## Tokenization

The template performs no analysis at all: whatever string it receives becomes a single token, byte for byte. Spaces, punctuation and case are all preserved, so a query matches only when it is identical to the indexed value as a whole.

| Input | Tokens |
|---|---|
| `New York City` | `{"New York City"}` |
| `Hello World 42` | `{"Hello World 42"}` |
| `ERR_TIMEOUT` | `{ERR_TIMEOUT}` |

The token is quoted in the output whenever it contains spaces or other characters that would otherwise be ambiguous in the array literal. Preview it with `ts_lexize`:

```sql
CREATE TEXT SEARCH DICTIONARY tok_keyword AS
    keyword() WITH (frequency);

SELECT ts_lexize('tok_keyword', 'New York City');
-- result:
ts_lexize
{"New York City"}
```

## Examples

Create a verbatim dictionary:

```sql
CREATE TEXT SEARCH DICTIONARY verbatim AS
    keyword() WITH (frequency);
```

Preview how it tokenizes — the whole string, spaces and all, becomes one token:

```sql
SELECT ts_lexize('verbatim', 'Hello World 42');
-- result:
ts_lexize
{"Hello World 42"}
```

## See also

- [`normalize_tokens`](../../functions/search/tokenizers/normalize_tokens.md) — a single token, normalized for case and accents
- [`split_text`](../../functions/search/tokenizers/split_text.md) — split into words
- [CREATE TEXT SEARCH DICTIONARY](./index.md)

