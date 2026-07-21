#!/usr/bin/env python3
"""Normalize legacy AdvancedMethods cards without inventing problem content."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FIELDS = ("方法名", "适用题型", "触发场景", "步骤逻辑", "高频错因", "confidence")


def title_of(text: str, path: Path) -> str:
    match = re.search(r"^# 方法卡：(.+)$", text, re.M)
    return match.group(1).strip() if match else path.stem


def section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, re.M)
    if not match:
        return ""
    tail = text[match.end() :]
    next_heading = re.search(r"^## ", tail, re.M)
    value = tail[: next_heading.start() if next_heading else len(tail)]
    return re.sub(r"\s+", " ", value).strip(" \n-:")


def has_field(text: str, field: str) -> bool:
    return bool(re.search(rf"^\|\s*{re.escape(field)}\s*\|", text, re.M))


def insert_into_first_table(text: str, rows: list[str]) -> str:
    start = text.find("| 字段 |")
    if start < 0:
        start = text.find("| 方法名 |")
    if start < 0:
        return text
    end = text.find("\n\n", start)
    if end < 0:
        end = len(text)
    return text[:end].rstrip() + "\n" + "\n".join(rows) + text[end:]


def add_metadata(text: str, path: Path) -> tuple[str, list[str]]:
    title = title_of(text, path)
    alias = "别名" in text or "已并入主卡" in text or "主卡" in text
    values = {
        "方法名": title,
        "适用题型": "见正文；按题型协议确认适用边界",
        "触发场景": section(text, "触发词补充") or f"题目出现与“{title}”相关的关键词或关系",
        "步骤逻辑": section(text, "步骤逻辑") or (
            "先读取对应主卡，再按主卡步骤执行；本卡只提供触发或别名补充"
            if alias
            else "按题型协议定位数据、条件和选项，再执行正文步骤"
        ),
        "高频错因": section(text, "高频错因") or (
            "只凭别名或局部口诀作答，未回到主卡、题干和适用条件"
            if alias
            else "忽略题型触发条件、适用边界或关键核验步骤"
        ),
        "confidence": "medium" if alias else "high",
    }
    missing = [field for field in FIELDS if not has_field(text, field)]
    if not missing:
        return text, []
    rows = [f"| {field} | {values[field]} |" for field in missing]
    if "| 字段 |" in text or "| 方法名 |" in text:
        return insert_into_first_table(text, rows), missing
    metadata = (
        "\n## 基本信息\n\n"
        "| 字段 | 值 |\n"
        "|---|---|\n"
        + "\n".join(rows)
        + "\n"
    )
    heading = re.search(r"^# .+$", text, re.M)
    if not heading:
        return metadata.lstrip() + text, missing
    insert_at = heading.end()
    return text[:insert_at] + "\n" + metadata + text[insert_at:], missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="skills/gongkao-review-pro/references/method-libraries/advanced-methods/方法卡")
    parser.add_argument("--write", action="store_true", help="写入规范化结果；默认只检查")
    args = parser.parse_args()
    root = Path(args.root)
    changed = 0
    missing_total = 0
    for path in sorted(root.glob("am-card-*.md")):
        text = path.read_text(encoding="utf-8")
        updated, missing = add_metadata(text, path)
        if missing:
            changed += 1
            missing_total += len(missing)
            print(f"{'updated' if args.write else 'would-update'}\t{path}\t{','.join(missing)}")
            if args.write:
                path.write_text(updated, encoding="utf-8")
    print(f"cards={len(list(root.glob('am-card-*.md')))} changed={changed} fields={missing_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
