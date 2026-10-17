-- Jev judges every log pattern once (plan 006): "real fault or routine output?" + 3 helper questions.
-- Needs the typesafe secret (./docker/secrets.sh). Run via scripts/judge_patterns.sh, which writes
-- data/pattern_judgments_bgl.csv (committed, so a clean checkout needs no key).
-- State = component, severity, masked template, one real example line. Criteria examples are generic log wording,
-- deliberately NOT taken from BGL (no pattern text appears in them), so the judgment is not fitted to this corpus.
-- :where is set by the caller (all patterns, or a dry-run subset).
SET sdb_ai_max_api_calls_per_query = 5000;

COPY (
SELECT p.dataset, p.component, p.template, p.pattern_id,
       round((j).fault, 4)          AS p_fault,
       round((j).dump, 4)           AS p_dump,
       round((j).corrected, 4)      AS p_corrected,
       (j).kind.choice              AS kind,
       round((j).kind.confidence, 4) AS kind_confidence
FROM (
    SELECT p.*, ai_system_one(
        'component: ' || p.component || chr(10) ||
        'severity: ' || p.severity || chr(10) ||
        'message template (numbers and ids masked): ' || p.template || chr(10) ||
        'example message: ' || coalesce(l.body, ''),
        questions := '{
          "fault": {
            "type": "noul",
            "instructions": "Does `message` report that hardware or software actually failed, crashed, lost a function, or aborted an operation?",
            "criteria": {
              "true": {"description": "Something broke or stopped working.",
                       "examples": ["segmentation fault, process terminated", "uncorrectable memory error on DIMM 3",
                                    "connection to storage server lost", "job aborted after timeout", "disk controller not responding"]},
              "false": {"description": "Routine output: status or progress notes, counters and statistics, configuration or register values printed for diagnosis, errors that were detected and corrected automatically, normal service start or stop.",
                        "examples": ["2 single-bit memory errors corrected", "retrying request, attempt 2 succeeded",
                                     "r7 = 0x00000000", "cpu temperature 54 C", "service sshd started"]}
            }
          },
          "dump": {
            "type": "noul",
            "instructions": "Is `message` one field of a multi-line diagnostic dump (a single register, flag or status value printed as part of a longer listing) rather than a sentence describing an event?",
            "criteria": {
              "true": {"description": "A field name followed by its value, as in a table of registers or status flags; often the name is padded with dots or the line is a name=value list. The field name may contain words like error or exception, because it names the flag, not an event that happened.",
                       "examples": ["retry count..........0", "timeout flag.........1", "r3=0x0000 r4=0x1a2b", "link error status: 0x0"]},
              "false": {"description": "A sentence reporting that something happened.",
                        "examples": ["disk sda failed", "2 memory errors corrected", "process 4711 killed by signal 9"]}
            }
          },
          "corrected": {
            "type": "noul",
            "instructions": "Does `message` say that an error was corrected, recovered, retried successfully or otherwise handled automatically?"
          },
          "kind": {
            "type": "choice",
            "instructions": "What kind of problem does `message` describe?",
            "criteria": {
              "hardware failure": "memory, cache, CPU, node card, power, cooling or other physical component failing",
              "system software failure": "kernel, operating system or control software failing or panicking",
              "network or I/O failure": "links, sockets, torus/tree network, file system or storage I/O failing",
              "job or application failure": "a user job or application crashing, timing out or being killed",
              "not a problem": "routine status, counters, configuration, diagnostic values or corrected errors"
            }
          }
        }'::JSON
    ) AS j
    FROM patterns p
    LEFT JOIN logs l ON l.dataset = p.dataset AND l.line_id = p.example_line_id
    WHERE :where
) p
ORDER BY p.dataset, p.pattern_id
) TO STDOUT WITH (FORMAT csv, HEADER);
