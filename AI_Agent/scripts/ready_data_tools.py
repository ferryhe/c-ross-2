from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
KNOWLEDGE_ROOT = REPO_ROOT / "Knowledge_Base_MarkDown"
READY_DATA_ROOT = KNOWLEDGE_ROOT / "ready_data"
DEFAULT_FEEDBACK_PATH = PROJECT_ROOT / "eval" / "feedback.jsonl"
CATALOG_MANIFEST_DOC_ID = "manifest.json"
CATALOG_MANIFEST_PATH = "Knowledge_Base_MarkDown/manifest.json"

REQUIRED_ARTIFACTS = (
    "doc_catalog.jsonl",
    "title_aliases.jsonl",
    "doc_summaries.jsonl",
    "sections_structured.jsonl",
    "formula_cards.jsonl",
    "relations_graph.json",
    "ready_data_manifest.json",
)
JSONL_REQUIRED_FIELDS = {
    "doc_catalog.jsonl": {"doc_id", "path", "title", "category", "aliases", "summary_short"},
    "title_aliases.jsonl": {"alias", "normalized_alias", "doc_id", "title", "category", "alias_type"},
    "doc_summaries.jsonl": {
        "doc_id",
        "title",
        "category",
        "summary_short",
        "summary_structured",
        "focus_points",
        "related_doc_ids",
    },
    "sections_structured.jsonl": {
        "section_id",
        "doc_id",
        "path",
        "title",
        "section_heading",
        "content_type",
        "text",
        "token_count",
        "has_formula",
        "has_table",
    },
    "formula_cards.jsonl": {
        "formula_id",
        "doc_id",
        "title",
        "path",
        "section_heading",
        "formula_text",
        "variables",
        "variable_hints",
    },
}
SUMMARY_MARKERS = ("主要内容", "概览", "概要", "总结", "介绍", "概括", "讲什么", "适用范围")
FORMULA_MARKERS = ("公式", "计算", "变量", "系数", "因子", "阈值", "上限", "下限", "取值", "曲线")
RELATION_MARKERS = (
    "关系",
    "通知",
    "调整",
    "修订",
    "延长",
    "过渡期",
    "优化",
    "附件",
    "影响",
    "对应",
    "按照",
    "哪一项规则",
    "计量",
)
ARTICLE_PATTERN = re.compile(r"第[一二三四五六七八九十百零〇\d]+条")

LATEX_CONTROL_WORDS = {
    "begin",
    "end",
    "leq",
    "geq",
    "lt",
    "gt",
    "times",
    "cdot",
    "operatorname",
    "mathrm",
    "mathbf",
    "mathit",
    "math",
    "text",
    "cases",
    "sqrt",
    "left",
    "right",
    "min",
    "max",
    "sum",
    "prod",
    "frac",
    "quad",
    "qquad",
    "dots",
    "cdots",
    "ldots",
    "in",
    "notin",
    "limits",
    "over",
    "under",
}
GREEK_VARIABLES = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "theta",
    "lambda",
    "mu",
    "rho",
    "sigma",
    "tau",
    "phi",
    "omega",
}


