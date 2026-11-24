"""Rebuildable SQLite projection of the validated Markdown journal."""

import json
import sqlite3
from contextlib import closing, contextmanager
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from .review import LINE_LAYERS, RECORD_FIELDS, facts, rows
from .rule_data import ROOT, rule_source

SCHEMA_PATH = ROOT / "database" / "schema.sql"
SCHEMA_VERSION = 1
DB_NAME = "records.sqlite3"
STEP_QUERIES = {
    "focus": ("v_gua", "v_yao", "v_yong_candidates"),
    "strength": ("v_gua", "v_yao", "v_yong_candidates", "v_shi_ying", "yongshen_judge"),
    "change": ("v_yao", "v_dong_effect", "month_day_judge", "yongshen_judge", "yuanji_judge", "shi_ying_judge"),
    "timing": ("v_gua", "v_yao", "v_yong_candidates", "v_dong_effect", *RECORD_FIELDS),
    "synthesis": ("v_gua", "v_yong_candidates", "v_shi_ying", *RECORD_FIELDS),
}
ORDER_COLUMNS = {
    "v_yao": "position", "v_dong_effect": "actor_pos, target_pos",
    "v_yong_candidates": "source, position", "yongshen_judge": "position, layer",
    "month_day_judge": "position, layer", "kong_po_judge": "position, layer",
    "shi_ying_judge": "position, item", "yuanji_judge": "position, layer, shen_type",
}
JUDGMENT_KEYS = {
    "yuanji_judge": ("shen_type", "position", "layer"),
    "shi_ying_judge": ("item", "position"),
}


def record_digest(run):
    # Same ordering and key representation as the embedded journal state.
    data = json.dumps(run, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return sha256(data.encode("utf-8")).hexdigest()


def eligibility(run):
    evidence = facts(run["entries"])
    recognition = run["steps"]["identify"]
    if recognition["state"] == "blocked":
        reason = recognition.get("reason") or "认卦已中断"
        if "查表失败" in reason or recognition.get("skill_use") == "unavailable":
            return "rules_unavailable", reason
        if reason.startswith("缺少"):
            return "missing_fields", reason
        return "chart_conflict", reason
    if recognition["state"] != "accepted" or not evidence.get("chart"):
        return "missing_fields", "本卦或动静尚未验收"
    calendar = evidence.get("calendar", {})
    if not calendar.get("month_branch") or not calendar.get("day_ganzhi"):
        return "missing_fields", "缺少月建或完整日辰"
    return "eligible", ""


def _schema():
    return SCHEMA_PATH.read_text(encoding="utf-8").split("CREATE TEMP TABLE rule_scope", 1)


def _bootstrap_schema(db):
    tables, _ = _schema()
    if db.execute("SELECT 1 FROM sqlite_schema WHERE type='table' LIMIT 1").fetchone():
        raise ValueError("检测到未版本化的记录库，需先按原结构核对迁移")
    statement = ""
    for line in tables.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            db.execute(statement)
            statement = ""


def _migrations():
    """Target version → migration callable. Bump SCHEMA_VERSION when adding one.

    Example for the next real change::

        def _migrate_to_2(db):
            db.execute("CREATE INDEX IF NOT EXISTS gua_record_created ON gua_record(created_at)")

        return {2: _migrate_to_2}
    """
    return {}


def _migrate(db, target=None):
    if target is None:
        target = SCHEMA_VERSION
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version == target:
        return
    if version > target:
        raise ValueError(f"记录库版本 {version} 高于程序支持的 {target}")
    db.execute("BEGIN IMMEDIATE")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        _bootstrap_schema(db)
        version = 1
    migrations = _migrations()
    while version < target:
        nxt = version + 1
        migrate = migrations.get(nxt)
        if migrate is None:
            raise ValueError(f"缺少到记录库版本 {nxt} 的迁移")
        migrate(db)
        version = nxt
    db.execute(f"PRAGMA user_version = {target}")
    db.commit()


def _usable_sqlite(path):
    try:
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as db:
            db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
        return True
    except (OSError, sqlite3.Error):
        return False


def _fixed_database(directory, version):
    # Validate the path component before checking for a cached database.
    if len(version) != 64 or any(char not in "0123456789abcdef" for char in version):
        raise ValueError("规则版本指纹无效")
    cache = directory / "rule-databases"
    database = cache / f"{version}.sqlite3"
    if database.is_file() and _usable_sqlite(database):
        return database
    sql = rule_source(directory, version)["gua.sql"].decode("utf-8-sig")
    cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=cache) as temp:
        staged = Path(temp) / database.name
        with closing(sqlite3.connect(staged)) as fixed:
            fixed.executescript(sql)
        if database.is_file():
            broken = database.with_suffix(".sqlite3.broken")
            broken.unlink(missing_ok=True)
            try:
                database.replace(broken)
            except OSError as error:
                if not _usable_sqlite(database):
                    raise ValueError(f"规则缓存不可读且无法替换: {error}") from error
                return database
        try:
            staged.replace(database)
        except OSError:
            if not (database.is_file() and _usable_sqlite(database)):
                raise
    return database


