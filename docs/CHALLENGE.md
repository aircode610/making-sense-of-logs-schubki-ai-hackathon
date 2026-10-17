# The challenge (SereneDB · SchubKI National AI Hackathon 2026)

**Making Sense of Logs: The Right Insights for the Right People.** Partner: SereneDB.
Dates: 16 Oct opening · **17–18 Oct work** · 19–20 evaluation · 21 closing. Jury Q&A: Sat 17 Oct 16:00–21:04 CEST
(ours 18:50–19:00, see `QA_JURY.md`). Submission deadline: **Sun 18 Oct 2026, 23:59** (format: ask organisers).

Full original text: **`BRIEF.md`** (verbatim; wins over this summary if they disagree).

## Brief (condensed, wording kept where it matters)
- Build a working prototype that turns log data into useful answers for three roles. **SereneDB finds evidence and
  calculates reliable summaries; an AI agent explains the results and recommends next steps.** One workflow:
  **question → evidence → recommendation.**
- "Millions of log lines will not fit into one prompt. Give the agent a way to ask focused questions. **The database
  searches and calculates; the agent uses the returned evidence to explain.**"
- **Engineer:** what failed, in which component, what happened just before and after? Return relevant error messages
  and nearby events, explain a possible cause, suggest the next check.
- **Team lead:** which problems recur, how often, which components/teams? Counts and trends over a **stated period**,
  using the ownership table; suggest what to investigate first.
- **Manager:** which observed problems deserve attention first, what next? Short prioritised risks + actions from
  measured frequency and affected components. **Do not invent financial losses, downtime or customer impact.**
- **Same agent + same base corpus for all roles.** Change questions, evidence and actions per role; "changing only the
  length of the answer is not enough."
- **Tools:** small set the agent can call (search logs, nearby events, summaries). Describe purpose, inputs, outputs so
  the agent can choose. Parameterized queries are enough; open-ended SQL generation is not required.
  Search returns a **limited** set; aggregation returns calculated counts/trends. **Include the query and filters, and
  say when results are truncated.** "A few retrieved examples cannot establish how often an error occurs."
- **Engineer:** full-text search + time filters + nearby events. **Lead/manager:** counts by component or team + trend
  over a suitable period. Phrase/fuzzy matching, detailed comparisons: optional.
- **Grounding:** every measured claim from a query that actually ran (keep query + result). Separate observed facts from
  possible explanations and recommended checks. Say what remains unknown. **Count matching entries accurately; do not
  automatically treat them as separate incidents.**
- Recommended: expose tools via **MCP** so Claude can use them. CLI/TUI/web UI also fine. Existing agent is sufficient.
- Suggested timing (48 h): 0–6 inspect data + first queries · 6–18 search & summary tools · 18–30 agent + three roles ·
  30–40 check answers against query results · 40–48 README + demo rehearsal.

## Data
- **BGL** (search + trend data): 4,747,963 lines, 2005-06-03 → 2006-01-04 (214.7 days), severities (regex parse, plan 002) INFO 3.74M · FATAL 856k ·
  ERROR 112k · WARNING 23k · SEVERE 19k · FAILURE 1.7k; components KERNEL 4.32M · APP 229k · DISCOVERY 97k · MMCS 89k ·
  HARDWARE 5k · MONITOR 1.7k · LINKCARD 1.2k · …; **348,460 labelled alert lines in 41 categories** (KERNDTLB 153k,
  KERNSTOR 63k, APPSEV 50k, KERNMNTF 32k, KERNTERM 23k, …). Note: 855k FATAL lines but 348k alert lines → severity ≠ problem.
- **OpenStack** (aggregation data): 207,820 lines; nova-api 102,868 · nova-compute 104,086 · nova-scheduler 866; request
  ids, tenant ids, inline latency; 3 VM instances with injected anomalies (`anomaly_labels.txt`).
- Ownership table: we invent it → `data/ownership.csv` (document in README).
- Optional: larger Loghub sets; 50B-row OTel Parquet on S3
  (`https://public-pme.s3.eu-west-3.amazonaws.com/text_bench/part_000.parquet` … `part_049`, query in place, don't download);
  RCAEval / Nezha for logs+traces+metrics.
- Licence: research use, cite Loghub (Zhu et al., ISSRE 2023) and BGL (Oliner & Stearley, DSN 2007).

## Minimal requirements (checklist — keep ticking)
- [ ] Agent answers ≥ 1 question per role, each with relevant evidence, right level of detail, role-suited next step.
- [ ] Retrieval **and** aggregation on **both** BGL and OpenStack; ≥ 1 answer uses full-text search; ≥ 1 uses an
      aggregation over the **whole base corpus** (e.g. counts by dataset or team). Data scope + filters stated.
- [ ] Practical recommendations supported by findings: what to check/fix first and why.
- [ ] Search + summary exposed as tools with clear descriptions (purpose, inputs, outputs).
- [ ] Shows its work: executed queries + results behind every number; hypotheses and limitations labelled.
- [ ] Runs from a clean checkout: connect to SereneDB, load base data with our loader, start the agent.
      Organisers (2026-10-17): schema, loading SQL/scripts and ownership table are **ours, in the repo**; README must
      say how to start SereneDB, load BGL + OpenStack, start the agent (`BRIEF.md` § clarifications).

## Expected output
- [ ] Public repo + README (workflow, setup, run, known limitations, tool docs, ownership table).
- [ ] Working prototype (MCP server recommended; UI optional).
- [ ] **One worked investigation** of a real issue/recurring pattern: questions, tool calls, executed queries, results,
      answer + action per role; both search and aggregation; what the data does and doesn't establish.
- [ ] ≤ 5-minute demo/presentation + slides.

## Rubric
| Weight | Criterion | What it means for us |
|---|---|---|
| **30%** | Role-appropriate insight | three distinct uses of evidence: investigation / recurring patterns / prioritised risks |
| **25%** | Search and analytics together | relevant full-text evidence + correct aggregations over the stated scope |
| **25%** | Recommendation quality | specific next steps backed by query evidence; facts vs hypotheses separated |
| **20%** | Execution | clean-checkout run, clear setup, coherent demo, **novelty**, presentation |

Special awards (separate, optional): **Best MCP Server** (clear tool descriptions, right tool selection, useful result
limits, Claude connects via our instructions) · **Working with Huge Datasets** (remote OTel Parquet / big Loghub; show
data volume, usefulness, query times, costs; on-demand indexing optional).
Informal bonuses: logs ↔ traces/metrics correlation; row-level security per role.

Optional extension in the brief: agent-managed index workspace (create index for a time range, drop after); if done,
**measure repeated-question time with vs without the index** and explain build-time vs saved-time trade-off.
