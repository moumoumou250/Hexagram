"""Execute and resume a reading from its saved Markdown."""

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .journal import Journal
from .report import render, validate
from .review import facts, flagged_items, focus_choice, normalize_entries, words
from .rule_data import CHART_FIELDS, SKILL_PATHS, RuleData, chart_fields, freeze_rules, rule_source

STEPS = {
    "identify": "认卦、查 SQL",
    "focus": "取用神",
    "strength": "看日月、世应和世用",
    "change": "看动变",
    "timing": "按需看应期",
    "synthesis": "汇总答复",
}
FACT_LABELS = {
    "chart": "固定盘和变卦独立复算", "moves": "动爻与同位变爻",
    "calendar": "月建、日辰、旬空和六神查表", "relations": "月令旺衰与日月作用",
    "roles": "六亲、五行及用神对应关系", "timing": "冲合值及生旺墓绝候选",
}
STATES = {"pending", "accepted", "partial", "blocked", "skipped"}
TOPICS = {
    "identify": (),
    "focus": ("chart", "roles", "calendar", "moves", "relations"),
    "strength": ("chart", "calendar", "relations", "moves"),
    "change": ("chart", "calendar", "relations", "moves"),
    "timing": ("chart", "calendar", "relations", "moves", "timing"),
    "synthesis": ("chart", "calendar"),
}


def reading_input(payload):
    if not isinstance(payload, dict):
        raise ValueError("解卦输入应为 JSON 对象")
    allowed = CHART_FIELDS | {"question", "source", "cast_time", "timezone", "ask_timing", "comparison_targets"}
    if unknown := payload.keys() - allowed:
        raise ValueError(f"未知输入字段：{', '.join(sorted(unknown))}")
    normalized = chart_fields(payload)
    for name in ("question", "source"):
        normalized[name] = words(payload.get(name), name)
    for name in ("cast_time", "timezone"):
        if payload.get(name) is not None:
            normalized[name] = words(payload[name], name)
    ask_timing = payload.get("ask_timing", False)
    if type(ask_timing) is not bool:
        raise ValueError("ask_timing 应为 true 或 false")
    normalized["ask_timing"] = ask_timing
    targets = payload.get("comparison_targets", [])
    if not isinstance(targets, list):
        raise ValueError("comparison_targets 应为对象名称数组")
    normalized["comparison_targets"] = list(dict.fromkeys(words(value, "比较对象") for value in targets))
    return normalized



def next_step(steps):
    for step in STEPS:
        state = steps[step]["state"]
        if state == "blocked":
            return None
        if state == "pending":
            return step
    return None


def reading_state(run):
    if next_step(run["steps"]):
        return "running"
    for step, result in run["steps"].items():
        if result["state"] == "accepted":
            continue
        if step == "timing" and result["state"] == "skipped" and not run["input"]["ask_timing"]:
            continue
        return "partial"
    return "complete"


def timing_issue(run, evidence):
    if not run["input"]["ask_timing"]:
        return "本次未询问应期"
    calendar = evidence.get("calendar", {})
    if not calendar.get("month_branch") or not calendar.get("day_ganzhi"):
        return "缺月建或完整日辰，暂不推应期"
    if not (run["focus"] or {}).get("primary"):
        return "主用神待核，暂不推应期"
    if run["steps"]["change"]["state"] == "partial":
        return "动变条件仍待核，暂不推应期"
    return None