def normalize_doc_id(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    prefixes = ("./", "Knowledge_Base_MarkDown/")
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
                changed = True
    return normalized


def _normalize_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def _truncate(value: str, limit: int) -> str:
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "..."


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
        if isinstance(item, dict):
            rows.append(item)
    return rows


@lru_cache(maxsize=8)
def _load_jsonl_cached(path_value: str) -> tuple[dict[str, Any], ...]:
    return tuple(_read_jsonl(Path(path_value)))


def _load_jsonl(root: Path, name: str) -> list[dict[str, Any]]:
    return [dict(item) for item in _load_jsonl_cached(str((root / name).resolve()))]


@lru_cache(maxsize=8)
def _load_relations_cached(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.exists():
        return {"nodes": [], "edges": []}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {"nodes": [], "edges": []}
    nodes = raw.get("nodes", [])
    edges = raw.get("edges", [])
    return {
        "nodes": nodes if isinstance(nodes, list) else [],
        "edges": edges if isinstance(edges, list) else [],
    }


def _load_relations(root: Path = READY_DATA_ROOT) -> dict[str, Any]:
    return dict(_load_relations_cached(str((root / "relations_graph.json").resolve())))


def refresh_ready_data_cache() -> None:
    _load_jsonl_cached.cache_clear()
    _load_relations_cached.cache_clear()


def _catalog_by_doc_id(root: Path = READY_DATA_ROOT) -> dict[str, dict[str, Any]]:
    return {normalize_doc_id(str(item.get("doc_id", ""))): item for item in _load_jsonl(root, "doc_catalog.jsonl")}


def _doc_path(doc_id: str, catalog: dict[str, dict[str, Any]]) -> str:
    normalized = normalize_doc_id(doc_id)
    item = catalog.get(normalized, {})
    return str(item.get("path") or f"Knowledge_Base_MarkDown/{normalized}")


def _char_ngrams(value: str) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()
    grams: set[str] = set()
    for size in (2, 3, 4):
        if len(normalized) < size:
            continue
        grams.update(normalized[index : index + size] for index in range(len(normalized) - size + 1))
    return grams


def _score_text_query(
    query: str,
    haystack: str,
    *,
    keywords: list[str] | tuple[str, ...] | None = None,
    exact_boost: float = 80.0,
) -> tuple[float, list[str]]:
    query_norm = _normalize_text(query)
    haystack_norm = _normalize_text(haystack)
    if not query_norm or not haystack_norm:
        return 0.0, []

    score = 0.0
    reasons: list[str] = []
    if query_norm in haystack_norm:
        score += exact_boost
        reasons.append("文本直接覆盖查询")

    query_grams = _char_ngrams(query)
    haystack_grams = _char_ngrams(haystack)
    if query_grams and haystack_grams:
        overlap = len(query_grams & haystack_grams) / max(1, len(query_grams))
        if overlap:
            score += overlap * 60.0
            reasons.append("语义片段相关")

    keyword_hits: list[str] = []
    for keyword in keywords or []:
        keyword_norm = _normalize_text(str(keyword))
        if not keyword_norm:
            continue
        if keyword_norm in query_norm or (keyword_norm in haystack_norm and keyword_norm in query_norm):
            keyword_hits.append(str(keyword))
        if len(keyword_hits) >= 5:
            break

    if keyword_hits:
        score += min(40.0, 8.0 * len(keyword_hits))
        reasons.append("关键词命中：" + "、".join(keyword_hits[:3]))

    return score, reasons


def _scope_doc_ids(doc_ids: list[str] | tuple[str, ...] | None) -> set[str]:
    return {normalize_doc_id(item) for item in doc_ids or [] if normalize_doc_id(item)}


def _add_score_reason(row: dict[str, Any], score: float, reasons: list[str]) -> dict[str, Any]:
    return {
        **row,
        "score": round(score, 4),
        "reason": "；".join(dict.fromkeys(reason for reason in reasons if reason)) or "ready_data 相关",
    }


def search_summaries(
    query: str,
    *,
    limit: int = 5,
    doc_ids: list[str] | None = None,
    root: Path = READY_DATA_ROOT,
) -> list[dict[str, Any]]:
    target_ids = _scope_doc_ids(doc_ids)
    catalog = _catalog_by_doc_id(root)
    hits: list[dict[str, Any]] = []

    for row in _load_jsonl(root, "doc_summaries.jsonl"):
        doc_id = normalize_doc_id(str(row.get("doc_id", "")))
        if target_ids and doc_id not in target_ids:
            continue
        catalog_row = catalog.get(doc_id, {})
        haystack = "\n".join(
            [
                str(row.get("title", "")),
                str(row.get("summary_short", "")),
                str(row.get("summary_structured", "")),
                " ".join(str(item) for item in row.get("focus_points", [])),
                " ".join(str(item) for item in row.get("related_doc_ids", [])),
            ]
        )
        score, reasons = _score_text_query(query, haystack, keywords=row.get("focus_points", []), exact_boost=90.0)
        if target_ids and doc_id in target_ids:
            score += 35.0
            reasons.append("已限定目标文档")
        if not score:
            continue
        hits.append(
            _add_score_reason(
                {
                    "doc_id": doc_id,
                    "path": str(catalog_row.get("path") or f"Knowledge_Base_MarkDown/{doc_id}"),
                    "title": str(row.get("title") or catalog_row.get("title") or Path(doc_id).stem),
                    "category": str(row.get("category") or catalog_row.get("category") or ""),
                    "summary_short": str(row.get("summary_short", "")),
                    "summary_structured": str(row.get("summary_structured", "")),
                    "focus_points": [str(item) for item in row.get("focus_points", [])],
                    "related_doc_ids": [normalize_doc_id(str(item)) for item in row.get("related_doc_ids", [])],
                    "aliases": [str(item) for item in catalog_row.get("aliases", [])][:6],
                },
                score,
                reasons,
            )
        )

    hits.sort(key=lambda item: (float(item.get("score", 0.0)), str(item.get("title", ""))), reverse=True)
    return hits[:limit]


def search_sections(
    query: str,
    *,
    limit: int = 5,
    doc_ids: list[str] | None = None,
    root: Path = READY_DATA_ROOT,
) -> list[dict[str, Any]]:
    target_ids = _scope_doc_ids(doc_ids)
    hits: list[dict[str, Any]] = []
    article_match = ARTICLE_PATTERN.search(query)
    wants_formula = any(marker in query for marker in FORMULA_MARKERS)

    for row in _load_jsonl(root, "sections_structured.jsonl"):
        doc_id = normalize_doc_id(str(row.get("doc_id", "")))
        if target_ids and doc_id not in target_ids:
            continue
        haystack = "\n".join(
            [
                str(row.get("title", "")),
                str(row.get("section_heading", "")),
                str(row.get("article_no", "")),
                str(row.get("clause_no", "")),
                str(row.get("content_type", "")),
                str(row.get("text", "")),
                " ".join(str(item) for item in row.get("keywords", [])),
                " ".join(str(item) for item in row.get("mentions_rules", [])),
                " ".join(str(item) for item in row.get("mentions_attachments", [])),
            ]
        )
        score, reasons = _score_text_query(query, haystack, keywords=row.get("keywords", []), exact_boost=95.0)
        if target_ids and doc_id in target_ids:
            score += 45.0
            reasons.append("已限定目标文档")
        if article_match and str(row.get("article_no", "")) == article_match.group(0):
            score += 80.0
            reasons.append("条文编号命中")
        if wants_formula and row.get("has_formula"):
            score += 30.0
            reasons.append("公式型 section")
        if not score:
            continue

        item = dict(row)
        item["doc_id"] = doc_id
        item["text_preview"] = _truncate(str(row.get("text", "")), 420)
        hits.append(_add_score_reason(item, score, reasons))

    hits.sort(
        key=lambda item: (
            float(item.get("score", 0.0)),
            bool(item.get("has_formula")),
            -int(item.get("token_count", 0) or 0),
        ),
        reverse=True,
    )
    return hits[:limit]


def _clean_variable_token(value: str) -> str:
    token = value.strip().strip("{}").strip()
    token = re.sub(r"\s+", "", token)
    token = token.replace("\\_", "_").replace("\\", "")
    token = token.replace("^{*}", "").replace("^*", "").replace("^T", "_T")
    token = re.sub(r"_\{([^{}]+)\}", r"_\1", token)
    token = re.sub(r"\{([^{}]+)\}", r"\1", token)
    token = token.strip("_")
    return token


def _should_keep_variable(value: str) -> bool:
    token = _clean_variable_token(value)
    if not token:
        return False
    lowered = token.lower()
    if lowered in LATEX_CONTROL_WORDS:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?%?", token):
        return False
    if re.fullmatch(r"[_^{}()\\]+", token):
        return False
    if token in {"M", "C", "E", "X", "R", "F", "T"}:
        return False
    return True


def clean_formula_variables(formula_text: str) -> list[str]:
    raw = formula_text.replace("```math", "").replace("```", "").replace("$$", "")
    variables: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        token = _clean_variable_token(value)
        if not _should_keep_variable(token):
            return
        key = _normalize_text(token)
        if not key or key in seen:
            return
        seen.add(key)
        variables.append(token)

    macro_pattern = re.compile(
        r"\\(?P<macro>mathrm|mathbf|mathit|operatorname|text)\s*\{\s*(?P<base>[^{}]+?)\s*\}"
        r"\s*(?:_\s*(?:\{\s*(?P<braced_sub>[^{}]+?)\s*\}|(?P<plain_sub>[A-Za-z0-9]+)))?",
        flags=re.DOTALL,
    )
    for match in macro_pattern.finditer(raw):
        macro = match.group("macro")
        base = _clean_variable_token(match.group("base"))
        subscript = _clean_variable_token(match.group("braced_sub") or match.group("plain_sub") or "")
        if macro == "text" and not re.search(r"[A-Za-z]", base):
            continue
        if subscript and _should_keep_variable(subscript):
            add(f"{base}_{subscript}")
        add(base)

    for match in re.finditer(
        r"(?<!\\)\b([A-Za-z][A-Za-z0-9]*)\s*_\s*(?:\{\s*([A-Za-z0-9*]+)\s*\}|([A-Za-z0-9*]+))",
        raw,
    ):
        base = _clean_variable_token(match.group(1))
        subscript = _clean_variable_token(match.group(2) or match.group(3) or "")
        if subscript:
            add(f"{base}_{subscript}")
        add(base)

    for command in re.findall(r"\\([A-Za-z]+)", raw):
        if command in GREEK_VARIABLES:
            add(command)

    without_commands = re.sub(r"\\[A-Za-z]+", " ", raw)
    without_commands = re.sub(r"[{}_^]", " ", without_commands)
    for token in re.findall(r"\b[A-Za-z][A-Za-z0-9]{0,30}\b", without_commands):
        add(token)

    return variables[:16]


def search_formulas(
    query: str,
    *,
    limit: int = 5,
    doc_ids: list[str] | None = None,
    root: Path = READY_DATA_ROOT,
) -> list[dict[str, Any]]:
    target_ids = _scope_doc_ids(doc_ids)
    hits: list[dict[str, Any]] = []
    wants_formula = any(marker in query for marker in FORMULA_MARKERS)

    for row in _load_jsonl(root, "formula_cards.jsonl"):
        doc_id = normalize_doc_id(str(row.get("doc_id", "")))
        if target_ids and doc_id not in target_ids:
            continue
        cleaned_variables = clean_formula_variables(str(row.get("formula_text", "")))
        haystack = "\n".join(
            [
                str(row.get("title", "")),
                str(row.get("section_heading", "")),
                str(row.get("article_no", "")),
                str(row.get("formula_text", "")),
                " ".join(cleaned_variables),
                " ".join(str(item) for item in row.get("keywords", [])),
            ]
        )
        score, reasons = _score_text_query(query, haystack, keywords=[*cleaned_variables, *row.get("keywords", [])])
        if target_ids and doc_id in target_ids:
            score += 50.0
            reasons.append("已限定目标文档")
        if wants_formula:
            score += 25.0
            reasons.append("公式查询")
        if not score:
            continue
        item = {
            **row,
            "doc_id": doc_id,
            "variables": cleaned_variables,
            "variable_hints": cleaned_variables[:6],
            "formula_preview": _truncate(str(row.get("formula_text", "")), 240),
        }
        hits.append(_add_score_reason(item, score, reasons))

    def formula_order(item: dict[str, Any]) -> int:
        match = re.search(r"#formula-(\d+)$", str(item.get("formula_id", "")))
        return int(match.group(1)) if match else 9999

    hits.sort(key=lambda item: (-float(item.get("score", 0.0)), formula_order(item), str(item.get("formula_id", ""))))
    return hits[:limit]


def find_formula(formula_id: str, *, root: Path = READY_DATA_ROOT) -> dict[str, Any] | None:
    normalized = normalize_doc_id(formula_id)
    for row in _load_jsonl(root, "formula_cards.jsonl"):
        if normalize_doc_id(str(row.get("formula_id", ""))) == normalized:
            return {
                **row,
                "doc_id": normalize_doc_id(str(row.get("doc_id", ""))),
                "variables": clean_formula_variables(str(row.get("formula_text", ""))),
            }
    return None


def _find_formula_section(formula: dict[str, Any], *, root: Path = READY_DATA_ROOT) -> dict[str, Any] | None:
    doc_id = normalize_doc_id(str(formula.get("doc_id", "")))
    article_no = str(formula.get("article_no") or "")
    section_heading = str(formula.get("section_heading") or "")
    formula_text = _normalize_text(str(formula.get("formula_text") or ""))
    candidates = [row for row in _load_jsonl(root, "sections_structured.jsonl") if normalize_doc_id(str(row.get("doc_id", ""))) == doc_id]

    for row in candidates:
        if article_no and str(row.get("article_no") or "") == article_no:
            return row
    for row in candidates:
        if section_heading and str(row.get("section_heading") or "") == section_heading and row.get("has_formula"):
            return row
    for row in candidates:
        if formula_text and formula_text[:80] in _normalize_text(str(row.get("text", ""))):
            return row
    return candidates[0] if candidates else None


def _variable_context(variable: str, section_text: str, *, limit: int = 2) -> list[str]:
    base = variable.split("_", 1)[0]
    candidates = {variable, variable.replace("_", ""), base}
    snippets: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip(" -\t")
        if not line:
            continue
        normalized_line = _normalize_text(line)
        if any(_normalize_text(item) and _normalize_text(item) in normalized_line for item in candidates):
            snippets.append(_truncate(line, 180))
        if len(snippets) >= limit:
            break
    return snippets


def explain_formula(
    *,
    query: str | None = None,
    formula_id: str | None = None,
    root: Path = READY_DATA_ROOT,
) -> dict[str, Any]:
    formula: dict[str, Any] | None = None
    if formula_id:
        formula = find_formula(formula_id, root=root)
    elif query:
        hits = search_formulas(query, limit=1, root=root)
        formula = hits[0] if hits else None

    if formula is None:
        return {
            "ok": False,
            "query": query,
            "formula_id": formula_id,
            "message": "未找到可解释的公式。",
            "formula": None,
            "section": None,
        }

    section = _find_formula_section(formula, root=root)
    section_text = str(section.get("text", "")) if section else ""
    variables = clean_formula_variables(str(formula.get("formula_text", "")))
    explanations = [
        {
            "variable": variable,
            "evidence": _variable_context(variable, section_text),
        }
        for variable in variables
    ]
    return {
        "ok": True,
        "query": query,
        "formula_id": str(formula.get("formula_id", "")),
        "doc_id": normalize_doc_id(str(formula.get("doc_id", ""))),
        "title": str(formula.get("title", "")),
        "path": str(formula.get("path", "")),
        "article_no": formula.get("article_no"),
        "section_heading": str(formula.get("section_heading", "")),
        "formula_text": str(formula.get("formula_text", "")),
        "variables": variables,
        "variable_explanations": explanations,
        "applicability_evidence": _truncate(section_text, 700) if section_text else "",
        "section": section,
        "citations": [
            {
                "source_kind": "formula",
                "id": str(formula.get("formula_id", "")),
                "path": str(formula.get("path", "")),
                "section_heading": str(formula.get("section_heading", "")),
            }
        ],
    }


def resolve_doc_ids(query_or_id: str, *, limit: int = 5, root: Path = READY_DATA_ROOT) -> list[str]:
    normalized_value = normalize_doc_id(query_or_id)
    catalog = _catalog_by_doc_id(root)
    if normalized_value in catalog:
        return [normalized_value]

    query_norm = _normalize_text(query_or_id)
    scored: list[tuple[float, str]] = []
    for row in _load_jsonl(root, "title_aliases.jsonl"):
        alias_norm = str(row.get("normalized_alias") or _normalize_text(str(row.get("alias", ""))))
        doc_id = normalize_doc_id(str(row.get("doc_id", "")))
        if not alias_norm or not doc_id:
            continue
        score = 0.0
        if query_norm == alias_norm:
            score = 200.0
        elif alias_norm in query_norm or query_norm in alias_norm:
            score = 120.0
        if score:
            scored.append((score, doc_id))

    for doc_id, row in catalog.items():
        haystack = "\n".join(
            [
                str(row.get("title", "")),
                " ".join(str(item) for item in row.get("aliases", [])),
                str(row.get("summary_short", "")),
            ]
        )
        score, _reasons = _score_text_query(query_or_id, haystack)
        if score:
            scored.append((score, doc_id))

    scored.sort(key=lambda item: item[0], reverse=True)
    doc_ids: list[str] = []
    for _score, doc_id in scored:
        if doc_id not in doc_ids:
            doc_ids.append(doc_id)
        if len(doc_ids) >= limit:
            break
    return doc_ids


def _enrich_edge(edge: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source = normalize_doc_id(str(edge.get("source", "")))
    target = normalize_doc_id(str(edge.get("target", "")))
    return {
        **edge,
        "source": source,
        "target": target,
        "source_title": str(catalog.get(source, {}).get("title", "")),
        "target_title": str(catalog.get(target, {}).get("title", "")),
        "source_path": _doc_path(source, catalog),
        "target_path": _doc_path(target, catalog),
    }


def trace_relations(
    *,
    doc_id: str | None = None,
    query: str | None = None,
    direction: str = "both",
    relation: str | None = None,
    limit: int = 20,
    root: Path = READY_DATA_ROOT,
) -> dict[str, Any]:
    catalog = _catalog_by_doc_id(root)
    target_ids = [normalize_doc_id(doc_id)] if doc_id else resolve_doc_ids(query or "", root=root)
    graph = _load_relations(root)
    edges: list[dict[str, Any]] = []
    relation_filter = relation.strip() if relation else ""

    for edge in graph.get("edges", []):
        source = normalize_doc_id(str(edge.get("source", "")))
        target = normalize_doc_id(str(edge.get("target", "")))
        if relation_filter and edge.get("relation") != relation_filter:
            continue
        matches_source = source in target_ids
        matches_target = target in target_ids
        if direction == "out" and not matches_source:
            continue
        if direction == "in" and not matches_target:
            continue
        if direction == "both" and not (matches_source or matches_target):
            continue
        edges.append(_enrich_edge(edge, catalog))

    return {
        "query": query,
        "doc_id": doc_id,
        "resolved_doc_ids": target_ids,
        "direction": direction,
        "relation": relation_filter or None,
        "edges": edges[:limit],
    }


def trace_notices(rule: str, *, limit: int = 20, root: Path = READY_DATA_ROOT) -> dict[str, Any]:
    resolved_rules = resolve_doc_ids(rule, root=root)
    graph = _load_relations(root)
    catalog = _catalog_by_doc_id(root)
    edges: list[dict[str, Any]] = []
    for edge in graph.get("edges", []):
        source = normalize_doc_id(str(edge.get("source", "")))
        target = normalize_doc_id(str(edge.get("target", "")))
        if target not in resolved_rules:
            continue
        if str(catalog.get(source, {}).get("category", "")) != "notices":
            continue
        edges.append(_enrich_edge(edge, catalog))
    return {"rule": rule, "resolved_doc_ids": resolved_rules, "edges": edges[:limit]}


def trace_adjustments(notice: str, *, limit: int = 20, root: Path = READY_DATA_ROOT) -> dict[str, Any]:
    resolved_notices = resolve_doc_ids(notice, root=root)
    graph = _load_relations(root)
    catalog = _catalog_by_doc_id(root)
    semantic_relations = {"adjusts_rule", "extends_transition", "clarifies_formula", "applies_to_rule", "requires_attachment"}
    edges: list[dict[str, Any]] = []
    for edge in graph.get("edges", []):
        source = normalize_doc_id(str(edge.get("source", "")))
        if source not in resolved_notices:
            continue
        if edge.get("relation") not in semantic_relations and str(edge.get("relation")) != "mentions_rule":
            continue
        edges.append(_enrich_edge(edge, catalog))
    return {"notice": notice, "resolved_doc_ids": resolved_notices, "edges": edges[:limit]}


def build_evidence_plan(question_type: str, scoped_doc_ids: list[str] | None) -> dict[str, Any]:
    if question_type == "catalog":
        return {
            "scope_doc_ids": [],
            "steps": ["catalog"],
            "answer_rule": "目录统计类问题必须回到 manifest/目录元数据后再回答。",
        }
    steps = ["titles"]
    if question_type in {"summary", "comparison", "version", "analysis", "locate"}:
        steps.append("summaries")
    if question_type in {"formula", "compliance", "analysis", "version"}:
        steps.append("sections")
    if question_type == "formula":
        steps.append("formulas")
    if question_type in {"version", "comparison"}:
        steps.append("relations")
    return {
        "scope_doc_ids": [normalize_doc_id(item) for item in scoped_doc_ids or []],
        "steps": list(dict.fromkeys(steps)),
        "answer_rule": "必须回到 summary/section/formula 原文证据后再回答；关系边只作为导航提示。",
    }


def _catalog_manifest_evidence(root: Path = READY_DATA_ROOT) -> dict[str, Any]:
    manifest_path = root.parent / "manifest.json"
    text = "目录统计类问题使用 manifest.json 元数据回答。"
    if manifest_path.exists():
        raw = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if isinstance(raw, list):
            entries = raw
        elif isinstance(raw, dict):
            entries = raw.get("entries", [])
        else:
            entries = []
        if isinstance(entries, list):
            rules_count = sum(
                1 for item in entries if isinstance(item, dict) and item.get("category") == "rules"
            )
            text = f"manifest 共收录 {rules_count} 份 rules 类文件，可用于回答监管规则数量问题。"

    return {
        "doc_id": CATALOG_MANIFEST_DOC_ID,
        "path": CATALOG_MANIFEST_PATH,
        "title": "知识库目录清单",
        "source_kind": "catalog",
        "text": text,
        "score": 1.0,
    }


def collect_evidence(
    question: str,
    *,
    plan: dict[str, Any] | None = None,
    limit: int = 5,
    root: Path = READY_DATA_ROOT,
) -> dict[str, Any]:
    question_type = str((plan or {}).get("question_type", "analysis"))
    scoped_doc_ids = [normalize_doc_id(str(item)) for item in (plan or {}).get("scoped_doc_ids", [])]
    if question_type == "catalog":
        catalog_hit = _catalog_manifest_evidence(root)
        return {
            "question": question,
            "plan": plan or {},
            "evidence": {
                "catalog": [catalog_hit],
                "summaries": [],
                "sections": [],
                "formulas": [],
                "relations": [],
            },
            "citations": [
                {
                    "source_kind": "catalog",
                    "id": catalog_hit["doc_id"],
                    "path": catalog_hit["path"],
                    "title": catalog_hit["title"],
                }
            ],
        }

    if not scoped_doc_ids:
        scoped_doc_ids = [
            normalize_doc_id(str(hit.get("doc_id", "")))
            for hit in (plan or {}).get("title_hits", [])[:2]
            if str(hit.get("doc_id", "")).strip()
        ]
    doc_scope = scoped_doc_ids or None
    summaries = search_summaries(question, limit=limit, doc_ids=doc_scope, root=root)
    sections = search_sections(question, limit=limit, doc_ids=doc_scope, root=root)
    formulas = search_formulas(question, limit=limit, doc_ids=doc_scope, root=root) if any(
        marker in question for marker in FORMULA_MARKERS
    ) or question_type == "formula" else []

    relation_edges: list[dict[str, Any]] = []
    if any(marker in question for marker in RELATION_MARKERS) or question_type in {"version", "comparison"}:
        for scoped_doc_id in scoped_doc_ids:
            relation_edges.extend(
                trace_relations(doc_id=scoped_doc_id, direction="out", limit=max(limit, 10), root=root).get("edges", [])
            )
            relation_edges.extend(
                trace_relations(doc_id=scoped_doc_id, direction="in", limit=max(limit, 10), root=root).get("edges", [])
            )
        if not scoped_doc_ids:
            relation_edges.extend(trace_relations(query=question, limit=limit, root=root).get("edges", []))

    citations: list[dict[str, Any]] = []
    for summary in summaries[:2]:
        citations.append(
            {
                "source_kind": "summary",
                "id": summary.get("doc_id"),
                "path": summary.get("path"),
                "title": summary.get("title"),
            }
        )
    for section in sections[:3]:
        citations.append(
            {
                "source_kind": "section",
                "id": section.get("section_id"),
                "path": section.get("path"),
                "title": section.get("title"),
                "section_heading": section.get("section_heading"),
                "article_no": section.get("article_no"),
            }
        )
    for formula in formulas[:2]:
        citations.append(
            {
                "source_kind": "formula",
                "id": formula.get("formula_id"),
                "path": formula.get("path"),
                "title": formula.get("title"),
                "section_heading": formula.get("section_heading"),
                "article_no": formula.get("article_no"),
            }
        )

    return {
        "question": question,
        "plan": plan or {},
        "evidence": {
            "summaries": summaries,
            "sections": sections,
            "formulas": formulas,
            "relations": relation_edges[:limit],
        },
        "citations": citations,
    }


def evidence_to_answer_hits(evidence: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    evidence_groups = evidence.get("evidence", {}) if isinstance(evidence, dict) else {}

    for summary in evidence_groups.get("summaries", [])[:2]:
        text = str(summary.get("summary_structured") or summary.get("summary_short") or "")
        if not text:
            continue
        hits.append(
            {
                "path": summary.get("path"),
                "title": summary.get("title"),
                "text": text,
                "source_kind": "summary",
                "retrieval_score": float(summary.get("score", 0.0)) / 100.0,
            }
        )

    for section in evidence_groups.get("sections", [])[:4]:
        text = str(section.get("text", ""))
        if not text:
            continue
        hits.append(
            {
                "path": section.get("path"),
                "title": section.get("title"),
                "text": text,
                "source_kind": "section",
                "section_heading": section.get("section_heading"),
                "article_no": section.get("article_no"),
                "retrieval_score": float(section.get("score", 0.0)) / 100.0,
            }
        )

    for formula in evidence_groups.get("formulas", [])[:2]:
        text = "\n".join(
            [
                str(formula.get("formula_text", "")),
                "变量：" + "、".join(str(item) for item in formula.get("variables", [])),
            ]
        ).strip()
        if not text:
            continue
        hits.append(
            {
                "path": formula.get("path"),
                "title": formula.get("title"),
                "text": text,
                "source_kind": "formula",
                "section_heading": formula.get("section_heading"),
                "article_no": formula.get("article_no"),
                "retrieval_score": float(formula.get("score", 0.0)) / 100.0,
            }
        )

    return hits[:limit]


def answer_verified(question: str, *, plan: dict[str, Any] | None = None, root: Path = READY_DATA_ROOT) -> dict[str, Any]:
    evidence = collect_evidence(question, plan=plan, root=root)
    groups = evidence["evidence"]
    citations = evidence["citations"]
    if not any(groups.values()):
        return {
            "mode": "verified",
            "answer": "当前 ready_data 证据不足以回答该问题；建议先检查最相关 Markdown 或重建 ready_data。",
            "evidence": evidence,
            "citations": [],
        }

    if groups.get("catalog"):
        catalog_hit = groups["catalog"][0]
        answer = f"根据目录元数据，{catalog_hit.get('text')} [1]"
        return {"mode": "verified", "answer": answer, "evidence": evidence, "citations": citations[:1]}

    if groups["formulas"]:
        explanation = explain_formula(formula_id=str(groups["formulas"][0].get("formula_id", "")), root=root)
        variables = "、".join(explanation.get("variables", [])) or "未识别到稳定变量"
        formula_citations = [citation for citation in citations if citation.get("source_kind") == "formula"]
        answer = (
            "根据 ready_data 中的公式卡和对应 section，最相关公式为：\n\n"
            f"{explanation.get('formula_text', '')}\n\n"
            f"已过滤 LaTeX 控制词后的变量包括：{variables}。"
        )
        if explanation.get("applicability_evidence"):
            answer += f"\n\n适用上下文证据：{_truncate(str(explanation['applicability_evidence']), 500)}"
        answer += " [1]"
        return {"mode": "verified", "answer": answer, "evidence": evidence, "citations": formula_citations[:1] or citations[:1]}

    if groups["sections"]:
        section = groups["sections"][0]
        heading = str(section.get("section_heading") or section.get("title") or "")
        article = str(section.get("article_no") or "")
        section_citations = [citation for citation in citations if citation.get("source_kind") == "section"]
        answer = f"根据结构化 section 证据，{article + ' ' if article else ''}{heading} 中的相关规定是：{_truncate(str(section.get('text', '')), 700)} [1]"
        return {"mode": "verified", "answer": answer, "evidence": evidence, "citations": section_citations[:1] or citations[:1]}

    summary = groups["summaries"][0]
    answer = f"根据摘要层证据，{summary.get('title')} 的要点是：{summary.get('summary_structured') or summary.get('summary_short')} [1]"
    return {"mode": "verified", "answer": answer, "evidence": evidence, "citations": citations[:1]}


def inspect_ready_data(root: Path = READY_DATA_ROOT, *, sample_size: int = 2) -> dict[str, Any]:
    root = root.resolve()
    counts = {
        "doc_count": len(_load_jsonl(root, "doc_catalog.jsonl")),
        "alias_count": len(_load_jsonl(root, "title_aliases.jsonl")),
        "summary_count": len(_load_jsonl(root, "doc_summaries.jsonl")),
        "section_count": len(_load_jsonl(root, "sections_structured.jsonl")),
        "formula_count": len(_load_jsonl(root, "formula_cards.jsonl")),
        "relation_edge_count": len(_load_relations(root).get("edges", [])),
    }
    manifest_path = root / "ready_data_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return {
        "root": str(root),
        "counts": counts,
        "manifest": manifest,
        "samples": {
            "summaries": _load_jsonl(root, "doc_summaries.jsonl")[:sample_size],
            "sections": _load_jsonl(root, "sections_structured.jsonl")[:sample_size],
            "formulas": _load_jsonl(root, "formula_cards.jsonl")[:sample_size],
            "relations": _load_relations(root).get("edges", [])[:sample_size],
        },
    }


def validate_ready_data(root: Path = READY_DATA_ROOT) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    for name in REQUIRED_ARTIFACTS:
        if not (root / name).exists():
            errors.append(f"缺少产物：{name}")

    counts: dict[str, int] = {}
    for name, required_fields in JSONL_REQUIRED_FIELDS.items():
        rows = _load_jsonl(root, name) if (root / name).exists() else []
        counts[name] = len(rows)
        for index, row in enumerate(rows, start=1):
            missing = sorted(field for field in required_fields if field not in row)
            if missing:
                errors.append(f"{name}:{index} 缺少字段 {missing}")
                break

    relation_graph = _load_relations(root)
    counts["relations_graph.edges"] = len(relation_graph.get("edges", []))
    if not isinstance(relation_graph.get("nodes", []), list) or not isinstance(relation_graph.get("edges", []), list):
        errors.append("relations_graph.json 必须包含 nodes 和 edges 列表")

    manifest_path = root / "ready_data_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest_expectations = {
        "doc_count": counts.get("doc_catalog.jsonl", 0),
        "alias_count": counts.get("title_aliases.jsonl", 0),
        "summary_count": counts.get("doc_summaries.jsonl", 0),
        "section_count": counts.get("sections_structured.jsonl", 0),
        "formula_count": counts.get("formula_cards.jsonl", 0),
        "relation_edge_count": counts.get("relations_graph.edges", 0),
    }
    for field, expected in manifest_expectations.items():
        if field in manifest and int(manifest.get(field) or 0) != expected:
            errors.append(f"manifest {field}={manifest.get(field)}，实际为 {expected}")

    for row in _load_jsonl(root, "formula_cards.jsonl"):
        noisy = [item for item in row.get("variables", []) if _normalize_text(str(item)) in LATEX_CONTROL_WORDS]
        if noisy:
            warnings.append(f"{row.get('formula_id')} 仍含 LaTeX 控制词变量：{noisy[:3]}")
            if len(warnings) >= 5:
                break

    return {
        "ok": not errors,
        "root": str(root),
        "counts": manifest_expectations,
        "errors": errors,
        "warnings": warnings,
    }


def _default_retrieval_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "rule_count",
            "question": "偿二代二期监管规则一共有多少号规定？",
            "expected_doc": "Knowledge_Base_MarkDown/manifest.json",
            "category": "规则数量类",
        },
        {
            "case_id": "rule2_overview",
            "question": "保险公司偿付能力监管规则第2号主要涉及什么内容？",
            "expected_doc": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
            "category": "单规则概览类",
        },
        {
            "case_id": "minimum_capital_components",
            "question": "最低资本由哪些部分组成？",
            "expected_doc": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
            "category": "条文结论类",
        },
        {
            "case_id": "rule2_formula",
            "question": "规则第2号里最低资本的计算公式是什么？请解释变量含义。",
            "expected_doc": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
            "category": "公式解释类",
        },
        {
            "case_id": "threshold_interest_curve",
            "question": "终极利率暂定为多少？",
            "expected_doc": "attachments/附件1：寿险合同负债评估的折现率曲线.md",
            "category": "阈值类",
        },
        {
            "case_id": "attachment4_summary",
            "question": "附件4是什么，主要包含什么内容？",
            "expected_doc": "attachments/附件4：保险公司压力测试必测压力情景和必测因素.md",
            "category": "附件定位类",
        },
        {
            "case_id": "notice_adjustment",
            "question": "优化保险公司偿付能力监管标准的通知调整了哪些规则？",
            "expected_doc": "notices/【2023-9 金规5号】国家金融监督管理总局关于优化保险公司偿付能力监管标准的通知.md",
            "category": "通知调整类",
        },
        {
            "case_id": "control_risk_relation",
            "question": "控制风险最低资本按照哪一项规则计量？",
            "expected_doc": "rules/保险公司偿付能力监管规则第12号：偿付能力风险管理要求与评估.md",
            "category": "跨规则关系类",
        },
    ]


