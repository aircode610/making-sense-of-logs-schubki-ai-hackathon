---
layout: docu
redirect_from:
- /docs/guides/import/http_import
- /docs/guides/network_cloud_storage/http_import
- /docs/preview/guides/network_cloud_storage/http_import
- /docs/stable/guides/network_cloud_storage/http_import
title: HTTP Parquet Import
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

SereneDB can read Parquet files over `http(s)`:

```sql
SELECT * FROM read_parquet('https://⟨domain⟩/path/to/file.parquet');
```

For example:

```sql
SELECT * FROM read_parquet('https://⟨domain⟩/data/prices.parquet');
```

Moreover, the `read_parquet` function itself can also be omitted thanks to the replacement scan mechanism:

```sql
SELECT * FROM 'https://⟨domain⟩/data/holdings.parquet';
```

