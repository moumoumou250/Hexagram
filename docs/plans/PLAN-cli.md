# Jingfang v5 CLI 化方案

本方案盘点项目内全部可执行入口，判断哪些适合做成命令行、哪些不该做，并给出分批实施顺序。
原则：**只加命令，不加解卦步骤**；旧调用路径全部保留可用。

## 一、现状盘点

### 1. 已经是 CLI 的部分

`jingfang/__main__.py`（97 行）是项目唯一规范化入口，11 个子命令，输出单行 JSON：

`start` · `next` · `status` · `context` · `submit` · `revise` · `outcome` · `validate` · `export` · `dump` · `backfill`

它已经承担了「解卦状态机」的全部机器接口，AGENTS.md 的操作约定就建立在这套命令上。**这部分不需要重做，只需要补缺。**

现存缺口：

| 缺口 | 表现 | 影响 |
| --- | --- | --- |
| 无安装入口 | 只能 `python -X utf8 -m jingfang` | 换机器、换目录都要先 cd 到项目根 |
| 无列表命令 | 想知道跑过哪几卦只能 `ls reading-logs`，编号靠翻 Markdown | 最高频的日常动作没有接口 |
| 无单卦人读视图 | `dump` 语义是「审计产物」，不是「给我看这卦」 | 想快速回看必须开 HTML |
| 输出只有 JSON | 无 `--format`、无 `--quiet` | 人读要自己拿管道接 `jq` |
| `--log-dir` 只能写在子命令之前 | `start x.json --log-dir y` 直接报错 | 高频踩坑 |
| 无 `--version` | 无版本概念，规则指纹也不暴露 | 排查「哪版规则跑的」不方便 |
| `save_reading_log` 是独立模块 | 走 `python -m jingfang.save_reading_log` | 中断救场时命令不一致 |

### 2. 半 CLI：有参数，但没有统一形态

| 入口 | 现参数 | 问题 |
| --- | --- | --- |
| `verify/run_all.py` | `--compat` `--report` | 只会 subprocess 拼字符串；无结构化结果；失败项只能从文本里数 |
| `tools/build_gua_sql.py` | `--check` | 参数设计已够用，只是不在统一入口下 |
| `verify/workflow/view_check.cjs` | 位置参数 `<html> [chrome]` | 无 `--json`；依赖 playwright-core，缺依赖时直接抛异常 |

### 3. 纯脚本：零参数、硬编码路径

`verify/` 下共 19 个 `.py`（其中 3 个是 `runpy` 兼容壳：`verify/oracle_v3.py`、`verify/build_gua_sql.py`、`verify/workflow/blackboard_check.py`）+ 1 个 `.cjs`。
**只有 2 个用了 argparse**（`run_all.py`、`build_gua_sql.py`），其余 17 个一律零参数：

- `verify/sql/`：`oracle_v3.py`（独立复算 64×64）、`perf_size.py`
- `verify/cases/`：`cases_check.py`、`skill_walkthrough.py`
- `verify/workflow/`：`journal_check.py`、`audit_check.py`、`dump_check.py`、`forces_unit_check.py`、`interpretation_check.py`、`forces_check.py`、`window_check.py`
- `verify/compat/`：`compat_v2.py`、`diff_v4.py`、`audit_regress.py`
- `tools/`：`build_view.py`（无参，直接改写 `templates/hexagram-view.html`）、`make_cases_md.py`（打印 Markdown 到 stdout）
- `database/test.py`（unittest，无参）

具体毛病：

1. **输出路径硬编码**。`forces_check.py` 写死 `docs/verification/forces-baseline.json` 与 `forces-conflicts.md`；`window_check.py` 写死 `window-replay.md`。想输出到别处只能改代码。
2. **外部路径靠环境变量**。`compat_v2.py` 读 `V2_SQL`、`diff_v4.py` 读 `V4_SQL`、`audit_regress.py` 读 `AUDIT_DIR`，且默认值指向 `../../../Jingfang-v2` 这类同级目录。无法在命令行里指定。
3. **import 即执行**。`oracle_v3.py`、`compat_v2.py`、`make_cases_md.py`、`cases_check.py` 都在模块顶层跑 SQL、`sys.exit()`。收进统一入口前必须先 `main()` 化，否则 `import` 就会跑全库。
4. **静默跳过**。`audit_regress.py` 在 `audit-v3` 不存在时 `print + sys.exit(0)`，与「通过」无法区分。
5. **返回码语义不统一**。有的 `sys.exit(1 if fails else 0)`，有的 unittest 默认，有的永远 0（`perf_size.py` 只测速不判定）。

