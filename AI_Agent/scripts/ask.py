from __future__ import annotations

import argparse
import json
import re
import os
import pickle
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import tiktoken
from openai import OpenAI

# Add parent directory to path for local imports when executed as a script.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from agentic_rag import AgenticRagEngine
from build_index import derive_section_index_path, derive_section_meta_path
from project_config import DEFAULT_OUTPUT_LANGUAGE, KNOWLEDGE_BASE_NAME, load_project_env
from query_enhancements import rerank_hits
from utils import extract_json_payload, retry_with_exponential_backoff

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parent

load_project_env(PROJECT_ROOT)

MODEL = os.getenv("MODEL", "gpt-4.1")
EMB_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
DEFAULT_MODE = os.getenv("RAG_MODE", "agentic")
DEFAULT_TOP_K = int(os.getenv("TOP_K", "4"))
DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.0"))
DEFAULT_MAX_ITERATIONS = int(os.getenv("AGENTIC_MAX_ITERATIONS", "2"))
DEFAULT_SYNTHESIS_TOP_K = os.getenv("AGENTIC_SYNTHESIS_TOP_K")
DEFAULT_DOC_CONTEXT_TOKENS = int(os.getenv("DOC_CONTEXT_TOKENS", "120000"))
DEFAULT_SECTION_CONTEXT_TOKENS = int(os.getenv("SECTION_CONTEXT_TOKENS", "16000"))
DEFAULT_LANGUAGE = os.getenv("OUTPUT_LANGUAGE", DEFAULT_OUTPUT_LANGUAGE)
INSUFFICIENT_INFO_RESPONSE = "I don't have enough information to answer this question."
RULE_NUMBER_PATTERN = re.compile(r"\u89c4\u5219\u7b2c(\d+)\u53f7")
COUNT_QUERY_MARKERS = (
    "\u591a\u5c11",
    "\u51e0",
    "\u603b\u5171",
    "\u4e00\u5171",
    "\u5171\u6709",
    "\u603b\u6570",
)
COUNT_SCOPE_MARKERS = (
    "\u89c4\u5219",
    "\u89c4\u5b9a",
    "\u9644\u4ef6",
    "\u901a\u77e5",
)
SECTION_QUERY_MARKERS = (
    "\u516c\u5f0f",
    "\u6761",
    "\u6b3e",
    "\u8868",
    "\u8868\u683c",
    "\u540d\u5355",
    "\u9636\u6bb5",
    "\u66f2\u7ebf",
    "\u60c5\u666f",
    "\u56e0\u5b50",
    "\u7cfb\u6570",
    "\u9608\u503c",
    "\u4e0a\u9650",
    "\u4e0b\u9650",
    "\u6bd4\u4f8b",
    "\u53d6\u503c",
    "\u5b9a\u4e49",
    "\u600e\u4e48\u8ba1\u7b97",
    "\u8ba1\u7b97\u516c\u5f0f",
)
DOCUMENT_QUERY_MARKERS = (
    "\u4e3b\u8981\u5185\u5bb9",
    "\u4e3b\u8981\u6d89\u53ca",
    "\u6982\u89c8",
    "\u6982\u8981",
    "\u603b\u7ed3",
    "\u4ecb\u7ecd",
    "\u6982\u62ec",
    "\u8bb2\u4ec0\u4e48",
    "\u9002\u7528\u8303\u56f4",
)
HYBRID_QUERY_MARKERS = (
    "\u6bd4\u8f83",
    "\u5bf9\u6bd4",
    "\u533a\u522b",
    "\u5173\u7cfb",
    "\u8054\u7cfb",
    "\u5206\u522b",
    "\u540c\u65f6",
    "\u7efc\u5408",
)


def _resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default.resolve()
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (PROJECT_ROOT / candidate).resolve()


INDEX_PATH = _resolve_path(os.getenv("INDEX_PATH"), PROJECT_ROOT / "knowledge_base.faiss")
META_PATH = _resolve_path(os.getenv("META_PATH"), PROJECT_ROOT / "knowledge_base.meta.pkl")
MANIFEST_PATH = _resolve_path(os.getenv("MANIFEST_PATH"), REPO_ROOT / "Knowledge_Base_MarkDown" / "manifest.json")
_INDEX_CACHE = None
_DOCS_CACHE = None
_SECTION_INDEX_CACHE = None
_SECTION_DOCS_CACHE = None
_INDEX_CACHE_PATHS = None
_SECTION_CACHE_PATHS = None
_MANIFEST_CACHE = None
_ENCODER = None


class _FallbackEncoder:
    def encode(self, text: str) -> list[str]:
        return re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]", text)

    def decode(self, tokens: list[str]) -> str:
        return "".join(tokens)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lower()


