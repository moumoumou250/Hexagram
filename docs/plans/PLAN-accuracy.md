# Jingfang v5 准确性改造方案

本方案针对「解卦准确性」提出改动，来源是对 `dao`、`fortune-liuyao-skill`、`liuyao-divination-main`、`liuyao-master` 四个项目的对照阅读。规则条文不抄（v5 已是唯一按 1925 本逐章立规的版本），只吸收它们在**判断如何被验证、误判如何被拦截**上的做法。

## 一、现状诊断

| 层 | 现状 | 缺口 |
| --- | --- | --- |
| 排盘 | `verify/sql/oracle_v3.py` 复算 64×64，`verify/cases` 核对 53 例，百例核对 100 例全过 | 无缺口 |
| 规则 | 五份 SKILL 带章节引用，`gua.sql` 冻结快照 | 无缺口 |
| 判断 | `review.normalize_entries` 校验引用与字段一致性 | 结论是自由文字，**无法核对、无法积累** |
| 误判 | `review.flagged_items` 只有 5 条提示 | 用神无根、元忌力度、三合虚实、空墓、化空破墓、进退神均无提示 |
| 表述 | HTML 输出吉凶与理由 | 结论写错盘面（爻位、六亲、世应）无任何拦截 |

结论：准确性的瓶颈不在规则，在**没有反馈闭环**，和**判断层没有被程序预判的部分**。

## 二、三条硬约束

1. **不新增步骤。** `Orchestrator._load` 用 `set(steps) != set(STEPS)` 校验，新增第六步会让 `reading-logs/` 下所有现存记录直接报「解卦步骤状态无效」。取象、分层等一律并入 `synthesis`。
2. **不改 `gua.sql`。** 保住 `oracle_v3.py`、`cases_check.py`、百例核对的基线；本方案所需的三合（`sanhe`）、长生墓绝（`changsheng`）、进退神（`jin_tui`）表已齐备。
3. **新字段只在新提交时必填。** v5 的 `validate` 是严格回放，若对旧记录也校验新字段，4 份历史记录立即失效。必填性放在 `submit` 路径，回放路径一律容错（`.get`）。

## 三、变更清单

| 编号 | 事项 | 优先级 | 主要文件 | 规模 |
| --- | --- | --- | --- | --- |
| M1 | 应期多通道窗口与置信度 | P0 | `jingfang-05-timing/SKILL.md`、`review.py` | 中 |
| M2 | 结论分层与证伪条件 | P0 | `review.py`、`orchestrator.py`、`report.py` | 中 |
| M3 | 应验登记与复盘渲染 | P0 | `orchestrator.py`、`__main__.py`、`report.py` | 中 |
| M4 | 判断摘要的盘面断言审计 | P0 | 新建 `jingfang/audit.py`、`report.py` | 中 |
| M5 | 元忌有力无力预判 | P1 | 新建 `jingfang/forces.py`、`orchestrator.py` | 大 |
| M6 | 自查清单扩容 | P1 | `review.py`、`rule_data.py` | 中 |
| M7 | 受限取象层（最小版） | P2 | `AGENTS.md`、`view.py`、模板 | 中 |
| M8 | 行动建议与免责收尾 | P2 | `view.py`、`templates/hexagram-view.html` | 小 |
| M9 | 起卦前清晰度门槛 | P2 | `AGENTS.md`、`reading_input` | 小 |

---

## 四、M1 应期多通道窗口

**问题。** `jingfang-05-timing` 要求「输出主事爻、候选应期及首选」，但结果是一段文字，几个候选各自独立，没有「几条通道指向同一窗口」的概念，也无法核对。

**改法。** `timing` 步骤新增结构化条目 `topic: "window"`，一条通道一条记录：

```json
{"state": "accepted", "skill_use": "applied",
 "entries": [
   {"kind": "judgment", "topic": "window", "skill": "timing", "section": "操作",
    "branch": "亥", "unit": "月", "channel": "当令",
    "summary": "用神亥水衰，待亥月当令得旺", "refs": [...]},
   {"kind": "judgment", "topic": "window", "skill": "timing", "section": "操作",
    "branch": "丑", "unit": "月", "channel": "冲墓",
    "summary": "世爻入未墓，丑冲未出墓，但丑土克水，财同转弱", "refs": [...]}
 ]}
```

