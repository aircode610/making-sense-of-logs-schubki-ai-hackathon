---
title: Time Zones
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

An up-to-date version of this list can be pulled from the `pg_timezone_names()` table function:

```sql
SELECT name, abbrev
FROM pg_timezone_names()
ORDER BY name;
```

