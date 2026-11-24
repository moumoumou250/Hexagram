#!/usr/bin/env python3
"""由 gua_v1.sql（原数据，逐行保留）+ 本文件中按《增删卜易》录入的固定表，生成新的 gua.sql。
固定表的字面值按书中原文录入；oracle_v3.py 用另一套算法独立重算核对（含 v3 动变预计算两表）。"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / 'tests' / 'fixtures' / 'gua_v1.sql').read_text(encoding='utf-8')

def q(s): return "'" + str(s).replace("'", "''") + "'"
def rows(vals): return ',\n'.join('(' + ', '.join(q(v) if isinstance(v, str) else ('NULL' if v is None else str(v)) for v in r) + ')' for r in vals)

BR = '子丑寅卯辰巳午未申酉戌亥'
ST = '甲乙丙丁戊己庚辛壬癸'
# ---------- 字面录入（依书） ----------
WUXING = [('木',1,'火','土'),('火',2,'土','金'),('土',3,'金','水'),('金',4,'水','木'),('水',5,'木','火')]  # 五行相生章第十一、五行相克章第十二
TIANGAN = [('甲',1,'木','阳'),('乙',2,'木','阴'),('丙',3,'火','阳'),('丁',4,'火','阴'),('戊',5,'土','阳'),
           ('己',6,'土','阴'),('庚',7,'金','阳'),('辛',8,'金','阴'),('壬',9,'水','阳'),('癸',10,'水','阴')]
# 日辰章第十七：子水，丑土，寅木，卯木，辰土，巳火，午火，未土，申金，酉金，戌土，亥水；月破章第二十七：正申二酉…（寅为正月）
DIZHI = [('子',1,'水','阳',11),('丑',2,'土','阴',12),('寅',3,'木','阳',1),('卯',4,'木','阴',2),('辰',5,'土','阳',3),('巳',6,'火','阴',4),
         ('午',7,'火','阳',5),('未',8,'土','阴',6),('申',9,'金','阳',7),('酉',10,'金','阴',8),('戌',11,'土','阳',9),('亥',12,'水','阴',10)]
# 八卦章第一（父母男女、俱属阳/阴）；code 自下而上，1=阳
TRIGRAMS = [('乾','111','天','金','父','阳'),('兑','110','泽','金','少女','阴'),('离','101','火','火','中女','阴'),('震','100','雷','木','长男','阳'),
            ('巽','011','风','木','长女','阴'),('坎','010','水','水','中男','阳'),('艮','001','山','土','少男','阳'),('坤','000','地','土','母','阴')]
# 浑天甲子章第四
NAJIA = {'乾':('甲','子寅辰','壬','午申戌'),'坎':('戊','寅辰午','戊','申戌子'),'艮':('丙','辰午申','丙','戌子寅'),'震':('庚','子寅辰','庚','午申戌'),
         '巽':('辛','丑亥酉','辛','未巳卯'),'离':('己','卯丑亥','己','酉未巳'),'坤':('乙','未巳卯','癸','丑亥酉'),'兑':('丁','巳卯丑','丁','亥酉未')}
# 六亲歌章第五：以宫五行为我
LIUQIN = []
for (pe,_,s,k) in WUXING:
    for (le,_,s2,k2) in WUXING:
        rel = '兄弟' if le==pe else '子孙' if le==s else '妻财' if le==k else '父母' if s2==pe else '官鬼'
        LIUQIN.append((pe, le, rel))
# 用神元神忌神仇神章第九（书作“元神”，即原神）
YONGSHEN = [('父母','官鬼','妻财','子孙'),('兄弟','父母','官鬼','妻财'),('子孙','兄弟','父母','官鬼'),('妻财','子孙','兄弟','父母'),('官鬼','妻财','子孙','兄弟')]
CHONG = ['子午','丑未','寅申','卯酉','辰戌','巳亥']          # 六冲章第二十
HE = ['子丑','寅亥','卯戌','辰酉','巳申','午未']             # 六合章第十九
SANHE = [('水','申','子','辰'),('金','巳','酉','丑'),('火','寅','午','戌'),('木','亥','卯','未')]  # 六合章第十九 三合
# 三刑章第二十一（1925 本原文：寅刑巳 巳刑申 子刑卯 卯刑子 丑戌相刑 未辰相刑 又云辰午酉亥谓之自刑）
SANXING = [('寅','巳','刑'),('巳','申','刑'),('子','卯','刑'),('卯','子','刑'),('丑','戌','相刑'),('戌','丑','相刑'),
           ('未','辰','相刑'),('辰','未','相刑'),('辰','辰','自刑'),('午','午','自刑'),('酉','酉','自刑'),('亥','亥','自刑')]
# 生旺墓绝章第又二十六：只验生旺墓绝；金巳酉丑寅、木亥卯未申、土水申子辰巳；火行 1925 本漏列，据书中“巳(火)长生于寅”“火墓于戌”补
CS_SRC_BOOK = '生旺墓绝章原文'
CHANGSHENG = []
for el, brs, csrc in [('金','巳酉丑寅',CS_SRC_BOOK),('木','亥卯未申',CS_SRC_BOOK),('水','申子辰巳',CS_SRC_BOOK),('土','申子辰巳',CS_SRC_BOOK+'（土随水，李我平、觉子按语同）'),
                     ('火','寅午戌亥','1925本漏列火行；长生寅见本章觉子曰，墓戌见应期总注章，旺午绝亥按同法补')]:
    for stg, b in zip(('长生','帝旺','墓','绝'), brs): CHANGSHENG.append((el, stg, b, csrc))
# 四时旺相章第又十五
MONTH = {'寅':('木','火',None,'寅木旺，卯木次之'),'卯':('木','火',None,'卯木旺，寅木次之'),'辰':('土','金',None,'辰土旺，丑未次之'),
         '巳':('火','土',None,'巳火旺，午火次之'),'午':('火','土',None,'午火旺，巳火次之'),'未':('土','金','火','未土旺，辰戌次之'),
         '申':('金','水',None,'申金旺，酉金次之'),'酉':('金','水',None,'酉金旺，申金次之'),'戌':('土','金',None,'戌土旺，丑未次之'),
         '亥':('水','木',None,'亥水旺，子水次之'),'子':('水','木',None,'子水旺，亥水次之'),'丑':('土','金','水','丑土旺，辰戌次之')}
MS = []
for mb,(w,x,yu,note) in MONTH.items():
    for el in '木火土金水':
        if el==w: MS.append((mb,el,'旺',note))
        elif el==x: MS.append((mb,el,'相','相虽不旺，还有余气' if w=='土' else None))
        else: MS.append((mb,el,'休囚','虽衰，有余气' if el==yu else None))
# 旬空章第二十六
XUN = {'甲子':'戌亥','甲戌':'申酉','甲申':'午未','甲午':'辰巳','甲辰':'寅卯','甲寅':'子丑'}
JIAZI = []
head = None
for i in range(60):
    gz = ST[i%10] + BR[i%12]
    if gz[0]=='甲': head = gz
    JIAZI.append((i+1, gz, gz[0], gz[1], head, XUN[head][0], XUN[head][1]))
# 进神退神章第二十九（1925 本原文各七对，无戌化丑/丑化戌）
JIN = ['亥子','寅卯','巳午','申酉','丑辰','辰未','未戌']
JT = [(a,b,'进神') for a,b in JIN] + [(b,a,'退神') for a,b in JIN]
# 六神章第十八（原表自上爻起列；元武即玄武，滕蛇即螣蛇）
LS_TABLE = {'上':('玄武','青龙','朱雀','勾陈','螣蛇','白虎'),'五':('白虎','玄武','青龙','朱雀','勾陈','螣蛇'),'四':('螣蛇','白虎','玄武','青龙','朱雀','勾陈'),
            '三':('勾陈','螣蛇','白虎','玄武','青龙','朱雀'),'二':('朱雀','勾陈','螣蛇','白虎','玄武','青龙'),'初':('青龙','朱雀','勾陈','螣蛇','白虎','玄武')}
COLS = [('甲','乙'),('丙','丁'),('戊',),('己',),('庚','辛'),('壬','癸')]
POSN = {'初':1,'二':2,'三':3,'四':4,'五':5,'上':6}
LIUSHEN = []
for p,names in LS_TABLE.items():
    for stems, sp in zip(COLS, names):
        for s in stems: LIUSHEN.append((s, POSN[p], sp))
LIUSHEN.sort(key=lambda r:(ST.index(r[0]), r[1]))

REF = f"""
-- ======================================================================
-- 一、按《增删卜易》可直接固定的查表资料（v2 新增）。章名据 1925 年上海文明书局石印本（秦慎安校）。
-- 只收不随某次占卜变化的内容；月建、日辰、动爻等每次占卜的内容由 skill 现场代入查询。
-- 书中明言不用的不收：卦身（各门类题头总注章“身即世爻…非卦身”）、六害（三刑章末“六害章全无应验删之不录”）、
-- 十二长生中沐浴冠带等八位（生旺墓绝章“只验生旺墓绝，其余不验，不必用之”）。
-- ======================================================================
CREATE TABLE wuxing (  -- 五行相生章第十一、五行相克章第十二
    element TEXT PRIMARY KEY CHECK (element IN ('木','火','土','金','水')),
    seq INTEGER NOT NULL UNIQUE CHECK (seq BETWEEN 1 AND 5),
    sheng TEXT NOT NULL REFERENCES wuxing(element),  -- 我生
    ke TEXT NOT NULL REFERENCES wuxing(element)      -- 我克
);
INSERT INTO wuxing VALUES
{rows(WUXING)};
CREATE TABLE wuxing_relation (  -- subject 对 object：生=subject 生 object，被生=object 生 subject
    subject TEXT NOT NULL REFERENCES wuxing(element), object TEXT NOT NULL REFERENCES wuxing(element),
    relation TEXT NOT NULL CHECK (relation IN ('比和','生','克','被生','被克')),
    PRIMARY KEY (subject, object)
);
INSERT INTO wuxing_relation
SELECT a.element, b.element,
       CASE WHEN a.element=b.element THEN '比和' WHEN a.sheng=b.element THEN '生' WHEN a.ke=b.element THEN '克'
            WHEN b.sheng=a.element THEN '被生' ELSE '被克' END
