-- Shared schema for every dataset (contract: plans/002-bgl-load.md, pattern_id: plan 004, generic columns: plan 011).
-- DROPS and recreates the tables (SereneDB can't ALTER a search table): a full reload is `./load/reload.sh`.
-- Run: psql -h localhost -p 7890 -U postgres -d postgres -f load/00_schema.sql
-- CASCADE: the table macros of load/97_macros.sql depend on these tables; reload.sh recreates them at the end.
DROP TABLE IF EXISTS logs CASCADE;
DROP TABLE IF EXISTS labels CASCADE;
DROP TABLE IF EXISTS pattern_templates CASCADE;
DROP TABLE IF EXISTS datasets CASCADE;
DROP TABLE IF EXISTS ingest_runs CASCADE;
DROP TABLE IF EXISTS ingest_unparsed CASCADE;

-- Lowercase alpha tokens, with frequency/position/norm for BM25 + phrase queries (same as otel_logs), and offset so
-- ts_highlight can mark phrase matches (plan 011). Recreated on every reload so its flags always match this file.
DROP TEXT SEARCH DICTIONARY IF EXISTS log_body_dict CASCADE;
CREATE TEXT SEARCH DICTIONARY log_body_dict AS
    split_text(case := 'lower', break := 'alpha')
    WITH (frequency, position, norm, offset);

-- Hierarchical location ('a/a-b/a-b-c') is indexed as every ancestor path, so one predicate filters
-- at any level (query with ts_tokenize(path, 'keyword') for an exact level).
DROP TEXT SEARCH DICTIONARY IF EXISTS location_dict CASCADE;
CREATE TEXT SEARCH DICTIONARY location_dict AS expand_path(delimiter := '/');

-- Query-time only (not attached to a column): expands a search word to its log-jargon synonyms, analyzed like
-- log_body_dict, so `body @@ ts_tokenize('disconnected', 'log_synonyms')` also finds "severed" / "lost".
-- Generic operations vocabulary, deliberately not taken from one dataset.
DROP TEXT SEARCH DICTIONARY IF EXISTS log_synonyms CASCADE;
CREATE TEXT SEARCH DICTIONARY log_synonyms AS
    split_text(case := 'lower', break := 'alpha') | expand_solr_synonyms('error, errors, err, fail, failed, failure, failures, fault
fatal, critical, panic, crash, crashed
disconnected, disconnect, severed, lost, dropped, closed, reset, broken
timeout, timed, expired, unresponsive, hang, hung
denied, refused, rejected, unauthorized, forbidden, invalid
killed, terminated, aborted, abort, stopped, exit, exited
memory, ram, ddr, dimm, ecc
disk, storage, filesystem, mount, volume, io
network, link, socket, connection, tcp, port
restart, restarted, reboot, rebooted, recovered
slow, latency, delay, delayed')
    WITH (frequency, position);

-- Dataset registry (plan 011): one row per loaded dataset, written by its loader. Tools read it to validate `dataset`
-- and to describe the corpus, so a new dataset needs no tool or agent change.
CREATE TABLE datasets (
    dataset          VARCHAR NOT NULL,   -- short name used everywhere ('bgl', 'openstack', 'zookeeper', ...)
    title            VARCHAR,            -- one line for people and for the agent's corpus description
    description      VARCHAR,            -- what the logs are, where they come from, quirks (assumed year, ...)
    -- What each generic column means in THIS dataset (plan 012); NULL = the dataset does not fill it. Tools show these
    -- texts in their descriptions and in describe_corpus, so an agent knows what to pass for each dataset.
    node_meaning     VARCHAR,            -- e.g. 'compute / I/O node R02-M1-N0-C:J12-U11', 'host name'
    location_meaning VARCHAR,            -- e.g. 'rack/midplane/node', 'namespace/node/pod'
    request_meaning  VARCHAR,            -- e.g. 'nova request id (req-…)', 'trace id', 'block id (blk_…)'
    object_meaning   VARCHAR,            -- e.g. 'VM instance uuid (followed across requests)'
    status_meaning   VARCHAR,            -- e.g. 'HTTP status of API requests'
    duration_meaning VARCHAR,            -- e.g. 'HTTP request time; VM lifecycle step times (Took N seconds)'
    pattern_base     INTEGER             -- pattern_id = pattern_base + rank: ids never collide across datasets
);

-- One row per log line. Columns a dataset doesn't have stay NULL.
CREATE TABLE logs (
    dataset     VARCHAR   NOT NULL,  -- see datasets
    line_id     BIGINT    NOT NULL,  -- line number in the raw file (per dataset/file): stable evidence id
    ts          TIMESTAMP NOT NULL,
    component   VARCHAR,             -- the emitting program / service / class (dataset-defined)
    severity    VARCHAR,             -- upper case as logged (INFO .. FATAL); NULL when the format has no level
    node        VARCHAR,             -- the emitting machine / host (datasets.node_meaning)
    location    VARCHAR,             -- hierarchical path, '/'-separated, coarse → fine (datasets.location_meaning)
    request_id  VARCHAR,             -- one request / session / trace / block (datasets.request_meaning)
    object_id   VARCHAR,             -- a long-lived thing followed across requests, e.g. a VM (datasets.object_meaning)
    status      INTEGER,             -- status code where logged (datasets.status_meaning)
    duration_ms DOUBLE,              -- a measured duration in the line (datasets.duration_meaning)
    entities    VARCHAR[],           -- typed values pulled out of the message: 'ip:10.0.0.1', 'uuid:…', 'path:/a/b'
    body        VARCHAR,             -- message text (full-text indexed)
    pattern_id  INTEGER              -- log template id (patterns table; plan 004)
) WITH (storage = 'search', optimize_top_k = 'bm25(1.2, 0.75)');

-- Text + every filter column in one index, so search and filters resolve in one pass.
CREATE INDEX logs_idx ON logs USING inverted (
    ts, body log_body_dict, dataset, component, severity, node, location location_dict,
    request_id, object_id, status, duration_ms, entities, pattern_id
);

-- Auto-detected loaders (plan 057 part 3, load/gen/*.sql written by scripts/ingest.py): one row per generated dataset
-- with the format chosen and how well it fit, and the line ids its regexes did not match (kept as continuation lines).
-- Hand-written loaders write nothing here. Read by the ingest_report tool.
CREATE TABLE ingest_runs (
    dataset        VARCHAR NOT NULL,
    file           VARCHAR,   -- raw file, relative to the repo
    format         VARCHAR,   -- lnav format name (formats/lnav/<format>.json)
    format_title   VARCHAR,
    sample_lines   INTEGER,   -- first N lines scored
    sample_matched INTEGER,   -- of those, matched by the chosen format
    ts_format      VARCHAR,   -- strptime format that parsed the most sample timestamps
    year_assumed   INTEGER,   -- set when the format logs no year
    field_map      VARCHAR,   -- JSON: role → format field (timestamp, level, body, component, node, request_id, status)
    candidates     VARCHAR,   -- JSON: top formats with their sample coverage
    regexes_skipped INTEGER   -- lnav regexes RE2 cannot compile (look-around), over all formats
);
CREATE TABLE ingest_unparsed (dataset VARCHAR NOT NULL, line_id BIGINT NOT NULL);

-- Ground-truth labels: evaluation only, never read by agent tools.
CREATE TABLE labels (
    dataset VARCHAR NOT NULL,
    line_id BIGINT  NOT NULL,
    label   VARCHAR NOT NULL
);

-- Template text per pattern_id, written by each loader (plan 004); aggregates live in load/95_patterns_episodes.sql.
CREATE TABLE pattern_templates (
    dataset    VARCHAR NOT NULL,
    pattern_id INTEGER NOT NULL,
    component  VARCHAR,
    template   VARCHAR
);

-- Typed values in a message, generic across formats (plan 011): IPv4, UUID, filesystem path, URL.
CREATE OR REPLACE MACRO extract_entities(b) AS list_distinct(list_concat(
    list_transform(regexp_extract_all(coalesce(b, ''), '(?:^|[^\d.])(\d{1,3}(?:\.\d{1,3}){3})(?:[^\d.]|$)', 1), x -> 'ip:' || x),
    list_transform(regexp_extract_all(coalesce(b, ''), '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'), x -> 'uuid:' || lower(x)),
    list_transform(regexp_extract_all(coalesce(b, ''), '(?:^|[\s=:(\[''"])((?:/[\w.\-]+){2,})', 1), x -> 'path:' || x),
    list_transform(regexp_extract_all(coalesce(b, ''), 'https?://[^\s"''<>]+'), x -> 'url:' || x)));

-- Generic template mask for new datasets (plan 011; BGL / OpenStack keep their own masks so pattern ids and stored
-- judgments stay valid). Most specific first, then merge runs of masks and squeeze spaces.
CREATE OR REPLACE MACRO mask_template(b) AS regexp_replace(regexp_replace(regexp_replace(regexp_replace(
    regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
        coalesce(b, ''),
        '([_=:])-(\d)', '\1\2', 'g'),                         -- signed ids (blk_-123 = blk_123 as a template)
        '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '<UUID>', 'g'),
        'https?://[^\s"''<>]+', '<URL>', 'g'),
        '\d{1,3}(\.\d{1,3}){3}(:\d+)?', '<IP>', 'g'),
        '([0-9A-Fa-f]{2}:){3,}[0-9A-Fa-f]{1,2}', '<MAC>', 'g'),
        '\b[A-Z0-9]*(?:[A-Z][A-Z0-9]*[0-9]|[0-9][A-Z0-9]*[A-Z])[A-Z0-9]*\b', '<ID>', 'g'),   -- L9ECAV7KIM, 2ZYFJ3GM2N
        '\b[A-Za-z]+[0-9]{2,}[A-Za-z0-9]*\b', '<ID>', 'g'),                                    -- conn21234, worker17
        '(/[\w.\-<>]+){2,}/?', '<PATH>', 'g'),
        '(^|[^A-Za-z])(0x)?[0-9a-fA-F]{6,}', '\1<HEX>', 'g'),
        '(^|[^A-Za-z<])\d+(\.\d+)*', '\1<N>', 'g'),
        '(<N>|<HEX>)([:./\-x,]*(<N>|<HEX>))+', '<N>', 'g'),
        '\s+', ' ', 'g');