def _section_index_path() -> Path:
    env_value = os.getenv("SECTION_INDEX_PATH")
    if env_value:
        return _resolve_path(env_value, derive_section_index_path(INDEX_PATH))
    return derive_section_index_path(INDEX_PATH).resolve()


def _section_meta_path() -> Path:
    env_value = os.getenv("SECTION_META_PATH")
    if env_value:
        return _resolve_path(env_value, derive_section_meta_path(META_PATH))
    return derive_section_meta_path(META_PATH).resolve()


def get_index_artifact_paths() -> tuple[Path, Path, Path, Path]:
    return INDEX_PATH, META_PATH, _section_index_path(), _section_meta_path()


def _get_encoder():
    global _ENCODER
    if _ENCODER is None:
        try:
            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _ENCODER = _FallbackEncoder()
    return _ENCODER


def _normalize_match_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def _extract_filename_hints(question: str) -> list[str]:
    return re.findall(r"(规则第\d+号|第\d+号|附件\d+(?:-\d+)?)", question)


def classify_retrieval_strategy(question: str) -> str:
    normalized = question.replace(" ", "")

    if any(marker in normalized for marker in HYBRID_QUERY_MARKERS):
        return "hybrid"

    has_document_marker = any(marker in normalized for marker in DOCUMENT_QUERY_MARKERS)
    has_section_marker = any(marker in normalized for marker in SECTION_QUERY_MARKERS)

    if has_document_marker and not has_section_marker:
        return "document"
    if has_section_marker and not has_document_marker:
        return "section"
    if has_document_marker and has_section_marker:
        return "hybrid"

    return "hybrid"


def _collect_filename_match_hits(
    question: str,
    docs: list[dict],
    *,
    max_paths: int = 3,
    chunks_per_path: int = 2,
) -> list[dict]:
    docs_by_path: dict[str, list[dict]] = {}
    for doc in docs:
        docs_by_path.setdefault(str(doc.get("path", "")), []).append(doc)

    question_norm = _normalize_match_text(question)
    hints = _extract_filename_hints(question)
    scored_paths: list[tuple[float, str]] = []

    for path, path_docs in docs_by_path.items():
        if not path_docs:
            continue
        stem = Path(path).stem
        stem_norm = _normalize_match_text(stem)
        if not stem_norm:
            continue

        stem_hints = set(_extract_filename_hints(stem))
        numbered_hints = [hint for hint in hints if any(char.isdigit() for char in hint)]
        exact_number_match = any(hint in stem for hint in numbered_hints)

        if numbered_hints and stem_hints and not exact_number_match:
            continue

        score = 0.0
        for hint in hints:
            if hint in stem:
                score += 50.0

        if question_norm and question_norm in stem_norm:
            score += float(len(question_norm))
        elif stem_norm and stem_norm in question_norm:
            score += float(len(stem_norm))
        else:
            longest = SequenceMatcher(None, question_norm, stem_norm).find_longest_match(
                0,
                len(question_norm),
                0,
                len(stem_norm),
            ).size
            if longest >= 4:
                score += float(longest)

        if score > 0:
            scored_paths.append((score, path))

    scored_paths.sort(key=lambda item: item[0], reverse=True)

    direct_hits: list[dict] = []
    for score, path in scored_paths[:max_paths]:
        for item in docs_by_path[path][:chunks_per_path]:
            direct_hits.append(
                {
                    **item,
                    "retrieval_score": max(float(item.get("retrieval_score", 0.0)), 1.5 + score / 100.0),
                }
            )
    return direct_hits


def _legacy_get_system_prompt(language: str = "en") -> str:
    """
    Get the system prompt with language-specific instructions.

    Args:
        language: Language code ('en' or 'zh') - determines the response language

    Returns:
        System prompt with language instructions
    """

    base_prompt = (
        f"You are the documentation expert for the {KNOWLEDGE_BASE_NAME}. "
        "CRITICAL INSTRUCTIONS:\n"
        "1. Answer ONLY using information from the retrieved documents provided below.\n"
        "2. Every claim must cite evidence using only the numeric document tag in the format `[n]`.\n"
        "3. Structure answers with a short summary followed by bullet points of supporting evidence.\n"
        "4. If the documents do not contain sufficient information to answer the question, you MUST reply 'I don't have enough information to answer this question.' "
        "and recommend the most relevant Markdown file to inspect.\n"
        "5. NEVER make up information or draw conclusions not directly supported by the snippets.\n"
        "6. If you're uncertain about any detail, explicitly state your uncertainty.\n"
    )

    if language == "zh":
        base_prompt += (
            "7. LANGUAGE INSTRUCTION: Respond in Chinese (中文). "
            "Maintain the same professional tone and citation format, but use Chinese language for all explanations and summaries."
        )
    else:
        base_prompt += (
            "7. LANGUAGE INSTRUCTION: Respond in English. "
            "Maintain the same professional tone and citation format, and always use English for all explanations and summaries, even if the user's question is in another language."
        )

    return base_prompt


