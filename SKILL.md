---
name: theory-physics-ppt
description: Plan theory-physics research PowerPoint decks from papers, PDFs, Markdown notes, arXiv sources, and achievement summaries, then hand the final `.pptx` authoring to the PowerPoint workflow. Use for conference talks, assessment/review PPTs, and group-meeting or journal-club presentations when the deck should match formal academic styles, support either a built-in academic style or a user-supplied `.pptx` template, include slide-local citation guidance for non-original content, automatically review and optimize the slide plan before final authoring, and require a render-level overflow/collision guard before export. Prefer TeX/arXiv source or a clean Markdown conversion over PDF-only input whenever possible.
license: Proprietary
metadata:
  author: Jinhui Guo
  copyright: Copyright (c) 2026 Jinhui Guo. All rights reserved.
  version: 0.2.1
---

# Theory Physics PPT

Use this skill when the user wants a physics-research PPT planned from one or more papers, a PDF, a Markdown/MD summary, an arXiv source package, or a structured list of academic achievements, and the final deck should look like a real research talk rather than a generic business presentation.

If the user can choose the input format, prefer:
1. TeX or arXiv source
2. A clean Markdown conversion with headings, figure labels, and short summaries
3. PDF only as fallback

Use the session's PowerPoint workflow for the actual `.pptx` build. This skill is primarily the domain-specific planner/reviewer: it extracts source structure, builds a slide plan, assigns timing, suggests figure/equation emphasis, chooses a style mode, and flags review issues before final authoring.

For `TeX/arXiv source`, the planner should prefer richer structure over generic summaries:
- section-level logical roles
- symbol definitions
- equation roles such as defining formalism, analysis engine, or observable relation
- section-level formalism chains that track how setup objects flow into method equations and then into result quantities
- slide bindings that keep setup and method pages anchored to those objects

## Bundled Resources

- `templates/`: optional bundled `.pptx` template catalog. Use when the user wants one of the built-in local families, or when no custom template is supplied and `style-mode=auto` prefers a bundled template before falling back to the built-in academic contract.
- `scripts/run_ppt_workflow.py`: default end-to-end planner from paper or achievement input to deck plan artifacts.
- `scripts/extract_research_source.py`: lower-level extractor for PDF, TeX, arXiv-like source archives, or assessment JSON.
- `scripts/build_slide_plan.py`: lower-level slide-plan generator from normalized JSON.
- `scripts/profile_ppt_template.py`: inspect a user-provided `.pptx` and write a lightweight theme/master profile JSON.
- `scripts/review_deck_plan.py`: standalone review-and-optimize pass for an existing `deck_plan.json`.
- `scripts/render_layout_guard.mjs`: shared render-level guard for width-aware text fitting, boxed-callout containment, and slide-local text-collision checks before final export.
- `scripts/package_skill_release.py`: build a clean release bundle for marketplace/GitHub upload without local outputs, temp files, or sample input papers.
- `references/workflow.md`: command examples and the default local pipeline.
- `references/input_formats.md`: preferred assessment JSON format and supported source types.

Read `references/workflow.md` when you need the exact command shape. Read `references/input_formats.md` when the user wants an `assessment` deck or the source needs normalization first.

## Default Local Workflow

Use this order unless the user explicitly wants a different process:

1. Run the workflow with a Python environment that has the required dependencies installed, especially `pypdf` for PDF input:
   - preferred: the bundled Codex runtime when available
   - fallback: `python3 scripts/run_ppt_workflow.py ...`
   - style mode:
     - `--style-mode auto`: use a `.pptx` template when available, otherwise fall back to the built-in academic style
     - `--style-mode builtin`: never require a template
     - `--style-mode template`: require either a user-supplied `.pptx` or a bundled template family
   This generates:
   - `source_summary.json`
   - `deck_plan.json`
   - `deck_review.json`
   - `deck_review.md`
   - `narrative_plan.md`
2. Let the automatic review pass compress overloaded slides, add per-slide blue-emphasis terms, check for empty or weak content, and warn about weak source quality or missing structure.
3. Before final delivery, run the shared render-level layout guard on the actual `.pptx` authoring pass: use `scripts/render_layout_guard.mjs` together with an `inspect.ndjson` artifact so width-aware text-fit estimates, boxed-callout containment checks, and text-region collision checks can stop export before wrapped text spills outside its card or overlaps the next block.
4. Review the chosen style source and the optimized slide sequence.
5. Use the PowerPoint skill to build the actual `.pptx` from `narrative_plan.md` and either the selected `.pptx` template or the built-in academic contract.
6. Verify that all non-original content carries slide-local citations.

If the user only wants planning, stop after step 1. If the user wants a full deck, continue into the PowerPoint build path.

