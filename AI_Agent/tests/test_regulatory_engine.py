from __future__ import annotations

import json
import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import regulatory_engine as engine_module


def _entry(
    *,
    doc_id: str,
    path: str,
    title: str,
    category: str,
    aliases: tuple[str, ...],
    summary_short: str,
    summary_structured: str,
    keywords: tuple[str, ...],
):
    return engine_module.CatalogEntry(
        doc_id=doc_id,
        path=path,
        title=title,
        category=category,
        source_type=".md",
        publish_date="",
        aliases=aliases,
        headings=("第一章 总则",),
        summary_short=summary_short,
        summary_structured=summary_structured,
        keywords=keywords,
    )


def test_search_titles_prefers_rule_number_match(monkeypatch):
    monkeypatch.setattr(
        engine_module,
        "load_catalog",
        lambda: (
            _entry(
                doc_id="rules/rule-2.md",
                path="Knowledge_Base_MarkDown/rules/rule-2.md",
                title="保险公司偿付能力监管规则第2号：最低资本",
                category="rules",
                aliases=("规则第2号", "第2号规则"),
                summary_short="最低资本规则。",
                summary_structured="标题：规则第2号\n内容摘要：最低资本规则。",
                keywords=("规则第2号", "最低资本"),
            ),
            _entry(
                doc_id="rules/rule-4.md",
                path="Knowledge_Base_MarkDown/rules/rule-4.md",
                title="保险公司偿付能力监管规则第4号：保险风险最低资本（非寿险业务）",
                category="rules",
                aliases=("规则第4号",),
                summary_short="非寿险最低资本。",
                summary_structured="标题：规则第4号\n内容摘要：非寿险最低资本。",
                keywords=("规则第4号", "非寿险"),
            ),
        ),
    )

    hits = engine_module.search_titles("规则第2号主要内容", limit=2)

    assert hits[0]["title"] == "保险公司偿付能力监管规则第2号：最低资本"
    assert "规则编号命中" in hits[0]["reason"]


def test_plan_regulatory_query_uses_title_hits_for_scoped_queries(monkeypatch):
    monkeypatch.setattr(
        engine_module,
        "search_titles",
        lambda query, limit=5: [
            {
                "doc_id": "rules/rule-2.md",
                "path": "Knowledge_Base_MarkDown/rules/rule-2.md",
                "title": "保险公司偿付能力监管规则第2号：最低资本",
                "category": "rules",
                "score": 220.0,
                "reason": "规则编号命中：第2号",
                "summary_short": "最低资本规则。",
                "aliases": ("规则第2号",),
            }
        ],
    )
    monkeypatch.setattr(
        engine_module,
        "search_summaries",
        lambda query, limit=5, doc_ids=None: [
            {
                "doc_id": "rules/rule-2.md",
                "path": "Knowledge_Base_MarkDown/rules/rule-2.md",
                "title": "保险公司偿付能力监管规则第2号：最低资本",
                "category": "rules",
                "score": 100.0,
                "reason": "摘要层直接覆盖查询",
                "summary_short": "最低资本规则。",
                "aliases": ("规则第2号",),
            }
        ],
    )

    plan = engine_module.plan_regulatory_query("规则第2号主要内容是什么")

    assert plan["question_type"] == "summary"
    assert plan["retrieval_strategy"] == "title-summary-document"
    assert "保险公司偿付能力监管规则第2号：最低资本" in plan["scoped_queries"]


def test_detect_question_type_recognizes_formula_query():
    assert engine_module.detect_question_type("规则第2号的计算公式是什么") == "formula"


def test_load_catalog_prefers_ready_data_artifact(tmp_path, monkeypatch):
    ready_data_root = tmp_path / "ready_data"
    ready_data_root.mkdir(parents=True)
    doc_catalog = ready_data_root / "doc_catalog.jsonl"
    doc_catalog.write_text(
        json.dumps(
            {
                "doc_id": "rules/rule-2.md",
                "path": "Knowledge_Base_MarkDown/rules/rule-2.md",
                "title": "保险公司偿付能力监管规则第2号：最低资本",
                "category": "rules",
                "source_type": ".pdf",
                "publish_date": "",
                "aliases": ["规则第2号"],
                "summary_short": "最低资本规则。",
                "summary_structured": "标题：规则第2号",
                "headings": ["第一章 总则"],
                "keywords": ["最低资本"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(engine_module, "DOC_CATALOG_PATH", doc_catalog, raising=False)
    monkeypatch.setattr(engine_module, "MANIFEST_PATH", tmp_path / "missing.json", raising=False)
    engine_module.refresh_catalog()

    entries = engine_module.load_catalog()

    assert len(entries) == 1
    assert entries[0].doc_id == "rules/rule-2.md"
    assert entries[0].summary_short == "最低资本规则。"
