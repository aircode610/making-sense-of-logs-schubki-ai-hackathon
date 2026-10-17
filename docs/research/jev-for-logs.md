# Prior art: Jev on logs (search 2026-10-09, from search snippets — not all read in full)

| Source | What | Takeaway |
|---|---|---|
| Cribl blog — https://cribl.io/blog/what-typesafes-jev-means-for-telemetry | 28-class log-type classification (syslog, Cisco ASA, auditd…) | **Jev misclassified 2–3× more than a purpose-built classifier or GPT-5.6 Terra** on semi-structured logs. Great economics, accuracy gap on raw log format ID. |
| dev.to "tuned Jev for log triage without alert storms" — https://dev.to/reachjalil/how-we-tuned-typesafe-jev-for-log-triage-without-alert-storms-1ei0 (HF: reachjalil/jev-luna-pagerduty-trigger) | Jev as pre-filter on Loghub **HDFS** | Default kept 99.16% of lines (too conservative) → filter cost > savings. Tips: route FATAL/CRITICAL in code, **sanitize IDs/IPs + hash + cache templates**, one boolean question, threshold the continuous probability in code. |
| Medium "Jevops" — https://medium.com/@muhamad99t/one-million-logs-zero-wasted-pages-inside-jevops-and-typesafe-jev-35ac25179215 | OSS SRE triage tool, 1M logs/mo ≈ $3 | **"Jev decides, code narrows, LLM explains."** Mode B: chunk time range → Jev labels every chunk in parallel → recurse into important ones → LLM only sees surviving leaves, cites line IDs. Very close to our brief. |
| Zenn — https://zenn.dev/hogehogetaro/articles/typesafe-jev-log-classification?locale=en | 30 Cloud Run fault-injected logs | All 30 classifications matched; uncertainty/judgment calibration questions remained. Small n. |
| KodeKloud — https://kodekloud.com/blog/what-is-jev-and-how-devops-teams-can-use-typesafes-ai-model | DevOps tutorial | Alert triage (page/slack/ticket/suppress), CI flaky-vs-real, command guardrails, **one Noul per log cluster** for "user-facing failure?". Shadow mode, fail toward humans. |
| GitHub shivam2003-dev/typesafe-triage-guard | support + observability alert triage + deploy-risk gate | Composable judgment pipelines. |
| GitHub jeremymungai/jev-security-playground | SOC triage (auth logs: spray vs brute force vs compromise) | System1 inline triage, ambiguous → System2 LLM. |
| SereneDB examples/demo7 (local) | Jev via SQL generated column | Native integration path. |

## Implications for us
- Don't use Jev for raw log *parsing/format ID* — use templates (Drain / regex) + SQL. Use Jev on **semantic** judgments
  over templates/clusters/incident windows (user impact? root-cause candidate? recurring same cause? severity level).
- Always template + dedupe before Jev (cost + consistency); SereneDB already dedupes identical texts per chunk.
- Must benchmark vs: (a) LLM same questions, (b) classical classifier (TF-IDF+LR / fine-tuned small model) on labeled set,
  (c) rules. Metrics: accuracy/F1, calibration (Brier/ECE), self-consistency, latency, $ per 1M logs.
- Datasets to consider: Loghub (HDFS, BGL, Thunderbird, OpenStack… with anomaly labels), LogHub-2.0, plus our own
  scenario-based synthetic set with ground-truth incidents.
