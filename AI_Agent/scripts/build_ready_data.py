from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Add parent directory to path for sibling script imports when executed directly.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SCRIPT_DIR))

from build_index import (
    ARTICLE_PATTERN,
    CLAUSE_PATTERN,
    DEFAULT_SECTION_MAX_TOKENS,
    HEADING_PATTERN,
    REPO_ROOT,
    estimate_tokens,
    iter_markdown_files,
    split_structured_sections,
    strip_front_matter,
)


DEFAULT_SOURCE = REPO_ROOT / "Knowledge_Base_MarkDown"
DEFAULT_OUTPUT = DEFAULT_SOURCE / "ready_data"
RULE_NO_PATTERN = re.compile(r"规则第(\d+)号")
ATTACHMENT_NO_PATTERN = re.compile(r"附件(\d+(?:-\d+)?)")
NOTICE_TITLE_PATTERN = re.compile(r"关于(.+?)的通知")
RULE_REF_PATTERN = re.compile(r"规则第(\d+)号")
ATTACHMENT_REF_PATTERN = re.compile(r"附件(\d+(?:-\d+)?)")
MATH_BLOCK_PATTERN = re.compile(r"```math\s*(.*?)```|\$\$(.*?)\$\$", re.DOTALL | re.IGNORECASE)
TABLE_LINE_PATTERN = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
OBLIGATION_MARKERS = ("应当", "不得", "可以", "负责", "报送", "披露", "编报", "提交")
THRESHOLD_MARKERS = ("上限", "下限", "阈值", "比例", "取值", "系数", "因子", "区间", "范围")
FOCUS_STOPWORDS = {"第一章", "第二章", "第三章", "第四章", "第五章", "第六章", "第七章", "第八章"}


@dataclass(frozen=True)
class DocCatalogRecord:
    doc_id: str
    path: str
    title: str
    category: str
    source_type: str
    publish_date: str
    aliases: list[str]
    summary_short: str
    summary_structured: str
    headings: list[str]
    keywords: list[str]


@dataclass(frozen=True)
class TitleAliasRecord:
    alias: str
    normalized_alias: str
    doc_id: str
    title: str
    category: str
    alias_type: str


@dataclass(frozen=True)
class DocSummaryRecord:
    doc_id: str
    title: str
    category: str
    summary_short: str
    summary_structured: str
    focus_points: list[str]
    related_doc_ids: list[str]


@dataclass(frozen=True)
class StructuredSectionRecord:
    section_id: str
    doc_id: str
    path: str
    title: str
    heading_path: list[str]
    section_heading: str
    article_no: str | None
    clause_no: str | None
    section_kind: str
    content_type: str
    text: str
    token_count: int
    has_formula: bool
    has_table: bool
    mentions_rules: list[str]
    mentions_attachments: list[str]
    keywords: list[str]


@dataclass(frozen=True)
class FormulaCardRecord:
    formula_id: str
    doc_id: str
    title: str
    path: str
    article_no: str | None
    section_heading: str
    formula_text: str
    variables: list[str]
    variable_hints: list[str]
    keywords: list[str]


def _normalize_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def _truncate(value: str, limit: int) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "..."


