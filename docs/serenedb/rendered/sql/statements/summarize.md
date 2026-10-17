---
title: SUMMARIZE
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `SUMMARIZE` statement returns summary statistics for a table, view or a query.

## Usage

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

## See Also

For more examples, see the [guide on `SUMMARIZE`](../../cookbook/meta/summarize.md).

