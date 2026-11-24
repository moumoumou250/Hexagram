"""Yongshen-only interpretation presets (EL15). Not a sixth reading step."""

import json
from pathlib import Path

from .review import rows

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "jingfang-06-interpretation"
WANG = {"旺", "相"}
TRUE_VOID_MONTH = {
    "寅": "土", "卯": "土", "巳": "金", "午": "金",
    "申": "木", "酉": "木", "亥": "火", "子": "火",
}
FORCE_HOW = {"有力": "有力", "无力": "没力", "中和": "力量一般"}
STRENGTH_GLOSS = {
    "旺": "月令最有气。",
    "相": "月令生它，也比较有气。",
    "休囚": "月令不帮它，偏弱。",
}
WUXING_PAIR = {
    "生": "前者生后者",
    "克": "前者克后者",
    "被生": "后者生前者",
    "被克": "后者克前者",
    "比和": "比和",
}
# 六爻判断表（EL15 table v2）
POS_TITLE = {1: "初爻", 2: "二爻", 3: "三爻", 4: "四爻", 5: "五爻", 6: "上爻"}
DASH = "—"
PENDING = "待核"
CELL_MAX = 14
WUXING_CELL = {"生": "生", "克": "克", "被生": "泄", "被克": "耗", "比和": "比和"}
YONG_STRENGTH = {"旺", "有气", "衰而有救", "衰", "无用"}
YUANJI_FORCE = {"有力", "无力", "中和"}
KONG_NATURE = {"真空", "不为空", "待出空"}
PO_NATURE = {"真破", "待出月填实"}
OVERALL_STATE = {"旺", "有气", "衰", "无用"}
MONTH_STATE = {"旺", "相", "休囚"}
MOVE_KIND = {"明动", "暗动", "静", "静·伏"}
TABLE_WHITELIST = (
    YONG_STRENGTH | YUANJI_FORCE | KONG_NATURE | PO_NATURE | OVERALL_STATE | MONTH_STATE
    | MOVE_KIND | set(WUXING_CELL.values()) | {
        DASH, PENDING, "派", "临", "月破", "日冲", "日破", "空", "化空", "退神", "进神",
        "回头生", "回头克", "化伏吟", "见绝", "见墓", "入墓", "长生", "帝旺", "与世相冲",
        "与世相合", "与应相冲", "与应相合", "动爻相冲", "动爻相合", "能作用", "不能作用",
        "作用待核", "旁爻", "用神", "原神", "忌神", "仇神", "世", "应", "仇神·世", "仇神·应",
        "用神·世", "用神·应", "原神·世", "原神·应", "忌神·世", "忌神·应",
    }
)


def load_config():
    return json.loads((SKILL_DIR / "config.json").read_text(encoding="utf-8"))


def load_rules():
    return json.loads((SKILL_DIR / "rules.json").read_text(encoding="utf-8"))


def _rule_map(catalog):
    return {rule["id"]: rule for rule in catalog["rules"]}


def _enabled_ids(config, catalog):
    enabled = set(config.get("enabled_blocks") or ())
    return [
        rule for rule in catalog["rules"]
        if rule["id"] in enabled and rule.get("enabled", True)
    ]


def assert_el15_text(text, forbidden):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("解读文案应非空")
    for term in forbidden:
        if term in text:
            raise ValueError(f"解读文案含事项禁词「{term}」，本页只分析用神")
    return text.strip()


def _primary_line(evidence, focus):
    primary = (focus or {}).get("primary") or {}
    if primary.get("source") != "base" or primary.get("position") is None:
        return None, primary
    line = next(
        (row for row in rows(evidence.get("chart", {}), "hexagram_board")
         if row["position"] == primary["position"]),
        None,
    )
    return line, primary


def _board_line(evidence, position):
    if position is None:
        return None
    return next(
        (row for row in rows(evidence.get("chart", {}), "hexagram_board")
         if row["position"] == position),
        None,
    )


def _interaction(evidence, actor, target):
    if not actor or not target:
        return {}
    return next(
        (row for row in rows(evidence.get("relations", {}), "branch_interaction")
         if row["actor"] == actor and row["target"] == target),
        {},
    )


def _month_state(evidence, element):
    return next(
        (row["state"] for row in rows(evidence.get("relations", {}), "month_strength")
         if row["element"] == element),
        None,
    )


def _move_at(evidence, position):
    return next(
        (row for row in rows(evidence.get("moves", {}), "change_board")
         if row["position"] == position),
        None,
    )


def _block(rule, text, *, derived, params=None):
    return {
        "id": rule["id"],
        "text": text,
        "status": rule.get("status", "fixed"),
        "source": rule.get("source", ""),
        "derived": derived,
        "params": params or {},
    }


def render_template(template, params):
    try:
        return template.format(**params)
    except KeyError as error:
        raise ValueError(f"解读模板缺参数 {error}") from error


def _line_label(position, *, primary_pos=None, shi=None, ying=None, relative=None):
    if primary_pos is not None and position == primary_pos:
        return "用神"
    if shi is not None and position == shi:
        return "世爻"
    if ying is not None and position == ying:
        return "应爻"
    if relative:
        return f"第{position}爻{relative}"
    return f"第{position}爻"


