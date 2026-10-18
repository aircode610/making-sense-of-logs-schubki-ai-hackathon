#!/usr/bin/env bash
# Download the base corpus (BGL + OpenStack, ~770 MB) into data/raw/, plus optional extra Loghub sets. Idempotent.
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

# Extra Loghub datasets (plan 011: generality test; small, different formats). `--all` or name them:
#   scripts/download_data.sh zookeeper apache ssh      (+ hdfs: 1.5 GB, 11M lines, the scale test)
extra() {  # name, zenodo file
  [ -d "data/raw/$1" ] && return
  mkdir -p "data/raw/$1"
  curl -L -o "data/raw/$1/$2" "https://zenodo.org/records/8196385/files/$2?download=1"
  tar -xzf "data/raw/$1/$2" -C "data/raw/$1" && rm "data/raw/$1/$2"
  find "data/raw/$1" -name '*.log' -exec wc -l {} +
}
for ds in "$@"; do
  case "$ds" in
    --all) extra zookeeper Zookeeper.tar.gz; extra apache Apache.tar.gz; extra ssh SSH.tar.gz ;;
    zookeeper) extra zookeeper Zookeeper.tar.gz ;;
    apache) extra apache Apache.tar.gz ;;
    ssh) extra ssh SSH.tar.gz ;;
    hdfs)  # 1.5 GB zip, 11M lines: the scale test (not part of --all)
      if [ ! -f data/raw/hdfs/HDFS.log ]; then
        mkdir -p data/raw/hdfs
        curl -L -o data/raw/hdfs/HDFS_v1.zip "https://zenodo.org/records/8196385/files/HDFS_v1.zip?download=1"
        unzip -o -q data/raw/hdfs/HDFS_v1.zip -d data/raw/hdfs && rm data/raw/hdfs/HDFS_v1.zip
      fi ;;
    *) echo "unknown dataset $ds" >&2; exit 1 ;;
  esac
done
