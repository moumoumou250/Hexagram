"""Local CLI for executing one Jingfang reading step at a time."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .orchestrator import STEPS, Orchestrator
from .rule_data import ROOT


def read_json(path):
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description="Jingfang 单 Agent 顺序解卦")
    parser.add_argument("--log-dir", type=Path, default=ROOT / "reading-logs",
                        help="运行目录，默认项目下的 reading-logs")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="按 JSON 输入创建解卦")
    start.add_argument("file", help="JSON 文件，- 从标准输入读取")
    for name, help_text in (
        ("next", "查看下一步"), ("status", "查看保存的步骤状态"),
        ("validate", "核对引用并复算盘面"), ("export", "返回本次已保存的 Markdown 路径"),
        ("context", "读取当前步骤所需的规则路径和证据"),
        ("submit", "校验并保存当前步骤结果"),
        ("revise", "更正未完成记录的输入并从认卦重新执行"),
        ("outcome", "为已汇总记录追加应验登记"),
        ("dump", "只读按步汇总 journal 产物"),
    ):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("run_id")
        if name == "export":
            sub.add_argument("--html", action="store_true", help="校验并生成本次用户版 HTML")
            sub.add_argument("--allow-claims", action="store_true",
                             help="允许在摘要盘面断言冲突时仍导出 HTML")
        if name == "dump":
            sub.add_argument("--step", choices=STEPS, help="只看某一步")
            sub.add_argument("--json", action="store_true", help="输出完整结构化 dump")
            sub.add_argument("--html", action="store_true", help="导出分步产物网页")
        if name == "context":
            sub.add_argument("step", nargs="?", choices=STEPS)
        if name == "submit":
            sub.add_argument("step", choices=STEPS)
        if name in ("submit", "revise", "outcome"):
            sub.add_argument("file", help="JSON 文件，- 从标准输入读取")
        if name == "revise":
            sub.add_argument("reason")
    args = parser.parse_args()
    try:
        service = Orchestrator(args.log_dir)
        command = args.command
        if command == "start":
            result = service.start(read_json(args.file))
        elif command == "context":
            result = service.context(args.run_id, args.step)
        elif command == "submit":
            result = service.submit(args.run_id, args.step, read_json(args.file))
        elif command == "revise":
            result = service.revise(args.run_id, read_json(args.file), args.reason)
        elif command == "outcome":
            result = service.outcome(args.run_id, read_json(args.file))
        elif command == "export" and args.html:
            result = service.export_html(args.run_id, allow_claims=args.allow_claims)
        elif command == "dump":
            if args.html:
                result = service.dump_html(args.run_id, step=args.step)
            else:
                result = service.dump(args.run_id, step=args.step, include_detail=args.json)
                if not args.json:
                    print(result["text"], end="")
                    return 0
                result = {key: result[key] for key in ("run_id", "path", "state", "dump")}
        elif command == "validate":
            result = service.validate(args.run_id)
        else:
            result = service.status(args.run_id)
            if command == "next":
                result = {key: result[key] for key in ("run_id", "state", "next", "path")}
            elif command == "export":
                result = {key: result[key] for key in ("run_id", "state", "path")}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
