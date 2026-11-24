#!/usr/bin/env python3
"""卦例回归（v3）：1) 由动爻推变卦并与书中卦名核对（旧写法 moving_positions、新写法 move_mask 正查、按变卦反查 move_mask 各一条）；2) 书中可查表的断语要点逐条用 gua.sql 核对；
3) 维基文库录图与 gua.sql 盘面逐爻比对（报告录文差异，供人工对照 1925 本）。"""
import os, re, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from fixtures.book_cases import CASES
con = sqlite3.connect(':memory:'); con.executescript(open(os.path.join(HERE, '..', '..', 'gua.sql'), encoding='utf-8').read())
Q = lambda s, *p: con.execute(s, p).fetchall()
def one(s, *p):
    r = Q(s, *p); return r[0][0] if r else None
fails, total = [], 0
n_fwd = n_rev = 0
def check(cid, desc, ok):
    global total; total += 1
    if not ok: fails.append((cid, desc))
for c in CASES:
    cid = c['id']; mp = ','.join(map(str, sorted(c['mv'])))
    chg = one("select changed_name from hexagram_change where base_name=? and moving_positions=?", c['base'], mp)
    check(cid, f"变卦 {c['base']} 动{mp or '无'} → 应为{c['label']} 实得{chg}", chg == c['label'])
    mask = sum(1 << (p - 1) for p in c['mv'])
    chg2 = one("select changed_name from hexagram_change where base_name=? and move_mask=?", c['base'], mask)
    check(cid, f"mask 正查 {c['base']} mask={mask} → 应为{c['label']} 实得{chg2}", chg2 == c['label']); n_fwd += 1
    back = Q("select move_mask from hexagram_change where base_name=? and changed_name=?", c['base'], c['label'])
    check(cid, f"mask 反查 {c['base']}→{c['label']} 应为 mask={mask} 实得{back}", back == [(mask,)]); n_rev += 1
    hb = lambda pos, col: one(f"select {col} from hexagram_board where name=? and position=?", c['base'], pos)
    cb = lambda pos, col: one(f"select {col} from change_board where base_name=? and move_mask=? and position=?", c['base'], mask, pos)
    hx = lambda col: one(f"select {col} from hexagram_change where base_name=? and move_mask=?", c['base'], mask)
    for a in c['a']:
        k = a[0]
        if k == 'rel': ok = one("select hexagram_relation from hexagrams where name=?", c['base']) == a[1]
        elif k == 'change': ok = hx('relation_change') == a[1]
        elif k == 'fanfu': ok = hx('inner_fanfu' if a[1] == '内' else 'outer_fanfu') == a[2]
        elif k == 'gua_change': ok = hx('gua_change') == a[1]
        elif k == 'huitou': ok = cb(a[1], 'huitou') == a[2]
        elif k == 'jintui': ok = cb(a[1], 'jin_tui') == a[2]
        elif k == 'hua_stage': ok = cb(a[1], 'hua_stage') == a[2]
        elif k == 'hua_chong': ok = cb(a[1], 'hua_chong') == 1
        elif k == 'hua_he': ok = cb(a[1], 'hua_he') == 1
        elif k == 'chg_rel': ok = cb(a[1], 'changed_relative') == a[2]
        elif k == 'line': ok = (hb(a[1], 'relative'), hb(a[1], 'branch')) == (a[2], a[3])
        elif k == 'shi': ok = hb(a[1], 'shi_ying') == '世'
        elif k == 'hidden': ok = (hb(a[1], 'hidden_relative'), hb(a[1], 'hidden_branch')) == (a[2], a[3])
        elif k == 'yuepo': ok = one("select chong from branch_interaction where actor=? and target=?", c['m'], a[1]) == 1
        elif k == 'kong': ok = a[1] in (Q("select kong_1, kong_2 from jiazi where ganzhi=?", c['d']) or [()])[0]
        elif k == 'same': ok = one("select same_branch from branch_interaction where actor=? and target=?", a[1], a[2]) == 1
        elif k == 'chong': ok = one("select chong from branch_interaction where actor=? and target=?", a[1], a[2]) == 1
        elif k == 'he': ok = one("select he from branch_interaction where actor=? and target=?", a[1], a[2]) == 1
        elif k == 'wx': ok = one("select wuxing from branch_interaction where actor=? and target=?", a[1], a[2]) == a[3]
        elif k == 'stage': ok = one("select target_stage from branch_interaction where actor=? and target=?", a[1], a[2]) == a[3]
        elif k == 'xing': ok = one("select xing from branch_interaction where actor=? and target=?", a[1], a[2]) is not None
        elif k == 'sanhe': ok = sorted(Q("select sheng_branch, wang_branch, mu_branch from sanhe where element=?", a[1])[0]) == sorted(a[2])
        elif k == 'ms': ok = one("select state from month_strength where month_branch=? and element=?", a[1], a[2]) == a[3]
        elif k == 'liushen': ok = one("select spirit from liushen where day_stem=? and position=?", c['d'][0], a[1]) == a[2]
        else: raise ValueError(a)
        check(cid, f"{a}", ok)
