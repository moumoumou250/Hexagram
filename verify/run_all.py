#!/usr/bin/env python3
"""运行当前项目的回归验证。"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    ("tools/build_gua_sql.py", "--check"),
    ("verify/sql/oracle_v3.py",),
    ("verify/cases/cases_check.py",),
    ("verify/cases/skill_walkthrough.py",),
    ("verify/workflow/journal_check.py",),
    ("verify/workflow/audit_check.py",),
    ("verify/workflow/dump_check.py",),
    ("verify/workflow/forces_unit_check.py",),
    ("verify/workflow/interpretation_check.py",),
)
COMPAT_CHECKS = (
    ("verify/compat/compat_v2.py",),
    ("verify/compat/diff_v4.py",),
    ("verify/compat/audit_regress.py",),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compat", action="store_true", help="同时执行依赖外部资料的历史版本对照")
    parser.add_argument("--report", type=Path, help="把验证输出另存为 UTF-8 报告")
    args = parser.parse_args()
    checks = CHECKS + COMPAT_CHECKS if args.compat else CHECKS
    report = []
    failed = 0
    for check in checks:
        heading = f"$ python -X utf8 {' '.join(check)}"
        print(heading, flush=True)
        result = subprocess.run(
            [sys.executable, "-X", "utf8", *check], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8",
        )
        output = result.stdout + f"exit={result.returncode}\n"
        print(output, end="", flush=True)
        report.append(f"{heading}\n{output}")
        failed += result.returncode != 0
    summary = f"验证项 {len(checks)}，失败 {failed}"
    print(summary)
    if args.report:
        args.report.write_text("\n".join([*report, summary]) + "\n", encoding="utf-8")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
