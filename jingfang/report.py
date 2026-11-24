"""Replay recorded evidence and render one Markdown file per reading."""

import json

from .review import facts, rows
from .rule_data import SKILL_PATHS, RuleData, rule_source

STATUS = {
    "running": "进行中或中断", "complete": "完整", "partial": "部分完成",
    "pending": "待执行", "accepted": "已保存", "blocked": "已中断", "skipped": "已跳过",
}
SKILL_USE = {"applied": "已应用", "read": "已读取", "unavailable": "不可用"}


def validate(snapshot, directory):
    entries = {entry["id"]: entry for entry in snapshot["entries"]}
    if len(entries) != len(snapshot["entries"]):
        raise ValueError("记录包含重复的证据编号")
    for entry in entries.values():
        if any(ref not in entries or ref >= entry["id"] for ref in entry["refs"]):
            raise ValueError(f"条目 E{entry['id']} 引用了已失效或不属于本次的证据")
    evidence = facts(entries.values())
    known_chart = evidence.get("chart")
    if known_chart is not None:
        sources = rule_source(directory, snapshot["rule_version"])
        reconstructed, conflicts, missing = RuleData(sources["gua.sql"].decode("utf-8-sig")).board(
            snapshot["input"], known_chart["transcription"]
        )
        reconstructed["chart"]["transcription"] = known_chart["transcription"]
        if reconstructed != evidence:
            raise ValueError("本轮查表证据与冻结规则下的复算不一致")
        if snapshot["steps"]["identify"]["state"] == "accepted" and (conflicts or missing):
            raise ValueError("已验收盘面存在冲突或缺项")
    return {"entries": len(entries), "chart_replayed": known_chart is not None}


def _text(value):
    return str(value).replace("\r", "").replace("\n", " ").replace("|", "\\|")


def _fact_lines(entry):
    detail = entry["detail"]
    tables = list(dict.fromkeys(query["table"] for query in detail.get("queries", ())))
    source = " · ".join(f"`{table}`" for table in tables) or "按本次已提供的资料记录"
    details = ["", "<details>", f"<summary>E{entry['id']} {_text(entry['summary'])} · {source}</summary>", "",
               '~~~json', json.dumps(detail, ensure_ascii=False, indent=2), '~~~', "", "</details>"]
    return details


def _finding(entry, steps):
    detail = entry["detail"]
    role = steps[entry["step"]]["label"]
    label = "待核" if entry["kind"] == "pending" else role
    lines = [f"- **E{entry['id']} · {label}** {_text(entry['summary'])}"]
    if detail.get("skill"):
        lines.append(f"  - 规则 `{detail['skill']}` · {_text(detail['section'])} · {_text(detail['rule'])}")
    for key, name in (("condition", "条件"), ("exceptions", "例外")):
        if detail.get(key):
            lines.append(f"  - {name} · {_text(detail[key])}")
    if entry["refs"]:
        lines.append("  - 引用 · " + "、".join(f"E{ref}" for ref in entry["refs"]))
    return lines


