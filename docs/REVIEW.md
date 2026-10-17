# Swap review (B3): each of us reads the other's role answers

Plan 055. Humans only, ~20 min each. Rules come from `docs/ROLES.md` ("Answer content", "Must not") and the
non-negotiables in `CLAUDE.md`. Write findings at the bottom (one line each: question id, what is wrong, suggested fix).

## Where to read the answers
- **LangSmith (EU)**, project `making-sense-of-logs`, dataset `logs-dev-…`: experiments `ours-<commit>-…` (each run =
  question → answer card + evidence). Latest full set: `eval/results/20261017-174933.md` (plan 009); engineer subset
  after plan 055: newest file in `eval/results/`.
- Or run one yourself: `.venv/bin/python -m agent.run --role <role> "<question from eval/dev_questions.yaml>"`.

## Konark reviews team lead + manager (D-L01…L06, D-M01…M06)
Lead:
- [ ] Period and scope first, as absolute dates; datasets and filters named
- [ ] Top recurring problems in plain words, each with owner team, **bursts** (not just lines), nodes, weeks active
- [ ] Trend as numbers ("12 → 31"), never only adjectives
- [ ] Exactly one "investigate first", with a measured reason (recurring + spreading + rising), owner, first diagnostic
- [ ] Says lines ≠ incidents where it matters (a storm on one node inflates lines)

Manager:
- [ ] Top 3, in the computed order of `priority_table`, each with owner, one-line measured basis, action / decision
- [ ] Risk only in measured terms (frequency, spread, trend, persistence)
- [ ] Unknowns say impact, cost, downtime, customers are **not in the logs**; nothing invented
- [ ] Short; not ranked by raw line counts

## Amirali reviews engineer (D-E01…E08)
- [ ] What failed: component, node / VM, pattern, first / last time, line count, all from a cited result
- [ ] Timeline before → at → after with verbatim lines and timestamps
- [ ] Local vs spread (nodes) and new vs recurring
- [ ] **Rate vs usual** (`rate_vs_baseline`, plan 055): "N/h now vs M/h over the previous 7 days" or "new here"
- [ ] Slow-VM question (D-E07): uses `value_outliers`, names the VMs with ratio to the normal time, no invented cause
- [ ] Exactly one hypothesis, labelled as such, naming supporting lines; one concrete, runnable next check
- [ ] Never turns a sample of lines into a frequency

## Both: across roles (same topic, different person)
- [ ] Same corpus and agent, but different questions, evidence and actions per role (not just shorter / longer)
- [ ] Every number traceable to an `ev-…` id with its SQL; scope and truncation stated

## Findings
| Reviewer | Question | Problem | Suggested fix |
|---|---|---|---|
