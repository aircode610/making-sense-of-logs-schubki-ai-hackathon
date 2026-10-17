---
layout: docu
redirect_from:
    - /docs/preview/guides/sql_features/timestamps
    - /docs/stable/guides/sql_features/timestamps
title: Timestamp Issues
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

## Timestamp with Time Zone Promotion Casts

Working with time zones in SQL can be quite confusing at times.
For example, when filtering to a date range, one might try the following query:

```sql
SET timezone = 'America/Los_Angeles';

CREATE OR REPLACE TABLE times AS
    FROM range('2025-08-30'::TIMESTAMPTZ, '2025-08-31'::TIMESTAMPTZ, INTERVAL 1 HOUR) tbl(t);

SELECT count(*) AS matching_rows
FROM times
WHERE t <= '2025-08-30';
-- result:
matching_rows
1
```

But if you change to another time zone, the results of the query change:

```sql
SET timezone = 'HST';

SELECT count(*) AS matching_rows
FROM times
WHERE t <= '2025-08-30';
-- result:
matching_rows
4
```

Or worse:

```sql
SET timezone = 'America/New_York';

SELECT count(*) AS matching_rows
FROM times
WHERE t <= '2025-08-30';
-- result:
matching_rows
0
```

These confusing results are due to the SQL casting rules from `DATE` to `TIMESTAMP WITH TIME ZONE`.
This cast is required to promote the date to midnight _in the current time zone_.

In general, unless you need to use the current time zone for display (or
other temporal binning operations)
you should use plain `TIMESTAMP`s for temporal data.
This will avoid confusing issues such as this, and the arithmetic operations are generally faster.

## Time Zone Performance

SereneDB's time zone support follows the rules of the _International Components for Unicode_
and carries the IANA time zone database, including daylight savings time past 2037.
(Note: Pandas gives incorrect results past that year).

Zoned binning and arithmetic (`date_trunc`, `date_part`, `strftime`, `time_bucket`, the casts,
`AT TIME ZONE`, interval arithmetic and `date_diff`, among others) read a per-zone table of the days
from 1900 to 2299 instead of running the calendar computation for every value.
A value outside that range, or on a day with several transitions, takes the per-value computation.

When the same bins are needed again and again, a calendar table for the timestamps being modeled still helps.
For example, if the application is modeling electrical supply and demand out to 2100 at hourly resolution,
one can create the calendar table like so:

```sql
CREATE OR REPLACE TABLE hourly AS
    SELECT
        ts,
        year::SMALLINT AS year,
        month::TINYINT AS month,
        day::TINYINT AS day,
        hour::TINYINT AS hour,
    FROM (
        SELECT ts, unnest(date_part(['year', 'month', 'day', 'hour'], ts))
        FROM generate_series(
            '2020-01-01'::DATE::TIMESTAMP,
            '2100-01-01'::DATE::TIMESTAMP,
            INTERVAL 1 HOUR) tbl(ts)
    ) parts;

SELECT count(*) AS rows FROM hourly;
-- result:
rows
701281
```

You can then join this ~700K row table against any timestamp column
to quickly obtain the temporal bin values for the time zone in question.
The inner casts are not required, but result in a smaller table
because `date_part` returns 64 bit integers for all parts.

Notice that we can extract _all_ of the parts with a single call to `date_part`.
This part list version of the function is faster than extracting the parts one by one
because the underlying binning computation computes all parts,
so picking out the ones in the list avoids computing the bins once per part.

Also notice that we are leveraging the `DATE` cast rules from the previous section
to bound the calendar to the model domain.

## Half-Open Intervals

Another subtle problem in using SQL for temporal analytics is the `BETWEEN` operator.
Temporal analytics almost always uses
[half-open binning intervals](https://www.cs.arizona.edu/~rts/tdbbook.pdf)
to avoid overlaps at the ends.
Unfortunately, the `BETWEEN` operator is a closed-closed interval:

```sql
SELECT
    TIMESTAMP '2025-08-31 00:00:00'
        BETWEEN TIMESTAMP '2025-08-30' AND TIMESTAMP '2025-08-31' AS between_closed,
    TIMESTAMP '2025-08-31 00:00:00' >= TIMESTAMP '2025-08-30'
        AND TIMESTAMP '2025-08-31 00:00:00' < TIMESTAMP '2025-08-31' AS half_open;
-- result:
between_closed	half_open
t	f
```

To avoid this problem, make sure you are explicit about comparison boundaries instead of using `BETWEEN`.