def _daily_lines(evidence, focus):
    calendar = evidence.get("calendar", {})
    relations = evidence.get("relations", {})
    strength = {row["element"]: row["state"] for row in rows(relations, "month_strength")}
    interactions = {(row["actor"], row["target"]): row for row in rows(relations, "branch_interaction")}
    primary = (focus or {}).get("primary") or {}

    def relation(actor, target):
        record = interactions.get((actor, target))
        if not record:
            return "待核"
        effects = [record["wuxing"]]
        effects.extend(label for flag, label in (("same_branch", "临"), ("chong", "冲"), ("he", "合")) if record[flag])
        if record["target_stage"]:
            effects.append(record["target_stage"])
        return "、".join(effects)

    lines = ["| 爻位 | 本爻 | 世应与用神 | 月令 | 月建→本爻 | 日辰→本爻 | 旬空 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in sorted(rows(evidence["chart"], "hexagram_board"), key=lambda line: line["position"]):
        position, branch = row["position"], row["branch"]
        marker = [row["shi_ying"]] if row["shi_ying"] else []
        if primary.get("source") == "base" and primary.get("position") == position:
            marker.append("主用")
        month = relation(calendar.get("month_branch"), branch)
        day = relation(calendar.get("day_branch"), branch)
        voids = calendar.get("void")
        void = "待核" if voids is None else "空" if branch in voids else "不空"
        name = row["relative"] + row["stem"] + branch + row["element"]
        lines.append(f"| {position} | {name} | {'、'.join(marker) or '—'} | "
                     f"{strength.get(row['element'], '待核')} | {month} | {day} | {void} |")
    return lines


def render(snapshot, status):
    inputs = snapshot["input"]
    tasks = status["steps"]
    entries = snapshot["entries"]
    evidence = facts(entries)
    chart = evidence.get("chart", {})
    calendar = evidence.get("calendar", inputs)
    findings = [entry for entry in entries if entry["kind"] in ("judgment", "pending")]
    lines = ["# Jingfang 解卦记录", "", "## 1. 输入与状态", "",
             f"- 问题 · {_text(inputs['question'])}", f"- 来源 · {_text(inputs['source'])}",
             f"- 起卦时间与时区 · {_text(inputs.get('cast_time', '待核'))} / {_text(inputs.get('timezone', '待核'))}",
             f"- 月建 · {calendar.get('month_branch') or '待核'}",
             f"- 日辰 · {calendar.get('day_ganzhi') or calendar.get('day_branch') or '待核'}",
             f"- 旬空 · {'、'.join(calendar.get('void') or ()) or '待核'}",
             f"- 状态 · {STATUS[status['state']]}",
             f"- 下一步 · {tasks[status['next']]['label'] if status['next'] else '—'}",
             f"- 编号 · `{snapshot['id']}`，修订 {snapshot['revision']}，创建于 {snapshot['created_at']}",
             f"- 规则版本 · `{snapshot['rule_version']}`",
             "", "## 2. Skill 使用记录", "",
             "| 步骤 | Skill | 状态 | 备注 |", "| --- | --- | --- | --- |"]
    for step, task in tasks.items():
        skill = f"`{SKILL_PATHS[step]}`" if step in SKILL_PATHS else "汇总各步依据"
        usage = SKILL_USE.get(task.get("skill_use"))
        step_status = " · ".join(filter(None, (STATUS[task["state"]], usage)))
        lines.append(f"| {task['label']} | {skill} | {step_status} | {_text(task.get('reason') or '—')} |")
    lines.extend(["", "## 3. 排盘核对", ""])
    if calendar.get("reported_void"):
        lines.append(f"- 原图旬空 · {'、'.join(calendar['reported_void'])}")
    if chart:
        moving = "、".join(map(str, chart["moving_positions"])) or "静卦"
        lines.extend([f"- 本卦 · {chart['base_name']}（`{chart['line_code']}`）",
                      f"- 世应 · 世在第 {chart['shi_line']} 爻，应在第 {chart['ying_line']} 爻",
                      f"- 明动与动爻码 · {moving}，`move_mask={chart['move_mask']}`",
                      f"- 独立复算变卦 · {chart['changed_name']}（`{chart['changed_code']}`）",
                      f"- 来源所列变卦 · {chart['reported_changed_name'] or '未提供'}"
                      f"（{chart['reported_changed_code'] or '六画未提供'}）"])
        source_checks = chart.get("source_line_checks", [])
        if source_checks:
            lines.extend(["", "| 爻位 | 原图本爻 | 世应 | 动静 | 原图变爻 | 核对 |",
                          "| --- | --- | --- | --- | --- | --- |"])
            for item in source_checks:
                original = item["observed"]
                statuses = "、".join(dict.fromkeys(item["results"].values()))
                moving = "动" if original.get("moving") else "静" if "moving" in original else "—"
                lines.append(f"| {item['position']} | {_text(original.get('relative', '') + original.get('stem_branch', '')) or '—'} | "
                             f"{_text(original.get('marker', '—'))} | {moving} | "
                             f"{_text(original.get('changed_relative', '') + original.get('changed_stem_branch', '')) or '—'} | {statuses} |")
        fixed = rows(chart, "hexagram_board")
        if fixed:
            lines.extend(["", "| 爻位 | 六亲、干支与五行 | 世应 | 动静 |",
                          "| --- | --- | --- | --- |"])
            for item in sorted(fixed, key=lambda row: row["position"]):
                position = item["position"]
                moving = "动" if position in chart["moving_positions"] else "静"
                name = item["relative"] + item["stem"] + item["branch"] + item["element"]
                lines.append(f"| {position} | {name} | {item['shi_ying'] or '—'} | {moving} |")
    else:
        lines.append("- 本卦与动爻组合待核。")
    for entry in entries:
        if entry["kind"] == "fact":
            lines.extend(_fact_lines(entry))
    for entry in findings:
        if entry["step"] == "identify":
            lines.extend(_finding(entry, tasks))
    lines.extend(["", "## 4. 判断依据", ""])
    if snapshot["focus"]:
        focus = snapshot["focus"]
        lines.append(f"- 所取类别 · {focus['relative']}")
        entry = {"主用神": focus["primary"], "全部候选": focus["candidates"], "原忌仇": focus["roles"]}
        lines.extend(["", '~~~json', json.dumps(entry, ensure_ascii=False, indent=2), '~~~', ""])
    for step in ("focus", "strength", "change", "timing"):
        task = tasks[step]
        if task["state"] == "pending":
            continue
        lines.extend(["", f"### {task['label']}", ""])
        if step == "strength" and "chart" in evidence:
            lines.extend([*_daily_lines(evidence, snapshot["focus"]), ""])
        for entry in findings:
            if entry["step"] == step:
                lines.extend(_finding(entry, tasks))
        if task["state"] == "skipped":
            lines.append(f"- {_text(task['reason'])}")
    if snapshot["history"]:
        lines.extend(["", "<details>", "<summary>历次更正</summary>", ""])
        for item in snapshot["history"]:
            lines.append(f"- 第 {item['revision']} 轮 · {_text(item['reason'])}")
            lines.extend(["", '~~~json', json.dumps(item, ensure_ascii=False, indent=2), '~~~', ""])
        lines.append("</details>")
    lines.extend(["", "## 5. 结论与待核项", ""])
    for entry in findings:
        if entry["step"] == "synthesis":
            lines.extend(_finding(entry, tasks))
    if not any(entry["step"] == "synthesis" and entry["kind"] == "judgment" for entry in findings):
        lines.append("- 当前尚无汇总结论。")
    for task in tasks.values():
        if task.get("reason") and task["reason"] != "本次未询问应期":
            lines.append(f"- {task['label']} · {_text(task['reason'])}")
    return "\n".join(lines) + "\n"