def _extract_front_matter_value(text: str, key: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:[ \t]*(.*?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    value = match.group(1).strip().strip('"').strip("'")
    return value


def _category_from_path(relative_path: Path) -> str:
    return relative_path.parts[0] if relative_path.parts else "unknown"


def _repo_relative_path(md_path: Path, source: Path) -> str:
    resolved = md_path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return f"Knowledge_Base_MarkDown/{resolved.relative_to(source.resolve()).as_posix()}"


def _intro_paragraphs(body: str, *, limit: int = 3) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    in_fence = False

    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if current:
                paragraph = " ".join(current).strip()
                if paragraph:
                    paragraphs.append(paragraph)
                current = []
            continue

        if in_fence or not stripped or stripped.startswith("|") or stripped.startswith("#"):
            if current:
                paragraph = " ".join(current).strip()
                if paragraph:
                    paragraphs.append(paragraph)
                current = []
            continue

        current.append(stripped)
        if len(paragraphs) >= limit:
            break

    if current and len(paragraphs) < limit:
        paragraph = " ".join(current).strip()
        if paragraph:
            paragraphs.append(paragraph)

    return paragraphs[:limit]


def _headings(body: str, *, limit: int = 8) -> list[str]:
    headings: list[str] = []
    for _, heading in HEADING_PATTERN.findall(body):
        cleaned = " ".join(heading.split()).strip()
        if cleaned:
            headings.append(cleaned)
    return headings[:limit]


def _aliases(title: str, category: str, relative_path: str) -> list[TitleAliasRecord]:
    aliases: list[tuple[str, str]] = [(title, "title"), (Path(relative_path).stem, "stem")]

    rule_match = RULE_NO_PATTERN.search(title)
    if rule_match:
        number = rule_match.group(1)
        aliases.extend(
            [
                (f"规则第{number}号", "rule_number"),
                (f"第{number}号规则", "rule_number"),
                (f"偿付能力监管规则第{number}号", "rule_number"),
                (f"偿二代规则第{number}号", "rule_number"),
            ]
        )

    attachment_match = ATTACHMENT_NO_PATTERN.search(title)
    if attachment_match:
        number = attachment_match.group(1)
        aliases.extend(
            [
                (f"附件{number}", "attachment_number"),
                (f"附件 {number}", "attachment_number"),
            ]
        )

    notice_match = NOTICE_TITLE_PATTERN.search(title)
    if notice_match:
        topic = notice_match.group(1)
        aliases.extend(
            [
                (topic, "notice_topic"),
                (f"关于{topic}的通知", "notice_title"),
            ]
        )

    if category == "rules":
        aliases.append(("监管规则", "category_hint"))
    if category == "attachments":
        aliases.append(("附件", "category_hint"))
    if category == "notices":
        aliases.append(("通知", "category_hint"))

    deduped: list[TitleAliasRecord] = []
    seen: set[str] = set()
    for alias, alias_type in aliases:
        normalized = _normalize_text(alias)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(
            TitleAliasRecord(
                alias=alias,
                normalized_alias=normalized,
                doc_id=relative_path,
                title=title,
                category=category,
                alias_type=alias_type,
            )
        )
    return deduped


def _keywords(title: str, headings: list[str], aliases: Iterable[str], text: str) -> list[str]:
    values = [title, *headings, *aliases, text]
    keywords: list[str] = []
    seen: set[str] = set()

    for value in values:
        for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", value):
            if token in seen:
                continue
            seen.add(token)
            keywords.append(token)
            if len(keywords) >= 40:
                return keywords
    return keywords


def _focus_points(headings: list[str], keywords: list[str]) -> list[str]:
    points: list[str] = []
    for value in [*headings, *keywords]:
        if value in FOCUS_STOPWORDS:
            continue
        if value not in points:
            points.append(value)
        if len(points) >= 5:
            break
    return points


def _select_summary_short(title: str, paragraphs: list[str]) -> str:
    title_norm = _normalize_text(title)
    for paragraph in paragraphs:
        normalized = _normalize_text(paragraph)
        if not normalized:
            continue
        if normalized == title_norm:
            continue
        if ATTACHMENT_NO_PATTERN.fullmatch(paragraph.strip()):
            continue
        if len(paragraph.strip()) < 8:
            continue
        return _truncate(paragraph, 180)
    if paragraphs:
        return _truncate(paragraphs[0], 180)
    return title


def _summary_structured(title: str, headings: list[str], paragraphs: list[str]) -> str:
    parts = [f"标题：{title}"]
    if headings:
        parts.append("重点章节：" + "；".join(headings[:4]))
    if paragraphs:
        parts.append("内容摘要：" + " ".join(_truncate(item, 120) for item in paragraphs[:2]))
    return "\n".join(parts)


def _classify_content_type(text: str, *, has_formula: bool, has_table: bool) -> str:
    stripped = text.strip()
    if ARTICLE_PATTERN.search(stripped):
        if has_formula:
            return "article_formula"
        if has_table:
            return "article_table"
        return "article"
    if has_formula:
        return "formula"
    if has_table:
        return "table"
    if any(marker in text for marker in THRESHOLD_MARKERS) and re.search(r"\d", text):
        return "threshold"
    if any(marker in text for marker in OBLIGATION_MARKERS):
        return "obligation"
    return "semantic"


def _extract_heading_path(section_text: str) -> list[str]:
    match = re.search(r"^Section:\s+(.+?)\n", section_text, re.MULTILINE)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(">") if item.strip()]


def _strip_context_lines(section_text: str) -> str:
    lines = section_text.splitlines()
    filtered: list[str] = []
    for line in lines:
        if line.startswith("Document: ") or line.startswith("Section: "):
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def _article_no(text: str) -> str | None:
    match = ARTICLE_PATTERN.search(text)
    if not match:
        return None
    return match.group(0)


def _clause_no(text: str) -> str | None:
    match = CLAUSE_PATTERN.search(text)
    if not match:
        return None
    return match.group(0)


def _mentions_rules(text: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for number in RULE_REF_PATTERN.findall(text):
        label = f"规则第{number}号"
        if label not in seen:
            seen.add(label)
            values.append(label)
    return values


def _mentions_attachments(text: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for number in ATTACHMENT_REF_PATTERN.findall(text):
        label = f"附件{number}"
        if label not in seen:
            seen.add(label)
            values.append(label)
    return values


def _formula_variables(formula_text: str) -> list[str]:
    patterns = [
        re.compile(r"\\(?:mathrm|mathbf|text|mathit)\{([^{}]+)\}"),
        re.compile(r"\\([A-Za-z]+)"),
        re.compile(r"(?<!\\)\b([A-Za-z][A-Za-z0-9_]{0,30})\b"),
    ]
    values: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.findall(formula_text):
            token = str(match).strip()
            if not token:
                continue
            token = token.replace("text", "").strip()
            normalized = _normalize_text(token)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            values.append(token)
            if len(values) >= 12:
                return values
    return values


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def build_ready_data(
    source: Path = DEFAULT_SOURCE,
    output_root: Path = DEFAULT_OUTPUT,
    *,
    section_max_tokens: int = DEFAULT_SECTION_MAX_TOKENS,
) -> dict[str, int]:
    output_root.mkdir(parents=True, exist_ok=True)

    doc_catalog: list[dict] = []
    title_aliases: list[dict] = []
    doc_summaries: list[dict] = []
    sections_structured: list[dict] = []
    formula_cards: list[dict] = []

    doc_nodes: list[dict] = []
    relation_edges: list[dict] = []

    rule_targets: dict[str, str] = {}
    attachment_targets: dict[str, str] = {}

    raw_docs: list[dict] = []

    for md_path in iter_markdown_files(source):
        relative_path = md_path.resolve().relative_to(source.resolve()).as_posix()
        repo_relative_path = _repo_relative_path(md_path, source)
        raw_text = md_path.read_text(encoding="utf-8")
        title, body = strip_front_matter(raw_text)
        body = body.strip()
        doc_title = title or md_path.stem
        category = _category_from_path(Path(relative_path))
        source_type = _extract_front_matter_value(raw_text, "source_type")
        publish_date = _extract_front_matter_value(raw_text, "publish_date")
        headings = _headings(body)
        paragraphs = _intro_paragraphs(body)
        alias_records = _aliases(doc_title, category, relative_path)
        alias_values = [item.alias for item in alias_records]
        keywords = _keywords(doc_title, headings, alias_values, "\n".join(paragraphs[:2]))
        summary_short = _select_summary_short(doc_title, paragraphs)
        summary_structured = _summary_structured(doc_title, headings, paragraphs)
        focus_points = _focus_points(headings, keywords)

        catalog_record = DocCatalogRecord(
            doc_id=relative_path,
            path=repo_relative_path,
            title=doc_title,
            category=category,
            source_type=source_type,
            publish_date=publish_date,
            aliases=alias_values,
            summary_short=summary_short,
            summary_structured=summary_structured,
            headings=headings,
            keywords=keywords,
        )
        doc_catalog.append(asdict(catalog_record))
        title_aliases.extend(asdict(item) for item in alias_records)
        doc_summaries.append(
            asdict(
                DocSummaryRecord(
                    doc_id=relative_path,
                    title=doc_title,
                    category=category,
                    summary_short=summary_short,
                    summary_structured=summary_structured,
                    focus_points=focus_points,
                    related_doc_ids=[],
                )
            )
        )
        raw_docs.append(
            {
                "doc_id": relative_path,
                "path": repo_relative_path,
                "title": doc_title,
                "category": category,
                "body": body,
                "headings": headings,
                "keywords": keywords,
            }
        )
        doc_nodes.append(
            {
                "id": relative_path,
                "type": "document",
                "title": doc_title,
                "category": category,
                "path": repo_relative_path,
            }
        )

        rule_match = RULE_NO_PATTERN.search(doc_title)
        if rule_match:
            rule_targets[rule_match.group(1)] = relative_path
        attachment_match = ATTACHMENT_NO_PATTERN.search(doc_title)
        if attachment_match:
            attachment_targets[attachment_match.group(1)] = relative_path

        structured_sections = split_structured_sections(
            repo_relative_path,
            doc_title,
            body,
            max_tokens=section_max_tokens,
        )

        formula_count_for_doc = 0
        for index, section in enumerate(structured_sections, start=1):
            text = str(section["text"])
            section_heading = str(section.get("section_heading", doc_title))
            heading_path = _extract_heading_path(text)
            plain_text = _strip_context_lines(text)
            has_formula = bool(MATH_BLOCK_PATTERN.search(plain_text))
            has_table = bool(TABLE_LINE_PATTERN.search(plain_text))
            article_no = _article_no(plain_text)
            clause_no = _clause_no(plain_text)
            mentions_rules = _mentions_rules(plain_text)
            mentions_attachments = _mentions_attachments(plain_text)
            content_type = _classify_content_type(plain_text, has_formula=has_formula, has_table=has_table)
            section_keywords = _keywords(doc_title, heading_path, alias_values, plain_text)

            section_record = StructuredSectionRecord(
                section_id=f"{relative_path}#section-{index}",
                doc_id=relative_path,
                path=repo_relative_path,
                title=doc_title,
                heading_path=heading_path,
                section_heading=section_heading,
                article_no=article_no,
                clause_no=clause_no,
                section_kind=str(section.get("section_kind", "semantic")),
                content_type=content_type,
                text=plain_text,
                token_count=estimate_tokens(plain_text),
                has_formula=has_formula,
                has_table=has_table,
                mentions_rules=mentions_rules,
                mentions_attachments=mentions_attachments,
                keywords=section_keywords,
            )
            sections_structured.append(asdict(section_record))

            for formula_match in MATH_BLOCK_PATTERN.finditer(plain_text):
                formula_body = formula_match.group(0).strip()
                if not formula_body:
                    continue
                formula_count_for_doc += 1
                variables = _formula_variables(formula_body)
                formula_cards.append(
                    asdict(
                        FormulaCardRecord(
                            formula_id=f"{relative_path}#formula-{formula_count_for_doc}",
                            doc_id=relative_path,
                            title=doc_title,
                            path=repo_relative_path,
                            article_no=article_no,
                            section_heading=section_heading,
                            formula_text=formula_body,
                            variables=variables,
                            variable_hints=variables[:6],
                            keywords=_keywords(doc_title, heading_path, variables, formula_body),
                        )
                    )
                )

    for doc in raw_docs:
        body = str(doc["body"])
        doc_id = str(doc["doc_id"])
        seen_edges: set[tuple[str, str, str]] = set()

        for rule_number in RULE_REF_PATTERN.findall(body):
            target = rule_targets.get(rule_number)
            if not target or target == doc_id:
                continue
            edge = (doc_id, target, "mentions_rule")
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            relation_edges.append(
                {
                    "source": doc_id,
                    "target": target,
                    "relation": "mentions_rule",
                    "label": f"规则第{rule_number}号",
                }
            )

        for attachment_number in ATTACHMENT_REF_PATTERN.findall(body):
            target = attachment_targets.get(attachment_number)
            if not target or target == doc_id:
                continue
            edge = (doc_id, target, "mentions_attachment")
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            relation_edges.append(
                {
                    "source": doc_id,
                    "target": target,
                    "relation": "mentions_attachment",
                    "label": f"附件{attachment_number}",
                }
            )

    related_doc_ids_map: dict[str, list[str]] = {}
    for edge in relation_edges:
        source_doc_id = str(edge["source"])
        target = str(edge["target"])
        related_doc_ids_map.setdefault(source_doc_id, [])
        if target not in related_doc_ids_map[source_doc_id]:
            related_doc_ids_map[source_doc_id].append(target)

    for row in doc_summaries:
        doc_id = str(row["doc_id"])
        row["related_doc_ids"] = related_doc_ids_map.get(doc_id, [])

    _write_jsonl(output_root / "doc_catalog.jsonl", doc_catalog)
    _write_jsonl(output_root / "title_aliases.jsonl", title_aliases)
    _write_jsonl(output_root / "doc_summaries.jsonl", doc_summaries)
    _write_jsonl(output_root / "sections_structured.jsonl", sections_structured)
    _write_jsonl(output_root / "formula_cards.jsonl", formula_cards)

    relations_graph = {
        "nodes": doc_nodes,
        "edges": relation_edges,
    }
    (output_root / "relations_graph.json").write_text(
        json.dumps(relations_graph, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    ready_data_manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source.resolve()),
        "doc_count": len(doc_catalog),
        "alias_count": len(title_aliases),
        "summary_count": len(doc_summaries),
        "section_count": len(sections_structured),
        "formula_count": len(formula_cards),
        "relation_edge_count": len(relation_edges),
        "artifact_files": [
            "doc_catalog.jsonl",
            "title_aliases.jsonl",
            "doc_summaries.jsonl",
            "sections_structured.jsonl",
            "formula_cards.jsonl",
            "relations_graph.json",
            "ready_data_manifest.json",
        ],
    }
    (output_root / "ready_data_manifest.json").write_text(
        json.dumps(ready_data_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "doc_count": len(doc_catalog),
        "alias_count": len(title_aliases),
        "summary_count": len(doc_summaries),
        "section_count": len(sections_structured),
        "formula_count": len(formula_cards),
        "relation_edge_count": len(relation_edges),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build chatbot-ready and AI-agent-ready data artifacts from Markdown.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Markdown source root")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT, help="Output directory for ready-data artifacts")
    parser.add_argument(
        "--section-max-tokens",
        type=int,
        default=DEFAULT_SECTION_MAX_TOKENS,
        help="Maximum tokens per structured section",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_ready_data(
        source=args.source.resolve(),
        output_root=args.output_root.resolve(),
        section_max_tokens=args.section_max_tokens,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
