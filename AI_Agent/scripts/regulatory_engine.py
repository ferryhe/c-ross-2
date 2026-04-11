from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
KNOWLEDGE_ROOT = REPO_ROOT / "Knowledge_Base_MarkDown"
READY_DATA_ROOT = KNOWLEDGE_ROOT / "ready_data"
DOC_CATALOG_PATH = READY_DATA_ROOT / "doc_catalog.jsonl"
MANIFEST_PATH = KNOWLEDGE_ROOT / "manifest.json"
FRONT_MATTER_PATTERN = re.compile(r"\A---\s*\r?\n.*?\r?\n---\s*\r?\n?", re.DOTALL)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
RULE_NO_PATTERN = re.compile(r"规则第(\d+)号")
ATTACHMENT_NO_PATTERN = re.compile(r"附件(\d+(?:-\d+)?)")
NOTICE_TITLE_PATTERN = re.compile(r"关于(.+?)的通知")
COMPARE_MARKERS = ("比较", "对比", "区别", "差异", "分别")
SUMMARY_MARKERS = ("主要内容", "概览", "概要", "总结", "介绍", "概括", "讲什么", "适用范围")
FORMULA_MARKERS = ("公式", "计算", "系数", "因子", "阈值", "上限", "下限", "取值", "曲线", "表格")
VERSION_MARKERS = ("调整", "修订", "延长", "实施", "过渡期", "优化", "通知")
COMPLIANCE_MARKERS = ("应当", "是否需要", "要不要", "报送", "披露", "提交", "编报", "要求")
_ASK_MODULE: Any | None = None


@dataclass(frozen=True)
class CatalogEntry:
    doc_id: str
    path: str
    title: str
    category: str
    source_type: str
    publish_date: str
    aliases: tuple[str, ...]
    headings: tuple[str, ...]
    summary_short: str
    summary_structured: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class CatalogHit:
    doc_id: str
    path: str
    title: str
    category: str
    score: float
    reason: str
    summary_short: str
    aliases: tuple[str, ...]


def _get_ask_module():
    global _ASK_MODULE
    if _ASK_MODULE is None:
        try:
            from . import ask as ask_module
        except ImportError:
            import ask as ask_module

        _ASK_MODULE = ask_module
    return _ASK_MODULE


def _strip_front_matter(text: str) -> tuple[str | None, str]:
    normalized = text.lstrip("\ufeff")
    match = FRONT_MATTER_PATTERN.match(normalized)
    if not match:
        return None, normalized
    return None, normalized[match.end() :].lstrip()


def _normalize_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def _iter_paragraphs(body: str, *, limit: int = 3) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    in_fence = False

    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            in_fence = not in_fence
            if current:
                paragraph = " ".join(current).strip()
                if paragraph:
                    paragraphs.append(paragraph)
                current = []
            continue

        if in_fence or not stripped or stripped.startswith("|"):
            if current:
                paragraph = " ".join(current).strip()
                if paragraph:
                    paragraphs.append(paragraph)
                current = []
            continue

        if stripped.startswith("#"):
            continue

        current.append(stripped)
        if len(paragraphs) >= limit:
            break

    if current and len(paragraphs) < limit:
        paragraph = " ".join(current).strip()
        if paragraph:
            paragraphs.append(paragraph)

    return paragraphs[:limit]


def _truncate(value: str, limit: int) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "..."


def _extract_heading_list(body: str, *, limit: int = 6) -> tuple[str, ...]:
    headings = [match.group(2).strip() for match in HEADING_PATTERN.finditer(body)]
    return tuple(headings[:limit])


def _build_aliases(title: str, category: str, path: str) -> tuple[str, ...]:
    aliases: list[str] = [title, Path(path).stem]

    rule_match = RULE_NO_PATTERN.search(title)
    if rule_match:
        number = rule_match.group(1)
        aliases.extend(
            [
                f"规则第{number}号",
                f"第{number}号规则",
                f"偿付能力监管规则第{number}号",
                f"偿二代规则第{number}号",
            ]
        )

    attachment_match = ATTACHMENT_NO_PATTERN.search(title)
    if attachment_match:
        number = attachment_match.group(1)
        aliases.extend(
            [
                f"附件{number}",
                f"附件 {number}",
            ]
        )

    notice_match = NOTICE_TITLE_PATTERN.search(title)
    if notice_match:
        aliases.append(f"关于{notice_match.group(1)}的通知")
        aliases.append(notice_match.group(1))

    if category == "notices":
        aliases.append("通知")
    elif category == "rules":
        aliases.append("监管规则")
    elif category == "attachments":
        aliases.append("附件")

    deduped = []
    seen: set[str] = set()
    for alias in aliases:
        normalized = _normalize_text(alias)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(alias)
    return tuple(deduped)


