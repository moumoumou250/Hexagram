"""Local CLI for executing one Jingfang reading step at a time."""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .orchestrator import STEPS, Orchestrator
from .rule_data import ROOT, live_rules, rule_version

EXIT_OK = 0
EXIT_CHECK = 1
EXIT_USAGE = 2
EXIT_MISSING = 3
EXIT_SKIPPED = 4
MISSING_MARKERS = ("找不到", "步骤状态无效", "步骤顺序无效", "续跑状态缺失", "不含解卦编号")
CHECK_MARKERS = ("复算不一致", "重复的证据", "引用了已失效", "存在冲突或缺项")


def read_json(path):
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            if getattr(stream, "encoding", None) and stream.encoding.lower() == "utf-8":
                continue
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            continue


def resolve_log_dir(value):
    if value is not None:
        return Path(value)
    env = os.environ.get("JINGFANG_LOG_DIR")
    if env:
        return Path(env)
    return ROOT / "reading-logs"


def peel_option(argv, option):
    """Pull every --opt/--opt=VALUE out of argv; last value wins."""
    value = None
    rest = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == option and index + 1 < len(argv):
            value = argv[index + 1]
            index += 2
            continue
        if item.startswith(option + "="):
            value = item.split("=", 1)[1]
            index += 1
            continue
        rest.append(item)
        index += 1
    return value, rest


def version_text():
    return f"jingfang {__version__}\nrules {rule_version(live_rules())}"


def classify_error(error):
    message = str(error)
    if any(marker in message for marker in MISSING_MARKERS):
        return EXIT_MISSING
    if isinstance(error, ValueError) and any(marker in message for marker in CHECK_MARKERS):
        return EXIT_CHECK
    return EXIT_USAGE


def emit_json(result, *, indent=None):
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=indent))


def emit_text(text):
    print(text, end="" if text.endswith("\n") or text == "" else "\n")


def format_list_text(rows):
    if not rows:
        return "(无续跑记录)\n"
    lines = ["编号\t状态\t下一步\t本卦→变卦\t起卦时间"]
    for row in rows:
        when = row.get("cast_time") or row.get("created_at") or ""
        nxt = row.get("next") or "-"
        lines.append(f"{row['run_id']}\t{row['state']}\t{nxt}\t{row['chart']}\t{when}")
    return "\n".join(lines) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(description="Jingfang 单 Agent 顺序解卦")
    parser.add_argument("--log-dir", type=Path, default=None,
                        help="运行目录；默认 JINGFANG_LOG_DIR 或项目下 reading-logs")
    parser.add_argument("--version", action="version", version=version_text())
    parser.add_argument("--format", choices=("json", "text"), default="json",
                        help="多数命令的默认输出为 JSON；list/show 默认 text，加 --json 出 JSON")
    parser.add_argument("--quiet", action="store_true", help="成功时不向 stdout 打印")
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start", help="按 JSON 输入创建解卦")
    start.add_argument("file", help="JSON 文件，- 从标准输入读取")
    backfill = commands.add_parser("backfill", help="核对历史 Markdown，按需回填 SQLite 查询库")
    backfill.add_argument("--apply", action="store_true", help="写入通过校验且核心字段齐全的记录")

    listing = commands.add_parser("list", help="只读列出可续跑卦例")
    listing.add_argument("--state", choices=("running", "partial", "complete"),
                         help="按阅读状态过滤")
    listing.add_argument("--json", action="store_true", dest="as_json",
                         help="输出 JSON 数组")

    show = commands.add_parser("show", help="只读回看一卦（复用 dump 渲染）")
    show.add_argument("run_id")
    show.add_argument("--step", choices=STEPS, help="只看某一步")
    show.add_argument("--html", action="store_true", help="导出分步产物网页")
    show.add_argument("--json", action="store_true", dest="as_json",
                      help="输出完整结构化 dump")

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
            sub.add_argument("--json", action="store_true", dest="as_json",
                             help="输出完整结构化 dump")
            sub.add_argument("--html", action="store_true", help="导出分步产物网页")
        if name == "context":
            sub.add_argument("step", nargs="?", choices=STEPS)
        if name == "submit":
            sub.add_argument("step", choices=STEPS)
        if name in ("submit", "revise", "outcome"):
            sub.add_argument("file", help="JSON 文件，- 从标准输入读取")
        if name == "revise":
            sub.add_argument("reason")
    return parser


def run_command(service, args):
    command = args.command
    if command == "start":
        return service.start(read_json(args.file)), EXIT_OK, None
    if command == "backfill":
        return service.backfill(args.apply), EXIT_OK, None
    if command == "list":
        rows = service.list_readings(args.state)
        if getattr(args, "as_json", False):
            return rows, EXIT_OK, None
        return rows, EXIT_OK, format_list_text(rows)
    if command in ("show", "dump"):
        if args.html:
            return service.dump_html(args.run_id, step=args.step), EXIT_OK, None
        as_json = getattr(args, "as_json", False)
        result = service.dump(args.run_id, step=args.step, include_detail=as_json)
        if as_json:
            payload = {key: result[key] for key in ("run_id", "path", "state", "dump")}
            return payload, EXIT_OK, None
        return result, EXIT_OK, result["text"]
    if command == "context":
        return service.context(args.run_id, args.step), EXIT_OK, None
    if command == "submit":
        return service.submit(args.run_id, args.step, read_json(args.file)), EXIT_OK, None
    if command == "revise":
        return service.revise(args.run_id, read_json(args.file), args.reason), EXIT_OK, None
    if command == "outcome":
        return service.outcome(args.run_id, read_json(args.file)), EXIT_OK, None
    if command == "export" and args.html:
        return service.export_html(args.run_id, allow_claims=args.allow_claims), EXIT_OK, None
    if command == "validate":
        result = service.validate(args.run_id)
        code = EXIT_CHECK if result.get("claims", {}).get("conflicts") else EXIT_OK
        if result.get("board_consistent") is False:
            code = EXIT_CHECK
        return result, code, None

    result = service.status(args.run_id)
    if command == "next":
        result = {key: result[key] for key in ("run_id", "state", "next", "path")}
    elif command == "export":
        result = {key: result[key] for key in ("run_id", "state", "path")}
    return result, EXIT_OK, None


def main(argv=None):
    configure_stdio()
    raw = list(sys.argv[1:] if argv is None else argv)
    peeled_log_dir, rest = peel_option(raw, "--log-dir")
    peeled_format, rest = peel_option(rest, "--format")
    quiet = False
    kept = []
    for item in rest:
        if item == "--quiet":
            quiet = True
            continue
        kept.append(item)
    rest = kept
    parser = build_parser()
    args = parser.parse_args(rest)
    args.log_dir = resolve_log_dir(Path(peeled_log_dir) if peeled_log_dir else args.log_dir)
    if peeled_format:
        if peeled_format not in ("json", "text"):
            parser.error("--format 只接受 json 或 text")
        args.format = peeled_format
    if quiet:
        args.quiet = True
    try:
        service = Orchestrator(args.log_dir)
        result, code, text = run_command(service, args)
        if not args.quiet:
            if text is not None:
                emit_text(text)
            else:
                emit_json(result, indent=2 if args.format == "text" else None)
        return code
    except (ValueError, OSError, sqlite3.Error) as error:
        code = classify_error(error)
        parser.exit(code, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
