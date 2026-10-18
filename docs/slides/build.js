// Slides (final branch): node docs/slides/build.js → docs/slides/making-sense-of-logs.pptx
// Order follows the SchubKI Founders' Award criteria (point in the first minute, business sense, wow, scalability,
// presentation) and keeps the technical slides. Every number is copied from a committed result: docs/INVESTIGATION.md,
// eval/results/ab-20261018-193248.md, plans/006 (1/10 → 5/10), docs/PERFORMANCE.md, README (load times).
// Speaker notes = the video script with timings.
const path = require("path");
const G = require("child_process").execSync("npm root -g").toString().trim();
const req = m => require(require.resolve(m, { paths: [G] }));
const pptxgen = req("pptxgenjs"), React = req("react"), RDS = req("react-dom/server"), sharp = req("sharp");
const fa = req("react-icons/fa");

const INK = "11121D", INK2 = "2A2C44", MIST = "F0F2F5", VIOLET = "7B4FD6", DEEP = "3E318C", LILAC = "C9B8F5";
const PALE = "E9E3FB", MUTED = "6B7386", WHITE = "FFFFFF", ORANGE = "EB6834", SOFT = "D5D8E5";
const HEAD = "Trebuchet MS", BODY = "Calibri", MONO = "Consolas";
const DIR = __dirname, IMG = path.join(DIR, "img");

