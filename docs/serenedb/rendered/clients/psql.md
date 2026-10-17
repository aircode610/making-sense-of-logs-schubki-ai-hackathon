---
title: psql
sidebar_position: 8
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# psql

[psql](https://www.postgresql.org/docs/current/app-psql.html) is PostgreSQL's interactive terminal client. It works directly with SereneDB.

## Connect

```sh
psql -h localhost -p 7890
```

## Useful commands

| Command | Description |
|---|---|
| `\l` | List databases |
| `\d` | List tables |
| `\d table_name` | Describe a table |
| `\d+` | List tables with sizes |
| `\i file.sql` | Execute a SQL file |
| `\timing` | Toggle query timing |
| `\q` | Quit |

## Running queries

Run any SQL statement at the prompt and terminate it with a semicolon:

```sql
SELECT title, rating FROM movies WHERE year > 2015 ORDER BY rating DESC LIMIT 5;
-- result:
title	rating
Intro to Search	9.5
Scaling Analytics	8.1
The Last Index	7.7
```

## Importing CSV

Use the server-side `COPY ... FROM` statement to load a CSV file into an existing table:

```sql
COPY movies FROM 'movies.csv' WITH (FORMAT CSV, HEADER TRUE);
```

## Tips

- Use **Tab** to auto-complete table and column names
- Press **Ctrl+R** to search command history
- Use `\timing` to benchmark queries