def get_system_prompt(language: str = "en") -> str:
    base_prompt = (
        f"You are the documentation expert for the {KNOWLEDGE_BASE_NAME}. "
        "CRITICAL INSTRUCTIONS:\n"
        "1. Answer ONLY using information from the retrieved documents provided below.\n"
        "2. Every claim must cite evidence using only the numeric document tag in the format `[n]`.\n"
        "3. Start with a direct answer, then provide a fuller, research-style explanation organized by theme when the evidence supports it.\n"
        "4. Prefer complete answers over minimal ones. Include relevant definitions, scope, formulas, conditions, thresholds, exceptions, reporting requirements, and cross-document links when they are directly supported.\n"
        "5. If the user asks for a summary, overview, or '主要内容', synthesize the whole retrieved document set instead of listing isolated fragments.\n"
        "6. Use prior conversation only as conversational context. Do not rely on anything from prior turns unless it is also supported by the retrieved documents in the current turn.\n"
        f"7. If the documents do not contain sufficient information to answer the question, reply '{INSUFFICIENT_INFO_RESPONSE}' and recommend the most relevant Markdown file to inspect.\n"
        "8. NEVER make up information or draw conclusions not directly supported by the retrieved documents.\n"
        "9. If you're uncertain about any detail, explicitly state the uncertainty.\n"
        "10. When the answer includes formulas, output valid LaTeX wrapped in `$...$` for inline math or `$$...$$` for block math. Preserve the source formula structure instead of rewriting it as plain text.\n"
    )

    if language == "zh":
        base_prompt += (
            "7. LANGUAGE INSTRUCTION: Respond in Chinese (中文). "
            "Maintain the same professional tone and citation format, but use Chinese for all explanations and summaries."
        )
    else:
        base_prompt += (
            "7. LANGUAGE INSTRUCTION: Respond in English. "
            "Maintain the same professional tone and citation format, and always use English for all explanations and summaries."
        )

    return base_prompt


def format_user_prompt(
    question: str,
    context: str,
    history: str | None = None,
    interpreted_question: str | None = None,
) -> str:
    history_block = ""
    if history:
        history_block = (
            "Prior conversation (use only as conversational context, not as evidence):\n"
            f"{history}\n\n"
        )
    interpreted_block = ""
    if interpreted_question and interpreted_question.strip() and interpreted_question.strip() != question.strip():
        interpreted_block = (
            "Interpreted latest question for retrieval continuity:\n"
            f"{interpreted_question}\n\n"
        )
    return (
        history_block
        + interpreted_block
        + f"You will receive full Markdown documents from the {KNOWLEDGE_BASE_NAME}. Each document already includes a numeric tag "
        "like [1], [2], etc., plus its file path. Use only these documents to answer the question. "
        "When citing information, cite only the numeric tag such as [1] or [2]. Do not repeat the file path or title in the answer body. "
        "Answer directly first, then expand with the most relevant supported details. "
        "If you include formulas, keep them as valid LaTeX using `$...$` or `$$...$$`. "
        "If the question asks for a summary, explanation, or comparison, organize the answer clearly by topic. "
        f"If there is no supporting document, reply '{INSUFFICIENT_INFO_RESPONSE}' and mention which Markdown file should be reviewed.\n\n"
        f"Retrieved documents:\n{context}\n\nQuestion: {question}"
    )


def _load_index(path: Path):
    try:
        return faiss.read_index(str(path))
    except TypeError:
        with open(path, "rb") as fh:
            buf = fh.read()
        arr = np.frombuffer(buf, dtype="uint8")
        return faiss.deserialize_index(arr)


def _validate_doc_metadata(docs: list[dict[str, Any]]) -> None:
    if any("token_count" not in doc or "title" not in doc for doc in docs):
        raise RuntimeError(
            "The current vector store was built with the legacy chunked format. "
            "Re-run scripts/build_index.py to rebuild the document-level index."
        )


def _validate_section_metadata(docs: list[dict[str, Any]]) -> None:
    if any("section_heading" not in doc or "section_kind" not in doc for doc in docs):
        raise RuntimeError(
            "The current section vector store is missing structured section metadata. "
            "Re-run scripts/build_index.py to rebuild the hybrid document/section indexes."
        )


def _load_manifest(refresh: bool = False) -> list[dict[str, Any]]:
    global _MANIFEST_CACHE

    if refresh or _MANIFEST_CACHE is None:
        if not MANIFEST_PATH.exists():
            raise FileNotFoundError(f"Manifest file not found: {MANIFEST_PATH}")

        with MANIFEST_PATH.open("r", encoding="utf-8-sig") as fh:
            raw = json.load(fh)

        if isinstance(raw, list):
            entries = raw
        elif isinstance(raw, dict):
            entries = raw.get("entries") or raw.get("documents") or raw.get("files") or []
        else:
            entries = []

        _MANIFEST_CACHE = [entry for entry in entries if isinstance(entry, dict)]

    return _MANIFEST_CACHE


