# NNN: <experiment name>

- **Status:** draft | approved | running | done | abandoned
- **Branch:** `exp/NNN-short-name`
- **Dataset(s):**
- **Date:**

## 1. Question this experiment answers
One sentence. What decision will the result let us make?

## 2. Hypothesis and success criteria
- Hypothesis:
- Success = (numbers, decided **before** running): e.g. accuracy ≥ X on dev, ECE ≤ Y, p50 latency ≤ Z ms, cost ≤ $W / 1k questions.

## 3. Data
- Source, preprocessing steps, how it becomes OTel rows in SereneDB.
- Split (dev / held-out): method, seed, sizes, **novelty per brick** (Pattern / Evidence / Verdict / Finding).
- Questions: generation templates + paraphrases.

## 4. Pipeline under test (bricks)
| Brick | What exactly is built | Tool (SQL / Drain3 / Jev / LLM) |
|---|---|---|
| Pattern | | |
| Evidence | | |
| Verdict | | |
| Finding | | |

Jev details: questions, criteria, model pin, confidence policy. SereneDB details: tables, indexes (and why), queries.

## 5. Baselines and ablations
- Baselines (D7):
- Ablation steps (lean rule: one component at a time):

## 6. Metrics
Accuracy/F1/top-k, calibration (Brier, ECE, reliability diagram), selective accuracy vs coverage, self-consistency,
option-order robustness, groundedness, latency p50/p95, $ cost.

## 7. Tracing
What is recorded per example per step; where it is stored; how to view it.

## 8. Held-out protocol
What `make_split.py` / `eval_heldout.py` do and print (aggregates only). When held-out is run (once, at the end).

## 9. Out of scope / risks

## 10. Steps (checklist)
- [ ] ...

## 11. Results (filled after running)
