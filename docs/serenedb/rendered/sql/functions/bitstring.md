---
title: Bitstring Functions
split: headings
---

import DocCallout from "@site/src/components/DocCallout";
import SqlLogicTest from "@site/src/components/SqlLogicTest";

<!-- markdownlint-disable MD001 -->

This section describes functions and operators for examining and manipulating [`BITSTRING`](../../sql/data_types/bitstring.md) values.
Bitstrings must be of equal length when performing the bitwise operands AND, OR and XOR. When bit shifting, the original length of the string is preserved.

## Bitstring Operators

The table below shows the available mathematical operators for `BIT` type.

<!-- markdownlint-disable MD056 -->

| Operator | Description         | Example                                   |             Result |
| :------- | :------------------ | :---------------------------------------- | -----------------: |
| `&`      | Bitwise AND         | `'10101'::BITSTRING & '10001'::BITSTRING` |            `10001` |
| <code>&#124;</code> | Bitwise OR | <code>'1011'::BITSTRING &#124; '0001'::BITSTRING</code> | `1011` |
| `xor`    | Bitwise XOR         | `xor('101'::BITSTRING, '001'::BITSTRING)` |              `100` |
| `~`      | Bitwise NOT         | `~('101'::BITSTRING)`                     |              `010` |
| `<<`     | Bitwise shift left  | `'1001011'::BITSTRING << 3`               |          `1011000` |
| `>>`     | Bitwise shift right | `'1001011'::BITSTRING >> 3`               |          `0001001` |

<!-- markdownlint-enable MD056 -->

## Bitstring Functions

The table below shows the available scalar functions for `BIT` type.

