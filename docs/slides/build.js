// Slides (final branch): node docs/slides/build.js → docs/slides/making-sense-of-logs.pptx
// SereneDB look (geometric sans, ink #11121D, mist #F0F2F5, violet gradient #A162F0 → #3E318C), light, rounded cards.
// Minimal text: a title + a few labels and numbers per slide; the speaker notes carry the explanation.
// Flow: problem → solution → accurate / fast → company → cheaper (Jev) → loading → performance (SereneDB) → MCP → wow
// → scale → try it. Numbers from committed results: docs/INVESTIGATION.md, eval/results/ab-20261018-193248.md,
// eval/results/cc-20261018-205503.md (Claude Code + MCP vs plain Claude Code, 50 questions), plans/006, docs/PERFORMANCE.md, README.
// Preview with LibreOffice-visible fonts: SLIDE_FONT=Arial SLIDE_MONO="Liberation Mono" node docs/slides/build.js
const path = require("path");
const G = require("child_process").execSync("npm root -g").toString().trim();
const req = m => require(require.resolve(m, { paths: [G] }));
const pptxgen = req("pptxgenjs"), React = req("react"), RDS = req("react-dom/server"), sharp = req("sharp");
const fa = req("react-icons/fa");

const INK = "11121D", INK2 = "3A3F55", MUTED = "6B7386", MIST = "F0F2F5", LINE = "E3E6EC", WHITE = "FFFFFF";
const VIOLET = "6A4BD8", DEEP = "3E318C", BRAND_A = "A162F0", PALE = "F1ECFD", WARN = "C2410C", OK = "15803D";
const FONT = process.env.SLIDE_FONT || "Avenir Next";
const HEAD = FONT, BODY = FONT, MONO = process.env.SLIDE_MONO || "Menlo";
const DIR = __dirname, IMG = path.join(DIR, "img"), OUT = process.env.SLIDE_OUT || path.join(DIR, "making-sense-of-logs.pptx");
const R = 0.14;                                   // corner radius (inches) of every card