字段与校验（`review.normalize_entries` 内新增分支）：

| 字段 | 取值 | 校验 |
| --- | --- | --- |
| `branch` | 十二支 | 必须在 `dizhi` 中 |
| `unit` | `日`/`月`/`年` | 枚举 |
| `channel` | `值`/`合`/`冲`/`填实`/`冲墓`/`当令`/`克神受克`/`化出之支值` | 枚举 |
| `confidence` | 由程序算，不由 Agent 填 | 同一 `branch+unit` 的不同 `channel` 数 ≥2 → `high`，=1 → `candidate`；若两条记录的 `unit` 不同但落在同一月（年+月换算）→ 标 `conflict` |

程序在 `timing` 提交后生成 fact `windows`，汇总每个窗口的通道列表与置信度，供 `synthesis` 引用。`_check_findings` 增加：`ask_timing=true` 且 `timing` 为 `accepted` 时，至少一条 `window`。缺 `当令`/`填实` 仅写入 `checks` 告警，**不阻断**（避免 Agent 硬贴标签）。

**为什么不新增「通道表」。** 通道只是取值的枚举，判定逻辑（哪些状态走哪条通道）留在 SKILL 里，程序只做一致性与计数。这样规则修订不必改代码。

**验收。** 用 CASES.md 已记应期的 30 例回放：手工把书中断语转成 `window` 条目，检查程序算出的置信度与书中「应验于某日/某月」是否同窗；不同窗的案例记入 `docs/verification/`，作为窗口规则的反例清单。

---

## 五、M2 结论分层与证伪条件

**问题。** 现有结论形如「这次有望升职」，无时间窗、无分层、无证伪条件。这种结论事后怎么解释都对，等于不可校验。

**改法。** `synthesis` 提交新增顶层 `verdict`（与 `focus` 同级，存 `run["verdict"]`）：

```json
{"state": "accepted", "skill_use": "applied",
 "entries": [ ...现有一条 conclusion... ],
 "verdict": {
   "direction": "favorable",
   "layers": [
     {"name": "牵绊不断", "condition": "亥卯未虚合、变卦六合、日建根", "status": "met", "refs": [16, 19]},
     {"name": "关系确立", "condition": "化出之支六合用神，值日兑现", "status": "waiting", "refs": [21]},
     {"name": "全实", "condition": "用神当令且世爻出墓", "status": "waiting", "refs": [22, 24]}
   ],
   "falsifier": "若 2027 年 3 月前双方无任何实质进展，则本次「可成」的判断偏错"
 }}
```

校验（新函数 `review.verdict_choice`）：

1. `direction` ∈ `favorable`/`unfavorable`/`mixed`；旧记录无此字段，`report.render` 渲染为「本次未记录分层条件」。
2. `layers` 非空，`name` 唯一且不超过 20 字，`status` ∈ `met`/`waiting`/`unlikely`。
3. 每层 `refs` 必须指向已存在的 `judgment` 条目——**层必须由已有判断支撑，不能凭空造层**。这是防止事后补释的关键约束。
4. `falsifier` 长度 10–120 字，且不得为空。无证伪条件的结论不许提交。
5. 一致性告警（不阻断）：所有层均为 `unlikely` 而 `direction=favorable`，写进 `checks`。

**渲染。** `report.render` 在第 5 节末追加：

```
### 结论的分层与证伪条件

| 层 | 成立条件 | 状态 | 依据 |
| --- | --- | --- | --- |
| 关系确立 | 化出之支六合用神，值日兑现 | 待时 | E21 |

- 证伪条件 · 若 2027 年 3 月前...
```

**验收。** 4 份旧记录仍能 `validate` 与 `export`（缺 `verdict` 走容错分支）；`blackboard_check.py` 的 `finish()` 需补 `verdict`，同步更新。

---

## 六、M3 应验登记与复盘

**问题。** 没有地方记录「后来应了没有」。`reading-logs` 只增不改，`rule-versions` 只保证复算一致，都不涉及判断对错。

**改法。** 新增命令：

```
python -X utf8 -m jingfang outcome <解卦编号> <应验.json>
```

`应验.json`：

