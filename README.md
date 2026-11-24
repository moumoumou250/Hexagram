# Jingfang v5

## 项目简介

Jingfang v5 是一个用于解读和复核京房纳甲六爻卦例的本地项目。给定一张卦图或文字排盘和一个具体问题，单 Agent 将盘面转录为 JSON。Python 程序用本次冻结的 SQL 规则核对本卦、世应、动爻和变卦，Agent 再结合所问取用神，按日月旺衰和动变给出判断，按需推应期。

命令行输入至少包含所问问题 `question` 和盘面来源 `source`。每次解读在 `reading-logs/` 保存一份可复核的 Markdown，逐步记录盘面、判断依据和待核项。交付给求测者的 HTML 保存在 `reading-logs/html/`，可直接查看六爻对照和白话结论。各步输入和提交格式见 [AGENTS.md](AGENTS.md)。

## 项目结构

| 位置 | 用途 |
| --- | --- |
| `jingfang/` | 命令行、步骤调度、查表、记录和复核 |
| `skills/` | 认卦至应期的五份规则，以及用户版解读的渲染规则 |
| `gua.sql` | 当前版本的排盘与动变数据 |
| `templates/` | [用户版 HTML](templates/hexagram-view.html)和[分步复核 HTML](templates/step-dump.html)的模板 |
| `reading-logs/` | 本地解卦 Markdown、`html/` 导出文件和 `rule-versions/` 规则快照 |
| [docs/CASES.md](docs/CASES.md) 和 [docs/CHANGES.md](docs/CHANGES.md) | 书例与版本变更 |
| [docs/plans/](docs/plans/) | 排盘准确性与解读页设计方案 |
| `docs/verification/` | 验证报告和百例核对表 |
| `tools/` | 生成排盘 SQL、刷新 HTML 模板预览、生成书例表 |
| `verify/sql/` | SQL 独立复算和性能检查 |
| `verify/workflow/`、`verify/cases/` | 单 Agent 流程、百例核对、书例验证与规则校准 |
| `verify/compat/`、`verify/fixtures/` | 跨版本和外部审计工具，以及验证使用的数据 |

`reading-logs/` 在首次解卦时自动创建。这个目录由 Git 忽略。迁移历史卦例时，请一并复制 Markdown 和对应的 `rule-versions/` 快照，供历史复算和重新导出使用。

## 常用命令

| 操作 | 从根目录运行 |
| --- | --- |
| 新建解读 | `python -X utf8 -m jingfang start 输入.json` |
| 查看当前步骤及其证据 | `python -X utf8 -m jingfang context 解卦编号` |
| 校验历史记录 | `python -X utf8 -m jingfang validate 解卦编号` |
| 校验并生成本次用户版 HTML | `python -X utf8 -m jingfang export 解卦编号 --html` |
| 获取已保存的 Markdown 路径 | `python -X utf8 -m jingfang export 解卦编号` |
| 运行当前项目的回归 | `python -X utf8 verify/run_all.py` |
| 运行流程回归和百例核对 | `python -X utf8 verify/workflow/journal_check.py` |
| 独立复算固定盘及动变 | `python -X utf8 verify/sql/oracle_v3.py` |
| 重建排盘 SQL | `python -X utf8 tools/build_gua_sql.py` |
| 更新默认 HTML 模板中的单卦预览 | `python -X utf8 tools/build_view.py` |
| 核对书例 | `python -X utf8 verify/cases/cases_check.py` |

从模板制作用户版 HTML 的步骤见 [交付约定](AGENTS.md)。手工补存中断记录时使用 `python -X utf8 -m jingfang.save_reading_log`。

回归命令按当前仓库的文件运行。需要留档时加 `--report 路径`。手头有历史资料时可加 `--compat`，其中 v2、v4 SQL 和全书审计目录可分别由 `V2_SQL`、`V4_SQL` 和 `AUDIT_DIR` 指定。SQL 性能测量可单独运行 `python -X utf8 verify/sql/perf_size.py`。

## 解读交付与复核

1. **导出本次解读**。按解卦编号导出 HTML 时，程序先校验记录，再把本次问题、盘面和结论填入默认模板。成品可离线打开，一页展示一份卦例。
2. **浏览器验收**。安装 Node.js 和 `playwright-core` 后，可运行 `node verify/workflow/view_check.cjs "导出的HTML路径" "Chrome可执行文件路径"`，核对问题、本变卦、世应、动爻、主用神和结论。
3. **区分排盘和判断**。固定盘和动变按本次冻结的 SQL 复算。主用神由解读步骤结合所问选定，导出页面按记录还原其来源和位置。动爻未知时显示待核。
4. **定位转录错误**。同位变爻地支提交错误时，提示包含爻位、字段、提交值和复算值。先核对原图；若未汇总记录的输入有误，用 `revise` 更正后从认卦重新执行。
5. **验证排盘**。独立复算覆盖 64 卦 × 64 种动爻组合。百例核对与书例验证用于比对具体案例的动爻、变爻和变卦。
6. **区分个案与通用规则**。单次取用和应期判断保存在本次记录。写入通用 Skill 前，说明成立条件和例外，并用条件变化的卦例复核。详见 [个案与通用规则](AGENTS.md#个案与通用规则)。
