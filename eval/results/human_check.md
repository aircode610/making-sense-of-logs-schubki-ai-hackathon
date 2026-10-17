# Judge sanity check (plan 009): rate 6 answers by hand, without looking at the key

For each answer give 1-5 for: **role fit**, **next-step specificity**, **evidence use**, **separation** (facts vs hypotheses vs unknowns), **clarity** (anchors in `eval/judge.py`). Fill the table at the end, then compare with `human_check_key.md`.

## Answer A (D-M03, role: manager)
**Question:** Which team's area carried the most risk in September 2005 (2005-09-01 to 2005-10-01), and is it getting better or worse?

node-platform carried the most risk in September 2005: it has the most bursts of any team and owns the top two ranked problems. Its burst count is roughly flat against the prior period (268 vs 275), while hpc-workloads is getting clearly worse (106 bursts vs 23).
Scope: bgl dataset (priority and team roll-up), 2005-09-01 to 2005-10-01, compared with 2005-08-02 to 2005-09-01. Candidates are problem patterns only. The priority table is truncated: 143 candidates matched and only the top 10 items are listed. The team roll-up covers all candidates. openstack had 0 matches. Log-line counts by team cover all datasets for the period and are not truncated.
node-platform: 45 problem patterns, 268 bursts vs 275 in the previous period (change -7), 26763 log lines.
hpc-workloads: 88 problem patterns, 106 bursts vs 23 in the previous period (change 83), 52757 log lines.
cluster-control: 10 problem patterns, 44 bursts vs 64 in the previous period (change -20), 70389 log lines.
Total log lines by team over the whole period (all patterns): node-platform 83298, cluster-control 83222, hpc-workloads 52757, out of 219277.
The two highest-scoring patterns, 609 (score 98.5) and 69 (score 96.0), are both owned by node-platform. hpc-workloads' top item, pattern 478, scores 94.2.
The ranked items after the top three are all hpc-workloads patterns flagged as new this period, each with 1 burst. They are program-image or directory load errors.
1. Lustre mount FAILED on I/O nodes (network or I/O failure) — owner node-platform — 40 bursts vs 2 in the previous period (change 38), 1024 nodes, 3 weeks active, score 98.5 — Decide whether to fund a focused investigation of the Lustre mount and I/O path, since this pattern is spreading across all 1024 nodes.
2. rts panic! - stopping execution (system software failure) — owner node-platform — 49 bursts vs 24 in the previous period (change 25), 279 nodes, 5 weeks active, score 96.0 — Ask node-platform for a cause and fix plan. The pattern was active in all 5 weeks and its burst count has roughly doubled.
3. ciod: Link has been severed while reading the message prefix (network or I/O failure) — owner hpc-workloads — 14 bursts vs 13 in the previous period (change 1), 1024 nodes, 4 weeks active, score 94.2. The hpc-workloads team total rose from 23 to 106 bursts (change 83). — Decide whether hpc-workloads and node-platform should review the link-severed errors jointly, and have hpc-workloads explain its jump in bursts.
Hypothesis: The hpc-workloads increase may come from many new job-submission errors (missing program images or directories) rather than from one persistent fault. Would confirm: Check whether the new patterns share users or job launchers, and whether they stop after the paths are fixed.
Hypothesis: The Lustre mount failures and the link-severed errors may share a network or I/O cause. Would confirm: Compare the timing of the bursts of patterns 609 and 478, and review the I/O-node and network health records.
Unknown: Cost, downtime and customer impact are not in these logs.
Unknown: Root cause is not established by these logs.
Unknown: The priority table is truncated, so team rankings beyond the top 10 items rely on the roll-up only.
Next step: Request a cause-and-fix plan for Lustre mount failures (pattern 609) and rts panics (pattern 69), with a date for the next review. — These are the two top-ranked problems: 40 bursts vs 2 and 49 bursts vs 24.
Next step: Review the new program-image and directory errors and the overall growth in bursts (106 vs 23). — It is the fastest-worsening team, with a change of 83 bursts.

## Answer B (D-E01, role: engineer)
**Question:** What failed on the R43-M0 midplane around 2005-08-19 13:56, and what happened just before and after?

