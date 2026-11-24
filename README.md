# Jingfang v5

## 项目简介

Jingfang v5 是一个用于解读和复核京房纳甲六爻卦例的本地项目。给定一张卦图或文字排盘和一个具体问题，单 Agent 将盘面转录为 JSON。Python 程序用本次冻结的 SQL 规则核对本卦、世应、动爻和变卦，Agent 再结合所问取用神，按日月旺衰和动变给出判断，按需推应期。

命令行输入至少包含所问问题 `question` 和盘面来源 `source`。每次解读在 `reading-logs/` 保存一份可复核的 Markdown，逐步记录盘面、判断依据和待核项。交付给求测者的 HTML 保存在 `reading-logs/html/`，可直接查看六爻对照和白话结论。各步输入和提交格式见 [AGENTS.md](AGENTS.md)。

## 项目结构

| 位置 | 用途 |
| --- | --- |
| `jingfang/` | 命令行、步骤调度、查表、记录和复核 |
| `skills/` | 认卦至应期的五份规则，以及用户版解读的渲染规则 |
| `database/gua.sql` | 当前版本的排盘与动变数据 |
| `database/schema.sql` | SQLite 记录查询库的表和视图，字段见 [数据映射](database/现有数据映射.md) |
| `templates/` | [用户版 HTML](templates/hexagram-view.html)和[分步复核 HTML](templates/step-dump.html)的模板 |
| `reading-logs/` | 本地解卦 Markdown（`YYYYMMDD-HHmm_本卦_变卦.md`）、`html/` 导出文件和 `rule-versions/` 规则快照 |
| [docs/plans/](docs/plans/) | 排盘准确性与解读页设计方案 |
| `tools/` | 生成排盘 SQL、刷新 HTML 模板预览、生成书例表 |
| `tests/sql/` | SQL 独立复算和性能检查 |
| `tests/workflow/`、`tests/cases/` | 单 Agent 流程、百例核对、书例验证与规则校准 |
| `tests/compat/`、`tests/fixtures/` | 跨版本和外部审计工具，以及测试使用的数据 |

`reading-logs/` 在首次解卦时自动创建。这个目录由 Git 忽略。迁移历史卦例时，请一并复制 Markdown 和对应的 `rule-versions/` 快照，供历史复算和重新导出使用。

记录文件名由三段组成：起卦分钟的短时间戳、本卦名、变卦名，例如 `20261124-1323_本兑为泽_变雷水解.md`。起卦时若已知卦名即按此命名；只给六画或卦图待辨时先记作 `待认卦`，认卦提交后自动改名为本变卦名，同名 HTML 一并跟随。同一分钟内出现同名卦例时追加 `-2`、`-3`。解卦编号不写在文件名里，命令仍以编号定位记录，改名不影响续跑和导出。

## 常用命令

安装入口（可选）：在项目根执行 `pip install -e .` 后可直接用 `jingfang …`；未安装时仍用 `python -X utf8 -m jingfang …`。运行目录可用 `--log-dir`（写在子命令前或后）或环境变量 `JINGFANG_LOG_DIR`，默认 `reading-logs/`。

| 操作 | 从根目录运行 |
| --- | --- |
| 新建解读 | `python -X utf8 -m jingfang start 输入.json` |
| 列出可续跑卦例 | `python -X utf8 -m jingfang list`（`--json` 出数组；`--state complete` 过滤） |
| 只读回看一卦 | `python -X utf8 -m jingfang show 解卦编号`（与 `dump` 文本一致） |
| 查看当前步骤及其证据 | `python -X utf8 -m jingfang context 解卦编号` |
| 校验历史记录 | `python -X utf8 -m jingfang validate 解卦编号` |
| 校验并生成本次用户版 HTML | `python -X utf8 -m jingfang export 解卦编号 --html` |
| 获取已保存的 Markdown 路径 | `python -X utf8 -m jingfang export 解卦编号` |
| 运行当前项目的回归 | `python -X utf8 tests/run_all.py` |
| 检查历史记录是否可回填 | `python -X utf8 -m jingfang backfill` |
| 回填已通过校验的历史记录 | `python -X utf8 -m jingfang backfill --apply` |
| 单独验证查询库 | `python -X utf8 tests/test_database.py` |
| 运行流程回归和百例核对 | `python -X utf8 tests/workflow/journal_check.py` |
| 独立复算固定盘及动变 | `python -X utf8 tests/sql/oracle_v3.py` |
| 重建排盘 SQL | `python -X utf8 tools/build_gua_sql.py` |
| 更新默认 HTML 模板中的单卦预览 | `python -X utf8 tools/build_view.py` |
| 核对书例 | `python -X utf8 tests/cases/cases_check.py` |

从模板制作用户版 HTML 的步骤见 [交付约定](AGENTS.md)。手工补存中断记录时使用 `python -X utf8 -m jingfang.save_reading_log`。

回归命令按当前仓库的文件运行。需要留档时加 `--report 路径`。手头有历史资料时可加 `--compat`，其中 v2、v4 SQL 和全书审计目录可分别由 `V2_SQL`、`V4_SQL` 和 `AUDIT_DIR` 指定。SQL 性能测量可单独运行 `python -X utf8 tests/sql/perf_size.py`。

## 记录查询库

解卦进度和证据以 `reading-logs/` 的 Markdown 文件为准。认卦通过且月日、动静齐备后，保存记录时会更新同目录下的 `records.sqlite3`。规则库按该卦冻结版本从 `database/gua.sql` 创建并以只读方式挂载。`context` 只返回解卦编号、规则版本、修订号和记录摘要都匹配的查询结果。数据库暂不可用或尚未同步时，继续使用同一份 Markdown 的证据编号和盘面事实。字段与视图对照见 [数据映射](database/现有数据映射.md)。

迁移到另一台机器时，一并保留 Markdown 和 `rule-versions/` 下的对应快照，再运行 `backfill` 检查可导入范围。`--apply` 只写入查询库，可重复运行。命令会列出纯文本归档、缺字段、盘面冲突或规则快照不可用的记录。原 `blackboard.sqlite3` 等旧库由命令列出，便于单独核对。

## 解读交付与复核

1. **导出本次解读**。按解卦编号导出 HTML 时，程序先校验记录，再把本次问题、盘面和结论填入默认模板。成品可离线打开，一页展示一份卦例。
2. **浏览器验收**。安装 Node.js 和 `playwright-core` 后，可运行 `node tests/workflow/view_check.cjs "导出的HTML路径" "Chrome可执行文件路径"`，核对问题、本变卦、世应、动爻、主用神和结论。
3. **区分排盘和判断**。固定盘和动变按本次冻结的 SQL 复算。主用神由解读步骤结合所问选定，导出页面按记录还原其来源和位置。动爻未知时显示待核。
4. **定位转录错误**。同位变爻地支提交错误时，提示包含爻位、字段、提交值和复算值。先核对原图；若未汇总记录的输入有误，用 `revise` 更正后从认卦重新执行。
5. **验证排盘**。独立复算覆盖 64 卦 × 64 种动爻组合。百例核对与书例验证用于比对具体案例的动爻、变爻和变卦。
6. **区分个案与通用规则**。单次取用和应期判断保存在本次记录。写入通用 Skill 前，说明成立条件和例外，并用条件变化的卦例复核。详见 [个案与通用规则](AGENTS.md#个案与通用规则)。
