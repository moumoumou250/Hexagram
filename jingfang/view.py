"""Build the standalone viewer from the selected rule version and reading."""

import json
import re
import sqlite3

from .review import facts, rows
from .report import STATUS
from .rule_data import ROOT


def build_data(sql):
    with sqlite3.connect(":memory:") as database:
        database.row_factory = sqlite3.Row
        database.executescript(sql)

        def query(sql):
            return map(dict, database.execute(sql))

        charts = {row["hexagram_id"]: dict(row, lines=[]) for row in query(
            "SELECT * FROM hexagrams ORDER BY hexagram_id"
        )}
        for line in query("SELECT * FROM hexagram_board ORDER BY hexagram_id, position"):
            charts[line.pop("hexagram_id")]["lines"].append(line)

        transitions = {}
        for row in query(
            "SELECT base_id, move_mask, changed_id, relation_change, "
            "inner_fanfu, outer_fanfu, gua_change, gua_fanyin FROM hexagram_change"
        ):
            key = f"{row.pop('base_id')}:{row.pop('move_mask')}"
            transitions[key] = dict(row, lines={})

        for row in query(
            "SELECT base_id, move_mask, position, changed_relative, huitou, "
            "hua_chong, hua_he, jin_tui, hua_stage, line_fanfu, fuyin_line FROM change_board"
        ):
            key = f"{row.pop('base_id')}:{row.pop('move_mask')}"
            position = row.pop("position")
            transitions[key]["lines"][position] = {
                field: value for field, value in row.items() if value
            }

        return {
            "charts": charts,
            "transitions": transitions,
            "branches": [row["branch"] for row in query("SELECT branch FROM dizhi ORDER BY seq")],
            "days": {row["ganzhi"]: row for row in query("SELECT * FROM jiazi ORDER BY seq")},
            "spirits": {f"{row['day_stem']}{row['position']}": row["spirit"]
                        for row in query("SELECT * FROM liushen")},
            "interactions": {row["actor"] + row["target"]: row
                             for row in query("SELECT * FROM branch_interaction")},
            "elements": {row["subject"] + row["object"]: row["relation"]
                         for row in query("SELECT * FROM wuxing_relation")},
            "strength": {row["month_branch"] + row["element"]: row["state"]
                         for row in query("SELECT * FROM month_strength")},
            "roles": {row["yongshen"]: row for row in query("SELECT * FROM yongshen_roles")},
        }


def embed_data(document, data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    document, matches = re.subn(
        r'(<script id="chart-data" type="application/json">)[^<]*(</script>)',
        lambda match: match[1] + payload + match[2],
        document,
    )
    if matches != 1:
        raise ValueError("Expected one embedded chart-data block")
    return document


def reading_page(run, status, sql):
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
    reading = {
        "id": str(boards[0]["hexagram_id"]) if verified else "",
        "question": run["input"]["question"], "source": run["input"]["source"],
        "month": calendar.get("month_branch") or run["input"].get("month_branch", ""),
        "day": calendar.get("day_ganzhi") or run["input"].get("day_ganzhi", ""),
        "dayBranch": calendar.get("day_branch") or run["input"].get("day_branch", ""),
        "baseName": chart.get("base_name") or run["input"].get("base_name", ""),
        "mask": chart.get("move_mask") if verified else None,
        "role": focus.get("relative", ""), "primary": focus.get("primary"),
        "status": STATUS[status["state"]], "pending": list(dict.fromkeys(pending)),
        "summary": " ".join(e["summary"] for e in judgments if e["step"] == "synthesis"
                            and e["topic"] in ("comparison", "conclusion")) or "尚无汇总结论。",
        "notes": [{"step": e["step"], "text": e["summary"]} for e in judgments
                  if e["step"] in ("focus", "change", "strength", "timing")],
    }
    page = (ROOT / "templates" / "hexagram-view.html").read_text(encoding="utf-8")
    marker = '<script type="application/json" id="reading-data">null</script>'
    if page.count(marker) != 1:
        raise ValueError("模板缺少唯一的 reading-data 插入位置")
    payload = json.dumps(reading, ensure_ascii=False).replace("<", r"\u003c")
    return embed_data(page, build_data(sql)).replace(marker, marker.replace("null", payload))
