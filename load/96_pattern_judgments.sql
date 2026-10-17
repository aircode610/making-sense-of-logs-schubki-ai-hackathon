-- Jev pattern judgments (plan 006), loaded from the committed CSVs (regenerate: scripts/judge_patterns.sh, needs a key).
-- Joined on (dataset, component, template), so they survive pattern-id renumbering. Run after 95_patterns_episodes.sql.
\timing on
DROP TABLE IF EXISTS pattern_judgments;
CREATE TABLE pattern_judgments AS
SELECT t.dataset, t.pattern_id, j.p_fault, j.p_dump, j.p_corrected, j.kind, j.kind_confidence
FROM read_csv('/data/pattern_judgments_*.csv', header = true, quote = '"', escape = '"', auto_detect = false,
              columns = {'dataset': 'VARCHAR', 'component': 'VARCHAR', 'template': 'VARCHAR', 'pattern_id': 'INTEGER',
                         'p_fault': 'DOUBLE', 'p_dump': 'DOUBLE', 'p_corrected': 'DOUBLE', 'kind': 'VARCHAR',
                         'kind_confidence': 'DOUBLE'}) j
JOIN pattern_templates t ON t.dataset = j.dataset AND t.component = j.component AND t.template = coalesce(j.template, '');
