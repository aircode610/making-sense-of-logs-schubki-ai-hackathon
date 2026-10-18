-- Jev pattern judgments (plan 006) + pattern traits (plan 011), loaded from the committed CSVs (regenerate:
-- scripts/judge_patterns.sh and scripts/judge_traits.py, need a key). Joined on (dataset, component, template), so they
-- survive pattern-id renumbering. Run after 95_patterns_episodes.sql.
-- p_problem (DECISIONS H18, generalized in plan 011) = max(p_fault × (1 − p_dump), p_threat): a real fault OR a security
-- event (a failed login attack is not a hardware/software fault, but it is the problem of an SSH log).
\timing on
DROP TABLE IF EXISTS pattern_traits CASCADE;
CREATE TABLE pattern_traits AS
SELECT t.dataset, t.pattern_id, x.p_threat, x.cause, x.cause_confidence, x.actionable, x.role, nullif(x.owner_hint, '') AS owner_hint,
       x.owner_confidence
FROM read_csv('/data/pattern_traits_*.csv', header = true, quote = '"', escape = '"', auto_detect = false,
              columns = {'dataset': 'VARCHAR', 'component': 'VARCHAR', 'template': 'VARCHAR', 'pattern_id': 'INTEGER',
                         'p_threat': 'DOUBLE', 'cause': 'VARCHAR', 'cause_confidence': 'DOUBLE', 'actionable': 'DOUBLE',
                         'role': 'VARCHAR', 'owner_hint': 'VARCHAR', 'owner_confidence': 'DOUBLE'}) x
JOIN pattern_templates t ON t.dataset = x.dataset AND t.component IS NOT DISTINCT FROM x.component
                        AND t.template = coalesce(x.template, '');

DROP TABLE IF EXISTS pattern_judgments CASCADE;
CREATE TABLE pattern_judgments AS
SELECT t.dataset, t.pattern_id, j.p_fault, j.p_dump, j.p_corrected, j.kind, j.kind_confidence, tr.p_threat,
       greatest(j.p_fault * (1 - j.p_dump), coalesce(tr.p_threat, 0)) AS p_problem
FROM read_csv('/data/pattern_judgments_*.csv', header = true, quote = '"', escape = '"', auto_detect = false,
              columns = {'dataset': 'VARCHAR', 'component': 'VARCHAR', 'template': 'VARCHAR', 'pattern_id': 'INTEGER',
                         'p_fault': 'DOUBLE', 'p_dump': 'DOUBLE', 'p_corrected': 'DOUBLE', 'kind': 'VARCHAR',
                         'kind_confidence': 'DOUBLE'}) j
JOIN pattern_templates t ON t.dataset = j.dataset AND t.component IS NOT DISTINCT FROM j.component
                        AND t.template = coalesce(j.template, '')
LEFT JOIN pattern_traits tr ON tr.dataset = t.dataset AND tr.pattern_id = t.pattern_id;
