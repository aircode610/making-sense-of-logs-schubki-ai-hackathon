---
title: CREATE MACRO
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

The `CREATE MACRO` statement can create a scalar or table macro (function) in the catalog.

For a scalar macro, `CREATE MACRO` is followed by the name of the macro, and optionally parameters within a set of parentheses. The keyword `AS` is next, followed by the text of the macro. By design, a scalar macro may only return a single value.
For a table macro, the syntax is similar to a scalar macro except `AS` is replaced with `AS TABLE`. A table macro may return a table of arbitrary size and shape.

<DocCallout type="tip">
If a `MACRO` is temporary, it is only usable within the same database connection and is deleted when the connection is closed.
</DocCallout>

## Examples

### Scalar Macros

Create a macro that adds two expressions (`a` and `b`):

```sql
CREATE MACRO add(a, b) AS a + b;
```

Create a macro, replacing possible existing definitions:

```sql
CREATE OR REPLACE MACRO add(a, b) AS a + b;
```

Create a macro if it does not already exist, else do nothing:

```sql
CREATE MACRO IF NOT EXISTS add(a, b) AS a + b;
```

Create a macro for a `CASE` expression:

```sql
CREATE MACRO ifelse(a, b, c) AS CASE WHEN a THEN b ELSE c END;
```

Create a macro that does a subquery:

```sql
CREATE MACRO one() AS (SELECT 1);
```

Macros are schema-dependent, and have an alias, `FUNCTION`:

```sql
CREATE FUNCTION main.my_avg(x) AS sum(x) / count(x);
```

Create a macro with a default parameter:

```sql
CREATE MACRO add_default(a, b := 5) AS a + b;
```

Create a macro `arr_append` (with a functionality equivalent to `array_append`):

```sql
CREATE MACRO arr_append(l, e) AS list_concat(l, list_value(e));
```

Create a macro with a typed parameter:

```sql
CREATE MACRO is_maximal(a INTEGER) AS a = 2^31 - 1;
```

### Table Macros

Create a table macro without parameters:

```sql
CREATE MACRO static_table() AS TABLE
    SELECT 'Hello' AS column1, 'World' AS column2;
```

Create a table macro with parameters (that can be of any type):

```sql
CREATE MACRO dynamic_table(col1_value, col2_value) AS TABLE
    SELECT col1_value AS column1, col2_value AS column2;
```

Create a table macro that returns multiple rows. It will be replaced if it already exists, and it is temporary (will be automatically deleted when the connection ends):

```sql
CREATE OR REPLACE TEMP MACRO dynamic_table(col1_value, col2_value) AS TABLE
    SELECT col1_value AS column1, col2_value AS column2
    UNION ALL
    SELECT 'Hello' AS col1_value, 456 AS col2_value;
```

Pass an argument as a list:

```sql
CREATE MACRO get_users(i) AS TABLE
    SELECT * FROM users WHERE uid IN (SELECT unnest(i));
```

An example for how to use the `get_users` table macro is the following:

```sql
SELECT * FROM get_users([1, 5]);
-- result:
uid	name
1	Ada
5	Eve
```

To define macros on arbitrary tables, use the [`query_table` function](../../../cookbook/sql_features/query_and_query_table_functions.md). For example, the following macro computes a column-wise checksum on a table:

```sql
CREATE MACRO checksum(tbl) AS TABLE
    SELECT bit_xor(md5_number(COLUMNS(*)::VARCHAR))
    FROM query_table(tbl);

CREATE TABLE tbl AS SELECT unnest([42, 43]) AS x, 100 AS y;

skipif pg-wire-extended
SELECT * FROM checksum('tbl');
-- result:
x	y
60609334165039584609948387465088153270	0
```

## Overloading

It is possible to overload a macro based on the types or the number of its parameters; this works for both scalar and table macros.

By providing overloads we can have both `add_x(a, b)` and `add_x(a, b, c)` with different function bodies.