## 二、不该做成 CLI 的部分（防过度工程）

| 环节 | 为什么不做 |
| --- | --- |
| 看图认卦 | 视觉识别由 Agent 完成，`submit identify` + `chart` 字段已是唯一机器接口，再包一层只是空壳 |
| 取用神、旺衰、动变、应期判断 | 属判断层，程序只做校验（`review.normalize_entries`）。做成 CLI 会诱导「一键出结论」，与项目「只分析用神、不预言事项结局」的边界冲突 |
| 解读文字生成 | 渲染规则在 `skills/jingfang-06-interpretation/`，产出由 `export --html` 承担，无需新命令 |
| 新增解卦步骤 | `Orchestrator._load` 用 `set(steps) != set(STEPS)` 校验，新增步骤会让 `reading-logs/` 下所有历史记录报「步骤状态无效」。任何 CLI 改造**不得**引入第六步 |

## 三、目标形态

保留现有 11 个平铺子命令（它们是 AGENTS.md 的契约，不改名），新增三个分组承载「非解卦」的杂务：

```
# 解卦域：保持现状 + 新增 2 个
jingfang start | next | status | context | submit | revise | outcome | validate | export | dump | backfill
jingfang list   [--state running|partial|complete] [--json]      # 新增
jingfang show   <id> [--step S] [--html] [--json]                # 新增

# 验证域：把 14 个分散脚本收成一个入口
jingfang verify [all|records|board|cases|workflow|forces|window|audit|dump|interpret]
                [--json] [--report PATH] [--strict] [--compat]

# 数据与模板
jingfang db       build [--check] | oracle | perf | test
jingfang template refresh
jingfang cases    md
jingfang view-check <html> [--chrome PATH] [--json]

# 运维
jingfang doctor          # 环境自检：Python/utf8/sqlite/node/目录可写/gua.sql 与生成一致
jingfang salvage <md>    # 收编 jingfang.save_reading_log
```

命名取舍：`verify` 而不叫 `test`（项目里 `database/test.py` 已有专名）；`db` 而不是 `sql`（`verify/sql/` 是复算，语义不同）。

## 四、变更清单

| 编号 | 事项 | 优先级 | 涉及文件 | 规模 |
| --- | --- | --- | --- | --- |
| C1 | `pyproject.toml` + `console_scripts`，`jingfang` 直接可用 | P0 | 新建 `pyproject.toml` | 小 |
| C2 | `list` / `show` 两个只读子命令 | P0 | `__main__.py`、`orchestrator.py`（新增只读方法） | 中 |
| C3 | 统一 `--format json\|text`、`--quiet`、`--version`、退出码语义 | P0 | `__main__.py` | 小 |
| C4 | `--log-dir` 提到 `parents=[common]`，并支持 `JINGFANG_LOG_DIR` | P0 | `__main__.py` | 小 |
| C5 | `jingfang verify` 分发器；17 个脚本 `main(argv)->int` 化 | P1 | 新建 `jingfang/verify.py`，改造 `verify/**` | 大 |
| C6 | `forces_check` / `window_check` 的 `--out` 参数化 | P1 | 两个 check 脚本 | 小 |
| C7 | `compat` 三脚本的 `--v2-sql/--v4-sql/--audit-dir`（env 降为默认值） | P1 | `verify/compat/*` | 小 |
| C8 | `db build\|oracle\|perf\|test`、`template refresh`、`cases md`、`view-check` | P2 | `__main__.py`、`tools/*` | 中 |
| C9 | `doctor`、`salvage`、shell 补全（`argcomplete` 可选依赖） | P3 | `__main__.py` | 小 |

## 五、分批实施

### Batch 1（P0，纯新增，不动 AGENTS.md）

1. `pyproject.toml`：`[project.scripts] jingfang = "jingfang.__main__:main"`，`requires-python >= 3.11`，无第三方依赖。
2. `main()` 开头 `sys.stdout.reconfigure(encoding="utf-8")`，让 Windows 控制台不再必须加 `-X utf8`（保留 `-X utf8` 也不会坏）。
3. `list`：扫 `reading-logs/*.md`，复用 `Journal.read` + `_status`，输出 `编号 / 状态 / 本卦→变卦 / 起卦时间 / 下一步`。**必须走只读路径**，不调用 `records.sync`。
4. `show`：复用 `dump.build_dump` 的渲染，默认 `text`，`--html` 走 `dump_html`，`--json` 原样吐结构。
5. 退出码：`0` 成功 / `1` 校验或断言失败 / `2` 用法错误 / `3` 记录不存在 / `4` 跳过（仅 `--strict` 时升为 `1`）。

