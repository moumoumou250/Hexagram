#!/usr/bin/env python3
"""第一部分（沿用 v1 oracle）：按京房八宫纳甲标准规则重算 64 卦，与 gua.sql 原三表逐字段比对。"""
import sqlite3, sys, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
SQL = os.path.join(HERE, '..', '..', 'database', 'gua.sql')

# ---- 1. 执行 SQL 到空库 ----
con = sqlite3.connect(':memory:')
exec_error = None
try:
    con.executescript(open(SQL, encoding='utf-8').read())
except Exception as e:
    exec_error = repr(e)
print('EXEC:', exec_error or 'OK')
cur = con.cursor()
print('counts', [cur.execute(f'select count(*) from {t}').fetchone()[0] for t in ('hexagrams','hexagram_lines','hidden_spirits')])
print('fk_check', cur.execute('PRAGMA foreign_key_check').fetchall())
print('integrity', cur.execute('PRAGMA integrity_check').fetchall())
vc = cur.execute('select * from hexagram_board limit 1')
cols = [d[0] for d in vc.description]
print('view cols', cols, 'dups:', [c for c in set(cols) if cols.count(c) > 1])
print('view rows', cur.execute('select count(*) from hexagram_board').fetchone()[0])

# ---- 2. 基础规则 ----
# 三爻自下而上，1=阳 0=阴
TRI = {'乾':(1,1,1),'兑':(1,1,0),'离':(1,0,1),'震':(1,0,0),'巽':(0,1,1),'坎':(0,1,0),'艮':(0,0,1),'坤':(0,0,0)}
TRI_BY_LINES = {v:k for k,v in TRI.items()}
IMAGE = {'乾':'天','兑':'泽','离':'火','震':'雷','巽':'风','坎':'水','艮':'山','坤':'地'}
TRI_ELEM = {'乾':'金','兑':'金','离':'火','震':'木','巽':'木','坎':'水','艮':'土','坤':'土'}
# 纳甲：(内卦天干, 内卦三支 初二三), (外卦天干, 外卦三支 四五上)
NAJIA = {
 '乾':(('甲','子寅辰'),('壬','午申戌')), '坎':(('戊','寅辰午'),('戊','申戌子')),
 '艮':(('丙','辰午申'),('丙','戌子寅')), '震':(('庚','子寅辰'),('庚','午申戌')),
 '巽':(('辛','丑亥酉'),('辛','未巳卯')), '离':(('己','卯丑亥'),('己','酉未巳')),
 '坤':(('乙','未巳卯'),('癸','丑亥酉')), '兑':(('丁','巳卯丑'),('丁','亥酉未')),
}
BR_ELEM = dict(zip('子丑寅卯辰巳午未申酉戌亥', '水土木木土火火土金金土水'))
SHENG = {'木':'火','火':'土','土':'金','金':'水','水':'木'}
KE = {'木':'土','土':'水','水':'火','火':'金','金':'木'}
def relative(palace_el, el):
    if el == palace_el: return '兄弟'
    if SHENG[palace_el] == el: return '子孙'
    if SHENG[el] == palace_el: return '父母'
    if KE[palace_el] == el: return '妻财'
    if KE[el] == palace_el: return '官鬼'
SEQ = ('乾 坤 屯 蒙 需 讼 师 比 小畜 履 泰 否 同人 大有 谦 豫 随 蛊 临 观 噬嗑 贲 剥 复 无妄 大畜 颐 大过 坎 离 '
       '咸 恒 遁 大壮 晋 明夷 家人 睽 蹇 解 损 益 夬 姤 萃 升 困 井 革 鼎 震 艮 渐 归妹 丰 旅 巽 兑 涣 节 中孚 小过 既济 未济').split()
# 通行本卦序 → 上下卦（用于独立核对 name/上下卦）
SEQ_TRI = {}
for up in TRI:
    for lo in TRI:
        pass
