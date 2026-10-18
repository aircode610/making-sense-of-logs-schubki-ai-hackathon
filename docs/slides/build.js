// Slides (final branch): node docs/slides/build.js → docs/slides/making-sense-of-logs.pptx
// SereneDB look (serenedb.com: geometric sans, ink #11121D, mist #F0F2F5, violet gradient #A162F0 → #3E318C), light,
// rounded cards. Flow: problem → solution (helps, more accurate, faster) → fits the company → cheaper (Jev) →
// performance (SereneDB) → technical (MCP) → wow → scale → try it.
// Every number is copied from a committed result: docs/INVESTIGATION.md, eval/results/ab-20261018-193248.md,
// eval/results/cc-20261018-195733.md (plan 018 pilot, 3 questions), plans/006, docs/PERFORMANCE.md, README.
// Speaker notes = the video script.
const path = require("path");
const G = require("child_process").execSync("npm root -g").toString().trim();
const req = m => require(require.resolve(m, { paths: [G] }));
const pptxgen = req("pptxgenjs"), React = req("react"), RDS = req("react-dom/server"), sharp = req("sharp");
const fa = req("react-icons/fa");

const INK = "11121D", INK2 = "3A3F55", MUTED = "6B7386", MIST = "F0F2F5", LINE = "E3E6EC", WHITE = "FFFFFF";
const VIOLET = "6A4BD8", DEEP = "3E318C", BRAND_A = "A162F0", PALE = "F1ECFD", PALE2 = "E6DDFB", BLUE = "4A7AAD";
const OK = "15803D", WARN = "C2410C";
const FONT = process.env.SLIDE_FONT || "Avenir Next";        // SLIDE_FONT=Arial for a LibreOffice preview
const HEAD = FONT, BODY = FONT, MONO = process.env.SLIDE_MONO || "Menlo";
const DIR = __dirname, IMG = path.join(DIR, "img");
const R = 0.14;                                   // corner radius (inches) of every card

