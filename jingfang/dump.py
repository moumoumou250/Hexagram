"""Read-only per-step dump of a Jingfang reading journal."""

import json
from pathlib import Path

from .report import SKILL_USE, STATUS
from .rule_data import ROOT
from .view import embed_data


STEP_TOPICS = {
    "identify": (),
    "focus": ("focus",),
    "strength": (),
    "change": (),
    "timing": ("windows",),
    "synthesis": ("verdict", "interpretation", "outcomes"),
}


def _fact_brief(entry, fact_labels):
    detail = entry.get("detail") or {}
    queries = detail.get("queries") or ()
    tables = list(dict.fromkeys(query.get("table") for query in queries if query.get("table")))
    rows = sum(len(query.get("rows") or ()) for query in queries)
    label = fact_labels.get(entry.get("topic"), entry.get("topic", ""))
    parts = [label] if label else []
    if tables:
        parts.append("表 " + "、".join(tables))
    if rows:
        parts.append(f"{rows} 行")
    return " · ".join(parts) or entry.get("summary", "")


def _entry_view(entry, include_detail, fact_labels):
    item = {
        "id": entry.get("id"),
        "kind": entry["kind"],
        "topic": entry.get("topic"),
        "summary": entry.get("summary", ""),
        "refs": list(entry.get("refs") or ()),
    }
    if entry["kind"] == "fact":
        item["brief"] = _fact_brief(entry, fact_labels)
    detail = entry.get("detail")
    if include_detail and detail is not None:
        item["detail"] = detail
    elif detail is not None:
        item["detail_keys"] = sorted(detail) if isinstance(detail, dict) else []
    for key in ("position", "changed_branch", "spirit", "branches", "branch", "unit", "channel",
                "skill", "section", "rule", "condition", "exceptions", "elements",
                "compared_targets", "domain"):
        if key in entry:
            item[key] = entry[key]
        elif isinstance(detail, dict) and key in detail:
            item[key] = detail[key]
    return item


def _top_for_step(run, step):
    extras = {}
    for key in STEP_TOPICS.get(step, ()):
        if key == "focus":
            extras["focus"] = run.get("focus")
        elif key == "windows":
            evidence = [e for e in run.get("entries") or ()
                        if e.get("kind") == "fact" and e.get("topic") == "windows"]
            extras["windows"] = (evidence[-1].get("detail") if evidence else None)
        elif key == "verdict":
            extras["verdict"] = run.get("verdict")
        elif key == "interpretation":
            extras["interpretation"] = run.get("interpretation")
        elif key == "outcomes":
            extras["outcomes"] = run.get("outcomes") or []
    return extras


def build_dump(run, step=None, *, include_detail=True):
    """Group journal entries and top-level fields by pipeline step."""
    from .orchestrator import FACT_LABELS, STEPS, reading_state

    if step is not None and step not in STEPS:
        raise ValueError(f"未知步骤 {step}")
    wanted = [step] if step else list(STEPS)
    steps_out = {}
    for name in wanted:
        meta = dict(run["steps"].get(name) or {})
        meta.pop("submission", None)
        entries = [entry for entry in run.get("entries") or () if entry.get("step") == name]
        facts = [_entry_view(entry, include_detail, FACT_LABELS)
                 for entry in entries if entry["kind"] == "fact"]
        judgments = [_entry_view(entry, include_detail, FACT_LABELS)
                     for entry in entries if entry["kind"] == "judgment"]
        pending = [_entry_view(entry, include_detail, FACT_LABELS)
                   for entry in entries if entry["kind"] == "pending"]
        block = {
            "label": STEPS[name],
            "state": meta.get("state", "pending"),
            "state_label": STATUS.get(meta.get("state", "pending"), meta.get("state", "pending")),
            "skill_use": meta.get("skill_use"),
            "skill_use_label": SKILL_USE.get(meta.get("skill_use"), meta.get("skill_use")),
            "reason": meta.get("reason"),
            "facts": facts,
            "judgments": judgments,
            "pending": pending,
            "extras": _top_for_step(run, name),
        }
        if (not facts and not judgments and not pending
                and not any(v not in (None, [], {}) for v in block["extras"].values())):
            block["empty_note"] = "本步无 / 未记录"
        steps_out[name] = block
    state = reading_state(run)
    return {
        "run_id": run["id"],
        "state": state,
        "state_label": STATUS.get(state, state),
        "revision": run.get("revision"),
        "rule_version": run.get("rule_version"),
        "question": (run.get("input") or {}).get("question", ""),
        "source": (run.get("input") or {}).get("source", ""),
        "ask_timing": (run.get("input") or {}).get("ask_timing"),
        "created_at": run.get("created_at"),
        "steps": steps_out,
    }


def render_text(dump):
    lines = [
        f"解卦 {dump['run_id']} · {dump['state_label']}",
        f"问题 · {dump['question']}",
        f"来源 · {dump['source']}",
        "",
    ]
    for name, block in dump["steps"].items():
        lines.append(f"## {block['label']}（{name}）· {block['state_label']}")
        if block.get("skill_use_label"):
            lines.append(f"Skill · {block['skill_use_label']}")
        if block.get("reason"):
            lines.append(f"原因 · {block['reason']}")
        if block.get("empty_note") and not block["facts"] and not block["judgments"] and not block["pending"]:
            lines.append(block["empty_note"])
        if block["facts"]:
            lines.append("事实：")
            for item in block["facts"]:
                lines.append(f"  - E{item['id']} [{item.get('topic')}] {item.get('brief') or item['summary']}")
        if block["judgments"]:
            lines.append("判断：")
            for item in block["judgments"]:
                refs = ",".join(f"E{ref}" for ref in item.get("refs") or ())
                suffix = f" · refs {refs}" if refs else ""
                topic = f" [{item['topic']}]" if item.get("topic") else ""
                lines.append(f"  - E{item['id']}{topic} {item['summary']}{suffix}")
        if block["pending"]:
            lines.append("待核：")
            for item in block["pending"]:
                lines.append(f"  - E{item['id']} {item['summary']}")
        extras = block.get("extras") or {}
        for key, value in extras.items():
            if value in (None, [], {}):
                lines.append(f"{key} · 未记录")
            else:
                preview = json.dumps(value, ensure_ascii=False)
                if len(preview) > 200:
                    preview = preview[:200] + "…"
                lines.append(f"{key} · {preview}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html(dump):
    page = (ROOT / "templates" / "step-dump.html").read_text(encoding="utf-8")
    return embed_data(page, "dump-data", dump)


def write_html(dump, markdown_path):
    path = Path(markdown_path)
    destination = path.parent / "html" / f"{path.stem}-dump.html"
    from .save_reading_log import save_markdown
    save_markdown(render_html(dump), destination)
    return destination
