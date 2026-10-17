---
title: Wildcard Search
sidebar_position: 4
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Wildcard Search

Search for partial matches using pattern wildcards. Useful when you need prefix, infix, suffix, or complex pattern matching on indexed terms.

See [Setup](./index.md#setup) for the shared dataset used in all examples.

## Wildcard characters

| Character | Meaning |
|---|---|
| `_` | Match any single character |
| `%` | Match zero or more characters |
| `\_` | Literal underscore |
| `\%` | Literal percent sign |

## Prefix matching

Find genres starting with `'sci'`:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_like('sci%')
ORDER BY id;
-- result:
id	title	genre
1	The Matrix	sci-fi
2	The Matrix Reloaded	sci-fi
3	The Matrix Revolutions	sci-fi
7	Star Trek: The Motion Picture	sci-fi
8	Alien	sci-fi
```

## Suffix matching

Find genres ending with `'dy'`:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_like('%dy')
ORDER BY id;
-- result:
id	title	genre
6	Scary Movie	comedy
10	The Grand Budapest Hotel	comedy
```

## Infix matching

Find genres containing `'vent'`:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_like('%vent%')
ORDER BY id;
-- result:
id	title	genre
4	Jurassic Park	adventure
```

## Single character wildcard

Match genres with exactly one character between `'co'` and `'edy'`:

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_like('co_edy')
ORDER BY id;
-- result:
id	title	genre
6	Scary Movie	comedy
10	The Grand Budapest Hotel	comedy
```

## Complex patterns

Combine wildcards for more specific matching. Find words matching `'h_____'` (h + exactly 5 characters):

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_like('h_____')
ORDER BY id;
-- result:
id	title
1	The Matrix
9	Café Society
```

## Wildcard on text fields

Search for tokens matching a pattern within full-text columns:

```sql
SELECT id, title
FROM movies_idx
WHERE description @@ ts_like('block%')
ORDER BY id;
-- result:
id	title
4	Jurassic Park
6	Scary Movie
```

## Combine with other search functions

```sql
SELECT id, title, genre
FROM movies_idx
WHERE genre @@ ts_like('sci%') AND description @@ ts_phrase('alien')
ORDER BY id;
-- result:
id	title	genre
7	Star Trek: The Motion Picture	sci-fi
```

## See also

- [Exact Value Matching](./exact-value-matching.md) — exact term matching with the `@@` operator
- [Phrase and Proximity Search](./phrase-and-proximity-search.md) — ordered token matching

