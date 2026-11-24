-- =====================================================================
-- 《增删卜易》六爻断卦 · 可写记录库 v2（SQLite 3）
-- 原则：只读固定库（京房八宫纳甲固定资料 v5）只查不写；本库只存三类内容：
--   ① 起卦输入  ② 只读库给不了、需临场判断的结论  ③ 应期、吉凶、验否
-- 凡能由 本卦 hexagram_id + move_mask + 月建 + 日辰 从只读库查出的，一律不存，改用第二部分的 TEMP 视图实时关联。
-- 约定：爻位 1~6（初爻=1）；layer 指判断对象所在层：本=本卦爻，变=变爻，伏=伏神。
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 表1 起卦主记录（每卦 1 行；原“卦爻基础表”的逐爻内容全部改由视图 v_yao 提供）
-- ---------------------------------------------------------------------
CREATE TABLE gua_record (
  gua_id            TEXT PRIMARY KEY,                       -- 卦例/起卦ID
  question          TEXT NOT NULL,                          -- 占问事项原文
  question_category TEXT,                                   -- 占类：求财/功名/婚姻/疾病/出行/天时/家宅/词讼/失物等
  divine_time       TEXT,                                   -- 起卦时间 ISO8601，如 2026-11-24 10:56
  month_branch      TEXT NOT NULL CHECK (length(month_branch)=1
                    AND instr('子丑寅卯辰巳午未申酉戌亥', month_branch)>0),  -- 月建（按节气，由历法算出后录入）
  day_ganzhi        TEXT NOT NULL CHECK (length(day_ganzhi)=2),            -- 日辰干支，如 戊午（只读库 jiazi 可校验）
  hexagram_id       INTEGER NOT NULL CHECK (hexagram_id BETWEEN 1 AND 64), -- 本卦，对应只读库 hexagrams.hexagram_id
  move_mask         INTEGER NOT NULL DEFAULT 0 CHECK (move_mask BETWEEN 0 AND 63), -- 动爻掩码，初爻=bit0；0=静卦
  yong_liuqin       TEXT CHECK (yong_liuqin IN ('父母','兄弟','子孙','妻财','官鬼','世爻')), -- 用神六亲（用神章；自占可取世）
  yong_basis        TEXT,                                   -- 取用依据，如“占父病取父母”（只读库无“占事→用神”字典）
  ying_qi_basis     TEXT,                                   -- 应期取法：值日/冲空/出空填实/出月填实/冲开合/合起冲/逢生旺/入墓等
  ying_qi           TEXT,                                   -- 推得应期，如“甲寅日”“冬月”
  verdict           TEXT CHECK (verdict IN ('吉','凶','平','先吉后凶','先凶后吉','未定')), -- 吉凶
  verdict_text      TEXT,                                   -- 断语
  verified          INTEGER CHECK (verified IN (0,1)),      -- 验否：1验 0不验 NULL未知
  verify_note       TEXT,                                   -- 实际结果，如“果于甲寅日得之”
  created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ---------------------------------------------------------------------
-- 表2 用神专项判断（每个候选用神一行；两现、伏藏可多行）
-- ---------------------------------------------------------------------
CREATE TABLE yongshen_judge (
  gua_id            TEXT NOT NULL REFERENCES gua_record(gua_id) ON DELETE CASCADE,
  position          INTEGER NOT NULL CHECK (position BETWEEN 1 AND 6),
  layer             TEXT NOT NULL DEFAULT '本' CHECK (layer IN ('本','变','伏')), -- 用神在本卦、变出、伏藏
  is_selected       INTEGER NOT NULL DEFAULT 1 CHECK (is_selected IN (0,1)),     -- 两现时是否取用
  select_reason     TEXT,                                   -- 两现取舍：舍休囚用旺相、舍静用动、舍破用不破、舍空用不空、舍伤用不伤（兩現章）
  fu_can_emerge     INTEGER CHECK (fu_can_emerge IN (0,1)), -- 伏神能否得出（飛伏神章、月將章）
  fu_reason         TEXT,                                   -- 得出/不出的理由：飞来生伏、日月冲飞、飞神空破等
  ke_chu_feng_sheng INTEGER NOT NULL DEFAULT 0 CHECK (ke_chu_feng_sheng IN (0,1)), -- 受克有救（克處逢生章）
  san_he_ju         TEXT,                                   -- 三合是否成局及局性，如“申子辰水局成，生用”；不成局填 NULL
  strength          TEXT CHECK (strength IN ('旺','有气','衰而有救','衰','无用')), -- 综合力度
  remark            TEXT,
  PRIMARY KEY (gua_id, position, layer)
);

-- ---------------------------------------------------------------------
-- 表3 原神·忌神·仇神判断（谁是原忌仇由 yongshen_roles 查出，这里只存判断）
-- ---------------------------------------------------------------------
CREATE TABLE yuanji_judge (
  gua_id            TEXT NOT NULL REFERENCES gua_record(gua_id) ON DELETE CASCADE,
  shen_type         TEXT NOT NULL CHECK (shen_type IN ('原神','忌神','仇神')),
  position          INTEGER NOT NULL CHECK (position BETWEEN 1 AND 6),
  layer             TEXT NOT NULL DEFAULT '本' CHECK (layer IN ('本','变','伏')),
  tan_sheng_wang_ke INTEGER NOT NULL DEFAULT 0 CHECK (tan_sheng_wang_ke IN (0,1)), -- 贪生/贪合忘克
  yuan_ji_tong_dong INTEGER NOT NULL DEFAULT 0 CHECK (yuan_ji_tong_dong IN (0,1)), -- 原忌同动，连续相生（元神忌神衰旺章）
  effective_force   TEXT CHECK (effective_force IN ('有力','无力')),               -- 按元神有用五条、无用诸条判
  force_reason      TEXT,                                   -- 判有力/无力的依据
  can_act_on_yong   INTEGER CHECK (can_act_on_yong IN (0,1)),                      -- 能否实际生/克用神
  remark            TEXT,
  PRIMARY KEY (gua_id, shen_type, position, layer)
);

-- ---------------------------------------------------------------------
-- 表4 月建日辰作用判断（只记需要旺衰综合判断的结论；生克冲合墓绝本身由 v_yao 查）
-- ---------------------------------------------------------------------
CREATE TABLE month_day_judge (
  gua_id            TEXT NOT NULL REFERENCES gua_record(gua_id) ON DELETE CASCADE,
  position          INTEGER NOT NULL CHECK (position BETWEEN 1 AND 6),
  layer             TEXT NOT NULL DEFAULT '本' CHECK (layer IN ('本','变','伏')),
  day_chong_result  TEXT CHECK (day_chong_result IN ('暗动','日破','冲散','冲起','冲开')), -- 日辰冲爻的定性（日辰章、暗動章）
  overall           TEXT CHECK (overall IN ('旺','有气','衰','无用')),  -- 综合旺衰（月日、动爻合参）
  remark            TEXT,
  PRIMARY KEY (gua_id, position, layer)
);

-- ---------------------------------------------------------------------
-- 表5 空破动变判断（“是否旬空/月破/化空/化破/回头生克/进退”由 v_yao 查，这里只存效力判断）
-- ---------------------------------------------------------------------
CREATE TABLE kong_po_judge (
  gua_id            TEXT NOT NULL REFERENCES gua_record(gua_id) ON DELETE CASCADE,
  position          INTEGER NOT NULL CHECK (position BETWEEN 1 AND 6),
  layer             TEXT NOT NULL DEFAULT '本' CHECK (layer IN ('本','变','伏')),
  kong_nature       TEXT CHECK (kong_nature IN ('真空','不为空','待出空')),   -- 旺不为空、动不为空、有生扶不为空（旬空章）
  po_nature         TEXT CHECK (po_nature IN ('真破','待出月填实')),          -- 月破有无救（月破章）
  hua_effect        TEXT,                                   -- 化出效力判断，如“化回头克而日生，受克有救”“化空而旺动，待出空”
  du_fa_du_jing     TEXT CHECK (du_fa_du_jing IN ('独发','独静')),           -- 是否按独发/独静取应（獨發章）
  ying_qi_channel   TEXT,                                   -- 此爻提供的应期通道：出空日、冲空日、出月、冲开合日等
  remark            TEXT,
  PRIMARY KEY (gua_id, position, layer)
);

-- ---------------------------------------------------------------------
-- 表6 世应判断（世应爻位、六亲、生克冲合由 v_yao/v_shi_ying 查；这里只存判断）
-- ---------------------------------------------------------------------
CREATE TABLE shi_ying_judge (
  gua_id            TEXT NOT NULL REFERENCES gua_record(gua_id) ON DELETE CASCADE,
  item              TEXT NOT NULL CHECK (item IN ('世','应','间爻')),
  position          INTEGER NOT NULL DEFAULT 0 CHECK (position BETWEEN 0 AND 6), -- 世/应填 0（爻位可查）；间爻填实际爻位
  sui_gui_ru_mu     INTEGER NOT NULL DEFAULT 0 CHECK (sui_gui_ru_mu IN (0,1)),   -- 世随鬼入墓（隨鬼入墓章）
  yong_to_shi       TEXT,                                   -- 用神/动爻对世的效力判断，如“财动生世有力”
  jian_yao_block    INTEGER CHECK (jian_yao_block IN (0,1)),-- 间爻发动是否构成阻隔（化退、空破则无力）
  shi_ying_judge    TEXT,                                   -- 世应关系结论，如“应空，彼无实心”
  remark            TEXT,
  PRIMARY KEY (gua_id, item, position)
);

-- =====================================================================
-- 第二部分：只读库关联视图（每次连接执行一次）
-- 说明：SQLite 的持久视图不能引用 ATTACH 的其他库，所以用 TEMP VIEW；
--       只读库以 mode=ro 挂载，保证只查不写（Python 需 sqlite3.connect(..., uri=True)）。
-- =====================================================================
-- ATTACH DATABASE 'file:/path/najia_v5.db?mode=ro' AS fix;

-- 卦级：本卦/变卦、卦宫、世数、六冲六合、冲合变化、反伏、卦变、旬空、日干
CREATE TEMP VIEW v_gua AS
SELECT g.gua_id, g.question, g.month_branch, g.day_ganzhi, g.move_mask,
       substr(g.day_ganzhi,1,1) AS day_stem, substr(g.day_ganzhi,2,1) AS day_branch,
       j.kong_1, j.kong_2,
       c.base_name, b.palace, b.palace_element, b.palace_stage, b.shi_line, b.ying_line,
       c.base_relation   AS gua_relation,        -- 六冲/六合/无
       c.changed_name, c.changed_relation, c.relation_change,
       c.inner_fanfu, c.outer_fanfu, c.gua_change, c.gua_fanyin,
       c.moving_positions, c.moving_count,       -- moving_count=1 即独发
       g.yong_liuqin, r.yuanshen, r.jishen, r.choushen
FROM gua_record g
JOIN fix.hexagram_change c ON c.base_id=g.hexagram_id AND c.move_mask=g.move_mask
JOIN fix.hexagrams b       ON b.hexagram_id=g.hexagram_id
JOIN fix.jiazi j           ON j.ganzhi=g.day_ganzhi
LEFT JOIN fix.yongshen_roles r ON r.yongshen=g.yong_liuqin;

-- 爻级：纳甲六亲、世应、六神、角色、动静、旺衰、月日作用、旬空月破、变爻与化出、伏神
CREATE TEMP VIEW v_yao AS
SELECT v.gua_id, l.position, l.polarity, l.stem, l.branch, l.element, l.relative, l.shi_ying,
       ls.spirit AS liu_shen,
       CASE l.relative WHEN v.yong_liuqin THEN '用神' WHEN v.yuanshen THEN '原神'
                       WHEN v.jishen THEN '忌神' WHEN v.choushen THEN '仇神' END AS role,
       (l.position > min(v.shi_line,v.ying_line) AND l.position < max(v.shi_line,v.ying_line)) AS is_jian_yao,
       (v.move_mask >> (l.position-1)) & 1 AS is_moving,
       ms.state AS wang_shuai, ms.note AS wang_shuai_note,           -- 旺/相/休囚（余气见 note）
       mi.wuxing AS month_wuxing, mi.same_branch AS lin_month, mi.chong AS month_po, mi.he AS month_he,
       di.wuxing AS day_wuxing, di.same_branch AS lin_day, di.chong AS day_chong, di.he AS day_he,
       di.target_stage AS day_stage,                                  -- 日辰长生/帝旺/墓/绝
       (l.branch IN (v.kong_1, v.kong_2)) AS is_kong,
       CASE WHEN di.chong=1 AND ((v.move_mask >> (l.position-1)) & 1)=0
            THEN CASE WHEN ms.state IN ('旺','相') THEN '暗动候选' ELSE '日破候选' END END AS day_chong_hint,
       cb.changed_branch, cb.changed_element, cb.changed_relative,
       cb.huitou, cb.jin_tui, cb.hua_stage, cb.hua_chong, cb.hua_he, cb.line_fanfu,
       (cb.changed_branch IN (v.kong_1, v.kong_2)) AS hua_kong,
       (SELECT chong FROM fix.branch_interaction x WHERE x.actor=v.month_branch AND x.target=cb.changed_branch) AS hua_po,
       l.hidden_branch, l.hidden_element, l.hidden_relative,
       (SELECT wuxing FROM fix.branch_interaction x WHERE x.actor=l.branch AND x.target=l.hidden_branch) AS fei_to_fu, -- 飞对伏：生/克/比和/被生/被克
       (l.hidden_branch IN (v.kong_1, v.kong_2)) AS fu_kong,
       (SELECT chong FROM fix.branch_interaction x WHERE x.actor=v.month_branch AND x.target=l.hidden_branch) AS fu_month_po
FROM v_gua v
JOIN fix.hexagrams h            ON h.name=v.base_name
JOIN fix.hexagram_board l       ON l.hexagram_id=h.hexagram_id
LEFT JOIN fix.liushen ls        ON ls.day_stem=v.day_stem AND ls.position=l.position
LEFT JOIN fix.month_strength ms ON ms.month_branch=v.month_branch AND ms.element=l.element
JOIN fix.branch_interaction mi  ON mi.actor=v.month_branch AND mi.target=l.branch
JOIN fix.branch_interaction di  ON di.actor=v.day_branch   AND di.target=l.branch
LEFT JOIN fix.change_board cb   ON cb.base_id=h.hexagram_id AND cb.move_mask=v.move_mask AND cb.position=l.position;

-- 动爻对各爻的作用（动爻只取明动；变爻只作用本位动爻，见 v_yao 的 huitou）
CREATE TEMP VIEW v_dong_effect AS
SELECT a.gua_id, a.position AS actor_pos, a.relative AS actor_relative,
       t.position AS target_pos, t.relative AS target_relative,
       x.wuxing, x.chong, x.he, x.target_stage
FROM v_yao a JOIN v_yao t ON t.gua_id=a.gua_id AND t.position<>a.position
JOIN fix.branch_interaction x ON x.actor=a.branch AND x.target=t.branch
WHERE a.is_moving=1;

-- 世应关系
CREATE TEMP VIEW v_shi_ying AS
SELECT s.gua_id, s.position AS shi_pos, s.relative AS shi_relative, s.branch AS shi_branch,
       y.position AS ying_pos, y.relative AS ying_relative, y.branch AS ying_branch,
       x.wuxing AS shi_to_ying, x.chong, x.he, y.is_kong AS ying_kong
FROM v_yao s JOIN v_yao y ON y.gua_id=s.gua_id AND y.shi_ying='应'
JOIN fix.branch_interaction x ON x.actor=s.branch AND x.target=y.branch
WHERE s.shi_ying='世';

-- 用神候选（含两现、伏藏）：供填写 yongshen_judge 前查看
CREATE TEMP VIEW v_yong_candidates AS
SELECT gua_id, position, '本' AS layer, branch, element, wang_shuai, is_moving, is_kong, month_po, day_chong_hint
FROM v_yao WHERE role='用神'
UNION ALL
SELECT y.gua_id, y.position, '伏', y.hidden_branch, y.hidden_element, NULL, 0, y.fu_kong, y.fu_month_po, NULL
FROM v_yao y JOIN v_gua g ON g.gua_id=y.gua_id
WHERE y.hidden_relative=g.yong_liuqin
  AND NOT EXISTS (SELECT 1 FROM v_yao z WHERE z.gua_id=y.gua_id AND z.relative=g.yong_liuqin);