def _mover_label(line, *, primary_pos=None, shi=None, ying=None):
    base = _line_label(
        line["position"], primary_pos=primary_pos, shi=shi, ying=ying, relative=line.get("relative"),
    )
    branch = line.get("branch") or ""
    if base in ("用神", "世爻", "应爻"):
        return f"{base}{branch}" if branch else base
    return f"{base}{branch}" if branch and branch not in base else base


def _pair_relation(hit):
    bits = []
    wuxing = hit.get("wuxing")
    if wuxing in WUXING_PAIR:
        bits.append(WUXING_PAIR[wuxing])
    if hit.get("chong"):
        bits.append("相冲")
    if hit.get("he"):
        bits.append("相合")
    return "、".join(bits)


def match_presets(evidence, focus, *, derived=True):
    """Route A: derive preset blocks from board evidence + focus/forces."""
    config = load_config()
    catalog = load_rules()
    forbidden = catalog.get("forbidden_matter_terms") or ()
    rules = {rule["id"]: rule for rule in _enabled_ids(config, catalog)}
    line, primary = _primary_line(evidence, focus)
    primary_pos = primary.get("position") if primary.get("source") == "base" else None
    calendar = evidence.get("calendar") or {}
    month = calendar.get("month_branch")
    day = calendar.get("day_branch")
    voids = calendar.get("void") or ()
    chart = evidence.get("chart") or {}
    moving = set(chart.get("moving_positions") or ())
    shi = chart.get("shi_line")
    ying = chart.get("ying_line")
    forces_detail = evidence.get("forces") or {}
    blocks = []

    def add(rule_id, params):
        rule = rules.get(rule_id)
        if not rule:
            return
        text = assert_el15_text(render_template(rule["template"], params), forbidden)
        blocks.append(_block(rule, text, derived=derived, params=params))

    def emit_calendar_effects(who, target_line):
        if not target_line:
            return
        element = target_line["element"]
        branch = target_line["branch"]
        position = target_line["position"]
        state = _month_state(evidence, element)
        month_hit = _interaction(evidence, month, branch)
        day_hit = _interaction(evidence, day, branch)
        is_moving = position in moving
        wang = state in WANG
        resting = state == "休囚"

        if "R01" in rules and state:
            add("R01", {"who": who, "state": state, "gloss": STRENGTH_GLOSS.get(state, "")})

        if "R02" in rules and month_hit.get("chong"):
            if wang:
                how = "它本身旺，先看成「出了这个月再论破」。"
            elif resting:
                how = "它又休囚，这一层按没力看。"
            else:
                how = "先记下月破，再结合别的条件。"
            add("R02", {"who": who, "how": how})

        if "R04" in rules and month_hit.get("chong") and day_hit.get("same_branch"):
            add("R04", {"who": who})

        if "R05" in rules and day_hit.get("chong") and not is_moving:
            how = "月令还旺，结构上像被日辰叫醒（暗动结构）。" if wang else (
                "月令休囚，结构上偏日破。" if resting else "先记下日冲静爻。"
            )
            add("R05", {"who": who, "how": how})

        if "R06" in rules and is_moving and day_hit.get("chong"):
            add("R06", {"who": who})

        if "R07" in rules and branch in voids:
            if wang or is_moving:
                how = "它还旺或在动，先不当真空；等出空再看实。"
            elif TRUE_VOID_MONTH.get(month) == element and resting:
                how = "月令又休囚，接近真空，力量很虚。"
            elif month in ("丑", "未"):
                how = "丑未月真空映射待核，只作结构提示。"
            else:
                how = "先记下旬空，再看有没有生扶。"
            add("R07", {"who": who, "how": how})

        for actor_name, hit in (("月建", month_hit), ("日辰", day_hit)):
            stage = hit.get("target_stage")
            if "R08" in rules and stage in ("长生", "帝旺", "墓", "绝"):
                add("R08", {"who": who, "actor": actor_name, "stage": stage})
                break

    def emit_change_effects(who, move):
        if not move:
            return
        if "R11" in rules:
            bits = []
            if move.get("huitou"):
                bits.append(move["huitou"])
            if move.get("jin_tui"):
                bits.append(move["jin_tui"])
            if move.get("hua_stage"):
                bits.append("化" + move["hua_stage"])
            if move.get("changed_branch") in voids:
                bits.append("化空")
            if bits:
                add("R11", {"who": who, "effect": "、".join(bits)})
        if move.get("jin_tui") and "R13" in rules:
            add("R13", {"who": who, "kind": move["jin_tui"]})

    # 用神 / 世 / 应 / 原神 / 忌神 / 明动：日月结构（同位去重，用神优先）
    seen_positions = set()
    calendar_said = {}  # position -> set of reason tags already spoken

    def who_at(role_name, target_line):
        pos = target_line.get("position")
        title = POS_TITLE.get(pos, f"第{pos}爻") if pos else role_name
        branch = target_line.get("branch") or ""
        return f"{role_name}·{title}{branch}" if branch else f"{role_name}·{title}"

    def emit_calendar_dedup(who, target_line):
        if not target_line:
            return
        position = target_line["position"]
        before = len(blocks)
        emit_calendar_effects(who, target_line)
        said = calendar_said.setdefault(position, set())
        for block in blocks[before:]:
            if any(token in block["text"] for token in ("休囚", "旺", "相")):
                said.add("月令")
            if "月破" in block["text"]:
                said.add("月破")
            if "旬空" in block["text"]:
                said.add("旬空")
            if "日冲" in block["text"]:
                said.add("日冲")

    if line:
        emit_calendar_dedup(who_at("用神", line), line)
        seen_positions.add(line["position"])
    for who, position in (("世爻", shi), ("应爻", ying)):
        if position in seen_positions:
            continue
        target = _board_line(evidence, position)
        if not target:
            continue
        emit_calendar_dedup(who_at(who, target), target)
        seen_positions.add(position)

    role_map = {"原神": [], "忌神": []}
    for item in forces_detail.get("lines") or ():
        if item.get("role") in role_map and item.get("position") not in seen_positions:
            role_map[item["role"]].append(item)
    for role_name, items in role_map.items():
        for item in items:
            target = _board_line(evidence, item["position"])
            if not target:
                continue
            emit_calendar_dedup(who_at(role_name, target), target)
            seen_positions.add(item["position"])

    # 每位明动：日月（若未说过）+ 同位变对照
    for move in sorted(rows(evidence.get("moves", {}), "change_board"), key=lambda row: row["position"]):
        position = move["position"]
        board_line = _board_line(evidence, position) or {"position": position}
        who = who_at(
            _line_label(
                position,
                primary_pos=primary_pos,
                shi=shi,
                ying=ying,
                relative=board_line.get("relative"),
            ),
            board_line,
        )
        if position not in seen_positions:
            emit_calendar_dedup(who, board_line)
            seen_positions.add(position)
        emit_change_effects(who, move)

    if "R10" in rules and moving:
        add("R10", {})

    # 两动以上：只写动爻彼此
    if "R19" in rules and len(moving) >= 2:
        movers = sorted(
            (row for row in rows(evidence.get("chart", {}), "hexagram_board")
             if row["position"] in moving),
            key=lambda row: row["position"],
        )
        for index, left in enumerate(movers):
            for right in movers[index + 1:]:
                hit = _interaction(evidence, left["branch"], right["branch"])
                relation = _pair_relation(hit)
                if not relation:
                    continue
                add("R19", {
                    "a": _mover_label(left, primary_pos=primary_pos, shi=shi, ying=ying),
                    "b": _mover_label(right, primary_pos=primary_pos, shi=shi, ying=ying),
                    "relation": relation,
                })

    if "R15" in rules:
        rooted = forces_detail.get("primary_rooted")
        if rooted == "无根":
            reasons = "、".join(forces_detail.get("primary_rooted_reasons") or ())
            text = f"用神现在无根。{reasons + '，' if reasons else ''}原神再有力也难生起来。"
            add("R15", {"text": text})
        elif rooted == "有根":
            add("R15", {"text": "用神现在有根。自身还站得住。"})

    if "R14" in rules:
        seen_roles = set()
        for item in forces_detail.get("lines") or ():
            role = item.get("role")
            if role not in ("用神", "原神", "忌神", "仇神") or role in seen_roles:
                continue
            seen_roles.add(role)
            reasons = list(item.get("reasons") or ())
            # 去重：R01 已说过月令，则从 R14 原因里删掉旺/相/休囚字样
            pos = item.get("position")
            if pos in calendar_said and "月令" in calendar_said[pos]:
                reasons = [part for part in reasons if part not in ("旺", "相", "休囚", "月令旺", "月令相", "月令休囚")]
            reason = "、".join(reasons) or "盘面综合"
            add("R14", {
                "who": who_at(role, _board_line(evidence, pos) or {"position": pos, "branch": item.get("branch")}),
                "how": FORCE_HOW.get(item.get("force"), item.get("force") or "力量一般"),
                "reason": reason,
            })

    if "X01" in rules:
        add("X01", {})
    if "X02" in rules:
        add("X02", {})

    # stable order by enabled_blocks
    order = {rule_id: index for index, rule_id in enumerate(config.get("enabled_blocks") or ())}
    blocks.sort(key=lambda item: (order.get(item["id"], 999), item["id"], item["text"]))
    return blocks