async function icon(Comp, color, size = 256) {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
async function gradient(w, h, rx = 0) {             // brand gradient as a rounded PNG
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#${BRAND_A}"/><stop offset="1" stop-color="#${DEEP}"/></linearGradient></defs>
    <rect width="${w}" height="${h}" rx="${rx}" ry="${rx}" fill="url(#g)"/></svg>`;
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
async function rounded(file, rx = 28) {             // screenshot with rounded corners and a hairline border
  const img = sharp(file), m = await img.metadata();
  const mask = Buffer.from(`<svg width="${m.width}" height="${m.height}"><rect width="${m.width}" height="${m.height}" rx="${rx}" ry="${rx}"/></svg>`);
  const border = Buffer.from(`<svg width="${m.width}" height="${m.height}"><rect x="1" y="1" width="${m.width - 2}" height="${m.height - 2}" rx="${rx}" ry="${rx}" fill="none" stroke="#${LINE}" stroke-width="3"/></svg>`);
  const buf = await img.composite([{ input: mask, blend: "dest-in" }, { input: border }]).png().toBuffer();
  return { data: "image/png;base64," + buf.toString("base64"), ratio: m.width / m.height };
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "Making Sense of Logs";
  pres.author = "Amirali & Konark";
  const GRAD_BAR = await gradient(800, 80, 40), GRAD_SQ = await gradient(200, 200, 50);
  const gcard = (w, h) => gradient(Math.round(w * 200), Math.round(h * 200), Math.round(R * 200 * 1.4));   // inches → px, same radius as cards
  let N = 0;

  const card = (s, x, y, w, h, fill = MIST, line) => s.addShape(pres.shapes.ROUNDED_RECTANGLE,
    { x, y, w, h, rectRadius: R, fill: { color: fill }, line: line ? { color: line, width: 1 } : { type: "none" } });
  const slide = (section) => {
    const s = pres.addSlide(); s.background = { color: WHITE }; N++;
    s.addImage({ data: GRAD_SQ, x: 0.5, y: 5.18, w: 0.16, h: 0.16 });
    s.addText("Making Sense of Logs" + (section ? `  ·  ${section}` : ""), { x: 0.74, y: 5.14, w: 6, h: 0.25, fontSize: 9, fontFace: BODY, color: MUTED, margin: 0 });
    s.addText(String(N), { x: 8.5, y: 5.14, w: 1, h: 0.25, fontSize: 9, fontFace: BODY, color: MUTED, align: "right", margin: 0 });
    return s;
  };
  const title = (s, kicker, t, sub) => {
    s.addText(kicker.toUpperCase(), { x: 0.5, y: 0.3, w: 9, h: 0.25, fontSize: 10, bold: true, charSpacing: 3, fontFace: BODY, color: VIOLET, margin: 0 });
    s.addText(t, { x: 0.5, y: 0.55, w: 9, h: 0.6, fontSize: 26, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    if (sub) s.addText(sub, { x: 0.5, y: 1.13, w: 9, h: 0.35, fontSize: 12.5, fontFace: BODY, color: MUTED, margin: 0 });
  };
  const dot = async (s, ic, x, y, d = 0.5) => {
    s.addImage({ data: GRAD_SQ, x, y, w: d, h: d });
    s.addImage({ data: await icon(ic, WHITE), x: x + d * 0.26, y: y + d * 0.26, w: d * 0.48, h: d * 0.48 });
  };
  const big = (s, n, l, x, y, w, color = VIOLET, size = 30) => {
    s.addText(n, { x, y, w, h: 0.55, fontSize: size, bold: true, fontFace: HEAD, color, margin: 0 });
    s.addText(l, { x, y: y + 0.55, w, h: 0.55, fontSize: 11, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  };
  const bullets = (items, extra = {}) => items.map((t, k) => ({ text: t, options: { bullet: { indent: 12 }, breakLine: k < items.length - 1, ...extra } }));

  // ───────────── 1 · title
  let s = pres.addSlide(); s.background = { color: WHITE }; N++;
  s.addImage({ data: await gcard(3.6, 4.7), x: 5.9, y: 0.45, w: 3.6, h: 4.7 });
  const t1 = [["5 M", "log lines, BGL + OpenStack"], ["44", "MCP tools for Claude"], ["62 / 62", "numbers traced to a query"]];
  t1.forEach(([n, l], i) => {
    s.addText(n, { x: 6.25, y: 0.85 + i * 1.4, w: 3, h: 0.6, fontSize: 32, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(l, { x: 6.25, y: 1.45 + i * 1.4, w: 3, h: 0.35, fontSize: 12, fontFace: BODY, color: "EDE7FF", margin: 0 });
  });
  s.addImage({ data: GRAD_SQ, x: 0.5, y: 0.6, w: 0.42, h: 0.42 });
  s.addText("SereneDB challenge · SchubKI National AI Hackathon 2026", { x: 1.05, y: 0.62, w: 4.7, h: 0.38, fontSize: 11, fontFace: BODY, color: MUTED, margin: 0, valign: "middle" });
  s.addText("Making Sense\nof Logs", { x: 0.5, y: 1.3, w: 5.3, h: 1.4, fontSize: 38, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  s.addText("Ask your logs a question in plain words. The engineer, the team lead and the manager each get the answer they need, and every number is checked against the query that produced it.",
    { x: 0.5, y: 2.9, w: 5.1, h: 1.3, fontSize: 14, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  s.addText("Amirali & Konark", { x: 0.5, y: 4.55, w: 5, h: 0.3, fontSize: 12, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addNotes("0:00–0:15. We built an assistant that answers questions about millions of log lines, for three people who need different things: the engineer who fixes, the team lead who plans, and the manager who decides. Every number it says can be checked.");

  // ───────────── 2 · the problem
  s = slide("The problem");
  title(s, "The problem", "Logs hold the answers, but nobody can read them", "Three people ask about the same logs. Today each of them works by hand.");
  const pains = [
    [fa.FaWrench, "Engineer", "What failed, and what happened just before?", "Greps across millions of lines while the system is down, then pieces the timeline together by hand."],
    [fa.FaUsers, "Team lead", "What keeps coming back, and whose is it?", "Counts in spreadsheets. One noisy storm looks like a thousand incidents."],
    [fa.FaChartLine, "Manager", "What do we fix first?", "Priorities set by whoever is loudest, not by measured frequency, spread and trend."],
  ];
  for (let i = 0; i < 3; i++) {
    const [ic, r, q, d] = pains[i], x = 0.5 + i * 3.05;
    card(s, x, 1.65, 2.85, 2.55);
    await dot(s, ic, x + 0.25, 1.88);
    s.addText(r, { x: x + 0.9, y: 1.9, w: 1.8, h: 0.45, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(`“${q}”`, { x: x + 0.25, y: 2.55, w: 2.4, h: 0.6, fontSize: 12, italic: true, fontFace: BODY, color: DEEP, margin: 0, valign: "top" });
    s.addText(d, { x: x + 0.25, y: 3.2, w: 2.4, h: 0.9, fontSize: 11, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  card(s, 0.5, 4.35, 9, 0.62, PALE);
  s.addText([{ text: "Why an AI chatbot alone does not fix it: ", options: { bold: true, color: DEEP } },
    { text: "4.7 M lines do not fit in a prompt, and a model that guesses numbers is worse than no answer." }],
    { x: 0.7, y: 4.38, w: 8.6, h: 0.56, fontSize: 12, fontFace: BODY, color: INK, margin: 0, valign: "middle" });
  s.addNotes("0:15–0:40. The client's problem. Three people, three questions, the same logs. Engineers grep, team leads count in spreadsheets, managers decide by gut. And you cannot just hand the logs to an AI: millions of lines do not fit, and a model that makes up numbers is dangerous.");

  // ───────────── 3 · the problem in numbers
  s = slide("The problem");
  title(s, "The problem", "Raw logs mislead, even when you can read them", "Measured on the brief's BGL supercomputer logs.");
  const traps = [
    ["855,501", "FATAL lines", "but only 36,714 bursts of recurring problems over all 4.7 M lines. Lines are not incidents."],
    ["1 / 10", "real alerts", "in the top 10 when you rank by log level. The loudest messages are routine register dumps."],
    ["69.6 %", "claims correct", "when plain Claude Code greps the raw files itself (pilot, 3 questions). With our server: 94.3 %."],
  ];
  traps.forEach(([n, u, d], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.7, 2.85, 2.9, WHITE, LINE);
    s.addText(n, { x: x + 0.25, y: 1.95, w: 2.4, h: 0.65, fontSize: 34, bold: true, fontFace: HEAD, color: i === 2 ? WARN : INK, margin: 0 });
    s.addText(u, { x: x + 0.25, y: 2.6, w: 2.4, h: 0.3, fontSize: 13, bold: true, fontFace: BODY, color: VIOLET, margin: 0 });
    s.addText(d, { x: x + 0.25, y: 3.0, w: 2.4, h: 1.45, fontSize: 11.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  });
  s.addNotes("0:40–1:00. Even when you can read them, raw logs mislead. BGL has 855 thousand FATAL lines but they come from a few thousand bursts. Rank by severity and only one of the top ten is a real alert. And when plain Claude Code greps the raw files itself, it got 70 percent of its claims right in our pilot.");

  // ───────────── 4 · the solution
  s = slide("The solution");
  title(s, "The solution", "The database counts, the AI explains", "A question goes in. Evidence comes from SereneDB. The answer is written for the role and checked.");
  const flow = [
    [fa.FaComments, "1 · Ask", "In plain words, in Claude Code (or any MCP client)."],
    [fa.FaPlug, "2 · Pick tools", "Claude chooses from 44 safe, fixed queries. It never writes SQL."],
    [fa.FaDatabase, "3 · SereneDB", "Searches and counts every line: full text, timelines, trends, rankings."],
    [fa.FaBalanceScale, "4 · Jev", "Already knows which kinds of messages are real faults."],
    [fa.FaCheckDouble, "5 · Answer", "Facts, a labelled hypothesis, unknowns and a next step. Every number is linked to its query."],
  ];
  for (let i = 0; i < 5; i++) {
    const [ic, h, d] = flow[i], x = 0.5 + i * 1.83;
    card(s, x, 1.7, 1.68, 2.55, i === 4 ? PALE : MIST);
    await dot(s, ic, x + 0.2, 1.9, 0.48);
    s.addText(h, { x: x + 0.2, y: 2.5, w: 1.4, h: 0.35, fontSize: 13, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.2, y: 2.88, w: 1.36, h: 1.3, fontSize: 10.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
    if (i < 4) s.addText("›", { x: x + 1.64, y: 2.6, w: 0.22, h: 0.4, fontSize: 22, bold: true, color: VIOLET, fontFace: HEAD, margin: 0, align: "center" });
  }
  s.addText([{ text: "Setup: ", options: { bold: true, color: INK } }, { text: "docker compose up -d  ·  claude  ·  “Load the base corpus”", options: { fontFace: MONO, color: DEEP } },
    { text: "  →  5 M lines ready in 72 s.", options: { color: INK2 } }], { x: 0.5, y: 4.45, w: 9, h: 0.4, fontSize: 12, fontFace: BODY, margin: 0 });
  s.addNotes("1:00–1:20. Our solution splits the work. The database does what databases are good at: searching and counting every line. Jev already knows which kinds of messages are real faults. Claude only picks tools and explains. Setup is two commands and one sentence.");

  // ───────────── 5 · one problem, three answers
  s = slide("The solution");
  title(s, "Demo", "One problem, three different answers", "BGL supercomputer, November 2005: the top-ranked problem, seen by each role.");
  const roles = [
    ["Engineer", "What failed, before and after?", ["New fault “Link has been severed”: 12,996 lines on 1,024 nodes", "First burst hit 504 nodes in 4 minutes; 21 minutes earlier, 64 job launches failed", "Every line points to one host: 172.16.96.116"], "Next check: that host's log, 05:30–05:40"],
    ["Team lead", "What recurs, and whose is it?", ["451 problem bursts: node-platform 283, hpc-workloads 106, cluster-control 62", "The new fault: 31 bursts; its owner is disputed between two teams", "Weekly problem bursts 69.6 → 119.3"], "Next step: both teams triage it together"],
    ["Manager", "What do we fix first?", ["Computed rank 1: the new fault (score 97.8)", "Ranks 2 and 3: two kernel faults (93.6, 90.5)", "hpc-workloads: 9 → 106 bursts vs the month before"], "Decision: name one owner now. Cost and downtime are not in the logs."],
  ];
  roles.forEach(([r, q, facts, nx], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.62, 2.85, 3.38, WHITE, LINE);
    s.addImage({ data: GRAD_BAR, x: x + 0.25, y: 1.8, w: 0.6, h: 0.06 });
    s.addText(r, { x: x + 0.25, y: 1.92, w: 2.4, h: 0.35, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(q, { x: x + 0.25, y: 2.25, w: 2.4, h: 0.28, fontSize: 10.5, italic: true, fontFace: BODY, color: MUTED, margin: 0 });
    s.addText(bullets(facts), { x: x + 0.2, y: 2.58, w: 2.5, h: 1.6, fontSize: 10, fontFace: BODY, color: INK2, valign: "top", paraSpaceAfter: 3, margin: 0 });
    card(s, x + 0.15, 4.25, 2.55, 0.6, PALE);
    s.addText(nx, { x: x + 0.25, y: 4.27, w: 2.35, h: 0.56, fontSize: 10, bold: true, fontFace: BODY, color: DEEP, margin: 0, valign: "middle" });
  });
  s.addNotes("1:20–2:10 LIVE DEMO in Claude Code: /mcp__logs__worked_investigation with topic 'what deserves attention in November 2005'. The same problem, but each role gets different evidence: the engineer one occurrence and what happened around it, the lead recurrence by team with a disputed owner, the manager a computed ranking and a decision. Not one answer at three lengths. Backup: docs/investigation/report.html.");

  // ───────────── 6 · more accurate
  s = slide("The solution");
  title(s, "Why it is more accurate", "Numbers come from the database, not the model");
  const acc = [
    [fa.FaLink, "Every number traced", "62 of 62 numbers in the worked investigation are found in a tool result. A Verify button re-runs each query: 17 of 17 give the same result."],
    [fa.FaLayerGroup, "Bursts, not lines", "Tools count recurrences and affected nodes, so a storm of 12,996 lines reads as 31 bursts, not 12,996 incidents."],
    [fa.FaBalanceScale, "Real faults first", "Jev's judgment per kind of message lifts real alerts in the top 10 from 1 to 5."],
    [fa.FaClipboardCheck, "Facts vs guesses", "Facts, a labelled hypothesis, what the logs do not show, and a next step, every time."],
  ];
  for (let i = 0; i < 4; i++) {
    const [ic, h, d] = acc[i], x = 0.5 + (i % 2) * 2.85, y = 1.35 + Math.floor(i / 2) * 1.85;
    card(s, x, y, 2.7, 1.7);
    await dot(s, ic, x + 0.2, y + 0.2, 0.42);
    s.addText(h, { x: x + 0.75, y: y + 0.2, w: 1.85, h: 0.42, fontSize: 12.5, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(d, { x: x + 0.2, y: y + 0.72, w: 2.35, h: 0.95, fontSize: 10, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  card(s, 6.35, 1.35, 3.15, 3.55, PALE);
  s.addText("Measured on 50 golden questions", { x: 6.55, y: 1.5, w: 2.8, h: 0.3, fontSize: 11, bold: true, fontFace: BODY, color: DEEP, margin: 0 });
  big(s, "13 – 2", "wins vs the brief's reference agent on BGL + OpenStack (blind Opus judge)", 6.55, 1.85, 2.8);
  big(s, "53 vs 69", "wrong claims over 50 answers, checked against frozen answer keys", 6.55, 3.05, 2.8);
  s.addText("Full results: docs/dashboard.html", { x: 6.55, y: 4.4, w: 2.8, h: 0.3, fontSize: 9.5, fontFace: BODY, color: MUTED, margin: 0 });
  s.addNotes("2:10–2:35. Why it is more accurate: numbers come from the database. Every number traces to a query, and Verify re-runs it. We count bursts, not lines. Jev pushes real faults to the top. On 50 questions with known answers, a blind judge preferred us 13 to 2 on the brief's data, with fewer wrong claims.");

  // ───────────── 7 · faster
  s = slide("The solution");
  title(s, "Why it is faster", "The database does the reading", "Claude reads a few results instead of grepping millions of lines.");
  card(s, 0.5, 1.65, 4.4, 3.3, WHITE, LINE);
  s.addText("Claude Code, same model, same questions (pilot, 3 questions)", { x: 0.7, y: 1.8, w: 4.0, h: 0.3, fontSize: 11, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addChart(pres.charts.BAR, [{ name: "seconds per answer", labels: ["With our MCP server", "Plain, grepping raw files"], values: [13.0, 70.9] }],
    { x: 0.6, y: 2.15, w: 4.2, h: 1.8, barDir: "bar", chartColors: [VIOLET], valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      showValue: true, dataLabelFormatCode: '0.0 "s"', dataLabelColor: INK, dataLabelFontSize: 12, catAxisLabelColor: INK2, catAxisLabelFontSize: 11,
      catAxisLineShow: false, barGapWidthPct: 60, catAxisOrientation: "maxMin" });
  s.addText("Mean seconds per answer.\nClaims correct: 94.3 % vs 69.6 %.", { x: 0.7, y: 4.05, w: 4.0, h: 0.75, fontSize: 11, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  big(s, "1.8 s", "of database time for all 20 tool calls of the worked investigation", 5.2, 1.65, 4.3);
  big(s, "7 ms", "to count 121,498 full-text matches over 4.7 M lines (inverted index, no scan)", 5.2, 2.75, 4.3);
  big(s, "~90 %", "of an answer's time is the AI writing; SereneDB is under 1 s per answer", 5.2, 3.85, 4.3);
  s.addNotes("2:35–2:55. Why it is faster: the database does the reading. In our pilot, Claude Code with our server answered in 13 seconds on average; plain Claude Code grepping the raw files took 71, and got more wrong. The whole investigation spent 1.8 seconds in the database. Most of the time is the AI writing.");

  // ───────────── 8 · fits the company
  s = slide("In the company");
  title(s, "How it fits the company", "It plugs into routines that already exist");
  const fit = [
    [fa.FaBell, "On-call incident", "The engineer asks during the outage and gets the failure, its neighbours and a next check in about 13–44 s, instead of a manual search."],
    [fa.FaCalendarWeek, "Weekly team review", "The lead opens recurring problems by team and trend for a stated period, ready for the meeting."],
    [fa.FaChessKing, "Monthly planning", "The manager gets a computed ranking with owners and a decision. It never invents cost or downtime."],
  ];
  for (let i = 0; i < 3; i++) {
    const [ic, h, d] = fit[i], x = 0.5 + i * 3.05;
    card(s, x, 1.35, 2.85, 1.95);
    await dot(s, ic, x + 0.22, 1.55, 0.44);
    s.addText(h, { x: x + 0.8, y: 1.55, w: 1.95, h: 0.44, fontSize: 13, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(d, { x: x + 0.22, y: 2.1, w: 2.45, h: 1.15, fontSize: 10.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  const integ = [["Tools they already use", "Claude Code, Claude Desktop or any MCP client."], ["Their data stays home", "SereneDB runs locally in Docker; only tool results reach the AI."],
    ["Their own logs", "Any file; the format is detected from 76 known formats in seconds."], ["Their org chart", "An ownership table maps components to teams; access per team is enforced by the database."]];
  integ.forEach(([h, d], i) => {
    const x = 0.5 + (i % 2) * 4.55, y = 3.5 + Math.floor(i / 2) * 0.75;
    card(s, x, y, 4.45, 0.65, WHITE, LINE);
    s.addText([{ text: h + "  ", options: { bold: true, color: DEEP } }, { text: d, options: { color: INK2 } }],
      { x: x + 0.2, y, w: 4.1, h: 0.65, fontSize: 10.5, fontFace: BODY, margin: 0, valign: "middle" });
  });
  s.addNotes("2:55–3:15. It fits three routines a company already has: the incident, the weekly review, the monthly planning. It uses the tools people have, keeps the logs on their machine, reads their own log formats, and maps problems to their teams, with access per team enforced by the database itself.");

  // ───────────── 9 · cheaper: Jev
  s = slide("Cost");
  title(s, "Cheaper than the alternatives", "Judge each kind of message once, not every line", "Jev is a small model that gives typed, calibrated judgments. It runs inside SereneDB with one SQL call.");
  card(s, 0.5, 1.7, 4.4, 3.25, WHITE, LINE);
  s.addText("Reading BGL once with an LLM", { x: 0.7, y: 1.85, w: 4.0, h: 0.3, fontSize: 12, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addText("≈ 177 M", { x: 0.7, y: 2.2, w: 4.0, h: 0.6, fontSize: 32, bold: true, fontFace: HEAD, color: WARN, margin: 0 });
  s.addText("input tokens (709 MB ÷ ~4 bytes per token, an estimate), and again for every new question or new day of logs.", { x: 0.7, y: 2.8, w: 4.0, h: 0.75, fontSize: 11, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  s.addText("Jev on the 1,126 kinds of message", { x: 0.7, y: 3.6, w: 4.0, h: 0.3, fontSize: 12, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addText([{ text: "≈ 0.5 M tokens · 20 s · ≈ $0.02", options: { bold: true, color: OK } }, { text: "  once, stored, reused by every answer", options: { color: INK2 } }],
    { x: 0.7, y: 3.92, w: 4.0, h: 0.6, fontSize: 12, fontFace: BODY, margin: 0, valign: "top" });
  const why = [
    ["Measured, not decorative", "Real alerts in the priority top 10: 1 → 5 after Jev's judgment."],
    ["No model at question time", "Tools read the stored judgments, so answering needs no extra classification calls."],
    ["Probabilities, not vibes", "Each judgment and each fact's support is a calibrated probability, never self-reported confidence."],
    ["Pennies per answer", "Claude Code + our server: about $0.07 per answer in the pilot."],
  ];
  why.forEach(([h, d], i) => {
    const y = 1.7 + i * 0.83;
    card(s, 5.2, y, 4.3, 0.73, i % 2 ? MIST : PALE);
    s.addText([{ text: h, options: { bold: true, color: DEEP, breakLine: true } }, { text: d, options: { color: INK2 } }],
      { x: 5.4, y, w: 3.95, h: 0.73, fontSize: 10.5, fontFace: BODY, margin: 0, valign: "middle" });
  });
  s.addNotes("3:15–3:35. Why it is cheaper. Reading all of BGL with a large model is around 177 million tokens, every time. Jev judges each kind of message once: 1,126 patterns in 20 seconds for about two cents, stored in the database and reused by every answer. That one step moved real alerts in the top ten from one to five.");

  // ───────────── 10 · performance: SereneDB
  s = slide("Performance");
  title(s, "Performance", "Built on SereneDB's search-analytics engine", "Every feature below is used by a tool, and every number is measured on the base corpus.");
  const perf = [
    ["Inverted index + BM25", "full-text, phrase, fuzzy, top-k", "7 ms", "count over 4.7 M lines"],
    ["Counts from the term dictionary", "group-bys without scanning rows", "3–39 ms", "whole-corpus breakdowns"],
    ["SQL-native load", "read_csv + regex parse inside SereneDB", "18 s", "4.7 M BGL lines loaded"],
    ["ASOF join · ROLLUP · PIVOT", "precursors, subtotals, team × week", "< 100 ms", "per analytics tool"],
    ["Remote Parquet over S3", "row-group pruning, read in place", "2.8 s", "10 of 1,624 row groups"],
    ["On-demand index", "index a remote slice, search it", "0.94 ms", "vs 281 ms scan; pays off after 4 searches"],
  ];
  perf.forEach(([f, d, n, l], i) => {
    const x = 0.5 + (i % 2) * 4.55, y = 1.65 + Math.floor(i / 2) * 1.1;
    card(s, x, y, 4.45, 0.98, i % 2 ? MIST : WHITE, i % 2 ? undefined : LINE);
    s.addText([{ text: f, options: { bold: true, color: INK, breakLine: true } }, { text: d, options: { color: MUTED } }],
      { x: x + 0.2, y, w: 2.45, h: 0.98, fontSize: 10.5, fontFace: BODY, margin: 0, valign: "middle" });
    s.addText([{ text: n, options: { bold: true, fontSize: 20, color: VIOLET, breakLine: true } }, { text: l, options: { fontSize: 9, color: INK2 } }],
      { x: x + 2.7, y, w: 1.65, h: 0.98, fontFace: HEAD, margin: 0, valign: "middle" });
  });
  s.addNotes("3:35–3:55. Performance comes from SereneDB's engine. The inverted index counts a full-text search over 4.7 million lines in 7 milliseconds, and group-bys come straight from the index without scanning rows. Data loads inside the database. Timelines use ASOF joins, rankings use ROLLUP and PIVOT. Remote Parquet on S3 is read in place, and an on-demand index pays for itself after four searches.");

  // ───────────── 11 · MCP overview (technical)
  s = slide("Technical · MCP");
  title(s, "Technical · MCP", "One MCP server, four ways to use it", "MCP is how Claude discovers and calls our functions. Ours offers all four kinds of MCP features.");
  const surf = [
    [fa.FaTools, "44 tools", "Search, count, timelines, patterns, priorities, ownership and setup. Claude picks them from their descriptions.", "Just ask in plain words"],
    [fa.FaTerminal, "5 prompts", "Ready-made playbooks: one per role, a three-role investigation and whole-corpus counts.", "/mcp__logs__set_priorities"],
    [fa.FaFolderOpen, "6 resources", "Read-only context: datasets, glossary, field guide, ownership and the session's full evidence.", "@logs:logs://ownership/bgl"],
    [fa.FaMagic, "Completions", "Prompt arguments complete with real values from the data: datasets, components, teams.", "Tab inside a prompt argument"],
  ];
  for (let i = 0; i < 4; i++) {
    const [ic, h, d, how] = surf[i], x = 0.5 + (i % 2) * 4.55, y = 1.6 + Math.floor(i / 2) * 1.75;
    card(s, x, y, 4.45, 1.6);
    await dot(s, ic, x + 0.22, y + 0.22, 0.5);
    s.addText(h, { x: x + 0.9, y: y + 0.22, w: 3.3, h: 0.5, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(d, { x: x + 0.22, y: y + 0.8, w: 4.05, h: 0.45, fontSize: 10.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
    s.addText(how, { x: x + 0.22, y: y + 1.25, w: 4.05, h: 0.28, fontSize: 10, fontFace: MONO, color: VIOLET, margin: 0 });
  }
  s.addNotes("3:55–4:05. Now the technical part. Our MCP server offers all four kinds of MCP features: tools, prompts, resources and completions.");

  // ───────────── 12 · MCP tools
  s = slide("Technical · MCP");
  title(s, "Technical · MCP tools", "44 tools, grouped by the question they answer", "Each description says when to use it, when not to, what it returns and which tool comes next.");
  const groups = [
    ["Set up", "setup_status · load_logs · use_dataset · remove_dataset", "Load my log file ~/app.log"],
    ["Find", "search_logs · get_context · find_patterns · suggest_terms · facet", "What failed on R43 at 13:56?"],
    ["Count", "count_by · trend · facet · rollup · heatmap · rate_vs_baseline", "Errors per team, week over week?"],
    ["Recurring", "top_patterns · pattern_history · whats_new · spread · periodicity", "What keeps coming back?"],
    ["Explain", "burst_timeline · precursors · request_timeline · value_outliers", "What happens just before it?"],
    ["Decide", "priority_table · reliability_trend · team_risk · owner_of", "What first, and who owns it?"],
    ["Workspace", "create_focus_index · index_stats · explain_tool · session_report", "Index this week for a deep dive"],
  ];
  groups.forEach(([g, t, q], i) => {
    const y = 1.6 + i * 0.47;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 1.25, h: 0.38, rectRadius: 0.19, fill: { color: i % 2 ? PALE2 : PALE } });
    s.addText(g, { x: 0.5, y, w: 1.25, h: 0.38, fontSize: 10.5, bold: true, fontFace: BODY, color: DEEP, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: 1.9, y, w: 5.55, h: 0.38, fontSize: 8.5, fontFace: MONO, color: INK2, valign: "middle", margin: 0 });
    s.addText(q, { x: 7.5, y, w: 2.0, h: 0.38, fontSize: 9.5, italic: true, fontFace: BODY, color: MUTED, valign: "middle", margin: 0 });
  });
  s.addText("Every result: the SQL that ran, filters, scope, the exact total, and a flag when rows were cut to 50.  Reference: docs/TOOLS.md",
    { x: 0.5, y: 4.9, w: 9, h: 0.22, fontSize: 9.5, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addNotes("4:05–4:15. Forty-four tools grouped by the question they answer. You never name a tool; Claude picks it. Every result carries its SQL, scope, exact total and a truncation flag.");

  // ───────────── 13 · prompts + resources
  s = slide("Technical · MCP");
  title(s, "Technical · prompts, resources, completions", "How to use them in Claude Code");
  card(s, 0.5, 1.3, 4.4, 3.65);
  s.addText("Prompts: type /", { x: 0.7, y: 1.42, w: 4, h: 0.32, fontSize: 13, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  [["/mcp__logs__investigate_failure", "engineer playbook"], ["/mcp__logs__review_recurring_problems", "team-lead playbook"], ["/mcp__logs__set_priorities", "manager playbook"],
    ["/mcp__logs__worked_investigation", "one topic, all three roles"], ["/mcp__logs__whole_corpus_counts", "counts over every dataset"]].forEach(([c, d], i) => {
    s.addText(c, { x: 0.7, y: 1.85 + i * 0.6, w: 4.1, h: 0.26, fontSize: 9.5, fontFace: MONO, color: VIOLET, margin: 0 });
    s.addText(d, { x: 0.7, y: 2.1 + i * 0.6, w: 4.1, h: 0.24, fontSize: 10, fontFace: BODY, color: INK2, margin: 0 });
  });
  card(s, 5.1, 1.3, 4.4, 2.75);
  s.addText("Resources: type @", { x: 5.3, y: 1.42, w: 4, h: 0.32, fontSize: 13, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  [["logs://datasets", "what is loaded"], ["logs://glossary", "line, pattern, burst; the rules"], ["logs://field-guide/{dataset}", "what each field means"],
    ["logs://ownership/{dataset}", "component → team"], ["logs://session/latest", "every query so far"], ["logs://session/{id}/step/{n}", "one step in full"]].forEach(([c, d], i) => {
    s.addText(c, { x: 5.3, y: 1.82 + i * 0.36, w: 2.45, h: 0.32, fontSize: 9.5, fontFace: MONO, color: VIOLET, margin: 0, valign: "middle" });
    s.addText(d, { x: 7.75, y: 1.82 + i * 0.36, w: 1.65, h: 0.32, fontSize: 9.5, fontFace: BODY, color: INK2, margin: 0, valign: "middle" });
  });
  card(s, 5.1, 4.2, 4.4, 0.75, PALE);
  s.addText([{ text: "Completions  ", options: { bold: true, color: DEEP } }, { text: "Prompt arguments suggest real datasets, components, teams and levels as you type.", options: { color: INK2 } }],
    { x: 5.3, y: 4.2, w: 4.05, h: 0.75, fontSize: 10.5, fontFace: BODY, margin: 0, valign: "middle" });
  s.addNotes("4:15–4:25. Prompts are slash commands: one per role, plus a three-role investigation and the whole-corpus counts the brief asks for. Resources attach context with @, including the full evidence of the session beyond the 50-row tool limit.");

  // ───────────── 14 · connect, load, restrict, verify
  s = slide("Technical · MCP");
  title(s, "Technical · setup and control", "Connect, load, restrict, verify");
  const ctl = [
    [fa.FaLink, "Connect", "In the repo, run claude (it reads .mcp.json). From anywhere: claude mcp add -s user logs -- uv run … python mcp_server/server.py"],
    [fa.FaFileImport, "Load", "load_logs('base') = BGL + OpenStack from the brief's Zenodo links in 72 s. load_logs('~/app.log') detects the format from 76 known ones and refuses below 95 % match."],
    [fa.FaUserLock, "Restrict", "LOGS_DB_ROLE=team_<team>: the database shows a team only its own components. logs_manager is read-only."],
    [fa.FaCheckDouble, "Verify", "session_report gives a local page: the answer, each number linked to its query, and a Verify button that re-runs each step read-only."],
  ];
  for (let i = 0; i < 4; i++) {
    const [ic, h, d] = ctl[i], y = 1.3 + i * 0.92;
    card(s, 0.5, y, 9, 0.8, i % 2 ? WHITE : MIST, i % 2 ? LINE : undefined);
    await dot(s, ic, 0.68, y + 0.17, 0.46);
    s.addText(h, { x: 1.3, y, w: 1.3, h: 0.8, fontSize: 14, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(d, { x: 2.6, y, w: 6.75, h: 0.8, fontSize: 10.5, fontFace: BODY, color: INK2, margin: 0, valign: "middle" });
  }
  s.addNotes("4:25–4:35. Connecting is one line. Loading works for the base corpus and for any log file. Access can be limited per team by the database itself, not by the prompt. And every session can be verified.");

  // ───────────── 15 · wow: beyond the brief
  s = slide("Wow");
  title(s, "Wow", "Beyond what the brief asked for");
  const wow = [
    [fa.FaFileAlt, "Bring your own logs", "Any file, format detected, loaded in seconds (21 k lines in 1.6 s). 10 Loghub datasets, no code change."],
    [fa.FaCheckDouble, "A Verify button", "Re-runs the query behind every number on a read-only connection."],
    [fa.FaBrain, "Judged once, reused", "Jev labels each kind of message inside the database; nothing re-reads raw lines."],
    [fa.FaCloud, "1 billion remote rows", "OpenTelemetry Parquet on S3, queried in place: no download."],
    [fa.FaUserShield, "Access per team", "Enforced by database roles and views, not by the prompt."],
    [fa.FaFlask, "Our own blind evaluation", "50 answer keys built from raw SQL and labels, an Opus judge, both answer orders."],
  ];
  for (let i = 0; i < 6; i++) {
    const [ic, h, d] = wow[i], x = 0.5 + (i % 3) * 3.05, y = 1.3 + Math.floor(i / 3) * 1.85;
    card(s, x, y, 2.85, 1.7, i % 2 ? PALE : MIST);
    await dot(s, ic, x + 0.22, y + 0.22, 0.46);
    s.addText(h, { x: x + 0.22, y: y + 0.78, w: 2.45, h: 0.3, fontSize: 12.5, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.22, y: y + 1.1, w: 2.45, h: 0.55, fontSize: 9.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  s.addNotes("4:35–4:45. What goes beyond the brief: your own log files with no code, a Verify button on every number, judgments computed once inside the database, a billion rows read in place, team access enforced by the database, and an evaluation the client can re-run themselves.");

  // ───────────── 16 · wow: the evidence page
  s = slide("Wow");
  title(s, "Wow", "Every answer comes with its proof");
  const rep = await rounded(path.join(IMG, "report.png")), dash = await rounded(path.join(IMG, "dashboard.png"));
  const H = 3.0;
  [[rep, "Session report", "each number links to the query behind it; Verify re-runs it."],
   [dash, "Eval dashboard", "50 questions, both answers, the judge's reasons, how to re-run."]].forEach(([im, h, d], i) => {
    const x = 0.5 + i * 4.6, w = Math.min(4.4, H * im.ratio), hh = w / im.ratio;
    card(s, x, 1.3, 4.4, 3.75, MIST);
    s.addImage({ data: im.data, x: x + (4.4 - w) / 2, y: 1.42, w, h: Math.min(hh, H) });
    s.addText([{ text: h + "  ", options: { bold: true, color: INK } }, { text: d, options: { color: INK2 } }],
      { x: x + 0.2, y: 4.5, w: 4.0, h: 0.5, fontSize: 10.5, fontFace: BODY, margin: 0, valign: "middle" });
  });
  s.addNotes("4:45–4:50. Every answer comes with its proof: the session report on the left, the evaluation dashboard on the right. Both open offline from the repo.");

  // ───────────── 17 · scale
  s = slide("Scale");
  title(s, "Scale", "Where it goes next");
  const nx = [
    [fa.FaIndustry, "Mittelstand", "Machine and production logs, IT operations, managed service providers: the same tools on their files."],
    [fa.FaBuilding, "Other industries", "Any system that writes logs: cloud, telecom, devices, security. SSH brute-force logs are already in our eval."],
    [fa.FaBoxOpen, "A product", "A self-hosted log copilot: MCP server + SereneDB in one container, team access, alerts from saved searches."],
  ];
  for (let i = 0; i < 3; i++) {
    const [ic, h, d] = nx[i], x = 0.5 + i * 3.05;
    card(s, x, 1.3, 2.85, 2.1);
    await dot(s, ic, x + 0.22, 1.5, 0.5);
    s.addText(h, { x: x + 0.22, y: 2.1, w: 2.45, h: 0.35, fontSize: 15, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.22, y: 2.48, w: 2.45, h: 0.9, fontSize: 10.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  s.addImage({ data: await gcard(9, 1.35), x: 0.5, y: 3.6, w: 9, h: 1.35 });
  const sc = [["10", "log types loaded, 7 kinds of systems, no code change"], ["11.2 M", "HDFS lines loaded in 47 s"], ["1 B", "remote OTel rows, queried in place"]];
  sc.forEach(([n, l], i) => {
    s.addText(n, { x: 0.8 + i * 3.0, y: 3.72, w: 2.7, h: 0.55, fontSize: 28, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(l, { x: 0.8 + i * 3.0, y: 4.27, w: 2.6, h: 0.55, fontSize: 10.5, fontFace: BODY, color: "EDE7FF", margin: 0, valign: "top" });
  });
  s.addNotes("4:50–4:57. Nothing in the code is specific to one dataset: ten log types load without code changes, eleven million HDFS lines load in 47 seconds, and a billion remote rows are queried in place. That makes it a product: a self-hosted log copilot for the Mittelstand and beyond.");

  // ───────────── 18 · try it
  s = pres.addSlide(); s.background = { color: WHITE }; N++;
  s.addImage({ data: await gcard(9, 4.6), x: 0.5, y: 0.5, w: 9, h: 4.6 });
  s.addText("Try it in two commands", { x: 1.0, y: 0.9, w: 8, h: 0.7, fontSize: 32, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.0, y: 1.8, w: 8, h: 1.25, rectRadius: R, fill: { color: WHITE, transparency: 88 }, line: { type: "none" } });
  s.addText("docker compose up -d\nclaude          # in the repo, approve the logs server\n> Load the base corpus",
    { x: 1.25, y: 1.85, w: 7.6, h: 1.15, fontSize: 14, fontFace: MONO, color: WHITE, margin: 0, valign: "middle" });
  s.addText(bullets(["docs/INVESTIGATION.md: the worked investigation and its evidence page", "docs/dashboard.html: the evaluation, every answer, how to re-run it", "docs/TOOLS.md: every tool, prompt and resource"], { color: WHITE }),
    { x: 1.0, y: 3.25, w: 8, h: 1.05, fontSize: 13, fontFace: BODY, margin: 0, paraSpaceAfter: 4 });
  s.addText("github.com/aircode610/making-sense-of-logs-schubki-ai-hackathon", { x: 1.0, y: 4.45, w: 8, h: 0.35, fontSize: 12, bold: true, fontFace: BODY, color: "EDE7FF", margin: 0 });
  s.addNotes("4:57–5:00. Two commands and one sentence, and your logs answer back. Thank you.");

  await pres.writeFile({ fileName: path.join(DIR, "making-sense-of-logs.pptx") });
  console.log(`wrote docs/slides/making-sense-of-logs.pptx (${N} slides)`);
})();