FROM wuxing a CROSS JOIN wuxing b;
CREATE TABLE tiangan (
    stem TEXT PRIMARY KEY, seq INTEGER NOT NULL UNIQUE CHECK (seq BETWEEN 1 AND 10),
    element TEXT NOT NULL REFERENCES wuxing(element), polarity TEXT NOT NULL CHECK (polarity IN ('阳','阴'))
);
INSERT INTO tiangan VALUES
{rows(TIANGAN)};
CREATE TABLE dizhi (  -- 日辰章第十七（地支五行）；月破章第二十七（正月建寅）
    branch TEXT PRIMARY KEY, seq INTEGER NOT NULL UNIQUE CHECK (seq BETWEEN 1 AND 12),
    element TEXT NOT NULL REFERENCES wuxing(element), polarity TEXT NOT NULL CHECK (polarity IN ('阳','阴')),
    month_no INTEGER NOT NULL UNIQUE CHECK (month_no BETWEEN 1 AND 12),
    CHECK (element = substr('水土木木土火火土金金土水', seq, 1)),
    CHECK (polarity = CASE seq % 2 WHEN 1 THEN '阳' ELSE '阴' END),
    CHECK (month_no = (seq + 9) % 12 + 1)
);
INSERT INTO dizhi VALUES
{rows(DIZHI)};
CREATE TABLE trigrams (  -- 八卦章第一；code 自下而上，1=阳
    trigram TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE CHECK (length(code)=3 AND code GLOB '[01][01][01]'),
    image TEXT NOT NULL UNIQUE, element TEXT NOT NULL REFERENCES wuxing(element),
    family TEXT NOT NULL UNIQUE, yinyang TEXT NOT NULL CHECK (yinyang IN ('阳','阴'))
);
INSERT INTO trigrams VALUES
{rows(TRIGRAMS)};
CREATE TABLE najia (  -- 浑天甲子章第四；half 内=初二三爻，外=四五上爻
    trigram TEXT NOT NULL REFERENCES trigrams(trigram), half TEXT NOT NULL CHECK (half IN ('内','外')),
    pos_in_half INTEGER NOT NULL CHECK (pos_in_half BETWEEN 1 AND 3),
    stem TEXT NOT NULL REFERENCES tiangan(stem), branch TEXT NOT NULL REFERENCES dizhi(branch),
    PRIMARY KEY (trigram, half, pos_in_half)
);
INSERT INTO najia VALUES
{rows([(t,h,i+1,(v[0] if h=='内' else v[2]),(v[1] if h=='内' else v[3])[i]) for t,v in NAJIA.items() for h in ('内','外') for i in range(3)])};
CREATE TABLE liuqin_rule (  -- 六亲歌章第五：以本卦宫五行为“我”；动变章第七：变爻六亲“仍照正卦而推”
    palace_element TEXT NOT NULL REFERENCES wuxing(element), line_element TEXT NOT NULL REFERENCES wuxing(element),
    relative TEXT NOT NULL CHECK (relative IN ('父母','兄弟','子孙','妻财','官鬼')),
    PRIMARY KEY (palace_element, line_element)
);
INSERT INTO liuqin_rule VALUES
{rows(LIUQIN)};
CREATE TABLE yongshen_roles (  -- 用神元神忌神仇神章第九：元神生用神，忌神克用神，仇神克元神而生忌神
    yongshen TEXT PRIMARY KEY CHECK (yongshen IN ('父母','兄弟','子孙','妻财','官鬼')),
    yuanshen TEXT NOT NULL, jishen TEXT NOT NULL, choushen TEXT NOT NULL,
    CHECK (yongshen<>yuanshen AND yongshen<>jishen AND yongshen<>choushen AND yuanshen<>jishen AND yuanshen<>choushen AND jishen<>choushen)
);
INSERT INTO yongshen_roles VALUES
{rows(YONGSHEN)};
CREATE TABLE dizhi_chong (  -- 六冲章第二十；月建冲爻即月破（月破章第二十七）
    branch_a TEXT NOT NULL REFERENCES dizhi(branch), branch_b TEXT NOT NULL REFERENCES dizhi(branch),
    PRIMARY KEY (branch_a, branch_b), CHECK (branch_a<>branch_b)
);
INSERT INTO dizhi_chong VALUES
{rows([(p[0],p[1]) for p in CHONG] + [(p[1],p[0]) for p in CHONG])};
CREATE TABLE dizhi_he (  -- 六合章第十九
    branch_a TEXT NOT NULL REFERENCES dizhi(branch), branch_b TEXT NOT NULL REFERENCES dizhi(branch),
    PRIMARY KEY (branch_a, branch_b), CHECK (branch_a<>branch_b)
);
INSERT INTO dizhi_he VALUES
{rows([(p[0],p[1]) for p in HE] + [(p[1],p[0]) for p in HE])};
CREATE TABLE sanhe (  -- 六合章第十九：申子辰水局、巳酉丑金局、寅午戌火局、亥卯未木局
    element TEXT PRIMARY KEY REFERENCES wuxing(element),
    sheng_branch TEXT NOT NULL REFERENCES dizhi(branch), wang_branch TEXT NOT NULL REFERENCES dizhi(branch),
    mu_branch TEXT NOT NULL REFERENCES dizhi(branch)
);
INSERT INTO sanhe VALUES
{rows(SANHE)};
CREATE TABLE sanxing (  -- 三刑章第二十一，按 1925 本原文逐条录入。野鹤：“独犯三刑得验者少，占过数十年止验得一卦”。
    -- 注意：原文“未辰相刑”与通行“丑戌未”不同，疑为刻误；原文亦未列“申刑寅”。书中唯一验例为寅月庚申日巳爻（寅巳申）。
    from_branch TEXT NOT NULL REFERENCES dizhi(branch), to_branch TEXT NOT NULL REFERENCES dizhi(branch),
    kind TEXT NOT NULL CHECK (kind IN ('刑','相刑','自刑')),
    PRIMARY KEY (from_branch, to_branch), CHECK ((kind='自刑') = (from_branch=to_branch))
);
INSERT INTO sanxing VALUES
{rows(SANXING)};
CREATE TABLE changsheng (  -- 生旺墓绝章第又二十六：只用长生、帝旺、墓、绝；土随水（长生申、旺子、墓辰、绝巳）
    element TEXT NOT NULL REFERENCES wuxing(element),
    stage TEXT NOT NULL CHECK (stage IN ('长生','帝旺','墓','绝')),
    branch TEXT NOT NULL REFERENCES dizhi(branch), source TEXT NOT NULL,
    PRIMARY KEY (element, stage), UNIQUE (element, branch)
);
INSERT INTO changsheng VALUES
{rows(CHANGSHENG)};
CREATE TABLE month_strength (  -- 四时旺相章第又十五：月建五行为旺，月建所生为相，其余休囚；未月火、丑月水“有余气”
    month_branch TEXT NOT NULL REFERENCES dizhi(branch), element TEXT NOT NULL REFERENCES wuxing(element),
    state TEXT NOT NULL CHECK (state IN ('旺','相','休囚')), note TEXT,
    PRIMARY KEY (month_branch, element)
);
INSERT INTO month_strength VALUES
{rows(MS)};
CREATE TABLE jiazi (  -- 旬空章第二十六：甲子旬中戌亥空……甲寅旬中子丑空
    seq INTEGER PRIMARY KEY CHECK (seq BETWEEN 1 AND 60), ganzhi TEXT NOT NULL UNIQUE,
    stem TEXT NOT NULL REFERENCES tiangan(stem), branch TEXT NOT NULL REFERENCES dizhi(branch),
    xun_head TEXT NOT NULL, kong_1 TEXT NOT NULL REFERENCES dizhi(branch), kong_2 TEXT NOT NULL REFERENCES dizhi(branch),
    CHECK (ganzhi = stem || branch)
);
INSERT INTO jiazi VALUES
{rows(JIAZI)};
CREATE TABLE jin_tui (  -- 进神退神章第二十九，1925 本原文各七对（本书无戌化丑、丑化戌）
    from_branch TEXT NOT NULL REFERENCES dizhi(branch), to_branch TEXT NOT NULL REFERENCES dizhi(branch),
    kind TEXT NOT NULL CHECK (kind IN ('进神','退神')), PRIMARY KEY (from_branch, to_branch)
);
INSERT INTO jin_tui VALUES
{rows(JT)};
CREATE TABLE liushen (  -- 六神章第十八。野鹤：六神“乃附合之神”，不以之断生死，只辅助辨事（玄武主盗贼、朱雀主口舌等）
    day_stem TEXT NOT NULL REFERENCES tiangan(stem), position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 6),
    spirit TEXT NOT NULL CHECK (spirit IN ('青龙','朱雀','勾陈','螣蛇','白虎','玄武')),
    PRIMARY KEY (day_stem, position)
);
INSERT INTO liushen VALUES
{rows(LIUSHEN)};
CREATE TABLE trigram_fanfu (  -- 反伏章第二十五：经卦动变后三爻地支逐位相冲为反吟，逐位相同为伏吟（由纳甲推出，见下方 INSERT）
    half TEXT NOT NULL CHECK (half IN ('内','外')), from_trigram TEXT NOT NULL REFERENCES trigrams(trigram),
    to_trigram TEXT NOT NULL REFERENCES trigrams(trigram), kind TEXT NOT NULL CHECK (kind IN ('反吟','伏吟')),
    PRIMARY KEY (half, from_trigram, to_trigram)
);
INSERT INTO trigram_fanfu
SELECT a.half, a.trigram, b.trigram,
       CASE WHEN SUM(EXISTS (SELECT 1 FROM dizhi_chong c WHERE c.branch_a=a.branch AND c.branch_b=b.branch))=3 THEN '反吟' ELSE '伏吟' END
