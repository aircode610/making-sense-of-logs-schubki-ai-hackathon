---
layout: docu
redirect_from:
- /docs/guides/meta/summarize
- /docs/preview/guides/meta/summarize
- /docs/stable/guides/meta/summarize
title: Summarize
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `SUMMARIZE` command can be used to easily compute a number of aggregates over a table or a query.
The `SUMMARIZE` command launches a query that computes a number of aggregates over all columns (`min`, `max`, `approx_unique`, `avg`, `std`, `q25`, `q50`, `q75`, `count`), and return these along the column name, column type, and the percentage of `NULL` values in the column.
Note that the quantiles and percentiles are **approximate values**.

## Usage

To summarize the contents of a table, use `SUMMARIZE` followed by the table name.

```sql
SUMMARIZE TABLE tbl;
-- result:
column_name	column_type	min	max	approx_unique	avg	std	q25	q50	q75	count	null_percentage
id	INTEGER	1	7	3	3.6666666666666665	3.055050463303893	2	3	6	3	0.00
name	VARCHAR	bookmark	other	3	NULL	NULL	NULL	NULL	NULL	3	0.00
col1	DOUBLE	1	9	3	4.666666666666667	4.041451884327381	1.75	4	7.75	3	0.00
col2	DOUBLE	2	16	3	7.666666666666667	7.371114795831994	2.75	5	13.25	3	0.00
Some Column Name	VARCHAR	alpha	gamma	3	NULL	NULL	NULL	NULL	NULL	3	0.00
i	INTEGER	1	3	3	2	1	1	2	3	3	0.00
a	INTEGER	10	12	3	11	1	10	11	12	3	0.00
b	INTEGER	20	22	3	21	1	20	21	22	3	0.00
c	INTEGER	30	32	3	31	1	30	31	32	3	0.00
number	INTEGER	10	20	2	15	7.0710678118654755	10	15	20	3	33.33
number1	INTEGER	100	300	3	200	100	125	200	275	3	0.00
number2	INTEGER	1000	3000	3	2000	1000	1250	2000	2750	3	0.00
```

To summarize a query, prepend `SUMMARIZE` to a query.

```sql
SUMMARIZE SELECT * FROM tbl;
```

## Example

Below is an example of `SUMMARIZE` on a sample `lineitem` table modeled on the TPC-H schema.

```sql
CREATE TABLE lineitem AS SELECT * FROM (VALUES
    (1, 155, 4, 1, 17.0, 21168.23, 0.04, 0.02, 'N', 'O', DATE '1996-03-13', DATE '1996-02-12', DATE '1996-03-22', 'DELIVER IN PERSON', 'TRUCK', 'to beans x-ray carefully'),
    (1, 67, 9, 2, 36.0, 45983.16, 0.09, 0.06, 'N', 'O', DATE '1996-04-12', DATE '1996-02-28', DATE '1996-04-20', 'TAKE BACK RETURN', 'MAIL', 'slyly bold pinto beans'),
    (2, 106, 5, 1, 38.0, 44694.46, 0.00, 0.05, 'N', 'O', DATE '1997-01-28', DATE '1997-01-14', DATE '1997-02-02', 'TAKE BACK RETURN', 'RAIL', 'requests against the'),
    (3, 4, 2, 1, 45.0, 54058.05, 0.06, 0.00, 'R', 'F', DATE '1994-02-02', DATE '1994-01-04', DATE '1994-02-23', 'NONE', 'AIR', 'pending foxes wake'),
    (3, 19, 8, 2, 49.0, 46796.47, 0.10, 0.00, 'R', 'F', DATE '1993-11-09', DATE '1993-12-20', DATE '1993-11-24', 'TAKE BACK RETURN', 'RAIL', 'sleep quickly bold pinto beans')
) AS t(l_orderkey, l_partkey, l_suppkey, l_linenumber, l_quantity, l_extendedprice, l_discount, l_tax, l_returnflag, l_linestatus, l_shipdate, l_commitdate, l_receiptdate, l_shipinstruct, l_shipmode, l_comment);
```

```sql
SUMMARIZE lineitem;
-- result:
column_name	column_type	min	max	approx_unique	avg	std	q25	q50	q75	count	null_percentage
l_orderkey	INTEGER	1	3	3	2	1	1	2	3	5	0.00
l_partkey	INTEGER	4	155	5	70.2	62.22298610642212	15	67	118	5	0.00
l_suppkey	INTEGER	2	9	5	5.6	2.8809720581775866	4	5	8	5	0.00
l_linenumber	INTEGER	1	2	2	1.4	0.5477225575051662	1	1	2	5	0.00
l_quantity	DECIMAL(3,1)	17.0	49.0	5	37	12.349089035228468	31	38	46	5	0.00
l_extendedprice	DECIMAL(7,2)	21168.23	54058.05	5	42540.074	12490.322396220607	38812	45983	48612	5	0.00
l_discount	DECIMAL(3,2)	0.00	0.10	5	0.057999999999999996	0.04024922359499621	0	0	0	5	0.00
l_tax	DECIMAL(3,2)	0.00	0.06	4	0.026000000000000002	0.027928480087537882	0	0	0	5	0.00
l_returnflag	VARCHAR	N	R	2	NULL	NULL	NULL	NULL	NULL	5	0.00
l_linestatus	VARCHAR	F	O	2	NULL	NULL	NULL	NULL	NULL	5	0.00
l_shipdate	DATE	1993-11-09	1997-01-28	5	1995-07-02 04:48:00	NULL	1994-01-12	1996-03-13	1996-06-24	5	0.00
l_commitdate	DATE	1993-12-20	1997-01-14	5	1995-06-17 00:00:00	NULL	1993-12-31	1996-02-12	1996-05-18	5	0.00
l_receiptdate	DATE	1993-11-24	1997-02-02	5	1995-07-13 19:12:00	NULL	1994-01-31	1996-03-22	1996-07-01	5	0.00
l_shipinstruct	VARCHAR	DELIVER IN PERSON	TAKE BACK RETURN	3	NULL	NULL	NULL	NULL	NULL	5	0.00
l_shipmode	VARCHAR	AIR	TRUCK	4	NULL	NULL	NULL	NULL	NULL	5	0.00
l_comment	VARCHAR	pending foxes wake	to beans x-ray carefully	5	NULL	NULL	NULL	NULL	NULL	5	0.00
```

## Using `SUMMARIZE` in a Subquery

`SUMMARIZE` can be used as a subquery. This allows creating a table from the summary, for example:

```sql
CREATE TABLE tbl_summary AS SELECT * FROM (SUMMARIZE TABLE tbl);
```

## Summarizing Remote Tables

It is possible to summarize remote tables over HTTP(S) and S3 using the `SUMMARIZE TABLE` statement. For example:

```sql
SUMMARIZE TABLE 'https://example.com/data/data.csv';
```

