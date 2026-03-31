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


def normalize_corpus(raw_root: Path = RAW_MARKDOWN_ROOT, output_root: Path = KNOWLEDGE_BASE_ROOT) -> list[Path]:
    outputs: list[Path] = []
    for raw_markdown in sorted(raw_root.rglob("*.md")):
        meta_path = raw_markdown.with_suffix(".meta.json")
        metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        category = metadata.get("category") or categorize_source_path(raw_markdown.relative_to(raw_root))
        target_path = _resolve_target_path(output_root / category / raw_markdown.name)
        ensure_parent(target_path)

        body = normalize_math_entities(raw_markdown.read_text(encoding="utf-8"))
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
    return MATH_SEGMENT_PATTERN.sub(lambda match: _decode_math_entities(match.group(0)), markdown)


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
