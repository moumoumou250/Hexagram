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
        change_rows = []
        if mask:
            transition, = query("SELECT changed_id FROM hexagram_change WHERE base_id = ? AND move_mask = ?",
                                base_id, mask)
            changed = chart(transition["changed_id"])
            change_rows = query(
                "SELECT position, changed_stem, changed_branch, changed_element, changed_relative, "
                "huitou, jin_tui, hua_stage, hua_chong, hua_he, fuyin_line "
                "FROM change_board WHERE base_id = ? AND move_mask = ?",
                base_id, mask,
            )
            moving = {row["position"]: row["changed_relative"] for row in change_rows}

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

        # 世应、动爻互作（不进 facts；仅供解读表第 10 列）
        pair_links = []
        shi_line = next((line for line in base["lines"] if line["shi_ying"] == "世"), None)
        ying_line = next((line for line in base["lines"] if line["shi_ying"] == "应"), None)
        pair_targets = []
        if shi_line and ying_line:
            pair_targets.append(("世应", shi_line["branch"], ying_line["branch"]))
        mover_branches = [
            (line["position"], line["branch"]) for line in base["lines"] if line["position"] in moving
        ]
        for index, (left_pos, left_branch) in enumerate(mover_branches):
            for right_pos, right_branch in mover_branches[index + 1:]:
                pair_targets.append((f"动{left_pos}-{right_pos}", left_branch, right_branch))
        for label, left, right in pair_targets:
            if not left or not right:
                continue
            hit = next(iter(query(
                "SELECT actor, target, wuxing, same_branch, chong, he, target_stage "
                "FROM branch_interaction WHERE actor = ? AND target = ?", left, right,
            )), None)
            chong = bool(query("SELECT 1 FROM dizhi_chong WHERE branch_a = ? AND branch_b = ?", left, right))
            he = bool(query("SELECT 1 FROM dizhi_he WHERE branch_a = ? AND branch_b = ?", left, right))
            pair_links.append({
                "label": label, "left": left, "right": right,
                "chong": int(chong or (hit or {}).get("chong") or 0),
                "he": int(he or (hit or {}).get("he") or 0),
                "wuxing": (hit or {}).get("wuxing"),
                "target_stage": (hit or {}).get("target_stage"),
            })
            if hit:
                interactions[left + right] = hit

        return {
            "base": base, "changed": changed, "moving": moving, "changes": change_rows,
            "day": day, "interactions": interactions, "pair_links": pair_links,
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
    detail_summary = " ".join(
        e["summary"] for e in judgments
        if e["step"] == "synthesis" and e["topic"] in ("comparison", "conclusion")
    ) or "尚无汇总结论。"
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
        "detail_summary": detail_summary,
        "notes": [{"step": e["step"], "text": e["summary"]} for e in judgments
                  if e["step"] in ("focus", "change", "strength", "timing")],
        "disclaimer": DISCLAIMER,
        "falsifier": verdict.get("falsifier") or "",
    }
    chart_data = build_data(sql, reading) if reading["id"] else {}
    interpretation = build_interpretation(run, evidence, chart_data=chart_data)
    reading["interpretation"] = interpretation
    reading["headline"] = interpretation.get("headline") or ""
    reading["summary"] = reading["headline"] or detail_summary
    return render_page(reading, sql)
