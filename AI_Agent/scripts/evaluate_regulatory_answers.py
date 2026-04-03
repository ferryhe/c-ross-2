from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ask import run_query
from scripts.project_config import load_project_env
from scripts.regulatory_engine import run_regulatory_query


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "eval"
DEFAULT_CASES = (
    {
        "case_id": "rule_count",
        "question": "偿二代二期监管规则一共有多少号规定？",
        "goal": "验证 manifest/catalog 类问题能直接回答。",
    },
    {
        "case_id": "rule2_overview",
        "question": "保险公司偿付能力监管规则第2号主要涉及什么内容？",
        "goal": "验证编号命中后的标题定位、摘要缩圈和整体概述能力。",
    },
    {
        "case_id": "minimum_capital_components",
        "question": "最低资本由哪些部分组成？",
        "goal": "验证规则核心结论型问题是否能直接回答。",
    },
    {
        "case_id": "rule2_formula",
        "question": "规则第2号里最低资本的计算公式是什么？请解释变量含义。",
        "goal": "验证公式检索、公式解释和变量说明能力。",
    },
    {
        "case_id": "attachment4_summary",
        "question": "附件4是什么，主要包含什么内容？",
        "goal": "验证附件定位和附件摘要能力。",
    },
    {
        "case_id": "control_risk_relation",
        "question": "控制风险最低资本按照哪一项规则计量？",
        "goal": "验证跨规则关系回答能力。",
    },
)


def _json_safe_hits(hits: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    safe_hits: list[dict[str, Any]] = []
    for hit in hits[:limit]:
        safe_hits.append(
            {
                "path": hit.get("path"),
                "source_kind": hit.get("source_kind"),
                "section_heading": hit.get("section_heading"),
                "article_no": hit.get("article_no"),
                "retrieval_score": hit.get("retrieval_score"),
                "text_preview": str(hit.get("text", "")).strip()[:240],
            }
        )
    return safe_hits


def _run_professional_engine(client: OpenAI, question: str, model: str) -> dict[str, Any]:
    result = run_regulatory_query(
        client,
        question,
        language="zh",
        history=None,
        model=model,
        k=4,
    )
    plan = result.get("plan", {})
    return {
        "answer": result.get("answer"),
        "mode": result.get("mode"),
        "engine_mode": result.get("engine_mode"),
        "question_type": plan.get("question_type"),
        "retrieval_strategy": plan.get("retrieval_strategy"),
        "exact_scope_doc_ids": plan.get("exact_scope_doc_ids", []),
        "scoped_doc_ids": plan.get("scoped_doc_ids", []),
        "scoped_queries": result.get("sub_queries", []),
        "recommended_paths": plan.get("recommended_paths", []),
        "title_hits": plan.get("title_hits", []),
        "summary_hits": plan.get("summary_hits", []),
        "hits": _json_safe_hits(result.get("hits", [])),
    }


def _run_agentic_chatbot(client: OpenAI, question: str, model: str) -> dict[str, Any]:
    result = run_query(
        client,
        question,
        mode="agentic",
        language="zh",
        history=None,
        model=model,
        k=4,
        max_iterations=2,
    )
    return {
        "answer": result.get("answer"),
        "mode": result.get("mode"),
        "sub_queries": result.get("sub_queries", []),
        "executed_queries": result.get("executed_queries", []),
        "iterations": result.get("iterations"),
        "hits": _json_safe_hits(result.get("hits", [])),
    }


def run_evaluation(model: str, *, compare_agentic: bool) -> dict[str, Any]:
    load_project_env(PROJECT_ROOT)
    client = OpenAI()
    cases: list[dict[str, Any]] = []

    for item in DEFAULT_CASES:
        question = str(item["question"])
        case_result = {
            "case_id": item["case_id"],
            "goal": item["goal"],
            "question": question,
            "professional_engine": _run_professional_engine(client, question, model),
        }
        if compare_agentic:
            case_result["agentic_chatbot"] = _run_agentic_chatbot(client, question, model)
        cases.append(case_result)

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "compare_agentic": compare_agentic,
        "case_count": len(cases),
        "cases": cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate regulatory answers with a real model.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Chat completion model to use")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path. Defaults to AI_Agent/eval/<model>-<timestamp>.json",
    )
    parser.add_argument(
        "--compare-agentic",
        action="store_true",
        help="Also evaluate the current standalone chatbot agentic mode",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_evaluation(args.model, compare_agentic=args.compare_agentic)
    output = args.output
    if output is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = DEFAULT_OUTPUT_DIR / f"{args.model}-{timestamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
