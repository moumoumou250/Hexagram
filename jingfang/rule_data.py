"""Versioned, read-only access to Jingfang's existing rules and fixed board."""

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "identify": "jingfang-01-identify",
    "focus": "jingfang-02-focus",
    "strength": "jingfang-03-strength",
    "change": "jingfang-04-change",
    "timing": "jingfang-05-timing",
}
SKILL_PATHS = {step: f"skills/{name}/SKILL.md" for step, name in SKILLS.items()}
RULE_FILES = ("gua.sql", *SKILL_PATHS.values())
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
CHART_FIELDS = {
    "base_name", "line_code", "moving_positions", "changed_name", "changed_code",
    "month_branch", "day_ganzhi", "day_branch", "source_lines", "source_void",
}
SOURCE_LINE_FIELDS = {
    "position", "stem_branch", "relative", "marker", "hidden", "spirit", "moving",
    "changed_stem_branch", "changed_relative",
}


def rule_version(contents):
    digest = hashlib.sha256()
    for name, data in contents.items():
        digest.update(name.encode("ascii") + b"\0")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def freeze_rules(log_dir):
    contents = {name: (ROOT / name).read_bytes() for name in RULE_FILES}
    version = rule_version(contents)
    parent = log_dir / "rule-versions"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / version
    if not target.is_dir():
        with TemporaryDirectory(dir=parent) as directory:
            staged = Path(directory) / version
            for name, data in contents.items():
                path = staged / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            try:
                staged.rename(target)
            except OSError:
                if not target.is_dir():
                    raise
    return version


def rule_source(log_dir, version):
    """读取某次解卦冻结的规则副本。

    副本不可读（目录缺失、权限拒绝）时，仅当当前规则指纹与被引用版本完全一致才回退到
    当前规则；指纹不同则说明规则已改，回退会得到错误结论，因此直接报错。
    """
    if len(version) != 64 or any(char not in "0123456789abcdef" for char in version):
        raise ValueError("规则版本指纹无效")
    path = log_dir / "rule-versions" / version
    try:
        contents = {name: (path / name).read_bytes() for name in RULE_FILES}
    except OSError:
        contents = None
    if contents is not None:
        if rule_version(contents) != version:
            raise ValueError("本次规则副本的内容与版本指纹不符")
        return contents
    live = {name: (ROOT / name).read_bytes() for name in RULE_FILES}
    if rule_version(live) == version:
        return live
    # A Windows checkout may change text line endings. Accept only an exact hash match.
    lf = {name: data.replace(b"\r\n", b"\n") for name, data in live.items()}
    for candidate in (lf, {name: data.replace(b"\n", b"\r\n") for name, data in lf.items()}):
        if rule_version(candidate) == version:
            return candidate
    raise ValueError("规则副本不可读取，且当前规则已不是该版本，无法复算")


def chart_fields(data):
    fields = {}
    for key in CHART_FIELDS & data.keys():
        value = data[key]
        if value is None:
            continue
        if key == "source_lines":
            if not isinstance(value, list):
                raise ValueError("原图逐爻转录应为对象数组")
            lines = []
            for line in value:
                if (not isinstance(line, dict) or line.keys() - SOURCE_LINE_FIELDS
                        or type(line.get("position")) is not int or line["position"] not in range(1, 7)):
                    raise ValueError("原图逐爻转录需要 1 至 6 的爻位和有效字段")
                for name, item in line.items():
                    if name == "moving" and type(item) is not bool:
                        raise ValueError("原图动静标志应为 true 或 false")
                    if name not in ("position", "moving") and (not isinstance(item, str) or not item.strip()):
                        raise ValueError(f"原图爻位字段 {name} 应为非空文字")
                lines.append({name: item.strip() if isinstance(item, str) else item for name, item in line.items()})
            if len({line["position"] for line in lines}) != len(lines):
                raise ValueError("原图逐爻转录不能重复爻位")
            fields[key] = sorted(lines, key=lambda line: line["position"])
            continue
        if key == "source_void":
            if (not isinstance(value, list) or len(value) != 2 or value[0] == value[1]
                    or any(not isinstance(branch, str) or len(branch) != 1 or branch not in BRANCHES
                           for branch in value)):
                raise ValueError("原图旬空应为两个不同的地支")
            fields[key] = sorted(value, key=BRANCHES.index)
            continue
        if key == "moving_positions":
            if (not isinstance(value, list)
                    or any(type(position) is not int or position not in range(1, 7)
                           for position in value)
                    or len(value) != len(set(value))):
                raise ValueError("动爻位次应为 1 至 6 的无重复数组。明确静卦时使用空数组")
            fields[key] = sorted(value)
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} 应为非空文字")
        value = value.strip()
        if key.endswith("_code") and (len(value) != 6 or set(value) - {"0", "1"}):
            raise ValueError(f"{key} 应为从初爻到上爻的六位 0/1")
        if key.endswith("_branch") and (len(value) != 1 or value not in BRANCHES):
            raise ValueError(f"{key} 应为一个地支")
        fields[key] = value
    return fields


