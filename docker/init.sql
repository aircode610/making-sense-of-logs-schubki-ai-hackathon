-- One-time setup after the first `docker compose up` (re-running only errors on CREATE ROLE, harmless).
-- OTLP/HTTP uses Basic auth against catalog roles; this role is for local ingest only (otel:otel).
CREATE ROLE otel LOGIN PASSWORD 'otel';
GRANT INSERT, SELECT ON otel_logs TO otel;
GRANT INSERT, SELECT ON otel_traces TO otel;
GRANT INSERT, SELECT ON otel_metrics_gauge TO otel;
GRANT INSERT, SELECT ON otel_metrics_sum TO otel;
GRANT INSERT, SELECT ON otel_metrics_histogram TO otel;
GRANT INSERT, SELECT ON otel_metrics_exponential_histogram TO otel;
GRANT INSERT, SELECT ON otel_metrics_summary TO otel;
