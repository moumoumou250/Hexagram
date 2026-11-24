"""Program-side yuan/ji force estimates from frozen board evidence."""

from .review import rows

WANG = {"旺", "相"}
TRUE_VOID = {
    "寅": "土", "卯": "土",
    "巳": "金", "午": "金",
    "申": "木", "酉": "木",
    "亥": "火", "子": "火",
}
SANHE = (
    ("水", "申", "子", "辰"),
    ("金", "巳", "酉", "丑"),
    ("火", "寅", "午", "戌"),
    ("木", "亥", "卯", "未"),
)
ROLES = {
    "父母": {"yuanshen": "官鬼", "jishen": "妻财", "choushen": "子孙"},
    "兄弟": {"yuanshen": "父母", "jishen": "官鬼", "choushen": "妻财"},
    "子孙": {"yuanshen": "兄弟", "jishen": "父母", "choushen": "官鬼"},
    "妻财": {"yuanshen": "子孙", "jishen": "兄弟", "choushen": "父母"},
    "官鬼": {"yuanshen": "妻财", "jishen": "子孙", "choushen": "兄弟"},
}


def _interactions(evidence):
    return {(row["actor"], row["target"]): row
            for row in rows(evidence.get("relations", {}), "branch_interaction")}


def _strength(evidence):
    return {row["element"]: row["state"]
            for row in rows(evidence.get("relations", {}), "month_strength")}


def _moves(evidence):
    return {row["position"]: row for row in rows(evidence.get("moves", {}), "change_board")}


def _board_lines(evidence):
    return list(rows(evidence.get("chart", {}), "hexagram_board"))


def _month_day(evidence):
    calendar = evidence.get("calendar", {})
    return calendar.get("month_branch"), calendar.get("day_branch"), calendar.get("void") or ()


def _role_map(focus):
    roles = (focus or {}).get("roles") or {}
    primary = (focus or {}).get("primary") or {}
    mapping = {}
    if primary.get("source") == "base" and primary.get("position") is not None:
        mapping[primary["position"]] = "用神"
    yuan = roles.get("yuanshen")
    ji = roles.get("jishen")
    chou = roles.get("choushen")
    return mapping, yuan, ji, chou


def _line_force(line, *, month, day, voids, strength, interactions, moves, moving, dark):
    position = line["position"]
    branch, element = line["branch"], line["element"]
    month_state = strength.get(element, "休囚")
    wang = month_state in WANG
    resting = month_state == "休囚"
    void = branch in voids
    month_hit = interactions.get((month, branch), {}) if month else {}
    day_hit = interactions.get((day, branch), {}) if day else {}
    month_break = bool(month_hit.get("chong"))
    day_break = bool(day_hit.get("chong")) and position not in moving and position not in dark
    on_month = bool(month_hit.get("same_branch"))
    on_day = bool(day_hit.get("same_branch"))
    move = moves.get(position, {})
    moving_here = position in moving
    dark_here = position in dark
    huitou = move.get("huitou")
    jin_tui = move.get("jin_tui")
    hua_stage = move.get("hua_stage")
    into_mu = (month_hit.get("target_stage") == "墓" or day_hit.get("target_stage") == "墓"
               or hua_stage == "墓")
    true_void = void and TRUE_VOID.get(month) == element and resting

    # 1. 有用而暂困
    if wang and void:
        return "有力", ["旺相", "旬空", "待出空"]
    if wang and month_break:
        return "有力", ["旺相", "月破", "出月不破"]

    # 2. 无力
    if month_break and resting:
        return "无力", ["月破", "休囚"]
    if day_break:
        return "无力", ["日破"]
    if true_void:
        return "无力", ["真空"]
    if into_mu and resting:
        return "无力", ["入墓", "休囚"]
    if jin_tui == "退神":
        return "无力", ["化退神"]
    if huitou == "回头克":
        return "无力", ["化回头克"]
    if resting and not moving_here and not dark_here:
        return "无力", ["休囚", "非动"]

    # 3. 有力
    if on_month or on_day:
        return "有力", ["临日月"]
    if wang:
        return "有力", ["旺相"]
    if moving_here or dark_here:
        return "有力", ["动"] if moving_here else ["暗动"]
    if huitou == "回头生":
        return "有力", ["化回头生"]
    if jin_tui == "进神":
        return "有力", ["化进神"]

    return "中和", ["无明显旺衰偏倚"]


