#!/usr/bin/env python3
"""依次运行全部验证，输出写入 ../docs/verification/VERIFY.txt。"""
import os, subprocess, sys, datetime
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
STEPS = ['verify/build_gua_sql.py', 'verify/oracle_v3.py', 'verify/compat/compat_v2.py', 'verify/compat/diff_v4.py', 'verify/cases/cases_check.py', 'verify/compat/audit_regress.py', 'verify/cases/skill_walkthrough.py', 'verify/perf_size.py']
out = [f"# Jingfang v5 验证输出（v4 + 库内写入乾坤互变卦反吟）  {datetime.datetime.now(ZoneInfo("Asia/Singapore")):%Y-%m-%d %H:%M} (UTC+8)\n"]
bad = 0
for s in STEPS:
    r = subprocess.run([sys.executable, s], cwd=ROOT, capture_output=True, text=True)
    out.append(f"$ python3 {s}\n{r.stdout}{r.stderr}exit={r.returncode}\n")
    bad += r.returncode != 0
out.append(f"ALL STEPS EXIT 0: {'YES' if bad == 0 else 'NO'}\n")
open(os.path.join(ROOT, 'docs', 'verification', 'VERIFY.txt'), 'w', encoding='utf-8').write('\n'.join(out))
print('steps failed:', bad); sys.exit(1 if bad else 0)
