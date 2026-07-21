# gongkao-review-pro

行测复盘一体版 Skill：支持行测讲题、复盘首轮追问、错因诊断、方法库、题库、考我、复习和复盘引擎。

当前发布线：`v1.4.0`。运行时采用“脚本优先、Markdown 降级”：模型负责教学、答案裁决和错因判断；`skills/gongkao-review-pro/scripts/writeback.py` 只负责经过确认的结构化状态写入。

## 本地校验

```bash
python tools/validate_skill.py --skill-root skills/gongkao-review-pro
python tools/audit_methods.py --skill-root skills/gongkao-review-pro
python -m unittest discover -s tests -v
python tools/package_skill.py --version v1.4.0
```

安装包位于 `dist/`，包含可运行 Skill 和回写脚本，不包含维护工具、测试和用户运行状态。

本线程只处理行测；申论内容不在本项目范围内。
