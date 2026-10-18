// Slides (plan 017): node docs/slides/build.js  → docs/slides/making-sense-of-logs.pptx
// Numbers are copied from committed results: docs/INVESTIGATION.md, eval/results/ab-20261018-193248.md,
// plans/006 (1/10 → 5/10), docs/PERFORMANCE.md. Speaker notes = the 5-minute demo script.
const path = require("path");
const pptxgen = require(require.resolve("pptxgenjs", { paths: [require("child_process").execSync("npm root -g").toString().trim()] }));
const React = require(require.resolve("react", { paths: [require("child_process").execSync("npm root -g").toString().trim()] }));
const RDS = require(require.resolve("react-dom/server", { paths: [require("child_process").execSync("npm root -g").toString().trim()] }));
const sharp = require(require.resolve("sharp", { paths: [require("child_process").execSync("npm root -g").toString().trim()] }));
const fa = require(require.resolve("react-icons/fa", { paths: [require("child_process").execSync("npm root -g").toString().trim()] }));

const INK = "11121D", INK2 = "2A2C44", MIST = "F0F2F5", VIOLET = "7B4FD6", DEEP = "3E318C", LILAC = "C9B8F5";
const MUTED = "6B7386", WHITE = "FFFFFF", BLUE = "2A78D6", ORANGE = "EB6834", GREEN = "16A34A";
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

  const footer = (s, n, dark) => s.addText(`Making Sense of Logs · SereneDB challenge   ${n}`, {
    x: 0.5, y: 5.2, w: 9, h: 0.3, fontSize: 9, fontFace: BODY, color: dark ? "8B90A6" : MUTED, align: "right", margin: 0 });
  const title = (s, t, dark) => s.addText(t, { x: 0.5, y: 0.35, w: 9, h: 0.7, fontSize: 30, bold: true,
    fontFace: HEAD, color: dark ? WHITE : INK, margin: 0 });

  // 1 · title
  let s = pres.addSlide(); s.background = { color: INK };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: 5.625, fill: { color: VIOLET } });
  s.addText("Making Sense of Logs", { x: 0.8, y: 1.3, w: 8.4, h: 0.9, fontSize: 44, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
  s.addText("SereneDB counts, Jev judges, the LLM explains, and every number is checked against the query that produced it.",
    { x: 0.8, y: 2.25, w: 8.2, h: 0.9, fontSize: 18, fontFace: BODY, color: LILAC, margin: 0 });
  s.addText("One MCP server · 44 tools · 3 roles · BGL 4.7 M + OpenStack 208 k lines",
    { x: 0.8, y: 3.45, w: 8.4, h: 0.4, fontSize: 14, fontFace: BODY, color: "B8BDD0", margin: 0 });
  s.addText("Amirali & Konark · SchubKI National AI Hackathon 2026", { x: 0.8, y: 4.6, w: 8, h: 0.35, fontSize: 12, fontFace: BODY, color: "8B90A6", margin: 0 });
  s.addNotes("0:00–0:20. Millions of log lines don't fit in a prompt. Our answer: the database searches and counts, Jev (a typed-judgment model) decides which messages are real faults, and the LLM only explains. Every number traces back to a query.");

  // 2 · the problem with the reference design
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Where the reference design breaks");
  const probs = [
    [fa.FaListOl, "Lines are not incidents", "BGL: 4.7 M lines, 855,501 of them FATAL, but only 36,714 bursts of recurring patterns."],
    [fa.FaExclamationTriangle, "Severity ≠ real problem", "Ranked by log level, 1 of the top 10 is a real labelled alert. FATAL register dumps win."],
    [fa.FaCalculator, "Unverified numbers", "The LLM rounds, merges and invents numbers that no query returned."],
    [fa.FaUserFriends, "Roles become tone", "The same evidence, only shorter. The brief says that is not enough."],
  ];
  for (let i = 0; i < probs.length; i++) {
    const [ic, h, d] = probs[i], x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.85;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.35, h: 1.6, fill: { color: MIST } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.3, w: 0.6, h: 0.6, fill: { color: VIOLET } });
    s.addImage({ data: await icon(ic, WHITE), x: x + 0.39, y: y + 0.44, w: 0.32, h: 0.32 });
    s.addText(h, { x: x + 1.05, y: y + 0.22, w: 3.1, h: 0.4, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(d, { x: x + 1.05, y: y + 0.66, w: 3.1, h: 0.8, fontSize: 12.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  footer(s, 2);
  s.addNotes("0:20–0:50. Everyone builds the brief's reference: a ReAct agent plus SQL tools. We built it too, as our baseline, and measured where it fails. These four failures are what our design targets.");

  // 3 · architecture
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Question → evidence → recommendation");
  const boxes = [
    ["Claude or our agent", "picks tools from their descriptions; roles differ in the evidence they ask for", INK, WHITE],
    ["MCP server · 44 tools", "fixed parameterised SQL; every result carries its SQL, filters, scope, total, truncated flag", VIOLET, WHITE],
    ["SereneDB", "inverted index · BM25 · phrase / fuzzy · ASOF · ROLLUP · PIVOT · read_parquet over S3", DEEP, WHITE],
    ["Jev (in SQL)", "judges each pattern once: real fault or routine dump, and the owner area", "E9E3FB", INK],
  ];
  boxes.forEach(([h, d, bg, fg], i) => {
    const y = 1.2 + i * 0.95;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 5.6, h: 0.78, fill: { color: bg } });
    s.addText(h, { x: 0.7, y: y + 0.06, w: 5.2, h: 0.32, fontSize: 14, bold: true, fontFace: HEAD, color: fg, margin: 0 });
    s.addText(d, { x: 0.7, y: y + 0.38, w: 5.3, h: 0.34, fontSize: 10.5, fontFace: BODY, color: fg, margin: 0 });
  });
  s.addText([
    { text: "Beyond tools", options: { bold: true, fontSize: 15, color: INK, breakLine: true } },
    { text: "5 prompts: one per role, a worked investigation, whole-corpus counts", options: { bullet: true, breakLine: true } },
    { text: "6 resources: the session evidence, ownership, the field guide", options: { bullet: true, breakLine: true } },
    { text: "Completions from the data: datasets, components, teams", options: { bullet: true, breakLine: true } },
    { text: "Load the base corpus or any log file from Claude", options: { bullet: true, breakLine: true } },
    { text: "A session report: each number linked to its step, with Verify", options: { bullet: true } },
  ], { x: 6.4, y: 1.2, w: 3.2, h: 3.7, fontSize: 12, fontFace: BODY, color: INK2, valign: "top", paraSpaceAfter: 6, margin: 0 });
  footer(s, 3);
  s.addNotes("0:50–1:20. Setup is docker compose up, then claude in the repo, then 'load the base corpus': 72 s on a clean clone. The tools are fixed queries; the model only fills typed fields. Jev ran once per pattern inside SereneDB, 1,126 BGL patterns in 20 s.");

  // 4 · demo: the three roles
  s = pres.addSlide(); s.background = { color: MIST };
  title(s, "One problem, three roles: BGL, November 2005");
  const roles = [
    ["Engineer", "What failed, before and after?", ["New FATAL “Link has been severed”: 12,996 lines on 1,024 I/O nodes", "First burst: 504 nodes in 4 min; 21 min earlier, 64 “xhpl … Permission denied”", "One peer on every line: 172.16.96.116"], "Next check: that host's log at 05:30–05:40"],
    ["Team lead", "What recurs, and whose is it?", ["451 problem bursts: node-platform 283, hpc-workloads 106, cluster-control 62", "Link severed: 31 bursts, new; owner disputed (Jev p 0.939)", "Weekly bursts 69.6 → 119.3: worsening"], "Next step: both teams triage it together"],
    ["Manager", "What first?", ["Computed rank 1: Link severed, score 97.8", "2: rts kernel terminated, 93.6 · 3: rts panic, 90.5", "hpc-workloads bursts 9 → 106 vs the previous 30 days"], "Decision: one owner now; cost and downtime are not in the logs"],
  ];
  roles.forEach(([r, q, facts, nx], i) => {
    const x = 0.5 + i * 3.05;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.2, w: 2.85, h: 3.75, fill: { color: WHITE } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.2, w: 2.85, h: 0.08, fill: { color: VIOLET } });
    s.addText(r, { x: x + 0.18, y: 1.38, w: 2.5, h: 0.35, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(q, { x: x + 0.18, y: 1.72, w: 2.5, h: 0.3, fontSize: 11, italic: true, fontFace: BODY, color: MUTED, margin: 0 });
    s.addText(facts.map((f, k) => ({ text: f, options: { bullet: true, breakLine: k < facts.length - 1 } })),
      { x: x + 0.12, y: 2.08, w: 2.6, h: 2.0, fontSize: 10.5, fontFace: BODY, color: INK2, valign: "top", paraSpaceAfter: 4, margin: 0 });
    s.addText(nx, { x: x + 0.18, y: 4.2, w: 2.5, h: 0.62, fontSize: 10.5, bold: true, fontFace: BODY, color: DEEP, margin: 0, valign: "top" });
  });
  footer(s, 4);
  s.addNotes("1:20–3:00 LIVE DEMO in Claude Code. Type /mcp__logs__worked_investigation with topic 'what deserves attention in November 2005' (dataset bgl), or ask the three role questions from docs/INVESTIGATION.md. Point out: the engineer gets an occurrence and its neighbours, the lead gets recurrence by team, the manager gets the computed ranking. Different evidence, not different lengths. Backup if the network fails: open docs/investigation/report.html.");

  // 5 · evidence
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "Every number is checkable");
  s.addImage({ path: path.join(IMG, "report.png"), x: 0.5, y: 1.15, w: 4.9, h: 3.9, sizing: { type: "cover", w: 4.9, h: 3.9 } });
  const stats = [["62 / 62", "numbers in the answer found in a tool result"], ["17 / 17", "read steps give the same result when re-run on a read-only role"], ["1.8 s", "inside SereneDB for 20 tool calls"]];
  stats.forEach(([n, l], i) => {
    s.addText(n, { x: 5.8, y: 1.2 + i * 1.25, w: 3.8, h: 0.6, fontSize: 36, bold: true, fontFace: HEAD, color: VIOLET, margin: 0 });
    s.addText(l, { x: 5.8, y: 1.8 + i * 1.25, w: 3.8, h: 0.5, fontSize: 12.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  });
  footer(s, 5);
  s.addNotes("3:00–3:30. At the end Claude calls session_report and gives a link. Click a number to jump to the step and its SQL; Verify re-runs that step. Facts, hypothesis, unknown and next step are separate cards. Whole-corpus counts: BGL 4,747,963 lines and OpenStack 207,820 by team.");

  // 6 · eval
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, "50 golden questions, blind judge");
  s.addChart(pres.charts.BAR, [
    { name: "Our agent", labels: ["Base corpus (23)", "Engineer (21)", "All 50", "Manager (14)"], values: [13, 10, 16, 2] },
    { name: "Reference ReAct", labels: ["Base corpus (23)", "Engineer (21)", "All 50", "Manager (14)"], values: [2, 2, 12, 6] },
  ], { x: 0.4, y: 1.15, w: 5.4, h: 3.8, barDir: "bar", barGrouping: "clustered", chartColors: [BLUE, ORANGE],
    catAxisLabelColor: INK2, valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showValue: true, dataLabelColor: INK, dataLabelFontSize: 11, catAxisLabelFontSize: 11, catAxisOrientation: "maxMin",
    showLegend: true, legendPos: "b", legendFontSize: 11, showTitle: true, title: "Order-consistent wins", titleFontSize: 12, titleColor: MUTED });
  const ev = [["53 vs 69", "wrong claims, checked against the answer keys"], ["0.84 vs 0.71", "golden facts mentioned"], ["1/10 → 5/10", "real alerts in the top 10 after Jev's judgment"], ["44 s vs 22 s", "per answer: our cost, almost all of it LLM time"]];
  ev.forEach(([n, l], i) => {
    s.addText(n, { x: 6.1, y: 1.15 + i * 0.95, w: 3.5, h: 0.45, fontSize: 22, bold: true, fontFace: HEAD, color: i === 3 ? ORANGE : INK, margin: 0 });
    s.addText(l, { x: 6.1, y: 1.58 + i * 0.95, w: 3.5, h: 0.4, fontSize: 11, fontFace: BODY, color: MUTED, margin: 0 });
  });
  footer(s, 6);
  s.addNotes("3:30–4:15. 50 questions with frozen answer keys; the judge sees both answers blind, in both orders. On the base corpus we win 13 to 2, and on the engineer 10 to 2. Honest result: the reference agent wins more manager questions on the 7 extra small datasets, because our manager recipe always starts from the ranking. Everything is in docs/dashboard.html, which also explains how to re-run it.");

  // 7 · huge data
  s = pres.addSlide(); s.background = { color: INK };
  title(s, "Bigger data, same tools", true);
  const big = [["11.2 M", "HDFS lines loaded in 47 s"], ["1 B", "OTel records on S3, queried in place"], ["2.8 s", "count over 10 of 1,624 row groups"], ["4", "searches until a remote index pays off"]];
  big.forEach(([n, l], i) => {
    const x = 0.5 + i * 2.3;
    s.addText(n, { x, y: 1.7, w: 2.1, h: 0.9, fontSize: 40, bold: true, fontFace: HEAD, color: LILAC, margin: 0 });
    s.addText(l, { x, y: 2.65, w: 2.0, h: 0.8, fontSize: 13, fontFace: BODY, color: "D5D8E5", margin: 0, valign: "top" });
  });
  s.addText("Any log file: its format is detected from 76 lnav definitions (≥ 95 % match or refused). 10 Loghub datasets load with no code change.",
    { x: 0.5, y: 3.9, w: 9, h: 0.7, fontSize: 13, fontFace: BODY, color: "B8BDD0", margin: 0 });
  footer(s, 7, true);
  s.addNotes("4:15–4:40. The same tools on HDFS (11 M lines) and on the remote 1 B-record OpenTelemetry Parquet, read in place with row-group pruning. On-demand indexes report their own break-even.");

  // 8 · close
  s = pres.addSlide(); s.background = { color: INK };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: 5.625, fill: { color: VIOLET } });
  s.addText("Try it", { x: 0.8, y: 0.7, w: 8, h: 0.7, fontSize: 34, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
  s.addText([
    { text: "docker compose up -d", options: { breakLine: true } },
    { text: "claude          # in the repo, approve the logs server", options: { breakLine: true } },
    { text: "> Load the base corpus", options: {} },
  ], { x: 0.8, y: 1.6, w: 8.4, h: 1.2, fontSize: 15, fontFace: MONO, color: LILAC, margin: 0 });
  s.addText([
    { text: "docs/INVESTIGATION.md: the worked investigation and its evidence page", options: { bullet: true, breakLine: true } },
    { text: "docs/dashboard.html: the eval, every answer, how to re-run it", options: { bullet: true, breakLine: true } },
    { text: "docs/TOOLS.md: every tool, prompt and resource", options: { bullet: true } },
  ], { x: 0.8, y: 3.1, w: 8.4, h: 1.3, fontSize: 14, fontFace: BODY, color: "D5D8E5", margin: 0, paraSpaceAfter: 6 });
  s.addText("github.com/aircode610/making-sense-of-logs-schubki-ai-hackathon", { x: 0.8, y: 4.75, w: 8.4, h: 0.35, fontSize: 12, fontFace: BODY, color: "8B90A6", margin: 0 });
  s.addNotes("4:40–5:00. Two commands and one sentence. Thank you.");

  await pres.writeFile({ fileName: path.join(DIR, "making-sense-of-logs.pptx") });
  console.log("wrote docs/slides/making-sense-of-logs.pptx");
})();
