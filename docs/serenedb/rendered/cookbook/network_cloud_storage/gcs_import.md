---
layout: docu
redirect_from:
- /docs/guides/import/gcs_import
- /docs/guides/network_cloud_storage/gcs_import
- /docs/preview/guides/network_cloud_storage/gcs_import
- /docs/stable/guides/network_cloud_storage/gcs_import
title: Google Cloud Storage Import
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

SereneDB can read and write Google Cloud Storage (GCS) over HTTP(S) directly.

## Credentials and Configuration

You need to create [HMAC keys](https://console.cloud.google.com/storage/settings;tab=interoperability) and declare them:

```sql
CREATE SECRET (
    TYPE gcs,
    KEY_ID '⟨AKIAIOSFODNN7EXAMPLE⟩',
    SECRET '⟨wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY⟩'
);
```

## Querying

After setting up the GCS credentials, you can query the GCS data using:

```sql
SELECT *
FROM read_parquet('gs://⟨gcs_bucket⟩/⟨file.parquet⟩');
```

## Attaching to a Database

You can attach to a database file in read-only mode:

```sql
ATTACH 'gs://⟨gcs_bucket⟩/⟨file.duckdb⟩' AS ⟨duckdb_database⟩ (READ_ONLY);
```

<DocCallout type="note">

Databases in Google Cloud Storage can only be attached in read-only mode.

</DocCallout>

