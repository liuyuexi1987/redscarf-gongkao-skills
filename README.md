# 行测复盘一体版｜公考行测 AI Skill

行测复盘一体版 Skill：支持行测讲题、复盘首轮追问、错因诊断、方法库、题库、考我、复习和复盘引擎。

关键词：行测、公考、公务员考试、国家公务员考试、行测复盘、错题复盘、资料分析、数量关系、判断推理、言语理解、常识判断、AI 学习助手。

许可证：[GNU GPL v3.0（仅限 v3.0）](LICENSE)。再分发或修改本项目时，请保留许可证文本、版权声明和对应源码。

当前发布线：`v1.4.1`。运行时采用“脚本优先、Markdown 降级”：模型负责教学、答案裁决和错因判断；`skills/xingce-review-pro/scripts/writeback.py` 只负责经过确认的结构化状态写入。

## 本地校验

```bash
python tools/validate_skill.py --skill-root skills/xingce-review-pro
python tools/audit_methods.py --skill-root skills/xingce-review-pro
python -m unittest discover -s tests -v
python tools/package_skill.py --version v1.4.1
```

安装包位于 `dist/`，包含可运行 Skill、回写脚本、`LICENSE` 和 `NOTICE`，不包含维护工具、测试和用户运行状态。

本线程只处理行测；申论内容不在本项目范围内。
