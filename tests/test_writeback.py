import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "skills/gongkao-review-pro/scripts/writeback.py"


class WritebackTests(unittest.TestCase):
    def run_writeback(self, cwd: Path, payload: dict) -> tuple[int, dict]:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False)
            payload_path = Path(handle.name)
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--cwd", str(cwd), "--payload", str(payload_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            payload_path.unlink(missing_ok=True)
        self.assertTrue(result.stdout.strip(), result.stderr)
        return result.returncode, json.loads(result.stdout.strip().splitlines()[-1])

    def wrong_payload(self, event_id: str = "wrong-001") -> dict:
        return {
            "schema_version": 1,
            "event_id": event_id,
            "action": "wrong_answer",
            "date": "2026-07-21",
            "module": "资料分析",
            "question_type": "增长率比较",
            "weakness_key": "资料分析-增长率-增长率比较",
            "question_text": "某题完整题面",
            "user_answer": "D",
            "verified_answer": "A",
            "error_reason": "把增长量比较当成增长率比较",
            "method_refs": ["am-card-0004"],
            "next_review_prompt": "先写增长量，再还原基期比较增长率",
        }

    def test_wrong_answer_is_written_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            payload = self.wrong_payload()
            code, receipt = self.run_writeback(cwd, payload)
            self.assertEqual(code, 0)
            self.assertEqual(receipt["status"], "written")
            state = cwd / "复盘引擎"
            cards = list((state / "错因卡").glob("*.md"))
            weaknesses = list((state / "弱点档案").glob("*.md"))
            self.assertEqual(len(cards), 1)
            self.assertEqual(len(weaknesses), 1)
            weakness_text = weaknesses[0].read_text(encoding="utf-8")
            self.assertIn("../错因卡/", weakness_text)
            events = (state / ".writeback/events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(events), 1)

            code, receipt = self.run_writeback(cwd, payload)
            self.assertEqual(code, 0)
            self.assertEqual(receipt["status"], "noop")
            self.assertEqual(len(list((state / "错因卡").glob("*.md"))), 1)
            self.assertEqual(len((state / ".writeback/events.jsonl").read_text(encoding="utf-8").splitlines()), 1)

    def test_pending_topic_transfers_to_weakness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            pending = {
                "schema_version": 1,
                "event_id": "pending-001",
                "action": "pending_topic",
                "date": "2026-07-21",
                "topic_key": "资料分析-增长率-增长率比较",
                "module_question_type": "资料分析 / 增长率比较",
                "user_performance": "连续两次需要提示",
                "next_review_prompt": "先判断题型，再选增长率公式",
            }
            code, receipt = self.run_writeback(cwd, pending)
            self.assertEqual(code, 0)
            self.assertEqual(receipt["status"], "written")
            queue = cwd / "复盘引擎/学习记录/待巩固队列.md"
            self.assertIn("待巩固", queue.read_text(encoding="utf-8"))

            code, _ = self.run_writeback(cwd, self.wrong_payload("wrong-002"))
            self.assertEqual(code, 0)
            self.assertIn("转弱点", queue.read_text(encoding="utf-8"))

    def test_review_mastery_and_profile_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            self.run_writeback(cwd, self.wrong_payload())
            state = cwd / "复盘引擎"
            card_name = next((state / "错因卡").glob("*.md")).name
            review = {
                "schema_version": 1,
                "event_id": "review-001",
                "action": "review_result",
                "date": "2026-07-22",
                "module": "资料分析",
                "question_type": "增长率比较",
                "weakness_key": "资料分析-增长率-增长率比较",
                "result": "correct",
                "error_card": card_name,
                "notes": "独立完成，能先还原基期",
            }
            code, receipt = self.run_writeback(cwd, review)
            self.assertEqual(code, 0)
            self.assertEqual(receipt["status"], "written")
            weakness = next((state / "弱点档案").glob("*.md")).read_text(encoding="utf-8")
            self.assertIn('掌握判定: "巩固中"', weakness)
            card = (state / "错因卡" / card_name).read_text(encoding="utf-8")
            self.assertIn('复习次数: "1"', card)

            mastery = {
                "schema_version": 1,
                "event_id": "mastery-001",
                "action": "mastery_upgrade",
                "date": "2026-07-23",
                "method_name": "增长率比较",
                "key_point": "比较增长量/基期，不只看增长量",
                "method_refs": ["am-card-0004"],
                "weakness_key": "资料分析-增长率-增长率比较",
            }
            code, receipt = self.run_writeback(cwd, mastery)
            self.assertEqual(code, 0)
            self.assertEqual(receipt["status"], "written")
            self.assertIn("已掌握", next((state / "弱点档案").glob("*.md")).read_text(encoding="utf-8"))
            self.assertTrue((state / "reference/个人方法速查卡.md").exists())

            refresh = {
                "schema_version": 1,
                "event_id": "profile-001",
                "action": "profile_refresh",
                "date": "2026-07-24",
            }
            code, receipt = self.run_writeback(cwd, refresh)
            self.assertEqual(code, 0)
            self.assertEqual(receipt["status"], "written")
            self.assertIn("脚本刷新摘要", (state / "学习者画像.md").read_text(encoding="utf-8"))

    def test_validation_failure_does_not_create_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            payload = self.wrong_payload()
            payload["schema_version"] = 999
            code, receipt = self.run_writeback(cwd, payload)
            self.assertNotEqual(code, 0)
            self.assertEqual(receipt["status"], "blocked")
            self.assertFalse((cwd / "复盘引擎").exists())

    def test_ambiguous_state_roots_block_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            (cwd / "review-engine/错因卡").mkdir(parents=True)
            (cwd / "复盘引擎/错因卡").mkdir(parents=True)
            code, receipt = self.run_writeback(cwd, self.wrong_payload())
            self.assertNotEqual(code, 0)
            self.assertEqual(receipt["status"], "blocked")
            self.assertEqual(receipt["code"], "ambiguous_state_root")
            self.assertEqual(list((cwd / "review-engine/错因卡").iterdir()), [])
            self.assertEqual(list((cwd / "复盘引擎/错因卡").iterdir()), [])

    def test_state_root_symlink_outside_workdir_blocks_before_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cwd = base / "work"
            outside = base / "outside"
            cwd.mkdir()
            outside.mkdir()
            (outside / "错因卡").mkdir()
            (cwd / "复盘引擎").symlink_to(outside, target_is_directory=True)
            code, receipt = self.run_writeback(cwd, self.wrong_payload())
            self.assertNotEqual(code, 0)
            self.assertEqual(receipt["status"], "blocked")
            self.assertEqual(receipt["code"], "unsafe_path")
            self.assertEqual(list((outside / "错因卡").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
