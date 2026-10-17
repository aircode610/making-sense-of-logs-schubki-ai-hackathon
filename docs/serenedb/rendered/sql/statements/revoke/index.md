---
title: REVOKE
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `REVOKE` statement is the inverse of [`GRANT`](../grant/index.md): it removes privileges on an object from a role, or removes a role's membership in another role. The `GRANT OPTION FOR` / `ADMIN OPTION FOR` forms remove only the right to re-grant, keeping the underlying privilege or membership.

## Examples

Given a table with privileges granted and a role membership:

```sql
CREATE TABLE doc_vault (id int, secret text);

CREATE ROLE doc_auditor;

CREATE ROLE doc_team;

CREATE ROLE doc_member;

GRANT SELECT, INSERT ON doc_vault TO doc_auditor WITH GRANT OPTION;

GRANT doc_team TO doc_member;
```

Take one privilege away:

```sql
REVOKE INSERT ON doc_vault FROM doc_auditor;
```

```sql
SELECT has_table_privilege('doc_auditor', 'doc_vault', 'INSERT');
-- result:
has_table_privilege
f
```

Remove only the grant option — the role keeps `SELECT` but can no longer pass it on:

```sql
REVOKE GRANT OPTION FOR SELECT ON doc_vault FROM doc_auditor;
```

```sql
SELECT has_table_privilege('doc_auditor', 'doc_vault', 'SELECT');
-- result:
has_table_privilege
t
```

Revoke role membership:

```sql
REVOKE doc_team FROM doc_member;
```

```sql
SELECT pg_has_role('doc_member', 'doc_team', 'MEMBER');
-- result:
pg_has_role
f
```

`ALL PRIVILEGES` clears everything the role holds on the object:

```sql
REVOKE ALL PRIVILEGES ON doc_vault FROM doc_auditor;
```

## Notes

- Revoking requires the same authority as granting: object ownership (or `GRANT OPTION`) for privileges, `ADMIN OPTION` / `CREATEROLE` / superuser for membership.
- Revoking a privilege the role does not hold is not an error — the statement simply has no effect.

## See also

- [GRANT](../grant/index.md) — grant privileges or role membership
- [DROP ROLE](../drop_role/index.md) — remove roles entirely

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

