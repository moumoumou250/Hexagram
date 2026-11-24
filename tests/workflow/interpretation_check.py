"""EL15 interpretation presets: yongshen-only, no matter prophecy."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jingfang.forces import focus_from_case, forces
from jingfang.interpretation import (
    assert_el15_text, build_headline, build_line_table, check_table, group_items,
    load_config, load_rules, match_presets,
)
from jingfang.review import rows
from jingfang.rule_data import RULE_FILES, RuleData


class InterpretationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = RuleData((ROOT / "database" / "gua.sql").read_text(encoding="utf-8-sig"))
        cls.forbidden = load_rules().get("forbidden_matter_terms") or ()

    def test_not_in_rule_fingerprint(self):
        self.assertTrue(all("jingfang-06-interpretation" not in name for name in RULE_FILES))

    def test_forbidden_matter_terms(self):
        with self.assertRaisesRegex(ValueError, "事项禁词"):
            assert_el15_text("用神有力，这次会升职。", self.forbidden)

    def _case3(self):
        evidence, conflicts, missing = self.rules.board({
            "base_name": "泽风大过", "moving_positions": [5, 6], "changed_name": "火风鼎",
            "month_branch": "巳", "day_ganzhi": "乙未",
        }, {})
        self.assertEqual(conflicts + missing, [])
        board = list(rows(evidence["chart"], "hexagram_board"))
        # 取初见父母亥（二爻），故意不用世位，便于测世应日月句
        hai = next(row for row in board if row["branch"] == "亥" and row["relative"] == "父母")
        self.assertNotEqual(hai["position"], evidence["chart"]["shi_line"])
        focus = focus_from_case("父母", hai["position"], hai["branch"], hai["element"])
        evidence["forces"] = forces(evidence, focus)
        return evidence, focus

    def test_case3_rootless_el15(self):
        evidence, focus = self._case3()
        blocks = match_presets(evidence, focus)
        texts = " ".join(block["text"] for block in blocks)
        self.assertIn("无根", texts)
        self.assertTrue(any(block["id"] == "R15" for block in blocks))
        for block in blocks:
            assert_el15_text(block["text"], self.forbidden)
            self.assertLessEqual(len(block["text"]), 80)

    def test_shi_ying_calendar_and_multi_moves(self):
        evidence, focus = self._case3()
        blocks = match_presets(evidence, focus)
        texts = [block["text"] for block in blocks]
        joined = " ".join(texts)
        self.assertTrue(any(text.startswith("世爻") for text in texts), joined)
        self.assertTrue(any(text.startswith("应爻") for text in texts), joined)
        r19 = [block for block in blocks if block["id"] == "R19"]
        self.assertTrue(r19, joined)
        self.assertIn("同动", r19[0]["text"])
        r11 = [block for block in blocks if block["id"] == "R11"]
        self.assertGreaterEqual(len(r11), 2, joined)
        non_primary_r11 = [block for block in r11 if not block["text"].startswith("用神")]
        self.assertTrue(non_primary_r11, joined)
        for block in blocks:
            assert_el15_text(block["text"], self.forbidden)

    def test_templates_are_short_and_plain(self):
        catalog = load_rules()
        for rule in catalog["rules"]:
            if not rule.get("enabled", True):
                continue
            template = rule["template"]
            self.assertNotRegex(template, r"据.+章故")
            self.assertIn("{", template + "{")  # has slots or is X01/X02 fixed
            for term in self.forbidden:
                self.assertNotIn(term, template)

    def _dui_case(self):
        evidence, conflicts, missing = self.rules.board({
            "base_name": "兑为泽", "moving_positions": [1, 5], "changed_name": "雷水解",
            "month_branch": "酉", "day_ganzhi": "辛亥",
        }, {})
        self.assertEqual(conflicts + missing, [])
        focus = focus_from_case("妻财", 2, "卯", "木")
        evidence["forces"] = forces(evidence, focus)
        run = {"focus": focus, "entries": [], "verdict": {}, "interpretation": {}}
        return evidence, focus, run

    def test_line_table_six_rows_and_shi_ying_dash(self):
        evidence, focus, run = self._dui_case()
        table = build_line_table(evidence, run)
        self.assertEqual(len(table["rows"]), 6)
        self.assertEqual(sorted(row["position"] for row in table["rows"]), list(range(1, 7)))
        checks = check_table(table, run, evidence["forces"])
        self.assertTrue(checks["ok"], checks["problems"])
        by_pos = {row["position"]: row for row in table["rows"]}
        self.assertEqual(by_pos[6]["force"], "—")
        self.assertEqual(by_pos[3]["force"], "—")
        self.assertEqual(by_pos[2]["key"], "用神")
        self.assertIn(by_pos[2]["force"], {"衰而有救", "衰", "无用", "待核", "有气", "旺"})
        for row in table["rows"]:
            for key in ("month_effect", "day_effect", "void", "change", "clash", "state", "force"):
                self.assertLessEqual(len(str(row.get(key) or "")), 14, (row["position"], key, row.get(key)))
            if row["key"] in ("世", "应") or row["attrs"] == "—":
                self.assertEqual(row["force"], "—")

    def test_headline_and_items_el15(self):
        evidence, focus, run = self._dui_case()
        table = build_line_table(evidence, run)
        headline = build_headline(evidence, focus, table=table)
        assert_el15_text(headline, self.forbidden)
        self.assertTrue(headline.startswith("用神"))
        blocks = match_presets(evidence, focus)
        items = group_items(blocks, evidence, focus, table=table)
        self.assertTrue(any(item["key"] == "用神" for item in items))
        for item in items:
            for line in item.get("lines") or ():
                assert_el15_text(line, self.forbidden)
        self.assertEqual(load_config().get("table_version"), "2.0")

    def test_choushen_in_forces_lines_filter(self):
        evidence, focus, run = self._dui_case()
        from jingfang.interpretation import build_interpretation
        payload = build_interpretation(run, evidence)
        roles = {line["role"] for line in payload["conclusions"]["forces_lines"]}
        self.assertIn("仇神", roles)


if __name__ == "__main__":
    unittest.main(verbosity=2)
