from __future__ import annotations

import json
import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import ask as ask_module


def test_try_answer_catalog_query_counts_numbered_rules(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    manifest_entries = [
        {
            "path": "rules/\u4fdd\u9669\u516c\u53f8\u507f\u4ed8\u80fd\u529b\u76d1\u7ba1\u89c4\u5219\u7b2c1\u53f7\uff1a\u5b9e\u9645\u8d44\u672c.md",
            "title": "\u4fdd\u9669\u516c\u53f8\u507f\u4ed8\u80fd\u529b\u76d1\u7ba1\u89c4\u5219\u7b2c1\u53f7\uff1a\u5b9e\u9645\u8d44\u672c",
            "category": "rules",
        },
        {
            "path": "rules/\u4fdd\u9669\u516c\u53f8\u507f\u4ed8\u80fd\u529b\u76d1\u7ba1\u89c4\u5219\u7b2c2\u53f7\uff1a\u6700\u4f4e\u8d44\u672c.md",
            "title": "\u4fdd\u9669\u516c\u53f8\u507f\u4ed8\u80fd\u529b\u76d1\u7ba1\u89c4\u5219\u7b2c2\u53f7\uff1a\u6700\u4f4e\u8d44\u672c",
            "category": "rules",
        },
        {
            "path": "rules/\u4fdd\u9669\u516c\u53f8\u507f\u4ed8\u80fd\u529b\u76d1\u7ba1\u89c4\u5219\u7b2c20\u53f7\uff1a\u52b3\u5408\u793e\u4fdd\u9669\uff08\u4e2d\u56fd\uff09\u6709\u9650\u516c\u53f8.md",
            "title": "\u4fdd\u9669\u516c\u53f8\u507f\u4ed8\u80fd\u529b\u76d1\u7ba1\u89c4\u5219\u7b2c20\u53f7\uff1a\u52b3\u5408\u793e\u4fdd\u9669\uff08\u4e2d\u56fd\uff09\u6709\u9650\u516c\u53f8",
            "category": "rules",
        },
    ]
    manifest_path.write_text(json.dumps(manifest_entries, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(ask_module, "MANIFEST_PATH", manifest_path, raising=False)
    monkeypatch.setattr(ask_module, "_MANIFEST_CACHE", None, raising=False)

    result = ask_module.try_answer_catalog_query("\u4e8c\u671f\u89c4\u5219\u4e00\u5171\u6709\u591a\u5c11\u53f7\u89c4\u5b9a", language="zh")

    assert result is not None
    assert result["mode"] == "catalog"
    assert "\u5171\u6536\u5f55 3 \u9879" in result["answer"]
    assert "\u7b2c1\u53f7\u5230\u7b2c20\u53f7" in result["answer"]
    assert result["hits"][0]["path"] == "Knowledge_Base_MarkDown/manifest.json"


def test_run_query_prefers_catalog_answer_before_rag(monkeypatch):
    monkeypatch.setattr(
        ask_module,
        "try_answer_catalog_query",
        lambda question, language="zh": {
            "mode": "catalog",
            "answer": "catalog answer",
            "hits": [],
            "sub_queries": [question],
            "executed_queries": ["manifest"],
            "iterations": 0,
            "reflection_notes": [],
            "retrieval_history": [],
        },
        raising=False,
    )

    result = ask_module.run_query(client=object(), question="\u4e8c\u671f\u89c4\u5219\u4e00\u5171\u6709\u591a\u5c11\u53f7\u89c4\u5b9a")

    assert result["mode"] == "catalog"
    assert result["answer"] == "catalog answer"
