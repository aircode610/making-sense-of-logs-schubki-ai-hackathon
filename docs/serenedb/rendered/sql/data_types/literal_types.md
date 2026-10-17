---
title: Literal Types
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

SereneDB has special literal types for representing `NULL`, integer and string literals in queries. These have their own binding and conversion rules.

## Null Literals

The `NULL` literal is denoted with the keyword `NULL`. The `NULL` literal can be implicitly converted to any other type.

## Integer Literals

Integer literals are denoted as a sequence of one or more decimal digits. At runtime, these result in values of the `INTEGER_LITERAL` type. `INTEGER_LITERAL` types can be implicitly converted to any [fixed-width integer type](../../sql/data_types/numeric.md#fixed-width-integer-types) in which the value fits. For example, the integer literal `42` can be implicitly converted to a `TINYINT`, but the integer literal `1000` cannot be.

<DocCallout type="tip">
SereneDB does not support hexadecimal or binary literals directly. However, strings or string literals in hexadecimal or binary notation with `0x` or `0b` prefixes respectively, can be cast to integer types, e.g., `'0xFF'::INT = 255` or `0b101::INT = 5`.
</DocCallout>

## Other Numeric Literals

Non-integer numeric literals can be denoted with decimal notation, using the period character (`.`) to separate the integer part and the decimal part of the number.
The integer part may be omitted (for example, `.50`), but the decimal part may not: a trailing-dot literal such as `2.` is rejected with a syntax error.

```sql
SELECT 1.5;
-- result:
?column?
1.5

SELECT .50;
-- result:
?column?
0.50

SELECT 2.;
-- result:
?column?
2
```

Non-integer numeric literals can also be denoted using [_E notation_](https://en.wikipedia.org/wiki/Scientific_notation#E_notation). In E notation, an integer or decimal literal is followed by an exponential part, which is denoted by `e` or `E`, followed by a literal integer indicating the exponent.
The exponential part indicates that the preceding value should be multiplied by 10 raised to the power of the exponent:

```sql
SELECT 1e2;
-- result:
?column?
100

SELECT 6.02214e23;
-- result:
?column?
<slt:ignore>

SELECT 1e-10;
-- result:
?column?
<slt:ignore>
```

## Underscores in Numeric Literals

SereneDB's SQL dialect allows using the underscore character `_` in numeric literals as an optional separator. The rules for using underscores are as follows:

-   Underscores are allowed in integer, decimal, hexadecimal and binary notation.
-   Underscores cannot be the first or last character in a literal.
-   Underscores have to have an integer/numeric part on either side of them, i.e., there cannot be multiple underscores in a row and underscores cannot appear immediately before or after a decimal or exponent.

Examples:

```sql
SELECT 100_000_000;
-- result:
?column?
100000000

SELECT '0xFF_FF'::INTEGER;
-- result:
int4
65535

SELECT 1_2.1_2E0_1;
-- result:
?column?
121.2

SELECT '0b0_1_0_1'::INTEGER;
-- result:
int4
5
```

## String Literals

String literals are delimited using single quotes (`'`, apostrophe) and result in `STRING_LITERAL` values.
Note that double quotes (`"`) cannot be used as string delimiter character: instead, double quotes are used to delimit [quoted identifiers](../../compatibility/keywords_and_identifiers.md#identifiers).

### String Literal Concatenation

As in PostgreSQL, adjacent string literals are concatenated when the whitespace between them contains at least one newline:

```sql
SELECT 'Hello'
    ' '
    'World' AS greeting;
-- result:
greeting
Hello World
```

On a single line, placing two single-quoted literals next to each other is a syntax error:

```sql
query error
SELECT 'Hello' ' ' 'World' AS greeting;
-- result:
db error: ERROR: syntax error at or near "' '"
```

To concatenate strings anywhere, use the `||` operator explicitly:

```sql
SELECT 'Hello'
    || ' '
    || 'World' AS greeting;
-- result:
greeting
Hello World
```

### Implicit String Conversion

`STRING_LITERAL` instances can be implicitly converted to _any_ other type.

For example, we can compare string literals with dates:

```sql
SELECT d > '1992-01-01' AS result
FROM (VALUES (DATE '1992-01-01')) t(d);
-- result:
result
f
```

However, we cannot compare `VARCHAR` values with dates.

```sql
query error
SELECT d > '1992-01-01'::VARCHAR
FROM (VALUES (DATE '1992-01-01')) t(d);
-- result:
db error: ERROR: Cannot compare values of type DATE and type VARCHAR - an explicit cast is required
```

### Escape String Literals

To escape a single quote (apostrophe) character in a string literal, use `''`. For example, `SELECT '''' AS s` returns `'`.

To enable some common escape sequences, such as `\n` for the newline character, prefix a string literal with `e` (or `E`).

```sql
SELECT e'Hello\nworld' AS msg;
-- result:
msg
Hello\nworld
```

The following backslash escape sequences are supported:

| Escape sequence | Name            | ASCII code |
| :-------------- | :-------------- | ---------: |
| `\b`            | backspace       |          8 |
| `\f`            | form feed       |         12 |
| `\n`            | newline         |         10 |
| `\r`            | carriage return |         13 |
| `\t`            | tab             |          9 |

### Dollar-Quoted String Literals

SereneDB supports dollar-quoted string literals, which are surrounded by double-dollar symbols (`$$`):

```sql
SELECT $$Hello
world$$ AS msg;
-- result:
msg
Hello\nworld
```

```sql
SELECT $$The price is $9.95$$ AS msg;
-- result:
msg
The price is $9.95
```

Even more, you can insert alphanumeric tags in the double-dollar symbols to allow for the use of regular double-dollar symbols _within_ the string literal:

```sql
SELECT $tag$ this string can contain newlines,
'single quotes',
"double quotes",
and $$dollar quotes$$ $tag$ AS msg;
-- result:
msg
 this string can contain newlines,\n'single quotes',\n"double quotes",\nand $$dollar quotes$$
```

Dollar-quoted string literals cannot be concatenated implicitly; use the `||` operator to join them.

