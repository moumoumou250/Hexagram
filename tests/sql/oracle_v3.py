#!/usr/bin/env python3
"""v3 独立 oracle（在 v2 oracle 基础上增加 Part 5、Part 6）：
1) 运行 oracle_v1_part（原三表 64 卦/384 爻/56 伏神逐字段重算）；
2) 用与 build_gua_sql.py 不同的算法独立重算全部新增固定表与视图，逐行比对；
3) 反向测试：写入错误数据，确认 CHECK/触发器能拦住。
4) Part 5：算法 B（整数卦码异或、地支序号算术）重算 hexagram_transition、moving_line_change 全部行全部字段；
5) Part 6：两张新表的反向测试（约束、触发器、integrity_issues）。
v5：卦之反吟（gua_fanyin）按 1925 本反伏章 p88“如乾變坤是也”独立写死为“卦码全阳↔全阴”，Part 2/3/5 比对，Part 6 加反向测试。
输出 MISMATCHES 总数；要求为 0。"""
import os, sys, sqlite3, runpy, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    g = runpy.run_path(os.path.join(HERE, 'oracle_v1_part.py'))
print('== Part 1: 原三表（v1 oracle）'); print(buf.getvalue().strip())
con, ORACLE, TRI, NAJIA_O, BR_ELEM = g['con'], g['ORACLE'], g['TRI'], g['NAJIA'], g['BR_ELEM']
mism = list(g['mism'])
cur = con.cursor()
BR = '子丑寅卯辰巳午未申酉戌亥'; ST = '甲乙丙丁戊己庚辛壬癸'; EL = '木火土金水'
def gen(e): return EL[(EL.index(e)+1) % 5]          # 我生
def kill(e): return EL[(EL.index(e)+2) % 5]         # 我克
def rel_of(a, b):  # a 对 b
    return '比和' if a==b else '生' if gen(a)==b else '克' if kill(a)==b else '被生' if gen(b)==a else '被克'
def cmp(name, sql, expected):
    got = set(tuple(r) for r in cur.execute(sql))
    exp = set(tuple(r) for r in expected)
    extra, miss = got-exp, exp-got
    for r in sorted(extra, key=str)[:20]: mism.append((name, '多出/不符', r))
    for r in sorted(miss, key=str)[:20]: mism.append((name, '缺少/应为', r))
    print(f'{name:22s} rows db={len(got):5d} oracle={len(exp):5d} diff={len(extra)+len(miss)}')
