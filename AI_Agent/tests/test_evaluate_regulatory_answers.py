from __future__ import annotations

import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import evaluate_regulatory_answers as eval_module


def test_run_evaluation_collects_professional_and_agentic_results(monkeypatch):
    monkeypatch.setattr(eval_module, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(eval_module, "OpenAI", lambda: object())
    monkeypatch.setattr(
        eval_module,
        "_run_professional_engine",
        lambda client, question, model: {
            "answer": f"professional:{question}",
            "mode": "regulatory-engine",
            "engine_mode": "professional",
            "question_type": "analysis",
            "retrieval_strategy": "summary-hybrid",
            "exact_scope_doc_ids": [],
            "scoped_queries": [question],
            "recommended_paths": [],
            "title_hits": [],
            "summary_hits": [],
            "hits": [],
        },
    )
    monkeypatch.setattr(
        eval_module,
        "_run_agentic_chatbot",
        lambda client, question, model: {
            "answer": f"agentic:{question}",
            "mode": "agentic",
            "sub_queries": [question],
            "executed_queries": [question],
            "iterations": 1,
            "hits": [],
        },
    )

    report = eval_module.run_evaluation("gpt-5.4-mini", compare_agentic=True)

    assert report["model"] == "gpt-5.4-mini"
    assert report["compare_agentic"] is True
    assert report["case_count"] == len(eval_module.DEFAULT_CASES)
    assert report["cases"][0]["professional_engine"]["mode"] == "regulatory-engine"
    assert report["cases"][0]["agentic_chatbot"]["mode"] == "agentic"