@contextmanager
def _open(directory, *, write=False, version=None):
    path = directory / DB_NAME
    target = path.as_uri() + ("?mode=rwc" if write else "?mode=ro")
    with closing(sqlite3.connect(target, uri=True)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ValueError("SQLite 外键约束未启用")
        if write:
            _migrate(db)
        elif db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise ValueError("记录库版本不匹配")
        if version is not None:
            fixed = _fixed_database(directory, version)
            db.execute("ATTACH DATABASE ? AS fix", (fixed.as_uri() + "?mode=ro",))
            _, views = _schema()
            db.executescript("CREATE TEMP TABLE rule_scope" + views)
            db.execute("INSERT INTO rule_scope VALUES (?)", (version,))
            db.commit()
        yield db


def _upsert(db, table, key, values):
    columns = ", ".join((*key, *values))
    placeholders = ", ".join("?" for _ in range(len(key) + len(values)))
    updates = ", ".join(f"{column}=excluded.{column}" for column in values)
    db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
               f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {updates}",
               (*key.values(), *values.values()))


def _texts(entries, field="summary"):
    texts = (entry.get(field) for entry in entries)
    return "\n".join(dict.fromkeys(text for text in texts if text)) or None


def _verified(outcomes):
    results = {item.get("result") for item in outcomes}
    if results not in ({"met"}, {"unmet"}):
        return None
    result = next(iter(results))
    if any(layer.get("status") != result for item in outcomes for layer in item.get("layers", ())):
        return None
    return int(result == "met")


def sync(directory, run):
    state, _ = eligibility(run)
    run_id = run["id"]
    if state != "eligible":
        if (directory / DB_NAME).is_file():
            with _open(directory, write=True) as db:
                db.execute("DELETE FROM gua_record WHERE gua_id=?", (run_id,))
        return state

    version = run["rule_version"]
    evidence = facts(run["entries"])
    chart, calendar = evidence["chart"], evidence["calendar"]
    focus = run.get("focus") or {}
    primary = focus.get("primary") or {}
    entries = [entry for entry in run["entries"] if entry["kind"] == "judgment"]
    windows = [entry for entry in entries if entry["topic"] == "window"]
    outcomes = run.get("outcomes") or []
    summary = [entry for entry in entries if entry["topic"] in ("conclusion", "comparison")
               and entry["step"] == "synthesis"]
    values = {
        "rule_version": version, "revision": run["revision"], "record_digest": record_digest(run),
        "question": run["input"]["question"], "divine_time": run["input"].get("cast_time"),
        "month_branch": calendar["month_branch"], "day_ganzhi": calendar["day_ganzhi"],
        "hexagram_id": rows(chart, "hexagrams")[0]["hexagram_id"], "move_mask": chart["move_mask"],
        "yong_liuqin": focus.get("relative"), "yong_source": primary.get("source"),
        "yong_position": primary.get("position"),
        "yong_basis": _texts(entry for entry in entries if entry["step"] == "focus"),
        "ying_qi_basis": "、".join(dict.fromkeys(entry["detail"]["channel"] for entry in windows)) or None,
        "ying_qi": "、".join(dict.fromkeys(entry["detail"]["branch"] + entry["detail"]["unit"]
                                         for entry in windows)) or None,
        "verdict": (run.get("verdict") or {}).get("direction"), "verdict_text": _texts(summary),
        "verified": _verified(outcomes), "verify_note": _texts(outcomes, "note"), "created_at": run["created_at"],
    }
    with _open(directory, write=True, version=version) as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT record_digest FROM gua_record WHERE gua_id=?", (run_id,)).fetchone()
        if previous and previous[0] == values["record_digest"]:
            return "unchanged"
        _upsert(db, "gua_record", {"gua_id": run_id}, values)
        _verify_projection(db, run_id, evidence, focus)
        for table in RECORD_FIELDS:
            db.execute(f"DELETE FROM {table} WHERE gua_id=?", (run_id,))
        _sync_judgments(db, run_id, evidence, focus, values, entries, run["steps"])
    return "synced"