```json
{"checked_at": "2027-03-15", "result": "partial",
 "layers": [
   {"name": "牵绊不断", "status": "met", "evidence": "12 月至 2 月持续联系"},
   {"name": "关系确立", "status": "met", "evidence": "3 月 8 日确认关系"}
 ],
 "note": "全实层未发生"}
```

校验与存储：

- 仅允许 `synthesis` 为 `accepted` 的记录追加；可多次追加，按 `checked_at` 排序。
- `layers[].name` 必须是 `run["verdict"]["layers"]` 中的层名。**未在占时写明的层不许作为应验层**——命中则记为「事后补充」，单独渲染。
- `result` ∈ `met`/`partial`/`unmet`/`unresolved`。
- 追加不清空、不改写已有条目，`Journal.writer` 已保证原子性。

**渲染。** 新增第 6 节：

```
## 6. 应验与复盘

- 核对日期 · 2027-03-15 · 结果 · 部分应验

| 层 | 占时状态 | 实际 | 证据 | 证据强度 |
| --- | --- | --- | --- | --- |
| 牵绊不断 | 已备 | 应 | 12 月至 2 月持续联系 | 强（占时已写明该层） |
| 同住 | — | 已应 | 4 月起同住 | 弱（占时未设该层，事后补充） |
```

证据强度由「层名是否存在于 `verdict.layers`」自动判定，不让 Agent 自称。这一步对应 `12-应期与应验.md` 里「强证据 = 事前断语，弱证据 = 事后补释」的区分。

**不做统计报表。** 目前只有 4 份记录，出「断准率」没有统计意义，且会诱导为凑数而放松判断。等有 20 份以上带 `outcome` 的记录再议 `jingfang stats`。

---

## 七、M4 判断摘要的盘面断言审计

**问题。** 现有 4 份记录里，判断摘要含大量盘面断言（「五爻应位妻财亥水」）。这类断言写错，等于盘面读错还写进结论，而 `validate` 只校验 JSON 结构与复算一致性，不看摘要文字。

**为什么不照搬 `fortune-liuyao-skill/scripts/verify_facts.py`。** 它对最终 Markdown 全文做正则，误报率高（正文里「化出之官」「伏神」等语境无法区分）。v5 的判断摘要已经是结构化 JSON，**只扫 `entries[*].summary`**，语境由 `topic` 与上下文词决定，精度可控。

**改法。** 新建 `jingfang/audit.py`：

```python
def audit_claims(run) -> {"checked": int, "conflicts": [...]}
```

三类句式，命中后按语境路由到正确数据源：

| 句式 | 正则（要点） | 比对对象 |
| --- | --- | --- |
| 爻位 + 六亲 | `([初二三四五上])爻[^，。；]{0,4}(父母\|兄弟\|子孙\|妻财\|官鬼)` | 前 4 字含「化」「变」→ `change_board`；含「伏」→ `hidden_*`；否则 `hexagram_board` |
| 六亲 + 支 + 五行 | `(父母\|兄弟\|子孙\|妻财\|官鬼)([子丑…亥])([木火土金水])` | 同上路由，四件套同时比 |
| 世应位置 | `世(?:在\|居\|临)?第?([一二三四五六])爻`、`应…` | `chart.shi_line` / `chart.ying_line` |

命中但比对不符 → 记 `{entry_id, claim, expected, actual}`。**只报冲突，不判吉凶。**

**接入。** `Orchestrator.validate` 返回值增加 `claims`；`export --html` 在 `conflicts` 非空时拒绝导出，可用 `--allow-claims` 强制。`submit` 阶段不阻断（避免打断连续解卦），只在 `synthesis` 的 `checks` 里列出。

**验收。** 4 份现有记录 0 冲突；新增单测覆盖 8 种句型（本爻、变爻、伏神、世应、「三、四爻」并列、「化官鬼」、无六亲的「五、上爻同动」、阿拉伯数字爻位）。

---

## 八、M5 元忌有力无力预判

**问题。** `jingfang-03-strength` 把「原神有力五条 / 无用六条 / 忌神有力五条 / 不克七条」共 23 条交给 Agent 逐条回忆，漏一条结论就偏。`liuyao-divination-main/src/liuyao/board.py` 的 `_spirit_effective()` 证明这套判定可以程序化。

