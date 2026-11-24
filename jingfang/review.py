"""Checks on evidence, deterministic assertions and review eligibility."""

import re

from .rule_data import BRANCHES, SKILL_PATHS

WINDOW_CHANNELS = {"值", "合", "冲", "填实", "冲墓", "当令", "克神受克", "化出之支值"}
WINDOW_UNITS = {"日", "月", "年"}
DIRECTIONS = {"favorable", "unfavorable", "mixed"}
LAYER_STATUS = {"met", "waiting", "unlikely"}
OUTCOME_RESULTS = {"met", "partial", "unmet", "unresolved"}
LAYER_STATUS_LABEL = {"met": "已备", "waiting": "待时", "unlikely": "难成"}
OUTCOME_LAYER_LABEL = {"met": "应", "partial": "部分", "unmet": "未应", "unresolved": "未决"}
DIRECTION_LABEL = {"favorable": "偏吉", "unfavorable": "偏凶", "mixed": "吉凶交错"}
LINE_LAYERS = {"base": "本", "changed": "变", "hidden": "伏"}
RECORD_FIELDS = {
    "yongshen_judge": {
        "select_reason": str, "fu_can_emerge": bool, "fu_reason": str, "ke_chu_feng_sheng": bool,
        "san_he_ju": str, "strength": ("旺", "有气", "衰而有救", "衰", "无用"),
    },
    "yuanji_judge": {
        "tan_sheng_wang_ke": bool, "yuan_ji_tong_dong": bool, "can_act_on_yong": bool,
        "effective_force": ("有力", "无力", "中和"), "force_reason": str,
    },
    "month_day_judge": {
        "day_chong_result": ("暗动", "日破", "冲散", "冲起", "冲开"),
        "overall": ("旺", "有气", "衰", "无用"),
    },
    "kong_po_judge": {
        "kong_nature": ("真空", "不为空", "待出空"), "po_nature": ("真破", "待出月填实"),
        "hua_effect": str, "du_fa_du_jing": ("独发", "独静"), "ying_qi_channel": str,
    },
    "shi_ying_judge": {
        "sui_gui_ru_mu": bool, "yong_to_shi": str, "jian_yao_block": bool, "shi_ying_judge": str,
    },
}
RECORD_TABLES = {
    "focus": {"yongshen_judge"},
    "strength": {"yongshen_judge", "yuanji_judge", "month_day_judge", "shi_ying_judge"},
    "change": {"kong_po_judge", "yuanji_judge", "shi_ying_judge"},
    "timing": {"kong_po_judge"},
}


def words(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} 应为非空文字")
    return value.strip()


def rows(evidence, table):
    return [row for query in evidence.get("queries", ()) if query["table"] == table for row in query["rows"]]


def facts(entries):
    return {entry["topic"]: entry["detail"] for entry in entries if entry["kind"] == "fact"}


def candidates(facts, relative):
    base = facts.get("chart", {})
    roles = facts.get("roles", {})
    candidates = []
    for line in rows(base, "hexagram_board"):
        for source, prefix in (("base", ""), ("hidden", "hidden_")):
            if line[prefix + "relative"] == relative:
                candidates.append({"source": source, "position": line["position"], "branch": line[prefix + "branch"],
                                   "element": line[prefix + "element"]})
    for line in rows(facts.get("moves", {}), "change_board"):
        if line["changed_relative"] == relative:
            candidates.append({"source": "changed", "position": line["position"], "branch": line["changed_branch"],
                               "element": line["changed_element"]})
    palace = next(iter(rows(base, "hexagrams")), {}).get("palace_element")
    elements = {row["branch"]: row["element"] for row in rows(roles, "dizhi")}
    by_element = {row["line_element"]: row["relative"] for row in rows(roles, "liuqin_rule")
                  if row["palace_element"] == palace}
    for source in ("month", "day"):
        branch = facts.get("calendar", {}).get(source + "_branch")
        element = elements.get(branch)
        if element and by_element.get(element) == relative:
            candidates.append({"source": source, "position": None, "branch": branch, "element": element})
    return candidates


