---
title: Caveats
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

## Equality Comparison

Equality and ordering comparisons on `JSON` values are based on their raw physical text, not on their logical content. Two `JSON` values with identical logical content are treated as different whenever their text differs in whitespace, number formatting, or object key order.

The following query shows that `JSON` comparison is purely textual, so logically equivalent values are treated as not equal when their physical text differs. It also shows the subscript operator (`[...]`) extracting an array element by position and an object field by key:

```sql
SELECT
    '[1,2]'::JSON = '[1, 2]'::JSON                 AS whitespace_differs,    -- f: the extra space is part of the physical text
    '1'::JSON = '1.0'::JSON                        AS number_format_differs, -- f: 1 and 1.0 are not textually equal
    '{"a":1,"b":2}'::JSON = '{"b":2,"a":1}'::JSON  AS key_order_differs,     -- f: object key order is physical
    ('[10,20,30]'::JSON)[1]                        AS element_by_index,      -- 20: array subscript extracts by position
    ('{"a":42}'::JSON)['a']                        AS field_by_key;          -- 42: object subscript extracts by key
-- result:
whitespace_differs	number_format_differs	key_order_differs	element_by_index	field_by_key
f	f	f	20	42
```

