---
title: Timestamp Functions
split: headings
---

import DocCallout from "@site/src/components/DocCallout";
import SqlLogicTest from "@site/src/components/SqlLogicTest";

<!-- markdownlint-disable MD001 -->

This section describes functions and operators for examining and manipulating [`TIMESTAMP` values](../../sql/data_types/timestamp.md).
See also the related [`TIMESTAMPTZ` functions](../../sql/functions/timestamptz.md).

## Timestamp Operators

The table below shows the available mathematical operators for `TIMESTAMP` types.

| Operator | Description                  | Example                                            | Result                |
| :------- | :--------------------------- | :------------------------------------------------- | :-------------------- |
| `+`      | addition of an `INTERVAL`    | `TIMESTAMP '1992-03-22 01:02:03' + INTERVAL 5 DAY` | `1992-03-27 01:02:03` |
| `-`      | subtraction of `TIMESTAMP`s  | `TIMESTAMP '1992-03-27' - TIMESTAMP '1992-03-22'`  | `5 days`              |
| `-`      | subtraction of an `INTERVAL` | `TIMESTAMP '1992-03-27 01:02:03' - INTERVAL 5 DAY` | `1992-03-22 01:02:03` |

Adding to or subtracting from [infinite values](../../sql/data_types/timestamp.md#special-values) produces the same infinite value.

## Scalar Timestamp Functions

The table below shows the available scalar functions for `TIMESTAMP` values.

| Name                                                                                                                         | Description                                                                                                                                                                                                                                                                 |
| :--------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`age(timestamp, timestamp)`](#agetimestamp-timestamp)                                                                       | Subtract arguments, resulting in the time difference between the two timestamps.                                                                                                                                                                                            |
| `age(timestamp)`                                                                                            | Subtract from current_date.                                                                                                                                                                                                                                                 |
| `ago(interval)`                                                                                              | Subtracts an interval from the current timestamp.                                                                                                                                                                                                                           |
| [`century(timestamp)`](#centurytimestamp)                                                                                    | Extracts the century of a timestamp.                                                                                                                                                                                                                                        |
| `current_localtimestamp()`                                                                        | Returns the current timestamp (at the start of the transaction).                                                                                                                                                                                                            |
| [`date_diff(part, starttimestamp, endtimestamp)`](#date_diffpart-starttimestamp-endtimestamp)                                | The number of [`part`](../../sql/functions/datepart.md) boundaries between `starttimestamp` and `endtimestamp`, inclusive of the larger timestamp and exclusive of the smaller timestamp.                                                                                   |
| [`date_part([part, ...], timestamp)`](#date_partpart--timestamp)                                                             | Get the listed [subfields](../../sql/functions/datepart.md) as a `struct`. The list must be constant.                                                                                                                                                                       |
| [`date_part(part, timestamp)`](#date_partpart-timestamp)                                                                     | Get [subfield](../../sql/functions/datepart.md) (equivalent to `extract`).                                                                                                                                                                                                  |
| [`date_sub(part, starttimestamp, endtimestamp)`](#date_subpart-starttimestamp-endtimestamp)                                  | The signed length of the interval between `starttimestamp` and `endtimestamp`, truncated to whole multiples of [`part`](../../sql/functions/datepart.md).                                                                                                                   |
| [`date_trunc(part, timestamp)`](#date_truncpart-timestamp)                                                                   | Truncate to specified [precision](../../sql/functions/datepart.md).                                                                                                                                                                                                         |
| [`dayname(timestamp)`](#daynametimestamp)                                                                                    | The (English) name of the weekday.                                                                                                                                                                                                                                          |
| [`epoch_ms(timestamp)`](#epoch_mstimestamp)                                                                                  | Returns the total number of milliseconds since the epoch.                                                                                                                                                                                                                   |
| [`epoch_ns(timestamp)`](#epoch_nstimestamp)                                                                                  | Returns the total number of nanoseconds since the epoch.                                                                                                                                                                                                                    |
| [`epoch_us(timestamp)`](#epoch_ustimestamp)                                                                                  | Returns the total number of microseconds since the epoch.                                                                                                                                                                                                                   |
| [`epoch(timestamp)`](#epochtimestamp)                                                                                        | Returns the total number of seconds since the epoch.                                                                                                                                                                                                                        |
| [`extract(field FROM timestamp)`](#extractfield-from-timestamp)                                                              | Get [subfield](../../sql/functions/datepart.md) from a timestamp.                                                                                                                                                                                                           |
| [`greatest(timestamp, timestamp)`](#greatesttimestamp-timestamp)                                                             | The later of two timestamps.                                                                                                                                                                                                                                                |
| [`isfinite(timestamp)`](#isfinitetimestamp)                                                                                  | Returns true if the timestamp is finite, false otherwise.                                                                                                                                                                                                                   |
| [`isinf(timestamp)`](#isinftimestamp)                                                                                        | Returns true if the timestamp is infinite, false otherwise.                                                                                                                                                                                                                 |
| [`julian(timestamp)`](#juliantimestamp)                                                                                      | Extract the Julian Day number from a timestamp.                                                                                                                                                                                                                             |
| [`last_day(timestamp)`](#last_daytimestamp)                                                                                  | The last day of the month.                                                                                                                                                                                                                                                  |
| [`least(timestamp, timestamp)`](#leasttimestamp-timestamp)                                                                   | The earlier of two timestamps.                                                                                                                                                                                                                                              |
| [`make_timestamp(bigint, bigint, bigint, bigint, bigint, double)`](#make_timestampbigint-bigint-bigint-bigint-bigint-double) | The timestamp for the given parts.                                                                                                                                                                                                                                          |
| [`make_timestamp(microseconds)`](#make_timestampmicroseconds)                                                                | Converts microseconds since the epoch to a timestamp.                                                                                                                                                                                                                       |
| [`make_timestamp_ms(milliseconds)`](#make_timestamp_msmilliseconds)                                                          | Converts milliseconds since the epoch to a timestamp.                                                                                                                                                                                                                       |
| [`make_timestamp_ns(nanoseconds)`](#make_timestamp_nsnanoseconds)                                                            | Converts nanoseconds since the epoch to a timestamp.                                                                                                                                                                                                                        |
| [`monthname(timestamp)`](#monthnametimestamp)                                                                                | The (English) name of the month.                                                                                                                                                                                                                                            |
| [`strftime(timestamp, format)`](#strftimetimestamp-format)                                                                   | Converts timestamp to string according to the [format string](../../sql/functions/dateformat.md#format-specifiers).                                                                                                                                                         |
| [`strptime(text, format-list)`](#strptimetext-format-list)                                                                   | Converts the string `text` to timestamp applying the [format strings](../../sql/functions/dateformat.md) in the list until one succeeds. Throws an error on failure. To return `NULL` on failure, use [`try_strptime`](#try_strptimetext-format-list).                      |
| [`strptime(text, format)`](#strptimetext-format)                                                                             | Converts the string `text` to timestamp according to the [format string](../../sql/functions/dateformat.md#format-specifiers). Throws an error on failure. To return `NULL` on failure, use [`try_strptime`](#try_strptimetext-format).                                     |
| [`time_bucket(bucket_width, timestamp[, offset])`](#time_bucketbucket_width-timestamp-offset)                                | Truncate `timestamp` to a grid of width `bucket_width`. The grid is anchored at `2000-01-01 00:00:00[ + offset]` when `bucket_width` is a number of months or coarser units, else `2000-01-03 00:00:00[ + offset]`. Note that `2000-01-03` is a Monday.                     |
| [`time_bucket(bucket_width, timestamp[, origin])`](#time_bucketbucket_width-timestamp-origin)                                | Truncate `timestamp` to a grid of width `bucket_width`. The grid is anchored at the `origin` timestamp, which defaults to `2000-01-01 00:00:00` when `bucket_width` is a number of months or coarser units, else `2000-01-03 00:00:00`. Note that `2000-01-03` is a Monday. |
| [`try_strptime(text, format-list)`](#try_strptimetext-format-list)                                                           | Converts the string `text` to timestamp applying the [format strings](../../sql/functions/dateformat.md) in the list until one succeeds. Returns `NULL` on failure.                                                                                                         |
| [`try_strptime(text, format)`](#try_strptimetext-format)                                                                     | Converts the string `text` to timestamp according to the [format string](../../sql/functions/dateformat.md#format-specifiers). Returns `NULL` on failure.                                                                                                                   |

There are also dedicated extraction functions to get the [subfields](../../sql/functions/datepart.md).

Functions applied to infinite dates will either return the same infinite dates
(e.g., `greatest`) or `NULL` (e.g., `date_part`) depending on what “makes sense”.
In general, if the function needs to examine the parts of the infinite date, the result will be `NULL`.

#### `age(timestamp, timestamp)`

Subtract arguments, resulting in the time difference between the two timestamps.

```sql
SELECT age(TIMESTAMP '2001-04-10', TIMESTAMP '1992-09-20') AS age;
-- result:
age
8 years 6 mons 20 days
```

#### `age(timestamp)`

<div className="docs-table-properties">

| **Description** | Subtract from current_date. |
| :--- | :--- |
| **Example** | `age(TIMESTAMP '1992-09-20')` |
| **Result** | `29 years 1 month 27 days 12:39:00.844` |

</div>

#### `ago(interval)`

<div className="docs-table-properties">

| **Description** | Subtracts an interval from the current timestamp, returning a timestamp in the past. Equivalent to `current_timestamp - interval`. |
| :--- | :--- |
| **Example** | `ago(INTERVAL 1 HOUR)` |
| **Result** | `2024-11-30 12:28:48.895` (if current time is `2024-11-30 13:28:48.895`) |

</div>

#### `century(timestamp)`

Extracts the century of a timestamp.

```sql
SELECT century(TIMESTAMP '1992-03-22') AS century;
-- result:
century
20
```

#### `current_localtimestamp()`

<div className="docs-table-properties">

| **Description** | Returns the current timestamp with time zone (at the start of the transaction). |
| :--- | :--- |
| **Example** | `current_localtimestamp()` |
| **Result** | `2024-11-30 13:28:48.895` |

</div>

#### `date_diff(part, starttimestamp, endtimestamp)`

The signed number of [`part`](../../sql/functions/datepart.md) boundaries between `starttimestamp` and `endtimestamp`, inclusive of the larger timestamp and exclusive of the smaller timestamp.

```sql
SELECT date_diff('hour', TIMESTAMP '1992-09-30 23:59:59', TIMESTAMP '1992-10-01 01:58:00') AS diff;
-- result:
diff
2
```

#### `date_part([part, ...], timestamp)`

Get the listed [subfields](../../sql/functions/datepart.md) as a `struct`. The list must be constant.

```sql
SELECT date_part(['year', 'month', 'day'], TIMESTAMP '1992-09-20 20:38:40') AS parts;
-- result:
parts
(1992,9,20)
```

#### `date_part(part, timestamp)`

Get [subfield](../../sql/functions/datepart.md) (equivalent to `extract`).

```sql
SELECT date_part('minute', TIMESTAMP '1992-09-20 20:38:40') AS minute;
-- result:
minute
38
```

#### `date_sub(part, starttimestamp, endtimestamp)`

The signed length of the interval between `starttimestamp` and `endtimestamp`, truncated to whole multiples of [`part`](../../sql/functions/datepart.md).

```sql
SELECT date_sub('hour', TIMESTAMP '1992-09-30 23:59:59', TIMESTAMP '1992-10-01 01:58:00') AS sub;
-- result:
sub
1
```

#### `date_trunc(part, timestamp)`

Truncate to specified [precision](../../sql/functions/datepart.md).

```sql
SELECT date_trunc('hour', TIMESTAMP '1992-09-20 20:38:40') AS truncated;
-- result:
truncated
1992-09-20 20:00:00
```

#### `dayname(timestamp)`

The (English) name of the weekday.

```sql
SELECT dayname(TIMESTAMP '1992-03-22') AS dayname;
-- result:
dayname
Sunday
```

#### `epoch_ms(timestamp)`

Returns the total number of milliseconds since the epoch.

```sql
SELECT epoch_ms(TIMESTAMP '2021-08-03 11:59:44.123456') AS ms;
-- result:
ms
1627991984123
```

#### `epoch_ns(timestamp)`

Returns the total number of nanoseconds since the epoch.

```sql
SELECT epoch_ns(TIMESTAMP '2021-08-03 11:59:44.123456') AS ns;
-- result:
ns
1627991984123456000
```

#### `epoch_us(timestamp)`

Returns the total number of microseconds since the epoch.

```sql
SELECT epoch_us(TIMESTAMP '2021-08-03 11:59:44.123456') AS us;
-- result:
us
1627991984123456
```

#### `epoch(timestamp)`

Returns the total number of seconds since the epoch.

```sql
SELECT epoch('2022-11-07 08:43:04'::TIMESTAMP) AS seconds;
-- result:
seconds
1667810584
```

#### `extract(field FROM timestamp)`

Get [subfield](../../sql/functions/datepart.md) from a timestamp.

```sql
SELECT extract('hour' FROM TIMESTAMP '1992-09-20 20:38:48') AS hour;
-- result:
hour
20
```

#### `greatest(timestamp, timestamp)`

The later of two timestamps.

```sql
SELECT greatest(TIMESTAMP '1992-09-20 20:38:48', TIMESTAMP '1992-03-22 01:02:03.1234') AS greatest;
-- result:
greatest
1992-09-20 20:38:48
```

#### `isfinite(timestamp)`

Returns true if the timestamp is finite, false otherwise.

```sql
SELECT isfinite(TIMESTAMP '1992-03-07') AS isfinite;
-- result:
isfinite
t
```

#### `isinf(timestamp)`

Returns true if the timestamp is infinite, false otherwise.

```sql
SELECT isinf(TIMESTAMP '-infinity') AS isinf;
-- result:
isinf
t
```

#### `julian(timestamp)`

Extract the Julian Day number from a timestamp.

```sql
SELECT julian(TIMESTAMP '1992-03-22 01:02:03.1234') AS julian;
-- result:
julian
2448704.043091706
```

#### `last_day(timestamp)`

The last day of the month.

```sql
SELECT last_day(TIMESTAMP '1992-03-22 01:02:03.1234') AS last_day;
-- result:
last_day
1992-03-31
```

#### `least(timestamp, timestamp)`

The earlier of two timestamps.

```sql
SELECT least(TIMESTAMP '1992-03-22 01:02:03', TIMESTAMP '1993-08-14 08:22:33') AS least;
-- result:
least
1992-03-22 01:02:03
```

#### `make_timestamp(bigint, bigint, bigint, bigint, bigint, double)`

The timestamp for the given parts.

```sql
SELECT make_timestamp(1992, 9, 20, 13, 34, 27.123456) AS ts;
-- result:
ts
1992-09-20 13:34:27.123456
```

#### `make_timestamp(microseconds)`

Converts microseconds since the epoch to a timestamp.

```sql
SELECT make_timestamp(1667810584123456) AS ts;
-- result:
ts
2022-11-07 08:43:04.123456
```

#### `make_timestamp_ms(milliseconds)`

Converts milliseconds since the epoch to a timestamp.

```sql
SELECT make_timestamp_ms(1667810584123) AS ts;
-- result:
ts
2022-11-07 08:43:04.123
```

#### `make_timestamp_ns(nanoseconds)`

Converts nanoseconds since the epoch to a timestamp.

```sql
skipif pg-wire-extended
SELECT make_timestamp_ns(1667810584123456789) AS ts;
-- result:
ts
2022-11-07 08:43:04.123456789
```

#### `monthname(timestamp)`

The (English) name of the month.

```sql
SELECT monthname(TIMESTAMP '1992-09-20') AS monthname;
-- result:
monthname
September
```

#### `strftime(timestamp, format)`

Converts timestamp to string according to the [format string](../../sql/functions/dateformat.md#format-specifiers).

```sql
SELECT strftime(TIMESTAMP '1992-01-01 20:38:40', '%a, %-d %B %Y - %I:%M:%S %p') AS formatted;
-- result:
formatted
Wed, 1 January 1992 - 08:38:40 PM
```

#### `strptime(text, format-list)`

Converts the string `text` to timestamp applying the [format strings](../../sql/functions/dateformat.md) in the list until one succeeds. Throws an error on failure. To return `NULL` on failure, use [`try_strptime`](#try_strptimetext-format-list).

```sql
SELECT strptime('4/15/2023 10:56:00', ['%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S']) AS ts;
-- result:
ts
2023-04-15 10:56:00
```

#### `strptime(text, format)`

Converts the string `text` to timestamp according to the [format string](../../sql/functions/dateformat.md#format-specifiers). Throws an error on failure. To return `NULL` on failure, use [`try_strptime`](#try_strptimetext-format).

```sql
SELECT strptime('Wed, 1 January 1992 - 08:38:40 PM', '%a, %-d %B %Y - %I:%M:%S %p') AS ts;
-- result:
ts
1992-01-01 20:38:40
```

#### `time_bucket(bucket_width, timestamp[, offset])`

Truncate `timestamp` to a grid of width `bucket_width`. The grid includes `2000-01-01 00:00:00[ + offset]` when `bucket_width` is a number of months or coarser units, else `2000-01-03 00:00:00[ + offset]`. Note that `2000-01-03` is a Monday.

```sql
SELECT time_bucket(INTERVAL '10 minutes', TIMESTAMP '1992-04-20 15:26:00-07', INTERVAL '5 minutes') AS bucket;
-- result:
bucket
1992-04-20 15:25:00
```

#### `time_bucket(bucket_width, timestamp[, origin])`

Truncate `timestamp` to a grid of width `bucket_width`. The grid includes the `origin` timestamp, which defaults to `2000-01-01 00:00:00` when `bucket_width` is a number of months or coarser units, else `2000-01-03 00:00:00`. Note that `2000-01-03` is a Monday.

```sql
SELECT time_bucket(INTERVAL '2 weeks', TIMESTAMP '1992-04-20 15:26:00', TIMESTAMP '1992-04-01 00:00:00') AS bucket;
-- result:
bucket
1992-04-15 00:00:00
```

#### `try_strptime(text, format-list)`

Converts the string `text` to timestamp applying the [format strings](../../sql/functions/dateformat.md) in the list until one succeeds. Returns `NULL` on failure.

```sql
SELECT try_strptime('4/15/2023 10:56:00', ['%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S']) AS ts;
-- result:
ts
2023-04-15 10:56:00
```

#### `try_strptime(text, format)`

Converts the string `text` to timestamp according to the [format string](../../sql/functions/dateformat.md#format-specifiers). Returns `NULL` on failure.

```sql
SELECT try_strptime('Wed, 1 January 1992 - 08:38:40 PM', '%a, %-d %B %Y - %I:%M:%S %p') AS ts;
-- result:
ts
1992-01-01 20:38:40
```

## Timestamp Table Functions

The table below shows the available table functions for `TIMESTAMP` types.

| Name                                                                                              | Description                                                                      |
| :------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------- |
| [`generate_series(timestamp, timestamp, interval)`](#generate_seriestimestamp-timestamp-interval) | Generate a table of timestamps in the closed range, stepping by the interval.    |
| [`range(timestamp, timestamp, interval)`](#rangetimestamp-timestamp-interval)                     | Generate a table of timestamps in the half open range, stepping by the interval. |

<DocCallout type="tip">

Infinite values are not allowed as table function bounds.

</DocCallout>

#### `generate_series(timestamp, timestamp, interval)`

Generate a table of timestamps in the closed range, stepping by the interval.

```sql
SELECT * FROM generate_series(TIMESTAMP '2001-04-10', TIMESTAMP '2001-04-11', INTERVAL 30 MINUTE) ORDER BY 1 LIMIT 3;
-- result:
generate_series
2001-04-10 00:00:00
2001-04-10 00:30:00
2001-04-10 01:00:00
```

#### `range(timestamp, timestamp, interval)`

Generate a table of timestamps in the half open range, stepping by the interval.

```sql
SELECT * FROM range(TIMESTAMP '2001-04-10', TIMESTAMP '2001-04-11', INTERVAL 30 MINUTE) ORDER BY 1 LIMIT 3;
-- result:
range
2001-04-10 00:00:00
2001-04-10 00:30:00
2001-04-10 01:00:00
```

