# The three roles: what each one asks, what evidence answers it, what they get back

This spec drives the tools, agent recipes, answer cards and eval. Expand any part when a question can't be answered
fully. The same agent and the same corpus serve all three roles. Roles differ in **questions, evidence and actions**, not
in answer length (brief).

## Shared definitions (state them in every answer that uses them)
| Term | Definition (draft; tune once after looking at the data, then freeze) |
|---|---|
| **Corpus "now"** | The last timestamp per dataset (BGL 2006-01-04, OpenStack end of its log). "Last 4 weeks" is measured back from there. Every answer names its absolute period. |
| **Line** | One log entry. Counts are exact SQL counts. |
| **Pattern** | A log template with variable parts masked (numbers, hex, ids, IPs, paths). Computed once at load; `pattern_id` on every row. |
| **Episode** | A burst of the same pattern on the same node/component: lines split when the gap is > 30 min. "152k lines in 40 episodes on 3 nodes" never "152k incidents". |
| **Problem pattern** | Deterministic first: severity ∈ {FATAL, FAILURE, SEVERE, ERROR} (BGL) / {ERROR, CRITICAL} or HTTP 5xx / outlier latency (OpenStack). Then a Jev judgment per pattern ("real fault or routine?", calibrated probability) refines it. Labels are never used here, only in eval. |
| **Spread** | Distinct nodes / midplanes / racks (BGL location `R02-M1-N0-C:J12-U11` = rack-midplane-nodecard-card-unit) or hosts / instances (OpenStack) affected. |
| **Trend** | Week-over-week change of episodes (and lines) over the stated period, plus direction (rising / flat / falling, rule-based thresholds in code). |
| **New** | Pattern's first occurrence in the corpus falls inside the period. |
| **Owner** | `data/ownership.csv` (dataset, component → team); unmapped → `unowned`. |

## Answer card (common frame, role-specific content)
`ANSWER` (1–3 sentences) · `FACTS` (each with evidence id → query + result) · `HYPOTHESES` (labelled, with what
supports or contradicts them) · `UNKNOWN` (what the logs cannot establish) · `NEXT STEP` (role-specific) · `SCOPE`
(datasets, period, filters, truncation) · `CONFIDENCE` (computed: verified-number rate + Jev probabilities, never LLM
self-report).

---

## 1. Engineer: "what failed, where, and what happened around it?"
**Job:** investigate one error or failure fast and leave with a concrete next check.

### Question bank (core ★ / stretch)
| # | Question | Dataset |
|---|---|---|
| E1 ★ | "What failed on node `<location>` around `<time>`, and what happened just before and after?" | BGL |
| E2 ★ | "Find `<error text>` between `<t1>` and `<t2>`. Where and when did it start?" (full-text, phrase/fuzzy) | BGL |
| E3 ★ | "What happened to instance `<uuid>`?" (all events for the instance across api → scheduler → compute) | OpenStack |
| E4 | "Why are nova-api requests failing or slow between `<t1>` and `<t2>`?" (status codes, latency inline) | OpenStack |
| E5 | "Is this error local to one node or happening across the system right now?" | both |
| E6 | "Has this error happened before? Is it new?" | both |
| E7 | "Which error came first in this burst?" (earliest event in the chain) | both |

### Evidence recipe (what the agent must gather, in this order, in parallel where possible)
1. **Anchor:** full-text search with time and component/severity filters → top matches (≤ 50), **total match count**, truncated flag.
2. **First occurrence** of the anchor pattern in the window, and in the whole corpus (new vs known).
3. **Context:** events ± N minutes (default 5) on the same node, then the same midplane/rack (BGL), or the same
   request id / instance id across services (OpenStack). Before and after are kept separate.
