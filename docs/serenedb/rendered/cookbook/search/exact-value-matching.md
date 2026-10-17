---
title: Exact Value Matching
sidebar_position: 1
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Exact Value Matching

Match precise token values in indexed columns. This is the simplest form of search — find documents that contain an exact term.

See [Setup](./index.md#setup) for the shared dataset used in all examples.

## Match a single value

Match a single exact token with the `@@` operator and a bare term:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ 'sci-fi'
ORDER BY id;
-- result:
id	title	genre
1	The Matrix	sci-fi
2	The Matrix Reloaded	sci-fi
3	The Matrix Revolutions	sci-fi
7	Star Trek: The Motion Picture	sci-fi
8	Alien	sci-fi
```

## Match multiple alternatives

Use `ts_any` to match any of several values — more efficient than chaining `OR`:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_any(['comedy', 'drama'])
ORDER BY id;
-- result:
id	title	genre
6	Scary Movie	comedy
9	Café Society	drama
10	The Grand Budapest Hotel	comedy
```

## Negation

Combine `NOT` with term operations to exclude matches:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE NOT (genre @@ 'sci-fi')
ORDER BY id;
-- result:
id	title	genre
4	Jurassic Park	adventure
5	Harry Potter and the Order of the Phoenix	fantasy
6	Scary Movie	comedy
9	Café Society	drama
10	The Grand Budapest Hotel	comedy
```

## Combine with phrase search

Search for an exact genre and a phrase in the description:

```sql
SELECT id, title
FROM movies_idx
WHERE genre @@ 'sci-fi' AND description @@ ts_phrase('alien spacecraft')
ORDER BY id;
-- result:
id	title
7	Star Trek: The Motion Picture
```

## Combine with analytics

Search and aggregate in the same query:

```sql
SELECT genre, COUNT(*) AS count, AVG(runtime) AS avg_runtime
FROM movies_idx
WHERE description @@ ts_phrase('biggest blockbuster')
GROUP BY genre
ORDER BY genre;
-- result:
genre	count	avg_runtime
adventure	1	127
comedy	1	88
```

## See also

- [Range Queries](./range-queries.md) — compare terms with `>`, `<`, `>=`, `<=`
- [Inverted index query functions](../../sql/statements/create_index/index.md) — `@@`, `ts_any` and more