def focus_choice(submitted, facts, state):
    if submitted is None and state != "accepted":
        return None
    if not isinstance(submitted, dict):
        raise ValueError("取用神应提供 focus 对象")
    relative = submitted.get("relative")
    roles = next((row for row in rows(facts.get("roles", {}), "yongshen_roles")
                  if row["yongshen"] == relative), None)
    if roles is None and relative != "世应":
        raise ValueError("focus.relative 应为规则库中的六亲，或填写 世应")
    options = candidates(facts, relative)
    primary = submitted.get("primary")
    if relative == "世应":
        options = [{"source": "base", "position": row["position"], "branch": row["branch"],
                    "element": row["element"], "marker": row["shi_ying"]}
                   for row in rows(facts["chart"], "hexagram_board") if row["shi_ying"] in ("世", "应")]
    if primary is not None:
        if not isinstance(primary, dict):
            raise ValueError("focus.primary 应提供 source 和 position")
        if primary.get("position") is not None and type(primary["position"]) is not int:
            raise ValueError("主用神爻位应为整数")
        primary = next((option for option in options if option["source"] == primary.get("source")
                        and option["position"] == primary.get("position")), None)
        if primary is None:
            raise ValueError("主用神的位置、来源或六亲与固定盘不符")
    if state == "accepted" and primary is None:
        raise ValueError("完成取用神需给出主用神。候选待定可提交 partial")
    return {"relative": relative, "candidates": options, "primary": primary, "roles": roles}


def record_judgment(value, step, topic, detail, evidence, focus):
    if not isinstance(value, dict) or not isinstance(value.get("table"), str):
        raise ValueError("record_judgment 应为含 table 和 fields 的对象")
    table = value["table"]
    fields = value.get("fields")
    if (table not in RECORD_TABLES.get(step, ()) or not isinstance(fields, dict) or not fields
            or fields.keys() - RECORD_FIELDS[table].keys()):
        raise ValueError("record_judgment 的表或判断字段不适用于本步骤")
    if step == "focus" and fields.keys() != {"select_reason"}:
        raise ValueError("取用步骤的候选记录只填写 select_reason")
    if step == "timing":
        channel = f"{detail.get('branch')}{detail.get('unit')}·{detail.get('channel')}"
        if topic != "window" or fields != {"ying_qi_channel": channel}:
            raise ValueError(f"应期记录仅可为本条通道填写 ying_qi_channel（{channel}）")
    position = value.get("position")
    if type(position) is not int:
        raise ValueError("record_judgment.position 应为整数")
    chart = evidence.get("chart", {})
    key = {"position": position}
    if table == "shi_ying_judge":
        item = value.get("item")
        shi, ying = sorted((chart["shi_line"], chart["ying_line"]))
        if not ((item in ("世", "应") and position == 0) or (item == "间爻" and shi < position < ying)):
            raise ValueError("世应判断应填世或应（位置 0），间爻应在世应之间")
        key["item"] = item
    else:
        source = value.get("source")
        if source not in tuple(LINE_LAYERS):
            raise ValueError("record_judgment.source 应为 base、changed 或 hidden")
        if source == "changed":
            lines = rows(evidence.get("moves", {}), "change_board")
            relative = next((row["changed_relative"] for row in lines if row["position"] == position), None)
        else:
            column = "hidden_relative" if source == "hidden" else "relative"
            relative = next((row[column] for row in rows(chart, "hexagram_board")
                             if row["position"] == position), None)
        if relative is None:
            raise ValueError("record_judgment 的爻层或爻位在本卦不存在")
        key["layer"] = LINE_LAYERS[source]
        focus = focus or {}
        if table == "yongshen_judge" and not any(
            row["source"] == source and row["position"] == position for row in focus.get("candidates", ())
        ):
            raise ValueError("用神判断的爻位和来源须在本次候选中")
        if table == "yuanji_judge":
            role = value.get("shen_type")
            column = {"原神": "yuanshen", "忌神": "jishen", "仇神": "choushen"}.get(role) if isinstance(role, str) else None
            if column is None or (focus.get("roles") or {}).get(column) != relative:
                raise ValueError("原忌仇判断的角色与该爻的六亲不符")
            key["shen_type"] = role
        if topic == "moving_line" and detail.get("position") != position:
            raise ValueError("动爻判断的爻位与本条明动记录不符")
    identity = (set(value) - {"table", "fields", "position"})
    target = {"item"} if table == "shi_ying_judge" else {"source"}
    if table == "yuanji_judge":
        target.add("shen_type")
    if identity != target:
        raise ValueError("record_judgment 的位置标识字段不适用于该表")
    clean = {}
    for name, field in fields.items():
        expected = RECORD_FIELDS[table][name]
        if expected is str:
            field = words(field, name)
        elif (expected is bool and type(field) is not bool) or (isinstance(expected, tuple) and field not in expected):
            raise ValueError(f"record_judgment.{name} 的值无效")
        clean[name] = field
    return {"table": table, "key": key, "fields": clean}


