# 解读区改造方案：EL15 逐项展开 + 六爻判断表（v2 · 已对齐库结构）

状态：**待评审**（未改渲染代码）
上一版：本文件 v1。本版按 `database/gua.sql`、`database/schema.sql`、`jingfang/review.py`、`jingfang/report.py` 的实际结构修正词汇与取数路径。

---

## 0. 一句话

解读区改成 **「首屏用神结论 → 按对象逐条说人话 → 一张六爻 × 12 列判断表」**；表里每一格都来自项目已有的表/视图或已提交的判断字段，不新建表、不新造词。

---

## 1. 本次核对了什么

| 对象 | 结论 |
| --- | --- |
| `database/gua.sql` | 13 张规则表 + `hexagram_board` / `change_board` / `branch_interaction` / `hexagram_change` 等视图；枚举全部由 `CHECK` 锁死 |
| `database/schema.sql` | 记录库 6 张业务表（`gua_record` + 5 张判断表），已有 `strength`、`effective_force`、`kong_nature`、`day_chong_result`、`overall` 等**权威力度/性质字段** |
| `jingfang/review.py` | `RECORD_FIELDS` 定义了这些字段的全部合法值；`LINE_LAYERS = {base:本, changed:变, hidden:伏}` |
| `jingfang/rule_data.py` | `_board()` 组装的 facts 只有 `chart / calendar / relations / roles / timing / moves` 六个 topic |
| `jingfang/report.py` | `validate` 要求 `RuleData.board()` 复算与已存 facts **严格全等**（`BOARD_TOPICS` 六项） |
| `jingfang/view.py` | `build_data` 另建 in-memory 库跑同一份 `gua.sql`，**可以自由加查询**，不参与 facts 比对 |
| `database/现有数据映射.md` | 「解读 Skill 只服务 HTML 渲染，不进规则指纹，也不写业务表」 |

---

## 2. 三处必须修正的不一致（v1 → v2）

### 2.1 词汇：v1 自造了一套力度词，库里已有

| 位置 | v1 写法 | 库里已有 | v2 改为 |
| --- | --- | --- | --- |
| 用神力度 | 有力 / 无力 / 中和 +「自身有力」 | `yongshen_judge.strength` ∈ **旺 / 有气 / 衰而有救 / 衰 / 无用** | 直接用五级 |
| 原忌力度 | 同上 | `yuanji_judge.effective_force` ∈ **有力 / 无力 / 中和** + `can_act_on_yong` | 三级 + 能否作用 |
| 旬空 | 空 / 空（真空）/ 空（待出） | `kong_po_judge.kong_nature` ∈ **真空 / 不为空 / 待出空** | 直接复用 |
| 月破效力 | 月破 | `kong_po_judge.po_nature` ∈ **真破 / 待出月填实** | 直接复用 |
| 日冲定性 | 日冲 / 日破 | `month_day_judge.day_chong_result` ∈ 暗动 / 日破 / 冲散 / 冲起 / 冲开 | 静爻日冲用它 |
| 综合旺衰 | 「月破旬空·有根待出」 | `month_day_judge.overall` ∈ 旺 / 有气 / 衰 / 无用 | 用它，缺则派生并标 `派` |

> 真实后果：v1 预览给世应写「世爻偏弱」，但 `shi_ying_judge` 根本没有力度字段（它存的是关系判断：`yong_to_shi` / `shi_ying_judge` / `sui_gui_ru_mu` / `jian_yao_block`）。**世应行不判力度，写 `—`**；世应强弱只在 ① 里以关系句出现。

### 2.2 取数：不能改 `_board()`，否则历史记录 validate 全挂

`validate()` 里 `reconstructed != board_evidence` 即报错。给 `_board()` 加一条查询（例如世应相冲），新记录 facts 会多一条 query 而旧记录没有 → **所有旧卦例导不出**。

因此：
- 事实类新增查询全部放 **`view.build_data`**（独立建库、独立查、不进 facts）
- 判断类字段从 `entries[].detail.fields` 读（与 `records.py` 投影同源，不重算）

