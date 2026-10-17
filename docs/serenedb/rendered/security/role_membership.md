---
title: Role Membership
sidebar_position: 3
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

It is convenient to group roles together to manage privileges in one place: grant a privilege to the group once, and every member has it. In SereneDB, as in PostgreSQL, a group is just a role — membership is granted and revoked with the same [`GRANT`](../sql/statements/grant/index.md) and [`REVOKE`](../sql/statements/revoke/index.md) statements used for privileges.

Set up a group role, give it a privilege, and add a member:

```sql
CREATE ROLE doc_sec_analysts;

CREATE ROLE doc_sec_bob LOGIN PASSWORD 'doc_sec_bob_pw';

CREATE TABLE doc_sec_reports (id int, total int);

GRANT SELECT ON doc_sec_reports TO doc_sec_analysts;

GRANT doc_sec_analysts TO doc_sec_bob;
```

`pg_has_role` reports membership:

```sql
SELECT pg_has_role('doc_sec_bob', 'doc_sec_analysts', 'MEMBER') AS is_member;
-- result:
is_member
t
```

## Inheritance

Members with the default `INHERIT` attribute exercise the group's privileges automatically — `doc_sec_bob` can read the table because `doc_sec_analysts` can:

```sql
SELECT has_table_privilege('doc_sec_bob', 'doc_sec_reports', 'SELECT') AS can_read;
-- result:
can_read
t
```

## SET ROLE

A session can also switch to a role explicitly with [`SET ROLE`](../sql/statements/set_role/index.md). Privilege checks then apply to that role instead of the one that authenticated; `session_user` keeps reporting the login identity while `current_user` reports the active one. `RESET ROLE` switches back:

```sql
SET ROLE doc_sec_analysts;

SELECT current_user, session_user;
-- result:
current_user	session_user
doc_sec_analysts	postgres

RESET ROLE;
```

A superuser can set any role; other roles can only set roles they are a member of.

## Grant options and delegation

Membership can be granted `WITH ADMIN OPTION`, which lets the member grant the same membership on to others — the mechanism for delegating group management without superuser:

```sql
CREATE ROLE doc_mo_lead;

CREATE ROLE doc_mo_deputy LOGIN PASSWORD 'doc_mo_deputy_pw';

GRANT doc_mo_lead TO doc_mo_deputy WITH ADMIN OPTION;

SELECT pg_has_role('doc_mo_deputy', 'doc_mo_lead', 'MEMBER WITH ADMIN OPTION') AS can_admin;
-- result:
can_admin
t
```

The deputy, holding `ADMIN OPTION`, can now add members itself:

```sql
CREATE ROLE doc_mo_staff LOGIN PASSWORD 'doc_mo_staff_pw';

SET ROLE doc_mo_deputy;

GRANT doc_mo_lead TO doc_mo_staff;

RESET ROLE;

SELECT pg_has_role('doc_mo_staff', 'doc_mo_lead', 'MEMBER') AS is_member;
-- result:
is_member
t
```

A member created `NOINHERIT` is still a member, but does not use the group's privileges automatically — it must `SET ROLE` to the group to exercise them:

```sql
CREATE ROLE doc_mo_alice LOGIN PASSWORD 'doc_mo_alice_pw' NOINHERIT;

GRANT doc_mo_lead TO doc_mo_alice;

SELECT rolinherit FROM pg_roles WHERE rolname = 'doc_mo_alice';
-- result:
rolinherit
f
```

## Transitive membership

Membership chains: a member of a member is a member. Adding `doc_mo_staff` to `doc_mo_deputy` (which is a member of `doc_mo_lead`) reaches `doc_mo_lead` through the chain:

```sql
GRANT doc_mo_deputy TO doc_mo_staff;

SELECT pg_has_role('doc_mo_staff', 'doc_mo_lead', 'MEMBER') AS reaches_lead;
-- result:
reaches_lead
t
```

Cycles are refused — a role cannot become a member of a role that is already (transitively) a member of it:

```sql
GRANT doc_mo_staff TO doc_mo_lead;
```

## Revoking membership

Revoking the membership takes the inherited privileges with it:

```sql
REVOKE doc_sec_analysts FROM doc_sec_bob;

SELECT pg_has_role('doc_sec_bob', 'doc_sec_analysts', 'MEMBER') AS is_member;
-- result:
is_member
f
```

## Notes

- Granting membership requires `ADMIN OPTION` on the role, the `CREATEROLE` attribute, or superuser.
- Membership is not cyclic: a role cannot be granted to itself, directly or through a chain.
- Groups usually have no `LOGIN` — they exist to be granted, not to connect.
- A `NOINHERIT` member does not use the group's privileges implicitly; it must [`SET ROLE`](../sql/statements/set_role/index.md) to the group first, as in PostgreSQL.

## See also

- [GRANT](../sql/statements/grant/index.md) — the membership form of GRANT
- [SET ROLE](../sql/statements/set_role/index.md) — switch the active role
- [Privileges](privileges.md) — what the group grants actually confer

