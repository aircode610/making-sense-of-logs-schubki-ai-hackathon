---
title: Match Several Terms
sidebar_position: 26
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Match Several Terms

Find rows that contain at least N of a set of M values, with the floor as a knob you turn. Reach for this "N of M" filter when a candidate needs most of a required skill set, a product needs most of a feature list or a document needs most of a keyword set. If you come from Elastic it is the [`terms_set`](../../sql/indexes/inverted/migrating-from-elasticsearch.md) query, and [`ts_any`](../../sql/functions/search/full-text.md#ts_any) is the function underneath.

Six candidates each list a handful of `skills` in a `VARCHAR[]` array. An array column indexes every element as an exact keyword on its own, so there is no dictionary to declare.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TABLE candidates (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    skills VARCHAR[] NOT NULL
);

INSERT INTO candidates VALUES
(1, 'Alice', ['java', 'sql', 'rust']),
(2, 'Bob',   ['java', 'sql', 'python']),
(3, 'Carol', ['java', 'rust', 'go']),
(4, 'Dave',  ['sql', 'python', 'go']),
(5, 'Erin',  ['java', 'sql', 'rust', 'go']),
(6, 'Frank', ['python', 'go']);

CREATE INDEX candidates_idx ON candidates
    USING inverted (id, name, skills);

VACUUM (REFRESH_TABLE) candidates;
```

</details>

## Require every skill

Pass the list length as the second argument to `ts_any` and every alternative must match. Here all three skills are required, so only candidates whose skill set covers `java`, `sql` and `rust` come back:

```sql
SELECT id, name, skills
FROM candidates_idx
WHERE skills @@ ts_any(['java', 'sql', 'rust'], 3)
ORDER BY id;
-- result:
id	name	skills
1	Alice	{java,sql,rust}
5	Erin	{java,sql,rust,go}
```

## Relax the floor to N of M

Lower the second argument to demand fewer of the alternatives. Dropping the floor to `2` keeps everyone who has any two of the three skills, which pulls in Bob and Carol alongside the full matches:

```sql
SELECT id, name, skills
FROM candidates_idx
WHERE skills @@ ts_any(['java', 'sql', 'rust'], 2)
ORDER BY id;
-- result:
id	name	skills
1	Alice	{java,sql,rust}
2	Bob	{java,sql,python}
3	Carol	{java,rust,go}
5	Erin	{java,sql,rust,go}
```

## Same filter as a boolean helper

`has_any_tokens` is sugar for the same query without the `@@` operator or an explicit list of sub-queries. It takes the column, the candidate values and the same minimum-match count, returning the identical rows:

```sql
SELECT id, name, skills
FROM candidates_idx
WHERE has_any_tokens(skills, ['java', 'sql', 'rust'], 2)
ORDER BY id;
-- result:
id	name	skills
1	Alice	{java,sql,rust}
2	Bob	{java,sql,python}
3	Carol	{java,rust,go}
5	Erin	{java,sql,rust,go}
```

## See also

- [Full-text functions](../../sql/functions/search/full-text.md): `ts_any`, `ts_all` and `has_any_tokens` in full
- [Exact Value Matching](./exact-value-matching.md): single-term and any-of filters on keyword columns
- [Faceted Search](./faceted-search.md): count and group the rows a terms filter returns
- [Migrating from Elasticsearch](../../sql/indexes/inverted/migrating-from-elasticsearch.md): the `terms_set` and `minimum_should_match` mapping

