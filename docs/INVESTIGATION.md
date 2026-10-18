# Worked investigation: the ciod "Link has been severed" storm (BGL, November 2005) + the base corpus

One Claude Code session with only our `logs` MCP server: 20 tool calls, 1.8 s inside SereneDB in total. Every number
below comes from a tool result. **62 / 62 numbers in the answer were found in a result**, and **17 / 17 read steps give
the same result when re-run** on a read-only database role (the other 3 steps switch datasets).

**Open the evidence: [`docs/investigation/report.html`](investigation/report.html)** (a static page, no server needed:
the answer with every number linked to its step, the SQL of each step, and the Verify result of each step). To
reproduce it live, ask Claude in this repo the same three questions below; the server writes the same kind of page to
`http://127.0.0.1:8765/latest`.

Why this topic: we did not pick it. It is **rank 1** of the manager's computed priority ranking for November 2005
(step 3), and it is new in that month. One problem seen three ways shows how the roles differ.

## The questions
| Role | Question |
|---|---|
| Engineer | What failed in November 2005 across the I/O nodes, where, and what happened just before and after? |
| Team lead | Which problems recurred in November 2005 (2005-11-01 → 2005-12-01), how often, and which teams own them? |
| Manager | Based on November 2005, which problems deserve attention first and what should happen next? |
| (Scope) | How do all lines of the base corpus split by team? (whole-corpus aggregation, BGL + OpenStack) |

## Tool calls (the session, in order)
| Step | Tool | Arguments | Result (cited) | SereneDB |
|---|---|---|---|---|
| 3 | `priority_table` | bgl, 2005-11-01 → 2005-12-01 | 133 candidates; #1 pattern 968 score 97.8 | 127 ms |
| 4 | `search_logs` (full text) | `"Link has been severed"`, Nov 2005 | **12,996 lines, 1,024 nodes**, 11-17 05:33 → 11-30 07:07 | 31 ms |
| 5 | `pattern_history` | pattern 968, as_of 2005-11-01 | 0 lines before → new; 26,546 lines / 82 bursts in all | 53 ms |
| 6 | `burst_timeline` | pattern 968 at 11-17 05:33, 30 min before | burst 1 = 504 lines / 504 nodes; 05:12 "xhpl … Permission denied" (64), 05:14 "Received signal" (424) | 23 ms |
| 7 | `top_entities` | ip, pattern 968 | one peer: 172.16.96.116 on all 26,546 lines | 40 ms |
| 8 | `precursors` | pattern 968, 600 s, control 1 day earlier | register-dump patterns precede 40 % of bursts (lift 33) | 90 ms |
| 9 | `top_patterns` | Nov 2005 | by bursts: Kill job timed out 37, rts panic 35, Link severed 31 (new) | 254 ms |
| 10 | `rollup` | team, Nov 2005 | 451 problem bursts: node-platform 283, hpc-workloads 106, cluster-control 62 | 30 ms |
| 12 | `reliability_trend` | weeks 2005-10-03 → 12-04 | 69.6 → 119.25 bursts / week, "worsening" (rule in result) | 77 ms |
| 13 | `owner_of` | APP | curated hpc-workloads; Jev hints node-platform (p 0.939): **disputed** | 85 ms |
| 14, 15 | `count_by` | team (all lines; FATAL) | BGL 4,747,963 lines; FATAL 855,501 | 321 / 79 ms |
| 17 | `count_by` | team (openstack) | 207,820 lines: cloud-compute 104,952, cloud-api 102,868 | 27 ms |
| 18 | `value_outliers` | openstack | 6 VMs with slow builds; slowest spawn 50.72 s vs median 19.74 s | 149 ms |
| 19 | `search_logs` | status 503 (openstack) | 2 lines in 3 days | 10 ms |

The executed queries (exact SQL, values inlined) are in every result and in the report page. Two of them:
```sql
-- step 4: full-text search (inverted index), exact total over all matches
SELECT count(*) AS total_matches, min(ts), max(ts), count(DISTINCT node) FROM logs
WHERE dataset = 'bgl' AND ts >= '2005-11-01' AND ts < '2005-12-01'
  AND body @@ websearch_to_tsquery('"Link has been severed"');
-- step 10: problem bursts per team (ownership table + Jev problem filter), GROUP BY ROLLUP
SELECT coalesce(o.team, 'unowned') AS team, count(*) AS bursts FROM bursts b
JOIN patterns p ON … LEFT JOIN ownership o ON … LEFT JOIN pattern_judgments j ON …
WHERE p.problem_lines > 0 AND j.p_problem >= 0.5 AND b.dataset = 'bgl'
  AND b.start_ts >= '2005-11-01' AND b.start_ts < '2005-12-01'
GROUP BY ROLLUP (coalesce(o.team, 'unowned'));
```