验收：`jingfang list` 能列出 `20261124-1323_本兑为泽_变雷水解`；`jingfang show <id>` 与 `dump` 文本一致；`jingfang start` 用旧写法仍然通过；`python -X utf8 verify/run_all.py` 仍 10 项全过。

### Batch 2（P1，验证域收敛）

1. 新建 `jingfang/verify.py`：`CHECKS` 注册表（名称 → 模块路径 → 默认参数），逐项 `subprocess` 跑或直接调 `main()`，汇总为 `{name, status, exit, summary, log}`。
2. 17 个脚本统一成 `def main(argv=None) -> int` + `if __name__ == "__main__": raise SystemExit(main())`。unittest 类用 `unittest.main(argv=[...], exit=False)` 后返回 `0 if result.wasSuccessful() else 1`。
3. `verify/run_all.py` 降级为 `jingfang verify all` 的薄包装，**文件保留**（README 与 AGENTS.md 都引用它）。
4. `--json` 输出机读汇总，`--report PATH` 落盘（沿用 `run_all` 现有格式），`--strict` 把 skipped 视为失败。

验收：`jingfang verify --json` 各项状态与 `run_all.py` 逐项 exit code 一致；`verify/compat/*` 在无外部目录时报 `skipped` 而非 `ok`。

### Batch 3（P2，工具与数据）

1. `jingfang db build` 转发 `tools/build_gua_sql.py`（保留 `--check`）；`db oracle` / `db perf` / `db test` 对应 `verify/sql/oracle_v3.py`、`perf_size.py`、`database/test.py`。
2. `template refresh` 转发 `tools/build_view.py`；`cases md` 转发 `make_cases_md.py`。
3. `view-check`：`shutil.which("node")` 缺失时返回 `skipped` 并在 JSON 说明原因，不要抛栈。

验收：`jingfang db build --check` 与直接跑脚本结果一致；改 `tools/build_view.py` 后 `templates/hexagram-view.html` 无差异。

### Batch 4（P3，体验）

`doctor`（Python 版本、stdout 编码、sqlite3 版本、node/playwright-core、`reading-logs/` 可写、`gua.sql` 与 `build_gua_sql --check` 一致、`rule-versions/` 快照完整）；`salvage`；`argcomplete` 可选补全。

## 六、约束与风险

| 约束 | 后果 | 应对 |
| --- | --- | --- |
| `_load` 严格校验 `set(steps)` | 新增步骤 → 全部历史记录报错 | CLI 只加命令，不加 step |
| `report.validate` 严格回放盘面 | `list`/`show` 若触发 `_save` 会写记录库并可能报错 | 两个命令只读，不碰 `journal.save` / `records.sync` |
| 多个 verify 脚本 import 即执行 | 收进 `jingfang.verify` 后一 import 就跑全库 | 先 `main()` 化再接入；接入顺序按 Batch 2 |
| `freeze_rules` 把快照写进 `--log-dir/rule-versions/` | `--log-dir` 写错会把规则快照散到别处 | 环境变量只读不覆盖显式参数；`doctor` 检查目录归属 |
| Windows 控制台默认 GBK | 中文 JSON 打印崩 | `reconfigure(encoding="utf-8")`，保留 `-X utf8` 兼容 |
| `view_check.cjs` 依赖 node + playwright-core | CI 无依赖时误报失败 | 明确 `skipped`，`--strict` 才计失败 |
| AGENTS.md 是 Agent 契约 | 命令改名会让文档与历史习惯脱节 | 11 个平铺命令不改名；新增命令另写一节，Batch 1 完成后同步 README 常用命令表 |

## 七、完成标准

1. `pip install -e .` 后 `jingfang <TAB>` 能看到全部分组，`jingfang --help` 覆盖所有子命令。
2. 旧命令 `python -X utf8 -m jingfang <cmd>` 全部保持可用，AGENTS.md 无需改动词汇。
3. `jingfang verify` 与 `verify/run_all.py` 结果逐项一致，退出码一致。
4. `jingfang list` / `show` 对 `reading-logs/` 无任何写入（可用文件 mtime 前后比对验收）。
5. `docs/verification/` 下两份产物可由 `--out` 指到任意路径。
