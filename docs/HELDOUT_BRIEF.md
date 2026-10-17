# Brief: writing `eval/heldout/questions.yaml` (Amirali + Konark, no Claude)

Context: `docs/HELDOUT.md`. Write these **by hand**: if an LLM writes them it picks the same obvious nodes/errors the
agent gets tuned on, and the held-out set stops proving anything. A model may help with wording at most. Never paste
the questions (or which nodes/errors they use) into a Claude Code session.

## Goal
30 questions (10 per role) that the agent's developers never see. They test whether our agent generalises beyond the
dev/demo questions. Each question gets a hand-checked "golden" answer.

## Rules
1. Use the question patterns in `docs/ROLES.md` (E1–E7, L1–L7, M1–M5), but swap in **new** specifics: different nodes,
   periods, error texts, instance ids. Avoid the most obvious/loudest things (top error family, top node); we'll likely
   demo those.
2. Each question must be answerable from the logs + `data/ownership.csv` alone.
3. Write it the way a real user would ask it. Short and natural, with no tool names or SQL hints.
4. Every golden number comes from a query or awk command you ran yourself on the raw files. Keep the command next to
   the number. Until tables are loaded, awk/grep on `data/raw/*` is fine; convert to SQL after B1.
5. Only use measures whose definition is frozen today: line counts, distinct nodes/hosts/instances, first/last
   timestamp, counts per day/week, counts per component/team, HTTP status counts, latency percentiles. Do **not** put
   "episodes" or "priority score" numbers in golden answers yet (definitions not frozen); use `must_mention` instead.
6. Use absolute dates in questions that need a period ("between 2005-11-01 and 2005-11-28"), plus a few that say
   "last 4 weeks" (= measured back from the dataset's last timestamp).
7. Put about a third of the BGL questions inside the held-out slice (`ts >= 2005-12-05`).
8. Labels (BGL first field, OpenStack `anomaly_labels.txt`) may be used to *choose* good questions, but the golden
   answer must be derivable without them.

## Mix (10 per role)
- engineer: E1 ×2, E2 ×2, E3 ×2, E4, E5, E6, E7 (≥ 3 OpenStack)
- lead: L1 ×2, L2 ×2, L3 ×2, L4, L5, L6, L7 (≥ 2 OpenStack)
- manager: M1 ×2, M2 ×2, M3 ×2, M4 ×2, M5 ×2

## Format (one entry per question; keep field names exact, `eval/run_heldout.py` parses them)
```yaml
- id: H-E01                      # H-E / H-L / H-M + number
  role: engineer                 # engineer | lead | manager
  pattern: E1                    # ROLES.md id
  dataset: bgl                   # bgl | openstack | both
  question: "What failed on R..-M.-N.-C:J..-U.. around 2005-..-.. ..:.., and what happened just before and after?"
  period: {from: "2005-..-.. ..:..:..", to: "2005-..-.. ..:..:.."}   # absolute; omit if none
  golden:                        # facts a correct answer MUST contain; each hand-checked
    - fact: "lines matching '<error text>' on that node in the window"
      value: 42
      tolerance: 0               # 0 for counts; e.g. 0.05 for latency/ratios
      check: "awk -F' ' '...' data/raw/BGL.log | wc -l"
    - fact: "first occurrence in the window"
      value: "2005-..-..-..."
      check: "..."
  must_mention: ["<node or instance>", "<team from ownership.csv>", "<component>"]
  must_not: []                   # manager: ["downtime", "cost", "$", "customers", "revenue"]
  expected_first_tool: search_logs   # search_logs | get_context | count_by | trend | top_patterns | priority_table
  notes: "why this is a good test (optional)"
```

## Per role: what a golden answer pins down
- **engineer:** anchor count in the window, first/last timestamp, node/instance, one event just before and one just
  after (verbatim substring), spread (distinct nodes, same pattern, same window).
- **lead:** stated period, counts per component **and** per team, weekly counts for one pattern/team (list of numbers),
  top-node share for L4, first-seen date for L5.
- **manager:** the measured inputs (lines, distinct nodes, weeks active, weekly trend numbers) for the 2–3 problems you'd
  expect at the top + the owner team. `must_not` = invented impact. M5: `must_mention` what the logs can't show (cost,
  downtime, customer impact, root cause).

## Done when
30 entries, every value has a check command you ran, file saved at `eval/heldout/questions.yaml` (gitignored), shared
privately, never pasted into a Claude Code session.
