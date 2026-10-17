# H4 confidence signals (dev, session 001-dev-20261011-192903, frozen A4_rarity_evidence_structured)

Coverage = share of the 105 questions answered automatically; the rest go to "needs review".
Thresholds are picked on dev (optimistic); held-out validates once.

| Model | Signal | Accuracy if answering all | Max coverage @ ≥90% acc | Max coverage @ ≥80% acc | AURC ↓ |
|---|---|---|---|---|---|
| Jev | computed confidence (current) | 48% | 0% | 10% (t=1.00) | 0.446 |
| Jev | top probability | 48% | 0% | 10% (t=1.00) | 0.446 |
| Jev | top-two margin | 48% | 0% | 10% (t=1.00) | 0.439 |
| Jev | key-evidence confidence | 48% | 0% | 0% | 0.507 |
| Jev | confidence × answer/citation consistent | 48% | 0% | 10% (t=1.00) | 0.419 |
| Jev | confidence × A3 shuffle agreement | 48% | 0% | 10% (t=1.00) | 0.444 |
| Jev | confidence × wording agreement (3 asks) | 48% | 0% | 10% (t=1.00) | 0.445 |
| LLM | self-reported confidence (current) | 48% | 0% | 5% (t=0.98) | 0.522 |
| LLM | confidence × A3 shuffle agreement | 48% | 0% | 5% (t=0.98) | 0.529 |
| LLM | confidence × wording agreement (3 asks) | 48% | 0% | 5% (t=0.98) | 0.514 |
