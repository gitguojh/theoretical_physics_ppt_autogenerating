#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from theory_ppt_lib import (
    read_json,
    render_narrative_plan,
    render_review_report,
    review_and_optimize_plan,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review and optimize an existing theory-physics PPT deck plan.")
    parser.add_argument("--input-plan", required=True, help="Path to an existing deck_plan.json file.")
    parser.add_argument("--input-source", default=None, help="Optional source_summary.json path for better review context.")
    parser.add_argument("--output-plan", required=True, help="Path to the optimized deck plan JSON.")
    parser.add_argument("--output-review-json", required=True, help="Path to the review JSON report.")
    parser.add_argument("--output-review-md", required=True, help="Path to the review Markdown report.")
    parser.add_argument("--output-md", default=None, help="Optional path to write an updated narrative plan Markdown.")
    args = parser.parse_args()

    plan = read_json(Path(args.input_plan))
    source = read_json(Path(args.input_source)) if args.input_source else {}
    optimized, review = review_and_optimize_plan(plan, source=source)

    output_plan = Path(args.output_plan)
    output_review_json = Path(args.output_review_json)
    output_review_md = Path(args.output_review_md)
    output_plan.parent.mkdir(parents=True, exist_ok=True)
    output_review_json.parent.mkdir(parents=True, exist_ok=True)
    output_review_md.parent.mkdir(parents=True, exist_ok=True)

    write_json(output_plan, optimized)
    write_json(output_review_json, review)
    output_review_md.write_text(render_review_report(review), encoding="utf-8")

    if args.output_md:
        output_md = Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_narrative_plan(optimized), encoding="utf-8")
        print(f"Wrote narrative plan to {output_md.resolve()}")

    print(f"Wrote optimized deck plan to {output_plan.resolve()}")
    print(f"Wrote deck review JSON to {output_review_json.resolve()}")
    print(f"Wrote deck review Markdown to {output_review_md.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
