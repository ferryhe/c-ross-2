from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.common import KNOWLEDGE_BASE_ROOT, RAW_MARKDOWN_ROOT, categorize_source_path, ensure_parent


FRONT_MATTER_ORDER = [
    "title",
    "category",
    "source_type",
    "source_file",
    "source_url",
    "publish_date",
    "converted_engine",
    "converted_at",
]

MATH_SEGMENT_PATTERN = re.compile(
    r"(?P<display_dollar>\$\$.*?\$\$)"
    r"|(?P<display_bracket>\\\[.*?\\\])"
    r"|(?P<inline_paren>\\\(.*?\\\))"
    r"|(?P<inline_dollar>(?<!\$)\$(?!\$).*?(?<!\\)\$)",
    re.DOTALL,
)

ENTITY_REPLACEMENTS = (
    (re.compile(r"&\s*lt;", re.IGNORECASE), "<"),
    (re.compile(r"&\s*gt;", re.IGNORECASE), ">"),
    (re.compile(r"&\s*amp;", re.IGNORECASE), "&"),
)

BROKEN_CJK_SUBSUP_WITH_INDEX_PATTERN = re.compile(
    r"(?P<op>[_^])\s*\{\s*\\(?P<label>[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+)\s*_(?P<index>[A-Za-z0-9]+)\s*\}"
)

BROKEN_CJK_SUBSUP_PATTERN = re.compile(
    r"(?P<op>[_^])\s*\{\s*\\(?P<label>[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+)\s*\}"
)

LEFT_ARRAY_CASES_PATTERN = re.compile(
    r"\\left\\\{\s*\\begin\{array\}\{[lcr\s]+\}(?P<body>.*?)\\end\{array\}\s*\\right\.",
    re.DOTALL,
)

CASES_ENV_PATTERN = re.compile(
    r"(?P<prefix>.*?)\\begin\{cases\}(?P<body>.*?)\\end\{cases\}(?P<suffix>.*)",
    re.DOTALL,
)

INLINE_MATH_PATTERN = re.compile(r"(?<!\$)\$(?!\$)(?P<body>.*?)(?<!\\)\$")

INLINE_PLAINIFY_BLOCKERS = (
    r"\frac",
    r"\sqrt",
    r"\sum",
    r"\times",
    r"\left",
    r"\right",
    r"\begin",
    r"\end",
    r"\min",
    r"\max",
    r"\operatorname",
    r"\in",
    r"\le",
    r"\ge",
    r"\dots",
    r"\cdot",
    "<",
    ">",
)

INLINE_WRAPPER_PATTERN = re.compile(r"\\(?:mathrm|mathbf|mathit|text)\s*\{([^{}]*)\}")
INLINE_SUBSUP_BRACES_PATTERN = re.compile(r"([_^])\s*\{([^{}]+)\}")
INLINE_SIMPLE_BRACES_PATTERN = re.compile(r"\{([^{}]+)\}")
INLINE_SPACE_AROUND_SCRIPT_PATTERN = re.compile(r"\s*([_^,])\s*")
INLINE_SYMBOL_TOKEN = r"[A-Za-z0-9\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaffα-ωΑ-ΩΔρβγμνπστυφχψω_,]+(?:\^[A-Za-z0-9\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff*]+)?"
SIMPLE_PLAIN_INLINE_PATTERN = re.compile(rf"^{INLINE_SYMBOL_TOKEN}$")
ASSIGNMENT_PLAIN_INLINE_PATTERN = re.compile(rf"^{INLINE_SYMBOL_TOKEN}\s*=\s*[-+−]?\d+(?:\.\d+)?(?:\s*%?)?$")
RANGE_PLAIN_INLINE_PATTERN = re.compile(rf"^{INLINE_SYMBOL_TOKEN}\s*-\s*{INLINE_SYMBOL_TOKEN}$")

LATEX_INLINE_REPLACEMENTS = {
    r"\rho": "ρ",
    r"\beta": "β",
    r"\Delta": "Δ",
    r"\alpha": "α",
    r"\gamma": "γ",
    r"\mu": "μ",
    r"\pi": "π",
    r"\sigma": "σ",
    r"\tau": "τ",
}

HEADING_PATTERN = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")