def apply_rules_fired(submitted, evidence, focus):
    """Route B: validate optional synthesis rules_fired; fall back to match_presets."""
    catalog = load_rules()
    config = load_config()
    forbidden = catalog.get("forbidden_matter_terms") or ()
    by_id = _rule_map(catalog)
    enabled = set(config.get("enabled_blocks") or ())
    if submitted is None:
        return match_presets(evidence, focus, derived=True)
    if not isinstance(submitted, list):
        raise ValueError("rules_fired 应为对象数组")
    derived = match_presets(evidence, focus, derived=True)
    derived_ids = {item["id"] for item in derived}
    blocks = []
    for item in submitted:
        if not isinstance(item, dict):
            raise ValueError("rules_fired 条目应为对象")
        rule_id = item.get("rule_id")
        if rule_id not in by_id:
            raise ValueError(f"未知 rule_id：{rule_id}")
        if rule_id not in enabled or not by_id[rule_id].get("enabled", True):
            raise ValueError(f"rule_id {rule_id} 未启用")
        rule = by_id[rule_id]
        params = item.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError("rules_fired.params 应为对象")
        # Only accept rules the board also supports, unless template is self-contained
        if rule.get("trigger") not in ("manual", "always_once") and rule_id not in derived_ids:
            raise ValueError(f"{rule_id} 与当前盘面未命中，不能写入 rules_fired")
        if "text" in params:
            text = assert_el15_text(params["text"], forbidden)
        else:
            text = assert_el15_text(render_template(rule["template"], params), forbidden)
        blocks.append(_block(rule, text, derived=False, params=params))
    if not blocks:
        return derived
    order = {rule_id: index for index, rule_id in enumerate(config.get("enabled_blocks") or ())}
    blocks.sort(key=lambda item: (order.get(item["id"], 999), item["id"]))
    return blocks


