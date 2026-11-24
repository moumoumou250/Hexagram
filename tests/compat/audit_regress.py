#!/usr/bin/env python3
"""全书 258 例回归（在 ../../audit-v3）：按 v5 skill 规则 + 本包 gua.sql 跑，与 expected_flags_v5.json 比对；
再用 v3 规则 + 本包 gua.sql 跑一遍，确认相对 v3 基线只有 IXI03（乾变坤卦反吟）由“项目错误”转为一致。"""
import os, subprocess, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); GUA = os.path.abspath(os.path.join(HERE, '..', '..', 'database', 'gua.sql'))
AUD = os.environ.get('AUDIT_DIR', os.path.join(HERE, '..', '..', '..', 'audit-v3'))
if not os.path.isdir(AUD): print('audit-v3 不在，跳过'); sys.exit(0)
r = subprocess.run([sys.executable, 'src/run_all.py', '--skill', 'v5', '--gua', GUA, '--check'], cwd=AUD, capture_output=True, text=True)
print(r.stdout.strip()); bad = r.returncode
r2 = subprocess.run([sys.executable, 'src/run_all.py', '--skill', 'v3', '--gua', GUA, '--check'], cwd=AUD, capture_output=True, text=True)
diffs = [l for l in r2.stdout.splitlines() if l.startswith('DIFF')]
print('v3 规则 + v5 库 相对 v3 基线的变化：', diffs)
ok2 = [d.split()[1] for d in diffs] == ['IXI03'] and '一致' in r2.stdout.split('got')[-1].split('\n')[0]
print('只变 IXI03 且转为一致：', 'YES' if ok2 else 'NO')
subprocess.run([sys.executable, 'src/run_all.py', '--check'], cwd=AUD, capture_output=True)   # 还原 out/ 为 v3 基线
sys.exit(1 if (bad or not ok2) else 0)