## First Pass

1. Classify the deck as `conference`, `assessment`, or `group-meeting`.
2. Determine:
   - target audience
   - talk language
   - total speaking time
   - whether Q&A is included in that time
   - whether the key papers are the user's own work or other people's work
3. Choose the style mode:
   - `builtin`: use the built-in academic style contract with no external template
   - `template`: use a user-supplied `.pptx` or a bundled template family
   - `auto`: prefer a user or bundled template when available, otherwise fall back to `builtin`
4. If `template` mode is chosen, visually confirm the selected `.pptx` family before final authoring. If `builtin` mode is chosen, follow the built-in academic style contract consistently.

If the user does not specify a duration, use these defaults:
- `conference`: 20 minutes
- `assessment`: 15-20 minutes
- `group-meeting`: 30-45 minutes

## Style Modes

This skill supports two compatible authoring modes:

- `builtin`: template-free academic style. Use the rendering contract directly, even if no `.pptx` template is available.
- `template`: template-driven style. Preserve either a user-supplied `.pptx` or one bundled local template family.
- `auto`: try `template` first, then fall back to `builtin` if no usable `.pptx` is available.

## Style Mode Selection

Use this quick rule in normal operation:

- default to `builtin` when the user does not care about matching a pre-existing deck style
- use `template` when the user explicitly wants to preserve a lab, university, conference, or personal `.pptx` template
- use `auto` when the user is happy to let the workflow try a `.pptx` template first and silently fall back to the built-in academic style if needed

For public release and first-time users, recommend `builtin` first because it removes the template dependency and is the most stable starting point.

For a custom user template, the minimum reliable input is a `.pptx` file. The skill can inspect its theme fonts, colors, slide size, and master/layout count, but the final authoring pass should still visually preserve the template master rather than pretending the profile is a complete semantic understanding of the deck.

## Template Selection

Treat `templates/` as an optional workspace folder for `.pptx` templates, not as a required built-in catalog.

In `style-mode=template`, choose the template source in this order:
1. an explicit `--template /absolute/path/to/your-template.pptx`
2. a user-provided `.pptx` placed in the local `templates/` folder
3. any bundled example templates if the local workspace happens to ship them

For public release and marketplace distribution, do not assume the workspace contains bundled personal templates.
The generic skill should still work with:
- no template at all via `builtin`
- an arbitrary user-provided `.pptx` via `template`
- fallback behavior via `auto`

Choose one primary style source per deck. It is fine to borrow a small motif from another template, but do not mix incompatible title pages, fonts, and section styles in the same presentation.

## Built-In Academic Style DNA

- Keep a wide `16:9` layout and a formal academic tone.
- Cover slides are centered: large title, then author, affiliation, and date below, often with a top banner, university mark, or thematic image strip.
- Body slides use a clear title area, then large figures, equations, tables, or diagrams. Text is supporting material, not the main content.
- For the default English research style in this skill, prefer a very light canvas, top-left section titles, and generous whitespace instead of heavy colored header bands.
- For the main built-in English seminar style, the standard body-slide skeleton is:
  blue slide title at top -> black divider line -> main content -> black footer divider -> presenter name left and slide number right.
- A practical master-derived default for this family is:
  slide title in `DengXian/等线`-style sans font around `44 pt`, blue;
  in-slide section headers in PKU red around `28 pt`, bold;
  explanatory body text in `Helvetica` around `26 pt`, black, with selective blue emphasis for key words.
- Use blue emphasis sparingly for genuinely important terms: core model names, physical mechanisms, observables, benchmark labels, or the one phrase the speaker wants the audience to remember.
- Treat blue emphasis as a rendering rule, not a vague style wish: in final authoring, render only the per-slide `blue_emphasis_terms` using rich-text segments or equivalent inline styling.
- For in-slide mini-sections, prefer a colored dot-led heading such as `· Subtopic`, followed by black body text on the same line or the next line. Avoid decorative vertical accent bars when they make the layout look crowded.
- If a slide uses a colored or boxed callout region, the box must be tall enough to contain its heading and body after wrapping. If the local citation makes the box too crowded, move the citation outside the box rather than shrinking the scientific text below readability.
- Footer default for this family:
  presenter name plus affiliation in black `18 pt`;
  slide number in black at the lower-right;
  citations should stay above the footer divider or near the borrowed object, not inside the footer itself.
