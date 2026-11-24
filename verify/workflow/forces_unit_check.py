"""Focused unit checks for forces rooted / window aggregation."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jingfang.forces import build_windows, focus_from_case, forces
from jingfang.review import rows
from jingfang.rule_data import RuleData


class ForcesUnit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = RuleData((ROOT / "gua.sql").read_text(encoding="utf-8-sig"))

    def test_case3_yongshen_rootless(self):
        # 泽风大过，巳月乙未日：亥水父母月破日克 → 无根
        evidence, conflicts, missing = self.rules.board({
            "base_name": "泽风大过", "moving_positions": [5, 6], "changed_name": "火风鼎",
            "month_branch": "巳", "day_ganzhi": "乙未",
        }, {})
        self.assertEqual(conflicts + missing, [])
        board = list(rows(evidence["chart"], "hexagram_board"))
        hai = next(row for row in board if row["branch"] == "亥" and row["relative"] == "父母")
        focus = focus_from_case("父母", hai["position"], hai["branch"], hai["element"])
        detail = forces(evidence, focus)
        self.assertEqual(detail["primary_rooted"], "无根")
        self.assertIn("月破", detail["primary_rooted_reasons"])

    def test_window_confidence_high(self):
        findings = [
            ("judgment", "window", "午日逢值",
             {"branch": "午", "unit": "日", "channel": "值"}, [1]),
            ("judgment", "window", "午日冲墓",
             {"branch": "午", "unit": "日", "channel": "冲墓"}, [2]),
        ]
        detail = build_windows(findings)
        self.assertEqual(len(detail["windows"]), 1)
        self.assertEqual(detail["windows"][0]["confidence"], "high")
        self.assertEqual(set(detail["windows"][0]["channels"]), {"值", "冲墓"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
