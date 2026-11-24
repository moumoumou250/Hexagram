"""Audit chart claims embedded in judgment summaries."""

import re

from .review import facts, rows

POSITIONS = {"初": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "上": 6, "六": 6,
             "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}
RELATIVES = ("父母", "兄弟", "子孙", "妻财", "官鬼")
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = "木火土金水"
POS_RE = "|".join(re.escape(key) for key in ("初", "一", "二", "三", "四", "五", "上", "六"))
REL_RE = "|".join(RELATIVES)
SHI_POS_RE = "|".join(re.escape(key) for key in ("一", "二", "三", "四", "五", "六", "1", "2", "3", "4", "5", "6"))


def _route(fragment):
    if "伏" in fragment:
        return "hidden"
    if any(mark in fragment for mark in ("化", "变")):
        return "changed"
    return "base"


def _line_maps(evidence):
    base, hidden, changed = {}, {}, {}
    for line in rows(evidence.get("chart", {}), "hexagram_board"):
        base[line["position"]] = {
            "relative": line["relative"], "branch": line["branch"], "element": line["element"],
        }
        if line.get("hidden_relative"):
            hidden[line["position"]] = {
                "relative": line["hidden_relative"], "branch": line["hidden_branch"],
                "element": line["hidden_element"],
            }
    for line in rows(evidence.get("moves", {}), "change_board"):
        changed[line["position"]] = {
            "relative": line["changed_relative"], "branch": line["changed_branch"],
            "element": line["changed_element"],
        }
    return {"base": base, "hidden": hidden, "changed": changed}


def _conflict(entry_id, claim, expected, actual):
    return {"entry_id": entry_id, "claim": claim, "expected": expected, "actual": actual}


def audit_claims(run):
    evidence = facts(run.get("entries") or ())
    maps = _line_maps(evidence)
    chart = evidence.get("chart") or {}
    checked = 0
    conflicts = []
    pos_rel = re.compile(rf"({POS_RE})爻([^，。；]{{0,4}})({REL_RE})")
    rel_branch = re.compile(rf"({REL_RE})([{BRANCHES}])([{ELEMENTS}])")
    shi = re.compile(rf"世(?:在|居|临)?第?({SHI_POS_RE})爻")
    ying = re.compile(rf"应(?:在|居|临)?第?({SHI_POS_RE})爻")

    for entry in run.get("entries") or ():
        if entry.get("kind") != "judgment":
            continue
        summary = entry.get("summary") or ""
        entry_id = entry["id"]

        for match in pos_rel.finditer(summary):
            checked += 1
            position = POSITIONS[match.group(1)]
            relative = match.group(3)
            source = _route(match.group(2) + relative)
            actual = maps[source].get(position)
            claim = match.group(0)
            if actual is None:
                conflicts.append(_conflict(entry_id, claim, f"{source}第{position}爻存在", "无此爻资料"))
            elif actual["relative"] != relative:
                conflicts.append(_conflict(
                    entry_id, claim, f"{source}第{position}爻{actual['relative']}", relative
                ))

        for match in rel_branch.finditer(summary):
            checked += 1
            relative, branch, element = match.group(1), match.group(2), match.group(3)
            source = _route(summary[max(0, match.start() - 4):match.start()])
            claim = match.group(0)
            pool = maps[source].values()
            hit = next((row for row in pool
                        if row["relative"] == relative and row["branch"] == branch
                        and row["element"] == element), None)
            if hit is None:
                expected = "、".join(
                    f"{row['relative']}{row['branch']}{row['element']}" for row in pool
                ) or f"{source}无对应爻"
                conflicts.append(_conflict(entry_id, claim, expected, claim))

        for kind, pattern, key in (("世", shi, "shi_line"), ("应", ying, "ying_line")):
            for match in pattern.finditer(summary):
                checked += 1
                claimed = POSITIONS[match.group(1)]
                actual = chart.get(key)
                if actual is not None and claimed != actual:
                    conflicts.append(_conflict(
                        entry_id, match.group(0), f"{kind}在第{actual}爻", f"第{claimed}爻"
                    ))

    return {"checked": checked, "conflicts": conflicts}
