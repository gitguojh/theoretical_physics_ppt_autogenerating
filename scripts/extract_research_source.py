#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from theory_ppt_lib import extract_source, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract structured metadata from a paper PDF, Markdown/MD summary, TeX source, or assessment JSON.")
    parser.add_argument("--input", required=True, help="Path to a local PDF, Markdown file, TeX file, TeX directory/archive, or assessment JSON.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--kind", default="auto", choices=["auto", "pdf", "markdown", "tex", "tex-dir", "tex-archive", "achievements-json"])
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum number of PDF pages to scan.")
    args = parser.parse_args()

    payload = extract_source(Path(args.input), explicit_kind=args.kind, max_pages=args.max_pages)
    write_json(Path(args.output), payload)
    print(f"Wrote extraction summary to {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