def _judgment_index(run):
    """Map (position, layer, table[, shen_type]) -> fields from entries."""
    index = {}
    for entry in run.get("entries") or ():
        detail = entry.get("detail") or {}
        record = detail.get("record_judgment")
        if not record:
            continue
        key = record.get("key") or {}
        position = key.get("position")
        table = record.get("table")
        if position is None or not table:
            continue
        layer = key.get("layer") or "本"
        bucket = index.setdefault((position, layer, table), [])
        bucket.append({"fields": record.get("fields") or {}, "shen_type": key.get("shen_type")})
    return index


def _first_field(index, position, table, field, *, layer="本", shen_type=None):
    for item in index.get((position, layer, table), ()):
        if shen_type and item.get("shen_type") != shen_type:
            continue
        if field in item["fields"]:
            return item["fields"][field]
    return None


def _effect_bits(hit, *, period, month_state=None, is_moving=False):
    """Month/day influence cell: short tokens from the line's perspective."""
    if not hit:
        return []
    bits = []
    if period == "月" and month_state:
        bits.append(month_state)
    if hit.get("same_branch"):
        bits.append("临")
    else:
        mapped = WUXING_CELL.get(hit.get("wuxing"))
        if mapped:
            bits.append(mapped)
    if hit.get("chong"):
        bits.append("月破" if period == "月" else ("日冲" if not is_moving else "日冲"))
    if hit.get("he"):
        bits.append("合")
    stage = hit.get("target_stage")
    if stage in ("长生", "帝旺", "墓", "绝"):
        bits.append(stage if stage in ("长生", "帝旺") else f"见{stage}")
    return bits


def _clip_cell(text):
    text = text or DASH
    if len(text) <= CELL_MAX:
        return text
    return text[: CELL_MAX - 1] + "…"


def _derive_strength(overall, rooted):
    if overall == "旺":
        return "旺", True
    if overall == "有气":
        return "有气", True
    if overall == "衰":
        return ("衰而有救" if rooted == "有根" else "无用"), True
    if overall == "无用":
        return "无用", True
    return None, False


def _attrs_for_line(position, relative, *, primary, roles, shi, ying):
    tags = []
    if primary.get("source") == "base" and primary.get("position") == position:
        tags.append("用神")
    if roles:
        if relative == roles.get("yuanshen") and "用神" not in tags:
            tags.append("原神")
        if relative == roles.get("jishen"):
            tags.append("忌神")
        if relative == roles.get("choushen"):
            tags.append("仇神")
    if position == shi:
        tags.append("世")
    if position == ying:
        tags.append("应")
    if not tags:
        return DASH
    if len(tags) == 1:
        return tags[0]
    # 仇神·世 / 用神·世
    role = next((tag for tag in tags if tag in ("用神", "原神", "忌神", "仇神")), None)
    marker = next((tag for tag in tags if tag in ("世", "应")), None)
    if role and marker:
        return f"{role}·{marker}"
    return "·".join(tags)