def normalize_corpus(raw_root: Path = RAW_MARKDOWN_ROOT, output_root: Path = KNOWLEDGE_BASE_ROOT) -> list[Path]:
    outputs: list[Path] = []
    for raw_markdown in sorted(raw_root.rglob("*.md")):
        meta_path = raw_markdown.with_suffix(".meta.json")
        metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        category = metadata.get("category") or categorize_source_path(raw_markdown.relative_to(raw_root))
        target_path = _resolve_target_path(output_root / category / raw_markdown.name)
        ensure_parent(target_path)

        merged_title = metadata.get("title") or raw_markdown.stem
        body = normalize_math_entities(raw_markdown.read_text(encoding="utf-8").lstrip("\ufeff"))
        body = _clean_body(body, merged_title)
        target_path.write_text(_render_front_matter(metadata, raw_markdown, body, category), encoding="utf-8")

        for asset_dir_name in metadata.get("asset_dirs", []):
            source_asset_dir = raw_markdown.parent / asset_dir_name
            if not source_asset_dir.is_dir():
                continue
            target_asset_dir = target_path.parent / asset_dir_name
            if target_asset_dir.exists():
                shutil.rmtree(target_asset_dir)
            shutil.copytree(source_asset_dir, target_asset_dir)

        outputs.append(target_path)
    return outputs


def normalize_math_entities(markdown: str) -> str:
    decoded = MATH_SEGMENT_PATTERN.sub(lambda match: _decode_math_entities(match.group(0)), markdown)
    return _plainify_inline_math_references(decoded)


def _decode_math_entities(segment: str) -> str:
    cleaned = segment
    for pattern, replacement in ENTITY_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    for _ in range(3):
        unescaped = html.unescape(cleaned)
        if unescaped == cleaned:
            break
        cleaned = unescaped
    cleaned = BROKEN_CJK_SUBSUP_WITH_INDEX_PATTERN.sub(_replace_broken_cjk_subsup_with_index, cleaned)
    cleaned = BROKEN_CJK_SUBSUP_PATTERN.sub(_replace_broken_cjk_subsup, cleaned)
    cleaned = LEFT_ARRAY_CASES_PATTERN.sub(_replace_left_array_cases, cleaned)
    cleaned = cleaned.replace("\xa0", " ")
    if cleaned.startswith("$$") and cleaned.endswith("$$") and r"\begin{cases}" in cleaned:
        return _rewrite_display_cases_as_math_fence(cleaned)
    return cleaned


def _plainify_inline_math_references(markdown: str) -> str:
    lines = markdown.splitlines()
    normalized_lines: list[str] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            normalized_lines.append(line)
            continue
        if in_fence or "$$" in line or stripped.startswith("|") or _line_is_only_inline_math(line):
            normalized_lines.append(line)
            continue
        normalized_lines.append(INLINE_MATH_PATTERN.sub(_replace_inline_math_reference, line))
    return "\n".join(normalized_lines)


def _replace_inline_math_reference(match: re.Match[str]) -> str:
    body = match.group("body")
    plain = _plainify_inline_math(body)
    if plain is None:
        return match.group(0)
    return f"`{plain}`"


