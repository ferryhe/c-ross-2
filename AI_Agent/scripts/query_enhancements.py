from __future__ import annotations

import re
from dataclasses import dataclass


TOKEN_PATTERN = re.compile(r"[\w-]+", flags=re.UNICODE)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "their",
    "these",
    "this",
    "to",
    "use",
    "what",
    "when",
    "which",
    "with",
}


@dataclass(frozen=True)
class DomainContext:
    planner_hint: str
    reflector_hint: str
    priority_terms: tuple[str, ...]


DOMAIN_RULES = (
    {
        "keywords": {
            "actuarial",
            "actuary",
            "insurance",
            "underwriting",
            "pricing",
            "reserve",
            "reserving",
            "claims",
            "mortality",
            "annuity",
            "pension",
            "solvency",
            "ifrs17",
        },
        "planner_hint": (
            "For actuarial and insurance questions, separate sub-queries across actuarial practice, "
            "insurance business process, model assumptions, and operational implications."
        ),
        "reflector_hint": (
            "Check whether the evidence covers actuarial context, insurance use case, material assumptions, "
            "and practical implementation consequences."
        ),
        "priority_terms": (
            "actuarial",
            "insurance",
            "underwriting",
            "pricing",
            "reserve",
            "pension",
            "mortality",
        ),
    },
    {
        "keywords": {
            "governance",
            "risk",
            "ethic",
            "ethics",
            "regulation",
            "regulatory",
            "compliance",
            "oversight",
            "audit",
            "accountability",
            "transparency",
            "bias",
            "fairness",
            "control",
            "controls",
        },
        "planner_hint": (
            "For governance, risk, ethics, or regulation questions, create sub-queries that separate framework, "
            "risk categories, controls, oversight responsibilities, and monitoring or audit expectations."
        ),
        "reflector_hint": (
            "Check whether the evidence covers governance responsibilities, risk or bias concerns, controls, "
            "transparency, and auditability."
        ),
        "priority_terms": (
            "governance",
            "risk",
            "ethics",
            "regulation",
            "compliance",
            "oversight",
            "audit",
            "transparency",
            "bias",
            "controls",
        ),
    },
    {
        "keywords": {
            "ai",
            "artificial",
            "intelligence",
            "machine",
            "learning",
            "model",
            "models",
            "llm",
            "generative",
            "federated",
            "interpretable",
            "explainable",
        },
        "planner_hint": (
            "For AI and model questions, prefer sub-queries that separate capability, limitations, deployment risks, "
            "and evaluation or validation guidance."
        ),
        "reflector_hint": (
            "Check whether the evidence covers the AI technique itself, limitations, validation expectations, "
            "and deployment or monitoring considerations."
        ),
        "priority_terms": (
            "ai",
            "model",
            "models",
            "machine",
            "learning",
            "generative",
            "validation",
            "monitoring",
        ),
    },
)


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text.lower())]


def _content_terms(text: str) -> list[str]:
    return [token for token in _tokenize(text) if len(token) > 2 and token not in STOPWORDS]


def build_domain_context(question: str) -> DomainContext:
    query_terms = _content_terms(question)
    query_term_set = set(query_terms)

    planner_hints = []
    reflector_hints = []
    priority_terms: list[str] = []

    for rule in DOMAIN_RULES:
        if not query_term_set.intersection(rule["keywords"]):
            continue
        planner_hints.append(rule["planner_hint"])
        reflector_hints.append(rule["reflector_hint"])
        priority_terms.extend(rule["priority_terms"])

    if not planner_hints:
        planner_hints.append(
            "Prefer sub-queries that separate the main topic, supporting evidence, implementation details, and constraints."
        )
    if not reflector_hints:
        reflector_hints.append(
            "Check whether the evidence covers the main topic, practical details, caveats, and any missing tradeoffs."
        )

    priority_terms.extend(query_terms[:8])
    deduped_terms = tuple(dict.fromkeys(priority_terms))
    return DomainContext(
        planner_hint=" ".join(planner_hints),
        reflector_hint=" ".join(reflector_hints),
        priority_terms=deduped_terms,
    )


def _normalize_semantic_scores(hits: list[dict]) -> list[float]:
    raw_scores = [float(hit.get("retrieval_score", 0.0)) for hit in hits]
    if not raw_scores:
        return []

    high = max(raw_scores)
    low = min(raw_scores)
    if high == low:
        return [1.0 for _ in raw_scores]
    return [(score - low) / (high - low) for score in raw_scores]


def rerank_hits(question: str, hits: list[dict], top_k: int) -> list[dict]:
    if len(hits) <= 1:
        return hits[:top_k]

    context = build_domain_context(question)
    query_terms = set(_content_terms(question))
    priority_terms = set(context.priority_terms)
    normalized_semantic_scores = _normalize_semantic_scores(hits)
    reranked = []

    for index, hit in enumerate(hits):
        text = str(hit.get("text", ""))
        path = str(hit.get("path", ""))
        doc_terms = set(_content_terms(f"{path} {text}"))
        path_terms = set(_content_terms(path.replace("/", " ")))

        lexical_overlap = len(query_terms & doc_terms) / max(1, len(query_terms))
        path_overlap = len(query_terms & path_terms) / max(1, len(query_terms))
        domain_overlap = len(priority_terms & doc_terms) / max(1, len(priority_terms))
        exact_phrase = 1.0 if question.lower() in f"{path} {text}".lower() else 0.0
        semantic = normalized_semantic_scores[index]
        score = (
            float(hit.get("retrieval_score", 0.0))
            + 0.35 * lexical_overlap
            + 0.15 * path_overlap
            + 0.20 * domain_overlap
            + 0.10 * exact_phrase
            + 0.10 * semantic
        )

        reranked.append(
            {
                **hit,
                "rerank_score": score,
                "domain_terms_matched": sorted(priority_terms & doc_terms),
            }
        )

    reranked.sort(
        key=lambda hit: (
            float(hit.get("rerank_score", 0.0)),
            float(hit.get("retrieval_score", 0.0)),
        ),
        reverse=True,
    )
    return reranked[:top_k]
