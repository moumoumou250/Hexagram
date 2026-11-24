#!/usr/bin/env python3
"""v3：01、04 改按 move_mask 查（并做反查核对）。用 skill 01–05 中写明的 SQL，原样走三个书中卦例，打印每步证据，供人工对照书中断语。"""
import os, sqlite3
HERE = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(':memory:'); con.executescript(open(os.path.join(HERE, '..', '..', 'database', 'gua.sql'), encoding='utf-8').read())
Q = lambda s, *p: con.execute(s, p).fetchall()
DEMO = [
 ('用神元神忌神仇神章：辰月戊申日占父近病', '乾为天', '4', '父母', 3, '辰', '戊申', '书断：取临月建之辰土；申冲寅暗动克辰；午化未合住；丑日冲未起床'),
 ('月破章：辰月戊子日占父何日归', '乾为天', '6', '父母', 6, '辰', '戊子', '书断：戌父月破化未空；卯日（破而逢合）得信，乙未日（出空）到家'),
 ('反伏章：卯月壬申日占随官府上任', '水地比', '2,3', '官鬼', 3, '卯', '壬申', '书断：世官临月建；内卦反吟有反复；世绝于申日又化回头冲克，大凶'),
]
for title, base, mv, ys, ypos, mb, day, book in DEMO:
    print('='*70); print(title); print(book)
    mask = sum(1 << (int(p) - 1) for p in mv.split(',') if p)
    chg = Q("SELECT changed_name FROM hexagram_change WHERE base_name = ? AND move_mask = ?", base, mask)[0][0]
    assert Q("SELECT move_mask FROM hexagram_change WHERE base_name = ? AND changed_name = ?", base, chg) == [(mask,)]   # 01 反查核对
    print(f'①认卦：{base} 动{mv} → {chg}')
    for r in Q("SELECT position, line_title, stem||branch||element, relative, shi_ying, coalesce(hidden_relative||hidden_branch,'') FROM hexagram_board WHERE name = ? ORDER BY position", base)[::-1]:
        print('   ', r)
    roles = Q("SELECT yuanshen, jishen, choushen FROM yongshen_roles WHERE yongshen = ?", ys)[0]
    print(f'②用神 {ys}（第{ypos}爻），原/忌/仇 = {roles}')
    br = Q("SELECT branch, element FROM hexagram_board WHERE name=? AND position=?", base, ypos)[0]
    st = Q("SELECT state, note FROM month_strength WHERE month_branch = ? AND element = ?", mb, br[1])[0]
    m = Q("SELECT wuxing, same_branch, chong, he, target_stage FROM branch_interaction WHERE actor = ? AND target = ?", mb, br[0])[0]
    d = Q("SELECT wuxing, same_branch, chong, he, target_stage FROM branch_interaction WHERE actor = ? AND target = ?", day[1], br[0])[0]
    kong = Q("SELECT kong_1, kong_2 FROM jiazi WHERE ganzhi = ?", day)[0]
    print(f'③用神{br[0]}{br[1]}：月令{st}；对月建(生克,临,冲,合,长生位)={m}；对日辰={d}；旬空={kong}')
    for r in Q("SELECT position, base_branch||'→'||changed_branch, changed_relative, huitou, hua_chong, hua_he, jin_tui, hua_stage FROM change_board WHERE base_name = ? AND move_mask = ? ORDER BY position", base, mask):
        print('④动爻', r)
    print('④卦级', Q("SELECT relation_change, inner_fanfu, outer_fanfu, gua_change, gua_fanyin FROM hexagram_change WHERE base_name = ? AND move_mask = ?", base, mask)[0])
    print('⑤候选应期（冲/合/值用神之支）', Q("SELECT actor, chong, he, same_branch FROM branch_interaction WHERE target = ? AND (chong = 1 OR he = 1 OR same_branch = 1)", br[0]))
