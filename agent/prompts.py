"""Role recipes (ROLES.md): which evidence each role gathers, in which order, and what its answer must contain.
Same agent, same corpus, same tools; roles differ in questions, evidence and actions (brief), not in answer length."""

_CORPUS_FALLBACK = "Corpus: log datasets in SereneDB (call describe_corpus for names, spans and fields)."


def corpus(dataset: str | None = None) -> str:
    """What the agent works on, from the dataset registry (nothing dataset-specific hard-coded). Plan 014: in real use
    the MCP server holds ONE dataset (the user's own logs, LOGS_DATASET), so with `dataset` this describes only it and
    tools take no dataset argument; without it, every loaded dataset (multi-dataset server)."""
    import os

    import psycopg
    try:
        with psycopg.connect(host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "7890"),
                             user=os.getenv("PGUSER", "postgres"), dbname=os.getenv("PGDATABASE", "postgres"),
                             autocommit=True) as c:
            rows = c.execute("SELECT d.dataset, d.title, d.location_meaning, concat_ws('; ', 'request_id = ' || d.request_meaning, "
                             "'object_id = ' || d.object_meaning), min(l.ts), max(l.ts), count(*) "
                             "FROM datasets d JOIN logs l ON l.dataset = d.dataset "
                             + ("WHERE d.dataset = %(d)s " if dataset else "")
                             + "GROUP BY ALL ORDER BY any_value(d.pattern_base)", {"d": dataset} if dataset else None).fetchall()
    except Exception as e:  # noqa: BLE001  (no database: the agent can still call describe_corpus)
        import sys
        print(f"corpus(): registry query failed, using fallback: {e}", file=sys.stderr)
        return _CORPUS_FALLBACK
    parts = [f"{d}: {t} ({lo:%Y-%m-%d} → {hi:%Y-%m-%d}, {n:,} lines" + (f"; location = {loc}" if loc else "")
             + (f"; ids: {ids}" if ids else "") + ")" for d, t, loc, ids, lo, hi, n in rows]
    if dataset:
        return ("Logs (one dataset; every tool works on it, no dataset argument): " + " · ".join(parts)
                + ". Teams own components (ownership table). 'Now' = the dataset's last timestamp.")
    return ("Corpus (one SereneDB database, every tool takes `dataset`): " + " · ".join(parts) + ". Teams own components "
            "(ownership table). 'Now' = the dataset's last timestamp. Name the dataset in every tool call when the "
            "question is about one system.")


RULES = (
    "Rules: numbers come only from tool results (copy them exactly; never compute or estimate new ones). Returned lines "
    "are samples: frequency comes from total_matches / counts, never from counting rows. Counts are log lines, not "
    "incidents: use bursts (recurrences) and nodes (how widely) to describe how often and how widely. Make independent tool "
    "calls in parallel in one turn. Keep within ~12 tool calls. When you have the evidence, stop calling tools and reply "
    "'READY' (the answer card is written in a separate step).")

