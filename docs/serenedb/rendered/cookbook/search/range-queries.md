---
title: Range Queries
sidebar_position: 2
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Range Queries

Match terms that are above, below, or between reference values using lexicographic comparison. Useful for filtering categories, tags, or any indexed string values by order.

See [Setup](./index.md#setup) for the shared dataset used in all examples.

## Greater than

Find genres that come after `'drama'` lexicographically:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_gt('drama')
ORDER BY id;
-- result:
id	title	genre
1	The Matrix	sci-fi
2	The Matrix Reloaded	sci-fi
3	The Matrix Revolutions	sci-fi
5	Harry Potter and the Order of the Phoenix	fantasy
7	Star Trek: The Motion Picture	sci-fi
8	Alien	sci-fi
```

## Less than or equal

Find genres up to and including `'comedy'`:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_le('comedy')
ORDER BY id;
-- result:
id	title	genre
4	Jurassic Park	adventure
6	Scary Movie	comedy
10	The Grand Budapest Hotel	comedy
```

## Combining range conditions

Use `AND` to define a range:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_ge('comedy') AND genre @@ ts_le('fantasy')
ORDER BY genre, id;
-- result:
id	title	genre
6	Scary Movie	comedy
10	The Grand Budapest Hotel	comedy
9	Café Society	drama
5	Harry Potter and the Order of the Phoenix	fantasy
```

## Negation with range

Find everything outside a range:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE NOT (genre @@ ts_le('drama'))
ORDER BY id;
-- result:
id	title	genre
1	The Matrix	sci-fi
2	The Matrix Reloaded	sci-fi
3	The Matrix Revolutions	sci-fi
5	Harry Potter and the Order of the Phoenix	fantasy
7	Star Trek: The Motion Picture	sci-fi
8	Alien	sci-fi
```

## Combine with phrase search

Range query on genre plus full-text search on description:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_ge('sci-fi') AND description @@ ts_phrase('galaxy')
ORDER BY id;
-- result:
id	title	genre
7	Star Trek: The Motion Picture	sci-fi
8	Alien	sci-fi
```

## See also

- [Exact Value Matching](./exact-value-matching.md) — equality and IN queries
- [Wildcard Search](./wildcard-search.md) — pattern matching

