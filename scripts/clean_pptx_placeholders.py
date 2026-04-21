#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


SLIDE_NUMBER_PLACEHOLDER_RE = re.compile(
    r"<p:sp>.*?<p:ph\b[^>]*type=\"sldNum\"[^>]*/>.*?</p:sp>",
    flags=re.DOTALL,
)


def clean_pptx_placeholders(path: Path) -> int:
    if not path.exists():
        raise FileNotFoundError(path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / path.name
        removed = 0
        with zipfile.ZipFile(path, "r") as src, zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for member in src.infolist():
                data = src.read(member.filename)
                if member.filename.startswith("ppt/slides/slide") and member.filename.endswith(".xml"):
                    text = data.decode("utf-8", errors="ignore")
                    text, count = SLIDE_NUMBER_PLACEHOLDER_RE.subn("", text)
                    if count:
                        removed += count
                    data = text.encode("utf-8")
                dst.writestr(member, data)
        shutil.move(str(temp_path), str(path))
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove editable-view PPTX slide-number placeholders that show as dashed boxes.")
    parser.add_argument("pptx", help="Path to the pptx file to clean in place.")
    args = parser.parse_args()

    pptx_path = Path(args.pptx).resolve()
    removed = clean_pptx_placeholders(pptx_path)
    print(f"Removed {removed} placeholder shape(s) from {pptx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
