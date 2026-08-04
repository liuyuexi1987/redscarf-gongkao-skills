import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MaintenanceToolTests(unittest.TestCase):
    def run_tool(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / name), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_validate_and_audit_pass(self) -> None:
        validated = self.run_tool("validate_skill.py", "--skill-root", "skills/xingce-review-pro")
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        audited = self.run_tool("audit_methods.py", "--skill-root", "skills/xingce-review-pro")
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)

    def test_skill_behavior_contract_is_present(self) -> None:
        skill = (ROOT / "skills/xingce-review-pro/SKILL.md").read_text(encoding="utf-8")
        engine = (ROOT / "skills/xingce-review-pro/references/review-engine/复盘引擎说明.md").read_text(
            encoding="utf-8"
        )
        data = (ROOT / "skills/xingce-review-pro/references/protocols/data.md").read_text(
            encoding="utf-8"
        )
        writeback_runtime = (
            ROOT / "skills/xingce-review-pro/references/review-engine/写回运行协议.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("display_name:", skill)
        self.assertNotIn("display_name_zh:", skill)
        for phrase in (
            "name: 行测复盘一体版",
            "Skill v1.4.1",
            "v1.4 运行优化",
            "`行测解答`直接进入【解法】",
            "`行测复盘`进入【复盘】",
            "只有用户明确给出答案且本轮已核验判错",
            "scripts/writeback.py",
            "只调用一次",
            "不得读取 `writeback.py` 源码",
            "不改变 1.3.1 的方法卡读取范围和先后顺序",
            "不得以“快路径”“最小集合”或卡片数量限制删减方法依据",
            "同一批次读取",
            "最终草稿必须原样出现",
            "`方法依据`不能替代该栏目",
            "方法讲解与速度评估",
            "预计超过 60 秒",
            "速算判定",
            "脚本调用必须是本轮最后一个工具动作",
            "explanation_completed: true",
        ):
            self.assertIn(phrase, skill)
        for phrase in (
            "方法库使用（讲解/解法的第一动作",
            "资料分析公式卡 + AdvancedMethods 高频卡",
            "读完高频卡后",
            "资料分析技巧索引.md",
        ):
            self.assertIn(phrase, data)
        for phrase in (
            "只调用一次",
            "不读取 `writeback.py` 源码",
            "不默认执行 `--dry-run`",
            "不得额外写每日记忆",
            "`written`：确认回执",
            "`noop`：说明同一",
            "`blocked`：报告",
            "explanation_completed",
            "本轮最后一个工具动作",
        ):
            self.assertIn(phrase, writeback_runtime)
        for phrase in ("脚本不可用", "答案冲突", "状态根冲突", "输入校验失败", "必须停止写回"):
            self.assertIn(phrase, engine + writeback_runtime)
        self.assertNotIn("python3 <skill-install-dir>/scripts/writeback.py", engine)

    def test_all_question_types_preserve_full_method_loading(self) -> None:
        protocol_root = ROOT / "skills/xingce-review-pro/references/protocols"
        expected = {
            "verbal": ("读完高频卡后", "言语理解错因诊断总卡"),
            "cloze": ("逻辑填空三步法", "词义辨析强触发（必做）"),
            "data": ("资料分析公式卡 + AdvancedMethods 高频卡", "资料分析技巧索引.md"),
            "quant": ("读完高频卡后", "数量关系错因诊断总卡"),
            "common-sense": ("必读总纲卡", "常识判断错因诊断卡"),
            "judgement": ("图推总纲观察顺序与排查路径", "判断推理错因诊断总卡"),
        }
        for name in ("verbal", "cloze", "data", "quant", "common-sense", "judgement"):
            with self.subTest(protocol=name):
                text = (protocol_root / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn("## 方法库使用", text)
                self.assertIn("references/review-engine/写回运行协议.md", text)
                self.assertIn("调用一次脚本", text)
                self.assertIn("批量读取只优化工具调用", text)
                self.assertIn("方法讲解与速度评估", text)
                for phrase in expected[name]:
                    self.assertIn(phrase, text)
                for field in ("预计用时：", "关键步骤数：", "模型推理风险：", "是否值得做："):
                    self.assertIn(field, text)
                self.assertNotIn("references/protocols/method-loading.md", text)
                self.assertNotIn("## 方法库最小充分读取", text)
                self.assertNotIn("按 `references/review-engine/复盘引擎说明.md` 写回", text)

    def test_package_is_deterministic_and_contains_runtime_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory)
            first = self.run_tool(
                "package_skill.py",
                "--version",
                "v-test",
                "--out-dir",
                str(out_dir),
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            archive = out_dir / "xingce-review-pro-v-test.zip"
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            second = self.run_tool(
                "package_skill.py",
                "--version",
                "v-test",
                "--out-dir",
                str(out_dir),
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as handle:
                listing = handle.namelist()
                packaged_skill = handle.read("xingce-review-pro/SKILL.md").decode("utf-8")
            self.assertIn("xingce-review-pro/scripts/writeback.py", listing)
            self.assertIn(
                "xingce-review-pro/references/review-engine/写回运行协议.md",
                listing,
            )
            self.assertNotIn(
                "xingce-review-pro/references/protocols/method-loading.md",
                listing,
            )
            self.assertNotIn("xingce-review-pro/tools/validate_skill.py", listing)
            self.assertNotIn("xingce-review-pro/README.md", listing)
            self.assertIn("name: 行测复盘一体版", packaged_skill)
            self.assertNotIn("name: xingce-review-pro", packaged_skill)


if __name__ == "__main__":
    unittest.main()
