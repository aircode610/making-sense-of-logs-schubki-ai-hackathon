---
title: One Search Box
sidebar_position: 11
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# One Search Box

A single input that searches everything is the most common search UI there is, and it does not need one `@@` predicate per column. Declare a catch-all column as `GENERATED ALWAYS AS (concat_ws(...)) STORED`, index it, and point the search box at that one field. The table keeps the column in sync on every write, so the index never drifts from the source columns — unlike a concatenation you materialize by hand at load time.

`concat_ws` skips NULLs, so optional columns cost nothing to include.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY osb_en AS
    split_text(case := 'lower') | normalize_tokens('en_US.UTF-8', accent := false)
    WITH (frequency, position);

CREATE TABLE machines (
    id INTEGER PRIMARY KEY,
    name VARCHAR,
    brand VARCHAR,
    owner VARCHAR,
    notes VARCHAR,
    all_text VARCHAR GENERATED ALWAYS AS
        (concat_ws(' ', name, brand, owner, notes)) STORED
);

CREATE INDEX machines_idx ON machines
    USING inverted (id, name osb_en, all_text osb_en);

INSERT INTO machines (id, name, brand, owner, notes) VALUES
  (1, '826 Vario', 'Fendt', 'Aerts Wouter', 'front loader fitted'),
  (2, 'Axion 850', 'Claas', 'Desmeth', 'annual service due'),
  (3, 'D254 SW', 'Giant', 'Wouter Thys', NULL),
  (4, '714', 'Fendt', 'Beel', 'gearbox rebuilt');

VACUUM (REFRESH_TABLE) machines;
```

</details>

## Search everything with one predicate

A bare multi-token string matches any of its tokens (`OR` semantics) and [BM25](../../sql/functions/search/scoring.md) sums the per-term contributions, so rows matching more of the query rank first: the machine that matches both `wouter` and `fendt` beats the rows matching one term each.

```sql
SELECT id, name, owner FROM machines_idx
WHERE all_text @@ 'wouter fendt'
ORDER BY BM25(machines_idx.tableoid) DESC, id;
-- result:
id	name	owner
1	826 Vario	Aerts Wouter
3	D254 SW	Wouter Thys
4	714	Beel
```

## Keep a boosted field for precision

Index an important column separately alongside the catch-all and [boost](boosting.md) it, so matches on the record's own name outrank matches buried in the long field.

```sql
SELECT id, name, owner FROM machines_idx
WHERE name @@ ('vario'::tsquery ^ 2.0) OR all_text @@ 'vario'
ORDER BY BM25(machines_idx.tableoid) DESC, id;
-- result:
id	name	owner
1	826 Vario	Aerts Wouter
```

## Updates stay searchable

Because the catch-all is a stored generated column, an `UPDATE` to any source column recomputes it and the index follows — no reindex step, no drift.

```sql
UPDATE machines SET owner = 'Vandamme' WHERE id = 3;

VACUUM (REFRESH_TABLE) machines;

SELECT id, name, owner FROM machines_idx
WHERE all_text @@ 'wouter'
ORDER BY BM25(machines_idx.tableoid) DESC, id;
-- result:
id	name	owner
1	826 Vario	Aerts Wouter
```

## Related

- [Computed Values](computed-values.md) — expression indexes and generated columns in general.
- [Boosting](boosting.md) — weighting one field over another.
- [Ranking](ranking.md) — scoring and ordering the merged result.