### 2.3 命名：爻层与用神来源沿用库里的叫法

| v1 | v2（与库一致） |
| --- | --- |
| base / changed / hidden | `LINE_LAYERS` 的 **本 / 变 / 伏** |
| 变爻行、伏神行 | 补充行前缀 **补·变 / 补·伏 / 补·月建 / 补·日辰**（对应 `gua_record.yong_source` 五个合法值） |
| 属性「用/原/忌/世/应」 | 加 **仇神**：`yongshen_roles.choushen` 与 `yuanji_judge.shen_type` 都是一等角色 |
| 旺 / 相 / 休 / 囚 | **旺 / 相 / 休囚** 三值（`month_strength.state` 的 CHECK 只有三个，不拆休、囚） |

---

## 3. 新输出结构

```
解读
├─ 首屏一句        只讲用神状态（替换原 synthesis 长文）
├─ ① 用神盘面要点   按对象分组：用神 → 世 → 应 → 原神 → 忌神 → 各明动爻 → 结构
├─ ② 六爻判断表     6 行 × 12 列
├─ ③ 判断摘要       折叠，标「推断原文」
├─ ④ 应期通道       只写通道 + 置信度
└─ ⑤ 分层与证伪
```

`view.py` 的 `summary` 降级到 ③；新增 `headline`，由 `forces.primary_rooted` + 用神力度生成。

---

## 4. EL15 逐项展开规则

| 规则 | 内容 |
| --- | --- |
| 分组键 | **对象**，不是规则编号 |
| 组标题 | `用神 · 二爻 卯木 妻财` + 力度徽标（取库中原值） |
| 句数 | 每组 2–4 句，第 5 句折叠 |
| 句长 | ≤ 28 汉字，超长拆句 |
| 句序 | 现在怎样 → 为什么 → 还等什么 |
| 术语 | 首现括号白话：月破（被月建冲掉）、旬空（这旬轮空）、无根（自己站不住）、退神（力量往下走） |
| 去重 | 同一原因只说一次；R01 说过「休囚」，R14 的原因里删掉 |
| 缺口 | 写「需核对：日辰未给」，不猜 |
| 禁词 | `headline` / `items` / `detail_summary` 一律过 `assert_el15_text`（现在只查模板） |

---

## 5. 12 列表格

行序 **上爻 → 初爻**；一格只说一件事，最多 4 个词。

| # | 列 | 数据来源（精确到字段） | 写法 | 空值 |
| --- | --- | --- | --- | --- |
| 1 | 爻位 | `hexagram_board.position` / `line_title` | 上六 / 九五 | 必填 |
| 2 | 对象（动/静） | `chart.moving_positions`；暗动按 `forces._dark_moves` 同判据；`hidden_*` 非空 → 伏 | 明动 / 暗动 / 静 / 静·伏 | 必填 |
| 3 | 六亲 | `hexagram_board.relative`（伏神用 `hidden_relative`） | 父母 / 兄弟 | 必填 |
| 4 | 地支五行 | `stem + branch + element` | 丁卯木 | 必填 |
| 5 | 属性 | `focus.primary`→用神；`yongshen_roles.{yuanshen,jishen,choushen}` 按六亲匹配；`hexagrams.shi_line/ying_line` | 用神 / 仇神·世 | 无关爻 `—` |
| 6 | 月建影响 | `month_strength.state` + `branch_interaction(actor=月, target=爻)` 的 `wuxing / chong / he / same_branch / target_stage` | 酉月休囚·月破 | 无月建 `待核` |
| 7 | 日辰影响 | 同上，`actor=日辰` | 亥日生·长生 | 无日辰 `待核` |
| 8 | 旬空 | `jiazi.kong_1/kong_2` 命中 + `kong_po_judge.kong_nature` | 空 / 空·待出空 / 空·真空 | 不空 `—` |
| 9 | 动变情况 | `change_board`：`changed_stem/branch/element`、`huitou`、`jin_tui`、`hua_stage`、`hua_chong`、`hua_he`、`fuyin_line`；化空由 `void` 判 | 动→申金·退神 | 静爻 `—` |
| 10 | 冲合·墓绝 | `branch_interaction.target_stage`；`dizhi_chong` / `dizhi_he`（世应、动爻互作）；`hua_chong` / `hua_he` / `fuyin_line` | 与世相冲 / 见绝 / 化伏吟 | 无 `—` |
| 11 | 当前状态 | 三槽：动静 + `month_day_judge.overall`（缺则 `month_strength.state`）+ `kong_nature` / `po_nature` | 静·衰·月破 | 无 `—` |
| 12 | 力度评估 | 用神 `yongshen_judge.strength`；原忌仇 `yuanji_judge.effective_force` + `can_act_on_yong`；世应/旁爻 `—` | 衰而有救 / 有力·能作用 | 未判 `待核` |

