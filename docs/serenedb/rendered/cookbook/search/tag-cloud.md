---
title: Tag Cloud
sidebar_position: 19
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Tag Cloud

A tag cloud or a trending words panel needs the vocabulary of a text column ranked by how often each word gets written. SereneDB keeps that tally in the [inverted index](../../sql/indexes/inverted/index.md) dictionary, so [`ts_dict_freq`](../../sql/functions/search/term-dictionary.md) ranks every term by total mentions without reading a single document.

The `posts` table below holds a handful of espresso brewing tips. Its `body` column runs through a `split_text` dictionary that sets `frequency = true` (what `ts_dict_freq` reads) and adds a small stopword list so filler like `the` never lands in the cloud.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY tx AS
    split_text(case := 'lower')
    | normalize_tokens('en_US.UTF-8', accent := false)
    | remove_stopwords(['the', 'a', 'an', 'and', 'at', 'to', 'of', 'in', 'for', 'more', 'than'])
    WITH (frequency, position);

CREATE TABLE posts (id INTEGER PRIMARY KEY, body VARCHAR);

INSERT INTO posts VALUES
(1, 'Espresso starts at the grind. Grind finer to slow the shot, grind coarser to speed the shot.'),
(2, 'Dial the grind, pull the shot, read the crema. A tight grind pulls a rich shot.'),
(3, 'Fresh beans need a fresh grind. Grind the beans and pull a clean shot.'),
(4, 'The grinder matters more than the machine. Dose, grind, tamp, pull: the grind rules the shot.');

CREATE INDEX posts_idx ON posts USING inverted (id, body tx);

VACUUM (REFRESH_TABLE) posts;
```

</details>

## Rank terms by mentions

`ts_dict_freq` is the total number of times a term occurs across the corpus, aligned with `ts_dict_agg`. Order by it and the cloud falls out, biggest word first.

```sql
SELECT unnest(ts_dict_agg(body))  AS term,
       unnest(ts_dict_freq(body)) AS mentions
FROM posts_idx
ORDER BY mentions DESC, term;
-- result:
term	mentions
grind	9
shot	6
pull	3
beans	2
fresh	2
clean	1
coarser	1
crema	1
dial	1
dose	1
espresso	1
finer	1
grinder	1
machine	1
matters	1
need	1
pulls	1
read	1
rich	1
rules	1
slow	1
speed	1
starts	1
tamp	1
tight	1
```

## Mentions is not documents

Watch the gap between [`ts_dict_count`](../../sql/functions/search/term-dictionary.md) and `ts_dict_freq`. Count is how many documents hold the term, frequency is how many times it shows up in total. `grind` and `shot` both land in all four posts, so their document counts tie, but `grind` gets written far more often and frequency pulls it clear ahead. `beans` and `fresh` go the other way with two mentions packed inside a single post.

```sql
SELECT unnest(ts_dict_agg(body))   AS term,
       unnest(ts_dict_count(body))  AS docs,
       unnest(ts_dict_freq(body))   AS mentions
FROM posts_idx
ORDER BY mentions DESC, term;
-- result:
term	docs	mentions
grind	4	9
shot	4	6
pull	3	3
beans	1	2
fresh	1	2
clean	1	1
coarser	1	1
crema	1	1
dial	1	1
dose	1	1
espresso	1	1
finer	1	1
grinder	1	1
machine	1	1
matters	1	1
need	1	1
pulls	1	1
read	1	1
rich	1	1
rules	1	1
slow	1	1
speed	1	1
starts	1	1
tamp	1	1
tight	1	1
```

Reach for count when presence is the question (how many posts mention grinding) and frequency when volume is (how loud a word is across the corpus).

## Cap it at the top terms

A cloud only shows the headline terms, so `LIMIT` the ranked list to the size of your widget.

```sql
SELECT unnest(ts_dict_agg(body))  AS term,
       unnest(ts_dict_freq(body)) AS mentions
FROM posts_idx
ORDER BY mentions DESC, term
LIMIT 2;
-- result:
term	mentions
grind	9
shot	6
```

## See also

- [Term Dictionary](../../sql/functions/search/term-dictionary.md): the full `ts_dict_*` reference, including how `ts_dict_freq` counts under deletes before compaction
- [Faceted Search](./faceted-search.md): count documents behind each value rather than rank the vocabulary
- [Autocomplete](./autocomplete.md): rank a prefix match by popularity from the same dictionary

