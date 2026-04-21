# Workflow

Use this reference when you need the default local path from source material to a deck plan.

Preferred source quality:
1. TeX or arXiv source
2. Clean Markdown/MD notes converted from the paper
3. PDF only as fallback

The automatic review-and-optimize pass is much more reliable on TeX/arXiv source or clean Markdown than on PDF-only input. In PDF-only mode, automatic citations are intentionally conservative: the workflow binds the source paper itself, but does not pretend it has trustworthy local background-reference binding.

## Default Command

Use any Python environment that has the required dependencies installed. For PDF input, `pypdf` is required. If the bundled Codex runtime is available, it is the safest default.

```bash
python3 scripts/run_ppt_workflow.py \
  --input /absolute/path/to/paper.md \
  --deck-type group-meeting \
  --minutes 35 \
  --language zh \
  --audience experts \
  --style-mode auto \
  --presenter-name "Your Name" \
  --presenter-affiliation "Your University" \
  --output-dir outputs/paper-talk
```

Style modes:
- `--style-mode auto`: use a user or bundled `.pptx` template when available, otherwise fall back to the built-in academic style
- `--style-mode builtin`: never require a template
- `--style-mode template`: require a `.pptx` template, either via `--template /path/to/your-template.pptx` or the bundled catalog

In a generic/public release, do not assume bundled templates exist.
Users can supply their own template in either of these ways:
- pass `--template /absolute/path/to/your-template.pptx`
- or place a `.pptx` file in the local `templates/` folder and point `--template` to it

## How To Choose A Style Mode

In realistic day-to-day use, choose the mode like this:

1. Start with `builtin` if the user does not already have a preferred `.pptx` template.
   This is the recommended default for first-time users, marketplace users, and public distribution because it removes the template dependency.
2. Switch to `template` when the user explicitly wants to preserve a personal, group, university, conference, or defense-style `.pptx`.
   Pass the template with `--template /absolute/path/to/your-template.pptx`.
3. Use `auto` when the user is happy to let the workflow try a template first and fall back automatically.
   This is convenient for local use, but less explicit than `builtin` or `template`.

Quick decision rule:
- no template and no strong style preference: `builtin`
- must match an existing `.pptx`: `template`
- not sure and okay with fallback: `auto`

Inspect a custom template only:

```bash
python3 scripts/profile_ppt_template.py \
  --input /absolute/path/to/your-template.pptx \
  --deck-type group-meeting \
  --language en \
  --output outputs/template_profile.json
```

## What It Produces

- `source_summary.json`: normalized extraction of the paper or achievement file
- `deck_plan.json`: machine-readable slide plan after automatic review-and-optimize, including per-slide citation candidates when the source quality allows binding
- `deck_review.json`: structured review findings and auto-cleanup record
- `deck_review.md`: human-readable review summary
- `narrative_plan.md`: human-readable outline for deck authoring

For TeX/arXiv-like sources, `source_summary.json` may also include a bibliography catalog, section-level citation context, equation entries, and definition-like snippets that can be reused in planning.
It may also include section-level symbol definitions, equation-role hints, and a lightweight formalism chain so the planner can connect setup objects, method equations, and result quantities more faithfully.

## Lower-Level Commands

Extract only:

```bash
python3 scripts/extract_research_source.py \
  --input /absolute/path/to/source.tar.gz \
  --output outputs/source_summary.json
```

Plan only:

```bash
python3 scripts/build_slide_plan.py \
  --input outputs/source_summary.json \
  --deck-type conference \
  --minutes 20 \
  --language en \
  --style-mode template \
  --template /absolute/path/to/your-template.pptx \
  --output-json outputs/deck_plan.json \
  --output-md outputs/narrative_plan.md \
  --output-review-json outputs/deck_review.json \
  --output-review-md outputs/deck_review.md
```

Review an existing plan only:

```bash
python3 scripts/review_deck_plan.py \
  --input-plan outputs/deck_plan.json \
  --input-source outputs/source_summary.json \
  --output-plan outputs/deck_plan.optimized.json \
  --output-review-json outputs/deck_review.json \
  --output-review-md outputs/deck_review.md \
  --output-md outputs/narrative_plan.optimized.md
```

## After Planning

After the plan is generated:
1. Use the PowerPoint skill to build the actual `.pptx`.
2. Follow the style source recommended in `deck_plan.json`: either the built-in academic contract or one `.pptx` template family.
3. Preserve slide-local citations for all non-original content.
   For PDF-only input, expect those auto-citations to default to the source paper unless you manually verify tighter local references.
4. Keep only one main takeaway per slide.
5. Match the local footer convention: presenter name and affiliation at bottom-left, slide number at bottom-right.
6. Rebuild equations as true math objects or LaTeX-rendered assets rather than plain text.
7. Prefer dot-led subsection headings over decorative vertical accent bars on content slides.
8. If edit mode shows dashed placeholder boxes, clean them before delivery.
9. Use blue emphasis only for the per-slide `blue_emphasis_terms`, rendered inline as rich-text segments or equivalent partial styling.
10. During final authoring, emit an `inspect.ndjson` artifact with textbox bounding boxes, font sizes, fit metadata, and optional card/container ids, then run `node scripts/render_layout_guard.mjs /absolute/path/to/inspect.ndjson`.
11. If a colored callout or rounded card cannot cleanly contain its heading, body, and citation together, move the citation outside the card before shrinking the scientific text below readability.
12. Check `deck_review.md` before final export; if it still reports warnings, resolve them before delivering the deck.
