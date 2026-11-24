#!/usr/bin/env python3
"""v5 与 v4 整库语义比对：两库各建一份，逐表、逐视图按共有列双向 EXCEPT。
预期只有：新增规则表 gua_fanyin（2 行）；hexagram_transition、hexagram_change 新增列 gua_fanyin，非空仅乾为天↔坤为地 mask 63 两行；其余全部 0 差异。"""
import os, sqlite3, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
V4 = os.environ.get('V4_SQL', os.path.join(HERE, '..', '..', '..', 'Jingfang-v4', 'gua.sql'))
tmp = os.path.join(tempfile.mkdtemp(), 'v4.db')
d = sqlite3.connect(tmp); d.executescript(open(V4, encoding='utf-8').read()); d.close()
con = sqlite3.connect(':memory:'); con.executescript(open(os.path.join(HERE, '..', '..', 'database', 'gua.sql'), encoding='utf-8').read())
con.execute('ATTACH ? AS v4', (tmp,))
objs = lambda db: {r[0]: r[1] for r in con.execute(f"select name, type from {db}.sqlite_master where type in ('table','view')")}
o5, o4 = objs('main'), objs('v4')
cols = lambda db, t: [r[1] for r in con.execute(f'pragma {db}.table_xinfo({t})')]
bad = 0
added = sorted(set(o5) - set(o4)); removed = sorted(set(o4) - set(o5))
EXP_ADDED = ['gua_fanyin']; EXP_NEWCOL = {'hexagram_transition': ['gua_fanyin'], 'hexagram_change': ['gua_fanyin']}
print('新增对象:', added, ' 删除对象:', removed)
if added != EXP_ADDED or removed: bad += 1
for t in added: print(f"  {t}:", con.execute(f'select * from main.{t}').fetchall())
for t in sorted(set(o5) & set(o4)):
    c5, c4 = cols('main', t), cols('v4', t)
    newc = [c for c in c5 if c not in c4]; lost = [c for c in c4 if c not in c5]
    common = ', '.join(f'"{c}"' for c in c4 if c in c5)
    a = con.execute(f'select count(*) from (select {common} from main.{t} except select {common} from v4.{t})').fetchone()[0]
    b = con.execute(f'select count(*) from (select {common} from v4.{t} except select {common} from main.{t})').fetchone()[0]
    n4 = con.execute(f'select count(*) from v4.{t}').fetchone()[0]; n5 = con.execute(f'select count(*) from main.{t}').fetchone()[0]
    ok = a == 0 and b == 0 and n4 == n5 and not lost and newc == EXP_NEWCOL.get(t, []) and (o5[t] == 'table' or c5[:len(c4)] == c4)  # 视图旧列须为前缀；表的新列位于生成列 l1..l6 之前
    extra = ''
    if newc:
        nn = con.execute(f"select * from main.{t} where " + ' or '.join(f'"{c}" is not null' for c in newc)).fetchall()
        key = 'hexagram_id, move_mask' if t == 'hexagram_transition' else 'base_name, changed_name, move_mask'
        rows = con.execute(f"select {key}, {', '.join(newc)} from main.{t} where " + ' or '.join(f'"{c}" is not null' for c in newc)).fetchall()
        extra = f' 新增列 {newc} 非空 {len(nn)} 行: {rows}'
        if len(nn) != 2: ok = False
    bad += not ok
    print(f"{'OK  ' if ok else 'DIFF'} {t:22s} v4={n4:6d} v5={n5:6d} 共有列差异 v5-v4={a} v4-v5={b}{extra}")
print('V4 DIFFS (unexpected)', bad); sys.exit(1 if bad else 0)