# 以卦画定义 64 卦短名（独立表）
SHORT = {
('乾','乾'):'乾',('坤','坤'):'坤',('坎','震'):'屯',('艮','坎'):'蒙',('坎','乾'):'需',('乾','坎'):'讼',('坤','坎'):'师',('坎','坤'):'比',
('巽','乾'):'小畜',('乾','兑'):'履',('坤','乾'):'泰',('乾','坤'):'否',('乾','离'):'同人',('离','乾'):'大有',('坤','艮'):'谦',('震','坤'):'豫',
('兑','震'):'随',('艮','巽'):'蛊',('坤','兑'):'临',('巽','坤'):'观',('离','震'):'噬嗑',('艮','离'):'贲',('艮','坤'):'剥',('坤','震'):'复',
('乾','震'):'无妄',('艮','乾'):'大畜',('艮','震'):'颐',('兑','巽'):'大过',('坎','坎'):'坎',('离','离'):'离',('兑','艮'):'咸',('震','巽'):'恒',
('乾','艮'):'遁',('震','乾'):'大壮',('离','坤'):'晋',('坤','离'):'明夷',('巽','离'):'家人',('离','兑'):'睽',('坎','艮'):'蹇',('震','坎'):'解',
('艮','兑'):'损',('巽','震'):'益',('兑','乾'):'夬',('乾','巽'):'姤',('兑','坤'):'萃',('坤','巽'):'升',('兑','坎'):'困',('坎','巽'):'井',
('兑','离'):'革',('离','巽'):'鼎',('震','震'):'震',('艮','艮'):'艮',('巽','艮'):'渐',('震','兑'):'归妹',('震','离'):'丰',('离','艮'):'旅',
('巽','巽'):'巽',('兑','兑'):'兑',('巽','坎'):'涣',('坎','兑'):'节',('巽','兑'):'中孚',('震','艮'):'小过',('坎','离'):'既济',('离','坎'):'未济'}
assert len(SHORT) == 64 and len(set(SHORT.values())) == 64
def fullname(up, lo):
    s = SHORT[(up,lo)]
    return f'{s}为{IMAGE[up]}' if up == lo else IMAGE[up] + IMAGE[lo] + s

# 八宫：由本宫纯卦逐爻变出
STAGES = ['本宫','一世','二世','三世','四世','五世','游魂','归魂']
SHI = {'本宫':6,'一世':1,'二世':2,'三世':3,'四世':4,'五世':5,'游魂':4,'归魂':3}
PALACE = {}  # lines(tuple6) -> (palace, stage)
for p, t in TRI.items():
    lines = list(t + t)
    PALACE[tuple(lines)] = (p, '本宫')
    for k in range(1, 6):
        lines[k-1] ^= 1
        PALACE[tuple(lines)] = (p, STAGES[k])
    lines[3] ^= 1; PALACE[tuple(lines)] = (p, '游魂')
    for i in range(3): lines[i] ^= 1
    PALACE[tuple(lines)] = (p, '归魂')
assert len(PALACE) == 64
LIUCHONG = {'乾','坤','坎','离','震','艮','巽','兑','无妄','大壮'}
LIUHE = {'否','泰','困','节','贲','豫','复','旅'}
TITLE_POS = {1:('初九','初六'),2:('九二','六二'),3:('九三','六三'),4:('九四','六四'),5:('九五','六五'),6:('上九','上六')}

def build(up, lo):
    lines = TRI[lo] + TRI[up]
    pal, stage = PALACE[lines]
    pel = TRI_ELEM[pal]
    shi = SHI[stage]; ying = shi - 3 if shi > 3 else shi + 3
    short = SHORT[(up,lo)]
    rel = '六冲' if short in LIUCHONG else '六合' if short in LIUHE else '无'
    L = []
    for pos in range(1, 7):
        tri = lo if pos <= 3 else up
        stem, brs = NAJIA[tri][0 if pos <= 3 else 1]
        br = brs[(pos-1) % 3]; el = BR_ELEM[br]
        L.append(dict(polarity='阳' if lines[pos-1] else '阴',
                      line_title=TITLE_POS[pos][0 if lines[pos-1] else 1],
                      stem=stem, branch=br, element=el, relative=relative(pel, el)))
    return dict(id=SEQ.index(short)+1, name=fullname(up,lo), upper_trigram=up, lower_trigram=lo,
                palace=pal, palace_element=pel, palace_stage=stage, shi_line=shi, ying_line=ying,
                hexagram_relation=rel, lines=L)

