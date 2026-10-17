---
layout: docu
redirect_from:
    - /docs/guides/network_cloud_storage/duckdb_over_https_or_s3
    - /docs/preview/guides/network_cloud_storage/duckdb_over_https_or_s3
    - /docs/stable/guides/network_cloud_storage/duckdb_over_https_or_s3
title: Attach to a DuckDB Database over HTTPS or S3
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";
import DocCallout from "@site/src/components/DocCallout";

You can establish a read-only connection to a DuckDB database via HTTPS or the S3 API. Access over HTTP(S) and S3 is built into SereneDB.

## Attaching to a Database over HTTPS

To connect to a DuckDB database via HTTPS, use the `ATTACH` statement as follows:

```sql
ATTACH 'https://blobs.duckdb.org/databases/stations.duckdb' AS stations_db;
```

Then, the database can be queried using:

```sql
SELECT count(*) AS num_stations
FROM db111.stations;
-- result:
num_stations
2
```

## Attaching to a Database over the S3 API

To connect to a DuckDB database via the S3 API, [configure the authentication](./s3_import.md#credentials-and-configuration) for your bucket (if required).
Then, use the `ATTACH` statement as follows:

```sql
ATTACH 's3://my-bucket/stations.duckdb' AS stations_db;
```

The database can be queried using:

```sql
SELECT count(*) AS num_stations
FROM db112.stations;
-- result:
num_stations
2

DETACH IF EXISTS db112;

DETACH IF EXISTS db111;
```

<DocCallout type="tip">

Connecting to S3-compatible APIs such as the [Google Cloud Storage (`gs://`)](./gcs_import.md#attaching-to-a-database) is also supported.

</DocCallout>

## Limitations

-   Only read-only connections are allowed, writing the database via the HTTPS protocol or the S3 API is not possible.