### 5.1 生克用词（爻的视角，两字说完）

`branch_interaction.wuxing` 是 **actor 对 target** 的关系，映射不可反：

| `wuxing` | 含义 | 写法 |
| --- | --- | --- |
| `same_branch=1` | 同支 | 临 |
| `生` | 月/日生爻 | 生 |
| `克` | 月/日克爻 | 克 |
| `被生` | 爻生月/日（泄气） | 泄 |
| `被克` | 爻克月/日（耗力） | 耗 |
| `chong=1` | 月建冲 → 月破；日辰冲静爻 → 日冲 / 日破 | 月破 / 日冲 |

旧页面写「爻生月建」「不生扶（受爻所克）」，一行十几个字；这里统一为 泄 / 耗。

### 5.2 力度派生规则（只在权威字段为空时启用，格内标 `派`）

| `overall` | `primary_rooted` | 派生 `strength` |
| --- | --- | --- |
| 旺 | — | 旺 |
| 有气 | — | 有气 |
| 衰 | 有根 | 衰而有救 |
| 衰 | 无根 | 无用 |
| 无用 | — | 无用 |
| 缺 | — | 待核 |

原忌仇 `effective_force` 直接取 `forces.lines[].force`（已含 override，与 `yuanji_judge` 同源），不再派生。

### 5.3 空值二分

| 写法 | 含义 | 场景 |
| --- | --- | --- |
| `—` | 结构上本来没有 | 静爻无动变；旁爻无属性；世应无力度字段 |
| `待核` | 记录里没判，本应可判 | `strength` 空且无法派生；`can_act_on_yong` 未填 |

不用 `待时`（那是 `LAYER_STATUS_LABEL` 的分层状态，语义不同），也不拿 `—` 掩盖缺资料。

### 5.4 补充行（不破坏 6 行）

| 情况 | 行首 | 依据 |
| --- | --- | --- |
| 用神为伏神 | 补·伏 | `gua_record.yong_source='hidden'` |
| 用神为变爻 | 补·变 | `yong_source='changed'` |
| 用神取月建/日辰 | 补·月建 / 补·日辰 | `yong_source IN ('month','day')`，`yong_position` 为空 |

### 5.5 一致性校验（导出时跑，不通过标「需核对」）

| 编号 | 约束 | 实现位置 |
| --- | --- | --- |
| C1 | 用神力度 = `yongshen_judge.strength`（或 5.2 派生） | `interpretation.check_table` |
| C2 | 原忌力度 = `forces.lines[].force` | 同上 |
| C3 | 当前状态不得与该爻 `kong_nature` / `po_nature` 互斥 | 同上 |
| C4 | 第 6 列月破 ⇔ 第 10 列不重复写月冲 | 同上 |
| C5 | 表内 0 事项禁词 | `assert_el15_text` |
| C6 | 每格 ≤ 14 汉字 | 同上 |
| C7 | 6 行齐全，position 1–6 不重不漏 | 同上 |
| C8 | 所有取值 ∈ 本文档词表（白名单） | 词表常量 |

---

## 6. 与首版「角色表」的关系

角色表（判断项目 × 6 列）**并入**爻位表，不并存：角色 → 第 5 列，作用方向 → 第 12 列 `can_act_on_yong`。一个角色多爻现各自成行，候选取舍写在 ①。

