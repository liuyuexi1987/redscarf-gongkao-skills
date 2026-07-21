#!/usr/bin/env python3
"""Safe, idempotent Markdown writeback for gongkao-review-pro.

The model decides whether a write is allowed and supplies structured facts.
This script only validates and persists those facts. It never grades a question
or invents an error diagnosis.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


SCRIPT_SCHEMA_VERSION = 1
ALLOWED_ACTIONS = {
    "wrong_answer",
    "review_result",
    "pending_topic",
    "mastery_upgrade",
    "profile_refresh",
}
STATE_DIRS = ("错因卡", "弱点档案", "学习记录", "导出", "reference")
ROOT_CANDIDATES = ("review-engine", ".workbuddy/memory", "复盘引擎")
EVENTS_RELATIVE = Path(".writeback") / "events.jsonl"


class WritebackError(Exception):
    """A safe, user-visible writeback failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def emit(status: str, **fields: Any) -> None:
    payload = {"status": status, **fields}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def read_payload(source: str) -> dict[str, Any]:
    try:
        raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise WritebackError("invalid_json", f"无法读取 JSON payload：{exc}") from exc
    if not isinstance(value, dict):
        raise WritebackError("invalid_payload", "payload 顶层必须是 JSON 对象")
    return value


def require_text(payload: dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise WritebackError("invalid_payload", f"字段 {key} 必须是非空字符串")
    if "\x00" in value:
        raise WritebackError("invalid_payload", f"字段 {key} 含非法字符")
    return value.strip()


def validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != SCRIPT_SCHEMA_VERSION:
        raise WritebackError(
            "unsupported_schema",
            f"只支持 schema_version={SCRIPT_SCHEMA_VERSION}",
        )
    event_id = require_text(payload, "event_id")
    if len(event_id) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", event_id):
        raise WritebackError("invalid_payload", "event_id 只能包含字母、数字、点、下划线、冒号和连字符")
    action = require_text(payload, "action")
    if action not in ALLOWED_ACTIONS:
        raise WritebackError("invalid_action", f"不支持 action={action}")
    date_value = require_text(payload, "date")
    try:
        dt.date.fromisoformat(date_value)
    except ValueError as exc:
        raise WritebackError("invalid_payload", "date 必须使用 YYYY-MM-DD") from exc

    if action in {"wrong_answer", "review_result"}:
        for key in ("module", "question_type", "weakness_key"):
            require_text(payload, key)
    if action == "wrong_answer":
        for key in (
            "question_text",
            "user_answer",
            "verified_answer",
            "error_reason",
        ):
            require_text(payload, key)
        refs = payload.get("method_refs", [])
        if not isinstance(refs, list) or not all(isinstance(item, str) and item.strip() for item in refs):
            raise WritebackError("invalid_payload", "method_refs 必须是字符串数组")
    elif action == "review_result":
        result = require_text(payload, "result")
        if result not in {"correct", "incorrect", "passed", "failed"}:
            raise WritebackError("invalid_payload", "review_result.result 不合法")
    elif action == "pending_topic":
        for key in ("topic_key", "module_question_type", "user_performance", "next_review_prompt"):
            require_text(payload, key)
    elif action == "mastery_upgrade":
        for key in ("method_name", "key_point"):
            require_text(payload, key)
        refs = payload.get("method_refs", [])
        if not isinstance(refs, list) or not refs:
            raise WritebackError("invalid_payload", "mastery_upgrade.method_refs 不能为空")
    elif action == "profile_refresh":
        return


def is_state_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any((path / name).exists() for name in STATE_DIRS) or any(
        (path / name).is_file() for name in ("学习者画像.md",)
    )


def resolve_state_root(cwd: Path) -> Path:
    cwd = cwd.resolve()
    if not cwd.is_dir():
        raise WritebackError("invalid_cwd", f"cwd 不是目录：{cwd}")
    existing = [cwd / rel for rel in ROOT_CANDIDATES if is_state_root(cwd / rel)]
    if len(existing) > 1:
        raise WritebackError(
            "ambiguous_state_root",
            "发现多个有效状态根：" + ", ".join(str(item) for item in existing),
        )
    root = existing[0] if existing else cwd / "复盘引擎"
    resolved = root.resolve()
    if cwd not in resolved.parents and resolved != cwd:
        raise WritebackError("unsafe_path", "状态根不在当前工作目录内")
    resolved.mkdir(parents=True, exist_ok=True)
    for directory in STATE_DIRS:
        (resolved / directory).mkdir(parents=True, exist_ok=True)
    return resolved


def safe_name(value: str, fallback: str = "未命名") -> str:
    cleaned = re.sub(r"[\x00-\x1f\x7f/\\:*?\"<>|]", "-", value).strip(" .-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:80] or fallback).strip(" .-")


def yaml_value(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ").replace("\"", "\\\"")
    return f'"{text}"'


def frontmatter_bounds(text: str) -> tuple[int, int] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    return 0, end + 4


def get_frontmatter_value(text: str, key: str, default: str = "") -> str:
    bounds = frontmatter_bounds(text)
    if not bounds:
        return default
    header = text[bounds[0] : bounds[1]]
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.*?)\s*$", header)
    return match.group(1).strip().strip('"') if match else default


def set_frontmatter_value(text: str, key: str, value: Any) -> str:
    bounds = frontmatter_bounds(text)
    if not bounds:
        raise WritebackError("invalid_state_file", "状态文件缺少合法 YAML frontmatter")
    start, end = bounds
    header = text[start:end]
    line = f"{key}: {yaml_value(value)}"
    pattern = re.compile(rf"(?m)^{re.escape(key)}:.*$")
    if pattern.search(header):
        header = pattern.sub(line, header, count=1)
    else:
        header = header[:-4].rstrip("\n") + "\n" + line + "\n---\n"
    return header + text[end:]


def append_under_heading(text: str, heading: str, line: str) -> str:
    marker = f"## {heading}"
    position = text.find(marker)
    if position < 0:
        return text.rstrip() + f"\n\n{marker}\n\n{line}\n"
    next_heading = re.search(r"\n## ", text[position + len(marker) :])
    insert_at = position + len(marker) + (next_heading.start() if next_heading else len(text[position + len(marker) :]))
    return text[:insert_at].rstrip() + f"\n\n{line}\n" + text[insert_at:]


def unique_bullets(text: str, heading: str, lines: Iterable[str]) -> str:
    result = text
    for line in lines:
        if line and line not in result:
            result = append_under_heading(result, heading, line)
    return result


def new_weakness(payload: dict[str, Any], error_card_name: str = "") -> str:
    key = payload["weakness_key"]
    strategy = payload.get("next_review_prompt") or f"复习 {payload['module']} 的 {payload['question_type']} 方法与易错点"
    methods = payload.get("method_refs", [])
    method_lines = "\n".join(f"- {item}" for item in methods) or "- 未记录"
    backlink = f" [[../错因卡/{error_card_name}]]" if error_card_name else ""
    return (
        "---\n"
        f"聚合key: {yaml_value(key)}\n"
        "别名: []\n"
        "出错次数: 1\n"
        "难度档: 基础\n"
        "掌握判定: 未掌握\n"
        f"下次出题策略: {yaml_value(strategy)}\n"
        f"最后一次错误日期: {yaml_value(payload['date'])}\n"
        "---\n\n"
        "## 每次错法\n\n"
        f"- {payload['date']}：{payload['error_reason']}{backlink}\n\n"
        "## 关联方法卡\n\n"
        f"{method_lines}\n\n"
        "## 方法掌握度\n\n"
        "<!-- 记录方法工作流题表现；不计入真题正确率 -->\n"
    )


def update_weakness(existing: str, payload: dict[str, Any], error_card_name: str) -> str:
    text = existing
    count_text = get_frontmatter_value(text, "出错次数", "0")
    try:
        count = int(count_text)
    except ValueError:
        count = 0
    text = set_frontmatter_value(text, "出错次数", count + 1)
    text = set_frontmatter_value(text, "最后一次错误日期", payload["date"])
    if payload.get("next_review_prompt"):
        text = set_frontmatter_value(text, "下次出题策略", payload["next_review_prompt"])
    method_lines = [f"- {item}" for item in payload.get("method_refs", [])]
    text = unique_bullets(text, "关联方法卡", method_lines)
    return append_under_heading(
        text,
        "每次错法",
        f"- {payload['date']}：{payload['error_reason']} [[../错因卡/{error_card_name}]]",
    )


def new_error_card(payload: dict[str, Any], weakness_key: str) -> str:
    refs = ", ".join(payload.get("method_refs", [])) or "未记录"
    next_review = payload.get("next_review_prompt", "")
    return (
        "---\n"
        f"题型: {yaml_value(payload['question_type'])}\n"
        f"来源: {yaml_value(payload.get('source', '用户提供'))}\n"
        f"我的答案: {yaml_value(payload['user_answer'])}\n"
        f"正确答案: {yaml_value(payload['verified_answer'])}\n"
        f"错在哪一步: {yaml_value(payload['error_reason'])}\n"
        f"正确方法: {yaml_value(payload.get('correct_method', '按题型协议执行最短路径'))}\n"
        f"方法依据: {yaml_value(refs)}\n"
        f"关联弱点档案: {yaml_value(weakness_key)}\n"
        "难度档: 基础\n"
        "掌握程度: 待复习\n"
        "上次复习:\n"
        f"下次复习: {yaml_value(next_review)}\n"
        "复习次数: 0\n"
        "---\n\n"
        "## 题面\n\n"
        f"{payload['question_text'].strip()}\n\n"
        "## 复盘记录\n\n"
        f"- {payload['date']}：用户答案 {payload['user_answer']}；核验答案 {payload['verified_answer']}。\n"
    )


def add_event(changes: dict[Path, bytes], state_root: Path, event_id: str, action: str) -> None:
    path = state_root / EVENTS_RELATIVE
    existing = path.read_bytes() if path.exists() else b""
    line = json.dumps(
        {"event_id": event_id, "action": action, "recorded_at": dt.datetime.now().isoformat(timespec="seconds")},
        ensure_ascii=False,
    ).encode("utf-8") + b"\n"
    changes[path] = existing + line


def event_seen(state_root: Path, event_id: str) -> bool:
    path = state_root / EVENTS_RELATIVE
    if not path.exists():
        return False
    return any(f'"event_id": "{event_id}"' in line for line in path.read_text(encoding="utf-8").splitlines())


def queue_path(state_root: Path) -> Path:
    return state_root / "学习记录" / "待巩固队列.md"


def queue_header() -> str:
    return (
        "# 待巩固队列\n\n"
        "> 脚本写回的主动学习索引；不等于错因或弱点。\n\n"
        "| 主题键 | 模块/题型 | 用户表现 | 求助次数 | 最近日期 | 状态 | 下次复习问法 |\n"
        "| --- | --- | --- | ---: | --- | --- | --- |\n"
    )


def split_table_row(line: str) -> list[str] | None:
    if not line.startswith("|"):
        return None
    parts = [item.strip() for item in line.strip().strip("|").split("|")]
    return parts if len(parts) >= 7 else None


def render_table_row(parts: list[str]) -> str:
    return "| " + " | ".join(item.replace("|", "\\|") for item in parts[:7]) + " |\n"


def update_queue_for_pending(state_root: Path, payload: dict[str, Any]) -> str:
    path = queue_path(state_root)
    text = path.read_text(encoding="utf-8") if path.exists() else queue_header()
    rows = text.splitlines(keepends=True)
    topic = payload["topic_key"]
    found = False
    output: list[str] = []
    for line in rows:
        parts = split_table_row(line.rstrip("\n"))
        if parts and parts[0] == topic and parts[0] != "主题键":
            found = True
            try:
                count = int(parts[3]) + 1
            except ValueError:
                count = 1
            output.append(
                render_table_row(
                    [
                        topic,
                        payload["module_question_type"],
                        payload["user_performance"],
                        str(count),
                        payload["date"],
                        "待巩固",
                        payload["next_review_prompt"],
                    ]
                )
            )
        else:
            output.append(line)
    if not found:
        if not text.endswith("\n"):
            output.append("\n")
        output.append(
            render_table_row(
                [
                    topic,
                    payload["module_question_type"],
                    payload["user_performance"],
                    "1",
                    payload["date"],
                    "待巩固",
                    payload["next_review_prompt"],
                ]
            )
        )
    return "".join(output)


def mark_queue_transferred(state_root: Path, weakness_key: str) -> tuple[Path, str] | None:
    path = queue_path(state_root)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    output: list[str] = []
    changed = False
    for line in text.splitlines(keepends=True):
        parts = split_table_row(line.rstrip("\n"))
        if parts and parts[0] == weakness_key and parts[0] != "主题键":
            parts[5] = "转弱点"
            line = render_table_row(parts)
            changed = True
        output.append(line)
    return (path, "".join(output)) if changed else None


def update_review(state_root: Path, payload: dict[str, Any]) -> dict[Path, str]:
    weakness = state_root / "弱点档案" / f"{safe_name(payload['weakness_key'])}.md"
    if not weakness.exists():
        raise WritebackError("missing_state", f"未找到弱点档案：{weakness}")
    text = weakness.read_text(encoding="utf-8")
    result = payload["result"]
    if result in {"correct", "passed"}:
        text = set_frontmatter_value(text, "掌握判定", "巩固中")
    note = payload.get("notes", f"复习结果：{result}")
    text = append_under_heading(text, "方法掌握度", f"- {payload['date']}：{note}")
    updates: dict[Path, str] = {weakness: text}
    card_name = payload.get("error_card")
    if card_name:
        safe_card = safe_name(card_name)
        card = state_root / "错因卡" / safe_card
        if card.exists():
            card_text = card.read_text(encoding="utf-8")
            card_text = set_frontmatter_value(card_text, "上次复习", payload["date"])
            count = get_frontmatter_value(card_text, "复习次数", "0")
            try:
                count_value = int(count) + 1
            except ValueError:
                count_value = 1
            card_text = set_frontmatter_value(card_text, "复习次数", count_value)
            updates[card] = append_under_heading(card_text, "复盘记录", f"- {payload['date']}：{note}")
    return updates


def update_mastery(state_root: Path, payload: dict[str, Any]) -> dict[Path, str]:
    refs = ", ".join(payload["method_refs"])
    line = f"- {payload['method_name']} — {payload['key_point']} — {refs}"
    path = state_root / "reference" / "个人方法速查卡.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# 个人方法速查卡\n\n"
    if line not in text:
        text = text.rstrip() + "\n\n## 已掌握方法\n\n" + line + "\n"
    updates: dict[Path, str] = {path: text}
    weakness_key = payload.get("weakness_key")
    if weakness_key:
        weakness = state_root / "弱点档案" / f"{safe_name(weakness_key)}.md"
        if weakness.exists():
            updates[weakness] = set_frontmatter_value(
                weakness.read_text(encoding="utf-8"), "掌握判定", "已掌握"
            )
    return updates


def refresh_profile(state_root: Path, payload: dict[str, Any]) -> dict[Path, str]:
    path = state_root / "学习者画像.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# 学习者画像\n\n"
    weakness_files = sorted((state_root / "弱点档案").glob("*.md"))
    records: list[tuple[str, str, str]] = []
    for file in weakness_files:
        if file.name.endswith("-template.md"):
            continue
        content = file.read_text(encoding="utf-8")
        records.append(
            (
                get_frontmatter_value(content, "聚合key", file.stem),
                get_frontmatter_value(content, "出错次数", "0"),
                get_frontmatter_value(content, "掌握判定", "未掌握"),
            )
        )
    summary = [
        "<!-- writeback:summary:start -->",
        "## 脚本刷新摘要",
        "",
        f"刷新日期：{payload['date']}",
        f"已验证弱点档案数：{len(records)}",
        "",
        "| 聚合key | 出错次数 | 掌握判定 |",
        "| --- | ---: | --- |",
    ]
    summary.extend(f"| {key} | {count} | {mastery} |" for key, count, mastery in records)
    summary.extend(["", "<!-- writeback:summary:end -->"])
    block = "\n".join(summary)
    pattern = re.compile(r"<!-- writeback:summary:start -->.*?<!-- writeback:summary:end -->", re.S)
    text = pattern.sub(block, text) if pattern.search(text) else text.rstrip() + "\n\n" + block + "\n"
    return {path: text}


def build_changes(state_root: Path, payload: dict[str, Any]) -> dict[Path, bytes]:
    action = payload["action"]
    updates: dict[Path, str] = {}
    if action == "wrong_answer":
        title = payload.get("short_title") or payload["question_type"]
        base = f"{payload['date']}-{payload['module']}-{payload['question_type']}-{title}"
        card_name = safe_name(base) + ".md"
        card = state_root / "错因卡" / card_name
        suffix = 1
        while card.exists():
            if payload["event_id"] in card.read_text(encoding="utf-8"):
                return {}
            card_name = safe_name(base) + f"-{suffix}.md"
            card = state_root / "错因卡" / card_name
            suffix += 1
        weakness = state_root / "弱点档案" / f"{safe_name(payload['weakness_key'])}.md"
        updates[card] = new_error_card(payload, payload["weakness_key"])
        updates[weakness] = update_weakness(
            weakness.read_text(encoding="utf-8") if weakness.exists() else new_weakness(payload),
            payload,
            card_name,
        ) if weakness.exists() else new_weakness(payload, card_name)
        transferred = mark_queue_transferred(state_root, payload["weakness_key"])
        if transferred:
            updates[transferred[0]] = transferred[1]
    elif action == "review_result":
        updates.update(update_review(state_root, payload))
    elif action == "pending_topic":
        path = queue_path(state_root)
        updates[path] = update_queue_for_pending(state_root, payload)
    elif action == "mastery_upgrade":
        updates.update(update_mastery(state_root, payload))
    elif action == "profile_refresh":
        updates.update(refresh_profile(state_root, payload))
    changes = {path: content.encode("utf-8") for path, content in updates.items()}
    add_event(changes, state_root, payload["event_id"], action)
    return changes


@contextmanager
def state_lock(state_root: Path):
    lock_path = state_root / ".writeback.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def apply_changes(changes: dict[Path, bytes], dry_run: bool) -> list[str]:
    paths = sorted(changes, key=lambda item: str(item))
    if dry_run:
        return [str(path) for path in paths]
    originals: dict[Path, bytes | None] = {path: path.read_bytes() if path.exists() else None for path in paths}
    written: list[Path] = []
    temp_paths: dict[Path, Path] = {}
    try:
        for path, content in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".writeback-", delete=False) as temp:
                temp.write(content)
                temp.flush()
                os.fsync(temp.fileno())
                temp_paths[path] = Path(temp.name)
        for path in paths:
            os.replace(temp_paths[path], path)
            written.append(path)
        return [str(path) for path in written]
    except Exception as exc:
        for path, original in originals.items():
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(original)
            except OSError:
                pass
        raise WritebackError("rollback", f"写回失败，已尝试回滚：{exc}") from exc
    finally:
        for temp in temp_paths.values():
            temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply validated gongkao-review-pro Markdown writeback")
    parser.add_argument("--cwd", default=os.getcwd(), help="用户项目工作目录")
    parser.add_argument("--payload", default="-", help="JSON 文件路径；- 表示从 stdin 读取")
    parser.add_argument("--dry-run", action="store_true", help="只校验并列出将要写入的文件")
    args = parser.parse_args()
    try:
        payload = read_payload(args.payload)
        validate_payload(payload)
        cwd = Path(args.cwd).resolve()
        state_root = resolve_state_root(cwd)
        event_id = payload["event_id"]
        with state_lock(state_root):
            if event_seen(state_root, event_id):
                emit("noop", event_id=event_id, state_root=str(state_root), files=[])
                return 0
            changes = build_changes(state_root, payload)
            files = apply_changes(changes, args.dry_run)
        emit(
            "dry_run" if args.dry_run else "written",
            event_id=event_id,
            state_root=str(state_root),
            files=files,
            warnings=[],
        )
        return 0
    except WritebackError as exc:
        emit("blocked", code=exc.code, message=exc.message)
        return 2
    except Exception as exc:  # defensive boundary for machine callers
        emit("blocked", code="unexpected_error", message=str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