class RuleData:
    def __init__(self, sql):
        self.sql = sql

    def board(self, supplied, interpreted):
        fields = chart_fields(supplied)
        conflicts = []
        for name, value in chart_fields(interpreted).items():
            if name in fields and fields[name] != value:
                conflicts.append(f"{name}：输入为 {fields[name]}，认卦记录为 {value}")
            else:
                fields[name] = value
        with closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = sqlite3.Row
            db.executescript(self.sql)
            db.execute("PRAGMA query_only = ON")
            return self._board(db, fields, conflicts)

    @staticmethod
    def _board(db, fields, conflicts):
        facts = {}

        def query(table, where="", values=(), order=""):
            sql = f"SELECT * FROM {table}"
            if where:
                sql += " WHERE " + where
            if order:
                sql += " ORDER BY " + order
            return {"table": table, "where": where, "params": list(values),
                    "rows": [dict(row) for row in db.execute(sql, values)]}

        name = fields.get("base_name")
        code = fields.get("line_code")
        by_name = query("hexagram_code", "name = ?", (name,)) if name else None
        by_code = query("hexagram_code", "code = ?", (code,)) if code else None
        identified = [item for item in (by_name, by_code) if item]
        base = (by_code or by_name or {"rows": []})["rows"]
        if any(not item["rows"] for item in identified):
            conflicts.append("本卦名或本卦爻画在规则库中查不到")
        if by_name and by_code and by_name["rows"] != by_code["rows"]:
            conflicts.append("本卦名称与六爻爻画不符")
        if base:
            name, code = base[0]["name"], base[0]["code"]
        moving = fields.get("moving_positions")
        month = fields.get("month_branch")
        day = fields.get("day_ganzhi")
        day_query = query("jiazi", "ganzhi = ?", (day,)) if day else None
        day_row = day_query["rows"] if day_query else []
        if day and not day_row:
            conflicts.append(f"日辰干支 {day} 在六十甲子中查不到")
        day_branch = fields.get("day_branch")
        if day_row:
            if day_branch and day_branch != day_row[0]["branch"]:
                conflicts.append("日支与日辰干支不符")
            day_branch = day_row[0]["branch"]
        calendar = {"month_branch": month, "day_ganzhi": day_row[0]["ganzhi"] if day_row else None,
                    "day_branch": day_branch, "void": [day_row[0]["kong_1"], day_row[0]["kong_2"]]
                    if day_row else None, "queries": [day_query] if day_query else []}
        if day_row:
            calendar["queries"].append(query("liushen", "day_stem = ?", (day_row[0]["stem"],), "position"))
        reported_void = fields.get("source_void")
        if reported_void:
            calendar["reported_void"] = reported_void
            if calendar["void"] and set(reported_void) != set(calendar["void"]):
                conflicts.append(f"原图旬空 {'、'.join(reported_void)} 与日辰所查 {'、'.join(calendar['void'])} 不符")
        facts["calendar"] = calendar
        if not base or moving is None:
            missing = []
            if not base:
                missing.append("本卦名或六画")
            if moving is None:
                missing.append("动爻位次或明确静卦")
            return facts, conflicts, missing

        mask = sum(1 << (position - 1) for position in moving)
        flipped = "".join(str(1 - int(bit)) if position in moving else bit
                          for position, bit in enumerate(code, start=1))
        independent = query("hexagram_code", "code = ?", (flipped,))
        transition = query("hexagram_change", "base_name = ? AND move_mask = ?", (name, mask))
        hexagram = query("hexagrams", "name = ?", (name,))
        board = query("hexagram_board", "name = ?", (name,), "position")
        changes = query("change_board", "base_name = ? AND move_mask = ?", (name, mask), "position")
        claimed = fields.get("changed_name")
        changed = independent["rows"][0]["name"] if independent["rows"] else None
        claimed_code = fields.get("changed_code")
        if changed and claimed and claimed != changed:
            conflicts.append(f"盘面变卦 {claimed} 与翻爻复算 {changed} 不符")
        if claimed_code and claimed_code != flipped:
            conflicts.append("盘面变卦六画与逐爻翻转结果不符")
        if (not changed or len(transition["rows"]) != 1
                or transition["rows"][0]["changed_name"] != changed
                or transition["rows"][0]["moving_count"] != len(moving)):
            conflicts.append("SQL 变卦或动爻数与逐爻翻转不符")
        if [row["position"] for row in changes["rows"]] != moving:
            conflicts.append("同位变爻集合与动爻位次不符")

        detail = hexagram["rows"][0] if hexagram["rows"] else {}
        lines = board["rows"]
        if ([line["position"] for line in lines] != list(range(1, 7))
                or "".join(str(int(line["polarity"] == "阳")) for line in lines) != code
                or [line["position"] for line in lines if line["shi_ying"] == "世"] != [detail.get("shi_line")]
                or [line["position"] for line in lines if line["shi_ying"] == "应"] != [detail.get("ying_line")]):
            conflicts.append("本卦固定盘的六画或世应不一致")
        for row in changes["rows"]:
            position = row["position"] - 1
            expected_polarity = "阳" if flipped[position] == "1" else "阴"
            if row["changed_name"] != changed or row["changed_polarity"] != expected_polarity:
                conflicts.append(f"第 {position + 1} 爻的变卦或阴阳与复算不符")

        observations = fields.get("source_lines", [])
        actual_lines = {line["position"]: line for line in lines}
        actual_moves = {line["position"]: line for line in changes["rows"]}
        spirits = {line["position"]: line["spirit"] for result in calendar["queries"]
                   if result["table"] == "liushen" for line in result["rows"]}
        checked = []
        for observation in observations:
            position = observation["position"]
            original = actual_lines.get(position, {})
            changed_line = actual_moves.get(position, {})
            expected = {
                "stem_branch": original.get("stem", "") + original.get("branch", ""),
                "relative": original.get("relative"), "marker": original.get("shi_ying"),
                "hidden": (original.get("hidden_relative") or "") + (original.get("hidden_branch") or "")
                + (original.get("hidden_element") or ""),
                "spirit": spirits.get(position), "moving": position in moving,
                "changed_stem_branch": changed_line.get("changed_stem", "") + changed_line.get("changed_branch", ""),
                "changed_relative": changed_line.get("changed_relative"),
            }
            matches = {}
            for field in sorted(observation.keys() - {"position"}):
                if field == "spirit" and not day_row:
                    matches[field] = "待核"
                    continue
                matches[field] = "一致" if observation[field] == expected[field] else "不符"
                if matches[field] == "不符":
                    labels = {"stem_branch": "本爻干支", "relative": "六亲", "marker": "世应",
                              "hidden": "伏神", "spirit": "六神", "moving": "动静",
                              "changed_stem_branch": "变爻干支", "changed_relative": "变爻六亲"}
                    conflicts.append(f"原图第 {position} 爻{labels[field]} {observation[field]} 与复算 {expected[field]} 不符；"
                                     f"核对 source_lines 中的 {field}，转录有误可用 revise 更正")
            checked.append({"position": position, "results": matches, "observed": observation})
        facts["chart"] = {
            "base_name": name, "line_code": code, "changed_name": changed, "changed_code": flipped,
            "reported_changed_name": claimed, "reported_changed_code": claimed_code,
            "moving_positions": moving, "move_mask": mask, "shi_line": detail.get("shi_line"),
            "ying_line": detail.get("ying_line"), "queries": [*identified, hexagram, board, independent, transition],
        }
        if checked:
            facts["chart"]["source_line_checks"] = checked
        facts["moves"] = {"moving_positions": moving, "queries": [changes, transition]}
        elements = {line["element"] for line in lines}
        targets = {line["branch"] for line in lines}
        targets.update(line["hidden_branch"] for line in lines if line["hidden_branch"])
        targets.update(row["changed_branch"] for row in changes["rows"])
        elements.update(line["hidden_element"] for line in lines if line["hidden_element"])
        elements.update(row["changed_element"] for row in changes["rows"])
        relations = []
        if month:
            relations.extend(query("month_strength", "month_branch = ? AND element = ?", (month, element))
                             for element in sorted(elements))
        for actor in sorted({branch for branch in (month, day_branch) if branch}):
            relations.extend(query("branch_interaction", "actor = ? AND target = ?", (actor, target))
                             for target in sorted(targets))
        facts["relations"] = {"queries": relations}
        facts["roles"] = {"queries": [query("yongshen_roles"), query("dizhi"), query("liuqin_rule"),
                                      query("wuxing_relation")]}
        if targets:
            clauses = ", ".join("?" for _ in targets)
            facts["timing"] = {"queries": [
                query("branch_interaction", f"target IN ({clauses}) AND (chong = 1 OR he = 1 OR same_branch = 1)",
                      sorted(targets), "target, actor"),
                query("changsheng", order="element, stage"),
            ]}
        return facts, conflicts, []
