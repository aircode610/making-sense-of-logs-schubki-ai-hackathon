---
title: Numeric Functions
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

<!-- markdownlint-disable MD001 -->

## Numeric Operators

The table below shows the available mathematical operators for [numeric types](../../sql/data_types/numeric.md).

<!-- markdownlint-disable MD056 -->

| Operator | Description               | Example    | Result |
| -------- | ------------------------- | ---------- | ------ |
| `+`      | Addition                  | `2 + 3`    | `5`    |
| `-`      | Subtraction               | `2 - 3`    | `-1`   |
| `*`      | Multiplication            | `2 * 3`    | `6`    |
| `/`      | Division                  | `5 / 2`    | `2`    |
| `//`     | Division                  | `5 // 2`   | `2`    |
| `%`      | Modulo (remainder)        | `5 % 4`    | `1`    |
| `**`     | Exponent                  | `3 ** 4`   | `81`   |
| `^`      | Exponent (alias for `**`) | `3 ^ 4`    | `81`   |
| `&`      | Bitwise AND               | `91 & 15`  | `11`   |
| <code>&#124;</code> | Bitwise OR | <code>32 &#124; 3</code> | `35` |
| `<<`     | Bitwise shift left        | `1 << 4`   | `16`   |
| `>>`     | Bitwise shift right       | `8 >> 2`   | `2`    |
| `~`      | Bitwise negation          | `~15`      | `-16`  |
| `!`      | Factorial of `x`          | `4!`       | `24`   |

<!-- markdownlint-enable MD056 -->

### Division and Modulo Operators

There are two division operators: `/` and `//`.
They are equivalent when at least one of the operands is a `FLOAT` or a `DOUBLE`.
When both operands are integers, `//` performs integer division (`5 // 2 = 2`) and `/` follows the [`integer_division`](../../configuration/overview.md) setting: a server truncates like PostgreSQL (`5 / 2 = 2`), while `serened shell` divides as floats (`5 / 2 = 2.5`). Write `5 / 2.0` for a fractional result on both. Integer division or modulo by zero fails with a `Division by zero` error. To return `NULL` instead, wrap the expression in `TRY(...)`, or run `SET error_on_division_by_zero = false` to return `NULL` for all divisions by zero:

```sql
SELECT 1 // 0 AS quotient;
-- result:
db error: ERROR: Division by zero in expression (1 // 0). Use TRY(...) to return NULL for this expression, or SET error_on_division_by_zero=false to return NULL for all divisions by zero.


SELECT TRY(1 // 0) AS quotient, TRY(5 % 0) AS remainder;
-- result:
quotient	remainder
NULL	NULL


SELECT 5 % 0 AS remainder;

SET error_on_division_by_zero = false;

SELECT 1 // 0 AS quotient, 5 % 0 AS remainder;
-- result:
quotient	remainder
NULL	NULL

RESET error_on_division_by_zero;
```

### Supported Types

The modulo, bitwise, negation, and factorial operators work only on integral data types,
whereas the others are available for all numeric data types.

## Numeric Functions

The table below shows the available mathematical functions.

