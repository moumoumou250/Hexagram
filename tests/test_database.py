"""Run SQLite integration checks in a temporary reading directory."""

import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jingfang import records
from jingfang.orchestrator import Orchestrator


class RecordChecks(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory(prefix="jingfang-record-test-")
        self.addCleanup(scratch.cleanup)
        self.directory = Path(scratch.name).resolve()
        self.service = Orchestrator(self.directory)

    def recognize(self, **changes):
        run_id = self.service.start(dict({
            "question": "测试岗位用神的盘面情况", "source": "数据库集成测试",
            "base_name": "乾为天", "moving_positions": [4], "month_branch": "辰", "day_ganzhi": "戊申",
        }, **changes))["run_id"]
        result = self.service.submit(run_id, "identify", {"state": "accepted", "skill_use": "applied"})
        self.assertNotIn("database_warning", result)
        return run_id

    def context(self, run_id):
        context = self.service.context(run_id)
        self.assertNotIn("database_warning", context)
        return context

    def submit(self, run_id, step, topic=None, structured=None, **extra):
        context = self.context(run_id)
        refs = [entry["id"] for entry in context["entries"] if entry["kind"] == "fact"]
        entry = {"kind": "judgment", "section": "操作", "summary": "根据本次查表核对位置",
                 "rule": "查表", "condition": "盘面可核", "refs": refs}
        if topic:
            entry["topic"] = topic
        if structured is not None:
            entry["record_judgment"] = structured
        result = self.service.submit(run_id, step, {"state": "accepted", "skill_use": "applied",
                                                     "entries": [entry], **extra})
        self.assertNotIn("database_warning", result)

    def test_candidate_sources_and_read_only_rule_database(self):
        for source in ("base", "changed", "hidden", "month", "day", "marker"):
            with self.subTest(source=source):
                run_id = self.recognize(base_name="天风姤" if source == "hidden" else "乾为天")
                data = self.context(run_id)["database"]
                self.assertEqual(len(data["v_yao"]), 6)
                targets = data["v_yong_candidates"]
                self.assertTrue(all(item["is_selected"] is None for item in targets))
                target = next(item for item in targets if
                              (item["shi_ying"] == "应" if source == "marker" else item["source"] == source))
                selection = {key: target[key] for key in ("source", "position")}
                self.submit(run_id, "focus", focus={
                    "relative": "世应" if source == "marker" else target["relative"], "primary": selection,
                })
                data = self.context(run_id)["database"]
                self.assertEqual(len(data["v_shi_ying"]), 1)
                picked = [item for item in data["v_yong_candidates"] if item["is_selected"]]
                self.assertEqual({key: picked[0][key] for key in selection}, selection)
                self.assertEqual(len(picked), 1)
                self.assertEqual(sum(item["is_selected"] for item in data["yongshen_judge"]),
                                 int(selection["position"] is not None))
        with records._open(self.directory, write=True, version=data["gua_record"]["rule_version"]) as db:
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                db.execute("CREATE TABLE fix.forbidden (test)")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            db.execute("UPDATE gua_record SET rule_version=? WHERE gua_id=?", ("0" * 64, run_id))
            self.assertIsNone(db.execute("SELECT 1 FROM v_gua WHERE gua_id=?", (run_id,)).fetchone())

    def test_database_lag_and_recovery_from_markdown(self):
        run_id = self.recognize()
        before = self.context(run_id)["database"]["gua_record"]["record_digest"]
        focus = {"relative": "官鬼", "primary": {"source": "base", "position": 4}}
        chart = next(item for item in self.context(run_id)["entries"] if item["topic"] == "chart")
        payload = {"state": "accepted", "skill_use": "applied", "focus": focus, "entries": [
            {"kind": "judgment", "summary": "按盘面选择官鬼", "section": "操作", "rule": "核对六亲",
             "condition": "事业类用神", "refs": [chart["id"]]},
        ]}
        with patch("jingfang.records.sync", side_effect=sqlite3.OperationalError("模拟数据库不可用")):
            result = self.service.submit(run_id, "focus", payload)
        self.assertIn("database_warning", result)
        context = self.context(run_id)
        self.assertEqual(context["step"], "strength")
        self.assertTrue(context["entries"])
        self.assertIsNone(context["database"])
        result = self.service.submit(run_id, "focus", payload)
        self.assertTrue(result["duplicate"])
        self.assertNotEqual(self.context(run_id)["database"]["gua_record"]["record_digest"], before)
        record = {"table": "month_day_judge", "source": "changed", "position": 3, "fields": {"overall": "有气"}}
        with self.assertRaisesRegex(ValueError, "爻层或爻位"):
            self.submit(run_id, "strength", structured=record)
        record["position"] = 4
        self.submit(run_id, "strength", structured=record)
        database = self.context(run_id)["database"]
        self.assertEqual(len(database["v_dong_effect"]), 5)
        self.assertEqual(database["month_day_judge"][0]["overall"], "有气")
        self.assertTrue(database["yuanji_judge"])
        self.assertEqual(self.service.backfill()["counts"], {"eligible": 1})
        self.assertEqual(self.service.backfill(apply=True)["counts"], {"unchanged": 1})
        _, latest = self.service.journal.load(run_id)
        self.assertEqual(self.context(run_id)["database"]["gua_record"]["record_digest"],
                         records.record_digest(latest))
        self.service.revise(run_id, dict(latest["input"], month_branch="卯"), "测试修订")
        with records._open(self.directory) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM gua_record").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM month_day_judge").fetchone()[0], 0)

    def test_ineligible_readings_are_reported_without_creating_database(self):
        self.recognize(day_ganzhi=None)
        self.recognize(changed_name="坤为地")
        result = self.service.backfill(apply=True)
        self.assertEqual(result["counts"], {"missing_fields": 1, "chart_conflict": 1})
        self.assertFalse((self.directory / records.DB_NAME).exists())

    def test_unreadable_rule_cache_is_rebuilt(self):
        run_id = self.recognize()
        version = self.context(run_id)["database"]["gua_record"]["rule_version"]
        cache = self.directory / "rule-databases" / f"{version}.sqlite3"
        self.assertTrue(cache.is_file())
        cache.write_bytes(b"not a sqlite database")
        self.assertFalse(records._usable_sqlite(cache))
        rebuilt = records._fixed_database(self.directory, version)
        self.assertEqual(rebuilt, cache)
        self.assertTrue(records._usable_sqlite(cache))
        self.assertTrue((self.directory / "rule-databases" / f"{version}.sqlite3.broken").is_file())
        self.assertEqual(len(self.context(run_id)["database"]["v_yao"]), 6)

    def test_incremental_migration_template(self):
        def migrate_to_2(db):
            db.execute("CREATE INDEX IF NOT EXISTS gua_record_created ON gua_record(created_at)")

        run_id = self.recognize()
        with patch.object(records, "SCHEMA_VERSION", 2), patch.object(
            records, "_migrations", return_value={2: migrate_to_2}
        ):
            with records._open(self.directory, write=True) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
                self.assertTrue(db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='index' AND name='gua_record_created'"
                ).fetchone())
                self.assertEqual(
                    db.execute("SELECT count(*) FROM gua_record WHERE gua_id=?", (run_id,)).fetchone()[0], 1
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)