# ---- 方案固定示例：天雷无妄 mask 1 / mask 3（PLAN-transition.md 第 2 节）----
WW = [
 ("select changed_name, relation_change, moving_mask, moving_positions from hexagram_change where base_name='天雷无妄' and move_mask=1", [('天地否', '六冲变六合', '100000', '1')]),
 ("select changed_name, relation_change, moving_mask, moving_positions from hexagram_change where base_name='天雷无妄' and move_mask=3", [('天水讼', None, '110000', '1,2')]),
 ("select changed_name from hexagram_change where base_name='天雷无妄' and l1=1 and l2=1 and l3=0 and l4=0 and l5=0 and l6=0", [('天水讼',)]),
 ("select position, shi_ying, base_stem||base_branch||base_element||base_relative, changed_stem||changed_branch||changed_element||changed_relative, changed_relative_own_palace, huitou, hua_chong, hua_he, jin_tui, hua_stage, fuyin_line from change_board where base_name='天雷无妄' and move_mask=1",
  [(1, '应', '庚子水父母', '乙未土妻财', '父母', '回头克', 0, 0, None, None, 0)]),
 ("select position, shi_ying, base_stem||base_branch||base_element||base_relative, changed_stem||changed_branch||changed_element||changed_relative, changed_relative_own_palace, huitou, hua_chong, hua_he, jin_tui, hua_stage, fuyin_line from change_board where base_name='天雷无妄' and move_mask=3 order by position",
  [(1, '应', '庚子水父母', '戊寅木兄弟', '父母', '动生变', 0, 0, None, None, 0), (2, '', '庚寅木兄弟', '戊辰土妻财', '子孙', '动克变', 0, 0, None, None, 0)]),
 ("select move_mask, moving_positions from hexagram_change where base_name='天雷无妄' and changed_name='天地否'", [(1, '1')]),
 ("select count(*) from change_board where base_name='天雷无妄' and move_mask=0", [(0,)]),
 ("select changed_name, moving_count from hexagram_change where base_name='天雷无妄' and move_mask=0", [('天雷无妄', 0)]),
 # v5 反伏章 1925 p88“如乾變坤是也”：卦之反吟
 ("select changed_name, gua_fanyin, inner_fanfu, outer_fanfu from hexagram_change where base_name='乾为天' and move_mask=63", [('坤为地', '反吟', None, None)]),
 ("select changed_name, gua_fanyin from hexagram_change where base_name='坤为地' and move_mask=63", [('乾为天', '反吟')]),
 ("select count(*) from hexagram_change where gua_fanyin is not null", [(2,)]),
]
n_ww = 0
for sql, exp in WW:
    got = Q(sql); n_ww += 1
    check('无妄', f"{sql[:60]}… 应为{exp} 实得{got}", got == exp)
# ---- 录图比对 ----
T = {'財':'财','孫':'孙','兄':'兄','鬼':'鬼'}
def norm(s): return ''.join(T.get(ch, ch) for ch in s)
charts = {}
cur_id = None
for line in open(os.path.join(HERE, '..', 'fixtures', 'book_charts_wikisource.txt'), encoding='utf-8'):
    m = re.match(r'### ([CV]\d+)', line)
    if m: cur_id = m.group(1); charts[cur_id] = []; continue
    if cur_id and re.search(r'[⚊⚋○ㄨ]', line) and not line.startswith('>>'):
        charts[cur_id].append(norm(line.strip()))
CELL = re.compile(r'(父母|兄弟|子孙|妻财|官鬼)([子丑寅卯辰巳午未申酉戌亥])([水火木金土])([⚊⚋○ㄨ])(世|應)?')
chart_diffs = []
for c in CASES:
    rows = charts.get(c['chart'], [])
    if len(rows) != 6: chart_diffs.append((c['id'], c['chart'], f'录图行数 {len(rows)}')); continue
    for i, row in enumerate(rows):
        pos = 6 - i
        cells = CELL.findall(row)
        if not cells: chart_diffs.append((c['id'], c['chart'], f'第{pos}爻无法解析')); continue
        rel, br, el, mk, sy = cells[0]
        db = Q("select relative, branch, polarity, shi_ying from hexagram_board where name=? and position=?", c['base'], pos)[0]
        pol = '阳' if mk in '⚊○' else '阴'
        moving = mk in '○ㄨ'
        sy = {'應':'应'}.get(sy, sy)
        if (rel, br, pol) != (db[0], db[1], db[2]): chart_diffs.append((c['id'], c['chart'], f'本卦第{pos}爻 录图{rel}{br}{pol} 库{db[0]}{db[1]}{db[2]}'))
        if (sy or '') != db[3]: chart_diffs.append((c['id'], c['chart'], f'第{pos}爻世应 录图{sy or "-"} 库{db[3] or "-"}'))
        if moving != (pos in c['mv']): chart_diffs.append((c['id'], c['chart'], f'第{pos}爻动静 录图{"动" if moving else "静"} 书例{"动" if pos in c["mv"] else "静"}'))
        if len(cells) > 1 and c['label'] != c['base']:
            rel2, br2 = cells[1][0], cells[1][1]
            want_br = one("select branch from hexagram_board where name=? and position=?", c['label'], pos)
            pe = one("select palace_element from hexagrams where name=?", c['base'])
            want_rel = one("select relative from liuqin_rule where palace_element=? and line_element=(select element from dizhi where branch=?)", pe, br2)
            if br2 != want_br: chart_diffs.append((c['id'], c['chart'], f'变卦第{pos}爻 录图{br2} 库{want_br}'))
            if rel2 != want_rel: chart_diffs.append((c['id'], c['chart'], f'变卦第{pos}爻六亲 录图{rel2} 按本宫应为{want_rel}'))
print(f'卦例 {len(CASES)} 个；核对 {total} 条（变卦推算 {len(CASES)} + mask 正查 {n_fwd} + mask 反查 {n_rev} + 断语查表 {total-len(CASES)-n_fwd-n_rev-n_ww}（按 move_mask 查） + 无妄固定示例 {n_ww}）；不符 {len(fails)} 条')
for f in fails: print('  FAIL', f)
print(f'维基文库录图与库比对：差异 {len(chart_diffs)} 处（录文问题，需对照 1925 本；目前仅卦例37，已目验 1925 本确认是录文错）')
for d in chart_diffs: print('  DIFF', d)
sys.exit(1 if fails else 0)
