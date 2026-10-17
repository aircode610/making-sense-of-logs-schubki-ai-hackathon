---
layout: docu
redirect_from:
- /docs/guides/import/fastly_object_storage_import
- /docs/guides/network_cloud_storage/fastly_object_storage_import
- /docs/preview/guides/network_cloud_storage/fastly_object_storage_import
- /docs/stable/guides/network_cloud_storage/fastly_object_storage_import
title: Fastly Object Storage Import
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

For Fastly Object Storage, the [S3 Compatibility API](https://docs.fastly.com/products/object-storage) lets SereneDB read and write from Fastly buckets over HTTP(S) directly.

## Credentials and Configuration

You will need to [generate an S3 auth token](https://docs.fastly.com/en/guides/working-with-object-storage#creating-an-object-storage-access-key) and create an `S3` secret in SereneDB:

```sql
CREATE SECRET my_secret (
    TYPE s3,
    KEY_ID '⟨AKIAIOSFODNN7EXAMPLE⟩',
    SECRET '⟨wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY⟩',
    URL_STYLE 'path',
    REGION '⟨us-east⟩',
    ENDPOINT '⟨us-east⟩.object.fastlystorage.app' -- see note below
);
```

* The `ENDPOINT` needs to point to the [Fastly endpoint for the region](https://docs.fastly.com/en/guides/working-with-object-storage#working-with-the-s3-compatible-api) you want to use (e.g., `eu-central.object.fastlystorage.app`).
* `REGION` must use the same region mentioned in `ENDPOINT`.
* `URL_STYLE` needs to use `path`.

## Querying

After setting up the Fastly Object Storage credentials, you can query the data there using SereneDB's built-in methods, such as `read_csv` or `read_parquet`:

```sql
SELECT * FROM 's3://⟨fastly-bucket-name⟩/(file).csv';

SELECT * FROM read_parquet('s3://⟨fastly-bucket-name⟩/⟨file⟩.parquet');
```