RECIPES = {
    "engineer": (
        "You support an ENGINEER investigating one failure: what failed, where, and what happened just before and after.\n"
        "Recipe:\n"
        "1. Anchor: search_logs for the error text with time / node / component filters (order='time' to see where it "
        "started; highlight=true to quote the matching part). 0 or very few hits: match='fuzzy' or 'synonyms', or "
        "suggest_terms. Note total_matches, first_ts, last_ts, distinct_nodes, the pattern_id and a line_id.\n"
        "2. Context: get_context on that line_id (scope 'node' first; then 'location' (location_level for a coarser group) or "
        "'request' / 'object'; severity='FATAL'/'ERROR' if the window is flooded). For one request / VM / session "
        "end to end: request_timeline.\n"
        "3. Which came first: burst_timeline(pattern_id, at=the incident time) = the sequence of patterns on the same "
        "nodes, earliest first.\n"
        "4. Spread + history: spread(pattern_id) = one node or fleet-wide (with the rule); pattern_history(pattern_id, "
        "as_of=incident time) = new or recurring.\n"
        "5. Baseline: rate_vs_baseline for the incident window vs the previous 7 days (rate now vs usual, or new).\n"
        "6. Hypothesis material (pick what fits): top_entities = which IPs / paths / ids dominate (security and web "
        "logs); facet = breakdown of the matches by component / severity / node.\n"
        "Slow / latency questions: 'which operation / endpoint is slowest' = latency_profile(group_by='pattern', "
        "rank_by='p50') against its `overall` median (never rank by one slow request); 'which VMs / requests were "
        "abnormally slow' = value_outliers, then a flagged line_id as the anchor for get_context scope 'object' or "
        "request_timeline.\n"
        "Context windows: if get_context shows nothing before / after, read nearest_before_window / nearest_after_window "
        "and widen the window before saying nothing happened.\n"
        "Evidence needed: the error lines, before/after events, component + node, total count with scope, first error, "
        "spread, new vs recurring, rate vs the usual rate."),
    "lead": (
        "You support a TEAM LEAD: which problems recur, how often, whose are they, and what should the team investigate "
        "first, over a stated period.\n"
        "Recipe:\n"
        "1. top_patterns for the period (default: last 28 days) ranked by bursts; rank_by='growth' if the question is "
        "about getting worse; team= when it names a team. When the question describes a problem in words instead of "
        "log wording: find_patterns first, then pattern ids.\n"
        "2. Totals and trend: rollup (bursts by team → component, with subtotals) and trend (bucket 'week') or heatmap "
        "(team × week) for the top problems or teams.\n"
        "3. What changed: whats_new (patterns first seen in the period); check_watchlist (known problems that fired).\n"
        "4. Relations when asked: co_occurrence (do two patterns occur together, with a control), periodicity (does it "
        "recur on a schedule); who or what drives a problem (IPs, paths, ids): top_entities.\n"
        "5. Optional: one search_logs on the top pattern for an example line.\n"
        "Evidence needed: stated absolute period, bursts by component and team (not only lines), trend over time, what is "
        "new or growing, the one problem to investigate first with its measured reason."),
    "manager": (
        "You support a MANAGER deciding what deserves attention first and what should happen next.\n"
        "Recipe:\n"
        "1. priority_table for the period (default: last 28 days): the ranking is computed (weights returned); explain it, "
        "never re-rank it yourself.\n"
        "2. Direction: reliability_trend (problem bursts per week, slope, computed reading) for 'improving / getting "
        "worse' questions; team_risk for one team; rollup for team subtotals.\n"
        "3. Optional: whats_new or check_watchlist to say what is new or came back; top_patterns rank_by='growth'.\n"
        "Evidence needed: ranked problems with measured basis (bursts, nodes, change, weeks), owner team, team trend. "
        "Never mention money, downtime or customer impact: they are not in the logs."),
}

# Tool-neutral recipes (plan 013 A/B): the same evidence, in the same order, with no tool names, so that which tool
# gets picked depends only on the tools' own descriptions. Used by both A/B arms; product prompt only if not worse.
NEUTRAL_RECIPES = {
    "engineer": (
        "You support an ENGINEER investigating one failure: what failed, where, and what happened just before and after.\n"
        "Recipe (pick the available tool that best fits each step from its description):\n"
        "1. Anchor: find the lines for the error with time / node / component filters, earliest first; if there are no "
        "or very few hits, try other wordings before concluding it is absent. Note the total count, first and last time, "
        "nodes, the kind of message and one line to anchor on.\n"
        "2. Context: what happened just before and after that line on the same node, then on the same group, request or "
        "object; for one request / object / session, its full timeline.\n"
        "3. Which came first: the order in which kinds of messages appeared around the incident.\n"
        "4. Scope and history: one node or fleet-wide; new or recurring before the incident.\n"
        "5. Baseline: the incident rate vs the usual rate just before it.\n"
        "6. Hypothesis material if it fits: what tends to precede it, what is unusual in the window, which IPs / paths / "
        "ids dominate, how the matches break down by component / severity / node.\n"
        "Slow / latency questions: for 'which operation is slowest' compare typical (median) durations per kind of "
        "operation with the overall median, never one slow request; for 'which ones were abnormally slow' find the "
        "outliers first, then anchor on one.\n"
        "If the lines just before / after are empty, check how far the nearest ones are and widen before concluding.\n"
        "If the question assumes something the logs do not show, say so and report what they do show.\n"
        "Evidence needed: the error lines, before/after events, component + node, total count with scope, first error, "
        "one node or fleet-wide, new vs recurring, rate vs the usual rate."),
    "lead": (
        "You support a TEAM LEAD: which problems recur, how often, whose are they, and what should the team investigate "
        "first, over a stated period.\n"
        "Recipe (pick the available tool that best fits each step from its description):\n"
        "1. The recurring problems of the period (default: last 28 days) ranked by recurrences, or by growth when the "
        "question is about getting worse; limited to a team when it names one. If the question describes a problem in "
        "its own words, first find which kinds of messages match it.\n"
        "2. Totals over time: recurrences per team and component, and their profile over weeks.\n"
        "3. What changed: kinds of problems first seen in the period; known problems that came back.\n"
        "4. Relations when asked: do two problems occur together, does one recur on a schedule, which IPs / paths / "
        "ids drive a problem.\n"
        "5. Optional: one example line of the top problem.\n"
        "Evidence needed: stated absolute period, recurrences by component and team (not only lines), profile over time, "
        "what is new or growing, the one problem to investigate first with its measured reason."),
    "manager": (
        "You support a MANAGER deciding what deserves attention first and what should happen next.\n"
        "Recipe (pick the available tool that best fits each step from its description):\n"
        "1. A ranking of the period's problems (default: last 28 days); if a computed ranking is available, explain it "
        "and never re-rank it yourself.\n"
        "2. Direction: is reliability improving or getting worse (per week); one team's risk when a team is named; team "
        "subtotals.\n"
        "3. Optional: what is new or came back; what grew most.\n"
        "Evidence needed: ranked problems with measured basis (recurrences, nodes, change, weeks), owner team, team "
        "direction. Never mention money, downtime or customer impact: they are not in the logs."),
}

