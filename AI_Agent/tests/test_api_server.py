from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

import api_server


client = TestClient(api_server.app)


def test_normalize_model_mode_falls_back_to_reasoning():
    assert api_server._normalize_model_mode("general") == "general"
    assert api_server._normalize_model_mode("reasoning") == "reasoning"
    assert api_server._normalize_model_mode("invalid-mode") == "reasoning"
    assert api_server._normalize_model_mode("") == "reasoning"


def test_healthz_reports_service_flags(monkeypatch):
    monkeypatch.setattr(api_server, "_has_real_openai_api_key", lambda: True)
    monkeypatch.setattr(api_server, "_index_artifacts_ready", lambda: True)
    monkeypatch.setattr(api_server, "_frontend_built", lambda: True)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "has_api_key": True,
        "index_ready": True,
        "frontend_built": True,
    }


def test_get_config_returns_model_choices(monkeypatch):
    monkeypatch.setattr(api_server, "DEFAULT_GENERAL_MODEL", "gpt-4.1")
    monkeypatch.setattr(api_server, "DEFAULT_REASONING_MODEL", "gpt-5.4-mini")
    monkeypatch.setattr(api_server, "DEFAULT_MODEL_MODE", "reasoning")

    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_model_mode"] == "reasoning"
    assert payload["models"]["general"] == "gpt-4.1"
    assert payload["models"]["reasoning"] == "gpt-5.4-mini"


def test_get_engine_config_returns_capabilities(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "build_engine_config",
        lambda: {
            "engine_mode": "professional",
            "keeps_standalone_chatbot": True,
            "capabilities": ["title-search", "summary-search"],
        },
    )

    response = client.get("/api/engine/config")

    assert response.status_code == 200
    assert response.json()["engine_mode"] == "professional"
    assert response.json()["keeps_standalone_chatbot"] is True


def test_engine_title_search_endpoint_returns_catalog_hits(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "search_titles",
        lambda query, limit=5: [
            {
                "doc_id": "rules/rule-2.md",
                "path": "Knowledge_Base_MarkDown/rules/rule-2.md",
                "title": "规则第2号",
                "category": "rules",
                "score": 220.0,
                "reason": "规则编号命中",
                "summary_short": "最低资本相关规则。",
                "aliases": ["规则第2号", "第2号规则"],
            }
        ],
    )

    response = client.post("/api/engine/search/titles", json={"query": "规则第2号"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["hits"][0]["title"] == "规则第2号"
    assert payload["hits"][0]["aliases"] == ["规则第2号", "第2号规则"]


def test_engine_section_search_endpoint_returns_ready_data_hits(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "search_sections",
        lambda query, limit=5, doc_ids=None: [
            {
                "section_id": "rules/rule-2.md#section-1",
                "doc_id": "rules/rule-2.md",
                "title": "规则第2号",
                "text": "最低资本由三部分组成。",
                "score": 120.0,
            }
        ],
    )

    response = client.post(
        "/api/engine/search/sections",
        json={"query": "最低资本由哪些部分组成", "docId": "rules/rule-2.md"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["hits"][0]["section_id"] == "rules/rule-2.md#section-1"


def test_engine_formula_explain_endpoint_returns_formula_details(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "explain_formula",
        lambda query=None, formula_id=None: {
            "ok": True,
            "formula_id": formula_id,
            "variables": ["MC", "LA"],
        },
    )

    response = client.post(
        "/api/engine/explain/formula",
        json={"formulaId": "rules/rule-2.md#formula-1"},
    )

    assert response.status_code == 200
    assert response.json()["variables"] == ["MC", "LA"]


def test_engine_plan_endpoint_returns_scoped_queries(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "plan_regulatory_query",
        lambda question: {
            "question_type": "summary",
            "retrieval_strategy": "title-summary-document",
            "scoped_queries": [question, "保险公司偿付能力监管规则第2号：最低资本"],
            "recommended_paths": ["Knowledge_Base_MarkDown/rules/rule-2.md"],
            "title_hits": [
                {
                    "doc_id": "rules/rule-2.md",
                    "path": "Knowledge_Base_MarkDown/rules/rule-2.md",
                    "title": "规则第2号",
                    "category": "rules",
                    "score": 220.0,
                    "reason": "规则编号命中",
                    "summary_short": "最低资本相关规则。",
                    "aliases": ["规则第2号"],
                }
            ],
            "summary_hits": [],
        },
    )

    response = client.post(
        "/api/engine/plan",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "规则第2号主要内容是什么"}],
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question_type"] == "summary"
    assert payload["scoped_queries"][0] == "规则第2号主要内容是什么"
    assert payload["title_hits"][0]["path"] == "Knowledge_Base_MarkDown/rules/rule-2.md"


def test_engine_evidence_endpoint_returns_collected_evidence(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "collect_evidence",
        lambda question: {"question": question, "evidence": {"sections": [{"section_id": "s1"}]}},
    )

    response = client.post(
        "/api/engine/evidence",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "最低资本由哪些部分组成？"}],
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["evidence"]["sections"][0]["section_id"] == "s1"


def test_engine_answer_endpoint_returns_verified_answer(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "answer_verified",
        lambda question: {"mode": "verified", "answer": f"verified:{question}", "citations": []},
    )

    response = client.post(
        "/api/engine/answer",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "最低资本由哪些部分组成？"}],
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"].startswith("verified:")


def test_chat_endpoint_returns_answer_and_sources(monkeypatch):
    monkeypatch.setattr(api_server, "_has_real_openai_api_key", lambda: True)
    monkeypatch.setattr(api_server, "_index_artifacts_ready", lambda: True)
    monkeypatch.setattr(api_server, "_model_name_for_mode", lambda _: "gpt-5.4-mini")
    monkeypatch.setattr(api_server, "OpenAI", lambda: object())
    monkeypatch.setattr(
        api_server,
        "run_query",
        lambda *args, **kwargs: {
            "answer": "认可资产主要包括以下类别。[1]",
            "hits": [
                {
                    "path": "Knowledge_Base_MarkDown/rules/sample.md",
                    "text": "规则正文片段",
                    "source_kind": "section",
                    "section_heading": "第二章",
                }
            ],
        },
    )

    response = client.post(
        "/api/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "认可资产都包含哪些种类"}],
                }
            ],
            "modelMode": "reasoning",
            "language": "zh",
            "ragMode": "agentic",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "认可资产主要包括以下类别。[1]"
    assert payload["model"] == "gpt-5.4-mini"
    assert payload["model_mode"] == "reasoning"
    assert payload["sources"][0]["index"] == 1
    assert payload["sources"][0]["path"] == "Knowledge_Base_MarkDown/rules/sample.md"
    assert payload["sources"][0]["section_heading"] == "第二章"
    assert payload["sources"][0]["url"].startswith("https://github.com/")