FROM najia a JOIN najia b ON a.half=b.half AND a.pos_in_half=b.pos_in_half AND a.trigram<>b.trigram
GROUP BY a.half, a.trigram, b.trigram
HAVING SUM(EXISTS (SELECT 1 FROM dizhi_chong c WHERE c.branch_a=a.branch AND c.branch_b=b.branch))=3 OR SUM(a.branch=b.branch)=3;
CREATE TABLE trigram_change (  -- 卦变生克墓绝章第二十四：卦变以经卦五行论；变生本=化生，变克本=化克（“不论用神衰旺皆以凶推”），本克变=化去不克
    from_trigram TEXT NOT NULL REFERENCES trigrams(trigram), to_trigram TEXT NOT NULL REFERENCES trigrams(trigram),
    relation TEXT NOT NULL CHECK (relation IN ('化生','化克','比和','化去生','化去不克')),
    PRIMARY KEY (from_trigram, to_trigram)
);
INSERT INTO trigram_change
SELECT f.trigram, t.trigram,
       CASE r.relation WHEN '生' THEN '化生' WHEN '克' THEN '化克' WHEN '比和' THEN '比和' WHEN '被生' THEN '化去生' ELSE '化去不克' END
FROM trigrams f CROSS JOIN trigrams t JOIN wuxing_relation r ON r.subject=t.element AND r.object=f.element
WHERE f.trigram<>t.trigram;
CREATE TABLE gua_fanyin (  -- v5 反伏章第二十五（1925 本 PDF p88）：“內外動而反吟同一卦也。如乾變坤是也”。卦级反吟只收书中明举之乾坤互变（八纯卦六爻皆动）
    from_trigram TEXT NOT NULL REFERENCES trigrams(trigram), to_trigram TEXT NOT NULL REFERENCES trigrams(trigram),
    kind TEXT NOT NULL CHECK (kind = '反吟'), basis TEXT NOT NULL,
    PRIMARY KEY (from_trigram, to_trigram), CHECK (from_trigram <> to_trigram)
);
INSERT INTO gua_fanyin VALUES
('乾','坤','反吟','反伏章第二十五 1925本PDF p88：如乾變坤是也'),
('坤','乾','反吟','反伏章第二十五 1925本PDF p88：乾變坤之互变');
"""

# ---------- 原表加约束 ----------
OLD_HEX = src[src.index('CREATE TABLE hexagrams ('):src.index('CREATE TABLE hexagram_lines (')]
OLD_LINES = src[src.index('CREATE TABLE hexagram_lines ('):src.index('CREATE TABLE hidden_spirits (')]
OLD_HID = src[src.index('CREATE TABLE hidden_spirits ('):src.index('INSERT INTO hexagrams VALUES')]

NEW_HEX = """CREATE TABLE hexagrams (
    hexagram_id INTEGER PRIMARY KEY CHECK (hexagram_id BETWEEN 1 AND 64),
    name TEXT NOT NULL UNIQUE,
    upper_trigram TEXT NOT NULL REFERENCES trigrams(trigram), lower_trigram TEXT NOT NULL REFERENCES trigrams(trigram),
    palace TEXT NOT NULL REFERENCES trigrams(trigram), palace_element TEXT NOT NULL, palace_stage TEXT NOT NULL
        CHECK (palace_stage IN ('本宫','一世','二世','三世','四世','五世','游魂','归魂')),
    shi_line INTEGER NOT NULL CHECK (shi_line BETWEEN 1 AND 6),
    ying_line INTEGER NOT NULL CHECK (ying_line BETWEEN 1 AND 6 AND abs(shi_line-ying_line)=3),
    hexagram_relation TEXT NOT NULL CHECK(hexagram_relation IN ('无','六冲','六合')),
    UNIQUE (upper_trigram, lower_trigram), UNIQUE (palace, palace_stage),
    -- 世应章第六：本宫世六，一至五世世在初至五爻，游魂世四，归魂世三
    CHECK (shi_line = CASE palace_stage WHEN '本宫' THEN 6 WHEN '一世' THEN 1 WHEN '二世' THEN 2 WHEN '三世' THEN 3
                       WHEN '四世' THEN 4 WHEN '五世' THEN 5 WHEN '游魂' THEN 4 ELSE 3 END),
    -- 宫五行：乾兑金，离火，震巽木，坎水，艮坤土
    CHECK (palace_element = CASE palace WHEN '乾' THEN '金' WHEN '兑' THEN '金' WHEN '离' THEN '火' WHEN '震' THEN '木'
                       WHEN '巽' THEN '木' WHEN '坎' THEN '水' ELSE '土' END),
    -- 本宫卦即八纯卦
    CHECK ((palace_stage='本宫') = (upper_trigram=lower_trigram AND upper_trigram=palace)),
    -- 纯卦名“某为某”
    CHECK ((upper_trigram=lower_trigram) = (name LIKE '_为_'))
);
"""
NEW_LINES = """CREATE TABLE hexagram_lines (
    hexagram_id INTEGER NOT NULL REFERENCES hexagrams(hexagram_id),
    position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 6),
    polarity TEXT NOT NULL CHECK (polarity IN ('阳','阴')), line_title TEXT NOT NULL,
    stem TEXT NOT NULL REFERENCES tiangan(stem), branch TEXT NOT NULL REFERENCES dizhi(branch),
    element TEXT NOT NULL, relative TEXT NOT NULL CHECK (relative IN ('父母','兄弟','子孙','妻财','官鬼')),
    PRIMARY KEY (hexagram_id, position),
    -- 爻题：阳九阴六，初爻称初、上爻称上（初=1…上=6）
    CHECK (line_title = (CASE position WHEN 1 THEN '初' WHEN 6 THEN '上' ELSE '' END)
                        || (CASE polarity WHEN '阳' THEN '九' ELSE '六' END)
                        || (CASE position WHEN 2 THEN '二' WHEN 3 THEN '三' WHEN 4 THEN '四' WHEN 5 THEN '五' ELSE '' END)),
    -- 五行随地支
    CHECK (instr('子丑寅卯辰巳午未申酉戌亥', branch) > 0
           AND element = substr('水土木木土火火土金金土水', instr('子丑寅卯辰巳午未申酉戌亥', branch), 1))
);
"""
NEW_HID = """CREATE TABLE hidden_spirits (
    hexagram_id INTEGER NOT NULL, position INTEGER NOT NULL,
    stem TEXT NOT NULL REFERENCES tiangan(stem), branch TEXT NOT NULL REFERENCES dizhi(branch),
    element TEXT NOT NULL, relative TEXT NOT NULL CHECK (relative IN ('父母','兄弟','子孙','妻财','官鬼')),
    PRIMARY KEY (hexagram_id, position),
    FOREIGN KEY (hexagram_id, position) REFERENCES hexagram_lines(hexagram_id, position),
    CHECK (instr('子丑寅卯辰巳午未申酉戌亥', branch) > 0
           AND element = substr('水土木木土火火土金金土水', instr('子丑寅卯辰巳午未申酉戌亥', branch), 1))
);