async function icon(Comp, color, size = 256) {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
async function gradient(w, h, rx = 0) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#${BRAND_A}"/><stop offset="1" stop-color="#${DEEP}"/></linearGradient></defs>
    <rect width="${w}" height="${h}" rx="${rx}" ry="${rx}" fill="url(#g)"/></svg>`;
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
async function rounded(file, rx = 28) {
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
  const GRAD_SQ = await gradient(200, 200, 50);
  const gcard = (w, h) => gradient(Math.round(w * 200), Math.round(h * 200), Math.round(R * 200 * 1.4));
  let N = 0;

  const card = (s, x, y, w, h, fill = MIST, line) => s.addShape(pres.shapes.ROUNDED_RECTANGLE,
    { x, y, w, h, rectRadius: R, fill: { color: fill }, line: line ? { color: line, width: 1 } : { type: "none" } });
  const slide = section => {
    const s = pres.addSlide(); s.background = { color: WHITE }; N++;
    s.addImage({ data: GRAD_SQ, x: 0.5, y: 5.18, w: 0.16, h: 0.16 });
    s.addText("Making Sense of Logs  ·  " + section, { x: 0.74, y: 5.14, w: 6, h: 0.25, fontSize: 9, fontFace: BODY, color: MUTED, margin: 0 });
    s.addText(String(N), { x: 8.5, y: 5.14, w: 1, h: 0.25, fontSize: 9, fontFace: BODY, color: MUTED, align: "right", margin: 0 });
    return s;
  };
  const title = (s, kicker, t) => {
    s.addText(kicker.toUpperCase(), { x: 0.5, y: 0.35, w: 9, h: 0.25, fontSize: 10, bold: true, charSpacing: 3, fontFace: BODY, color: VIOLET, margin: 0 });
    s.addText(t, { x: 0.5, y: 0.62, w: 9, h: 0.65, fontSize: 28, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  };
  const dot = async (s, ic, x, y, d = 0.55) => {
    s.addImage({ data: GRAD_SQ, x, y, w: d, h: d });
    s.addImage({ data: await icon(ic, WHITE), x: x + d * 0.26, y: y + d * 0.26, w: d * 0.48, h: d * 0.48 });
  };
  // a row of n cards: icon, heading, one short line
  const tiles = async (s, items, y = 1.6, h = 2.6, fills) => {
    const n = items.length, gap = 0.2, w = (9 - gap * (n - 1)) / n;
    for (let i = 0; i < n; i++) {
      const [ic, head, line] = items[i], x = 0.5 + i * (w + gap);
      card(s, x, y, w, h, fills ? fills[i] : MIST);
      await dot(s, ic, x + 0.28, y + 0.3);
      s.addText(head, { x: x + 0.28, y: y + 1.05, w: w - 0.5, h: 0.45, fontSize: n > 4 ? 13 : 16, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "top" });
      if (line) s.addText(line, { x: x + 0.28, y: y + 1.5, w: w - 0.5, h: h - 1.65, fontSize: n > 4 ? 11 : 13, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
    }
  };
  // a row of big numbers
  const stats = (s, items, y = 1.7, h = 2.3, fill = WHITE) => {
    const n = items.length, gap = 0.2, w = (9 - gap * (n - 1)) / n;
    items.forEach(([num, label, color], i) => {
      const x = 0.5 + i * (w + gap);
      card(s, x, y, w, h, fill, fill === WHITE ? LINE : undefined);
      s.addText(num, { x: x + 0.3, y: y + 0.35, w: w - 0.5, h: 0.8, fontSize: n > 3 ? 30 : 38, bold: true, fontFace: HEAD, color: color || VIOLET, margin: 0 });
      s.addText(label, { x: x + 0.3, y: y + 1.2, w: w - 0.5, h: h - 1.35, fontSize: 13, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
    });
  };

  // 1 · title
  let s = pres.addSlide(); s.background = { color: WHITE }; N++;
  s.addImage({ data: await gcard(3.4, 4.6), x: 6.1, y: 0.5, w: 3.4, h: 4.6 });
  [["5 M", "log lines"], ["3", "roles"], ["2", "commands to set up"]].forEach(([n, l], i) => {
    s.addText(n, { x: 6.45, y: 0.95 + i * 1.35, w: 2.8, h: 0.65, fontSize: 36, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(l, { x: 6.45, y: 1.58 + i * 1.35, w: 2.8, h: 0.35, fontSize: 13, fontFace: BODY, color: "EDE7FF", margin: 0 });
  });
  s.addImage({ data: GRAD_SQ, x: 0.5, y: 0.65, w: 0.42, h: 0.42 });
  s.addText("SereneDB challenge · SchubKI Hackathon 2026", { x: 1.05, y: 0.67, w: 4.9, h: 0.38, fontSize: 11, fontFace: BODY, color: MUTED, margin: 0, valign: "middle" });
  s.addText("Making Sense\nof Logs", { x: 0.5, y: 1.45, w: 5.4, h: 1.5, fontSize: 40, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  s.addText("Ask your logs a question. Get the answer your role needs, with proof.", { x: 0.5, y: 3.05, w: 5.2, h: 0.8, fontSize: 16, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  s.addText("Amirali & Konark", { x: 0.5, y: 4.55, w: 5, h: 0.3, fontSize: 12, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addNotes("We built an assistant that answers questions about millions of log lines for three people who need different things: the engineer who fixes, the team lead who plans, the manager who decides. Every number it says can be checked.");

  // 2 · problem
  s = slide("Problem");
  title(s, "The problem", "Logs hold the answers. Nobody reads them.");
  await tiles(s, [[fa.FaWrench, "Engineer", "“What failed?”"], [fa.FaUsers, "Team lead", "“What keeps coming back?”"], [fa.FaChartLine, "Manager", "“What do we fix first?”"]], 1.6, 2.05);
  card(s, 0.5, 3.85, 9, 0.9, PALE);
  s.addText("Millions of lines don't fit in a prompt, and an AI that guesses numbers can't be trusted.",
    { x: 0.8, y: 3.85, w: 8.4, h: 0.9, fontSize: 15, bold: true, fontFace: BODY, color: DEEP, margin: 0, valign: "middle" });
  s.addNotes("Three people ask about the same logs. Engineers grep for hours during an outage, team leads count in spreadsheets, managers decide by gut. And you cannot just hand the logs to an AI: they don't fit, and a model that makes up numbers is dangerous.");

  // 3 · problem in numbers
  s = slide("Problem");
  title(s, "The problem", "Raw logs mislead");
  stats(s, [["855,501", "FATAL lines, but only 36,714 bursts of problems"], ["1 / 10", "real alerts in the top 10 when ranked by log level"], ["186", "wrong claims when Claude Code greps the raw files (50 questions)", WARN]]);
  s.addNotes("Even when you can read them, raw logs mislead. BGL has 855 thousand FATAL lines, but they come from far fewer recurring problems. Rank by severity and only one of the top ten is a real alert. And when plain Claude Code greps the raw files itself, a judge found 186 wrong claims over 50 answers.");

  // 4 · solution
  s = slide("Solution");
  title(s, "The solution", "The database counts, the AI explains");
  await tiles(s, [[fa.FaComments, "Ask", "in plain words"], [fa.FaDatabase, "SereneDB", "searches and counts every line"], [fa.FaBalanceScale, "Jev", "knows which messages are real faults"], [fa.FaCheckDouble, "Answer", "for your role, with proof"]],
    1.6, 2.4, [MIST, MIST, MIST, PALE]);
  s.addText("docker compose up -d   ·   claude   ·   “Load the base corpus”", { x: 0.5, y: 4.3, w: 9, h: 0.45, fontSize: 13, fontFace: MONO, color: DEEP, margin: 0, align: "center" });
  s.addNotes("Our solution splits the work. You ask in plain words. SereneDB searches and counts every line. Jev already knows which kinds of messages are real faults. Claude only picks the tools and writes the answer for your role, with every number linked to its query. Setup is two commands and one sentence.");

  // 5 · demo: one problem, three answers
  s = slide("Solution");
  title(s, "Demo", "One problem, three answers");
  const roles = [["Engineer", "1,024 nodes hit by a new fault", "Next: check host 172.16.96.116"], ["Team lead", "31 bursts, owner disputed", "Next: two teams triage together"], ["Manager", "Rank 1 of 133 problems", "Next: name one owner now"]];
  roles.forEach(([r, f, nx], i) => {
    const x = 0.5 + i * 3.07;
    card(s, x, 1.6, 2.87, 3.1, WHITE, LINE);
    s.addText(r, { x: x + 0.3, y: 1.85, w: 2.3, h: 0.45, fontSize: 18, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(f, { x: x + 0.3, y: 2.4, w: 2.3, h: 1.0, fontSize: 15, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
    card(s, x + 0.2, 3.75, 2.47, 0.75, PALE);
    s.addText(nx, { x: x + 0.35, y: 3.75, w: 2.2, h: 0.75, fontSize: 12.5, bold: true, fontFace: BODY, color: DEEP, margin: 0, valign: "middle" });
  });
  s.addNotes("LIVE DEMO in Claude Code: /mcp__logs__worked_investigation, topic 'what deserves attention in November 2005'. The top problem in BGL, November 2005, is a new fault: 'Link has been severed', 12,996 lines on 1,024 nodes. The engineer gets the first burst and what happened 21 minutes before; the lead gets 31 recurrences and an owner disputed between two teams; the manager gets rank 1 of 133 and a decision. Different evidence, not different lengths. Backup: docs/investigation/report.html.");

  // 6 · accurate + faster
  s = slide("Solution");
  title(s, "Why it's better", "More accurate and faster");
  stats(s, [["62 / 62", "numbers traced to a query"], ["30 – 15", "wins vs plain Claude Code (blind judge, 50 questions)"], ["14 s", "per answer, vs 86 s for plain Claude Code"]]);
  s.addNotes("More accurate: every number comes from the database. In the worked investigation, 62 of 62 numbers trace to a query, and Verify re-runs each one. On 50 questions with known answers, a blind judge preferred Claude Code with our server over plain Claude Code 30 to 15. Faster: 14 seconds per answer instead of 86.");

  // 6b · the headline comparison: Claude Code with vs without our server
  s = slide("Solution");
  title(s, "Measured", "Claude Code, with and without our server");
  card(s, 0.5, 1.55, 4.4, 3.4, WHITE, LINE);
  s.addText("Seconds per answer (mean)", { x: 0.8, y: 1.7, w: 3.9, h: 0.35, fontSize: 13, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addChart(pres.charts.BAR, [{ name: "s", labels: ["With our MCP", "Plain Claude Code"], values: [14.3, 86.0] }],
    { x: 0.6, y: 2.1, w: 4.2, h: 2.2, barDir: "bar", chartColors: [VIOLET], valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      showValue: true, dataLabelFormatCode: '0 "s"', dataLabelColor: INK, dataLabelFontSize: 14, catAxisLabelColor: INK2, catAxisLabelFontSize: 12,
      catAxisLineShow: false, barGapWidthPct: 50, catAxisOrientation: "maxMin" });
  s.addText("same model · same 50 questions · blind judge", { x: 0.8, y: 4.4, w: 3.9, h: 0.35, fontSize: 11, fontFace: BODY, color: MUTED, margin: 0 });
  [["30 – 15", "wins (18 – 4 on BGL + OpenStack)"], ["116 vs 186", "wrong claims"], ["0.64 vs 0.46", "golden facts found"]].forEach(([n, l], k) => {
    const y = 1.55 + k * 1.16;
    card(s, 5.1, y, 4.4, 1.04, k % 2 ? MIST : PALE);
    s.addText(n, { x: 5.4, y: y + 0.08, w: 3.9, h: 0.55, fontSize: 26, bold: true, fontFace: HEAD, color: VIOLET, margin: 0 });
    s.addText(l, { x: 5.4, y: y + 0.62, w: 3.9, h: 0.35, fontSize: 12.5, fontFace: BODY, color: INK2, margin: 0 });
  });
  s.addNotes("The headline test: the same Claude Code, the same model, the same 50 questions with frozen answers. One gets our MCP server; the other gets the raw log files and its own Bash, Read and Grep. A blind Opus judge preferred ours 30 to 15, and 18 to 4 on the brief's base corpus. Fewer wrong claims, 116 vs 186; more of the key facts found; and 14 seconds per answer instead of 86. On the big BGL and HDFS logs plain Claude Code needs 168 seconds on average and once timed out at 25 minutes. Honest limit: on small logs, where grep reads every line, plain Claude Code wins some engineer questions, 9 to 8.");

  // 7 · fits the company
  s = slide("Company");
  title(s, "How it fits the company", "It plugs into routines that already exist");
  await tiles(s, [[fa.FaBell, "On-call", "the engineer, during an incident"], [fa.FaCalendarWeek, "Weekly review", "the lead, recurring problems by team"], [fa.FaChessKing, "Monthly planning", "the manager, a computed ranking"]], 1.6, 2.1);
  const fit = [["Their tools", "Claude Code / any MCP client"], ["Their data", "stays on their machine"], ["Their logs", "any file format"], ["Their teams", "access per team"]];
  fit.forEach(([h, d], i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 3.9, 2.1, 0.85, WHITE, LINE);
    s.addText([{ text: h, options: { bold: true, color: DEEP, breakLine: true } }, { text: d, options: { color: INK2 } }],
      { x: x + 0.2, y: 3.9, w: 1.8, h: 0.85, fontSize: 11.5, fontFace: BODY, margin: 0, valign: "middle" });
  });
  s.addNotes("It fits three routines a company already has: the incident, the weekly review, the monthly planning. It uses the tools people already have, keeps logs on their own machine, reads their own log formats, and maps problems to their teams, with access per team enforced by the database itself.");

  // 8 · cheaper: Jev
  s = slide("Cost");
  title(s, "Cheaper than the alternatives", "Judge once, not every line");
  card(s, 0.5, 1.6, 4.4, 3.15, WHITE, LINE);
  s.addText("An LLM reads every line", { x: 0.85, y: 1.85, w: 3.8, h: 0.4, fontSize: 15, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addText("≈ 177 M tokens", { x: 0.85, y: 2.35, w: 3.8, h: 0.8, fontSize: 34, bold: true, fontFace: HEAD, color: WARN, margin: 0 });
  s.addText("every time (estimate)", { x: 0.85, y: 3.15, w: 3.8, h: 0.4, fontSize: 13, fontFace: BODY, color: INK2, margin: 0 });
  card(s, 5.1, 1.6, 4.4, 3.15, PALE);
  s.addText("Jev judges 1,126 patterns", { x: 5.45, y: 1.85, w: 3.8, h: 0.4, fontSize: 15, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addText("$0.02 · 20 s", { x: 5.45, y: 2.35, w: 3.8, h: 0.8, fontSize: 34, bold: true, fontFace: HEAD, color: VIOLET, margin: 0 });
  s.addText("once, reused by every answer", { x: 5.45, y: 3.15, w: 3.8, h: 0.4, fontSize: 13, fontFace: BODY, color: INK2, margin: 0 });
  s.addText("real alerts in the top 10: 1 → 5", { x: 5.45, y: 3.85, w: 3.8, h: 0.5, fontSize: 14, bold: true, fontFace: BODY, color: DEEP, margin: 0 });
  s.addNotes("Why it's cheaper. Reading all of BGL with a large model is around 177 million tokens, every time you ask; that is an estimate from the file size. Jev, a small model for typed judgments, runs inside SereneDB and judges each kind of message once: 1,126 patterns in 20 seconds for about two cents, stored and reused by every answer. That single step moved real alerts in the top ten from one to five. An answer with Claude Code plus our server costs about 5 cents.");

  // 8b · how Jev drives decisions
  s = slide("Cost");
  title(s, "Jev", "How Jev helps us decide");
  const dec = [
    [fa.FaFilter, "Is it a real problem?", "776 → 538", "kinds of message with error lines that Jev keeps as real faults"],
    [fa.FaSortAmountDown, "What comes first?", "1 → 5", "real alerts in the manager's top 10"],
    [fa.FaUserShield, "Is it an attack?", "54 / 109", "SSH patterns flagged as threats, though SSH logs have no level"],
    [fa.FaUsers, "Who owns it?", "4", "owners disputed; 1,114 inferred for new logs"],
  ];
  for (let i = 0; i < 4; i++) {
    const [ic, h, n, l] = dec[i], x = 0.5 + (i % 2) * 4.6, y = 1.45 + Math.floor(i / 2) * 1.62;
    card(s, x, y, 4.4, 1.5, i % 3 ? MIST : PALE);
    await dot(s, ic, x + 0.25, y + 0.25, 0.5);
    s.addText(h, { x: x + 0.9, y: y + 0.25, w: 3.3, h: 0.5, fontSize: 15, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(n, { x: x + 0.25, y: y + 0.85, w: 1.75, h: 0.5, fontSize: 21, bold: true, fontFace: HEAD, color: VIOLET, margin: 0, valign: "middle" });
    s.addText(l, { x: x + 2.05, y: y + 0.82, w: 2.2, h: 0.58, fontSize: 10.5, fontFace: BODY, color: INK2, margin: 0, valign: "middle" });
  }
  s.addText("Probabilities, not guesses: p_problem = max(fault × (1 − dump), threat)", { x: 0.5, y: 4.72, w: 9, h: 0.25, fontSize: 11.5, bold: true, fontFace: BODY, color: DEEP, margin: 0 });
  s.addNotes("How Jev helps us decide. Jev answers typed questions about each kind of message, with calibrated probabilities. Is it a real problem? Of 776 BGL message kinds with error-level lines, Jev keeps 538 as real faults and drops routine register dumps. What comes first? That moves real alerts in the manager's top 10 from one to five. Is it an attack? On SSH logs, which have no severity at all, Jev flags 54 of 109 patterns as security events. Who owns it? Jev checks the ownership table, flags 4 disputed owners, and inferred 1,114 owners for logs we had never seen. The full list of questions and choices is in the Jev tab of every session report.");

  // 9 · loading
  s = slide("Loading");
  title(s, "Loading", "One sentence loads your logs");
  const steps = [[fa.FaFileImport, "Stream"], [fa.FaSearch, "Detect format"], [fa.FaCogs, "Parse"], [fa.FaLayerGroup, "Patterns"], [fa.FaBalanceScale, "Jev judges"], [fa.FaSearchPlus, "Index"]];
  for (let i = 0; i < steps.length; i++) {
    const [ic, h] = steps[i], x = 0.5 + i * 1.53;
    card(s, x, 1.6, 1.35, 1.55, i === 4 ? PALE : MIST);
    await dot(s, ic, x + 0.4, 1.8);
    s.addText(h, { x: x + 0.08, y: 2.5, w: 1.2, h: 0.5, fontSize: 12.5, bold: true, fontFace: HEAD, color: INK, margin: 0, align: "center", valign: "middle" });
    if (i < steps.length - 1) s.addText("›", { x: x + 1.33, y: 2.15, w: 0.2, h: 0.4, fontSize: 20, bold: true, color: VIOLET, fontFace: HEAD, margin: 0, align: "center" });
  }
  stats(s, [["72 s", "base corpus, 5 M lines"], ["1.6 s", "a new 21 k-line file"], ["76", "log formats detected"]], 3.35, 1.6, MIST);
  s.addNotes("Loading. One sentence to Claude starts it, and every step runs inside SereneDB: the file is streamed in with COPY, its format detected from 76 known formats, parsed with SQL into typed columns, reduced to kinds of message, judged once by Jev in SQL, and indexed. The base corpus is ready in 72 seconds, a new 21 thousand line file in 1.6. The expensive work happens once, so every later answer is fast and cheap.");

  // 10 · performance
  s = slide("Performance");
  title(s, "Performance", "Built on SereneDB's search-analytics engine");
  const perf = [["Inverted index", "7 ms", "full-text count, 4.7 M lines"], ["Term dictionary", "3–39 ms", "group-bys without scanning"], ["SQL-native load", "18 s", "4.7 M lines parsed"],
    ["ASOF · ROLLUP · PIVOT", "< 100 ms", "timelines and rankings"], ["Remote Parquet", "2.8 s", "1 B rows on S3, in place"], ["On-demand index", "0.94 ms", "vs 281 ms scan"]];
  perf.forEach(([f, n, l], i) => {
    const x = 0.5 + (i % 3) * 3.07, y = 1.6 + Math.floor(i / 3) * 1.6;
    card(s, x, y, 2.87, 1.45, i % 2 ? MIST : WHITE, i % 2 ? undefined : LINE);
    s.addText(f, { x: x + 0.28, y: y + 0.15, w: 2.4, h: 0.35, fontSize: 12.5, bold: true, fontFace: BODY, color: INK, margin: 0 });
    s.addText(n, { x: x + 0.28, y: y + 0.5, w: 2.4, h: 0.5, fontSize: 24, bold: true, fontFace: HEAD, color: VIOLET, margin: 0 });
    s.addText(l, { x: x + 0.28, y: y + 1.0, w: 2.4, h: 0.35, fontSize: 11, fontFace: BODY, color: INK2, margin: 0 });
  });
  s.addNotes("Performance comes from SereneDB's engine. The inverted index counts a full-text search over 4.7 million lines in 7 milliseconds; group-bys come straight from the term dictionary without scanning rows. Data loads inside the database. Timelines use ASOF joins, rankings use ROLLUP and PIVOT. Remote Parquet on S3 is read in place, and an on-demand index pays for itself after four searches. The database takes under a second per answer; most of the time is the AI writing.");

  // 11 · MCP overview
  s = slide("Technical");
  title(s, "Technical · MCP", "One MCP server, four ways to use it");
  await tiles(s, [[fa.FaTools, "44 tools", "just ask"], [fa.FaTerminal, "5 prompts", "type /"], [fa.FaFolderOpen, "6 resources", "type @"], [fa.FaMagic, "Completions", "press Tab"]], 1.6, 2.6);
  s.addNotes("Now the technical part. MCP is how Claude discovers and calls our functions. Our server offers all four kinds: 44 tools Claude picks from their descriptions, 5 prompts as slash commands, 6 resources you attach with @, and completions that suggest real values from your data.");

  // 12 · tools
  s = slide("Technical");
  title(s, "Technical · tools", "44 tools, grouped by the question");
  const groups = [["Find", "search_logs · get_context"], ["Count", "count_by · trend · rollup"], ["Recurring", "top_patterns · pattern_history"], ["Explain", "burst_timeline · precursors"], ["Decide", "priority_table · owner_of"], ["Set up", "load_logs · use_dataset"]];
  groups.forEach(([g, t], i) => {
    const x = 0.5 + (i % 3) * 3.07, y = 1.6 + Math.floor(i / 3) * 1.55;
    card(s, x, y, 2.87, 1.4, i % 2 ? PALE : MIST);
    s.addText(g, { x: x + 0.28, y: y + 0.2, w: 2.4, h: 0.45, fontSize: 18, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(t, { x: x + 0.28, y: y + 0.7, w: 2.45, h: 0.5, fontSize: 10.5, fontFace: MONO, color: VIOLET, margin: 0, valign: "top" });
  });
  s.addText("Every result: its SQL, the exact total, and a flag if cut to 50 rows", { x: 0.5, y: 4.75, w: 9, h: 0.3, fontSize: 11.5, bold: true, fontFace: BODY, color: INK2, margin: 0 });
  s.addNotes("Forty-four tools grouped by the question they answer: find, count, recurring, explain, decide, set up. You never name a tool; Claude picks it from its description, which says when to use it, when not to, what it returns and what comes next. Every result carries the SQL that ran, the exact total, and a flag if rows were cut to 50. Full list in docs/TOOLS.md.");

  // 13 · prompts + resources
  s = slide("Technical");
  title(s, "Technical · prompts and resources", "Shortcuts in Claude Code");
  card(s, 0.5, 1.6, 4.4, 3.15);
  s.addText("Prompts  /", { x: 0.8, y: 1.8, w: 3.8, h: 0.4, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  s.addText(["investigate_failure", "review_recurring_problems", "set_priorities", "worked_investigation", "whole_corpus_counts"].map((t, k, a) => ({ text: t, options: { breakLine: k < a.length - 1 } })),
    { x: 0.8, y: 2.3, w: 3.9, h: 2.2, fontSize: 12, fontFace: MONO, color: VIOLET, margin: 0, valign: "top", paraSpaceAfter: 8 });
  card(s, 5.1, 1.6, 4.4, 3.15, PALE);
  s.addText("Resources  @", { x: 5.4, y: 1.8, w: 3.8, h: 0.4, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  s.addText(["datasets", "glossary", "field-guide/{dataset}", "ownership/{dataset}", "session/latest"].map((t, k, a) => ({ text: "logs://" + t, options: { breakLine: k < a.length - 1 } })),
    { x: 5.4, y: 2.3, w: 3.9, h: 2.2, fontSize: 12, fontFace: MONO, color: DEEP, margin: 0, valign: "top", paraSpaceAfter: 8 });
  s.addNotes("Prompts are slash commands: one playbook per role, a three-role worked investigation, and the whole-corpus counts the brief asks for. Resources attach context with @: the loaded datasets, the glossary, what each field means, the ownership table, and the full evidence of the session, beyond the 50-row tool limit. Arguments complete with real values from the data.");

  // 14 · wow
  s = slide("Wow");
  title(s, "Wow", "Beyond what the brief asked for");
  const wow = [[fa.FaFileAlt, "Your own logs"], [fa.FaCheckDouble, "Verify button"], [fa.FaCloud, "1 B remote rows"], [fa.FaUserShield, "Access per team"], [fa.FaFlask, "Blind evaluation"], [fa.FaBrain, "Judged once"]];
  for (let i = 0; i < 6; i++) {
    const [ic, h] = wow[i], x = 0.5 + (i % 3) * 3.07, y = 1.6 + Math.floor(i / 3) * 1.6;
    card(s, x, y, 2.87, 1.45, i % 2 ? PALE : MIST);
    await dot(s, ic, x + 0.28, y + 0.45);
    s.addText(h, { x: x + 1.0, y: y + 0.4, w: 1.8, h: 0.65, fontSize: 15, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
  }
  s.addNotes("What goes beyond the brief: load your own log files with no code; a Verify button that re-runs the query behind any number; a billion OpenTelemetry rows queried in place on S3; access per team enforced by the database, not the prompt; our own blind evaluation with 50 answer keys; and AI judgments computed once inside the database.");

  // 15 · proof
  s = slide("Wow");
  title(s, "Wow", "Every answer comes with its proof");
  const rep = await rounded(path.join(IMG, "report.png")), dash = await rounded(path.join(IMG, "dashboard.png"));
  [[rep, "Session report"], [dash, "Eval dashboard"]].forEach(([im, h], i) => {
    const x = 0.5 + i * 4.6, H = 2.75, w = Math.min(4.4 - 0.3, H * im.ratio), hh = w / im.ratio;
    card(s, x, 1.55, 4.4, 3.4, MIST);
    s.addImage({ data: im.data, x: x + (4.4 - w) / 2, y: 1.7, w, h: Math.min(hh, H) });
    s.addText(h, { x: x + 0.2, y: 4.5, w: 4.0, h: 0.38, fontSize: 13, bold: true, fontFace: BODY, color: INK, margin: 0, align: "center" });
  });
  s.addNotes("Every answer comes with its proof. On the left, the session report: each number links to the query behind it, and Verify re-runs it. On the right, the evaluation dashboard: 50 questions, both answers, the judge's reasons, and how to re-run it. Both open offline from the repo.");

  // 16 · scale
  s = slide("Scale");
  title(s, "Scale", "Where it goes next");
  await tiles(s, [[fa.FaIndustry, "Mittelstand", "production and IT logs"], [fa.FaBuilding, "Other industries", "anything that writes logs"], [fa.FaBoxOpen, "A product", "a self-hosted log copilot"]], 1.6, 1.95);
  s.addImage({ data: await gcard(9, 1.2), x: 0.5, y: 3.75, w: 9, h: 1.2 });
  [["10", "log types, no code change"], ["11.2 M", "lines loaded in 47 s"], ["1 B", "remote rows, in place"]].forEach(([n, l], i) => {
    s.addText(n, { x: 0.85 + i * 3.0, y: 3.85, w: 2.7, h: 0.55, fontSize: 28, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(l, { x: 0.85 + i * 3.0, y: 4.4, w: 2.7, h: 0.4, fontSize: 12, fontFace: BODY, color: "EDE7FF", margin: 0 });
  });
  s.addNotes("Nothing in the code is specific to one dataset: ten log types load without code changes, eleven million HDFS lines load in 47 seconds, and a billion remote rows are queried in place. That makes it a product: a self-hosted log copilot for Mittelstand production and IT, and any industry that writes logs.");

  // 17 · try it
  s = pres.addSlide(); s.background = { color: WHITE }; N++;
  s.addImage({ data: await gcard(9, 4.6), x: 0.5, y: 0.5, w: 9, h: 4.6 });
  s.addText("Try it in two commands", { x: 1.0, y: 0.95, w: 8, h: 0.7, fontSize: 34, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.0, y: 1.9, w: 8, h: 1.45, rectRadius: R, fill: { color: WHITE, transparency: 88 }, line: { type: "none" } });
  s.addText("docker compose up -d\nclaude\n> Load the base corpus", { x: 1.3, y: 1.95, w: 7.5, h: 1.35, fontSize: 18, fontFace: MONO, color: WHITE, margin: 0, valign: "middle" });
  s.addText("github.com/aircode610/making-sense-of-logs-schubki-ai-hackathon", { x: 1.0, y: 4.0, w: 8, h: 0.4, fontSize: 14, bold: true, fontFace: BODY, color: "EDE7FF", margin: 0 });
  s.addNotes("Two commands and one sentence, and your logs answer back. The worked investigation, the dashboard and every tool are documented in the repo. Thank you.");

  await pres.writeFile({ fileName: OUT });
  console.log(`wrote ${path.relative(process.cwd(), OUT)} (${N} slides)`);
})();
