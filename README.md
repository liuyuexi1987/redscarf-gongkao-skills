# 红领巾考公复盘 Skills

一组可独立安装的 Claude Code / Claudian skills，用来做公考题目复盘、方法调用和错因诊断。

仓库内不包含原始 Obsidian vault，也不依赖 `网友红领巾/` 之类的原始语料目录。每个 skill 都自带 `SKILL.md` 和 `references/`，可以单独使用。

## 包含内容

- `redscarf-method-router`
- `redscarf`
- `redscarf-verbal`
- `redscarf-cloze`
- `redscarf-data`
- `redscarf-quant`
- `redscarf-judgement`
- `redscarf-error-diagnosis`

这些目录都位于 `skills/`。

## 安装

给智能体的一句话安装提示词：

```text
安装这个仓库里的整套 redscarf-* skills，包括 redscarf、redscarf-method-router、redscarf-verbal、redscarf-cloze、redscarf-data、redscarf-quant、redscarf-judgement、redscarf-error-diagnosis，只安装这些技能本体，不要把整个仓库当项目内容引入：https://github.com/liuyuexi1987/redscarf-gongkao-skills
```

## 使用

示例问法：

- `用红领巾方法诊断我这道言语错题`
- `这道逻辑填空为什么不能选 A`
- `资料分析增长率怎么按红领巾方法速算`
- `把这道错题整理成错因卡`

各 skill 的职责：

- `redscarf`：总路由，记不住细分 skill 时直接用它
- `redscarf-method-router`：全局规则、数据字典、跨库定位
- `redscarf-verbal`：阅读理解/言语理解
- `redscarf-cloze`：逻辑填空/选词填空
- `redscarf-data`：资料分析
- `redscarf-quant`：数量关系
- `redscarf-judgement`：判断推理
- `redscarf-error-diagnosis`：错因诊断与错因卡

## 设计原则

- 这是“讲解驱动”的方法库，不是完整 OCR 题库。
- OCR 只作辅助，不作题面真值。
- `source_quote` 是证据；引用方法时优先给 `source_quote` 和 `unit_id`。
- ASR 来源默认待核。
- 不补全缺失题面，不把公考通用常识包装成红领巾原方法。

## 仓库说明

当前仓库只整理 skills 本体，适合独立发布和复用。
仓库已经包含 `MIT` 许可证，可直接开源分发和复用。