def _load_artifacts(refresh: bool = False):
    global _INDEX_CACHE, _DOCS_CACHE, _INDEX_CACHE_PATHS
    current_paths = (INDEX_PATH.resolve(), META_PATH.resolve())

    if refresh or _INDEX_CACHE is None or _DOCS_CACHE is None or _INDEX_CACHE_PATHS != current_paths:
        if not INDEX_PATH.exists() or not META_PATH.exists():
            raise FileNotFoundError(
                "Missing vector store files. Run scripts/build_index.py first.\n"
                f"Expected:\n  {INDEX_PATH}\n  {META_PATH}"
            )

        _INDEX_CACHE = _load_index(INDEX_PATH)
        with META_PATH.open("rb") as fh:
            _DOCS_CACHE = pickle.load(fh)
        _validate_doc_metadata(_DOCS_CACHE)
        _INDEX_CACHE_PATHS = current_paths

    return _INDEX_CACHE, _DOCS_CACHE


def _load_section_artifacts(refresh: bool = False, *, required: bool = False):
    global _SECTION_INDEX_CACHE, _SECTION_DOCS_CACHE, _SECTION_CACHE_PATHS

    section_index_path = _section_index_path()
    section_meta_path = _section_meta_path()
    current_paths = (section_index_path.resolve(), section_meta_path.resolve())

    if not section_index_path.exists() or not section_meta_path.exists():
        _SECTION_INDEX_CACHE = None
        _SECTION_DOCS_CACHE = None
        _SECTION_CACHE_PATHS = None
        if required:
            raise FileNotFoundError(
                "Missing section vector store files. Run scripts/build_index.py first.\n"
                f"Expected:\n  {section_index_path}\n  {section_meta_path}"
            )
        return None, []

    if refresh or _SECTION_INDEX_CACHE is None or _SECTION_DOCS_CACHE is None or _SECTION_CACHE_PATHS != current_paths:
        _SECTION_INDEX_CACHE = _load_index(section_index_path)
        with section_meta_path.open("rb") as fh:
            _SECTION_DOCS_CACHE = pickle.load(fh)
        _validate_section_metadata(_SECTION_DOCS_CACHE)
        _SECTION_CACHE_PATHS = current_paths

    return _SECTION_INDEX_CACHE, _SECTION_DOCS_CACHE


def refresh_cache():
    """Reload FAISS and metadata, useful after re-building the index."""
    _load_artifacts(refresh=True)
    _load_section_artifacts(refresh=True, required=False)


def refresh_manifest_cache():
    _load_manifest(refresh=True)


def get_document_snippets(doc_path: str, limit: int | None = None):
    """Return FAISS metadata records for a specific Markdown path."""
    _, docs = _load_artifacts()
    target = _normalize_path(doc_path)
    matches = [doc for doc in docs if _normalize_path(doc["path"]).endswith(target)]
    if limit is not None:
        return matches[:limit]
    return matches


def _is_catalog_count_query(question: str) -> bool:
    normalized = question.replace("\uFF1F", "?").replace(" ", "")
    return any(marker in normalized for marker in COUNT_QUERY_MARKERS) and any(
        marker in normalized for marker in COUNT_SCOPE_MARKERS
    )


def _build_manifest_hit(entries: list[dict[str, Any]], summary_lines: list[str]) -> list[dict[str, str]]:
    snippet_lines = summary_lines[:]
    for entry in entries:
        path = entry.get("path", "")
        title = entry.get("title", "")
        if path and title:
            snippet_lines.append(f"- {title} ({path})")

    return [
        {
            "path": "Knowledge_Base_MarkDown/manifest.json",
            "text": "\n".join(snippet_lines),
            "retrieval_score": 1.0,
        }
    ]


