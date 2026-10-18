# data/

- `raw/` (gitignored): `./scripts/download_data.sh` → `BGL.log` (4,747,963 lines, 2005-06-03 → 2006-01-04) and
  `openstack/` (`openstack_normal1.log`, `openstack_normal2.log`, `openstack_abnormal.log`, `anomaly_labels.txt`;
  207,820 lines; nova-api 102,868 · nova-compute 104,086 · nova-scheduler 866).
- Optional extra sets (`download_data.sh --all`, `hdfs`, `linux healthapp`): `zookeeper/`, `apache/`, `ssh/`, `hdfs/`,
  `linux/` (25,567 lines; read as latin-1: some lines carry raw attack bytes) and `healthapp/` (253,395 lines). Linux and
  HealthApp are the plan-012 "unseen" sets: loaded with a loader file + a `*` ownership row only.
- `pattern_judgments_<ds>.csv`, `pattern_traits_<ds>.csv`, `pattern_vectors.parquet`, `burst_summaries.csv`
  (committed): AI outputs computed inside SereneDB (Jev / embeddings / summaries), so a clean checkout needs no key.
- `ownership.csv` (committed): **fictional** component → team mapping for team-lead / manager aggregations.
  BGL component = 9th field of a line (KERNEL, APP, DISCOVERY, MMCS, HARDWARE, MONITOR, LINKCARD, CMCS, BGLMASTER, …);
  OpenStack component = the nova service from the file prefix. Since plan 057 rows are optional: components without
  a row get an inferred owner (below), and only those with no owner at confidence ≥ 0.6 are grouped as `unowned`.
- `ownership_rules.csv` (committed, plan 057): `priority, match_type (exact|prefix|regex), pattern, area, source_ref`:
  public name lists → functional area (OpenStack service-types authority, Kubernetes components, ~50 common programs).
  Names are normalised first (lower case, no `[pid]`, `(pam_unix)`, trailing `-<n>` / `.service`).
- `area_teams.csv` (committed, plan 057): area → team, **fictional** like `ownership.csv`; the only place inferred
  team names come from.
- `component_areas_<ds>.csv` (committed, plan 057): Jev's functional area per component with its probability
  (`scripts/judge_areas.py`, one `ai_system_one` call per component inside SereneDB).

Labels (for evaluation only, never shown to the agent as answers): BGL first field `-` = normal, otherwise alert
category; OpenStack `anomaly_labels.txt` lists 3 VM instance ids with injected anomalies (in `openstack_abnormal.log`).

Citation: Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023;
BGL: Oliner & Stearley, *What Supercomputers Say*, DSN 2007.
