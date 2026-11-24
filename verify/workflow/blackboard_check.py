"""Regression checks for Markdown-first readings and the 100 chart cases."""

import re
import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jingfang.orchestrator import Orchestrator
from jingfang.review import rows
from jingfang.rule_data import RuleData


def fixture(**changes):
    return dict({"question": "测试卦例中的岗位条件", "source": "合成验收卦例",
                 "base_name": "乾为天", "line_code": "111111", "moving_positions": [4],
                 "changed_name": "风天小畜", "month_branch": "辰", "day_ganzhi": "戊申",
                 "ask_timing": True}, **changes)


def judgment(refs, summary="按盘面记录该步骤的验收依据", **fields):
    return dict({"kind": "judgment", "summary": summary, "section": "操作",
                 "rule": "回查该爻及所用关系", "condition": "本次给定盘面", "refs": refs}, **fields)


class SequentialChecks(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="jingfang-reading-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.service = Orchestrator(self.directory)

    def start(self, case=None):
        status = self.service.start(case or fixture())
        path = Path(status["path"])
        self.assertTrue(path.is_file())
        self.assertEqual(status["next"], "identify")
        self.assertFalse((self.directory / "blackboard.sqlite3").exists())
        return status["run_id"], path

    def submit(self, run, step, entries=(), **fields):
        payload = dict({"state": "accepted", "skill_use": "applied", "entries": list(entries)}, **fields)
        return self.service.submit(run, step, payload)

    def context(self, run, step):
        context = self.service.context(run)
        self.assertEqual(context["step"], step)
        if context["skill_file"]:
            self.assertTrue(Path(context["skill_file"]).is_file())
        return context

    @staticmethod
    def fact(context, topic):
        return next(entry for entry in context["entries"] if entry["kind"] == "fact" and entry["topic"] == topic)

    def recognize_and_choose(self, run, position=4):
        self.assertEqual(self.submit(run, "identify")["next"], "focus")
        context = self.context(run, "focus")
        chart = self.fact(context, "chart")["id"]
        choice = {"relative": "官鬼", "primary": {"source": "base", "position": position}}
        result = self.submit(run, "focus", [judgment([chart], "按岗位取官鬼")], focus=choice)
        self.assertEqual(result["next"], "strength")

    def strength_and_change(self, run):
        context = self.context(run, "strength")
        relations = self.fact(context, "relations")["id"]
        self.submit(run, "strength", [judgment([relations], "按爻位依据日月查表")])
        context = self.context(run, "change")
        moves = self.fact(context, "moves")
        findings = [judgment([moves["id"]], topic="moving_line", position=row["position"],
                             changed_branch=row["changed_branch"])
                    for row in rows(moves["detail"], "change_board")]
        self.assertEqual(self.submit(run, "change", findings)["next"], "timing")

    def finish(self, run):
        context = self.context(run, "synthesis")
        refs = [entry["id"] for entry in context["entries"] if entry["kind"] == "judgment"]
        return self.submit(run, "synthesis", [judgment(refs, "所问事项的汇总判断",
                                                       skill="strength", topic="conclusion")])

    def test_career_chart_saves_each_step_to_same_markdown(self):
        career = fixture(base_name="雷风恒", line_code="011100", moving_positions=[3, 4, 5, 6],
                         changed_name="风水涣", changed_code="010011", month_branch="亥",
                         day_ganzhi="己亥", source_void=["辰", "巳"], ask_timing=False,
                         source_lines=[{"position": 3, "marker": "世", "stem_branch": "辛酉",
                                        "relative": "官鬼", "changed_stem_branch": "戊午", "spirit": "玄武"},
                                       {"position": 5, "moving": True, "changed_stem_branch": "辛巳",
                                        "changed_relative": "子孙"}])
        run, path = self.start(career)
        snapshot = path.read_bytes()
        self.recognize_and_choose(run, position=3)
        self.assertNotEqual(path.read_bytes(), snapshot)
        self.assertIn("风水涣", path.read_text(encoding="utf-8"))
        self.strength_and_change(run)
        self.assertEqual(self.context(run, "timing")["skip_reason"], "本次未询问应期")
        self.service.submit(run, "timing", {"state": "skipped"})
        result = self.finish(run)
        self.assertIsNone(result["next"])
        self.assertEqual(result["state"], "complete")
        self.assertEqual(Path(result["path"]), path)
        self.assertEqual(list(self.directory.glob("*.md")), [path])
        self.assertTrue(self.service.validate(run)["chart_replayed"])
        report = path.read_text(encoding="utf-8")
        for text in ("原图旬空 · 辰、巳", "### 看日月、世应和世用", "### 看动变", "### 按需看应期", "所问事项的汇总判断"):
            self.assertIn(text, report)

    def test_reject_out_of_order_and_invalid_findings(self):
        run, path = self.start()
        self.recognize_and_choose(run)
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "当前应执行 strength"):
            self.submit(run, "change")
        self.assertEqual(path.read_bytes(), before)
        context = self.context(run, "strength")
        calendar = self.fact(context, "calendar")["id"]
        with self.assertRaisesRegex(ValueError, "branches"):
            self.submit(run, "strength", [judgment([calendar], topic="day_void", branches=["子", "丑"])])
        self.assertEqual(path.read_bytes(), before)
        relations = self.fact(context, "relations")["id"]
        self.submit(run, "strength", [judgment([relations])])
        context = self.context(run, "change")
        moves = self.fact(context, "moves")["id"]
        with self.assertRaisesRegex(ValueError, "同位变爻"):
            self.submit(run, "change", [judgment([moves], topic="moving_line", position=4, changed_branch="申")])
        self.assertEqual(self.service.status(run)["next"], "change")

    def test_write_failure_keeps_previous_step_and_resumes(self):
        run, path = self.start()
        before = path.read_bytes()
        with patch.object(Path, "replace", side_effect=PermissionError("模拟落盘失败")):
            with self.assertRaisesRegex(PermissionError, "模拟落盘失败"):
                self.submit(run, "identify")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual({item.name for item in self.directory.iterdir()}, {path.name, "rule-versions"})
        self.service = Orchestrator(self.directory)
        self.assertEqual(self.service.status(run)["next"], "identify")
        self.submit(run, "identify")
        self.service = Orchestrator(self.directory)
        self.assertEqual(self.service.status(run)["next"], "focus")
        self.assertTrue(self.submit(run, "identify")["duplicate"])
        self.assertIn("风天小畜", path.read_text(encoding="utf-8"))

    def test_conflict_saved_and_corrected_in_same_log(self):
        run, path = self.start(fixture(changed_name="坤为地"))
        result = self.submit(run, "identify")
        self.assertEqual(result["steps"]["identify"]["state"], "blocked")
        self.assertIsNone(result["next"])
        self.assertEqual(self.service.validate(run)["state"], "partial")
        report = path.read_text(encoding="utf-8")
        self.assertIn("坤为地", report)
        self.assertIn("风天小畜", report)
        self.assertIn("不符", report)
        with self.assertRaisesRegex(ValueError, "本轮已停止"):
            self.submit(run, "focus")
        revised = self.service.revise(run, fixture(), "复核原图")
        self.assertEqual(Path(revised["path"]), path)
        self.assertEqual(revised["next"], "identify")
        self.assertEqual(self.submit(run, "identify")["next"], "focus")
        self.assertIn("复核原图", path.read_text(encoding="utf-8"))

    def test_timing_saved_before_summary_and_required_in_refs(self):
        run, path = self.start()
        self.recognize_and_choose(run)
        self.strength_and_change(run)
        context = self.context(run, "timing")
        self.assertIsNone(context["skip_reason"])
        with self.assertRaisesRegex(ValueError, "当前应执行 timing"):
            self.submit(run, "synthesis")
        timing = self.fact(context, "timing")["id"]
        self.submit(run, "timing", [judgment([timing], "以值合为应期候选")])
        self.assertIn("以值合为应期候选", path.read_text(encoding="utf-8"))
        context = self.context(run, "synthesis")
        refs = [entry["id"] for entry in context["entries"]
                if entry["kind"] == "judgment" and entry["step"] in ("change", "strength")]
        with self.assertRaisesRegex(ValueError, "引用已完成"):
            self.submit(run, "synthesis", [judgment(refs, skill="strength", topic="conclusion")])
        self.assertEqual(self.finish(run)["state"], "complete")

    def test_missing_day_stem_is_partial_and_does_not_block_summary(self):
        run, path = self.start(fixture(day_ganzhi=None, day_branch="申"))
        self.recognize_and_choose(run)
        calendar = self.fact(self.context(run, "strength"), "calendar")["id"]
        with self.assertRaisesRegex(ValueError, "缺有效日干支"):
            self.submit(run, "strength", [judgment([calendar], "确认旬空", topic="day_void")])
        self.strength_and_change(run)
        status = self.service.status(run)
        self.assertEqual(status["steps"]["strength"]["state"], "partial")
        self.assertIn("缺月建或完整日辰", self.context(run, "timing")["skip_reason"])
        self.service.submit(run, "timing", {"state": "skipped"})
        self.assertEqual(self.finish(run)["state"], "partial")
        self.assertIn("保留可确认的旺衰依据", path.read_text(encoding="utf-8"))

    def test_static_all_moving_and_bad_transcribed_rows(self):
        for positions, changed, flag in (([], "乾为天", None), (list(range(1, 7)), "坤为地", "反吟")):
            with self.subTest(positions=positions):
                run, _ = self.start(fixture(moving_positions=positions, changed_name=changed))
                self.submit(run, "identify")
                moves = self.fact(self.context(run, "focus"), "moves")["detail"]
                self.assertEqual([row["position"] for row in rows(moves, "change_board")], positions)
                self.assertEqual(rows(moves, "hexagram_change")[0]["gua_fanyin"], flag)
        run, path = self.start(fixture(source_void=["子", "丑"],
                                       source_lines=[{"position": 4, "changed_stem_branch": "辛午"}]))
        status = self.submit(run, "identify")
        self.assertEqual(status["steps"]["identify"]["state"], "blocked")
        report = path.read_text(encoding="utf-8")
        self.assertIn("原图旬空", report)
        self.assertIn("原图第 4 爻变爻干支", report)