def _build_keywords(title: str, headings: tuple[str, ...], aliases: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = [title, *headings, *aliases]
    keywords: list[str] = []
    seen: set[str] = set()

    for value in values:
        for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", value):
            if token in seen:
                continue
            seen.add(token)
            keywords.append(token)

    return tuple(keywords[:30])


def _build_structured_summary(title: str, headings: tuple[str, ...], paragraphs: list[str]) -> str:
    parts = [f"标题：{title}"]
    if headings:
        parts.append("重点章节：" + "；".join(headings[:4]))
    if paragraphs:
        parts.append("内容摘要：" + " ".join(_truncate(item, 120) for item in paragraphs[:2]))
    return "\n".join(parts)


def _entry_to_hit(entry: CatalogEntry, score: float, reason: str) -> dict[str, Any]:
    return asdict(
        CatalogHit(
            doc_id=entry.doc_id,
            path=entry.path,
            title=entry.title,
            category=entry.category,
            score=round(score, 4),
            reason=reason,
            summary_short=entry.summary_short,
            aliases=entry.aliases[:6],
        )
    )


def _title_focus_terms(title: str) -> tuple[str, ...]:
    segments = [segment.strip() for segment in re.split(r"[：:]", title) if segment.strip()]
    if len(segments) <= 1:
        return tuple()
    return tuple(segment for segment in segments[1:] if len(segment) >= 2)


@lru_cache(maxsize=1)
def load_catalog() -> tuple[CatalogEntry, ...]:
    if DOC_CATALOG_PATH.exists():
        entries: list[CatalogEntry] = []
        for line in DOC_CATALOG_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                continue
            entries.append(
                CatalogEntry(
                    doc_id=str(item.get("doc_id", "")).replace("\\", "/"),
                    path=str(item.get("path", "")).replace("\\", "/"),
                    title=str(item.get("title", "")),
                    category=str(item.get("category", "")),
                    source_type=str(item.get("source_type", "")),
                    publish_date=str(item.get("publish_date", "")),
                    aliases=tuple(str(value) for value in item.get("aliases", []) if str(value).strip()),
                    headings=tuple(str(value) for value in item.get("headings", []) if str(value).strip()),
                    summary_short=str(item.get("summary_short", "")),
                    summary_structured=str(item.get("summary_structured", "")),
                    keywords=tuple(str(value) for value in item.get("keywords", []) if str(value).strip()),
                )
            )
        if entries:
            return tuple(entries)

    if not MANIFEST_PATH.exists():
        return tuple()

    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        return tuple()

    entries: list[CatalogEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        relative_path = str(item.get("path", "")).strip()
        normalized_relative_path = relative_path.replace("\\", "/")
        absolute_path = KNOWLEDGE_ROOT / relative_path
        title = str(item.get("title", Path(relative_path).stem)).strip() or Path(relative_path).stem
        category = str(item.get("category", "")).strip() or absolute_path.parent.name
        source_type = str(item.get("source_type", "")).strip()
        publish_date = str(item.get("publish_date", "")).strip()

        body = ""
        if absolute_path.exists():
            raw_markdown = absolute_path.read_text(encoding="utf-8")
            _, body = _strip_front_matter(raw_markdown)
        headings = _extract_heading_list(body)
        paragraphs = _iter_paragraphs(body)
        summary_short = _truncate(paragraphs[0], 140) if paragraphs else title
        summary_structured = _build_structured_summary(title, headings, paragraphs)
        aliases = _build_aliases(title, category, relative_path)
        keywords = _build_keywords(title, headings, aliases)

        entries.append(
            CatalogEntry(
                doc_id=normalized_relative_path,
                path=f"Knowledge_Base_MarkDown/{normalized_relative_path}",
                title=title,
                category=category,
                source_type=source_type,
                publish_date=publish_date,
                aliases=aliases,
                headings=headings,
                summary_short=summary_short,
                summary_structured=summary_structured,
                keywords=keywords,
            )
        )

    return tuple(entries)


def refresh_catalog() -> None:
    load_catalog.cache_clear()


def _score_title_query(query: str, entry: CatalogEntry) -> tuple[float, str] | None:
    query_norm = _normalize_text(query)
    if not query_norm:
        return None

    best_score = 0.0
    best_reason = ""
    title_norm = _normalize_text(entry.title)
    if query_norm == title_norm:
        best_score = 200.0
        best_reason = "精确命中文档标题"
    elif query_norm in title_norm:
        best_score = 150.0
        best_reason = "标题包含查询"

    for focus_term in _title_focus_terms(entry.title):
        focus_norm = _normalize_text(focus_term)
        if not focus_norm:
            continue
        if focus_norm in query_norm and 90.0 > best_score:
            best_score = 90.0
            best_reason = f"标题主题命中：{focus_term}"

    for alias in entry.aliases:
        alias_norm = _normalize_text(alias)
        if not alias_norm:
            continue
        if query_norm == alias_norm:
            if 180.0 > best_score:
                best_score = 180.0
                best_reason = f"精确命中别名：{alias}"
        elif query_norm in alias_norm or alias_norm in query_norm:
            if 120.0 > best_score:
                best_score = 120.0
                best_reason = f"别名相关：{alias}"

    query_rule = RULE_NO_PATTERN.search(query)
    entry_rule = RULE_NO_PATTERN.search(entry.title)
    if query_rule and entry_rule and query_rule.group(1) == entry_rule.group(1):
        best_score = max(best_score, 220.0)
        best_reason = f"规则编号命中：第{query_rule.group(1)}号"

    query_attachment = ATTACHMENT_NO_PATTERN.search(query)
    entry_attachment = ATTACHMENT_NO_PATTERN.search(entry.title)
    if query_attachment and entry_attachment and query_attachment.group(1) == entry_attachment.group(1):
        best_score = max(best_score, 220.0)
        best_reason = f"附件编号命中：附件{query_attachment.group(1)}"

    if best_score == 0.0:
        overlap = sum(1 for token in entry.keywords if token and token in query)
        if overlap <= 0:
            return None
        best_score = float(overlap * 10)
        best_reason = "标题关键词相关"

    return best_score, best_reason


def search_titles(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for entry in load_catalog():
        result = _score_title_query(query, entry)
        if result is None:
            continue
        score, reason = result
        scored.append(_entry_to_hit(entry, score, reason))

    scored.sort(key=lambda item: (float(item["score"]), item["title"]), reverse=True)
    return scored[:limit]


def _score_summary_query(query: str, entry: CatalogEntry) -> tuple[float, str] | None:
    query_norm = _normalize_text(query)
    if not query_norm:
        return None

    haystack = "\n".join(
        [
            entry.title,
            entry.summary_short,
            entry.summary_structured,
            *entry.headings,
            *entry.keywords,
        ]
    )
    haystack_norm = _normalize_text(haystack)
    if query_norm in haystack_norm:
        return 100.0, "摘要层直接覆盖查询"

    overlap = [token for token in entry.keywords if token in query]
    if overlap:
        return float(15 + len(overlap) * 8), "摘要关键词相关"

    return None


def search_summaries(query: str, *, limit: int = 5, doc_ids: list[str] | None = None) -> list[dict[str, Any]]:
    target_ids = {item.replace("\\", "/") for item in doc_ids or []}
    scored: list[dict[str, Any]] = []

    for entry in load_catalog():
        if target_ids and entry.doc_id not in target_ids:
            continue
        result = _score_summary_query(query, entry)
        if result is None:
            continue
        score, reason = result
        scored.append(_entry_to_hit(entry, score, reason))

    scored.sort(key=lambda item: (float(item["score"]), item["title"]), reverse=True)
    return scored[:limit]


def detect_question_type(question: str) -> str:
    normalized = question.replace(" ", "")
    if any(marker in normalized for marker in COMPARE_MARKERS):
        return "comparison"
    if any(marker in normalized for marker in FORMULA_MARKERS):
        return "formula"
    if any(marker in normalized for marker in VERSION_MARKERS):
        return "version"
    if any(marker in normalized for marker in COMPLIANCE_MARKERS):
        return "compliance"
    if any(marker in normalized for marker in SUMMARY_MARKERS):
        return "summary"
    if RULE_NO_PATTERN.search(question) or ATTACHMENT_NO_PATTERN.search(question):
        return "locate"
    return "analysis"


def build_scoped_queries(question: str, title_hits: list[dict[str, Any]], summary_hits: list[dict[str, Any]]) -> list[str]:
    return _build_scoped_queries(question, title_hits, summary_hits)


def _filter_hits_by_doc_ids(hits: list[dict[str, Any]], doc_ids: list[str] | None) -> list[dict[str, Any]]:
    target_ids = {item.replace("\\", "/") for item in doc_ids or []}
    if not target_ids:
        return hits
    filtered = [hit for hit in hits if str(hit.get("doc_id", "")).replace("\\", "/") in target_ids]
    return filtered or hits


def _resolve_exact_scope_doc_ids(question: str, title_hits: list[dict[str, Any]]) -> list[str]:
    question_rule = RULE_NO_PATTERN.search(question)
    if question_rule:
        exact_rule_hits = [
            str(hit.get("doc_id", "")).replace("\\", "/")
            for hit in title_hits
            if RULE_NO_PATTERN.search(str(hit.get("title", "")))
            and RULE_NO_PATTERN.search(str(hit.get("title", ""))).group(1) == question_rule.group(1)
        ]
        if exact_rule_hits:
            return exact_rule_hits[:1]

    question_attachment = ATTACHMENT_NO_PATTERN.search(question)
    if question_attachment:
        exact_attachment_hits = [
            str(hit.get("doc_id", "")).replace("\\", "/")
            for hit in title_hits
            if ATTACHMENT_NO_PATTERN.search(str(hit.get("title", "")))
            and ATTACHMENT_NO_PATTERN.search(str(hit.get("title", ""))).group(1) == question_attachment.group(1)
        ]
        if exact_attachment_hits:
            return exact_attachment_hits[:1]

    return []


def _resolve_preferred_scope_doc_ids(question_type: str, title_hits: list[dict[str, Any]]) -> list[str]:
    if question_type == "comparison" or not title_hits:
        return []

    first_hit = title_hits[0]
    first_score = float(first_hit.get("score", 0.0))
    second_score = float(title_hits[1].get("score", 0.0)) if len(title_hits) > 1 else 0.0
    if first_score >= 60.0 and first_score >= second_score + 20.0:
        doc_id = str(first_hit.get("doc_id", "")).replace("\\", "/")
        if doc_id:
            return [doc_id]
    return []


def _build_scoped_queries(
    question: str,
    title_hits: list[dict[str, Any]],
    summary_hits: list[dict[str, Any]],
    *,
    scoped_doc_ids: list[str] | None = None,
) -> list[str]:
    filtered_title_hits = _filter_hits_by_doc_ids(title_hits, scoped_doc_ids)
    filtered_summary_hits = _filter_hits_by_doc_ids(summary_hits, scoped_doc_ids)
    queries = [question]

    title_limit = 1 if scoped_doc_ids else 2
    summary_limit = 1 if scoped_doc_ids else 2

    for hit in filtered_title_hits[:title_limit]:
        title = str(hit.get("title", "")).strip()
        if title:
            queries.append(title)

    for hit in filtered_summary_hits[:summary_limit]:
        title = str(hit.get("title", "")).strip()
        summary_short = str(hit.get("summary_short", "")).strip()
        if title and summary_short:
            queries.append(f"{title} {summary_short}")

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = _normalize_text(query)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(query)

    return deduped[:4]


def plan_regulatory_query(question: str) -> dict[str, Any]:
    question_type = detect_question_type(question)
    title_hits = search_titles(question, limit=5)
    exact_scope_doc_ids = _resolve_exact_scope_doc_ids(question, title_hits)
    preferred_scope_doc_ids = _resolve_preferred_scope_doc_ids(question_type, title_hits)
    scoped_doc_ids = exact_scope_doc_ids or preferred_scope_doc_ids
    title_doc_ids = [str(hit["doc_id"]) for hit in title_hits]
    summary_scope_doc_ids = scoped_doc_ids or title_doc_ids or None
    summary_hits = search_summaries(question, limit=5, doc_ids=summary_scope_doc_ids)
    retrieval_strategy = {
        "locate": "title-first",
        "summary": "title-summary-document",
        "formula": "title-summary-section-formula",
        "comparison": "title-summary-hybrid",
        "version": "title-summary-related-notices",
        "compliance": "title-summary-evidence",
        "analysis": "summary-hybrid",
    }.get(question_type, "summary-hybrid")
    scoped_queries = _build_scoped_queries(
        question,
        title_hits,
        summary_hits,
        scoped_doc_ids=scoped_doc_ids,
    )
    recommended_title_hits = _filter_hits_by_doc_ids(title_hits, scoped_doc_ids)
    recommended_summary_hits = _filter_hits_by_doc_ids(summary_hits, scoped_doc_ids)
    recommended_paths = [str(hit["path"]) for hit in [*recommended_title_hits[:2], *recommended_summary_hits[:2]]]

    return {
        "question": question,
        "question_type": question_type,
        "retrieval_strategy": retrieval_strategy,
        "title_hits": title_hits,
        "summary_hits": summary_hits,
        "exact_scope_doc_ids": exact_scope_doc_ids,
        "scoped_doc_ids": scoped_doc_ids,
        "scoped_queries": scoped_queries,
        "recommended_paths": list(dict.fromkeys(recommended_paths)),
    }


def _merge_hits(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], int] = {}

    for group in groups:
        for hit in group:
            path = str(hit.get("path", ""))
            text = str(hit.get("text", ""))
            key = (path, text)
            if key in seen:
                existing = merged[seen[key]]
                existing["retrieval_score"] = max(
                    float(existing.get("retrieval_score", 0.0)),
                    float(hit.get("retrieval_score", 0.0)),
                )
                continue
            seen[key] = len(merged)
            merged.append(hit)

    return merged


def _catalog_snippets_from_title_hits(question_type: str, title_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if question_type not in {"locate", "summary", "comparison", "version"}:
        return []

    ask_module = _get_ask_module()
    snippets: list[dict[str, Any]] = []
    for hit in title_hits[:2]:
        path = str(hit.get("path", "")).replace("Knowledge_Base_MarkDown/", "")
        for item in ask_module.get_document_snippets(path, limit=1):
            snippets.append(
                {
                    **item,
                    "retrieval_score": max(float(item.get("retrieval_score", 0.0)), 1.25),
                }
            )
    return snippets


def run_regulatory_query(
    client: Any,
    question: str,
    *,
    language: str,
    history: str | None,
    model: str | None,
    k: int = 4,
    similarity_threshold: float | None = None,
) -> dict[str, Any]:
    ask_module = _get_ask_module()
    threshold = ask_module.DEFAULT_SIMILARITY_THRESHOLD if similarity_threshold is None else similarity_threshold
    standalone_question = ask_module.rewrite_question_with_history(client, question, history, model=model)
    catalog_answer = ask_module.try_answer_catalog_query(standalone_question, language=language)
    if catalog_answer is not None:
        return {
            **catalog_answer,
            "mode": "regulatory-engine",
            "engine_mode": "professional",
            "plan": plan_regulatory_query(standalone_question),
        }

    plan = plan_regulatory_query(standalone_question)
    aggregated_hits: list[dict[str, Any]] = []

    for scoped_query in plan["scoped_queries"]:
        aggregated_hits.extend(
            ask_module.retrieve(
                client,
                scoped_query,
                k=max(4, k),
                similarity_threshold=threshold,
            )
        )

    catalog_hits = _catalog_snippets_from_title_hits(plan["question_type"], plan["title_hits"])
    merged_hits = _merge_hits(catalog_hits, aggregated_hits)
    reranked_hits = (
        ask_module.rerank_hits(standalone_question, merged_hits, top_k=min(len(merged_hits), max(8, k * 2)))
        if merged_hits
        else []
    )
    answer_hits = ask_module.prepare_answer_hits(standalone_question, reranked_hits)
    answer = ask_module.answer_from_hits(
        client,
        question,
        answer_hits,
        language=language,
        history=history,
        interpreted_question=standalone_question,
        model=model,
    )

    return {
        "mode": "regulatory-engine",
        "engine_mode": "professional",
        "answer": answer,
        "hits": answer_hits,
        "sub_queries": plan["scoped_queries"],
        "executed_queries": plan["scoped_queries"],
        "iterations": len(plan["scoped_queries"]),
        "reflection_notes": ["Regulatory engine combined title, summary, and evidence retrieval."],
        "retrieval_history": [],
        "plan": plan,
    }


def build_engine_config() -> dict[str, Any]:
    return {
        "engine_mode": "professional",
        "keeps_standalone_chatbot": True,
        "capabilities": [
            "title-search",
            "summary-search",
            "question-planning",
            "scoped-retrieval",
            "citation-grounded-answering",
        ],
    }
