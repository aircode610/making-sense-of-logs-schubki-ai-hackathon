---
title: Time Functions
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

<!-- markdownlint-disable MD001 -->

This section describes functions and operators for examining and manipulating [`TIME` values](../../sql/data_types/time.md).

## Time Operators

The table below shows the available mathematical operators for `TIME` types.

| Operator | Description                  | Example                             | Result     |
| :------- | :--------------------------- | :---------------------------------- | :--------- |
| `+`      | addition of an `INTERVAL`    | `TIME '01:02:03' + INTERVAL 5 HOUR` | `06:02:03` |
| `-`      | subtraction of an `INTERVAL` | `TIME '06:02:03' - INTERVAL 5 HOUR` | `01:02:03` |

## Time Functions

The table below shows the available scalar functions for `TIME` types.

| Name                                                                      | Description                                                                                                                                                           |
| :------------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`date_diff(part, starttime, endtime)`](#date_diffpart-starttime-endtime) | The number of [`part`](../../sql/functions/datepart.md) boundaries between `starttime` and `endtime`, inclusive of the larger time and exclusive of the smaller time. |
| [`date_part(part, time)`](#date_partpart-time)                            | Get [subfield](../../sql/functions/datepart.md) (equivalent to `extract`).                                                                                            |
| [`date_sub(part, starttime, endtime)`](#date_subpart-starttime-endtime)   | The signed length of the interval between `starttime` and `endtime`, truncated to whole multiples of [`part`](../../sql/functions/datepart.md).                       |
| [`extract(part FROM time)`](#extractpart-from-time)                       | Get subfield from a time.                                                                                                                                             |
| `get_current_time()`                                 | Current time (start of current transaction).                                                                                                                          |
| [`make_time(bigint, bigint, double)`](#make_timebigint-bigint-double)     | The time for the given parts.                                                                                                                                         |

The only [date parts](../../sql/functions/datepart.md) that are defined for times are `epoch`, `hours`, `minutes`, `seconds`, `milliseconds` and `microseconds`.

#### `date_diff(part, starttime, endtime)`

The number of [`part`](../../sql/functions/datepart.md) boundaries between `starttime` and `endtime`, inclusive of the larger time and exclusive of the smaller time. Alias: `datediff`.

```sql
SELECT date_diff('hour', TIME '01:02:03', TIME '06:01:03') AS date_diff;
-- result:
date_diff
5
```

#### `date_part(part, time)`

Get [subfield](../../sql/functions/datepart.md) (equivalent to `extract`). Alias: `datepart`.

```sql
SELECT date_part('minute', TIME '14:21:13') AS date_part;
-- result:
date_part
21
```

#### `date_sub(part, starttime, endtime)`

The signed length of the interval between `starttime` and `endtime`, truncated to whole multiples of [`part`](../../sql/functions/datepart.md). Alias: `datesub`.

```sql
SELECT date_sub('hour', TIME '01:02:03', TIME '06:01:03') AS date_sub;
-- result:
date_sub
4
```

#### `extract(part FROM time)`

Get subfield from a time.

```sql
SELECT extract('hour' FROM TIME '14:21:13') AS extract;
-- result:
extract
14
```

#### `get_current_time()`

<div className="docs-table-properties">

| **Description** | Current time (start of current transaction) in the local time zone as `TIMETZ`. |
| :--- | :--- |
| **Example** | `get_current_time()` |
| **Result** | `06:09:59.988+2` |
| **Alias** | `current_time` (no parentheses necessary) |

</div>

#### `make_time(bigint, bigint, double)`

The time for the given parts.

```sql
SELECT make_time(13, 34, 27.123456) AS make_time;
-- result:
make_time
13:34:27.123456
```