- When building with JS/PPT automation, verify the exported `.pptx` keeps these as true final sizes, not only authoring-time sizes.
- Put the presenter identity in the lower-left footer, typically `Name (Affiliation)`, and put the slide number in the lower-right corner. Do not hide page numbers in the top bar.
- Treat the presenter identity as user-provided metadata, not as a hard-coded string. If the user supplies presenter name, affiliation, or a preferred footer label, propagate that through the plan and final deck.
- Section or agenda slides are explicit and help the audience re-orient.
- Summary slides are terse: a few takeaways, then outlook or thanks.
- References are usually compact bracketed items placed near the borrowed object or along the bottom edge.
- Equations should remain readable and math-native. Prefer native PPT equations when practical; otherwise render equations from LaTeX into high-resolution vector-like assets before placing them on slides. Never fake equations with plain body text.

Useful working sizes for the built-in academic style:
- slide title: roughly `24-36 pt`
- cover title: roughly `36-52 pt`
- body text: roughly `18-24 pt`
- references: roughly `11-15 pt`
- equations: use readable math fonts such as `Cambria Math` when native equations are rebuilt

If `style-mode=template` and the chosen `.pptx` defines fonts and theme colors, preserve them. Do not restyle the deck unless the user asks for a different visual direction.

Practical style cues for the built-in academic style:
- titles: `Helvetica`-like sans fonts around `28-30 pt`
- highlighted subsection headers inside the slide body: dark red or blue, bold, visibly separated from the body text
- body: prefer `Helvetica`-like body text around `24-26 pt`; use serif only when a specific equation or literature style requires it
- compact citations: `Helvetica Light`-like `11-12 pt`
- page footer: thin bottom rule, presenter left, page number right

## Citation Rules

- Any text, figure, table, equation, schematic, or claim that is not the user's own work must show a slide-local citation.
- For `group-meeting` decks based on someone else's paper, cite the source on every slide that reproduces or closely adapts a figure, table, equation, or claim. A title-slide citation alone is not enough.
- For `PDF-only` input, automatic citation binding should stay conservative: bind the source paper itself, but do not pretend you have trustworthy figure-to-reference or background-reference binding unless the evidence is explicit.
- Follow the template style: short bracketed references such as `[Author et al., JHEP 04 (2022) 024]` or `[Author et al., arXiv:xxxx.xxxxx]`.
- Put citations near the borrowed object or at the slide bottom when the scope is visually unambiguous.
- If several borrowed elements on one slide come from the same source, one citation block is acceptable only if it clearly covers all of them.
- If a figure is modified, cropped, recolored, or annotated, label it as adapted rather than pretending it is original.
- Do not invent bibliographic details. Use the paper metadata, bibliography, DOI, journal info, or arXiv record.

## Content Compression Rules

- A talk is not a paper. Do not paste the paper section order onto slides.
- Each slide should do one job: motivate, define, explain the setup, explain the method, interpret one key figure, summarize, or critique.
- Every slide should have one spoken takeaway.
- Prefer one main figure/table/equation cluster per slide.
- Do not pack three narrow text columns next to a large figure at `28/26 pt`. If a slide needs a large figure, keep the accompanying commentary to `1-2` short conclusion blocks or split the material across more slides.
- On content slides, prefer short dot-led subheadings plus compact explanatory text instead of boxed mini-cards with tall decorative accents.
- Keep blue emphasis semantic rather than decorative: highlight only a small number of important words or phrases, not whole paragraphs.
- Every generated plan should go through an automatic review-and-optimize pass before final `.pptx` authoring. The review should check report-type completeness, time-vs-slide balance, slide density, citation expectations, presenter metadata, and source-quality risk, then compress or clean slides when that can be done safely.
- The final `.pptx` authoring pass should not trust plan-level review alone. It should run the shared `scripts/render_layout_guard.mjs` check on an `inspect.ndjson` artifact, catch wrapped text boxes whose real rendered height exceeds their nominal box height, enforce boxed-callout containment, and stop export until those collisions are resolved.
- If a paper figure has too many panels, split it across slides or mute the nonessential panels.
- For broad audiences, explain the physical question before showing the formalism.
- For expert audiences, keep the crucial equations but still state what they mean physically.
- If multiple papers are involved, organize by theme and logic, not by publication chronology.

## Time And Slide Planning

Assume speaking time excludes Q&A unless the user says otherwise.

Starting heuristics:
- `conference`: about `0.8-1.1` slides per minute
- `assessment`: about `0.7-1.0` slides per minute
- `group-meeting`: about `0.6-0.9` slides per minute

Reduce slide count by `10-20%` when the talk contains heavy derivations, dense parameter-space plots, or several multi-panel figures that need careful live explanation.

## Report-Type Playbooks

### 1) Conference PPT

Use for one paper or a tightly related set of papers around one theme.

