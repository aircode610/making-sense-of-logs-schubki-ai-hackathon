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
  const stats = (s, items, y = 1.7, h = 2.3, fill = WHITE, size) => {
    const n = items.length, gap = 0.2, w = (9 - gap * (n - 1)) / n;
    items.forEach(([num, label, color], i) => {
      const x = 0.5 + i * (w + gap);
      card(s, x, y, w, h, fill, fill === WHITE ? LINE : undefined);
      s.addText(num, { x: x + 0.3, y: y + 0.35, w: w - 0.5, h: 0.8, fontSize: size || (n > 3 ? 30 : 38), bold: true, fontFace: HEAD, color: color || VIOLET, margin: 0 });
      s.addText(label, { x: x + 0.3, y: y + 1.2, w: w - 0.5, h: h - 1.35, fontSize: 13, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
    });
  };

  // a pipeline strip: the 5 stages, `on` highlighted (used on the stage slides)
  const STAGES = [[fa.FaFileImport, "Load"], [fa.FaBalanceScale, "Judge"], [fa.FaSearch, "Ask"], [fa.FaComments, "Answer"], [fa.FaCheckDouble, "Verify"]];
  const strip = async (s, on) => {
    for (let i = 0; i < 5; i++) {
      const x = 0.5 + i * 1.83, act = i === on;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.32, w: 1.68, h: 0.5, rectRadius: 0.25,
        fill: { color: act ? VIOLET : MIST }, line: { type: "none" } });
      s.addImage({ data: await icon(STAGES[i][0], act ? WHITE : MUTED), x: x + 0.2, y: 1.44, w: 0.26, h: 0.26 });
      s.addText(`${i + 1} · ${STAGES[i][1]}`, { x: x + 0.52, y: 1.32, w: 1.1, h: 0.5, fontSize: 12.5, bold: act, fontFace: BODY, color: act ? WHITE : INK2, margin: 0, valign: "middle" });
    }
  };
  // a stage slide: strip + left "what happens" list + right big numbers
  const stage = async (on, kicker, t, what, nums, notes) => {
    const s = slide("Pipeline");
    title(s, kicker, t);
    await strip(s, on);
    card(s, 0.5, 2.05, 4.4, 2.9, MIST);
    s.addText(what.map((w, k) => ({ text: w, options: { bullet: { indent: 14 }, breakLine: k < what.length - 1 } })),
      { x: 0.75, y: 2.2, w: 4.0, h: 2.65, fontSize: 13.5, fontFace: BODY, color: INK2, margin: 0, valign: "top", paraSpaceAfter: 8 });
    nums.forEach(([n, l], k) => {
      const h = 2.9 / nums.length - 0.12, y = 2.05 + k * (h + 0.12);
      card(s, 5.1, y, 4.4, h, k === 0 ? PALE : WHITE, k === 0 ? undefined : LINE);
      s.addText(n, { x: 5.35, y: y + 0.08, w: 3.95, h: h * 0.55, fontSize: nums.length > 2 ? 24 : 30, bold: true, fontFace: HEAD, color: VIOLET, margin: 0, valign: "bottom" });
      s.addText(l, { x: 5.35, y: y + h * 0.6, w: 3.95, h: h * 0.38, fontSize: 11.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
    });
    s.addNotes(notes);
    return s;
  };

  // 1 · title
  let s = pres.addSlide(); s.background = { color: WHITE }; N++;
  s.addImage({ data: await gcard(3.4, 4.6), x: 6.1, y: 0.5, w: 3.4, h: 4.6 });
  [["14 s", "per answer"], ["≈ 5 ¢", "per answer"], ["$0.02", "to judge 1,126 kinds of message"]].forEach(([n, l], i) => {
    s.addText(n, { x: 6.45, y: 0.95 + i * 1.35, w: 2.8, h: 0.65, fontSize: 36, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(l, { x: 6.45, y: 1.58 + i * 1.35, w: 2.8, h: 0.35, fontSize: 13, fontFace: BODY, color: "EDE7FF", margin: 0 });
  });
  s.addImage({ data: GRAD_SQ, x: 0.5, y: 0.65, w: 0.42, h: 0.42 });
  s.addText("SereneDB challenge · SchubKI Hackathon 2026", { x: 1.05, y: 0.67, w: 4.9, h: 0.38, fontSize: 11, fontFace: BODY, color: MUTED, margin: 0, valign: "middle" });
  s.addText("Making Sense\nof Logs", { x: 0.5, y: 1.45, w: 5.4, h: 1.5, fontSize: 40, bold: true, fontFace: HEAD, color: INK, margin: 0 });
  s.addText("Ask your logs a question. Get the answer your role needs, fast, cheap, and with proof.", { x: 0.5, y: 3.05, w: 5.2, h: 0.8, fontSize: 16, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  s.addText("Amirali & Konark", { x: 0.5, y: 4.55, w: 5, h: 0.3, fontSize: 12, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addNotes("0:00 \u00b7 1 \u00b7 Title\n\"We built an assistant that answers questions about millions of log lines, for the engineer, the team lead and the manager. An answer takes 14 seconds, costs about 5 cents, and every number in it can be checked.\"");

  // 2 · problem
  s = slide("Problem");
  title(s, "The problem", "Millions of lines, three people, no answers");
  await tiles(s, [[fa.FaWrench, "Engineer", "“What failed?”"], [fa.FaUsers, "Team lead", "“What keeps coming back?”"], [fa.FaChartLine, "Manager", "“What do we fix first?”"]], 1.4, 1.75);
  stats(s, [["4.7 M", "lines: no prompt fits"], ["855,501", "FATAL lines, 36,714 bursts"], ["86 s", "per answer on raw files"]], 3.3, 1.7, MIST);
  s.addNotes("0:15 \u00b7 2 \u00b7 Problem\n\"Three people ask about the same logs. BGL alone is 4.7 million lines: no prompt fits that. It has 855 thousand FATAL lines, but they are only 36 thousand bursts of real recurrences, so counting lines misleads. And if you just let Claude grep the raw files, it takes 86 seconds per answer and gets things wrong.\"");

  // 3 · the pipeline at a glance
  s = slide("Pipeline");
  title(s, "The pipeline", "The database counts, the AI explains");
  const pipe = [[fa.FaFileImport, "Load", "SereneDB parses and indexes", "72 s · 5 M lines"], [fa.FaBalanceScale, "Judge", "Jev labels each kind of message", "$0.02 · 20 s"],
    [fa.FaSearch, "Ask", "Claude picks MCP tools", "< 0.1 s per query"], [fa.FaComments, "Answer", "written for your role", "14 s · ≈ 5 ¢"], [fa.FaCheckDouble, "Verify", "every number re-runs", "62 / 62 traced"]];
  for (let i = 0; i < 5; i++) {
    const [ic, h, d, n] = pipe[i], x = 0.5 + i * 1.83;
    card(s, x, 1.55, 1.68, 3.0, i % 2 ? MIST : PALE);
    await dot(s, ic, x + 0.22, 1.75, 0.5);
    s.addText(h, { x: x + 0.22, y: 2.42, w: 1.35, h: 0.4, fontSize: 16, bold: true, fontFace: HEAD, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.22, y: 2.85, w: 1.35, h: 0.8, fontSize: 11, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
    s.addText(n, { x: x + 0.22, y: 3.75, w: 1.38, h: 0.65, fontSize: 13.5, bold: true, fontFace: HEAD, color: VIOLET, margin: 0, valign: "top" });
    if (i < 4) s.addText("›", { x: x + 1.64, y: 2.75, w: 0.22, h: 0.4, fontSize: 22, bold: true, color: VIOLET, fontFace: HEAD, margin: 0, align: "center" });
  }
  s.addText("Setup:  docker compose up -d  ·  uv sync  ·  claude  ·  “Load the base corpus”", { x: 0.5, y: 4.7, w: 9, h: 0.3, fontSize: 12, fontFace: MONO, color: DEEP, margin: 0, align: "center" });
  s.addNotes("0:35 \u00b7 3 \u00b7 Pipeline\n\"Our answer is a pipeline in five steps. The database does the counting, the AI only explains. Load, judge, ask, answer, verify. Setup is four commands.\"");

  // 4–8 · the five stages
  await stage(0, "Step 1 · Load", "SereneDB loads and indexes every line",
    ["Download from Zenodo, or any log file on disk", "Format detected from 76 known formats", "Parsed with SQL inside SereneDB: typed columns", "Masked into kinds of message; bursts by window functions", "One inverted index: full text, BM25, phrase, fuzzy"],
    [["72 s", "clean clone → BGL + OpenStack ready (5 M lines)"], ["18 s", "4.7 M BGL lines parsed + indexed in SQL"], ["1.6 s", "a new 21 k-line file, format auto-detected"]], "0:50 \u00b7 4 \u00b7 Load\n\"Step one. Say 'Load the base corpus'. SereneDB downloads BGL and OpenStack, detects the format from 76 known ones, parses everything with SQL into typed columns, groups lines into kinds of message and builds one full-text index. 72 seconds for 5 million lines. Your own log file: under 2 seconds.\"");
  await stage(1, "Step 2 · Judge", "Jev decides what is a real problem, once",
    ["Typed questions, calibrated probabilities: real fault? routine dump? attack? whose?", "Asked once per kind of message, inside SereneDB with one SQL call", "Stored: answering never re-reads raw lines"],
    [["$0.02 · 20 s", "Jev judges all 1,126 BGL kinds of message"], ["≈ 177 M tokens", "for an LLM to read BGL once (estimate), every time"], ["1 → 5", "real alerts in the manager's top 10"]], "1:15 \u00b7 5 \u00b7 Judge\n\"Step two is where it gets cheap. Jev, a small typed-judgment model, runs inside SereneDB and asks each kind of message once: is it a real fault or a routine dump? an attack? whose is it? 1,126 kinds of message in 20 seconds for 2 cents, stored. Reading BGL with a large model would be about 177 million tokens, every time. And it works: real alerts in the manager's top 10 go from 1 to 5.\"");
  await stage(2, "Step 3 · Ask", "Claude asks focused questions through MCP",
    ["44 tools: search, context, counts, trends, rankings, owners", "Each tool is a fixed, safe SQL query; Claude fills typed fields", "Results: the SQL, exact totals, ≤ 50 rows, truncation flag", "5 prompts (type /) and 6 resources (type @)"],
    [["7 ms", "full-text count over 4.7 M lines (inverted index)"], ["3–39 ms", "group-bys straight from the term dictionary"], ["1.8 s", "of database time for a 20-step investigation"]], "1:45 \u00b7 6 \u00b7 Ask\n\"Step three. Claude asks focused questions through our MCP server: 44 tools, each a fixed, safe SQL query. A full-text count over 4.7 million lines takes 7 milliseconds; group-bys come straight from the index. A whole 20-step investigation spends 1.8 seconds in the database.\"");
  await stage(3, "Step 4 · Answer", "One problem, three different answers",
    ["Engineer: 12,996 lines on 1,024 nodes, one host → check it", "Team lead: 31 bursts, owner disputed → triage together", "Manager: rank 1 of 133 → name an owner now", "Facts, hypothesis, unknowns and a next step, every time"],
    [["14 s", "per answer with Claude Code + our server"], ["≈ 5 ¢", "per answer (Claude Code, 50 questions)"]], "2:05 \u00b7 7 \u00b7 Answer \u2192 switch to Claude Code\nLive: run /mcp__logs__worked_investigation (topic: what deserves attention in November 2005, dataset bgl). \"One problem, three answers. The engineer gets 12,996 lines on 1,024 nodes, all pointing to one host, and the check to run. The team lead gets 31 recurrences and an owner disputed between two teams. The manager gets rank 1 of 133 and a decision. Different evidence, not different lengths.\"");
  await stage(4, "Step 5 · Verify", "Every number traces to its query",
    ["Session report: each number links to the step that produced it", "Verify re-runs the step read-only and compares", "Jev checks each sentence against its evidence", "Offline copy: docs/investigation/report.html"],
    [["62 / 62", "numbers in the worked investigation traced to a query"], ["17 / 17", "steps give the same result when re-run"]], "2:50 \u00b7 8 \u00b7 Verify \u2192 show the report\nOpen the link Claude gives. Click a number: it jumps to its step. Click Verify. \"Every number traces to the query that produced it: 62 of 62. Re-running every step gives the same result. The Jev tab shows every question Jev is asked and what each answer means.\"");

  // 9 · price + performance
  s = slide("Price & performance");
  title(s, "Price & performance", "Faster, more correct, for about a cent more");
  card(s, 0.5, 1.5, 4.4, 3.45, WHITE, LINE);
  s.addText("Seconds per answer (mean, 50 questions)", { x: 0.8, y: 1.62, w: 3.9, h: 0.35, fontSize: 12.5, bold: true, fontFace: BODY, color: INK, margin: 0 });
  s.addChart(pres.charts.BAR, [{ name: "s", labels: ["Claude Code + our MCP", "Plain Claude Code"], values: [14.3, 86.0] }],
    { x: 0.6, y: 2.0, w: 4.2, h: 2.4, barDir: "bar", chartColors: [VIOLET], valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      showValue: true, dataLabelFormatCode: '0 "s"', dataLabelColor: INK, dataLabelFontSize: 14, catAxisLabelColor: INK2, catAxisLabelFontSize: 11.5,
      catAxisLineShow: false, barGapWidthPct: 50, catAxisOrientation: "maxMin" });
  s.addText("same model · same questions · blind judge", { x: 0.8, y: 4.5, w: 3.9, h: 0.3, fontSize: 10.5, fontFace: BODY, color: MUTED, margin: 0 });
  const pp = [["6× faster", "14 s vs 86 s per answer"], ["4.9 ¢ vs 3.8 ¢", "per answer: about a cent more"], ["47 vs 100", "wrong claims per dollar spent"], ["< 1 s", "of each answer is the database; the rest is AI"]];
  pp.forEach(([n, l], k) => {
    const y = 1.5 + k * 0.88;
    card(s, 5.1, y, 4.4, 0.78, k % 2 ? MIST : PALE);
    s.addText(n, { x: 5.35, y, w: 1.95, h: 0.78, fontSize: 18, bold: true, fontFace: HEAD, color: VIOLET, margin: 0, valign: "middle" });
    s.addText(l, { x: 7.3, y, w: 2.1, h: 0.78, fontSize: 11, fontFace: BODY, color: INK2, margin: 0, valign: "middle" });
  });
  s.addNotes("3:15 \u00b7 9 \u00b7 Price & performance\n\"The main point. Same Claude Code, same model, 50 questions. With our server: 14 seconds per answer instead of 86, six times faster. It costs about one cent more, 4.9 instead of 3.8, but makes half the wrong claims per dollar. Under one second of each answer is the database; the rest is the AI writing.\"");

  // 10 · results
  s = slide("Results");
  title(s, "Results", "Measured on 50 questions with known answers");
  stats(s, [["30 – 15", "wins vs plain Claude Code (18 – 4 on BGL + OpenStack)"], ["116 vs 186", "wrong claims"], ["64 vs 46 %", "key facts found"]], 1.55, 1.9, WHITE, 30);
  card(s, 0.5, 3.65, 9, 1.3, MIST);
  s.addText([{ text: "Where it still loses: ", options: { bold: true, color: DEEP } }, { text: "engineer questions on small logs (8 – 9), where grep can read every line. All 50 answers and the judge's reasons are in the dashboard.", options: { color: INK2 } }],
    { x: 0.8, y: 3.65, w: 8.4, h: 1.3, fontSize: 13, fontFace: BODY, margin: 0, valign: "middle" });
  s.addNotes("3:40 \u00b7 10 \u00b7 Results\n\"Measured against frozen answer keys with a blind judge: we win 30 to 15, and 18 to 4 on the brief's data, with 116 wrong claims instead of 186. Where we still lose: engineer questions on small logs, where grep can read every line.\"");

  // 11 · features → better results
  s = slide("Features");
  title(s, "Features", "Each feature fixes a way answers go wrong");
  const feat = [
    [fa.FaLayerGroup, "Bursts, not lines", "a storm of 12,996 lines reads as 31 recurrences"],
    [fa.FaBalanceScale, "Jev judgments", "real alerts in the top 10: 1 → 5"],
    [fa.FaCalculator, "Exact totals in SQL", "62 / 62 numbers traced; no rounding by the model"],
    [fa.FaUsers, "Ownership table", "every problem has a team; 4 disputes flagged"],
    [fa.FaSortAmountDown, "Computed priority", "the manager's ranking is SQL, not opinion"],
    [fa.FaClipboardCheck, "Facts vs hypotheses", "unknowns stated in 100 % of answers"],
  ];
  for (let i = 0; i < 6; i++) {
    const [ic, h, d] = feat[i], x = 0.5 + (i % 3) * 3.07, y = 1.5 + Math.floor(i / 3) * 1.75;
    card(s, x, y, 2.87, 1.6, i % 2 ? PALE : MIST);
    await dot(s, ic, x + 0.25, y + 0.25, 0.46);
    s.addText(h, { x: x + 0.85, y: y + 0.25, w: 1.95, h: 0.46, fontSize: 13.5, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(d, { x: x + 0.25, y: y + 0.85, w: 2.45, h: 0.65, fontSize: 11.5, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  s.addNotes("4:00 \u00b7 11 \u00b7 Features\n\"Each feature fixes a way answers go wrong. Bursts instead of lines. Jev's judgments. Exact totals in SQL, never rounded by the model. An ownership table, so every problem has a team. A computed priority. And facts are always separated from hypotheses.\"");

  // 12 · beyond the brief
  s = slide("Wow");
  title(s, "Beyond the brief", "More than the challenge asked for");
  const wow = [[fa.FaFileAlt, "Your own logs", "any file, no code"], [fa.FaCloud, "1 B remote rows", "queried in place on S3"], [fa.FaUserShield, "Access per team", "enforced by the database"],
    [fa.FaDatabase, "11.2 M lines", "HDFS loaded in 47 s"], [fa.FaFlask, "Blind evaluation", "50 answer keys + dashboard"], [fa.FaUndo, "Fully reproducible", "--fresh reruns Jev live, same result"]];
  for (let i = 0; i < 6; i++) {
    const [ic, h, d] = wow[i], x = 0.5 + (i % 3) * 3.07, y = 1.5 + Math.floor(i / 3) * 1.75;
    card(s, x, y, 2.87, 1.6, i % 2 ? MIST : PALE);
    await dot(s, ic, x + 0.25, y + 0.3, 0.46);
    s.addText(h, { x: x + 0.85, y: y + 0.27, w: 1.95, h: 0.5, fontSize: 14, bold: true, fontFace: HEAD, color: INK, margin: 0, valign: "middle" });
    s.addText(d, { x: x + 0.25, y: y + 0.95, w: 2.45, h: 0.5, fontSize: 12, fontFace: BODY, color: INK2, margin: 0, valign: "top" });
  }
  s.addNotes("4:25 \u00b7 12 \u00b7 Beyond the brief\n\"Beyond the brief: your own log files with no code, a billion remote rows queried in place, access per team enforced by the database, 11 million lines loaded in 47 seconds, our own blind evaluation, and it is fully reproducible: run with --fresh and Jev judges everything live with the same result.\"");

  // 13 · scale
  s = slide("Scale");
  title(s, "Scale", "Where it goes next");
  await tiles(s, [[fa.FaIndustry, "Mittelstand", "production and IT logs"], [fa.FaBuilding, "Other industries", "anything that writes logs"], [fa.FaBoxOpen, "A product", "a self-hosted log copilot"]], 1.55, 1.95);
  s.addImage({ data: await gcard(9, 1.2), x: 0.5, y: 3.75, w: 9, h: 1.2 });
  [["10", "log types, no code change"], ["≈ 5 ¢", "per answer"], ["2 min", "fresh install → answers"]].forEach(([n, l], i) => {
    s.addText(n, { x: 0.85 + i * 3.0, y: 3.85, w: 2.7, h: 0.55, fontSize: 28, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
    s.addText(l, { x: 0.85 + i * 3.0, y: 4.4, w: 2.7, h: 0.4, fontSize: 12, fontFace: BODY, color: "EDE7FF", margin: 0 });
  });
  s.addNotes("4:45 \u00b7 13 \u00b7 Scale\n\"Nothing is specific to one dataset: ten log types load with no code change. That makes it a product: a self-hosted log copilot for the Mittelstand and beyond.\"");

  // 14 · try it
  s = pres.addSlide(); s.background = { color: WHITE }; N++;
  s.addImage({ data: await gcard(9, 4.6), x: 0.5, y: 0.5, w: 9, h: 4.6 });
  s.addText("Try it in two minutes", { x: 1.0, y: 0.95, w: 8, h: 0.7, fontSize: 34, bold: true, fontFace: HEAD, color: WHITE, margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.0, y: 1.9, w: 8, h: 1.6, rectRadius: R, fill: { color: WHITE, transparency: 88 }, line: { type: "none" } });
  s.addText("docker compose up -d\nuv sync\nclaude\n> Load the base corpus", { x: 1.3, y: 1.95, w: 7.5, h: 1.5, fontSize: 17, fontFace: MONO, color: WHITE, margin: 0, valign: "middle" });
  s.addText("github.com/aircode610/making-sense-of-logs-schubki-ai-hackathon", { x: 1.0, y: 4.05, w: 8, h: 0.4, fontSize: 14, bold: true, fontFace: BODY, color: "EDE7FF", margin: 0 });
  s.addNotes("4:55 \u00b7 14 \u00b7 Try it\n\"Four commands, about two minutes from a fresh install to answers. Thank you.\"");

  await pres.writeFile({ fileName: OUT });
  console.log(`wrote ${path.relative(process.cwd(), OUT)} (${N} slides)`);
})();
