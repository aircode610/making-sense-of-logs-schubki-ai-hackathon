| system | n | accuracy | macro_f1 | macro_f1_ci95 | brier | ece | selective_acc | coverage | latency_p50_ms | latency_p95_ms | cost_per_1k_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev A0_basic_evidence_plain_labels | 105 | 0.343 | 0.414 | [0.32, 0.49] | 0.945 | 0.362 | 0.422 | 0.429 | 261 | 428 | 0.032 |
| LLM A0_basic_evidence_plain_labels | 105 | 0.362 | 0.441 | [0.34, 0.53] | 1.137 | 0.548 | 0.362 | 1.000 | 2543 | 8647 | 0.894 |
| Jev A1_full_evidence_plain_labels | 105 | 0.352 | 0.431 | [0.34, 0.51] | 1.021 | 0.454 | 0.347 | 0.686 | 259 | 336 | 0.048 |
| LLM A1_full_evidence_plain_labels | 105 | 0.276 | 0.314 | [0.22, 0.40] | 1.279 | 0.643 | 0.276 | 1.000 | 2546 | 11073 | 1.359 |
| Jev A2_full_evidence_structured | 105 | 0.400 | 0.479 | [0.39, 0.55] | 1.009 | 0.430 | 0.386 | 0.667 | 255 | 293 | 0.059 |
| LLM A2_full_evidence_structured | 105 | 0.286 | 0.344 | [0.25, 0.43] | 1.287 | 0.640 | 0.286 | 1.000 | 2533 | 14370 | 1.199 |
| Jev A3_structured_plus_3_shuffles | 105 | 0.400 | 0.476 | [0.38, 0.55] | 1.014 | 0.434 | 0.366 | 0.676 | 254 | 395 | 0.103 |
| LLM A3_structured_plus_3_shuffles | 105 | 0.295 | 0.365 | [0.27, 0.44] | 1.273 | 0.632 | 0.299 | 0.829 | 11290 | 43667 | 5.342 |
| Jev A4_rarity_evidence_structured | 105 | 0.476 | 0.506 | [0.39, 0.59] | 0.836 | 0.324 | 0.486 | 0.686 | 233 | 311 | 0.079 |
| LLM A4_rarity_evidence_structured | 105 | 0.476 | 0.494 | [0.39, 0.59] | 0.924 | 0.427 | 0.476 | 1.000 | 1863 | 6967 | 1.328 |
| Jev FROZEN=A4_rarity_evidence_structured @t=None | 105 | 0.476 | 0.506 | [0.39, 0.59] | 0.836 | 0.324 |  |  | 233 | 311 | 0.079 |
| LLM FROZEN=A4_rarity_evidence_structured @t=None | 105 | 0.476 | 0.494 | [0.39, 0.59] | 0.924 | 0.427 |  |  | 1863 | 6967 | 1.328 |
| B2 LLM raw logs | 105 | 0.333 | 0.375 | [0.27, 0.46] | 1.196 | 0.586 | 0.333 | 1.000 | 1927 | 6615 | 5.513 |
| B3 classifier (LORO-CV) | 105 | 0.429 | 0.229 | [0.18, 0.28] | 0.836 | 0.122 | 0 | 0.029 | 0 | 0 | 0.000 |
| B3 classifier (stratified 5-fold CV) | 105 | 0.571 | 0.482 | [0.37, 0.58] | 0.649 | 0.223 | nan | 0.000 | 0 | 0 | 0.000 |
| B4 rules | 105 | 0.571 | 0.360 | [0.25, 0.45] | 0.857 | 0.429 | 0.571 | 1.000 | 0 | 0 | 0.000 |

```json
{
 "frozen_variant": "A4_rarity_evidence_structured",
 "freeze_rule": "max average macro-F1 of Jev and LLM",
 "avg_macro_f1_per_variant": {
  "A0_basic_evidence_plain_labels": 0.4271788121149576,
  "A1_full_evidence_plain_labels": 0.37272331478738463,
  "A2_full_evidence_structured": 0.41143924116589503,
  "A3_structured_plus_3_shuffles": 0.4207798487432108,
  "A4_rarity_evidence_structured": 0.5000862232732417
 },
 "tuned_auto_threshold": {
  "jev": null,
  "llm": null
 },
 "dev_selective_at_t": {
  "jev": [
   NaN,
   0.0
  ],
  "llm": [
   NaN,
   0.0
  ]
 },
 "paraphrase_consistency": {
  "jev": 0.9142857142857143,
  "llm": 0.7142857142857143,
  "B2 LLM raw logs": 0.6285714285714286,
  "B3 classifier (LORO-CV)": 1,
  "B3 classifier (stratified 5-fold CV)": 1,
  "B4 rules": 1
 },
 "self_consistency_3_runs": {
  "jev": 0.9142857142857143,
  "llm": 0.8857142857142857
 },
 "option_order_agreement_A3": {
  "jev": 0.9571428571428572,
  "llm": 0.8809523809523809
 }
}
```
