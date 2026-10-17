#!/usr/bin/env bash
# Download the base corpus (BGL + OpenStack, ~770 MB) into data/raw/. Idempotent.
# Source: Loghub (Zhu et al., ISSRE 2023), Zenodo record 8196385. Keep ?download=1 and -L.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw/openstack
if [ ! -f data/raw/BGL.log ]; then
  curl -L -o data/raw/BGL.zip "https://zenodo.org/records/8196385/files/BGL.zip?download=1"
  unzip -o data/raw/BGL.zip -d data/raw && rm data/raw/BGL.zip
fi
if [ ! -f data/raw/openstack/openstack_abnormal.log ]; then
  curl -L -o data/raw/OpenStack.tar.gz "https://zenodo.org/records/8196385/files/OpenStack.tar.gz?download=1"
  tar -xzf data/raw/OpenStack.tar.gz -C data/raw/openstack && rm data/raw/OpenStack.tar.gz
fi
wc -l data/raw/BGL.log data/raw/openstack/*.log   # expect BGL 4,747,963; OpenStack 207,820 total
