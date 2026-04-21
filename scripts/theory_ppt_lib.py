#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import tarfile
import tempfile
import zipfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # pragma: no cover - depends on local runtime choice
    PdfReader = None


DEFAULT_MINUTES = {
    "conference": 20,
    "assessment": 18,
    "group-meeting": 35,
}

SKILL_ROOT = Path(__file__).resolve().parents[1]
EMU_PER_INCH = 914400
PPTX_XML_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}

SLIDES_PER_MINUTE = {
    "conference": 0.95,
    "assessment": 0.85,
    "group-meeting": 0.75,
}

TEMPLATE_CATALOG = [
    {
        "id": "smpbh-lrd-dpt",
        "file": "templates/SMPBH-LRD-DPT.pptx",
        "language": "en",
        "best_for": ["conference", "group-meeting"],
        "notes": "blue title plus black divider rules, strong academic footer, spacious result slides",
        "style_tags": ["clean", "spacious", "formal", "research"],
    },
    {
        "id": "bsm-atomic-laser",
        "file": "templates/BSM-atomic-laser-1.pptx",
        "language": "en",
        "best_for": ["conference", "group-meeting"],
        "notes": "clean seminar deck, compact references, light background",
        "style_tags": ["clean", "compact", "seminar", "research"],
    },
    {
        "id": "uldm-axion-ucas",
        "file": "templates/ULDM-axion-UCAS-HangZhou.pptx",
        "language": "en",
        "best_for": ["conference"],
        "notes": "long multi-work thematic research talk",
        "style_tags": ["long-form", "research", "theme-driven"],
    },
    {
        "id": "axion-domain-wall",
        "file": "templates/Axion-Domain-Wall-and-PBH.pptx",
        "language": "en",
        "best_for": ["conference", "group-meeting"],
        "notes": "compact single-topic research talk",
        "style_tags": ["compact", "research", "single-topic"],
    },
    {
        "id": "llp-defense-zh",
        "file": "templates/chinese-defense-template.pptx",
        "language": "zh",
        "best_for": ["assessment", "conference"],
        "notes": "formal Chinese defense and review style",
        "style_tags": ["formal", "brand-heavy", "defense"],
    },
]

BUILTIN_STYLE_PROFILE = {
    "id": "builtin-academic-blue-red",
    "file": "builtin:academic-blue-red",
    "language": "multi",
    "best_for": ["conference", "assessment", "group-meeting"],
    "notes": "template-free academic research style with blue title, black divider rules, PKU-red subsection headings, and academic footer",
    "style_tags": ["builtin", "clean", "formal", "research", "template-free"],
    "mode": "builtin",
    "source": "builtin-style",
    "template_required": False,
}

BLUE_EMPHASIS_COLOR = "#1F5FBF"
TITLE_BLUE = "#1E64C8"
PKU_RED = "#8B1E3F"

SCIENTIFIC_EMPHASIS_PHRASES = (
    "effective field theory",
    "symmetry breaking",
    "renormalization group",
    "beta function",
    "partition function",
    "correlation function",
    "mass matrix",
    "mixing angle",
    "coupling constant",
    "vacuum structure",
    "order parameter",
    "equation of state",
    "critical temperature",
    "ground state",
    "boundary condition",
    "spectral function",
    "transport coefficient",
    "topological sector",
    "nonperturbative effect",
    "parameter space",
    "benchmark point",
    "signal region",
    "event rate",
    "cross section",
    "likelihood analysis",
    "phase transition",
    "phase diagram",
    "vacuum energy",
    "scalar potential",
    "gravitational waves",
    "dark matter",
)

EMPHASIS_STOPWORDS = {
    "abstract",
    "agenda",
    "analysis",
    "appendix",
    "background",
    "backup",
    "benchmark",
    "claim",
    "closing",
    "comparison",
    "conference",
    "conclusion",
    "conclusions",
    "context",
    "core",
    "critique",
    "discussion",
    "fig",
    "figure",
    "figures",
    "future",
    "funding",
    "group",
    "impact",
    "introduction",
    "journal",
    "limitations",
    "main",
    "method",
    "methods",
    "model",
    "motivation",
    "opening",
    "outlook",
    "overview",
    "paper",
    "plan",
    "plain",
    "prerequisites",
    "problem",
    "questions",
    "research",
    "results",
    "review",
    "roadmap",
    "service",
    "setup",
    "status",
    "summary",
    "takeaways",
    "teaching",
    "this",
    "talks",
    "why",
    "work",
}

SECTION_ALIASES = {
    "opening": ("opening", "agenda", "roadmap", "目录", "提纲"),
    "agenda": ("agenda", "roadmap", "目录", "提纲"),
    "motivation": ("motivation", "why this paper", "why this problem", "为什么讲这篇文章", "为什么这个问题重要"),
    "why this paper": ("why this paper", "why this problem", "为什么讲这篇文章", "为什么这个问题重要"),
    "background": ("background", "prerequisites", "context", "plain language", "预备知识", "上下文", "直白语言", "直白"),
    "plain language": ("plain language", "paper claim in plain language", "用直白语言讲论文主张", "直白语言"),
    "setup": ("setup", "model", "formalism", "framework", "scenario", "设定", "模型", "形式", "formalism"),
    "method": ("method", "methods", "analysis", "strategy", "pipeline", "derivation", "simulation", "calculation", "recast", "方法", "分析", "推导"),
    "results": ("results", "figure", "table", "observable", "constraint", "signal", "phenomenology", "结果", "图", "表", "可观测量"),
    "limitations": ("limitations", "open questions", "critique", "caveat", "局限", "开放问题", "批判", "问题"),
    "summary": ("summary", "takeaways", "outlook", "closing", "总结", "展望", "要点"),
    "takeaways": ("takeaways", "summary", "总结要点", "总结"),
    "publications": ("publications", "research output", "论文", "科研产出"),
    "funding": ("funding", "grants", "项目", "经费"),
    "talks": ("talks", "teaching", "service", "报告", "教学", "服务"),
    "future": ("future", "future plan", "outlook", "未来计划", "展望"),
}

SOURCE_SECTION_ROLE_HINTS = {
    "background": (
        "abstract",
        "introduction",
        "motivation",
        "background",
        "preliminar",
        "preliminary",
        "context",
        "overview",
        "problem",
    ),
    "setup": (
        "model",
        "setup",
        "framework",
        "formalism",
        "lagrangian",
        "hamiltonian",
        "action",
        "effective theory",
        "operator basis",
        "notation",
        "kinematics",
    ),
    "method": (
        "method",
        "methods",
        "analysis",
        "derivation",
        "proof",
        "matching",
        "renormalization",
        "evolution",
        "simulation",
        "numerical procedure",
        "calculation",
        "algorithm",
        "construction",
        "solution",
    ),
    "results": (
        "result",
        "results",
        "phenomenology",
        "application",
        "applications",
        "signal",
        "observable",
        "constraints",
        "spectra",
        "phase diagram",
        "numerics",
        "discussion",
    ),
    "limitations": (
        "caveat",
        "uncertainty",
        "robustness",
        "assumption",
        "limitation",
    ),
    "summary": (
        "conclusion",
        "conclusions",
        "summary",
        "outlook",
    ),
}

FIGURE_LABEL_PATTERN = re.compile(r"^(fig(?:ure)?\.?\s*\d+|table\s+\d+)\b", flags=re.IGNORECASE)
CANONICAL_SECTION_LABELS = {
    "introduction": "Introduction",
    "background": "Background",
    "model setup": "Model Setup",
    "model": "Model",
    "setup": "Setup",
    "method": "Method",
    "methods": "Methods",
    "analysis": "Analysis",
    "result": "Results",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "conclusions": "Conclusions",
    "outlook": "Outlook",
    "appendix": "Appendix",
}

LATEX_SYMBOL_ALIASES = {
    "alpha": "alpha",
    "beta": "beta",
    "gamma": "gamma",
    "delta": "delta",
    "epsilon": "epsilon",
    "varepsilon": "epsilon",
    "zeta": "zeta",
    "eta": "eta",
    "theta": "theta",
    "vartheta": "theta",
    "iota": "iota",
    "kappa": "kappa",
    "lambda": "lambda",
    "mu": "mu",
    "nu": "nu",
    "xi": "xi",
    "pi": "pi",
    "varpi": "pi",
    "rho": "rho",
    "sigma": "sigma",
    "tau": "tau",
    "upsilon": "upsilon",
    "phi": "phi",
    "varphi": "phi",
    "chi": "chi",
    "psi": "psi",
    "omega": "omega",
}

DEFINITION_SIGNAL_HINTS = (
    "lagrangian",
    "operator",
    "potential",
    "coupling",
    "field",
    "mass",
    "rate",
    "density",
    "cross section",
    "width",
    "mixing",
    "observable",
    "benchmark",
    "parameter",
    "temperature",
    "abundance",
    "scale",
    "background",
)

DEFINITION_NOISE_HINTS = (
    "earlier studies",
    "previous work",
    "related work",
    "in this talk",
    "this talk",
    "literature",
    "for a review",
    "for reviews",
)


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_lines(text: str) -> list[str]:
    return [clean_whitespace(line) for line in (text or "").splitlines() if clean_whitespace(line)]


def _is_zh(language: str) -> bool:
    return (language or "").lower().startswith("zh")


def _lt(language: str, en: str, zh: str) -> str:
    return zh if _is_zh(language) else en


def _audience_bucket(audience: str) -> str:
    lowered = clean_whitespace(audience).lower()
    if any(token in lowered for token in ("broad", "general", "non-expert", "beginner")):
        return "broad"
    if "mixed" in lowered:
        return "mixed"
    return "experts"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text or "").strip("-").lower()
    return slug or "deck"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_catalog_template_path(item: dict[str, Any]) -> Path:
    return (SKILL_ROOT / str(item.get("file", ""))).resolve()


def _catalog_item_with_path(item: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(item)
    payload["resolved_file"] = str(_resolve_catalog_template_path(item))
    payload["template_required"] = True
    payload.setdefault("mode", "template")
    payload.setdefault("source", "bundled-template")
    return payload


def _available_catalog_templates() -> list[dict[str, Any]]:
    return [item for item in TEMPLATE_CATALOG if _resolve_catalog_template_path(item).exists()]


def _ppt_color_value(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    srgb = element.find("a:srgbClr", PPTX_XML_NS)
    if srgb is not None and srgb.get("val"):
        return f"#{srgb.get('val').upper()}"
    sys = element.find("a:sysClr", PPTX_XML_NS)
    if sys is not None and sys.get("lastClr"):
        return f"#{sys.get('lastClr').upper()}"
    scheme = element.find("a:schemeClr", PPTX_XML_NS)
    if scheme is not None and scheme.get("val"):
        return scheme.get("val", "")
    return None


def _extract_pptx_theme_profile(template_path: Path) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "fonts": {},
        "colors": {},
        "slide_size": {},
        "master_count": 0,
        "layout_count": 0,
    }
    with zipfile.ZipFile(template_path) as archive:
        names = archive.namelist()
        profile["master_count"] = len(
            [name for name in names if name.startswith("ppt/slideMasters/slideMaster") and name.endswith(".xml")]
        )
        profile["layout_count"] = len(
            [name for name in names if name.startswith("ppt/slideLayouts/slideLayout") and name.endswith(".xml")]
        )
        if "ppt/presentation.xml" in names:
            root = ET.fromstring(archive.read("ppt/presentation.xml"))
            size = root.find("p:sldSz", PPTX_XML_NS)
            if size is not None:
                cx = int(size.get("cx", "0") or 0)
                cy = int(size.get("cy", "0") or 0)
                if cx and cy:
                    profile["slide_size"] = {
                        "cx": cx,
                        "cy": cy,
                        "width_in": round(cx / EMU_PER_INCH, 2),
                        "height_in": round(cy / EMU_PER_INCH, 2),
                    }
        theme_name = next((name for name in names if name.startswith("ppt/theme/theme") and name.endswith(".xml")), None)
        if theme_name:
            root = ET.fromstring(archive.read(theme_name))
            profile["theme_file"] = theme_name
            major_latin = root.find(".//a:fontScheme/a:majorFont/a:latin", PPTX_XML_NS)
            minor_latin = root.find(".//a:fontScheme/a:minorFont/a:latin", PPTX_XML_NS)
            if major_latin is not None and major_latin.get("typeface"):
                profile["fonts"]["major_latin"] = major_latin.get("typeface", "")
            if minor_latin is not None and minor_latin.get("typeface"):
                profile["fonts"]["minor_latin"] = minor_latin.get("typeface", "")
            color_scheme = root.find(".//a:clrScheme", PPTX_XML_NS)
            if color_scheme is not None:
                for tag in ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6"):
                    color = _ppt_color_value(color_scheme.find(f"a:{tag}", PPTX_XML_NS))
                    if color:
                        profile["colors"][tag] = color
    return profile


def inspect_template_pptx(template_path: str | Path, deck_type: str, language: str) -> dict[str, Any]:
    resolved = Path(template_path).expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"Template file does not exist: {resolved}")
    if resolved.suffix.lower() != ".pptx":
        raise ValueError(f"Custom template must be a .pptx file: {resolved}")
    profile: dict[str, Any] = {}
    notes = "user-provided PowerPoint template; preserve its master, theme, and page furniture during final authoring"
    try:
        profile = _extract_pptx_theme_profile(resolved)
        font_bits = [
            clean_whitespace(str(profile.get("fonts", {}).get("major_latin", ""))),
            clean_whitespace(str(profile.get("fonts", {}).get("minor_latin", ""))),
        ]
        font_bits = [item for item in font_bits if item]
        if font_bits:
            notes += f"; detected theme fonts: {', '.join(font_bits[:2])}"
        if profile.get("master_count"):
            notes += f"; detected {profile.get('master_count')} slide master(s)"
    except Exception as exc:  # pragma: no cover - defensive for malformed PPTX
        profile = {"profile_error": str(exc)}
        notes += "; theme parsing failed, so preserve the file as-is and inspect visually"
    return {
        "id": f"custom-{slugify(resolved.stem)}",
        "file": str(resolved),
        "resolved_file": str(resolved),
        "display_name": resolved.name,
        "language": (language or "en").lower(),
        "best_for": [deck_type],
        "notes": notes,
        "style_tags": ["custom-template", "user-template", "pptx", "research"],
        "mode": "template",
        "source": "user-template",
        "template_required": True,
        "profile": profile,
    }


def choose_template(
    deck_type: str,
    language: str,
    preferred_template: str | None = None,
    style_mode: str = "auto",
) -> dict[str, Any]:
    normalized_mode = clean_whitespace(style_mode or "auto").lower() or "auto"
    if normalized_mode not in {"auto", "builtin", "template"}:
        raise ValueError(f"Unsupported style mode: {style_mode}")

    if normalized_mode == "builtin":
        builtin = deepcopy(BUILTIN_STYLE_PROFILE)
        builtin["language"] = (language or "en").lower()
        builtin["best_for"] = [deck_type]
        builtin["notes"] = f"{builtin['notes']}; no external .pptx template is required"
        return builtin

    if preferred_template:
        preferred_path = Path(preferred_template).expanduser()
        preferred_name = preferred_path.name
        for item in TEMPLATE_CATALOG:
            if item["file"] == preferred_template or Path(item["file"]).name == preferred_name:
                catalog_item = _catalog_item_with_path(item)
                if Path(catalog_item["resolved_file"]).exists():
                    try:
                        catalog_item["profile"] = _extract_pptx_theme_profile(Path(catalog_item["resolved_file"]))
                    except Exception as exc:  # pragma: no cover - defensive for malformed PPTX
                        catalog_item["profile"] = {"profile_error": str(exc)}
                return catalog_item
        if preferred_path.exists():
            return inspect_template_pptx(preferred_path, deck_type=deck_type, language=language)
        if normalized_mode == "auto":
            builtin = deepcopy(BUILTIN_STYLE_PROFILE)
            builtin["language"] = (language or "en").lower()
            builtin["best_for"] = [deck_type]
            builtin["notes"] = f"{builtin['notes']}; requested template was not found, so the planner fell back to the built-in style"
            builtin["fallback_reason"] = f"Requested template not found: {preferred_template}"
            return builtin
        raise ValueError(f"Unknown template: {preferred_template}")

    available_catalog = _available_catalog_templates()
    if normalized_mode == "template":
        if not available_catalog:
            raise ValueError("Template mode requires a .pptx template, but no bundled template files are available. Pass --template /path/to/your-template.pptx or switch to --style-mode builtin.")
        catalog = [item for item in available_catalog if deck_type in item["best_for"] and item["language"] == (language or "en").lower()]
        if not catalog:
            catalog = [item for item in available_catalog if item["language"] == (language or "en").lower()]
        if not catalog:
            catalog = [item for item in available_catalog if deck_type in item["best_for"]]
        if not catalog:
            catalog = available_catalog
    else:
        catalog = available_catalog

    if catalog:
        desired_tags = {
            "conference": {"clean", "research", "formal"},
            "group-meeting": {"clean", "spacious", "research"},
            "assessment": {"formal", "brand-heavy", "defense"},
        }.get(deck_type, {"research"})

        def score(item: dict[str, Any]) -> tuple[int, int, int]:
            tags = set(item.get("style_tags", []))
            return (
                len(desired_tags & tags),
                1 if item.get("language") == (language or "en").lower() else 0,
                len(item.get("best_for", [])),
            )

        chosen = _catalog_item_with_path(sorted(catalog, key=score, reverse=True)[0])
        try:
            chosen["profile"] = _extract_pptx_theme_profile(Path(chosen["resolved_file"]))
        except Exception as exc:  # pragma: no cover - defensive for malformed PPTX
            chosen["profile"] = {"profile_error": str(exc)}
        return chosen

    builtin = deepcopy(BUILTIN_STYLE_PROFILE)
    builtin["language"] = (language or "en").lower()
    builtin["best_for"] = [deck_type]
    builtin["notes"] = f"{builtin['notes']}; no bundled or user-supplied template was available"
    builtin["fallback_reason"] = "No usable .pptx template was available."
    return builtin


def estimate_slide_count(deck_type: str, minutes: int | float | None) -> int:
    talk_minutes = int(minutes or DEFAULT_MINUTES[deck_type])
    raw = talk_minutes * SLIDES_PER_MINUTE[deck_type]
    floor = {"conference": 12, "assessment": 10, "group-meeting": 14}[deck_type]
    return max(floor, int(round(raw)))