def build_line_table(evidence, run, chart_data=None):
    """Build 6×12 line judgment table. Prefer evidence; chart_data for pair_links fallback."""
    chart_data = chart_data or {}
    chart = evidence.get("chart") or {}
    calendar = evidence.get("calendar") or {}
    focus = run.get("focus") or {}
    primary = focus.get("primary") or {}
    forces_detail = evidence.get("forces") or {}
    month = calendar.get("month_branch")
    day = calendar.get("day_branch")
    voids = list(calendar.get("void") or ())
    moving = set(chart.get("moving_positions") or ())
    from .forces import _dark_moves
    dark = set(_dark_moves(evidence, moving) or ())
    shi = chart.get("shi_line")
    ying = chart.get("ying_line")
    board = list(rows(chart, "hexagram_board"))
    if len(board) != 6:
        board = (chart_data.get("base") or {}).get("lines") or board
    roles = focus.get("roles") or chart_data.get("roles") or {}
    if not roles:
        role_rows = rows(evidence.get("roles") or {}, "yongshen_roles")
        relative = focus.get("relative")
        hit = next((row for row in role_rows if row.get("yongshen") == relative), None)
        if hit:
            roles = {"yuanshen": hit["yuanshen"], "jishen": hit["jishen"], "choushen": hit["choushen"]}
    judgments = _judgment_index(run)
    force_by_pos = {line["position"]: line for line in forces_detail.get("lines") or ()}
    moves = {row["position"]: row for row in rows(evidence.get("moves") or {}, "change_board")}
    if not moves and chart_data.get("changes"):
        moves = {row["position"]: row for row in chart_data["changes"]}
    pair_links = list(chart_data.get("pair_links") or ())
    if not pair_links:
        # timing / relations fallback for 世应
        shi_line = next((row for row in board if row.get("position") == shi), None)
        ying_line = next((row for row in board if row.get("position") == ying), None)
        if shi_line and ying_line:
            for topic in ("timing", "relations"):
                for row in rows(evidence.get(topic) or {}, "branch_interaction"):
                    if {row.get("actor"), row.get("target")} == {shi_line["branch"], ying_line["branch"]}:
                        pair_links.append({
                            "label": "世应", "left": shi_line["branch"], "right": ying_line["branch"],
                            "chong": int(row.get("chong") or 0), "he": int(row.get("he") or 0),
                        })
                        break
                if pair_links:
                    break

    gaps = []
    table_rows = []
    for line in sorted(board, key=lambda row: -row["position"]):
        position = line["position"]
        branch = line["branch"]
        element = line["element"]
        relative = line["relative"]
        hidden = bool(line.get("hidden_branch"))
        is_moving = position in moving
        is_dark = position in dark and not is_moving
        if is_moving:
            move_kind = "明动"
        elif is_dark:
            move_kind = "暗动"
        elif hidden:
            move_kind = "静·伏"
        else:
            move_kind = "静"

        month_state = _month_state(evidence, element)
        if month_state is None and chart_data.get("strength"):
            month_state = chart_data["strength"].get(element)
        month_hit = _interaction(evidence, month, branch)
        day_hit = _interaction(evidence, day, branch)
        if not month_hit and chart_data.get("interactions") and month:
            month_hit = chart_data["interactions"].get((month or "") + branch) or {}
        if not day_hit and chart_data.get("interactions") and day:
            day_hit = chart_data["interactions"].get((day or "") + branch) or {}

        month_bits = _effect_bits(month_hit, period="月", month_state=month_state, is_moving=is_moving)
        day_bits = _effect_bits(day_hit, period="日", is_moving=is_moving)
        if not month:
            month_cell = PENDING
            gaps.append(f"第{position}爻月建待核")
        elif month_bits:
            month_cell = f"{month}月" + "·".join(month_bits)
        else:
            month_cell = f"{month}月" + (month_state or DASH)

        if day and day_bits:
            day_cell = f"{day}日" + "·".join(day_bits)
        elif not day:
            day_cell = PENDING
            gaps.append(f"第{position}爻日辰待核")
        else:
            day_cell = f"{day}日" + DASH

        # 旬空
        kong_nature = _first_field(judgments, position, "kong_po_judge", "kong_nature")
        if branch in voids:
            void_cell = f"空·{kong_nature}" if kong_nature and kong_nature != "不为空" else "空"
        else:
            void_cell = DASH

        # 动变
        move = moves.get(position)
        if move:
            bits = [f"动→{move.get('changed_branch') or ''}{move.get('changed_element') or ''}"]
            if move.get("jin_tui"):
                bits.append(move["jin_tui"])
            if move.get("huitou"):
                bits.append(move["huitou"])
            if move.get("changed_branch") in voids:
                bits.append("化空")
            if move.get("fuyin_line"):
                bits.append("化伏吟")
            change_cell = "·".join(bit for bit in bits if bit and bit != "动→")
            if bits[0]:
                change_cell = "·".join(bits)
        else:
            change_cell = DASH

        # 冲合·墓绝（月破已在第 6 列则不重复月冲）
        clash_bits = []
        for link in pair_links:
            if link.get("label") == "世应" and position in (shi, ying) and link.get("chong"):
                clash_bits.append("与世相冲" if position == ying else "与应相冲")
            if link.get("label") == "世应" and position in (shi, ying) and link.get("he"):
                clash_bits.append("与世相合" if position == ying else "与应相合")
        if move:
            if move.get("hua_chong"):
                clash_bits.append("化冲")
            if move.get("hua_he"):
                clash_bits.append("化合")
            if move.get("fuyin_line"):
                clash_bits.append("化伏吟")
        stage = (day_hit or {}).get("target_stage") or (month_hit or {}).get("target_stage")
        if stage == "绝" and "见绝" not in clash_bits:
            clash_bits.append("见绝")
        if stage == "墓" and "见墓" not in clash_bits:
            clash_bits.append("见墓")
        # C4: 月破已在月建列 → 不在此列写月冲
        clash_bits = [bit for bit in clash_bits if bit not in ("月冲", "月破")]
        clash_cell = "·".join(dict.fromkeys(clash_bits)) if clash_bits else DASH

        # 当前状态
        overall = _first_field(judgments, position, "month_day_judge", "overall")
        po_nature = _first_field(judgments, position, "kong_po_judge", "po_nature")
        state_bits = [move_kind]
        if overall:
            state_bits.append(overall)
        elif month_state:
            state_bits.append(month_state)
        if branch in voids:
            state_bits.append(kong_nature or "空")
        if month_hit.get("chong"):
            state_bits.append(po_nature or "月破")
        if is_moving and day_hit.get("chong"):
            state_bits.append("日冲不散")
        state_cell = "·".join(state_bits)

        # 力度
        attrs = _attrs_for_line(position, relative, primary=primary, roles=roles, shi=shi, ying=ying)
        force_meta = {"value": DASH, "derived": False, "note": ""}
        force_line = force_by_pos.get(position)
        is_yong = attrs == "用神" or attrs.startswith("用神")
        is_yuanji = any(tag in attrs for tag in ("原神", "忌神", "仇神"))
        # 世应无力度字段；兼仇神的世应行仍写 —（方案 §2.1 / §10）
        if attrs == DASH:
            force_meta = {"value": DASH, "derived": False, "note": "旁爻"}
        elif attrs in ("世", "应"):
            force_meta = {"value": DASH, "derived": False, "note": "世应无力度字段"}
        elif is_yong:
            strength = _first_field(judgments, position, "yongshen_judge", "strength")
            if strength:
                force_meta = {"value": strength, "derived": False, "note": ""}
            else:
                rooted = forces_detail.get("primary_rooted")
                derived, ok = _derive_strength(overall, rooted)
                if ok and derived:
                    force_meta = {"value": derived, "derived": True, "note": "派生"}
                elif force_line and rooted == "有根" and force_line.get("force") == "无力":
                    force_meta = {"value": "衰而有救", "derived": True, "note": "派生"}
                elif force_line and rooted == "无根" and force_line.get("force") == "无力":
                    force_meta = {"value": "无用", "derived": True, "note": "派生"}
                elif force_line and force_line.get("force") == "有力":
                    force_meta = {
                        "value": "旺" if month_state == "旺" else "有气",
                        "derived": True, "note": "派生",
                    }
                else:
                    force_meta = {"value": PENDING, "derived": False, "note": ""}
                    gaps.append("用神力度待核")
        elif is_yuanji:
            shen = next(tag for tag in ("原神", "忌神", "仇神") if tag in attrs)
            eff = _first_field(judgments, position, "yuanji_judge", "effective_force", shen_type=shen)
            can_act = _first_field(judgments, position, "yuanji_judge", "can_act_on_yong", shen_type=shen)
            if not eff and force_line:
                eff = force_line.get("force")
            if eff:
                note = ""
                if can_act is True:
                    note = "能作用"
                elif can_act is False:
                    note = "不能作用"
                else:
                    note = "作用待核"
                force_meta = {"value": eff, "derived": False, "note": note}
            else:
                force_meta = {"value": PENDING, "derived": False, "note": ""}
                gaps.append(f"{shen}力度待核")
        else:
            force_meta = {"value": DASH, "derived": False, "note": ""}

        # 补充：世应兼仇神时，第 12 列取仇神力度（方案：世应行不判力度写 —；预览验收要求 —）
        # 严格按方案：只要带「世」或「应」且不是用神，力度列写 —
        if ("世" in attrs or "应" in attrs) and not is_yong:
            force_meta = {"value": DASH, "derived": False, "note": "世应无力度字段"}

        row = {
            "position": position,
            "line_title": line.get("line_title") or POS_TITLE.get(position, ""),
            "pos_label": POS_TITLE.get(position, f"第{position}爻"),
            "move_kind": move_kind,
            "relative": relative,
            "stem_branch_element": f"{line.get('stem') or ''}{branch}{element}",
            "attrs": attrs,
            "month_effect": _clip_cell(month_cell),
            "day_effect": _clip_cell(day_cell),
            "void": _clip_cell(void_cell),
            "change": _clip_cell(change_cell),
            "clash": _clip_cell(clash_cell),
            "state": _clip_cell(state_cell),
            "force": force_meta["value"],
            "force_derived": force_meta["derived"],
            "force_note": force_meta["note"],
            "key": "用神" if is_yong else (
                "世" if position == shi else ("应" if position == ying else (
                    "忌神" if "忌神" in attrs else ("原神" if "原神" in attrs else (
                        "仇神" if "仇神" in attrs else "旁"
                    ))
                ))
            ),
        }
        table_rows.append(row)

    # 补充行：用神为伏/变/月建/日辰
    extras = []
    source = primary.get("source")
    if source in ("hidden", "changed", "month", "day"):
        label = {"hidden": "补·伏", "changed": "补·变", "month": "补·月建", "day": "补·日辰"}[source]
        extras.append({
            "position": primary.get("position"),
            "pos_label": label,
            "line_title": label,
            "move_kind": DASH,
            "relative": focus.get("relative") or DASH,
            "stem_branch_element": f"{primary.get('branch') or ''}{primary.get('element') or ''}" or DASH,
            "attrs": "用神",
            "month_effect": PENDING,
            "day_effect": PENDING,
            "void": DASH,
            "change": DASH,
            "clash": DASH,
            "state": PENDING,
            "force": PENDING,
            "force_derived": False,
            "force_note": "",
            "key": "用神",
            "extra": True,
        })

    result = {"rows": table_rows, "extras": extras, "gaps": list(dict.fromkeys(gaps))}
    result["checks"] = check_table(result, run, forces_detail)
    return result


