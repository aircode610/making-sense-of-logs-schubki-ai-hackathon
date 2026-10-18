# Answer keys (plan 013): frozen 2026-10-18

One file per dev question (`eval/dev_questions.yaml`, 50 questions). Each was written by a fresh agent with no project
context, from read-only SQL over raw `logs` + `labels` + `ownership` (no MCP tools, no past answers), anchored on the
question's golden facts. All 50 golden facts were reproduced. The A/B judge grades answers against these keys.

Rules for the judge (decided by Claude at Amirali's request, `docs/DECISIONS.md` H27):
- The key is the truth; a golden fact computed by one of our tools (`match: order` / `priority_table`) is not. Grade the
  substance (right problem, owner, scope), not the tool's exact order or wording.
- Ambiguous windows or definitions (e.g. an exclusive end date, a template vs its variants, ERROR vs ERROR+FATAL): any
  reading the answer states explicitly is accepted; the key's `notes` give the numbers for each.
- A key's optional `judging` field overrides the above for that question.
- Do not edit keys after an A/B run has started; a fix means re-running the affected comparisons.
- `data_update` (plan 014): a loader fix changed how the data represents something the key mentions (never the facts);
  the note says what changed. Golden values were re-run after the reload and none changed.