def _verify_projection(db, run_id, evidence, focus):
    chart = evidence["chart"]
    board = db.execute("SELECT base_name, changed_name, shi_line, ying_line FROM v_gua WHERE gua_id=?",
                       (run_id,)).fetchone()
    expected = tuple(chart[name] for name in ("base_name", "changed_name", "shi_line", "ying_line"))
    lines = db.execute("SELECT position, is_moving, changed_branch FROM v_yao WHERE gua_id=? ORDER BY position",
                       (run_id,)).fetchall()
    if board is None or tuple(board) != expected or len(lines) != 6:
        raise ValueError("查询库的月日、本卦或动变与冻结盘面不符")
    if [line["position"] for line in lines if line["is_moving"]] != chart["moving_positions"]:
        raise ValueError("查询库的动爻位次与冻结盘面不符")
    if ([(line["position"], line["changed_branch"]) for line in lines if line["is_moving"]]
            != [(line["position"], line["changed_branch"]) for line in rows(evidence["moves"], "change_board")]):
        raise ValueError("查询库的同位变爻与冻结盘面不符")
    projected = {tuple(row) for row in db.execute(
        "SELECT source, position, branch, element, is_selected FROM v_yong_candidates "
        "WHERE gua_id=? AND is_candidate=1", (run_id,)
    )}
    primary = focus.get("primary")
    expected_candidates = {
        (row["source"], row["position"], row["branch"], row["element"], None if primary is None else int(row == primary))
        for row in focus.get("candidates", ())
    }
    if projected != expected_candidates:
        raise ValueError("查询库的候选或主用神与已校验取用记录不符")


def _sync_judgments(db, run_id, evidence, focus, values, entries, steps):
    primary = focus.get("primary")
    for row in focus.get("candidates", ()):
        layer = LINE_LAYERS.get(row["source"])
        if layer is not None:
            _upsert(db, "yongshen_judge", {"gua_id": run_id, "position": row["position"], "layer": layer},
                    {"is_selected": None if primary is None else int(row == primary),
                     "select_reason": values["yong_basis"] if row == primary else None})
    role_columns = {"原神": "yuanshen", "忌神": "jishen", "仇神": "choushen"}
    roles = focus.get("roles") or {}
    if steps["strength"]["state"] in ("accepted", "partial"):
        for line in evidence.get("forces", {}).get("lines", ()):
            for role, column in role_columns.items():
                if roles.get(column) == line["relative"]:
                    key = {"gua_id": run_id, "shen_type": role, "position": line["position"], "layer": "本"}
                    _upsert(db, "yuanji_judge", key, {
                        "effective_force": line["force"], "force_reason": "、".join(line["reasons"] or []) or None,
                    })
    for entry in entries:
        record = entry["detail"].get("record_judgment")
        if record:
            table = record["table"]
            columns = record["fields"]
            key_columns = JUDGMENT_KEYS.get(table, ("position", "layer"))
            if table not in RECORD_FIELDS or columns.keys() - RECORD_FIELDS[table].keys() or set(key_columns) != record["key"].keys():
                raise ValueError("记录中的结构化判断字段无效")
            key = {"gua_id": run_id, **{name: record["key"][name] for name in key_columns}}
            if entry["topic"] == "window":
                previous = db.execute("SELECT ying_qi_channel FROM kong_po_judge "
                                      "WHERE gua_id=? AND position=? AND layer=?", tuple(key.values())).fetchone()
                if previous and previous[0]:
                    channels = [*previous[0].split("\n"), columns["ying_qi_channel"]]
                    columns = {"ying_qi_channel": "\n".join(dict.fromkeys(channels))}
            _upsert(db, table, key, {**columns, "remark": entry["summary"]})


def query(directory, run, step):
    if (step not in STEP_QUERIES or not (directory / DB_NAME).is_file()
            or eligibility(run)[0] != "eligible"):
        return None
    params = (run["id"], run["rule_version"], run["revision"], record_digest(run))
    with _open(directory, version=run["rule_version"]) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        row = db.execute("SELECT * FROM gua_record WHERE gua_id=? AND rule_version=? "
                         "AND revision=? AND record_digest=?", params).fetchone()
        if row is None:
            return None
        results = {}
        for table in STEP_QUERIES[step]:
            order = " ORDER BY " + ORDER_COLUMNS[table] if table in ORDER_COLUMNS else ""
            results[table] = [dict(item) for item in db.execute(
                f"SELECT * FROM {table} WHERE gua_id=?{order}", (run["id"],)
            )]
    return {"gua_record": dict(row), **results}

