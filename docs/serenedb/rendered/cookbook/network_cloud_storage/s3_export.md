---
layout: docu
redirect_from:
- /docs/guides/import/s3_export
- /docs/guides/network_cloud_storage/s3_export
- /docs/preview/guides/network_cloud_storage/s3_export
- /docs/stable/guides/network_cloud_storage/s3_export
title: S3 Parquet Export
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

To write data to S3, set up the credentials. Note that the `region` parameter should match the region of the bucket you want to access.

```sql
CREATE SECRET (
    TYPE s3,
    KEY_ID '⟨AKIAIOSFODNN7EXAMPLE⟩',
    SECRET '⟨wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY⟩',
    REGION '⟨us-east-1⟩'
);
```

<DocCallout type="tip">

If you get an IO Error (`Connection error for HTTP HEAD`), configure the endpoint explicitly via `ENDPOINT 's3.⟨your-region⟩.amazonaws.com'`.

</DocCallout>

SereneDB cannot read the AWS credential chain (`PROVIDER credential_chain`): that provider comes from DuckDB's `aws` extension, which is not built in. Pass keys as above, or use one of the other methods in [AWS Credentials](../../configuration/aws_credentials.md).

Once the S3 credentials are configured, Parquet files can be written to S3 using the following command:

```sql
COPY table_name TO 's3://s3-bucket/filename.parquet';
```

Similarly, Google Cloud Storage (GCS) is supported through the Interoperability API.
You need to create [HMAC keys](https://console.cloud.google.com/storage/settings;tab=interoperability) and provide the credentials as follows:

```sql
CREATE SECRET (
    TYPE gcs,
    KEY_ID '⟨AKIAIOSFODNN7EXAMPLE⟩',
    SECRET '⟨wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY⟩'
);
```

After setting up the GCS credentials, you can export using:

```sql
COPY table_name TO 'gs://gcs_bucket/filename.parquet';
```

