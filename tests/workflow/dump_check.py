"""Checks for read-only per-step dump and HTML export."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jingfang.dump import build_dump, render_html, render_text
from jingfang.orchestrator import STEPS, Orchestrator
from jingfang.review import rows


def fixture(**changes):
    return dict({"question": "测试卦例中的岗位条件", "source": "dump 验收卦例",
                 "base_name": "乾为天", "line_code": "111111", "moving_positions": [4],
                 "changed_name": "风天小畜", "month_branch": "辰", "day_ganzhi": "戊申",
                 "ask_timing": False}, **changes)


def judgment(refs, summary="按盘面记录该步骤的验收依据", **fields):
    return dict({"kind": "judgment", "summary": summary, "section": "操作",
                 "rule": "回查该爻及所用关系", "condition": "本次给定盘面", "refs": refs}, **fields)


class DumpChecks(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="jingfang-dump-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.service = Orchestrator(self.directory)

    def submit(self, run, step, entries=(), **fields):
        payload = dict({"state": "accepted", "skill_use": "applied", "entries": list(entries)}, **fields)
        return self.service.submit(run, step, payload)

    def complete_reading(self):
        status = self.service.start(fixture())
        run = status["run_id"]
        path = Path(status["path"])
        self.submit(run, "identify")
        context = self.service.context(run)
        chart = next(e for e in context["entries"] if e["kind"] == "fact" and e["topic"] == "chart")
        self.submit(run, "focus", [judgment([chart["id"]], "按岗位取官鬼")],
                    focus={"relative": "官鬼", "primary": {"source": "base", "position": 4}})
        context = self.service.context(run)
        relations = next(e for e in context["entries"] if e["kind"] == "fact" and e["topic"] == "relations")
        self.submit(run, "strength", [judgment([relations["id"]], "按爻位依据日月查表")])
        context = self.service.context(run)
        moves = next(e for e in context["entries"] if e["kind"] == "fact" and e["topic"] == "moves")
        findings = [judgment([moves["id"]], topic="moving_line", position=row["position"],
                             changed_branch=row["changed_branch"])
                    for row in rows(moves["detail"], "change_board")]
        self.submit(run, "change", findings)
        self.service.submit(run, "timing", {"state": "skipped"})
        context = self.service.context(run)
        refs = [entry["id"] for entry in context["entries"] if entry["kind"] == "judgment"]
        verdict = {
            "direction": "favorable",
            "layers": [{"name": "用神可立", "condition": "用神得生无破",
                        "status": "waiting", "refs": refs[:1]}],
            "falsifier": "若用神再受克破且原神无力，则本次偏吉判断不成立",
        }
        self.submit(run, "synthesis",
                    [judgment(refs, "用神侧汇总", skill="strength", topic="conclusion")],
                    verdict=verdict)
        return run, path

    def test_dump_has_six_steps_and_chart_fact(self):
        run, path = self.complete_reading()
        result = self.service.dump(run)
        payload = result["dump"]
        self.assertEqual(set(payload["steps"]), set(STEPS))
        identify = payload["steps"]["identify"]
        self.assertEqual(identify["state"], "accepted")
        topics = {item["topic"] for item in identify["facts"]}
        self.assertIn("chart", topics)
        self.assertIn("focus", payload["steps"]["focus"]["extras"])
        self.assertIsNotNone(payload["steps"]["focus"]["extras"]["focus"])
        self.assertIn("verdict", payload["steps"]["synthesis"]["extras"])
        text = render_text(payload)
        self.assertIn("认卦、查 SQL", text)
        self.assertIn(run, text)
        self.assertTrue(path.is_file())

    def test_dump_html_embeds_json(self):
        run, path = self.complete_reading()
        result = self.service.dump_html(run)
        html_path = Path(result["path"])
        self.assertTrue(html_path.is_file())
        self.assertEqual(html_path.name, f"{path.stem}-dump.html")
        html = html_path.read_text(encoding="utf-8")
        self.assertIn('id="dump-data"', html)
        self.assertIn(run, html)
        self.assertIn("分步产物", html)
        # embedded payload parses
        start = html.index('id="dump-data"')
        open_tag = html.index(">", start) + 1
        close = html.index("</script>", open_tag)
        payload = json.loads(html[open_tag:close])
        self.assertEqual(payload["run_id"], run)
        self.assertIn("chart", {f["topic"] for f in payload["steps"]["identify"]["facts"]})

    def test_dump_step_filter(self):
        run, _ = self.complete_reading()
        result = self.service.dump(run, step="focus")
        self.assertEqual(list(result["dump"]["steps"]), ["focus"])
        page = render_html(result["dump"])
        self.assertIn("取用神", page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
