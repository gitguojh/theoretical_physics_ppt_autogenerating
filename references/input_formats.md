# Input Formats

Use this reference when the deck is an `assessment` PPT or when the source material is noisy and needs normalization before slide planning.

## 1. Assessment JSON

Preferred input format for achievement-focused decks:

```json
{
  "profile": {
    "name": "Your Name",
    "affiliation": "Your University",
    "title": "Stage Review",
    "footer_label": "Your Name (Your University)"
  },
  "papers": [
    {
      "title": "Heavy long-lived coannihilation partner from inelastic Dark Matter model and its signatures at the LHC",
      "journal": "JHEP",
      "year": 2022,
      "status": "published",
      "role": "first author",
      "impact_note": "Representative collider LLP work"
    }
  ],
  "grants": [
    {
      "name": "National Natural Science Foundation",
      "amount": 300000,
      "currency": "CNY",
      "role": "PI",
      "period": "2026-2028"
    }
  ],
  "talks": [
    {
      "venue": "ICHEP",
      "type": "oral",
      "year": 2025,
      "title": "Searching for ULDM at Collider and Gravitational Wave Experiments"
    }
  ],
  "teaching": [
    {
      "item": "Quantum Field Theory TA",
      "year": 2025
    }
  ],
  "service": [
    {
      "item": "Group seminar organizer",
      "year": 2025
    }
  ],
  "representative_works": [
    {
      "title": "Searching for ULDM at Collider and Gravitational Wave Experiments",
      "motivation": "Time-varying signals can reopen parameter space excluded in static searches.",
      "problem": "Existing bounds assume a fixed dark-photon mass.",
      "method": "Recast beam-dump and collider searches including time-dependent mass effects.",
      "result": "Bounds weaken significantly and time-domain analyses recover sensitivity."
    }
  ],
  "future_plan": [
    "Develop simulation-ready predictions for axion-PBH formation.",
    "Expand collider recasts to time-dependent dark sectors."
  ]
}
```

## 2. Paper-Like Inputs

Supported by the scripts:
- local `.pdf`
- local `.md`
- local `.tex`
- directory containing LaTeX sources
- archive of LaTeX sources: `.zip`, `.tar`, `.tar.gz`, `.tgz`

## 3. What The Scripts Extract

For papers and notes, the extractor tries to recover:
- title
- authors
- abstract
- section titles
- figure captions or figure mentions
- conclusion-like text
- citation keys or reference-like lines

For TeX/arXiv-like sources, it can also recover richer formalism structure:
- section-level summaries
- symbol definitions such as `g -> coupling constant`
- equation entries with approximate roles such as defining formalism, analysis engine, or observable/fit relation
- lightweight formalism-chain steps such as `L_int -> Boltzmann evolution for Y -> observable rate R`

For assessment JSON, the extractor validates and normalizes:
- papers
- grants
- talks
- teaching
- service
- representative works
- future plan

## 4. Minimal Fields That Matter Most

If the input is incomplete, prioritize these:
- `conference`: title, motivation, model/setup, method, main result, conclusion
- `group-meeting`: full paper title, abstract, key figures, conclusion
- `assessment`: papers, grants, talks, representative works

## 5. Presenter Metadata

For final deck authoring, presenter identity should be treated as separate metadata from the paper itself.

Preferred sources:
- pass `--presenter-name`, `--presenter-affiliation`, and optionally `--presenter-footer` on the workflow CLI
- or, for `assessment`, put `profile.name`, `profile.affiliation`, and optional `profile.footer_label` in the JSON

The footer label is usually the exact string shown at bottom-left, for example `Name (Affiliation)`.

## 6. Style Inputs

This skill can work in two compatible style modes:
- `builtin`: no `.pptx` template is needed
- `template`: preserve a user-supplied or bundled `.pptx` template

If the user wants a custom visual style, the minimum supported template input is:
- one local `.pptx` file

Recommended workflow for a custom template:
- pass `--style-mode template --template /absolute/path/to/your-template.pptx`
- optionally inspect it first with `scripts/profile_ppt_template.py`
- if convenient, store the `.pptx` in the workspace `templates/` folder, but this is optional rather than required

The template profiler can recover lightweight information such as:
- slide size
- theme fonts
- theme accent colors
- slide master count and layout count

That profile helps planning and rendering hints, but final authoring should still preserve the original template master visually rather than assuming the profile is a perfect semantic reconstruction of the deck.

## 7. Source Preference For Paper-Like Inputs

For the cleanest downstream slide planning:
- best: TeX or arXiv source
- next best: clean Markdown with explicit headings, figure labels, and short summaries
- weakest: PDF only

PDF-only extraction is supported, but section headings, abstracts, and figure-caption detection can be noisy.
That noise also propagates into the automatic review-and-optimize stage, so TeX/arXiv source or a clean Markdown conversion is strongly preferred when available.
For PDF-only input, automatic citations should be interpreted conservatively as source-paper attribution unless a tighter section/figure binding is explicitly available.
