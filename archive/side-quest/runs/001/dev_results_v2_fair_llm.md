| system | n | accuracy | macro_f1 | macro_f1_ci95 | brier | ece | selective_acc | coverage | latency_p50_ms | latency_p95_ms | cost_per_1k_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev A0_basic_evidence_plain_labels | 105 | 0.343 | 0.415 | [0.32, 0.49] | 0.944 | 0.354 | 0.422 | 0.429 | 261 | 429 | 0.032 |
| Jev A1_full_evidence_plain_labels | 105 | 0.333 | 0.413 | [0.32, 0.49] | 1.023 | 0.474 | 0.347 | 0.686 | 257 | 352 | 0.048 |
| Jev A2_full_evidence_structured | 105 | 0.400 | 0.479 | [0.39, 0.55] | 1.008 | 0.431 | 0.375 | 0.686 | 255 | 291 | 0.059 |
| Jev A3_structured_plus_3_shuffles | 105 | 0.390 | 0.467 | [0.38, 0.55] | 1.017 | 0.433 | 0.380 | 0.676 | 254 | 398 | 0.103 |
| Jev FROZEN=A2_full_evidence_structured @t=None | 105 | 0.400 | 0.479 | [0.39, 0.55] | 1.008 | 0.431 |  |  | 255 | 291 | 0.059 |
| B1 LLM same evidence | 105 | 0.286 | 0.352 | [0.25, 0.44] | 1.287 | 0.640 |  |  | 2541 | 14368 | 1.141 |
| B2 LLM raw logs | 105 | 0.333 | 0.375 | [0.27, 0.46] | 1.196 | 0.586 | 0.333 | 1.000 | 1927 | 6615 | 5.513 |
| B3 classifier (LORO-CV) | 105 | 0.200 | 0.095 | [0.06, 0.12] | 0.938 | 0.290 | 0.200 | 0.143 | 0 | 0 | 0.000 |
| B4 rules | 105 | 0.343 | 0.358 | [0.24, 0.46] | 1.314 | 0.657 | 0.343 | 1.000 | 0 | 0 | 0.000 |

```json
{
 "frozen_variant": "A2_full_evidence_structured",
 "tuned_auto_threshold": null,
 "dev_selective_acc_at_t": NaN,
 "dev_coverage_at_t": 0.0,
 "b1_tuned_threshold": null,
 "paraphrase_consistency": {
  "jev": 0.8857142857142857,
  "B1 LLM same evidence": 0.7428571428571429,
  "B2 LLM raw logs": 0.6285714285714286,
  "B3 classifier (LORO-CV)": 1,
  "B4 rules": 1
 },
 "self_consistency_3_runs": {
  "jev": 1,
  "B1": 0.8
 },
 "option_order_agreement_A3": 0.9595238095238096
}
```
