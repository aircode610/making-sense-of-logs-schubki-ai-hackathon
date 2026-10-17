| system | n | accuracy | macro_f1 | macro_f1_ci95 | brier | ece | selective_acc | coverage | latency_p50_ms | latency_p95_ms | cost_per_1k_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev A0_basic_evidence_plain_labels | 105 | 0.343 | 0.415 | [0.32, 0.49] | 0.946 | 0.364 | 0.422 | 0.429 | 256 | 429 | 0.032 |
| Jev A1_full_evidence_plain_labels | 105 | 0.333 | 0.413 | [0.32, 0.49] | 1.023 | 0.472 | 0.347 | 0.686 | 260 | 352 | 0.048 |
| Jev A2_full_evidence_structured | 105 | 0.400 | 0.479 | [0.39, 0.55] | 1.012 | 0.440 | 0.380 | 0.676 | 255 | 282 | 0.059 |
| Jev A3_structured_plus_3_shuffles | 105 | 0.400 | 0.476 | [0.38, 0.55] | 1.011 | 0.434 | 0.380 | 0.676 | 252 | 393 | 0.103 |
| Jev FROZEN=A2_full_evidence_structured @t=None | 105 | 0.400 | 0.479 | [0.39, 0.55] | 1.012 | 0.440 |  |  | 255 | 282 | 0.059 |
| B1 LLM same evidence | 105 | 0.324 | 0.383 | [0.28, 0.47] | 1.203 | 0.590 |  |  | 2234 | 6830 | 0.879 |
| B2 LLM raw logs | 105 | 0.286 | 0.321 | [0.23, 0.40] | 1.270 | 0.632 | 0.286 | 1.000 | 2245 | 13032 | 5.729 |
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
  "B2 LLM raw logs": 0.5142857142857142,
  "B3 classifier (LORO-CV)": 1,
  "B4 rules": 1
 },
 "self_consistency_3_runs": {
  "jev": 0.9714285714285714,
  "B1": 0.8857142857142857
 },
 "option_order_agreement_A3": 0.9571428571428572
}
```