class Orchestrator:
    def __init__(self, directory):
        self.journal = Journal(directory)
        self.directory = self.journal.directory

    def start(self, payload):
        data = reading_input(payload)
        now = datetime.now(timezone(timedelta(hours=8)))
        run_id = uuid4().hex
        path = self.directory / f"{now:%Y-%m-%d_%H-%M-%S}_{run_id}.md"
        run = {
            "id": run_id, "input": data, "revision": 1, "rule_version": freeze_rules(self.directory),
            "created_at": now.isoformat(timespec="seconds"),
            "steps": {step: {"state": "pending"} for step in STEPS},
            "entries": [], "focus": None, "history": [], "last_entry": 0,
        }
        self._save(path, run)
        return self._status(path, run)

    def _load(self, run_id):
        path, run = self.journal.load(run_id)
        steps = run.get("steps")
        if (not isinstance(steps, dict) or set(steps) != set(STEPS)
                or any(not isinstance(item, dict) or item.get("state") not in STATES for item in steps.values())):
            raise ValueError("记录的解卦步骤状态无效")
        terminal = next_step(steps)
        if terminal is None:
            terminal = next((step for step in STEPS if steps[step]["state"] == "blocked"), None)
        if terminal is not None:
            following = list(STEPS)[list(STEPS).index(terminal) + 1:]
            if any(steps[step]["state"] != "pending" for step in following):
                raise ValueError("记录的解卦步骤顺序无效")
        return path, run

    @staticmethod
    def _status(path, run):
        return {"run_id": run["id"], "path": str(path), "state": reading_state(run),
                "next": next_step(run["steps"]), "revision": run["revision"], "rule_version": run["rule_version"],
                "steps": {step: {"label": label, **{
                    key: value for key, value in run["steps"][step].items() if key != "submission"
                }} for step, label in STEPS.items()}}

    @staticmethod
    def _expect(run, step):
        ready = next_step(run["steps"])
        if step != ready:
            raise ValueError(f"当前应执行 {ready or '无（本轮已停止或完成）'}，不能提交或读取 {step}")

    def status(self, run_id):
        path, run = self._load(run_id)
        return self._status(path, run)

    def context(self, run_id, step=None):
        _, run = self._load(run_id)
        step = next_step(run["steps"]) if step is None else step
        if step is None:
            raise ValueError("本轮已停止或完成，没有下一步")
        self._expect(run, step)
        version_path = self.directory / "rule-versions" / run["rule_version"]
        evidence = facts(run["entries"])
        info = {"run_id": run_id, "step": step, "input": run["input"],
                "skill_file": str(version_path / SKILL_PATHS[step]) if step in SKILL_PATHS else None,
                "entries": [entry for entry in run["entries"]
                            if entry["kind"] != "fact" or entry["topic"] in TOPICS[step]],
                "focus": run["focus"]}
        if step == "timing":
            info["skip_reason"] = timing_issue(run, evidence)
        if step == "synthesis":
            info["checks"] = flagged_items(evidence, run["focus"], ())
        return info

    def submit(self, run_id, step, payload):
        if step not in STEPS:
            raise ValueError(f"未知步骤 {step}")
        if not isinstance(payload, dict) or payload.get("state") not in STATES - {"pending"}:
            raise ValueError("提交需要 state，允许 accepted、partial、blocked 或应期的 skipped")
        signature = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))
        with self.journal.writer(run_id):
            path, run = self._load(run_id)
            current = run["steps"][step]
            if current.get("submission") == signature:
                return dict(self._status(path, run), duplicate=True)
            self._expect(run, step)
            self._apply(run, step, payload, signature)
            self._save(path, run)
            return self._status(path, run)

    def _apply(self, run, step, payload, signature):
        entries = run["entries"]
        evidence = facts(entries)
        state = payload["state"]
        reason = payload.get("reason")
        skill_use = payload.get("skill_use")
        generated = []

        def add(kind, topic, summary, detail, refs=()):
            run["last_entry"] += 1
            entry_id = run["last_entry"]
            entries.append({"id": entry_id, "step": step, "kind": kind,
                            "topic": topic, "summary": summary, "detail": detail, "refs": list(refs)})
            return entry_id

        if step == "timing" and (skip := timing_issue(run, evidence)):
            if state != "skipped":
                raise ValueError(f"{skip}，请提交 skipped")
            reason = skip
        elif state == "skipped":
            if step != "timing":
                raise ValueError("只有应期可提交 skipped")
            raise ValueError("本次有应期问题且盘面条件齐备，可用 partial 记录待核项")
        if state == "skipped":
            if payload.get("entries") or skill_use not in (None, "read"):
                raise ValueError("跳过应期时只记录原因和实际读取状态")
        else:
            sources = {} if state == "blocked" and not payload.get("entries") else rule_source(
                self.directory, run["rule_version"]
            )
            if state != "accepted" or reason is not None:
                reason = words(reason, "部分完成或中断的原因")
            if step in SKILL_PATHS and skill_use not in ("applied", "read", "unavailable"):
                raise ValueError("提交应报告 skill_use，允许 applied、read 或 unavailable")
            if step in SKILL_PATHS and state == "accepted" and skill_use != "applied":
                raise ValueError("完成步骤需应用对应 Skill")

            if step == "identify":
                interpreted = payload.get("chart", {})
                if not isinstance(interpreted, dict) or interpreted.keys() - CHART_FIELDS:
                    raise ValueError("chart 只接受盘面、日月和动爻字段")
                if state != "blocked":
                    try:
                        evidence, conflicts, missing = RuleData(sources["gua.sql"].decode("utf-8-sig")).board(
                            run["input"], interpreted
                        )
                    except sqlite3.Error as error:
                        evidence, conflicts, missing = {}, [f"查表失败：{error}"], []
                    if "chart" in evidence:
                        evidence["chart"]["transcription"] = interpreted
                    for topic, data in evidence.items():
                        generated.append(add("fact", topic, FACT_LABELS[topic], data))
                    if conflicts or missing:
                        state = "blocked"
                        reason = "；".join([*conflicts, *(f"缺少{field}" for field in missing)])
                if state == "partial":
                    state = "blocked"
                if state == "blocked":
                    add("pending", "chart", reason, {"transcription": interpreted}, generated)
            if step == "strength" and state == "accepted":
                calendar = evidence.get("calendar", {})
                if not calendar.get("month_branch") or not calendar.get("day_ganzhi"):
                    state, reason = "partial", "月建或完整日辰缺失，保留可确认的旺衰依据"
            if step == "focus":
                run["focus"] = focus_choice(payload.get("focus"), evidence, state)

            visible = [entry for entry in entries if entry["step"] != step]
            if step == "identify" and state == "blocked":
                findings = []
            else:
                findings = normalize_entries(payload, step, sources, visible, evidence, generated)
            judgments = [item for item in findings if item[0] == "judgment"]
            self._check_findings(run, step, state, skill_use, evidence, judgments)
            for kind, topic, summary, detail, refs in findings:
                add(kind, topic, summary, detail, refs)
            if state != "accepted" and step != "identify":
                add("pending", step, reason, {})

        run["steps"][step] = {"state": state, "reason": reason, "skill_use": skill_use, "submission": signature}

    @staticmethod
    def _check_findings(run, step, state, skill_use, evidence, judgments):
        if judgments and step in SKILL_PATHS and skill_use != "applied":
            raise ValueError("有判断条目时，应报告已应用对应 Skill")
        if step != "identify" and state == "accepted" and not judgments:
            raise ValueError("完成步骤需要至少一条有证据的判断")
        if step == "change" and state == "accepted":
            reported = {detail["position"] for _, topic, _, detail, _ in judgments if topic == "moving_line"}
            if reported != set(evidence.get("moves", {}).get("moving_positions", ())):
                raise ValueError("完成动变应记录每个明动爻及其作用")
        conclusions = [item for item in judgments if item[1] in ("conclusion", "comparison")]
        if step == "synthesis" and state == "accepted" and not conclusions:
            raise ValueError("汇总应提交带 conclusion 或 comparison 主题的主结论")
        for _, topic, _, detail, refs in conclusions:
            if step == "synthesis":
                linked = {entry["step"] for entry in run["entries"]
                          if entry["id"] in refs and entry["kind"] == "judgment"}
                required = {name for name in ("strength", "change", "timing")
                            if run["steps"][name]["state"] == "accepted"}
                if not required <= linked:
                    raise ValueError("主结论需引用已完成的旺衰、动变和应期判断")
            if topic == "comparison":
                targets = run["input"]["comparison_targets"]
                compared = detail["compared_targets"]
                if (len(targets) < 2 or not isinstance(compared, list)
                        or any(not isinstance(target, str) for target in compared)
                        or sorted(compared) != sorted(targets)):
                    raise ValueError("排序结论需覆盖输入中的比较对象。资料不足时记录为待核")

    def revise(self, run_id, payload, reason):
        data = reading_input(payload)
        reason = words(reason, "更正原因")
        with self.journal.writer(run_id):
            path, run = self._load(run_id)
            if run["steps"]["synthesis"]["state"] in ("accepted", "partial"):
                raise ValueError("已汇总的卦例请用 start 创建新的记录")
            if run["input"] == data:
                raise ValueError("更正输入与原记录一致")
            run["history"].append({"revision": run["revision"], "input": run["input"], "reason": reason,
                                   "steps": {step: result["state"] for step, result in run["steps"].items()},
                                   "findings": [entry["summary"] for entry in run["entries"] if entry["kind"] != "fact"]})
            run.update(input=data, revision=run["revision"] + 1, focus=None, entries=[],
                       steps={step: {"state": "pending"} for step in STEPS})
            self._save(path, run)
            return self._status(path, run)

    def _save(self, path, run):
        self.journal.save(path, run, render(run, self._status(path, run)))

    def export_html(self, run_id):
        from .view import reading_page
        from .save_reading_log import save_markdown

        with self.journal.writer(run_id):
            path, run = self._load(run_id)
            validate(run, self.directory)
            status = self._status(path, run)
            sql = rule_source(self.directory, run["rule_version"])["gua.sql"].decode("utf-8-sig")
            destination = path.parent / "html" / path.with_suffix(".html").name
            save_markdown(reading_page(run, status, sql), destination)
            return {"run_id": run_id, "state": status["state"], "path": str(destination)}

    def validate(self, run_id):
        path, run = self._load(run_id)
        return dict(self._status(path, run), **validate(run, self.directory))