async function icon(Comp, color, size = 256) {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "Making Sense of Logs";
  pres.author = "Amirali & Konark";
  let N = 0;

  const slide = (dark, bg) => { const s = pres.addSlide(); s.background = { color: bg || (dark ? INK : WHITE) }; N++;
    s.addText(`Making Sense of Logs   ${N}`, { x: 6.5, y: 5.22, w: 3, h: 0.25, fontSize: 9, fontFace: BODY,
      color: dark ? "8B90A6" : MUTED, align: "right", margin: 0 }); return s; };
  const title = (s, t, dark, kicker) => {
    if (kicker) s.addText(kicker.toUpperCase(), { x: 0.5, y: 0.28, w: 9, h: 0.25, fontSize: 10, bold: true, charSpacing: 3,
      fontFace: BODY, color: dark ? LILAC : VIOLET, margin: 0 });
    s.addText(t, { x: 0.5, y: kicker ? 0.52 : 0.35, w: 9, h: 0.65, fontSize: 28, bold: true, fontFace: HEAD,
      color: dark ? WHITE : INK, margin: 0 });
  };
  const circle = async (s, ic, x, y, d = 0.55, bg = VIOLET) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg } });
    s.addImage({ data: await icon(ic, WHITE), x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52 });
  };
  const bullets = items => items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } }));

  // 1 · title: what we built, for whom (first 20 s)
  let s = slide(true);
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: 5.625, fill: { color: VIOLET } });
  s.addText("Making Sense of Logs", { x: 0.8, y: 0.9, w: 8.4, h: 0.85, fontSize: 42, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
  s.addText("Ask your logs a question in plain words and get an answer that fits your role: the engineer, the team lead and the manager each get what they need, and every number is checked against the query that produced it.",
    { x: 0.8, y: 1.85, w: 8.3, h: 1.1, fontSize: 17, fontFace: BODY, color: LILAC, margin: 0 });
  const t1 = [["5 M", "log lines (BGL and OpenStack)"], ["62 / 62", "numbers traced to a query"], ["2", "commands to set up"]];
  t1.forEach(([n, l], i) => {
    s.addText(n, { x: 0.8 + i * 2.9, y: 3.25, w: 2.8, h: 0.55, fontSize: 26, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(l, { x: 0.8 + i * 2.9, y: 3.8, w: 2.7, h: 0.35, fontSize: 12, fontFace: BODY, color: SOFT, margin: 0 });
  });
  s.addText("Amirali & Konark · SchubKI National AI Hackathon 2026 · SereneDB challenge", { x: 0.8, y: 4.7, w: 8, h: 0.3, fontSize: 11, fontFace: BODY, color: "8B90A6", margin: 0 });
  s.addNotes("0:00–0:20. We built an assistant that answers questions about millions of log lines for three different people: the engineer who fixes, the team lead who plans, the manager who decides. It runs on the company's own machine, and every number it says can be checked.");

  // 2 · the client's problem
  s = slide(false);
  title(s, "Logs hold the answers, but nobody can read them", false, "The problem");
  const pains = [
    [fa.FaWrench, "Engineer", "“What failed, and what happened just before?”", "Hours of grep across millions of lines while the system is down."],
    [fa.FaUsers, "Team lead", "“What keeps coming back, and whose is it?”", "Counts by hand in spreadsheets; one log storm looks like a thousand incidents."],
    [fa.FaChartLine, "Manager", "“What do we fix first?”", "Priorities set by whoever is loudest, not by measured frequency and spread."],
  ];
  for (let i = 0; i < 3; i++) {
    const [ic, r, q, d] = pains[i], x = 0.5 + i * 3.05;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.4, w: 2.85, h: 2.7, fill: { color: MIST } });
    await circle(s, ic, x + 0.25, 1.62);
    s.addText(r, { x: x + 0.95, y: 1.7, w: 1.8, h: 0.4, fontSize: 17, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(q, { x: x + 0.25, y: 2.35, w: 2.4, h: 0.6, fontSize: 12.5, italic: true, fontFace: BODY, color: DEEP, margin: 0 });
    s.addText(d, { x: x + 0.25, y: 3.0, w: 2.4, h: 0.95, fontSize: 12, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  s.addText("An AI model alone cannot help: millions of lines do not fit in a prompt, and a model that guesses numbers is worse than no answer.",
    { x: 0.5, y: 4.35, w: 9, h: 0.6, fontSize: 13.5, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addNotes("0:20–0:45. The client's problem in their words. Three people, three questions about the same logs. Today engineers grep, leads count in spreadsheets, and managers decide by gut. An AI model alone does not fix this: the logs do not fit in a prompt, and the model invents numbers.");

  // 3 · what we built (one picture)
  s = slide(false);
  title(s, "The database counts, the AI explains", false, "What we built");
  const layers = [
    ["Claude (or our own agent)", "Understands the question and picks the tools. Writes the answer for the role.", INK, WHITE, fa.FaComments],
    ["Our MCP server", "44 tools, 5 prompts, 6 resources. Each tool is a fixed, safe query; the AI only fills in the blanks.", VIOLET, WHITE, fa.FaPlug],
    ["SereneDB", "Searches and counts over every line: full-text index, aggregations, timelines, remote data.", DEEP, WHITE, fa.FaDatabase],
    ["Jev", "Judges each kind of message once: a real fault, or routine noise?", PALE, INK, fa.FaBalanceScale],
  ];
  for (let i = 0; i < layers.length; i++) {
    const [h, d, bg, fg, ic] = layers[i], y = 1.35 + i * 0.9;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 6.0, h: 0.75, fill: { color: bg } });
    s.addImage({ data: await icon(ic, fg), x: 0.7, y: y + 0.2, w: 0.35, h: 0.35 });
    s.addText(h, { x: 1.25, y: y + 0.06, w: 5.1, h: 0.3, fontSize: 14, bold: true, fontFace: HEAD, color: fg, margin: 0 });
    s.addText(d, { x: 1.25, y: y + 0.37, w: 5.2, h: 0.33, fontSize: 11, fontFace: BODY, color: fg, margin: 0 });
  }
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.35, w: 2.7, h: 3.45, fill: { color: MIST } });
  s.addText("Setup", { x: 7.0, y: 1.5, w: 2.4, h: 0.35, fontSize: 15, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  s.addText("docker compose up -d\nclaude\n> Load the base corpus", { x: 7.0, y: 1.9, w: 2.4, h: 0.9, fontSize: 11, fontFace: MONO, color: DEEP, margin: 0 });
  s.addText(bullets(["72 s from nothing to 5 M lines loaded (clean clone)", "Any log file: format detected automatically", "Runs locally: the logs stay on your machine"]),
    { x: 7.0, y: 2.95, w: 2.4, h: 1.75, fontSize: 11, fontFace: BODY, color: INK2, margin: 0, paraSpaceAfter: 5, valign: "top" });
  s.addNotes("0:45–1:00. That is the whole idea. The database does the searching and counting over every line. Our MCP server gives Claude 44 safe tools for it. Jev decides which messages are real faults. Claude only explains. Setup is two commands and one sentence.");

  // 4 · demo: one problem, three roles
  s = slide(false, MIST);
  title(s, "One problem, three answers", false, "Live demo · BGL supercomputer, November 2005");
  const roles = [
    ["Engineer", "What failed, before and after?", ["New fault “Link has been severed”: 12,996 lines on 1,024 nodes", "First burst: 504 nodes in 4 min; 21 min earlier, 64 job launches failed", "Every line points to one host: 172.16.96.116"], "Next check: that host's log at 05:30–05:40"],
    ["Team lead", "What recurs, and whose is it?", ["451 recurring problem bursts: node-platform 283, hpc-workloads 106", "The new fault: 31 bursts; its owner is disputed between two teams", "Weekly problem bursts 69.6 → 119.3: getting worse"], "Next step: both teams triage it together"],
    ["Manager", "What do we fix first?", ["Computed rank 1: the new fault, score 97.8", "2 and 3: two kernel faults (93.6 and 90.5)", "hpc-workloads: 9 → 106 bursts vs the month before"], "Decision: name one owner now. Cost and downtime are not in the logs."],
  ];
  roles.forEach(([r, q, facts, nx], i) => {
    const x = 0.5 + i * 3.05;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.35, w: 2.85, h: 3.65, fill: { color: WHITE } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.35, w: 2.85, h: 0.08, fill: { color: VIOLET } });
    s.addText(r, { x: x + 0.18, y: 1.52, w: 2.5, h: 0.35, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(q, { x: x + 0.18, y: 1.86, w: 2.5, h: 0.3, fontSize: 11, italic: true, fontFace: BODY, color: MUTED, margin: 0 });
    s.addText(bullets(facts), { x: x + 0.12, y: 2.22, w: 2.62, h: 1.95, fontSize: 10.5, fontFace: BODY, color: INK2, valign: "top", paraSpaceAfter: 4, margin: 0 });
    s.addText(nx, { x: x + 0.18, y: 4.25, w: 2.5, h: 0.65, fontSize: 10.5, bold: true, fontFace: BODY, color: DEEP, margin: 0, valign: "top" });
  });
  s.addNotes("1:00–2:00 LIVE DEMO in Claude Code: /mcp__logs__worked_investigation, topic 'what deserves attention in November 2005', dataset bgl. Point out: the same problem, but each role gets different evidence: one occurrence and its neighbours, recurrence by team, a computed ranking. Not three lengths of the same answer. Backup: docs/investigation/report.html.");

  // 5 · every number checkable
  s = slide(false);
  title(s, "Every number can be checked", false, "Trust");
  s.addImage({ path: path.join(IMG, "report.png"), x: 0.5, y: 1.3, w: 4.9, h: 3.7, sizing: { type: "cover", w: 4.9, h: 3.7 } });
  const st = [["62 / 62", "numbers in the answer found in a database result"], ["17 / 17", "steps give the same result when re-run with read-only access"], ["1.8 s", "of database time for 20 tool calls"]];
  st.forEach(([n, l], i) => {
    s.addText(n, { x: 5.8, y: 1.3 + i * 1.2, w: 3.8, h: 0.6, fontSize: 34, bold: true, fontFace: HEAD, color: VIOLET, margin: 0 });
    s.addText(l, { x: 5.8, y: 1.88 + i * 1.2, w: 3.7, h: 0.5, fontSize: 12.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  });
  s.addNotes("2:00–2:20. At the end Claude gives a link to the session report. Click any number to jump to the query that produced it; Verify runs it again. Facts, hypotheses and unknowns are separate. This is what lets a manager act on it.");

  // 6 · MCP overview
  s = slide(true);
  title(s, "The MCP server: four ways to use it", true, "MCP · overview");
  const surf = [
    [fa.FaTools, "44 tools", "Search, count, timelines, patterns, priorities, ownership, setup. Claude picks them from their descriptions.", "Just ask in plain words"],
    [fa.FaTerminal, "5 prompts", "Ready-made playbooks: one per role, a three-role investigation, whole-corpus counts.", "/mcp__logs__set_priorities"],
    [fa.FaFolderOpen, "6 resources", "Read-only context: datasets, glossary, field guide, ownership, the session's evidence.", "@logs:logs://ownership/bgl"],
    [fa.FaMagic, "Completions", "Prompt arguments complete with real values from the data: datasets, components, teams.", "Tab in a prompt argument"],
  ];
  for (let i = 0; i < 4; i++) {
    const [ic, h, d, how] = surf[i], x = 0.5 + (i % 2) * 4.6, y = 1.4 + Math.floor(i / 2) * 1.85;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.35, h: 1.65, fill: { color: INK2 } });
    await circle(s, ic, x + 0.22, y + 0.25);
    s.addText(h, { x: x + 0.95, y: y + 0.2, w: 3.2, h: 0.38, fontSize: 17, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(d, { x: x + 0.95, y: y + 0.6, w: 3.25, h: 0.62, fontSize: 11, fontFace: BODY, color: SOFT, margin: 0, valign: "top" });
    s.addText(how, { x: x + 0.95, y: y + 1.22, w: 3.25, h: 0.3, fontSize: 10.5, fontFace: MONO, color: LILAC, margin: 0 });
  }
  s.addNotes("2:20–2:40. MCP is how Claude talks to our server. It offers four things: tools, prompts, resources and completions. On top of that, the server instructions explain how to investigate, and every session gets a report.");

  // 7 · MCP tools
  s = slide(false);
  title(s, "44 tools, grouped by the question they answer", false, "MCP · tools");
  const groups = [
    ["Set up", "setup_status · load_logs · use_dataset · remove_dataset", "“Load my log file ~/app.log”"],
    ["Find", "search_logs (9 match modes) · get_context · find_patterns · suggest_terms", "“What failed on node R43 at 13:56?”"],
    ["Count", "count_by · trend · facet · rollup · heatmap · rate_vs_baseline", "“Errors per team, week over week?”"],
    ["Recurring", "top_patterns · pattern_history · whats_new · spread · periodicity", "“What keeps coming back?”"],
    ["Explain", "burst_timeline · precursors · co_occurrence · request_timeline · value_outliers", "“What happens just before it?”"],
    ["Decide", "priority_table · reliability_trend · team_risk · owner_of · ownership_gaps", "“What do we fix first, and who owns it?”"],
    ["Scale", "create_focus_index · index_stats · explain_tool · session_report", "“Index this week for a deep dive”"],
  ];
  groups.forEach(([g, t, q], i) => {
    const y = 1.3 + i * 0.52;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 1.25, h: 0.44, fill: { color: i % 2 ? DEEP : VIOLET } });
    s.addText(g, { x: 0.5, y, w: 1.25, h: 0.44, fontSize: 12, bold: true, fontFace: HEAD, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: 1.9, y, w: 4.9, h: 0.44, fontSize: 10.5, fontFace: MONO, color: INK2, valign: "middle", margin: 0 });
    s.addText(q, { x: 6.9, y, w: 2.6, h: 0.44, fontSize: 10.5, italic: true, fontFace: BODY, color: MUTED, valign: "middle", margin: 0 });
  });
  s.addText("Every result returns its SQL, filters, scope, the exact total, and whether it was cut to 50 rows. Full reference: docs/TOOLS.md",
    { x: 0.5, y: 5.0, w: 6.0, h: 0.3, fontSize: 10.5, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addNotes("2:40–2:55. The tools are grouped by the question they answer. You never name a tool: you ask, and Claude picks one from its description. Each description says when to use it, when not to, what it returns and which tool comes next.");

  // 8 · MCP prompts, resources, completions: how to use
  s = slide(false);
  title(s, "Prompts, resources, completions", false, "MCP · how to use");
  s.addText("Prompts: type / and pick one", { x: 0.5, y: 1.3, w: 4.4, h: 0.35, fontSize: 14, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  const pr = [["/mcp__logs__investigate_failure", "engineer playbook"], ["/mcp__logs__review_recurring_problems", "team-lead playbook"], ["/mcp__logs__set_priorities", "manager playbook"],
    ["/mcp__logs__worked_investigation", "one topic, all three roles"], ["/mcp__logs__whole_corpus_counts", "counts over every dataset"]];
  pr.forEach(([c, d], i) => {
    s.addText(c, { x: 0.5, y: 1.72 + i * 0.5, w: 4.4, h: 0.25, fontSize: 10.5, fontFace: MONO, color: DEEP, margin: 0 });
    s.addText(d, { x: 0.5, y: 1.95 + i * 0.5, w: 4.4, h: 0.22, fontSize: 10.5, fontFace: BODY, color: MUTED, margin: 0 });
  });
  s.addText("Resources: type @ to attach", { x: 5.2, y: 1.3, w: 4.3, h: 0.35, fontSize: 14, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  const rs = [["logs://datasets", "what is loaded"], ["logs://glossary", "line, pattern, burst, the rules"], ["logs://field-guide/{dataset}", "what each field means"],
    ["logs://ownership/{dataset}", "component → team, with confidence"], ["logs://session/latest", "every query of this session"], ["logs://session/{id}/step/{n}", "one step in full"]];
  rs.forEach(([c, d], i) => {
    s.addText(c, { x: 5.2, y: 1.72 + i * 0.42, w: 2.55, h: 0.36, fontSize: 10.5, fontFace: MONO, color: DEEP, margin: 0, valign: "middle" });
    s.addText(d, { x: 7.75, y: 1.72 + i * 0.42, w: 1.8, h: 0.36, fontSize: 10.5, fontFace: BODY, color: MUTED, margin: 0, valign: "middle" });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.2, y: 4.35, w: 4.3, h: 0.65, fill: { color: PALE } });
  s.addText("Completions: prompt arguments suggest real datasets, components, teams and levels as you type.",
    { x: 5.35, y: 4.38, w: 4.05, h: 0.6, fontSize: 11, fontFace: BODY, color: INK, margin: 0, valign: "middle" });
  s.addNotes("2:55–3:10. Prompts are slash commands: one per role, plus a three-role investigation and the whole-corpus counts the brief asks for. Resources attach context with @: ownership, the field guide, or the complete evidence of the session, beyond the 50-row tool limit.");

  // 9 · MCP: connect, load, restrict, verify
  s = slide(false, MIST);
  title(s, "Connect, load, restrict, verify", false, "MCP · setup and control");
  const steps = [
    [fa.FaLink, "Connect", "In the repo: claude (reads .mcp.json). Anywhere: claude mcp add -s user logs -- uv run … python mcp_server/server.py"],
    [fa.FaFileImport, "Load", "load_logs('base') = BGL + OpenStack from Zenodo (72 s). load_logs('~/app.log'): format detected from 76 known formats, refused below 95 %."],
    [fa.FaLock, "Restrict", "LOGS_DB_ROLE=team_<team>: the database itself shows a team only its own components. logs_manager is read-only."],
    [fa.FaCheckDouble, "Verify", "session_report → a local page: the answer, each number linked to its query, and Verify re-runs each step read-only."],
  ];
  for (let i = 0; i < 4; i++) {
    const [ic, h, d] = steps[i], y = 1.32 + i * 0.92;
    await circle(s, ic, 0.5, y + 0.08, 0.6);
    s.addText(h, { x: 1.3, y, w: 1.6, h: 0.75, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(d, { x: 2.9, y, w: 6.6, h: 0.75, fontSize: 12, fontFace: BODY, color: INK2, margin: 0, valign: "middle" });
  }
  s.addNotes("3:10–3:25. Connecting is one line. Loading works for our base corpus and for any log file. Access can be restricted per team by the database itself, not by the prompt. And every session can be verified.");

  // 10 · results
  s = slide(false);
  title(s, "Measured, not claimed: 50 questions, blind judge", false, "Results");
  s.addImage({ path: path.join(IMG, "dashboard.png"), x: 0.5, y: 1.3, w: 5.0, h: 3.7, sizing: { type: "cover", w: 5.0, h: 3.7 } });
  const ev = [["13 – 2", "wins vs the reference design on the brief's data (BGL + OpenStack)"], ["53 vs 69", "wrong claims over 50 answers"], ["1/10 → 5/10", "real alerts in the top 10 once Jev judged the messages"], ["44 s vs 22 s", "our cost: slower, almost all of it AI time"]];
  ev.forEach(([n, l], i) => {
    s.addText(n, { x: 5.8, y: 1.3 + i * 0.93, w: 3.7, h: 0.45, fontSize: 22, bold: true, fontFace: HEAD, color: i === 3 ? ORANGE : INK, margin: 0 });
    s.addText(l, { x: 5.8, y: 1.73 + i * 0.93, w: 3.7, h: 0.42, fontSize: 11, fontFace: BODY, color: MUTED, margin: 0, valign: "top" });
  });
  s.addNotes("3:25–3:50. We tested it like a client would: 50 questions with known answers, and a judge that does not know which system wrote which answer. On the brief's data we win 13 to 2 and make fewer wrong claims. Honest limits: we are twice as slow, and on small extra datasets the simpler agent wins more manager questions. The dashboard shows every answer.");

  // 11 · wow: beyond the brief
  s = slide(true);
  title(s, "Beyond what the brief asked for", true, "Wow");
  const wow = [
    [fa.FaFileAlt, "Bring your own logs", "Any file, format detected, loaded in seconds (21 k lines: 1.6 s)"],
    [fa.FaCheckDouble, "Verify button", "Re-runs the query behind every number"],
    [fa.FaBrain, "AI judgments, computed once", "Jev labels each kind of message; nothing re-reads raw lines"],
    [fa.FaCloud, "1 billion remote rows", "Queried in place on S3, no download"],
    [fa.FaUserShield, "Per-team access", "Enforced by the database, not the prompt"],
    [fa.FaFlask, "Our own blind eval", "50 answer keys, built from raw SQL and labels"],
  ];
  for (let i = 0; i < 6; i++) {
    const [ic, h, d] = wow[i], x = 0.5 + (i % 3) * 3.05, y = 1.4 + Math.floor(i / 3) * 1.8;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.85, h: 1.6, fill: { color: INK2 } });
    await circle(s, ic, x + 0.2, y + 0.2, 0.5);
    s.addText(h, { x: x + 0.2, y: y + 0.8, w: 2.5, h: 0.3, fontSize: 13, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(d, { x: x + 0.2, y: y + 1.1, w: 2.5, h: 0.45, fontSize: 10.5, fontFace: BODY, color: SOFT, margin: 0, valign: "top" });
  }
  s.addNotes("3:50–4:10. What goes beyond the brief: your own log files with no code, a Verify button on every number, team access enforced by the database, a billion rows read in place, and an evaluation the client can re-run themselves.");

  // 12 · business sense
  s = slide(false);
  title(s, "Where it fits in a company", false, "Business sense");
  const fit = [["On-call", "Engineer asks during an incident", "an answer in ~44 s instead of a manual search"], ["Weekly review", "Lead opens the recurring problems", "counts by team, ready for the meeting"], ["Monthly planning", "Manager gets the computed ranking", "a decision backed by measured frequency"]];
  fit.forEach(([h, a, b], i) => {
    const x = 0.5 + i * 3.05;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.35, w: 2.85, h: 1.45, fill: { color: PALE } });
    s.addText(h, { x: x + 0.2, y: 1.45, w: 2.5, h: 0.35, fontSize: 15, bold: true, fontFace: HEAD, color: DEEP, margin: 0 });
    s.addText(a, { x: x + 0.2, y: 1.85, w: 2.5, h: 0.4, fontSize: 11.5, fontFace: BODY, color: INK, margin: 0 });
    s.addText(b, { x: x + 0.2, y: 2.25, w: 2.5, h: 0.45, fontSize: 11, italic: true, fontFace: BODY, color: INK2, margin: 0 });
  });
  s.addText("What it saves (measured)", { x: 0.5, y: 3.0, w: 4.4, h: 0.32, fontSize: 13.5, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  s.addText(bullets(["Setup: 72 s to 5 M lines; a new log file in seconds", "Database time per answer: under 1 s", "Logs stay in the company; only tool results reach the AI"]),
    { x: 0.5, y: 3.35, w: 4.4, h: 1.5, fontSize: 11.5, fontFace: BODY, color: INK2, margin: 0, paraSpaceAfter: 4, valign: "top" });
  s.addText("Risks and limits (stated)", { x: 5.2, y: 3.0, w: 4.3, h: 0.32, fontSize: 13.5, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  s.addText(bullets(["Logs hold no cost or downtime: we never invent them", "~44 s per answer: AI time, not database time", "New formats without a Jev key fall back to log levels"]),
    { x: 5.2, y: 3.35, w: 4.3, h: 1.5, fontSize: 11.5, fontFace: BODY, color: INK2, margin: 0, paraSpaceAfter: 4, valign: "top" });
  s.addNotes("4:10–4:30. In the company it fits three existing routines: the incident, the weekly review, the monthly planning. Measured: setup in about a minute, under a second of database time per answer. Limits we state openly: the logs hold no money or downtime, and an answer takes about 44 seconds.");

  // 13 · scalability
  s = slide(true);
  title(s, "Where it goes next", true, "Scalability");
  const nx = [
    [fa.FaIndustry, "Mittelstand", "Machine and production logs, IT operations, managed service providers: same tools, their files."],
    [fa.FaBuilding, "Other industries", "Any system that writes logs: cloud, telecom, devices, security (SSH attacks are already in our eval)."],
    [fa.FaBoxOpen, "A product", "A self-hosted log copilot: MCP server + SereneDB in one container, per-team access, alerts from saved searches."],
  ];
  for (let i = 0; i < 3; i++) {
    const [ic, h, d] = nx[i], x = 0.5 + i * 3.05;
    await circle(s, ic, x, 1.5, 0.7);
    s.addText(h, { x, y: 2.35, w: 2.8, h: 0.4, fontSize: 17, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(d, { x, y: 2.8, w: 2.8, h: 1.1, fontSize: 12, fontFace: BODY, color: SOFT, margin: 0, valign: "top" });
  }
  s.addText("Already shown: 10 Loghub datasets from 7 kinds of systems load with no code change.",
    { x: 0.5, y: 4.3, w: 9, h: 0.4, fontSize: 13, bold: true, fontFace: BODY, color: LILAC, margin: 0 });
  s.addNotes("4:30–4:45. Nothing in the code is specific to one dataset: 10 different log types load without code changes. That makes it a product: a self-hosted log copilot for Mittelstand IT and production, with per-team access and alerts.");

  // 14 · close
  s = slide(true);
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: 5.625, fill: { color: VIOLET } });
  s.addText("Try it in two commands", { x: 0.8, y: 0.6, w: 8, h: 0.7, fontSize: 32, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
  s.addText("docker compose up -d\nclaude          # in the repo, approve the logs server\n> Load the base corpus",
    { x: 0.8, y: 1.5, w: 8.4, h: 1.1, fontSize: 15, fontFace: MONO, color: LILAC, margin: 0 });
  s.addText(bullets(["docs/INVESTIGATION.md: the worked investigation and its evidence page", "docs/dashboard.html: the evaluation, every answer, how to re-run it", "docs/TOOLS.md: every tool, prompt and resource"]),
    { x: 0.8, y: 2.95, w: 8.4, h: 1.2, fontSize: 14, fontFace: BODY, color: SOFT, margin: 0, paraSpaceAfter: 6 });
  s.addText("github.com/aircode610/making-sense-of-logs-schubki-ai-hackathon", { x: 0.8, y: 4.7, w: 8.4, h: 0.35, fontSize: 12, fontFace: BODY, color: "8B90A6", margin: 0 });
  s.addNotes("4:45–5:00. Two commands and one sentence, and your logs answer back. Thank you.");

  await pres.writeFile({ fileName: path.join(DIR, "making-sense-of-logs.pptx") });
  console.log(`wrote docs/slides/making-sense-of-logs.pptx (${N} slides)`);
})();