def check_table(table, run, forces_detail):
    """C1–C8 consistency checks. Failed checks listed in problems."""
    problems = []
    rows_ = table.get("rows") or []
    positions = [row["position"] for row in rows_]
    if sorted(positions) != list(range(1, 7)):
        problems.append("C7: 六爻行不齐全或位次重复")
    judgments = _judgment_index(run)
    force_by_pos = {line["position"]: line for line in (forces_detail or {}).get("lines") or ()}
    for row in rows_:
        for key in ("month_effect", "day_effect", "void", "change", "clash", "state", "force", "attrs",
                    "move_kind", "relative", "stem_branch_element"):
            value = row.get(key) or ""
            if isinstance(value, str) and len(value) > CELL_MAX:
                problems.append(f"C6: 第{row['position']}爻 {key} 超 14 字")
        force = row.get("force")
        pos = row["position"]
        if "用神" in (row.get("attrs") or ""):
            strength = _first_field(judgments, pos, "yongshen_judge", "strength")
            if strength and force != strength and not row.get("force_derived"):
                problems.append(f"C1: 用神力度与 yongshen_judge.strength 不一致")
        for role in ("原神", "忌神", "仇神"):
            if role in (row.get("attrs") or "") and "世" not in row.get("attrs", "") and "应" not in row.get("attrs", ""):
                expected = force_by_pos.get(pos, {}).get("force")
                if expected and force not in (expected, DASH, PENDING) and not row.get("force_note"):
                    problems.append(f"C2: {role}力度与 forces 不一致")
        # C3: 状态与旬空性质不互斥
        if row.get("void") == DASH and "空" in (row.get("state") or ""):
            problems.append(f"C3: 第{pos}爻状态含空但旬空列为 —")
        # C4 handled at build time
        if row.get("void") == PENDING and row.get("force") == DASH:
            pass  # — vs 待核 语义不同，允许同列不同格
        # whitelist tokens (loose: allow composed cells)
        for key in ("force", "move_kind"):
            value = row.get(key)
            if value and value not in TABLE_WHITELIST and value not in (DASH, PENDING):
                # composed force notes ok
                if key == "force" and value in YONG_STRENGTH | YUANJI_FORCE:
                    continue
                if value not in YONG_STRENGTH | YUANJI_FORCE | MOVE_KIND:
                    problems.append(f"C8: 第{pos}爻 {key}={value} 不在词表")
    try:
        catalog = load_rules()
        forbidden = catalog.get("forbidden_matter_terms") or ()
        for row in rows_:
            for key in ("month_effect", "day_effect", "change", "clash", "state"):
                assert_el15_text(str(row.get(key) or "—"), forbidden)
    except ValueError as error:
        problems.append(f"C5: {error}")
    return {"ok": not problems, "problems": problems}


