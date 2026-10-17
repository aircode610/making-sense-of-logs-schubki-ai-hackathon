# Jev (TypeSafe AI) — distilled notes

Source: docs.typesafe.ai snapshot 2026-10-09, model `jev-1.13`. Full pages in `pages/`.
Note: `<TypesafeExample />` tags in docs are interactive widgets — their JSON is NOT in the dump; cookbooks have real code.

## What it is
- "System One" model: **non-autoregressive**, no text out. Input = `state` + typed `questions`; output = typed answers
  with calibrated probabilities. Trained with RLCD (RL for Calibrated Decisions). ~70–500 ms, $0.042/M input tokens, output free.
- Endpoint: `POST https://api.typesafe.ai/v1/systemone` (`model`, `state`, `questions`). SDKs: Python `typesafe_sdk`, JS `@typesafe-ai/sdk`.
- Also served via OpenRouter Decisions API (`/api/alpha/decisions`, model `~typesafe/jev-latest`) and locally by **Kev**
  (github.com/jaredpalmer/kev, Qwen-based, same API; Kev-4B on 32GB Mac; Kev-27B ≈ Jev on their benchmark).
- Limits: 64k tokens/request; **32k for state + longest question**. 80 rps / 100k tok/s. English best.
- Same weights for everyone; no fine-tuning. Customise via state + instructions + criteria only.

## The three primitives
| Type | Use for | Returns |
|---|---|---|
| **Noul** | clean yes/no where probability is the signal | `noul` = P(yes). No confidence field. 0.5 = unsure, NOT "medium". |
| **Choice** | one of 2–255 unordered options | `choice`, `probabilities` (sum 1), `confidence` |
| **Score** | position on 2–10 ordered, described levels | `score` (expected level index, fractional), `probabilities`, `confidence`, `legend` |

- `instructions`, choice option descriptions, score levels, noul `criteria.true/false` all accept **JSON objects/arrays**
  (definitions, "covers / does not cover", examples). Use structure to sharpen boundaries.
- Question IDs are NOT sent to the model — put full meaning in `instructions`.
- Point at state parts with backticked paths: ``"Does `ticket.messages[0].text` request a refund?"``.
- Choice probabilities always sum to 1 → something always wins. Add `none`/`other` option or a separate Noul "does any apply?".

## Confidence
- Choice: `(p_max - 1/n)/(1 - 1/n)`. Score: 1 − (prob-weighted distance from mode)/MAD_uniform (adjacent-level splits penalised less).
- Noul: use `|2p−1|` if you want a confidence-like number.
- Alternatives worth testing: top prob, top/second ratio.
- Pattern: high → act, medium → confirm/review, low → human / System-2 LLM. Thresholds scale with stakes; tune on own data.

## Prompting rules (the important part)
1. **One snap judgment per question** — something an expert answers in ~1 second. Broad "analyse this" = bad.
2. **Decompose** multi-factor judgments into atomic Scores/Nouls, combine with weights **in code** (composite scoring).
3. **Fan-out**: put every question about the same state in ONE request (parallel, near-free); incl. speculative ones you may ignore.
   Questions can't see each other's answers. 2nd request only if answer 1 is needed to build state/options for 2.
4. **Minimal state**: filter/retrieve in code first. Irrelevant detail = distractor ("context rot").
5. **Literal reading**: write the exact condition; boundary cases in criteria. If you catch yourself explaining "what I meant" → that belongs in the prompt.
6. Align instructions with criteria (no inverted true/false).
7. **Option order bias**: leans to first option → shuffle & check consistency.
8. Prefer **named/semantic** representations over raw numbers/hex/codes.

## Known weaknesses (jev-1.13 jaggedness) → keep in code
Math, counting, date/time comparison, multi-hop indirection, generation, adversarial/injected content in state, huge noisy state.
Counting trick: one Noul per item, sum in code.

## Key techniques / cookbooks relevant to logs
- **Evidence-in-choices ("select instead of generate")**: tag candidates with IDs, make them the Choice options
  → model picks the evidence. `cookbooks__semantic_find.md` (218 line IDs as options + Noul "does an answer exist?"),
  `cookbooks__pre_parsed_value_extraction_cookbook.md` (regex candidates → Choice picks the span, code copies verbatim).
  For logs: candidate log lines / templates / error clusters / root-cause hypotheses as options, each option's
  *value* = the evidence snippet. Choice over ≤255; larger → score independently then choose (or beam/hierarchy).
- **Re-ranking**: one Noul/Score per (query, candidate) after BM25 shortlist (`cookbooks__rerank_typesafe.md`: top-1 5%→18%).
- **Classifying RAG passages**: relevance Noul per retrieved passage, code decides what goes to the LLM.
- **Hierarchical classification**: one Choice per taxonomy level, options' values = subtrees, beam search on close probs.
  → error taxonomy (component → failure class → specific cause).
- **Composite scoring**: severity × blast radius × recurrence × user impact → weights per role (engineer vs lead vs manager!).
- **Confidence-gated routing / SDE cascade**: Jev first, escalate low-confidence to big LLM.
- **Self-consistency cookbooks**: compare label stability vs LLMs (useful for our eval).
- **Autoresearch feature discovery**: Jev probabilities as features for a classical model (CatBoost) — hybrid vs classifier baseline.
- **Citation check**: Choice "does the context support the claim?" → verify LLM's explanation against evidence.

## Mental model for this project
SereneDB (search + SQL aggregates = evidence & numbers) → Jev (cheap typed judgments on every log/cluster/candidate)
→ code (thresholds, weights per role, routing) → LLM (explain + recommend, citing evidence IDs Jev selected).