def latex_to_text(text: str) -> str:
    value = text or ""
    value = re.sub(r"(?<!\\)%.*", "", value)
    value = re.sub(r"\$([^$]+)\$", r"\1", value)
    for _ in range(6):
        value = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?{([^{}]*)}", r"\1", value)
    value = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", value)
    value = value.replace("\\", " ")
    value = value.replace("~", " ")
    value = value.replace("{", " ").replace("}", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _extract_quoted(text: str, start: int) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != '"':
        return None
    out: list[str] = []
    escaped = False
    for idx in range(start + 1, len(text)):
        char = text[idx]
        if escaped:
            out.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            return "".join(out), idx + 1
        out.append(char)
    return None


def _extract_bib_field(entry_body: str, field: str) -> str | None:
    match = re.search(rf"\b{re.escape(field)}\s*=\s*", entry_body, flags=re.IGNORECASE)
    if not match:
        return None
    idx = match.end()
    while idx < len(entry_body) and entry_body[idx].isspace():
        idx += 1
    if idx >= len(entry_body):
        return None
    if entry_body[idx] == "{":
        found = _extract_braced(entry_body, idx)
        return found[0] if found else None
    if entry_body[idx] == '"':
        found = _extract_quoted(entry_body, idx)
        return found[0] if found else None
    end = idx
    while end < len(entry_body) and entry_body[end] not in ",\n":
        end += 1
    return entry_body[idx:end].strip()


def _short_author_list(raw: str) -> str:
    parts = [clean_whitespace(latex_to_text(part)) for part in re.split(r"\s+\band\b\s+", raw or "") if clean_whitespace(latex_to_text(part))]
    if not parts:
        return ""

    def surname(name: str) -> str:
        if "," in name:
            return clean_whitespace(name.split(",", 1)[0])
        return clean_whitespace(name.split()[-1])

    if len(parts) == 1:
        return surname(parts[0])
    return f"{surname(parts[0])} et al."


def _infer_arxiv_id_from_text(text: str) -> str:
    match = re.search(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b", text or "")
    return match.group(1) if match else ""


def _format_bibliography_entry(fields: dict[str, str], fallback_key: str = "") -> str:
    author = _short_author_list(fields.get("author", ""))
    title = clean_whitespace(latex_to_text(fields.get("title", "")))
    journal = clean_whitespace(latex_to_text(fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""))
    year = clean_whitespace(latex_to_text(fields.get("year", "")))
    eprint = clean_whitespace(latex_to_text(fields.get("eprint", "")))
    archive_prefix = clean_whitespace(latex_to_text(fields.get("archiveprefix", ""))).lower()
    doi = clean_whitespace(latex_to_text(fields.get("doi", "")))
    parts: list[str] = []
    if author:
        parts.append(author)
    if journal:
        parts.append(journal + (f" ({year})" if year else ""))
    elif title:
        parts.append(title)
        if year:
            parts.append(f"({year})")
    elif year:
        parts.append(f"({year})")
    if eprint:
        parts.append(f"arXiv:{eprint}" if archive_prefix == "arxiv" or re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", eprint) else eprint)
    elif doi and not journal:
        parts.append(f"DOI:{doi}")
    formatted = clean_whitespace(", ".join(part for part in parts if part))
    return formatted or fallback_key


def _parse_bibtex_catalog(text: str) -> dict[str, str]:
    catalog: dict[str, str] = {}
    pos = 0
    while True:
        match = re.search(r"@(\w+)\s*{\s*([^,\s]+)\s*,", text[pos:], flags=re.IGNORECASE)
        if not match:
            break
        start = pos + match.start()
        brace_start = text.find("{", start)
        if brace_start < 0:
            break
        depth = 0
        end = brace_start
        while end < len(text):
            char = text[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end += 1
                    break
            end += 1
        key = clean_whitespace(match.group(2))
        entry_body = text[match.end() + pos:end - 1]
        formatted = _format_bibliography_entry(
            {
                "author": _extract_bib_field(entry_body, "author") or "",
                "title": _extract_bib_field(entry_body, "title") or "",
                "journal": _extract_bib_field(entry_body, "journal") or "",
                "booktitle": _extract_bib_field(entry_body, "booktitle") or "",
                "publisher": _extract_bib_field(entry_body, "publisher") or "",
                "year": _extract_bib_field(entry_body, "year") or "",
                "eprint": _extract_bib_field(entry_body, "eprint") or "",
                "archiveprefix": _extract_bib_field(entry_body, "archiveprefix") or "",
                "doi": _extract_bib_field(entry_body, "doi") or "",
            },
            fallback_key=key,
        )
        if formatted:
            catalog[key] = formatted
        pos = end
    return catalog


def _parse_bibitem_catalog(text: str) -> dict[str, str]:
    catalog: dict[str, str] = {}
    pattern = re.compile(r"\\bibitem(?:\[[^\]]*\])?{([^{}]+)}(.*?)(?=\\bibitem(?:\[[^\]]*\])?{|\\end{thebibliography}|$)", flags=re.DOTALL)
    for match in pattern.finditer(text):
        key = clean_whitespace(match.group(1))
        value = clean_whitespace(latex_to_text(match.group(2)))
        if value:
            catalog[key] = value[:220]
    return catalog


def _extract_citation_keys(text: str) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\\cite\w*\*?(?:\[[^\]]*\])?{([^{}]+)}", text):
        for raw_key in match.group(1).split(","):
            key = clean_whitespace(raw_key)
            if key and key not in seen:
                keys.append(key)
                seen.add(key)
    return keys


def _latex_math_to_text(text: str) -> str:
    value = text or ""
    previous = None
    while value != previous:
        previous = value
        value = re.sub(
            r"\\(?:mathcal|mathrm|mathbf|mathbb|text|operatorname|boldsymbol)\*?{([^{}]+)}",
            r"\1",
            value,
        )
        value = re.sub(r"\\(?:bar|hat|tilde|vec|overline|underline)\*?{([^{}]+)}", r"\1", value)
        value = re.sub(
            r"\\frac{([^{}]+)}{([^{}]+)}",
            lambda match: f"{_latex_math_to_text(match.group(1))}/{_latex_math_to_text(match.group(2))}",
            value,
        )
        value = re.sub(
            r"_\{([^{}]+)}",
            lambda match: "_" + _latex_math_to_text(match.group(1)),
            value,
        )
        value = re.sub(
            r"\^\{([^{}]+)}",
            lambda match: "^" + _latex_math_to_text(match.group(1)),
            value,
        )
        value = re.sub(r"\\([A-Za-z]+)", lambda match: LATEX_SYMBOL_ALIASES.get(match.group(1).lower(), match.group(1)), value)
    value = latex_to_text(value)
    value = re.sub(r"\b([A-Za-z]+)_rm\s+([A-Za-z0-9]+)\b", r"\1_\2", value)
    value = re.sub(r"\s*\^\s*[A-Za-z0-9_+\-./]+", "", value)
    value = re.sub(r"\s*/\s*", "/", value)
    value = re.sub(r"\s+", " ", value)
    return clean_whitespace(value)


def _clean_definition_candidate(text: str) -> str:
    value = text or ""
    value = re.sub(r"(?<!\\)%.*", "", value)
    value = re.sub(r"\\label{[^{}]+}", " ", value)
    value = re.sub(r"\\(?:cite\w*\*?|ref|eqref|autoref|cref|Cref)\*?(?:\[[^\]]*\])?{[^{}]+}", " ", value)
    value = re.sub(
        r"\\begin{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*|eqnarray\*?)}(.*?)\\end{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*|eqnarray\*?)}",
        lambda match: " " + _latex_math_to_text(match.group(1)) + " ",
        value,
        flags=re.DOTALL,
    )
    value = re.sub(r"\\(?:begin|end){[^{}]+}", " ", value)
    value = re.sub(r"\\\[(.*?)\\\]", lambda match: " " + _latex_math_to_text(match.group(1)) + " ", value, flags=re.DOTALL)
    value = re.sub(r"\$\$(.*?)\$\$", lambda match: " " + _latex_math_to_text(match.group(1)) + " ", value, flags=re.DOTALL)
    value = re.sub(r"\$([^$]+)\$", lambda match: _latex_math_to_text(match.group(1)), value)
    value = latex_to_text(value)
    value = re.sub(r"\b(?:eq|fig|sec|tab):[\w:-]+\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b[a-z][a-z0-9_-]*20\d{2}[a-z]?\b", " ", value)
    value = re.sub(r"\b(?:defined|define)\s+by\s+equation\b", lambda match: match.group(0).replace(" equation", ""), value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:as|from)\s+equation\b", lambda match: match.group(0).replace(" equation", ""), value, flags=re.IGNORECASE)
    value = re.sub(r"\bequation\b", " ", value, flags=re.IGNORECASE)
    for label in CANONICAL_SECTION_LABELS.values():
        value = re.sub(rf"^{re.escape(label)}\s+", "", value, flags=re.IGNORECASE)
    value = clean_whitespace(value.strip(" .;,:"))
    value = re.sub(r"\b([A-Za-z])_$", r"\1", value)
    value = re.sub(r"\b([A-Za-z]+)\s+g_$", r"\1", value)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    return value


def _looks_like_natural_language_snippet(text: str) -> bool:
    cleaned = clean_whitespace(text)
    if not cleaned:
        return False
    alpha_words = re.findall(r"[A-Za-z]{3,}", cleaned)
    if len(alpha_words) < 4:
        return False
    symbol_count = len(re.findall(r"[=<>≈≤≥±*/_^]", cleaned))
    if symbol_count > max(4, len(alpha_words)):
        return False
    if re.search(r"\b(?:as|is|are|denotes|represents|stands for|defined by)\s+[A-Za-z](?:\s+[A-Za-z0-9])?$", cleaned, flags=re.IGNORECASE):
        return False
    trailing_tokens = cleaned.split()[-3:]
    if trailing_tokens and sum(1 for token in trailing_tokens if len(token) <= 2 and token.isalpha()) >= 2:
        return False
    return True


def _definition_priority(text: str) -> int:
    lowered = text.lower()
    if any(token in lowered for token in DEFINITION_NOISE_HINTS):
        return -1
    score = 0
    if re.search(r"\b(where|denote|denotes|represents|stands for)\b", lowered):
        score += 4
    if re.search(r"\b(define|defined)\b", lowered):
        score += 2
    if any(token in lowered for token in DEFINITION_SIGNAL_HINTS):
        score += 2
    if re.search(r"\b[a-z]+_[a-z0-9]+\b", lowered):
        score += 1
    if len(text) > 180:
        score -= 1
    return score


def _extract_definition_snippets(text: str, limit: int = 6) -> list[str]:
    raw = re.sub(r"(?<!\\)%.*", "", text or "")
    raw = raw.replace("\n", " ")
    snippets: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for index, sentence in enumerate(re.split(r"(?<=[.!?;])\s+", raw)):
        cleaned = _clean_definition_candidate(sentence)
        lowered = cleaned.lower()
        if len(cleaned) < 30 or len(cleaned) > 220:
            continue
        if not _looks_like_natural_language_snippet(cleaned):
            continue
        if not re.search(r"\b(where|define|defined|denote|denotes|stands for|represents)\b", lowered):
            continue
        if lowered in seen:
            continue
        priority = _definition_priority(cleaned)
        if priority < 0:
            continue
        snippets.append((priority, index, cleaned))
        seen.add(lowered)
    snippets.sort(key=lambda item: (-item[0], item[1]))
    return [text for _, _, text in snippets[:limit]]


def _inline_math_spans(text: str) -> list[str]:
    spans: list[str] = []
    spans.extend(match.group(1) for match in re.finditer(r"\$([^$]+)\$", text))
    spans.extend(match.group(1) for match in re.finditer(r"\\\((.*?)\\\)", text))
    return spans


def _clean_symbol_name(text: str) -> str:
    value = _latex_math_to_text(text or "")
    value = re.sub(r"\s+", "", value)
    value = value.strip(".,;:()[]{}")
    if not value:
        return ""
    if len(value) > 24:
        return ""
    if any(token in value for token in ("=", "<", ">", "/", "+", "approx")):
        return ""
    if not re.search(r"[A-Za-z]", value):
        return ""
    return value


def _clean_symbol_meaning(text: str) -> str:
    value = _clean_section_summary_candidate(text)
    value = re.sub(r"^(?:the|a|an)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:respectively|respectively\.)$", "", value, flags=re.IGNORECASE)
    value = clean_whitespace(value.strip(" ,;:."))
    if len(value) < 4 or len(value) > 120:
        return ""
    return value


def _extract_symbol_entries_from_text(text: str, section_title: str, limit: int = 12) -> list[dict[str, str]]:
    raw = re.sub(r"(?<!\\)%.*", "", text or "")
    raw = raw.replace("\n", " ")
    sentences = [clean_whitespace(item) for item in re.split(r"(?<=[.!?;])\s+", raw) if clean_whitespace(item)]
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    inline_pattern = re.compile(r"(?P<math>\$[^$]+\$|\\\((?:.*?)\\\))")
    local_meaning_pattern = re.compile(
        r"^\s*(?:is|are|denotes?|represents?|stands for|be)\s+(?P<meaning>.*?)(?=(?:\s+and\s+(?:\$|\\\())|[.;,]|$)",
        flags=re.IGNORECASE,
    )
    denote_pattern = re.compile(
        r"(?:we\s+denote(?:\s+by)?|let)\s+(?P<math>\$[^$]+\$|\\\((?:.*?)\\\))\s+(?:as\s+|be\s+)?(?P<meaning>.*?)(?=(?:\s+and\s+(?:\$|\\\())|[.;,]|$)",
        flags=re.IGNORECASE,
    )
    for sentence in sentences:
        if len(entries) >= limit:
            break
        for match in denote_pattern.finditer(sentence):
            symbol = _clean_symbol_name(match.group("math"))
            meaning = _clean_symbol_meaning(match.group("meaning"))
            if not symbol or not meaning:
                continue
            key = (symbol.lower(), meaning.lower())
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "symbol": symbol,
                    "meaning": meaning,
                    "section": clean_whitespace(section_title),
                    "evidence": _compress_key_point(_clean_definition_candidate(sentence), 140),
                }
            )
            if len(entries) >= limit:
                break
        for match in inline_pattern.finditer(sentence):
            symbol = _clean_symbol_name(match.group("math"))
            if not symbol:
                continue
            after = sentence[match.end():]
            local = local_meaning_pattern.match(after)
            if not local:
                continue
            meaning = _clean_symbol_meaning(local.group("meaning"))
            if not meaning:
                continue
            key = (symbol.lower(), meaning.lower())
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "symbol": symbol,
                    "meaning": meaning,
                    "section": clean_whitespace(section_title),
                    "evidence": _compress_key_point(_clean_definition_candidate(sentence), 140),
                }
            )
            if len(entries) >= limit:
                break
    return entries[:limit]


def _classify_equation_role(equation: str, label: str, context: str, section_title: str) -> str:
    haystack = " ".join((equation or "", label or "", context or "", section_title or "")).lower()
    if any(token in haystack for token in ("boltzmann", "rg", "renormalization", "matching", "beta function", "likelihood", "chi2", "logl")):
        return "analysis-engine"
    if any(token in haystack for token in ("lagrang", "potential", "hamilton", "action")):
        return "defining-formalism"
    if any(token in haystack for token in ("constraint", "bound", "limit", "confidence level")):
        return "constraint"
    if any(token in haystack for token in ("cross section", "event rate", "spectrum", "observable", "branching", "decay width", "mass matrix", "yield", "abundance")):
        return "observable-or-fit"
    if any(token in haystack for token in ("define", "denote", "where", "normalization")):
        return "definition"
    section_role = _classify_source_section_role(section_title)
    if section_role == "setup":
        return "defining-formalism"
    if section_role == "method":
        return "analysis-engine"
    if section_role == "results":
        return "observable-or-fit"
    return "formalism"


def _equation_role_explainer(role: str, language: str) -> str:
    mapping = {
        "defining-formalism": _lt(language, "This is a defining formalism equation; keep it visible as the anchor of the setup.", "这是定义性 formalism 方程，应作为设定页的锚点保留下来。"),
        "analysis-engine": _lt(language, "This equation drives the analysis or derivation; explain what step it advances.", "这条方程驱动分析或推导，应说明它推进了哪一步。"),
        "observable-or-fit": _lt(language, "This equation links the formalism to observables or fit quantities.", "这条方程把 formalism 和可观测量或拟合量连接起来。"),
        "constraint": _lt(language, "This equation encodes a bound, constraint, or decision boundary.", "这条方程编码了一个限制、约束或判据。"),
        "definition": _lt(language, "This equation mainly defines notation or normalization.", "这条方程主要在定义记号或归一化。"),
        "formalism": _lt(language, "Use this equation as a compact formal anchor for the section.", "把这条方程作为这一节的形式锚点。"),
    }
    return mapping.get(role, mapping["formalism"])


