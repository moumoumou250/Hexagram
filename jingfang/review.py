"""Checks on evidence, deterministic assertions and review eligibility."""

import re

from .rule_data import SKILL_PATHS


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


def flagged_items(evidence, focus, steps):
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
    for row in rows(evidence.get("moves", {}), "change_board"):
        if row["huitou"] == "回头克" or row["hua_he"]:
            flags.append(f"第 {row['position']} 爻含回头克或化合，复核对世用的影响")
    if any(row["gua_fanyin"] for row in rows(evidence.get("moves", {}), "hexagram_change")):
        flags.append("复核卦级反吟及其适用范围")
    flags.extend(reason for reason in steps if reason)
    return list(dict.fromkeys(flags))


def normalize_entries(payload, step, sources, visible, evidence, generated_refs):
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
        findings.append((kind, topic, summary, detail, refs))
    return findings
