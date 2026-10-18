# Tools, prompts and resources of the `logs` MCP server

Generated from the server's own MCP listing by `scripts/tools_doc.py` (what Claude sees, verbatim). 44 tools, 5 prompts, 3 resources + 3 resource templates, argument completions for dataset / component / team / severity.

Every tool result is an envelope: `tool`, `params`, `sql` (exact queries, values inlined), `filters`, `scope`, `total_matches` (exact, over all matches), `truncated`, `elapsed_ms`, `evidence_id`, `rows` (≤ 50, messages cut at 300 chars), `hints` (next step).

## Index

| Tool | Title | Read-only |
|---|---|---|
| [`setup_status`](#setup_status) | Setup and loaded datasets | yes |
| [`load_logs`](#load_logs) | Load logs (base corpus or a file) | no |
| [`use_dataset`](#use_dataset) | Switch the active dataset | no |
| [`remove_dataset`](#remove_dataset) | Remove a dataset | no |
| [`describe_corpus`](#describe_corpus) | What is loaded | yes |
| [`list_values`](#list_values) | Valid filter values | yes |
| [`suggest_terms`](#suggest_terms) | Spelling suggestions | yes |
| [`explain_search`](#explain_search) | Why a search matches | yes |
| [`ingest_report`](#ingest_report) | How a log format was detected | yes |
| [`search_logs`](#search_logs) | Search logs | yes |
| [`get_context`](#get_context) | Events around a line | yes |
| [`facet`](#facet) | Breakdown of matches | yes |
| [`distinctive_terms`](#distinctive_terms) | What is different in a window | yes |
| [`top_entities`](#top_entities) | Top IPs / paths / ids | yes |
| [`check_watchlist`](#check_watchlist) | Saved searches fired | yes |
| [`count_by`](#count_by) | Counts by group | yes |
| [`trend`](#trend) | Counts over time | yes |
| [`rate_vs_baseline`](#rate_vs_baseline) | Rate vs usual | yes |
| [`value_outliers`](#value_outliers) | Slow operations | yes |
| [`top_patterns`](#top_patterns) | Recurring problems | yes |
| [`priority_table`](#priority_table) | Priority ranking | yes |
| [`owner_of`](#owner_of) | Who owns a component | yes |
| [`ownership_gaps`](#ownership_gaps) | Unowned or uncertain owners | yes |
| [`pattern_history`](#pattern_history) | New or recurring | yes |
| [`burst_timeline`](#burst_timeline) | Which error came first | yes |
| [`spread`](#spread) | One node or fleet-wide | yes |
| [`whats_new`](#whats_new) | New problems in a period | yes |
| [`precursors`](#precursors) | What comes before | yes |
| [`co_occurrence`](#co_occurrence) | What occurs together | yes |
| [`periodicity`](#periodicity) | Does it recur on a schedule | yes |
| [`request_timeline`](#request_timeline) | One request end to end | yes |
| [`rollup`](#rollup) | Totals with subtotals | yes |
| [`heatmap`](#heatmap) | Team × week matrix | yes |
| [`reliability_trend`](#reliability_trend) | Is reliability improving | yes |
| [`latency_profile`](#latency_profile) | Latency and error rate | yes |
| [`team_risk`](#team_risk) | One team's risk | yes |
| [`similar_patterns`](#similar_patterns) | Patterns that mean the same | yes |
| [`find_patterns`](#find_patterns) | Find patterns by meaning | yes |
| [`summarize_burst`](#summarize_burst) | Model summary of a burst | yes |
| [`create_focus_index`](#create_focus_index) | Create a focus index | no |
| [`drop_focus_index`](#drop_focus_index) | Drop a focus index | no |
| [`index_stats`](#index_stats) | Index statistics | yes |
| [`explain_tool`](#explain_tool) | Query plan of a tool | yes |
| [`session_report`](#session_report) | Show the session report | yes |

## Prompts (slash commands in Claude Code: `/mcp__logs__<name>`)

- **`investigate_failure`**(`question`): Engineer playbook: what failed, where, what happened just before and after, local or widespread, new or
    recurring, a labelled hypothesis and a concrete next check.
- **`review_recurring_problems`**(`question`): Team-lead playbook: which problems recur over a period, how often, whose, trending how, what to look at first.
- **`set_priorities`**(`question`): Manager playbook: what deserves attention first, measured, with owners and actions; no invented impact.
- **`worked_investigation`**(`topic`, `period` (optional), `dataset` (optional)): Run the whole workflow on one topic: an engineer answer, a team-lead answer and a manager answer, each from the
    evidence that role needs (not the same evidence at three lengths), with the queries behind every number.
- **`whole_corpus_counts`**(`group_by` (optional), `severity` (optional)): Counts over the WHOLE base corpus, not a sample: one count_by per loaded dataset, reported together.

## Resources (`@logs:<uri>` in Claude Code)

- `logs://datasets`: The loaded datasets (lines, time span, Jev-judged or not) and which one is active.
- `logs://glossary`: What line, pattern, burst, episode and problem pattern mean, and the rules every tool follows.
- `logs://session/latest`: Every tool call of this session so far: tool, arguments, dataset, SQL, total_matches, truncated, server ms. The full trail behind an answer.
- `logs://field-guide/{dataset}`: What node / location / request_id / object_id / status / duration / entities mean in one dataset, its span, levels, components and teams, with real example values.
- `logs://ownership/{dataset}`: Component → owning team for one dataset, with source (curated / rule / Jev), confidence and disputes (plan 057).
- `logs://session/{sid}/step/{n}`: One step of a session in full: arguments, SQL, totals and the rows the client saw.

## Tools

### `setup_status`

Is the database ready, which datasets are loaded, which one is active, and how is a running load doing?

    Use when: the first call of a session, before any analysis tool; after load_logs to follow its progress; when a
    tool says no dataset is loaded; to list datasets before use_dataset.
    Not for: what a dataset contains (describe_corpus), the format detection of one dataset (ingest_report).
    Returns: database version and reachability, schema ready, loaded datasets (lines, span, judged by Jev or not),
    the active dataset, AI keys registered (typesafe = Jev, gemini = embeddings), the loadable catalog (the brief's
    Loghub table) and load jobs (state, last log lines, result).
    Caveats: a running load keeps the previous active dataset until it finishes.
    Example: setup_status()
    Next: load_logs(source='base') for the base corpus; use_dataset(name).

### `load_logs`

Load logs into SereneDB: the base corpus, another Loghub dataset, or the user's own log file.

    Use when: setup_status shows nothing loaded, the user asks to load / add / analyse a log file or a dataset, or a
    question needs a dataset that is not loaded yet.
    Not for: switching between loaded datasets (use_dataset), deleting one (remove_dataset).
    Returns: the load job: state (running / done / refused / failed), log lines, and when done the dataset name, lines,
    time span, patterns, whether Jev judged it, the detected format and its sample coverage (files).
    Caveats: catalog names download from the brief's Zenodo links (BGL 709 MB, a few minutes) and use our loaders;
    a file is streamed in, its format detected from 76 lnav formats and loaded only at >= 95 % sample coverage
    (else refused with the closest formats; nothing guessed). Without a Jev key a new file's problems use log levels
    only (stated in results). The finished dataset becomes the active one.
    Example: load_logs(source='base'); load_logs(source='~/logs/app.log', name='app')
    Next: setup_status() while running; then describe_corpus(), ingest_report() for a file, top_patterns().

| Input | Type | Default | Description |
|---|---|---|---|
| `source` | string | required | 'base' = the base corpus (every catalog dataset marked base), a dataset name from the catalog (setup_status lists them: other Loghub sets), or the path of a log file on this machine (any folder; '~' allowed). |
| `name` | string (optional) | `None` | Dataset name for a file (lower case, digits, _); default: the file name. Loading the same name again replaces it. |
| `year` | integer (optional) | `None` | Year for formats that log none (e.g. syslog); stated in the dataset description. |
| `judge` | boolean | `True` | Judge new patterns with Jev inside SereneDB (needs TYPESAFE_API_KEY in .env). Catalog datasets use committed judgments either way. |
| `confirm_large` | boolean | `False` | Allow catalog datasets above 20M lines (multi-GB downloads). |
| `wait_s` | integer | `40` | Seconds to wait for the load to finish before returning (it keeps running in the background). |

### `use_dataset`

Switch the dataset every tool works on.

    Use when: several datasets are loaded and the question is about another one, a whole-corpus answer needs each
    dataset in turn, or the user names a dataset.
    Not for: loading a new one (load_logs).
    Returns: the new active dataset and its field guide (span, levels, components, field meanings, teams).
    Caveats: tools have no dataset parameter; every later call uses this dataset until the next switch or load.
    Example: use_dataset(name=<a dataset from setup_status>)
    Next: describe_corpus() for the dataset's details.

| Input | Type | Default | Description |
|---|---|---|---|
| `name` | string | required | A loaded dataset (setup_status lists them). |

### `remove_dataset`

Delete one loaded dataset from SereneDB (its lines, patterns, judgments and ownership rows).

    Use when: the user asks to remove or unload a dataset, or to start over with a file (loading the same name again
    also replaces it).
    Not for: switching datasets (use_dataset).
    Returns: the dataset removed, log lines deleted, the datasets left and the new active dataset.
    Caveats: cannot be undone; a catalog dataset can be loaded again with load_logs (files under data/raw are kept).
    Example: remove_dataset(name='myapp')
    Next: setup_status().

| Input | Type | Default | Description |
|---|---|---|---|
| `name` | string | required | The dataset to delete (setup_status lists them). |

### `describe_corpus`

What logs are loaded, over which period, and what does each field mean in each dataset? Start here.

    Use when: starting on a question, the question does not name a dataset or period, or you need to know what a
    field means (node, location, request_id, object_id, status, duration) in a given dataset before filtering on it.
    Not for: the values of one field (list_values), counts (count_by).
    Returns: one row per dataset: title, description, first_ts / last_ts (each dataset has its own clock: "now" = its
    last line), lines, patterns, bursts, owning teams, components and log levels (most frequent first), entity kinds,
    and per field its meaning here with a real example value (NULL = the dataset does not log it).
    Caveats: exact counts over the whole dataset; descriptions are written by whoever loaded the data.
    Example: describe_corpus()
    Next: list_values(dataset, field) for valid filter values; search_logs / top_patterns with the dataset and period.

### `list_values`

Which values does this field take (and how many lines carry each)? Valid filter values instead of guesses.

    Use when: you need the exact spelling of a component, node, location level, team or entity before filtering, or
    the question is "which X exist / which X logs the most".
    Not for: values of matching lines only (facet: breakdown of a search), ranked entities with first / last time
    (top_entities).
    Returns: rows {value, lines}, most lines first; values_total = all distinct values (truncated when > limit).
    Read from the inverted index's term dictionary: no scan, cheap to call.
    Caveats: lines are log lines, not incidents.
    Example: list_values(field='component')
    Next: use a value as the filter of search_logs / count_by / trend.

| Input | Type | Default | Description |
|---|---|---|---|
| `field` | `component` / `severity` / `node` / `location` / `request_id` / `object_id` / `status` / `team` / `entity` | required | Which field's values: component, severity, node, location (every level of the path is a value), request_id, object_id, status, team (ownership) or entity (typed values like ip:…, path:…). |
| `prefix` | string (optional) | `None` | Only values starting with this, e.g. a location's first level, 'ip:' for entities, or the start of a component name. |
| `limit` | integer | `30` | Values to return, most lines first (max 50). |

### `suggest_terms`

Which words really occur in the logs close to this spelling? Fixes a search that found nothing.

    Use when: search_logs returned 0 or very few matches, or you are unsure of the log's wording or spelling
    ("pasword" → password, "mont" → mount), before concluding that something is absent.
    Not for: finding messages by meaning in other words (find_patterns), why a search matches (explain_search).
    Returns: per word of `text`, indexed terms within `max_distance` edits, closest first then most lines, with the
    lines containing each; exact_found = words that do occur as typed.
    Caveats: candidates share the first letter; terms are lower-case word tokens.
    Example: suggest_terms(text='conection refused', dataset=<dataset>)
    Next: search_logs with the corrected words (or match='fuzzy').

| Input | Type | Default | Description |
|---|---|---|---|
| `text` | string | required | A word or a few words as you would search them (typos allowed). |
| `max_distance` | integer | `2` | Edit distance allowed per word. |
| `per_word` | integer | `5` | Suggestions per word. |

### `explain_search`

Why does this search match what it matches? Tokens, per-token line counts and whether the index serves it.

    Use when: a search returns 0 or surprisingly many lines and you need to see how the text is tokenized (numbers,
    dotted ids and punctuation) and which token is rare or common.
    Not for: spelling fixes (suggest_terms), the matching lines themselves (search_logs).
    Returns: tokens of the text, lines containing each token, total matches of the whole query, and the query plan
    (index_served = the inverted index answers it).
    Caveats: diagnostic only; nothing about the incident itself.
    Example: explain_search(query_text='"status: 503"', dataset=<dataset>)
    Next: search_logs with an adjusted query or match mode.

| Input | Type | Default | Description |
|---|---|---|---|
| `query_text` | string | required | The search text exactly as you would pass it to search_logs. |
| `match` | `web` / `all` / `any` / `phrase` / `near` / `fuzzy` / `prefix` / `at_least` / `synonyms` | `web` | How query_text matches: 'web' (default: all words, "phrase", a OR b, -word); 'all'; 'any' (one word is enough); 'phrase' (adjacent, in order); 'near' (within `slop` words); 'fuzzy' (up to `distance` typos per word); 'prefix' (`sever` → severed); 'at_least' (`min_match` of the words); 'synonyms' (a word or its log-jargon synonym: fail/error/fault, lost/severed, denied/refused, …). |

### `ingest_report`

How was this dataset's log format detected, and how much of the file did the parser understand?

    Use when: a dataset was loaded by auto-detection (its description says so) and you must say how reliable its
    timestamps, levels and components are, or a question touches lines that may not have been parsed.
    Not for: what a dataset contains (describe_corpus); hand-written loaders (no report: they are parsed by design).
    Returns: format (lnav name + title), sample coverage, lines loaded, lines the format did not match (count, share,
    samples with line_id), timestamp format, assumed year if the log has none, the field → column map, the runner-up
    formats with their coverage.
    Caveats: unmatched lines keep their text but inherit time, component and level from the previous line.
    Example: ingest_report(unmatched_limit=5)
    Next: search_logs / get_context(line_id) on an unmatched line; describe_corpus for the field meanings.

| Input | Type | Default | Description |
|---|---|---|---|
| `unmatched_limit` | integer | `5` | Unmatched lines to show (default 5). |

### `search_logs`

Find log lines: which lines say X, where, and when did it start? The main entry point into the raw logs.

    Use when: you need the log lines for an error / message / id, its first and last time, how many lines match, or a
    line_id / pattern_id to drill into. Filters work with or without query_text.
    Not for: counts per group (count_by / facet), counts over time (trend), ranking recurring problems (top_patterns),
    one request end to end (request_timeline).
    Returns: up to `limit` sample lines (line_id, ts, component, severity, node, ids, pattern_id, body) plus, over ALL
    matches: total_matches, first_ts, last_ts, distinct_nodes (cite these for "how many / since when / how widespread").
    Caveats: counts are log lines, not incidents. 0 matches is not proof of absence: try match='fuzzy' or 'synonyms',
    or suggest_terms for the real wording.
    Example: search_logs(query_text='"connection refused"', start='<period start>', order='time')
    Next: get_context(line_id) for what happened around a line; pattern_history / spread / precursors(pattern_id) for
    that kind of message; top_entities for the IPs / paths behind the matches.

| Input | Type | Default | Description |
|---|---|---|---|
| `query_text` | string (optional) | `None` | Words to find in the log message. Default syntax (match="web"): all words must appear, "exact phrase" in double quotes, a OR b, -word to exclude. Case-insensitive; numbers, dotted ids and hex inside messages are whole tokens (`503`, `10.0.0.7`). Omit to list lines by filters only. |
| `start` | date-time (optional) | `None` | Inclusive start time, 'YYYY-MM-DD HH:MM[:SS]', in the dataset's own clock (each dataset has its own span). Omit for the dataset's beginning. |
| `end` | date-time (optional) | `None` | Exclusive end time, same format. Omit for the dataset's end. |
| `component` | string (optional) | `None` | Exact component (program / service / class that logged the line; case-sensitive). Per dataset: field guide; all values: list_values. |
| `severity` | string (optional) | `None` | Exact log level, upper case (e.g. ERROR). Per dataset: field guide. |
| `node` | string (optional) | `None` | Exact node / host that logged the line. Per dataset: field guide. |
| `location` | string (optional) | `None` | Location path ('/'-separated, coarse → fine), matched at ANY level: the first level(s) filter a whole group. Per dataset: field guide. |
| `entity` | string (optional) | `None` | One typed value extracted from the message text, 'kind:value', e.g. 'ip:10.0.0.7', 'path:/var/log', 'uuid:…'. top_entities ranks them. |
| `request_id` | string (optional) | `None` | Exact request / session / trace / block id: all lines of one unit of work. Per dataset: field guide. |
| `object_id` | string (optional) | `None` | Exact id of a long-lived object followed across requests (e.g. a VM). Per dataset: field guide. |
| `status` | integer (optional) | `None` | Exact status code (e.g. HTTP 503) where the dataset logs one. Per dataset: field guide. |
| `pattern_id` | integer (optional) | `None` | Log pattern id (a kind of message; rows of most tools carry one). |
| `match` | `web` / `all` / `any` / `phrase` / `near` / `fuzzy` / `prefix` / `at_least` / `synonyms` | `web` | How query_text matches: 'web' (default: all words, "phrase", a OR b, -word); 'all'; 'any' (one word is enough); 'phrase' (adjacent, in order); 'near' (within `slop` words); 'fuzzy' (up to `distance` typos per word); 'prefix' (`sever` → severed); 'at_least' (`min_match` of the words); 'synonyms' (a word or its log-jargon synonym: fail/error/fault, lost/severed, denied/refused, …). |
| `slop` | integer | `2` | match='near': max positions between the words. |
| `distance` | integer | `1` | match='fuzzy': typos allowed per word. |
| `min_match` | integer | `2` | match='at_least': how many of the words must appear. |
| `exclude_text` | string (optional) | `None` | Drop lines that match this (same web syntax), e.g. 'heartbeat OR healthcheck'. |
| `highlight` | boolean | `False` | Add `snippet` to each row: the best passage with the matched words wrapped in «…» (needs query_text). |
| `order` | `time` / `recent` / `relevance` / `relevance_recent` | `time` | 'time' = earliest first (where / when did it start), 'recent' = latest first, 'relevance' = best BM25 match first, 'relevance_recent' = BM25 x recency (30-day half-life from the dataset's last line). |
| `limit` | integer | `20` | Sample lines to return (max 50); totals are always over all matches. |
| `workspace` | string (optional) | `None` | Search a focus index made with create_focus_index instead of the whole corpus. |

### `get_context`

What happened just before and just after this log line on the same node / location / request / object?

    Use when: you have one line (an error) and need its timeline: the events leading up to it and what followed, on
    the same machine, group of machines, component, request or object.
    Not for: finding the line in the first place (search_logs), a whole request or object end to end
    (request_timeline), which kinds of messages tend to precede a problem across all its occurrences (precursors).
    Returns: the anchor line, `before` (nearest first) and `after` (nearest first) lines, each side with its total
    count in the window and a truncated flag, plus nearest_before_window / nearest_after_window: the closest line of
    the same scope outside the window and how many seconds from the anchor it is.
    Caveats: earlier is not cause: label any causal reading as a hypothesis. A flooded window: narrow before_s /
    after_s or filter by severity.
    Example: get_context(line_id=<line_id from search_logs>, scope='node', before_s=600)
    Next: search_logs(pattern_id=…) for a preceding message seen here; burst_timeline(pattern_id, at=anchor time) for
    the order of first appearance across the affected nodes.

| Input | Type | Default | Description |
|---|---|---|---|
| `line_id` | integer | required | line_id of the anchor line (from search_logs or any row with a line_id). |
| `before_s` | integer | `300` | Seconds before the anchor to include. |
| `after_s` | integer | `300` | Seconds after the anchor to include. |
| `scope` | `node` / `location` / `component` / `request` / `object` / `all` | `node` | Which neighbours: same 'node' (machine / host), same 'location' path (with location_level: a coarser group such as a rack or a namespace), same 'component', same 'request' (request / session / trace id), same 'object' (object id, followed across requests), or 'all' lines of the dataset. A scope the anchor has no value for is refused with the scopes it does have. |
| `location_level` | integer (optional) | `None` | scope='location' only: keep the first N levels of the anchor's path (1 = coarsest); omit for the full path. |
| `severity` | string (optional) | `None` | Exact log level, upper case (e.g. ERROR). Per dataset: field guide. |
| `limit` | integer | `20` | Max lines per side (max 50). |

### `facet`

Where do the matching lines come from? One search broken down by component, severity, node, location,
    pattern, status and dataset at once.

    Use when: you have a search or filter and want its shape in one call: "of 49,651 matching lines, 99.9 % from one
    component, all at one level, spread over 1,024 nodes; top nodes …".
    Not for: one grouping with team ownership (count_by group_by='team'), lines over time (trend), extracted values
    such as IPs or paths (top_entities).
    Returns: rows {dim, value, lines, share} for each requested breakdown (cut to `top` values); total_matches over
    all lines; `distinct` = how many values each breakdown has. Exact counts over every match.
    Caveats: lines are not incidents.
    Example: facet(query_text='timeout', dims=['component', 'node', 'pattern_id'])
    Next: search_logs with the dominant value as a filter; pattern_history for a dominant pattern_id.

| Input | Type | Default | Description |
|---|---|---|---|
| `query_text` | string (optional) | `None` | Optional words the lines must contain (see match). |
| `match` | `web` / `all` / `any` / `phrase` / `near` / `fuzzy` / `prefix` / `at_least` / `synonyms` | `web` | How query_text matches: 'web' (default: all words, "phrase", a OR b, -word); 'all'; 'any' (one word is enough); 'phrase' (adjacent, in order); 'near' (within `slop` words); 'fuzzy' (up to `distance` typos per word); 'prefix' (`sever` → severed); 'at_least' (`min_match` of the words); 'synonyms' (a word or its log-jargon synonym: fail/error/fault, lost/severed, denied/refused, …). |
| `start` | date-time (optional) | `None` | Inclusive start time, 'YYYY-MM-DD HH:MM[:SS]', in the dataset's own clock (each dataset has its own span). Omit for the dataset's beginning. |
| `end` | date-time (optional) | `None` | Exclusive end time, same format. Omit for the dataset's end. |
| `component` | string (optional) | `None` | Exact component (program / service / class that logged the line; case-sensitive). Per dataset: field guide; all values: list_values. |
| `severity` | string (optional) | `None` | Exact log level, upper case (e.g. ERROR). Per dataset: field guide. |
| `node` | string (optional) | `None` | Exact node / host that logged the line. Per dataset: field guide. |
| `location` | string (optional) | `None` | Location path ('/'-separated, coarse → fine), matched at ANY level: the first level(s) filter a whole group. Per dataset: field guide. |
| `entity` | string (optional) | `None` | One typed value extracted from the message text, 'kind:value', e.g. 'ip:10.0.0.7', 'path:/var/log', 'uuid:…'. top_entities ranks them. |
| `pattern_id` | integer (optional) | `None` | Log pattern id (a kind of message; rows of most tools carry one). |
| `dims` | list of `component` / `severity` / `node` / `location` / `pattern_id` / `status` / `dataset` | `['component', 'severity', 'node']` | Breakdowns to compute in ONE pass, e.g. ['component', 'severity', 'node']. |
| `top` | integer | `8` | Values per breakdown, most lines first. |
| `workspace` | string (optional) | `None` | Use a focus index (create_focus_index) instead of the corpus. |

### `distinctive_terms`

What is different about this time window? Words over-represented in the window compared with a baseline.

    Use when: an incident window or a period looks odd and you do not yet know what to search for ("what changed?",
    "what's unusual this week?"); the words point to the messages worth searching.
    Not for: new kinds of messages (whats_new: patterns first seen), counts of a known search (count_by / trend).
    Returns: per term: window_lines, baseline_lines (lines containing it), lift = window_lines minus the expected
    from the baseline rate, ratio of rates, new_term (absent from the baseline). From the index's term dictionary,
    no scan.
    Caveats: words, not causes: label any reading as a hypothesis; very common words are filtered by lift, not by a
    stop list.
    Example: distinctive_terms(start='<incident start>', end='<incident end>', baseline='before')
    Next: search_logs(query_text=<term>) in the window for the lines behind the top terms.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time | required | Window start (inclusive): the incident / period of interest. |
| `end` | date-time | required | Window end (exclusive). |
| `baseline` | `before` / `rest` / `none` | `before` | 'before' = the `baseline_days` just before the window (what changed?), 'rest' = the whole dataset outside the window, 'none' = just the loudest words of the window (tag cloud). |
| `baseline_days` | integer | `7` | Length of the 'before' baseline in days. |
| `node` | string (optional) | `None` | Exact node / host that logged the line. Per dataset: field guide. |
| `component` | string (optional) | `None` | Exact component (program / service / class that logged the line; case-sensitive). Per dataset: field guide; all values: list_values. |
| `min_lines` | integer | `5` | A term must appear in at least this many window lines. |
| `limit` | integer | `20` | Terms to return. |

### `top_entities`

Which IPs / paths / ids / URLs appear most in these lines? Who or what is behind the messages.

    Use when: "which IP addresses / clients / files / VMs / users drive X", attacks, scans, a noisy client, or which
    object ids are involved; values were extracted from every message at load time (column `entities`).
    Not for: grouping by component / node / severity (count_by / facet), the values of a structured field
    (list_values).
    Returns: per value: lines, first / last time, nodes, patterns; total_matches = distinct values; mentions = all
    mentions. Exact counts over every matching line.
    Caveats: a value appears only if the message text contains it; lines are not incidents.
    Example: top_entities(entity_type='ip', query_text='"authentication failure"')
    Next: search_logs(entity='ip:…') to drill into one value; trend(entity='ip:…') for its time profile.

| Input | Type | Default | Description |
|---|---|---|---|
| `entity_type` | string | `any` | Which kind of extracted value: ip, path, uuid, url, … or 'any' (kinds per dataset: field guide). |
| `query_text` | string (optional) | `None` | Optional words the lines must contain (see match). |
| `match` | `web` / `all` / `any` / `phrase` / `near` / `fuzzy` / `prefix` / `at_least` / `synonyms` | `web` | How query_text matches: 'web' (default: all words, "phrase", a OR b, -word); 'all'; 'any' (one word is enough); 'phrase' (adjacent, in order); 'near' (within `slop` words); 'fuzzy' (up to `distance` typos per word); 'prefix' (`sever` → severed); 'at_least' (`min_match` of the words); 'synonyms' (a word or its log-jargon synonym: fail/error/fault, lost/severed, denied/refused, …). |
| `start` | date-time (optional) | `None` | Inclusive start time, 'YYYY-MM-DD HH:MM[:SS]', in the dataset's own clock (each dataset has its own span). Omit for the dataset's beginning. |
| `end` | date-time (optional) | `None` | Exclusive end time, same format. Omit for the dataset's end. |
| `pattern_id` | integer (optional) | `None` | Log pattern id (a kind of message; rows of most tools carry one). |
| `limit` | integer | `15` | Values to return, most lines first. |

### `check_watchlist`

Did any of the known, saved problem searches fire in this window? A quick health check against a watchlist.

    Use when: "did any of the known problems come back", "anything from our usual suspects this week", a routine check
    of a period; watches are fixed searches configured per dataset (data/watchlist.csv).
    Not for: problems nobody has saved yet (top_patterns, whats_new), a single search (search_logs).
    Returns: one row per watch (name, query, match mode): window_lines, previous_lines (previous window of the same
    length), first_ts, fired; total_matches = watches that fired. Quiet watches are listed too.
    Caveats: datasets without configured watches return no rows; lines, not incidents.
    Example: check_watchlist(start='<week start>', end='<week end>')
    Next: search_logs(query_text=<watch query>) for a fired watch; trend for its profile.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time | required | Window start (inclusive). |
| `end` | date-time | required | Window end (exclusive). |

### `count_by`

How many log lines per team / component / severity / node / location / dataset? Exact totals, not samples.

    Use when: "how much", "which team / component / node logs the most X", comparing groups, or a total for a filter
    (e.g. how many requests failed with a status, how many ERROR lines per service).
    Not for: several breakdowns of one search at once (facet), lines per time bucket (trend), recurrences of problems
    (top_patterns: bursts, not lines), totals with subtotals (rollup).
    Returns: rows {<group>, lines}, largest first; total_lines = sum over ALL groups; groups_total = distinct groups
    (truncated when > limit).
    Caveats: lines are not incidents: one fault can log thousands of lines; use bursts (top_patterns, rollup
    unit='bursts') for how often something happened.
    Example: count_by(group_by='component', severity='ERROR', start='<period start>')
    Next: trend with the same filters for the time profile; search_logs for example lines of the largest group.

| Input | Type | Default | Description |
|---|---|---|---|
| `group_by` | `dataset` / `team` / `component` / `severity` / `node` / `location` | required | Group the counts by dataset, owning team, component, severity, node or full location path. |
| `start` | date-time (optional) | `None` | Inclusive start time, 'YYYY-MM-DD HH:MM'; omit for the data's start. |
| `end` | date-time (optional) | `None` | Exclusive end time; omit for the data's end. |
| `team` | string (optional) | `None` | Owning team, or 'unowned' (component without an owner). Teams per dataset: field guide. |
| `component` | string (optional) | `None` | Exact component (program / service / class that logged the line; case-sensitive). Per dataset: field guide; all values: list_values. |
| `severity` | string (optional) | `None` | Exact log level, upper case (e.g. ERROR). Per dataset: field guide. |
| `node` | string (optional) | `None` | Exact node / host that logged the line. Per dataset: field guide. |
| `location` | string (optional) | `None` | Location path ('/'-separated, coarse → fine), matched at ANY level: the first level(s) filter a whole group. Per dataset: field guide. |
| `entity` | string (optional) | `None` | One typed value extracted from the message text, 'kind:value', e.g. 'ip:10.0.0.7', 'path:/var/log', 'uuid:…'. top_entities ranks them. |
| `status` | integer (optional) | `None` | Exact status code (e.g. HTTP 503) where the dataset logs one. Per dataset: field guide. |
| `query_text` | string (optional) | `None` | Optional words the message must contain (web syntax: words, "phrase", a OR b, -word). Numbers and dotted ids are whole tokens (`503`, `10.0.0.7`). |
| `limit` | integer | `20` | Groups to return, largest first (max 50). |

### `trend`

How did the number of matching log lines change over time? Lines per hour / day / week, zero-filled.

    Use when: "is it rising", "when did it start / stop", "week over week", "at which hours / days does X peak",
    for any filter or search text, optionally one series per team / component / node.
    Not for: recurrences of one pattern over its life (pattern_history), problem bursts with a computed direction
    (reliability_trend), a team x week matrix of bursts (heatmap), whether this window is unusual (rate_vs_baseline).
    Returns: rows {bucket_start, [group], lines} with empty buckets as 0; total_lines; first_ts / last_ts of the
    matches; the bucket used.
    Caveats: lines, not incidents; direction is not computed here (compare the numbers or use reliability_trend);
    the first / last bucket can be partial.
    Example: trend(query_text='"failed password"', bucket='day')
    Next: rate_vs_baseline for the peak window; search_logs in the peak bucket for example lines.

| Input | Type | Default | Description |
|---|---|---|---|
| `bucket` | `hour` / `day` / `week` (optional) | `None` | Time bucket. Omit to choose by the data's span (> 60 days: week, > 3 days: day, else hour); weeks start on Monday. The bucket used is returned. |
| `group_by` | `dataset` / `team` / `component` / `severity` / `node` / `location` (optional) | `None` | Optional: one series per dataset / team / component / severity / node / location. |
| `start` | date-time (optional) | `None` | Inclusive start time, 'YYYY-MM-DD HH:MM'; omit for the data's start. |
| `end` | date-time (optional) | `None` | Exclusive end time; omit for the data's end. |
| `team` | string (optional) | `None` | Owning team, or 'unowned' (component without an owner). Teams per dataset: field guide. |
| `component` | string (optional) | `None` | Exact component (program / service / class that logged the line; case-sensitive). Per dataset: field guide; all values: list_values. |
| `severity` | string (optional) | `None` | Exact log level, upper case (e.g. ERROR). Per dataset: field guide. |
| `node` | string (optional) | `None` | Exact node / host that logged the line. Per dataset: field guide. |
| `location` | string (optional) | `None` | Location path ('/'-separated, coarse → fine), matched at ANY level: the first level(s) filter a whole group. Per dataset: field guide. |
| `entity` | string (optional) | `None` | One typed value extracted from the message text, 'kind:value', e.g. 'ip:10.0.0.7', 'path:/var/log', 'uuid:…'. top_entities ranks them. |
| `status` | integer (optional) | `None` | Exact status code (e.g. HTTP 503) where the dataset logs one. Per dataset: field guide. |
| `pattern_id` | integer (optional) | `None` | Log pattern id (a kind of message; rows of most tools carry one). |
| `query_text` | string (optional) | `None` | Optional words the message must contain (web syntax: words, "phrase", a OR b, -word). Numbers and dotted ids are whole tokens (`503`, `10.0.0.7`). |
| `top_groups` | integer | `5` | With group_by: keep the N largest groups. |

### `rate_vs_baseline`

Is this rate unusual here? Matching lines in a window vs the same-length windows just before it.

    Use when: you have an incident window and need "how unusual is this": the rate now vs the usual rate, how many
    earlier windows reached it, or whether it never happened before (new here).
    Not for: a time series (trend), whether a pattern is new in the whole dataset (pattern_history / whats_new).
    Returns: window_lines and rate per hour; baseline_lines, baseline rate, ratio (window / usual), max per earlier
    window, how many earlier windows were at or above the window; flags new_in_baseline (0 before → new here),
    baseline_clipped (less history than asked), no_baseline_data (nothing earlier: cannot call it new or unusual).
    Caveats: lines, not incidents; the baseline is cut into windows of the SAME length as the window.
    Example: rate_vs_baseline(start='<incident hour start>', end='<+1 h>', severity='ERROR', days=7)
    Next: get_context / burst_timeline at the window to explain the jump.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time | required | Window start (inclusive), e.g. the hour around the incident. |
| `end` | date-time | required | Window end (exclusive). |
| `days` | integer | `7` | Baseline = up to `days` days just before `start`. |
| `query_text` | string (optional) | `None` | Optional words the message must contain (web syntax: words, "phrase", a OR b, -word). Numbers and dotted ids are whole tokens (`503`, `10.0.0.7`). |
| `pattern_id` | integer (optional) | `None` | Log pattern id (a kind of message; rows of most tools carry one). |
| `component` | string (optional) | `None` | Exact component (program / service / class that logged the line; case-sensitive). Per dataset: field guide; all values: list_values. |
| `severity` | string (optional) | `None` | Exact log level, upper case (e.g. ERROR). Per dataset: field guide. |
| `node` | string (optional) | `None` | Exact node / host that logged the line. Per dataset: field guide. |
| `location` | string (optional) | `None` | Location path ('/'-separated, coarse → fine), matched at ANY level: the first level(s) filter a whole group. Per dataset: field guide. |
| `status` | integer (optional) | `None` | Exact status code (e.g. HTTP 503) where the dataset logs one. Per dataset: field guide. |

### `value_outliers`

Which operations took far longer than normal for their own kind? Slow steps that log no error.

    Use when: "slow", "took long", "latency", "performance", "which requests / VMs / objects were abnormal" and the
    logs carry durations (datasets with durations: none loaded). The problem is an unusual number inside a
    normal message, not an error line.
    Not for: latency percentiles and error rates per group (latency_profile), error messages (search_logs).
    Returns: baselines per pattern (n, median, p95, MAD, threshold, flagged), flagged objects (max ratio, lines,
    first time) and flagged lines (value_s, ratio = value / median, ids); total_matches = flagged lines.
    Caveats: a flag says "unusually slow for this step", not why. Datasets without durations return nothing.
    Example: value_outliers(dataset=<dataset with durations>, start='<period start>')
    Next: request_timeline(object_id=… or request_id=…) for a flagged one; get_context(line_id) around the slow line.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_id` | integer (optional) | `None` | Only this pattern (from top_patterns / search_logs). |
| `object_id` | string (optional) | `None` | Exact id of a long-lived object followed across requests (e.g. a VM). Per dataset: field guide. |
| `start` | date-time (optional) | `None` | Flag lines from this time (baseline stays the whole dataset). |
| `end` | date-time (optional) | `None` | Flag lines before this time (exclusive). |
| `k` | number | `6.0` | Threshold = median + k × MAD (robust spread). |
| `min_excess_s` | number | `2.0` | A flagged value is also at least this many seconds above the median. |
| `limit` | integer | `20` | Flagged lines to return, most extreme first (max 50). |

### `top_patterns`

Which problems recur most in a period, how often, where, whose, and are they growing?

    Use when: "which problems keep coming back", "top errors this month", "what got worse", "what does team X
    struggle with": one row per kind of problem (a log pattern), ranked.
    Not for: a computed priority order with weights (priority_table), one known error's lines (search_logs), patterns
    first seen in the period only (whats_new), finding a pattern by meaning (find_patterns).
    Returns: per pattern: template, component, owner team (with owner_source / owner_confidence: curated or inferred,
    see owner_of), lines, bursts (recurrences split by > 30 min quiet),
    nodes, weeks_active, bursts_prev (previous period of equal length), change, new (first seen in the period),
    top_node_share (1.0 = one node only), p_problem / kind (stored Jev judgment). Both periods as absolute dates.
    excluded_by_filter = the top recurring patterns with error-level lines that the Jev filter judged not a fault.
    Caveats: bursts count recurrences, not confirmed incidents; lines count log entries. Default period = the
    dataset's last 28 days.
    Example: top_patterns(start='<month start>', end='<next month start>', rank_by='growth')
    Next: pattern_history / spread / precursors(pattern_id) for one row; search_logs(pattern_id=…) for its lines.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time (optional) | `None` | Period start (inclusive), 'YYYY-MM-DD'. Default: 28 days before `end`. |
| `end` | date-time (optional) | `None` | Period end (exclusive). Default: just after the dataset's last line ('now' of that dataset). |
| `team` | string (optional) | `None` | Owning team, or 'unowned' (component without an owner). Teams per dataset: field guide. |
| `component` | string (optional) | `None` | Exact component (program / service / class that logged the line; case-sensitive). Per dataset: field guide; all values: list_values. |
| `problem_only` | boolean | `True` | Only problem patterns (see problem_filter); False = every kind of message. |
| `problem_filter` | `jev` / `severity` | `jev` | How 'problem pattern' is decided: 'jev' (default) = has problem-level lines (error-or-worse, WARN, 5xx status, or no level in the format) AND the stored Jev judgment says it reports a real fault (not a routine diagnostic dump) or a security event (p_problem >= 0.5); 'severity' = level / status only (the naive rule, kept for comparison). |
| `rank_by` | `bursts` / `nodes` / `lines` / `growth` | `bursts` | 'bursts' = how often it recurs (default), 'nodes' = how widespread, 'lines' = log volume (inflated by storms), 'growth' = bursts now minus bursts in the previous period. |
| `limit` | integer | `20` | Patterns to return (max 50). |

### `priority_table`

What deserves attention first? A computed priority ranking of problems for a period, with a team roll-up.

    Use when: "what should we fix / prioritise first", "top 3 risks", "if we can fix only one thing": the ranking
    is computed, so explain it instead of re-ranking yourself.
    Not for: a plain list of recurring problems ranked by one measure (top_patterns), one team in depth (team_risk),
    whether things improve over time (reliability_trend).
    Returns: items (rank, score 0-100, template, component, team, measured inputs: bursts, change, nodes,
    persistence, p_problem, and each input's contribution), the weights and formula, and team_rollup over ALL
    problem patterns of the period.
    Caveats: the logs measure frequency, spread, trend and persistence; cost, downtime and customer impact are not in
    the logs (stated in `unknown`). Default period = the dataset's last 28 days.
    Example: priority_table(start='<period start>', end='<period end>')
    Next: team_risk(team) for the top team; pattern_history / spread for the top item.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time (optional) | `None` | Period start (inclusive), 'YYYY-MM-DD'. Default: 28 days before `end`. |
| `end` | date-time (optional) | `None` | Period end (exclusive). Default: just after the dataset's last line ('now' of that dataset). |
| `limit` | integer | `10` | Ranked problems to return (max 50). |
| `problem_filter` | `jev` / `severity` | `jev` | How 'problem pattern' is decided: 'jev' (default) = has problem-level lines (error-or-worse, WARN, 5xx status, or no level in the format) AND the stored Jev judgment says it reports a real fault (not a routine diagnostic dump) or a security event (p_problem >= 0.5); 'severity' = level / status only (the naive rule, kept for comparison). |

### `owner_of`

Who owns this component, how do we know, and how sure is it?

    Use when: an answer names an owning team and you must say whether that owner is curated or inferred, or a team
    lead asks who should handle a component, or a component shows as 'unowned'.
    Not for: counts per team (count_by group_by='team'), all weak spots at once (ownership_gaps).
    Returns: one row: team, source ('curated' = hand-written table, 'curated default' = the dataset's default
    row, 'jev owner_hint' = Jev chose among the dataset's curated teams, 'rule: …' = public name list → area → team,
    'jev area' = Jev chose the functional area → team), confidence (1.0 curated, 0.95 default, else the rule's 0.9 or
    the Jev probability), area with its own source and confidence, disputed_by / dispute_confidence when confident
    Jev hints for most of the component's lines name another curated team, and the lines and patterns it logged.
    Caveats: teams outside the curated table come from data/area_teams.csv and are generic, not a real org chart;
    an inferred owner below 0.6 confidence is never stored (the component shows as unowned); a dispute is a flag
    to check the table, not a correction.
    Example: owner_of(component=<a value from list_values(field='component')>)
    Next: ownership_gaps() for every unowned / inferred / disputed component; top_patterns(team=…) for that
    team's recurring problems.

| Input | Type | Default | Description |
|---|---|---|---|
| `component` | string | required | Exact component (case-sensitive); all values: list_values. |

### `ownership_gaps`

Where is ownership missing, guessed or disputed, and how many log lines does that affect?

    Use when: before naming owners in a team-lead or manager answer, to know which owners are solid; or when asked
    which components nobody owns or whose owner table may be wrong.
    Not for: the owner of one component (owner_of), counts per team (count_by group_by='team').
    Returns: one row per weak component, most lines first: kind ('unowned' = no owner at all, 'inferred' = owner
    not from the curated table, 'weak' = inferred below min_confidence, 'disputed' = curated owner contradicted by
    confident Jev hints), team, source, confidence, disputed_by, lines, patterns; plus totals per kind with their
    share of the dataset's lines.
    Caveats: components with a curated owner and no dispute are not listed; lines are log entries, not incidents.
    Example: ownership_gaps(min_confidence=0.8)
    Next: owner_of(component) for the evidence of one row; top_patterns(team=…) to see what an uncertain
    team would own.

| Input | Type | Default | Description |
|---|---|---|---|
| `min_confidence` | number | `0.8` | Inferred owners below this confidence count as weak (default 0.8). |
| `limit` | integer | `20` | Rows to return, most lines first (max 50). |

### `pattern_history`

Is this kind of message new or recurring, and how has it behaved over the whole dataset?

    Use when: you have one pattern (a kind of error) and need its life: first / last seen, how many bursts over time,
    longest quiet gap, and with `as_of` whether it had ever happened before an incident ("new or recurring?").
    Not for: many patterns at once (top_patterns), lines of any search over time (trend), schedule / time-of-day
    regularity (periodicity).
    Returns: the pattern (template, component, team, lines, bursts, nodes, weeks_active, first_ts, last_ts,
    p_problem), per bucket over the whole dataset (zero-filled) bursts_started and lines (lines by their own
    timestamp), gap statistics, and `before`
    (bursts / lines before as_of, new_as_of).
    Caveats: bursts = recurrences split by > 30 min quiet, not confirmed incidents.
    Example: pattern_history(pattern_id=<id>, bucket='week', as_of='<incident time>')
    Next: spread(pattern_id) for how widespread; precursors(pattern_id) for what comes before it.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_id` | integer | required | Log pattern id: a kind of message (from search_logs rows, top_patterns, priority_table, find_patterns, …). |
| `bucket` | `day` / `week` / `month` | `week` | Bucket of the bursts-over-time series. |
| `as_of` | date-time (optional) | `None` | Optional 'now' for the new-vs-recurring question: counts before this time are returned too. |

### `burst_timeline`

Which error came first? The order in which kinds of messages appeared around one burst of a problem.

    Use when: an incident involves several errors and you need the sequence: what showed up first on the affected
    nodes, from `before_s` before the burst to its end.
    Not for: the raw lines around one line (get_context), what usually precedes this problem across all its
    occurrences (precursors).
    Returns: the burst (start, end, lines, nodes, its first line) and one row per pattern seen in the window (first
    time, lines, nodes, level, owner, template), earliest first; first_problem = the earliest pattern with
    problem-level lines.
    Caveats: earlier is not cause: label a causal reading as a hypothesis. Without a node in the dataset, "same
    nodes" means the same component.
    Example: burst_timeline(pattern_id=<id>, at='<incident time>')
    Next: get_context(line_id of the first problem line) for the raw lines; precursors(pattern_id) for the general
    pattern.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_id` | integer | required | Log pattern id: a kind of message (from search_logs rows, top_patterns, priority_table, find_patterns, …). |
| `at` | date-time (optional) | `None` | A time inside (or just before) the burst; omit to take the pattern's largest burst. |
| `before_s` | integer | `600` | Also look this many seconds before the burst start. |
| `same_nodes` | boolean | `True` | Only lines on the burst's own nodes (else the whole dataset). |
| `limit` | integer | `20` | Patterns in the sequence to return. |

### `spread`

Is it one bad node or fleet-wide? How the matching lines spread over nodes and top-level locations.

    Use when: "local or systemic?", "how many machines are affected", "is it one host / rack / pod".
    Not for: lines per node as a ranking only (count_by group_by='node'), spread over time (trend).
    Returns: nodes, top nodes with lines, top_node_share (1.0 = one node only), entropy_norm (0 = all on one node,
    1 = perfectly even), lines and nodes per top-level location, and `reading` (concentrated / mixed / widespread)
    with the fixed rule that produced it.
    Caveats: datasets without a node use the component as the unit (said in `scope`); lines, not incidents.
    Example: spread(pattern_id=<id>, start='<period start>')
    Next: search_logs(node=<top node>) or get_context on that node; pattern_history for whether it is new.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_id` | integer (optional) | `None` | Pattern to measure (or give query_text). |
| `query_text` | string (optional) | `None` | Full-text search instead of a pattern (web syntax). |
| `start` | date-time (optional) | `None` | Inclusive start time. |
| `end` | date-time (optional) | `None` | Exclusive end time. |

### `whats_new`

What is new this period? Kinds of messages whose first appearance in the whole dataset falls inside it.

    Use when: "anything new this week", "did a new error appear after the change", a period review.
    Not for: problems that existed before and grew (top_patterns rank_by='growth'), unusual words (distinctive_terms).
    Returns: per new pattern: template, component, team, first_ts, bursts / lines / nodes up to the period end,
    p_problem and kind (stored Jev judgment); total_matches = all new patterns in the period.
    Caveats: a new pattern is a new kind of message, not necessarily a new problem (problem_only=True keeps only
    those judged real faults or security events).
    Example: whats_new(start='<week start>', end='<week end>')
    Next: pattern_history / spread(pattern_id) for a new pattern; search_logs(pattern_id=…) for its lines.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time | required | Period start (inclusive). |
| `end` | date-time | required | Period end (exclusive). |
| `problem_only` | boolean | `True` | Only patterns the stored Jev judgment calls a real fault. |
| `limit` | integer | `20` | Patterns to return, most bursts first. |

### `precursors`

What tends to happen just BEFORE this problem? Other kinds of messages that start shortly before it, across
    all its occurrences, compared with a control.

    Use when: "what leads up to X", "is there an early warning sign", looking for a candidate cause or precursor of a
    recurring problem.
    Not for: the lines around one occurrence (get_context), the order inside one burst (burst_timeline), what happens
    at the same time (co_occurrence).
    Returns: per preceding pattern: occurrences preceded, share, median lead time (s), control share (same look-back
    one day earlier) and lift = share / control; `nearest` = the immediately preceding pattern per occurrence.
    Caveats: association in time, not cause: report candidates with lift and share, never as "the cause". scope='node'
    needs a node in the dataset; otherwise use scope='dataset'.
    Example: precursors(pattern_id=<id>, window_s=600)
    Next: search_logs(pattern_id=<precursor>) for its lines; burst_timeline to see one occurrence in order.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_id` | integer | required | Log pattern id: a kind of message (from search_logs rows, top_patterns, priority_table, find_patterns, …). |
| `window_s` | integer | `600` | How far before each occurrence to look (seconds). |
| `scope` | `node` / `dataset` | `node` | 'node' = before it on the SAME node (per-node episodes), 'dataset' = anywhere (bursts). |
| `start` | date-time (optional) | `None` | Only occurrences from this time. |
| `end` | date-time (optional) | `None` | Only occurrences before this time. |
| `limit` | integer | `10` | Preceding patterns to return. |

### `co_occurrence`

Do these kinds of messages occur together? What shows up around a problem, compared with a control.

    Use when: "does X happen together with Y", "what else goes wrong at the same time as X", grouping symptoms of one
    problem.
    Not for: what comes BEFORE (precursors), the order inside one burst (burst_timeline).
    Returns: share of A's occurrences with a B occurrence within ±window_s (same node or anywhere), the control share
    (A shifted one day) and lift; without pattern_b: the patterns most often found around A.
    Caveats: association, not cause.
    Example: co_occurrence(pattern_a=<id>, window_s=300, scope='dataset')
    Next: search_logs(pattern_id=…) for the companion pattern's lines.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_a` | integer | required | Log pattern id: a kind of message (from search_logs rows, top_patterns, priority_table, find_patterns, …). |
| `pattern_b` | integer (optional) | `None` | Second pattern; omit to list the patterns that co-occur most with A. |
| `window_s` | integer | `300` | Within how many seconds (either side) counts as together. |
| `scope` | `node` / `dataset` | `node` | 'node' = on the SAME node (episodes), 'dataset' = anywhere (bursts). |
| `limit` | integer | `10` | Patterns to return when pattern_b is omitted. |

### `periodicity`

Does this problem recur on a schedule or at certain hours / weekdays?

    Use when: "is it periodic", "does it happen every night / every hour", "at what time of day does it peak",
    cron-like or shift-like faults.
    Not for: lines of a search per hour across days (trend bucket='hour'), whether it is new (pattern_history).
    Returns: gap statistics between bursts (count, median, MAD, regular_share = gaps within ±20 % of the median),
    a gap histogram (< 1 h … > 7 d), bursts by hour of day and by weekday, and `reading` with its fixed rule.
    Caveats: counts burst starts of one pattern, not lines.
    Example: periodicity(pattern_id=<id>)
    Next: trend(pattern_id=…, bucket='hour') for the raw hourly volume.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_id` | integer | required | Log pattern id: a kind of message (from search_logs rows, top_patterns, priority_table, find_patterns, …). |

### `request_timeline`

What happened to this one request / session / trace / object, step by step, end to end?

    Use when: the question names one id (a request, connection, trace, block, VM …) and asks what happened to it,
    where it spent its time or where it failed (what request_id / object_id are in each dataset: field guide).
    Not for: the neighbours of one line on a machine (get_context), all slow operations (value_outliers).
    Returns: the id's lines in time order with seconds since the previous step and since the start; per component
    first / last time, lines, statuses, max duration; total duration and problem lines. Reused ids are split into
    sessions at quiet gaps > max_gap_s (`sessions`; `at` picks one).
    Caveats: steps are log lines; a missing step is not proof it did not happen.
    Example: request_timeline(request_id=<id from a search row>)
    Next: get_context(line_id of the failing step, scope='node') for what else happened on that machine.

| Input | Type | Default | Description |
|---|---|---|---|
| `request_id` | string (optional) | `None` | Exact request / session / trace / block id: all lines of one unit of work. Per dataset: field guide. |
| `object_id` | string (optional) | `None` | Exact id of a long-lived object followed across requests (e.g. a VM). Per dataset: field guide. |
| `at` | date-time (optional) | `None` | Pick the session containing (or starting after) this time; ids such as process ids get reused. |
| `max_gap_s` | integer | `3600` | A quiet gap longer than this starts a new session of the same id. |
| `limit` | integer | `50` | Steps to return. |

### `rollup`

How many problems per team, and per component within each team, with subtotals and a grand total?

    Use when: "which team has the most problems", "break it down by team and component", the whole-corpus or
    whole-period summary for a lead or manager, in bursts (recurrences) or lines, in ONE query (GROUP BY ROLLUP).
    Not for: a ranked list of individual problems (top_patterns), lines per group without the problem filter
    (count_by), a time profile (heatmap / trend).
    Returns: rows with the grouping columns (NULL = 'all' at that level), the count, and `level` (0 = finest … the
    first row is the grand total).
    Caveats: problem_only=True (default) counts only problem patterns (stored Jev judgment + problem-level lines);
    bursts are recurrences, not confirmed incidents.
    Example: rollup(start='<period start>', end='<period end>', by=['team', 'component'])
    Next: top_patterns(team=…) for the largest team's problems; heatmap for its weekly profile.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time (optional) | `None` | Inclusive start (default: the dataset's first line). |
| `end` | date-time (optional) | `None` | Exclusive end (default: after its last line). |
| `by` | list of `dataset` / `team` / `component` / `severity` | `['team', 'component']` | Hierarchy to roll up, coarse → fine, e.g. ['team', 'component']. |
| `unit` | `bursts` / `lines` | `bursts` | 'bursts' = recurrences of a pattern (> 30 min apart), the incident-like unit; 'lines' = log entries. |
| `problem_only` | boolean | `True` | Only patterns the stored Jev judgment calls a real fault. |
| `limit` | integer | `60` | Rows to return (subtotals first). |

### `heatmap`

When and where do problems cluster? A matrix of bursts or lines: teams / components / levels x weeks / days /
    months / hours of day / weekdays.

    Use when: "which team's problems grow week over week", "at what hour do faults cluster", a compact overview of
    many groups over time.
    Not for: one series (trend), a computed improving / worsening verdict (reliability_trend).
    Returns: one row per matrix row with one key per column (missing = 0) plus a row total; `columns` lists the
    column keys.
    Caveats: keeps the `top_rows` largest rows; problem_only=True counts problem patterns only.
    Example: heatmap(rows='team', cols='week', unit='bursts')
    Next: top_patterns(team=…, start=<hot week>) for what drove a hot cell.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time (optional) | `None` | Inclusive start (default: the dataset's first line). |
| `end` | date-time (optional) | `None` | Exclusive end (default: after its last line). |
| `rows` | `team` / `component` / `severity` | `team` | One matrix row per … |
| `cols` | `week` / `day` / `month` / `hour_of_day` / `weekday` | `week` | One matrix column per time bucket (or hour of day / weekday for daily rhythm). |
| `unit` | `bursts` / `lines` | `bursts` | 'bursts' = recurrences of a pattern (> 30 min apart), the incident-like unit; 'lines' = log entries. |
| `problem_only` | boolean | `True` | Only real-fault patterns (stored Jev judgment). |
| `top_rows` | integer | `10` | Keep the N largest rows. |

### `reliability_trend`

Is reliability getting better or worse? Problem bursts per week (or day) with a computed slope and verdict.

    Use when: "are we improving", "is it getting worse", "trend of problems over the quarter", per team as well.
    Not for: lines of an arbitrary search over time (trend), a priority list (priority_table).
    Returns: problem bursts per bucket (zero-filled), least-squares slope, first-half vs second-half mean, total, per
    team the slope and bursts, and `reading` (improving / worsening / no clear change) with its fixed rule.
    Caveats: counts recurrences of problem patterns (stored Jev judgment), not incidents, downtime or impact.
    Example: reliability_trend(start='<period start>', end='<period end>', bucket='week')
    Next: team_risk(team) for the worst slope; top_patterns(rank_by='growth') for what grew.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time (optional) | `None` | Inclusive start (default: the dataset's first line). |
| `end` | date-time (optional) | `None` | Exclusive end (default: after its last line). |
| `bucket` | `day` / `week` | `week` | Bucket of the series. |
| `by_team` | boolean | `True` | Also the slope per owning team. |

### `latency_profile`

How long do operations take and how often do they fail? Duration percentiles and error rate per group.

    Use when: "how slow is X", "p95 latency per service", "is latency different for failed requests", "did it get
    slower over the day" (bucket), in datasets that log durations: none loaded.
    Not for: individual abnormal operations (value_outliers), error counts without durations (count_by).
    Returns: per group (component, pattern = each kind of operation, e.g. one API endpoint, or status; optionally per
    hour / day): timed operations, p50 / p95 / p99 / max in seconds, lines, error_rate (problem level or status >= 500
    among the group's lines), ordered by rank_by; `overall` p50 / p95 of everything (the "typical" to compare with),
    plus a duration histogram.
    Caveats: only lines that carry a duration are timed; error_rate counts lines.
    Example: latency_profile(dataset=<dataset with durations>, group_by='pattern', rank_by='p50')
    Next: value_outliers for the slowest single operations; request_timeline for one slow request.

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time (optional) | `None` | Inclusive start (default: the dataset's first line). |
| `end` | date-time (optional) | `None` | Exclusive end (default: after its last line). |
| `group_by` | `component` / `pattern` / `status` | `component` | One profile per component, per pattern (each kind of timed operation) or per status code. |
| `bucket` | `hour` / `day` (optional) | `None` | Optional: one profile per group and time bucket. |
| `rank_by` | `p50` / `p95` / `max` | `p50` | Order groups by typical (p50, default), tail (p95) or single worst (max) duration. 'Which X is slowest' = p50; one outlier request does not make an endpoint slow. |
| `min_timed` | integer | `5` | Ignore groups with fewer timed operations (default 5). |
| `limit` | integer | `20` | Rows to return, slowest first. |

### `team_risk`

How much risk does one team carry, and is it getting better? One team's problems in measured terms.

    Use when: the question names one team: "how is team X doing", "what should team X fix first", "is team X
    improving".
    Not for: comparing all teams (rollup / priority_table team_rollup), the whole dataset's direction
    (reliability_trend).
    Returns: the team's problem items from the computed priority ranking (rank, score, bursts, change, nodes, weeks),
    its burst totals now vs the previous period, and its weekly problem-burst slope.
    Caveats: ranks are among the top 50 items of all teams; nothing about cost, downtime or customers.
    Example: team_risk(team=<team>, start='<period start>')
    Next: pattern_history / spread(pattern_id) for the team's top item.

| Input | Type | Default | Description |
|---|---|---|---|
| `team` | string | required | Owning team (list_values(field='team') or describe_corpus lists them). |
| `start` | date-time (optional) | `None` | Inclusive start (default: the dataset's first line). |
| `end` | date-time (optional) | `None` | Exclusive end (default: after its last line). |

### `similar_patterns`

Which other kinds of messages MEAN the same as this one, even when worded differently?

    Use when: grouping a problem's variants before counting them, finding the same failure in another component,
    or "has something like this happened in another system?" (any_dataset=True).
    Not for: finding a pattern from your own words (find_patterns), patterns that occur at the same time
    (co_occurrence).
    Returns: nearest patterns by template-embedding cosine distance (0 = same meaning) with template, owner, lines,
    bursts, nodes, p_problem and cause family (stored Jev traits).
    Caveats: similar wording, not proof of a shared cause.
    Example: similar_patterns(pattern_id=<id>, k=8)
    Next: top_patterns / search_logs(pattern_id=…) to count the variants together.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_id` | integer | required | The pattern to find look-alikes for. |
| `k` | integer | `8` | Neighbours to return. |
| `any_dataset` | boolean | `False` | Also search the other datasets (same problem in another system?). |

### `find_patterns`

Which kinds of log messages are about this topic? Find patterns from plain words when you do not know the
    log's exact wording.

    Use when: the question describes a problem in its own words ("disk failures", "network problems", "login
    attacks", "memory errors") and you need the matching message templates and their pattern ids.
    Not for: lines of a known wording (search_logs), patterns similar to a known pattern (similar_patterns).
    Returns: ranked patterns with dataset, pattern_id, template, owner, lines, bursts, nodes, p_problem and cause;
    rank_source = which ranking found each (lexical BM25 on template words, semantic embeddings, or both fused).
    Caveats: semantic mode needs the embedding key (falls back to lexical, said in `note`); ranks, not counts.
    Example: find_patterns(text='connection to peer lost', dataset=<dataset>)
    Next: pattern_history / spread / precursors(pattern_id); search_logs(pattern_id=…) for lines.

| Input | Type | Default | Description |
|---|---|---|---|
| `text` | string | required | What you are looking for in plain words, e.g. 'network connection lost', 'memory hardware errors', 'brute force login attempts'. |
| `mode` | `hybrid` / `semantic` / `lexical` | `hybrid` | 'semantic' = by meaning (embeds the text, needs the embedding key), 'lexical' = BM25 on the template words, 'hybrid' (default) = both fused with reciprocal rank fusion (falls back to lexical without a key). |
| `k` | integer | `10` | Patterns to return. |

### `summarize_burst`

What do the logs say during this burst, in a few sentences? A MODEL-WRITTEN summary for reading, not evidence.

    Use when: a burst involves many different messages and you want a quick plain-language overview before
    digging, or to explain a burst to a non-specialist.
    Not for: any number or fact you will cite (take those from the other tools).
    Returns: model_summary (text written by SereneDB's ai_summarize_agg over the burst's distinct messages and
    `window_s` around it, stored or generated live), the burst (start, end, lines, nodes) and how many messages were
    summarized.
    Caveats: model text: never cite numbers or claims from it as facts.
    Example: summarize_burst(pattern_id=<id>, at='<incident time>')
    Next: burst_timeline / get_context for the evidence behind the summary.

| Input | Type | Default | Description |
|---|---|---|---|
| `pattern_id` | integer | required | Pattern whose burst to summarize. |
| `at` | date-time (optional) | `None` | A time inside the burst; omit for the pattern's largest burst. |
| `window_s` | integer | `300` | Also include other messages this many seconds around it. |

### `create_focus_index`

Create a temporary, indexed copy of one investigation window (a workspace) to search it repeatedly and fast.

    Use when: you will run many searches / facets over the same window of a large dataset during one investigation,
    or the question is about the speed trade-off of building an index for a time range.
    Not for: one-off searches (search_logs already uses the corpus index).
    Returns: rows copied, build time, and the measured time of a typical search and count on the full corpus vs on the
    workspace, with break_even_queries = build time / time saved per query.
    Caveats: writes to the database (a new table); drop it with drop_focus_index when done. Max 2M lines.
    Example: create_focus_index(start='<window start>', end='<window end>', name='incident1')
    Next: search_logs(workspace='incident1') / facet(workspace='incident1'); then drop_focus_index('incident1').

| Input | Type | Default | Description |
|---|---|---|---|
| `start` | date-time | required | Window start (inclusive). |
| `end` | date-time | required | Window end (exclusive). |
| `name` | string (optional) | `None` | Short name (letters, digits, _); default derived from the window. |
| `component` | string (optional) | `None` | Exact component (program / service / class that logged the line; case-sensitive). Per dataset: field guide; all values: list_values. |
| `node` | string (optional) | `None` | Exact node / host that logged the line. Per dataset: field guide. |
| `benchmark_text` | string (optional) | `None` | A search you expect to repeat (used to measure the speed-up); default 'error'. |

### `drop_focus_index`

Remove a workspace (a focus index or a remote-data index) when the investigation is over.

    Use when: a create_focus_index / remote_index workspace is no longer needed.
    Not for: anything else: this deletes the workspace's table / view and index.
    Returns: the removed workspace's name, kind, dataset, rows and build time.
    Caveats: destructive for the workspace only (never touches the corpus).
    Example: drop_focus_index(name='incident1')
    Next: index_stats to confirm it is gone.

| Input | Type | Default | Description |
|---|---|---|---|
| `name` | string | required | Workspace name (see index_stats). |

### `index_stats`

Which indexes and workspaces exist right now, and how big / healthy are they?

    Use when: checking that a workspace exists, reporting index cost (documents, size, segments, commit time), or when
    counts look stale (buffered_docs > 0 = recent writes not yet searchable).
    Not for: anything about the log contents.
    Returns: one row per inverted index (docs, live docs, buffered docs, segments, bytes, avg commit ms) and the
    workspace registry (window, rows, build time).
    Caveats: operator information only.
    Example: index_stats()
    Next: drop_focus_index for workspaces no longer needed.

### `explain_tool`

How does the database execute this tool call? The query plan of a tool's main SQL, with index-usage flags.

    Use when: a performance question ("is this served by the index or a scan?", "why is this slow?") or to show how
    a result was computed.
    Not for: the result itself (call the tool).
    Returns: the plan (EXPLAIN, or EXPLAIN ANALYZE with timings when analyze=True) of the tool's first SQL statement
    and flags: inverted_index_scan, term_dictionary_facets, wand_top_k, vector_knn, full_scan.
    Caveats: analyze=True runs the query.
    Example: explain_tool(tool='search_logs', args={'dataset': <dataset>, 'query_text': 'timeout'})
    Next: create_focus_index if a repeated query scans a lot.

| Input | Type | Default | Description |
|---|---|---|---|
| `tool` | string | required | Tool name, e.g. 'search_logs', 'facet', 'top_patterns'. |
| `args` | object | required | The tool's arguments as you would pass them. |
| `analyze` | boolean | `False` | Also run it (EXPLAIN ANALYZE) for per-operator timings. |

### `session_report`

Show the user what happened in this session: a local page with the answer, every tool call, and one-click
    verification of every number.

    Use when: you have answered the user's question with these tools — call it once at the end with the question and
    your final answer, and give the user the link. Also when the user asks for the report / to see the session.
    Not for: answering questions (it runs no new queries).
    Returns: url (open in a browser; local only), session id, tool calls recorded, and how many numbers in the answer
    were found in a tool result.
    Caveats: the page is served on 127.0.0.1 by this server process and lives as long as the session; a session file
    stays in runs/sessions/.
    Example: session_report(question='<the question>', answer='<your final answer>')
    Next: tell the user the url.

| Input | Type | Default | Description |
|---|---|---|---|
| `question` | string (optional) | `None` | The user's question, verbatim. |
| `answer` | string (optional) | `None` | Your final answer as you gave it to the user (plain text or markdown), so the page can check every number in it. |