def _dark_moves(evidence, moving):
    _, day, _ = _month_day(evidence)
    strength = _strength(evidence)
    interactions = _interactions(evidence)
    dark = set()
    if not day:
        return dark
    for line in _board_lines(evidence):
        position = line["position"]
        if position in moving:
            continue
        if strength.get(line["element"]) not in WANG:
            continue
        if interactions.get((day, line["branch"]), {}).get("chong"):
            dark.add(position)
    return dark


def _moving_help(line, lines, moves, moving, interactions):
    """Whether a moving/changed line generates 生 toward this line."""
    target = line["branch"]
    for other in lines:
        if other["position"] not in moving:
            continue
        hit = interactions.get((other["branch"], target), {})
        if hit.get("wuxing") == "生":
            return True
        changed = moves.get(other["position"], {})
        changed_branch = changed.get("changed_branch")
        if changed_branch:
            hit = interactions.get((changed_branch, target), {})
            if hit.get("wuxing") == "生":
                return True
    return False


def _rooted(line, month, day, strength, interactions, lines, moves, moving):
    branch, element = line["branch"], line["element"]
    month_hit = interactions.get((month, branch), {}) if month else {}
    day_hit = interactions.get((day, branch), {}) if day else {}
    month_break = bool(month_hit.get("chong"))
    day_ke = day_hit.get("wuxing") == "克"
    resting = strength.get(element) == "休囚"
    jue = month_hit.get("target_stage") == "绝" or day_hit.get("target_stage") == "绝"
    helped = (day_hit.get("wuxing") == "生" or month_hit.get("wuxing") == "生"
              or _moving_help(line, lines, moves, moving, interactions))
    if month_break and day_ke:
        return "无根", ["月破", "日克"]
    if resting and jue and not helped:
        return "无根", ["衰绝", "无生扶"]
    if month_break and resting and day_ke and not helped:
        return "无根", ["月破", "休囚", "日克"]
    return "有根", []


def forces(evidence, focus, overrides=None):
    """Return {lines: [...], primary_rooted, primary_rooted_reasons}."""
    overrides = overrides or {}
    lines = _board_lines(evidence)
    if not lines:
        return {"lines": [], "primary_rooted": None, "primary_rooted_reasons": []}
    month, day, voids = _month_day(evidence)
    strength = _strength(evidence)
    interactions = _interactions(evidence)
    moves = _moves(evidence)
    moving = set((evidence.get("chart") or {}).get("moving_positions") or ())
    dark = _dark_moves(evidence, moving)
    role_at, yuan, ji, chou = _role_map(focus)
    shi = (evidence.get("chart") or {}).get("shi_line")
    moving_relatives = {line["relative"] for line in lines if line["position"] in moving}

    result = []
    for line in lines:
        position = line["position"]
        force, reasons = _line_force(
            line, month=month, day=day, voids=voids, strength=strength,
            interactions=interactions, moves=moves, moving=moving, dark=dark,
        )
        if (yuan and line["relative"] == yuan and ji in moving_relatives) or (
            ji and line["relative"] == ji and yuan in moving_relatives
        ):
            if force != "有力":
                force, reasons = "有力", [*(reasons or []), "元忌同动"]
        role = role_at.get(position)
        if role is None:
            if line["relative"] == yuan:
                role = "原神"
            elif line["relative"] == ji:
                role = "忌神"
            elif line["relative"] == chou:
                role = "仇神"
            elif position == shi:
                role = "世"
            else:
                role = line["relative"]
        item = {
            "position": position, "relative": line["relative"], "branch": line["branch"],
            "element": line["element"], "role": role, "force": force, "reasons": reasons,
            "rooted": None,
        }
        override = overrides.get(str(position)) or overrides.get(position)
        if override:
            item["force"] = override["force"]
            item["reasons"] = [override["override_reason"]]
            item["force_override"] = override["force"]
            item["override_reason"] = override["override_reason"]
        result.append(item)

    primary = (focus or {}).get("primary") or {}
    rooted, rooted_reasons = None, []
    proxy = None
    if primary.get("source") == "base" and primary.get("position") is not None:
        proxy = next((row for row in lines if row["position"] == primary["position"]), None)
    elif primary.get("source") == "hidden" and primary.get("position") is not None:
        line = next((row for row in lines if row["position"] == primary["position"]), None)
        if line and line.get("hidden_branch"):
            proxy = {
                "position": line["position"], "branch": line["hidden_branch"],
                "element": line["hidden_element"], "relative": line["hidden_relative"],
            }
    if proxy is not None:
        rooted, rooted_reasons = _rooted(
            proxy, month, day, strength, interactions, lines, moves, moving
        )
        for item in result:
            if item["position"] == primary.get("position") and primary.get("source") == "base":
                item["rooted"] = rooted
                item["role"] = "用神"

    return {
        "lines": result,
        "primary_rooted": rooted,
        "primary_rooted_reasons": rooted_reasons,
    }