-- 写入校验触发器：纳甲、阴阳、六亲必须与上方固定表一致；伏神必须是本卦缺失的六亲且取自本宫首卦同位爻（飞伏神章第二十八）
CREATE TRIGGER hexagram_lines_check BEFORE INSERT ON hexagram_lines
BEGIN
    SELECT RAISE(ABORT, 'hexagram_lines: 天干地支与浑天甲子（najia）不符')
    WHERE NOT EXISTS (SELECT 1 FROM hexagrams h JOIN najia n
        ON n.trigram = CASE WHEN NEW.position<=3 THEN h.lower_trigram ELSE h.upper_trigram END
       AND n.half = CASE WHEN NEW.position<=3 THEN '内' ELSE '外' END AND n.pos_in_half = (NEW.position-1)%3+1
        WHERE h.hexagram_id=NEW.hexagram_id AND n.stem=NEW.stem AND n.branch=NEW.branch);
    SELECT RAISE(ABORT, 'hexagram_lines: 阴阳与上下卦爻画不符')
    WHERE NOT EXISTS (SELECT 1 FROM hexagrams h JOIN trigrams t
        ON t.trigram = CASE WHEN NEW.position<=3 THEN h.lower_trigram ELSE h.upper_trigram END
        WHERE h.hexagram_id=NEW.hexagram_id AND substr(t.code,(NEW.position-1)%3+1,1) = CASE NEW.polarity WHEN '阳' THEN '1' ELSE '0' END);
    SELECT RAISE(ABORT, 'hexagram_lines: 六亲与本卦宫五行不符')
    WHERE NOT EXISTS (SELECT 1 FROM hexagrams h JOIN liuqin_rule q ON q.palace_element=h.palace_element AND q.line_element=NEW.element
        WHERE h.hexagram_id=NEW.hexagram_id AND q.relative=NEW.relative);
END;
CREATE TRIGGER hidden_spirits_check BEFORE INSERT ON hidden_spirits
BEGIN
    SELECT RAISE(ABORT, 'hidden_spirits: 该六亲已在本卦出现，不应列伏神')
    WHERE EXISTS (SELECT 1 FROM hexagram_lines l WHERE l.hexagram_id=NEW.hexagram_id AND l.relative=NEW.relative);
    SELECT RAISE(ABORT, 'hidden_spirits: 与本宫首卦同位爻不符')
    WHERE NOT EXISTS (SELECT 1 FROM hexagrams h JOIN hexagrams g ON g.palace=h.palace AND g.palace_stage='本宫'
        JOIN hexagram_lines gl ON gl.hexagram_id=g.hexagram_id AND gl.position=NEW.position
        WHERE h.hexagram_id=NEW.hexagram_id AND gl.stem=NEW.stem AND gl.branch=NEW.branch AND gl.relative=NEW.relative);
END;
CREATE TRIGGER hexagram_lines_no_update BEFORE UPDATE ON hexagram_lines BEGIN SELECT RAISE(ABORT, '固定盘只读：请改源数据后重建'); END;
CREATE TRIGGER hidden_spirits_no_update BEFORE UPDATE ON hidden_spirits BEGIN SELECT RAISE(ABORT, '固定盘只读：请改源数据后重建'); END;
CREATE TRIGGER hexagrams_no_update BEFORE UPDATE ON hexagrams BEGIN SELECT RAISE(ABORT, '固定盘只读：请改源数据后重建'); END;

"""
VIEWS = """
-- ======================================================================
-- 三、查询视图（v2 新增；v3 起 hexagram_change、change_board 改读第二部分实表）。hexagram_board 保持原样。
-- ======================================================================

-- 卦级动变（v3：读 hexagram_transition 实表；v2 旧列名、旧取值不变，末尾增列）
-- moving_mask 为旧列：自下而上 6 位文本（'110000' = 初、二爻动）；move_mask 为新列：整数，初爻=bit0（同例 = 3）
CREATE VIEW hexagram_change AS
SELECT t.hexagram_id AS base_id, b.name AS base_name, t.changed_hexagram_id AS changed_id, c.name AS changed_name,
       t.l1||t.l2||t.l3||t.l4||t.l5||t.l6 AS moving_mask,
       t.move_positions AS moving_positions, t.move_count AS moving_count,
       b.hexagram_relation AS base_relation, c.hexagram_relation AS changed_relation,
       t.relation_change, t.inner_fanfu, t.outer_fanfu, t.gua_change,
       t.move_mask, t.l1, t.l2, t.l3, t.l4, t.l5, t.l6, t.inner_changed, t.outer_changed,
       t.gua_fanyin