**改法。** 新建 `jingfang/forces.py`，纯函数，输入 `evidence` 与 `run["focus"]`，不碰数据库：

```python
def forces(evidence, focus):
    """每爻返回 {position, relative, role, force, reasons[], rooted}"""
```

`force` 判定顺序（照 1925 本原文重排，与 `_spirit_effective` 的优先级不同——原项目先判无力，会把「旺动临空」误判为无力）：

1. 先判「有用而暂困」：旺相 + 旬空 → `有力(待出空)`；旺相 + 月破 → `有力(出月不破)`。这两条对应书中「旺不为空」「破爻动则仍能伤爻」。
2. 再判无力：月破且休囚、日破、真空（春土夏金秋木冬火）、入三墓、化退神、化回头克、休囚不动。
3. 再判有力：临日月、旺相、动或暗动、化回头生、化进神、与忌神（或元神）同动。
4. 其余 `中和`。

每条命中都要写 `reasons`（如 `["月破", "休囚", "非动"]`），渲染时原样展示，Agent 引用时必须带上理由。

**用神另加 `rooted`。** 对应用神「有根/无根」：月破又受日克、或衰绝无生扶 → `无根`，此时即使元忌力度相反也不改判（书中「用神无根，元神有力亦难生」）。

**挂载点。** `focus` 步骤提交成功后，`Orchestrator._apply` 调用 `forces()`，以 fact 写入 `FACT_LABELS["forces"] = "用神元忌的力量判定"`；`TOPICS` 给 `strength`/`change`/`timing`/`synthesis` 加上 `forces`。

> **实现陷阱（M1、M5 都会踩）。** `report.validate` 断言 `RuleData.board()` 的复算结果与记录的 facts **完全相等**（`if reconstructed != evidence`）。`facts()` 按 topic 聚合全部 fact 条目，一旦新增 `forces`、`windows` 这类不由 `board()` 生成的 fact，该断言必然失败，导致所有新记录无法 `export`。改法：把比较范围收窄为 `board()` 的产出集（`chart`/`calendar`/`relations`/`roles`/`timing`/`moves`），其余 topic 跳过；同时 `validate` 的返回里区分「复算一致」与「派生一致」两类。这一条必须与 M5 同批改，否则新记录一律导不出。

**争议处理。** 程序判定与书中断语冲突时以书为准，条目支持 `"force_override": "有力"` 与 `"override_reason": "…"`，回放时优先取 override，并在 Markdown 中标出。这一条必须有，否则遇到口径分歧会卡住解卦。

**验收。** 新增 `verify/workflow/forces_check.py`：对 CASES.md 53 例，逐例输出程序判定的元/忌力度与实际断语方向（吉/凶）的对照表，**第一版只产统计，不设通过阈值**。基线数字写入 `docs/verification/`，作为后续调规则的依据。这一项改动的价值不在第一天就准，而在把「凭记忆判力度」变成「有记录可校准」。

---

## 九、M6 自查清单扩容

`review.flagged_items` 现有 5 条（用神多现、月破临日、日冲、回头克/化合、卦级反吟），扩为 11 条：

| 新增提示 | 触发条件 | 数据来源 |
| --- | --- | --- |
| 用神无根 | 主用神月破且受日克，或衰绝无生扶 | `forces.rooted == 无根` |
| 元忌力度 | 存在 `force != 中和` 的元/忌 | `forces` |
| 三合虚实 | 卦爻 + 月 + 日 + 变支中出现完整三合三支 | 派生 fact `sanhe`（`sanhe_scan`，**不**改 `board().timing`） |
| 空墓 | 用神或世爻入墓且墓库支落旬空 | `changsheng` + `calendar.void` |
| 化空 / 化破 / 化墓 | `change_board.hua_stage` ∈ {墓, 绝}，或变支落空 | `change_board` |
| 进退神 | `jin_tui` 非空 | `change_board` |
| 独发独静 | 明动爻数 = 1 或 5 | `chart.moving_positions` |

三合虚实需单独判：三支齐备后数「卦内动爻（含暗动）数」——≥2 为实局，=1 且靠月日凑齐为虚一待用，支齐而有月破为破而待填。三种结论分别给不同提示语。这一层对应 `06-三合六合.md` 里标记为「最易判错」的部分。

