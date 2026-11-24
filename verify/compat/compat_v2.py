#!/usr/bin/env python3
"""v3 与 v2 兼容性比对：v2 的 hexagram_change / change_board 是现算视图，v3 改读实表。
按 v2 全部旧列做双向 EXCEPT，要求 0 差异；另核对 hexagram_board 等其余视图与固定表逐行相同。"""
import os, sqlite3, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.environ.get('V2_SQL', os.path.join(HERE, '..', '..', '..', 'Jingfang-v2', 'gua.sql'))
tmp = os.path.join(tempfile.mkdtemp(), 'v2.db')
d = sqlite3.connect(tmp); d.executescript(open(V2, encoding='utf-8').read()); d.close()
con = sqlite3.connect(':memory:'); con.executescript(open(os.path.join(HERE, '..', '..', 'gua.sql'), encoding='utf-8').read())
con.execute('ATTACH ? AS v2', (tmp,))
OBJ = {
 'hexagram_change': 'base_id, base_name, changed_id, changed_name, moving_mask, moving_positions, moving_count, base_relation, changed_relation, relation_change, inner_fanfu, outer_fanfu, gua_change',
 'change_board': 'base_id, base_name, changed_id, changed_name, position, base_polarity, base_stem, base_branch, base_element, base_relative, changed_stem, changed_branch, changed_element, changed_relative, changed_relative_own_palace, huitou, hua_chong, hua_he, jin_tui, hua_stage, fuyin_line',
}
for t in [r[0] for r in con.execute("select name from v2.sqlite_master where type in ('table','view') and name not in ('hexagram_change','change_board') order by name")]:
    OBJ[t] = '*'
bad = 0
for t, cols in OBJ.items():
    a = con.execute(f'select count(*) from (select {cols} from main.{t} except select {cols} from v2.{t})').fetchone()[0]
    b = con.execute(f'select count(*) from (select {cols} from v2.{t} except select {cols} from main.{t})').fetchone()[0]
    n2 = con.execute(f'select count(*) from v2.{t}').fetchone()[0]; n3 = con.execute(f'select count(*) from main.{t}').fetchone()[0]
    ok = a == 0 and b == 0 and n2 == n3
    bad += not ok
    print(f"{'OK  ' if ok else 'DIFF'} {t:22s} v2={n2:6d} v3={n3:6d} v3-v2={a} v2-v3={b}")
# 旧列顺序必须是新视图的前缀
for t, cols in list(OBJ.items())[:2]:
    new = [r[1] for r in con.execute(f'pragma main.table_info({t})')]; old = [r[1] for r in con.execute(f'pragma v2.table_info({t})')]
    ok = new[:len(old)] == old; bad += not ok
    print(f"{'OK  ' if ok else 'DIFF'} {t} 旧列顺序为前缀；新增列 {new[len(old):]}")
print('COMPAT DIFFS', bad); sys.exit(1 if bad else 0)
