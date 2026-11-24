"""Build timing-window replay checklist from book cases. Heuristic, for calibration."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jingfang.rule_data import BRANCHES
from tests.fixtures.book_cases import CASES

OUT_MD = ROOT / "docs" / "verification" / "window-replay.md"
OUT_JSON = ROOT / "docs" / "verification" / "window-replay.json"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCH_RE = "|".join(BRANCHES)


def infer_channel(blob):
    blob = blob or ""
    if any(mark in blob for mark in ("冲墓", "冲开墓", "墓")) and "冲" in blob:
        return "冲墓"
    if any(mark in blob for mark in ("冲开", "冲去", "逢冲", "日冲", "冲空")):
        return "冲"
    if any(mark in blob for mark in ("填实", "出空", "实破", "实空")):
        return "填实"
    if any(mark in blob for mark in ("当令", "旺于", "旺地")):
        return "当令"
    if any(mark in blob for mark in ("逢合", "破而逢合", "动而逢合")):
        return "合"
    if "化出" in blob or "所化" in blob:
        return "化出之支值"
    if any(mark in blob for mark in ("逢值", "值日", "值月")):
        return "值"
    if "克神" in blob:
        return "克神受克"
    return "值"


def extract_windows(outcome, experience):
    text = f"{outcome or ''} {experience or ''}"
    found = []
    for match in re.finditer(rf"(?:[{STEMS}])?([{BRANCH_RE}])日", text):
        found.append({"branch": match.group(1), "unit": "日",
                      "channel": infer_channel(text), "span": match.group(0)})
    for match in re.finditer(rf"([{BRANCH_RE}])月", text):
        # skip 本月 as bare without branch already handled; 「三月」in Chinese uses 三 not 寅
        found.append({"branch": match.group(1), "unit": "月",
                      "channel": infer_channel(text), "span": match.group(0)})
    for match in re.finditer(rf"([{BRANCH_RE}])年", text):
        found.append({"branch": match.group(1), "unit": "年",
                      "channel": infer_channel(text), "span": match.group(0)})
    # 三月/六月 etc. — month number words mapped loosely to earthly branches via 正月=寅
    month_words = {"正": "寅", "二": "卯", "三": "辰", "四": "巳", "五": "午", "六": "未",
                   "七": "申", "八": "酉", "九": "戌", "十": "亥", "十一": "子", "十二": "丑"}
    for word, branch in month_words.items():
        if re.search(rf"{word}月", text):
            found.append({"branch": branch, "unit": "月", "channel": infer_channel(text),
                          "span": f"{word}月"})
    # dedupe by branch+unit keep first
    seen = set()
    unique = []
    for item in found:
        key = (item["branch"], item["unit"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def main():
    rows = []
    for case in CASES:
        windows = extract_windows(case.get("o"), case.get("l"))
        if not windows:
            continue
        rows.append({
            "id": case["id"], "question": case.get("q"), "outcome": case.get("o"),
            "experience": case.get("l"), "windows": windows,
            "same_window_note": (
                "多通道同支同单位时可标 high；与书中应验支比对人工勾选 same/diff"
            ),
        })

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    lines = [
        "# 应期窗口回放清单（启发式，需人工勾选）",
        "",
        "从 CASES 结果/经验句抽出 `branch+unit+channel` 候选。",
        "解卦提交 `topic: window` 后，把程序 `windows` fact 的置信度与书中应验支对比：",
        "`same` = 同窗，`diff` = 不同窗（记入反例）。",
        "",
        f"- 抽出有应期表述的卦例 · {len(rows)}",
        "",
        "| # | 问事 | 书中结果 | 候选 window | 人工 same/diff | 备注 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        windows = "；".join(
            f"{w['branch']}{w['unit']}/{w['channel']}（{w['span']}）" for w in row["windows"]
        )
        lines.append(
            f"| {row['id']} | {row['question']} | {row['outcome']} | {windows} |  |  |"
        )
    lines.extend([
        "",
        "## 用法",
        "",
        "1. 对新解或书例回放，timing 提交对应 `window` 条目。",
        "2. 看 `windows` fact：同支同单位多通道 → `high`，单通道 → `candidate`。",
        "3. 与上表书中应验支比对，`diff` 写入本文件备注列，作为通道规则反例。",
        "4. 「当令/填实」缺失仅告警，不阻断提交。",
        "",
    ])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_MD} cases={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
