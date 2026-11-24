"""Unit checks for judgment-summary chart claim audit."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jingfang.audit import audit_claims


def run_with(entries, chart=None, moves=None):
    chart = chart or {
        "shi_line": 6, "ying_line": 3, "moving_positions": [4],
        "queries": [{
            "table": "hexagram_board",
            "rows": [
                {"position": 3, "relative": "父母", "branch": "辰", "element": "土",
                 "hidden_relative": None, "hidden_branch": None, "hidden_element": None},
                {"position": 4, "relative": "妻财", "branch": "午", "element": "火",
                 "hidden_relative": "官鬼", "hidden_branch": "寅", "hidden_element": "木"},
                {"position": 5, "relative": "官鬼", "branch": "申", "element": "金",
                 "hidden_relative": None, "hidden_branch": None, "hidden_element": None},
            ],
        }],
    }
    moves = moves or {
        "moving_positions": [4],
        "queries": [{
            "table": "change_board",
            "rows": [
                {"position": 4, "changed_relative": "父母", "changed_branch": "未", "changed_element": "土"},
            ],
        }],
    }
    facts = [
        {"id": 1, "kind": "fact", "topic": "chart", "summary": "盘", "detail": chart, "refs": []},
        {"id": 2, "kind": "fact", "topic": "moves", "summary": "动", "detail": moves, "refs": []},
    ]
    return audit_claims({"entries": facts + entries})


class AuditChecks(unittest.TestCase):
    def test_base_relative_ok(self):
        result = run_with([{"id": 3, "kind": "judgment", "summary": "五爻官鬼持世", "refs": [1]}])
        self.assertEqual(result["conflicts"], [])

    def test_base_relative_conflict(self):
        result = run_with([{"id": 3, "kind": "judgment", "summary": "五爻妻财申金", "refs": [1]}])
        self.assertTrue(result["conflicts"])

    def test_changed_line(self):
        result = run_with([{"id": 3, "kind": "judgment", "summary": "四爻化父母未土", "refs": [2]}])
        self.assertEqual(result["conflicts"], [])

    def test_hidden_line(self):
        result = run_with([{"id": 3, "kind": "judgment", "summary": "四爻伏官鬼寅木", "refs": [1]}])
        self.assertEqual(result["conflicts"], [])

    def test_shi_ying(self):
        ok = run_with([{"id": 3, "kind": "judgment", "summary": "世在第六爻，应在第三爻", "refs": [1]}])
        bad = run_with([{"id": 3, "kind": "judgment", "summary": "世居第3爻", "refs": [1]}])
        self.assertEqual(ok["conflicts"], [])
        self.assertTrue(bad["conflicts"])

    def test_relative_branch_element(self):
        result = run_with([{"id": 3, "kind": "judgment", "summary": "官鬼申金临日", "refs": [1]}])
        self.assertEqual(result["conflicts"], [])
        bad = run_with([{"id": 3, "kind": "judgment", "summary": "官鬼亥水临日", "refs": [1]}])
        self.assertTrue(bad["conflicts"])

    def test_hua_guan_not_base(self):
        # 「化官鬼」应走变爻路由；本盘变爻是父母，故冲突
        result = run_with([{"id": 3, "kind": "judgment", "summary": "四爻化官鬼", "refs": [2]}])
        self.assertTrue(result["conflicts"])

    def test_multi_positions_without_relative(self):
        result = run_with([{"id": 3, "kind": "judgment", "summary": "五、上爻同动", "refs": [1]}])
        self.assertEqual(result["conflicts"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