FROM hexagram_transition t
JOIN hexagrams b ON b.hexagram_id=t.hexagram_id
JOIN hexagrams c ON c.hexagram_id=t.changed_hexagram_id;

-- 爻级动变（v3：读 moving_line_change 实表；v2 旧列名、顺序不变，末尾增列）
-- changed_relative 按本卦宫五行（动变章第七）；changed_relative_own_palace 按变卦自身宫，仅供对照，不用
CREATE VIEW change_board AS
SELECT m.hexagram_id AS base_id, b.name AS base_name, t.changed_hexagram_id AS changed_id, c.name AS changed_name,
       m.position, m.base_polarity, m.base_stem, m.base_branch, m.base_element, m.base_relative,
       m.changed_stem, m.changed_branch, m.changed_element, m.changed_relative,
       cl.relative AS changed_relative_own_palace,
       m.huitou, m.hua_chong, m.hua_he, m.jin_tui, m.hua_stage, m.fuyin_line,
       m.move_mask, m.changed_polarity, m.line_fanfu,
       CASE m.position WHEN b.shi_line THEN '世' WHEN b.ying_line THEN '应' ELSE '' END AS shi_ying
FROM moving_line_change m
JOIN hexagram_transition t ON t.hexagram_id=m.hexagram_id AND t.move_mask=m.move_mask
JOIN hexagrams b ON b.hexagram_id=m.hexagram_id
JOIN hexagrams c ON c.hexagram_id=t.changed_hexagram_id
JOIN hexagram_lines cl ON cl.hexagram_id=t.changed_hexagram_id AND cl.position=m.position;

-- 地支作用：actor（月建、日辰、动爻、变爻）对 target（爻支）。月建冲=月破；日冲静爻须再按旺衰分暗动/日破（日辰章第十七、暗动章第二十二）
CREATE VIEW branch_interaction AS
SELECT a.branch AS actor, t.branch AS target, a.element AS actor_element, t.element AS target_element,
       r.relation AS wuxing,                         -- actor 对 target：生/克/比和/被生/被克
       (a.branch=t.branch) AS same_branch,          -- 临（值）
       EXISTS (SELECT 1 FROM dizhi_chong x WHERE x.branch_a=a.branch AND x.branch_b=t.branch) AS chong,
       EXISTS (SELECT 1 FROM dizhi_he x WHERE x.branch_a=a.branch AND x.branch_b=t.branch) AS he,
       cs.stage AS target_stage,                     -- target 五行在 actor 支的长生/帝旺/墓/绝（日墓、日绝等）
       (SELECT kind FROM sanxing s WHERE s.from_branch=a.branch AND s.to_branch=t.branch) AS xing
FROM dizhi a CROSS JOIN dizhi t
JOIN wuxing_relation r ON r.subject=a.element AND r.object=t.element
LEFT JOIN changsheng cs ON cs.element=t.element AND cs.branch=a.branch;

-- 自检：应为 0 行
CREATE VIEW integrity_issues AS
SELECT h.hexagram_id, h.name, '爻数不是6' AS issue FROM hexagrams h
 WHERE (SELECT count(*) FROM hexagram_lines l WHERE l.hexagram_id=h.hexagram_id)<>6
UNION ALL
SELECT h.hexagram_id, h.name, '六冲六合标注与内外卦对位地支不符' FROM hexagrams h
 WHERE h.hexagram_relation <> (
   SELECT CASE WHEN SUM(EXISTS (SELECT 1 FROM dizhi_chong x WHERE x.branch_a=a.branch AND x.branch_b=b.branch))=3 THEN '六冲'
               WHEN SUM(EXISTS (SELECT 1 FROM dizhi_he x WHERE x.branch_a=a.branch AND x.branch_b=b.branch))=3 THEN '六合' ELSE '无' END
   FROM hexagram_lines a JOIN hexagram_lines b ON b.hexagram_id=a.hexagram_id AND b.position=a.position+3
   WHERE a.hexagram_id=h.hexagram_id)
UNION ALL
SELECT h.hexagram_id, h.name, '缺伏神：'||gl.relative||' 第'||gl.position||'爻' FROM hexagrams h
 JOIN hexagrams g ON g.palace=h.palace AND g.palace_stage='本宫'
 JOIN hexagram_lines gl ON gl.hexagram_id=g.hexagram_id
 WHERE NOT EXISTS (SELECT 1 FROM hexagram_lines l WHERE l.hexagram_id=h.hexagram_id AND l.relative=gl.relative)
   AND NOT EXISTS (SELECT 1 FROM hidden_spirits f WHERE f.hexagram_id=h.hexagram_id AND f.position=gl.position)
UNION ALL
SELECT h.hexagram_id, h.name, '卦变表动爻组合数不是64' FROM hexagrams h
 WHERE (SELECT count(*) FROM hexagram_transition t WHERE t.hexagram_id=h.hexagram_id)<>64
UNION ALL
SELECT t.hexagram_id, h.name, '动变爻行数与动爻数不符：mask '||t.move_mask FROM hexagram_transition t JOIN hexagrams h ON h.hexagram_id=t.hexagram_id
 WHERE (SELECT count(*) FROM moving_line_change m WHERE m.hexagram_id=t.hexagram_id AND m.move_mask=t.move_mask)<>t.move_count
UNION ALL
SELECT m.hexagram_id, h.name, '动变爻关系列与规则表不符：mask '||m.move_mask||' 第'||m.position||'爻'
FROM moving_line_change m JOIN hexagrams h ON h.hexagram_id=m.hexagram_id
JOIN wuxing_relation r ON r.subject=m.changed_element AND r.object=m.base_element
WHERE m.huitou <> CASE r.relation WHEN '生' THEN '回头生' WHEN '克' THEN '回头克' WHEN '比和' THEN '比和' WHEN '被生' THEN '动生变' ELSE '动克变' END
   OR m.hua_chong <> EXISTS (SELECT 1 FROM dizhi_chong x WHERE x.branch_a=m.base_branch AND x.branch_b=m.changed_branch)
   OR m.hua_he <> EXISTS (SELECT 1 FROM dizhi_he x WHERE x.branch_a=m.base_branch AND x.branch_b=m.changed_branch)
   OR m.jin_tui IS NOT (SELECT kind FROM jin_tui j WHERE j.from_branch=m.base_branch AND j.to_branch=m.changed_branch)
   OR m.hua_stage IS NOT (SELECT stage FROM changsheng cs WHERE cs.element=m.base_element AND cs.branch=m.changed_branch)
UNION ALL
SELECT t.hexagram_id, b.name, '卦反吟与 gua_fanyin 规则表不符：mask '||t.move_mask
FROM hexagram_transition t JOIN hexagrams b ON b.hexagram_id=t.hexagram_id JOIN hexagrams c ON c.hexagram_id=t.changed_hexagram_id
WHERE t.gua_fanyin IS NOT (SELECT f.kind FROM gua_fanyin f WHERE b.upper_trigram=b.lower_trigram AND c.upper_trigram=c.lower_trigram
                             AND f.from_trigram=b.upper_trigram AND f.to_trigram=c.upper_trigram);