## The three answers

### Engineer: what failed, where, before / after
**Facts.** A message never seen before November appeared on 2005-11-17 at 05:33:24: FATAL APP *"ciod: Error reading
message prefix on CioStream socket to 172.16.96.116, Link has been severed"*. In November it accounts for 12,996 lines on
1,024 nodes (full-text search, step 4). Its first burst hit 504 I/O nodes in 4 minutes. On those same nodes, 21 minutes
earlier, 64 nodes had failed to load `/bgl/apps/followup/HPL/xhpl` (*Permission denied*), followed by 424
*"ciod: Received signal"* lines (step 6). Every line names the same peer, 172.16.96.116 (step 7).
**Hypothesis (not established).** The I/O nodes lose their control connection to one service host, possibly after a
failed job launch. The host's own log at 05:33 would confirm it.
**Unknown.** The root cause: the logs of 172.16.96.116 are not in the corpus.
**Next check.** The service-node log of 172.16.96.116 for 2005-11-17 05:30–05:40, and the job that launched `xhpl`.

### Team lead: what recurs, how often, whose
**Facts.** November 2005 has 451 problem bursts (recurrences, not incidents): node-platform 283, hpc-workloads 106,
cluster-control 62 (step 10). The most frequent are *Kill job timed out* (37 bursts), *rts panic* (35 bursts on 35
nodes) and the new *Link has been severed* (31 bursts on 1,024 nodes) (step 9). Weekly problem bursts went from a mean of
69.6 to 119.25; the computed reading is "worsening" (step 12). The owner of `APP` is curated as hpc-workloads, but Jev
hints for most of its lines name node-platform (p 0.939) (step 13).
**Next step.** hpc-workloads and node-platform triage the severed-link storm **together**, because the owner is
disputed. Start from burst 1 and the `xhpl` launch failure.

### Manager: what first
**Facts.** This is the computed ranking (weights frequency 0.3, trend 0.2, spread 0.25, persistence 0.15, severity 0.1,
over 133 candidates; step 3):
1. *Link has been severed* (hpc-workloads): score 97.8. New this month, 31 bursts, 1,024 nodes.
2. *rts: kernel terminated* (node-platform): 93.6. 7 bursts, 3,584 nodes.
3. *rts panic* (node-platform): 90.5. 35 bursts, active every week.

Problem bursts went from 9 to 106 for hpc-workloads and from 218 to 283 for node-platform, compared with the previous 30 days.
**Decision.** Name one owner for item 1 now (the ownership is disputed) and fund the cross-team investigation; ask
node-platform for a plan for items 2–3. **Not in the logs:** cost, downtime, customer impact.

### Whole base corpus (aggregation over every line, reported per dataset)
| Dataset | Lines | By team |
|---|---|---|
| BGL | 4,747,963 (FATAL 855,501) | node-platform 4,331,285 · hpc-workloads 228,536 · cluster-control 188,142 |
| OpenStack | 207,820 | cloud-compute 104,952 · cloud-api 102,868 |

OpenStack shows almost no errors: 2 HTTP 503 responses in 3 days (step 19). Its anomaly is slowness, which only an
aggregation can find. 6 VMs built slowly; the slowest took 50.72 s to spawn against a median of 19.74 s (step 18).
These include the 4 VMs labelled anomalous in Loghub (checked in plan 054).

## What the data does and does not establish
- **Established:** when the storm started, where (1,024 I/O nodes, one peer IP), how often (31 bursts in November, 82 in
  all), that it is new, who owns it (with a recorded dispute), and that problem bursts rose over the 9 weeks.
- **Not established:** why the links were severed (the logs of the peer host are not in the corpus), whether the failed
  `xhpl` launch is related (it only came first), and any cost, downtime or user impact.
- **Counting rule:** 12,996 lines are not 12,996 incidents. They are 31 bursts in November.
