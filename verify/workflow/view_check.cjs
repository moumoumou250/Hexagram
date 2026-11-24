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
      function verify() {
        equal(get("question").value, reading.question, "question");
        equal(get("base").value, reading.id, "base");
        equal(get("month").value, reading.month, "month");
        equal(get("day").value, reading.day, "day");
        equal(get("role").value, reading.role, "focus");
        equal(get("summary").textContent.startsWith(reading.summary), true, "conclusion");
        if (!reading.id) {
          equal(get("hero").textContent, "盘面待核", "pending chart");
          equal(get("board").rows.length, 0, "pending rows");
          return;
        }
        const chart = data.charts[reading.id];
        const transition = data.transitions[reading.id + ":" + reading.mask];
        equal(get("hero").querySelector("h1").textContent, chart.name, "base name");
        equal(get("hero").querySelector("h2")?.textContent || "", reading.mask ?
          data.charts[transition.changed_id].name : "", "changed name");
        const moves = [...doc.querySelectorAll("#moves input:checked")];
        equal(moves.reduce((mask, el) => mask | (1 << (Number(el.value) - 1)), 0), reading.mask, "moves");
        const labels = ["初", "二", "三", "四", "五", "上"];
        for (const [kind, pos] of [["shi", chart.shi_line], ["ying", chart.ying_line]]) {
          equal(get("roles").querySelector(".role-" + kind + " strong").textContent.startsWith(labels[pos-1]), true, kind);
        }
        const choice = get("candidate").selectedOptions[0];
        if (reading.primary) {
          equal(Boolean(choice.value), true, "selected primary");
          equal(choice.textContent.includes(reading.primary.branch + reading.primary.element), true, "primary branch");
          const sourceNames = {hidden: "伏神", changed: "变爻", month: "月建", day: "日辰"};
          if (sourceNames[reading.primary.source]) equal(choice.textContent.includes(sourceNames[reading.primary.source]), true, "primary source");
          if (reading.primary.position) equal(choice.textContent.startsWith(labels[reading.primary.position-1]), true, "primary position");
        } else equal(choice.value, "", "pending primary");
      }
      verify();
      if (reading.id) {
        get("clear").click();
        equal(get("question").value, "", "clear");
      }
      get("example").click();
      verify();
    });
    if (errors.length) throw Error(errors.join("\n"));
    console.log("PASS: first load and reload", html);
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