Two KERNEL FATAL 'kernel panic' log lines (pattern 576) hit two different nodes on R43-M0 at 2005-08-19 13:56:00.280831 and 2005-08-19 13:56:00.628434, within the same second. Nothing else was logged on R43 in the hour before, and only the second panic line followed in the hour after.
Scope: Dataset bgl. Main window 2005-08-19 13:46:00 → 2005-08-19 14:06:00, midplane R43-M0. Context window on rack R43, 2005-08-19 12:56:00.280831 → 2005-08-19 14:56:00.280831. Pattern 576 history covers corpus start → corpus end (matches from 2005-08-15 16:31:53.274944 to 2005-11-11 13:51:11.907657). The R43-M0 window, the context and the pattern 576 results were not truncated. The full-history R43-M0 query was truncated (8739 matching lines, only the first rows returned), so it is not a complete history.
In the window 2005-08-19 13:46:00 → 2005-08-19 14:06:00, R43-M0 has 2 log lines across 2 distinct nodes, first 2005-08-19 13:56:00.280831 and last 2005-08-19 13:56:00.628434.
At 2005-08-19 13:56:00.280831, node R43-M0-NC-I:J18-U01 logged component KERNEL, severity FATAL, body 'kernel panic' (line_id 3069219, pattern_id 576).
At 2005-08-19 13:56:00.628434, node R43-M0-N8-I:J18-U11 logged component KERNEL, severity FATAL, body 'kernel panic' (line_id 3069220, pattern_id 576).
Before the first panic, rack R43 had 0 log lines in the preceding hour (before_total 0).
After the first panic, rack R43 had 1 log line in the following hour (after_total 1), which is the second kernel panic line on R43-M0-N8-I:J18-U11.
Pattern 576 ('kernel panic') has 18 log lines on 18 distinct nodes in bgl, first 2005-08-15 16:31:53.274944 and last 2005-11-11 13:51:11.907657. Each log line is on a different node, so it recurs across the machine.
Earlier pattern 576 lines were on other racks: R04-M0-N8-I:J18-U01 at 2005-08-15 16:31:53.274944, R24-M1-N4-I:J18-U11 at 2005-08-15 16:31:54.039941, and R10-M0-N4-I:J18-U11 at 2005-08-15 17:03:49.739447. Later lines were on R57-M1, R66-M1 and R67-M1 on 2005-08-23.
R43-M0 has 8739 log lines overall across 541 distinct nodes, with the first at 2005-08-04 10:39:53.744546. The first rows are DISCOVERY WARNING/SEVERE/ERROR lines such as 'Node card is not fully functional' (pattern 165) on R43-M0-N6, R43-M0-N4, R43-M0-N8 and R43-M0-N1. That is more than two weeks before the panics.
Hypothesis: The two panics may be one burst from a shared cause affecting the midplane (for example a job or boot failure on that partition), not two independent node faults. Both lines fall within the same second, on the same midplane, with the same pattern and severity. Would confirm: Check whether the two nodes were in the same job or partition, and whether the other pattern 576 close pairs (R57-M1 on 2005-08-23, R04/R24 on 2005-08-15) show the same shape.
Unknown: The root cause of the kernel panics is not in these logs. The lines contain only the body 'kernel panic', with no stack trace or error code.
Unknown: The ledger shows no log lines on R43 in the hour before the panic, so any precursor would be outside this log source or on other racks.
Unknown: Whether the nodes recovered or were rebooted is not shown. No lines follow on R43 other than the second panic.
Unknown: Job impact, downtime and customer impact are not in the logs.
Unknown: The full R43-M0 history was truncated, so whether R43-M0 had earlier kernel panics is not established from the first rows returned.
Unknown: Only part of the pattern 576 rows was shown, so the remaining locations are not established from the ledger.
Next step: Pull the pattern 576 rows that were not shown and check which racks and midplanes they involve. Also query bgl for pattern_id 576 grouped by midplane and ts to see whether R43-M0 appears elsewhere. — The ledger shows only part of the 18 pattern 576 lines. This would tell whether R43-M0 is a repeat location or a one-off.
Next step: Query bgl across all racks for the window 2005-08-19 13:46:00 → 2005-08-19 14:06:00 without the midplane or rack filter, plus any job or control-system logs for R43-M0 around 2005-08-19 13:56:00.280831. — The R43 context shows no lines before the panic. A wider search could find a precursor on other components or racks.

