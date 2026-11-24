// Usage: node view_check.cjs reading.html [chromium-executable]
const { chromium } = require("playwright-core");
const { pathToFileURL } = require("node:url");
const { resolve } = require("node:path");

async function main() {
  const [html, executablePath] = process.argv.slice(2);
  if (!html) throw Error("Expected the path to an exported reading");
  const browser = await chromium.launch({ executablePath });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(pathToFileURL(resolve(html)).href);
    await page.evaluate(() => {
      const doc = document;
      const get = id => doc.getElementById(id);
      const reading = JSON.parse(get("reading-data").textContent);
      const data = JSON.parse(get("chart-data").textContent);
      function equal(actual, expected, field) {
        if (actual !== expected) throw Error(field + ": " + actual + " != " + expected);
      }
      function verifyStrength() {
        const table = get("strength");
        equal([...table.tHead.rows[0].cells].map(cell => cell.textContent).join("、"),
          "爻位与纳甲、角色、月令、月建对爻、日辰对爻、旬空", "strength columns");
        const bodyRows = [...table.tBodies[0].rows];
        equal(bodyRows.length, 6, "strength row count");
        equal(bodyRows.map(row => row.dataset.position).join(","), "6,5,4,3,2,1", "strength order");
        equal(bodyRows.every(row => row.cells.length === 6), true, "strength cell count");
        const interpretation = get("interpretation-title");
        equal(Boolean(table.compareDocumentPosition(interpretation) & Node.DOCUMENT_POSITION_FOLLOWING), true, "interpretation follows table");
        equal(interpretation.parentElement.contains(get("summary")), true, "conclusion in interpretation");
      }
      function verify() {
        equal(doc.querySelectorAll("form, select, input, button").length, 0, "read-only page");
        equal(get("question").textContent, reading.question, "question");
        equal(get("month").textContent, reading.month ? reading.month + "月" : "待核", "month");
        equal(get("day").textContent, reading.day ? reading.day + "日" :
          reading.dayBranch ? reading.dayBranch + "日（天干待核）" : "待核", "day");
        equal(reading.summary.trim().startsWith(get("summary").textContent), true, "core conclusion from saved summary");
        if (get("summary").textContent !== reading.summary) {
          equal(get("summary-detail").textContent, reading.summary, "complete summary retained");
        }
        for (const id of ["roles", "facts", "focus", "changes"]) equal(get(id), null, id);
        verifyStrength();
        const savedNotes = [...get("reading-notes").children].slice(0, reading.notes.length);
        equal(JSON.stringify(savedNotes.map(note => note.textContent)),
          JSON.stringify(reading.notes.map(note => note.text)), "saved interpretation notes");
        equal(get("review-details").open, false, "review details collapsed by default");
        equal(get("interpretation-title").parentElement.innerText.includes("按当前配置派生"),
          false, "no repeated provenance labels");
        const points = [...get("key-points").tBodies[0].rows];
        const pointRoles = [...new Set(points.map(row => row.cells[0].textContent))].join("、");
        equal(get("key-points-block").hidden, !reading.id, "key points wait for the board");
        equal([...get("key-points").tHead.rows[0].cells].map(cell => cell.textContent).join("、"),
          "判断项目、对象、月建影响、日辰影响、当前状态、力度评估", "key point columns");
        equal(points.every(row => row.cells.length === 6 && row.cells[5].querySelector(".force-status")),
          true, "key point cells and force badge");
        equal(pointRoles, reading.primary ? "用神、原神生用、忌神克用、世爻、应爻"
          : reading.id ? "世爻、应爻" : "", "key point order");
        if (reading.primary) {
          equal(points[0].cells[1].textContent, get("primary").textContent, "focus identity in key points");
          equal([...get("basis-list").querySelectorAll("dt")].map(term => term.textContent).join("、"),
            "月建、日辰、旬空、动变、原忌神", "evidence order");
        }
        for (const [before, after] of [["inferred-title", "fixed-title"], ["fixed-title", "basis-title"],
          ["basis-title", "windows-title"], ["windows-title", "verdict-title"]]) {
          equal(Boolean(get(before).compareDocumentPosition(get(after)) & Node.DOCUMENT_POSITION_FOLLOWING),
            true, `${before} precedes ${after}`);
        }
        const conclusions = reading.interpretation?.conclusions || {};
        if (conclusions.windows?.length) {
          equal(get("windows-block").innerText.includes("候选通道"), true, "candidate timing notice");
          equal(get("windows-lines").children.length, conclusions.windows.length, "timing list");
        }
        for (const [index, layer] of (conclusions.verdict_layers || []).entries()) {
          const item = get("verdict-layers").children[index];
          equal(item.querySelector(".layer-status").textContent, layer.status === "已备" ? "已具备" : layer.status, "layer status");
          equal(item.querySelector(".layer-condition").textContent, layer.condition, "layer condition");
        }
        if (conclusions.falsifier) equal(get("falsifier-line").textContent, conclusions.falsifier, "falsifier retained");
        if (reading.disclaimer) equal(get("disclaimer").textContent, reading.disclaimer, "scope disclaimer");
        if (!reading.id) {
          equal(get("hero").querySelector("h1").textContent, "盘面待核", "pending chart");
          equal(get("board").rows.length, 0, "pending rows");
          equal(Object.keys(data).length, 0, "pending data");
          return;
        }
        equal(Object.keys(data).sort().join(","), "base,changed,day,interactions,moving,roles,strength", "single-case payload");
        const chart = data.base;
        equal(String(chart.hexagram_id), reading.id, "base id");
        equal(get("hero").querySelector("h1").textContent, chart.name, "base name");
        equal(Boolean(data.changed), Boolean(reading.mask), "changed data");
        equal(get("hero").querySelector("h2")?.textContent || "", data.changed?.name || "", "changed name");
        const moves = [...doc.querySelectorAll("#board tr.moving")];
        equal(moves.reduce((mask, row) => mask | (1 << (Number(row.dataset.position) - 1)), 0), reading.mask, "moves");
        const labels = ["初", "二", "三", "四", "五", "上"];
        const board = get("board");
        const positions = rows => [...rows].map(row => row.dataset.position).join(",");
        equal(positions(board.tBodies[0].rows), "6,5,4,3,2,1", "board order");
        equal([...board.tHead.rows[0].cells].map(cell => cell.textContent).join("、"),
          reading.mask ? "本卦六亲、世应与动静、变卦六亲" : "本卦六亲、世应与动静", "board columns");
        for (const line of chart.lines) {
          const row = board.querySelector(`tr[data-position="${line.position}"]`);
          equal(row.cells[0].querySelector(".relative").textContent, line.relative, "base relative");
          const change = data.moving[line.position];
          if (change) equal(row.querySelector(".changed-line .relative").textContent, change, "changed relative");
        }
        for (const [kind, pos] of [["shi", chart.shi_line], ["ying", chart.ying_line]]) {
          const row = board.querySelector(".role-" + kind);
          equal(Number(row.dataset.position), pos, kind);
          equal(row.querySelector(".role-badge").textContent, kind === "shi" ? "世爻" : "应爻", kind + " badge");
        }
        const primary = get("primary").textContent;
        if (reading.primary) {
          equal(primary.includes(reading.primary.branch + reading.primary.element), true, "primary branch");
          const sourceNames = {hidden: "伏神", changed: "变爻", month: "月建", day: "日辰"};
          if (sourceNames[reading.primary.source]) equal(primary.includes(sourceNames[reading.primary.source]), true, "primary source");
          if (reading.primary.position) equal(primary.startsWith(labels[reading.primary.position - 1]), true, "primary position");
        } else equal(primary, reading.role ? `${reading.role}（爻位待核）` : "待核", "pending primary");
      }
      verify();
    });
    if (errors.length) throw Error(errors.join("\n"));
    console.log("PASS: single-case view", html);
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
