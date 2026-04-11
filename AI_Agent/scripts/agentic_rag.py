from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

try:
    from .query_enhancements import build_domain_context, rerank_hits
    from .utils import extract_json_payload
except ImportError:
    from query_enhancements import build_domain_context, rerank_hits
    from utils import extract_json_payload


ChatFn = Callable[[list[dict], float], str]
RetrieveFn = Callable[[str, int, float], list[dict]]
SynthesizeFn = Callable[[str, list[dict], str, str | None], str]


@dataclass
class AgenticRagResult:
    question: str
    answer: str
    hits: list[dict]
    sub_queries: list[str]
    executed_queries: list[str]
    retrieval_history: list[dict]
    reflection_notes: list[str]
    iterations: int


def _normalize_queries(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []

    for value in values:
        if not isinstance(value, str):
            continue
        query = value.strip().strip("-").strip()
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(query)
        if len(normalized) >= limit:
            break

    return normalized


class AgenticRagEngine:
    def __init__(
        self,
        chat_fn: ChatFn,
        retrieve_fn: RetrieveFn,
        synthesize_fn: SynthesizeFn,
        *,
        language: str = "en",
        max_iterations: int = 2,
        max_sub_queries: int = 4,
        top_k: int = 4,
        similarity_threshold: float = 0.0,
        synthesis_top_k: int | None = None,
    ) -> None:
        self.chat_fn = chat_fn
        self.retrieve_fn = retrieve_fn
        self.synthesize_fn = synthesize_fn
        self.language = language
        self.max_iterations = max(1, max_iterations)
        self.max_sub_queries = max(1, max_sub_queries)
        self.top_k = max(1, top_k)
        self.similarity_threshold = similarity_threshold
        self.synthesis_top_k = (
            max(1, synthesis_top_k)
            if synthesis_top_k is not None
            else max(self.top_k, min(10, self.top_k * 2))
        )

    def _truncate(self, value: str, limit: int = 220) -> str:
        text = " ".join(value.split())
        if len(text) <= limit:
            return text
        return f"{text[:limit].rstrip()}..."

    def _plan_sub_queries(self, question: str) -> list[str]:
        domain_context = build_domain_context(question)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a retrieval planner for a grounded RAG system over Markdown documents. "
                    "Return JSON only in the form {\"sub_queries\": [\"...\"]}. "
                    "Produce 2-4 distinct retrieval-oriented sub-queries that together cover the question. "
                    "Do not answer the question. "
                    f"Domain guidance: {domain_context.planner_hint}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    "Rules:\n"
                    "- Use the same language as the question when possible.\n"
                    "- Preserve important domain terms and named standards.\n"
                    "- Make each sub-query searchable against a document corpus.\n"
                    f"- Domain focus: {domain_context.planner_hint}\n"
                    "- Return JSON only.\n"
                ),
            },
        ]

        try:
            payload = extract_json_payload(self.chat_fn(messages, 0.0))
            if isinstance(payload, dict):
                queries = payload.get("sub_queries", [])
            elif isinstance(payload, list):
                queries = payload
            else:
                queries = []
        except Exception:
            queries = []

        planned = _normalize_queries(queries, self.max_sub_queries)
        return planned or [question]

    def _build_evidence_summary(self, hits: list[dict], limit: int = 6) -> str:
        if not hits:
            return "- No evidence retrieved yet."

        lines = []
        for index, hit in enumerate(hits[:limit], start=1):
            path = hit.get("path", "unknown")
            preview = self._truncate(str(hit.get("text", "")))
            lines.append(f"[{index}] {path}: {preview}")
        return "\n".join(lines)

    def _reflect(
        self,
        question: str,
        executed_queries: list[str],
        hits: list[dict],
        iteration: int,
    ) -> tuple[str, list[str], str]:
        domain_context = build_domain_context(question)
        executed_lookup = {item.lower() for item in executed_queries}
        messages = [
            {
                "role": "system",
                "content": (
                    "You evaluate whether the current evidence is sufficient for a grounded RAG answer. "
                    "Return JSON only in the form "
                    "{\"decision\": \"continue\" | \"synthesize\", \"reason\": \"...\", \"additional_queries\": [\"...\"]}. "
                    "Choose \"continue\" only if a major aspect of the question is still missing. "
                    f"Domain guidance: {domain_context.reflector_hint}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original question: {question}\n"
                    f"Current iteration: {iteration} of {self.max_iterations}\n"
                    f"Executed queries: {executed_queries}\n"
                    "Current evidence:\n"
                    f"{self._build_evidence_summary(hits)}\n\n"
                    "Rules:\n"
                    "- If continuing, provide at most 2 concrete retrieval queries.\n"
                    "- If the evidence is already sufficient, choose synthesize.\n"
                    f"- Domain focus: {domain_context.reflector_hint}\n"
                    "- Return JSON only.\n"
                ),
            },
        ]

        fallback_reason = "Reflection fallback triggered; proceeding to synthesis."
        fallback_queries = (
            [question]
            if not hits and iteration < self.max_iterations and question.lower() not in executed_lookup
            else []
        )

        try:
            payload = extract_json_payload(self.chat_fn(messages, 0.0))
            if not isinstance(payload, dict):
                raise ValueError("Expected dict response")
            decision = str(payload.get("decision", "synthesize")).strip().lower()
            reason = str(payload.get("reason", "")).strip() or fallback_reason
            additional_queries = payload.get("additional_queries", [])
            queries = _normalize_queries(additional_queries, 2)
            if decision not in {"continue", "synthesize"}:
                decision = "synthesize"
            return decision, queries, reason
        except Exception:
            if fallback_queries:
                return "continue", fallback_queries, "Reflection failed; retrying with the original question."
            return "synthesize", [], "Reflection failed; proceeding to synthesis."

    def _select_hits_for_synthesis(self, question: str, hits: list[dict]) -> list[dict]:
        if not hits:
            return []
        capped_top_k = min(len(hits), self.synthesis_top_k)
        return rerank_hits(question, hits, top_k=capped_top_k)

    def run(self, question: str, history: str | None = None) -> AgenticRagResult:
        sub_queries = self._plan_sub_queries(question)
        executed_queries: list[str] = []
        retrieval_history: list[dict] = []
        reflection_notes: list[str] = []
        hits: list[dict] = []
        pending_queries = list(sub_queries)
        seen_hits: set[tuple[str, str]] = set()
        iterations = 0

        while pending_queries and iterations < self.max_iterations:
            current_round = _normalize_queries(pending_queries, self.max_sub_queries)
            pending_queries = []

            if not current_round:
                break

            iterations += 1
            for query in current_round:
                if query.lower() in {item.lower() for item in executed_queries}:
                    continue

                round_paths: list[str] = []
                new_hits = 0
                for hit in self.retrieve_fn(query, self.top_k, self.similarity_threshold):
                    path = str(hit.get("path", ""))
                    text = str(hit.get("text", ""))
                    dedupe_key = (path, text)
                    if dedupe_key in seen_hits:
                        continue
                    seen_hits.add(dedupe_key)
                    hits.append(hit)
                    round_paths.append(path)
                    new_hits += 1

                executed_queries.append(query)
                retrieval_history.append(
                    {
                        "iteration": iterations,
                        "query": query,
                        "new_hits": new_hits,
                        "paths": round_paths,
                    }
                )

            if iterations >= self.max_iterations:
                reflection_notes.append("Reached the configured iteration limit; moving to synthesis.")
                break

            decision, additional_queries, reason = self._reflect(
                question=question,
                executed_queries=executed_queries,
                hits=hits,
                iteration=iterations,
            )
            reflection_notes.append(reason)

            if decision != "continue":
                break

            executed_lookup = {item.lower() for item in executed_queries}
            pending_queries = [query for query in additional_queries if query.lower() not in executed_lookup]
            if not pending_queries:
                break

        final_hits = self._select_hits_for_synthesis(question, hits)
        answer = self.synthesize_fn(question, final_hits, self.language, history)
        return AgenticRagResult(
            question=question,
            answer=answer,
            hits=final_hits,
            sub_queries=sub_queries,
            executed_queries=executed_queries,
            retrieval_history=retrieval_history,
            reflection_notes=reflection_notes,
            iterations=iterations,
        )