print('\n== Part 2: 新增固定表')
cmp('wuxing', 'select element, sheng, ke from wuxing', [(e, gen(e), kill(e)) for e in EL])
cmp('wuxing_relation', 'select * from wuxing_relation', [(a, b, rel_of(a, b)) for a in EL for b in EL])
cmp('tiangan', 'select stem, element, polarity from tiangan', [(s, EL[i//2], '阳' if i%2==0 else '阴') for i, s in enumerate(ST)])
# 地支五行：寅卯木 巳午火 申酉金 亥子水 辰戌丑未土（按季：每季首两支本气，第三支土）
season = {}
for start, e in ((2,'木'),(5,'火'),(8,'金'),(11,'水')):
    season[BR[start%12]] = e; season[BR[(start+1)%12]] = e; season[BR[(start+2)%12]] = '土'
cmp('dizhi', 'select branch, element, polarity, month_no from dizhi',
    [(b, season[b], '阳' if i%2==0 else '阴', (i-2)%12+1) for i, b in enumerate(BR)])
FAMILY = {'乾':'父','坤':'母','震':'长男','坎':'中男','艮':'少男','巽':'长女','离':'中女','兑':'少女'}
IMAGE = g['IMAGE']; TRI_ELEM = g['TRI_ELEM']
cmp('trigrams', 'select trigram, code, image, element, family, yinyang from trigrams',
    [(t, ''.join(map(str, v)), IMAGE[t], TRI_ELEM[t], FAMILY[t], '阳' if sum(v)%2==1 else '阴') for t, v in TRI.items()])
cmp('najia', 'select * from najia', [(t, h, i+1, v[k][0], v[k][1][i]) for t, v in NAJIA_O.items() for k, h in ((0,'内'),(1,'外')) for i in range(3)])
cmp('liuqin_rule', 'select * from liuqin_rule', [(p, e, g['relative'](p, e)) for p in EL for e in EL])
CYCLE = ['父母','兄弟','子孙','妻财','官鬼']  # 父母生兄弟(我)…官鬼生父母
def prev(r, k=1): return CYCLE[(CYCLE.index(r)-k) % 5]
cmp('yongshen_roles', 'select * from yongshen_roles', [(r, prev(r), prev(r, 2), prev(r, 3)) for r in CYCLE])
cmp('dizhi_chong', 'select * from dizhi_chong', [(BR[i], BR[(i+6)%12]) for i in range(12)])
HE_O = [(BR[i], BR[(1-i)%12]) for i in range(12)]   # 子丑、寅亥…：序号和为 1 (mod 12)
cmp('dizhi_he', 'select * from dizhi_he', HE_O)
# 三合：长生、帝旺、墓 = 各行长生支起，+4，+8
CS_START = {'木':'亥','火':'寅','金':'巳','水':'申'}
cmp('sanhe', 'select * from sanhe', [(e, s, BR[(BR.index(s)+4)%12], BR[(BR.index(s)+8)%12]) for e, s in CS_START.items()])
cmp('sanxing(1925原文)', 'select * from sanxing',
    [('寅','巳','刑'),('巳','申','刑'),('子','卯','刑'),('卯','子','刑')] + [(a,b,'相刑') for a,b in (('丑','戌'),('戌','丑'),('未','辰'),('辰','未'))] + [(x,x,'自刑') for x in '辰午酉亥'])
CS_START2 = dict(CS_START, 土='申')   # 土随水
cmp('changsheng', 'select element, stage, branch from changsheng',
    [(e, st, BR[(BR.index(s)+off)%12]) for e, s in CS_START2.items() for st, off in (('长生',0),('帝旺',4),('墓',8),('绝',9))])
ms = []
for mb in BR:
    me = season[mb]
    for e in EL:
        ms.append((mb, e, '旺' if e==me else '相' if e==gen(me) else '休囚'))
cmp('month_strength', 'select month_branch, element, state from month_strength', ms)
cmp('month_strength余气', "select month_branch, element from month_strength where note like '%余气%' and state='休囚'", [('未','火'),('丑','水')])
jz = []
for i in range(60):
    head = i - i % 10
    kong = (BR[(head+10)%12], BR[(head+11)%12])
    jz.append((i+1, ST[i%10]+BR[i%12], ST[head%10]+BR[head%12], kong[0], kong[1]))
cmp('jiazi(旬空)', 'select seq, ganzhi, xun_head, kong_1, kong_2 from jiazi', jz)
jt = []
for a in BR:
    for b in BR:
        d = (BR.index(b)-BR.index(a)) % 12
        if season[a]==season[b]!='土' and d==1: jt += [(a,b,'进神'),(b,a,'退神')]
        if season[a]==season[b]=='土' and d==3 and not (a=='戌' and b=='丑'): jt += [(a,b,'进神'),(b,a,'退神')]
cmp('jin_tui(1925七对)', 'select * from jin_tui', jt)
SP = ['青龙','朱雀','勾陈','螣蛇','白虎','玄武']
START = {'甲':0,'乙':0,'丙':1,'丁':1,'戊':2,'己':3,'庚':4,'辛':4,'壬':5,'癸':5}
cmp('liushen', 'select * from liushen', [(s, p, SP[(START[s]+p-1)%6]) for s in ST for p in range(1,7)])
ff = []
for h, k in (('内',0),('外',1)):
    for a in TRI:
        for b in TRI:
            if a==b: continue
            A, B = NAJIA_O[a][k][1], NAJIA_O[b][k][1]
            if all(BR.index(x)==(BR.index(y)+6)%12 for x, y in zip(A, B)): ff.append((h, a, b, '反吟'))
            if A==B: ff.append((h, a, b, '伏吟'))
cmp('trigram_fanfu', 'select * from trigram_fanfu', ff)
NAME = {'生':'化生','克':'化克','比和':'比和','被生':'化去生','被克':'化去不克'}
# v5 卦之反吟规则表：书中只举乾变坤（1925 p88），互变两向
cmp('gua_fanyin', 'select from_trigram, to_trigram, kind from gua_fanyin', [('乾', '坤', '反吟'), ('坤', '乾', '反吟')])
cmp('trigram_change', 'select * from trigram_change', [(a, b, NAME[rel_of(TRI_ELEM[b], TRI_ELEM[a])]) for a in TRI for b in TRI if a!=b])

print('\n== Part 3: 视图')
code = {hid: ''.join('1' if l['polarity']=='阳' else '0' for l in h['lines']) for hid, h in ORACLE.items()}
cmp('hexagram_code', 'select hexagram_id, name, code from hexagram_code', [(hid, h['name'], code[hid]) for hid, h in ORACLE.items()])
hc = []
for bi, b in ORACLE.items():
    for ci, c in ORACLE.items():
        mask = ''.join('1' if x!=y else '0' for x, y in zip(code[bi], code[ci]))
        mp = ','.join(str(i+1) for i, m in enumerate(mask) if m=='1')
        rc = (b['hexagram_relation']+'变'+c['hexagram_relation']) if mp and b['hexagram_relation']!='无' and c['hexagram_relation']!='无' else None
        def fan(k, x, y):
            for r in ff:
                if r[0]==k and r[1]==x and r[2]==y: return r[3]
        inner = fan('内', b['lower_trigram'], c['lower_trigram']); outer = fan('外', b['upper_trigram'], c['upper_trigram'])
        gc = NAME[rel_of(TRI_ELEM[c['upper_trigram']], TRI_ELEM[b['upper_trigram']])] if (b['upper_trigram']==b['lower_trigram'] and c['upper_trigram']==c['lower_trigram'] and bi!=ci) else None
        gf = '反吟' if {code[bi], code[ci]} == {'111111', '000000'} else None   # v5：六爻全阳↔全阴（乾变坤、坤变乾）
        hc.append((b['name'], c['name'], mask, mp, len(mp.replace(',','')), rc, inner, outer, gc, gf))
cmp('hexagram_change', 'select base_name, changed_name, moving_mask, moving_positions, moving_count, relation_change, inner_fanfu, outer_fanfu, gua_change, gua_fanyin from hexagram_change', hc)
JT = {(a,b):k for a,b,k in jt}
CSB = {(e, BR[(BR.index(s)+off)%12]): st for e, s in CS_START2.items() for st, off in (('长生',0),('帝旺',4),('墓',8),('绝',9))}
HU = {'生':'回头生','克':'回头克','比和':'比和','被生':'动生变','被克':'动克变'}
cb = []
for bi, b in ORACLE.items():
    for ci, c in ORACLE.items():
        for p in range(6):
            x, y = b['lines'][p], c['lines'][p]
            if x['polarity']==y['polarity']: continue
            cb.append((b['name'], c['name'], p+1, x['branch'], x['relative'], y['branch'], g['relative'](b['palace_element'], y['element']),
                       y['relative'], HU[rel_of(y['element'], x['element'])], int((BR.index(x['branch'])-BR.index(y['branch']))%12==6),
                       int((BR.index(x['branch'])+BR.index(y['branch']))%12==1), JT.get((x['branch'], y['branch'])),
                       CSB.get((x['element'], y['branch'])), int(x['branch']==y['branch'])))
cmp('change_board', 'select base_name, changed_name, position, base_branch, base_relative, changed_branch, changed_relative, changed_relative_own_palace, huitou, hua_chong, hua_he, jin_tui, hua_stage, fuyin_line from change_board', cb)
XING = {('寅','巳'):'刑',('巳','申'):'刑',('子','卯'):'刑',('卯','子'):'刑',('丑','戌'):'相刑',('戌','丑'):'相刑',('未','辰'):'相刑',('辰','未'):'相刑',('辰','辰'):'自刑',('午','午'):'自刑',('酉','酉'):'自刑',('亥','亥'):'自刑'}
bi_ = [(a, t, rel_of(season[a], season[t]), int(a==t), int((BR.index(a)-BR.index(t))%12==6), int((BR.index(a)+BR.index(t))%12==1),
        CSB.get((season[t], a)), XING.get((a, t))) for a in BR for t in BR]
cmp('branch_interaction', 'select actor, target, wuxing, same_branch, chong, he, target_stage, xing from branch_interaction', bi_)
cmp('integrity_issues', 'select * from integrity_issues', [])
cmp('hexagram_board(原视图)', 'select count(*), count(distinct name) from hexagram_board', [(384, 64)])

print('\n== Part 4: 反向测试（应全部被拦截）')
NEG = [  # (说明, 期望报错片段, SQL)
 ('爻题与阴阳不符', 'line_title', "DELETE FROM hidden_spirits WHERE hexagram_id=2; DELETE FROM hexagram_lines WHERE hexagram_id=2 AND position=1; INSERT INTO hexagram_lines VALUES (2,1,'阴','初九','乙','未','土','兄弟')"),
 ('地支五行不符', 'element = substr', "DELETE FROM hidden_spirits WHERE hexagram_id=2; DELETE FROM hexagram_lines WHERE hexagram_id=2 AND position=1; INSERT INTO hexagram_lines VALUES (2,1,'阴','初六','乙','未','火','父母')"),
 ('纳甲不符', '浑天甲子', "DELETE FROM hidden_spirits WHERE hexagram_id=2; DELETE FROM hexagram_lines WHERE hexagram_id=2 AND position=1; INSERT INTO hexagram_lines VALUES (2,1,'阴','初六','乙','丑','土','兄弟')"),
 ('六亲不符', '六亲与本卦宫', "DELETE FROM hidden_spirits WHERE hexagram_id=2; DELETE FROM hexagram_lines WHERE hexagram_id=2 AND position=1; INSERT INTO hexagram_lines VALUES (2,1,'阴','初六','乙','未','土','父母')"),
 ('阴阳与卦画不符', '阴阳与上下卦', "DELETE FROM hidden_spirits WHERE hexagram_id=2; DELETE FROM hexagram_lines WHERE hexagram_id=2 AND position=1; INSERT INTO hexagram_lines VALUES (2,1,'阳','初九','乙','未','土','兄弟')"),
 ('伏神六亲已出现', '已在本卦出现', "INSERT INTO hidden_spirits VALUES (1,1,'甲','子','水','子孙')"),
 ('伏神不取首卦同位', '本宫首卦同位', "DELETE FROM hidden_spirits WHERE hexagram_id=27 AND position=5; INSERT INTO hidden_spirits VALUES (27,5,'辛','午','火','子孙')"),
 ('世爻与卦宫阶段不符', 'shi_line = CASE', "DELETE FROM hidden_spirits WHERE hexagram_id=25; DELETE FROM hexagram_lines WHERE hexagram_id=25; DELETE FROM hexagrams WHERE hexagram_id=25; INSERT INTO hexagrams VALUES (25,'天雷无妄','乾','震','巽','木','四世',5,2,'六冲')"),
 ('宫五行不符', 'palace_element = CASE', "DELETE FROM hidden_spirits WHERE hexagram_id=25; DELETE FROM hexagram_lines WHERE hexagram_id=25; DELETE FROM hexagrams WHERE hexagram_id=25; INSERT INTO hexagrams VALUES (25,'天雷无妄','乾','震','巽','金','四世',4,1,'六冲')"),
 ('固定盘只读', '只读', "UPDATE hexagram_lines SET element='火' WHERE hexagram_id=1 AND position=1"),
 ('地支表五行', 'element = substr', "UPDATE dizhi SET element='金' WHERE branch='子'"),
 ('十二长生只收四位', "stage IN", "INSERT INTO changsheng VALUES ('金','沐浴','午','x')"),
]
CLR = 'DELETE FROM moving_line_change; DELETE FROM hexagram_transition; '
NEG = [(l, w, (CLR + q) if q.lstrip().startswith('DELETE') else q) for l, w, q in NEG]  # v3：新表外键引用原表，删原表行前先清空新表
for label, want, sql in NEG:
    cur.execute('SAVEPOINT neg')
    try:
        for s in sql.split(';'):
            if s.strip(): cur.execute(s)
        ok = False; msg = '未被拦截'
    except sqlite3.DatabaseError as e:
        msg = str(e).split('\n')[0]; ok = want in str(e)
    cur.execute('ROLLBACK TO neg'); cur.execute('RELEASE neg')
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {msg}")
    if not ok: mism.append(('negative', label, msg))

print('\n== Part 5: 动变预计算实表（算法 B：整数卦码异或；地支序号算术）')
icode = {hid: sum((1 if l['polarity']=='阳' else 0) << k for k, l in enumerate(h['lines'])) for hid, h in ORACLE.items()}
by_code = {v: k for k, v in icode.items()}
def ff_of(k, x, y):
    for r in ff:
        if r[0]==k and r[1]==x and r[2]==y: return r[3]
T_EXP, M_EXP = [], []
for bi, b in ORACLE.items():
    for mask in range(64):
        ci = by_code[icode[bi] ^ mask]; c = ORACLE[ci]
        bits = [(mask >> k) & 1 for k in range(6)]
        pos = [k+1 for k in range(6) if bits[k]]
        rc = (b['hexagram_relation']+'变'+c['hexagram_relation']) if mask and '无' not in (b['hexagram_relation'], c['hexagram_relation']) else None
        pure = lambda h: h['upper_trigram']==h['lower_trigram']
        gc = NAME[rel_of(TRI_ELEM[c['upper_trigram']], TRI_ELEM[b['upper_trigram']])] if pure(b) and pure(c) and mask else None
        T_EXP.append((bi, mask, ci, bin(mask).count('1'), ','.join(map(str, pos)), int(any(bits[:3])), int(any(bits[3:])), rc,
                      ff_of('内', b['lower_trigram'], c['lower_trigram']), ff_of('外', b['upper_trigram'], c['upper_trigram']), gc,
                      '反吟' if {icode[bi], icode[ci]} == {0, 63} else None, *bits))
        for p in pos:
            x, y = b['lines'][p-1], c['lines'][p-1]
            ix, iy = BR.index(x['branch']), BR.index(y['branch'])
            chong = int((ix-iy) % 12 == 6); fu = int(ix == iy)
            M_EXP.append((bi, mask, p, x['polarity'], x['stem'], x['branch'], x['element'], x['relative'],
                          y['polarity'], y['stem'], y['branch'], y['element'], g['relative'](b['palace_element'], y['element']),
                          HU[rel_of(y['element'], x['element'])], chong, int((ix+iy) % 12 == 1), JT.get((x['branch'], y['branch'])),
                          CSB.get((x['element'], y['branch'])), fu, '反吟' if chong else '伏吟' if fu else None))
cmp('hexagram_transition', 'select hexagram_id, move_mask, changed_hexagram_id, move_count, move_positions, inner_changed, outer_changed, relation_change, inner_fanfu, outer_fanfu, gua_change, gua_fanyin, l1, l2, l3, l4, l5, l6 from hexagram_transition', T_EXP)
cmp('moving_line_change', 'select hexagram_id, move_mask, position, base_polarity, base_stem, base_branch, base_element, base_relative, changed_polarity, changed_stem, changed_branch, changed_element, changed_relative, huitou, hua_chong, hua_he, jin_tui, hua_stage, fuyin_line, line_fanfu from moving_line_change', M_EXP)
cmp('hexagram_change(新列)', 'select base_id, move_mask, l1||l2||l3||l4||l5||l6 = moving_mask, inner_changed, outer_changed from hexagram_change',
    [(r[0], r[1], 1, r[5], r[6]) for r in T_EXP])
cmp('卦反吟(v5)', 'select base_name, changed_name, move_mask from hexagram_change where gua_fanyin is not null', [('乾为天', '坤为地', 63), ('坤为地', '乾为天', 63)])
cmp('change_board(新列)', 'select base_id, move_mask, position, changed_polarity, line_fanfu, shi_ying from change_board',
    [(r[0], r[1], r[2], r[8], r[19], '世' if ORACLE[r[0]]['shi_line']==r[2] else '应' if ORACLE[r[0]]['ying_line']==r[2] else '') for r in M_EXP])
cmp('行数', "select (select count(*) from hexagram_transition), (select count(*) from moving_line_change), (select count(*) from moving_line_change where move_mask=0)", [(4096, 12288, 0)])
cmp('integrity_issues(v3)', 'select * from integrity_issues', [])

print('\n== Part 6: 新表反向测试（应全部被拦截或报出）')
TC_ = 'hexagram_id, move_mask, changed_hexagram_id, move_count, move_positions, inner_changed, outer_changed, relation_change, inner_fanfu, outer_fanfu, gua_change'
MC_ = 'hexagram_id, move_mask, position, base_polarity, base_stem, base_branch, base_element, base_relative, changed_polarity, changed_stem, changed_branch, changed_element, changed_relative, huitou, hua_chong, hua_he, jin_tui, hua_stage, fuyin_line'
DEL_T = "DELETE FROM moving_line_change WHERE hexagram_id=25 AND move_mask=1; DELETE FROM hexagram_transition WHERE hexagram_id=25 AND move_mask=1; "
DEL_M = "DELETE FROM moving_line_change WHERE hexagram_id=25 AND move_mask=1; "
NEG2 = [  # 无妄=25；mask1 正确行：(25,1,12,1,'1',1,0,'六冲变六合',NULL,NULL,NULL) / (25,1,1,'阳','庚','子','水','父母','阴','乙','未','土','妻财','回头克',0,0,NULL,NULL,0)
 ('变卦id写错', '翻爻所得', DEL_T + f"INSERT INTO hexagram_transition ({TC_}) VALUES (25,1,6,1,'1',1,0,NULL,NULL,NULL,NULL)"),
 ('静卦mask0给了别的变卦', '翻爻所得', "DELETE FROM hexagram_transition WHERE hexagram_id=25 AND move_mask=0; " + f"INSERT INTO hexagram_transition ({TC_}) VALUES (25,0,12,0,'',0,0,NULL,NULL,NULL,NULL)"),
 ('move_count写错', 'move_count', DEL_T + f"INSERT INTO hexagram_transition ({TC_}) VALUES (25,1,12,2,'1',1,0,'六冲变六合',NULL,NULL,NULL)"),
 ('move_positions写错', 'move_positions', DEL_T + f"INSERT INTO hexagram_transition ({TC_}) VALUES (25,1,12,1,'2',1,0,'六冲变六合',NULL,NULL,NULL)"),
 ('六冲变六合漏标', '六冲六合变化', DEL_T + f"INSERT INTO hexagram_transition ({TC_}) VALUES (25,1,12,1,'1',1,0,NULL,NULL,NULL,NULL)"),
 ('内卦反吟误标', '内卦反吟伏吟', DEL_T + f"INSERT INTO hexagram_transition ({TC_}) VALUES (25,1,12,1,'1',1,0,'六冲变六合','反吟',NULL,NULL)"),
 ('动爻位不在mask内', '不在 move_mask 内', DEL_M + f"INSERT INTO moving_line_change ({MC_}) VALUES (25,1,2,'阴','庚','寅','木','兄弟','阳','乙','巳','火','子孙','动生变',0,0,NULL,NULL,0)"),
 ('本爻与hexagram_lines不符', '本爻与 hexagram_lines', DEL_M + f"INSERT INTO moving_line_change ({MC_}) VALUES (25,1,1,'阳','庚','子','水','兄弟','阴','乙','未','土','妻财','回头克',0,0,NULL,NULL,0)"),
 ('变爻干支不符', '变爻与变卦同位爻', DEL_M + f"INSERT INTO moving_line_change ({MC_}) VALUES (25,1,1,'阳','庚','子','水','父母','阴','乙','丑','土','妻财','回头克',0,0,NULL,NULL,0)"),
 ('变爻六亲按变卦自身宫', '按本卦宫五行', DEL_M + f"INSERT INTO moving_line_change ({MC_}) VALUES (25,1,1,'阳','庚','子','水','父母','阴','乙','未','土','父母','回头克',0,0,NULL,NULL,0)"),
 ('变爻阴阳未翻转', '变爻与变卦同位爻', DEL_M + f"INSERT INTO moving_line_change ({MC_}) VALUES (25,1,1,'阳','庚','子','水','父母','阳','乙','未','土','妻财','回头克',0,0,NULL,NULL,0)"),
 ('伏吟标志与地支不符', 'fuyin_line', DEL_M + f"INSERT INTO moving_line_change ({MC_}) VALUES (25,1,1,'阳','庚','子','水','父母','阴','乙','未','土','妻财','回头克',0,0,NULL,NULL,1)"),
 ('huitou写错', '@integrity', DEL_M + f"INSERT INTO moving_line_change ({MC_}) VALUES (25,1,1,'阳','庚','子','水','父母','阴','乙','未','土','妻财','回头生',0,0,NULL,NULL,0)"),
 ('进神误标', '@integrity', DEL_M + f"INSERT INTO moving_line_change ({MC_}) VALUES (25,1,1,'阳','庚','子','水','父母','阴','乙','未','土','妻财','回头克',0,0,'进神',NULL,0)"),
 ('删掉一个动爻行', '@integrity', DEL_M),
 ('删掉一个组合', '@integrity', DEL_T),
 ('卦变表只读', '只读', "UPDATE hexagram_transition SET gua_change='化生' WHERE hexagram_id=1 AND move_mask=63"),
 ('动变爻表只读', '只读', "UPDATE moving_line_change SET huitou='比和' WHERE hexagram_id=25 AND move_mask=1"),
]
# v5 卦之反吟反向测试
TCF = TC_ + ', gua_fanyin'
def trow(hid, mask, gf):
    r = cur.execute(f"select {TC_} from hexagram_transition where hexagram_id=? and move_mask=?", (hid, mask)).fetchone()
    vals = ','.join('NULL' if v is None else (str(v) if isinstance(v, int) else "'" + v + "'") for v in r)
    return (f"DELETE FROM moving_line_change WHERE hexagram_id={hid} AND move_mask={mask}; DELETE FROM hexagram_transition WHERE hexagram_id={hid} AND move_mask={mask}; "
            f"INSERT INTO hexagram_transition ({TCF}) VALUES ({vals},{'NULL' if gf is None else repr(gf)})")
QIAN = cur.execute("select hexagram_id from hexagrams where name='乾为天'").fetchone()[0]
KUN = cur.execute("select hexagram_id from hexagrams where name='坤为地'").fetchone()[0]
ZHEN = cur.execute("select hexagram_id from hexagrams where name='震为雷'").fetchone()[0]
NEG2 += [
 ('乾变坤卦反吟漏标', '卦反吟', trow(QIAN, 63, None)),
 ('坤变乾卦反吟漏标', '卦反吟', trow(KUN, 63, None)),
 ('震变巽误标卦反吟', '卦反吟', trow(ZHEN, 63, '反吟')),
 ('非六爻皆动误标卦反吟（触发器）', '卦反吟', trow(25, 1, '反吟')),
 ('非六爻皆动误标卦反吟（去触发器只验 CHECK）', 'move_mask = 63', 'DROP TRIGGER hexagram_transition_check; ' + trow(25, 1, '反吟')),
 ('卦反吟取值非法（去触发器只验 CHECK）', "gua_fanyin IN", 'DROP TRIGGER hexagram_transition_check; ' + trow(QIAN, 63, '伏吟')),
 ('删去规则表乾坤一行', '@integrity', "DELETE FROM gua_fanyin WHERE from_trigram='乾'"),
 ('卦反吟列只读', '只读', f"UPDATE hexagram_transition SET gua_fanyin=NULL WHERE hexagram_id={QIAN} AND move_mask=63"),
]
for label, want, sql in NEG2:
    cur.execute('SAVEPOINT neg')
    try:
        for s_ in sql.split(';'):
            if s_.strip(): cur.execute(s_)
        if want == '@integrity':
            iss = cur.execute('select issue from integrity_issues').fetchall()
            ok = len(iss) > 0; msg = f'integrity_issues 报出 {len(iss)} 行：' + (iss[0][0] if iss else '无')
        else:
            ok = False; msg = '未被拦截'
    except sqlite3.DatabaseError as e:
        msg = str(e).split('\n')[0]; ok = want != '@integrity' and want in str(e)
    cur.execute('ROLLBACK TO neg'); cur.execute('RELEASE neg')
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {msg[:110]}")
    if not ok: mism.append(('negative-v3', label, msg))
print('\nTOTAL MISMATCHES', len(mism))
for m in mism: print(m)
sys.exit(1 if mism else 0)