def group_items(blocks, evidence, focus, table=None):
    """Group preset blocks by object for ① 用神盘面要点."""
    chart = evidence.get("chart") or {}
    primary = (focus or {}).get("primary") or {}
    primary_pos = primary.get("position") if primary.get("source") == "base" else None
    shi = chart.get("shi_line")
    ying = chart.get("ying_line")
    forces_detail = evidence.get("forces") or {}
    force_by_role = {}
    for line in forces_detail.get("lines") or ():
        role = line.get("role")
        if role and role not in force_by_role:
            force_by_role[role] = line

    order = ["用神", "世", "应", "原神", "忌神", "仇神", "动爻", "结构"]
    buckets = {key: [] for key in order}
    catalog = load_rules()
    forbidden = catalog.get("forbidden_matter_terms") or ()

    for block in blocks or ():
        text = block.get("text") or ""
        assert_el15_text(text, forbidden)
        key = "结构"
        if text.startswith("用神") or (block.get("id") in ("R14", "R15") and "用神" in text[:6]):
            key = "用神"
        if block.get("id") == "R14":
            who = (block.get("params") or {}).get("who") or text
            if "原神" in who:
                key = "原神"
            elif "忌神" in who:
                key = "忌神"
            elif "仇神" in who:
                key = "仇神"
            elif "用神" in who:
                key = "用神"
        elif text.startswith("世"):
            key = "世"
        elif text.startswith("应"):
            key = "应"
        elif block.get("id") in ("R10", "R19", "X01", "X02"):
            key = "结构"
        elif block.get("id") in ("R11", "R13"):
            key = "动爻"
            params_who = (block.get("params") or {}).get("who") or ""
            if "用神" in params_who:
                key = "用神"
            elif "忌神" in params_who:
                key = "忌神"
            elif "原神" in params_who:
                key = "原神"
        # split long sentences
        parts = [part.strip() for part in text.replace("。", "。\n").split("\n") if part.strip()]
        for part in parts:
            if not part.endswith(("。", "！", "？")):
                part += "。"
            if len(part) > 28:
                # soft split at commas
                for chunk in part.replace("，", "，\n").split("\n"):
                    chunk = chunk.strip()
                    if chunk:
                        if not chunk.endswith(("。", "！", "？", "，")):
                            chunk += "。"
                        buckets[key].append(chunk)
            else:
                buckets[key].append(part)

    # object labels from board
    def line_obj(position):
        row = _board_line(evidence, position)
        if not row:
            return ""
        return f"{POS_TITLE.get(position, '')} {row.get('branch') or ''}{row.get('element') or ''} {row.get('relative') or ''}".strip()

    yong_force = None
    if table:
        for row in table.get("rows") or ():
            if row.get("key") == "用神":
                yong_force = row.get("force")
                break
    if not yong_force:
        yong_force = (force_by_role.get("用神") or {}).get("force")

    items = []
    for key in order:
        lines = buckets.get(key) or []
        if not lines and key not in ("用神", "世", "应"):
            continue
        if key == "用神":
            obj = line_obj(primary_pos) if primary_pos else (focus.get("relative") or "")
            state = yong_force or PENDING
        elif key == "世":
            obj = line_obj(shi)
            state = "关系待判"
            if not lines:
                continue
        elif key == "应":
            obj = line_obj(ying)
            state = "关系待判"
            if not lines:
                continue
        elif key in ("原神", "忌神", "仇神"):
            force_line = force_by_role.get(key) or {}
            obj = line_obj(force_line.get("position"))
            state = force_line.get("force") or PENDING
            if not lines and not force_line:
                continue
        elif key == "动爻":
            movers = chart.get("moving_positions") or []
            obj = "、".join(POS_TITLE.get(pos, "") for pos in movers) or "明动"
            state = "明动"
            if not lines:
                continue
        else:
            obj = "结构说明"
            state = "说明"
            if not lines:
                continue
        visible, folded = lines[:4], lines[4:]
        items.append({
            "key": key,
            "tag": {"用神": "用神", "世": "世爻", "应": "应爻"}.get(key, key),
            "object": obj,
            "state": state,
            "lines": visible,
            "folded": folded,
        })
    return items