def flagged_items(evidence, focus, steps, run=None):
    flags = []
    if len((focus or {}).get("candidates", ())) > 1:
        flags.append("用神候选多现，核对取舍和影响")
    calendar = evidence.get("calendar", {})
    month = calendar.get("month_branch")
    day = calendar.get("day_branch")
    interactions = rows(evidence.get("relations", {}), "branch_interaction")
    if any(row["actor"] == month and row["target"] == day and row["chong"] for row in interactions):
        flags.append("月破遇临日，核对例外")
    if any(row["actor"] == day and row["chong"] for row in interactions):
        flags.append("日冲相关爻，核对暗动、日破和明动的前提")
    voids = calendar.get("void") or ()
    for row in rows(evidence.get("moves", {}), "change_board"):
        if row["huitou"] == "回头克" or row["hua_he"]:
            flags.append(f"第 {row['position']} 爻含回头克或化合，复核对世用的影响")
        if row.get("jin_tui"):
            flags.append(f"第 {row['position']} 爻{row['jin_tui']}，核对进退应期与力度")
        if row.get("hua_stage") in ("墓", "绝"):
            flags.append(f"第 {row['position']} 爻化{row['hua_stage']}，核对化墓化绝")
        if row.get("changed_branch") in voids:
            flags.append(f"第 {row['position']} 爻化空（变支{row['changed_branch']}），核对出空")
        if any(item["actor"] == month and item["target"] == row.get("changed_branch") and item["chong"]
               for item in interactions):
            flags.append(f"第 {row['position']} 爻化破（变支{row['changed_branch']}月破），核对出月")
    if any(row["gua_fanyin"] for row in rows(evidence.get("moves", {}), "hexagram_change")):
        flags.append("复核卦级反吟及其适用范围")

    moving = (evidence.get("chart") or {}).get("moving_positions") or ()
    if len(moving) == 1:
        flags.append("独发一爻，核对独发用神与应期")
    if len(moving) == 5:
        flags.append("五爻动独静一爻，核对独静取用")

    forces = evidence.get("forces") or {}
    if forces.get("primary_rooted") == "无根":
        flags.append("用神无根，元神有力亦难生，核对无根断法")
    for line in forces.get("lines") or ():
        if line.get("role") in ("原神", "忌神") and line.get("force") not in (None, "中和"):
            flags.append(f"{line['role']}第{line['position']}爻判定为{line['force']}（{'、'.join(line.get('reasons') or ())}）")

    for group in (evidence.get("sanhe") or {}).get("groups") or ():
        flags.append(f"{group['element']}局{'、'.join(group['branches'])}为{group['kind']}，核对三合虚实")

    voids = calendar.get("void") or ()
    primary = (focus or {}).get("primary") or {}
    shi = (evidence.get("chart") or {}).get("shi_line")
    board = {row["position"]: row for row in rows(evidence.get("chart", {}), "hexagram_board")}
    for label, position in (("用神", primary.get("position") if primary.get("source") == "base" else None),
                            ("世爻", shi)):
        if position is None:
            continue
        line = board.get(position)
        if not line:
            continue
        for actor in (month, day):
            hit = next((row for row in interactions if row["actor"] == actor and row["target"] == line["branch"]), None)
            if hit and hit.get("target_stage") == "墓":
                mu = next((row for row in rows(evidence.get("timing", {}), "changsheng")
                           if row["element"] == line["element"] and row["stage"] == "墓"), None)
                mu_branch = mu["branch"] if mu else None
                if mu_branch in voids:
                    flags.append(f"{label}入墓且墓库{mu_branch}落空，核对空墓")

    windows = (evidence.get("windows") or {}).get("windows") or ()
    if run and run.get("input", {}).get("ask_timing") and run.get("steps", {}).get("timing", {}).get("state") == "accepted":
        if not windows:
            flags.append("应期已完成但无 window 通道，核对应期落点")
        elif not any("当令" in item.get("channels", ()) or "填实" in item.get("channels", ()) for item in windows):
            flags.append("应期通道未见当令或填实，核对是否缺落点（告警不阻断）")

    if run and (verdict := run.get("verdict")):
        layers = verdict.get("layers") or ()
        if layers and all(layer.get("status") == "unlikely" for layer in layers) and verdict.get("direction") == "favorable":
            flags.append("全部层为难成却方向偏吉，核对一致性")

    flags.extend(reason for reason in steps if reason)
    return list(dict.fromkeys(flags))


