---
title: Privileges
sidebar_position: 4
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

Every database object has an owner and an access-control list. The owner — normally the role that created the object — holds every privilege on it implicitly; everyone else has only what has been granted to them (directly, through [role membership](role_membership.md), or through `PUBLIC`).

The owner holds all privileges from the start:

```sql
CREATE TABLE doc_sec_ledger (id int, amount int, note text);

SELECT has_table_privilege(current_user, 'doc_sec_ledger', 'SELECT') AS owner_reads,
       has_table_privilege(current_user, 'doc_sec_ledger', 'DELETE') AS owner_deletes;
-- result:
owner_reads	owner_deletes
t	t
```

## Granting privileges

[`GRANT`](../sql/statements/grant/index.md) gives a privilege on an object to a role, and the `has_*_privilege` functions inspect the result:

```sql
CREATE ROLE doc_sec_reader;

GRANT SELECT ON doc_sec_ledger TO doc_sec_reader;

SELECT has_table_privilege('doc_sec_reader', 'doc_sec_ledger', 'SELECT') AS can_select,
       has_table_privilege('doc_sec_reader', 'doc_sec_ledger', 'INSERT') AS can_insert;
-- result:
can_select	can_insert
t	f
```

Privileges are enforced on every query. Acting as the role, reading works and writing is refused:

```sql
SET ROLE doc_sec_reader;

SELECT count(*) AS row_count FROM doc_sec_ledger;
-- result:
row_count
0

INSERT INTO doc_sec_ledger VALUES (1, 100, 'blocked');

RESET ROLE;
```

## Available privileges

| Object | Privileges |
|---|---|
| `TABLE` (default) | `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`, `MAINTAIN` |
| `SEQUENCE` | `USAGE`, `SELECT`, `UPDATE` |
| `FUNCTION` | `EXECUTE` |
| `DATABASE` | `CREATE`, `CONNECT`, `TEMPORARY` |
| `SCHEMA` | `CREATE`, `USAGE` |
| `TYPE` | `USAGE` |
| `FOREIGN SERVER` | `USAGE` |

`ALL PRIVILEGES` grants everything applicable to the object type.

`USAGE` on a schema is needed to use any object in it: a role with `SELECT` on `s.t` but no `USAGE` on `s` gets `permission denied for schema s`. As in PostgreSQL, `public` grants `USAGE` to everyone, and a view reads its sources with its owner's privileges, so reading through a view needs `USAGE` only on the view's own schema.