def _answer_rule_count_question(question: str, *, language: str = DEFAULT_LANGUAGE) -> dict[str, Any] | None:
    normalized = question.replace(" ", "")
    if "\u89c4\u5219" not in normalized and "\u89c4\u5b9a" not in normalized:
        return None
    if not _is_catalog_count_query(normalized):
        return None

    entries = _load_manifest()
    numbered_rules: list[tuple[int, dict[str, Any]]] = []
    for entry in entries:
        if entry.get("category") != "rules":
            continue
        title = str(entry.get("title", ""))
        match = RULE_NUMBER_PATTERN.search(title)
        if match:
            numbered_rules.append((int(match.group(1)), entry))

    if not numbered_rules:
        return None

    numbered_rules.sort(key=lambda item: item[0])
    first_no = numbered_rules[0][0]
    last_no = numbered_rules[-1][0]
    count = len(numbered_rules)
    sample_entries = [numbered_rules[0][1], numbered_rules[-1][1]]

    if language == "zh":
        answer = (
            f"\u6839\u636e\u5f53\u524d\u77e5\u8bc6\u5e93\u6e05\u5355\uff0c\u507f\u4e8c\u4ee3\u4e8c\u671f\u76d1\u7ba1\u89c4\u5219\u5171\u6536\u5f55 {count} \u9879\uff0c"
            f"\u7f16\u53f7\u4ece\u7b2c{first_no}\u53f7\u5230\u7b2c{last_no}\u53f7\u3002"
            " [1] Knowledge_Base_MarkDown/manifest.json"
        )
        summary_lines = [
            f"\u5f53\u524d manifest \u5171\u6536\u5f55 {count} \u4efd `rules` \u7c7b\u6587\u4ef6\u3002",
            f"\u89c4\u5219\u7f16\u53f7\u8303\u56f4\uff1a\u7b2c{first_no}\u53f7\u81f3\u7b2c{last_no}\u53f7\u3002",
        ]
    else:
        answer = (
            f"According to the current knowledge-base manifest, the Phase II solvency rules include {count} numbered rule files, "
            f"running from Rule {first_no} to Rule {last_no}.[1] Knowledge_Base_MarkDown/manifest.json"
        )
        summary_lines = [
            f"The manifest contains {count} rule files.",
            f"Rule numbers range from {first_no} to {last_no}.",
        ]

    return {
        "mode": "catalog",
        "answer": answer,
        "hits": _build_manifest_hit(sample_entries, summary_lines),
        "sub_queries": [question],
        "executed_queries": ["manifest:rules:count"],
        "iterations": 0,
        "reflection_notes": ["Answered from manifest metadata instead of vector retrieval."],
        "retrieval_history": [],
    }


def try_answer_catalog_query(question: str, *, language: str = DEFAULT_LANGUAGE) -> dict[str, Any] | None:
    return _answer_rule_count_question(question, language=language)


@retry_with_exponential_backoff(max_retries=3, initial_delay=1.0)
def _create_embedding(client: OpenAI, text: str) -> list[float]:
    """Create embedding with retry logic."""
    return client.embeddings.create(model=EMB_MODEL, input=[text]).data[0].embedding


@retry_with_exponential_backoff(max_retries=3, initial_delay=2.0)
def _create_chat_completion(
    client: OpenAI,
    messages: list[dict],
    temperature: float = 0.2,
    *,
    model: str | None = None,
) -> str:
    """Create chat completion with retry logic."""
    response = client.chat.completions.create(
        model=model or MODEL,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def _estimate_text_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))


def _invoke_chat_completion(
    client: OpenAI,
    messages: list[dict],
    *,
    temperature: float = 0.2,
    model: str | None = None,
) -> str:
    if model:
        return _create_chat_completion(client, messages, temperature=temperature, model=model)
    return _create_chat_completion(client, messages, temperature=temperature)


def rewrite_question_with_history(
    client: OpenAI,
    question: str,
    history: str | None,
    *,
    model: str | None = None,
) -> str:
    if not history or not question.strip():
        return question
    if not _question_needs_history_context(question):
        return question

    messages = [
        {
            "role": "system",
            "content": (
                "You rewrite the latest user message into a standalone retrieval question for a grounded regulatory QA system. "
                "Return JSON only in the form {\"question\": \"...\"}. "
                "Preserve the user's language, domain terms, rule numbers, formulas, comparisons, and requested scope. "
                "Resolve pronouns and omitted references using the prior conversation. "
                "Do not answer the question and do not add unsupported assumptions."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Prior conversation:\n{history}\n\n"
                f"Latest user question:\n{question}\n\n"
                "Return JSON only."
            ),
        },
    ]

    try:
        payload = extract_json_payload(_invoke_chat_completion(client, messages, temperature=0.0, model=model))
    except Exception:
        return question

    if isinstance(payload, dict):
        rewritten = str(payload.get("question", "")).strip()
        return rewritten or question

    return question


def _question_needs_history_context(question: str) -> bool:
    """Return True when a question looks like a context-dependent follow-up turn."""

    normalized = question.strip().lower()
    if not normalized:
        return False

    context_dependent_prefixes = (
        "那",
        "那它",
        "那这个",
        "那这些",
        "它",
        "这个",
        "这些",
        "该",
        "其",
        "前者",
        "后者",
        "再",
        "继续",
        "另外",
        "还有",
        "那么",
        "then",
        "what about",
        "how about",
        "and ",
        "also ",
        "what else",
        "compare that",
    )
    context_dependent_terms = (
        "它",
        "这个",
        "这些",
        "那个",
        "上述",
        "上面",
        "前面",
        "刚才",
        "之前",
        "前者",
        "后者",
        "该规则",
        "该要求",
    )
    context_dependent_patterns = (
        r"\bthat\b",
        r"\bthose\b",
        r"\bthem\b",
        r"\bit\b",
        r"\bthis\b",
        r"\bthese\b",
        r"\bformer\b",
        r"\blatter\b",
        r"\babove\b",
        r"\bprevious\b",
        r"\bearlier\b",
    )
    standalone_patterns = (
        r"规则第\d+号",
        r"附件\d+(?:-\d+)?",
        r"第\d+号",
    )

    if normalized.startswith(context_dependent_prefixes):
        return True
    has_standalone_pattern = any(re.search(pattern, normalized) for pattern in standalone_patterns)
    if has_standalone_pattern:
        return False
    if any(term in normalized for term in context_dependent_terms) or any(
        re.search(pattern, normalized) for pattern in context_dependent_patterns
    ):
        return True
    return False