Recommended time split:
- title + outline: `10%`
- background + motivation + literature gap: `20-25%`
- related work / model / setup: `15-20%`
- method + key technical issue: `20-25%`
- core results + physics implications: `25-35%`
- summary + outlook: `10-15%`

Default skeleton:
1. title
2. roadmap using the actual source section arc
3. big-picture motivation
4. section-driven core narrative following the source material in order
5. integrated conclusion and outlook
6. backup slides if needed

Use a broader introduction for mixed audiences. For specialized workshops, shorten background and spend more time on the new idea and the results.

### 2) Assessment / Review PPT

Use for annual review, stage summary, defense-style self-introduction, promotion/assessment, or milestone check.

Recommended time split:
- title + agenda: `5-10%`
- overall achievements dashboard: `30-40%`
- teaching / service / awards: `10-15%`
- representative work highlights: `35-45%`
- future plan / outlook: `10-15%`

The achievements dashboard should usually include:
- paper quantity and quality
- major journals or venues
- funding: amount, source, role, and period
- conferences: invited/oral/poster counts and representative venues
- teaching, supervision, public service, or collaborations

Representative work sections should be simpler than a conference talk:
- 1 slide for background and motivation in plain language
- 1 slide for the core idea or model
- 1-2 slides for the key result and why it matters
- 1 short takeaway slide only if the work is central enough

Prefer charts, timelines, and tables for achievements. Numbers must be traceable to source material.

### 3) Group-Meeting / Journal-Club PPT

Use for presenting someone else's paper PDF or arXiv source to advisors and lab members.

Recommended time split:
- title + why this paper: `10%`
- background + problem statement + paper position: `15-20%`
- model / assumptions / setup: `15-20%`
- method / calculation strategy / data pipeline: `15-20%`
- key figures and tables: `30-40%`
- limitations, caveats, and your critique: `10-15%`
- summary: `5-10%`

Default skeleton:
1. title slide with full paper metadata
2. core question + one-sentence claim
3. roadmap using the paper's actual section logic
4. section-driven narrative following the paper's argument in order
5. figure-driven result slides when the paper needs them
6. what the paper did not solve or what remains unclear
7. final takeaways

Do not simply follow the PDF page order. Follow the paper's logical section arc; only when the source structure is too noisy should you fall back to a generic seminar scaffold.

## Figure And Table Handling

- Every imported figure should come with a spoken explanation of axes, benchmark choice, color meaning, main trend, and physics takeaway.
- If a figure is visually dense, add a companion slide with zoom-in, highlights, or simplified annotation.
- If a table supports only one claim, replace a full-page dump with a short conclusion plus a cropped or reformatted table.
- For result slides with a dominant figure or table, prefer one big visual plus a small number of short interpretive statements, instead of a crowded paper-summary layout.
- If the exported PPTX shows editable-view placeholder dashes or unused master placeholders, remove them before delivering the final deck.
- Crop away irrelevant paper body text before importing a figure or table. The slide should show the plot/table, not a screenshot of half a PDF page.
- Keep captions short and interpretive.
- In group meetings, spend extra effort on the paper's main figures and tables. Those are often the real core of the talk.

## Source Handling

- If arXiv source is available, prefer it for section titles, equations, figure captions, and bibliography.
- A clean Markdown file is the next-best option after TeX/arXiv source, especially if it already contains explicit headings, figure labels, and short figure summaries.
- If only a PDF is available, extract at least: title, abstract or fallback summary, section headings, figure captions, conclusion-like text, and bibliography-like lines.
- Check equations and symbol definitions manually after PDF extraction. PDF math recovery is noisy and should not be trusted blindly.
- PDF-only extraction is the noisiest path for this skill. Expect more cleanup work for abstracts, section headings, and figure-caption detection.
- For PDF-only input, automatic local citations should default to the source paper itself unless a tighter binding is genuinely available.
- For assessment decks, request or infer structured inputs for papers, grants, invited talks, teaching/service, awards, dates, and representative works.
- Prefer the bundled extractor scripts over ad hoc manual parsing when the input is local and well-structured.

## Language Rules

- Match the main language to the audience and the selected style source.
- `language` and `audience` should change the generated slide titles, stock bullets, and explanation style rather than living only in metadata.
- Chinese decks may keep standard technical terms, journal names, and equations in English.
- Do not translate paper titles inside citations unless the user explicitly wants translated references.

## Output Standard

Before exporting the deck, check that:
- the deck follows one coherent style source: either one `.pptx` template family or the built-in academic contract
- the audience and report type are clear from the first two slides
- every slide has one main takeaway
- non-original content is cited locally
- figures are large enough to explain live
- the last section is a short summary/outlook rather than an appendix dump
- the slide count matches the speaking time

When forced to choose between completeness and clarity, choose clarity.
