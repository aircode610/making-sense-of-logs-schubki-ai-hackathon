---
title: Highlighting
sidebar_position: 24
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Highlighting

A results page is easier to trust when it shows why each row matched. [`ts_highlight`](../../sql/functions/search/highlighting.md) wraps the matched terms in a snippet of the document and [`ts_offsets`](../../sql/functions/search/highlighting.md) hands you the raw byte spans if you would rather render the markup yourself. Both read the match from the same [inverted index](../../sql/indexes/inverted/index.md) scan that answered the `WHERE`, so highlighting costs one extra column, not a second query.

Four short articles fill a `body` column here. Highlighting needs to know where each token sits, so the dictionary on that column sets `position = true`.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY hl AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position, offset);

CREATE TABLE articles (id INTEGER PRIMARY KEY, body VARCHAR);

INSERT INTO articles VALUES
(1, 'SereneDB runs full text search directly over an inverted index'),
(2, 'Vector search ranks similar documents by embedding distance'),
(3, 'The same inverted index powers faceted search and result highlighting'),
(4, 'No relevant content in this row at all');

CREATE INDEX articles_idx ON articles USING inverted (id, body hl);

VACUUM (REFRESH_TABLE) articles;
```

</details>

## Wrap the matched terms

Pass the searched column to `ts_highlight` and it returns the body with every hit in `<b>` tags. The match comes from whatever the `@@` predicate found, so you never repeat the query.

```sql
SELECT id, ts_highlight(body) AS snippet
FROM articles_idx
WHERE body @@ 'search'
ORDER BY id;
-- result:
id	snippet
1	SereneDB runs full text <b>search</b> directly over an inverted index
2	Vector <b>search</b> ranks similar documents by embedding distance
3	The same inverted index powers faceted <b>search</b> and result highlighting
```

## Use your own tags

`StartSel` and `StopSel` set the opening and closing markup, so point them at whatever your frontend styles.

```sql
SELECT id, ts_highlight(body, 'StartSel=<mark>, StopSel=</mark>') AS snippet
FROM articles_idx
WHERE body @@ 'search'
ORDER BY id;
-- result:
id	snippet
1	SereneDB runs full text <mark>search</mark> directly over an inverted index
2	Vector <mark>search</mark> ranks similar documents by embedding distance
3	The same inverted index powers faceted <mark>search</mark> and result highlighting
```

## Highlight a phrase as one span

A phrase match is a single span from the first token to the last, not one box per word, so `inverted index` highlights as a unit.

```sql
SELECT id, ts_highlight(body) AS snippet
FROM articles_idx
WHERE body @@ ts_phrase('inverted index')
ORDER BY id;
-- result:
id	snippet
1	SereneDB runs full text search directly over an <b>inverted index</b>
3	The same <b>inverted index</b> powers faceted search and result highlighting
```

## Get the raw offsets instead

When you build the markup in the application layer, `ts_offsets` gives you the interleaved `start, end` byte pairs of each match and stays out of the rendering. `ts_highlight(body)` is exactly `ts_highlight(body, ts_offsets(body))` with the default tags.

```sql
SELECT id, ts_offsets(body) AS offsets
FROM articles_idx
WHERE body @@ 'search'
ORDER BY id;
-- result:
id	offsets
1	{24,30}
2	{7,13}
3	{39,45}
```

## Rank, then highlight the winners

Highlighting is a projection, so it composes with ranking and `LIMIT`. Order by [`BM25`](./ranking.md) and highlight only the page you return.

```sql
SELECT id, ts_highlight(body) AS snippet
FROM articles_idx
WHERE body @@ 'search'
ORDER BY BM25(articles_idx.tableoid) DESC, id
LIMIT 2;
-- result:
id	snippet
1	SereneDB runs full text <b>search</b> directly over an inverted index
2	Vector <b>search</b> ranks similar documents by embedding distance
```

## Trim the snippet to a window

On a long document you want a snippet around the hit, not the whole thing. `MaxWords` caps the fragment length and `ts_highlight` keeps the window tight around the match.

```sql
SELECT ts_highlight(body, 'MaxWords=9') AS snippet
FROM articles_idx
WHERE id = 5 AND body @@ 'search';
-- result:
snippet
of filler words before we finally mention the <b>search</b>
```

Other options tune the output: `MaxFragments` returns several passages joined by `FragmentDelimiter`, and `HighlightAll` wraps every match in the full untrimmed text. See the [reference](../../sql/functions/search/highlighting.md) for the full list.

## See also

- [Highlighting reference](../../sql/functions/search/highlighting.md): every `ts_highlight` option, `ts_offsets` and the standalone dictionary forms
- [BM25/TFIDF Ranking](./ranking.md): order the results before you highlight them
- [Phrase and Proximity Search](./phrase-and-proximity-search.md): the phrase queries that highlight as one span