ORACLE = {}
for up in TRI:
    for lo in TRI:
        h = build(up, lo); ORACLE[h['id']] = h
# 伏神
RELS = ['父母','兄弟','子孙','妻财','官鬼']
HIDDEN = {}; HIDDEN_AMBIG = {}
for hid, h in ORACLE.items():
    present = {l['relative'] for l in h['lines']}
    head = build(h['palace'], h['palace'])
    for r in RELS:
        if r in present: continue
        cands = [i+1 for i, l in enumerate(head['lines']) if l['relative'] == r]
        if len(cands) > 1: HIDDEN_AMBIG[(hid, r)] = cands
        for p in cands:
            hl = head['lines'][p-1]
            HIDDEN[(hid, p)] = dict(stem=hl['stem'], branch=hl['branch'], element=hl['element'], relative=r)

# ---- 3. 比对 ----
mism = []
def M(table, hid, pos, field, filev, right, why=''):
    mism.append(dict(table=table, hexagram_id=hid, position=pos, field=field, file=filev, correct=right, why=why))

hcols = ['hexagram_id','name','upper_trigram','lower_trigram','palace','palace_element','palace_stage','shi_line','ying_line','hexagram_relation']
for row in cur.execute('select * from hexagrams order by hexagram_id'):
    r = dict(zip(hcols, row)); hid = r['hexagram_id']
    # 以文件给出的上下卦为准重算，再交叉验证卦序与卦名
    o = build(r['upper_trigram'], r['lower_trigram'])
    if o['id'] != hid: M('hexagrams', hid, None, 'hexagram_id/上下卦', f"{hid} {r['upper_trigram']}{r['lower_trigram']}", f"上{r['upper_trigram']}下{r['lower_trigram']}在通行本为第{o['id']}卦 {o['name']}")
    for f in hcols[1:]:
        if r[f] != o[f]: M('hexagrams', hid, None, f, r[f], o[f])
lcols = ['hexagram_id','position','polarity','line_title','stem','branch','element','relative']
for row in cur.execute('select * from hexagram_lines order by hexagram_id, position'):
    r = dict(zip(lcols, row)); hid, pos = r['hexagram_id'], r['position']
    o = ORACLE[hid]['lines'][pos-1]
    for f in lcols[2:]:
        if r[f] != o[f]: M('hexagram_lines', hid, pos, f, r[f], o[f])
    # 内部一致性
    if BR_ELEM.get(r['branch']) != r['element']: M('hexagram_lines', hid, pos, 'element(内部)', r['element'], BR_ELEM.get(r['branch']), '地支五行不符')
# 伏神
fcols = ['hexagram_id','position','stem','branch','element','relative']
file_hidden = {}
for row in cur.execute('select * from hidden_spirits'):
    r = dict(zip(fcols, row)); file_hidden[(r['hexagram_id'], r['position'])] = r
for k in sorted(set(file_hidden) | set(HIDDEN)):
    f, o = file_hidden.get(k), HIDDEN.get(k)
    if f and not o: M('hidden_spirits', k[0], k[1], '整行(多余)', f"{f['stem']}{f['branch']}{f['element']}{f['relative']}", '不应有', '该卦此六亲并不缺失或首卦该位非此六亲')
    elif o and not f: M('hidden_spirits', k[0], k[1], '整行(缺失)', '无', f"{o['stem']}{o['branch']}{o['element']}{o['relative']}", '本卦缺此六亲，应列伏神')
    else:
        for fld in ('stem','branch','element','relative'):
            if f[fld] != o[fld]: M('hidden_spirits', k[0], k[1], fld, f[fld], o[fld])
# 计数检查
lc = cur.execute('select hexagram_id, count(*) from hexagram_lines group by hexagram_id having count(*)!=6').fetchall()
print('hexagrams with !=6 lines:', lc)
print('hidden ambiguities:', HIDDEN_AMBIG)
print('oracle hidden count', len(HIDDEN), 'file', len(file_hidden))
print('MISMATCHES', len(mism))
for m in mism: print(json.dumps(m, ensure_ascii=False))
