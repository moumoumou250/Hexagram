"""Build the standalone viewer from the selected rule version and reading."""

import json
import re
import sqlite3
from contextlib import closing

from .review import facts, rows
from .report import STATUS
from .rule_data import ROOT


def build_data(sql, reading):
    if not reading["id"]:
        return {}

    with closing(sqlite3.connect(":memory:")) as database:
        database.row_factory = sqlite3.Row
        database.executescript(sql)

        def query(statement, *params):
            return [dict(row) for row in database.execute(statement, params)]

        def chart(hexagram_id):
            data, = query("SELECT * FROM hexagrams WHERE hexagram_id = ?", hexagram_id)
            return dict(data, lines=query(
                "SELECT position, polarity, line_title, stem, branch, element, relative, shi_ying, "
                "hidden_stem, hidden_branch, hidden_element, hidden_relative "
                "FROM hexagram_board WHERE hexagram_id = ? ORDER BY position", hexagram_id,
            ))

        base_id, mask = reading["id"], reading["mask"]
        base = chart(base_id)
        changed = None
        moving = {}
        if mask:
            transition, = query("SELECT changed_id FROM hexagram_change WHERE base_id = ? AND move_mask = ?",
                                base_id, mask)
            changed = chart(transition["changed_id"])
            moving = {row["position"]: row["changed_relative"] for row in query(
                "SELECT position, changed_relative FROM change_board WHERE base_id = ? AND move_mask = ?",
                base_id, mask,
            )}

        day = next(iter(query("SELECT branch, kong_1, kong_2 FROM jiazi WHERE ganzhi = ?", reading["day"])), None)
        month = reading["month"]
        day_branch = day["branch"] if day else reading.get("dayBranch")
        actors = sorted({branch for branch in (month, day_branch) if branch})
        targets = set(actors)
        elements = {choice["element"] for choice in (*reading.get("candidates", ()), reading.get("primary")) if choice}
        for line in base["lines"]:
            targets.update((line["branch"], line["hidden_branch"]))
            elements.update((line["element"], line["hidden_element"]))
        if changed:
            for position in moving:
                line = changed["lines"][position - 1]
                targets.add(line["branch"])
                elements.add(line["element"])

        interactions = {row["actor"] + row["target"]: row for actor in actors for row in query(
            "SELECT actor, target, wuxing, same_branch, chong, he, target_stage "
            "FROM branch_interaction WHERE actor = ?", actor,
        ) if row["target"] in targets}

        return {
            "base": base, "changed": changed, "moving": moving, "day": day, "interactions": interactions,
            "strength": {row["element"]: row["state"] for row in query(
                "SELECT element, state FROM month_strength WHERE month_branch = ?", month,
            ) if row["element"] in elements},
            "roles": next(iter(query("SELECT yuanshen, jishen, choushen FROM yongshen_roles WHERE yongshen = ?",
                                     reading["role"])), None),
        }


def embed_data(document, script_id, data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    document, matches = re.subn(
        rf'(<script id="{script_id}" type="application/json">)[^<]*(</script>)',
        lambda match: match[1] + payload + match[2],
        document,
    )
    if matches != 1:
        raise ValueError(f"模板缺少唯一的 {script_id} 数据块")
    return document


def render_page(reading, sql):
    page = (ROOT / "templates" / "hexagram-view.html").read_text(encoding="utf-8")
    return embed_data(embed_data(page, "reading-data", reading), "chart-data", build_data(sql, reading))


DISCLAIMER = (
    "本页只分析用神及相关爻的力量与条件，不对所问具体事情作结果预言，以免误导。"
    "依据《增删卜易》体例与本次盘面资料，仅供参考；应期只给通道，不给保证。"
)


def reading_page(run, status, sql):
    from .interpretation import build_interpretation

    evidence = facts(run["entries"])
    chart = evidence.get("chart", {})
    calendar = evidence.get("calendar", {})
    boards = rows(chart, "hexagrams")
    verified = bool(boards) and run["steps"]["identify"]["state"] == "accepted"
    focus = run.get("focus") or {}
    judgments = [entry for entry in run["entries"] if entry["kind"] == "judgment"]
    pending = [entry["summary"] for entry in run["entries"] if entry["kind"] == "pending"]
    pending.extend(step["reason"] for step in run["steps"].values()
                   if step["state"] in ("partial", "blocked") and step.get("reason"))
    verdict = run.get("verdict") or {}
    interpretation = build_interpretation(run, evidence)
    reading = {
        "id": str(boards[0]["hexagram_id"]) if verified else "",
        "question": run["input"]["question"], "source": run["input"]["source"],
        "month": calendar.get("month_branch") or run["input"].get("month_branch", ""),
        "day": calendar.get("day_ganzhi") or run["input"].get("day_ganzhi", ""),
        "dayBranch": calendar.get("day_branch") or run["input"].get("day_branch", ""),
        "baseName": chart.get("base_name") or run["input"].get("base_name", ""),
        "mask": chart.get("move_mask") if verified else None,
        "role": focus.get("relative", ""), "primary": focus.get("primary"),
        "candidates": focus.get("candidates", []) if not focus.get("primary") else [],
        "status": STATUS[status["state"]], "pending": list(dict.fromkeys(pending)),
        "summary": " ".join(e["summary"] for e in judgments if e["step"] == "synthesis"
                            and e["topic"] in ("comparison", "conclusion")) or "尚无汇总结论。",
        "notes": [{"step": e["step"], "text": e["summary"]} for e in judgments
                  if e["step"] in ("focus", "change", "strength", "timing")],
        "disclaimer": DISCLAIMER,
        "falsifier": verdict.get("falsifier") or "",
        "interpretation": interpretation,
    }
    return render_page(reading, sql)