## Answer C (D-M02, role: manager)
**Question:** Based on October 2005 (2005-10-01 to 2005-11-01), which observed problems deserve attention first and what should happen next?

**October 2005 summary (BGL only; there are no OpenStack logs in this window)**

The ranking below comes from the priority score, which weighs how often a problem recurs, its trend, how many nodes it touches, how many weeks it appears, and a fault judgment. It doesn't know cost, downtime or customer impact, and the logs don't show root cause.

**Attention first**

1. **Memory and cache hardware errors on a small set of nodes (node-platform).**
   - These patterns top the ranking (scores 74–82):
     - uncorrectable error in external DDR, EDRAM and directory
     - DDR failing address and data registers
     - parity error in bank and read queue
     - memory manager uncorrectable error
   - Each one recurred 4 times in October, up from 2 in the prior period, across 4 nodes, and each was active in 4 of the 6 weeks.
   - The identical counts suggest one shared fault, but I didn't check whether they hit the same 4 nodes.
   - These are the most clearly hardware-related faults (fault probability 0.84–0.96).
   - **Next:** node-platform should list the affected nodes and node cards. They should check whether the patterns are one incident or several, and pull or replace the suspect DIMMs or cards if the same nodes repeat.

2. **Machine check interrupts (node-platform).**
   - "L3 major internal error" rose from 5 to 10 bursts on 8 nodes.
   - The generic "machine check interrupt" (34 bursts on 34 nodes) and "L1 dcache data parity error" (14 bursts on 13 nodes) are steady, not rising.
   - Each node is hit only about once, so this looks like a broad pattern rather than one bad node.
   - **Next:** check whether the affected nodes cluster in the same racks or midplanes, and watch the rising L3 pattern.

3. **"Kill job … timed out. Block freed." (node-platform).**
   - This is the most frequent problem, at 44 bursts, up from 29, and it was active in all 6 weeks.
   - The log lines carry no node, so the affected hardware can't be identified from them.
   - **Next:** correlate the job IDs with the scheduler and job logs to see whether the timeouts follow the hardware faults above or have a separate cause.

**Watch, but lower priority**

- **"rts panic! – stopping execution"** (33 bursts on 38 nodes) is falling from 51. It is still large and has a high fault probability (0.96).
- **"Can not get assembly information for node card"** (cluster-control/DISCOVERY) produced 1,121 lines on 254 nodes, in 20 bursts, down from 23. It is steady and widespread. It is probably a discovery or service-network issue rather than 254 separate failures, so cluster-control should check the common cause.
- **hpc-workloads (APP/ciod)** is the only team whose problems grew sharply, from 18 to 43 bursts. It produced about 36,000 lines.
  - The biggest pattern, "Link has been severed" on CioStream, hit about 1,000 nodes in 8 bursts, down from 14.
  - The top-scoring item is a "Permission denied" program-image load error for a single user's HPCC job.
  - These look like job or I/O issues, and the permission error looks like a user or configuration problem.
  - **Next:** hpc-workloads should confirm whether the growth is a few storms or a trend, and fix the permissions on that job.

**Overall:** Start with node-platform's memory and machine-check faults, because they are recurring, rising and hardware-related. In parallel, find out whether the job-timeout and ciod errors are consequences of those faults or independent.

## Answer D (D-L06, role: lead)
**Question:** Which recurring problems got worse in October 2005 (2005-10-01 to 2005-11-01) compared with September, and who owns them?

