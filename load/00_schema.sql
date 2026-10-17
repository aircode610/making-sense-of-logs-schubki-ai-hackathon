-- Shared schema for both datasets (contract: plans/002-bgl-load.md). Idempotent.
-- Run: psql -h localhost -p 7890 -U postgres -d postgres -f load/00_schema.sql

-- Lowercase alpha tokens, with frequency/position/norm for BM25 + phrase queries (same as otel_logs).
CREATE TEXT SEARCH DICTIONARY IF NOT EXISTS log_body_dict AS
    split_text(case := 'lower', break := 'alpha')
    WITH (frequency, position, norm);

-- One row per log line. Columns a dataset doesn't have stay NULL.
CREATE TABLE IF NOT EXISTS logs (
    dataset     VARCHAR   NOT NULL,  -- 'bgl' | 'openstack'
    line_id     BIGINT    NOT NULL,  -- line number in the raw file (per dataset/file): stable evidence id
    ts          TIMESTAMP NOT NULL,
    component   VARCHAR,             -- BGL: KERNEL, APP, ...; OpenStack: nova service
    severity    VARCHAR,             -- BGL: INFO..FAILURE; OpenStack: INFO/WARNING/ERROR/...
    node        VARCHAR,             -- BGL location (R02-M1-N0-C:J12-U11); OpenStack host
    rack        VARCHAR,             -- BGL: R02
    midplane    VARCHAR,             -- BGL: R02-M1
    request_id  VARCHAR,             -- OpenStack
    instance_id VARCHAR,             -- OpenStack
    tenant_id   VARCHAR,             -- OpenStack
    status      INTEGER,             -- OpenStack HTTP status
    latency_ms  DOUBLE,              -- OpenStack request latency
    body        VARCHAR              -- message text (full-text indexed)
) WITH (storage = 'search', optimize_top_k = 'bm25(1.2, 0.75)');

-- Text + every filter column in one index, so search and filters resolve in one pass.
CREATE INDEX IF NOT EXISTS logs_idx ON logs USING inverted (
    ts, body log_body_dict, dataset, component, severity, node, rack, midplane,
    request_id, instance_id, tenant_id, status
);

-- Ground-truth labels: evaluation only, never read by agent tools.
CREATE TABLE IF NOT EXISTS labels (
    dataset VARCHAR NOT NULL,
    line_id BIGINT  NOT NULL,
    label   VARCHAR NOT NULL
);