def build_headline(evidence, focus, table=None):
    """One-sentence yongshen status for the hero strip."""
    forces_detail = evidence.get("forces") or {}
    rooted = forces_detail.get("primary_rooted")
    force = None
    if table:
        for row in table.get("rows") or ():
            if row.get("key") == "用神":
                force = row.get("force")
                break
    if not force:
        for line in forces_detail.get("lines") or ():
            if line.get("role") == "用神":
                force = line.get("force")
                break
    force = force or PENDING
    calendar = evidence.get("calendar") or {}
    primary = (focus or {}).get("primary") or {}
    line = _board_line(evidence, primary.get("position")) if primary.get("source") == "base" else None
    text = f"用神眼下是{force}"
    if line:
        month = calendar.get("month_branch")
        day = calendar.get("day_branch")
        voids = calendar.get("void") or ()
        month_hit = _interaction(evidence, month, line["branch"])
        day_hit = _interaction(evidence, day, line["branch"])
        press, help_ = [], []
        if month_hit.get("chong"):
            press.append("月破")
        if line["branch"] in voids:
            press.append("旬空")
        if day_hit.get("wuxing") == "生":
            help_.append("日辰生它")
        elif day_hit.get("same_branch"):
            help_.append("临日")
        if rooted == "有根":
            help_.append("有根")
        elif rooted == "无根":
            press.append("无根")
        if press:
            text += "：" + "、".join(press) + "压着"
        if help_:
            text += ("，但" if press else "：") + "、".join(help_)
        if "旬空" in press:
            text += "，等出空再论"
    text += "。"
    return assert_el15_text(text, load_rules().get("forbidden_matter_terms") or ())


def build_interpretation(run, evidence, chart_data=None):
    """Public entry used by view.reading_page."""
    from .review import LAYER_STATUS_LABEL  # local to avoid cycles if any

    focus = run.get("focus")
    forces_detail = evidence.get("forces") or {}
    windows = (evidence.get("windows") or {}).get("windows") or []
    verdict = run.get("verdict") or {}
    stored = run.get("interpretation") or {}
    if stored.get("preset_blocks"):
        preset = stored["preset_blocks"]
    else:
        preset = match_presets(evidence, focus, derived=True)
    config = load_config()
    primary = (focus or {}).get("primary") or {}
    main_change = _move_at(evidence, primary.get("position")) if primary.get("source") == "base" else None
    table = build_line_table(evidence, run, chart_data=chart_data)
    items = group_items(preset, evidence, focus, table=table)
    headline = build_headline(evidence, focus, table=table)
    shi = evidence.get("chart", {}).get("shi_line")
    ying = evidence.get("chart", {}).get("ying_line")
    return {
        "config_version": config.get("config_version", "1.0"),
        "table_version": config.get("table_version", "2.0"),
        "el15": True,
        "scope": "yongshen_only",
        "preset_blocks": preset,
        "headline": headline,
        "items": items,
        "table": table,
        "conclusions": {
            "primary_change": {key: main_change[key] for key in (
                "changed_branch", "changed_element", "changed_relative", "huitou", "hua_he",
                "hua_chong", "jin_tui", "hua_stage",
            )} if main_change else None,
            "primary_rooted": forces_detail.get("primary_rooted"),
            "primary_rooted_reasons": forces_detail.get("primary_rooted_reasons") or [],
            "forces_lines": [
                {
                    "position": line.get("position"), "role": line.get("role"),
                    "force": line.get("force"), "reasons": line.get("reasons") or [],
                }
                for line in forces_detail.get("lines") or ()
                if line.get("role") in ("用神", "原神", "忌神", "仇神")
                or line.get("position") in (shi, ying)
            ],
            "windows": [
                {
                    "branch": item.get("branch"), "unit": item.get("unit"),
                    "channels": item.get("channels") or [], "confidence": item.get("confidence"),
                }
                for item in windows
            ],
            "verdict_layers": [
                {
                    "name": layer.get("name"), "condition": layer.get("condition"),
                    "status": LAYER_STATUS_LABEL.get(layer.get("status"), layer.get("status")),
                }
                for layer in verdict.get("layers") or ()
            ],
            "falsifier": verdict.get("falsifier") or "",
        },
    }