---

## 十、M7 受限取象层（最小版）

**问题。** v5 没有取象，六神只作「辨事参考」，HTML 的白话结论只有吉凶方向，没有「为什么是这个意思」。

**最小版做法（推荐先做）。** 不新增 skill 文件（新增会改 `RULE_FILES` 指纹，牵动 `compat` 回归），只允许 `synthesis` 提交 `topic: "image"` 条目，`skill` 填 `change`、`section` 填该 skill 的真实小节名，从而复用现有校验链：

```json
{"kind": "judgment", "topic": "image", "skill": "change", "section": "操作",
 "domain": "career",
 "elements": ["官鬼持世", "外卦反吟", "玄武"],
 "summary": "官鬼持世而外卦反吟：职位本身属我，但岗位会来回调整，非一次定盘",
 "refs": [12, 15]}
```

同时往 `AGENTS.md` 加一节「取象约束」，写明三条（来自 `13-象意解读.md` 的语法，不是条文）：

1. 象只取盘面已有要素（五行、爻位、世应、六神、卦名、进退神），不引入神煞。
2. **象核无吉凶，随域翻转**——化进在求财是增益、在疾病是转重；不得由象反推五行结论。
3. 多象同向方可定性，孤象不入结论；六神只作形容词，不改吉凶。

**完整版（可选，单独立项）。** 新增 `skills/jingfang-image/SKILL.md` 并入 `RULE_FILES`，代价是所有新记录指纹变更、`compat_v2.py` 需复核。

---

## 十一、M8 / M9 输出与入口

**M8 收尾。** `view.reading_page` 的 `reading` dict 增加 `actions`（由 `verdict.layers` 中 `status=waiting` 的层生成「等什么条件、等到何时」）与 `disclaimer`（固定文本）。模板在结论区下方渲染。改模板后 `export --html` 即可生效，`tools/build_view.py` 只负责内嵌 `chart-data`，不受影响。

**M9 门槛。** `AGENTS.md` 增加「起卦前」一段：问题须能识别**核心事项**与**所求结果**，两项缺一先问一句、不起卦；一次多问取优先。代码侧只加一条软校验：`reading_input` 中 `question` 去掉标点后少于 6 字时拒绝，提示补充。不做语义判断——关键词计数会误伤「问这个能不能成」这类正常短问。

---

## 十二、兼容性矩阵

| 变更 | 旧记录 validate | 旧记录 export | blackboard_check | cases_check | oracle_v3 | 规则指纹 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | 通过（无 window 不校验） | 通过 | 需补 window 或放宽 | 不受影响 | 不受影响 | 变（改 SKILL） |
| M2 | 通过（`.get` 容错） | 通过（渲染「未记录」） | **需补 verdict** | 不受影响 | 不受影响 | 不变 |
| M3 | 通过（`outcomes` 缺省空） | 通过（无第 6 节） | 不受影响 | 不受影响 | 不受影响 | 不变 |
| M4 | 通过（只报 warning） | 有冲突时拒绝 | 需确认 fixture 摘要无冲突 | 不受影响 | 不受影响 | 不变 |
| M5 | 通过 | 通过 | 需补 forces fact 的引用 | 不受影响 | 不受影响 | 不变 |
| M6 | 通过 | 通过 | 需确认新提示不阻断 | 不受影响 | 不受影响 | 不变（只改代码；若同批改 SKILL 则变） |
| M7 | 通过 | 通过 | 不受影响 | 不受影响 | 不受影响 | 不变（最小版） |
| M8 | 通过 | 通过 | 不受影响 | 不受影响 | 不受影响 | 不变 |

规则指纹变化只影响**新**记录（`freeze_rules` 在 `start` 时写入），旧记录仍用各自快照，`rule_source` 逻辑无需改动。

---

## 十三、实施批次

**批 1（P0，先止血）**
0. 先把 `report.validate` 的比较范围从「全部 facts」收窄为「`board()` 的产出集」——这是 M1/M5 的前置；`forces`/`windows`/`sanhe` 一律派生 fact，不改 `board()` 形状
1. M4 审计模块 + 单测（不改任何提交格式，风险最低，先跑通）
2. M2 verdict（`review.verdict_choice` + `_apply` + `render`）
3. M3 outcome 命令 + 第 6 节渲染
4. 同步 `verify/workflow/journal_check.py` 的 `finish()`

