#!/usr/bin/env bash
# Stream a GAIA business CSV to stdout WITHOUT extracting it (the split zip breaks `unzip`/`zip -s 0`,
# and the August file is 22.7GB uncompressed). bsdtar reads the concatenated split parts as one stream.
#   scripts/gaia_stream.sh webservice1_2021-07 | head          (14.57M lines, 1.5GB)
#   scripts/gaia_stream.sh 2021-08 | head                       (22.7GB, all services, August 2021)
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)/dataset/raw/gaia/business"
cat "$D"/business_split.z{01..45} "$D"/business_split.zip | tar -xOf - "business/business_table_$1.csv"
