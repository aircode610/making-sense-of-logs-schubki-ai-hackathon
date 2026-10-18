-- Load a SLICE of the remote OpenTelemetry demo logs (50 B rows on S3, ClickHouse text_bench, Apache-2.0) into the
-- corpus as dataset `otel` (plan 011): 0.1 s of every minute of part_000's first 30 minutes (~1.7M records), read in
-- place over HTTPS with row-group pruning (only the 30 one-second row groups that overlap are fetched), then the generic
-- loader. Every role tool then works on OTel data. Optional (needs internet): LOAD_OTEL=1 ./load/reload.sh
-- Mapping: component = service.name, severity = upper(SeverityText), node = k8s node, location =
-- namespace/node/pod, request_id = TraceId (the log ↔ trace correlation id).
\timing on
CREATE TEMP TABLE stage AS
SELECT row_number() OVER (ORDER BY "Timestamp") AS line_id,
       "Timestamp"::TIMESTAMP                                                       AS ts,
       nullif("ServiceName", '')                                                    AS component,
       nullif(upper("SeverityText"), '')                                            AS severity,
       nullif("ResourceAttributes"['k8s.node.name'], '')                            AS node,
       nullif(concat_ws('/', nullif("ResourceAttributes"['k8s.namespace.name'], ''),
                        nullif("ResourceAttributes"['k8s.node.name'], ''),
                        nullif("ResourceAttributes"['k8s.pod.name'], '')), '')      AS location,
       NULL::INTEGER AS status, NULL::DOUBLE AS latency_ms,
       left("Body", 2000)                                                           AS body,
       NULL::VARCHAR AS label,
       nullif("TraceId", '')                                                        AS request_id
FROM read_parquet('https://public-pme.s3.eu-west-3.amazonaws.com/text_bench/part_000.parquet')
WHERE ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:00:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:00:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:01:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:01:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:02:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:02:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:03:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:03:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:04:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:04:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:05:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:05:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:06:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:06:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:07:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:07:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:08:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:08:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:09:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:09:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:10:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:10:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:11:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:11:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:12:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:12:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:13:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:13:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:14:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:14:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:15:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:15:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:16:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:16:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:17:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:17:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:18:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:18:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:19:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:19:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:20:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:20:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:21:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:21:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:22:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:22:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:23:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:23:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:24:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:24:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:25:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:25:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:26:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:26:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:27:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:27:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:28:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:28:00.1+00') OR
      ("Timestamp" >= TIMESTAMPTZ '2025-09-23 00:29:00+00' AND "Timestamp" < TIMESTAMPTZ '2025-09-23 00:29:00.1+00');
\set ds otel
\set pbase 600000
\set title 'OpenTelemetry demo app logs (slice of 1 B remote records)'
\set description 'OpenTelemetry demo (microservices webshop on Kubernetes) logs from the public text_bench Parquet on S3 (part_000 = 1 billion records, first 30 minutes of 2025-09-23). This dataset holds 0.1 s of every minute of those 30 minutes; the full files are queried in place with the remote_* tools. component = service, location = namespace/node/pod, request_id = TraceId.'
\set location_hint 'k8s namespace/node/pod'
\set id_fields 'request_id (OTel TraceId)'
\ir lib/stage_to_logs.sql