def _hit_token_count(hit: dict[str, Any]) -> int:
    token_count = hit.get("token_count")
    if isinstance(token_count, int) and token_count > 0:
        return token_count
    return _estimate_text_tokens(str(hit.get("text", "")))


def prepare_answer_hits(
    question: str,
    hits: list[dict],
    *,
    max_context_tokens: int = DEFAULT_DOC_CONTEXT_TOKENS,
    section_context_tokens: int = DEFAULT_SECTION_CONTEXT_TOKENS,
) -> list[dict]:
    if not hits:
        return []

    def select_hits_with_budget(items: list[dict], budget: int, max_hits: int | None = None) -> list[dict]:
        selected: list[dict] = []
        total_tokens = 0
        for hit in items:
            hit_tokens = _hit_token_count(hit)
            if selected and total_tokens + hit_tokens > budget:
                continue
            selected.append(hit)
            total_tokens += hit_tokens
            if total_tokens >= budget:
                break
            if max_hits is not None and len(selected) >= max_hits:
                break
        return selected

    doc_hits = rerank_hits(
        question,
        [hit for hit in hits if hit.get("source_kind") != "section"],
        top_k=len([hit for hit in hits if hit.get("source_kind") != "section"]),
    )
    section_hits = rerank_hits(
        question,
        [hit for hit in hits if hit.get("source_kind") == "section"],
        top_k=len([hit for hit in hits if hit.get("source_kind") == "section"]),
    )

    if section_hits and doc_hits:
        selected = select_hits_with_budget(doc_hits, max_context_tokens, max_hits=3)
        selected.extend(select_hits_with_budget(section_hits, section_context_tokens, max_hits=6))
        if selected:
            return rerank_hits(question, selected, top_k=len(selected))

    prioritized = section_hits or doc_hits
    budget = section_context_tokens if section_hits and not doc_hits else max_context_tokens
    selected = select_hits_with_budget(prioritized, budget)
    if selected:
        return selected
    return prioritized[:1]


def _search_hits(
    question: str,
    query_vec: list[float],
    index: Any,
    docs: list[dict],
    *,
    k: int,
    similarity_threshold: float,
    include_direct_matches: bool = True,
) -> list[dict]:
    query_array = np.array([query_vec], dtype="float32")
    faiss.normalize_L2(query_array)

    search_k = min(len(docs), max(k, max(k * 4, 12)))
    distances, indices = index.search(query_array, search_k)

    results = []
    for score, item_index in zip(distances[0], indices[0]):
        if 0 <= item_index < len(docs) and score >= similarity_threshold:
            results.append({**docs[item_index], "retrieval_score": float(score)})

    if include_direct_matches:
        seen = {(item["path"], item["text"]): index for index, item in enumerate(results)}
        for hit in _collect_filename_match_hits(question, docs):
            key = (hit["path"], hit["text"])
            if key in seen:
                results[seen[key]]["retrieval_score"] = max(
                    float(results[seen[key]].get("retrieval_score", 0.0)),
                    float(hit.get("retrieval_score", 0.0)),
                )
                continue
            seen[key] = len(results)
            results.append(hit)

    return rerank_hits(question, results, top_k=k)


def retrieve_documents(
    client: OpenAI,
    question: str,
    *,
    query_vec: list[float] | None = None,
    k: int = DEFAULT_TOP_K,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict]:
    index, docs = _load_artifacts()
    query_vec = query_vec or _create_embedding(client, question)
    return _search_hits(
        question,
        query_vec,
        index,
        docs,
        k=k,
        similarity_threshold=similarity_threshold,
        include_direct_matches=True,
    )


