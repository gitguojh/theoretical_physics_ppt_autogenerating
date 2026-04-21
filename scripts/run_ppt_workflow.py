#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from theory_ppt_lib import (
    build_deck_plan,
    extract_source,
    render_narrative_plan,
    render_review_report,
    review_and_optimize_plan,
    slugify,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the default theory-physics PPT planning workflow.")
    parser.add_argument("--input", required=True, help="Path to a local PDF, Markdown file, TeX file, TeX directory/archive, or assessment JSON.")
    parser.add_argument("--deck-type", required=True, choices=["conference", "assessment", "group-meeting"])
    parser.add_argument("--minutes", type=int, default=None, help="Planned speaking time in minutes.")
    parser.add_argument("--language", default="en", help="Deck language, usually 'en' or 'zh'.")
    parser.add_argument("--audience", default="experts", help="Audience label, e.g. experts, broad, mixed.")
    parser.add_argument("--style-mode", default="auto", choices=["auto", "builtin", "template"], help="auto: use a template when available and fall back to built-in style; builtin: never require a PPTX template; template: require a PPTX template or bundled template family.")
    parser.add_argument("--presenter-name", default=None, help="Presenter name to use on the cover/footer.")
    parser.add_argument("--presenter-affiliation", default=None, help="Presenter affiliation to use on the cover/footer.")
    parser.add_argument("--presenter-footer", default=None, help="Explicit footer label, e.g. 'Name (Affiliation)'.")
    parser.add_argument("--kind", default="auto", choices=["auto", "pdf", "markdown", "tex", "tex-dir", "tex-archive", "achievements-json"])
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum number of PDF pages to scan.")
    parser.add_argument("--template", default=None, help="Preferred built-in template name/path, or a user-supplied .pptx when --style-mode template or auto.")
    parser.add_argument("--skip-review", action="store_true", help="Skip the automatic review-and-optimize pass.")
    parser.add_argument("--output-dir", default=None, help="Output directory. Defaults to outputs/<slug>.")
    args = parser.parse_args()

    source_path = Path(args.input)
    source = extract_source(source_path, explicit_kind=args.kind, max_pages=args.max_pages)
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

    output_dir = Path(args.output_dir) if args.output_dir else Path("outputs") / slugify(source.get("title", source_path.stem))
    output_dir.mkdir(parents=True, exist_ok=True)
    source_json = output_dir / "source_summary.json"
    plan_json = output_dir / "deck_plan.json"
    plan_md = output_dir / "narrative_plan.md"
    review_json = output_dir / "deck_review.json"
    review_md = output_dir / "deck_review.md"

    write_json(source_json, source)
    write_json(plan_json, plan)
    plan_md.write_text(render_narrative_plan(plan), encoding="utf-8")
    if review is not None:
        write_json(review_json, review)
        review_md.write_text(render_review_report(review), encoding="utf-8")

    print(f"Source summary: {source_json.resolve()}")
    print(f"Deck plan: {plan_json.resolve()}")
    print(f"Narrative plan: {plan_md.resolve()}")
    if review is not None:
        print(f"Deck review JSON: {review_json.resolve()}")
        print(f"Deck review Markdown: {review_md.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
