---
name: redscarf-method-router
description: Use when the user asks about 红领巾、公考复盘、方法库、考公做题策略、题型方法、错因诊断, or wants to search/reuse the generated redscarf method corpus inside this Obsidian vault.
---

# 红领巾方法库路由 Skill

这个 Skill 是红领巾公考复盘语料库的入口。它负责全局规则、数据字典查询和语料库定位，不承担学科分发。

## 工作目录

Claudian 会把 Obsidian vault 作为工作目录。本项目资料已安装在：

- 技能目录：`.claude/skills/redscarf-*`
- 人类可读入口：`红领巾方法库/入口.md`
- 原始转写稿：`网友红领巾/`

## 触发后先做什么

1. 先读 `references/红领巾方法库入口.md`，只取与问题相关的部分。
2. 用户问字段、文件结构、产物含义、JSONL schema 时，再读 `references/产物数据字典.md`。
3. 不要默认读取大型 JSONL。需要证据时优先用 `rg` 搜 `红领巾方法库/` 或专题 `references/`。

## 回答原则

- 这是“讲解驱动”的方法库，不是完整 OCR 题库。
- OCR 只作辅助，不作题面真值。
- `source_quote` 是证据；引用方法时优先给 `source_quote`、`unit_id`、原始文件名。
- 遇到 ASR 来源，要提醒“ASR 待核”或“据 ASR 讲解，术语/数字待核”。
- 不补全缺失题面，不把公考通用常识包装成红领巾方法。

## 输出模板

1. 查询目标：<用户要找的方法/字段/索引/证据>
2. 应读资料：<入口/数据字典/具体 reference>
3. 全局约束：OCR 只辅助；`source_quote` 是证据；ASR 待核；不补题面
4. 可回看位置：<文件路径、`unit_id` 或 `source_quote`>
5. 下一步建议：<继续查证/转为错因卡/交给对应专题 skill>

## 常用问法

- “红领巾这套方法怎么判断结语题？”
- “我资料分析增长率老错，用红领巾方法诊断一下。”
- “从库里找偷换概念/想太多的例子。”
- “按我的错题生成一张错因复盘卡。”