---

## 7. 展示样式

预览：`docs/plans/preview-el15-line-table.html`（已按本版词表更新）

- 表宽 ~1160px，窄屏横滚，首列 sticky
- 用神行浅绿 + 左竖线；世应行浅米；明动 `○/× 动` 徽标
- 力度色块只表达力度，不表达吉凶；`派` / `待核` 用灰字小标记
- 表下「用词说明」一行：临/生/克/泄/耗/月破/日冲/`—`/`待核`

---

## 8. 代码改动清单

### 8.1 `jingfang/view.py`（主要工作量，不碰 facts）

| 动作 | 说明 |
| --- | --- |
| 改 `build_data` | 增查 `change_board` 全列（作前端/离线兜底）、`dizhi_chong` / `dizhi_he`（世应、动爻互作） |
| 改 `reading` | `summary` → `detail_summary`；增 `headline`、`interpretation.table` |
| 动变取数 | **优先 `evidence.moves` 的 `change_board` 全列**（与冻结 facts 一致）；`build_data` 全列为兜底 |
| 不改 | 不动 `RuleData._board()`、不动 `BOARD_TOPICS`、不写 `records.sqlite3` |

### 8.2 `jingfang/interpretation.py`

| 动作 | 说明 |
| --- | --- |
| 新增 | `build_line_table(chart_data, evidence, run)`：按上表 12 列取数，返回 `rows[] + gaps[]` |
| 新增 | `group_items(blocks, evidence, focus)`：平铺 blocks → 按对象分组的 `items[]` |
| 新增 | `check_table(rows, run, forces)`：C1–C8 |
| 改 | `emit_calendar_effects` 扩到 原神 / 忌神 / 明动爻；`match_presets` 去重、`who` 带爻位 |
| 保留 | `preset_blocks` 原样输出，兼容旧记录 |

### 8.3 `skills/jingfang-06-interpretation/`

- `SKILL.md` 增「表格取数与词表」小节，写明**只读、不写业务表**
- `rules.json` 用 R01–R08 既有模板覆盖原神/忌神的日月句，不新增 id
- `config.json` 增 `table_version: "2.0"`

### 8.4 `templates/hexagram-view.html`

删 `renderStrength()` + `renderKeyPoints()`（约 150 行），换 `renderItems()` + `renderTable()`；`renderBasis()` 只留应期与原忌摘要。

### 8.5 `verify/workflow/interpretation_check.py`

加：6 行齐全、C1/C2 与库值一致、每格 ≤14 字、`—`/`待核` 不混用、`headline` 无禁词、词表白名单。

---

## 9. 实施顺序

| 批次 | 内容 | 完成判据 |
| --- | --- | --- |
| P0 | `view.build_data` 补查 + `build_line_table` + 词表常量 | 6×12 数据与库一致，C1–C8 通过 |
| P1 | `group_items` + ① 区块 | 首屏要点可读，主语是用神侧 |
| P2 | 替换两张旧表 | 页面只剩一张表 |
| P3 | 回放 20261124-1323 + case3 夹具 | `validate` 通过、`--allow-claims` 不需要 |
| P4 | 375px / 打印 | 首列固定、不撕裂 |

---

## 10. 验收

- [ ] 表内每个枚举值都能在 `RECORD_FIELDS` 或 `gua.sql` 的 CHECK 里找到
- [ ] `python -X utf8 -m jingfang validate` 通过（旧记录不受影响）
- [ ] 世应行力度为 `—`，不是编造的「偏弱」
- [ ] 用神行力度与 ① 徽标一致
- [ ] 仇神行存在（本卦父母两现于三、上爻）
- [ ] 首屏一句话无事项结局、无应验日

---

## 11. 明确不做

- 不新增业务表、不改 `schema.sql`、不加迁移（渲染层只读）
- 不给 `_board()` 加查询（会破坏历史 facts 全等）
- 不用三刑（`branch_interaction.xing` 有值，但 R17 默认关闭，避免与规则启用状态冲突）
- 不引入权重分、不判吉凶、不写应验日
