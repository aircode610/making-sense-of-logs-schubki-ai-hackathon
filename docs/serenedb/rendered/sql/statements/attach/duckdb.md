---
title: DuckDB
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

A DuckDB database file is SereneDB's native attachable database. `ATTACH` opens a DuckDB file for reading and writing, and the alias is inferred from the file name unless an explicit one is given. For the general `ATTACH` and `DETACH` syntax, see [ATTACH AND DETACH](./index.md).

Attach the database `file.db` with the alias inferred from the name (`file`):

```sql
ATTACH 'file.db';
```

Attach the database `file.db` with an explicit alias (`file_db`):

```sql
ATTACH 'file.db' AS file_db;
```

Attach the database `file.db` only if the inferred alias `file` does not yet exist:

```sql
ATTACH IF NOT EXISTS 'file.db';
```

Attach the database `file.db` only if the explicit alias `file_db` does not yet exist:

```sql
ATTACH IF NOT EXISTS 'file.db' AS file_db;
```

Attach the database `file2.db` as alias `file_db`, detaching and replacing the existing alias if it exists:

```sql
ATTACH OR REPLACE 'file2.db' AS file_db;
```

Create a table in the attached database with alias `file`:

```sql
CREATE TABLE db16.new_table (i INTEGER);
```

Detach the database with alias `file`:

```sql
DETACH db16;
```

Show a list of all attached databases:

```sql
SHOW DATABASES;
```

Change the default database that is used to the database `file`:

```sql
USE db16;
```

## Options

Zero or more options may be provided within parentheses following the `ATTACH` statement. Parameter values can be passed in with or without wrapping in single quotes. Arbitrary expressions may be used for parameter values.

| Name                | Description                                                                                                                 | Type      | Default value |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------- | ------------- |
| `ACCESS_MODE`       | Access mode of the database (`AUTOMATIC`, `READ_ONLY`, or `READ_WRITE`).                                                    | `VARCHAR` | `automatic`   |
| `COMPRESS`          | Whether the database is compressed. Only applicable for in-memory databases.                                                | `VARCHAR` | `false`       |
| `TYPE`              | The database type. `DUCKDB` for a file, or `postgres` deduced from a connection string.                                     | `VARCHAR` | `DUCKDB`      |
| `BLOCK_SIZE`        | The block size of a new database file. Must be a power of two and within [16384, 262144]. Cannot be set for existing files. | `UBIGINT` | `262144`      |
| `ROW_GROUP_SIZE`    | The row group size of a new database file.                                                                                  | `UBIGINT` | `122880`      |
| `STORAGE_VERSION`   | The version of the storage used.                                                                                            | `VARCHAR` | `v1.0.0`      |
| `ENCRYPTION_KEY`    | The encryption key used for encrypting the database.                                                                        | `VARCHAR` | -             |
| `ENCRYPTION_CIPHER` | The encryption cipher used for encrypting the database (`CTR` or `GCM`).                                                     | `VARCHAR` | -             |
| `RECOVERY_MODE`     | Recovery mode for the database. `no_wal_writes` disables WAL writes, improving performance at the cost of crash recovery.   | `VARCHAR` | -             |

Attach the database `file.db` in read only mode:

```sql
ATTACH 'file.db' (READ_ONLY);
```

Attach the database `file.db` with a block size of 16 kB:

```sql
ATTACH 'file.db' (BLOCK_SIZE 16_384);
```

Attach the database `file.db` with a row group size of 2048 rows:

```sql
ATTACH 'file.db' (ROW_GROUP_SIZE 2048);
```

Attach the database `file.db` with WAL writes disabled for improved performance:

```sql
ATTACH 'file.db' (RECOVERY_MODE no_wal_writes);
```

## Explicit Storage Versions

SereneDB allows explicitly specifying the storage version. Using this, you can opt-in to newer forwards-incompatible features:

```sql
ATTACH 'file.db' (STORAGE_VERSION 'v1.2.0');
```

This setting specifies the minimum SereneDB version that should be able to read the database file. When database files are written with this option, the resulting files cannot be opened by older SereneDB versions than the specified version. They can be read by the specified version and all newer versions of SereneDB.

A DuckDB database takes only DuckDB storage versions: `ATTACH` refuses `STORAGE_VERSION 'serenedb_v1'` and `STORAGE_VERSION 'serenedb_latest'`. Those belong to SereneDB's own databases, which [`CREATE DATABASE`](../create_database/index.md) creates with their own catalog log, write-ahead log and compression formats. A SereneDB database is never attached by path: `ATTACH '<path>' (TYPE serenedb)` is refused, and a file with a SereneDB storage version does not open as a DuckDB database.

A file with a DuckDB storage version holds only what DuckDB reads, so the DuckDB release of that version opens it too. A statement that would store more fails at commit: stored generated columns, partial indexes, index operator classes, views with `security_invoker`, `ALTER TABLE ... ADD UNIQUE`, and renaming an index, a schema or a sequence. As in DuckDB, a table that has an index can't be renamed, and neither can its columns. Objects in such a file have no owner and no privileges, and `GRANT`, `REVOKE` and `OWNER TO` fail on them. Constraint names, and the link between a `SERIAL` column and its sequence, are not kept once the file is closed. In-memory databases and SereneDB databases keep all of these.

## Database Encryption

SereneDB supports database encryption. By default, it uses [AES encryption](https://en.wikipedia.org/wiki/Advanced_Encryption_Standard) with a key length of 256 bits using the recommended [GCM](https://en.wikipedia.org/wiki/Galois/Counter_Mode) mode. The encryption covers the main database file, the write-ahead-log (WAL) file and even temporary files. To attach to an encrypted database, use the `ATTACH` statement with an `ENCRYPTION_KEY`:

```sql
ATTACH 'encrypted.db' AS enc_db (ENCRYPTION_KEY 'secret_key');
```

To change the AES mode to [CTR](https://en.wikipedia.org/wiki/Block_cipher_mode_of_operation#Counter_%28CTR%29), use the `ENCRYPTION_CIPHER` option:

```sql
ATTACH 'encrypted.db' AS enc_db (ENCRYPTION_KEY 'secret_key', ENCRYPTION_CIPHER 'CTR');
```

<DocCallout type="tip">
SereneDB's encryption does not yet meet the official [NIST requirements](https://csrc.nist.gov/projects/cryptographic-standards-and-guidelines).
</DocCallout>

## Remote files (HTTP / S3)

`ATTACH` supports HTTP and S3 endpoints. For these, it creates a read-only connection by default. Therefore, the following two commands are equivalent:

```sql
ATTACH 'https://blobs.duckdb.org/databases/stations.duckdb' AS stations_db;

ATTACH 'https://blobs.duckdb.org/databases/stations.duckdb' AS stations_db (READ_ONLY);
```

Similarly, the following two commands connecting to S3 are equivalent:

```sql
ATTACH 's3://⟨blobs-duckdb⟩/databases/stations.duckdb' AS stations_db;

ATTACH 's3://⟨blobs-duckdb⟩/databases/stations.duckdb' AS stations_db (READ_ONLY);
```

