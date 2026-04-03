from __future__ import annotations

import json
import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import build_ready_data as ready_data_module


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_build_ready_data_outputs_expected_artifacts(tmp_path):
    source = tmp_path / "Knowledge_Base_MarkDown"
    rules_dir = source / "rules"
    attachments_dir = source / "attachments"
    rules_dir.mkdir(parents=True)
    attachments_dir.mkdir(parents=True)

    (attachments_dir / "附件4：压力测试情景.md").write_text(
        "---\n"
        "title: 附件4：压力测试情景\n"
        "category: attachments\n"
        "source_type: .pdf\n"
        "---\n\n"
        "# 附件4：压力测试情景\n\n"
        "列出压力测试情景。\n",
        encoding="utf-8",
    )

    (rules_dir / "保险公司偿付能力监管规则第2号：最低资本.md").write_text(
        "---\n"
        "title: 保险公司偿付能力监管规则第2号：最低资本\n"
        "category: rules\n"
        "source_type: .pdf\n"
        "---\n\n"
        "# 保险公司偿付能力监管规则第2号：最低资本\n\n"
        "## 第一章 总则\n\n"
        "第一条 最低资本由三部分组成，并可参考附件4。 \n\n"
        "## 第三章 计量方法\n\n"
        "第十五条 计算公式如下：\n\n"
        "$$\n"
        "\\mathrm{MC}^{*}=\\sqrt{\\mathrm{MC}^2+\\mathrm{LA}^2}\n"
        "$$\n\n"
        "| 项目 | 数值 |\n"
        "| --- | --- |\n"
        "| 系数 | 0.35 |\n",
        encoding="utf-8",
    )

    output_root = source / "ready_data"
    stats = ready_data_module.build_ready_data(source=source, output_root=output_root, section_max_tokens=200)

    assert stats["doc_count"] == 2
    assert (output_root / "doc_catalog.jsonl").exists()
    assert (output_root / "title_aliases.jsonl").exists()
    assert (output_root / "doc_summaries.jsonl").exists()
    assert (output_root / "sections_structured.jsonl").exists()
    assert (output_root / "formula_cards.jsonl").exists()
    assert (output_root / "relations_graph.json").exists()
    assert (output_root / "ready_data_manifest.json").exists()


def test_build_ready_data_generates_rule_aliases_and_formula_cards(tmp_path):
    source = tmp_path / "Knowledge_Base_MarkDown"
    rules_dir = source / "rules"
    rules_dir.mkdir(parents=True)

    (rules_dir / "保险公司偿付能力监管规则第2号：最低资本.md").write_text(
        "---\n"
        "title: 保险公司偿付能力监管规则第2号：最低资本\n"
        "category: rules\n"
        "---\n\n"
        "# 保险公司偿付能力监管规则第2号：最低资本\n\n"
        "第十五条 计算公式如下：\n\n"
        "$$\n"
        "\\mathrm{MC}^{*}=\\sqrt{\\mathrm{MC}^2+\\mathrm{LA}^2}\n"
        "$$\n",
        encoding="utf-8",
    )

    output_root = source / "ready_data"
    ready_data_module.build_ready_data(source=source, output_root=output_root, section_max_tokens=200)

    aliases = _read_jsonl(output_root / "title_aliases.jsonl")
    formulas = _read_jsonl(output_root / "formula_cards.jsonl")

    assert any(item["alias"] == "规则第2号" for item in aliases)
    assert formulas
    assert formulas[0]["doc_id"] == "rules/保险公司偿付能力监管规则第2号：最低资本.md"
    assert "MC" in "".join(formulas[0]["variables"])


def test_build_ready_data_generates_relation_edges(tmp_path):
    source = tmp_path / "Knowledge_Base_MarkDown"
    rules_dir = source / "rules"
    attachments_dir = source / "attachments"
    rules_dir.mkdir(parents=True)
    attachments_dir.mkdir(parents=True)

    (attachments_dir / "附件4：压力测试情景.md").write_text(
        "# 附件4：压力测试情景\n\n内容。\n",
        encoding="utf-8",
    )
    (rules_dir / "保险公司偿付能力监管规则第2号：最低资本.md").write_text(
        "# 保险公司偿付能力监管规则第2号：最低资本\n\n"
        "第一条 具体要求见附件4。\n",
        encoding="utf-8",
    )

    output_root = source / "ready_data"
    ready_data_module.build_ready_data(source=source, output_root=output_root, section_max_tokens=200)

    graph = json.loads((output_root / "relations_graph.json").read_text(encoding="utf-8"))
    assert any(edge["relation"] == "mentions_attachment" for edge in graph["edges"])
