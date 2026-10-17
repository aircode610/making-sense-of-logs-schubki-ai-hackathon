---
title: Recency and Decay
sidebar_position: 13
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Recency and Decay

Fresh content and popular content both deserve a say in the final order, but neither should steamroll relevance. Because [BM25](../../sql/functions/search/scoring.md) is a plain number you can do arithmetic on, you express both as ordinary SQL in the `ORDER BY`: a time-decay factor that fades a document as it ages and a saturating factor that rewards popularity with diminishing returns. The `gauss`/`exp` decay and `rank_feature` saturation you would reach for in Elastic are both plain arithmetic here, no DSL.

Four articles cover the same topic, each tagged with an `age_days` and a `popularity`. The queries pull back `id` and `title` alone, so a signal earns its place by moving a row up the page, not by printing a score beside it.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY d2 AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE articles (id INTEGER PRIMARY KEY, title VARCHAR, body VARCHAR, age_days INTEGER, popularity DOUBLE);

CREATE INDEX articles_idx ON articles USING inverted (id, title d2, body d2);

INSERT INTO articles VALUES
(1, 'kubernetes networking guide', 'a practical kubernetes guide covering kubernetes networking and kubernetes cluster internals', 90, 220.0),
(2, 'kubernetes storage guide', 'a practical kubernetes guide covering kubernetes storage and volume internals', 1, 180.0),
(3, 'platform notes', 'we run kubernetes in production and the whole team leans on kubernetes every day', 20, 5.0),
(4, 'yearly retro', 'a few scattered notes on kubernetes and several other tools we tried last year', 200, 400.0);

VACUUM (REFRESH_TABLE) articles;
```

</details>

## Baseline relevance

Start with pure relevance so you can see what the signals change. Every article mentions "kubernetes" and the one that mentions it most, in the shortest field, ranks first.

```sql
SELECT id, title FROM articles_idx WHERE title @@ 'kubernetes' OR body @@ 'kubernetes' ORDER BY BM25(articles_idx.tableoid) DESC, id;
-- result:
id	title
1	kubernetes networking guide
2	kubernetes storage guide
3	platform notes
4	yearly retro
```

## Fade older documents with a decay factor

Multiply the score by `1.0 / (1 + age_days)` and a document loses ground as it ages. The storage guide is a touch less relevant than the networking guide but it is one day old against ninety, so it climbs past it to the top. The stale-but-relevant article slips to second without falling off the page. Swap in `exp(-age_days / 30.0)` for a gentler curve with a half-life instead of a hard hyperbola.

```sql
SELECT id, title, age_days FROM articles_idx WHERE title @@ 'kubernetes' OR body @@ 'kubernetes' ORDER BY BM25(articles_idx.tableoid) * (1.0 / (1 + age_days)) DESC, id;
-- result:
id	title	age_days
2	kubernetes storage guide	1
1	kubernetes networking guide	90
3	platform notes	20
4	yearly retro	200
```

## Reward popularity with a saturating curve

A linear popularity multiply lets one runaway hit dominate everything. Multiply by `popularity / (popularity + 10)` instead and the factor rises steeply for the first few points then flattens toward 1, so extra popularity beyond the knee barely moves the needle. Here the year-end retro is the least relevant article but it is the most read, so it overtakes the low-traffic platform notes. Notice that neither low-relevance article reaches the top pair: because the multiplier is capped at 1, popularity refines the order inside a relevance tier rather than buying a way past it. The `10` sets the pivot where the boost hits half strength, the knob Elastic exposes as `k` on a `saturation` feature.

```sql
SELECT id, title FROM articles_idx WHERE title @@ 'kubernetes' OR body @@ 'kubernetes' ORDER BY BM25(articles_idx.tableoid) * (popularity / (popularity + 10)) DESC, id;
-- result:
id	title
1	kubernetes networking guide
2	kubernetes storage guide
4	yearly retro
3	platform notes
```

## See also

- [Relevance Tuning](./boosting.md): the boost operator and folding a business signal into the score
- [BM25/TFIDF Ranking](./ranking.md): scoring functions and their `k1` and `b` parameters
- [Scoring reference](../../sql/functions/search/scoring.md): the `BM25` and `TFIDF` signatures