4. **Spread at that time:** how many other nodes or hosts show the same pattern in the window (local vs systemic).
5. **Baseline:** the pattern's usual rate on this node/component in the previous 7 days ("14 lines now vs about 2/h usual").
6. Optional: significant terms of the window vs the baseline (what's unusual), same-request latency.

### Answer content
- **What failed:** component, node/instance, pattern, first/last time, lines, episodes. All from SQL.
- **Timeline:** before → at → after, verbatim lines with ids and timestamps.
- **Scope:** local vs spread (N nodes), new vs recurring.
- **Possible cause:** a hypothesis, labelled as one, naming the supporting lines (e.g. "ECC/parity errors precede the
  kernel panic on the same node card").
- **Next check:** concrete and runnable. A query to run, a component to inspect, a metric to look at
  (e.g. "check node card R02-M1-N0-C hardware counters; query the same pattern on its neighbours J13–J15").
- **Must not:** generalise from the sample to frequency ("a few examples can't establish how often"; use the count tool).

### Acceptance checklist
error lines quoted ✔ · before/after events ✔ · component + node named ✔ · total count with scope ✔ · cause labelled as
hypothesis ✔ · next check is specific ✔ · full-text search used ✔

---

## 2. Team lead: "what keeps coming back, how often, and whose is it?"
**Job:** see recurring problems over a stated period, by component and team, and pick what the team investigates first.

### Question bank
| # | Question | Dataset |
|---|---|---|
| L1 ★ | "Which problems recurred most in `<period>`, and which teams own them?" | BGL (+ OpenStack) |
| L2 ★ | "How did `<pattern / team / component>` trend week over week over `<period>`?" | BGL |
| L3 ★ | "Error rate and latency (p50/p95) per nova service per hour: where are the outliers?" | OpenStack |
| L4 | "Is `<problem>` one bad node or fleet-wide?" (concentration: top-node share) | BGL |
| L5 | "What's new this period compared with before?" | both |
| L6 | "Which recurring problems are getting worse?" | both |
| L7 | "Do these two patterns tend to occur together?" (same node, within minutes) | BGL |

### Evidence recipe
1. **Problem patterns in the period**, ranked by episodes (and shown with lines, nodes, active weeks, team).
2. **Weekly trend** for the top patterns and per team (full-corpus aggregation, not samples).
3. **Concentration:** share of lines/episodes from the top node; distinct nodes.
4. **New vs recurring:** first-seen inside or before the period.
5. **Whole-corpus counts by dataset and team** (meets the "aggregation over the whole base corpus" requirement).
6. OpenStack: per-service error rate and latency percentiles per hour.

### Answer content
- **Period + scope** stated first (absolute dates, datasets, filters).
- **Top recurring problems:** a table (pattern in plain words, team, episodes, lines, nodes, weeks active, trend).
- **Trends:** numbers ("episodes 12 → 31 over the last 3 weeks"), not adjectives.
- **Investigate first:** one problem, with the reason in measured terms (recurring + spreading + rising beats a single loud
  burst), its owner, and the first diagnostic for the team.
- **Caveats:** lines ≠ incidents; a logging storm on one node inflates lines (episodes and nodes correct for that).

### Acceptance checklist
stated period ✔ · counts by component and team ✔ · trend over time ✔ · ownership table used ✔ · lines vs episodes
distinguished ✔ · one "investigate first" with measured reason ✔

---

## 3. Manager: "what deserves attention first, and what should happen next?"
**Job:** decide priorities and owners from measured risk. Short, ranked, honest about unknowns.

### Question bank
| # | Question |
|---|---|
| M1 ★ | "What should we prioritise next, based on `<period>`?" |
| M2 ★ | "Which team's area carries the most risk right now, and is it getting better or worse?" |
| M3 | "Is overall reliability improving over `<period>`?" (problem episodes per week, all teams) |
| M4 | "If we can fix only one thing, which one and why?" |
| M5 | "What can't the logs tell us about these problems?" |

### Evidence recipe
1. **Priority table** (computed, reproducible): per problem pattern, the inputs frequency (episodes), trend (slope),
   spread (nodes/components/teams), persistence (weeks active), severity (deterministic + Jev Score). Score =
   weighted sum in code, weights shown. The LLM explains the ranking; it never makes it.
2. **Team roll-up:** problem episodes per team, trend per team.
3. **Period comparison:** this period vs the previous one.

### Answer content
- **Top 3 priorities:** rank, problem in plain language, owner team, one-line measured basis
  ("31 episodes on 14 nodes, rising 3 weeks in a row"), trend arrow.
- **Risk in measured terms only:** frequency, spread, trend, persistence.
- **Action per item:** owner + what to decide or fund (e.g. "node-platform: hardware check of rack R02. Decide whether to
  drain those node cards").
- **Unknown:** impact, cost, downtime and customers are not in these logs. Say so explicitly.
- **Must not:** invent money, downtime or customer impact. Must not rank by raw line counts.

### Acceptance checklist
ranked ✔ · each item has measured basis + owner + action ✔ · unknowns stated ✔ · no invented impact ✔ · short ✔

---

## How the roles differ (what we show judges)
| | Engineer | Team lead | Manager |
|---|---|---|---|
| Unit | lines + events around one moment | patterns × weeks × teams | ranked problems |
| Main tools | `search_logs`, `get_context`, spread/baseline | `top_patterns`, `trend`, `count_by` | `priority_table`, team roll-up, period compare |
| Search vs aggregation | search-led | aggregation-led | aggregation only (+ cited examples) |
| Time scope | minutes around an event | weeks / stated period | period vs previous period |
| Next step | a diagnostic check | what to investigate first + owner | what to prioritise / decide + owner |

## Worked investigation (to pick in hours 0–6)
One real recurring problem walked through all three roles (e.g. a BGL kernel error family such as data-TLB or storage
errors, or the OpenStack anomalous instances). Pick it from the data: high episodes, several nodes, a visible trend, and
clear before/after context. Record every question, tool call, query and result for the README.
