# Jingfang v5 解卦与本地记录

在本项目中，每次对具体卦例解卦或重新判断，都要把本次记录写入项目根目录下的 `reading-logs/`。一卦一份 UTF-8 Markdown，同一卦重新判断时新建记录。遇到资料不足、盘面矛盾或查表失败而提前结束，也要保存已完成的步骤和停下的原因。

## 单 Agent 顺序解卦

- 每次向求测者交付解读时，以 `templates/hexagram-view.html` 为默认模板，运行 `python -X utf8 -m jingfang export <解卦编号> --html` 生成到 `reading-logs/html/`，与该次 Markdown 同名、扩展名为 `.html`。保留原版布局、排盘控件、世应标记、六爻对照和判断依据区。把默认载入和重载示例都设为本次卦，依据已校验的记录填入问题、日月、动爻、主用神和白话结论。资料不足时显示已确认内容和待核项。交付前打开成品核对，答复优先链接用户版 HTML，Markdown 留作本地复核。

- 由当前主会话执行全部步骤。从项目根目录运行 `python -X utf8 -m jingfang start <输入.json>`，取得解卦编号和 Markdown 路径，记录此时已经创建。输入至少含 `question`（所问问题）和 `source`（原图来源或文字转录来源）。已知时可填写 `base_name`、`line_code`、`moving_positions`、`changed_name`、`changed_code`、`month_branch`、`day_ganzhi`、`day_branch`、`cast_time`、`timezone`。明确静卦用空数组，动爻未知时省略该字段。按所问设置 `ask_timing`，有明确比较对象才填 `comparison_targets`。
- 严格按照 **认卦查 SQL → 取用神 → 看日月、世应和世用 → 看动变 → 按需看应期 → 汇总答复** 顺序执行。对应步骤名为 `identify`、`focus`、`strength`、`change`、`timing`、`synthesis`。用 `next <解卦编号>` 查下一步，`context <解卦编号>` 取当步冻结版 Skill 路径和上游证据，实际处理后用 `submit <解卦编号> <步骤> <结果.json>` 提交。输入文件和结果文件也可用 `-` 从标准输入读取。
- 每步提交会重新生成并原子替换同一份 UTF-8 Markdown，只有校验和写入成功后才进入下一步。用 `status <解卦编号>` 查看已保存状态，中断后用同一编号继续。复算冲突写入 `identify` 并停止。其他缺项用 `partial` 记下可确认内容和待核项。汇总时根据当步 `context` 提示复核用神取舍、冲合与动变例外。
- 卦图清晰时，可用 `source_void` 记录图上两个旬空地支，用 `source_lines` 转录各爻。每项必填 `position`，按图选择填写 `stem_branch`、`relative`、`marker`、`hidden`、`spirit`、`moving`、`changed_stem_branch` 和 `changed_relative`。变爻干支与六亲只填明动爻。
- 固定盘、动变及其他可查表规则取自该次冻结的 `gua.sql`。未汇总的记录可用 `revise <解卦编号> <更正后的完整输入.json> <原因>` 更正输入，原日志保留更正历史并从认卦重走。已汇总的卦例如需重新判断，用 `start` 创建新记录。旧卦例可直接查阅历史 Markdown。

### 步骤提交约定

- `state` 填 `accepted`、`partial` 或 `blocked`。部分完成和中断填写 `reason`。五个 Skill 步骤的 `skill_use` 填 `applied`、`read` 或 `unavailable`，按实际情况记录。若 `timing` 的上下文给出 `skip_reason`，提交 `{"state":"skipped"}`，程序保存跳过原因后进入汇总。
- `identify` 可提交 `chart`，填写从原图辨认的盘面字段，系统随后独立复算并写入事实。 `focus` 提交所选六亲及主用神，例如 `"focus":{"relative":"官鬼","primary":{"source":"base","position":4}}`。伏神、变爻、月建、日辰分别用 `hidden`、`changed`、`month`、`day`，日月的 `position` 用 `null`。候选待定可提交 `partial`。
- `entries` 中每条判断填写 `kind: "judgment"`、`summary`、`rule`、`section`（Skill 的真实标题）、`condition`、`refs`（上下文条目编号数组）。另以 `exceptions` 记录影响结论的例外。汇总判断同时填写对应的 `skill` 步骤名。缺项或待定结论用 `kind: "pending"`。认卦可省略 `refs`，程序关联本步查表证据。
- 旬空用 `topic: "day_void"`，另填两个旬空地支 `branches`。六神用 `"six_spirits"`，另填 `position` 和 `spirit`。每个明动爻各写一条 `"moving_line"`，另填 `position` 和同位变爻地支 `changed_branch`。汇总结论用 `topic: "conclusion"`，引用已完成的旺衰、动变和应期判断。排序判断用 `"comparison"` 并填 `compared_targets`。判断须依据引用的事实说明取舍。

## 记录内容

每次记录按下列小节书写。对缺失、跳过或无法核实的内容说明原因。

1. **输入与状态**。记下所问问题、盘面来源、起卦时间和时区（如已提供）、月建、日辰，以及本次是完整解卦还是部分完成。只记与解卦有关的输入。
2. **Skill 使用记录**。按实际顺序列出步骤、Skill 名称及相对路径、执行状态、使用的规则小节、实际查询的表或视图、关键参数和结果。区分已读取、已应用、跳过和中断。跳过的步骤写明原因。
3. **排盘核对**。记录本卦、世应、动爻位次和 `move_mask`，以及据此推出的变卦。图上有变卦时记录核对结果，保留冲突项和待核项。
4. **判断依据**。记录用神候选及取舍、世应及世用关系、日月与旺衰、旬空与冲合、动爻及同位变爻的作用。若用了六神或推了应期，记录实际使用的规则、涉及的爻和对判断的影响。逐条给出相关的盘面数据、按项目规则得到的中间结果和判断摘要，标明条件和不确定项。
5. **结论**。写明对原问题的判断及成立条件。若提前结束，写明最后完成的步骤和还缺的信息。

答复用户前运行 `python -X utf8 -m jingfang validate <解卦编号>` 和 `python -X utf8 -m jingfang export <解卦编号>`，核对返回路径与记录内容，并附上本地链接。中断时也执行导出。若续跑状态无法恢复，可用 `python -X utf8 -m jingfang.save_reading_log <临时Markdown路径>` 保存已经确认的部分并记录故障。

## 个案与通用规则

单次取用、旺衰或应期的判断保存在本次记录。将经验写入通用 Skill 时，说明适用条件、例外，并用条件成立与条件变化的卦例核对结论。
