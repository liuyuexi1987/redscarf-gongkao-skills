#!/usr/bin/env python3
"""Validate and create a deterministic Skill ZIP plus SHA-256 checksum."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path


def run_check(script: Path, skill_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(script), "--skill-root", str(skill_root)],
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", default="skills/gongkao-review-pro")
    parser.add_argument("--version", default="v1.4.0")
    parser.add_argument("--out-dir", default="dist")
    args = parser.parse_args()
    skill_root = Path(args.skill_root).resolve()
    project_root = Path(__file__).resolve().parents[1]
    out_dir = (project_root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    run_check(project_root / "tools/validate_skill.py", skill_root)
    run_check(project_root / "tools/audit_methods.py", skill_root)
    licensing_files = (project_root / "LICENSE", project_root / "NOTICE")
    missing_files = [path for path in licensing_files if not path.is_file()]
    if missing_files:
        raise SystemExit("缺少发布所需的许可证文件：" + "、".join(map(str, missing_files)))

    package_name = f"gongkao-review-pro-{args.version}.zip"
    archive = out_dir / package_name
    files = sorted(
        path
        for path in skill_root.rglob("*")
        if path.is_file()
        and path.name not in {".DS_Store", "README.md"}
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in files:
            relative = Path("gongkao-review-pro") / path.relative_to(skill_root)
            data = path.read_bytes()
            info = zipfile.ZipInfo(str(relative).replace(os.sep, "/"), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            handle.writestr(info, data)
        for path in licensing_files:
            relative = Path("gongkao-review-pro") / path.name
            info = zipfile.ZipInfo(str(relative), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            handle.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"package={archive}")
    print(f"sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