def load_retrieval_cases(cases_path: Path | None = None) -> list[dict[str, Any]]:
    if cases_path is None or not cases_path.exists():
        return _default_retrieval_cases()
    return _read_jsonl(cases_path)


def run_retrieval_eval(
    *,
    cases_path: Path | None = None,
    root: Path = READY_DATA_ROOT,
    planner: Any | None = None,
) -> dict[str, Any]:
    cases = load_retrieval_cases(cases_path)
    results: list[dict[str, Any]] = []
    passed = 0
    for case in cases:
        question = str(case.get("question", ""))
        expected_doc = normalize_doc_id(str(case.get("expected_doc", "")))
        plan = planner(question) if planner else {}
        evidence = collect_evidence(question, plan=plan, root=root)
        candidate_doc_ids: list[str] = []
        for hit in plan.get("title_hits", []) if isinstance(plan, dict) else []:
            candidate_doc_ids.append(normalize_doc_id(str(hit.get("doc_id", ""))))
        for group in evidence.get("evidence", {}).values():
            if not isinstance(group, list):
                continue
            for item in group:
                if isinstance(item, dict):
                    for key in ("doc_id", "source", "target"):
                        if item.get(key):
                            candidate_doc_ids.append(normalize_doc_id(str(item.get(key))))
        unique_doc_ids = [item for item in dict.fromkeys(candidate_doc_ids) if item]
        ok = expected_doc in unique_doc_ids
        if ok:
            passed += 1
        results.append(
            {
                "case_id": case.get("case_id"),
                "category": case.get("category"),
                "question": question,
                "expected_doc": expected_doc,
                "ok": ok,
                "question_type": plan.get("question_type") if isinstance(plan, dict) else None,
                "candidate_doc_ids": unique_doc_ids[:10],
            }
        )

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / max(1, len(results)), 4),
        "cases": results,
    }


def add_feedback(
    *,
    question: str,
    expected_doc: str = "",
    note: str = "",
    path: Path = DEFAULT_FEEDBACK_PATH,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "expected_doc": normalize_doc_id(expected_doc),
        "note": note,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(path), "record": record}