```sql
CREATE MACRO add_x
    (a, b) AS a + b,
    (a, b, c) AS a + b + c;
```

```sql
SELECT
    add_x(21, 42) AS two_args,
    add_x(21, 42, 21) AS three_args;
-- result:
two_args	three_args
63	84
```

```sql
CREATE OR REPLACE MACRO is_maximal
    (a TINYINT) AS a = 2^7 - 1,
    (a INT) AS a = 2^31 - 1;
```

```sql
SELECT
    is_maximal(127::TINYINT) AS tiny,
    is_maximal(127) AS regular;
-- result:
tiny	regular
t	f
```

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

Macros allow you to create shortcuts for combinations of expressions.

```sql
CREATE MACRO add(a) AS a + b;
-- result:
db error: ERROR: Referenced column "b" was not found because the FROM clause is missing
```

This works:

```sql
CREATE MACRO add(a, b) AS a + b;
```

Usage example:

```sql
SELECT add(1, 2) AS x;
-- result:
x
3
```

However, this fails:

```sql
query error
SELECT add('hello', 3);
-- result:
db error: ERROR: Could not convert string 'hello' to INT32
```

Macros can have default parameters.

`b` is a default parameter:

```sql
CREATE MACRO add_default(a, b := 5) AS a + b;
```

The following will result in 42:

```sql
SELECT add_default(37);
-- result:
add_default
42
```

The order of named parameters does not matter:

```sql
CREATE MACRO triple_add(a, b := 5, c := 10) AS a + b + c;
```

```sql
SELECT triple_add(40, c := 1, b := 1) AS x;
-- result:
x
42
```

When macros are used, they are expanded (i.e., replaced with the original expression), and the parameters within the expanded expression are replaced with the supplied arguments. Step by step:

The `add` macro we defined above is used in a query:

```sql
SELECT add(40, 2) AS x;
-- result:
x
42
```

Internally, `add` is replaced with its definition of `a + b`:

```sql
query error
SELECT a + b AS x;
-- result:
db error: ERROR: Referenced column "a" was not found because the FROM clause is missing
```

Then, the parameters are replaced by the supplied arguments:

```sql
SELECT 40 + 2 AS x;
-- result:
x
42
```

## Limitations

### Using Subquery Macros

Table macros as well as scalar macros defined using scalar subqueries cannot be used in the arguments of table functions. SereneDB will return an error:

```sql
SELECT * FROM range(scalar_sub());
-- result:
db error: ERROR: Table function cannot contain subqueries
```


### Recursive Functions

Defining recursive functions is not supported. A recursive macro expands until it exceeds the expression-depth limit (`max_expression_depth`, `1000` by default). For example, the following macro – supposed to compute the *n*th number of the Fibonacci sequence – fails (the example lowers `max_expression_depth` so the failure is immediate):

```sql
CREATE OR REPLACE FUNCTION fibo(n) AS (SELECT 1);

CREATE OR REPLACE FUNCTION fibo(n) AS (
    CASE
        WHEN n <= 1 THEN 1
        ELSE fibo(n - 1)
    END
);

query error
SELECT fibo(3);
-- result:
db error: ERROR: Max expression depth limit of 50 exceeded. Use "SET max_expression_depth TO x" to increase the maximum expression depth.
```

### Function Chaining on the First Function

Macros support the dot operator for function chaining on the first function.
For example, the following macro uses the `lower` function in the conventional form:

```sql
CREATE OR REPLACE MACRO low(s) AS lower(s);

SELECT low('AA');
-- result:
low
aa
```

Rewriting `lower(s)` to use function chaining works as well:

```sql
CREATE OR REPLACE MACRO low(s) AS s.lower();

SELECT low('AA');
-- result:
low
aa
```

### Viewing the List of Macros and Table Macros

You can use the following query to display the list of macros and table macros:

```sql
SELECT schema_name, function_name, function_type, parameters
FROM sdb_functions()
WHERE function_type IN ('macro', 'table_macro');
```

