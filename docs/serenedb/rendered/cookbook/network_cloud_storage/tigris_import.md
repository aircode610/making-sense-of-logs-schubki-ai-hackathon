---
layout: docu
title: Tigris Import
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

For [Tigris](https://www.tigrisdata.com/), the [S3-compatible API](https://www.tigrisdata.com/docs/api/s3/) lets SereneDB read and write from Tigris buckets over HTTP(S) directly.

## Credentials and Configuration

You will need to [generate an access key pair](https://www.tigrisdata.com/docs/iam/) and create an `S3` secret in SereneDB:

```sql
CREATE SECRET my_secret (
    TYPE s3,
    KEY_ID '⟨tid_xxxxxxxxxxxx⟩',
    SECRET '⟨tsec_xxxxxxxxxxxxxxxxxxxxxxxx⟩',
    REGION 'auto',
    ENDPOINT 'fly.storage.tigris.dev'
);
```

* A single endpoint (`fly.storage.tigris.dev`) serves all regions; requests are routed to the Tigris region nearest the caller. `REGION` is required for request signing but is not used for routing — set it to `auto`.
* `URL_STYLE` does not need to be set. Tigris uses virtual-hosted-style URLs, which is SereneDB's default for `TYPE s3`.

<DocCallout type="tip">

When SereneDB runs on a [Fly.io](https://fly.io/) Machine, requests to `fly.storage.tigris.dev` stay on Fly's internal network and are served from the same region as the Machine when possible.

</DocCallout>

## Querying

After setting up the Tigris credentials, you can query the data using SereneDB's built-in methods, such as `read_csv` or `read_parquet`:

```sql
SELECT * FROM 's3://⟨tigris-bucket-name⟩/⟨file⟩.csv';

SELECT * FROM read_parquet('s3://⟨tigris-bucket-name⟩/⟨file⟩.parquet');
```

