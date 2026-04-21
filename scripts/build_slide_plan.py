#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from theory_ppt_lib import (
    build_deck_plan,
    read_json,
    render_narrative_plan,
    render_review_report,
    review_and_optimize_plan,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a slide-by-slide plan from a normalized source summary JSON.")
    parser.add_argument("--input", required=True, help="Path to a normalized source summary JSON.")
    parser.add_argument("--deck-type", required=True, choices=["conference", "assessment", "group-meeting"])
    parser.add_argument("--minutes", type=int, default=None, help="Planned speaking time in minutes.")
    parser.add_argument("--language", default="en", help="Deck language, usually 'en' or 'zh'.")
    parser.add_argument("--audience", default="experts", help="Audience label, e.g. experts, broad, mixed.")
    parser.add_argument("--style-mode", default="auto", choices=["auto", "builtin", "template"], help="auto: use a template when available and fall back to built-in style; builtin: never require a PPTX template; template: require a PPTX template or bundled template family.")
    parser.add_argument("--presenter-name", default=None, help="Presenter name to use on the cover/footer.")
    parser.add_argument("--presenter-affiliation", default=None, help="Presenter affiliation to use on the cover/footer.")
    parser.add_argument("--presenter-footer", default=None, help="Explicit footer label, e.g. 'Name (Affiliation)'.")
    parser.add_argument("--template", default=None, help="Preferred built-in template name/path, or a user-supplied .pptx when --style-mode template or auto.")
    parser.add_argument("--skip-review", action="store_true", help="Skip the automatic review-and-optimize pass.")
    parser.add_argument("--output-json", required=True, help="Output deck-plan JSON path.")
    parser.add_argument("--output-md", required=True, help="Output narrative plan Markdown path.")
    parser.add_argument("--output-review-json", default=None, help="Optional path for the review JSON report.")
    parser.add_argument("--output-review-md", default=None, help="Optional path for the review Markdown report.")
    args = parser.parse_args()

    source = read_json(Path(args.input))
    plan = build_deck_plan(
        source,
        deck_type=args.deck_type,
        minutes=args.minutes,
        language=args.language,
        audience=args.audience,
        style_mode=args.style_mode,
        preferred_template=args.template,
        presenter_name=args.presenter_name,
        presenter_affiliation=args.presenter_affiliation,
        presenter_footer=args.presenter_footer,
    )
    review = None
    if not args.skip_review:
        plan, review = review_and_optimize_plan(plan, source=source)
    write_json(Path(args.output_json), plan)
    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_narrative_plan(plan), encoding="utf-8")
    if review is not None and args.output_review_json:
        write_json(Path(args.output_review_json), review)
    if review is not None and args.output_review_md:
        review_md = Path(args.output_review_md)
        review_md.parent.mkdir(parents=True, exist_ok=True)
        review_md.write_text(render_review_report(review), encoding="utf-8")
    print(f"Wrote deck plan to {Path(args.output_json).resolve()}")
    print(f"Wrote narrative plan to {output_md.resolve()}")
    if review is not None and args.output_review_json:
        print(f"Wrote deck review JSON to {Path(args.output_review_json).resolve()}")
    if review is not None and args.output_review_md:
        print(f"Wrote deck review Markdown to {Path(args.output_review_md).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