def retrieve_sections(
    client: OpenAI,
    question: str,
    *,
    query_vec: list[float] | None = None,
    k: int = DEFAULT_TOP_K,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict]:
    global _SECTION_INDEX_CACHE, _SECTION_DOCS_CACHE, _SECTION_CACHE_PATHS
    index, docs = _load_section_artifacts(required=False)
    if index is None or not docs:
        return []
    query_vec = query_vec or _create_embedding(client, question)
    try:
        return _search_hits(
            question,
            query_vec,
            index,
            docs,
            k=k,
            similarity_threshold=similarity_threshold,
            include_direct_matches=True,
        )
    except AssertionError:
        # If a stale or incompatible section index is configured, fall back to
        # document retrieval instead of failing the whole answer pipeline.
        _SECTION_INDEX_CACHE = None
        _SECTION_DOCS_CACHE = None
        _SECTION_CACHE_PATHS = None
        return []


def merge_retrieval_hits(
    question: str,
    document_hits: list[dict],
    section_hits: list[dict],
    *,
    top_k: int,
) -> list[dict]:
    combined: list[dict] = []
    seen: dict[tuple[str, str], int] = {}

    for hit in [*document_hits, *section_hits]:
        key = (str(hit.get("path", "")), str(hit.get("text", "")))
        if key in seen:
            existing = combined[seen[key]]
            existing["retrieval_score"] = max(
                float(existing.get("retrieval_score", 0.0)),
                float(hit.get("retrieval_score", 0.0)),
            )
            continue
        seen[key] = len(combined)
        combined.append(hit)

    return rerank_hits(question, combined, top_k=min(top_k, len(combined)))


def retrieve(
    client: OpenAI,
    question: str,
    k: int = DEFAULT_TOP_K,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
):
    """
    Retrieve relevant evidence using a hybrid document/section strategy.
    """

    strategy = classify_retrieval_strategy(question)
    query_vec = _create_embedding(client, question)

    if strategy == "document":
        return retrieve_documents(
            client,
            question,
            query_vec=query_vec,
            k=max(4, k),
            similarity_threshold=similarity_threshold,
        )

    if strategy == "section":
        section_hits = retrieve_sections(
            client,
            question,
            query_vec=query_vec,
            k=max(6, k * 2),
            similarity_threshold=similarity_threshold,
        )
        document_hits = retrieve_documents(
            client,
            question,
            query_vec=query_vec,
            k=2,
            similarity_threshold=similarity_threshold,
        )
        if not section_hits:
            return document_hits[:k]
        return merge_retrieval_hits(question, document_hits[:1], section_hits, top_k=max(6, k * 2))

    document_hits = retrieve_documents(
        client,
        question,
        query_vec=query_vec,
        k=max(4, k),
        similarity_threshold=similarity_threshold,
    )
    section_hits = retrieve_sections(
        client,
        question,
        query_vec=query_vec,
        k=max(6, k * 2),
        similarity_threshold=similarity_threshold,
    )
    if not section_hits:
        return document_hits[:k]
    return merge_retrieval_hits(question, document_hits[:3], section_hits[:6], top_k=max(8, k * 2))


def render_context(hits: list[dict]) -> str:
    formatted = []
    for index, hit in enumerate(hits, start=1):
        header = hit["path"]
        if hit.get("source_kind") == "section":
            header += f" | {hit.get('section_heading', 'Section')}"
        formatted.append(f"[{index}] {header}\n{hit['text']}")
    return "\n\n".join(formatted)


def answer_from_hits(
    client: OpenAI,
    question: str,
    hits: list[dict],
    *,
    language: str = DEFAULT_LANGUAGE,
    history: str | None = None,
    interpreted_question: str | None = None,
    hits_prepared: bool = False,
    model: str | None = None,
) -> str:
    if not hits:
        return INSUFFICIENT_INFO_RESPONSE
    answer_hits = hits if hits_prepared else prepare_answer_hits(interpreted_question or question, hits)
    if not answer_hits:
        return INSUFFICIENT_INFO_RESPONSE

    messages = [
        {"role": "system", "content": get_system_prompt(language)},
        {
            "role": "user",
            "content": format_user_prompt(
                question,
                render_context(answer_hits),
                history,
                interpreted_question=interpreted_question,
            ),
        },
    ]
    return _invoke_chat_completion(client, messages, model=model)


