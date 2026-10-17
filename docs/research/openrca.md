# OpenRCA notes

- Repo: https://github.com/microsoft/OpenRCA · data: Google Drive folder linked in README (~80GB disk recommended for all)
- Layout: `dataset/{Bank|Telecom|Market/cloudbed-1|Market/cloudbed-2}/{query.csv, record.csv, telemetry/{YYYY_MM_DD}/{log,metric,trace}/*.csv}`
- **Timezone: all records UTC+8.**
- 335 queries total (Bank 136, Market cb1 70, cb2 78, Telecom 51). 7 task types = combinations of
  {occurrence time (±1 min), component, reason}; query gives time range + number of failures.
- Prediction format: JSON `{"1": {"root cause occurrence datetime", "root cause component", "root cause reason"}}`;
  scored by `python -m main.evaluate -p pred.csv -q query.csv -r report.csv`.
- Baseline RCA-agent (Claude 3.5) archive mean score: Bank 0.225, Market cb1 0.125, cb2 0.128, Telecom 0.281
  (`rca/archive/agent-*.csv` also has instruction + groundtruth per query). Paper best ≈ 11.34% fully correct.

## Candidate sets (closed → Jev Choice)
- **Bank** reasons (8): high CPU usage, high memory usage, network latency, network packet loss, high disk I/O read usage,
  high disk space usage, high JVM CPU load, JVM Out of Memory (OOM) Heap. Components (14): apache01/02, Tomcat01-04, MG01/02, IG01/02, Mysql01/02, Redis01/02.
- **Market** reasons (15): container {CPU load, memory load, network packet retransmission, network packet corruption,
  network latency, packet loss, process termination, read I/O load, write I/O load}, node {CPU load, CPU spike, memory consumption,
  disk read I/O, disk write I/O, disk space consumption}. Components: node-1..6, 40 pods (`<svc>-0/1/2`, `<svc>2-0`), 10 services.
- **Telecom** reasons (5): CPU fault, network delay, network loss, db connection limit, db close. Components: os_001-022, docker_001-008, db_001-013. **No logs.**

## Telemetry schemas
- Logs: `log_id,timestamp(s),cmdb_id,log_name,value` — Bank `log_service.csv` (mostly JVM GC lines); Market `log_proxy.csv` + `log_service.csv` (app logs).
- Metrics: `metric_app.csv` (timestamp,rr,sr,cnt,mrt,tc), `metric_container.csv` (timestamp,cmdb_id,kpi_name,value) [+ more in Market].
- Traces: `trace_span.csv` (timestamp(ms),cmdb_id,parent_id,span_id,trace_id,duration) — Bank; Market has its own columns.
