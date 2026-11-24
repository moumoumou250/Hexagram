#!/usr/bin/env python3
"""v3 规模与性能：gua.sql 大小、建库耗时、库文件大小、按键查询耗时；并跑 PLAN 第 5 节示例查询。"""
import os, sqlite3, time, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); SQL = os.path.join(HERE, '..', '..', 'database', 'gua.sql')
src = open(SQL, encoding='utf-8').read()
db = os.path.join(tempfile.mkdtemp(), 'gua.db')
t = time.time(); con = sqlite3.connect(db); con.executescript(src); con.commit(); t_exec = time.time() - t
con.execute('VACUUM'); con.close()
print(f'sqlite {sqlite3.sqlite_version}')
print(f'gua.sql {os.path.getsize(SQL):,} 字节；空库执行 {t_exec:.2f} 秒；建成库文件 {os.path.getsize(db):,} 字节')
con = sqlite3.connect(db)
for t_ in ('hexagram_transition', 'moving_line_change'):
    print(f'{t_}: {con.execute(f"select count(*) from {t_}").fetchone()[0]} 行')
def timeit(label, sql, *p, n=200):
    t = time.time()
    for _ in range(n): r = con.execute(sql, p).fetchall()
    print(f'{label}: {(time.time()-t)/n*1000:.3f} ms/次  → {r[:3]}{" …" if len(r) > 3 else ""}')
timeit('① 卦名+l1..l6', "SELECT changed_name FROM hexagram_change WHERE base_name='天雷无妄' AND l1=1 AND l2=1 AND l3=0 AND l4=0 AND l5=0 AND l6=0")
timeit('② 卦名+mask', "SELECT changed_name, relation_change FROM hexagram_change WHERE base_name='天雷无妄' AND move_mask=1")
timeit('③ 本爻变爻并排', "SELECT position, shi_ying, base_stem||base_branch||base_element||base_relative, changed_stem||changed_branch||changed_element||changed_relative, huitou, line_fanfu, jin_tui, hua_stage FROM change_board WHERE base_name='天雷无妄' AND move_mask=3 ORDER BY position")
timeit('④ 反查动爻', "SELECT move_mask, moving_positions FROM hexagram_change WHERE base_name='天雷无妄' AND changed_name='天地否'")
timeit('⑤ 某卦六冲变六合的动法', "SELECT move_mask, moving_positions, changed_name FROM hexagram_change WHERE base_name='天雷无妄' AND relation_change='六冲变六合'", n=50)
timeit('⑥ 世爻化回头克（全库计数）', "SELECT count(*) FROM change_board WHERE shi_ying='世' AND huitou='回头克'", n=5)