Among the patterns shown, every one that got worse in October 2005 is owned by node-platform. The one to investigate first is "Kill job <N> timed out. Block freed.", which went from 29 bursts to 44, a change of 15. The results are truncated, so this is not a complete list.
Scope: Dataset bgl, 2005-10-01 to 2005-11-01. Comparison window is the tool's previous period, 2005-08-31 to 2005-10-01. Filter: patterns with problem log lines and p_problem >= 0.5. 84 patterns matched; each ranking query returned 15 and showed 12 (truncated). Team log-line counts cover all datasets for October. The weekly trend is truncated to 12 of 30 rows.
Pattern 261 "Kill job <N> timed out. Block freed." (KERNEL, node-platform, FATAL) had 44 bursts in October versus 29 in the previous period, a change of 15. It had 47 log lines and was active in 6 weeks. The results list 0 nodes for it.
Pattern 93 "machine check interrupt (bit=<N>): L<N> major internal error" (node-platform, FATAL) had 10 bursts versus 5 before, a change of 5. It had 10 log lines across 8 nodes and was active in 5 weeks.
Ten other node-platform FATAL patterns each went from 2 bursts to 4, a change of 2, each active in 4 weeks across 4 nodes. Pattern ids: 120, 122, 123, 124, 125, 126, 135, 153, 154, 158. These are the uncorrectable-error, parity-error and DDR patterns. Their first_seen times are all on 2005-06-08 between 04:48:52 and 04:48:58.
Several large patterns improved: pattern 69 "rts panic! - stopping execution" went from 51 bursts to 33 (change -18). Pattern 478 (ciod link severed, hpc-workloads) went from 14 bursts to 8 (change -6). Pattern 33 "machine check interrupt" went from 38 to 34 (change -4). Pattern 166 (DISCOVERY, cluster-control) went from 23 to 20 (change -3).
Pattern 86 (L<N> dcache unit data parity error, node-platform) was flat at 14 bursts versus 14 (change 0).
October log lines by owning team: node-platform 112809, hpc-workloads 36295, cluster-control 4247, out of 153351 total.
Weekly cluster-control log lines in October were 486, 3021, 335 and 405, for weeks starting 2005-10-03, 10-10, 10-17 and 10-24. The week of 2005-09-19 had 75763.
1. Pattern 261, "Kill job <N> timed out. Block freed.": jobs killed on timeout, classified as job or application failure. Investigate first. — owner node-platform — 44 bursts versus 29 previously (change 15), the largest increase in bursts. 47 log lines, active in 6 weeks. — Check which jobs and blocks the timeouts hit and whether they cluster in time. The node field shows 0 nodes, so find where the node is recorded.
2. Pattern 93, machine check interrupt: L<N> major internal error (hardware failure). — owner node-platform — 10 bursts versus 5 (change 5), 8 nodes, 5 weeks active. — Review the 8 affected nodes for repeat offenders and decide whether hardware inspection is needed.
3. Ten uncorrectable-error, parity-error and DDR patterns (ids 120, 122, 123, 124, 125, 126, 135, 153, 154, 158) that doubled together. — owner node-platform — Each went from 2 bursts to 4 (change 2), across 4 nodes and 4 weeks active. — Check whether the patterns occur at the same moments on the same 4 nodes. If so, treat them as one memory or hardware problem, not ten.
Hypothesis: The ten patterns with identical burst counts (4 versus 2) and nodes may be one underlying hardware event that the logs split across several message templates. Would confirm: Compare burst start times and node names across these patterns. Matching timestamps and nodes would support a single event.
Hypothesis: The rise in pattern 261 timeouts may be linked to the machine-check and uncorrectable-error patterns, with jobs hanging on faulty hardware. Would confirm: Check whether the timeout bursts follow the machine-check bursts on the same blocks or nodes.
Unknown: Because the results are truncated, patterns beyond the 12 shown (84 matched) with a change of 2 or less, possibly in other teams, are not visible.
Unknown: The tool's previous period starts 2005-08-31, so it is not exactly calendar September.
Unknown: The logs cannot establish root cause, downtime, cost or customer impact.
Unknown: Pattern 261 shows 0 nodes, so which nodes it affected is unknown from these results.
Next step: Pull the 44 October bursts of pattern 261 with job and block details, and compare against the 29 earlier bursts. — It has the largest increase in bursts (change 15) and is classified as job or application failure.
Next step: Overlay burst times and node lists for pattern 93 and the ten 4-burst patterns to see whether they are one event. — Pattern 93 went from 5 bursts to 10, and the ten patterns each went from 2 to 4 across 4 nodes.
Next step: Rerun the comparison with a larger limit or per-team filters to cover the remaining matches. — Results were truncated: total_matches is 84 and only part of them was shown (ev-a6c82b8456).

## Answer E (D-E04, role: engineer)
**Question:** Why did nova-api return HTTP 503 errors, when did it happen, and what happened around those requests?

nova-api returned HTTP 503 twice in the whole corpus. In both cases the identity (Keystone) service failed to validate the auth token. The logs don't show why Keystone failed.

**When**

