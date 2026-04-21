#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path


PACKAGE_NAME = "theory-physics-ppt"
PACKAGE_VERSION = "0.2.1"
AUTHOR = "Jinhui Guo"
COPYRIGHT = "Copyright (c) 2026 Jinhui Guo. All rights reserved."
LICENSE_NAME = "Proprietary"

REPO_ROOT = Path(__file__).resolve().parents[1]

INCLUDED_PATHS = [
    Path(".gitignore"),
    Path("README.md"),
    Path("SKILL.md"),
    Path("agents/openai.yaml"),
    Path("references/input_formats.md"),
    Path("references/workflow.md"),
    Path("scripts/build_slide_plan.py"),
    Path("scripts/clean_pptx_placeholders.py"),
    Path("scripts/extract_research_source.py"),
    Path("scripts/package_skill_release.py"),
    Path("scripts/profile_ppt_template.py"),
    Path("scripts/render_layout_guard.mjs"),
    Path("scripts/review_deck_plan.py"),
    Path("scripts/run_ppt_workflow.py"),
    Path("scripts/theory_ppt_lib.py"),
    Path("templates/.gitkeep"),
]

EXCLUDED_NOTES = [
    "outputs/**: generated deck artifacts are excluded from the release bundle.",
    "tmp/**: temporary build products and previews are excluded from the release bundle.",
    "templates/*.pptx: local or personal PowerPoint templates are excluded from the public release; users can add their own later.",
    "templates/*.pdf: sample input papers are excluded from redistribution.",
    "templates/arXiv-*/**: sample arXiv source packages are excluded from redistribution.",
    ".DS_Store: local Finder metadata is excluded.",
]


def _license_text() -> str:
    return (
        f"{LICENSE_NAME} License\n\n"
        f"{COPYRIGHT}\n\n"
        "This skill package, including its bundled planning scripts, references, and presentation "
        "templates, is provided as a proprietary work by the copyright holder.\n\n"
        "No permission to copy, redistribute, sublicense, or publish modified versions is granted "
        "except with prior written permission from the copyright holder.\n"
    )


def _copyright_text() -> str:
    return (
        f"Skill: {PACKAGE_NAME}\n"
        f"Version: {PACKAGE_VERSION}\n"
        f"Author: {AUTHOR}\n"
        f"{COPYRIGHT}\n\n"
        "Release bundle note:\n"
        "- Only the reusable skill files are packaged.\n"
        "- Example source papers, temporary build products, and generated outputs are excluded.\n"
    )


def _manifest(included_files: list[str]) -> dict[str, object]:
    return {
        "name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "author": AUTHOR,
        "license": LICENSE_NAME,
        "copyright": COPYRIGHT,
        "entrypoint": "SKILL.md",
        "agent_metadata": "agents/openai.yaml",
        "package_kind": "codex-skill",
        "summary": (
            "Theory-physics presentation planning skill with TeX-aware source extraction, "
            "automatic review/optimization, dual built-in-or-template style modes, and "
            "render-level layout validation for PowerPoint authoring."
        ),
        "included_files": included_files,
        "excluded_notes": EXCLUDED_NOTES,
        "upload_targets": [
            "Codex skill marketplace",
            "GitHub repository or release archive",
        ],
    }


def build_release(output_root: Path) -> tuple[Path, Path]:
    package_root = output_root / PACKAGE_NAME
    archive_path = output_root / f"{PACKAGE_NAME}-{PACKAGE_VERSION}.zip"

    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    for relative_path in INCLUDED_PATHS:
        src = REPO_ROOT / relative_path
        if not src.exists():
            raise FileNotFoundError(f"Missing required release file: {src}")
        dest = package_root / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied_files.append(relative_path.as_posix())

    (package_root / "LICENSE").write_text(_license_text(), encoding="utf-8")
    (package_root / "COPYRIGHT").write_text(_copyright_text(), encoding="utf-8")
    (package_root / "skill-package.json").write_text(
        json.dumps(_manifest(sorted(copied_files + ["LICENSE", "COPYRIGHT", "skill-package.json"])), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(package_root.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, arcname=f"{PACKAGE_NAME}/{file_path.relative_to(package_root).as_posix()}")

    return package_root, archive_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a clean release bundle for the theory-physics-ppt skill.")
    parser.add_argument(
        "--output-root",
        default=str(REPO_ROOT / "release"),
        help="Directory where the release folder and zip archive will be written.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    package_root, archive_path = build_release(output_root)
    print(f"Release folder: {package_root}")
    print(f"Release archive: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