| Name                                                                        | Description                                                                                                                              |
| :-------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------- |
| [`bit_count(bitstring)`](#bit_countbitstring)                               | Returns the number of set bits in the bitstring.                                                                                         |
| [`bit_length(bitstring)`](#bit_lengthbitstring)                             | Returns the number of bits in the bitstring.                                                                                             |
| [`bit_position(substring, bitstring)`](#bit_positionsubstring-bitstring)    | Returns first starting index of the specified substring within bits, or zero if it's not present. The first (leftmost) bit is indexed 1. |
| [`bitstring(bitstring, length)`](#bitstringbitstring-length)                | Returns a bitstring of determined length.                                                                                                |
| [`get_bit(bitstring, index)`](#get_bitbitstring-index)                      | Extracts the nth bit from bitstring; the first (leftmost) bit is indexed 0.                                                              |
| [`length(bitstring)`](#lengthbitstring)                                     | Alias for `bit_length`.                                                                                                                  |
| [`octet_length(bitstring)`](#octet_lengthbitstring)                         | Returns the number of bytes in the bitstring.                                                                                            |
| [`set_bit(bitstring, index, new_value)`](#set_bitbitstring-index-new_value) | Sets the nth bit in bitstring to newvalue; the first (leftmost) bit is indexed 0. Returns a new bitstring.                               |

#### `bit_count(bitstring)`

Returns the number of set bits in the bitstring.

```sql
SELECT bit_count('1101011'::BITSTRING) AS bit_count;
-- result:
bit_count
5
```

#### `bit_length(bitstring)`

Returns the number of bits in the bitstring.

```sql
SELECT bit_length('1101011'::BITSTRING) AS bit_length;
-- result:
bit_length
7
```

#### `bit_position(substring, bitstring)`

Returns first starting index of the specified substring within bits, or zero if it's not present. The first (leftmost) bit is indexed 1.

```sql
SELECT bit_position('010'::BITSTRING, '1110101'::BITSTRING) AS bit_position;
-- result:
bit_position
4
```

#### `bitstring(bitstring, length)`

Returns a bitstring of determined length.

```sql
SELECT bitstring('1010'::BITSTRING, 7) AS bitstring;
-- result:
bitstring
0001010
```

#### `get_bit(bitstring, index)`

Extracts the nth bit from bitstring; the first (leftmost) bit is indexed 0.

```sql
SELECT get_bit('0110010'::BITSTRING, 2) AS get_bit;
-- result:
get_bit
1
```

#### `length(bitstring)`

Alias for `bit_length`.

```sql
SELECT length('1101011'::BITSTRING) AS length;
-- result:
length
7
```

#### `octet_length(bitstring)`

Returns the number of bytes in the bitstring.

```sql
SELECT octet_length('1101011'::BITSTRING) AS octet_length;
-- result:
octet_length
1
```

#### `set_bit(bitstring, index, new_value)`

Sets the nth bit in bitstring to newvalue; the first (leftmost) bit is indexed 0. Returns a new bitstring.

```sql
SELECT set_bit('0110010'::BITSTRING, 2, 0) AS set_bit;
-- result:
set_bit
0100010
```

## Bitstring Aggregate Functions

These aggregate functions are available for `BIT` type.

| Name                                                        | Description                                                                                                                                                                     |
| :---------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`bit_and(arg)`](#bit_andarg)                               | Returns the bitwise AND operation performed on all bitstrings in a given expression.                                                                                            |
| [`bit_or(arg)`](#bit_orarg)                                 | Returns the bitwise OR operation performed on all bitstrings in a given expression.                                                                                             |
| [`bit_xor(arg)`](#bit_xorarg)                               | Returns the bitwise XOR operation performed on all bitstrings in a given expression.                                                                                            |
| [`bitstring_agg(arg)`](#bitstring_aggarg)                   | Returns a bitstring with bits set for each distinct position defined in `arg`.                                                                                                  |
| [`bitstring_agg(arg, min, max)`](#bitstring_aggarg-min-max) | Returns a bitstring with bits set for each distinct position defined in `arg`. All positions must be within the range [`min`, `max`] or an `Out of Range Error` will be thrown. |

The examples below use a table `bits` with a `BITSTRING` column `A` holding `10101`, `11001` and `00110`, and a table `nums` with an `INTEGER` column `A` holding `1`, `3`, `5` and `8`.

```sql
CREATE TABLE bits (A BITSTRING);

INSERT INTO bits VALUES ('10101'::BITSTRING), ('11001'::BITSTRING), ('00110'::BITSTRING);

CREATE TABLE nums (A INTEGER);

INSERT INTO nums VALUES (1), (3), (5), (8);
```

#### `bit_and(arg)`

Returns the bitwise AND operation performed on all bitstrings in a given expression.

```sql
SELECT bit_and(A) AS bit_and FROM bits;
-- result:
bit_and
00000
```

#### `bit_or(arg)`

Returns the bitwise OR operation performed on all bitstrings in a given expression.

```sql
SELECT bit_or(A) AS bit_or FROM bits;
-- result:
bit_or
11111
```

#### `bit_xor(arg)`

Returns the bitwise XOR operation performed on all bitstrings in a given expression.

```sql
SELECT bit_xor(A) AS bit_xor FROM bits;
-- result:
bit_xor
01010
```

#### `bitstring_agg(arg)`

The `bitstring_agg` function takes any integer type as input and returns a bitstring with bits set for each distinct value. The left-most bit represents the smallest value in the column and the right-most bit the maximum value. If possible, the min and max are retrieved from the column statistics. Otherwise, it is also possible to provide the min and max values.

```sql
SELECT bitstring_agg(A) AS bitstring_agg FROM nums;
-- result:
bitstring_agg
10101001
```

<DocCallout type="tip">
The combination of `bit_count` and `bitstring_agg` can be used as an alternative to `count(DISTINCT ...)`, with possible performance improvements in cases of low cardinality and dense values.
</DocCallout>

#### `bitstring_agg(arg, min, max)`

Returns a bitstring with bits set for each distinct position defined in `arg`. All positions must be within the range [`min`, `max`] or an `Out of Range Error` will be thrown.

```sql
SELECT bitstring_agg(A, 1, 42) AS bitstring_agg FROM nums;
-- result:
bitstring_agg
101010010000000000000000000000000000000000
```