批 1 验收：`verify/run_all.py` 全绿；有状态脚且规则快照齐全的旧记录 `validate`/`export` 通过；新解一卦走完全流程，Markdown 出现分层表，`outcome` 追加后出现第 6 节。

**批 2（P1，把误判前置）**
5. M5 `forces.py` + 挂载 + `force_override`
6. M6 清单扩容（派生 `sanhe` fact，不改 `board().timing`）
7. M1 window 条目 + 置信度（改 timing SKILL；当令/填实仅告警）
8. `verify/workflow/forces_check.py` 产出基线统计

批 2 验收：书例力度对照表生成；`checks` 能命中三合虚实/空墓等；应期 accepted 时至少一条 window。

**批 3（P2，表述与入口）**
9. M7 最小版 + `AGENTS.md` 取象约束（`topic:image`，`skill` 用既有 Skill）
10. M8 模板收尾
11. M9 门槛

批 3 验收：`export --html` 结论区出现行动与免责；`view_check.cjs` 仍通过。

**批 4（观察期）**
积累 ≥20 份带 `outcome` 的记录后，再评估是否做 `jingfang stats`、是否把某条力度规则从 `forces.py` 移入 SKILL（条件是先有反例）。

---

## 十四、风险与取舍

| 风险 | 表现 | 应对 |
| --- | --- | --- |
| 分层造层 | Agent 为满足校验编造四五个层 | 每层必须 `refs` 指向已有判断；层名不得超出已引用判断的语义 |
| 证伪条件流于形式 | 写成「若判断错了则我错了」 | 长度下限 + 必须含具体时间或具体事件（人工复核，不做程序判定） |
| 力度预判与书冲突 | 程序判「有力」，书中断凶 | `force_override` 以书为准，冲突记入 `docs/verification/` 作为规则分歧表 |
| 审计误报 | 「化出之官」被当本爻官鬼 | 语境路由 + 只报冲突不阻断 + `--allow-claims` |
| outcome 样本少 | 得出虚假「准确率」 | 明确不做统计报表；样本门槛 20 份 |
| 规则指纹漂移 | 历史记录与新规则混用 | 已有 `rule-versions/` 快照机制，不改动 |

## 十五、明确不做

1. 不引入六害、卦身——`docs/CHANGES.md` 已按 1925 本原文排除（「六害章全无应验，删之不录」）。
2. 不搬 `liuyao-divination-main` 的简化反吟判定——v5 的 `gua_fanyin` 已覆盖乾坤互变，简化版更弱。
3. 不用 `dao/data` 的卦爻辞改变五行结论。野鹤一派重五行轻爻辞，爻辞最多作取象佐证，权重必须低于五行。
4. 不做自动起卦、不做多卦合断的批量流程——超出现有单 Agent 顺序解卦的边界。
5. 不在第一版做「准确率」面板。

## 十六、外部项目优点对照（补充阅读后新增）

三个项目值得吸收的优点，按「是否已进本方案」归类：

### 已被方案吸收

| 优点 | 来源 | 落点 |
| --- | --- | --- |
| 应期多通道交叉 + 强弱证据区分 | divination-main `12-应期与应验.md` | M1/M3 |
| 结论分层条件 + 证伪式断语 | divination-main `12-应期与应验.md` | M2 |
| 有力无力程序预判（返回三态 + 理由） | divination-main `board.py::_spirit_effective` | M5 |
| 象核 × 域 × 角色取象语法 | divination-main `13-象意解读.md` | M7 |
| 正文盘面断言审计 | fortune `scripts/verify_facts.py` | M4（改良：只扫结构化摘要） |
| 起卦前清晰度门槛 | fortune `references/domain-routing.md` | M9 |

### 本轮补读新发现，建议吸收

