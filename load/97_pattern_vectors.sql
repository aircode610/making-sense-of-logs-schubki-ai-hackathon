-- Pattern index (plan 011): one row per pattern with its template text AND its embedding in ONE inverted index
-- (full-text + IVF vector), for similar_patterns / find_patterns (lexical, semantic and hybrid). Vectors come from
-- data/pattern_vectors.parquet (scripts/embed_patterns.py, gemini-embedding-001, 768 dims); joined on
-- (dataset, component, template) so they survive id renumbering. Patterns without a stored vector keep emb NULL.
\timing on
DROP TABLE IF EXISTS pattern_index CASCADE;
CREATE TABLE pattern_index (
    dataset    VARCHAR NOT NULL,
    pattern_id INTEGER NOT NULL,
    component  VARCHAR,
    template   VARCHAR,
    emb        FLOAT[768]
) WITH (storage = 'search');
CREATE INDEX pattern_index_idx ON pattern_index USING inverted (
    dataset, pattern_id, component, template log_body_dict, emb ivf (metric = 'cosine'));
INSERT INTO pattern_index
SELECT p.dataset, p.pattern_id, p.component, p.template, v.emb::FLOAT[768]
FROM patterns p
LEFT JOIN read_parquet('/data/pattern_vectors*.parquet') v  -- + per-dataset files of scripts/embed_patterns.py <ds> (plan 057)
  ON v.dataset = p.dataset AND v.component IS NOT DISTINCT FROM p.component AND v.template = p.template;
VACUUM (REFRESH_TABLE) pattern_index;

-- Stored model summaries of the top problem bursts (scripts/summarize_bursts.py, ai_summarize_agg): context, not evidence.
DROP TABLE IF EXISTS burst_summaries CASCADE;
CREATE TABLE burst_summaries AS
SELECT * FROM read_csv('/data/burst_summaries.csv', header = true, quote = '"', escape = '"', auto_detect = false,
    columns = {'dataset': 'VARCHAR', 'pattern_id': 'INTEGER', 'burst_no': 'INTEGER', 'summary': 'VARCHAR',
               'model': 'VARCHAR', 'created': 'VARCHAR'});
