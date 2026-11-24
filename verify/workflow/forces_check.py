"""Baseline: program forces vs book-case tone. No pass threshold."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jingfang.forces import focus_from_case, forces
from jingfang.review import rows
from jingfang.rule_data import BRANCHES, RuleData
from verify.fixtures.book_cases import CASES

OUT_JSON = ROOT / "docs" / "verification" / "forces-baseline.json"
OUT_MD = ROOT / "docs" / "verification" / "forces-conflicts.md"
STEMS = "甲乙丙丁戊己庚辛壬癸"


def tone(text):
    text = text or ""
    bad = sum(mark in text for mark in ("凶", "卒", "病", "狱", "盗", "亡", "刑", "害", "死", "革职"))
    good = sum(mark in text for mark in ("吉", "得", "成", "愈", "见", "升", "救", "免", "财", "中式", "连捷", "蒙恩"))
    if bad and not good:
        return "凶"
    if good and not bad:
        return "吉"
    return "混"


def parse_day(value):
    if not value:
        return {}
    value = str(value).strip()
    if len(value) == 3 and value[0] in STEMS and value[1:] in BRANCHES:
        # e.g. unexpected 3-char; fall through
        pass
    if len(value) >= 2 and value[0] in STEMS and value[1] in BRANCHES:
        return {"day_ganzhi": value[:2]}
    if len(value) == 1 and value in BRANCHES:
        return {"day_branch": value}
    return {}


def pick_focus(case, evidence):
    board = list(rows(evidence.get("chart", {}), "hexagram_board"))
    for item in case.get("a") or ():
        if item[0] == "line":
            _, position, relative, branch = item
            line = next((row for row in board if row["position"] == position), None)
            if line and line["relative"] == relative:
                return focus_from_case(relative, position, line["branch"], line["element"])
    # fallback: first 用神 hint in judgment text
    for relative in ("父母", "官鬼", "妻财", "子孙", "兄弟"):
        if relative in (case.get("j") or ""):
            matches = [row for row in board if row["relative"] == relative]
            if len(matches) == 1:
                line = matches[0]
                return focus_from_case(relative, line["position"], line["branch"], line["element"])
            if matches:
                # prefer month-linked
                month = case.get("m")
                linked = [row for row in matches if row["branch"] == month]
                line = linked[0] if linked else matches[0]
                return focus_from_case(relative, line["position"], line["branch"], line["element"])
    return None


def expect_rootless(case):
    blob = f"{case.get('j', '')} {case.get('l', '')}"
    return "无根" in blob


def classify_row(row):
    notes = []
    if row.get("error"):
        return "error", notes
    if row.get("expect_rootless"):
        if row.get("primary_rooted") == "无根":
            notes.append("无根命中书例")
            return "aligned", notes
        notes.append("书言无根但程序未判无根")
        return "conflict", notes
    if row.get("tone") == "吉" and row.get("yuan_force") == "无力" and row.get("ji_force") == "有力":
        notes.append("吉断但元无力忌有力，需人工核")
        return "review", notes
    if row.get("tone") == "凶" and row.get("yuan_force") == "有力" and row.get("ji_force") == "无力":
        if row.get("primary_rooted") == "无根":
            notes.append("凶断且用神无根，元有力不救，口径可合")
            return "aligned", notes
        notes.append("凶断但元有力忌无力，需人工核")
        return "review", notes
    return "neutral", notes


def main():
    sql = (ROOT / "gua.sql").read_text(encoding="utf-8-sig")
    rules = RuleData(sql)
    rows_out = []
    for case in CASES:
        if not case.get("m"):
            rows_out.append({"id": case["id"], "error": "缺月建", "question": case.get("q")})
            continue
        day_fields = parse_day(case.get("d"))
        if not day_fields:
            rows_out.append({"id": case["id"], "error": "缺日辰", "question": case.get("q")})
            continue
        fields = {
            "base_name": case["base"],
            "moving_positions": case.get("mv") or [],
            "changed_name": case.get("label"),
            "month_branch": case["m"],
            **day_fields,
        }
        try:
            evidence, conflicts, missing = rules.board(fields, {})
        except Exception as error:  # noqa: BLE001
            rows_out.append({"id": case["id"], "error": str(error), "question": case.get("q")})
            continue
        if conflicts or missing or "chart" not in evidence:
            rows_out.append({
                "id": case["id"], "error": "board", "conflicts": conflicts,
                "missing": missing, "question": case.get("q"),
            })
            continue
        focus = pick_focus(case, evidence)
        if focus is None:
            rows_out.append({"id": case["id"], "error": "无法推定用神", "question": case.get("q")})
            continue
        detail = forces(evidence, focus)
        yuan = next((line for line in detail["lines"] if line.get("role") == "原神"), None)
        ji = next((line for line in detail["lines"] if line.get("role") == "忌神"), None)
        row = {
            "id": case["id"], "question": case.get("q"), "outcome": case.get("o"),
            "tone": tone(f"{case.get('o', '')} {case.get('j', '')}"),
            "focus": focus["relative"], "position": focus["primary"]["position"],
            "primary_rooted": detail.get("primary_rooted"),
            "primary_rooted_reasons": detail.get("primary_rooted_reasons"),
            "yuan_force": None if yuan is None else yuan.get("force"),
            "yuan_reasons": None if yuan is None else yuan.get("reasons"),
            "ji_force": None if ji is None else ji.get("force"),
            "ji_reasons": None if ji is None else ji.get("reasons"),
            "expect_rootless": expect_rootless(case),
            "label": case.get("l"),
        }
        kind, notes = classify_row(row)
        row["class"] = kind
        row["notes"] = notes
        rows_out.append(row)

    summary = {
        "count": len(rows_out),
        "ok": sum(1 for row in rows_out if "error" not in row),
        "errors": sum(1 for row in rows_out if "error" in row),
        "aligned": sum(1 for row in rows_out if row.get("class") == "aligned"),
        "conflict": sum(1 for row in rows_out if row.get("class") == "conflict"),
        "review": sum(1 for row in rows_out if row.get("class") == "review"),
        "rooted_none": sum(1 for row in rows_out if row.get("primary_rooted") == "无根"),
        "rows": rows_out,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 元忌力度与书例对照（基线，无通过阈值）",
        "",
        f"- 可排盘例数 · {summary['ok']} / {summary['count']}",
        f"- 程序判无根 · {summary['rooted_none']}",
        f"- 口径对齐 · {summary['aligned']} · 冲突 · {summary['conflict']} · 待核 · {summary['review']}",
        "",
        "| # | 问事 | 用神 | 根基 | 原神 | 忌神 | 书例调 | 分类 | 备注 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows_out:
        if row.get("error"):
            lines.append(f"| {row['id']} | {row.get('question', '')} | — | — | — | — | — | error | {row['error']} |")
            continue
        lines.append(
            f"| {row['id']} | {row.get('question', '')} | {row.get('focus')}@{row.get('position')} | "
            f"{row.get('primary_rooted') or '—'} | {row.get('yuan_force') or '—'} | "
            f"{row.get('ji_force') or '—'} | {row.get('tone')} | {row.get('class')} | "
            f"{'；'.join(row.get('notes') or ()) or '—'} |"
        )
    lines.extend(["", "冲突与待核仅作调参线索，不以通过率卡死。", ""])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_JSON.name} ok={summary['ok']} conflict={summary['conflict']} review={summary['review']}")
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