"""


# ---------- v3：本卦 + 动爻组合 预计算（算法 A：本文件字面规则逐一枚举） ----------
import sqlite3 as _sq
_v1 = _sq.connect(':memory:'); _v1.executescript(src)
HEX = {r[0]: dict(zip(('id','name','upper','lower','palace','pe','stage','shi','ying','rel'), r)) for r in _v1.execute('select * from hexagrams')}
LINES = {(r[0], r[1]): r for r in _v1.execute('select hexagram_id, position, polarity, line_title, stem, branch, element, relative from hexagram_lines')}
TCODE = {t[0]: t[1] for t in TRIGRAMS}; CODE_T = {v: k for k, v in TCODE.items()}; TEL = {t[0]: t[3] for t in TRIGRAMS}
BYTRI = {(h['upper'], h['lower']): i for i, h in HEX.items()}
BREL = {r[0]: r[2] for r in DIZHI}
SHENG = {w[0]: w[2] for w in WUXING}; KE = {w[0]: w[3] for w in WUXING}
def wrel(a, b):  # a 对 b
    return '比和' if a == b else '生' if SHENG[a] == b else '克' if KE[a] == b else '被生' if SHENG[b] == a else '被克'
LQ = {(pe, le): r for pe, le, r in LIUQIN}
CH = {(x[0], x[1]) for x in CHONG} | {(x[1], x[0]) for x in CHONG}
HH = {(x[0], x[1]) for x in HE} | {(x[1], x[0]) for x in HE}
JTD = {(a, b): k for a, b, k in JT}
CSD = {(e, b): st for e, st, b, _ in CHANGSHENG}
HU = {'生': '回头生', '克': '回头克', '比和': '比和', '被生': '动生变', '被克': '动克变'}
TC = {'生': '化生', '克': '化克', '比和': '比和', '被生': '化去生', '被克': '化去不克'}
def najia_line(tri, half, k):  # k=0..2
    stem, brs = (NAJIA[tri][0], NAJIA[tri][1]) if half == '内' else (NAJIA[tri][2], NAJIA[tri][3])
    return stem, brs[k]
def fanfu(half, a, b):
    if a == b: return None
    A = [najia_line(a, half, k)[1] for k in range(3)]; B = [najia_line(b, half, k)[1] for k in range(3)]
    if all((x, y) in CH for x, y in zip(A, B)): return '反吟'
    if A == B: return '伏吟'
    return None
GFY = {('乾', '坤'): '反吟', ('坤', '乾'): '反吟'}  # v5 反伏章 1925 p88“如乾變坤是也”（与 SQL gua_fanyin 规则表同源）
TRANS, MLC = {}, {}
for hid in sorted(HEX):
    h = HEX[hid]; code = TCODE[h['lower']] + TCODE[h['upper']]
    TRANS[hid], MLC[hid] = [], []
    for mask in range(64):
        nc = ''.join(('0' if code[k] == '1' else '1') if (mask >> k) & 1 else code[k] for k in range(6))
        lo, up = CODE_T[nc[:3]], CODE_T[nc[3:]]
        cid = BYTRI[(up, lo)]; c = HEX[cid]
        pos = [k + 1 for k in range(6) if (mask >> k) & 1]
        rc = (h['rel'] + '变' + c['rel']) if mask and h['rel'] != '无' and c['rel'] != '无' else None
        gc = TC[wrel(TEL[c['upper']], TEL[h['upper']])] if (h['upper'] == h['lower'] and c['upper'] == c['lower'] and mask) else None
        TRANS[hid].append((hid, mask, cid, len(pos), ','.join(map(str, pos)), int(mask & 7 != 0), int(mask & 56 != 0), rc,
                           fanfu('内', h['lower'], lo), fanfu('外', h['upper'], up), gc,
                           GFY.get((h['upper'], c['upper'])) if (h['upper'] == h['lower'] and c['upper'] == c['lower']) else None))
        for p in pos:
            bl = LINES[(hid, p)]
            tri, half = (lo, '内') if p <= 3 else (up, '外')
            cs, cb = najia_line(tri, half, (p - 1) % 3)
            ce = BREL[cb]; cpol = '阳' if nc[p - 1] == '1' else '阴'
            MLC[hid].append((hid, mask, p, bl[2], bl[4], bl[5], bl[6], bl[7], cpol, cs, cb, ce, LQ[(h['pe'], ce)],
                             HU[wrel(ce, bl[6])], int((bl[5], cb) in CH), int((bl[5], cb) in HH), JTD.get((bl[5], cb)),
                             CSD.get((bl[6], cb)), int(bl[5] == cb)))
T_COLS = 'hexagram_id, move_mask, changed_hexagram_id, move_count, move_positions, inner_changed, outer_changed, relation_change, inner_fanfu, outer_fanfu, gua_change, gua_fanyin'
M_COLS = ('hexagram_id, move_mask, position, base_polarity, base_stem, base_branch, base_element, base_relative, '
          'changed_polarity, changed_stem, changed_branch, changed_element, changed_relative, huitou, hua_chong, hua_he, jin_tui, hua_stage, fuyin_line')
TRANS_ROWS = ''.join(f"-- {hid} {HEX[hid]['name']}（{HEX[hid]['palace']}宫{HEX[hid]['pe']}）\n"
                     f"INSERT INTO hexagram_transition ({T_COLS}) VALUES\n{rows(TRANS[hid])};\n"
                     f"INSERT INTO moving_line_change ({M_COLS}) VALUES\n{rows(MLC[hid])};\n" for hid in sorted(HEX))

TRANS_DDL = """
-- ======================================================================
-- 二、动变预计算（v3）：本卦 + 动爻组合 move_mask（0–63，初爻=bit0）→ 变卦与每个动爻的变化。
-- 只收固定部分；化空、化破、日月作用随每次起卦而定，不在此。生成：tests/build_gua_sql.py；核对：tests/sql/oracle_v3.py
-- ======================================================================
CREATE TABLE hexagram_transition (  -- 动变章第七：动则必变，诸动爻同时变，得一个之卦；move_mask=0 为静卦
    hexagram_id         INTEGER NOT NULL REFERENCES hexagrams(hexagram_id),
    move_mask           INTEGER NOT NULL CHECK (move_mask BETWEEN 0 AND 63),
    changed_hexagram_id INTEGER NOT NULL REFERENCES hexagrams(hexagram_id),
    move_count          INTEGER NOT NULL CHECK (move_count BETWEEN 0 AND 6),
    move_positions      TEXT    NOT NULL,
    inner_changed       INTEGER NOT NULL CHECK (inner_changed IN (0,1)),
    outer_changed       INTEGER NOT NULL CHECK (outer_changed IN (0,1)),
    relation_change     TEXT CHECK (relation_change IN ('六冲变六合','六合变六冲','六冲变六冲','六合变六合')),  -- 六合章第十九、六冲章第二十
    inner_fanfu         TEXT CHECK (inner_fanfu IN ('反吟','伏吟')),           -- 反伏章第二十五（取 trigram_fanfu）
    outer_fanfu         TEXT CHECK (outer_fanfu IN ('反吟','伏吟')),
    gua_change          TEXT CHECK (gua_change IN ('化生','化克','比和','化去生','化去不克')),  -- 卦变生克墓绝章第二十四，仅八纯卦互变
    gua_fanyin          TEXT CHECK (gua_fanyin IN ('反吟')),  -- v5 卦之反吟（取 gua_fanyin 规则表：乾坤互变，反伏章 1925 p88）
    l1 INTEGER GENERATED ALWAYS AS ( move_mask       & 1) VIRTUAL,
    l2 INTEGER GENERATED ALWAYS AS ((move_mask >> 1) & 1) VIRTUAL,
    l3 INTEGER GENERATED ALWAYS AS ((move_mask >> 2) & 1) VIRTUAL,
    l4 INTEGER GENERATED ALWAYS AS ((move_mask >> 3) & 1) VIRTUAL,
    l5 INTEGER GENERATED ALWAYS AS ((move_mask >> 4) & 1) VIRTUAL,
    l6 INTEGER GENERATED ALWAYS AS ((move_mask >> 5) & 1) VIRTUAL,
    PRIMARY KEY (hexagram_id, move_mask),
    UNIQUE (hexagram_id, changed_hexagram_id),
    CHECK ((move_mask = 0) = (changed_hexagram_id = hexagram_id)),
    CHECK (move_count = (move_mask&1)+((move_mask>>1)&1)+((move_mask>>2)&1)+((move_mask>>3)&1)+((move_mask>>4)&1)+((move_mask>>5)&1)),
    CHECK (inner_changed = ((move_mask & 7)  <> 0)),
    CHECK (outer_changed = ((move_mask & 56) <> 0)),
    CHECK (move_positions = rtrim((CASE WHEN move_mask&1  THEN '1,' ELSE '' END)||(CASE WHEN move_mask&2  THEN '2,' ELSE '' END)
                                ||(CASE WHEN move_mask&4  THEN '3,' ELSE '' END)||(CASE WHEN move_mask&8  THEN '4,' ELSE '' END)
                                ||(CASE WHEN move_mask&16 THEN '5,' ELSE '' END)||(CASE WHEN move_mask&32 THEN '6,' ELSE '' END), ',')),
    CHECK (inner_fanfu IS NULL OR inner_changed = 1),
    CHECK (outer_fanfu IS NULL OR outer_changed = 1),
    CHECK (relation_change IS NULL OR move_mask <> 0),
    CHECK (gua_fanyin IS NULL OR move_mask = 63)
);
CREATE INDEX ix_transition_changed ON hexagram_transition(changed_hexagram_id);

