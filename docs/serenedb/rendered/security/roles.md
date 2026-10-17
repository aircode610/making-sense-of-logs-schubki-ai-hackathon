---
title: Database Roles
sidebar_position: 2
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

Roles are the identities of the access-control system. A role can own database objects, hold privileges on other roles' objects, and — if it has the `LOGIN` attribute — start client connections. Roles are global across the server: the same role exists in every database.

The concept of a role subsumes the classic notions of "user" and "group": a role with `LOGIN` behaves like a user, a role that is granted to other roles behaves like a group, and nothing stops one role from being both.

Every server starts with one predefined role: the superuser `postgres`. It bypasses all permission checks and is always able to connect locally, so it cannot be locked out — use it to create the rest.

## Viewing roles

The existing roles are listed in the `pg_roles` catalog (and, for password state, the superuser-only `pg_authid`):

```sql
SELECT rolname, rolcanlogin, rolsuper
FROM pg_roles WHERE rolname = 'postgres';
-- result:
rolname	rolcanlogin	rolsuper
postgres	t	t
```

## Creating roles

Create a role that can connect, with a password to authenticate:

```sql
CREATE ROLE doc_sec_alice LOGIN PASSWORD 'doc_sec_alice_pw';

SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = 'doc_sec_alice';
-- result:
rolname	rolcanlogin
doc_sec_alice	t
```

`CREATE ROLE` and `CREATE USER` differ only in their default: `CREATE ROLE` creates a role **without** `LOGIN` (a group, or a pure owner of objects), while `CREATE USER` includes it:

```sql
CREATE ROLE doc_sec_batch;

CREATE USER doc_sec_carol;

SELECT rolname, rolcanlogin FROM pg_roles
WHERE rolname IN ('doc_sec_batch', 'doc_sec_carol') ORDER BY rolname;
-- result:
rolname	rolcanlogin
doc_sec_batch	f
doc_sec_carol	t
```

## Role attributes

Attributes control a role's server-level abilities. They are set at creation or changed later with [`ALTER ROLE`](../sql/statements/alter_role/index.md):

```sql
CREATE ROLE doc_sec_deploy LOGIN PASSWORD 'doc_sec_deploy_pw' CREATEDB CREATEROLE;

SELECT rolcreatedb, rolcreaterole, rolsuper FROM pg_roles
WHERE rolname = 'doc_sec_deploy';
-- result:
rolcreatedb	rolcreaterole	rolsuper
t	t	f
```

| Attribute | Meaning |
|---|---|
| `LOGIN` / `NOLOGIN` | May the role start client connections? Roles without it can still be granted to others or own objects. |
| `SUPERUSER` / `NOSUPERUSER` | Bypasses every permission check. Only another superuser can create one. |
| `CREATEDB` / `NOCREATEDB` | May the role create databases? |
| `CREATEROLE` / `NOCREATEROLE` | May the role create, alter and drop other roles? It cannot hand out attributes it does not hold itself. |
| `INHERIT` / `NOINHERIT` | Does the role automatically use privileges of roles it is a member of? Default `INHERIT`. |
| `PASSWORD '...'` | Stores a SCRAM-SHA-256 verifier for password authentication. `PASSWORD NULL` clears it. |
| `VALID UNTIL '<timestamp>'` | The password stops working after this time — enforced at login. |
| `CONNECTION LIMIT <n>` | Accepted and stored for PostgreSQL compatibility; not currently enforced. |

A role that grants management powers with `CREATEROLE` gets them, but bounded like PostgreSQL: a `CREATEROLE` role cannot hand out an attribute it does not itself hold (so it cannot create a `SUPERUSER`), and it can only alter or drop roles it administers — i.e. roles it created, on which it automatically receives `ADMIN OPTION`:

```sql
CREATE ROLE doc_mr_admin LOGIN PASSWORD 'doc_mr_admin_pw' CREATEROLE;

SELECT rolcreaterole, rolsuper, rolcreatedb FROM pg_roles
WHERE rolname = 'doc_mr_admin';
-- result:
rolcreaterole	rolsuper	rolcreatedb
t	f	f
```

Change attributes, rotate a password, or set an expiry at any time:

```sql
ALTER ROLE doc_sec_alice PASSWORD 'doc_sec_rotated_pw';

ALTER ROLE doc_sec_alice VALID UNTIL '2099-01-01 00:00:00+00';

ALTER ROLE doc_sec_batch LOGIN PASSWORD 'doc_sec_batch_pw';
```

A role can also be renamed:

```sql
ALTER ROLE doc_sec_carol RENAME TO doc_sec_renamed;

SELECT count(*) AS remaining FROM pg_roles WHERE rolname = 'doc_sec_carol';
-- result:
remaining
0
```

Creating a role whose name is already taken is an error:

```sql
CREATE ROLE doc_mr_dupe;

CREATE ROLE doc_mr_dupe;
```

## Dropping roles

A role cannot be dropped while it still owns objects — the dependency is reported and the drop is refused. Reassign or drop the objects first:

```sql
CREATE ROLE doc_sec_owner;

CREATE TABLE doc_sec_audit (id int);

ALTER TABLE doc_sec_audit OWNER TO doc_sec_owner;

DROP ROLE doc_sec_owner;

DROP TABLE doc_sec_audit;

DROP ROLE doc_sec_owner;
```

`DROP ROLE` accepts a comma-separated list, and `IF EXISTS` makes a missing role a no-op instead of an error:

```sql
DROP ROLE doc_sec_alice, doc_sec_batch;

DROP ROLE IF EXISTS doc_sec_missing;
```

<DocCallout type="attention">

Privileges the role holds on *other* objects are revoked automatically when it is dropped — only ownership blocks the drop. PostgreSQL's bulk helpers `DROP OWNED BY` and `REASSIGN OWNED BY` are not supported yet, so transfer ownership with `ALTER ... OWNER TO` per object.

</DocCallout>

## See also

- [CREATE ROLE](../sql/statements/create_role/index.md) — full syntax and options
- [ALTER ROLE](../sql/statements/alter_role/index.md) — change attributes and passwords
- [DROP ROLE](../sql/statements/drop_role/index.md) — remove roles
- [Role membership](role_membership.md) — use roles as groups