| 优点 | 来源 | 价值 | 落点 |
| --- | --- | --- | --- |
| **追问锁定规范**：不重新起卦、不用当前日期替换原起卦月日、不因用户想听好话改写盘面、五类追问分流、复盘时「不事后改写原始结论制造应验」 | fortune `references/follow-up-dialogue.md` | 防止 Agent 在追问环节引入新变量污染原盘，与 M3 的应验登记直接互补——登记的证据必须是原盘占时结论，不是被追问改写过的 | 并入 M3：`outcome` 登记时校验 `checked_at` 之后的追加不得修改原 `verdict`；追问规范写入 `AGENTS.md` |
| **确定性敏感分流**：关键词 → 类别 → 固定话术，医疗/生死/失踪/胎儿性别/押上身家直接停止排盘，urgent 分级 | fortune `scripts/classify_sensitive.py` | 三个项目里唯一落地的安全闸，纯函数、零依赖、返回结构化决策。v5 完全没有这层 | 新增 M10（P2）：`start` 前跑同款分类器，命中即拒答并给话术 |
| **领域检查清单 JSON 化**：每领域 `focus`（检查项列表）+ `instruction`（分析顺序），且 `_metadata` 声明「提醒分析顺序用，不替代排盘事实或最终判断」 | fortune `references/domain-methods.json` | 两点可抄：① 检查项做成清单让 Agent 逐项过，不靠记忆；② **反直觉禁令**写得极好——「不把官鬼爻数直接等同现实机会数」「兄弟出现不自动等于破财，必须结合是否实际作用到财爻」 | 新增 M11（P2）：给 `synthesis` 的 `focus` 产物加 `checklist`（程序按 `focus.domain` 出预置清单，Agent 逐项标注 `checked`/`not_applicable`）；禁令类条目并入 M6 自查 |
| **应期组织框架**：「先看用神缺什么、等什么」——缺气等值日、被合等冲日、空等待出旬；再按近（日）/中（月）/远（年）分档，「动则速静则迟、六冲主快六合主慢」 | liuyao-master `references/09-应期.md` | M1 的多通道解决「几条通道怎么合」，这个框架解决「先想什么再查表」的思维顺序。作为 `jingfang-05-timing` 开篇的组织原则，与多通道结构互补 | 并入 M1：改 timing SKILL 时把「缺什么等什么」写成第一节，通道表作为其展开 |
| **权重声明模式**：「六爻纳甲断法以用神旺衰生克为本，卦辞判辞为意象参考，不可只凭卦辞判辞定吉凶」+「世爻位置与六冲六合一律以引擎排盘为准」 | divination-main `references/11-六十四卦判辞.md` | 给佐证材料定认识论地位的现成措辞。M7 取象层和爻辞佐证都需要这种显式声明，防止低权重材料反客为主 | 并入 M7：取象约束第 4 条照此措辞；「与程序复算冲突时以程序为准」写进每个 SKILL 的通用约束 |
| **旺衰与吉凶分离原则**：「旺衰决定有没有力，生克关系决定吉凶方向——二者分开论」 | divination-main `references/03-旺衰月日.md` | 一句话防住「旺就吉、衰就凶」的混淆。M5 力度预判的产物恰好是纯力度，这句可作为 strength/forces 的开篇共识 | 并入 M5：`forces` fact 渲染时附带此说明 |
| **环境自检 + 宁停不猜**：`--selfcheck` 输出 READY/NOT_READY，NOT_READY 时停止排盘，「不得用模型心算替代缺失的历法或排盘引擎」 | fortune `references/runtime-contract.md` | 把「环境不满足时降级为心算」这条最常见的静默失败路径堵死 | 可选（P3）：`jingfang --check` 一键校验数据库快照 + 规则指纹 + 依赖，异常即拒绝开始新解卦 |

### 看过但明确不吸收

| 项 | 来源 | 不抄的理由 |
| --- | --- | --- |
| 硬币正反定义前置展示 | fortune `manual-coin-casting.md` | v5 走指定卦局/时间起卦，无硬币环节；「约定主动展示」的原则已由 M9 覆盖 |
| 节气换月表 | liuyao-master `07-时间因素.md` | v5 排盘由程序按历法计算，无手工换月需求 |
| 基础合冲刑害表 | liuyao-master `05-生克制化.md` | `gua.sql` 已冻结且更全 |
| 六十四卦判辞歌诀全文 | divination-main `11-六十四卦判辞.md` | 只抄它的**权重声明**（见上），判辞本身与野鹤一派「重五行轻卦辞」冲突，引入会稀释主线 |
