---
title: GRANT
split: headings
---

import RailroadDiagram from '@site/src/components/RailroadDiagram';
import RailroadSource from './diagram.js';

import SqlLogicTest from "@site/src/components/SqlLogicTest";

The `GRANT` statement has two forms. The first grants privileges on an object (a table, sequence, function, database, schema, or type) to a role. The second grants membership in a role to another role, so the member inherits the role's privileges.

## Examples

Given a table and some roles:

```sql
CREATE TABLE doc_ledger (id int, amount int, note text);

CREATE ROLE doc_reader;

CREATE ROLE doc_writer;

CREATE ROLE doc_staff;

CREATE ROLE doc_clerk;
```

Allow a role to read the table:

```sql
GRANT SELECT ON doc_ledger TO doc_reader;
```

Grant several privileges at once:

```sql
GRANT INSERT, UPDATE, DELETE ON doc_ledger TO doc_writer;
```

`ALL PRIVILEGES` grants every privilege applicable to the object:

```sql
GRANT ALL PRIVILEGES ON doc_ledger TO doc_staff;
```

A privilege can be restricted to specific columns:

```sql
GRANT SELECT (id, amount) ON doc_ledger TO doc_clerk;
```

With `WITH GRANT OPTION`, the grantee may pass the privilege on to others:

```sql
GRANT SELECT ON doc_ledger TO doc_reader WITH GRANT OPTION;
```

Inspect the result with the `has_*_privilege` functions:

```sql
SELECT has_table_privilege('doc_reader', 'doc_ledger', 'SELECT');
-- result:
has_table_privilege
t
```

```sql
SELECT has_column_privilege('doc_clerk', 'doc_ledger', 'amount', 'SELECT');
-- result:
has_column_privilege
t
```

The second form grants role membership — `doc_staff` now inherits everything granted to `doc_reader`:

```sql
GRANT doc_reader TO doc_staff;
```

```sql
SELECT pg_has_role('doc_staff', 'doc_reader', 'MEMBER');
-- result:
pg_has_role
t
```

`PUBLIC` is a pseudo-role meaning every role:

```sql
GRANT SELECT (note) ON doc_ledger TO PUBLIC;
```

Granting to a role that does not exist is an error:

```sql
GRANT SELECT ON doc_ledger TO doc_nobody;
```

## Privileges by object type

| Object | Privileges |
|---|---|
| `TABLE` (default) | `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`, `MAINTAIN` |
| `SEQUENCE` | `USAGE`, `SELECT`, `UPDATE` |
| `FUNCTION` | `EXECUTE` |
| `DATABASE` | `CREATE`, `CONNECT`, `TEMPORARY` |
| `SCHEMA` | `CREATE`, `USAGE` |
| `TYPE` | `USAGE` |

## Notes

- Granting a privilege requires owning the object or holding the privilege `WITH GRANT OPTION`; granting membership requires `ADMIN OPTION` on the role, the `CREATEROLE` attribute, or superuser.
- The object's owner always holds all privileges on it, and the owner of a granted role's privileges flow to members automatically.
- Unlike PostgreSQL, an unknown privilege keyword (e.g. `GRANT FLY ON t TO r`) is a syntax error rather than a semantic one.

## See also

- [REVOKE](../revoke/index.md) — take privileges or membership away
- [CREATE ROLE](../create_role/index.md) — create roles to grant to
- [SET ROLE](../set_role/index.md) — act as a role you are a member of

## Syntax

<RailroadDiagram source={RailroadSource} production="rrdiagram" />

