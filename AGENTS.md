# Jingfang v5 解卦与本地记录

在本项目中，每次对具体卦例解卦或重新判断，都要把本次记录写入项目根目录下的 `reading-logs/`。一卦一份 UTF-8 Markdown，同一卦重新判断时新建记录。遇到资料不足、盘面矛盾或查表失败而提前结束，也要保存已完成的步骤和停下的原因。

## 起卦前

问题须能识别**核心事项**与**所求结果**，两项缺一先问一句、不起卦；一次多问取优先。代码侧：`question` 去掉标点后少于 6 字会拒绝。

## 单 Agent 顺序解卦

- 每次向求测者交付解读时，以 `templates/hexagram-view.html` 为默认模板，运行 `python -X utf8 -m jingfang export <解卦编号> --html` 生成到 `reading-logs/html/`，与该次 Markdown 同名、扩展名为 `.html`。页面可离线直接查看，只展示本次卦例。保留世应标记、六爻对照和判断依据区，依照已校验的记录填入问题、日月、动爻、主用神和白话结论。资料不足时显示已确认内容和待核项。交付前打开成品核对，答复优先链接用户版 HTML，Markdown 留作本地复核。

- 由当前主会话执行全部步骤。从项目根目录运行 `python -X utf8 -m jingfang start <输入.json>`，取得解卦编号和 Markdown 路径，记录此时已经创建。文件名以起卦分钟的短时间戳加本卦、变卦命名（如 `20261124-1323_本兑为泽_变雷水解.md`）；输入未给卦名时先记作 `待认卦`，认卦提交后自动改名。输入至少含 `question`（所问问题）和 `source`（原图来源或文字转录来源）。已知时可填写 `base_name`、`line_code`、`moving_positions`、`changed_name`、`changed_code`、`month_branch`、`day_ganzhi`、`day_branch`、`cast_time`、`timezone`。明确静卦用空数组，动爻未知时省略该字段。按所问设置 `ask_timing`，有明确比较对象才填 `comparison_targets`。
- 严格按照 **认卦查 SQL → 取用神 → 看日月、世应和世用 → 看动变 → 按需看应期 → 汇总答复** 顺序执行。对应步骤名为 `identify`、`focus`、`strength`、`change`、`timing`、`synthesis`。用 `next <解卦编号>` 查下一步，`context <解卦编号>` 取当步冻结版 Skill 路径和上游证据，实际处理后用 `submit <解卦编号> <步骤> <结果.json>` 提交。输入文件和结果文件也可用 `-` 从标准输入读取。
- 每步提交会重新生成并原子替换同一份 UTF-8 Markdown，只有校验和写入成功后才进入下一步。用 `status <解卦编号>` 查看已保存状态，中断后用同一编号继续。复算冲突写入 `identify` 并停止。其他缺项用 `partial` 记下可确认内容和待核项。汇总时根据当步 `context` 提示复核用神取舍、冲合与动变例外。
- `context.database` 可用于交叉核对本卦的查询结果。为 `null` 时，使用 `context.entries` 的证据；提交引用仍填其中的条目编号。只在规则和盘面足以定性时填写判断条目的可选 `record_judgment`，字段见 [数据映射](database/现有数据映射.md)。
- 卦图清晰时，可用 `source_void` 记录图上两个旬空地支，用 `source_lines` 转录各爻。每项必填 `position`，按图选择填写 `stem_branch`、`relative`、`marker`、`hidden`、`spirit`、`moving`、`changed_stem_branch` 和 `changed_relative`。变爻干支与六亲只填明动爻。
- 固定盘、动变及其他可查表规则取自该次冻结的 `gua.sql`（新记录从 `database/gua.sql` 创建快照）。未汇总的记录可用 `revise <解卦编号> <更正后的完整输入.json> <原因>` 更正输入，原日志保留更正历史并从认卦重走。已汇总的卦例如需重新判断，用 `start` 创建新记录。旧卦例可直接查阅历史 Markdown。

### 步骤提交约定