def run_standard_query(
    client: OpenAI,
    question: str,
    *,
    language: str = DEFAULT_LANGUAGE,
    history: str | None = None,
    model: str | None = None,
    k: int = DEFAULT_TOP_K,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    standalone_question = rewrite_question_with_history(client, question, history, model=model)
    hits = retrieve(client, standalone_question, k=k, similarity_threshold=similarity_threshold)
    answer_hits = prepare_answer_hits(standalone_question, hits)
    answer = answer_from_hits(
        client,
        question,
        answer_hits,
        language=language,
        history=history,
        interpreted_question=standalone_question,
        hits_prepared=True,
        model=model,
    )
    return {
        "mode": "standard",
        "answer": answer,
        "hits": answer_hits,
        "sub_queries": [standalone_question],
        "executed_queries": [standalone_question] if answer_hits else [],
        "iterations": 1 if answer_hits else 0,
        "reflection_notes": [],
        "retrieval_history": [],
    }


def run_agentic_query(
    client: OpenAI,
    question: str,
    *,
    language: str = DEFAULT_LANGUAGE,
    history: str | None = None,
    model: str | None = None,
    k: int = 4,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> dict[str, Any]:
    standalone_question = rewrite_question_with_history(client, question, history, model=model)
    engine = AgenticRagEngine(
        chat_fn=lambda messages, temperature=0.2: _invoke_chat_completion(
            client,
            messages,
            temperature=temperature,
            model=model,
        ),
        retrieve_fn=lambda query, round_k, threshold: retrieve(
            client,
            query,
            k=round_k,
            similarity_threshold=threshold,
        ),
        synthesize_fn=lambda prompt_question, hits, response_language, conversation_history: answer_from_hits(
            client,
            question,
            hits,
            language=response_language,
            history=conversation_history,
            interpreted_question=prompt_question,
            hits_prepared=True,
            model=model,
        ),
        language=language,
        max_iterations=max_iterations,
        top_k=k,
        similarity_threshold=similarity_threshold,
        synthesis_top_k=int(DEFAULT_SYNTHESIS_TOP_K) if DEFAULT_SYNTHESIS_TOP_K else max(k, min(10, k * 2)),
    )
    result = engine.run(standalone_question, history=history)
    answer_hits = prepare_answer_hits(standalone_question, result.hits)
    return {
        "mode": "agentic",
        "answer": result.answer,
        "hits": answer_hits,
        "sub_queries": result.sub_queries,
        "executed_queries": result.executed_queries,
        "iterations": result.iterations,
        "reflection_notes": result.reflection_notes,
        "retrieval_history": result.retrieval_history,
    }


def run_query(
    client: OpenAI,
    question: str,
    *,
    mode: str = DEFAULT_MODE,
    language: str = DEFAULT_LANGUAGE,
    history: str | None = None,
    model: str | None = None,
    k: int = DEFAULT_TOP_K,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> dict[str, Any]:
    catalog_answer = try_answer_catalog_query(question, language=language)
    if catalog_answer is not None:
        return catalog_answer

    if mode == "standard":
        return run_standard_query(
            client,
            question,
            language=language,
            history=history,
            model=model,
            k=k,
            similarity_threshold=similarity_threshold,
        )
    return run_agentic_query(
        client,
        question,
        language=language,
        history=history,
        model=model,
        k=k,
        similarity_threshold=similarity_threshold,
        max_iterations=max_iterations,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Query the solvency regulation knowledge base.")
    parser.add_argument("question", nargs="?", help="Question to ask the knowledge base")
    parser.add_argument(
        "--mode",
        choices=["standard", "agentic"],
        default=DEFAULT_MODE if DEFAULT_MODE in {"standard", "agentic"} else "agentic",
        help="Retrieval mode to use",
    )
    parser.add_argument(
        "--language",
        choices=["en", "zh"],
        default=DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in {"en", "zh"} else "en",
        help="Output language for the final answer",
    )
    parser.add_argument("--k", type=int, default=DEFAULT_TOP_K, help="Top-k results for retrieval")
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help="Minimum cosine similarity score to keep a retrieved chunk",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help="Maximum retrieval rounds in agentic mode",
    )
    parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Print planner, retrieval, and reflection trace after the answer",
    )
    return parser.parse_args()


def _print_trace(result: dict[str, Any]) -> None:
    if result.get("mode") != "agentic":
        return

    print("\n=== Agentic Trace ===")
    print(f"Sub-queries: {result.get('sub_queries', [])}")
    print(f"Executed queries: {result.get('executed_queries', [])}")
    print(f"Iterations: {result.get('iterations', 0)}")

    retrieval_history = result.get("retrieval_history", [])
    if retrieval_history:
        print("Retrieval history:")
        for entry in retrieval_history:
            print(
                f"- iteration {entry['iteration']}: {entry['query']} "
                f"(new_hits={entry['new_hits']}, paths={entry['paths']})"
            )

    reflection_notes = result.get("reflection_notes", [])
    if reflection_notes:
        print("Reflection notes:")
        for note in reflection_notes:
            print(f"- {note}")


def main():
    args = parse_args()
    if not args.question:
        print('Usage: python scripts/ask.py "your question"')
        sys.exit(1)

    client = OpenAI()

    try:
        result = run_query(
            client,
            args.question,
            mode=args.mode,
            language=args.language,
            k=args.k,
            similarity_threshold=args.similarity_threshold,
            max_iterations=args.max_iterations,
        )
        print(result["answer"])
        if args.show_trace:
            _print_trace(result)
    except FileNotFoundError as error:
        print(f"Error: {error}")
        print("Please run 'make index' or 'python scripts/build_index.py' first.")
        sys.exit(1)
    except Exception as error:  # noqa: BLE001 - surface the failure for CLI callers
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