CREATE TABLE moving_line_change (  -- 每个动爻一行；变爻只生克冲合本位动爻（动变生克冲合章第十五）
    hexagram_id      INTEGER NOT NULL,
    move_mask        INTEGER NOT NULL,
    position         INTEGER NOT NULL CHECK (position BETWEEN 1 AND 6),
    base_polarity    TEXT NOT NULL CHECK (base_polarity IN ('阳','阴')),
    base_stem        TEXT NOT NULL REFERENCES tiangan(stem),
    base_branch      TEXT NOT NULL REFERENCES dizhi(branch),
    base_element     TEXT NOT NULL,
    base_relative    TEXT NOT NULL CHECK (base_relative IN ('父母','兄弟','子孙','妻财','官鬼')),
    changed_polarity TEXT NOT NULL CHECK (changed_polarity IN ('阳','阴')),
    changed_stem     TEXT NOT NULL REFERENCES tiangan(stem),
    changed_branch   TEXT NOT NULL REFERENCES dizhi(branch),
    changed_element  TEXT NOT NULL,
    changed_relative TEXT NOT NULL CHECK (changed_relative IN ('父母','兄弟','子孙','妻财','官鬼')),  -- 按本卦宫五行（动变章第七）
    huitou     TEXT NOT NULL CHECK (huitou IN ('回头生','回头克','比和','动生变','动克变')),  -- 变对本：生/克；本对变：动生变（我生）/动克变（我克）
    hua_chong  INTEGER NOT NULL CHECK (hua_chong IN (0,1)),   -- 化回头冲，即爻之反吟（六冲章、反伏章）
    hua_he     INTEGER NOT NULL CHECK (hua_he IN (0,1)),      -- 化扶（六合章“爻动化合”）
    jin_tui    TEXT CHECK (jin_tui IN ('进神','退神')),       -- 进神退神章第二十九（1925 本七对）
    hua_stage  TEXT CHECK (hua_stage IN ('长生','帝旺','墓','绝')),  -- 生旺墓绝章（土随水）
    fuyin_line INTEGER NOT NULL CHECK (fuyin_line IN (0,1)),  -- 本支=变支（乾震互变之半卦），爻之伏吟
    line_fanfu TEXT GENERATED ALWAYS AS (CASE WHEN hua_chong = 1 THEN '反吟' WHEN fuyin_line = 1 THEN '伏吟' END) VIRTUAL,
    PRIMARY KEY (hexagram_id, move_mask, position),
    FOREIGN KEY (hexagram_id, move_mask) REFERENCES hexagram_transition(hexagram_id, move_mask),
    FOREIGN KEY (hexagram_id, position)  REFERENCES hexagram_lines(hexagram_id, position),
    CHECK (((move_mask >> (position-1)) & 1) = 1),
    CHECK (changed_polarity <> base_polarity),
    CHECK (instr('子丑寅卯辰巳午未申酉戌亥', base_branch) > 0
           AND base_element = substr('水土木木土火火土金金土水', instr('子丑寅卯辰巳午未申酉戌亥', base_branch), 1)),
    CHECK (instr('子丑寅卯辰巳午未申酉戌亥', changed_branch) > 0
           AND changed_element = substr('水土木木土火火土金金土水', instr('子丑寅卯辰巳午未申酉戌亥', changed_branch), 1)),
    CHECK (NOT (hua_chong = 1 AND fuyin_line = 1)),
    CHECK (fuyin_line = (base_branch = changed_branch))
);
CREATE INDEX ix_mlc_changed_branch ON moving_line_change(changed_branch);

CREATE TRIGGER hexagram_transition_check BEFORE INSERT ON hexagram_transition
BEGIN
    SELECT RAISE(ABORT, 'hexagram_transition: 变卦不是本卦按动爻组合翻爻所得')
    WHERE NOT EXISTS (SELECT 1 FROM hexagram_code b JOIN hexagram_code c ON c.hexagram_id=NEW.changed_hexagram_id
        WHERE b.hexagram_id=NEW.hexagram_id AND c.code =
              (CASE WHEN NEW.move_mask&1  THEN (CASE substr(b.code,1,1) WHEN '1' THEN '0' ELSE '1' END) ELSE substr(b.code,1,1) END)
            ||(CASE WHEN NEW.move_mask&2  THEN (CASE substr(b.code,2,1) WHEN '1' THEN '0' ELSE '1' END) ELSE substr(b.code,2,1) END)
            ||(CASE WHEN NEW.move_mask&4  THEN (CASE substr(b.code,3,1) WHEN '1' THEN '0' ELSE '1' END) ELSE substr(b.code,3,1) END)
            ||(CASE WHEN NEW.move_mask&8  THEN (CASE substr(b.code,4,1) WHEN '1' THEN '0' ELSE '1' END) ELSE substr(b.code,4,1) END)
            ||(CASE WHEN NEW.move_mask&16 THEN (CASE substr(b.code,5,1) WHEN '1' THEN '0' ELSE '1' END) ELSE substr(b.code,5,1) END)
            ||(CASE WHEN NEW.move_mask&32 THEN (CASE substr(b.code,6,1) WHEN '1' THEN '0' ELSE '1' END) ELSE substr(b.code,6,1) END));
    SELECT RAISE(ABORT, 'hexagram_transition: 六冲六合变化与两卦标注不符')
    WHERE NEW.relation_change IS NOT (SELECT CASE WHEN NEW.move_mask<>0 AND b.hexagram_relation<>'无' AND c.hexagram_relation<>'无'
                                                  THEN b.hexagram_relation||'变'||c.hexagram_relation END
                                      FROM hexagrams b, hexagrams c WHERE b.hexagram_id=NEW.hexagram_id AND c.hexagram_id=NEW.changed_hexagram_id);
    SELECT RAISE(ABORT, 'hexagram_transition: 内卦反吟伏吟与 trigram_fanfu 不符')
    WHERE NEW.inner_fanfu IS NOT (SELECT f.kind FROM hexagrams b, hexagrams c, trigram_fanfu f
                                  WHERE b.hexagram_id=NEW.hexagram_id AND c.hexagram_id=NEW.changed_hexagram_id
                                    AND f.half='内' AND f.from_trigram=b.lower_trigram AND f.to_trigram=c.lower_trigram);
    SELECT RAISE(ABORT, 'hexagram_transition: 外卦反吟伏吟与 trigram_fanfu 不符')
    WHERE NEW.outer_fanfu IS NOT (SELECT f.kind FROM hexagrams b, hexagrams c, trigram_fanfu f
                                  WHERE b.hexagram_id=NEW.hexagram_id AND c.hexagram_id=NEW.changed_hexagram_id
                                    AND f.half='外' AND f.from_trigram=b.upper_trigram AND f.to_trigram=c.upper_trigram);
    SELECT RAISE(ABORT, 'hexagram_transition: 卦变生克与 trigram_change 不符')
    WHERE NEW.gua_change IS NOT (SELECT CASE WHEN b.upper_trigram=b.lower_trigram AND c.upper_trigram=c.lower_trigram AND b.hexagram_id<>c.hexagram_id
                                             THEN (SELECT relation FROM trigram_change x WHERE x.from_trigram=b.upper_trigram AND x.to_trigram=c.upper_trigram) END
                                 FROM hexagrams b, hexagrams c WHERE b.hexagram_id=NEW.hexagram_id AND c.hexagram_id=NEW.changed_hexagram_id);
    SELECT RAISE(ABORT, 'hexagram_transition: 卦反吟与 gua_fanyin 规则表不符')
    WHERE NEW.gua_fanyin IS NOT (SELECT f.kind FROM hexagrams b, hexagrams c, gua_fanyin f
                                 WHERE b.hexagram_id=NEW.hexagram_id AND c.hexagram_id=NEW.changed_hexagram_id
                                   AND b.upper_trigram=b.lower_trigram AND c.upper_trigram=c.lower_trigram
                                   AND f.from_trigram=b.upper_trigram AND f.to_trigram=c.upper_trigram);
