# Try the whole MCP server in Claude Code, step by step

Type each block into Claude Code, started with `claude` in the repo (approve the `logs` server when asked).
Every step was tested; numbers you should see are given for BGL so you know it worked.

## 0 · Start from zero (optional)
```bash
src/scripts/clean_slate.sh        # empty database, no old session reports (--raw: also re-download the logs)
claude                            # a NEW session, not /resume
```

## 0 · Setup and loading
```text
What is the setup status?
```
→ `setup_status`: database version, loaded datasets, the loadable catalog.

```text
Load the base corpus
```
→ `load_logs(source='base')`: downloads BGL + OpenStack from Zenodo and loads them (~72 s; Claude may check
`setup_status` while it runs). For the fully live pipeline, quit Claude and run
`uv run python -m loader load base --fresh` instead (needs `TYPESAFE_API_KEY`, ~2 min).

Optional, your own file:
```text
Load ~/logs/app.log
```
→ format detected from 76 known formats, loaded as its own dataset, judged by Jev if you have a key.

## 1 · Resources: type `@`, pick from the list
Resources attach read-only context to your message (interactive Claude Code; type `@logs:` to filter).
```text
@logs:logs://glossary  What is the difference between a line, a pattern and a burst?
```
```text
@logs:logs://datasets  Which datasets are loaded and which one is active?
```
```text
@logs:logs://ownership/bgl  Which BGL components does each team own, and which owner is disputed?
```
→ APP: curated to hpc-workloads, disputed by node-platform (Jev, p 0.94).
```text
@logs:logs://field-guide/openstack  What do request_id and object_id mean in OpenStack?
```
Other resources: `logs://field-guide/bgl`, `logs://ownership/openstack`, `logs://session/latest` (every query of this
session), and the templates `logs://field-guide/{dataset}`, `logs://ownership/{dataset}`, `logs://session/{id}/step/{n}`
(type the full URI).

## 2 · Prompts: type `/mcp__logs__` and pick one
Arguments are separated by spaces. A question argument takes the rest of the line. For several arguments, use
one word per argument (use `-` instead of spaces).

**Engineer**
```text
/mcp__logs__investigate_failure What failed on the R43-M0 midplane around 2005-08-19 13:56, and what happened just before and after?
```
→ a kernel panic on 2 I/O nodes at 13:56:00, the fleet-wide login storm before it, and a next check.

**Team lead**
```text
/mcp__logs__review_recurring_problems Which problems recurred most in November 2005 (2005-11-01 to 2005-12-01), and which teams own them?
```
→ 451 problem bursts: node-platform 283, hpc-workloads 106, cluster-control 62.

**Manager**
```text
/mcp__logs__set_priorities Based on November 2005, which problems deserve attention first and what should happen next?
```
→ computed rank 1: "Link has been severed" (score 97.8), with owner and a decision; no invented cost.

**All three roles on one topic**
```text
/mcp__logs__worked_investigation link-severed-fault 2005-11 bgl
```
→ engineer, team-lead and manager sections from different evidence, then a session report.

**Whole corpus**
```text
/mcp__logs__whole_corpus_counts team
```
→ one `count_by(team)` per loaded dataset, reported together (BGL 4,747,963 lines, OpenStack 207,820).

## 3 · Completions
Type `/mcp__logs__worked_investigation ` and press Tab on the `dataset` argument: real dataset names are suggested
(components, teams and levels too).

## 4 · Plain questions (Claude picks the tools)
```text
Were any OpenStack VMs abnormally slow to build?
```
→ `value_outliers`: 6 VMs, the slowest spawn 50.72 s vs a median of 19.74 s.
```text
Switch to openstack. How many HTTP 503 responses are there, and when?
```
→ 2 lines, 2017-05-16 06:25 and 2017-05-17 06:25.
```text
Is the rts panic problem getting worse in November 2005?
```

## 5 · Verify
Every answer ends with a link to the **session report**. Open it:
- **Answer** tab: click a number to jump to the step that produced it.
- **Steps** tab: arguments, rows and SQL of each step; **Verify all steps** re-runs them read-only.
- **Jev** tab: what Jev judged here, and every question Jev is asked with its choices and meanings.

Or ask:
```text
Show me the session report
```
```text
@logs:logs://session/latest  Which queries did you run, and were any results truncated?
```