def verdict_choice(submitted, judgment_ids, state, existing=None):
    if submitted is None:
        if state == "accepted":
            raise ValueError("完成汇总需提供 verdict（方向、分层与证伪条件）")
        return existing
    if not isinstance(submitted, dict):
        raise ValueError("verdict 应为对象")
    direction = submitted.get("direction")
    if direction not in DIRECTIONS:
        raise ValueError("verdict.direction 应为 favorable、unfavorable 或 mixed")
    layers = submitted.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("verdict.layers 不能为空")
    names = []
    available = set(judgment_ids or ())
    normalized = []
    for layer in layers:
        if not isinstance(layer, dict):
            raise ValueError("分层条目应为对象")
        name = words(layer.get("name"), "分层名称")
        if len(name) > 20:
            raise ValueError("分层名称不超过 20 字")
        if name in names:
            raise ValueError(f"分层名称重复：{name}")
        names.append(name)
        status = layer.get("status")
        if status not in LAYER_STATUS:
            raise ValueError("分层 status 应为 met、waiting 或 unlikely")
        condition = words(layer.get("condition"), "分层成立条件")
        refs = layer.get("refs", [])
        if not isinstance(refs, list) or not refs or any(type(ref) is not int for ref in refs):
            raise ValueError("每层 refs 必须指向已有判断编号")
        if any(ref not in available for ref in refs):
            raise ValueError(f"分层 {name} 引用了不存在的判断")
        normalized.append({"name": name, "condition": condition, "status": status, "refs": sorted(set(refs))})
    falsifier = words(submitted.get("falsifier"), "证伪条件")
    if not (10 <= len(falsifier) <= 120):
        raise ValueError("证伪条件长度应为 10–120 字")
    return {"direction": direction, "layers": normalized, "falsifier": falsifier}


def outcome_choice(payload, run):
    if run.get("steps", {}).get("synthesis", {}).get("state") != "accepted":
        raise ValueError("仅已汇总的记录可登记应验")
    if not isinstance(payload, dict):
        raise ValueError("应验登记应为 JSON 对象")
    checked_at = words(payload.get("checked_at"), "核对日期")
    result = payload.get("result")
    if result not in OUTCOME_RESULTS:
        raise ValueError("result 应为 met、partial、unmet 或 unresolved")
    declared = {layer["name"] for layer in (run.get("verdict") or {}).get("layers") or ()}
    layers = payload.get("layers", [])
    if not isinstance(layers, list):
        raise ValueError("layers 应为数组")
    normalized = []
    extras = []
    for layer in layers:
        if not isinstance(layer, dict):
            raise ValueError("应验层应为对象")
        name = words(layer.get("name"), "应验层名称")
        status = layer.get("status")
        if status not in OUTCOME_RESULTS:
            raise ValueError("应验层 status 应为 met、partial、unmet 或 unresolved")
        evidence = words(layer.get("evidence"), "应验证据")
        item = {"name": name, "status": status, "evidence": evidence}
        if name in declared:
            normalized.append(item)
        else:
            item["supplemental"] = True
            extras.append(item)
    note = payload.get("note")
    if note is not None:
        note = words(note, "应验备注")
    return {"checked_at": checked_at, "result": result, "layers": normalized,
            "supplemental_layers": extras, "note": note}


