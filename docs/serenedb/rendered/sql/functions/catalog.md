---
title: Catalog Functions
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

Several functions are provided to inspect the catalogs and schemas that are configured in the database.

The following catalog functions are available:

| Function | Description |
| :------- | :---------- |
| [`current_catalog()`](#current_catalog) | Returns the name of the currently active catalog. |
| [`current_schema()`](#current_schema) | Returns the name of the currently active schema. |
| [`current_schemas(include_implicit)`](#current_schemasinclude_implicit) | Returns the list of schemas in the search path. Pass `true` to include implicit schemas. |

#### `current_catalog()`

Returns the name of the currently active catalog, which is the database the session is connected to.

```sql
SELECT current_catalog() = current_database() AS catalog_is_current_db;
-- result:
catalog_is_current_db
t
```

#### `current_schema()`

Returns the name of the currently active schema.

```sql
SELECT current_schema();
-- result:
current_schema
public
```

#### `current_schemas(include_implicit)`

Returns the list of schemas in the search path. Pass `true` to include implicit schemas such as `pg_catalog`.

```sql
SELECT current_schemas(true) AS schemas;
-- result:
schemas
{pg_catalog,public}
```

```sql
SELECT current_schemas(false) AS schemas;
-- result:
schemas
{public}
```

