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

    # 用神 / 世 / 应：日月结构（同位去重，用神优先）
    seen_positions = set()
    if line:
        emit_calendar_effects("用神", line)
        seen_positions.add(line["position"])
    for who, position in (("世爻", shi), ("应爻", ying)):
        if position in seen_positions:
            continue
        target = _board_line(evidence, position)
        if not target:
            continue
        emit_calendar_effects(who, target)
        seen_positions.add(position)

    # 每位明动：同位变对照
    for move in sorted(rows(evidence.get("moves", {}), "change_board"), key=lambda row: row["position"]):
        position = move["position"]
        board_line = _board_line(evidence, position) or {"position": position}
        who = _line_label(
            position,
            primary_pos=primary_pos,
            shi=shi,
            ying=ying,
            relative=board_line.get("relative"),
        )
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
            if role not in ("用神", "原神", "忌神") or role in seen_roles:
                continue
            seen_roles.add(role)
            reason = "、".join(item.get("reasons") or ()) or "盘面综合"
            add("R14", {
                "who": role,
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


def build_interpretation(run, evidence):
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
    return {
        "config_version": config.get("config_version", "1.0"),
        "el15": True,
        "scope": "yongshen_only",
        "preset_blocks": preset,
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
                if line.get("role") in ("用神", "原神", "忌神")
                or line.get("position") in (evidence.get("chart", {}).get("shi_line"),
                                            evidence.get("chart", {}).get("ying_line"))
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