`USAGE` on a [foreign server](../sql/statements/create_server/index.md#privileges) is checked whenever a query reads through it, in any database. Creating a server is gated on `CREATE` on the **database**, not on a schema.

## Column privileges

`SELECT`, `INSERT` and `UPDATE` can be restricted to specific columns. A column grant does not confer the table-level privilege:

```sql
CREATE ROLE doc_sec_auditor;

GRANT SELECT (id, amount) ON doc_sec_ledger TO doc_sec_auditor;

SELECT has_column_privilege('doc_sec_auditor', 'doc_sec_ledger', 'amount', 'SELECT') AS amount_ok,
       has_column_privilege('doc_sec_auditor', 'doc_sec_ledger', 'note', 'SELECT') AS note_ok;
-- result:
amount_ok	note_ok
t	f
```

## Grant options

With `WITH GRANT OPTION`, the grantee may pass the privilege on to others:

```sql
CREATE ROLE doc_sec_clerk;

GRANT SELECT ON doc_sec_ledger TO doc_sec_clerk WITH GRANT OPTION;

SET ROLE doc_sec_clerk;

GRANT SELECT ON doc_sec_ledger TO doc_sec_auditor;

RESET ROLE;
```

### Reading the ACL

An object's access-control list is stored in its catalog `*acl` column (`relacl` for tables) as an array of `aclitem`s in PostgreSQL's format — `grantee=privileges/grantor`, where an empty grantee means `PUBLIC` and a trailing `*` marks a privilege held **with grant option**:

```sql
CREATE TABLE doc_pa_docs (id int, body text);

CREATE ROLE doc_pa_editor LOGIN PASSWORD 'doc_pa_editor_pw';

CREATE ROLE doc_pa_viewer LOGIN PASSWORD 'doc_pa_viewer_pw';

GRANT SELECT ON doc_pa_docs TO doc_pa_editor WITH GRANT OPTION;

SELECT relacl FROM pg_class WHERE relname = 'doc_pa_docs';
-- result:
relacl
{postgres=arwdDxtm/postgres,doc_pa_editor=r*/postgres}
```

The grantee can then pass the privilege on:

```sql
SET ROLE doc_pa_editor;

GRANT SELECT ON doc_pa_docs TO doc_pa_viewer;

RESET ROLE;

SELECT has_table_privilege('doc_pa_viewer', 'doc_pa_docs', 'SELECT') AS viewer_reads;
-- result:
viewer_reads
t
```

## PUBLIC

`PUBLIC` is a pseudo-role meaning every role, present and future:

```sql
GRANT SELECT ON doc_sec_ledger TO PUBLIC;

SELECT has_table_privilege('doc_sec_auditor', 'doc_sec_ledger', 'SELECT') AS via_public;
-- result:
via_public
t
```

## Revoking

[`REVOKE`](../sql/statements/revoke/index.md) removes grants — but only the grants the revoker (or a role it can act for) made. Revoking a direct grant does not remove access that still flows from `PUBLIC`, and a grant made by another grantor survives until that grantor revokes it:

```sql
REVOKE SELECT ON doc_sec_ledger FROM doc_sec_reader;

SELECT has_table_privilege('doc_sec_reader', 'doc_sec_ledger', 'SELECT') AS still_via_public;
-- result:
still_via_public
t

REVOKE SELECT ON doc_sec_ledger FROM PUBLIC;

SET ROLE doc_sec_clerk;

REVOKE SELECT ON doc_sec_ledger FROM doc_sec_auditor;

RESET ROLE;

SELECT has_table_privilege('doc_sec_auditor', 'doc_sec_ledger', 'SELECT') AS after_revoke;
-- result:
after_revoke
f
```

<DocCallout type="tip">

If a role still has access after a `REVOKE`, check where it flows from: a `PUBLIC` grant, a group membership, or a grant made by a different grantor. `has_table_privilege` reflects the combined result of all of them.

</DocCallout>

### Dependent grants: RESTRICT and CASCADE

When a privilege was passed on via `WITH GRANT OPTION`, those onward grants depend on it. By default (`RESTRICT`) `REVOKE` refuses while dependents exist:

```sql
REVOKE SELECT ON doc_pa_docs FROM doc_pa_editor;
```

`CASCADE` revokes the privilege and every grant that depended on it, in one step:

```sql
REVOKE SELECT ON doc_pa_docs FROM doc_pa_editor CASCADE;

SELECT has_table_privilege('doc_pa_editor', 'doc_pa_docs', 'SELECT') AS editor,
       has_table_privilege('doc_pa_viewer', 'doc_pa_docs', 'SELECT') AS viewer;
-- result:
editor	viewer
f	f
```

## Ownership

Ownership can be transferred with `ALTER ... OWNER TO`. The new owner immediately holds every privilege on the object, including the right to drop it:

```sql
ALTER TABLE doc_sec_ledger OWNER TO doc_sec_clerk;

SELECT has_table_privilege('doc_sec_clerk', 'doc_sec_ledger', 'DELETE') AS new_owner_all;
-- result:
new_owner_all
t
```

## Notes

- Granting a privilege requires owning the object or holding it `WITH GRANT OPTION`.
- Superusers bypass all privilege checks.
- `ALTER DEFAULT PRIVILEGES` is accepted and stored for PostgreSQL compatibility but is not yet applied to newly created objects.

## See also

- [GRANT](../sql/statements/grant/index.md) — full syntax, including the membership form
- [REVOKE](../sql/statements/revoke/index.md) — removing privileges
- [Database roles](roles.md) — the identities privileges are granted to