def test_engine_chat_endpoint_returns_plan_and_answer(monkeypatch):
    monkeypatch.setattr(api_server, "_has_real_openai_api_key", lambda: True)
    monkeypatch.setattr(api_server, "_index_artifacts_ready", lambda: True)
    monkeypatch.setattr(api_server, "_model_name_for_mode", lambda _: "gpt-4.1")
    monkeypatch.setattr(api_server, "OpenAI", lambda: object())
    monkeypatch.setattr(
        api_server,
        "run_regulatory_query",
        lambda *args, **kwargs: {
            "answer": "规则第2号主要规定最低资本框架。[1]",
            "engine_mode": "professional",
            "hits": [
                {
                    "path": "Knowledge_Base_MarkDown/rules/rule-2.md",
                    "text": "规则第2号主要规定最低资本。",
                    "source_kind": "document",
                }
            ],
            "plan": {
                "question_type": "summary",
                "retrieval_strategy": "title-summary-document",
                "scoped_queries": ["规则第2号主要内容是什么", "规则第2号"],
                "recommended_paths": ["Knowledge_Base_MarkDown/rules/rule-2.md"],
                "title_hits": [
                    {
                        "doc_id": "rules/rule-2.md",
                        "path": "Knowledge_Base_MarkDown/rules/rule-2.md",
                        "title": "规则第2号",
                        "category": "rules",
                        "score": 220.0,
                        "reason": "规则编号命中",
                        "summary_short": "最低资本相关规则。",
                        "aliases": ["规则第2号"],
                    }
                ],
                "summary_hits": [],
            },
        },
    )

    response = client.post(
        "/api/engine/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "规则第2号主要内容是什么"}],
                }
            ],
            "modelMode": "general",
            "language": "zh",
            "ragMode": "agentic",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "规则第2号主要规定最低资本框架。[1]"
    assert payload["engine_mode"] == "professional"
    assert payload["question_type"] == "summary"
    assert payload["title_hits"][0]["title"] == "规则第2号"
    assert payload["recommended_paths"] == ["Knowledge_Base_MarkDown/rules/rule-2.md"]


def test_chat_endpoint_requires_last_user_message(monkeypatch):
    monkeypatch.setattr(api_server, "_has_real_openai_api_key", lambda: True)
    monkeypatch.setattr(api_server, "_index_artifacts_ready", lambda: True)

    response = client.post(
        "/api/chat",
        json={
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "先前回答"}],
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "last message" in response.json()["detail"]
