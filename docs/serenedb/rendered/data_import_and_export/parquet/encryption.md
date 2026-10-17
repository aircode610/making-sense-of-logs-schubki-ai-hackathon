---
title: Encryption
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

SereneDB supports reading and writing encrypted Parquet files.
SereneDB broadly follows the [Parquet Modular Encryption specification](https://github.com/apache/parquet-format/blob/master/Encryption.md) with some [limitations](#limitations).

## Reading and Writing Encrypted Files

Using the `PRAGMA add_parquet_key` function, named encryption keys of 128, 192, or 256 bits can be added to a session. These keys are stored in-memory:

```sql
PRAGMA add_parquet_key('key128', '0123456789112345');
-- result:
Success

PRAGMA add_parquet_key('key192', '012345678911234501234567');
-- result:
Success

PRAGMA add_parquet_key('key256', '01234567891123450123456789112345');
-- result:
Success

PRAGMA add_parquet_key('key256base64', 'MDEyMzQ1Njc4OTExMjM0NTAxMjM0NTY3ODkxMTIzNDU=');
-- result:
Success
```

### Writing Encrypted Parquet Files

After specifying the key (e.g., `key256`), files can be encrypted as follows:

```sql
COPY tbl TO 'tbl.parquet' (ENCRYPTION_CONFIG {footer_key: 'key256'});
```

### Reading Encrypted Parquet Files

An encrypted Parquet file using a specific key (e.g., `key256`), can then be read as follows:

```sql
COPY tbl FROM 'tbl.parquet' (ENCRYPTION_CONFIG {footer_key: 'key256'});
```

Or:

```sql
SELECT *
FROM read_parquet('tbl.parquet', encryption_config = {footer_key: 'key256'});
```

## Interoperability

SereneDB can read uniformly encrypted Parquet files written by the Arrow C++ API (e.g., via PyArrow), as long as the same encryption key is used for both the footer and all columns.

## Limitations

SereneDB's Parquet encryption currently has the following limitations.

SereneDB encrypts the footer and all columns using the `footer_key`. The Parquet specification allows encryption of individual columns with different keys, e.g.:

```sql
COPY tbl TO 'tbl.parquet'
    (ENCRYPTION_CONFIG {
        footer_key: 'key256',
        column_keys: {key256: ['col0', 'col1']}
    });
-- result:
db error: ERROR: Parquet encryption_config column_keys not yet implemented
```

However, this is unsupported at the moment and will cause an error to be thrown (for now).

## Performance Implications

Note that encryption has some performance implications: reading and writing encrypted Parquet files is slower than reading and writing the unencrypted equivalents.