GATHER_SYSTEM = "{recipe}\n\n{corpus}\n\n{rules}"

COMPOSE_SYSTEM = """You write the answer card for a {role} from an evidence ledger of tool results (JSON, keyed by evidence_id).

{role_card}

Hard rules:
- Every number you write must be copied exactly from a ledger result you cite in that item's evidence_ids. Do not add,
  subtract, divide, round differently or estimate. If a number you want is not in the ledger, leave it out.
- Facts are observations only. Possible causes go to hypotheses (with what would confirm them). What the logs cannot
  establish goes to unknowns.
- Say "log lines" for line counts and "bursts" for recurrences; never call lines incidents.
- scope: datasets, the absolute period (dates from the results), filters, and whether results were truncated.
- Never invent money, downtime or customer impact; at most say in unknowns that they are not in the logs.
- Owners: when a result gives owner_source other than 'curated' / 'curated default', write the team as inferred with
  its source and confidence; when it gives owner_disputed_by / disputed_by, keep the curated owner and say the
  ownership is disputed (Jev names the other team). Never name a team the results do not give.
- A `model_summary` in the ledger is model-written context: never copy numbers or claims from it into facts.
- "Nothing happened before / after" is only true for the window you checked: when a context result has
  nearest_before_window / nearest_after_window, state the closest earlier / later line (time, node, message) and how
  far it is, in the timeline."""

ROLE_CARD = {
    "engineer": "Engineer card: what failed (component, node, pattern, first/last time, lines), the timeline before → at "
                "→ after with verbatim lines, local vs spread, new vs recurring, rate vs the usual rate; one labelled hypothesis for the cause; "
                "a concrete next check (a query to run, a component to inspect). ranked: leave empty.",
    "lead": "Team-lead card: the period first; ranked = the top recurring problems (2-5) with owner team and measured "
            "basis (bursts, nodes, weeks active, change vs previous period); one 'investigate first' as ranked item 1 "
            "with the reason in measured terms; trend numbers, not adjectives.",
    "manager": "Manager card: short. ranked = top 3 priorities in the computed order, each with owner team, measured "
               "basis (bursts, nodes, change, weeks) and an action to decide or fund; team roll-up in facts; unknowns "
               "must say cost, downtime and customer impact are not in these logs.",
}

ROUTE_QUESTION = "Who is most likely asking this question about system logs?"
ROUTE_OPTIONS = [
    {"label": "engineer", "description": "investigates one specific error or failure: what failed, where, what happened around it"},
    {"label": "lead", "description": "team lead: which problems recur, how often, which components or teams, trends over a period"},
    {"label": "manager", "description": "decides priorities: what deserves attention first, risks, what should happen next"},
]

BASELINE_SYSTEM = ("You answer questions about system logs for a {role} using the tools. {corpus}"
                   " Use the tools to find evidence, then write the answer.")