def sanhe_scan(evidence):
    """Classify sanhe fullness without touching board() output."""
    calendar = evidence.get("calendar", {})
    branches = set()
    for line in _board_lines(evidence):
        branches.add(line["branch"])
        if line.get("hidden_branch"):
            branches.add(line["hidden_branch"])
    for line in rows(evidence.get("moves", {}), "change_board"):
        branches.add(line["changed_branch"])
    for key in ("month_branch", "day_branch"):
        if calendar.get(key):
            branches.add(calendar[key])
    moving = set((evidence.get("chart") or {}).get("moving_positions") or ())
    dark = _dark_moves(evidence, moving)
    active = moving | dark
    findings = []
    interactions = _interactions(evidence)
    month = calendar.get("month_branch")
    for element, *trio in SANHE:
        if sum(1 for branch in trio if branch in branches) < 3:
            continue
        in_chart_moving = sum(
            1 for line in _board_lines(evidence)
            if line["branch"] in trio and line["position"] in active
        )
        month_break = any(interactions.get((month, branch), {}).get("chong") for branch in trio)
        if month_break:
            kind = "破而待填"
        elif in_chart_moving >= 2:
            kind = "实局"
        elif in_chart_moving == 1:
            kind = "虚一待用"
        else:
            kind = "虚局"
        findings.append({
            "element": element, "branches": list(trio), "kind": kind,
            "active_count": in_chart_moving,
        })
    return {"groups": findings}


def _as_window(entry):
    if isinstance(entry, tuple):
        _, topic, summary, detail, refs = entry
        return topic, summary, detail, refs
    detail = entry.get("detail", entry)
    topic = entry.get("topic") or detail.get("topic")
    return topic, entry.get("summary", ""), detail, entry.get("refs", [])


def build_windows(window_entries, cast_time=None):
    """Aggregate window judgments into confidence-tagged windows."""
    buckets = {}
    for entry in window_entries:
        topic, summary, detail, refs = _as_window(entry)
        if topic != "window" and "branch" not in detail:
            continue
        branch, unit = detail.get("branch"), detail.get("unit")
        if not branch or not unit:
            continue
        key = (branch, unit)
        bucket = buckets.setdefault(key, {
            "branch": branch, "unit": unit, "channels": [], "summaries": [], "refs": [],
        })
        channel = detail.get("channel")
        if channel and channel not in bucket["channels"]:
            bucket["channels"].append(channel)
        if summary:
            bucket["summaries"].append(summary)
        if isinstance(refs, list):
            bucket["refs"].extend(refs)
    windows = []
    for bucket in buckets.values():
        channels = bucket["channels"]
        windows.append({
            "branch": bucket["branch"], "unit": bucket["unit"], "channels": channels,
            "confidence": "high" if len(channels) >= 2 else "candidate",
            "summaries": bucket["summaries"],
            "refs": sorted(set(bucket["refs"])),
        })
    if cast_time and len(str(cast_time)) >= 4:
        by_branch = {}
        for item in windows:
            by_branch.setdefault(item["branch"], []).append(item)
        for group in by_branch.values():
            units = {item["unit"] for item in group}
            if "月" in units and "年" in units:
                for item in group:
                    item["confidence"] = "conflict"
                    item.setdefault("notes", []).append("同年月通道指向不同单位")
    return {"windows": windows}


def focus_from_case(relative, position, branch=None, element=None):
    """Build a minimal focus object for verification harnesses."""
    roles = ROLES.get(relative)
    primary = {"source": "base", "position": position, "branch": branch, "element": element}
    return {"relative": relative, "primary": primary, "roles": roles, "candidates": [primary]}
