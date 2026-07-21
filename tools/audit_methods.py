#!/usr/bin/env python3
"""Audit method-card schema, indexes, references, and package hygiene."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


REQUIRED_CARD_FIELDS = ("方法名", "适用题型", "触发场景", "步骤逻辑", "高频错因", "confidence")
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def field_value(text: str, field: str) -> str:
    match = re.search(rf"^\|\s*{re.escape(field)}\s*\|\s*([^|]+)\|", text, re.M)
    return match.group(1).strip() if match else ""


def card_id(path: Path) -> str:
    match = re.match(r"am-card-(\d+)_", path.name)
    return match.group(1) if match else ""


def referenced_cards(skill_root: Path) -> tuple[set[str], list[str]]:
    referenced: set[str] = set()
    missing: list[str] = []
    pattern = re.compile(r"方法卡/(am-card-[^`|)]+?\.md)")
    for source in skill_root.rglob("*.md"):
        text = source.read_text(encoding="utf-8")
        for name in pattern.findall(text):
            if any(token in name for token in ("*", "xxxx", "完整名")):
                continue
            referenced.add(name)
            path = skill_root / "references/method-libraries/advanced-methods/方法卡" / name
            if not path.exists():
                missing.append(f"{source.relative_to(skill_root)} -> {name}")
    return referenced, sorted(set(missing))


def audit(skill_root: Path) -> dict[str, object]:
    card_dir = skill_root / "references/method-libraries/advanced-methods/方法卡"
    cards = sorted(card_dir.glob("am-card-*.md"))
    ids = [card_id(path) for path in cards]
    duplicates = sorted(item for item, count in Counter(ids).items() if item and count > 1)
    missing_fields: dict[str, list[str]] = defaultdict(list)
    invalid_confidence: dict[str, str] = {}
    titles: dict[str, list[str]] = defaultdict(list)
    for path in cards:
        text = path.read_text(encoding="utf-8")
        for field in REQUIRED_CARD_FIELDS:
            if not field_value(text, field):
                missing_fields[field].append(path.name)
        confidence = field_value(text, "confidence")
        if confidence and confidence not in ALLOWED_CONFIDENCE:
            invalid_confidence[path.name] = confidence
        title = field_value(text, "方法名")
        if title:
            titles[title].append(path.name)
    referenced, missing_refs = referenced_cards(skill_root)
    index_files = list((skill_root / "references/method-libraries/advanced-methods/按题型索引").glob("*.md"))
    index_files.append(skill_root / "references/method-libraries/advanced-methods/按题型索引.md")
    indexed_names = {
        path.name
        for path in cards
        if any(path.name in index.read_text(encoding="utf-8") for index in index_files)
    }
    duplicate_titles = {key: value for key, value in titles.items() if len(value) > 1}
    orphan_cards = sorted(path.name for path in cards if path.name not in indexed_names)
    lexical_dir = skill_root / "references/lexical-discrimination/groups"
    lexical_groups = sorted(lexical_dir.glob("group-*.md"))
    errors: list[str] = []
    warnings: list[str] = []
    if duplicates:
        errors.append("duplicate card ids: " + ", ".join(duplicates))
    if missing_refs:
        errors.extend("missing card reference: " + item for item in missing_refs)
    if invalid_confidence:
        errors.extend(f"invalid confidence: {name}={value}" for name, value in invalid_confidence.items())
    for field, paths in missing_fields.items():
        if paths:
            errors.append(f"missing field {field}: {len(paths)} cards")
    if duplicate_titles:
        warnings.append(f"duplicate method titles: {len(duplicate_titles)} titles; keep as aliases unless semantically identical")
    if orphan_cards:
        warnings.append(f"cards not present in module indexes: {len(orphan_cards)}")
    if len(lexical_groups) != 57:
        errors.append(f"lexical group count is {len(lexical_groups)}, expected 57 including template")
    if list(skill_root.rglob(".DS_Store")):
        errors.append(".DS_Store exists inside skill package")
    if list(skill_root.rglob("README.md")):
        errors.append("README.md exists inside skill package; use explicit protocol/guide names")
    return {
        "cards": len(cards),
        "referenced_cards": len(referenced),
        "indexed_cards": len(indexed_names),
        "orphan_cards": orphan_cards,
        "duplicate_titles": duplicate_titles,
        "missing_fields": {key: value for key, value in missing_fields.items() if value},
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", default="skills/gongkao-review-pro")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    report = audit(Path(args.skill_root))
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"cards={report['cards']} referenced={report['referenced_cards']} indexed={report['indexed_cards']}")
        for warning in report["warnings"]:  # type: ignore[index]
            print(f"WARNING: {warning}")
        for error in report["errors"]:  # type: ignore[index]
            print(f"ERROR: {error}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