class RecordedCases(unittest.TestCase):
    def test_100_chart_cases(self):
        sample = (ROOT / "docs" / "verification" / "jingfang-v5-100-case-check.md").read_text(encoding="utf-8")
        cases = re.findall(r"^\| (\d+) \| (\d+) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| "
                           r"([01]{6}) → ([01]{6}) \| (.+?) \|$", sample, re.M)
        self.assertEqual(len(cases), 100)
        moving_lines = 0
        with closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = sqlite3.Row
            db.executescript((ROOT / "gua.sql").read_text(encoding="utf-8"))
            db.execute("PRAGMA query_only = ON")
            for case, _, base, positions, changed, _, code, moved_code, pairs in cases:
                with self.subTest(case=case):
                    moving = [int(value) for value in positions.split(",")]
                    fields = {"base_name": base, "line_code": code, "moving_positions": moving,
                              "changed_name": changed, "changed_code": moved_code}
                    result, conflicts, missing = RuleData._board(db, fields, [])
                    self.assertEqual(conflicts + missing, [])
                    self.assertEqual(result["chart"]["changed_code"], moved_code)
                    actual = []
                    for row in rows(result["moves"], "change_board"):
                        left = "".join(row[f"base_{key}"] for key in ("polarity", "relative", "branch", "element"))
                        right = "".join(row[f"changed_{key}"] for key in ("polarity", "relative", "branch", "element"))
                        actual.append(f"{row['position']}爻 {left}→{right}")
                    self.assertEqual("；".join(actual), pairs)
                    moving_lines += len(actual)
        self.assertEqual(moving_lines, 167)


if __name__ == "__main__":
    unittest.main(verbosity=2)
