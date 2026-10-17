---
title: SET ROLE
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `SET ROLE` statement switches the current role of the session. Privilege checks then apply to that role instead of the role you authenticated as. A superuser can set any role; other users can only set roles they are a member of. `RESET ROLE` (or `SET ROLE DEFAULT`) switches back.

## Examples

Given a role with access to a table:

```sql
CREATE ROLE doc_reporter;

CREATE TABLE doc_report (id int);

INSERT INTO doc_report VALUES (1);

GRANT SELECT ON doc_report TO doc_reporter;
```

Switch to it:

```sql
SET ROLE doc_reporter;
```

`current_user` and `current_role` now report the set role, while `session_user` remains the role that authenticated:

```sql
query TTT
SELECT current_user, current_role, session_user;
-- result:
current_user	current_role	session_user
doc_reporter	doc_reporter	postgres
```

Access checks are made against the current role:

```sql
SELECT id FROM doc_report;
-- result:
id
1
```

Switch back:

```sql
RESET ROLE;
```

```sql
SHOW role;
-- result:
role
none
```

Setting a role that does not exist is an error:

```sql
SET ROLE doc_no_such_role;
```

## Notes

- Setting a role you are not a member of fails with `permission denied to set role "..."` (superusers are exempt).
- The switch lasts for the session (until `RESET ROLE`, another `SET ROLE`, or disconnect).

## See also

- [GRANT](../grant/index.md) — grant role membership
- [CREATE ROLE](../create_role/index.md) — create roles

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

