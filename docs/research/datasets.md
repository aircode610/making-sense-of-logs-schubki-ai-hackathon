# Datasets (log-based, with ground truth) — engineer role first

| Pick | Dataset | Logs-only? | Ground truth | Size | Get it |
|---|---|---|---|---|---|
| ⭐ main | **GAIA MicroSS** (CloudWise) — QR-code login microservices, 2 continuous weeks (Jul 2021, + Aug) | ✅ business logs (+ run/system logs) | `run/` = anomaly injection records (service, type, start, duration). LogKG paper: 1,083 log-diagnosable failures, 4 types: login failure (network congestion), memory anomaly, file not found (misconfig), access permission denied (bug) | business ≈2.4GB (46-part split zip), run.zip 0.8MB | https://github.com/CloudWise-OpenSource/GAIA-DataSet/tree/main/MicroSS (`business/`, `run/`) |
| warm-up | **Loghub Hadoop** — MapReduce jobs (WordCount, PageRank) | ✅ | per-job label: normal / machine down / network disconnection / disk full (`abnormal_label.txt`; see loghub issue #56 for label quirks) | ~48MB, ~55 jobs | https://zenodo.org/records/8196385/files/Hadoop.zip?download=1 |
| calibration n | **Loghub BGL** — Blue Gene/L | ✅ | per-line alert label + alert category (first column) | 4.7M lines, 709MB | https://zenodo.org/records/8196385/files/BGL.zip?download=1 |
| code faults | **RCAEval RE3** — Online Boutique / Sock Shop / Train Ticket | logs + metrics + traces | root-cause service + indicator; code-level faults with **stack traces in logs** | 90 cases | https://github.com/phamquiluan/RCAEval (HF parquet per case) |
| secondary | **OpenRCA** Bank / Market | logs + metrics + traces (metric-heavy) | record.csv: time, component, reason | GBs | see `openrca.md` |
| small | GAIA Companion `log.zip` | ✅ | log semantic anomaly labels, NER, parsing | 8MB | https://github.com/CloudWise-OpenSource/GAIA-DataSet/tree/main/Companion_Data |

Why GAIA main: logs-first (matches brief), multi-service, closed-set answers (service × failure type × time), and a
continuous 2-week timeline that we can reuse later for lead (recurrence) and manager (impact) questions.
Why BGL: large n → meaningful calibration stats (ECE/Brier, reliability diagrams) for Jev vs LLM vs classifier.

## OpenTelemetry format
- No mature labeled log dataset ships natively as OTLP. Candidates found:
  - **RCA100** (OTel Demo Store on K8s, 103 chaos-injected incidents, 4-layer ground truth incl. **evidence checkpoints**):
    https://www.aiops.cn/gitlab/aiops-live-benchmark/agenticopseval/-/tree/57c36fa46fb2f4dec19b5f5ca9cbf5a90f9c9e00/RCA100
    (paper https://arxiv.org/abs/2606.29193) — access/format NOT verified (page didn't load for us).
  - smithclay/otel-demo-telemetry (HF, OTLP→Parquet) — real OTel but **unlabeled** healthy traffic.
- Decision: choose dataset by label quality, then **replay it through SereneDB's OTLP endpoint** (`/v1/logs` → `otel_logs`)
  with original timestamps. Conversion is trivial and it exercises the real generic ingest path (= the product's input contract).
  GAIA mapping: datetime→timestamp, service→service_name, `| INFO |`→severity_text/number, span-like id→span_id, rest→body.

## Local status (2026-10-09)
| Dataset | Where | State |
|---|---|---|
| Loghub Hadoop | `dataset/hadoop/` (48MB, 55 app dirs + `abnormal_label.txt`) | ✅ ready. Labels imbalanced (machine down dominates; normal 11) |
| Loghub BGL | `dataset/bgl/BGL.log` (709MB, 4.7M lines; first column `-` = normal, else alert category) | ✅ ready |
| GAIA run (injection records = ground truth) | `dataset/gaia/run/run/run_table_2021-0{7,8}.csv` (~73k lines) | ✅ ready |
| GAIA business logs | `dataset/raw/gaia/business/*.z01..z45+zip` (all 46 parts verified vs GitHub sha) | ✅ via streaming (August fully streamed: 208M lines, days 08-01..08-31, no tar errors; header `id,datetime,service,message`). `unzip`/`zip -s 0`/`zip -FF` all fail on this split zip → **stream with `scripts/gaia_stream.sh <name>`** (bsdtar). GitHub only has `webservice1_2021-07` (1.5GB, 14.57M lines, verified) and `2021-08` (22.7GB, all services). Disk has ~27GB free → never extract August; stream + filter/load. |