END;
CREATE TRIGGER moving_line_change_check BEFORE INSERT ON moving_line_change
BEGIN
    SELECT RAISE(ABORT, 'moving_line_change: 爻位不在 move_mask 内（只存动爻）')
    WHERE ((NEW.move_mask >> (NEW.position-1)) & 1) <> 1;
    SELECT RAISE(ABORT, 'moving_line_change: 本爻与 hexagram_lines 不符')
    WHERE NOT EXISTS (SELECT 1 FROM hexagram_lines l WHERE l.hexagram_id=NEW.hexagram_id AND l.position=NEW.position
        AND l.polarity=NEW.base_polarity AND l.stem=NEW.base_stem AND l.branch=NEW.base_branch
        AND l.element=NEW.base_element AND l.relative=NEW.base_relative);
    SELECT RAISE(ABORT, 'moving_line_change: 变爻与变卦同位爻不符')
    WHERE NOT EXISTS (SELECT 1 FROM hexagram_transition t JOIN hexagram_lines l ON l.hexagram_id=t.changed_hexagram_id AND l.position=NEW.position
        WHERE t.hexagram_id=NEW.hexagram_id AND t.move_mask=NEW.move_mask
          AND l.polarity=NEW.changed_polarity AND l.stem=NEW.changed_stem AND l.branch=NEW.changed_branch);
    SELECT RAISE(ABORT, 'moving_line_change: 变爻六亲须按本卦宫五行')
    WHERE NOT EXISTS (SELECT 1 FROM hexagrams h JOIN liuqin_rule q ON q.palace_element=h.palace_element AND q.line_element=NEW.changed_element
        WHERE h.hexagram_id=NEW.hexagram_id AND q.relative=NEW.changed_relative);
END;
CREATE TRIGGER hexagram_transition_no_update BEFORE UPDATE ON hexagram_transition BEGIN SELECT RAISE(ABORT, '固定盘只读：请改源数据后重建'); END;
CREATE TRIGGER moving_line_change_no_update BEFORE UPDATE ON moving_line_change BEGIN SELECT RAISE(ABORT, '固定盘只读：请改源数据后重建'); END;

"""

CODE_VIEW = "CREATE VIEW hexagram_code AS  -- 卦码：自下而上 6 位，1=阳；用于由动爻推变卦\nSELECT h.hexagram_id, h.name,\n       group_concat(CASE l.polarity WHEN '阳' THEN '1' ELSE '0' END, '') AS code\nFROM hexagrams h JOIN (SELECT * FROM hexagram_lines ORDER BY hexagram_id, position) l ON l.hexagram_id=h.hexagram_id\nGROUP BY h.hexagram_id;\n\n"
header_old = src[:src.index('PRAGMA foreign_keys = ON;')]
header = ("-- 京房八宫纳甲固定资料 v5（依《增删卜易》）。SQLite 3，UTF-8，在空库执行。\n"
          "-- 卦序沿用通行本；爻位 1 为初爻，6 为上爻。\n"
          "-- 伏神仅列本卦缺失的六亲，取本宫首卦同位爻。该位置的本卦爻即飞神。\n"
          "-- v2：新增按《增删卜易》固定的查表资料、约束、触发器和视图；原三表数据与 hexagram_board 视图逐行未改。\n"
          "-- v3：新增 hexagram_transition（本卦+动爻组合 move_mask，初爻=bit0，4096 行）与 moving_line_change（每个动爻一行，12288 行）；\n"
          "--     hexagram_change、change_board 改读这两张表，v2 旧列名不变。\n"
          "-- v5：新增规则表 gua_fanyin 与 hexagram_transition.gua_fanyin 列：乾坤互变（mask 63）为卦之反吟（反伏章，1925 本 PDF p88）；hexagram_change 末尾增列 gua_fanyin。\n")
body = src[src.index('PRAGMA foreign_keys = ON;'):]
body = body.replace('BEGIN TRANSACTION;\n', 'BEGIN TRANSACTION;\n' + REF + '\n', 1)
body = body.replace(OLD_HEX, NEW_HEX).replace(OLD_LINES, NEW_LINES).replace(OLD_HID, NEW_HID)
body = body.replace('COMMIT;', '\n' + CODE_VIEW + TRANS_DDL + TRANS_ROWS + VIEWS + 'COMMIT;', 1)
tail_ex = ("-- 示例：SELECT * FROM hexagram_board WHERE name='天雷无妄' ORDER BY position;\n"
           "-- 示例：SELECT changed_name FROM hexagram_change WHERE base_name='乾为天' AND moving_positions='4';\n"
           "-- 示例：SELECT * FROM change_board WHERE base_name='乾为天' AND changed_name='风天小畜';\n"
           "-- 示例：SELECT changed_name FROM hexagram_change WHERE base_name='天雷无妄' AND move_mask=3;   -- 初、二爻动 → 天水讼\n"
           "-- 示例：SELECT changed_name FROM hexagram_change WHERE base_name='天雷无妄' AND l1=1 AND l2=1 AND l3=0 AND l4=0 AND l5=0 AND l6=0;\n"
           "-- 示例：SELECT * FROM change_board WHERE base_name='天雷无妄' AND move_mask=3 ORDER BY position;\n"
           "-- 示例：SELECT move_mask, moving_positions FROM hexagram_change WHERE base_name='天雷无妄' AND changed_name='天地否';\n"
           "-- 示例：SELECT gua_fanyin FROM hexagram_change WHERE base_name='乾为天' AND move_mask=63;   -- 反吟（v5）\n"
           "-- 示例：SELECT kong_1, kong_2 FROM jiazi WHERE ganzhi='辛亥';\n"
           "-- 示例：SELECT * FROM branch_interaction WHERE actor='申' AND target='寅';\n")
body = re.sub(r'-- 示例：.*\n?$', tail_ex, body)
out = header + body


def main():
    parser = argparse.ArgumentParser(description='生成或检查当前排盘 SQL')
    parser.add_argument('--check', action='store_true', help='比对生成内容，跳过写入')
    args = parser.parse_args()
    path = ROOT / 'database' / 'gua.sql'
    if args.check:
        if path.read_text(encoding='utf-8') != out:
            parser.exit(1, 'gua.sql 与生成结果不一致\n')
        print('gua.sql 与生成结果一致')
        return
    path.write_text(out, encoding='utf-8')
    print('wrote gua.sql', len(out))


if __name__ == '__main__':
    main()
