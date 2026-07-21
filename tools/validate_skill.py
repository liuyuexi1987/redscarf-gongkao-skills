#!/usr/bin/env python3
"""Validate the standard gongkao-review-pro Skill package."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"ERROR: {message}")


def frontmatter(text: str) -> tuple[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    body = text[4:end]
    name = re.search(r"(?m)^name:\s*(.+)$", body)
    description = re.search(r"(?m)^description:\s*(.+)$", body)
    return (name.group(1).strip(), description.group(1).strip()) if name and description else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", default="skills/gongkao-review-pro")
    args = parser.parse_args()
    root = Path(args.skill_root)
    errors: list[str] = []
    required = [
        root / "SKILL.md",
        root / "agents/openai.yaml",
        root / "scripts/writeback.py",
        root / "references/protocols/answer-authority.md",
        root / "references/protocols/question-bank.md",
        root / "references/review-engine/复盘引擎说明.md",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")
    skill_file = root / "SKILL.md"
    if skill_file.exists():
        parsed = frontmatter(skill_file.read_text(encoding="utf-8"))
        if not parsed:
            errors.append("SKILL.md frontmatter must contain name and description")
        else:
            name, description = parsed
            if name != "gongkao-review-pro":
                errors.append(f"Skill name must be gongkao-review-pro, got {name}")
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                errors.append("Skill name is not hyphen-case")
            if len(description) < 40:
                errors.append("Skill description is too short")
    metadata = root / "agents/openai.yaml"
    if metadata.exists():
        text = metadata.read_text(encoding="utf-8")
        for required_text in ("display_name:", "short_description:", "default_prompt:", "$gongkao-review-pro"):
            if required_text not in text:
                errors.append(f"agents/openai.yaml missing {required_text}")
    if list(root.rglob("README.md")):
        errors.append("README.md must not be inside the installable Skill package")
    if list(root.rglob(".DS_Store")):
        errors.append(".DS_Store must not be inside the installable Skill package")
    if list(root.rglob("__pycache__")) or list(root.rglob("*.pyc")):
        errors.append("Python cache files must not be inside the installable Skill package")
    if errors:
        for error in errors:
            fail(error)
        return 1
    print(f"valid skill: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
