#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from theory_ppt_lib import inspect_template_pptx, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a user-provided .pptx template and write a lightweight style profile JSON.")
    parser.add_argument("--input", required=True, help="Path to the .pptx template to inspect.")
    parser.add_argument("--deck-type", default="group-meeting", choices=["conference", "assessment", "group-meeting"])
    parser.add_argument("--language", default="en", help="Language hint for the template profile.")
    parser.add_argument("--output", required=True, help="Path to the output JSON file.")
    args = parser.parse_args()

    profile = inspect_template_pptx(args.input, deck_type=args.deck_type, language=args.language)
    output = Path(args.output)
    write_json(output, profile)
    print(f"Wrote template profile to {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
