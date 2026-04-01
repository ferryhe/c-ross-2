from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

import api_server


client = TestClient(api_server.app)


def test_normalize_model_mode_falls_back_to_general():
    assert api_server._normalize_model_mode("general") == "general"
    assert api_server._normalize_model_mode("reasoning") == "reasoning"
    assert api_server._normalize_model_mode("invalid-mode") == "general"
    assert api_server._normalize_model_mode("") == "general"


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
    monkeypatch.setattr(api_server, "DEFAULT_MODEL_MODE", "general")

    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_model_mode"] == "general"
    assert payload["models"]["general"] == "gpt-4.1"
    assert payload["models"]["reasoning"] == "gpt-5.4-mini"


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