- `state` 填 `accepted`、`partial` 或 `blocked`。部分完成和中断填写 `reason`。五个 Skill 步骤的 `skill_use` 填 `applied`、`read` 或 `unavailable`，按实际情况记录。若 `timing` 的上下文给出 `skip_reason`，提交 `{"state":"skipped"}`，程序保存跳过原因后进入汇总。
- `identify` 可提交 `chart`，填写从原图辨认的盘面字段，系统随后独立复算并写入事实。 `focus` 提交所选六亲及主用神，例如 `"focus":{"relative":"官鬼","primary":{"source":"base","position":4}}`。伏神、变爻、月建、日辰分别用 `hidden`、`changed`、`month`、`day`，日月的 `position` 用 `null`。候选待定可提交 `partial`。
- `entries` 中每条判断填写 `kind: "judgment"`、`summary`、`rule`、`section`（Skill 的真实标题）、`condition`、`refs`（上下文条目编号数组）。另以 `exceptions` 记录影响结论的例外。汇总判断同时填写对应的 `skill` 步骤名。缺项或待定结论用 `kind: "pending"`。认卦可省略 `refs`，程序关联本步查表证据。
- 旬空用 `topic: "day_void"`，另填两个旬空地支 `branches`。六神用 `"six_spirits"`，另填 `position` 和 `spirit`。每个明动爻各写一条 `"moving_line"`，另填 `position` 和同位变爻地支 `changed_branch`。应期通道用 `topic: "window"`，另填 `branch`、`unit`（日/月/年）、`channel`（值/合/冲/填实/冲墓/当令/克神受克/化出之支值）；询问应期且 accepted 时至少一条。汇总结论用 `topic: "conclusion"`，引用已完成的旺衰、动变和应期判断。排序判断用 `"comparison"` 并填 `compared_targets`。判断须依据引用的事实说明取舍。
- 汇总 `accepted` 时须提交顶层 `verdict`：`direction`（favorable/unfavorable/mixed）、非空 `layers`（每层 `name`/`condition`/`status`/`refs`，refs 指向已有判断）、`falsifier`（10–120 字证伪条件）。取象用 `topic: "image"`（仅 synthesis），`skill` 填既有 Skill 名，`elements` 至少两项。
- 应验登记：`python -X utf8 -m jingfang outcome <解卦编号> <应验.json>`，仅已汇总记录可追加；层名最好对应占时 `verdict.layers`，否则渲染为事后补充（弱证据）。

### 解读范围（防误导）

交付给求测者的 HTML / 白话区**只分析用神**（及直接相关的原神、忌神、世应结构），**不解读所问具体事情的结局**。  
可以说「用神无根、原神有力也难生」；不说「这次求职失败 / 会复合 / 会痊愈」。  
`question` 只用于取用神与核对范围；`verdict` / `summary` / `image` 的主语也应落在用神状态，不写事项剧本。

解读渲染层在 `skills/jingfang-06-interpretation/`（**不是**解卦第六步，不进规则指纹）。汇总时可选交 `rules_fired`；不交则导出时按盘面现算。页面顺序：先「用神盘面要点」，后「用神判断摘要」。

### 交付前核对解读块

1. 先读「用神盘面要点」：是否人话（EL15）、主语是否用神侧。  
2. 再读「用神判断摘要」：有无事项结局句（升职/复合/病愈等）——有则改掉再导出。  
3. 应期只应出现通道与置信度，不应出现「某日事必发生」。  
4. 打开成品 HTML 扫一眼免责声明是否仍写明「不对所问事情作结果预言」。

### 取象约束

1. 象只取盘面已有要素（五行、爻位、世应、六神、卦名、进退神），不引入神煞。
2. 象核无吉凶，随域翻转——化进在求财是增益、在疾病是转重；不得由象反推五行结论；**更不得由象写成所问之事的故事结局**。
3. 多象同向方可定性，孤象不入结论；六神只作形容词，不改吉凶。

## 记录内容

每次记录按下列小节书写。对缺失、跳过或无法核实的内容说明原因。

1. **输入与状态**。记下所问问题、盘面来源、起卦时间和时区（如已提供）、月建、日辰，以及本次是完整解卦还是部分完成。只记与解卦有关的输入。
2. **Skill 使用记录**。按实际顺序列出步骤、Skill 名称及相对路径、执行状态、使用的规则小节、实际查询的表或视图、关键参数和结果。区分已读取、已应用、跳过和中断。跳过的步骤写明原因。
3. **排盘核对**。记录本卦、世应、动爻位次和 `move_mask`，以及据此推出的变卦。图上有变卦时记录核对结果，保留冲突项和待核项。
4. **判断依据**。记录用神候选及取舍、世应及世用关系、日月与旺衰、旬空与冲合、动爻及同位变爻的作用。若用了六神或推了应期，记录实际使用的规则、涉及的爻和对判断的影响。逐条给出相关的盘面数据、按项目规则得到的中间结果和判断摘要，标明条件和不确定项。
5. **结论**。写明对原问题的判断及成立条件；含分层表与证伪条件。若提前结束，写明最后完成的步骤和还缺的信息。
6. **应验与复盘**（若已 `outcome`）。核对日期、各层实际与证据强度。

答复用户前运行 `python -X utf8 -m jingfang validate <解卦编号>` 和 `python -X utf8 -m jingfang export <解卦编号>`，核对返回路径与记录内容，并附上本地链接。交付用户版时再 `export --html`；若摘要盘面断言冲突，先修正或显式 `--allow-claims`。中断时也执行导出。若续跑状态无法恢复，可用 `python -X utf8 -m jingfang.save_reading_log <临时Markdown路径>` 保存已经确认的部分并记录故障。

准确性校准材料（不阻断解卦）：调规则前运行 `python -X utf8 tests/workflow/forces_check.py` 与 `window_check.py`，输出会写入 `docs/verification/`（元忌力度对照、应期窗口回放清单），按需重新生成。

## 个案与通用规则

单次取用、旺衰或应期的判断保存在本次记录。将经验写入通用 Skill 时，说明适用条件、例外，并用条件成立与条件变化的卦例核对结论。