def _clean_section_summary_candidate(text: str) -> str:
    value = text or ""
    value = re.sub(r"(?<!\\)%.*", "", value)
    value = re.sub(r"\\label{[^{}]+}", " ", value)
    value = re.sub(r"\\(?:cite\w*\*?|ref|eqref|autoref|cref|Cref)\*?(?:\[[^\]]*\])?{[^{}]+}", " ", value)
    value = re.sub(r"\\begin{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*|eqnarray\*?)}.*?\\end{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*|eqnarray\*?)}", " ", value, flags=re.DOTALL)
    value = re.sub(r"\\\[(.*?)\\\]", " ", value, flags=re.DOTALL)
    value = re.sub(r"\$\$(.*?)\$\$", " ", value, flags=re.DOTALL)
    value = re.sub(r"\$([^$]+)\$", " ", value)
    value = latex_to_text(value)
    value = re.sub(r"\b[a-z][a-z0-9_-]*20\d{2}[a-z]?\b", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\bas\s*[.]\s*$", "", value, flags=re.IGNORECASE)
    return clean_whitespace(value.strip(" .;,:"))


def _extract_section_summary_snippets(text: str, limit: int = 2) -> list[str]:
    raw = _clean_section_summary_candidate(text)
    if not raw:
        return []
    candidates: list[str] = []
    for sentence in re.split(r"(?<=[.!?;])\s+", raw):
        cleaned = clean_whitespace(sentence)
        if len(cleaned) < 40 or len(cleaned) > 220:
            continue
        if not _looks_like_natural_language_snippet(cleaned):
            continue
        if cleaned.lower().startswith(("figure ", "fig. ", "table ", "references", "acknowledg")):
            continue
        candidates.append(cleaned.rstrip(" ,;"))
        if len(candidates) >= limit:
            break
    return _dedupe_preserving_order(candidates)[:limit]


def _classify_source_section_role(title: str) -> str:
    lowered = clean_whitespace(title).lower()
    for role, keywords in SOURCE_SECTION_ROLE_HINTS.items():
        if any(keyword in lowered for keyword in keywords):
            return role
    return "core"


def _extract_bibliography_catalog(search_root: Path, merged_tex: str) -> dict[str, str]:
    catalog: dict[str, str] = {}
    root = search_root if search_root.is_dir() else search_root.parent
    for bib_path in sorted(root.rglob("*.bib")):
        parsed = _parse_bibtex_catalog(bib_path.read_text(encoding="utf-8", errors="ignore"))
        catalog.update({key: value for key, value in parsed.items() if value})
    for bbl_path in sorted(root.rglob("*.bbl")):
        parsed = _parse_bibitem_catalog(bbl_path.read_text(encoding="utf-8", errors="ignore"))
        for key, value in parsed.items():
            catalog.setdefault(key, value)
    inline_match = re.search(r"\\begin{thebibliography}.*?\\end{thebibliography}", merged_tex, flags=re.DOTALL)
    if inline_match:
        parsed = _parse_bibitem_catalog(inline_match.group(0))
        for key, value in parsed.items():
            catalog.setdefault(key, value)
    return catalog


def _build_primary_citation(source: dict[str, Any]) -> str:
    title = clean_whitespace(str(source.get("title", "")))
    authors = source.get("authors", [])
    author_part = ""
    if isinstance(authors, list) and authors:
        author_part = _short_author_list(" and ".join(str(item) for item in authors))
    if not author_part:
        metadata = source.get("metadata", {})
        if isinstance(metadata, dict):
            author_line = clean_whitespace(str(metadata.get("pdf_author_line", "")))
            if author_line:
                author_part = _short_author_list(author_line)
    input_path = clean_whitespace(str(source.get("input_path", "")))
    arxiv_id = _infer_arxiv_id_from_text(input_path)
    parts = [part for part in (author_part, title, f"arXiv:{arxiv_id}" if arxiv_id else "") if part]
    return clean_whitespace(", ".join(parts))


def _ensure_section_contexts(source: dict[str, Any]) -> list[dict[str, Any]]:
    contexts = source.get("section_contexts", [])
    normalized: list[dict[str, Any]] = []
    if isinstance(contexts, list):
        for context in contexts:
            if not isinstance(context, dict):
                continue
            title = clean_whitespace(str(context.get("title", "")))
            if not title:
                continue
            normalized.append(
                {
                    "title": title,
                    "role": clean_whitespace(str(context.get("role", ""))) or _classify_source_section_role(title),
                    "summary_snippets": _dedupe_preserving_order([str(item) for item in context.get("summary_snippets", []) if clean_whitespace(str(item))])[:2],
                    "citation_keys": [clean_whitespace(str(item)) for item in context.get("citation_keys", []) if clean_whitespace(str(item))],
                    "citation_candidates": [clean_whitespace(str(item)) for item in context.get("citation_candidates", []) if clean_whitespace(str(item))],
                    "definition_snippets": [clean_whitespace(str(item)) for item in context.get("definition_snippets", []) if clean_whitespace(str(item))][:4],
                    "symbol_entries": [
                        {
                            "symbol": clean_whitespace(str(item.get("symbol", ""))),
                            "meaning": clean_whitespace(str(item.get("meaning", ""))),
                            "section": clean_whitespace(str(item.get("section", ""))),
                            "evidence": clean_whitespace(str(item.get("evidence", ""))),
                        }
                        for item in context.get("symbol_entries", [])
                        if isinstance(item, dict) and clean_whitespace(str(item.get("symbol", ""))) and clean_whitespace(str(item.get("meaning", "")))
                    ][:8],
                    "equation_entries": [
                        {
                            "equation": clean_whitespace(str(item.get("equation", ""))),
                            "label": clean_whitespace(str(item.get("label", ""))),
                            "role": clean_whitespace(str(item.get("role", ""))),
                            "context_summary": clean_whitespace(str(item.get("context_summary", ""))),
                            "anchor_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("anchor_symbols", []) if clean_whitespace(str(symbol))][:4],
                        }
                        for item in context.get("equation_entries", [])
                        if isinstance(item, dict) and clean_whitespace(str(item.get("equation", "")))
                    ][:6],
                    "formalism_steps": [
                        {
                            "section": clean_whitespace(str(item.get("section", ""))),
                            "role": clean_whitespace(str(item.get("role", ""))),
                            "equation": clean_whitespace(str(item.get("equation", ""))),
                            "equation_role": clean_whitespace(str(item.get("equation_role", ""))),
                            "context_summary": clean_whitespace(str(item.get("context_summary", ""))),
                            "anchor_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("anchor_symbols", []) if clean_whitespace(str(symbol))][:4],
                            "input_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("input_symbols", []) if clean_whitespace(str(symbol))][:4],
                            "output_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("output_symbols", []) if clean_whitespace(str(symbol))][:4],
                            "carry_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("carry_symbols", []) if clean_whitespace(str(symbol))][:4],
                            "section_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("section_symbols", []) if clean_whitespace(str(symbol))][:4],
                        }
                        for item in context.get("formalism_steps", [])
                        if isinstance(item, dict)
                    ][:3],
                }
            )
    if not normalized:
        for title in source.get("section_titles", []):
            cleaned = clean_whitespace(str(title))
            if not cleaned:
                continue
            normalized.append(
                {
                    "title": cleaned,
                    "role": _classify_source_section_role(cleaned),
                    "summary_snippets": [],
                    "citation_keys": [],
                    "citation_candidates": [],
                    "definition_snippets": [],
                    "symbol_entries": [],
                    "equation_entries": [],
                    "formalism_steps": [],
                }
            )
    return normalized


def _finalize_source_payload(source: dict[str, Any]) -> dict[str, Any]:
    source.setdefault("citation_catalog", {})
    if not isinstance(source.get("citation_catalog"), dict):
        source["citation_catalog"] = {}
    refs = source.get("reference_like_lines") or []
    if not isinstance(refs, list):
        refs = []
    refs = _dedupe_preserving_order([str(item) for item in refs if clean_whitespace(str(item))])
    if not refs and source["citation_catalog"]:
        refs = list(source["citation_catalog"].values())[:12]
    if str(source.get("source_kind", "")).lower() == "pdf":
        source["diagnostic_reference_like_lines"] = refs
        source["reference_like_lines"] = []
        source["equation_snippets"] = []
        source["equation_entries"] = []
        source["citation_binding_quality"] = "primary-paper-only"
    else:
        source["reference_like_lines"] = refs
        source["citation_binding_quality"] = "section-and-figure-local"
    primary = clean_whitespace(str(source.get("primary_citation", "")))
    if not primary:
        primary = _build_primary_citation(source)
    if not primary and refs:
        primary = refs[0]
    source["primary_citation"] = primary
    if "definition_snippets" not in source or not isinstance(source.get("definition_snippets"), list):
        source["definition_snippets"] = []
    if "symbol_entries" not in source or not isinstance(source.get("symbol_entries"), list):
        source["symbol_entries"] = []
    source["section_contexts"] = _ensure_section_contexts(source)
    if "equation_entries" not in source or not isinstance(source.get("equation_entries"), list):
        source["equation_entries"] = []
    if "formalism_chain" not in source or not isinstance(source.get("formalism_chain"), list):
        source["formalism_chain"] = []
    if not source["formalism_chain"] and str(source.get("source_kind", "")).lower() in {"tex", "tex-dir", "tex-archive"}:
        source["formalism_chain"] = _build_formalism_chain(source["section_contexts"])
    if source["formalism_chain"]:
        formalism_by_section: dict[str, list[dict[str, Any]]] = {}
        for step in source["formalism_chain"]:
            if not isinstance(step, dict):
                continue
            section_title = clean_whitespace(str(step.get("section", "")))
            if not section_title:
                continue
            formalism_by_section.setdefault(section_title, []).append(step)
        for context in source["section_contexts"]:
            title = clean_whitespace(str(context.get("title", "")))
            if title and not context.get("formalism_steps"):
                context["formalism_steps"] = formalism_by_section.get(title, [])[:2]
    return source


def _extract_braced(text: str, start: int) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    out: list[str] = []
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
            if depth > 1:
                out.append(char)
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return "".join(out), idx + 1
            out.append(char)
            continue
        out.append(char)
    return None


def _find_command_argument(text: str, command: str) -> str | None:
    pattern = re.compile(rf"\\{re.escape(command)}\*?(?:\[[^\]]*\])?")
    match = pattern.search(text)
    if not match:
        return None
    idx = match.end()
    while idx < len(text) and text[idx].isspace():
        idx += 1
    found = _extract_braced(text, idx)
    return found[0] if found else None


def _expand_tex_inputs(tex: str, base_dir: Path, seen: set[Path]) -> str:
    pattern = re.compile(r"\\(?:input|include){([^{}]+)}")

    def replacer(match: re.Match[str]) -> str:
        rel = match.group(1).strip()
        candidate = (base_dir / rel)
        if candidate.suffix == "":
            candidate = candidate.with_suffix(".tex")
        candidate = candidate.resolve()
        if candidate in seen or not candidate.exists():
            return ""
        seen.add(candidate)
        nested = candidate.read_text(encoding="utf-8", errors="ignore")
        return _expand_tex_inputs(nested, candidate.parent, seen)

    return pattern.sub(replacer, tex)


def _find_main_tex(tex_files: list[Path]) -> Path:
    scored: list[tuple[int, int, Path]] = []
    for path in tex_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        score = 0
        if "\\documentclass" in text:
            score += 5
        if "\\begin{document}" in text:
            score += 5
        if "\\title" in text:
            score += 2
        scored.append((score, len(text), path))
    scored.sort(reverse=True)
    return scored[0][2]


def _ensure_within_directory(root: Path, target: Path) -> None:
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Archive member escapes extraction root: {target}") from exc


def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    for member in archive.infolist():
        target = destination / member.filename
        _ensure_within_directory(destination, target)
    archive.extractall(destination)


def _safe_extract_tar(archive: tarfile.TarFile, destination: Path) -> None:
    members = archive.getmembers()
    for member in members:
        if member.issym() or member.islnk():
            raise ValueError(f"Refusing to extract symbolic link from archive: {member.name}")
        target = destination / member.name
        _ensure_within_directory(destination, target)
    archive.extractall(destination, members=members)


def _unwrap_source_path(source: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    suffixes = source.suffixes
    if source.is_dir():
        return source, None
    if suffixes and suffixes[-1] in {".zip", ".tar", ".gz", ".tgz"}:
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        if source.suffix == ".zip":
            with zipfile.ZipFile(source) as archive:
                _safe_extract_zip(archive, root)
        else:
            with tarfile.open(source) as archive:
                _safe_extract_tar(archive, root)
        return root, temp_dir
    return source, None


def detect_source_kind(path: Path, explicit_kind: str = "auto") -> str:
    if explicit_kind != "auto":
        return explicit_kind
    lower = path.name.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".md"):
        return "markdown"
    if lower.endswith(".json"):
        return "achievements-json"
    if lower.endswith(".tex"):
        return "tex"
    if path.is_dir():
        return "tex-dir"
    if lower.endswith((".zip", ".tar", ".tar.gz", ".tgz")):
        return "tex-archive"
    raise ValueError(f"Cannot infer source kind from {path}")


def _looks_like_title(line: str) -> bool:
    if not line or len(line) < 12 or len(line) > 200:
        return False
    lowered = line.lower()
    bad_prefixes = ("arxiv", "submitted", "published", "abstract", "introduction", "contents")
    if lowered.startswith(bad_prefixes):
        return False
    if re.fullmatch(r"[\d.\- ]+", line):
        return False
    return True


def _guess_title_from_lines(lines: list[str], fallback: str | None = None) -> str:
    if fallback and _looks_like_title(fallback):
        return fallback
    for line in lines[:20]:
        if _looks_like_title(line):
            return line
    return fallback or "Untitled Research Talk"


def _extract_abstract_from_text(text: str) -> str:
    match = re.search(
        r"abstract[:\s]*(.+?)(?:\n\s*(?:\d+(?:\.\d+)*\s+)?(?:introduction|background|contents)\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return clean_whitespace(match.group(1))
    return ""


def _looks_like_pdf_affiliation_line(line: str) -> bool:
    lowered = clean_whitespace(line).lower()
    if re.match(r"^\d+\s*(department|school|institute|center|centre|laboratory|lab|faculty|college|university)\b", lowered):
        return True
    return bool(
        re.search(r"\b(university|institute|department|school|center|centre|laboratory|college)\b", lowered)
        and re.search(r"\b\d{5,6}\b", line)
    )


def _looks_like_pdf_author_line(line: str) -> bool:
    cleaned = clean_whitespace(line)
    lowered = cleaned.lower()
    if len(cleaned) < 8 or len(cleaned) > 240:
        return False
    if lowered.startswith(("abstract", "introduction", "contents", "arxiv:", "submitted")):
        return False
    if _looks_like_pdf_affiliation_line(cleaned):
        return False
    if "@" in cleaned:
        return False
    if re.search(r"\b(phys\.|jhep|jcap|doi)\b", lowered):
        return False
    capitalized_words = re.findall(r"\b[A-Z][A-Za-z'.-]+\b", cleaned)
    if len(capitalized_words) < 3:
        return False
    if not ("," in cleaned or " and " in lowered):
        return False
    return True


def _extract_pdf_author_names(first_lines: list[str]) -> tuple[list[str], str]:
    author_lines: list[str] = []
    for line in first_lines[1:8]:
        if _looks_like_pdf_affiliation_line(line) or line.lower().startswith(("abstract", "introduction", "contents")):
            break
        if _looks_like_pdf_author_line(line):
            author_lines.append(line)
        elif author_lines:
            break
    author_block = clean_whitespace(" ".join(author_lines))
    if not author_block:
        return [], ""

    block = author_block.replace(" and ", " | ")
    block = re.sub(r"(?:,?\s*\d+|,?\s*[†‡§¶∗*]+)+\s*(?=[A-Z])", " | ", block)
    block = re.sub(r"(?:,?\s*\d+|,?\s*[†‡§¶∗*]+)+", " ", block)
    parts = [clean_whitespace(part.strip(" ,;")) for part in re.split(r"\s*\|\s*", block) if clean_whitespace(part)]

    names: list[str] = []
    seen: set[str] = set()
    for part in parts:
        tokens = re.findall(r"[A-Za-z][A-Za-z'.-]*", part)
        if len(tokens) < 2 or len(tokens) > 5:
            continue
        candidate = clean_whitespace(" ".join(tokens))
        key = candidate.lower()
        if key in seen or _looks_like_pdf_affiliation_line(candidate):
            continue
        names.append(candidate)
        seen.add(key)
    if names:
        return names, author_block

    for match in re.finditer(r"[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){1,3}", author_block):
        candidate = clean_whitespace(match.group(0))
        key = candidate.lower()
        if key not in seen:
            names.append(candidate)
            seen.add(key)
    return names[:8], author_block


def _fallback_summary_from_page_texts(page_texts: list[str], title: str = "") -> str:
    sentence_pattern = re.compile(r"(?<=[.!?])\s+")
    noisy_tokens = (
        "arxiv",
        "phys. rev",
        "jhep",
        "jcap",
        "copyright",
        "figure",
        "table",
        "acknowledg",
    )
    corpus = " ".join(clean_whitespace(text) for text in page_texts[:2] if clean_whitespace(text))
    for sentence in sentence_pattern.split(corpus):
        cleaned = clean_whitespace(sentence.strip(" -"))
        lowered = cleaned.lower()
        if len(cleaned) < 90 or len(cleaned) > 320:
            continue
        if title and lowered == clean_whitespace(title).lower():
            continue
        if any(token in lowered for token in noisy_tokens):
            continue
        if not re.search(r"[A-Za-z]", cleaned):
            continue
        return cleaned
    return ""


def _canonicalize_section_title(text: str) -> str:
    normalized = clean_whitespace(text.rstrip(" .;,:"))
    lowered = normalized.lower()
    for prefix, label in sorted(CANONICAL_SECTION_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        if lowered == prefix:
            return label
        if lowered.startswith(prefix + " "):
            trailing = clean_whitespace(normalized[len(prefix):].lstrip(" :-"))
            if not trailing or len(trailing.split()) > 2 or normalized.endswith(("-", ".")):
                return label
    return normalized


def _guess_section_titles(page_texts: list[str]) -> list[str]:
    lines: list[str] = []
    for text in page_texts:
        lines.extend(clean_lines(text))
    sections: list[str] = []
    seen: set[str] = set()
    patterns = [
        re.compile(r"^(?:\d+(?:\.\d+)*)\s+[A-Z][A-Za-z0-9 ,:()/\-]{2,}$"),
        re.compile(r"^(Introduction|Background|Model(?: Setup)?|Setup|Methods?|Analysis|Results?|Discussion|Conclusion|Conclusions|Outlook|Appendix)\b.*$", re.IGNORECASE),
    ]
    for line in lines:
        normalized = _canonicalize_section_title(line)
        if len(normalized) > 90 or not normalized:
            continue
        lowered = normalized.lower()
        if lowered.startswith(("figure", "fig.", "table", "arxiv:", "[")):
            continue
        word_count = len(normalized.split())
        if word_count > 10:
            continue
        if lowered in CANONICAL_SECTION_LABELS:
            normalized = CANONICAL_SECTION_LABELS[lowered]
        elif not any(pattern.match(normalized) for pattern in patterns):
            continue
        else:
            tokens = re.findall(r"[A-Za-z]+", normalized)
            capitalized = sum(1 for token in tokens if token[:1].isupper() or token.isupper())
            if tokens and capitalized / len(tokens) < 0.35:
                continue
        if any(pattern.match(normalized) for pattern in patterns) or lowered in CANONICAL_SECTION_LABELS:
            key = normalized.lower()
            if key not in seen:
                sections.append(normalized)
                seen.add(key)
        if len(sections) >= 12:
            break
    return sections


def _figure_slot_key(text: str) -> str | None:
    match = re.search(r"\b(fig(?:ure)?\.?\s*\d+|table\s+\d+)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    key = match.group(1).lower().replace("figure", "fig").replace(" ", "").replace(".", "")
    return key


def _register_figure_caption(store: dict[str, str], order: list[str], caption: str) -> None:
    cleaned = clean_whitespace(caption[:220].rstrip(" .;,:"))
    key = _figure_slot_key(cleaned)
    if not cleaned or not key:
        return
    existing = store.get(key, "")
    if key not in store:
        order.append(key)
        store[key] = cleaned
        return
    if len(cleaned) > len(existing):
        store[key] = cleaned


def _collect_figure_like_lines(page_texts: list[str], limit: int = 10) -> list[str]:
    slots: dict[str, str] = {}
    order: list[str] = []
    line_pattern = re.compile(r"^(?:fig(?:ure)?\.?\s*\d+|table\s+\d+)\b", re.IGNORECASE)
    inline_pattern = re.compile(r"(?:Fig(?:ure)?\.?\s*\d+[^.\n]{0,120})", re.IGNORECASE)

    for text in page_texts[: min(len(page_texts), 12)]:
        for line in clean_lines(text):
            if line_pattern.match(line):
                _register_figure_caption(slots, order, line)
                if len(order) >= limit:
                    return [slots[key] for key in order[:limit]]
        for match in inline_pattern.findall(text):
            _register_figure_caption(slots, order, match)
            if len(order) >= limit:
                return [slots[key] for key in order[:limit]]
    return [slots[key] for key in order[:limit]]


def _clean_equation_snippet(text: str, max_chars: int = 180) -> str:
    value = text or ""
    value = re.sub(r"\\label{[^{}]+}", "", value)
    value = re.sub(r"\\(?:nonumber|tag\*?{[^{}]+})", "", value)
    value = clean_whitespace(value)
    if len(value) > max_chars:
        value = value[:max_chars].rsplit(" ", 1)[0].strip() or value[:max_chars].strip()
    return value.strip()


def _collect_equation_like_lines(page_texts: list[str], limit: int = 6) -> list[str]:
    equations: list[str] = []
    seen: set[str] = set()
    for text in page_texts[: min(len(page_texts), 10)]:
        for line in clean_lines(text):
            if line.lower().startswith(("fig", "figure", "table")):
                continue
            if not any(symbol in line for symbol in ("=", "<", ">", "≤", "≥", "∼", "≈")):
                continue
            if len(line) < 12 or len(line) > 180:
                continue
            candidate = _clean_equation_snippet(line)
            key = candidate.lower()
            if not candidate or key in seen:
                continue
            equations.append(candidate)
            seen.add(key)
            if len(equations) >= limit:
                return equations
    return equations


def _collect_reference_like_lines(page_texts: list[str], limit: int = 12) -> list[str]:
    lines: list[str] = []
    patterns = (
        "arxiv",
        "prl",
        "prd",
        "jhep",
        "jcap",
        "phys.",
        "nature",
        "science",
        "astrophys.",
    )
    incomplete_endings = ("phys.", "phys. rev.", "phys. rev. lett.", "jhep", "jcap", "eur. phys. j.", "nucl. phys.")
    continuation_starts = ("(", "arxiv:", "doi:", "[erratum", "rev.", "lett.", "jhep", "jcap")
    current = ""
    for text in page_texts:
        for line in clean_lines(text):
            lowered = line.lower()
            if any(token in lowered for token in ("supported by", "support by", "foundation", "grant", "project number")):
                continue
            if current:
                current_lower = current.lower()
                if (
                    line.startswith(continuation_starts)
                    or lowered.startswith(continuation_starts)
                    or line[:1].islower()
                    or (len(line) <= 120 and not re.search(r"[.!?]$", current))
                    or any(current_lower.endswith(token) for token in ("phys.", "rev.", "lett.", "jhep", "jcap", "eur.", "nucl.", "astrophys."))
                ):
                    current = clean_whitespace(f"{current} {line}")
                    if re.search(r"[.!?]$", line):
                        lines.append(current)
                        current = ""
                    continue
                lines.append(current)
                current = ""
            if any(token in lowered for token in patterns):
                current = line
                if re.search(r"[.!?]$", line) and not any(lowered.endswith(token) for token in incomplete_endings):
                    lines.append(current)
                    current = ""
    if current:
        lines.append(current)
    unique: list[str] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = clean_whitespace(line[:260].rstrip(" ,;"))
        key = cleaned.lower()
        if key not in seen:
            unique.append(cleaned)
            seen.add(key)
        if len(unique) >= limit:
            break
    return unique


def _section_spans_from_tex(merged_tex: str) -> list[dict[str, Any]]:
    matches = list(re.finditer(r"\\section\*?{([^{}]+)}", merged_tex))
    spans: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(merged_tex)
        title = latex_to_text(match.group(1))
        content = merged_tex[start:end]
        spans.append(
            {
                "title": title,
                "start": start,
                "end": end,
                "content": content,
                "role": _classify_source_section_role(title),
                "summary_snippets": _extract_section_summary_snippets(content, limit=2),
                "citation_keys": _extract_citation_keys(content),
                "definition_snippets": _extract_definition_snippets(content, limit=4),
                "symbol_entries": _extract_symbol_entries_from_text(content, title, limit=8),
            }
        )
    return spans


def _section_title_for_position(section_spans: list[dict[str, Any]], position: int) -> str:
    active = ""
    for section in section_spans:
        if int(section.get("start", 0)) <= position < int(section.get("end", 0)):
            return str(section.get("title", ""))
        if int(section.get("start", 0)) <= position:
            active = str(section.get("title", ""))
    return active


def _section_span_for_position(section_spans: list[dict[str, Any]], position: int) -> dict[str, Any] | None:
    for section in section_spans:
        if int(section.get("start", 0)) <= position < int(section.get("end", 0)):
            return section
    return None


def _extract_equation_entries_from_tex(merged_tex: str, section_spans: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    patterns = [
        re.compile(r"\\begin{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*|eqnarray\*?)}(.*?)\\end{(?:equation|equation\*|align|align\*|gather|gather\*|multline|multline\*|eqnarray\*?)}", flags=re.DOTALL),
        re.compile(r"\\\[(.*?)\\\]", flags=re.DOTALL),
        re.compile(r"\$\$(.*?)\$\$", flags=re.DOTALL),
    ]
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(merged_tex):
            body = match.group(1)
            equation = _clean_equation_snippet(body)
            key = equation.lower()
            if not equation or key in seen or len(equation) < 8:
                continue
            active_section = _section_span_for_position(section_spans, match.start())
            section_title = _section_title_for_position(section_spans, match.start())
            local_start = max(0, match.start() - 120)
            local_end = min(len(merged_tex), match.end() + 120)
            if active_section:
                local_start = max(local_start, int(active_section.get("start", 0)))
                local_end = min(local_end, int(active_section.get("end", len(merged_tex))))
            context = " ".join(
                [
                    merged_tex[local_start: match.start()],
                    body,
                    merged_tex[match.end(): local_end],
                ]
            )
            entries.append(
                {
                    "equation": equation,
                    "label": _find_command_argument(body, "label") or "",
                    "section": section_title,
                    "role": _classify_equation_role(equation, _find_command_argument(body, "label") or "", context, section_title),
                    "context_summary": (_extract_section_summary_snippets(context, limit=1) or [""])[0],
                    "citation_keys": _extract_citation_keys(context),
                    "definition_snippets": _extract_definition_snippets(context, limit=2),
                }
            )
            seen.add(key)
            if len(entries) >= limit:
                return entries
        if len(entries) >= limit:
            break
    return entries


def _aggregate_symbol_entries(section_spans: list[dict[str, Any]], limit: int = 20) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for section in section_spans:
        for item in section.get("symbol_entries", []):
            if not isinstance(item, dict):
                continue
            symbol = clean_whitespace(str(item.get("symbol", "")))
            meaning = clean_whitespace(str(item.get("meaning", "")))
            if not symbol or not meaning:
                continue
            key = (symbol.lower(), meaning.lower())
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "symbol": symbol,
                    "meaning": meaning,
                    "section": clean_whitespace(str(item.get("section", ""))) or clean_whitespace(str(section.get("title", ""))),
                    "evidence": clean_whitespace(str(item.get("evidence", ""))),
                }
            )
            if len(entries) >= limit:
                return entries
    return entries


def _anchor_symbols_for_equation(equation: str, section_symbols: list[dict[str, Any]]) -> list[str]:
    anchors: list[str] = []
    lowered_equation = equation.lower()
    for entry in section_symbols:
        symbol = clean_whitespace(str(entry.get("symbol", "")))
        if not symbol:
            continue
        if symbol.lower() in lowered_equation:
            anchors.append(symbol)
    return _dedupe_preserving_order(anchors)[:4]


def _equation_symbol_tokens(equation: str, limit: int = 8) -> list[str]:
    text = _latex_math_to_text(equation)
    tokens = re.findall(r"[A-Za-z]+(?:_[A-Za-z0-9]+)?", text)
    skip = {
        "begin",
        "end",
        "frac",
        "left",
        "right",
        "label",
        "nonumber",
        "text",
        "operatorname",
        "mathrm",
        "mathcal",
        "mathbf",
        "mathbb",
        "langle",
        "rangle",
        "partial",
        "bar",
        "barchi",
        "hat",
        "tilde",
        "vec",
        "rm",
        "exp",
        "log",
        "ln",
        "sin",
        "cos",
        "tan",
        "det",
        "tr",
        "sum",
        "prod",
        "int",
        "min",
        "max",
    }
    cleaned_tokens: list[str] = []
    for token in tokens:
        cleaned = _clean_symbol_name(token)
        lowered = cleaned.lower()
        if not cleaned or lowered in skip:
            continue
        cleaned_tokens.append(cleaned)
    return _dedupe_preserving_order(cleaned_tokens)[:limit]


def _equation_lhs_symbols(equation: str, limit: int = 4) -> list[str]:
    text = _latex_math_to_text(equation)
    lhs = re.split(r"\s*(?:=|≈|∼|<|>|≤|≥)\s*", text, maxsplit=1)[0]
    derivative_match = re.search(r"(?:d|partial)\s*([A-Za-z]+(?:_[A-Za-z0-9]+)?)\s*/\s*(?:d|partial)\s*([A-Za-z]+(?:_[A-Za-z0-9]+)?)", lhs)
    if derivative_match:
        return _dedupe_preserving_order([clean_whitespace(derivative_match.group(1))])[:limit]
    return _equation_symbol_tokens(lhs, limit=limit)


def _equation_rhs_symbols(equation: str, limit: int = 6) -> list[str]:
    text = _latex_math_to_text(equation)
    parts = re.split(r"\s*(?:=|≈|∼|<|>|≤|≥)\s*", text, maxsplit=1)
    rhs = parts[1] if len(parts) > 1 else text
    return _equation_symbol_tokens(rhs, limit=limit)


def _rank_equation_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda item: (
            0 if clean_whitespace(str(item.get("role", ""))) in {"defining-formalism", "analysis-engine", "observable-or-fit"} else 1,
            0 if item.get("anchor_symbols") else 1,
            0 if clean_whitespace(str(item.get("context_summary", ""))) else 1,
        ),
    )


def _build_formalism_chain(section_contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    previous_symbols: list[str] = []
    previous_outputs: list[str] = []
    for section in section_contexts:
        role = clean_whitespace(str(section.get("role", "")))
        if role not in {"setup", "method", "results", "core"}:
            continue
        equations = [item for item in section.get("equation_entries", []) if isinstance(item, dict)]
        lead_entry = _rank_equation_entries(equations)[0] if equations else None
        anchor_symbols = [clean_whitespace(str(item)) for item in (lead_entry or {}).get("anchor_symbols", []) if clean_whitespace(str(item))]
        lhs_symbols = _equation_lhs_symbols(str((lead_entry or {}).get("equation", "")))
        rhs_symbols = _equation_rhs_symbols(str((lead_entry or {}).get("equation", "")))
        section_symbols = [
            clean_whitespace(str(item.get("symbol", "")))
            for item in section.get("symbol_entries", [])
            if isinstance(item, dict) and clean_whitespace(str(item.get("symbol", "")))
        ]
        visible_symbols = _dedupe_preserving_order(lhs_symbols + anchor_symbols + section_symbols[:3])
        if not visible_symbols and not lead_entry:
            continue
        previous_lower = {item.lower() for item in previous_symbols}
        carry_symbols = [symbol for symbol in visible_symbols if symbol.lower() in previous_lower]
        rhs_overlap = [symbol for symbol in rhs_symbols if symbol.lower() in previous_lower]
        input_symbols = carry_symbols or rhs_overlap or [symbol for symbol in rhs_symbols if symbol not in lhs_symbols][:3]
        output_symbols = lhs_symbols or [symbol for symbol in anchor_symbols if symbol not in input_symbols][:2] or [symbol for symbol in section_symbols if symbol not in input_symbols][:2]
        chain.append(
            {
                "section": clean_whitespace(str(section.get("title", ""))),
                "role": role,
                "equation": clean_whitespace(str((lead_entry or {}).get("equation", ""))),
                "equation_role": clean_whitespace(str((lead_entry or {}).get("role", ""))) or ("formalism" if lead_entry else ""),
                "context_summary": clean_whitespace(str((lead_entry or {}).get("context_summary", ""))),
                "anchor_symbols": anchor_symbols[:4],
                "input_symbols": _dedupe_preserving_order(input_symbols)[:4],
                "output_symbols": _dedupe_preserving_order(output_symbols)[:4],
                "carry_symbols": _dedupe_preserving_order(carry_symbols)[:4],
                "section_symbols": _dedupe_preserving_order(section_symbols)[:4],
            }
        )
        previous_symbols = _dedupe_preserving_order(previous_symbols + visible_symbols + rhs_symbols + input_symbols + output_symbols)[:12]
        previous_outputs = _dedupe_preserving_order(previous_outputs + output_symbols)[:8]
    return chain


def extract_from_pdf(path: Path, max_pages: int | None = None) -> dict[str, Any]:
    if PdfReader is None:
        raise ModuleNotFoundError(
            "Missing dependency 'pypdf'. Use the Codex runtime Python from references/workflow.md or install pypdf."
        )
    reader = PdfReader(str(path))
    pages = reader.pages[:max_pages] if max_pages else reader.pages
    page_texts = [page.extract_text() or "" for page in pages]
    first_lines = clean_lines(page_texts[0]) if page_texts else []
    metadata_title = ""
    if reader.metadata and reader.metadata.title:
        metadata_title = clean_whitespace(str(reader.metadata.title))
    title = _guess_title_from_lines(first_lines, metadata_title)
    authors, author_line = _extract_pdf_author_names(first_lines)
    abstract = _extract_abstract_from_text("\n".join(page_texts[:3]))
    if not abstract:
        abstract = _fallback_summary_from_page_texts(page_texts, title=title)
    section_titles = _guess_section_titles(page_texts)
    figure_mentions = _collect_figure_like_lines(page_texts)
    conclusion = ""
    tail_text = "\n".join(page_texts[-4:])
    conclusion_match = re.search(
        r"(?:conclusion|conclusions|summary)[:\s]*(.+?)(?:references\b|acknowledg(?:e)?ments?\b|$)",
        tail_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if conclusion_match:
        conclusion = clean_whitespace(conclusion_match.group(1))
    payload = {
        "source_kind": "pdf",
        "input_path": str(path.resolve()),
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "section_titles": section_titles,
        "section_contexts": [
            {
                "title": section_title,
                "role": _classify_source_section_role(section_title),
                "summary_snippets": [],
                "citation_keys": [],
                "citation_candidates": [],
                "definition_snippets": [],
                "symbol_entries": [],
                "equation_entries": [],
                "formalism_steps": [],
            }
            for section_title in section_titles
        ],
        "figure_captions": figure_mentions,
        "equation_snippets": _collect_equation_like_lines(page_texts),
        "formalism_chain": [],
        "conclusion_excerpt": conclusion,
        "reference_like_lines": _collect_reference_like_lines(page_texts[-4:]),
        "page_count": len(reader.pages),
        "metadata": {
            "pdf_title": metadata_title,
            "pdf_author_line": author_line,
        },
    }
    return _finalize_source_payload(payload)


def extract_from_tex(source: Path) -> dict[str, Any]:
    root, temp_dir = _unwrap_source_path(source)
    try:
        if root.is_file() and root.suffix == ".tex":
            main_tex = root
        else:
            tex_files = sorted(root.rglob("*.tex"))
            if not tex_files:
                raise ValueError(f"No .tex files found under {source}")
            main_tex = _find_main_tex(tex_files)

        raw = main_tex.read_text(encoding="utf-8", errors="ignore")
        merged = _expand_tex_inputs(raw, main_tex.parent, {main_tex.resolve()})
        title = latex_to_text(_find_command_argument(merged, "title") or main_tex.stem.replace("_", " "))
        author_raw = _find_command_argument(merged, "author") or ""
        author_raw = re.sub(r"\\and\b", "\n", author_raw)
        author_parts = [latex_to_text(part) for part in author_raw.splitlines() if latex_to_text(part)]
        abstract_match = re.search(r"\\begin{abstract}(.*?)\\end{abstract}", merged, flags=re.DOTALL)
        abstract = latex_to_text(abstract_match.group(1)) if abstract_match else ""
        if not abstract:
            intro_match = re.search(
                r"\\section\*?{(?:Introduction|Background)}(.*?)(?:\\section|\\subsection|\\appendix|$)",
                merged,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if intro_match:
                abstract = latex_to_text(intro_match.group(1))[:500]

        section_spans = _section_spans_from_tex(merged)
        section_titles = [str(section.get("title", "")) for section in section_spans]
        subsection_titles = [
            latex_to_text(match.group(1))
            for match in re.finditer(r"\\subsection\*?{([^{}]+)}", merged)
        ]

        bibliography_catalog = _extract_bibliography_catalog(root, merged)
        figure_captions: list[dict[str, Any]] = []
        for idx, env_match in enumerate(re.finditer(r"\\begin{figure.*?}(.*?)\\end{figure.*?}", merged, flags=re.DOTALL), start=1):
            body = env_match.group(1)
            caption = latex_to_text(_find_command_argument(body, "caption") or "")
            label = _find_command_argument(body, "label") or ""
            graphics = re.findall(r"\\includegraphics(?:\[[^\]]*\])?{([^{}]+)}", body)
            citation_keys = _extract_citation_keys(body)
            figure_captions.append(
                {
                    "index": idx,
                    "caption": caption,
                    "label": label,
                    "graphics": graphics,
                    "section": _section_title_for_position(section_spans, env_match.start()),
                    "citation_keys": citation_keys,
                    "citation_candidates": [bibliography_catalog[key] for key in citation_keys if key in bibliography_catalog][:3],
                }
            )

        cite_counter: Counter[str] = Counter()
        for match in re.finditer(r"\\cite\w*\*?(?:\[[^\]]*\])?{([^{}]+)}", merged):
            for key in match.group(1).split(","):
                cite_counter[clean_whitespace(key)] += 1

        equation_entries = _extract_equation_entries_from_tex(merged, section_spans, limit=10)
        equation_snippets = [str(entry.get("equation", "")) for entry in equation_entries[:8] if clean_whitespace(str(entry.get("equation", "")))]
        symbol_entries = _aggregate_symbol_entries(section_spans, limit=20)
        definition_snippets = _dedupe_preserving_order(
            [
                str(item)
                for section in section_spans
                for item in section.get("definition_snippets", [])
                if clean_whitespace(str(item))
            ]
        )[:10]
        equation_entries_by_section: dict[str, list[dict[str, Any]]] = {}
        for entry in equation_entries:
            section_title = clean_whitespace(str(entry.get("section", "")))
            if not section_title:
                continue
            equation_entries_by_section.setdefault(section_title, []).append(entry)
        section_contexts = [
            {
                "title": str(section.get("title", "")),
                "role": str(section.get("role", "")) or _classify_source_section_role(str(section.get("title", ""))),
                "summary_snippets": section.get("summary_snippets", [])[:2],
                "citation_keys": section.get("citation_keys", []),
                "citation_candidates": [bibliography_catalog[key] for key in section.get("citation_keys", []) if key in bibliography_catalog][:4],
                "definition_snippets": section.get("definition_snippets", [])[:4],
                "symbol_entries": section.get("symbol_entries", [])[:8],
                "equation_entries": [
                    {
                        **item,
                        "anchor_symbols": _anchor_symbols_for_equation(str(item.get("equation", "")), section.get("symbol_entries", [])),
                    }
                    for item in equation_entries_by_section.get(str(section.get("title", "")), [])[:4]
                ],
                "formalism_steps": [],
            }
            for section in section_spans
        ]
        equation_entries = [
            {
                **entry,
                "anchor_symbols": _anchor_symbols_for_equation(
                    str(entry.get("equation", "")),
                    next((section.get("symbol_entries", []) for section in section_spans if str(section.get("title", "")) == str(entry.get("section", ""))), []),
                ),
            }
            for entry in equation_entries
        ]
        formalism_chain = _build_formalism_chain(section_contexts)
        formalism_by_section: dict[str, list[dict[str, Any]]] = {}
        for step in formalism_chain:
            section_title = clean_whitespace(str(step.get("section", "")))
            if not section_title:
                continue
            formalism_by_section.setdefault(section_title, []).append(step)
        for context in section_contexts:
            context["formalism_steps"] = formalism_by_section.get(clean_whitespace(str(context.get("title", ""))), [])[:2]

        conclusion = ""
        conclusion_match = re.search(
            r"\\section\*?{(?:Conclusion|Conclusions|Summary)}(.*?)(?:\\section|\\appendix|\\bibliography|\\begin{thebibliography}|$)",
            merged,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if conclusion_match:
            conclusion = latex_to_text(conclusion_match.group(1))

        payload = {
            "source_kind": "tex",
            "input_path": str(source.resolve()),
            "main_tex": str(main_tex.resolve()),
            "title": title,
            "authors": author_parts,
            "abstract": abstract,
            "section_titles": section_titles,
            "subsection_titles": subsection_titles[:20],
            "figure_captions": figure_captions,
            "equation_snippets": equation_snippets,
            "equation_entries": equation_entries,
            "definition_snippets": definition_snippets,
            "symbol_entries": symbol_entries,
            "formalism_chain": formalism_chain,
            "section_contexts": section_contexts,
            "conclusion_excerpt": conclusion,
            "citation_keys": [key for key, _ in cite_counter.most_common(20)],
            "citation_catalog": bibliography_catalog,
            "reference_like_lines": list(bibliography_catalog.values())[:12],
            "metadata": {
                "source_root": str(root.resolve()),
                "figure_count": len(figure_captions),
            },
        }
        return _finalize_source_payload(payload)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def extract_from_achievements_json(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    for key in ("papers", "grants", "talks", "teaching", "service", "representative_works", "future_plan"):
        value = payload.get(key, [])
        if value is None:
            payload[key] = []
        elif not isinstance(value, list):
            raise ValueError(f"Field '{key}' must be a list in {path}")
    profile = payload.get("profile", {})
    if not isinstance(profile, dict):
        raise ValueError("Field 'profile' must be an object")
    payload["source_kind"] = "achievements-json"
    payload["input_path"] = str(path.resolve())
    payload["title"] = profile.get("title") or f"{profile.get('name', 'Researcher')} Assessment"
    payload["metadata"] = {
        "paper_count": len(payload["papers"]),
        "grant_count": len(payload["grants"]),
        "talk_count": len(payload["talks"]),
    }
    return _finalize_source_payload(payload)


def extract_from_markdown(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = raw.splitlines()
    headings: list[tuple[int, str]] = []
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            headings.append((len(match.group(1)), clean_whitespace(match.group(2))))

    title = next((text for level, text in headings if level == 1 and text), "")
    if not title:
        title = _guess_title_from_lines(clean_lines(raw[:2000]), path.stem.replace("_", " "))

    abstract = ""
    remainder = raw
    if title:
        title_heading = f"# {title}"
        if title_heading in raw:
            remainder = raw.split(title_heading, 1)[1]
    paragraphs = [clean_whitespace(block) for block in re.split(r"\n\s*\n", remainder) if clean_whitespace(block)]
    if paragraphs:
        abstract = paragraphs[0][:600]

    section_titles = [text for level, text in headings if level in {2, 3} and text][:20]

    figure_captions: list[str] = []
    seen: set[str] = set()
    for line in clean_lines(raw):
        if re.match(r"^(?:fig(?:ure)?\.?\s*\d+|table\s+\d+)\b", line, flags=re.IGNORECASE):
            value = clean_whitespace(line[:180].rstrip(" .;,:"))
            key = value.lower()
            if key not in seen:
                figure_captions.append(value)
                seen.add(key)
        if len(figure_captions) >= 12:
            break

    conclusion = ""
    heading_indices = [
        (idx, len(match.group(1)), clean_whitespace(match.group(2)))
        for idx, line in enumerate(lines)
        if (match := re.match(r"^(#{1,6})\s+(.*)$", line.strip()))
    ]
    section_contexts: list[dict[str, Any]] = []
    for index, (pos, level, text) in enumerate(heading_indices):
        if level not in {2, 3} or not text:
            continue
        end = len(lines)
        for next_pos, _, _ in heading_indices[index + 1:]:
            if next_pos > pos:
                end = next_pos
                break
        content = "\n".join(lines[pos + 1:end])
        section_contexts.append(
            {
                "title": text,
                "role": _classify_source_section_role(text),
                "summary_snippets": _extract_section_summary_snippets(content, limit=2),
                "citation_keys": [],
                "citation_candidates": [],
                "definition_snippets": _extract_definition_snippets(content, limit=3),
                "symbol_entries": _extract_symbol_entries_from_text(content, text, limit=6),
                "equation_entries": [],
                "formalism_steps": [],
            }
        )

    for pos, level, text in heading_indices:
        if level in {2, 3} and text.lower() in {"conclusion", "conclusions", "summary", "takeaways", "outlook"}:
            end = len(lines)
            for next_pos, _, _ in heading_indices:
                if next_pos > pos:
                    end = next_pos
                    break
            conclusion = clean_whitespace("\n".join(lines[pos + 1:end]))[:800]
            break

    equation_snippets: list[str] = []
    seen_equations: set[str] = set()
    for pattern in (re.compile(r"\$\$(.*?)\$\$", flags=re.DOTALL), re.compile(r"\\\[(.*?)\\\]", flags=re.DOTALL)):
        for match in pattern.finditer(raw):
            candidate = _clean_equation_snippet(match.group(1))
            key = candidate.lower()
            if not candidate or key in seen_equations or len(candidate) < 8:
                continue
            equation_snippets.append(candidate)
            seen_equations.add(key)
            if len(equation_snippets) >= 8:
                break
        if len(equation_snippets) >= 8:
            break

    return _finalize_source_payload({
        "source_kind": "markdown",
        "input_path": str(path.resolve()),
        "title": title,
        "authors": [],
        "abstract": abstract,
        "section_titles": section_titles,
        "section_contexts": section_contexts,
        "figure_captions": figure_captions,
        "equation_snippets": equation_snippets,
        "formalism_chain": [],
        "conclusion_excerpt": conclusion,
        "reference_like_lines": _collect_reference_like_lines([raw]),
        "metadata": {},
    })


def extract_source(path: Path, explicit_kind: str = "auto", max_pages: int | None = None) -> dict[str, Any]:
    source_kind = detect_source_kind(path, explicit_kind)
    if source_kind == "pdf":
        return _finalize_source_payload(extract_from_pdf(path, max_pages=max_pages))
    if source_kind == "markdown":
        return _finalize_source_payload(extract_from_markdown(path))
    if source_kind in {"tex", "tex-dir", "tex-archive"}:
        return _finalize_source_payload(extract_from_tex(path))
    if source_kind == "achievements-json":
        return _finalize_source_payload(extract_from_achievements_json(path))
    raise ValueError(f"Unsupported source kind: {source_kind}")


def _first_matching(items: list[str], keywords: tuple[str, ...], fallback: str) -> str:
    for item in items:
        lowered = item.lower()
        if any(keyword in lowered for keyword in keywords):
            return item
    return fallback


def _normalize_figure_titles(figures: list[Any]) -> list[str]:
    titles: list[str] = []
    for figure in figures:
        if isinstance(figure, dict):
            caption = clean_whitespace(str(figure.get("caption", "")))
            if caption:
                titles.append(caption)
        else:
            caption = clean_whitespace(str(figure))
            if caption:
                titles.append(caption)
    return titles


def _strip_figure_label(text: str) -> str:
    cleaned = clean_whitespace(text)
    stripped = re.sub(r"^(?:fig(?:ure)?\.?\s*\d+|table\s+\d+)[:.\s-]*", "", cleaned, flags=re.IGNORECASE)
    return clean_whitespace(stripped) or cleaned


def _localized_title(language: str, en: str, zh: str) -> str:
    return _lt(language, en, zh)


def _plain_language_claim_points(source: dict[str, Any], language: str, audience: str) -> list[str]:
    summary = clean_whitespace(str(source.get("abstract", ""))) or clean_whitespace(str(source.get("conclusion_excerpt", "")))
    bucket = _audience_bucket(audience)
    points: list[str] = []
    if summary:
        points.append(_compress_key_point(summary, 220 if bucket == "broad" else 180))
    elif clean_whitespace(str(source.get("title", ""))):
        title = clean_whitespace(str(source.get("title", "")))
        points.append(
            _lt(
                language,
                f"State in one sentence what '{title}' claims and why it matters.",
                f"先用一句话说明《{title}》的核心结论，以及它为什么重要。",
            )
        )
    sections = [clean_whitespace(str(item)) for item in source.get("section_titles", []) if clean_whitespace(str(item))]
    if sections:
        focus = ", ".join(sections[:2])
        if bucket == "broad":
            points.append(_lt(language, f"Explain the physical question before diving into {focus}.", f"在进入 {focus} 之前，先讲清楚物理问题本身。"))
        elif bucket == "mixed":
            points.append(_lt(language, f"Connect the main claim to the paper's structure: {focus}.", f"把主要结论和论文结构对应起来：{focus}。"))
        else:
            points.append(_lt(language, f"Flag the technical entry points early: {focus}.", f"尽早点出技术切入点：{focus}。"))
    return _dedupe_preserving_order(points)[:2]


def _background_context_points(language: str, audience: str) -> list[str]:
    bucket = _audience_bucket(audience)
    if bucket == "broad":
        return [
            _lt(language, "State the physical question before introducing notation.", "先讲物理问题，再引入符号和记号。"),
            _lt(language, "Define only the minimum concepts needed to follow the main result.", "只定义理解主结果所需的最少概念。"),
        ]
    if bucket == "mixed":
        return [
            _lt(language, "Define the essential objects and notation.", "定义最关键的对象和记号。"),
            _lt(language, "Connect the setup to the paper's central observable or claim.", "把理论设定和论文的核心可观测量或主张对应起来。"),
        ]
    return [
        _lt(language, "Define the essential objects and notation.", "定义最关键的对象和记号。"),
        _lt(language, "State the problem this paper enters and the precision it needs.", "说明这篇文章切入的问题，以及它需要的理论精度。"),
    ]


def _symbol_anchor_points(source: dict[str, Any], target_roles: tuple[str, ...], language: str) -> list[str]:
    entries: list[dict[str, Any]] = []
    for context in _ensure_section_contexts(source):
        role = clean_whitespace(str(context.get("role", "")))
        if role not in target_roles:
            continue
        entries.extend(item for item in context.get("symbol_entries", []) if isinstance(item, dict))
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        symbol = clean_whitespace(str(entry.get("symbol", "")))
        meaning = clean_whitespace(str(entry.get("meaning", "")))
        if not symbol or not meaning:
            continue
        key = (symbol.lower(), meaning.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append((symbol, meaning))
        if len(unique) >= 3:
            break
    if not unique:
        return []
    if len(unique) == 1:
        symbol, meaning = unique[0]
        return [_lt(language, f"Define {symbol} as {meaning}.", f"先定义 {symbol}，它表示 {meaning}。")]
    joined = ", ".join(f"{symbol} ({meaning})" for symbol, meaning in unique[:3])
    return [_lt(language, f"Keep the controlling symbols explicit: {joined}.", f"把控制问题的关键符号讲清楚：{joined}。")]


def _equation_anchor_points(source: dict[str, Any], target_roles: tuple[str, ...], language: str) -> list[str]:
    entries: list[dict[str, Any]] = []
    for context in _ensure_section_contexts(source):
        role = clean_whitespace(str(context.get("role", "")))
        if role not in target_roles:
            continue
        entries.extend(item for item in context.get("equation_entries", []) if isinstance(item, dict))
    if not entries:
        entries = [item for item in source.get("equation_entries", []) if isinstance(item, dict)]
    if not entries:
        return []
    ranked = _rank_equation_entries(entries)
    entry = ranked[0]
    role = clean_whitespace(str(entry.get("role", ""))) or "formalism"
    points = [_equation_role_explainer(role, language)]
    anchors = [clean_whitespace(str(symbol)) for symbol in entry.get("anchor_symbols", []) if clean_whitespace(str(symbol))]
    if anchors:
        joined = ", ".join(anchors[:4])
        points.append(_lt(language, f"Explain how the equation depends on {joined}.", f"要说明这条方程怎样依赖 {joined}。"))
    elif clean_whitespace(str(entry.get("context_summary", ""))):
        points.append(_compress_key_point(str(entry.get("context_summary", "")), 140))
    return _dedupe_preserving_order(points)[:2]


def _setup_points(source: dict[str, Any], language: str, audience: str) -> list[str]:
    bucket = _audience_bucket(audience)
    equations = _usable_equation_snippets(source)
    points = [
        _lt(language, "Show the model ingredients and key scales.", "讲清模型成分和关键尺度。"),
        _lt(language, "State the benchmark or working assumptions.", "说明基准点、近似条件或工作假设。"),
    ]
    points.extend(_symbol_anchor_points(source, ("setup",), language))
    points.extend(_equation_anchor_points(source, ("setup",), language))
    if equations:
        points.append(
            _lt(
                language,
                "Keep the defining equation or Lagrangian visible on the slide.",
                "把定义模型的关键方程或拉氏量放到这一页上。",
            )
        )
    elif bucket == "broad":
        points.append(_lt(language, "Translate the formal setup into a physical picture.", "把形式化设定翻译成直观的物理图景。"))
    return points[:3]


def _method_points(source: dict[str, Any], language: str, audience: str) -> list[str]:
    bucket = _audience_bucket(audience)
    points = [
        _lt(language, "Show the observable, pipeline, or derivation idea.", "说明可观测量、计算流程或推导思路。"),
        _lt(language, "Clarify the main technical challenge.", "点出最关键的技术难点。"),
    ]
    points.extend(_equation_anchor_points(source, ("method",), language))
    points.extend(_symbol_anchor_points(source, ("method",), language))
    if _audience_bucket(audience) == "experts":
        points.append(_lt(language, "State the critical approximation, matching step, or numerical ingredient.", "说明关键近似、matching 步骤或数值输入。"))
    elif bucket == "broad":
        points.append(_lt(language, "Explain what the method is doing physically, not only algebraically.", "不仅要讲代数步骤，也要讲这个方法在物理上做了什么。"))
    return points[:3]


def _result_points(language: str, audience: str) -> list[str]:
    bucket = _audience_bucket(audience)
    points = [
        _lt(language, "Explain what each panel shows.", "解释每个 panel 在展示什么。"),
        _lt(language, "Explain axes, color code, and benchmark choice.", "解释坐标轴、颜色编码和 benchmark 的选择。"),
    ]
    if bucket == "broad":
        points.append(_lt(language, "State the take-home message in plain physical language.", "用直接的物理语言说清 take-home message。"))
    else:
        points.append(_lt(language, "State the take-home message and the main caveat.", "说清主结论以及最重要的 caveat。"))
    return points


def _critique_points(language: str, audience: str) -> list[str]:
    if _audience_bucket(audience) == "broad":
        return [
            _lt(language, "Which assumption is most likely to break first?", "哪一个假设最可能最先失效？"),
            _lt(language, "What would need to be checked before using this result elsewhere?", "如果把这个结果用于别处，最先该复查什么？"),
        ]
    return [
        _lt(language, "What assumptions are restrictive?", "有哪些假设是比较强的？"),
        _lt(language, "What is still numerically, conceptually, or phenomenologically unclear?", "还有哪些数值、概念或唯象层面的地方并不清楚？"),
    ]


def _figure_slide_title(caption: str, index: int, language: str, use_numbered_prefix: bool = True) -> str:
    cleaned = _strip_figure_label(caption)
    if use_numbered_prefix:
        prefix = _lt(language, f"Figure {index}", f"图 {index}")
        return f"{prefix}: {cleaned}" if cleaned else prefix
    return cleaned or _lt(language, f"Figure {index}", f"图 {index}")


def _usable_equation_snippets(source: dict[str, Any]) -> list[str]:
    source_kind = str(source.get("source_kind", "")).lower()
    snippets = [clean_whitespace(str(item)) for item in source.get("equation_snippets", []) if clean_whitespace(str(item))]
    if source_kind == "pdf":
        return []
    return snippets


def _normalized_figure_records(source: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, figure in enumerate(source.get("figure_captions", []), start=1):
        if isinstance(figure, dict):
            caption = clean_whitespace(str(figure.get("caption", "")))
            if not caption:
                continue
            records.append(
                {
                    "index": int(figure.get("index", index)),
                    "caption": caption,
                    "label": clean_whitespace(str(figure.get("label", ""))),
                    "section": clean_whitespace(str(figure.get("section", ""))),
                    "citation_keys": [clean_whitespace(str(item)) for item in figure.get("citation_keys", []) if clean_whitespace(str(item))],
                    "citation_candidates": [clean_whitespace(str(item)) for item in figure.get("citation_candidates", []) if clean_whitespace(str(item))],
                }
            )
        else:
            caption = clean_whitespace(str(figure))
            if caption:
                records.append({"index": index, "caption": caption, "label": "", "section": "", "citation_keys": [], "citation_candidates": []})
    return records


def _source_argument_contexts(source: dict[str, Any]) -> list[dict[str, Any]]:
    contexts = _ensure_section_contexts(source)
    result: list[dict[str, Any]] = []
    for context in contexts:
        title = clean_whitespace(str(context.get("title", "")))
        lowered = title.lower()
        if not title:
            continue
        if any(token in lowered for token in ("reference", "bibliograph", "acknowledg", "appendix")):
            continue
        result.append(
            {
                "title": title,
                "role": clean_whitespace(str(context.get("role", ""))) or _classify_source_section_role(title),
                "summary_snippets": [clean_whitespace(str(item)) for item in context.get("summary_snippets", []) if clean_whitespace(str(item))][:2],
                "citation_keys": [clean_whitespace(str(item)) for item in context.get("citation_keys", []) if clean_whitespace(str(item))],
                "citation_candidates": [clean_whitespace(str(item)) for item in context.get("citation_candidates", []) if clean_whitespace(str(item))],
                "definition_snippets": [clean_whitespace(str(item)) for item in context.get("definition_snippets", []) if clean_whitespace(str(item))][:4],
                "symbol_entries": [item for item in context.get("symbol_entries", []) if isinstance(item, dict)][:8],
                "equation_entries": [item for item in context.get("equation_entries", []) if isinstance(item, dict)][:4],
                "formalism_steps": [item for item in context.get("formalism_steps", []) if isinstance(item, dict)][:2],
            }
        )
    if str(source.get("source_kind", "")).lower() == "pdf":
        role_order = {"background": 0, "setup": 1, "method": 2, "core": 2, "results": 3, "limitations": 4, "summary": 5}
        ranked = sorted(enumerate(result), key=lambda item: (role_order.get(str(item[1].get("role", "core")), 2), item[0]))
        return [item[1] for item in ranked]
    return result


def _select_argument_contexts(contexts: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    if target_count <= 0:
        return []
    if len(contexts) <= target_count:
        return contexts

    selected_indices: list[int] = []
    used: set[int] = set()
    for role in ("background", "setup", "method", "results"):
        for index, context in enumerate(contexts):
            if index in used:
                continue
            if context.get("role") == role:
                selected_indices.append(index)
                used.add(index)
                break
        if len(selected_indices) >= target_count:
            break

    for index, context in enumerate(contexts):
        if len(selected_indices) >= target_count:
            break
        if index in used:
            continue
        if context.get("role") == "summary" and len(contexts) > target_count:
            continue
        selected_indices.append(index)
        used.add(index)

    selected_indices.sort()
    return [contexts[index] for index in selected_indices[:target_count]]


def _argument_roadmap_points(contexts: list[dict[str, Any]], limit: int = 4) -> list[str]:
    return [str(context.get("title", "")) for context in contexts[:limit] if clean_whitespace(str(context.get("title", "")))]


def _slide_section_from_context_role(deck_type: str, role: str) -> str:
    if deck_type == "group-meeting":
        if role == "background":
            return "Background"
        if role in {"setup", "method", "core"}:
            return "Core Paper"
        if role == "results":
            return "Results"
        if role == "limitations":
            return "Critique"
        return "Closing"
    if deck_type == "conference":
        if role == "background":
            return "Motivation"
        if role in {"setup", "method", "core"}:
            return "Core Work"
        if role == "results":
            return "Results"
        return "Closing"
    return "Core Work"


def _purpose_from_context(role: str, language: str, deck_type: str) -> str:
    if role == "background":
        return _lt(language, "Position this section in the paper's logical setup.", "把这一节放回论文的论证起点中去解释。")
    if role == "setup":
        return _lt(language, "Explain the formal setup that the later claim depends on.", "解释后续结论所依赖的理论设定。")
    if role == "method":
        return _lt(language, "Explain the derivation or analysis move that advances the argument.", "解释真正推进论证的推导或分析步骤。")
    if role == "results":
        return _lt(language, "Explain what this section establishes and why it matters physically.", "解释这一节究竟建立了什么，以及它在物理上意味着什么。")
    if role == "limitations":
        return _lt(language, "Show where the argument is strongest and where it still depends on assumptions.", "说明这部分论证最稳的地方和仍然依赖假设的地方。")
    if deck_type == "conference":
        return _lt(language, "Carry the audience through the next step of the scientific narrative.", "带着听众进入科学叙事的下一步。")
    return _lt(language, "Carry the audience through the next step of the paper's argument.", "带着听众进入论文论证链的下一步。")


def _visual_from_context(role: str, language: str) -> str:
    if role == "background":
        return _lt(language, "Use one minimal concept figure, notation table, or clean framing diagram.", "用一张最简洁的概念图、记号表或 framing 图。")
    if role == "setup":
        return _lt(language, "Show the defining equation, action, Lagrangian, or model schematic.", "展示定义模型的关键方程、作用量、拉氏量或设定示意图。")
    if role == "method":
        return _lt(language, "Use a reduced derivation, proof map, or analysis workflow.", "用简化推导、证明结构图或分析流程。")
    if role == "results":
        return _lt(language, "Use the main figure or table from this section, enlarged enough to be read live.", "使用这一节的主图或主表，并放大到足以现场讲解。")
    if role == "limitations":
        return _lt(language, "Short critique slide with one compact list or comparison panel.", "用一页简洁的 critique 页面，配一个紧凑列表或比较框。")
    return _lt(language, "Use a figure or equation cluster that directly supports this step.", "用能直接支撑这一节论证的图或方程组合。")


def _citation_rule_from_context(role: str, language: str, deck_type: str) -> str:
    if role == "background":
        return _lt(language, "Cite the source paper locally, and add extra references only when they can be traced reliably.", "本页至少引用源论文；只有当额外文献能被可靠绑定时才补充。")
    if role in {"setup", "method", "results"}:
        return _lt(language, "Cite the source paper on the same slide; add section-local or figure-local references when they are truly bound.", "同页引用源论文；只有在真的能绑定到本节或本图时再补 section-local 或 figure-local 引用。")
    if role == "limitations":
        return _lt(language, "Cite comparison papers only if the comparison is explicit and traceable.", "只有当比较对象明确且可追溯时，才引用比较论文。")
    if deck_type == "conference":
        return _lt(language, "Add a local citation whenever a claim, figure, or equation is not original.", "凡是非原创的论断、图或方程，都要在本页给出引用。")
    return _lt(language, "Keep the main paper citation visible if the slide depends on its content.", "如果本页依赖主论文内容，保持源论文引用可见。")


def _context_symbol_points(context: dict[str, Any], language: str) -> list[str]:
    entries = [item for item in context.get("symbol_entries", []) if isinstance(item, dict)]
    if not entries:
        return []
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        symbol = clean_whitespace(str(entry.get("symbol", "")))
        meaning = clean_whitespace(str(entry.get("meaning", "")))
        if not symbol or not meaning:
            continue
        key = (symbol.lower(), meaning.lower())
        if key in seen:
            continue
        seen.add(key)
        pairs.append((symbol, meaning))
        if len(pairs) >= 2:
            break
    if not pairs:
        return []
    if len(pairs) == 1:
        symbol, meaning = pairs[0]
        return [_lt(language, f"Define {symbol} as {meaning}.", f"先定义 {symbol}，它表示 {meaning}。")]
    joined = ", ".join(f"{symbol} ({meaning})" for symbol, meaning in pairs)
    return [_lt(language, f"Keep the controlling symbols explicit: {joined}.", f"把控制问题的关键符号讲清楚：{joined}。")]


def _context_formalism_points(context: dict[str, Any], language: str) -> list[str]:
    steps = [item for item in context.get("formalism_steps", []) if isinstance(item, dict)]
    if not steps:
        return []
    step = steps[0]
    role = clean_whitespace(str(step.get("role", ""))) or clean_whitespace(str(context.get("role", ""))) or "core"
    carry = [clean_whitespace(str(item)) for item in step.get("carry_symbols", []) if clean_whitespace(str(item))]
    inputs = [clean_whitespace(str(item)) for item in step.get("input_symbols", []) if clean_whitespace(str(item))]
    outputs = [clean_whitespace(str(item)) for item in step.get("output_symbols", []) if clean_whitespace(str(item))]
    section_symbols = [clean_whitespace(str(item)) for item in step.get("section_symbols", []) if clean_whitespace(str(item))]
    if role == "setup":
        focus = ", ".join((outputs or section_symbols)[:3])
        if focus:
            return [_lt(language, f"Start the formalism by defining the main object(s): {focus}.", f"先把 formalism 的核心对象讲清楚：{focus}。")]
        return [_lt(language, "Start the formalism by defining the main object of the setup.", "先把设定中的 formalism 主对象讲清楚。")]
    if role == "method":
        bridge = ", ".join((carry or inputs)[:3])
        target = ", ".join((outputs or section_symbols)[:3])
        if bridge and target:
            return [_lt(language, f"Carry {bridge} into the derivation for {target}.", f"把 {bridge} 带入推导，并说明怎样得到 {target}。")]
        if bridge:
            return [_lt(language, f"Advance the derivation from the previously defined quantity {bridge}.", f"从前面定义过的 {bridge} 出发推进推导。")]
        if target:
            return [_lt(language, f"Use the method section to solve for or evolve {target}.", f"把方法部分讲成求解或演化 {target} 的过程。")]
    if role == "results":
        bridge = ", ".join((carry or inputs)[:3])
        target = ", ".join((outputs or section_symbols)[:3])
        if bridge and target:
            return [_lt(language, f"Translate {bridge} into the observable/result quantity {target}.", f"把 {bridge} 转化成可观测或结果量 {target}。")]
        if target:
            return [_lt(language, f"State clearly which quantity the final result predicts or constrains: {target}.", f"明确说清最终结果预测或约束的是哪个量：{target}。")]
    return []


def _context_equation_points(context: dict[str, Any], language: str) -> list[str]:
    entries = [item for item in context.get("equation_entries", []) if isinstance(item, dict)]
    if not entries:
        return []
    ranked = _rank_equation_entries(entries)
    entry = ranked[0]
    role = clean_whitespace(str(entry.get("role", ""))) or "formalism"
    points = [_equation_role_explainer(role, language)]
    anchors = [clean_whitespace(str(symbol)) for symbol in entry.get("anchor_symbols", []) if clean_whitespace(str(symbol))]
    if anchors:
        points.append(_lt(language, f"Explain how the equation depends on {', '.join(anchors[:4])}.", f"要说明这条方程怎样依赖 {', '.join(anchors[:4])}。"))
    elif clean_whitespace(str(entry.get("context_summary", ""))):
        points.append(_compress_key_point(str(entry.get("context_summary", "")), 140))
    return _dedupe_preserving_order(points)[:2]


def _context_points(context: dict[str, Any], source: dict[str, Any], language: str, audience: str) -> list[str]:
    role = str(context.get("role", "core"))
    points: list[str] = []
    summary_snippets = [clean_whitespace(str(item)) for item in context.get("summary_snippets", []) if clean_whitespace(str(item))]
    if role in {"setup", "method", "results"}:
        points.extend(_context_formalism_points(context, language))
    if role in {"setup", "method"}:
        points.extend(_context_symbol_points(context, language))
        points.extend(_context_equation_points(context, language))
        points.extend(_compress_key_point(item, 150) for item in summary_snippets[:1])
    elif role == "results":
        points.extend(_context_equation_points(context, language))
        points.extend(_compress_key_point(item, 150) for item in summary_snippets[:1])
    else:
        points.extend(_compress_key_point(item, 150) for item in summary_snippets[:2])
    if role == "background":
        points.extend(_background_context_points(language, audience))
    elif role == "setup":
        points.extend(_setup_points(source, language, audience))
    elif role == "method":
        points.extend(_method_points(source, language, audience))
    elif role == "results":
        points.extend(_result_points(language, audience))
    elif role == "limitations":
        points.extend(_critique_points(language, audience))
    else:
        points.extend(_plain_language_claim_points(source, language, audience)[:1])

    definitions = [clean_whitespace(str(item)) for item in context.get("definition_snippets", []) if clean_whitespace(str(item))]
    if role in {"background", "setup"} and definitions:
        points.append(_compress_key_point(definitions[0], 140))
    return _dedupe_preserving_order(points)[:3]


def _append_context_slides(
    slides: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    source: dict[str, Any],
    deck_type: str,
    language: str,
    audience: str,
) -> None:
    for context in contexts:
        title = clean_whitespace(str(context.get("title", "")))
        if not title:
            continue
        role = str(context.get("role", "core"))
        slide_section = _slide_section_from_context_role(deck_type, role)
        _append_slide(
            slides,
            slide_section,
            title,
            _purpose_from_context(role, language, deck_type),
            _context_points(context, source, language, audience),
            _visual_from_context(role, language),
            _citation_rule_from_context(role, language, deck_type),
        )
        slides[-1]["source_context_title"] = title
        slides[-1]["source_context_role"] = role
        slides[-1]["bound_source_section"] = title
        slides[-1]["bound_source_role"] = role


def _append_figure_result_slides(
    slides: list[dict[str, Any]],
    source: dict[str, Any],
    slots: int,
    deck_type: str,
    language: str,
    audience: str,
) -> None:
    if slots <= 0:
        return
    existing_titles = {
        _strip_figure_label(str(slide.get("title", ""))).lower()
        for slide in slides
        if clean_whitespace(str(slide.get("title", "")))
    }
    records = _normalized_figure_records(source)
    for record in records:
        if slots <= 0:
            break
        caption = clean_whitespace(str(record.get("caption", "")))
        if not caption:
            continue
        stripped = _strip_figure_label(caption).lower()
        if stripped in existing_titles:
            continue
        _append_slide(
            slides,
            "Results",
            _figure_slide_title(caption[:90].rstrip("."), int(record.get("index", len(slides) + 1)), language, use_numbered_prefix=True),
            _lt(language, "Use this figure as one concrete step in the paper's evidential chain.", "把这张图当成论文证据链中的一个具体步骤来讲。"),
            _result_points(language, audience),
            _lt(language, "Large imported figure with callouts or zoom boxes if dense.", "如果图很密，就用大图加 callout 或局部放大。"),
            _citation_rule_from_context("results", language, deck_type),
        )
        if clean_whitespace(str(record.get("section", ""))):
            bound_section = clean_whitespace(str(record.get("section", "")))
            slides[-1]["source_context_title"] = bound_section
            slides[-1]["bound_source_section"] = bound_section
        slides[-1]["source_context_role"] = "results"
        slides[-1]["bound_source_role"] = "results"
        existing_titles.add(stripped)
        slots -= 1


def _needs_local_citation(slide: dict[str, Any]) -> bool:
    rule = clean_whitespace(str(slide.get("citation_rule", ""))).lower()
    if not rule:
        return False
    return all(token not in rule for token in ("no citation needed", "no extra citation needed", "无需引用"))


def _citation_candidates_from_keys(source: dict[str, Any], keys: list[str], include_main: bool = True, limit: int = 4) -> list[str]:
    candidates: list[str] = []
    primary = clean_whitespace(str(source.get("primary_citation", "")))
    if include_main and primary:
        candidates.append(primary)
    catalog = source.get("citation_catalog", {})
    if isinstance(catalog, dict):
        for key in keys:
            formatted = clean_whitespace(str(catalog.get(key, "")))
            if formatted:
                candidates.append(formatted)
    return _dedupe_preserving_order(candidates)[:limit]


def _context_candidates_for_keywords(source: dict[str, Any], keywords: tuple[str, ...], include_main: bool = True, limit: int = 4) -> list[str]:
    candidates: list[str] = []
    contexts = source.get("section_contexts", [])
    for context in contexts:
        title = clean_whitespace(str(context.get("title", ""))).lower()
        if not title:
            continue
        if any(keyword in title for keyword in keywords):
            candidates.extend(str(item) for item in context.get("citation_candidates", []))
            if isinstance(source.get("citation_catalog", {}), dict):
                candidates.extend(
                    str(source["citation_catalog"].get(key, ""))
                    for key in context.get("citation_keys", [])
                    if clean_whitespace(str(source["citation_catalog"].get(key, "")))
                )
    if include_main and clean_whitespace(str(source.get("primary_citation", ""))):
        candidates.insert(0, clean_whitespace(str(source.get("primary_citation", ""))))
    return _dedupe_preserving_order(candidates)[:limit]


def _match_source_context_for_slide(slide: dict[str, Any], source: dict[str, Any]) -> dict[str, Any] | None:
    bound_title = clean_whitespace(str(slide.get("source_context_title", ""))).lower()
    if not bound_title:
        bound_title = clean_whitespace(str(slide.get("bound_source_section", ""))).lower()
    if not bound_title:
        return None
    for context in source.get("section_contexts", []):
        context_title = clean_whitespace(str(context.get("title", ""))).lower()
        if context_title == bound_title:
            return context
    return None


def _symbol_candidates_for_slide(slide: dict[str, Any], source: dict[str, Any]) -> list[str]:
    bound_context = _match_source_context_for_slide(slide, source)
    candidates: list[str] = []
    contexts: list[dict[str, Any]] = [bound_context] if isinstance(bound_context, dict) else []
    if not contexts:
        contexts = [context for context in source.get("section_contexts", []) if isinstance(context, dict)]
    for context in contexts:
        for entry in context.get("symbol_entries", []):
            if not isinstance(entry, dict):
                continue
            symbol = clean_whitespace(str(entry.get("symbol", "")))
            meaning = clean_whitespace(str(entry.get("meaning", "")))
            if symbol and meaning:
                candidates.append(f"{symbol}: {meaning}")
    if not candidates and not isinstance(bound_context, dict):
        for entry in source.get("symbol_entries", []):
            if not isinstance(entry, dict):
                continue
            symbol = clean_whitespace(str(entry.get("symbol", "")))
            meaning = clean_whitespace(str(entry.get("meaning", "")))
            if symbol and meaning:
                candidates.append(f"{symbol}: {meaning}")
    return _dedupe_preserving_order(candidates)[:3]


def _match_figure_record_for_slide(slide: dict[str, Any], source: dict[str, Any]) -> dict[str, Any] | None:
    title = _strip_figure_label(str(slide.get("title", ""))).lower()
    if not title:
        return None
    for record in _normalized_figure_records(source):
        caption = _strip_figure_label(str(record.get("caption", ""))).lower()
        if not caption:
            continue
        if title in caption or caption in title:
            return record
    return None


def _pdf_primary_paper_citation_candidates(slide: dict[str, Any], source: dict[str, Any]) -> list[str]:
    primary = clean_whitespace(str(source.get("primary_citation", "")))
    if not primary or not _needs_local_citation(slide):
        return []
    title = clean_whitespace(str(slide.get("title", ""))).lower()
    if any(token in title for token in ("roadmap", "agenda", "目录", "提纲")):
        return []
    return [primary]


def _definition_candidates_for_slide(slide: dict[str, Any], source: dict[str, Any]) -> list[str]:
    section = str(slide.get("section", "")).lower()
    title = str(slide.get("title", "")).lower()
    bound_context = _match_source_context_for_slide(slide, source)
    if bound_context:
        snippets = [str(item) for item in bound_context.get("definition_snippets", []) if clean_whitespace(str(item))]
        if snippets:
            return _dedupe_preserving_order(snippets)[:2]
    strong: list[str] = []
    fallback: list[str] = []
    contexts = source.get("section_contexts", [])
    for context in contexts:
        context_title = clean_whitespace(str(context.get("title", ""))).lower()
        snippets = [str(item) for item in context.get("definition_snippets", [])]
        if not snippets:
            continue
        if title and title in context_title:
            strong.extend(snippets)
        elif section in {"core paper", "core work"} and any(token in title for token in ("method", "analysis")) and any(token in context_title for token in ("method", "analysis", "simulation", "calculation")):
            strong.extend(snippets)
        elif section in {"core paper", "core work"} and any(token in title for token in ("model", "setup", "formalism", "framework")) and any(token in context_title for token in ("model", "setup", "formalism", "framework")):
            strong.extend(snippets)
        elif section in {"background", "motivation"} and any(token in context_title for token in ("introduction", "background")):
            strong.extend(snippets)
        elif section in {"core paper", "core work"} and any(token in context_title for token in ("model", "setup", "formalism", "framework", "analysis", "method")):
            fallback.extend(snippets)
        else:
            fallback.extend(snippets)
    candidates = _dedupe_preserving_order(strong) if strong else _dedupe_preserving_order(fallback)
    if not candidates:
        candidates.extend(str(item) for item in source.get("definition_snippets", []))
    return _dedupe_preserving_order(candidates)[:2]


def _equation_candidates_for_slide(slide: dict[str, Any], source: dict[str, Any]) -> list[str]:
    if str(source.get("source_kind", "")).lower() == "pdf":
        return []
    section = str(slide.get("section", "")).lower()
    title = str(slide.get("title", "")).lower()
    bound_context = _match_source_context_for_slide(slide, source)
    bound_title = clean_whitespace(str(bound_context.get("title", ""))).lower() if bound_context else ""
    strong: list[str] = []
    fallback: list[str] = []
    for entry in source.get("equation_entries", []):
        equation = clean_whitespace(str(entry.get("equation", "")))
        section_title = clean_whitespace(str(entry.get("section", ""))).lower()
        if not equation:
            continue
        if bound_title and bound_title == section_title:
            strong.append(equation)
        elif title and title in section_title:
            strong.append(equation)
        elif section in {"core paper", "core work"} and any(token in title for token in ("method", "analysis")) and any(token in section_title for token in ("method", "analysis", "simulation", "calculation")):
            strong.append(equation)
        elif section in {"core paper", "core work"} and any(token in title for token in ("model", "setup", "formalism", "framework")) and any(token in section_title for token in ("model", "setup", "formalism", "framework")):
            strong.append(equation)
        elif section in {"core paper", "core work"} and any(token in section_title for token in ("model", "setup", "formalism", "framework", "analysis", "method")):
            fallback.append(equation)
        else:
            fallback.append(equation)
    matches = _dedupe_preserving_order(strong) if strong else _dedupe_preserving_order(fallback)
    if not matches:
        matches = _usable_equation_snippets(source)
    return _dedupe_preserving_order(matches)[:2]


def _citation_candidates_for_slide(slide: dict[str, Any], source: dict[str, Any], deck_type: str) -> list[str]:
    if not _needs_local_citation(slide):
        return []
    if str(source.get("source_kind", "")).lower() == "pdf":
        return _pdf_primary_paper_citation_candidates(slide, source)
    section = str(slide.get("section", "")).lower()
    title = str(slide.get("title", "")).lower()
    primary = clean_whitespace(str(source.get("primary_citation", "")))
    refs = [clean_whitespace(str(item)) for item in source.get("reference_like_lines", []) if clean_whitespace(str(item))]
    bound_context = _match_source_context_for_slide(slide, source)
    if bound_context:
        candidates = [clean_whitespace(str(item)) for item in bound_context.get("citation_candidates", []) if clean_whitespace(str(item))]
        if not candidates:
            candidates = _citation_candidates_from_keys(source, bound_context.get("citation_keys", []), include_main=True)
        if candidates:
            return _dedupe_preserving_order(candidates)[:4]

    if section == "opening":
        if "roadmap" in title or "agenda" in title or "目录" in title or "提纲" in title:
            return []
        return [primary] if primary else refs[:1]

    if section == "results":
        figure = _match_figure_record_for_slide(slide, source)
        if figure:
            candidates = [clean_whitespace(str(item)) for item in figure.get("citation_candidates", []) if clean_whitespace(str(item))]
            if not candidates:
                candidates = _citation_candidates_from_keys(source, figure.get("citation_keys", []), include_main=True)
            return _dedupe_preserving_order(candidates or ([primary] if primary else refs[:1]))[:4]
        return _context_candidates_for_keywords(source, ("result", "results", "analysis", "phenomenology"), include_main=True)

    if section in {"core paper", "core work"}:
        if any(token in title for token in ("method", "analysis", "strategy", "推导", "方法", "分析")):
            return _context_candidates_for_keywords(source, ("method", "analysis", "simulation", "calculation"), include_main=True)
        return _context_candidates_for_keywords(source, ("model", "setup", "formalism", "framework"), include_main=True)

    if section in {"background", "motivation"}:
        candidates = _context_candidates_for_keywords(source, ("introduction", "background"), include_main=True)
        if len(candidates) < 3:
            candidates.extend(refs[: max(0, 3 - len(candidates))])
        return _dedupe_preserving_order(candidates)[:4]

    if section in {"critique", "closing"}:
        candidates = [primary] if primary else []
        if deck_type == "group-meeting":
            candidates.extend(_context_candidates_for_keywords(source, ("result", "discussion", "conclusion"), include_main=False))
        return _dedupe_preserving_order(candidates)[:4]

    return _dedupe_preserving_order(([primary] if primary else []) + refs[:2])[:4]


def _enrich_slides_with_source_bindings(slides: list[dict[str, Any]], source: dict[str, Any], deck_type: str) -> None:
    for slide in slides:
        bound_context = _match_source_context_for_slide(slide, source)
        citation_candidates = _citation_candidates_for_slide(slide, source, deck_type)
        if citation_candidates:
            slide["citation_candidates"] = citation_candidates
            slide["citation_binding_mode"] = str(source.get("citation_binding_quality", ""))
        symbol_candidates = _symbol_candidates_for_slide(slide, source)
        if symbol_candidates and str(slide.get("section", "")).lower() in {"background", "core work", "core paper"}:
            slide["symbol_candidates"] = symbol_candidates
        definition_candidates = _definition_candidates_for_slide(slide, source)
        if definition_candidates and str(slide.get("section", "")).lower() in {"background", "core work", "core paper"}:
            slide["definition_candidates"] = definition_candidates
        equation_candidates = _equation_candidates_for_slide(slide, source)
        if equation_candidates and str(slide.get("section", "")).lower() in {"core work", "core paper"}:
            slide["equation_candidates"] = equation_candidates
        if isinstance(bound_context, dict):
            formalism_steps = [item for item in bound_context.get("formalism_steps", []) if isinstance(item, dict)]
            if formalism_steps and str(slide.get("section", "")).lower() in {"core work", "core paper", "results"}:
                slide["formalism_steps"] = formalism_steps[:2]


def _adjust_slide_count_for_content(source: dict[str, Any], deck_type: str, slide_count: int) -> int:
    if deck_type == "assessment":
        works = len(_representative_works(source))
        content_cap = max(10, 7 + works * 3)
        return min(slide_count, content_cap)

    figures = _normalize_figure_titles(source.get("figure_captions", []))
    section_count = len(source.get("section_titles", []))
    if deck_type == "conference":
        content_cap = max(12, 8 + len(figures) + min(section_count, 5))
        return min(slide_count, content_cap)
    if deck_type == "group-meeting":
        content_cap = max(14, 9 + max(len(figures), 2) * 2 + min(section_count, 4))
        return min(slide_count, content_cap)
    return slide_count


def _append_slide(
    slides: list[dict[str, Any]],
    section: str,
    title: str,
    purpose: str,
    key_points: list[str],
    suggested_visual: str,
    citation_rule: str,
) -> None:
    slides.append(
        {
            "slide": len(slides) + 1,
            "section": section,
            "title": title,
            "purpose": purpose,
            "key_points": key_points,
            "suggested_visual": suggested_visual,
            "citation_rule": citation_rule,
        }
    )


def _push_emphasis_candidate(
    candidates: list[tuple[int, str]],
    seen: set[str],
    term: str,
    position: int,
) -> None:
    cleaned = clean_whitespace(term.strip(" .,:;()[]{}"))
    if not cleaned:
        return
    lowered = cleaned.lower()
    if lowered in seen or lowered in EMPHASIS_STOPWORDS:
        return
    if len(cleaned) < 2 or len(cleaned) > 40:
        return
    if len(cleaned.split()) > 5:
        return
    if re.fullmatch(r"[\d.\-+/]+", cleaned):
        return
    seen.add(lowered)
    candidates.append((max(position, 0), cleaned))


def _match_phrase_with_original_case(text: str, phrase: str) -> tuple[str, int] | None:
    match = re.search(rf"\b{re.escape(phrase)}\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    return clean_whitespace(match.group(0)), match.start()


def _extract_emphasis_terms_from_text(text: str) -> list[tuple[int, str]]:
    corpus = clean_whitespace(text)
    if not corpus:
        return []

    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()

    for phrase in SCIENTIFIC_EMPHASIS_PHRASES:
        matched = _match_phrase_with_original_case(corpus, phrase)
        if matched:
            term, position = matched
            _push_emphasis_candidate(candidates, seen, term, position)

    for match in re.finditer(r"\b[A-Z]{2,}[A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*\b", corpus):
        _push_emphasis_candidate(candidates, seen, match.group(0), match.start())
    for match in re.finditer(r"\b[A-Za-z]*\d+[A-Za-z0-9-]*\b", corpus):
        _push_emphasis_candidate(candidates, seen, match.group(0), match.start())
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9]*[a-z][A-Z][A-Za-z0-9-]*\b", corpus):
        _push_emphasis_candidate(candidates, seen, match.group(0), match.start())
    for match in re.finditer(r'"([^"]{3,36})"', corpus):
        _push_emphasis_candidate(candidates, seen, match.group(1), match.start(1))

    candidates.sort(key=lambda item: (item[0], len(item[1])))
    return candidates


def _suggest_blue_emphasis_terms(slide: dict[str, Any], source: dict[str, Any], max_terms: int = 4) -> list[str]:
    title = str(slide.get("title", ""))
    if str(slide.get("section", "")).lower() == "results":
        title = _strip_figure_label(title)
    text_blocks: list[str] = [
        title,
        str(slide.get("purpose", "")),
    ]
    if str(slide.get("section", "")).lower() == "opening":
        text_blocks.append(str(source.get("title", "")))
    if str(slide.get("section", "")).lower() in {"core work", "core paper"}:
        text_blocks.extend(str(item) for item in source.get("equation_snippets", [])[:1])
    text_blocks.extend(str(point) for point in slide.get("key_points", []))
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for offset, block in enumerate(text_blocks):
        for position, term in _extract_emphasis_terms_from_text(block):
            _push_emphasis_candidate(candidates, seen, term, position + offset * 1000)

    return [term for _, term in sorted(candidates, key=lambda item: item[0])[:max_terms]]


def _shorten_title(text: str, max_chars: int = 72) -> str:
    cleaned = clean_whitespace(text)
    if len(cleaned) <= max_chars:
        return cleaned
    if ":" in cleaned:
        left, right = cleaned.split(":", 1)
        left = left.strip()
        right = clean_whitespace(right)
        duplicate_prefix = re.compile(rf"^{re.escape(left)}\s*:\s*", flags=re.IGNORECASE)
        right = duplicate_prefix.sub("", right)
        if len(left) + 2 < max_chars and right:
            budget = max_chars - len(left) - 2
            if len(right) > budget:
                right = right[:budget].rsplit(" ", 1)[0].strip() or right[:budget].strip()
            combined = f"{left}: {right}".rstrip(" -,:;")
            if combined:
                return combined
        cleaned = left
    truncated = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    return truncated.rstrip(" -,:;") or cleaned[:max_chars].strip()


def _compress_key_point(text: str, max_chars: int = 135) -> str:
    cleaned = clean_whitespace(text)
    if len(cleaned) <= max_chars:
        return cleaned
    clauses = [clean_whitespace(part) for part in re.split(r"(?<=[.;:])\s+", cleaned) if clean_whitespace(part)]
    if clauses:
        first = clauses[0]
        if len(first) <= max_chars:
            return first.rstrip(" ,;:") + ("." if not first.endswith((".", "?", "!")) else "")
    truncated = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    if not truncated:
        truncated = cleaned[:max_chars].strip()
    return truncated.rstrip(" ,;:") + "..."


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = clean_whitespace(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        unique.append(cleaned)
        seen.add(key)
    return unique


def _infer_layout_density(slide: dict[str, Any]) -> str:
    title = str(slide.get("title", "")).lower()
    visual = str(slide.get("suggested_visual", "")).lower()
    section = str(slide.get("section", "")).lower()
    if any(token in title for token in ("figure", "fig.", "table")):
        return "figure-heavy"
    if any(token in visual for token in ("large figure", "parameter-space", "imported figure", "zoom", "plot")):
        return "figure-heavy"
    if section in {"closing", "opening"}:
        return "light"
    return "standard"


def _point_cap_for_slide(slide: dict[str, Any]) -> int:
    density = _infer_layout_density(slide)
    if density == "light":
        return 4
    if density == "figure-heavy":
        return 3
    return 3


def _layout_advice_for_slide(slide: dict[str, Any], language: str = "en") -> str:
    density = _infer_layout_density(slide)
    if density == "figure-heavy":
        return _lt(language, "Keep one dominant figure and at most two short dot-led explanation blocks beside or below it.", "保留一张主图，旁边或下方至多放两小段点引导说明。")
    if density == "light":
        return _lt(language, "Use generous whitespace and avoid filling the slide just because room is available.", "保留足够留白，不要因为版面有空间就强行塞内容。")
    return _lt(language, "Use dot-led subsection headings and keep each text block short enough to breathe.", "用点引导的小标题，并让每段文字都保持足够短、足够透气。")


def _annotate_slide_rendering(slide: dict[str, Any], source: dict[str, Any], language: str = "en") -> None:
    emphasis_terms = _suggest_blue_emphasis_terms(slide, source)
    slide["blue_emphasis_terms"] = emphasis_terms
    section = str(slide.get("section", "")).lower()
    if section in {"core work", "core paper"} and not slide.get("equation_candidates"):
        equation_candidates = _usable_equation_snippets(source)
        if equation_candidates:
            slide["equation_candidates"] = equation_candidates[:2]
    slide["rendering_hints"] = {
        "subsection_heading_style": _lt(language, "Use a colored dot-led subsection heading, then black body text on the same line or the next line.", "使用带颜色的点引导小标题，后面接同一行或下一行的黑色正文。"),
        "emphasis_color": BLUE_EMPHASIS_COLOR,
        "max_emphasis_terms": 4,
        "emphasis_terms": emphasis_terms,
        "body_text_rule": _lt(language, "Keep body text black and use blue only for the listed key terms or short phrases.", "正文保持黑色，蓝色只用于列出的关键词或短语。"),
        "layout_density": _infer_layout_density(slide),
        "layout_advice": _layout_advice_for_slide(slide, language),
    }


def _default_rendering_contract() -> dict[str, Any]:
    return {
        "content_title": {
            "font": "DengXian/等线(正文)",
            "size_pt": 44,
            "color": TITLE_BLUE,
        },
        "subsection_heading": {
            "marker": "·",
            "font": "Helvetica",
            "size_pt": 28,
            "bold": True,
            "color": PKU_RED,
        },
        "body_text": {
            "font": "Helvetica",
            "size_pt": 26,
            "color": "#000000",
        },
        "emphasis_text": {
            "font": "Helvetica",
            "color": BLUE_EMPHASIS_COLOR,
            "render_mode": "rich-text segments",
            "scope": "Only highlight the per-slide emphasis terms or short phrases, never whole paragraphs.",
            "max_terms_per_slide": 4,
        },
        "footer": {
            "font": "Helvetica",
            "size_pt": 18,
            "color": "#000000",
            "layout": "Presenter footer left, page number right, both below the bottom divider.",
        },
        "divider_rules": {
            "top_rule": "Black textured divider below the blue title.",
            "bottom_rule": "Black textured divider above the footer.",
            "avoid_vertical_accent_bars": True,
        },
        "render_validation": {
            "script": "scripts/render_layout_guard.mjs",
            "inspect_artifact": "inspect.ndjson",
            "checks": [
                "Width-aware wrapped-text height estimation for each editable text box.",
                "Containment checks for colored or boxed callouts so title/body text stays inside the card.",
                "Per-slide text-region collision detection after estimated wrapping.",
                "Stop export when any overflow or collision remains unresolved.",
            ],
            "citation_policy": "If a local citation does not fit inside a colored card cleanly, move the citation outside the card instead of shrinking the scientific text below readability.",
        },
    }


def _rendering_contract_for_style(template: dict[str, Any]) -> dict[str, Any]:
    contract = _default_rendering_contract()
    contract["style_source"] = {
        "mode": template.get("mode", "builtin"),
        "source": template.get("source", ""),
        "file": template.get("file", ""),
        "resolved_file": template.get("resolved_file", template.get("file", "")),
        "template_required": bool(template.get("template_required", False)),
    }
    if template.get("mode") == "builtin":
        contract["style_source"]["note"] = "Use the built-in academic rendering contract even if no .pptx template is available."
        return contract

    profile = template.get("profile", {}) if isinstance(template.get("profile", {}), dict) else {}
    fonts = profile.get("fonts", {}) if isinstance(profile.get("fonts", {}), dict) else {}
    colors = profile.get("colors", {}) if isinstance(profile.get("colors", {}), dict) else {}
    major_font = clean_whitespace(str(fonts.get("major_latin", "")))
    minor_font = clean_whitespace(str(fonts.get("minor_latin", "")))
    if major_font:
        contract["content_title"]["font"] = major_font
    if minor_font:
        contract["subsection_heading"]["font"] = minor_font
        contract["body_text"]["font"] = minor_font
        contract["emphasis_text"]["font"] = minor_font
        contract["footer"]["font"] = minor_font
    if colors.get("accent1"):
        contract["content_title"]["color"] = colors["accent1"]
    if colors.get("accent2"):
        contract["subsection_heading"]["color"] = colors["accent2"]
    if colors.get("dk1", "").startswith("#"):
        contract["body_text"]["color"] = colors["dk1"]
        contract["footer"]["color"] = colors["dk1"]
    contract["style_source"]["note"] = "Preserve the user or bundled PPTX template master, theme colors, and footer geometry during final authoring."
    if profile.get("slide_size"):
        contract["style_source"]["slide_size"] = profile["slide_size"]
    return contract


def _slide_time_weight(slide: dict[str, Any], deck_type: str) -> float:
    section = str(slide.get("section", "")).lower()
    density = _infer_layout_density(slide)
    weights_by_type = {
        "conference": {
            "opening": 0.7,
            "motivation": 1.1,
            "core work": 1.15,
            "results": 1.35,
            "closing": 0.8,
        },
        "group-meeting": {
            "opening": 0.8,
            "background": 1.1,
            "core paper": 1.2,
            "results": 1.4,
            "critique": 1.05,
            "closing": 0.75,
        },
        "assessment": {
            "opening": 0.7,
            "overview": 0.95,
            "achievements": 1.0,
            "representative work": 1.2,
            "closing": 0.8,
        },
    }
    weight = weights_by_type.get(deck_type, {}).get(section, 1.0)
    if density == "figure-heavy":
        weight += 0.25
    if "summary" in str(slide.get("title", "")).lower() or "takeaways" in str(slide.get("title", "")).lower():
        weight *= 0.9
    return max(weight, 0.4)


def _assign_suggested_minutes(slides: list[dict[str, Any]], talk_minutes: int, deck_type: str) -> None:
    if not slides:
        return
    weights = [_slide_time_weight(slide, deck_type) for slide in slides]
    total_weight = sum(weights) or float(len(slides))
    assigned = [round(talk_minutes * weight / total_weight, 2) for weight in weights]
    if assigned:
        delta = round(talk_minutes - sum(assigned), 2)
        assigned[-1] = round(max(0.2, assigned[-1] + delta), 2)
    for slide, minutes in zip(slides, assigned):
        slide["suggested_minutes"] = minutes


def _review_check(name: str, status: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
    }


def _review_finding(
    severity: str,
    message: str,
    slide_number: int | None = None,
    resolved_by_automation: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "severity": severity,
        "message": message,
        "resolved_by_automation": resolved_by_automation,
    }
    if slide_number is not None:
        payload["slide"] = slide_number
    return payload


def _expected_slide_markers(deck_type: str) -> list[str]:
    if deck_type == "conference":
        return ["roadmap", "motivation", "summary"]
    if deck_type == "assessment":
        return ["agenda", "publications", "funding", "talks", "future"]
    if deck_type == "group-meeting":
        return ["roadmap", "setup", "method", "limitations", "takeaways"]
    return []


def _plan_has_marker(plan: dict[str, Any], marker: str) -> bool:
    aliases = SECTION_ALIASES.get(marker.lower(), (marker.lower(),))
    for slide in plan.get("slides", []):
        haystack = " ".join(
            [
                str(slide.get("section", "")),
                str(slide.get("title", "")),
                str(slide.get("purpose", "")),
            ]
        ).lower()
        if any(alias in haystack for alias in aliases):
            return True
    return False


def _bound_argument_roles(plan: dict[str, Any]) -> list[tuple[int, str]]:
    roles: list[tuple[int, str]] = []
    for slide in plan.get("slides", []):
        role = clean_whitespace(str(slide.get("source_context_role", "")))
        if role:
            roles.append((int(slide.get("slide", 0)), role))
    return roles


def _normalized_formalism_chain(source: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in source.get("formalism_chain", []):
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "section": clean_whitespace(str(item.get("section", ""))),
                "role": clean_whitespace(str(item.get("role", ""))),
                "equation": clean_whitespace(str(item.get("equation", ""))),
                "equation_role": clean_whitespace(str(item.get("equation_role", ""))),
                "input_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("input_symbols", []) if clean_whitespace(str(symbol))][:4],
                "output_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("output_symbols", []) if clean_whitespace(str(symbol))][:4],
                "carry_symbols": [clean_whitespace(str(symbol)) for symbol in item.get("carry_symbols", []) if clean_whitespace(str(symbol))][:4],
            }
        )
    return result


def review_and_optimize_plan(
    plan: dict[str, Any],
    source: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    optimized = deepcopy(plan)
    source = source or {}
    language = str(optimized.get("language", "en"))
    findings: list[dict[str, Any]] = []
    checks: list[dict[str, str]] = []
    optimization_actions: list[dict[str, Any]] = []

    presenter = optimized.get("presenter", {})
    footer = clean_whitespace(str(presenter.get("footer_label", "")))
    if footer:
        checks.append(_review_check("presenter_footer", "pass", f"Footer label resolved as `{footer}`."))
    else:
        checks.append(_review_check("presenter_footer", "warn", "Presenter footer label is empty; pass presenter metadata before final authoring."))
        findings.append(_review_finding("warning", "Presenter footer label is missing; provide presenter metadata before final authoring."))

    expected_ratio = SLIDES_PER_MINUTE[optimized["deck_type"]]
    actual_ratio = optimized["slide_count"] / max(int(optimized.get("minutes", 1)), 1)
    ratio_delta = abs(actual_ratio - expected_ratio)
    if ratio_delta <= 0.18:
        checks.append(_review_check("pace_vs_duration", "pass", f"Slides-per-minute ratio `{actual_ratio:.2f}` matches the target pace for `{optimized['deck_type']}`."))
    else:
        checks.append(_review_check("pace_vs_duration", "warn", f"Slides-per-minute ratio `{actual_ratio:.2f}` is farther from the heuristic target `{expected_ratio:.2f}`."))
        findings.append(_review_finding("warning", "Slide count and speaking time are somewhat misaligned; consider a final timing rehearsal."))

    source_kind = str(source.get("source_kind") or optimized.get("source_kind") or "").lower()
    if source_kind == "pdf":
        checks.append(_review_check("source_quality", "warn", "PDF-only extraction is the noisiest path for abstracts, section titles, and figure captions."))
        findings.append(_review_finding("warning", "Source input is PDF-only. Prefer TeX/arXiv source or a clean Markdown conversion for the cleanest auto-review and authoring results."))
    elif source_kind in {"tex", "tex-dir", "tex-archive"}:
        checks.append(_review_check("source_quality", "pass", "TeX/arXiv-like source gives the cleanest structure for planning and review."))
    elif source_kind == "markdown":
        checks.append(_review_check("source_quality", "pass", "Markdown source is clean enough for reliable planning and review."))

    for marker in _expected_slide_markers(optimized["deck_type"]):
        if _plan_has_marker(optimized, marker):
            checks.append(_review_check(f"required_marker:{marker}", "pass", f"Found the expected `{marker}` content."))
        else:
            checks.append(_review_check(f"required_marker:{marker}", "warn", f"Missing an expected `{marker}` slide or subsection."))
            findings.append(_review_finding("warning", f"Expected `{marker}` content is missing from the current slide plan."))

    source_roles = [str(context.get("role", "")) for context in _source_argument_contexts(source) if clean_whitespace(str(context.get("role", "")))]
    plan_roles = [role for _, role in _bound_argument_roles(optimized)]
    if optimized.get("deck_type") in {"conference", "group-meeting"} and source_roles:
        if plan_roles:
            checks.append(_review_check("argument_binding", "pass", f"Planner bound `{len(plan_roles)}` slide(s) to explicit source sections."))
        else:
            checks.append(_review_check("argument_binding", "warn", "Planner did not bind slides to explicit source sections."))
            findings.append(_review_finding("warning", "The slide plan is not grounded in explicit source sections yet; it may drift back toward a generic talk skeleton."))

        for role in ("background", "setup", "method", "results"):
            if role in source_roles and role not in plan_roles:
                checks.append(_review_check(f"argument_role:{role}", "warn", f"Source contains a `{role}` section but the current deck plan does not bind a slide to it."))
                findings.append(_review_finding("warning", f"The current plan skips a source section with role `{role}`."))
            elif role in source_roles:
                checks.append(_review_check(f"argument_role:{role}", "pass", f"Source role `{role}` is represented in the plan."))

        first_result = next((slide_no for slide_no, role in _bound_argument_roles(optimized) if role == "results"), None)
        first_setup_or_method = next((slide_no for slide_no, role in _bound_argument_roles(optimized) if role in {"setup", "method"}), None)
        if first_result is not None and first_setup_or_method is not None and first_result < first_setup_or_method:
            checks.append(_review_check("argument_order", "warn", "A result slide appears before the first setup/method slide."))
            findings.append(_review_finding("warning", "The current slide order reaches results before the setup or method has been established."))
        elif plan_roles:
            checks.append(_review_check("argument_order", "pass", "Core setup/method material appears before the main results."))

    formalism_chain = _normalized_formalism_chain(source)
    if source_kind in {"tex", "tex-dir", "tex-archive"}:
        if formalism_chain:
            checks.append(_review_check("formalism_chain", "pass", f"Recovered `{len(formalism_chain)}` formalism step(s) from the TeX/arXiv source."))
        else:
            checks.append(_review_check("formalism_chain", "warn", "No formalism chain was recovered from the TeX/arXiv source."))
            findings.append(_review_finding("warning", "TeX/arXiv source is available, but no section-level formalism chain was recovered."))
        for role in ("setup", "method", "results"):
            if role in source_roles and not any(step.get("role") == role for step in formalism_chain):
                checks.append(_review_check(f"formalism_role:{role}", "warn", f"No formalism step was recovered for the `{role}` role."))
                findings.append(_review_finding("warning", f"The TeX/arXiv source contains a `{role}` section, but the formalism chain did not recover a matching step."))
        previous_outputs: list[str] = []
        for step in formalism_chain:
            role = clean_whitespace(str(step.get("role", "")))
            outputs = [clean_whitespace(str(item)) for item in step.get("output_symbols", []) if clean_whitespace(str(item))]
            inputs = [clean_whitespace(str(item)) for item in step.get("input_symbols", []) if clean_whitespace(str(item))]
            carries = [clean_whitespace(str(item)) for item in step.get("carry_symbols", []) if clean_whitespace(str(item))]
            if role == "method" and previous_outputs and not carries and not inputs:
                findings.append(_review_finding("warning", f"The `{role}` formalism step in section `{step.get('section', '')}` does not visibly carry symbols from the earlier chain; verify the logical bridge manually."))
            if role == "results" and previous_outputs and not carries and not inputs:
                findings.append(_review_finding("warning", f"The `{role}` formalism step in section `{step.get('section', '')}` does not visibly map earlier quantities into the final observable; verify the logical bridge manually."))
            previous_outputs = _dedupe_preserving_order(previous_outputs + outputs)[:8]

    if source_kind == "pdf":
        checks.append(_review_check("pdf_citation_binding", "warn", "PDF-only mode now restricts automatic citations to the source paper itself rather than guessing local background references."))
        findings.append(_review_finding("note", "Automatic PDF citation binding is intentionally conservative: only the source paper is auto-bound, and extra local references should be added manually if needed."))

    for slide in optimized.get("slides", []):
        actions_for_slide: list[str] = []
        original_title = clean_whitespace(str(slide.get("title", "")))
        shortened_title = _shorten_title(original_title)
        if shortened_title != original_title:
            slide["title"] = shortened_title
            actions_for_slide.append("shortened an overlong slide title")
            findings.append(_review_finding("note", f"Slide title was shortened for layout stability: `{original_title}` -> `{shortened_title}`.", slide_number=slide["slide"], resolved_by_automation=True))

        point_cap = _point_cap_for_slide(slide)
        original_points = [str(point) for point in slide.get("key_points", [])]
        normalized_points = [_compress_key_point(point, 125 if _infer_layout_density(slide) == "figure-heavy" else 140) for point in original_points]
        normalized_points = _dedupe_preserving_order(normalized_points)
        if len(normalized_points) > point_cap:
            normalized_points = normalized_points[:point_cap]
            actions_for_slide.append(f"reduced key points to {point_cap}")
            findings.append(_review_finding("note", f"Compressed slide text to fit the expected density for this layout.", slide_number=slide["slide"], resolved_by_automation=True))
        slide["key_points"] = normalized_points
        if not normalized_points:
            findings.append(_review_finding("warning", "Slide has no content bullets after planning; add a concrete scientific claim before authoring.", slide_number=slide["slide"]))

        if not clean_whitespace(str(slide.get("citation_rule", ""))):
            findings.append(_review_finding("warning", "Slide is missing a citation rule; add a local citation before final authoring.", slide_number=slide["slide"]))
        elif _needs_local_citation(slide) and not slide.get("citation_candidates"):
            findings.append(_review_finding("warning", "Slide expects a local citation but no concrete citation candidates were bound automatically.", slide_number=slide["slide"]))
        elif source_kind == "pdf" and slide.get("citation_candidates"):
            non_primary = [
                item for item in slide.get("citation_candidates", [])
                if clean_whitespace(str(item)) != clean_whitespace(str(source.get("primary_citation", "")))
            ]
            if non_primary:
                findings.append(_review_finding("warning", "PDF-only auto citation binding attached non-primary references; verify them manually before delivery.", slide_number=slide["slide"]))
        if source_kind in {"tex", "tex-dir", "tex-archive"} and str(slide.get("section", "")).lower() in {"core work", "core paper"}:
            if not slide.get("symbol_candidates") and not slide.get("equation_candidates"):
                findings.append(_review_finding("warning", "TeX/arXiv source is available, but this core slide has no bound symbol or equation anchors.", slide_number=slide["slide"]))
            if str(slide.get("source_context_role", "")) in {"setup", "method", "results"} and not slide.get("formalism_steps"):
                findings.append(_review_finding("warning", "This core slide is bound to a formal section but has no recovered formalism-chain step.", slide_number=slide["slide"]))

        _annotate_slide_rendering(slide, source, language=language)
        if slide.get("blue_emphasis_terms"):
            actions_for_slide.append("generated blue emphasis terms")
        else:
            findings.append(_review_finding("note", "No strong blue-emphasis terms were detected automatically; keep this slide visually plain rather than forcing decorative emphasis.", slide_number=slide["slide"], resolved_by_automation=True))

        slide["review_notes"] = [
            slide["rendering_hints"]["layout_advice"],
            _lt(language, "Use the template's top and bottom divider rules; do not insert decorative vertical bars.", "沿用模板的上下分割线，不要再添加装饰性竖条。"),
            _lt(language, "If you use a colored or boxed callout, make sure the box truly contains the heading and body after wrapping; move local citations outside the box before shrinking the main text too far.", "如果使用彩色或带边框的提示框，要确保换行后标题和正文都真正装在框内；若本页引用挤不下，应先把引用移到框外，而不是一味缩小正文。"),
        ]
        if actions_for_slide:
            optimization_actions.append(
                {
                    "slide": slide["slide"],
                    "actions": actions_for_slide,
                }
            )

    unresolved = [item for item in findings if item["severity"] in {"warning", "error"} and not item["resolved_by_automation"]]
    status = "ok" if not unresolved else "needs-attention"
    resolved_count = len([item for item in findings if item["resolved_by_automation"]])
    summary = f"Auto-review completed with {len(checks)} checks, {resolved_count} automatic cleanups, and {len(unresolved)} remaining warning(s)."

    review = {
        "status": status,
        "summary": summary,
        "source_quality": source_kind or "unknown",
        "checks": checks,
        "findings": findings,
        "optimization_actions": optimization_actions,
    }
    optimized["review"] = {
        "status": status,
        "summary": summary,
        "source_quality": source_kind or "unknown",
    }
    return optimized, review


def render_review_report(review: dict[str, Any]) -> str:
    lines = [
        "# Deck Review",
        "",
        f"- Status: `{review.get('status', 'unknown')}`",
        f"- Summary: {review.get('summary', '')}",
        f"- Source quality: `{review.get('source_quality', 'unknown')}`",
        "",
        "## Checks",
    ]
    for check in review.get("checks", []):
        lines.append(f"- `{check['status']}` {check['name']}: {check['detail']}")

    findings = review.get("findings", [])
    if findings:
        lines.extend(["", "## Findings"])
        for finding in findings:
            slide_prefix = f"slide {finding['slide']}, " if "slide" in finding else ""
            suffix = " (auto-fixed)" if finding.get("resolved_by_automation") else ""
            lines.append(f"- `{finding['severity']}` {slide_prefix}{finding['message']}{suffix}")

    actions = review.get("optimization_actions", [])
    if actions:
        lines.extend(["", "## Auto Optimizations"])
        for action in actions:
            lines.append(f"- Slide {action['slide']}: {', '.join(action['actions'])}")

    return "\n".join(lines).rstrip() + "\n"


def _build_conference_plan(source: dict[str, Any], slide_count: int, language: str, audience: str) -> list[dict[str, Any]]:
    argument_contexts = _source_argument_contexts(source)
    roadmap_points = _argument_roadmap_points(argument_contexts) or [
        _localized_title(language, "Motivation", "动机"),
        _localized_title(language, "Setup", "设定"),
        _localized_title(language, "Method", "方法"),
        _localized_title(language, "Results", "结果"),
    ]
    slides: list[dict[str, Any]] = []
    _append_slide(slides, "Opening", source["title"], _lt(language, "Set the scientific topic and speaker context.", "交代报告主题和报告人信息。"), [_lt(language, "Present the talk title, author, affiliation, and date.", "展示报告标题、作者、单位和日期。")], _lt(language, "Template cover slide with theme image strip or institutional header.", "使用模板封面页，可带主题图片条或机构页眉。"), _lt(language, "If the talk title matches a paper title exactly, add a short publication reference.", "如果标题直接对应论文题目，封面页补上简短文献信息。"))
    _append_slide(slides, "Opening", _localized_title(language, "Roadmap", "报告提纲"), _lt(language, "Give the audience a map of the actual argument flow.", "按论文或报告材料的真实逻辑给听众一个结构地图。"), roadmap_points[:4], _lt(language, "Agenda slide in the chosen template style.", "按所选模板生成提纲页。"), _lt(language, "No citation needed unless borrowed phrasing is reused.", "除非直接借用他人表述，否则无需引用。"))
    _append_slide(slides, "Motivation", _localized_title(language, "Why This Problem Matters", "为什么这个问题重要"), _lt(language, "Explain the big-picture motivation before details.", "先讲清楚大图景中的物理动机，再进入细节。"), _plain_language_claim_points(source, language, audience), _lt(language, "One clean concept schematic or a single anchoring figure.", "用一张干净的概念示意图或锚点图。"), _lt(language, "Cite the motivating references if the background claim is not your own.", "如果背景判断不是自己的工作，需要引用动机性文献。"))
    remaining = slide_count - len(slides) - 2
    dynamic_contexts = [context for context in argument_contexts if context.get("role") != "summary"]
    selected_contexts = _select_argument_contexts(dynamic_contexts, remaining)
    _append_context_slides(slides, selected_contexts, source, "conference", language, audience)
    _append_figure_result_slides(slides, source, max(0, slide_count - len(slides) - 2), "conference", language, audience)

    _append_slide(slides, "Closing", _localized_title(language, "Summary And Outlook", "总结与展望"), _lt(language, "End with the smallest set of claims worth remembering.", "最后只保留最值得听众记住的几件事。"), [_lt(language, "One line for motivation.", "用一句话回顾动机。"), _lt(language, "One line for method.", "用一句话回顾方法。"), _lt(language, "One line for the main result.", "用一句话回顾主结果。"), _lt(language, "One line for next step or outlook.", "用一句话讲下一步或展望。")], _lt(language, "Short summary bullets with one anchor schematic if helpful.", "简短总结要点，必要时配一张锚点示意图。"), _lt(language, "Cite outlook material if it comes from other papers.", "如果展望内容来自他人工作，也要引用。"))
    _append_slide(slides, "Closing", _localized_title(language, "Backup", "备份页"), _lt(language, "Reserve a compact appendix for overflow material if time allows.", "为超时内容保留简短附录。"), [_lt(language, "Place extra derivations, parameter scans, or detailed citations here.", "把补充推导、参数扫描和详细引用放在这里。")], _lt(language, "Optional backup divider slide.", "可选的 backup 分隔页。"), _lt(language, "Keep citations on backup slides too.", "backup 页也要保留引用。"))
    return slides[:slide_count]


def _build_group_meeting_plan(source: dict[str, Any], slide_count: int, language: str, audience: str) -> list[dict[str, Any]]:
    argument_contexts = _source_argument_contexts(source)
    roadmap_points = _argument_roadmap_points(argument_contexts) or [
        _localized_title(language, "Question", "问题"),
        _localized_title(language, "Formalism", "形式设定"),
        _localized_title(language, "Method", "方法"),
        _localized_title(language, "Result", "结果"),
    ]
    slides: list[dict[str, Any]] = []
    _append_slide(slides, "Opening", source["title"], _lt(language, "Introduce the paper with full bibliographic context.", "用完整书目信息介绍这篇论文。"), [_lt(language, "Include author list or collaboration, venue, year, and arXiv or journal identifier.", "写清作者、合作组、期刊/会议、年份以及 arXiv 或 journal 编号。")], _lt(language, "Title slide with full citation.", "封面页附完整文献信息。"), _lt(language, "Always include the full paper citation on the title slide.", "封面页始终给出完整论文引用。"))
    _append_slide(slides, "Opening", _localized_title(language, "Question And Main Claim", "核心问题与主要结论"), _lt(language, "State the paper's central question and one-sentence claim before walking through the details.", "在进入细节之前，先说清论文的核心问题和一句话结论。"), _plain_language_claim_points(source, language, audience), _lt(language, "Short statement plus one orienting schematic.", "用短句主张配一张帮助定位的示意图。"), _lt(language, "Keep the source paper citation visible on this slide.", "这一页保持源论文引用可见。"))
    _append_slide(slides, "Opening", _localized_title(language, "Argument Roadmap", "论文论证结构"), _lt(language, "Map the talk onto the paper's actual section logic rather than a generic seminar skeleton.", "按论文自己的章节逻辑给出路线图，而不是套通用组会模板。"), roadmap_points[:4], _lt(language, "One clean roadmap slide using the paper's real section titles.", "用论文真实章节标题制作一页干净的路线图。"), _lt(language, "No extra citation needed beyond the source paper unless additional literature is introduced.", "除非引入额外文献，否则源论文引用即可。"))

    remaining = slide_count - len(slides) - 2
    dynamic_contexts = [context for context in argument_contexts if context.get("role") not in {"summary", "limitations"}]
    selected_contexts = _select_argument_contexts(dynamic_contexts, remaining)
    _append_context_slides(slides, selected_contexts, source, "group-meeting", language, audience)
    _append_figure_result_slides(slides, source, max(0, slide_count - len(slides) - 2), "group-meeting", language, audience)

    _append_slide(slides, "Critique", _localized_title(language, "Open Questions And Limitations", "开放问题与局限"), _lt(language, "Show that the paper has been critically read.", "体现出你对这篇文章做过真正的批判性阅读。"), _critique_points(language, audience), _lt(language, "Short critique slide with no clutter.", "简洁、不堆砌的 critique 页面。"), _lt(language, "Cite any comparative statements to other papers.", "涉及和其他工作的比较时需要引用。"))
    _append_slide(slides, "Closing", _localized_title(language, "Takeaways", "总结要点"), _lt(language, "End with the shortest faithful summary of the paper.", "用最短但忠实的方式总结整篇论文。"), [_lt(language, "Why it was done.", "为什么要做这件事。"), _lt(language, "What was done.", "具体做了什么。"), _lt(language, "What was learned.", "主要得到了什么。"), _lt(language, "What remains open.", "还留下了什么问题。")], _lt(language, "Four-line summary slide.", "四行式总结页。"), _lt(language, "Cite the main paper again if useful.", "必要时再引用一次主论文。"))
    return slides[:slide_count]


def _representative_works(source: dict[str, Any]) -> list[dict[str, Any]]:
    works = source.get("representative_works") or []
    if works:
        return [work for work in works if isinstance(work, dict)]
    papers = source.get("papers") or []
    result = []
    for paper in papers[:3]:
        if isinstance(paper, dict):
            result.append(
                {
                    "title": paper.get("title", "Representative Work"),
                    "motivation": paper.get("impact_note", "Explain why this work matters."),
                    "problem": paper.get("problem", "State the problem."),
                    "method": paper.get("method", "State the method."),
                    "result": paper.get("result", "State the main result."),
                }
            )
    if str(source.get("source_kind", "")).lower() == "pdf":
        role_order = {"background": 0, "setup": 1, "method": 2, "core": 2, "results": 3, "limitations": 4, "summary": 5}
        result = sorted(enumerate(result), key=lambda item: (role_order.get(str(item[1].get("role", "core")), 2), item[0]))
        return [item[1] for item in result]
    return result


def _build_assessment_plan(source: dict[str, Any], slide_count: int, language: str, audience: str) -> list[dict[str, Any]]:
    profile = source.get("profile", {})
    works = _representative_works(source)
    papers = source.get("papers", [])
    grants = source.get("grants", [])
    talks = source.get("talks", [])
    teaching = source.get("teaching", [])
    service = source.get("service", [])
    future_plan = source.get("future_plan", [])

    slides: list[dict[str, Any]] = []
    title = source.get("title") or f"{profile.get('name', 'Researcher')} Assessment"
    agenda_points: list[str] = []
    dashboard_blocks: list[tuple[str, str, list[str], str, str]] = []

    if papers:
        agenda_points.append(_lt(language, "Outputs and impact", "成果与影响"))
        dashboard_blocks.append(
            (
                "Achievements",
                _localized_title(language, "Publications And Research Output", "论文与科研产出"),
                [_lt(language, f"Total papers: {len(papers)}", f"论文总数：{len(papers)}"), _lt(language, "Group by status, venue, role, or topic.", "按状态、期刊、角色或主题分组。")],
                _lt(language, "Bar chart, table, or timeline.", "用柱图、表格或时间线。"),
                _lt(language, "Publication facts should be traceable to the source list.", "论文信息必须能追溯到输入数据。"),
            )
        )
    if grants:
        if _lt(language, "Funding, talks, teaching, service", "项目、报告、教学与服务") not in agenda_points:
            agenda_points.append(_lt(language, "Funding, talks, teaching, service", "项目、报告、教学与服务"))
        dashboard_blocks.append(
            (
                "Achievements",
                _localized_title(language, "Funding Overview", "项目经费概览"),
                [_lt(language, f"Total grants listed: {len(grants)}", f"项目总数：{len(grants)}"), _lt(language, "Highlight PI/co-PI role and major projects.", "突出 PI/co-PI 角色和重点项目。")],
                _lt(language, "Funding table or stacked bars.", "用经费表或堆叠图。"),
                _lt(language, "All amounts and project names must match the input data.", "金额和项目名称必须与输入一致。"),
            )
        )
    if talks or teaching or service:
        if _lt(language, "Funding, talks, teaching, service", "项目、报告、教学与服务") not in agenda_points:
            agenda_points.append(_lt(language, "Funding, talks, teaching, service", "项目、报告、教学与服务"))
        dashboard_blocks.append(
            (
                "Achievements",
                _localized_title(language, "Talks, Teaching, And Service", "报告、教学与服务"),
                [_lt(language, f"Talks: {len(talks)}", f"学术报告：{len(talks)}"), _lt(language, f"Teaching items: {len(teaching)}", f"教学项目：{len(teaching)}"), _lt(language, f"Service items: {len(service)}", f"服务事项：{len(service)}")],
                _lt(language, "Three-column dashboard or compact chart panel.", "三栏式 dashboard 或紧凑图表。"),
                _lt(language, "Use citations only when external rankings or conference metrics are quoted.", "只有引用外部排名或会议指标时才需要注释来源。"),
            )
        )
    if works:
        agenda_points.append(_lt(language, "Representative works", "代表性工作"))
    if future_plan:
        agenda_points.append(_lt(language, "Future plan", "未来计划"))
    agenda_points = _dedupe_preserving_order(agenda_points)[:4] or [
        _lt(language, "Outputs and impact", "成果与影响"),
        _lt(language, "Representative works", "代表性工作"),
        _lt(language, "Future plan", "未来计划"),
    ]

    _append_slide(slides, "Opening", title, _lt(language, "Set the assessment scope and presenter identity.", "说明汇报范围和报告人信息。"), [profile.get("name", _lt(language, "Presenter", "报告人")), profile.get("affiliation", _lt(language, "Affiliation", "单位"))], _lt(language, "Formal title slide with institutional branding.", "正式的封面页，保留机构风格。"), _lt(language, "If the title slide mentions representative publications, cite them.", "如果封面提到代表作，需要引用。"))
    _append_slide(slides, "Opening", _localized_title(language, "Agenda", "目录"), _lt(language, "Show the balance between achievements and representative work.", "展示成果概览与代表工作的整体比例。"), agenda_points, _lt(language, "Formal agenda slide.", "正式风格的目录页。"), _lt(language, "No citation needed.", "无需引用。"))
    _append_slide(slides, "Overview", _localized_title(language, "Research Overview", "研究概览"), _lt(language, "Give a one-slide overview of direction and themes.", "用一页概括研究方向与主线。"), [_lt(language, "State the main scientific themes.", "说明主要研究主题。"), _lt(language, "Position the work in the broader field.", "把工作放进更大的学科背景里。")], _lt(language, "Theme map or keyword cluster.", "用主题图或关键词簇。"), _lt(language, "Cite non-original field-overview graphics.", "如果用了他人的综述图，要引用。"))
    for section, block_title, points, visual, citation_rule in dashboard_blocks:
        _append_slide(slides, section, block_title, _lt(language, "Present this achievement block clearly and quantitatively.", "把这部分成果清楚而定量地展示出来。"), points, visual, citation_rule)

    remaining = slide_count - len(slides) - 1
    if works:
        slides_per_work = 2 if remaining <= 6 else 3
        work_count = max(1, min(len(works), max(1, remaining // slides_per_work)))
        for work in works[:work_count]:
            _append_slide(slides, "Representative Work", work.get("title", _localized_title(language, "Representative Work", "代表性工作")), _lt(language, "Introduce the representative work at a high level.", "从高层次介绍这项代表性工作。"), [work.get("motivation", _lt(language, "State the motivation.", "说明动机。")), work.get("problem", _lt(language, "State the problem.", "说明问题。"))], _lt(language, "One clear background or motivation slide.", "用一页清楚的背景或动机页。"), _lt(language, "Show the publication reference locally.", "本页展示论文引用。"))
            _append_slide(slides, "Representative Work", _localized_title(language, "Core Idea And Method", "核心思想与方法"), _lt(language, "Explain what was done without drowning the audience in technical detail.", "说明做了什么，但不要把听众淹没在技术细节里。"), [work.get("method", _lt(language, "State the method in plain language.", "用直白语言说明方法。"))], _lt(language, "Model schematic, reduced formalism, or pipeline.", "用模型示意、简化 formalism 或流程图。"), _lt(language, "Cite reused figures and equations.", "重用的图和方程都要引用。"))
            if slides_per_work == 3:
                _append_slide(slides, "Representative Work", _localized_title(language, "Key Result And Impact", "关键结果与影响"), _lt(language, "State why the work matters.", "说明这项工作为什么重要。"), [work.get("result", _lt(language, "State the main result and impact.", "说明主结果和影响。"))], _lt(language, "One main result figure or summary chart.", "用一张主结果图或总结图。"), _lt(language, "Keep the publication reference on the slide.", "本页继续保留论文引用。"))

    _append_slide(slides, "Closing", _localized_title(language, "Future Plan", "未来计划"), _lt(language, "End with the next-stage research trajectory.", "最后给出下一阶段研究路线。"), future_plan[:4] or [_lt(language, "List the next scientific directions, funding goals, or collaboration plans.", "列出下一步科学方向、项目目标或合作计划。")], _lt(language, "Short outlook slide.", "简短展望页。"), _lt(language, "No citation needed unless borrowing a roadmap graphic.", "除非借用了他人的路线图，否则无需引用。"))
    return slides[:slide_count]


def _resolve_presenter(
    source: dict[str, Any],
    presenter_name: str | None = None,
    presenter_affiliation: str | None = None,
    presenter_footer: str | None = None,
) -> dict[str, str]:
    profile = source.get("profile", {}) if isinstance(source.get("profile", {}), dict) else {}
    name = clean_whitespace(presenter_name or profile.get("name", ""))
    affiliation = clean_whitespace(presenter_affiliation or profile.get("affiliation", ""))
    footer = clean_whitespace(presenter_footer or "")
    if not footer and name and affiliation:
        footer = f"{name} ({affiliation})"
    elif not footer and name:
        footer = name
    elif not footer and affiliation:
        footer = affiliation
    return {
        "name": name,
        "affiliation": affiliation,
        "footer_label": footer,
    }


def build_deck_plan(
    source: dict[str, Any],
    deck_type: str,
    minutes: int | float | None = None,
    language: str = "en",
    audience: str = "experts",
    style_mode: str = "auto",
    preferred_template: str | None = None,
    presenter_name: str | None = None,
    presenter_affiliation: str | None = None,
    presenter_footer: str | None = None,
) -> dict[str, Any]:
    source = _finalize_source_payload(deepcopy(source))
    deck_type = deck_type.lower()
    slide_count = estimate_slide_count(deck_type, minutes)
    slide_count = _adjust_slide_count_for_content(source, deck_type, slide_count)
    template = choose_template(deck_type, language, preferred_template, style_mode=style_mode)
    talk_minutes = int(minutes or DEFAULT_MINUTES[deck_type])
    presenter = _resolve_presenter(
        source,
        presenter_name=presenter_name,
        presenter_affiliation=presenter_affiliation,
        presenter_footer=presenter_footer,
    )

    if deck_type == "conference":
        slides = _build_conference_plan(source, slide_count, language, audience)
    elif deck_type == "group-meeting":
        slides = _build_group_meeting_plan(source, slide_count, language, audience)
    elif deck_type == "assessment":
        slides = _build_assessment_plan(source, slide_count, language, audience)
    else:
        raise ValueError(f"Unsupported deck type: {deck_type}")

    _enrich_slides_with_source_bindings(slides, source, deck_type)
    _assign_suggested_minutes(slides, talk_minutes, deck_type)
    for slide in slides:
        _annotate_slide_rendering(slide, source, language=language)

    return {
        "deck_type": deck_type,
        "minutes": talk_minutes,
        "language": language,
        "audience": audience,
        "requested_style_mode": clean_whitespace(style_mode or "auto").lower() or "auto",
        "style_mode": template.get("mode", clean_whitespace(style_mode or "auto").lower() or "auto"),
        "template": template,
        "source_kind": source.get("source_kind", ""),
        "presenter": presenter,
        "slide_count": len(slides),
        "source_title": source.get("title", "Untitled Research Talk"),
        "formalism_chain": source.get("formalism_chain", []),
        "slides": slides,
        "rendering_contract": _rendering_contract_for_style(template),
        "global_rules": [
            _lt(language, "Use one coherent style source consistently: either the built-in academic contract or one selected PPTX template family.", "全程统一使用一种风格来源：要么是内置学术风格，要么是一套选定的 PPTX 模板。"),
            _lt(language, "Every slide should have one main takeaway.", "每页只承担一个主结论。"),
            _lt(language, "All non-original figures, tables, equations, and claims need slide-local citations.", "所有非原创图、表、方程和论断都需要本页引用。"),
            _lt(language, "Prefer large figures and reduced text.", "优先大图，减少正文堆砌。"),
            _lt(language, "Prefer dot-led subsection headings over decorative vertical accent bars on content slides.", "内容页优先使用点引导的小标题，而不是装饰性竖条。"),
            _lt(language, "Use blue emphasis only for a small number of important words or phrases, rendered as rich-text segments rather than whole blue paragraphs.", "蓝色高亮只用于少量真正重要的词或短语，而且应以局部富文本呈现，而不是整段变蓝。"),
            _lt(language, "Run the shared render-layout guard before export; no final deck should be delivered with text overflow, boxed-callout spill, or unresolved text collisions.", "导出前必须运行共享的版面检查；凡是有文字溢出、彩色框装不下内容或文本碰撞的页面，都不能直接交付。"),
        ],
    }


def render_narrative_plan(plan: dict[str, Any]) -> str:
    presenter = plan.get("presenter", {})
    rendering_contract = plan.get("rendering_contract", {})
    language = str(plan.get("language", "en"))
    lines = [
        f"# {plan['source_title']}",
        "",
        f"## {_lt(language, 'Deck Summary', '报告概览')}",
        f"- {_lt(language, 'Deck type', '报告类型')}: `{plan['deck_type']}`",
        f"- {_lt(language, 'Duration', '时长')}: `{plan['minutes']}` {_lt(language, 'minutes', '分钟')}",
        f"- {_lt(language, 'Language', '语言')}: `{plan['language']}`",
        f"- {_lt(language, 'Audience', '受众')}: `{plan['audience']}`",
        f"- {_lt(language, 'Requested style mode', '请求的风格模式')}: `{plan.get('requested_style_mode', plan.get('style_mode', 'auto'))}`",
        f"- {_lt(language, 'Style mode', '风格模式')}: `{plan.get('style_mode', plan['template'].get('mode', 'auto'))}`",
        f"- {_lt(language, 'Style source', '风格来源')}: `{plan['template'].get('file', '')}`",
        f"- {_lt(language, 'Style notes', '风格说明')}: {plan['template']['notes']}",
        f"- {_lt(language, 'Source kind', '源材料类型')}: `{plan.get('source_kind', '')}`",
        f"- {_lt(language, 'Formalism steps', '形式链步数')}: `{len(plan.get('formalism_chain', []))}`",
        f"- {_lt(language, 'Planned slide count', '计划页数')}: `{plan['slide_count']}`",
        f"- {_lt(language, 'Presenter name', '报告人')}: `{presenter.get('name', '')}`",
        f"- {_lt(language, 'Presenter affiliation', '报告单位')}: `{presenter.get('affiliation', '')}`",
        f"- {_lt(language, 'Footer label', '页脚标签')}: `{presenter.get('footer_label', '')}`",
        "",
        f"## {_lt(language, 'Global Rules', '全局规则')}",
    ]
    for rule in plan["global_rules"]:
        lines.append(f"- {rule}")
    if rendering_contract:
        render_validation = rendering_contract.get("render_validation", {})
        lines.extend(
            [
                "",
                f"## {_lt(language, 'Rendering Contract', '渲染约定')}",
                f"- {_lt(language, 'Title', '标题')}: `{rendering_contract.get('content_title', {}).get('font', '')}` `{rendering_contract.get('content_title', {}).get('size_pt', '')} pt`, `{rendering_contract.get('content_title', {}).get('color', '')}`.",
                f"- {_lt(language, 'Subsection heading', '小节标题')}: `{rendering_contract.get('subsection_heading', {}).get('marker', '·')}` plus `{rendering_contract.get('subsection_heading', {}).get('font', '')}` `{rendering_contract.get('subsection_heading', {}).get('size_pt', '')} pt`, `{rendering_contract.get('subsection_heading', {}).get('color', '')}`, {_lt(language, 'bold', '加粗')}.",
                f"- {_lt(language, 'Body text', '正文')}: `{rendering_contract.get('body_text', {}).get('font', '')}` `{rendering_contract.get('body_text', {}).get('size_pt', '')} pt`, `{rendering_contract.get('body_text', {}).get('color', '')}`.",
                f"- {_lt(language, 'Blue emphasis', '蓝色强调')}: {_lt(language, 'render only the listed terms using', '只对列出的词语使用')} `{rendering_contract.get('emphasis_text', {}).get('render_mode', 'rich-text segments')}` in `{rendering_contract.get('emphasis_text', {}).get('color', '')}`.",
                f"- {_lt(language, 'Footer', '页脚')}: `{rendering_contract.get('footer', {}).get('font', '')}` `{rendering_contract.get('footer', {}).get('size_pt', '')} pt`, `{rendering_contract.get('footer', {}).get('color', '')}`, {rendering_contract.get('footer', {}).get('layout', '')}",
                f"- {_lt(language, 'Style note', '风格说明')}: {rendering_contract.get('style_source', {}).get('note', '')}",
                f"- {_lt(language, 'Render guard', '版面检查')}: `{render_validation.get('script', '')}` on `{render_validation.get('inspect_artifact', '')}`.",
                f"- {_lt(language, 'Render checks', '检查内容')}: {', '.join(render_validation.get('checks', [])) or _lt(language, 'None', '无')}",
                f"- {_lt(language, 'Overflow policy', '溢出处理')}: {render_validation.get('citation_policy', '')}",
            ]
        )
    review = plan.get("review")
    if isinstance(review, dict):
        lines.extend(
            [
                "",
                f"## {_lt(language, 'Auto Review', '自动审查')}",
                f"- {_lt(language, 'Status', '状态')}: `{review.get('status', 'unknown')}`",
                f"- {_lt(language, 'Summary', '摘要')}: {review.get('summary', '')}",
                f"- {_lt(language, 'Source quality', '源材料质量')}: `{review.get('source_quality', 'unknown')}`",
            ]
        )
    lines.extend(["", f"## {_lt(language, 'Slide Plan', '逐页规划')}"])
    for slide in plan["slides"]:
        lines.extend(
            [
                f"### {slide['slide']}. {slide['title']}",
                f"- {_lt(language, 'Section', '分区')}: `{slide['section']}`",
                f"- {_lt(language, 'Bound source section', '绑定源章节')}: {slide.get('source_context_title', _lt(language, 'None', '无'))}",
                f"- {_lt(language, 'Bound source role', '绑定源角色')}: `{slide.get('source_context_role', '') or _lt(language, 'none', '无')}`",
                f"- {_lt(language, 'Purpose', '目的')}: {slide['purpose']}",
                f"- {_lt(language, 'Suggested time', '建议时间')}: `{slide['suggested_minutes']}` {_lt(language, 'min', '分钟')}",
                f"- {_lt(language, 'Visual', '视觉建议')}: {slide['suggested_visual']}",
                f"- {_lt(language, 'Citation rule', '引用规则')}: {slide['citation_rule']}",
                f"- {_lt(language, 'Layout note', '版式说明')}: {slide.get('rendering_hints', {}).get('layout_advice', '')}",
                f"- {_lt(language, 'Blue emphasis terms', '蓝色强调词')}: {', '.join(slide.get('blue_emphasis_terms', [])) or _lt(language, 'None', '无')}",
            ]
        )
        if slide.get("citation_candidates"):
            if slide.get("citation_binding_mode"):
                lines.append(f"- {_lt(language, 'Citation binding mode', '引用绑定模式')}: `{slide.get('citation_binding_mode', '')}`")
            lines.append(f"- {_lt(language, 'Citation candidates', '候选引用')}:")
            for item in slide.get("citation_candidates", []):
                lines.append(f"  - {item}")
        if slide.get("symbol_candidates"):
            lines.append(f"- {_lt(language, 'Symbol candidates', '候选符号定义')}:")
            for item in slide.get("symbol_candidates", []):
                lines.append(f"  - {item}")
        if slide.get("definition_candidates"):
            lines.append(f"- {_lt(language, 'Definition candidates', '候选定义说明')}:")
            for item in slide.get("definition_candidates", []):
                lines.append(f"  - {item}")
        if slide.get("equation_candidates"):
            lines.append(f"- {_lt(language, 'Equation candidates', '候选方程')}:")
            for item in slide.get("equation_candidates", []):
                lines.append(f"  - `{item}`")
        if slide.get("formalism_steps"):
            lines.append(f"- {_lt(language, 'Formalism chain', '形式链')}:")
            for step in slide.get("formalism_steps", []):
                if not isinstance(step, dict):
                    continue
                pieces = [
                    f"{_lt(language, 'role', '角色')}={step.get('role', '')}",
                    f"{_lt(language, 'input', '输入')}={', '.join(step.get('input_symbols', [])) or _lt(language, 'none', '无')}",
                    f"{_lt(language, 'output', '输出')}={', '.join(step.get('output_symbols', [])) or _lt(language, 'none', '无')}",
                ]
                if clean_whitespace(str(step.get("equation_role", ""))):
                    pieces.append(f"{_lt(language, 'equation role', '方程角色')}={step.get('equation_role', '')}")
                lines.append(f"  - {'; '.join(pieces)}")
        lines.append(f"- {_lt(language, 'Key points', '要点')}:")
        for point in slide["key_points"]:
            lines.append(f"  - {point}")
        for note in slide.get("review_notes", []):
            lines.append(f"  - {_lt(language, 'Review note', '审查提示')}: {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
