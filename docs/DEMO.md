# Demo script: 5 minutes

Slides: `docs/slides/making-sense-of-logs.pptx` (14 slides; the same text is in each slide's notes).
Every number below comes from a committed result (sources at the end).

**Before recording**
- `docker compose up -d`, then `claude` in the repo, base corpus loaded (`setup_status` shows bgl + openstack).
- Have a second window open: Claude Code with the question below already typed, and the session report open in a browser.
- Backup if anything fails live: `docs/investigation/report.html` (offline, same investigation).

| Time | Slide | What to say |
|---|---|---|
| 0:00 | **1 · Title** | "We built an assistant that answers questions about millions of log lines, for the engineer, the team lead and the manager. An answer takes 14 seconds, costs about 5 cents, and every number in it can be checked." |
| 0:15 | **2 · Problem** | "Three people ask about the same logs. BGL alone is 4.7 million lines: no prompt fits that. It has 855 thousand FATAL lines, but they are only 36 thousand bursts of real recurrences, so counting lines misleads. And if you just let Claude grep the raw files, it takes 86 seconds per answer and gets things wrong." |
| 0:35 | **3 · Pipeline** | "Our answer is a pipeline in five steps. The database does the counting, the AI only explains. Load, judge, ask, answer, verify. Setup is four commands." |
| 0:50 | **4 · Load** | "Step one. Say 'Load the base corpus'. SereneDB downloads BGL and OpenStack, detects the format from 76 known ones, parses everything with SQL into typed columns, groups lines into kinds of message and builds one full-text index. 72 seconds for 5 million lines. Your own log file: under 2 seconds." |
| 1:15 | **5 · Judge** | "Step two is where it gets cheap. Jev, a small typed-judgment model, runs inside SereneDB and asks each kind of message once: is it a real fault or a routine dump? an attack? whose is it? 1,126 kinds of message in 20 seconds for 2 cents, stored. Having an LLM read BGL instead is about 440 million tokens, measured: about two and a half hours and 220 dollars on Haiku, 880 on Sonnet, 1,760 on Opus, and again for every question. And it works: real alerts in the manager's top 10 go from 1 to 5." |
| 1:45 | **6 · Ask** | "Step three. Claude asks focused questions through our MCP server: 44 tools, each a fixed, safe SQL query. A full-text count over 4.7 million lines takes 7 milliseconds; group-bys come straight from the index. A whole 20-step investigation spends 1.8 seconds in the database." |
| 2:05 | **7 · Answer** → switch to Claude Code | **Live:** run `/mcp__logs__worked_investigation` (topic: *what deserves attention in November 2005*, dataset `bgl`). "One problem, three answers. The engineer gets 12,996 lines on 1,024 nodes, all pointing to one host, and the check to run. The team lead gets 31 recurrences and an owner disputed between two teams. The manager gets rank 1 of 133 and a decision. Different evidence, not different lengths." |
| 2:50 | **8 · Verify** → show the report | Open the link Claude gives. Click a number: it jumps to its step. Click **Verify**. "Every number traces to the query that produced it: 62 of 62. Re-running every step gives the same result. The Jev tab shows every question Jev is asked and what each answer means." |
| 3:15 | **9 · Price & performance** | "The main point. Same Claude Code, same model, 50 questions. With our server: 14 seconds per answer instead of 86, six times faster. It costs about one cent more, 4.9 instead of 3.8, but makes half the wrong claims per dollar. Under one second of each answer is the database; the rest is the AI writing." |
| 3:40 | **10 · Results** | "Measured against frozen answer keys with a blind judge: we win 30 to 15, and 18 to 4 on the brief's data, with 116 wrong claims instead of 186. Where we still lose: engineer questions on small logs, where grep can read every line." |
| 4:00 | **11 · Features** | "Each feature fixes a way answers go wrong. Bursts instead of lines. Jev's judgments. Exact totals in SQL, never rounded by the model. An ownership table, so every problem has a team. A computed priority. And facts are always separated from hypotheses." |
| 4:25 | **12 · Beyond the brief** | "Beyond the brief: your own log files with no code, a billion remote rows queried in place, access per team enforced by the database, 11 million lines loaded in 47 seconds, our own blind evaluation, and it is fully reproducible: run with --fresh and Jev judges everything live with the same result." |
| 4:45 | **13 · Scale** | "Nothing is specific to one dataset: ten log types load with no code change. That makes it a product: a self-hosted log copilot for the Mittelstand and beyond." |
| 4:55 | **14 · Try it** | "Four commands, about two minutes from a fresh install to answers. Thank you." |

## Numbers and where they come from
| Number | Source |
|---|---|
| 14 s vs 86 s per answer · 4.9 ¢ vs 3.8 ¢ · 30–15, 18–4 · 116 vs 186 wrong claims · 64 vs 46 % key facts | `eval/results/cc-20261018-205503.md` (Claude Code + our MCP vs plain Claude Code, 50 questions) |
| 47 vs 100 wrong claims per dollar | the same file: 116 / $2.46 vs 186 / $1.85 |
| 72 s load, 18 s BGL parse, 1.6 s new file, 7 ms count, 3–39 ms group-bys, 11.2 M lines in 47 s | `docs/PERFORMANCE.md`, README |
| $0.02 · 20 s for 1,126 patterns · 1 → 5 real alerts | `plans/006-jev-pattern-judgment.md` |
| ≈ 440 M tokens · ≈ 2.5 h · $220 / $880 / $1,760 | measured 2026-10-18: 800 KB of BGL = 473,801 input tokens (1.69 B/token) → 743 MB ≈ 440 M tokens; time to first token 9.6–9.9 s for 474 k tokens (≈ 48 k tokens/s, Haiku 5.5 and Sonnet 5.5) → ≈ 2.5 h; × list input price (Haiku 5.5 $0.50 / M over 100 k, Sonnet 5.5 $2 / M, Opus 5.5 $4 / M). Input only: a lower bound |
| 62 / 62 numbers, 17 / 17 steps, 1.8 s in SereneDB, 12,996 lines, 1,024 nodes, rank 1 of 133 | `docs/INVESTIGATION.md` |
| 2 min fresh install → answers, live Jev = committed counts | clean-clone test (commit b55de10) |