def normalize_entries(payload, step, sources, visible, evidence, generated_refs, focus=None):
    entries = payload.get("entries", [])
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("entries 应为对象数组")
    available = {entry["id"]: entry for entry in visible}
    for entry in generated_refs:
        available[entry] = {"kind": "fact"}
    grounded = set()
    for entry_id, entry in available.items():
        if entry["kind"] == "fact" or grounded.intersection(entry.get("refs", ())):
            grounded.add(entry_id)

    findings = []
    for entry in entries:
        kind = entry.get("kind")
        if kind not in ("judgment", "pending"):
            raise ValueError("条目类型为 judgment 或 pending。事实由查表生成")
        summary = words(entry.get("summary"), "条目摘要")
        topic = words(entry.get("topic", "general"), "条目主题")
        refs = entry.get("refs", list(generated_refs) if step == "identify" else [])
        if (not isinstance(refs, list) or any(type(ref) is not int or ref not in available for ref in refs)):
            raise ValueError("引用必须指向当次可用的上游条目")
        refs = sorted(set(refs))
        detail = {"condition": entry.get("condition"), "exceptions": entry.get("exceptions")}
        if kind == "judgment":
            if not grounded.intersection(refs):
                raise ValueError(f"判断缺少盘面证据引用：{summary}")
            skill = entry.get("skill", step if step in SKILL_PATHS else None)
            if not isinstance(skill, str) or skill not in SKILL_PATHS:
                raise ValueError("判断需标明使用的 Skill 步骤")
            if step in SKILL_PATHS and skill != step:
                raise ValueError("本步骤的判断应引用对应 Skill")
            section = words(entry.get("section"), "Skill 小节")
            headings = re.findall(r"^#{1,6}\s+([^\r\n]+)", sources[SKILL_PATHS[skill]].decode("utf-8-sig"), re.M)
            if section not in headings:
                raise ValueError(f"Skill {skill} 中找不到小节 {section}")
            detail.update(skill=SKILL_PATHS[skill], section=section,
                          rule=words(entry.get("rule"), "规则摘要"),
                          condition=words(entry.get("condition"), "适用条件"))
            if not evidence.get("calendar", {}).get("void") and (
                topic in ("day_void", "six_spirits") or re.search(r"旬空|空亡|出旬|化空", summary)
            ):
                raise ValueError("缺有效日干支时，旬空和六神应写为待核")
            if topic == "day_void":
                branches = entry.get("branches")
                expected = evidence["calendar"]["void"]
                if not isinstance(branches, list) or (branches != expected and branches != expected[::-1]):
                    raise ValueError("旬空条目的 branches 必须与当日查表的两个地支一致")
                detail["branches"] = expected
            if topic == "six_spirits":
                position = entry.get("position")
                spirit = entry.get("spirit")
                if type(position) is not int or not any(
                    line["position"] == position and line["spirit"] == spirit
                    for line in rows(evidence["calendar"], "liushen")
                ):
                    raise ValueError("六神条目的爻位或六神与日干查表结果不符")
                detail.update(position=position, spirit=spirit)
            if topic == "moving_line":
                position = entry.get("position")
                if type(position) is not int or position not in evidence.get("moves", {}).get("moving_positions", ()):
                    raise ValueError("明动条目的爻位必须出现在本卦动爻集合中")
                moving = next(line for line in rows(evidence["moves"], "change_board") if line["position"] == position)
                if entry.get("changed_branch") != moving["changed_branch"]:
                    raise ValueError(f"第 {position} 爻同位变爻 changed_branch 提交为 {entry.get('changed_branch')!r}，"
                                     f"与冻结规则复算的 {moving['changed_branch']} 不符。"
                                     "请核对本步字段；若原图转录有误，使用 revise 更正完整输入")
                detail.update(position=position, changed_branch=moving["changed_branch"])
            if topic == "comparison":
                detail["compared_targets"] = entry.get("compared_targets")
            if topic == "window":
                if step != "timing":
                    raise ValueError("window 条目仅用于应期步骤")
                branch = entry.get("branch")
                unit = entry.get("unit")
                channel = entry.get("channel")
                if branch not in BRANCHES:
                    raise ValueError("window.branch 必须是十二地支")
                if unit not in WINDOW_UNITS:
                    raise ValueError("window.unit 应为 日、月 或 年")
                if channel not in WINDOW_CHANNELS:
                    raise ValueError("window.channel 不在允许的通道枚举中")
                detail.update(branch=branch, unit=unit, channel=channel)
            if topic == "image":
                if step != "synthesis":
                    raise ValueError("image 条目仅用于汇总步骤")
                domain = words(entry.get("domain", "general"), "取象领域")
                elements = entry.get("elements", [])
                if not isinstance(elements, list) or not elements or any(not isinstance(item, str) or not item.strip()
                                                                         for item in elements):
                    raise ValueError("image.elements 应为非空字符串数组")
                if len(elements) < 2:
                    raise ValueError("取象须多象同向，孤象不入结论")
                detail.update(domain=domain, elements=[item.strip() for item in elements])
            if entry.get("force_override") is not None:
                override = entry.get("force_override")
                if override not in ("有力", "无力", "中和"):
                    raise ValueError("force_override 应为 有力、无力 或 中和")
                position = entry.get("position")
                if type(position) is not int:
                    raise ValueError("force_override 需同时提供 position")
                detail.update(force_override=override, override_reason=words(entry.get("override_reason"), "力度覆写原因"),
                              position=position)
            if "record_judgment" in entry:
                detail["record_judgment"] = record_judgment(entry["record_judgment"], step, topic, detail, evidence, focus)
        elif "record_judgment" in entry:
            raise ValueError("仅判断条目可填写 record_judgment")
        findings.append((kind, topic, summary, detail, refs))
    return findings