def _plainify_inline_math(body: str) -> str | None:
    if any(token in body for token in INLINE_PLAINIFY_BLOCKERS):
        return None
    candidate = body.strip().replace("\xa0", " ")
    if not candidate:
        return None
    candidate = candidate.replace(r"\%", "%")
    for latex, replacement in LATEX_INLINE_REPLACEMENTS.items():
        candidate = candidate.replace(latex, replacement)
    previous = None
    while candidate != previous:
        previous = candidate
        candidate = INLINE_WRAPPER_PATTERN.sub(r"\1", candidate)
        candidate = INLINE_SUBSUP_BRACES_PATTERN.sub(r"\1\2", candidate)
        candidate = INLINE_SIMPLE_BRACES_PATTERN.sub(r"\1", candidate)
    candidate = re.sub(r"\\([A-Za-z]+)", r"\1", candidate)
    candidate = INLINE_SPACE_AROUND_SCRIPT_PATTERN.sub(r"\1", candidate)
    candidate = re.sub(r"\s*=\s*", " = ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip()
    if (
        SIMPLE_PLAIN_INLINE_PATTERN.fullmatch(candidate)
        or ASSIGNMENT_PLAIN_INLINE_PATTERN.fullmatch(candidate)
        or RANGE_PLAIN_INLINE_PATTERN.fullmatch(candidate)
    ):
        return candidate
    return None


def _line_is_only_inline_math(line: str) -> bool:
    if "$" not in line:
        return False
    remainder = INLINE_MATH_PATTERN.sub("", line)
    return not remainder.strip()


def _replace_broken_cjk_subsup_with_index(match: re.Match[str]) -> str:
    op = match.group("op")
    label = match.group("label")
    index = match.group("index")
    return f"{op}{{\\text{{{label}}}_{index}}}"


def _replace_broken_cjk_subsup(match: re.Match[str]) -> str:
    op = match.group("op")
    label = match.group("label")
    return f"{op}{{\\text{{{label}}}}}"


def _replace_left_array_cases(match: re.Match[str]) -> str:
    body = match.group("body").strip()
    return f"\\begin{{cases}} {body} \\end{{cases}}"


def _rewrite_display_cases_as_math_fence(segment: str) -> str:
    body = segment[2:-2].strip()
    normalized = CASES_ENV_PATTERN.sub(_format_cases_environment, body)
    return f"```math\n{normalized}\n```"


def _format_cases_environment(match: re.Match[str]) -> str:
    prefix = match.group("prefix")
    body = match.group("body").strip()
    suffix = match.group("suffix").lstrip()
    rows = [row.strip() for row in re.split(r"\s*\\\\\s*", body) if row.strip()]
    rendered_body = "\n".join(
        f"{row} \\\\" if index < len(rows) - 1 else row
        for index, row in enumerate(rows)
    )
    pieces = []
    if prefix:
        pieces.append(f"{prefix}\\begin{{cases}}")
    else:
        pieces.append(r"\begin{cases}")
    if rendered_body:
        pieces.append(rendered_body)
    end_line = r"\end{cases}"
    if suffix:
        end_line = f"{end_line} {suffix}"
    pieces.append(end_line)
    return "\n".join(pieces)


def _resolve_target_path(candidate: Path) -> Path:
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        alternate = candidate.with_name(f"{stem}-{index}{suffix}")
        if not alternate.exists():
            return alternate
        index += 1


def _render_front_matter(metadata: dict, raw_markdown: Path, body: str, category: str) -> str:
    merged = {
        "title": metadata.get("title") or raw_markdown.stem,
        "category": category,
        "source_type": metadata.get("source_type", raw_markdown.suffix),
        "source_file": metadata.get("source_file", raw_markdown.name),
        "source_url": metadata.get("source_url", ""),
        "publish_date": metadata.get("publish_date", ""),
        "converted_engine": metadata.get("converted_engine", ""),
        "converted_at": metadata.get("converted_at", ""),
    }
    lines = ["---"]
    for key in FRONT_MATTER_ORDER:
        lines.append(f"{key}: {_yaml_scalar(merged.get(key, ''))}")
    lines.append("---")
    lines.append("")
    lines.append(body.strip())
    lines.append("")
    return "\n".join(lines)


def _yaml_scalar(value: object) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    if any(char in text for char in [":", "#", "\n", '"']) or text.startswith(" ") or text.endswith(" "):
        return json.dumps(text, ensure_ascii=False)
    return text


def _clean_body(text: str, title: str) -> str:
    cleaned = _dedupe_consecutive_identical_headings(text)
    cleaned = _dedupe_leading_title_heading(cleaned, title)
    return cleaned


def _dedupe_consecutive_identical_headings(text: str) -> str:
    lines = text.splitlines()
    rendered: list[str] = []
    pending_blanks: list[str] = []
    previous_heading: tuple[str, str] | None = None
    only_blank_since_heading = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            pending_blanks.append(line)
            continue
        heading_match = HEADING_PATTERN.match(stripped)
        if heading_match:
            key = (heading_match.group("level"), heading_match.group("title"))
            if previous_heading == key and only_blank_since_heading:
                pending_blanks.clear()
                continue
            rendered.extend(pending_blanks)
            pending_blanks.clear()
            rendered.append(line)
            previous_heading = key
            only_blank_since_heading = True
            continue
        rendered.extend(pending_blanks)
        pending_blanks.clear()
        rendered.append(line)
        only_blank_since_heading = False

    rendered.extend(pending_blanks)
    return "\n".join(rendered)


def _dedupe_leading_title_heading(text: str, title: str) -> str:
    lines = text.splitlines()
    first_heading_index = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("_Note:"):
            continue
        match = HEADING_PATTERN.match(stripped)
        if not match:
            return text
        if match.group("level") != "#":
            return text
        first_heading_index = index
        break
    if first_heading_index is None:
        return text

    normalized_title = title.strip()
    first_heading = HEADING_PATTERN.match(lines[first_heading_index].strip())
    if not first_heading or first_heading.group("title").strip() != normalized_title:
        return text

    next_index = first_heading_index + 1
    while next_index < len(lines) and not lines[next_index].strip():
        next_index += 1
    if next_index >= len(lines):
        return text

    next_line = lines[next_index].strip()
    next_heading = HEADING_PATTERN.match(next_line)
    if next_heading and next_heading.group("level") == "#" and next_heading.group("title").strip() == normalized_title:
        del lines[next_index]
        while next_index < len(lines) and not lines[next_index].strip():
            del lines[next_index]
        return "\n".join(lines)
    if next_line == normalized_title:
        del lines[next_index]
        while next_index < len(lines) and not lines[next_index].strip():
            del lines[next_index]
        return "\n".join(lines)
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize raw Markdown into the final knowledge base corpus.")
    parser.add_argument("--raw-root", type=Path, default=RAW_MARKDOWN_ROOT)
    parser.add_argument("--output-root", type=Path, default=KNOWLEDGE_BASE_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = normalize_corpus(args.raw_root, args.output_root)
    print(f"[ok] normalized {len(outputs)} Markdown file(s) into {args.output_root}")


if __name__ == "__main__":
    main()