| Name                                                                   | Description                                                                                                                                                                                    |
| :--------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`@(x)`](#x)                                                           | Absolute value. Parentheses are optional if `x` is a column name.                                                                                                                              |
| [`abs(x)`](#absx)                                                      | Absolute value.                                                                                                                                                                                |
| [`acos(x)`](#acosx)                                                    | Computes the inverse cosine of `x`.                                                                                                                                                            |
| [`acosh(x)`](#acoshx)                                                  | Computes the inverse hyperbolic cosine of `x`.                                                                                                                                                 |
| [`add(x, y)`](#addx-y)                                                 | Alias for `x + y`.                                                                                                                                                                             |
| [`asin(x)`](#asinx)                                                    | Computes the inverse sine of `x`.                                                                                                                                                              |
| [`asinh(x)`](#asinhx)                                                  | Computes the inverse hyperbolic sine of `x`.                                                                                                                                                   |
| [`atan(x)`](#atanx)                                                    | Computes the inverse tangent of `x`.                                                                                                                                                           |
| [`atanh(x)`](#atanhx)                                                  | Computes the inverse hyperbolic tangent of `x`.                                                                                                                                                |
| [`atan2(y, x)`](#atan2y-x)                                             | Computes the inverse tangent of `(y, x)`.                                                                                                                                                      |
| [`bit_count(x)`](#bit_countx)                                          | Returns the number of bits that are set.                                                                                                                                                       |
| [`cbrt(x)`](#cbrtx)                                                    | Returns the cube root of the number.                                                                                                                                                           |
| [`ceil(x)`](#ceilx)                                                    | Rounds the number up.                                                                                                                                                                          |
| [`ceiling(x)`](#ceilingx)                                              | Rounds the number up. Alias of `ceil`.                                                                                                                                                         |
| [`cos(x)`](#cosx)                                                      | Computes the cosine of `x`.                                                                                                                                                                    |
| [`cot(x)`](#cotx)                                                      | Computes the cotangent of `x`.                                                                                                                                                                 |
| [`degrees(x)`](#degreesx)                                              | Converts radians to degrees.                                                                                                                                                                   |
| [`divide(x, y)`](#dividex-y)                                           | Alias for `x // y`.                                                                                                                                                                            |
| [`even(x)`](#evenx)                                                    | Round to next even number by rounding away from zero.                                                                                                                                          |
| [`exp(x)`](#expx)                                                      | Computes `e ** x`.                                                                                                                                                                             |
| [`factorial(x)`](#factorialx)                                          | See the `!` operator. Computes the product of the current integer and all integers below it.                                                                                                   |
| [`fdiv(x, y)`](#fdivx-y)                                               | Performs integer division (`x // y`) but returns a `DOUBLE` value.                                                                                                                             |
| [`floor(x)`](#floorx)                                                  | Rounds the number down.                                                                                                                                                                        |
| [`fmod(x, y)`](#fmodx-y)                                               | Calculates the modulo value. Always returns a `DOUBLE` value.                                                                                                                                  |
| [`gamma(x)`](#gammax)                                                  | Interpolation of the factorial of `x - 1`. Fractional inputs are allowed.                                                                                                                      |
| [`gcd(x, y)`](#gcdx-y)                                                 | Computes the greatest common divisor of `x` and `y`.                                                                                                                                           |
| [`greatest_common_divisor(x, y)`](#greatest_common_divisorx-y)         | Computes the greatest common divisor of `x` and `y`.                                                                                                                                           |
| [`greatest(x1, x2, ...)`](#greatestx1-x2-)                             | Selects the largest value.                                                                                                                                                                     |
| [`isfinite(x)`](#isfinitex)                                            | Returns true if the floating point value is finite, false otherwise.                                                                                                                           |
| [`isinf(x)`](#isinfx)                                                  | Returns true if the floating point value is infinite, false otherwise.                                                                                                                         |
| [`isnan(x)`](#isnanx)                                                  | Returns true if the floating point value is not a number, false otherwise.                                                                                                                     |
| [`lcm(x, y)`](#lcmx-y)                                                 | Computes the least common multiple of `x` and `y`.                                                                                                                                             |
| [`least_common_multiple(x, y)`](#least_common_multiplex-y)             | Computes the least common multiple of `x` and `y`.                                                                                                                                             |
| [`least(x1, x2, ...)`](#leastx1-x2-)                                   | Selects the smallest value.                                                                                                                                                                    |
| [`lgamma(x)`](#lgammax)                                                | Computes the log of the `gamma` function.                                                                                                                                                      |
| [`ln(x)`](#lnx)                                                        | Computes the natural logarithm of `x`.                                                                                                                                                         |
| [`log(x)`](#logx)                                                      | Computes the base-10 logarithm of `x`.                                                                                                                                                         |
| [`log10(x)`](#log10x)                                                  | Alias of `log`. Computes the base-10 logarithm of `x`.                                                                                                                                         |
| [`log2(x)`](#log2x)                                                    | Computes the base-2 log of `x`.                                                                                                                                                                |
| [`multiply(x, y)`](#multiplyx-y)                                       | Alias for `x * y`.                                                                                                                                                                             |
| [`nextafter(x, y)`](#nextafterx-y)                                     | Return the next floating point value after `x` in the direction of `y`.                                                                                                                        |
| [`pi()`](#pi)                                                          | Returns the value of pi.                                                                                                                                                                       |
| [`pow(x, y)`](#powx-y)                                                 | Computes `x` to the power of `y`.                                                                                                                                                              |
| [`power(x, y)`](#powerx-y)                                             | Alias of `pow`. Computes `x` to the power of `y`.                                                                                                                                              |
| [`radians(x)`](#radiansx)                                              | Converts degrees to radians.                                                                                                                                                                   |
| [`random()`](#random)                                                  | Returns a random number `x` in the range `0.0 <= x < 1.0`.                                                                                                                                     |
| [`round_even(v NUMERIC, s INTEGER)`](#round_evenv-numeric-s-integer)   | Alias of `roundbankers(v, s)`. Round to `s` decimal places using the [_rounding half to even_ rule](https://en.wikipedia.org/wiki/Rounding#Rounding_half_to_even). Values `s < 0` are allowed. |
| [`roundbankers(v NUMERIC, s INTEGER)`](#round_evenv-numeric-s-integer) | Alias of `round_even(v, s)`. Round to `s` decimal places using the [_rounding half to even_ rule](https://en.wikipedia.org/wiki/Rounding#Rounding_half_to_even). Values `s < 0` are allowed.   |
| [`round(v NUMERIC, s INTEGER)`](#roundv-numeric-s-integer)             | Round to `s` decimal places. Values `s < 0` are allowed.                                                                                                                                       |
| [`setseed(x)`](#setseedx)                                              | Sets the seed to be used for the random function.                                                                                                                                              |
| [`sign(x)`](#signx)                                                    | Returns the sign of `x` as -1, 0 or 1.                                                                                                                                                         |
| [`signbit(x)`](#signbitx)                                              | Returns whether the signbit is set or not.                                                                                                                                                     |
| [`sin(x)`](#sinx)                                                      | Computes the sin of `x`.                                                                                                                                                                       |
| [`sqrt(x)`](#sqrtx)                                                    | Returns the square root of the number.                                                                                                                                                         |
| [`subtract(x, y)`](#subtractx-y)                                       | Alias for `x - y`.                                                                                                                                                                             |
| [`tan(x)`](#tanx)                                                      | Computes the tangent of `x`.                                                                                                                                                                   |
| [`to_hex(x)`](#to_hexx)                                                | Converts the integer `x` to lowercase hexadecimal, as PostgreSQL does.                                                                                                                         |
| [`trunc(x)`](#truncx)                                                  | Truncates the number.                                                                                                                                                                          |
| [`xor(x, y)`](#xorx-y)                                                 | Bitwise XOR.                                                                                                                                                                                   |

#### `@(x)`

<div className="docs-table-properties">

| **Description** | Absolute value. Parentheses are optional if `x` is a column name. |
| :--- | :--- |
| **Example** | `@(-17.4)` |
| **Result** | `17.4` |
| **Alias** | `abs` |

</div>

#### `abs(x)`

Absolute value. Alias: `@`.

```sql
SELECT abs(-17.4) AS abs;
-- result:
abs
17.4
```

#### `acos(x)`

Computes the inverse cosine of `x`.

```sql
SELECT acos(0.5) AS acos;
-- result:
acos
1.047197551196597<slt:ignore>
```

#### `acosh(x)`

Computes the inverse hyperbolic cosine of `x`.

```sql
SELECT acosh(1.5) AS acosh;
-- result:
acosh
0.9624236501192069
```

#### `add(x, y)`

Alias for `x + y`.

```sql
SELECT add(2, 3) AS add;
-- result:
add
5
```

#### `asin(x)`

Computes the inverse sine of `x`.

```sql
SELECT asin(0.5) AS asin;
-- result:
asin
0.523598775598298<slt:ignore>
```

#### `asinh(x)`

Computes the inverse hyperbolic sine of `x`.

```sql
SELECT asinh(0.5) AS asinh;
-- result:
asinh
0.48121182505960347
```

#### `atan(x)`

Computes the inverse tangent of `x`.

```sql
SELECT atan(0.5) AS atan;
-- result:
atan
0.463647609000806<slt:ignore>
```

#### `atanh(x)`

Computes the inverse hyperbolic tangent of `x`.

```sql
SELECT atanh(0.5) AS atanh;
-- result:
atanh
0.549306144334054<slt:ignore>
```

#### `atan2(y, x)`

Computes the inverse tangent of `(y, x)`.

```sql
SELECT atan2(0.5, 0.5) AS atan2;
-- result:
atan2
0.7853981633974483
```

#### `bit_count(x)`

Returns the number of bits that are set.

```sql
SELECT bit_count(31) AS bit_count;
-- result:
bit_count
5
```

#### `cbrt(x)`

Returns the cube root of the number.

```sql
SELECT cbrt(8) AS cbrt;
-- result:
cbrt
2
```

#### `ceil(x)`

Rounds the number up.

```sql
SELECT ceil(17.4) AS ceil;
-- result:
ceil
18
```

#### `ceiling(x)`

Rounds the number up. Alias of `ceil`.

```sql
SELECT ceiling(17.4) AS ceiling;
-- result:
ceiling
18
```

#### `cos(x)`

Computes the cosine of `x`.

```sql
SELECT cos(pi() / 3) AS cos;
-- result:
cos
0.5000000000000001
```

#### `cot(x)`

Computes the cotangent of `x`.

```sql
SELECT cot(0.5) AS cot;
-- result:
cot
1.830487721712452
```

#### `degrees(x)`

Converts radians to degrees.

```sql
SELECT degrees(pi()) AS degrees;
-- result:
degrees
180
```

#### `divide(x, y)`

Alias for `x // y`.

```sql
SELECT divide(5, 2) AS divide;
-- result:
divide
2
```

#### `even(x)`

Round to next even number by rounding away from zero.

```sql
SELECT even(2.9) AS even;
-- result:
even
4
```

#### `exp(x)`

Computes `e ** x`.

```sql
SELECT exp(0.693) AS exp;
-- result:
exp
1.9997056605411638
```

#### `factorial(x)`

See the `!` operator. Computes the product of the current integer and all integers below it.

```sql
SELECT factorial(4) AS factorial;
-- result:
factorial
24
```

#### `fdiv(x, y)`

Performs integer division (`x // y`) but returns a `DOUBLE` value.

```sql
SELECT fdiv(5, 2) AS fdiv;
-- result:
fdiv
2
```

#### `floor(x)`

Rounds the number down.

```sql
SELECT floor(17.4) AS floor;
-- result:
floor
17
```

#### `fmod(x, y)`

Calculates the modulo value. Always returns a `DOUBLE` value.

```sql
SELECT fmod(5, 2) AS fmod;
-- result:
fmod
1
```

#### `gamma(x)`

Interpolation of the factorial of `x - 1`. Fractional inputs are allowed.

```sql
SELECT gamma(5.5) AS gamma;
-- result:
gamma
52.34277778455352
```

#### `gcd(x, y)`

Computes the greatest common divisor of `x` and `y`.

```sql
SELECT gcd(42, 57) AS gcd;
-- result:
gcd
3
```

#### `greatest_common_divisor(x, y)`

Computes the greatest common divisor of `x` and `y`.

```sql
SELECT greatest_common_divisor(42, 57) AS greatest_common_divisor;
-- result:
greatest_common_divisor
3
```

#### `greatest(x1, x2, ...)`

Selects the largest value.

```sql
SELECT greatest(3, 2, 4, 4) AS greatest;
-- result:
greatest
4
```

#### `isfinite(x)`

Returns true if the floating point value is finite, false otherwise.

```sql
SELECT isfinite(5.5) AS isfinite;
-- result:
isfinite
t
```

#### `isinf(x)`

Returns true if the floating point value is infinite, false otherwise.

```sql
SELECT isinf('Infinity'::FLOAT) AS isinf;
-- result:
isinf
t
```

#### `isnan(x)`

Returns true if the floating point value is not a number, false otherwise.

```sql
SELECT isnan('NaN'::FLOAT) AS isnan;
-- result:
isnan
t
```

#### `lcm(x, y)`

Computes the least common multiple of `x` and `y`.

```sql
SELECT lcm(42, 57) AS lcm;
-- result:
lcm
798
```

#### `least_common_multiple(x, y)`

Computes the least common multiple of `x` and `y`.

```sql
SELECT least_common_multiple(42, 57) AS least_common_multiple;
-- result:
least_common_multiple
798
```

#### `least(x1, x2, ...)`

Selects the smallest value.

```sql
SELECT least(3, 2, 4, 4) AS least;
-- result:
least
2
```

#### `lgamma(x)`

Computes the log of the `gamma` function.

```sql
SELECT lgamma(2) AS lgamma;
-- result:
lgamma
0
```

#### `ln(x)`

Computes the natural logarithm of `x`.

```sql
SELECT ln(2) AS ln;
-- result:
ln
0.6931471805599453
```

#### `log(x)`

Computes the base-10 logarithm of `x`.

```sql
SELECT log(100) AS log;
-- result:
log
2
```

#### `log10(x)`

Alias of `log`. Computes the base-10 logarithm of `x`.

```sql
SELECT log10(1000) AS log10;
-- result:
log10
3
```

#### `log2(x)`

Computes the base-2 log of `x`.

```sql
SELECT log2(8) AS log2;
-- result:
log2
3
```

#### `multiply(x, y)`

Alias for `x * y`.

```sql
SELECT multiply(2, 3) AS multiply;
-- result:
multiply
6
```

#### `nextafter(x, y)`

Return the next floating point value after `x` in the direction of `y`.

```sql
SELECT nextafter(1::FLOAT, 2::FLOAT) AS nextafter;
-- result:
nextafter
1.0000001
```

#### `pi()`

Returns the value of pi.

```sql
SELECT pi() AS pi;
-- result:
pi
3.141592653589793
```

#### `pow(x, y)`

Computes `x` to the power of `y`.

```sql
SELECT pow(2, 3) AS pow;
-- result:
pow
8
```

#### `power(x, y)`

Alias of `pow`. Computes `x` to the power of `y`.

```sql
SELECT power(2, 3) AS power;
-- result:
power
8
```

#### `radians(x)`

Converts degrees to radians.

```sql
SELECT radians(90) AS radians;
-- result:
radians
1.5707963267948966
```

#### `random()`

<div className="docs-table-properties">

| **Description** | Returns a random number `x` in the range `0.0 <= x < 1.0`. |
| :--- | :--- |
| **Example** | `random()` |
| **Result** | various |

</div>

#### `round_even(v NUMERIC, s INTEGER)`

Alias of `roundbankers(v, s)`. Round to `s` decimal places using the [_rounding half to even_ rule](https://en.wikipedia.org/wiki/Rounding#Rounding_half_to_even). Values `s < 0` are allowed.

```sql
SELECT round_even(24.5, 0) AS round_even;
-- result:
round_even
24
```

#### `roundbankers(v NUMERIC, s INTEGER)`

Alias of `round_even(v, s)`. Round to `s` decimal places using the [_rounding half to even_ rule](https://en.wikipedia.org/wiki/Rounding#Rounding_half_to_even). Values `s < 0` are allowed.

```sql
SELECT roundbankers(24.5, 0) AS roundbankers;
-- result:
roundbankers
24
```

#### `round(v NUMERIC, s INTEGER)`

Round to `s` decimal places. Values `s < 0` are allowed.

```sql
SELECT round(42.4332, 2) AS round;
-- result:
round
42.43
```

#### `setseed(x)`

<div className="docs-table-properties">

| **Description** | Sets the seed to be used for the random function. |
| :--- | :--- |
| **Example** | `setseed(0.42)` |

</div>

#### `sign(x)`

Returns the sign of `x` as -1, 0 or 1.

```sql
SELECT sign(-349) AS sign;
-- result:
sign
-1
```

#### `signbit(x)`

Returns whether the signbit is set or not.

```sql
SELECT signbit(-1.0) AS signbit;
-- result:
signbit
t
```

#### `sin(x)`

Computes the sin of `x`.

```sql
SELECT sin(pi() / 6) AS sin;
-- result:
sin
0.49999999999999994
```

#### `sqrt(x)`

Returns the square root of the number.

```sql
SELECT sqrt(9) AS sqrt;
-- result:
sqrt
3
```

#### `subtract(x, y)`

Alias for `x - y`.

```sql
SELECT subtract(2, 3) AS subtract;
-- result:
subtract
-1
```

#### `tan(x)`

Computes the tangent of `x`.

```sql
SELECT tan(pi() / 4) AS tan;
-- result:
tan
0.9999999999999999
```

#### `to_hex(x)`

Converts the `integer` or `bigint` `x` to lowercase hexadecimal, as PostgreSQL does. A negative value is shown in the two's complement of its own width: `to_hex(-1)` is `ffffffff`, `to_hex(-1::BIGINT)` is `ffffffffffffffff`. For a string or blob, `to_hex` is an alias of [`hex`](../../sql/functions/text.md#hexstring).

```sql
SELECT to_hex(-1) AS to_hex;
-- result:
to_hex
ffffffff
```

#### `trunc(x)`

Truncates the number.

```sql
SELECT trunc(17.4) AS trunc;
-- result:
trunc
17
```

#### `xor(x, y)`

Bitwise XOR.

```sql
SELECT xor(17, 5) AS xor;
-- result:
xor
20
```

