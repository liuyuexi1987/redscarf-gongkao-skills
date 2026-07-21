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
        validated = self.run_tool("validate_skill.py", "--skill-root", "skills/gongkao-review-pro")
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        audited = self.run_tool("audit_methods.py", "--skill-root", "skills/gongkao-review-pro")
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)

    def test_skill_behavior_contract_is_present(self) -> None:
        skill = (ROOT / "skills/gongkao-review-pro/SKILL.md").read_text(encoding="utf-8")
        engine = (ROOT / "skills/gongkao-review-pro/references/review-engine/复盘引擎说明.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "`行测解答`直接进入【解法】",
            "`行测复盘`进入【复盘】",
            "只有用户明确给出答案且本轮已核验判错",
            "scripts/writeback.py",
            "方法讲解与速度评估",
            "预计超过 60 秒",
            "速算判定",
        ):
            self.assertIn(phrase, skill)
        for phrase in ("脚本不可用", "答案冲突", "状态根冲突", "输入校验失败", "必须停止写回"):
            self.assertIn(phrase, engine)

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
            archive = out_dir / "gongkao-review-pro-v-test.zip"
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
            self.assertIn("gongkao-review-pro/scripts/writeback.py", listing)
            self.assertNotIn("gongkao-review-pro/tools/validate_skill.py", listing)
            self.assertNotIn("gongkao-review-pro/README.md", listing)


if __name__ == "__main__":
    unittest.main()
