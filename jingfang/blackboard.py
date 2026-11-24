"""SQLite storage for isolated reading runs and append-only evidence."""

import json
import sqlite3
from contextlib import closing, contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    input TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    rule_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    report_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS tasks (
    run_id TEXT NOT NULL REFERENCES runs(id),
    step TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'running', 'accepted', 'partial', 'blocked', 'skipped')),
    attempt INTEGER NOT NULL DEFAULT 0,
    worker TEXT,
    token TEXT,
    expires REAL,
    submission TEXT,
    skill_use TEXT,
    reason TEXT,
    PRIMARY KEY (run_id, step)
);
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    step TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    author TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('fact', 'judgment', 'pending', 'event')),
    topic TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id, step) REFERENCES tasks(run_id, step),
    UNIQUE (run_id, id)
);
CREATE TABLE IF NOT EXISTS entry_refs (
    run_id TEXT NOT NULL,
    entry_id INTEGER NOT NULL,
    ref_id INTEGER NOT NULL CHECK (ref_id < entry_id),
    PRIMARY KEY (run_id, entry_id, ref_id),
    FOREIGN KEY (run_id, entry_id) REFERENCES entries(run_id, id),
    FOREIGN KEY (run_id, ref_id) REFERENCES entries(run_id, id)
);
CREATE INDEX IF NOT EXISTS entries_by_run ON entries(run_id, id);
"""


def encode(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False)


class Blackboard:
    def __init__(self, directory):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "blackboard.sqlite3"
        with closing(sqlite3.connect(self.path, timeout=15)) as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self, write=False):
        with closing(sqlite3.connect(self.path, timeout=15)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            with db:
                yield db

    @staticmethod
    def run(db, run_id):
        row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise ValueError(f"找不到解卦记录 {run_id}")
        return dict(row, input=json.loads(row["input"]))

    @staticmethod
    def tasks(db, run_id):
        return {row["step"]: dict(row) for row in
                db.execute("SELECT * FROM tasks WHERE run_id = ?", (run_id,))}

    @staticmethod
    def entries(db, run_id, history=False):
        rows = db.execute(
            """SELECT e.* FROM entries e JOIN tasks t ON t.run_id = e.run_id AND t.step = e.step
               WHERE e.run_id = ? AND
               (? OR e.kind = 'event' OR
                (e.attempt = t.attempt AND t.state IN ('accepted', 'partial', 'blocked')))
               ORDER BY e.id""",
            (run_id, int(history)),
        )
        refs = {}
        for row in db.execute("SELECT entry_id, ref_id FROM entry_refs WHERE run_id = ? ORDER BY ref_id", (run_id,)):
            refs.setdefault(row["entry_id"], []).append(row["ref_id"])
        return [dict(row, detail=json.loads(row["detail"]), refs=refs.get(row["id"], [])) for row in rows]

    @staticmethod
    def add(db, run_id, step, attempt, author, kind, topic, summary, detail, refs=()):
        inserted = db.execute(
            """INSERT INTO entries (run_id, step, attempt, author, kind, topic, summary, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, step, attempt, author, kind, topic, summary, encode(detail)),
        )
        db.executemany(
            "INSERT INTO entry_refs (run_id, entry_id, ref_id) VALUES (?, ?, ?)",
            ((run_id, inserted.lastrowid, ref) for ref in refs),
        )
        return inserted.lastrowid