| # | Time (UTC) | Request id | Request |
|---|---|---|---|
| 1 | 2017-05-16 06:25:02.87 | `req-1cc7d50c-…` | `GET /v2/54fadb41…/servers/detail` |
| 2 | 2017-05-17 06:25:03.05 | `req-abcdb287-…` | `GET /v2/54fadb41…/servers/detail` |

The two events are almost exactly 24 hours apart, within about 0.2 s of the same time of day. That points to something scheduled or periodic rather than random failures.

**Why**

Each 503 came with the same four log lines within about 3 ms of each other:
1. ERROR: `Bad response code while validating token: 503`
2. WARNING: `Identity response: <!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">`. The identity endpoint returned an HTML error page instead of a token reply, which usually means a web server or proxy error page.
3. CRITICAL: `Unable to validate token: Failed to fetch token data from identity server`
4. INFO: the access line with `status: 503 len: 323`, returned in 8–10 ms.

nova-api itself was not overloaded. The 503s came back in about 8–10 ms, against roughly 250–400 ms for normal `servers/detail` calls. So the request was rejected at the token-validation step, before any nova work. The cause is the identity service or the proxy in front of it being unavailable at that moment.

**What was happening around them**

- **Before:** the same client (10.11.10.1) was polling `GET servers/detail` about every 1.3 s. Each call returned 200 in about 250–280 ms.
- **Same request ids:** in both cases the request id also appears on a 200 response about 1 s earlier (06:25:01.857 for #1, 06:25:02.033 for #2). I haven't checked why a request id appears twice. It may be how the client reuses ids.
- **Compute side:** nova-compute showed nothing abnormal. The usual periodic image-cache check (`Active base files`) and resource audit were running.
- **Event 2:** a new instance (`96c58299…`) was spawning on the hypervisor at the time. It finished successfully, `Took 22.16 seconds to build instance`.
- **After:** other API calls returned 200 again within seconds. In event 2, the next lines were `os-server-external-events` and metadata calls, all 200. The outage lasted only a few seconds, and I found no 503s other than these two.

**Caveats and next steps**

- The logs show nova-api's side only. The root cause (Keystone or Apache/proxy restart, a scheduled job, or a token-cache or connection hiccup around 06:25 UTC) would be in the identity service's own logs and any cron or maintenance schedule at that time.
- Impact was small: 2 failed requests out of the thousands in the corpus.

## Answer F (D-L04, role: lead)
**Question:** Is 'rts panic! - stopping execution' one bad node or fleet-wide in October 2005 (2005-10-01 to 2005-11-01)?

**It's fleet-wide, not one bad node.** The message is spread thinly across many nodes, with one small cluster on 23 October.

- **Volume and spread:** There were 46 lines from 38 distinct nodes between 2005-10-01 and 2005-10-31. All are KERNEL, FATAL, pattern 69.
- **No single node dominates:** The worst nodes have only 2 lines each. 30 of the 38 nodes logged it exactly once. The nodes sit across many racks, including R00, R02, R04, R10, R15–R17, R20–R23, R25, R26, R30–R31, R33, R35, R42, R44, R50–R52, R60, R62–R63, R72, R75 and R77.
- **Timing:** It shows up on most days, with quiet gaps (5–11 October, 14–17 October, 24–25 October). That is a steady background of single-node panics.
- **The 23 October burst:** 14 lines landed that day, and 17 over 22–23 October. Two bursts, around 10:22 and 23:56, were each a few seconds long and hit several nodes at once. They involved:
  - the R30-M1-NF node card (J13, J15, J16 and J17 units);
  - R31-M1-N9;
  - R10-M0-NE.

  This looks like a correlated event, possibly a shared job or a node-card issue. That is a hypothesis, and I didn't check what else was logged at those times. R30-M1-NF is the only place with repeated hits.

**Bottom line:** Treat the October pattern as a diffuse, fleet-wide background of panics. Look separately at R30-M1-NF and the 23 October bursts. Replacing one node wouldn't remove the background rate.

## Your scores

| label | role_fit | next_step | evidence_use | separation | clarity | rater |
|---|---|---|---|---|---|---|
| A | | | | | | |
| B | | | | | | |
| C | | | | | | |
| D | | | | | | |
| E | | | | | | |
| F | | | | | | |